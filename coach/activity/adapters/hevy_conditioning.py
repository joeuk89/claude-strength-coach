"""Hevy conditioning workouts as Activities (contract C31). Reads the local Hevy cache; never calls the API."""

import re

from coach import dates, program, state
from coach.activity import records
from coach.activity.adapters import Drop, FetchResult
from coach.config import Key
from coach.hevy.cache import HevyCache, age_hours
from coach.library import Library

NAME = "hevy_conditioning"
KINDS = ("activity",)
NETWORK = False
CONFIG = {"enabled": Key("boolean", default=True)}
FRESH_BY = "sync"

KIND_BY_LIBRARY_ID = {
    "running": "run", "treadmill": "run",
    "cycling": "ride", "stationary_bike": "ride",
    "rowing_machine": "row",
}
DELETED = "deleted in Hevy"
NOT_CONDITIONING = "no longer a conditioning workout in Hevy"
LIFTING = "lifting workout; Hevy is the lifting logbook"
_RPE = re.compile(r"\bRPE\s*(\d{1,2}(?:\.\d+)?)", re.IGNORECASE)


def is_enabled(config):
    return bool(config["sources"][NAME]["enabled"] and config["hevy"]["enabled"])


def parse_rpe(text):
    """Session RPE from the first "RPE n" in a description: 0 to 10, halves allowed; else None."""
    match = _RPE.search(text or "")
    if not match:
        return None
    value = float(match.group(1))
    if not 0 <= value <= 10 or value % 1 not in (0, 0.5):
        return None
    return int(value) if value.is_integer() else value


def activity_kind(item):
    """The Activity kind for a fetched workout item, or None when it is a lifting workout."""
    if item["session_kind"] == "conditioning":
        return "conditioning"
    exercises = item["exercises"]
    if not exercises or not all(_is_conditioning(e) for e in exercises):
        return None
    kinds = {KIND_BY_LIBRARY_ID.get(e["library_id"]) for e in exercises}
    if len(kinds) == 1 and None not in kinds:
        return kinds.pop()
    return "conditioning"


def _is_conditioning(exercise):
    if exercise["library_id"] is not None:
        return exercise["pattern"] == "conditioning"
    return exercise["primary_muscle_group"] == "cardio"


def fetch(ctx, sync_state):
    cache = HevyCache(ctx.root)
    meta = cache.meta()
    if meta is None:
        return FetchResult([], dict(sync_state), ["there is no Hevy cache yet; run python3 -m coach hevy pull"])
    warnings = []
    age, limit = age_hours(meta, ctx.now()), ctx.config.hevy.cache_max_age_hours
    if age > limit:
        warnings.append(f"the Hevy cache is {age:g} hours old, past the {limit:g}-hour limit; "
                        "run python3 -m coach hevy pull first")

    lib = Library.load(ctx.root)
    templates = {t.get("id"): t for t in cache.exercise_templates()}
    session_kinds = _session_kinds(ctx.root)
    items, current = [], set()
    workouts = cache.workouts()
    for workout in workouts:
        item = {
            "workout": workout,
            "session_kind": session_kinds.get(workout.get("routine_id")),
            "exercises": [_exercise(lib, templates, e) for e in workout.get("exercises") or []],
        }
        items.append(item)
        if activity_kind(item) is not None:
            current.add(workout["id"])

    cached = {w["id"] for w in workouts}
    for workout_id in sorted(set(sync_state.get("seen_workout_ids", [])) - current):
        items.append({"void": workout_id, "reason": NOT_CONDITIONING if workout_id in cached else DELETED})
    return FetchResult(items, {"seen_workout_ids": sorted(current)}, warnings)


def _exercise(lib, templates, exercise):
    template_id = exercise.get("exercise_template_id")
    entry = lib.by_hevy_template_id(template_id) if template_id else None
    if entry is None and exercise.get("title"):
        entry, _ = lib.match_title(exercise["title"])
    template = templates.get(template_id) or {}
    return {
        "title": exercise.get("title"),
        "template_id": template_id,
        "library_id": entry["id"] if entry else None,
        "pattern": entry["pattern"] if entry else None,
        "primary_muscle_group": template.get("primary_muscle_group"),
    }


def _session_kinds(root):
    """{Hevy routine id: program session kind}, from the state and program when both exist.

    Raises ValidationError when either is malformed, so a broken file never voids routine-mapped Activities.
    """
    if not (state.exists(root) and program.exists(root)):
        return {}
    kinds = {s["id"]: s["kind"] for s in program.load(root)["sessions"]}
    routines = state.load(root)["hevy"]["routines"]
    return {routine_id: kinds.get(entry["session_id"]) for routine_id, entry in routines.items()}


def normalise(item, ctx):
    if "void" in item:
        return [{"op": "void", "id": f"{NAME}:{item['void']}", "source": NAME, "reason": item["reason"]}]
    kind = activity_kind(item)
    if kind is None:
        raise Drop(LIFTING)
    workout = item["workout"]
    start = dates.parse_timestamp(workout["start_time"])
    end = dates.parse_timestamp(workout["end_time"]) if workout.get("end_time") else None
    distances = [s["distance_meters"] for e in workout.get("exercises") or [] for s in e.get("sets") or []
                 if s.get("distance_meters") is not None]
    return [{
        "id": f"{NAME}:{workout['id']}", "source": NAME, "source_id": workout["id"],
        "kind": kind, "name": workout.get("title") or None, "indoor": None,
        "start": records.utc_text(start), "end": records.utc_text(end) if end else None, "utc_offset": None,
        "local_date": records.local_date(start, None, ctx.timezone()).isoformat(),
        "duration_seconds": max(0, int((end - start).total_seconds())) if end else 0,
        "distance_meters": sum(distances) if distances else None,
        "elevation_gain_meters": None, "avg_hr": None, "max_hr": None, "active_kcal": None,
        "rpe": parse_rpe(workout.get("description")), "device": "Hevy", "notes": None,
    }]
