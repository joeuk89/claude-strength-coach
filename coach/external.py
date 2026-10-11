"""Local Hevy readiness and managed-routine housekeeping facts."""

import json
from pathlib import Path

from coach import flags, paths, state
from coach.hevy.cache import HevyCache
from coach.library import Library, template_resolution


def template_requirements(root, doc):
    lib = Library.load(root)
    templates = HevyCache(root).exercise_templates()
    found = []
    for session in doc["sessions"]:
        for line in session["exercises"]:
            if line.get("hevy_template_id"):
                continue
            entry = lib.get(line["exercise_id"])
            resolution = template_resolution(entry, templates, lib.template_owners())
            found.append({"session_id": session["session_id"], "exercise_id": line["exercise_id"],
                          **resolution, "repair": f"python3 -m coach library set-template {line['exercise_id']} ID; "
                          "then rebuild the proposal/overlay so it carries the chosen template"})
    return found


def readiness(root, doc, enabled=True):
    from coach.routines import session_routines

    if not enabled:
        return {"enabled": False, "ready": True, "templates": [], "sessions": []}
    sessions = [{"session_id": s["session_id"], "title": s["title"], "action": "create_or_reuse"}
                for s, rid in zip(doc["sessions"], session_routines(root, doc)) if not rid]
    templates = template_requirements(root, doc)
    return {"enabled": True, "ready": not templates, "templates": templates, "sessions": sessions}


def readiness_flags(root, doc, enabled):
    report = readiness(root, doc, enabled)
    found = [flags.make("hevy_template_unresolved", session_id=row["session_id"],
                        exercise_id=row["exercise_id"],
                        message=f"Hevy template {row['status']}: {row['repair']}") for row in report["templates"]]
    found += [flags.make("hevy_routine_unmapped", session_id=row["session_id"],
                         message=f"{row['title']} needs a named create or reuse action before the write brief")
              for row in report["sessions"]]
    return found


def orphan_routines(root, active=None, previous=None):
    cache = HevyCache(root)
    if active is None:
        current = state.load(root)["hevy"] if state.exists(root) else {"routines": {}}
        active = set(current["routines"])
    else:
        current = (previous or {}).get("hevy", {"routines": {}})
        active = set(active)
    managed = dict(current["routines"])
    if previous:
        managed.update(previous["hevy"]["routines"])
    # Adoption archives mapping provenance; folder membership alone does not establish ownership.
    archive = Path(root) / paths.PROGRAM_ARCHIVE_DIR
    for path in sorted(archive.glob("*/state.json")):
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old, dict) and isinstance(old.get("hevy"), dict):
                mappings = old["hevy"].get("routines")
                if isinstance(mappings, dict):
                    managed.update({rid: row for rid, row in mappings.items()
                                    if isinstance(row, dict) and isinstance(row.get("session_id"), str)})
        except (ValueError, OSError):
            continue
    rows = []
    for rid in sorted(set(managed) - active):
        routine = cache.routine(rid)
        if routine is None or routine.get("title") == "(unused)":
            continue
        rows.append({"routine_id": rid, "title": routine.get("title", rid),
                     "previous_session_id": managed[rid]["session_id"],
                     "choices": ["leave", "reuse", "retire"]})
    return rows
