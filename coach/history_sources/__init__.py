"""History inputs: one module per source of logged workouts (contract C1, C17).

A source module exposes `workouts(root)`, returning a list of SourceWorkout
(or None when the source holds no data in this instance, so `history sync`
removes nothing it stored from it), and `version(workout) -> str`; a changed
version re-resolves the workout. The module's name is the `source` its
workouts carry. Modules are discovered, so adding a source adds a file.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceWorkout:
    """One logged workout as a source gives it, before resolution.

    `date` is the local date; None means history derives it from
    `start_time`. Each exercise is a dict: `exercise_id` (None when the
    library must match it), `title`, `hevy_template_id`, `load_mode` and
    `unit` (a manual log's own mode and unit, else None), `notes`, and
    `sets`, each with `index`, `type`, `reps`, `rpe`, `weight_kg` (Hevy's
    raw value), `value` (a manual log's coaching number),
    `duration_seconds` and `distance_meters`.
    """

    source: str
    workout_id: str
    date: str = None
    start_time: str = None
    end_time: str = None
    duration_minutes: int = None
    title: str = ""
    description: str = ""
    routine_id: str = None
    session_id: str = None
    overlay_id: str = None
    hevy_updated_at: str = None
    exercises: list = field(default_factory=list)


def discover():
    """{source name: module}, in name order."""
    found = {}
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        found[module_info.name] = importlib.import_module(f"{__name__}.{module_info.name}")
    return found
