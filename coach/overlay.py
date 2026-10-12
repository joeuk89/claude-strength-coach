"""Overlays: the per-exercise prescription in force for a span of days (contract C10).

One JSON file per programming pass in `data/overlays/<id>.json`. The coach
writes a draft in athlete units; `build` turns it into a complete overlay,
building every load object through `coach.units`. `validate` checks the
schema, the load arithmetic and the overlay's internal consistency.
"""

import builtins
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from coach import config as config_module
from coach import dates, jsonio, paths, timing, units
from coach.activity.records import utc_text
from coach.errors import ConfigError, ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "overlay"
DRAFT_SCHEMA = "overlay_draft"
WORKING_SET_TYPES = ("normal", "dropset", "failure")
NO_DATA = "no_data"

SCHEMA_PROBLEM = "schema"
ARITHMETIC_PROBLEM = "arithmetic"

_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
_LOAD_FIELDS = ("mode", "unit", "per_hand", "hevy_total", "hevy_kg")
_LINE_DEFAULTS = {
    "hevy_template_id": None, "rest_seconds": None, "superset_id": None, "cues": None, "focus": None,
    "target_note": None, "change": None, "provenance": None, "fold": None,
}


def current_version():
    return jsonio.current_version(jsonio.load_schema(SCHEMA))


def is_working(set_):
    return set_.get("type") in WORKING_SET_TYPES


def base_id(span_start, kind):
    return f"{span_start}-{kind.replace('_', '-')}"


def path_for(root, overlay_id):
    if not isinstance(overlay_id, str) or not _ID.fullmatch(overlay_id):
        raise ValidationError(f"{overlay_id!r} is not an overlay id (YYYY-MM-DD-<kind>)")
    return Path(root) / paths.OVERLAYS_DIR / f"{overlay_id}.json"


def ids(root):
    directory = Path(root) / paths.OVERLAYS_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json") if _ID.fullmatch(p.stem))


def read_json(path):
    """A JSON file's content, or a ValidationError naming the file."""
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"{path} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def load(root, overlay_id):
    """The overlay with this id, schema-checked. Raises ValidationError when absent or malformed."""
    path = path_for(root, overlay_id)
    if not path.is_file():
        raise ValidationError(f"No overlay {overlay_id}: {path} does not exist")
    doc = jsonio.read_doc(path, SCHEMA)
    if doc["id"] != overlay_id:
        raise ValidationError(f"{path} holds overlay {doc['id']}; the file must be named {doc['id']}.json")
    return doc


def list(root):
    return [load(root, overlay_id) for overlay_id in ids(root)]


def _as_date(day):
    return dates.parse_date(day) if isinstance(day, str) else day


def in_force(root, day):
    """(overlay, session) in force on `day`, or None when no overlay's span holds it.

    Of the overlays whose span holds the day and which have a session dated
    that day, the latest created wins. On a day no covering overlay has a
    session, the latest created covering overlay is in force with session
    None.
    """
    return pick_in_force(list(root), day)


def pick_in_force(docs, day):
    """`in_force` over overlays already loaded."""
    day = _as_date(day).isoformat()
    covering = [doc for doc in docs if doc["span"]["start"] <= day <= doc["span"]["end"]]
    with_session = [doc for doc in covering if any(s["date"] == day for s in doc["sessions"])]
    pool = with_session or covering
    if not pool:
        return None
    doc = max(pool, key=lambda d: (dates.parse_timestamp(d["created_at"]), d["id"]))
    session = next((s for s in doc["sessions"] if s["date"] == day), None)
    return doc, session


def sessions_on(doc, day):
    day = _as_date(day).isoformat()
    return [s for s in doc["sessions"] if s["date"] == day]


def created_on(doc, zone=None):
    return dates.parse_timestamp(doc["created_at"]).astimezone(dates.zone(zone) if zone else None).date()


