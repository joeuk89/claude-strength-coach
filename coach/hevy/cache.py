"""The local Hevy cache under `.coach/cache/hevy/` (contract C8).

Each file wraps the raw API payload unchanged:
`{"schema_version": 1, "fetched_at": ts, "source": "hevy", "data": <raw>}`.
Readers return the raw payloads; an absent file reads as empty.
"""

import re
from datetime import date, datetime, timezone
from pathlib import Path

from coach import dates, jsonio, paths
from coach.errors import ValidationError

CACHE_VERSION = 1
FILE_SCHEMA = "hevy_cache_file"
META_SCHEMA = "hevy_cache_meta"
META = "meta.json"
WORKOUTS_DIR = "workouts"
COLLECTIONS = ("routines", "routine_folders", "exercise_templates", "body_measurements")
_SAFE_ID = re.compile(r"^[A-Za-z0-9-]+$")


def wrap(data, fetched_at):
    return {"schema_version": CACHE_VERSION, "fetched_at": fetched_at, "source": "hevy", "data": data}


def _since_moment(since):
    if isinstance(since, datetime):
        return since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    if isinstance(since, date):
        return datetime(since.year, since.month, since.day, tzinfo=timezone.utc)
    if len(since) == 10:
        day = dates.parse_date(since)
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return dates.parse_timestamp(since)


class HevyCache:
    def __init__(self, root, clock=None):
        self.root = Path(root)
        self.dir = self.root / paths.HEVY_CACHE_DIR
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def path(self, name):
        return self.dir / name

    def workout_path(self, workout_id):
        if not isinstance(workout_id, str) or not _SAFE_ID.fullmatch(workout_id):
            raise ValidationError(f"Hevy workout id {workout_id!r} is not a safe file name")
        return self.dir / WORKOUTS_DIR / f"{workout_id}.json"

    def read(self, name):
        """The wrapped document for a collection file name, or None when absent."""
        path = self.path(f"{name}.json")
        return jsonio.read_doc(path, FILE_SCHEMA) if path.is_file() else None

    def _data(self, name):
        doc = self.read(name)
        return doc["data"] if doc else []

    def meta(self):
        path = self.path(META)
        return jsonio.read_doc(path, META_SCHEMA) if path.is_file() else None

    def routines(self):
        return self._data("routines")

    def routine(self, routine_id):
        return next((r for r in self.routines() if r.get("id") == routine_id), None)

    def folders(self):
        return self._data("routine_folders")

    def exercise_templates(self):
        return self._data("exercise_templates")

    def body_measurements(self):
        return self._data("body_measurements")

    def workout(self, workout_id):
        path = self.workout_path(workout_id)
        return jsonio.read_doc(path, FILE_SCHEMA)["data"] if path.is_file() else None

    def workout_ids(self):
        folder = self.dir / WORKOUTS_DIR
        return sorted(p.stem for p in folder.glob("*.json")) if folder.is_dir() else []

    def workouts(self, since=None):
        """Cached workouts, oldest first. `since` (a date means midnight UTC) keeps those starting at or after it."""
        found = [self.workout(workout_id) for workout_id in self.workout_ids()]
        if since is not None:
            start = _since_moment(since)
            found = [w for w in found if dates.parse_timestamp(w["start_time"]) >= start]
        return sorted(found, key=lambda w: w.get("start_time") or "")

    def upsert_routine(self, raw):
        """Replace the cached routine with raw's id, or add it; the collection's fetched_at stays."""
        doc = self.read("routines")
        routines = list(doc["data"]) if doc else []
        fetched_at = doc["fetched_at"] if doc else self._clock().strftime("%Y-%m-%dT%H:%M:%SZ")
        for position, routine in enumerate(routines):
            if routine.get("id") == raw.get("id"):
                routines[position] = raw
                break
        else:
            routines.append(raw)
        self.write_collection("routines", routines, fetched_at)

    def write_collection(self, name, data, fetched_at):
        jsonio.write_doc(self.path(f"{name}.json"), wrap(data, fetched_at), dry_run=False)

    def write_workout(self, raw, fetched_at):
        jsonio.write_doc(self.workout_path(raw.get("id")), wrap(raw, fetched_at), dry_run=False)

    def remove_workout(self, workout_id):
        path = self.workout_path(workout_id)
        if path.is_file():
            path.unlink()

    def write_meta(self, meta):
        jsonio.write_doc(self.path(META), meta, dry_run=False)


def age_hours(meta, now):
    """Hours since the last pull finished, to one decimal place."""
    finished = dates.parse_timestamp(meta["last_pull_finished_at"])
    return round((now - finished).total_seconds() / 3600, 1)
