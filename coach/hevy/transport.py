"""How a request reaches Hevy: over HTTPS, or replayed from fixture files.

A transport answers `request(method, path, params=, body=, headers=)` with
a `Response`, or raises `TransportTimeout` or `TransportUnreachable`. It
never retries, rate-limits or interprets status codes; the client does.
"""

import copy
import http.client
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from coach import __version__
from coach import dates

BASE_URL = "https://api.hevyapp.com"
TIMEOUT_SECONDS = 30
FIXTURES_ENV = "COACH_HEVY_FIXTURES"


@dataclass(frozen=True)
class Response:
    status: int
    body: object


class TransportTimeout(Exception):
    pass


class TransportUnreachable(Exception):
    pass


def _parse(raw):
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class UrllibTransport:
    def __init__(self, base_url=BASE_URL, timeout=TIMEOUT_SECONDS):
        self.base_url = base_url
        self.timeout = timeout

    def request(self, method, path, params=None, body=None, headers=None):
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        all_headers = {"accept": "application/json", "user-agent": f"coach/{__version__}"}
        all_headers.update(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            all_headers["content-type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=all_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as handle:
                return Response(handle.status, _parse(handle.read()))
        except urllib.error.HTTPError as exc:
            with exc:
                return Response(exc.code, _parse(exc.read()))
        except (socket.timeout, TimeoutError) as exc:
            raise TransportTimeout(str(exc)) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise TransportTimeout(str(exc.reason)) from None
            raise TransportUnreachable(str(exc.reason)) from None
        except (http.client.HTTPException, OSError) as exc:
            raise TransportUnreachable(str(exc) or type(exc).__name__) from None


# Collection endpoint -> (fixture file stem, response key, largest page size Hevy accepts).
COLLECTIONS = {
    "/v1/workouts": ("workouts", "workouts", 10),
    "/v1/workouts/events": ("workout_events", "events", 10),
    "/v1/routines": ("routines", "routines", 10),
    "/v1/routine_folders": ("routine_folders", "routine_folders", 10),
    "/v1/exercise_templates": ("exercise_templates", "exercise_templates", 100),
    "/v1/body_measurements": ("body_measurements", "body_measurements", 10),
}

# Single-item endpoint prefix -> (fixture file stem, id field, wrapper key or None).
ITEMS = {
    "/v1/workouts/": ("workouts", "id", None),
    "/v1/routines/": ("routines", "id", "routine"),
    "/v1/routine_folders/": ("routine_folders", "id", None),
    "/v1/exercise_templates/": ("exercise_templates", "id", None),
}


def event_time(event):
    if event.get("type") == "deleted":
        return event.get("deleted_at") or ""
    return (event.get("workout") or {}).get("updated_at") or ""


def _newest_first(stem, items):
    if stem == "workouts":
        return sorted(items, key=lambda w: w.get("start_time") or "", reverse=True)
    if stem == "workout_events":
        return sorted(items, key=event_time, reverse=True)
    return list(items)


class FixtureTransport:
    """Replays GET requests from fixture files; refuses every write.

    `directories` is one directory or several joined with os.pathsep; for
    each file, the last directory that has it wins. A fixture file holds
    one collection: {"x-synthetic": true, "<stem>": [...]}.
    """

    def __init__(self, directories):
        self.directories = [Path(part) for part in str(directories).split(os.pathsep) if part]
        self._loaded = {}

    def collection(self, stem):
        if stem not in self._loaded:
            items = []
            for directory in reversed(self.directories):
                path = directory / f"{stem}.json"
                if path.is_file():
                    items = json.loads(path.read_text(encoding="utf-8"))[stem]
                    break
            self._loaded[stem] = items
        return self._loaded[stem]

    def request(self, method, path, params=None, body=None, headers=None):
        if method != "GET":
            return Response(405, {"error": "the fixture transport replays GET requests only"})
        params = params or {}
        if path == "/v1/workouts/count":
            return Response(200, {"workout_count": len(self.collection("workouts"))})
        if path in COLLECTIONS:
            return self._page(path, params)
        for prefix, (stem, id_field, wrapper) in ITEMS.items():
            if path.startswith(prefix) and "/" not in path[len(prefix):]:
                wanted = path[len(prefix):]
                for item in self.collection(stem):
                    if str(item.get(id_field)) == wanted:
                        item = copy.deepcopy(item)
                        return Response(200, {wrapper: item} if wrapper else item)
                return Response(404, {"error": "Not found"})
        return Response(404, {"error": f"no fixture for {path}"})

    def _page(self, path, params):
        stem, key, max_size = COLLECTIONS[path]
        try:
            page = int(params.get("page", 1))
            size = int(params.get("pageSize", max_size))
        except (TypeError, ValueError):
            return Response(400, {"error": "Invalid page or pageSize"})
        if page < 1 or not 1 <= size <= max_size:
            return Response(400, {"error": "Invalid page size"})
        items = self.collection(stem)
        if stem == "workout_events":
            since = dates.parse_timestamp(params.get("since", "1970-01-01T00:00:00Z"))
            items = [e for e in items if dates.parse_timestamp(event_time(e)) > since]
        items = _newest_first(stem, items)
        page_count = -(-len(items) // size)
        chunk = copy.deepcopy(items[(page - 1) * size:page * size])
        return Response(200, {"page": page, "page_count": page_count, key: chunk})


def from_env(env):
    """The transport the environment asks for: fixtures when COACH_HEVY_FIXTURES is set."""
    fixtures = env.get(FIXTURES_ENV)
    if fixtures:
        return FixtureTransport(fixtures)
    return UrllibTransport()
