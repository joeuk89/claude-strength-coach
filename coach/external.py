"""Local Hevy mapping requirements and managed-routine housekeeping facts."""

import json
from pathlib import Path

from coach import flags, paths, state
from coach.hevy.cache import HevyCache
from coach.library import Library, template_resolution


def template_requirements(root, doc):
    lib = Library.load(root)
    cached = HevyCache(root).read_if_valid("exercise_templates")
    templates = cached["data"] if cached else []
    pull_first = "" if cached else "python3 -m coach hevy pull; then "
    owners = lib.template_owners()
    found = []
    for session in doc["sessions"]:
        for line in session["exercises"]:
            if line.get("hevy_template_id"):
                continue
            entry = lib.get(line["exercise_id"])
            resolution = template_resolution(entry, templates, owners)
            found.append({"session_id": session["session_id"], "exercise_id": line["exercise_id"],
                          **resolution, "repair": f"{pull_first}python3 -m coach library set-template "
                          f"{line['exercise_id']} ID; then rebuild the proposal/overlay so it carries "
                          "the chosen template"})
    return found


def hevy_requirements(root, doc, enabled=True):
    from coach.routines import session_routines

    if not enabled:
        return {"enabled": False, "ready": True, "templates": [], "sessions": []}
    sessions = [{"session_id": s["session_id"], "title": s["title"]}
                for s, rid in zip(doc["sessions"], session_routines(root, doc)) if not rid]
    templates = template_requirements(root, doc)
    return {"enabled": True, "ready": not templates, "templates": templates, "sessions": sessions}


def requirement_flags(root, doc, enabled):
    report = hevy_requirements(root, doc, enabled)
    found = [flags.make("hevy_template_unresolved", session_id=row["session_id"],
                        exercise_id=row["exercise_id"],
                        message=f"Hevy template {row['status']}: {row['repair']}") for row in report["templates"]]
    found += [flags.make("hevy_routine_unmapped", session_id=row["session_id"],
                         message=f"{row['title']} needs a named create or reuse action before the write brief")
              for row in report["sessions"]]
    return found


def orphan_routines(root, active=None, previous=None):
    """Managed routines no active mapping uses: a session mapping or a temporary-routine entry."""
    if active is None:
        current = state.load(root)["hevy"] if state.exists(root) else {}
        active = set(current.get("routines", {}))
    else:
        current = (previous or {}).get("hevy", {})
        active = set(active)
    active |= {entry["routine_id"] for entry in current.get("temporary_routines", [])}
    managed = _archived_mappings(root)
    managed.update(current.get("routines", {}))
    cache = HevyCache(root)
    rows = []
    for rid in sorted(set(managed) - active):
        routine = cache.routine(rid)
        if routine is None or routine.get("title") == "(unused)":
            continue
        rows.append({"routine_id": rid, "title": routine.get("title", rid),
                     "previous_session_id": managed[rid]["session_id"],
                     "choices": ["leave", "reuse", "retire"]})
    return rows


def _archived_mappings(root):
    # Ownership comes from mappings adoption archived; folder membership alone does not establish it.
    found = {}
    for path in sorted((Path(root) / paths.PROGRAM_ARCHIVE_DIR).glob("*/state.json")):
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        mappings = (old.get("hevy") or {}).get("routines") if isinstance(old, dict) else None
        if isinstance(mappings, dict):
            found.update({rid: row for rid, row in mappings.items()
                          if isinstance(row, dict) and isinstance(row.get("session_id"), str)})
    return found
