"""Niggles: aches worth watching, the movements they affect and the load limits they set (contract C26, C27).

`data/niggles.json` replaces the profile's niggle log. Rows are never
deleted, because a recurrence is the signal. While a row's status is one
of its `constrain_while` statuses, or always for a `chronic` row, its
constraints apply to every program line whose exercise it names or whose
movement pattern it covers. Nothing here diagnoses: escalation only
recommends a qualified professional.
"""

import re
from pathlib import Path

from coach import dates, flags, jsonio, paths, units
from coach.activity import records
from coach.errors import ValidationError
from coach.library import PATTERNS, Library
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "niggles"
STATUSES = ("aggravated", "watching", "easing", "resolved", "chronic")
DEFAULT_CONSTRAIN_WHILE = ("aggravated", "watching")
CONSTRAINT_KINDS = ("rpe_cap", "no_added_load", "load_cap")
ESCALATE_AFTER = 3
_STILL_THERE = ("aggravated", "watching")
_BETTER_THAN_AGGRAVATED = ("watching", "easing", "resolved")
_ID = re.compile(r"^n-(\d+)$")
ADVICE = ("recommend the athlete has it assessed by a qualified professional (a doctor or physiotherapist), and "
          "program around it meanwhile")
IMPORT_NOTE = "imported from profile.md"
_SECTION = re.compile(r"^##\s+injuries\s*/\s*limitations\s*$", re.IGNORECASE)
_LOG = re.compile(r"^###\s+niggle log\s*$", re.IGNORECASE)
_HEADING = re.compile(r"^(#{1,6})\s")
_BULLET = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_COLUMNS = ("area", "first noted", "last noted", "mentions", "status", "notes")
_EMPTY_CELLS = ("", "-", "—", "–", "n/a")


def path_for(root):
    return Path(root) / paths.NIGGLES


def exists(root):
    return path_for(root).is_file()


def empty():
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)), "niggles": []}


