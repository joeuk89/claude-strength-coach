"""Activity-source lines: building, hashing, validating, reading and appending (contract C7, C29, C30)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from coach import jsonio
from coach.errors import ValidationError
from coach.validate import Error, validate

VERSION = 1
SCHEMAS = {"activity": "activity_record", "wellness": "wellness_record", "planned": "planned_record"}
VOID_SCHEMA = "activity_void"
KINDS = ("run", "ride", "swim", "row", "walk", "hike", "conditioning", "sport", "mobility", "other")
BOOKKEEPING = ("schema_version", "op", "recorded_at", "content_hash")
_NOT_HASHED = ("op", "recorded_at", "content_hash")


def utc_text(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_local(text, zone):
    """An aware datetime from ISO 8601 text; text with no offset is local time in `zone` (None: system local)."""
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError(f"expected an ISO 8601 timestamp, found {text!r}") from None
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone) if zone else value.astimezone()
    return value


def offset_text(offset):
    minutes = int(offset.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    return f"{sign}{hours:02d}:{rest:02d}"


def parse_offset(text):
    sign = -1 if text[0] == "-" else 1
    hours, minutes = text[1:].split(":")
    return timedelta(minutes=sign * (int(hours) * 60 + int(minutes)))


def local_date(start, utc_offset, zone):
    """The calendar date of an aware `start`: by its offset text when known, else in `zone` (None: system local)."""
    if utc_offset is not None:
        return (start.astimezone(timezone.utc) + parse_offset(utc_offset)).date()
    return start.astimezone(zone).date()


def content_hash(record):
    return jsonio.canonical_hash({key: value for key, value in record.items() if key not in _NOT_HASHED})


def upsert_line(record, recorded_at):
    """The full C30 line for a normalised record: version, op, recorded_at and content_hash added."""
    body = {key: value for key, value in record.items() if key not in BOOKKEEPING}
    line = {"schema_version": VERSION, "op": "upsert", "id": body.pop("id"), "source": body.pop("source"),
            "recorded_at": recorded_at, **body}
    line["content_hash"] = content_hash(line)
    return line


def void_line(record_id, source, reason, by, recorded_at):
    return {"schema_version": VERSION, "op": "void", "id": record_id, "source": source,
            "recorded_at": recorded_at, "reason": reason, "by": by}


def strip(line):
    """A record without its bookkeeping fields, as readers see it."""
    return {key: value for key, value in line.items() if key not in BOOKKEEPING}


def line_errors(line, kind):
    """Every problem with one parsed line of the `kind` file, as validate.Error values."""
    if not isinstance(line, dict):
        return [Error("$", "expected an object")]
    version = line.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        if version > VERSION:
            return [Error("$.schema_version", f"version {version} is newer than this coach reads ({VERSION}); "
                                              "run /framework-sync")]
        if version < VERSION:
            return [Error("$.schema_version", f"version {version} is older than the current {VERSION}; "
                                              "run python3 -m coach migrate run")]
    schema = VOID_SCHEMA if line.get("op") == "void" else SCHEMAS[kind]
    errors = validate(line, jsonio.load_schema(schema))
    if errors:
        return errors
    if line["id"].split(":", 1)[0] != line["source"]:
        errors.append(Error("$.id", f"must start with its source, \"{line['source']}:\""))
    if line["op"] == "void":
        return errors
    if kind == "wellness" and line["span"]["end"] < line["span"]["start"]:
        errors.append(Error("$.span.end", "is before span.start"))
    if kind == "activity" and line.get("end") is not None and line["end"] < line["start"]:
        errors.append(Error("$.end", "is before start"))
    return errors


def read_lines(path, kind, label):
    """Every line of a JSONL file in order, validated; ValidationError names the file, line and JSONPath."""
    path = Path(path)
    if not path.is_file():
        return []
    lines, details = [], []
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not text.strip():
            continue
        try:
            line = json.loads(text)
        except json.JSONDecodeError as exc:
            details.append({"path": f"{label}:{number}", "message": f"{label} line {number}: not valid JSON ({exc.msg})"})
            continue
        errors = line_errors(line, kind)
        for error in errors:
            details.append({"path": f"{label}:{number} {error.path}",
                            "message": f"{label} line {number}: {error.path}: {error.message}"})
        if not errors:
            lines.append(line)
    if details:
        raise ValidationError(f"{details[0]['message']}" + (f" (and {len(details) - 1} more problem(s))"
                                                             if len(details) > 1 else ""), details=details)
    return lines


def append_lines(path, lines):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.is_file() and path.stat().st_size:
        with open(path, "rb") as handle:
            handle.seek(-1, 2)
            if handle.read(1) != b"\n":
                prefix = "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(prefix + "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines))
