"""The overlay in force, its push state, the next sessions and any uncovered day (contract C10, C52)."""

import json
from datetime import date, timedelta
from pathlib import Path

from coach import dates, paths, routines, statusdays
from coach import overlay as overlay_module
from coach import program as program_module
from coach.errors import ValidationError
from coach.status import Section, provider

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
NOT_APPROVED, EDITED = "not_approved", "edited_after_approval"
APPROVED, NO_ROUTINES, NOT_PUSHED, UNVERIFIED, PARTLY, VERIFIED = (
    "approved", "no_routines", "not_pushed", "unverified", "partly_verified", "verified")
_SETTLED = (APPROVED, VERIFIED)


@provider(id="overlay", owner="R-26b", order=30)
def overlay_status(ctx):
    today = ctx.today()
    docs, skipped = _overlays(ctx.root)
    if not docs and not skipped and not program_module.exists(ctx.root):
        return None
    hevy_on = ctx.config.hevy.enabled
    audit = _audit(ctx.root)

    found = overlay_module.pick_in_force(docs, today)
    current = found[0] if found else None
    upcoming = None if current else _next_to_start(docs, today)
    shown = current or upcoming
    summary = _summary(ctx.root, shown, audit, hevy_on) if shown else None

    coming = _coming_week(ctx, today)
    rows = _breaks(ctx.root, dates.Span(today, coming.end))
    off = {day for day in dates.Span(today, coming.end).days() if any(_covers(row, day) for row in rows)}
    uncovered = [day for day in coming.days()
                 if day >= today and day not in off and not overlay_module.pick_in_force(docs, day)]
    resting = today in off or (not uncovered and any(day in off for day in coming.days()))

    if current:
        head = f"Overlay in force today: {_describe(summary)}."
    elif upcoming:
        head = f"No overlay is in force today; the next is {_describe(summary, with_first=True)}."
    elif resting:
        head = "No overlay is in force today and none is needed: the athlete agreed a planned break."
    else:
        head = "No overlay is in force today and none is planned; plan the week with /program-week."
    lines = [head] + [_break_line(row) for row in rows]

    next_sessions = _next_sessions(docs, today, _breaks(ctx.root, dates.Span(today, date.max)))
    if next_sessions:
        lines.append(_next_line(next_sessions))

    if uncovered:
        lines.append(f"No overlay covers {_days(uncovered)} in the coming week; plan it with /program-week.")

    attention = bool(uncovered) or (shown is None and not resting) or (
        shown is not None and summary["state"] not in _SETTLED)
    data = {
        "in_force": summary if current else None,
        "next": summary if upcoming else None,
        "next_sessions": next_sessions,
        "coming_week": {"start": coming.start.isoformat(), "end": coming.end.isoformat()},
        "uncovered": [day.isoformat() for day in uncovered],
        "breaks": [{"id": row["id"], "kind": row["kind"], "span": row["span"], "note": row["note"]} for row in rows],
        "skipped": skipped,
    }
    return Section("overlay", lines, data, "attention" if attention else "info")


def _breaks(root, span):
    """Planned breaks overlapping the span; none when the status-days file cannot be read (its check reports it)."""
    try:
        return statusdays.breaks(root, span)
    except ValidationError:
        return []


def _covers(row, day):
    return statusdays.span_of(row).contains(day)


def _break_line(row):
    start = dates.parse_date(row["span"]["start"])
    if row["span"]["end"] is None:
        when = f"from {_day(start)} until it is ended (status-days end {row['id']})"
    else:
        end = dates.parse_date(row["span"]["end"])
        when = f"{_day(start)} to {_day(end)}; training resumes {_day(end + timedelta(days=1))}"
    return f"Planned break {row['id']} ({row['kind']}: {row['note']}): no training {when}."


def _overlays(root):
    docs, skipped = [], []
    for overlay_id in overlay_module.ids(root):
        try:
            docs.append(overlay_module.load(root, overlay_id))
        except ValidationError:
            skipped.append(overlay_id)
    return docs, skipped


def _next_to_start(docs, today):
    later = [doc for doc in docs if doc["span"]["start"] > today.isoformat()]
    if not later:
        return None
    first = min(doc["span"]["start"] for doc in later)
    starting = [doc for doc in later if doc["span"]["start"] == first]
    return max(starting, key=lambda d: (dates.parse_timestamp(d["created_at"]), d["id"]))


def _audit(root):
    path = Path(root) / paths.HEVY_WRITES
    if not path.is_file():
        return []
    lines = []
    for text in path.read_text(encoding="utf-8").splitlines():
        try:
            line = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(line, dict):
            lines.append(line)
    return lines


