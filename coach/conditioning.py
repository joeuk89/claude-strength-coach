"""Conditioning sessions in the proposal pipeline: the density scheme's inputs and the drop rule (contract C51).

A conditioning session's Hevy workout becomes an Activity, so its bouts are
the conditioning Activities matched to the dates its last approved overlay
planned. The drop rule reads R-43's sleep, status-day and quality rules: an
optional conditioning session leaves a draft when one fires, and a core one
stays with a warning.
"""

from datetime import timedelta

from coach import cardio, dates, flags, history, overlay, statusdays
from coach import state as state_module
from coach.activity.store import ActivityStore
from coach.plugins import base

KIND = "conditioning"
DRAFT_REF = "draft"
MATCHED = ("done", "moved")


def state_key(session_id):
    return f"{session_id}/{state_module.SESSION_SLOT}"


def is_state_key(key):
    return key.endswith(f"/{state_module.SESSION_SLOT}")


def has_scheme(session):
    return session["kind"] == KIND and session.get("scheme") is not None


def last_prescription(overlays, session_id):
    """The session in the newest approved overlay that holds it, or None (C51).

    `{overlay_id, session_id, date, dates, span, lines}`: `dates` are every
    date that overlay planned the session on, `lines` the newest date's sets
    per exercise as SetSpecs with coaching-number loads.
    """
    approved = sorted((doc for doc in overlays if overlay.is_approved(doc)),
                      key=lambda d: (d["created_at"], d["id"]), reverse=True)
    for doc in approved:
        sessions = sorted((s for s in doc["sessions"] if s["session_id"] == session_id), key=lambda s: s["date"])
        if sessions:
            newest = sessions[-1]
            lines = {line["exercise_id"]: tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load")))
                                                for s in line["sets"])
                     for line in newest["exercises"]}
            return {"overlay_id": doc["id"], "session_id": session_id, "date": newest["date"],
                    "dates": [s["date"] for s in sessions], "span": doc["span"], "lines": lines}
    return None


def bouts(root, config, last, today):
    """The conditioning Activities matched to the last prescription's dates, newest first (C49 matcher)."""
    if last is None or not cardio.activity_on(config):
        return ()
    span = dates.Span(dates.parse_date(last["span"]["start"]), dates.parse_date(last["span"]["end"]))
    planned = [{"id": f"{last['overlay_id']}/{last['session_id']}/{day}", "date": day, "kind": KIND,
                "title": last["session_id"], "quality": True, "target": {}} for day in last["dates"]]
    logged = ActivityStore(root, config).activities(span, kinds=(KIND,))
    items = cardio.match(planned, logged, config["cardio"]["reconcile_move_days"], today)
    found = [{"date": item["activity_date"], "activity_id": item["activity_id"],
              "duration_seconds": item["actual"]["duration_seconds"], "rpe": item["_activity"].get("rpe")}
             for item in items if item["status"] in MATCHED]
    return tuple(sorted(found, key=lambda b: (b["date"], b["activity_id"]), reverse=True))


def days_off(root, config, day):
    """Days from the newest logged conditioning Activity before `day`; 0 with none or no activity source."""
    if not cardio.activity_on(config):
        return 0
    found = [dates.parse_date(a["local_date"]) for a in ActivityStore(root, config).activity_groups()
             if a["kind"] == KIND and dates.parse_date(a["local_date"]) < day]
    return (day - max(found)).days if found else 0


def _sleep_debt(root, config, today):
    if not cardio.activity_on(config):
        return None
    settings = config["cardio"]
    short, nights, debt = cardio.sleep_judgement(ActivityStore(root, config), settings, today)
    if not debt:
        return None
    return (f"sleep debt: {short} of the {cardio.NIGHTS} nights to {today.isoformat()} were under "
            f"{settings['sleep_short_hours']:g} h asleep")


def _status_day(root, day):
    rows = statusdays.active(root, dates.Span(day, day))
    if not rows:
        return None
    row = rows[0]
    until = row["span"]["end"] or "ongoing"
    return f"{row['kind']} status day {row['id']} ({row['span']['start']} to {until}) covers {day.isoformat()}"


def _quality_bouts(root, config, today, span, draft_sessions):
    """The quality bouts `quality_stack` would judge with the draft as it stands (C49 proposal mode)."""
    if not cardio.activity_on(config):
        return []
    found = cardio.bouts(root, span, "proposal", overlay={"id": DRAFT_REF, "sessions": draft_sessions}, today=today)
    week_of = dates.week_span(span.start, config["athlete"]["week_starts"])
    if week_of.start < span.start:
        found = cardio.bouts(root, dates.Span(week_of.start, span.start - timedelta(days=1)), "logged") + found
    return [b for b in found if b.is_activity() and b.quality and (b.source == "logged" or cardio.plans_read(config))]


def _own(bout, session):
    return bout.ref == f"{DRAFT_REF}/{session['session_id']}" and bout.date.isoformat() == session["date"]


def _stack(quality, session, dropped):
    day = dates.parse_date(session["date"])
    for bout in quality:
        if _own(bout, session) or (bout.ref, bout.date.isoformat()) in dropped:
            continue
        if abs((bout.date - day).days) <= 1:
            source = "planned" if bout.source == "planned" else "logged"
            what = "conditioning session" if bout.kind == KIND else bout.kind
            return f"it would stack with a {source} quality {what} on {bout.date.isoformat()} (quality_stack)"
    return None


def triggers(root, config, today, span, draft_sessions, program_sessions):
    """Each conditioning session of the draft that a drop trigger fires for, in date order (C51 drop rule).

    Returns `{index, session_id, date, title, tier, trigger, reason}` per
    session. Triggers, first match wins: `sleep_debt` active today, a status
    day (`status_active`) on its date, or a `quality_stack` with another
    quality bout. A session already dropped is no longer a stack partner.
    """
    by_id = {s["id"]: s for s in program_sessions}
    found = [(index, s) for index, s in enumerate(draft_sessions) if by_id.get(s["session_id"], {}).get("kind") == KIND]
    if not found:
        return []
    debt = _sleep_debt(root, config, today)
    quality = _quality_bouts(root, config, today, span, draft_sessions)
    fired, dropped = [], set()
    for index, session in sorted(found, key=lambda pair: (pair[1]["date"], pair[0])):
        trigger, reason = None, None
        status = _status_day(root, dates.parse_date(session["date"]))
        stack = _stack(quality, session, dropped)
        if debt:
            trigger, reason = "sleep_debt", debt
        elif status:
            trigger, reason = "status_active", status
        elif stack:
            trigger, reason = "quality_stack", stack
        if trigger is None:
            continue
        tier = by_id[session["session_id"]]["tier"]
        if tier == "optional":
            dropped.add((f"{DRAFT_REF}/{session['session_id']}", session["date"]))
        fired.append({"index": index, "session_id": session["session_id"], "date": session["date"],
                      "title": session["title"], "tier": tier, "trigger": trigger, "reason": reason})
    return fired


def drop_flag(item):
    return flags.make("conditioning_dropped", "info", message=(
        f"Optional conditioning session {item['title']} ({item['session_id']}) on {item['date']} was dropped from "
        f"the proposal: {item['reason']}. Restore it with a reason if the athlete still wants it."))


def keep_flag(item, why):
    return flags.make("conditioning_dropped", "warn", session_id=item["session_id"], message=(
        f"Conditioning session {item['title']} on {item['date']} stays in the proposal although {item['reason']}: "
        f"{why}. Agree with the athlete whether to ease or move it."))
