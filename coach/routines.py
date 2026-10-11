"""Overlay to Hevy routines: build, diff, push, verify and retire (contract C9, C10, C12).

`intended_body` turns one overlay session into the PUT body for its Hevy
routine; `diff` compares that body with a routine as Hevy returns it. The
push refuses an overlay that is unapproved, edited after approval, blocked,
ended or superseded, and a routine edited in the app since the cache was
read. It writes each changed routine once, reads it back and logs whether
the read-back matches.
"""

import json

from coach import dates, jsonio
from coach import overlay as overlay_module
from coach import paths, render, units
from coach.errors import ConfigError, RefusedError, ValidationError
from coach.hevy.cache import HevyCache
from coach.hevy.client import HevyClient, timestamp
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

_SET_FIELDS = ("type", "weight_kg", "reps", "rep_range", "duration_seconds", "distance_meters")
_PULL = "python3 -m coach hevy pull"


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


def unmapped_sessions(doc):
    return [s for s in doc["sessions"] if not s.get("hevy_routine_id")]


def _require_mapped(doc):
    unmapped = unmapped_sessions(doc)
    if unmapped:
        names = ", ".join(f"{s['session_id']} ({s['date']})" for s in unmapped)
        raise ValidationError(
            f"Overlay {doc['id']} has session(s) with no Hevy routine: {names}; "
            "routines push only updates routines that exist"
        )


def plan(doc, today):
    """One (routine id, session, every date it carries) per routine, in overlay order.

    A routine used by several sessions carries the next one on or after
    today, or the last one when all have passed. Sessions with no routine
    are left out (see `unmapped_sessions`).
    """
    grouped = {}
    for session in doc["sessions"]:
        if session.get("hevy_routine_id"):
            grouped.setdefault(session["hevy_routine_id"], []).append(session)
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


def push_refusals(root, doc, today):
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
        for _, session, _ in plan(doc, today):
            if session["date"] < today.isoformat():
                continue
            governing = overlay_module.in_force(root, session["date"])
            if governing and governing[0]["id"] != doc["id"]:
                refuse(f"{session['title']} on {session['date']} is governed by overlay {governing[0]['id']}, "
                       f"which supersedes {doc['id']}")
    return found


def _refused(doc, reasons):
    first = reasons[0]["message"]
    more = f" (and {len(reasons) - 1} more reason(s))" if len(reasons) > 1 else ""
    return RefusedError(f"Overlay {doc['id']} is not pushed: {first}{more}.", details=reasons)


def _get_routine(client, routine_id):
    body = client.get(f"/v1/routines/{routine_id}")
    routine = body.get("routine") if isinstance(body, dict) else None
    if not isinstance(routine, dict):
        raise ValidationError(f"Hevy answered GET /v1/routines/{routine_id} without a routine")
    return routine


def _routines(ctx, cache, routine_ids, refresh, dry_run, client=None):
    """{routine id: routine}: re-read from Hevy with refresh (and cached unless dry_run), else from the cache."""
    if refresh:
        client = client or HevyClient.from_context(ctx)
        found = {}
        for routine_id in routine_ids:
            found[routine_id] = _get_routine(client, routine_id)
            if not dry_run:
                cache.upsert_routine(found[routine_id])
        return found
    found = {routine_id: cache.routine(routine_id) for routine_id in routine_ids}
    missing = [routine_id for routine_id, routine in found.items() if routine is None]
    if missing:
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


def _report(action, doc, ctx, entries, dry_run=False, writes=0):
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
    _require_mapped(doc)
    routine_plan = plan(doc, ctx.today())
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
    reasons = push_refusals(ctx.root, doc, today)
    if reasons:
        raise _refused(doc, reasons)
    _require_mapped(doc)
    overlay_hash = doc["approval"]["hash"]
    routine_plan = plan(doc, today)
    _warn_shared(ctx, doc, routine_plan)
    client = HevyClient.from_context(ctx)
    cache = HevyCache(ctx.root, clock=ctx.now)
    routine_ids = [routine_id for routine_id, _, _ in routine_plan]
    cached = _routines(ctx, cache, routine_ids, refresh, dry_run, client=client)
    live = cached if refresh else {routine_id: _get_routine(client, routine_id) for routine_id in routine_ids}
    moved = [cached[r] for r in routine_ids if live[r].get("updated_at") != cached[r].get("updated_at")]
    if moved:
        names = ", ".join(f"{r.get('title')} ({r.get('id')})" for r in moved)
        raise RefusedError(
            f"Overlay {doc['id']} is not pushed: {names} changed in Hevy since the cache was read; "
            f"run routines diff --overlay {doc['id']} --refresh and review before pushing.",
            details=[{"path": None, "message": f"{r.get('title')}: cached updated_at {r.get('updated_at')}, "
                                               f"Hevy now has {live[r['id']].get('updated_at')}"} for r in moved],
        )

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
    temporary = []
    for session in doc["sessions"]:
        if session.get("temporary") and session.get("hevy_routine_id"):
            if session["hevy_routine_id"] not in [s["hevy_routine_id"] for s in temporary]:
                temporary.append(session)
    in_use = _routines_in_live_overlays(ctx.root, doc, today)
    client = HevyClient.from_context(ctx)
    cache = HevyCache(ctx.root, clock=ctx.now)
    entries, writes, failure = [], 0, None
    for session in temporary:
        routine_id = session["hevy_routine_id"]
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
        for session in other["sessions"]:
            if session.get("hevy_routine_id"):
                found.setdefault(session["hevy_routine_id"], other["id"])
    return found


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
