"""Helpers for activity-source tests: a Hevy cache built from a synthetic fixture set (C8, C15)."""

import json

from coach.hevy.cache import HevyCache


def write_hevy_cache(root, fixture_dir, pulled_at="2026-10-11T12:00:00Z"):
    """Write the C8 cache under root/.coach/cache/hevy from a fixture set, as a full pull at `pulled_at` would."""
    cache = HevyCache(root)
    counts = {}
    for name in ("routines", "routine_folders", "exercise_templates", "body_measurements"):
        path = fixture_dir / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))[name] if path.is_file() else []
        cache.write_collection(name, data, pulled_at)
        counts[name] = len(data)
    workouts = json.loads((fixture_dir / "workouts.json").read_text(encoding="utf-8"))["workouts"]
    for workout in workouts:
        cache.write_workout(workout, pulled_at)
    counts["workouts"] = len(workouts)
    cache.write_meta({"schema_version": 1, "last_pull_started_at": pulled_at, "last_pull_finished_at": pulled_at,
                      "last_full_pull_at": pulled_at, "events_since": pulled_at, "counts": counts})
    return cache


def write_program_state(root, routine_kinds):
    """A minimal C16 program and state mapping each Hevy routine id to a session of the given kind."""
    sessions, routines = [], {}
    for number, (routine_id, kind) in enumerate(sorted(routine_kinds.items()), start=1):
        session_id = f"session-{number}"
        sessions.append({"id": session_id, "title": session_id, "kind": kind, "tier": "core", "status": "active",
                         "location": None, "focus": None, "exercises": []})
        routines[routine_id] = {"session_id": session_id}
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "program.json").write_text(json.dumps({"schema_version": 1, "name": "test", "sessions": sessions}),
                                       encoding="utf-8")
    (data / "state.json").write_text(json.dumps({"schema_version": 1, "hevy": {"routines": routines}}),
                                     encoding="utf-8")