def _routine_ids(root, doc):
    try:
        found = routines.session_routines(root, doc)
    except ValidationError:
        found = [session.get("hevy_routine_id") for session in doc["sessions"]]
    return list(dict.fromkeys(routine_id for routine_id in found if routine_id))


def _push_state(root, doc, audit):
    routine_ids = _routine_ids(root, doc)
    if not routine_ids:
        return NO_ROUTINES, 0, 0
    approval_hash = doc["approval"]["hash"]
    latest = {}
    for line in audit:
        if (line.get("kind") == "verify" and line.get("overlay_id") == doc["id"]
                and line.get("overlay_hash") == approval_hash):
            latest[line.get("routine_id")] = line.get("verified") is True
    verified = sum(1 for routine_id in routine_ids if latest.get(routine_id))
    if verified == len(routine_ids):
        return VERIFIED, verified, len(routine_ids)
    if verified:
        return PARTLY, verified, len(routine_ids)
    written = any(line.get("kind") == "write" and line.get("overlay_id") == doc["id"] for line in audit)
    return (UNVERIFIED if written or latest else NOT_PUSHED), 0, len(routine_ids)


def _summary(root, doc, audit, hevy_on):
    verified = total = None
    if overlay_module.is_approved(doc):
        if hevy_on:
            state, verified, total = _push_state(root, doc, audit)
        else:
            state = APPROVED
    else:
        state = EDITED if doc.get("approval") else NOT_APPROVED
    first = min(doc["sessions"], key=lambda s: s["date"]) if doc["sessions"] else None
    return {
        "id": doc["id"], "kind": doc["kind"], "span": doc["span"], "approved": state not in (NOT_APPROVED, EDITED),
        "state": state, "routines_verified": verified, "routines": total,
        "first_session": {"session_id": first["session_id"], "title": first["title"], "date": first["date"]}
        if first else None,
    }


def _describe(summary, with_first=False):
    span = summary["span"]
    state = {
        NOT_APPROVED: "not approved",
        EDITED: "edited after approval, so not approved",
        APPROVED: "approved",
        NO_ROUTINES: "approved, but no session has a Hevy routine yet (python3 -m coach routines create --dry-run)",
        NOT_PUSHED: "approved, not pushed to Hevy",
        UNVERIFIED: "approved, pushed but not verified",
        PARTLY: f"approved, {summary['routines_verified']} of {summary['routines']} Hevy routines verified",
        VERIFIED: "approved, pushed and verified",
    }[summary["state"]]
    text = f"{summary['id']} ({summary['kind']}, {span['start']} to {span['end']}), {state}"
    first = summary["first_session"]
    if with_first and first:
        text += f"; first session {first['title']} on {_day(first['date'])}"
    return text


def _next_sessions(docs, today, breaks=(), limit=2):
    found = []
    session_dates = sorted({s["date"] for doc in docs for s in doc["sessions"] if s["date"] >= today.isoformat()})
    for day in session_dates:
        if any(_covers(row, dates.parse_date(day)) for row in breaks):
            continue
        picked = overlay_module.pick_in_force(docs, day)
        if not picked:
            continue
        doc = picked[0]
        for session in overlay_module.sessions_on(doc, day):
            found.append({"date": day, "session_id": session["session_id"], "title": session["title"],
                          "overlay_id": doc["id"]})
            if len(found) == limit:
                return found
    return found


def _next_line(sessions):
    overlay_ids = {s["overlay_id"] for s in sessions}
    if len(overlay_ids) == 1:
        listed = ", ".join(f"{s['title']} on {_day(s['date'])}" for s in sessions)
        return f"Next sessions ({overlay_ids.pop()}): {listed}."
    listed = ", ".join(f"{s['title']} on {_day(s['date'])} ({s['overlay_id']})" for s in sessions)
    return f"Next sessions: {listed}."


def _coming_week(ctx, today):
    return dates.week_span(today + timedelta(days=1), ctx.config.athlete.week_starts)


def _day(iso):
    day = dates.parse_date(iso) if isinstance(iso, str) else iso
    return f"{WEEKDAYS[day.weekday()]} {day.isoformat()}"


def _days(days):
    runs, start, prev = [], days[0], days[0]
    for day in days[1:]:
        if day - prev != timedelta(days=1):
            runs.append((start, prev))
            start = day
        prev = day
    runs.append((start, prev))
    return ", ".join(a.isoformat() if a == b else f"{a.isoformat()} to {b.isoformat()}" for a, b in runs)