def moved_away(docs):
    """(original date, session id) of each session moved by an overlay that is in force on its new date."""
    found = set()
    for doc in docs:
        for session in doc["sessions"]:
            if session.get("moved_from"):
                picked = pick_in_force(docs, session["date"])
                if picked and picked[0]["id"] == doc["id"]:
                    found.add((session["moved_from"], session["session_id"]))
    return found


def planned(docs, days, adopted=None, zone=None):
    """(overlay, session) the overlay in force plans on each day (contract C41).

    A moved session is planned on its new date only. A day before `adopted` plans only from an overlay made
    before it, one written for an earlier program.
    """
    moved = moved_away(docs)
    found = []
    for day in days:
        picked = pick_in_force(docs, day)
        if not picked:
            continue
        doc = picked[0]
        if adopted is not None and _as_date(day) < adopted and created_on(doc, zone) >= adopted:
            continue
        found += [(doc, s) for s in sessions_on(doc, day) if (s["date"], s["session_id"]) not in moved]
    return found


def approval_hash(doc):
    """The C7 canonical hash of the overlay with `approval` removed."""
    return jsonio.canonical_hash({key: value for key, value in doc.items() if key != "approval"})


def is_approved(doc):
    approval = doc.get("approval")
    return bool(approval) and approval.get("hash") == approval_hash(doc)


def approve(doc, now):
    """A copy of `doc` stamped approved at `now`."""
    approved = dict(doc)
    approved["approval"] = {"approved_at": _timestamp(now), "hash": approval_hash(doc)}
    return approved


def unresolved_blocks(doc):
    return [flag for flag in doc.get("flags", []) if flag["severity"] == "block" and not flag["resolved"]]


