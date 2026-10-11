"""Hevy workouts from the local cache (contract C8, C17)."""

from coach.hevy.cache import HevyCache
from coach.history_sources import SourceWorkout


def workouts(root):
    cache = HevyCache(root)
    if cache.meta() is None:
        return None
    return [_source_workout(raw) for raw in cache.workouts()]


def version(workout):
    return workout.hevy_updated_at or ""


def _source_workout(raw):
    exercises = []
    for exercise in raw.get("exercises") or []:
        sets = [{
            "index": logged.get("index", position), "type": logged.get("type") or "normal",
            "reps": logged.get("reps"), "rpe": logged.get("rpe"), "weight_kg": logged.get("weight_kg"),
            "value": None, "duration_seconds": logged.get("duration_seconds"),
            "distance_meters": logged.get("distance_meters"),
        } for position, logged in enumerate(exercise.get("sets") or [])]
        exercises.append({"exercise_id": None, "title": exercise.get("title") or "",
                          "hevy_template_id": exercise.get("exercise_template_id"), "load_mode": None, "unit": None,
                          "notes": exercise.get("notes") or "", "sets": sets})
    return SourceWorkout(
        source="hevy", workout_id=raw["id"], start_time=raw.get("start_time"), end_time=raw.get("end_time"),
        title=raw.get("title") or "", description=raw.get("description") or "", routine_id=raw.get("routine_id"),
        hevy_updated_at=raw.get("updated_at"), exercises=exercises,
    )
