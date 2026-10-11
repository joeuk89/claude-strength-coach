"""Overlay to Hevy routines: build, diff, push, verify, create and retire (contract C9, C10, C12, C16).

`intended_body` turns one overlay session into the PUT body for its Hevy
routine; `diff` compares that body with a routine as Hevy returns it. A
session's routine is the overlay's `hevy_routine_id`, else the one
`data/state.json` records for it (`session_routines`). The push refuses an
overlay that is unapproved, edited after approval, blocked, ended or
superseded, and a routine edited in the app since the cache was read. It
writes each changed routine once, reads it back and logs whether the
read-back matches. `create` gives a session with no routine one, under the
same refusals, and records the new id in state.json only.
"""

import json

from coach import dates, jsonio
from coach import overlay as overlay_module
from coach import paths, render, units
from coach import program as program_module
from coach import state as state_module
from coach.errors import ConfigError, RefusedError, ValidationError
from coach.hevy.cache import HevyCache
from coach.hevy.client import HevyClient, created_routine, timestamp
from coach.validate import validate as validate_schema

PRESCRIPTION = "prescription"
STRUCTURAL = "structural"
PRESCRIPTION_FIELDS = ("weight_kg", "notes")
UNUSED_TITLE = "(unused)"
# Hevy keeps weights as floats; a gram is far below any plate or dumbbell step.
WEIGHT_TOLERANCE_KG = 0.001
AUDIT_VERSION = 1
VERIFY_SCHEMA = "hevy_verify_line"
RETIRE_SCHEMA = "hevy_retire_line"
ONE_OFF_FOLDER_TITLE = "One-off weeks"

_SET_FIELDS = ("type", "weight_kg", "reps", "rep_range", "duration_seconds", "distance_meters")
_PULL = "python3 -m coach hevy pull"
_NEW = "new:"


def intended_body(doc, session, cached_routine):
    """The PUT body that makes a routine carry this overlay session.

    A temporary session's routine takes the session title; any other keeps
    the routine's own title. The folder is kept, because a PUT may move the
    routine. Nothing in the body is null and the routine has no `notes`:
    Hevy rejects nulls and drops routine notes (C12).
    """
    cached_routine = cached_routine or {}
    routine = {"title": _title(session, cached_routine)}
    if cached_routine.get("folder_id") is not None:
        routine["folder_id"] = cached_routine["folder_id"]
    routine["exercises"] = [_exercise_body(doc, session, line, index == 0)
                            for index, line in enumerate(session["exercises"])]
    return {"routine": routine}


def _title(session, cached_routine):
    if session.get("temporary") or not cached_routine.get("title"):
        return session["title"]
    return cached_routine["title"]


def _exercise_body(doc, session, line, is_first):
    if not line.get("hevy_template_id"):
        raise ValidationError(
            f"Overlay {doc['id']}: {session['session_id']} / {line['exercise_id']} has no hevy_template_id, "
            "so it cannot be written to Hevy"
        )
    body = {"exercise_template_id": line["hevy_template_id"]}
    for key in ("superset_id", "rest_seconds"):
        if line.get(key) is not None:
            body[key] = line[key]
    body["notes"] = render.render_hevy_note(doc, session, line, is_first)
    body["sets"] = [_set_body(set_) for set_ in line["sets"]]
    return body


def _set_body(set_):
    body = {"type": set_["type"]}
    weight = _weight_kg(set_.get("load"))
    if weight is not None:
        body["weight_kg"] = weight
    if set_.get("reps") is not None:
        body["reps"] = set_["reps"]
    if set_.get("rep_range") is not None:
        body["rep_range"] = {"start": set_["rep_range"]["start"], "end": set_["rep_range"]["end"]}
    for key in ("duration_seconds", "distance_meters"):
        if set_.get(key) is not None:
            body[key] = set_[key]
    return body


def _weight_kg(load):
    if load is None:
        return None
    # Hevy's bodyweight routine sets carry no weight, so an unweighted one is sent without one.
    if load["mode"] == "bodyweight" and load["hevy_kg"] == 0:
        return None
    return load["hevy_kg"]


def _norm_rep_range(value):
    if not isinstance(value, dict):
        return None
    return {"start": value.get("start"), "end": value.get("end")}


def _norm_set(set_):
    found = {field: set_.get(field) for field in _SET_FIELDS}
    found["rep_range"] = _norm_rep_range(found["rep_range"])
    return found


def _norm_exercise(exercise):
    return {
        "exercise_template_id": exercise.get("exercise_template_id"),
        "superset_id": exercise.get("superset_id"),
        "rest_seconds": exercise.get("rest_seconds"),
        "notes": exercise.get("notes") or "",
        "sets": [_norm_set(s) for s in exercise.get("sets") or []],
    }


def _same(field, a, b):
    if field == "weight_kg" and a is not None and b is not None:
        return abs(a - b) <= WEIGHT_TOLERANCE_KG
    return a == b


def change_class(path):
    """`prescription` for a weight or a note, which every programming pass rewrites; else `structural`."""
    return PRESCRIPTION if path.rsplit(".", 1)[-1] in PRESCRIPTION_FIELDS else STRUCTURAL