def load(root, library=None):
    """The niggles document, checked against the library; an empty one when the file does not exist yet."""
    if not exists(root):
        return empty()
    doc = jsonio.read_doc(path_for(root), SCHEMA)
    errors = problems(doc, library or Library.load(root))
    if errors:
        raise ValidationError(f"{paths.NIGGLES} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def _constraint_problems(constraint, path):
    kind, value = constraint["kind"], constraint["value"]
    if kind == "no_added_load":
        return [] if value is None else [Error(f"{path}.value", "no_added_load takes no value (null)")]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return [Error(f"{path}.value", f"{kind} needs a number")]
    if kind == "rpe_cap" and not 1 <= value <= 10:
        return [Error(f"{path}.value", f"an RPE cap is 1 to 10, found {units.json_number(value)}")]
    return []


def problems(doc, library):
    """What the schema cannot say: ids, dates, patterns, exercise ids, activity kinds, constraint values, history."""
    errors, seen = [], set()
    known = set(library.ids())
    for index, row in enumerate(doc["niggles"]):
        path = f"$.niggles[{index}]"
        if row["id"] in seen:
            errors.append(Error(f"{path}.id", f"{row['id']} appears twice"))
        seen.add(row["id"])
        for key in ("first_noted", "last_noted"):
            try:
                dates.parse_date(row[key])
            except ValueError as exc:
                errors.append(Error(f"{path}.{key}", str(exc)))
        if row["last_noted"] < row["first_noted"]:
            errors.append(Error(f"{path}.last_noted", "last noted is before first noted"))
        applies = row["applies_to"]
        for number, pattern in enumerate(applies["patterns"]):
            if pattern not in PATTERNS:
                errors.append(Error(f"{path}.applies_to.patterns[{number}]",
                                    f"{pattern} is not a movement pattern; valid: {', '.join(PATTERNS)}"))
        for number, exercise_id in enumerate(applies["exercises"]):
            if exercise_id not in known:
                errors.append(Error(f"{path}.applies_to.exercises[{number}]",
                                    f"{exercise_id} is not in the exercise library"))
        for number, kind in enumerate(applies["activity_kinds"]):
            if kind not in records.KINDS:
                errors.append(Error(f"{path}.applies_to.activity_kinds[{number}]",
                                    f"{kind} is not an activity kind; valid: {', '.join(records.KINDS)}"))
        for number, constraint in enumerate(row["constraints"]):
            errors += _constraint_problems(constraint, f"{path}.constraints[{number}]")
        history = row["history"]
        for number in range(1, len(history)):
            if history[number]["date"] < history[number - 1]["date"]:
                errors.append(Error(f"{path}.history[{number}].date", "history is in date order"))
        if history[-1]["status"] != row["status"]:
            errors.append(Error(f"{path}.status", f"status {row['status']} does not match the newest history "
                                                  f"entry ({history[-1]['status']})"))
    return errors


def next_id(doc):
    numbers = [int(m.group(1)) for row in doc["niggles"] for m in [_ID.match(row["id"])] if m]
    return f"n-{max(numbers, default=0) + 1:04d}"


def save(root, doc, dry_run, library=None):
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA)) + problems(doc, library or Library.load(root))
    if errors:
        raise ValidationError(f"The niggles would not be valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(root), doc, dry_run)


def check_patterns(patterns):
    unknown = [p for p in patterns if p not in PATTERNS]
    if unknown:
        raise ValidationError(f"Not a movement pattern: {', '.join(unknown)}; valid: {', '.join(PATTERNS)}")
    return list(patterns)


def check_exercises(exercise_ids, library):
    unknown = [e for e in exercise_ids if library.get(e) is None]
    if unknown:
        raise ValidationError(f"Not in the exercise library: {', '.join(unknown)}; find ids with python3 -m coach "
                              "library search")
    return list(exercise_ids)


def check_activity_kinds(kinds):
    unknown = [k for k in kinds if k not in records.KINDS]
    if unknown:
        raise ValidationError(f"Not an activity kind: {', '.join(unknown)}; valid: {', '.join(records.KINDS)}")
    return list(kinds)


def check_statuses(statuses):
    unknown = [s for s in statuses if s not in STATUSES]
    if unknown:
        raise ValidationError(f"Not a niggle status: {', '.join(unknown)}; valid: {', '.join(STATUSES)}")
    return list(statuses)


def parse_constraint(text, reason):
    """A C26 constraint from KIND or KIND=VALUE ("rpe_cap=7", "no_added_load", "load_cap=20")."""
    kind, _, raw = text.partition("=")
    kind = kind.strip()
    if kind not in CONSTRAINT_KINDS:
        raise ValidationError(f"--constraint {text!r}: the kind is one of {', '.join(CONSTRAINT_KINDS)}")
    value = None
    if raw.strip():
        try:
            value = units.json_number(float(raw))
        except ValueError:
            raise ValidationError(f"--constraint {text!r}: {raw!r} is not a number") from None
    elif kind != "no_added_load":
        raise ValidationError(f"--constraint {text!r}: {kind} needs a value, e.g. {kind}=7")
    constraint = {"kind": kind, "value": value, "reason": reason}
    errors = _constraint_problems(constraint, "--constraint")
    if errors or (value is not None and value < 0):
        raise ValidationError(f"--constraint {text!r}: {errors[0].message if errors else 'the value is negative'}")
    return constraint


def _find(doc, niggle_id):
    row = next((r for r in doc["niggles"] if r["id"] == niggle_id), None)
    if row is None:
        raise ValidationError(f"No niggle {niggle_id} in {paths.NIGGLES}")
    return row


def _replace(doc, row):
    return dict(doc, niggles=[row if r["id"] == row["id"] else r for r in doc["niggles"]])


def _note(text):
    return text.strip() if text and text.strip() else None


def add(doc, area, on, status="watching", patterns=(), exercises=(), activity_kinds=(), constraints=(),
        constrain_while=DEFAULT_CONSTRAIN_WHILE, note=None, notes=None):
    """(doc with a new row, the row). The caller has checked patterns, exercise ids and kinds."""
    day = on.isoformat()
    row = {"id": next_id(doc), "area": area.strip(), "first_noted": day, "last_noted": day, "mentions": 1,
           "status": status, "notes": _note(notes),
           "applies_to": {"patterns": list(patterns), "exercises": list(exercises),
                          "activity_kinds": list(activity_kinds)},
           "constraints": list(constraints), "constrain_while": list(constrain_while),
           "history": [{"date": day, "status": status, "note": _note(note)}]}
    return dict(doc, niggles=doc["niggles"] + [row]), row


def update(doc, niggle_id, on, status=None, note=None, mention=False, **fields):
    """(doc, row) after a check-in report and any field changes.

    A status, a note or a mention adds a history entry dated `on`; a second
    report the same day replaces that day's entry, so history holds one
    entry per check-in. A mention counts once per day. `fields` replaces
    `area`, `notes`, `patterns`, `exercises`, `activity_kinds`,
    `constraints` or `constrain_while` when given (not None).
    """
    row = dict(_find(doc, niggle_id))
    day = on.isoformat()
    applies = dict(row["applies_to"])
    for key in ("patterns", "exercises", "activity_kinds"):
        if fields.get(key) is not None:
            applies[key] = list(fields[key])
    row["applies_to"] = applies
    for key in ("constraints", "constrain_while"):
        if fields.get(key) is not None:
            row[key] = list(fields[key])
    if fields.get("area") is not None:
        row["area"] = fields["area"].strip()
    if fields.get("notes") is not None:
        row["notes"] = _note(fields["notes"])
    if status is not None or note is not None or mention:
        if day < row["history"][-1]["date"]:
            raise ValidationError(f"Niggle {niggle_id} has a history entry after {day}")
        if mention and row["last_noted"] != day:
            row["mentions"] += 1
        if mention:
            row["last_noted"] = max(row["last_noted"], day)
        row["status"] = status or row["status"]
        history = list(row["history"])
        entry = {"date": day, "status": row["status"], "note": _note(note)}
        if history[-1]["date"] == day:
            entry["note"] = entry["note"] or history[-1]["note"]
            history[-1] = entry
        else:
            history.append(entry)
        row["history"] = history
    return _replace(doc, row), row


def resolve(doc, niggle_id, on, note=None):
    return update(doc, niggle_id, on, status="resolved", note=note)


def status_on(row, on_date):
    """The row's status on a date: its newest history entry on or before it, or None before it was noted."""
    day = on_date.isoformat() if hasattr(on_date, "isoformat") else on_date
    found = [entry for entry in row["history"] if entry["date"] <= day]
    return found[-1]["status"] if found else None


def constraints_active(row, on_date):
    """True when the row's constraints are in force on the date: always while chronic, else per constrain_while."""
    status = status_on(row, on_date)
    return status == "chronic" or (status is not None and status in row["constrain_while"])


def matches(row, entry):
    """True when the row applies to a library entry: by exercise id, or by its movement pattern."""
    applies = row["applies_to"]
    return entry.get("id") in applies["exercises"] or entry.get("pattern") in applies["patterns"]


def active_constraints(doc, entry, on_date):
    """The niggle constraints in force for one library entry on a date, each {kind, value, reason, source}."""
    return [dict(constraint, source=row["id"]) for row in doc["niggles"]
            if row["constraints"] and constraints_active(row, on_date) and matches(row, entry)
            for constraint in row["constraints"]]


def escalation(row):
    """Why the row needs a qualified professional, or None. A chronic row never escalates."""
    if row["status"] == "chronic":
        return None
    statuses = [entry["status"] for entry in row["history"]]
    if len(statuses) >= ESCALATE_AFTER and all(s in _STILL_THERE for s in statuses[-ESCALATE_AFTER:]):
        return "reported three check-ins running"
    if len(statuses) >= 2 and statuses[-1] == "aggravated" and statuses[-2] in _BETTER_THAN_AGGRAVATED:
        return f"worse: {statuses[-2]} to aggravated"
    return None


def escalate_message(row, reason):
    return f"Niggle {row['id']} ({row['area']}): {reason}. {ADVICE[0].upper()}{ADVICE[1:]}."


def escalate_flags(doc):
    """One week-level `niggle_escalate` flag per row that needs a qualified professional (C20)."""
    return [flags.make("niggle_escalate", message=escalate_message(row, reason))
            for row in doc["niggles"] for reason in [escalation(row)] if reason]


def week_flags(root):
    return escalate_flags(load(root)) if exists(root) else []


def is_open(row):
    return row["status"] != "resolved"


def _section(text):
    """(lines outside the niggle log, the niggle log's table lines) of the Injuries / limitations section."""
    lines, table, inside, in_log = [], [], False, False
    for raw in text.splitlines():
        line = raw.strip()
        heading = _HEADING.match(line)
        if _SECTION.match(line):
            inside, in_log = True, False
            continue
        if not inside:
            continue
        if heading and len(heading.group(1)) <= 2:
            break
        if _LOG.match(line):
            in_log = True
            continue
        if heading:
            in_log = False
            continue
        if in_log:
            if line.startswith("|"):
                table.append(line)
        elif line and not line.startswith("|"):
            lines.append(_BULLET.sub("", line))
    return lines, table


def _cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_rows(table):
    """[{column: cell}] from the niggle log's table lines, header first."""
    if not table:
        return []
    header = [cell.lower() for cell in _cells(table[0])]
    missing = [c for c in _COLUMNS if c not in header]
    if missing:
        raise ValidationError(f"The niggle log table in {paths.PROFILE} has no {', '.join(missing)} column; it needs "
                              f"{' · '.join(c.capitalize() for c in _COLUMNS)}")
    found = []
    for line in table[1:]:
        cells = _cells(line)
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        found.append(dict(zip(header, cells + [""] * (len(header) - len(cells)))))
    return found


def _imported(cells, number, errors):
    area = cells["area"]
    where = f"niggle log row {number} ({area or 'no area'})"
    if not area:
        errors.append({"path": where, "message": "the Area cell is empty"})
    parsed = {}
    for column in ("first noted", "last noted"):
        try:
            parsed[column] = dates.parse_date(cells[column]).isoformat()
        except ValueError:
            errors.append({"path": where,
                           "message": f"{column.capitalize()} {cells[column]!r} is not a YYYY-MM-DD date"})
    try:
        mentions = int(cells["mentions"])
        if mentions < 1:
            raise ValueError
    except ValueError:
        errors.append({"path": where, "message": f"Mentions {cells['mentions']!r} is not a whole number of 1 or more"})
        mentions = None
    status = cells["status"].lower()
    if status not in STATUSES:
        errors.append({"path": where, "message": f"Status {cells['status']!r} is not one of {', '.join(STATUSES)}"})
    if len(parsed) < 2 or mentions is None or status not in STATUSES or not area:
        return None
    notes = None if cells["notes"].lower() in _EMPTY_CELLS else cells["notes"]
    return {"area": area, "first_noted": parsed["first noted"], "last_noted": parsed["last noted"],
            "mentions": mentions, "status": status, "notes": notes,
            "history": [{"date": parsed["last noted"], "status": status, "note": IMPORT_NOTE}]}


def import_profile(doc, text, today, chronic=()):
    """(doc with the imported rows, rows, numbered section lines) from profile.md's text.

    Each niggle log row becomes a row with no constraints. Each section line
    whose number is in `chronic` becomes a `chronic` row with nothing in
    `applies_to`, for the coach to fill; the other lines are not imported.
    """
    if doc["niggles"]:
        raise ValidationError(f"{paths.NIGGLES} already holds {len(doc['niggles'])} niggle(s); the profile import "
                              "runs once. Add more with python3 -m coach niggles add")
    lines, table = _section(text)
    numbered = [{"index": number, "text": line} for number, line in enumerate(lines, 1)]
    bad = [index for index in chronic if not 1 <= index <= len(lines)]
    if bad:
        raise ValidationError(f"--chronic {', '.join(map(str, bad))}: the Injuries / limitations section has "
                              f"{len(lines)} line(s), numbered 1 to {len(lines)}")
    errors, found = [], []
    for number, cells in enumerate(_table_rows(table), 1):
        row = _imported(cells, number, errors)
        if row is not None:
            found.append(row)
    if errors:
        raise ValidationError(f"{len(errors)} problem(s) in the niggle log table of {paths.PROFILE}", details=errors)
    day = today.isoformat()
    for index in sorted(set(chronic)):
        found.append({"area": lines[index - 1], "first_noted": day, "last_noted": day, "mentions": 1,
                      "status": "chronic", "notes": None,
                      "history": [{"date": day, "status": "chronic", "note": f"{IMPORT_NOTE} Injuries / limitations"}]})
    rows = []
    for row in found:
        row = dict({"id": next_id(doc)}, **row, applies_to={"patterns": [], "exercises": [], "activity_kinds": []},
                   constraints=[], constrain_while=list(DEFAULT_CONSTRAIN_WHILE))
        row = {key: row[key] for key in ("id", "area", "first_noted", "last_noted", "mentions", "status", "notes",
                                         "applies_to", "constraints", "constrain_while", "history")}
        doc = dict(doc, niggles=doc["niggles"] + [row])
        rows.append(row)
    return doc, rows, numbered
