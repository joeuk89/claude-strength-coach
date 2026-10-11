"""A stateful fake Hevy server for tests: a transport that keeps writes in memory.

Seed it from a fixture set (`FakeHevy(SYNTHETIC)`) and pass it to
`HevyClient`, or patch `coach.hevy.transport.from_env` to return it so a
CLI command talks to it. It copies the Hevy behaviour the scripts must
survive: routine-level `notes` are dropped on write, a `null` set field is
a 400, more than `RAPID_WRITES` writes inside `RAPID_WINDOW_SECONDS` is a
429, and every write bumps the routine's `updated_at`.
"""

import copy
import uuid
from datetime import datetime, timedelta, timezone

from coach.hevy.transport import FixtureTransport, Response, TransportTimeout

RAPID_WRITES = 7
RAPID_WINDOW_SECONDS = 10
SET_FIELDS = ("type", "weight_kg", "reps", "distance_meters", "duration_seconds", "custom_metric", "rep_range")


class FakeClock:
    """Time that moves only when someone sleeps; `now()` and `sleep()` share it."""

    def __init__(self, start="2026-10-11T18:00:00Z"):
        self.current = datetime.fromisoformat(start.replace("Z", "+00:00"))
        self.slept = []

    def now(self):
        return self.current

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.current += timedelta(seconds=seconds)


def _ts(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _null_path(body):
    for e_index, exercise in enumerate((body.get("routine") or {}).get("exercises") or []):
        for s_index, item in enumerate(exercise.get("sets") or []):
            for key, value in item.items():
                if value is None:
                    return f'"routine.exercises[{e_index}].sets[{s_index}].{key}"'
    return None


class FakeHevy(FixtureTransport):
    def __init__(self, fixtures=None, clock=None):
        super().__init__(fixtures or "")
        self.clock = clock or FakeClock()
        self.requests = []
        self.writes = []
        self._failures = []
        self._write_times = []
        self._new_ids = 0

    @property
    def put_bodies(self):
        return [body for method, _, body in self.writes if method == "PUT"]

    def fail_next(self, status=None, body=None, exc=None, times=1):
        """Answer the next `times` requests with this status, or raise `exc` (e.g. TransportTimeout)."""
        for _ in range(times):
            self._failures.append((status, body, exc))

    def timeout_next(self, times=1):
        self.fail_next(exc=TransportTimeout("timed out"), times=times)

    def request(self, method, path, params=None, body=None, headers=None):
        self.requests.append({"method": method, "path": path, "params": dict(params or {}),
                              "body": copy.deepcopy(body), "headers": dict(headers or {})})
        if self._failures:
            status, fail_body, exc = self._failures.pop(0)
            if exc is not None:
                raise exc
            return Response(status, fail_body)
        if method == "GET":
            return super().request(method, path, params=params)
        if self._too_rapid():
            return Response(429, {"error": "Too many requests"})
        null_at = _null_path(body or {})
        if null_at:
            return Response(400, {"error": f"{null_at} Expected object, received null"})
        response = self._write(method, path, body or {})
        if response.status < 400:
            self.writes.append((method, path, copy.deepcopy(body)))
            self._write_times.append(self.clock.now())
        return response

    def _too_rapid(self):
        window_start = self.clock.now() - timedelta(seconds=RAPID_WINDOW_SECONDS)
        return sum(1 for moment in self._write_times if moment > window_start) >= RAPID_WRITES

    def _template_title(self, template_id):
        for template in self.collection("exercise_templates"):
            if template.get("id") == template_id:
                return template.get("title")
        return "Unknown exercise"

    def _stored_routine(self, request, existing):
        now = _ts(self.clock.now())
        exercises = []
        for e_index, exercise in enumerate(request.get("exercises") or []):
            sets = []
            for s_index, item in enumerate(exercise.get("sets") or []):
                stored = {"index": s_index}
                stored.update({field: item.get(field) for field in SET_FIELDS})
                sets.append(stored)
            exercises.append({
                "index": e_index,
                "title": self._template_title(exercise.get("exercise_template_id")),
                "rest_seconds": exercise.get("rest_seconds"),
                "notes": exercise.get("notes"),
                "exercise_template_id": exercise.get("exercise_template_id"),
                "superset_id": exercise.get("superset_id"),
                "sets": sets,
            })
        return {
            "id": existing["id"] if existing else self._new_id(),
            "title": request.get("title", existing.get("title") if existing else None),
            "folder_id": request.get("folder_id", existing.get("folder_id") if existing else None),
            "updated_at": now,
            "created_at": existing["created_at"] if existing else now,
            "exercises": exercises,
        }

    def _new_id(self):
        self._new_ids += 1
        return str(uuid.UUID(int=0xF0000000_0000_4000_8000_000000000000 + self._new_ids))

    def _write(self, method, path, body):
        routines = self.collection("routines")
        if method == "PUT" and path.startswith("/v1/routines/"):
            routine_id = path.rsplit("/", 1)[1]
            for position, existing in enumerate(routines):
                if existing.get("id") == routine_id:
                    routines[position] = self._stored_routine(body.get("routine") or {}, existing)
                    return Response(200, {"routine": copy.deepcopy(routines[position])})
            return Response(404, {"error": "Routine doesn't exist or doesn't belong to the user"})
        if method == "POST" and path == "/v1/routines":
            routine = self._stored_routine(body.get("routine") or {}, None)
            routines.append(routine)
            return Response(201, {"routine": copy.deepcopy(routine)})
        if method == "POST" and path == "/v1/routine_folders":
            folders = self.collection("routine_folders")
            folder_id = max([f.get("id", 0) for f in folders] + [0]) + 1
            now = _ts(self.clock.now())
            folder = {"id": folder_id, "index": len(folders),
                      "title": (body.get("routine_folder") or {}).get("title"),
                      "updated_at": now, "created_at": now}
            folders.append(folder)
            return Response(201, copy.deepcopy(folder))
        return Response(404, {"error": f"the fake does not handle {method} {path}"})
