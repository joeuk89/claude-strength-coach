"""Helpers for activity-source tests: a Hevy cache from a synthetic fixture set (C8, C15), and routine mappings (C16)."""

import copy
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


def map_routines(root, routine_kinds):
    """Map each Hevy routine id to a session of the given kind in the instance's C16 program and state.

    A kind the program lacks gets a copy of its last session under the id `<kind>-session`.
    """
    program_path, state_path = root / "data" / "program.json", root / "data" / "state.json"
    program = json.loads(program_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for routine_id, kind in sorted(routine_kinds.items()):
        session = next((s for s in program["sessions"] if s["kind"] == kind), None)
        if session is None:
            session = dict(copy.deepcopy(program["sessions"][-1]), id=f"{kind}-session", title=kind, kind=kind)
            program["sessions"].append(session)
        state["hevy"]["routines"][routine_id] = {"session_id": session["id"]}
    program_path.write_text(json.dumps(program, indent=2) + "\n", encoding="utf-8")
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
