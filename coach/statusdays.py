"""Status days: days the athlete was ill, injured or travelling (contract C50).

`data/status-days.json` keeps every row. A wrong row is withdrawn, never
deleted, and ids are never reused. An `ill` row in the gap before a
session counts exactly like an `ill` miss annotation for the illness
return rule; travel only explains a gap. A row marked `no_training` is a
planned break the athlete agreed: the sessions on its days are not planned
work, so nothing asks to program, tag or count them.
"""

import re
from datetime import date
from pathlib import Path

from coach import dates, jsonio, paths
from coach.errors import ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "status_days"
KINDS = ("ill", "injured", "travel")
BREAK_KINDS = ("injured", "travel")
_ID = re.compile(r"^s-(\d+)$")
_OPEN_END = date.max


def path_for(root):
    return Path(root) / paths.STATUS_DAYS


def exists(root):
    return path_for(root).is_file()


def empty():
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)), "days": []}


def load(root):
    """The status-days document, checked; an empty one when the file does not exist yet."""
    if not exists(root):
        return empty()
    doc = jsonio.read_doc(path_for(root), SCHEMA)
    errors = problems(doc)
    if errors:
        raise ValidationError(f"{paths.STATUS_DAYS} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def save(root, doc, dry_run):
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA)) + problems(doc)
    if errors:
        raise ValidationError(f"The status days would not be valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(root), doc, dry_run)


def problems(doc):
    """What the schema cannot say: unique ids, real dates, start on or before end, one open-ended row per kind,
    and no planned break on an `ill` row."""
    errors, seen, open_kinds = [], set(), {}
    for index, row in enumerate(doc["days"]):
        path = f"$.days[{index}]"
        if row["no_training"] and row["kind"] not in BREAK_KINDS:
            errors.append(Error(f"{path}.no_training", f"{row['kind']} rows cannot be planned breaks"))
        if row["id"] in seen:
            errors.append(Error(f"{path}.id", f"{row['id']} appears twice"))
        seen.add(row["id"])
        try:
            start = dates.parse_date(row["span"]["start"])
            end = dates.parse_date(row["span"]["end"]) if row["span"]["end"] is not None else None
        except ValueError as exc:
            errors.append(Error(f"{path}.span", str(exc)))
            continue
        if end is not None and end < start:
            errors.append(Error(f"{path}.span.end", f"ends ({end}) before it starts ({start})"))
        if end is None and row["withdrawn"] is None:
            if row["kind"] in open_kinds:
                errors.append(Error(f"{path}.span.end", f"{open_kinds[row['kind']]} is already an open-ended "
                                                        f"{row['kind']} row; end it first"))
            open_kinds.setdefault(row["kind"], row["id"])
    return errors


def span_of(row):
    """The row's days as a Span; an ongoing row runs on indefinitely."""
    start = dates.parse_date(row["span"]["start"])
    end = dates.parse_date(row["span"]["end"]) if row["span"]["end"] is not None else _OPEN_END
    return dates.Span(start, end)


def is_live(row):
    return row["withdrawn"] is None


def overlapping(doc, span):
    return [row for row in doc["days"] if is_live(row) and span_of(row).overlaps(span)]


def active(root, span):
    """Rows not withdrawn whose days overlap the span, oldest first."""
    return overlapping(load(root), span)


def ill_in(root, span):
    """True when an `ill` row overlaps the span: the illness return rule reads it like an `ill` miss (C22)."""
    return any(row["kind"] == "ill" for row in active(root, span))


def ill_days(root, span):
    """{day: row id} for each day in the span an `ill` row covers: no session is planned on them (C22)."""
    found = {}
    for row in active(root, span):
        if row["kind"] == "ill":
            covered = span_of(row)
            for day in span.days():
                if covered.contains(day):
                    found.setdefault(day, row["id"])
    return found


def breaks(root, span):
    """Live `no_training` rows overlapping the span, oldest first: planned breaks the athlete agreed."""
    return [row for row in active(root, span) if row["no_training"]]


def break_days(root, span):
    """{day: row id} for each day in the span a planned break covers; the oldest covering row names it."""
    found = {}
    for row in breaks(root, span):
        covered = span_of(row)
        for day in span.days():
            if covered.contains(day):
                found.setdefault(day, row["id"])
    return found


def next_id(doc):
    numbers = [int(m.group(1)) for row in doc["days"] for m in [_ID.match(row["id"])] if m]
    return f"s-{max(numbers, default=0) + 1:04d}"


def _find(doc, row_id):
    row = next((r for r in doc["days"] if r["id"] == row_id), None)
    if row is None:
        raise ValidationError(f"no status day has the id {row_id!r}; see python3 -m coach status-days list")
    return row


def add(doc, kind, start, end, note, source, created_at, no_training=False):
    if kind not in KINDS:
        raise ValidationError(f"kind must be one of {', '.join(KINDS)}, found {kind!r}")
    if no_training and kind not in BREAK_KINDS:
        raise ValidationError(f"--no-training marks a planned break, so it goes on a {' or '.join(BREAK_KINDS)} "
                              f"row; illness keeps its own return rule")
    if end is not None and end < start:
        raise ValidationError(f"--to {end} is before --from {start}")
    if not note.strip():
        raise ValidationError("--note must not be empty")
    row = {"id": next_id(doc), "kind": kind,
           "span": {"start": start.isoformat(), "end": end.isoformat() if end else None},
           "note": note.strip(), "no_training": bool(no_training), "created_at": created_at,
           "source": source.strip() or "coach", "withdrawn": None}
    if end is None:
        ongoing = next((r for r in doc["days"] if is_live(r) and r["kind"] == kind and r["span"]["end"] is None), None)
        if ongoing is not None:
            raise ValidationError(f"{ongoing['id']} is already an ongoing {kind} row; end it with "
                                  f"python3 -m coach status-days end {ongoing['id']} --date D first")
    return dict(doc, days=doc["days"] + [row]), row


def end(doc, row_id, day):
    row = _find(doc, row_id)
    if not is_live(row):
        raise ValidationError(f"{row_id} is withdrawn")
    if row["span"]["end"] is not None:
        raise ValidationError(f"{row_id} already ends on {row['span']['end']}")
    if day < dates.parse_date(row["span"]["start"]):
        raise ValidationError(f"--date {day} is before {row_id} starts ({row['span']['start']})")
    changed = dict(row, span=dict(row["span"], end=day.isoformat()))
    return _replace(doc, changed), changed


def withdraw(doc, row_id, reason, at):
    row = _find(doc, row_id)
    if not is_live(row):
        raise ValidationError(f"{row_id} is already withdrawn ({row['withdrawn']['reason']})")
    if not reason.strip():
        raise ValidationError("--reason must not be empty")
    changed = dict(row, withdrawn={"at": at, "reason": reason.strip()})
    return _replace(doc, changed), changed


def _replace(doc, changed):
    return dict(doc, days=[changed if r["id"] == changed["id"] else r for r in doc["days"]])
