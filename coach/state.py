"""Program state: rotation, block counters, the active one-off span, scheme state, Hevy ids (contract C16)."""

import json
import re
from pathlib import Path

from coach import dates, jsonio, paths
from coach.errors import ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "state"
_SLOT_KEY = re.compile(r"^([a-z0-9-]+)/([a-z0-9_]+)$")
SESSION_SLOT = "_session"


def path_for(root):
    return Path(root) / paths.STATE


def exists(root):
    return path_for(root).is_file()


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"No state yet: {path} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def load(root):
    """The state, schema-checked. Raises ValidationError when absent or malformed."""
    path = path_for(root)
    if not path.is_file():
        raise ValidationError(f"No state yet: {paths.STATE} does not exist in {root}")
    return jsonio.read_doc(path, SCHEMA)


def problems(doc, program_doc=None):
    """Every problem with a state document; with `program_doc`, also ids that point at nothing in it."""
    if isinstance(doc, dict):
        version = doc.get("schema_version")
        current = jsonio.current_version(jsonio.load_schema(SCHEMA))
        if isinstance(version, int) and not isinstance(version, bool) and version != current:
            hint = "run /framework-sync" if version > current else "run python3 -m coach migrate run"
            return [Error("$.schema_version", f"schema_version {version} is not the current {current}; {hint}")]
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA))
    if errors:
        return errors
    errors += _dates(doc)
    if program_doc is not None:
        errors += _references(doc, program_doc)
    return errors


def _child(path, key):
    return f"{path}.{key}" if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) else f"{path}[{key!r}]"


def _date(value, path, errors):
    if value is None:
        return None
    try:
        return dates.parse_date(value)
    except ValueError as exc:
        errors.append(Error(path, str(exc)))
        return None


def _dates(doc):
    errors = []
    _date(doc["rotation"]["confirmed_at"], "$.rotation.confirmed_at", errors)
    block = doc["block"]
    for key in ("started", "last_closed_week", "last_deep_review"):
        _date(block[key], f"$.block.{key}", errors)
    light = block["light_week"]
    _date(light["week"], "$.block.light_week.week", errors)
    if light["status"] in ("proposed", "agreed", "declined") and light["type"] is None:
        errors.append(Error("$.block.light_week.type", f"a {light['status']} light week names its type"))
    if light["status"] in ("not_due", "watch", "skipped") and any(light[k] for k in ("type", "reason", "week")):
        errors.append(Error("$.block.light_week", f"a light week that is {light['status']} has no type, reason or week"))
    if doc["one_off"] is not None:
        start = _date(doc["one_off"]["span"]["start"], "$.one_off.span.start", errors)
        end = _date(doc["one_off"]["span"]["end"], "$.one_off.span.end", errors)
        if start and end and end < start:
            errors.append(Error("$.one_off.span", f"span ends ({end}) before it starts ({start})"))
    return errors


def _references(doc, program_doc):
    errors = []
    sessions = {s["id"]: {e["exercise_id"] for e in s["exercises"]} for s in program_doc["sessions"]}
    kinds = {s["id"]: s["kind"] for s in program_doc["sessions"]}
    for key in doc["scheme_state"]:
        path = _child("$.scheme_state", key)
        match = _SLOT_KEY.fullmatch(key)
        if not match:
            errors.append(Error(path, "a scheme_state key is <session id>/<exercise id> or "
                                      f"<session id>/{SESSION_SLOT}, found {key!r}"))
        elif match.group(2) == SESSION_SLOT:
            if kinds.get(match.group(1)) != "conditioning":
                errors.append(Error(path, f"the program has no conditioning session {match.group(1)}"))
        elif match.group(2) not in sessions.get(match.group(1), ()):
            errors.append(Error(path, f"the program has no exercise {match.group(2)} in session {match.group(1)}"))
    for routine_id, entry in doc["hevy"]["routines"].items():
        if entry["session_id"] not in sessions:
            errors.append(Error(f"{_child('$.hevy.routines', routine_id)}.session_id",
                                f"no program session {entry['session_id']}"))
    return errors
