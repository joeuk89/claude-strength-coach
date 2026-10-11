"""Follow-ups: questions to come back to, each with a review date and an event log (contract C27).

`data/followups.json` keeps every item, open or closed. A deep check-in
must give each item open before its date a disposition dated that day
(resolved, dropped with a reason, or kept or deferred to a new review
date); `render_deep` refuses until it has.
"""

import re
from pathlib import Path

from coach import dates, flags, jsonio, paths
from coach.errors import ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "followups"
STATUSES = ("open", "resolved", "dropped")
CLOSING = {"resolved": "resolved", "dropped": "dropped"}
_ID = re.compile(r"^f-(\d+)$")


def path_for(root):
    return Path(root) / paths.FOLLOWUPS


def empty():
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)), "items": []}


def exists(root):
    return path_for(root).is_file()


def load(root):
    """The follow-ups document, checked; an empty one when the file does not exist yet."""
    if not exists(root):
        return empty()
    doc = jsonio.read_doc(path_for(root), SCHEMA)
    errors = problems(doc)
    if errors:
        raise ValidationError(f"{paths.FOLLOWUPS} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def problems(doc):
    """What the schema cannot say: unique ids, event order, a reason on each drop, status matching the events."""
    errors, seen = [], set()
    for index, item in enumerate(doc["items"]):
        path = f"$.items[{index}]"
        if item["id"] in seen:
            errors.append(Error(f"{path}.id", f"{item['id']} appears twice"))
        seen.add(item["id"])
        for key in ("raised", "review_at"):
            try:
                dates.parse_date(item[key])
            except ValueError as exc:
                errors.append(Error(f"{path}.{key}", str(exc)))
        if item["review_at"] < item["raised"]:
            errors.append(Error(f"{path}.review_at", f"review date {item['review_at']} is before the raised date "
                                                     f"{item['raised']}"))
        events = item["events"]
        if events[0]["action"] != "raised":
            errors.append(Error(f"{path}.events[0].action", "the first event is raised"))
        for number, event in enumerate(events):
            where = f"{path}.events[{number}]"
            if number and event["date"] < events[number - 1]["date"]:
                errors.append(Error(f"{where}.date", "events are in date order"))
            if number and event["action"] == "raised":
                errors.append(Error(f"{where}.action", "only the first event is raised"))
            if event["action"] == "dropped" and event["note"] is None:
                errors.append(Error(f"{where}.note", "a dropped follow-up records the reason it was dropped"))
        last = events[-1]["action"]
        if CLOSING.get(last, "open") != item["status"]:
            errors.append(Error(f"{path}.status", f"status {item['status']} does not match the last event ({last})"))
        if any(e["action"] in CLOSING for e in events[:-1]):
            errors.append(Error(f"{path}.events", "a closed follow-up takes no further events"))
    return errors


def next_id(doc):
    numbers = [int(m.group(1)) for item in doc["items"] for m in [_ID.match(item["id"])] if m]
    return f"f-{max(numbers, default=0) + 1:04d}"


def save(root, doc, dry_run):
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA)) + problems(doc)
    if errors:
        raise ValidationError(f"The follow-ups would not be valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(root), doc, dry_run)


def _text(value, what):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{what} must not be empty")
    return value.strip()


def add(doc, text, review_at, source, raised):
    """(doc with a new open item, the item). Dates are `date` objects."""
    if review_at < raised:
        raise ValidationError(f"The review date {review_at} is before the raised date {raised}")
    item = {"id": next_id(doc), "raised": raised.isoformat(), "source": _text(source, "--source"),
            "text": _text(text, "--text"), "review_at": review_at.isoformat(), "status": "open",
            "events": [{"date": raised.isoformat(), "action": "raised", "note": None}]}
    return dict(doc, items=doc["items"] + [item]), item


def _find_open(doc, item_id):
    item = next((i for i in doc["items"] if i["id"] == item_id), None)
    if item is None:
        raise ValidationError(f"No follow-up {item_id} in {paths.FOLLOWUPS}")
    if item["status"] != "open":
        raise ValidationError(f"Follow-up {item_id} is already {item['status']} "
                              f"({item['events'][-1]['date']}); closed items stay closed")
    return item


def _with_event(doc, item_id, on, action, note, **changes):
    item = _find_open(doc, item_id)
    if on.isoformat() < item["raised"]:
        raise ValidationError(f"Follow-up {item_id} was raised on {item['raised']}, after {on}")
    event = {"date": on.isoformat(), "action": action, "note": note.strip() if note and note.strip() else None}
    updated = dict(item, events=item["events"] + [event], **changes)
    return dict(doc, items=[updated if i["id"] == item_id else i for i in doc["items"]]), updated


def resolve(doc, item_id, on, note=None):
    return _with_event(doc, item_id, on, "resolved", note, status="resolved")


def drop(doc, item_id, on, reason):
    return _with_event(doc, item_id, on, "dropped", _text(reason, "--reason"), status="dropped")


def defer(doc, item_id, on, to, note=None, kept=False):
    """Keep an item open with a new review date: `kept` after a review, `deferred` otherwise."""
    if to <= on:
        raise ValidationError(f"The new review date {to} must be after {on}")
    return _with_event(doc, item_id, on, "kept" if kept else "deferred", note, review_at=to.isoformat())


def is_due(item, today):
    return item["status"] == "open" and item["review_at"] <= today.isoformat()


def due(doc, today):
    """Open items whose review date is today or past."""
    return [item for item in doc["items"] if is_due(item, today)]


def due_flags(root, today):
    """One week-level `followup_due` flag per due item (C20, C24)."""
    if not exists(root):
        return []
    return [flags.make("followup_due", message=f"Follow-up {item['id']} was due for review on {item['review_at']}: "
                                              f"{item['text']}")
            for item in due(load(root), today)]


def _disposition(item, day):
    """The item's event dated `day` that settles it (the last one that day), or None."""
    found = [e for e in item["events"] if e["date"] == day and e["action"] != "raised"]
    return found[-1] if found else None


def undisposed(doc, day):
    """Items open before `day` with no event dated `day`: the deep check-in has not dealt with them."""
    on = day.isoformat()
    return [item for item in doc["items"]
            if item["raised"] < on and item["status"] == "open" and _disposition(item, on) is None]


def deep_items(doc, day):
    """(item, disposition, note) for each item the deep record lists: everything settled on the day or raised on it."""
    on = day.isoformat()
    found = []
    for item in doc["items"]:
        event = _disposition(item, on)
        if event is not None:
            found.append((item, event["action"], event["note"]))
        elif item["raised"] == on:
            found.append((item, "raised", None))
    return found


def _line(item, disposition, note):
    head = f"- **{item['id']}** {item['text'].rstrip('.')} (raised {item['raised']}, {item['source']})"
    if disposition == "resolved":
        tail = "resolved"
    elif disposition == "dropped":
        tail = "dropped"
    elif disposition in ("kept", "deferred"):
        tail = f"{disposition}, next review {item['review_at']}"
    else:
        tail = f"new, review {item['review_at']}"
    return f"{head}: {tail}" + (f" — {note}" if note else "")


def render_deep(doc, day):
    """The deep record's follow-up section. Raises ValidationError while an item lacks a disposition dated `day`."""
    missing = undisposed(doc, day)
    if missing:
        raise ValidationError(
            f"{len(missing)} open follow-up(s) need a disposition dated {day}: "
            f"{', '.join(i['id'] for i in missing)}; resolve, drop with a reason, or defer each to a new date",
            details=[{"path": i["id"], "message": f"{i['text']} (review {i['review_at']})"} for i in missing])
    lines = [f"**Follow-ups** (reviewed {day.isoformat()})", ""]
    lines += [_line(*row) for row in deep_items(doc, day)] or ["- none open"]
    return "\n".join(lines) + "\n"