def diff(intended, actual):
    """Changes that would turn `actual` (a routine as Hevy returns it) into the `intended` PUT body.

    Each change is {routine_id, class, path, before, after}. Absent and null
    are the same; weights match within a gram. Exercises and sets compare by
    position; a different exercise template at a position is one change for
    the whole exercise.
    """
    routine_id = actual.get("id")
    want = intended["routine"]
    changes = []

    def add(path, before, after):
        changes.append({"routine_id": routine_id, "class": change_class(path), "path": path,
                        "before": before, "after": after})

    if want.get("title") != actual.get("title"):
        add("title", actual.get("title"), want.get("title"))
    if "folder_id" in want and want["folder_id"] != actual.get("folder_id"):
        add("folder_id", actual.get("folder_id"), want["folder_id"])
    have_exercises = [_norm_exercise(e) for e in actual.get("exercises") or []]
    want_exercises = [_norm_exercise(e) for e in want.get("exercises") or []]
    for index in range(max(len(have_exercises), len(want_exercises))):
        path = f"exercises[{index}]"
        have = have_exercises[index] if index < len(have_exercises) else None
        wanted = want_exercises[index] if index < len(want_exercises) else None
        if have is None or wanted is None or have["exercise_template_id"] != wanted["exercise_template_id"]:
            add(path, have, wanted)
            continue
        for key in ("superset_id", "rest_seconds", "notes"):
            if have[key] != wanted[key]:
                add(f"{path}.{key}", have[key], wanted[key])
        for s_index in range(max(len(have["sets"]), len(wanted["sets"]))):
            set_path = f"{path}.sets[{s_index}]"
            have_set = have["sets"][s_index] if s_index < len(have["sets"]) else None
            want_set = wanted["sets"][s_index] if s_index < len(wanted["sets"]) else None
            if have_set is None or want_set is None:
                add(set_path, have_set, want_set)
                continue
            for field in _SET_FIELDS:
                if not _same(field, have_set[field], want_set[field]):
                    add(f"{set_path}.{field}", have_set[field], want_set[field])
    return changes


def _request_exercise(exercise):
    """A routine exercise as Hevy returns it, reshaped as a PUT exercise with no nulls."""
    body = {"exercise_template_id": exercise.get("exercise_template_id")}
    for key in ("superset_id", "rest_seconds", "notes"):
        if exercise.get(key) is not None:
            body[key] = exercise[key]
    sets = []
    for set_ in exercise.get("sets") or []:
        out = {}
        for field in _SET_FIELDS + ("custom_metric",):
            value = set_.get(field)
            if field == "rep_range":
                value = _norm_rep_range(value)
                if value is not None and None in value.values():
                    value = None
            if value is not None:
                out[field] = value
        sets.append(out)
    body["sets"] = sets
    return body


def retire_body(live_routine):
    """The PUT body that retitles a routine `(unused)` and keeps its exercises as they are."""
    routine = {"title": UNUSED_TITLE}
    if live_routine.get("folder_id") is not None:
        routine["folder_id"] = live_routine["folder_id"]
    routine["exercises"] = [_request_exercise(e) for e in live_routine.get("exercises") or []]
    return {"routine": routine}


def session_routines(root, doc):
    """Each session's Hevy routine id, in overlay order, or None where there is none.

    The overlay's own `hevy_routine_id` comes first. Otherwise state.json
    decides: a temporary session takes the temporary routine recorded as
    carrying it in this overlay, any other session the routine mapped to its
    session id.
    """
    ids = [session.get("hevy_routine_id") for session in doc["sessions"]]
    if all(ids) or not state_module.exists(root):
        return ids
    hevy = state_module.load(root)["hevy"]
    return [routine_id or _recorded(hevy, doc, session) for routine_id, session in zip(ids, doc["sessions"])]


def _recorded(hevy, doc, session):
    session_id = session["session_id"]
    if session.get("temporary"):
        found = [entry["routine_id"] for entry in hevy["temporary_routines"]
                 if entry["overlay_id"] == doc["id"] and entry["session_id"] == session_id]
    else:
        found = [routine_id for routine_id, entry in hevy["routines"].items() if entry["session_id"] == session_id]
    if len(found) > 1:
        raise ValidationError(
            f"{paths.STATE} gives session {session_id} {len(found)} Hevy routines ({', '.join(found)}); "
            "keep the one the athlete trains from"
        )
    return found[0] if found else None


def _ids(doc, ids):
    return [s.get("hevy_routine_id") for s in doc["sessions"]] if ids is None else ids


def unmapped_sessions(doc, ids=None):
    return [session for session, routine_id in zip(doc["sessions"], _ids(doc, ids)) if not routine_id]


def _require_mapped(doc, ids):
    unmapped = unmapped_sessions(doc, ids)
    if unmapped:
        names = ", ".join(f"{s['session_id']} ({s['date']})" for s in unmapped)
        raise ValidationError(
            f"Overlay {doc['id']} has session(s) with no Hevy routine: {names}; "
            f"run python3 -m coach routines create --overlay {doc['id']} first"
        )


def plan(doc, today, ids=None):
    """One (routine id, session, every date it carries) per routine, in overlay order.

    `ids` gives each session's routine (`session_routines`); by default the
    overlay's own. A routine used by several sessions carries the next one
    on or after today, or the last one when all have passed. Sessions with
    no routine are left out (see `unmapped_sessions`).
    """
    grouped = {}
    for session, routine_id in zip(doc["sessions"], _ids(doc, ids)):
        if routine_id:
            grouped.setdefault(routine_id, []).append(session)
    today = today.isoformat()
    found = []
    for routine_id, sessions in grouped.items():
        upcoming = [s for s in sessions if s["date"] >= today]
        chosen = min(upcoming, key=lambda s: s["date"]) if upcoming else max(sessions, key=lambda s: s["date"])
        found.append((routine_id, chosen, sorted(s["date"] for s in sessions)))
    return found


