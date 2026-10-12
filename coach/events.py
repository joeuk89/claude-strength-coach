"""Goal events: dated races and other goal events, and the window agreed before each (contract C55).

`data/events.json` keeps every event: a cancelled or completed one stays as
history. No window is ever assumed: an event without an agreed window is a
pending decision, and an agreed window only flags heavy lower-body work
for review. Nothing here changes a prescription, a session or the block
count.
"""

import re
from pathlib import Path

from coach import cardio, dates, flags, interference, jsonio, paths, units
from coach import config as config_module
from coach import overlay as overlay_module
from coach.errors import ValidationError
from coach.library import Library
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "events"
PRIORITIES = ("A", "B", "C")
ACTIVE = "active"
ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PENDING_WINDOW, PENDING_RESULT = "window", "result"


def path_for(root):
    return Path(root) / paths.EVENTS


def exists(root):
    return path_for(root).is_file()


def empty():
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)), "events": []}


def load(root):
    """The events document, checked; an empty one when the file does not exist yet."""
    if not exists(root):
        return empty()
    doc = jsonio.read_doc(path_for(root), SCHEMA)
    errors = problems(doc)
    if errors:
        raise ValidationError(f"{paths.EVENTS} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def save(root, doc, dry_run):
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA)) + problems(doc)
    if errors:
        raise ValidationError(f"The events would not be valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(root), doc, dry_run)


def problems(doc):
    """What the schema cannot say: unique ids, real dates, the window inside the event, status and result agree."""
    errors, seen, links = [], set(), {}
    for index, row in enumerate(doc["events"]):
        path = f"$.events[{index}]"
        if row["id"] in seen:
            errors.append(Error(f"{path}.id", f"{row['id']} appears twice; event ids are never reused"))
        seen.add(row["id"])
        try:
            day = dates.parse_date(row["date"])
        except ValueError as exc:
            errors.append(Error(f"{path}.date", str(exc)))
            continue
        errors += _window_problems(row.get("window"), day, f"{path}.window")
        if (row["status"] == "completed") != (row["result"] is not None):
            errors.append(Error(f"{path}.result", "a completed event has a result, and only a completed one"))
        if row["status"] == ACTIVE and row["planned_id"]:
            if row["planned_id"] in links:
                errors.append(Error(f"{path}.planned_id", f"{links[row['planned_id']]} already links "
                                                          f"{row['planned_id']}; one planned activity, one event"))
            links.setdefault(row["planned_id"], row["id"])
    return errors


def _window_problems(window, day, path):
    if window is None:
        return []
    if (window["start"] is None) != (window["end"] is None):
        return [Error(path, "give both start and end, or neither for an agreed decision to keep no window")]
    if window["start"] is None:
        return []
    try:
        start, end = dates.parse_date(window["start"]), dates.parse_date(window["end"])
    except ValueError as exc:
        return [Error(path, str(exc))]
    if end < start:
        return [Error(f"{path}.end", f"ends ({end}) before it starts ({start})")]
    if end > day:
        return [Error(f"{path}.end", f"ends ({end}) after the event ({day})")]
    return []


def ordered(rows):
    """Events by date, then priority, then id: every view presents them in this order."""
    return sorted(rows, key=lambda row: (row["date"], row["priority"], row["id"]))


def active(doc):
    return ordered([row for row in doc["events"] if row["status"] == ACTIVE])


def find(doc, event_id):
    row = next((r for r in doc["events"] if r["id"] == event_id), None)
    if row is None:
        raise ValidationError(f"no event has the id {event_id!r}; see python3 -m coach events list --all")
    return row


def _active_row(doc, event_id):
    row = find(doc, event_id)
    if row["status"] != ACTIVE:
        raise ValidationError(f"{event_id} is {row['status']}: it stays as history and is not changed")
    return row


def _replace(doc, changed):
    return dict(doc, events=[changed if r["id"] == changed["id"] else r for r in doc["events"]])


def _change(row, at, text, reason=None):
    return row["changes"] + [{"at": at, "change": text, "reason": reason}]


def _text(value, flag):
    if value is None or not value.strip():
        raise ValidationError(f"{flag} must not be empty")
    return value.strip()


def add(doc, *, event_id, title, day, priority, activity, distance_meters, planned_id, note, created_at):
    if not ID_PATTERN.fullmatch(event_id or ""):
        raise ValidationError(f"--id {event_id!r} must be lowercase letters, digits and single hyphens, "
                              "such as autumn-10k")
    if any(r["id"] == event_id for r in doc["events"]):
        raise ValidationError(f"an event already has the id {event_id}; event ids are never reused, so choose "
                              "another (python3 -m coach events list --all shows them)")
    if priority not in PRIORITIES:
        raise ValidationError(f"--priority must be one of {', '.join(PRIORITIES)}, found {priority!r}")
    row = {"id": event_id, "title": _text(title, "--title"), "date": day.isoformat(), "activity": activity,
           "distance_meters": distance_meters, "priority": priority, "status": ACTIVE, "planned_id": planned_id,
           "window": None, "result": None, "note": note.strip() if note and note.strip() else None,
           "created_at": created_at, "changes": []}
    return dict(doc, events=doc["events"] + [row]), row


def update(doc, event_id, fields, reason, at):
    """Change an active event's fields. A new date drops the window and a plan on another date (`cleared`)."""
    row = _active_row(doc, event_id)
    changed, notes, cleared = dict(row), [], []
    for key, value in fields.items():
        if key == "title":
            value = _text(value, "--title")
        if key == "priority" and value not in PRIORITIES:
            raise ValidationError(f"--priority must be one of {', '.join(PRIORITIES)}, found {value!r}")
        if key == "date":
            value = value.isoformat()
        if changed[key] != value:
            notes.append(f"{key} {_shown(changed[key])} → {_shown(value)}")
            changed[key] = value
    if "date" in fields and changed["date"] != row["date"]:
        if changed["window"] is not None:
            changed["window"] = None
            cleared.append("window")
        if changed["planned_id"] and "planned_id" not in fields:
            changed["planned_id"] = None
            cleared.append("planned_id")
    if not notes:
        raise ValidationError(f"nothing to change: {event_id} already holds those values")
    text = "; ".join(notes) + (f"; cleared {', '.join(cleared)}" if cleared else "")
    changed["changes"] = _change(row, at, text, reason.strip() if reason and reason.strip() else None)
    return _replace(doc, changed), changed, cleared


def _shown(value):
    return "none" if value is None else str(value)


def set_window(doc, event_id, start, end, rationale, at):
    """Record the agreed window before the event; start and end None record an agreed decision to keep none."""
    row = _active_row(doc, event_id)
    rationale = _text(rationale, "--rationale")
    window = {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
              "rationale": rationale, "agreed_at": at}
    errors = _window_problems(window, dates.parse_date(row["date"]), "window")
    if errors:
        raise ValidationError(f"{event_id}: the window {errors[0].message}")
    text = f"window {window['start']} to {window['end']} agreed" if start else "agreed: no window"
    changed = dict(row, window=window, changes=_change(row, at, text, rationale))
    return _replace(doc, changed), changed


def clear_window(doc, event_id, reason, at):
    row = _active_row(doc, event_id)
    if row["window"] is None:
        raise ValidationError(f"{event_id} has no agreed window to clear")
    changed = dict(row, window=None, changes=_change(row, at, "window cleared: decision pending again",
                                                     _text(reason, "--reason")))
    return _replace(doc, changed), changed


def complete(doc, event_id, result, today, at):
    row = _active_row(doc, event_id)
    if dates.parse_date(row["date"]) > today:
        raise ValidationError(f"{event_id} is on {row['date']}, after today ({today}): record its result once it "
                              "has happened, or change its date with python3 -m coach events update")
    text = _text(result, "--result")
    changed = dict(row, status="completed", result={"text": text, "recorded_at": at},
                   changes=_change(row, at, "completed"))
    return _replace(doc, changed), changed


def cancel(doc, event_id, reason, at):
    row = _active_row(doc, event_id)
    changed = dict(row, status="cancelled", changes=_change(row, at, "cancelled", _text(reason, "--reason")))
    return _replace(doc, changed), changed


def check_link(store, doc, row):
    """Refuse a planned-activity link that is not live, not on the event's date, of another kind, or already used."""
    planned_id = row["planned_id"]
    if planned_id is None:
        return
    plan = next((p for p in store.planned() if p["id"] == planned_id), None)
    if plan is None:
        raise ValidationError(f"no live planned activity has the id {planned_id}; see python3 -m coach planned list")
    if plan["date"] != row["date"]:
        raise ValidationError(f"{planned_id} is planned for {plan['date']}, not the event's date {row['date']}")
    if row["activity"] is not None and plan["kind"] != row["activity"]:
        raise ValidationError(f"{planned_id} is a {plan['kind']}, not the event's {row['activity']}")
    other = next((r for r in doc["events"] if r["id"] != row["id"] and r["status"] == ACTIVE
                  and r["planned_id"] == planned_id), None)
    if other is not None:
        raise ValidationError(f"{other['id']} already links {planned_id}; one planned activity is one event")


def pending(row, today):
    """The decisions an active event waits on: `result` once its date has passed, else `window` until one is agreed."""
    if row["status"] != ACTIVE:
        return []
    if dates.parse_date(row["date"]) < today:
        return [PENDING_RESULT]
    return [PENDING_WINDOW] if row["window"] is None else []


def has_window(row):
    return row["window"] is not None and row["window"]["start"] is not None


def window_span(row):
    return dates.Span(dates.parse_date(row["window"]["start"]), dates.parse_date(row["window"]["end"]))


def window_sessions(root, row, sessions, library=None, params=None):
    """Heavy lower-body sessions dated in the event's agreed window: `[{date, session_id, title}]`."""
    if not has_window(row):
        return []
    library = library or Library.load(root)
    params = params or interference.heavy_lower_params(root)
    span = window_span(row)
    return [{"date": session["date"], "session_id": session["session_id"], "title": session.get("title")}
            for session in sessions
            if span.contains(dates.parse_date(session["date"]))
            and interference.is_heavy_lower_session(session, library, params)]


def _planned_sessions(root, row, today):
    """The sessions the overlays in force plan in the window, from today on."""
    if not has_window(row):
        return []
    span = window_span(row)
    days = [day for day in span.days() if day >= today]
    docs = []
    for overlay_id in overlay_module.ids(root):
        try:
            docs.append(overlay_module.load(root, overlay_id))
        except ValidationError:
            continue
    return [session for _, session in overlay_module.planned(docs, days)]


def link_status(root, config, row, today):
    """The linked plan's reconcile row: `{planned_id, status, activity_id}`; status None when it cannot be judged."""
    if row["planned_id"] is None:
        return None
    found = {"planned_id": row["planned_id"], "status": None, "activity_id": None}
    if not cardio.activity_on(config):
        return found
    items = cardio.reconcile(root, row["date"], today)["items"]
    item = next((i for i in items if i["planned_id"] == row["planned_id"]), None)
    if item is not None:
        found.update(status=item["status"], activity_id=item["activity_id"])
    return found


def view(root, config, row, today):
    """The event as views show it: countdown, pending decisions, sessions to review and the linked plan."""
    shown = dict(row)
    if row["status"] == ACTIVE:
        shown["days_to_go"] = (dates.parse_date(row["date"]) - today).days
        shown["pending"] = pending(row, today)
        shown["window_sessions"] = window_sessions(root, row, _planned_sessions(root, row, today))
    else:
        shown.update(days_to_go=None, pending=[], window_sessions=[])
    shown["link"] = link_status(root, config, row, today)
    return shown


def views(root, today, include_all=False):
    """Every active event's view in event order; with `include_all`, completed and cancelled ones too."""
    if not exists(root):
        return []
    config = config_module.load(root)
    doc = load(root)
    rows = ordered(doc["events"]) if include_all else active(doc)
    return [view(root, config, row, today) for row in rows]


def label(row, unit="km"):
    parts = [row["priority"]]
    if row["activity"]:
        distance = f" {units.from_meters(row['distance_meters'], unit):g} {unit}" if row["distance_meters"] else ""
        parts.append(f"{row['activity']}{distance}")
    return f"\"{row['title']}\" ({', '.join(parts)})"


def _window_text(row):
    window = row["window"]
    if window is None:
        return None
    if window["start"] is None:
        return "agreed: no taper or review window"
    return f"agreed window {window['start']} to {window['end']}"


def line(shown, unit="km"):
    """One plain sentence for a status or card view."""
    head = f"Event {label(shown, unit)} on {shown['date']}"
    days = shown["days_to_go"]
    if PENDING_RESULT in shown["pending"]:
        return (f"{head} was {-days} day{'s' if days != -1 else ''} ago: record the result "
                f"(python3 -m coach events complete {shown['id']} --result TEXT) or cancel it.")
    when = "is today" if days == 0 else f"{days} day{'s' if days != 1 else ''} to go"
    text = f"{head}: {when}"
    if PENDING_WINDOW in shown["pending"]:
        text += (f"; no taper or review window agreed: agree one with its rationale, or record none "
                 f"(python3 -m coach events window {shown['id']})")
    else:
        text += f"; {_window_text(shown)}"
        if shown["window_sessions"]:
            named = ", ".join(f"{s['title'] or s['session_id']} ({s['date']})" for s in shown["window_sessions"])
            text += f"; heavy lower-body work in the window to review: {named}"
    return text + "."


def distance_unit(config):
    return config["cardio"]["distance_unit"]


def proposal_flags(root, overlay, span, today):
    """The event flags for a draft overlay (C55): heavy lower work in an agreed window, and each pending window."""
    if not exists(root) or overlay is None:
        return []
    doc = load(root)
    unit = distance_unit(config_module.load(root))
    library, params = None, None
    found = []
    for row in active(doc):
        day = dates.parse_date(row["date"])
        if day < span.start:
            continue
        if row["window"] is None:
            found.append(flags.make("event_window_pending", message=(
                f"Event {label(row, unit)} on {row['date']} has no agreed taper or review window, so none is "
                "assumed. Agree one with the athlete and its rationale, or record none: python3 -m coach events "
                f"window {row['id']} (--from D --to D | --none) --rationale TEXT.")))
            continue
        if not has_window(row) or not window_span(row).overlaps(span):
            continue
        if library is None:
            library, params = Library.load(root), interference.heavy_lower_params(root)
        for session in window_sessions(root, row, overlay.get("sessions", []), library, params):
            title = session["title"] or session["session_id"]
            found.append(flags.make("event_window_heavy_lower", session_id=session["session_id"], message=(
                f"Event {label(row, unit)} on {row['date']}: {title} ({session['date']}) is heavy squat or hinge "
                f"work inside the agreed window {row['window']['start']} to {row['window']['end']} "
                f"({row['window']['rationale']}). Review it with the athlete: keep it and resolve this flag with "
                "the reason, or change the line through propose override.")))
    return found

