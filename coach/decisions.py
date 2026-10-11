"""Recorded coaching decisions: overrides, adherence triggers, light weeks (contract C25).

`data/decisions.json` is append-only: a decision is closed by withdrawing it
or expires when its `until` passes, and is never deleted. Expiry is worked
out when the file is read, so the stored `status` stays as written.
"""

import re
from datetime import timedelta
from pathlib import Path

from coach import dates, jsonio, paths
from coach.errors import ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "decisions"
KINDS = ("override", "adherence_trigger", "light_week")
STANDING_DEFAULT_DAYS = 28
STANDING_MAX_DAYS = 56
_ID = re.compile(r"^d-(\d+)$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DETAILS = {
    "adherence_trigger": {
        "type": "object", "required": ["rule", "adherence_pct", "weeks"], "additionalProperties": False,
        "properties": {
            "rule": {"enum": ["restructure", "add_session"]},
            "adherence_pct": {"type": "number", "minimum": 0, "maximum": 100},
            "weeks": {"type": "array", "items": {"type": "string", "pattern": _DATE.pattern}},
        },
    },
    "light_week": {
        "type": "object", "required": ["type", "week", "reason", "triggers", "hard_weeks"],
        "additionalProperties": False,
        "properties": {
            "type": {"enum": ["deload", "light", "return"]},
            "week": {"type": "string", "pattern": _DATE.pattern},
            "reason": {"type": "string", "pattern": "\\S"},
            "triggers": {"type": "array", "items": {"type": "string", "pattern": "\\S"}},
            "hard_weeks": {"type": "integer", "minimum": 0},
        },
    },
}


def path_for(root):
    return Path(root) / paths.DECISIONS


def empty():
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)), "decisions": []}


def load(root):
    """The decisions document, checked; an empty one when the file does not exist yet."""
    path = path_for(root)
    if not path.is_file():
        return empty()
    doc = jsonio.read_doc(path, SCHEMA)
    errors = problems(doc)
    if errors:
        raise ValidationError(f"{paths.DECISIONS} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def problems(doc):
    """What the schema cannot say: unique ids, scope and sets per kind, details per kind, dates."""
    errors = []
    seen = set()
    for index, decision in enumerate(doc["decisions"]):
        path = f"$.decisions[{index}]"
        if decision["id"] in seen:
            errors.append(Error(f"{path}.id", f"{decision['id']} appears twice"))
        seen.add(decision["id"])
        kind = decision["kind"]
        if kind == "override":
            if set(decision["scope"]) != {"session_id", "exercise_id"}:
                errors.append(Error(f"{path}.scope", "an override's scope names session_id and exercise_id"))
            if decision["details"] is not None:
                errors.append(Error(f"{path}.details", "an override has no details"))
            if decision["standing"] and decision["until"] is None:
                errors.append(Error(f"{path}.until", "a standing override needs an until date"))
        else:
            if decision["scope"]:
                errors.append(Error(f"{path}.scope", f"a {kind} decision is program-wide; its scope is {{}}"))
            for key in ("proposed_sets", "chosen_sets"):
                if decision[key] is not None:
                    errors.append(Error(f"{path}.{key}", f"only an override carries {key}"))
            if decision["details"] is None:
                errors.append(Error(f"{path}.details", f"a {kind} decision needs details"))
            else:
                errors += [Error(f"{path}.details{e.path[1:]}", e.message)
                           for e in validate_schema(decision["details"], _DETAILS[kind])]
        for key in ("until", "revisit_on"):
            if decision[key] is not None:
                try:
                    dates.parse_date(decision[key])
                except ValueError as exc:
                    errors.append(Error(f"{path}.{key}", str(exc)))
        if decision["status"] == "withdrawn" and decision["closed_at"] is None:
            errors.append(Error(f"{path}.closed_at", "a withdrawn decision records when it was closed"))
    return errors


def effective_status(decision, today):
    """`active`, `expired` (its until date has passed) or `withdrawn`."""
    if decision["status"] != "active":
        return decision["status"]
    if decision["until"] is not None and decision["until"] < today.isoformat():
        return "expired"
    return "active"


def with_status(doc, today):
    return [dict(d, effective_status=effective_status(d, today)) for d in doc["decisions"]]


def next_id(doc):
    numbers = [int(m.group(1)) for d in doc["decisions"] for m in [_ID.match(d["id"])] if m]
    return f"d-{max(numbers, default=0) + 1:04d}"


def standing_until(made_on, until=None):
    """The end date of a standing override: four weeks after it was made by default, eight at most."""
    latest = made_on + timedelta(days=STANDING_MAX_DAYS)
    if until is None:
        return made_on + timedelta(days=STANDING_DEFAULT_DAYS)
    if until > latest:
        raise ValidationError(f"A standing override lasts at most {STANDING_MAX_DAYS // 7} weeks: until {until} is "
                              f"after {latest}; renew it later with another propose override --standing")
    if until <= made_on:
        raise ValidationError(f"until {until} must be after the day the override is made ({made_on})")
    return until


def override(made_at, overlay_id, session_id, exercise_id, reason, proposed_sets, chosen_sets, standing, until):
    """A new override decision (no id yet)."""
    return {
        "id": None, "kind": "override", "made_at": made_at, "overlay_id": overlay_id,
        "scope": {"session_id": session_id, "exercise_id": exercise_id}, "outcome": "adopted", "reason": reason,
        "standing": standing, "until": until, "revisit_on": None, "proposed_sets": proposed_sets,
        "chosen_sets": chosen_sets, "details": None, "status": "active", "closed_at": None, "closed_reason": None,
    }


def append(root, doc, decision, dry_run):
    """`doc` with `decision` added under the next free id, written unless dry_run; returns (doc, decision)."""
    decision = dict(decision, id=next_id(doc))
    updated = dict(doc, decisions=doc["decisions"] + [decision])
    errors = validate_schema(updated, jsonio.load_schema(SCHEMA)) + problems(updated)
    if errors:
        raise ValidationError(f"The decision is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(root), updated, dry_run)
    return updated, decision


def withdraw(root, decision_id, reason, closed_at, dry_run):
    doc = load(root)
    found = next((d for d in doc["decisions"] if d["id"] == decision_id), None)
    if found is None:
        raise ValidationError(f"No decision {decision_id} in {paths.DECISIONS}")
    if found["status"] == "withdrawn":
        raise ValidationError(f"Decision {decision_id} was already withdrawn on {found['closed_at']}")
    closed = dict(found, status="withdrawn", closed_at=closed_at, closed_reason=reason)
    updated = dict(doc, decisions=[closed if d["id"] == decision_id else d for d in doc["decisions"]])
    jsonio.write_doc(path_for(root), updated, dry_run)
    return closed


def last_override(doc, session_id, exercise_id, today):
    """The newest active override decision for a slot, or None (C25)."""
    found = [d for d in doc["decisions"] if d["kind"] == "override"
             and d["scope"] == {"session_id": session_id, "exercise_id": exercise_id}
             and effective_status(d, today) == "active"]
    return max(found, key=lambda d: (d["made_at"], d["id"])) if found else None
