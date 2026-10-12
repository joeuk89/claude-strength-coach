"""Workouts from the manual lifting log, for athletes without Hevy (contract C46, C17)."""

from dataclasses import asdict

from coach import dates, jsonio, log, timing
from coach.activity.records import utc_text
from coach.history_sources import SourceWorkout
from coach.library import Library


def workouts(root):
    if not log.exists(root):
        return None
    slots = log.Slots(root)
    library = Library.load(root)
    return [_source_workout(line, slots.title(line), library) for line in log.live(root)]


def version(workout):
    return jsonio.canonical_hash(asdict(workout))


def _source_workout(line, title, library):
    exercises = []
    for exercise in line["exercises"]:
        entry = library.get(exercise["exercise_id"])
        sets = [{
            "index": index, "type": logged["type"], "reps": logged["reps"], "rpe": logged["rpe"], "weight_kg": None,
            "value": logged["value"], "duration_seconds": logged["duration_seconds"],
            "distance_meters": logged["distance_meters"],
        } for index, logged in enumerate(exercise["sets"])]
        exercises.append({"exercise_id": exercise["exercise_id"], "title": entry["name"] if entry else "",
                          "hevy_template_id": None, "load_mode": exercise["load_mode"], "unit": exercise["unit"],
                          "notes": exercise["notes"], "sets": sets})
    start = line.get("start_time")
    end = timing.end_of(dates.parse_timestamp(start), line["duration_minutes"]) if start else None
    return SourceWorkout(
        source="manual", workout_id=line["id"], date=line["date"], start_time=start,
        end_time=utc_text(end) if end else None, duration_minutes=line["duration_minutes"],
        title=title, description=line["notes"], session_id=line["session_id"], overlay_id=line["overlay_id"],
        exercises=exercises,
    )