def current_overlay(root, today):
    """The overlay that governs the coming sessions: the one in force today, else the next to start."""
    found = overlay_module.in_force(root, today)
    if found:
        return found[0]
    upcoming = [doc for doc in overlay_module.list(root) if doc["span"]["start"] > today.isoformat()]
    if not upcoming:
        return None
    first_start = min(doc["span"]["start"] for doc in upcoming)
    starting = [doc for doc in upcoming if doc["span"]["start"] == first_start]
    return max(starting, key=lambda d: (dates.parse_timestamp(d["created_at"]), d["id"]))


def _load(ctx, overlay_id):
    doc = overlay_module.read_json(overlay_module.path_for(ctx.root, overlay_id))
    errors = overlay_module.validate(doc, ctx.root, ctx.config)
    if errors:
        raise ValidationError(f"Overlay {overlay_id} is not valid ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    if doc["id"] != overlay_id:
        raise ValidationError(f"The file for {overlay_id} holds overlay {doc['id']}")
    return doc


def _require_hevy(ctx):
    if not ctx.config.hevy.enabled:
        raise ConfigError("Hevy is turned off in config.toml ([hevy] enabled = false), so there are no routines.")


def push_refusals(root, doc, today, ids=None):
    """Every reason a push of this overlay is refused, as envelope details; empty when it may go."""
    found = []

    def refuse(message):
        found.append({"path": None, "message": message})

    approval = doc.get("approval")
    if not approval:
        refuse(f"overlay {doc['id']} is not approved; run overlay approve {doc['id']} once the athlete agrees")
    elif not overlay_module.is_approved(doc):
        refuse(f"overlay {doc['id']} was edited after approval; run overlay approve {doc['id']} again "
               "once the athlete agrees")
    for flag in overlay_module.unresolved_blocks(doc):
        where = " / ".join(part for part in (flag["session_id"], flag["exercise_id"]) if part)
        refuse(f"unresolved block flag {flag['code']}" + (f" ({where})" if where else "") + f": {flag['message']}")
    if doc["span"]["end"] < today.isoformat():
        refuse(f"overlay {doc['id']} ended on {doc['span']['end']}")
    else:
        for _, session, _ in plan(doc, today, ids):
            if session["date"] < today.isoformat():
                continue
            governing = overlay_module.in_force(root, session["date"])
            if governing and governing[0]["id"] != doc["id"]:
                refuse(f"{session['title']} on {session['date']} is governed by overlay {governing[0]['id']}, "
                       f"which supersedes {doc['id']}")
    return found


def _refused(doc, reasons, outcome="is not pushed"):
    first = reasons[0]["message"]
    more = f" (and {len(reasons) - 1} more reason(s))" if len(reasons) > 1 else ""
    return RefusedError(f"Overlay {doc['id']} {outcome}: {first}{more}.", details=reasons)


def _get_routine(client, routine_id):
    body = client.get(f"/v1/routines/{routine_id}")
    routine = body.get("routine") if isinstance(body, dict) else None
    if not isinstance(routine, dict):
        raise ValidationError(f"Hevy answered GET /v1/routines/{routine_id} without a routine")
    return routine


def _routines(ctx, cache, routine_ids, refresh, dry_run):
    """{routine id: routine}: re-read from Hevy with refresh (and cached unless dry_run), else from the cache."""
    if refresh:
        client = HevyClient.from_context(ctx)
        found = {}
        for routine_id in routine_ids:
            found[routine_id] = _get_routine(client, routine_id)
            if not dry_run:
                cache.upsert_routine(found[routine_id])
        return found
    return _from_cache(cache, routine_ids)


def _from_cache(cache, routine_ids, allow_missing=False):
    found = {routine_id: cache.routine(routine_id) for routine_id in routine_ids}
    missing = [routine_id for routine_id, routine in found.items() if routine is None]
    if missing and not allow_missing:
        raise ValidationError(
            f"Routine(s) {', '.join(missing)} are not in the Hevy cache; run {_PULL}, or pass --refresh"
        )
    return found


def _exercise_context(session):
    return [
        {"index": index, "exercise_id": line["exercise_id"], "load_mode": line["load_mode"],
         "loads": [set_.get("load") for set_ in line["sets"]]}
        for index, line in enumerate(session["exercises"])
    ]


def _entry(routine_id, session, carries, title, changes, status, verified=None):
    return {
        "routine_id": routine_id, "session_id": session["session_id"], "date": session["date"],
        "carries": carries, "title": title, "temporary": bool(session.get("temporary")),
        "status": status, "verified": verified, "changes": changes, "exercises": _exercise_context(session),
    }


def _report(action, doc, ctx, entries, dry_run=False, writes=0, **extra):
    report = {
        "action": action,
        "overlay_id": doc["id"],
        "overlay_hash": doc["approval"]["hash"] if overlay_module.is_approved(doc) else None,
        "approved": overlay_module.is_approved(doc),
        "unit": ctx.config.athlete.units,
        "dry_run": dry_run,
        "routines": entries,
        "changes": [change for entry in entries for change in entry["changes"]],
        "writes": writes,
        **extra,
    }
    report["summary"] = summary(report)
    return report


def _warn_shared(ctx, doc, routine_plan):
    for routine_id, session, carries in routine_plan:
        if len(carries) > 1:
            ctx.warn(f"routine {routine_id} serves {len(carries)} sessions in {doc['id']} "
                     f"({', '.join(carries)}); it carries the one on {session['date']}")


def diff_report(ctx, overlay_id, refresh=False, dry_run=False):
    _require_hevy(ctx)
    doc = _load(ctx, overlay_id)
    ids = session_routines(ctx.root, doc)
    _require_mapped(doc, ids)
    routine_plan = plan(doc, ctx.today(), ids)
    _warn_shared(ctx, doc, routine_plan)
    cache = HevyCache(ctx.root, clock=ctx.now)
    found = _routines(ctx, cache, [routine_id for routine_id, _, _ in routine_plan], refresh, dry_run)
    entries = []
    for routine_id, session, carries in routine_plan:
        body = intended_body(doc, session, found[routine_id])
        changes = diff(body, found[routine_id])
        entries.append(_entry(routine_id, session, carries, body["routine"]["title"], changes,
                              "changes" if changes else "matches"))
    return _report("diff", doc, ctx, entries, dry_run=dry_run)


def verify(ctx, overlay_id, refresh=False, dry_run=False):
    """Per routine, whether Hevy (the cache, or a fresh read with refresh) matches the overlay."""
    report = diff_report(ctx, overlay_id, refresh=refresh, dry_run=dry_run)
    for entry in report["routines"]:
        entry["verified"] = not entry["changes"]
        entry["status"] = "verified" if entry["verified"] else "differs"
    report["action"] = "verify"
    report["verified"] = all(entry["verified"] for entry in report["routines"])
    report["summary"] = summary(report)
    return report


def _audit_path(root):
    return root / paths.HEVY_WRITES


def _audit_lines(ctx):
    path = _audit_path(ctx.root)
    if not path.is_file():
        return []
    lines = []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not text.strip():
            continue
        try:
            lines.append(json.loads(text))
        except json.JSONDecodeError:
            ctx.warn(f"{paths.HEVY_WRITES} line {number} is not JSON; it was skipped")
    return lines


def _already_verified(ctx, routine_id, doc, overlay_hash):
    return any(
        line.get("kind") == "verify" and line.get("routine_id") == routine_id and line.get("overlay_id") == doc["id"]
        and line.get("overlay_hash") == overlay_hash and line.get("verified") is True
        for line in _audit_lines(ctx)
    )


def _append(ctx, line, schema):
    errors = validate_schema(line, jsonio.load_schema(schema))
    if errors:
        raise RuntimeError(f"audit line does not match {schema}: {errors}")
    path = _audit_path(ctx.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n")


def _check_line(ctx, kind, routine_id, doc, overlay_hash, changes):
    return {"schema_version": AUDIT_VERSION, "at": timestamp(ctx.now()), "kind": kind, "routine_id": routine_id,
            "overlay_id": doc["id"], "overlay_hash": overlay_hash, "verified": not changes, "diff": changes}


def push(ctx, overlay_id, dry_run, refresh=False):
    """Write every routine whose Hevy content differs from the overlay, then read each back.

    Raises RefusedError (exit 3) before any write when a guard refuses,
    ValidationError (exit 1, report kept) when a read-back does not match.
    """
    _require_hevy(ctx)
    doc = _load(ctx, overlay_id)
    today = ctx.today()
    ids = session_routines(ctx.root, doc)
    reasons = push_refusals(ctx.root, doc, today, ids)
    if reasons:
        raise _refused(doc, reasons)
    _require_mapped(doc, ids)
    overlay_hash = doc["approval"]["hash"]
    routine_plan = plan(doc, today, ids)
    _warn_shared(ctx, doc, routine_plan)
    client = HevyClient.from_context(ctx)
    cache = HevyCache(ctx.root, clock=ctx.now)
    routine_ids = [routine_id for routine_id, _, _ in routine_plan]
    cached = _from_cache(cache, routine_ids, allow_missing=refresh)
    missing = [routine_id for routine_id, routine in cached.items() if routine is None]
    live = {routine_id: _get_routine(client, routine_id) for routine_id in routine_ids}
    moved = [cached[r] for r in routine_ids
             if cached[r] is not None and live[r].get("updated_at") != cached[r].get("updated_at")]
    if moved:
        names = ", ".join(f"{r.get('title')} ({r.get('id')})" for r in moved)
        raise RefusedError(
            f"Overlay {doc['id']} is not pushed: {names} changed in Hevy since the cache was read; "
            f"run routines diff --overlay {doc['id']} --refresh and review before pushing.",
            details=[{"path": None, "message": f"{r.get('title')}: cached updated_at {r.get('updated_at')}, "
                                               f"Hevy now has {live[r['id']].get('updated_at')}"} for r in moved],
        )
    for routine_id in missing:
        cached[routine_id] = live[routine_id]
    if refresh and not dry_run:
        for routine_id in routine_ids:
            cache.upsert_routine(live[routine_id])

    entries, bodies = [], {}
    for routine_id, session, carries in routine_plan:
        bodies[routine_id] = intended_body(doc, session, cached[routine_id])
        changes = diff(bodies[routine_id], cached[routine_id])
        status = ("would_write" if dry_run else "pending") if changes else "unchanged"
        entries.append(_entry(routine_id, session, carries, bodies[routine_id]["routine"]["title"], changes, status))
    if dry_run:
        return _report("push", doc, ctx, entries, dry_run=True)

    writes = 0
    for position, entry in enumerate(entries):
        routine_id = entry["routine_id"]
        body = bodies[routine_id]
        if entry["status"] == "unchanged":
            if not _already_verified(ctx, routine_id, doc, overlay_hash):
                remaining = diff(body, live[routine_id])
                entry["verified"] = not remaining
                _append(ctx, _check_line(ctx, "verify", routine_id, doc, overlay_hash, remaining), VERIFY_SCHEMA)
            continue
        client.put(f"/v1/routines/{routine_id}", body, routine_id=routine_id, overlay_id=doc["id"],
                   overlay_hash=overlay_hash)
        writes += 1
        read_back = _get_routine(client, routine_id)
        cache.upsert_routine(read_back)
        remaining = diff(body, read_back)
        _append(ctx, _check_line(ctx, "verify", routine_id, doc, overlay_hash, remaining), VERIFY_SCHEMA)
        entry["verified"] = not remaining
        entry["status"] = "written" if not remaining else "failed"
        if remaining:
            for later in entries[position + 1:]:
                if later["status"] == "pending":
                    later["status"] = "not_reached"
            report = _report("push", doc, ctx, entries, writes=writes)
            raise ValidationError(
                f"{entry['title']} did not read back as written ({len(remaining)} difference(s)); "
                "later routines were not written.",
                details=[{"path": c["path"], "message": f"sent {c['after']!r}, Hevy has {c['before']!r}"}
                         for c in remaining],
                data=report,
            )
    return _report("push", doc, ctx, entries, writes=writes)


def retire(ctx, overlay_id, dry_run, refresh=False):
    """Retitle the temporary routines of an ended overlay `(unused)`, keeping their exercises."""
    _require_hevy(ctx)
    doc = _load(ctx, overlay_id)
    today = ctx.today()
    if doc["span"]["end"] >= today.isoformat():
        raise RefusedError(
            f"Overlay {doc['id']} is not retired: its span runs to {doc['span']['end']}; "
            "retire its temporary routines once it has ended."
        )
    overlay_hash = overlay_module.approval_hash(doc)
    temporary = {}
    for session, routine_id in zip(doc["sessions"], session_routines(ctx.root, doc)):
        if session.get("temporary") and routine_id:
            temporary.setdefault(routine_id, session)
    in_use = _routines_in_live_overlays(ctx.root, doc, today)
    client = HevyClient.from_context(ctx)
    cache = HevyCache(ctx.root, clock=ctx.now)
    entries, writes, failure = [], 0, None
    for routine_id, session in temporary.items():
        entry = _entry(routine_id, session, [session["date"]], session["title"], [], "pending")
        entries.append(entry)
        if failure:
            entry["status"] = "not_reached"
            continue
        if routine_id in in_use:
            entry["status"] = "in_use"
            ctx.warn(f"routine {routine_id} is left alone: overlay {in_use[routine_id]} still uses it")
            continue
        live = _get_routine(client, routine_id)
        if refresh and not dry_run:
            cache.upsert_routine(live)
        entry["title"] = live.get("title")
        if live.get("title") == UNUSED_TITLE:
            entry["status"] = "already_retired"
            continue
        body = retire_body(live)
        entry["changes"] = diff(body, live)
        if dry_run:
            entry["status"] = "would_retire"
            continue
        client.put(f"/v1/routines/{routine_id}", body, routine_id=routine_id, overlay_id=doc["id"],
                   overlay_hash=overlay_hash)
        writes += 1
        read_back = _get_routine(client, routine_id)
        cache.upsert_routine(read_back)
        remaining = diff(body, read_back)
        _append(ctx, _check_line(ctx, "retire", routine_id, doc, overlay_hash, remaining), RETIRE_SCHEMA)
        entry["verified"] = not remaining
        entry["status"] = "retired" if not remaining else "failed"
        if remaining:
            failure = (entry, remaining)
    report = _report("retire", doc, ctx, entries, dry_run=dry_run, writes=writes)
    if failure:
        entry, remaining = failure
        raise ValidationError(
            f"{entry['title']} did not read back as retired ({len(remaining)} difference(s)); "
            "later routines were not retired.",
            details=[{"path": c["path"], "message": f"sent {c['after']!r}, Hevy has {c['before']!r}"}
                     for c in remaining],
            data=report,
        )
    return report


def _routines_in_live_overlays(root, doc, today):
    """{routine id: overlay id} for routines another overlay that has not ended still uses."""
    found = {}
    for other in overlay_module.list(root):
        if other["id"] == doc["id"] or other["span"]["end"] < today.isoformat():
            continue
        for routine_id in session_routines(root, other):
            if routine_id:
                found.setdefault(routine_id, other["id"])
    return found


def create(ctx, overlay_id, dry_run):
    """Give every session with no Hevy routine one, and record each new id in state.json, never in the overlay.

    A temporary session reuses a temporary routine no other overlay still
    carries before a new one is created in the one-off folder (created first
    when state.json has none); any other session gets a new routine in the
    program folder. Refuses (exit 3) as push does; a read-back that differs
    exits 1 with the report, keeping the ids already recorded.
    """
    _require_hevy(ctx)
    doc = _load(ctx, overlay_id)
    today = ctx.today()
    ids = session_routines(ctx.root, doc)
    planned = [routine_id or _NEW + session["session_id"] for routine_id, session in zip(ids, doc["sessions"])]
    reasons = push_refusals(ctx.root, doc, today, planned)
    if reasons:
        raise _refused(doc, reasons, outcome="gets no new routines")
    overlay_hash = doc["approval"]["hash"]
    needed = [(key, session, carries) for key, session, carries in plan(doc, today, planned) if key.startswith(_NEW)]
    folder = {"title": ONE_OFF_FOLDER_TITLE, "id": None, "status": "not_needed"}
    if not needed:
        return _create_report(doc, ctx, [], folder, dry_run, 0)

    state_doc = state_module.load(ctx.root)
    _require_program_sessions(ctx.root, doc, [session for _, session, _ in needed])
    hevy = state_doc["hevy"]
    client = HevyClient.from_context(ctx)
    spare = _spare_temporary(ctx.root, doc, today, hevy, ids)
    work = []
    for _, session, carries in needed:
        reuse = spare.pop(0) if session.get("temporary") and spare else None
        live = _get_routine(client, reuse) if reuse else None
        work.append((session, carries, reuse, live))
    one_off = hevy["folders"]["one_off"]
    if one_off is None and any(s.get("temporary") and not reuse for s, _, reuse, _ in work):
        folder["status"] = "would_create" if dry_run else "pending"
    else:
        folder.update(id=one_off, status="exists" if one_off is not None else "not_needed")

    entries, bodies = [], []
    for session, carries, reuse, live in work:
        body = _create_body(doc, session, live, hevy["folders"], folder["id"])
        bodies.append(body)
        entry = _entry(reuse, session, carries, body["routine"]["title"], diff(body, live or {}),
                       ("would_reuse" if dry_run else "pending") if reuse else
                       ("would_create" if dry_run else "pending"))
        entry["reuse"] = {"title": live.get("title")} if reuse else None
        entry["folder_id"] = body["routine"].get("folder_id")
        entry["targets"] = [f"{line['exercise_id']}: {_target(exercise['notes'])}"
                            for line, exercise in zip(session["exercises"], body["routine"]["exercises"])]
        entries.append(entry)
    if dry_run:
        return _create_report(doc, ctx, entries, folder, dry_run, 0)

    writes = 0
    if folder["status"] == "pending":
        answer = client.post("/v1/routine_folders", {"routine_folder": {"title": ONE_OFF_FOLDER_TITLE}},
                             overlay_id=doc["id"], overlay_hash=overlay_hash)
        writes += 1
        folder.update(id=_folder_id(answer), status="created")
        hevy["folders"]["one_off"] = folder["id"]
        _save_state(ctx.root, state_doc)
        for entry, body, (session, _, reuse, _) in zip(entries, bodies, work):
            if session.get("temporary") and not reuse:
                body["routine"]["folder_id"] = entry["folder_id"] = folder["id"]

    cache = HevyCache(ctx.root, clock=ctx.now)
    for position, (entry, body, (session, _, reuse, _)) in enumerate(zip(entries, bodies, work)):
        if reuse:
            client.put(f"/v1/routines/{reuse}", body, routine_id=reuse, overlay_id=doc["id"],
                       overlay_hash=overlay_hash)
            routine_id = reuse
        else:
            answer = client.post("/v1/routines", body, overlay_id=doc["id"], overlay_hash=overlay_hash)
            routine_id = _new_routine_id(answer)
        writes += 1
        entry["routine_id"] = routine_id
        _record(hevy, doc, session, routine_id)
        _save_state(ctx.root, state_doc)
        read_back = _get_routine(client, routine_id)
        cache.upsert_routine(read_back)
        remaining = diff(body, read_back)
        _append(ctx, _check_line(ctx, "verify", routine_id, doc, overlay_hash, remaining), VERIFY_SCHEMA)
        entry["verified"] = not remaining
        entry["status"] = ("reused" if reuse else "created") if not remaining else "failed"
        if remaining:
            for later in entries[position + 1:]:
                later["status"] = "not_reached"
            raise ValidationError(
                f"{entry['title']} did not read back as written ({len(remaining)} difference(s)); "
                "its id is recorded in state.json, and later routines were not written.",
                details=[{"path": c["path"], "message": f"sent {c['after']!r}, Hevy has {c['before']!r}"}
                         for c in remaining],
                data=_create_report(doc, ctx, entries, folder, dry_run, writes),
            )
    return _create_report(doc, ctx, entries, folder, dry_run, writes)


def _require_program_sessions(root, doc, sessions):
    if not program_module.exists(root):
        return
    known = {session["id"] for session in program_module.load(root)["sessions"]}
    missing = sorted({s["session_id"] for s in sessions if not s.get("temporary") and s["session_id"] not in known})
    if missing:
        raise ValidationError(
            f"Overlay {doc['id']}: session(s) {', '.join(missing)} are not temporary and not in {paths.PROGRAM}, "
            "so they cannot get a program routine; mark them temporary or add them to the program"
        )


def _spare_temporary(root, doc, today, hevy, ids):
    """Temporary routines free to reuse, in state.json order: none that carries a coming session elsewhere."""
    busy = set(ids) | _carrying(root, doc, today)
    return [entry["routine_id"] for entry in hevy["temporary_routines"] if entry["routine_id"] not in busy]


def _carrying(root, doc, today):
    """Routine ids carrying a session, today or later, of another overlay that is in force that day."""
    found = set()
    for other in overlay_module.list(root):
        if other["id"] == doc["id"] or other["span"]["end"] < today.isoformat():
            continue
        for routine_id, session in zip(session_routines(root, other), other["sessions"]):
            if not routine_id or session["date"] < today.isoformat():
                continue
            governing = overlay_module.in_force(root, session["date"])
            if governing and governing[0]["id"] == other["id"]:
                found.add(routine_id)
    return found


def _create_body(doc, session, live, folders, one_off_folder):
    if live is not None:
        return intended_body(doc, session, live)
    folder_id = one_off_folder if session.get("temporary") else folders["program"]
    return intended_body(doc, session, {"folder_id": folder_id})


def _record(hevy, doc, session, routine_id):
    if not session.get("temporary"):
        hevy["routines"][routine_id] = {"session_id": session["session_id"]}
        return
    carrier = {"routine_id": routine_id, "overlay_id": doc["id"], "session_id": session["session_id"]}
    for position, entry in enumerate(hevy["temporary_routines"]):
        if entry["routine_id"] == routine_id:
            hevy["temporary_routines"][position] = carrier
            return
    hevy["temporary_routines"].append(carrier)


def _save_state(root, doc):
    jsonio.write_doc(state_module.path_for(root), doc, dry_run=False)


def _new_routine_id(answer):
    routine = created_routine(answer)
    if routine is None:
        raise ValidationError(f"Hevy created a routine but its answer names no id; run {_PULL} and record the "
                              f"new routine in {paths.STATE} by hand")
    return routine["id"]


def _folder_id(answer):
    folder = answer.get("routine_folder", answer) if isinstance(answer, dict) else None
    folder_id = folder.get("id") if isinstance(folder, dict) else None
    if not isinstance(folder_id, int) or isinstance(folder_id, bool):
        raise ValidationError(f"Hevy created the {ONE_OFF_FOLDER_TITLE} folder but its answer names no id; "
                              f"run {_PULL} and set hevy.folders.one_off in {paths.STATE} by hand")
    return folder_id


def _create_report(doc, ctx, entries, folder, dry_run, writes):
    return _report("create", doc, ctx, entries, dry_run=dry_run, writes=writes, folder=dict(folder))


def _load_text(value, mode, unit, load=None):
    if value is None:
        return "no weight"
    if load is not None and abs(load["hevy_kg"] - value) <= WEIGHT_TOLERANCE_KG:
        text = units.format_load(load)
    elif mode in units.LOADED_MODES:
        text = units.format_load(units.make_load(units.from_hevy_kg(value, mode, unit), mode, unit))
    else:
        return f"{units.json_number(value)} kg in Hevy"
    return f"{text} {unit}" if mode == "total" else text


def _reps_text(set_):
    if set_.get("rep_range"):
        return f"{set_['rep_range']['start']}–{set_['rep_range']['end']}"
    if set_.get("reps") is not None:
        return str(set_["reps"])
    if set_.get("duration_seconds") is not None:
        return f"{set_['duration_seconds']} s"
    if set_.get("distance_meters") is not None:
        return f"{set_['distance_meters']} m"
    return "?"


def _set_text(set_, mode, unit, load=None):
    kind = "" if set_.get("type") == "normal" else f"{set_.get('type')} "
    return f"{kind}{_reps_text(set_)} @ {_load_text(set_.get('weight_kg'), mode, unit, load)}"


def _target(notes):
    for line in (notes or "").splitlines():
        if line.startswith("Target:"):
            return line
    return "rewritten"


def _value_text(field, value):
    if value is None:
        return "none"
    if field == "rep_range":
        return f"{value['start']}–{value['end']}"
    if field in ("rest_seconds", "duration_seconds"):
        return f"{value} s"
    if field == "distance_meters":
        return f"{value} m"
    return str(value)


_FIELD_NAMES = {"reps": "reps", "rep_range": "rep range", "type": "set type", "duration_seconds": "duration",
                "distance_meters": "distance", "rest_seconds": "rest", "superset_id": "superset"}


def _parse_path(path):
    """('routine', field) | ('exercise', i, None|field) | ('set', i, j, None|field)."""
    if not path.startswith("exercises["):
        return ("routine", path)
    head, _, rest = path.partition("]")
    index = int(head[len("exercises["):])
    if not rest:
        return ("exercise", index, None)
    rest = rest[1:]
    if not rest.startswith("sets["):
        return ("exercise", index, rest)
    set_head, _, field = rest.partition("]")
    return ("set", index, int(set_head[len("sets["):]), field[1:] or None)


def _sets_label(indexes):
    numbers = [index + 1 for index in indexes]
    if len(numbers) == 1:
        return f"set {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"sets {numbers[0]}–{numbers[-1]}"
    return "sets " + ", ".join(str(n) for n in numbers)


class _Exercises:
    """Names, load modes and overlay loads for a report entry's exercises, by position."""

    def __init__(self, entry):
        self._by_index = {item["index"]: item for item in entry["exercises"]}

    def name(self, index):
        item = self._by_index.get(index)
        return item["exercise_id"] if item else f"exercise {index + 1}"

    def mode(self, index):
        item = self._by_index.get(index)
        return item["load_mode"] if item else None

    def load(self, index, set_index):
        loads = self._by_index[index]["loads"] if index in self._by_index else []
        return loads[set_index] if set_index < len(loads) else None


def _change_line(change, parsed, exercises, unit):
    before, after = change["before"], change["after"]
    if parsed[0] == "routine":
        return f"{parsed[1].replace('_', ' ')}: {before!r} → {after!r}"
    if parsed[0] == "exercise" and parsed[2] is None:
        if before is None:
            return f"{exercises.name(parsed[1])} added ({len(after['sets'])} sets)"
        if after is None:
            return f"exercise {parsed[1] + 1} removed ({before['exercise_template_id']})"
        return f"exercise {parsed[1] + 1} replaced: {before['exercise_template_id']} → {exercises.name(parsed[1])}"
    if parsed[0] == "exercise" and parsed[2] == "notes":
        return f"{exercises.name(parsed[1])} note: {_target(after)}"
    if parsed[0] == "exercise":
        field = parsed[2]
        return (f"{exercises.name(parsed[1])} {_FIELD_NAMES.get(field, field)}: "
                f"{_value_text(field, before)} → {_value_text(field, after)}")
    _, index, set_index, _ = parsed
    if before is None:
        return (f"{exercises.name(index)} set {set_index + 1} added: "
                f"{_set_text(after, exercises.mode(index), unit, exercises.load(index, set_index))}")
    return f"{exercises.name(index)} set {set_index + 1} removed"


def _change_lines(entry, unit):
    """One line per change, with equal changes to one field across sets folded into one line."""
    exercises = _Exercises(entry)
    items, groups = [], {}
    for change in entry["changes"]:
        parsed = _parse_path(change["path"])
        if parsed[0] == "set" and parsed[3] is not None:
            _, index, set_index, field = parsed
            key = (index, field, json.dumps(change["before"]), json.dumps(change["after"]))
            if key not in groups:
                groups[key] = (change, [])
                items.append(("group", key))
            groups[key][1].append(set_index)
        else:
            items.append(("line", _change_line(change, parsed, exercises, unit)))
    lines = []
    for kind, item in items:
        if kind == "line":
            lines.append(f"  - {item}")
            continue
        index, field = item[:2]
        change, indexes = groups[item]
        if field == "weight_kg":
            text = (f"{_load_text(change['before'], exercises.mode(index), unit)} → "
                    f"{_load_text(change['after'], exercises.mode(index), unit, exercises.load(index, indexes[0]))}")
        else:
            text = (f"{_FIELD_NAMES.get(field, field)} {_value_text(field, change['before'])} → "
                    f"{_value_text(field, change['after'])}")
        lines.append(f"  - {exercises.name(index)} {_sets_label(indexes)}: {text}")
    return lines


def summary(report):
    """Plain text for the athlete or a permission prompt: each routine that changes, and how."""
    entries = report["routines"]
    unit = report["unit"]
    action = report["action"]
    changed = [entry for entry in entries if entry["changes"]]
    overlay_id = report["overlay_id"]
    if action == "retire":
        retiring = [e for e in entries if e["status"] in ("would_retire", "retired", "failed")]
        lines = [f"Overlay {overlay_id}: {len(retiring)} temporary routine(s) retitled \"{UNUSED_TITLE}\"."]
        lines += [f"{e['title']} → {UNUSED_TITLE}" for e in retiring]
        lines += [f"{e['title'] or e['routine_id']}: left alone ({e['status'].replace('_', ' ')})"
                  for e in entries if e["status"] in ("in_use", "already_retired")]
        return "\n".join(lines)
    if action == "create":
        return _create_summary(report)
    if action == "verify":
        matching = sum(1 for e in entries if e["verified"])
        lines = [f"Overlay {overlay_id} against Hevy: {matching} of {len(entries)} routine(s) match."]
    elif not changed:
        return f"Overlay {overlay_id} → Hevy: all {len(entries)} routine(s) already match; nothing to write."
    else:
        verb = "would change" if report.get("dry_run") or action == "diff" else "change"
        lines = [f"Overlay {overlay_id} → Hevy: {len(changed)} of {len(entries)} routine(s) {verb}."]
    for entry in changed:
        structural = sum(1 for c in entry["changes"] if c["class"] == STRUCTURAL)
        lines.append(f"{entry['title']} ({render.day_label(entry['date'])}): {len(entry['changes'])} change(s), "
                     f"{structural} structural")
        lines += _change_lines(entry, unit)
    return "\n".join(lines)


def _create_summary(report):
    entries = report["routines"]
    overlay_id = report["overlay_id"]
    if not entries:
        return f"Overlay {overlay_id} → Hevy: every session already has a routine; nothing to create."
    reused = sum(1 for entry in entries if entry["reuse"])
    lines = [f"Overlay {overlay_id} → Hevy: {len(entries) - reused} new routine(s), "
             f"{reused} temporary routine(s) reused."]
    folder = report["folder"]
    if folder["status"] == "would_create":
        lines.append(f'Folder "{folder["title"]}" is created first; {paths.STATE} has none.')
    elif folder["status"] == "created":
        lines.append(f'Folder "{folder["title"]}" created ({folder["id"]}) and recorded in {paths.STATE}.')
    for entry in entries:
        where = f"{entry['title']} ({render.day_label(entry['date'])})"
        if entry["reuse"]:
            lines.append(f"{where}: reuses \"{entry['reuse']['title']}\" ({entry['routine_id']})")
        else:
            folder = f" in folder {entry['folder_id']}" if entry["folder_id"] is not None else ""
            lines.append(f"{where}: new routine{folder}")
        lines += [f"  - {target}" for target in entry["targets"]]
    return "\n".join(lines)