def _timestamp(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



def validate(doc, root, config=None):
    """Every problem with an overlay document, each with a JSONPath; empty when it is sound."""
    return [error for _, error in problems(doc, root, config)]


def problems(doc, root, config=None):
    """Like `validate`, but each error is paired with its kind: SCHEMA_PROBLEM or ARITHMETIC_PROBLEM."""
    version_error = _version_error(doc)
    if version_error:
        return [(SCHEMA_PROBLEM, version_error)]
    config = config if config is not None else config_module.load(root)
    schema_errors = validate_schema(doc, jsonio.load_schema(SCHEMA))
    found = [(SCHEMA_PROBLEM, error) for error in schema_errors]
    found += [(ARITHMETIC_PROBLEM, error) for error in _arithmetic(doc, config, {e.path for e in schema_errors})]
    if not schema_errors:
        found += [(SCHEMA_PROBLEM, error) for error in _structure(doc, config)]
    return found


def _version_error(doc):
    if not isinstance(doc, dict):
        return None
    version = doc.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    current = current_version()
    if version > current:
        return Error("$.schema_version",
                     f"schema_version {version} is newer than this coach reads ({current}); run /framework-sync")
    if version < current:
        return Error("$.schema_version",
                     f"schema_version {version} is older than the current {current}; "
                     "run python3 -m coach migrate run")
    return None


def _lines(doc):
    """Yield (session index, exercise index, session, exercise) for every well-formed line."""
    sessions = doc.get("sessions") if isinstance(doc, dict) else None
    for s_index, session in enumerate(sessions if isinstance(sessions, builtins.list) else []):
        exercises = session.get("exercises") if isinstance(session, dict) else None
        for e_index, exercise in enumerate(exercises if isinstance(exercises, builtins.list) else []):
            if isinstance(exercise, dict):
                yield s_index, e_index, session, exercise


def _set_groups(exercise, line_path):
    """Yield (path, sets) for the line's sets and its override's proposed sets."""
    if isinstance(exercise.get("sets"), builtins.list):
        yield f"{line_path}.sets", exercise["sets"]
    override = exercise.get("override")
    if isinstance(override, dict) and isinstance(override.get("proposed_sets"), builtins.list):
        yield f"{line_path}.override.proposed_sets", override["proposed_sets"]


def _all_sets(doc):
    for s_index, e_index, session, exercise in _lines(doc):
        line_path = f"$.sessions[{s_index}].exercises[{e_index}]"
        for group_path, sets in _set_groups(exercise, line_path):
            for index, set_ in enumerate(sets):
                if isinstance(set_, dict):
                    yield f"{group_path}[{index}]", session, exercise, set_


def _arithmetic(doc, config, schema_error_paths):
    errors = []
    unit = config.athlete.units
    for set_path, _, exercise, set_ in _all_sets(doc):
        load = set_.get("load")
        load_path = f"{set_path}.load"
        if not isinstance(load, dict) or any(p.startswith(load_path) for p in schema_error_paths):
            continue
        for message in units.check_load(load):
            field, _, rest = message.partition(": ")
            if field in _LOAD_FIELDS and rest:
                errors.append(Error(f"{load_path}.{field}", rest))
            else:
                errors.append(Error(load_path, message))
        mode = exercise.get("load_mode")
        if load.get("mode") != mode and mode in units.LOADED_MODES:
            errors.append(Error(f"{load_path}.mode",
                                f"expected {mode} (the line's load_mode), found {load.get('mode')}"))
        if load.get("unit") != unit:
            errors.append(Error(f"{load_path}.unit", f"expected {unit} ([athlete] units), found {load.get('unit')}"))
    return errors


def _real_date(value, path, errors):
    try:
        return dates.parse_date(value)
    except ValueError as exc:
        errors.append(Error(path, str(exc)))
        return None


def _structure(doc, config):
    errors = []
    start = _real_date(doc["span"]["start"], "$.span.start", errors)
    end = _real_date(doc["span"]["end"], "$.span.end", errors)
    if start and end and end < start:
        errors.append(Error("$.span", f"span ends ({end}) before it starts ({start})"))
    try:
        dates.parse_timestamp(doc["created_at"])
    except ValueError as exc:
        errors.append(Error("$.created_at", str(exc)))

    base = base_id(doc["span"]["start"], doc["kind"])
    if doc["id"] != base and not re.fullmatch(re.escape(base) + r"-([2-9]|[1-9]\d+)", doc["id"]):
        errors.append(Error("$.id", f"expected {base} (span start and kind), or {base}-2, -3 ...; found {doc['id']}"))
    if doc["supersedes"] == doc["id"]:
        errors.append(Error("$.supersedes", "an overlay cannot supersede itself"))

    errors += _sessions(doc, config, start, end)
    errors += _flags(doc)
    return errors


def _sessions(doc, config, start, end):
    errors = []
    seen = set()
    no_data = {(f["session_id"], f["exercise_id"]) for f in doc["flags"] if f["code"] == NO_DATA}
    for s_index, session in enumerate(doc["sessions"]):
        path = f"$.sessions[{s_index}]"
        day = _real_date(session["date"], f"{path}.date", errors)
        if day and start and end and not start <= day <= end:
            errors.append(Error(f"{path}.date", f"{day} is outside the span {start}..{end}"))
        key = (session["session_id"], session["date"])
        if key in seen:
            errors.append(Error(path, f"session {key[0]} appears twice on {key[1]}"))
        seen.add(key)
        if session["location"] is not None:
            try:
                config_module.equipment_for(config, session["location"])
            except ConfigError:
                errors.append(Error(
                    f"{path}.location",
                    f'no [equipment.locations.{session["location"]}] table in config.toml '
                    f'for location "{session["location"]}"',
                ))
        for e_index, exercise in enumerate(session["exercises"]):
            line_path = f"{path}.exercises[{e_index}]"
            flagged = (session["session_id"], exercise["exercise_id"]) in no_data
            for group_path, sets in _set_groups(exercise, line_path):
                for index, set_ in enumerate(sets):
                    errors += _set_errors(set_, f"{group_path}[{index}]", exercise["load_mode"], flagged)
    return errors


def _set_errors(set_, path, mode, flagged):
    errors = []
    reps, rep_range = set_.get("reps"), set_.get("rep_range")
    timed = mode in ("duration", "distance")
    if reps is not None and rep_range is not None:
        errors.append(Error(path, "give reps or rep_range, not both"))
    elif reps is None and rep_range is None and not timed:
        errors.append(Error(path, "give reps or rep_range"))
    if rep_range is not None and rep_range["start"] > rep_range["end"]:
        errors.append(Error(f"{path}.rep_range", f"start {rep_range['start']} is above end {rep_range['end']}"))
    if set_.get("rep_out") and (set_.get("type") != "normal" or reps is None or timed):
        errors.append(Error(f"{path}.rep_out", "a rep-out set is a normal set with fixed reps"))
    if mode == "duration" and set_.get("duration_seconds") is None:
        errors.append(Error(path, "a duration set needs duration_seconds"))
    if mode == "distance" and set_.get("distance_meters") is None:
        errors.append(Error(path, "a distance set needs distance_meters"))

    load = set_.get("load")
    if mode not in units.LOADED_MODES:
        if load is not None:
            errors.append(Error(f"{path}.load", f"load mode {mode} carries no load; leave load null"))
    elif load is None and is_working(set_) and not flagged:
        errors.append(Error(
            f"{path}.load",
            f"a {mode} working set needs a load, unless the overlay has a no_data flag for this session and exercise",
        ))
    return errors


def _flags(doc):
    errors = []
    lines = {}
    for session in doc["sessions"]:
        lines.setdefault(session["session_id"], set()).update(e["exercise_id"] for e in session["exercises"])
    for index, flag in enumerate(doc["flags"]):
        path = f"$.flags[{index}]"
        session_id, exercise_id = flag["session_id"], flag["exercise_id"]
        if session_id is None and exercise_id is not None:
            errors.append(Error(f"{path}.session_id", "a flag that names an exercise must name its session"))
        elif session_id is not None and session_id not in lines:
            errors.append(Error(f"{path}.session_id", f"no session {session_id} in this overlay"))
        elif exercise_id is not None and exercise_id not in lines[session_id]:
            errors.append(Error(f"{path}.exercise_id", f"session {session_id} has no exercise {exercise_id}"))
        if flag["resolved"] and flag["resolution"] is None:
            errors.append(Error(f"{path}.resolution", "a resolved flag needs a resolution"))
        if not flag["resolved"] and flag["resolution"] is not None:
            errors.append(Error(f"{path}.resolution", "an unresolved flag has no resolution yet"))
    return errors


def _start(draft_session, where, zone, errors):
    """The session's planned start as a C7 timestamp: local text in `zone` or text with an offset, on its date."""
    text = draft_session.get("start")
    if text is None:
        return None
    try:
        return utc_text(timing.parse_start(text, draft_session["date"], zone))
    except ValueError as exc:
        errors.append(Error(where, str(exc)))
        return None


def build(draft, config, *, root=None, now=None):
    """A complete overlay from a draft in athlete units.

    `root` (default: the directory holding config.toml) is read for the
    program's session locations and for a free id; `now` stamps
    `created_at` when the draft has none. Raises ValidationError, with a
    JSONPath per problem, when the draft or the overlay it builds is invalid.
    """
    if isinstance(draft, dict) and draft.get("schema_version") == 5:
        draft = dict(draft, schema_version=6)  # v6 only added optional session fields
    draft_errors = validate_schema(draft, jsonio.load_schema(DRAFT_SCHEMA))
    if draft_errors:
        raise ValidationError(
            f"The draft is not a valid overlay draft ({len(draft_errors)} problem(s))",
            details=[error.to_json() for error in draft_errors],
        )
    root = Path(root) if root is not None else config.path.parent
    now = now or datetime.now(timezone.utc)
    unit = config.athlete.units
    locations = _program_locations(root)
    zone = dates.zone(config.athlete.timezone) if config.athlete.timezone else None
    load_errors = []

    sessions = []
    for s_index, draft_session in enumerate(draft["sessions"]):
        session_id = draft_session["session_id"]
        sessions.append({
            "session_id": session_id,
            "date": draft_session["date"],
            "title": draft_session["title"],
            "hevy_routine_id": draft_session.get("hevy_routine_id"),
            "temporary": draft_session.get("temporary", False),
            "location": draft_session.get("location", locations.get(session_id)),
            "focus": draft_session.get("focus"),
            "moved_from": draft_session.get("moved_from"),
            "start": _start(draft_session, f"$.sessions[{s_index}].start", zone, load_errors),
            "duration_minutes": draft_session.get("duration_minutes"),
            "exercises": [
                _build_line(line, unit, f"$.sessions[{s_index}].exercises[{e_index}]", load_errors)
                for e_index, line in enumerate(draft_session["exercises"])
            ],
        })

    if load_errors:
        raise ValidationError(f"The draft has {len(load_errors)} load(s) or start time(s) that cannot be built",
                              details=[error.to_json() for error in load_errors])

    doc = {
        "schema_version": current_version(),
        "id": draft.get("id") or _free_id(root, base_id(draft["span"]["start"], draft["kind"])),
        "kind": draft["kind"],
        "created_at": draft.get("created_at") or _timestamp(now),
        "span": {"start": draft["span"]["start"], "end": draft["span"]["end"]},
        "supersedes": draft.get("supersedes"),
        "focus": draft["focus"],
        "flags": [_build_flag(flag) for flag in draft.get("flags", [])],
        "approval": None,
        "sessions": sessions,
    }
    errors = validate(doc, root, config)
    if errors:
        raise ValidationError(f"The built overlay is not valid ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    return doc


def _build_line(draft_line, unit, line_path, load_errors):
    mode = draft_line["load_mode"]
    line = {"exercise_id": draft_line["exercise_id"], "hevy_template_id": None, "load_mode": mode}
    for key, default in _LINE_DEFAULTS.items():
        line[key] = draft_line.get(key, default)
    override = draft_line.get("override")
    if override is not None:
        override = {
            "reason": override["reason"],
            "proposed_sets": [
                _build_set(s, mode, unit, f"{line_path}.override.proposed_sets[{i}]", load_errors)
                for i, s in enumerate(override["proposed_sets"])
            ],
        }
    line["override"] = override
    line["sets"] = [_build_set(s, mode, unit, f"{line_path}.sets[{i}]", load_errors)
                    for i, s in enumerate(draft_line["sets"])]
    return line


def _build_set(draft_set, mode, unit, path, load_errors):
    built = {"type": draft_set["type"]}
    for key in ("reps", "rep_range"):
        if draft_set.get(key) is not None:
            built[key] = draft_set[key]
    built["rpe"] = draft_set.get("rpe")
    value = draft_set.get("load")
    if value is None:
        built["load"] = None
    elif mode not in units.LOADED_MODES:
        load_errors.append(Error(f"{path}.load", f"load mode {mode} carries no load; leave load null"))
        built["load"] = None
    else:
        try:
            built["load"] = units.make_load(value, mode, unit)
        except ValueError as exc:
            load_errors.append(Error(f"{path}.load", str(exc)))
            built["load"] = None
    for key in ("duration_seconds", "distance_meters"):
        if draft_set.get(key) is not None:
            built[key] = draft_set[key]
    if draft_set.get("rep_out"):
        built["rep_out"] = True
    return built


def _build_flag(flag):
    return {
        "code": flag["code"], "severity": flag["severity"], "session_id": flag.get("session_id"),
        "exercise_id": flag.get("exercise_id"), "message": flag["message"],
        "resolved": flag.get("resolved", False), "resolution": flag.get("resolution"),
    }


def _free_id(root, base):
    candidate, n = base, 1
    while path_for(root, candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _program_locations(root):
    """Session id -> location from data/program.json; empty when there is no program."""
    path = Path(root) / paths.PROGRAM
    if not path.is_file():
        return {}
    program = read_json(path)
    sessions = program.get("sessions") if isinstance(program, dict) else None
    if not isinstance(sessions, builtins.list):
        raise ValidationError(f"{path} has no sessions list")
    return {s["id"]: s.get("location") for s in sessions if isinstance(s, dict) and "id" in s}
