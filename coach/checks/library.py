"""Checks on the exercise library: it is valid, and every exercise in use has a confirmed load mode."""

import json

from coach import library, paths
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.hevy.cache import HevyCache
from coach.library import Library

_LIBRARY = paths.EXERCISES.as_posix()


@check(id="library_valid", owner="R-11")
def library_valid(ctx):
    try:
        lib = Library.load(ctx.root)
    except ValidationError as exc:
        if not exc.details:
            return [Result("fail", exc.message, _LIBRARY)]
        return [Result("fail", f"{detail['path']}: {detail['message']}", _LIBRARY) for detail in exc.details]
    if not lib.path.exists():
        return [Result("pass", "No instance library yet; the builtin catalogue is valid.", _LIBRARY)]
    return [Result("pass", f"The library is valid ({len(lib.instance['exercises'])} instance entries).", _LIBRARY)]


def _overlay_exercises(root):
    """{exercise id: [overlay ids]} from every overlay file; the overlay checks report unreadable ones."""
    found = {}
    for path in sorted((root / paths.OVERLAYS_DIR).glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        sessions = doc.get("sessions") if isinstance(doc, dict) else None
        for session in sessions if isinstance(sessions, list) else []:
            exercises = session.get("exercises") if isinstance(session, dict) else None
            for exercise in exercises if isinstance(exercises, list) else []:
                exercise_id = exercise.get("exercise_id") if isinstance(exercise, dict) else None
                if isinstance(exercise_id, str):
                    overlays = found.setdefault(exercise_id, [])
                    if path.stem not in overlays:
                        overlays.append(path.stem)
    return found


@check(id="load_modes_confirmed", owner="R-11")
def load_modes_confirmed(ctx):
    try:
        lib = Library.load(ctx.root)
        routines = HevyCache(ctx.root).routines()
    except ValidationError as exc:
        return [Result("fail", f"cannot read the library or the Hevy cache ({exc.message}); see library_valid",
                       _LIBRARY)]
    results = []
    cache_path = (paths.HEVY_CACHE_DIR / "routines.json").as_posix()
    for template_id, title, routine_titles in library.routine_exercises(routines):
        where = ", ".join(f"'{name}'" for name in routine_titles)
        entry = lib.by_hevy_template_id(template_id)
        if entry is None:
            results.append(Result("fail", (
                f"Hevy exercise '{title}' (template {template_id}) in routine {where} has no library entry; "
                "run python3 -m coach library seed, then library confirm"
            ), cache_path))
        elif lib.effective_load_mode(entry["id"]) is None:
            results.append(Result("fail", _unconfirmed(lib, entry["id"], f"'{title}' in routine {where}"), _LIBRARY))
    overlays = _overlay_exercises(ctx.root)
    for exercise_id in lib.unconfirmed(overlays):
        where = f"in overlay {', '.join(overlays[exercise_id])}"
        results.append(Result("fail", _unconfirmed(lib, exercise_id, where), _LIBRARY))
    return results


def _unconfirmed(lib, exercise_id, where):
    return f"{exercise_id} ({where}) has no confirmed load mode; run {lib.mode_repair(exercise_id)}"
