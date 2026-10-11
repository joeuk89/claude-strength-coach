"""Next in sequence: the program's sessions in order on the given weekdays, continuing after the last trained one.

The rotation position is the session last trained before the week it names
starts. A later week assumes every session planned in between was trained,
so its position stays unconfirmed until `schedule confirm` records the real one.
"""

from datetime import date, timedelta

from coach.plugins import base

API = 1
KIND = "schedule"
NAME = "next_in_sequence"
SUMMARY = ("Puts the program's sessions, in sequence order, on the given weekdays, continuing after the last "
           "trained session whatever weekday it fell on.")
SESSION_ID = {"type": "string", "pattern": "^[a-z0-9-]+$"}
PARAMS = {
    "schema": {
        "type": "object", "required": ["sequence", "days"], "additionalProperties": False,
        "properties": {
            "sequence": {"type": "array", "minItems": 1, "items": SESSION_ID},
            "days": {"type": "array", "minItems": 1, "items": {"enum": list(base.WEEKDAYS)}},
        },
    },
    "defaults": {},
}
FLAGS = {}
CITES = ()


def positions(params):
    return tuple(params.get("sequence", []))


def _slots(start, days):
    """The dates of week `start` that carry a session, in calendar order."""
    return [start + timedelta(days=offset) for offset in range(7)
            if base.WEEKDAYS[(start + timedelta(days=offset)).weekday()] in days]


def plan(ctx):
    sequence, days = ctx.params["sequence"], set(ctx.params["days"])
    per_week = len(days)
    rotation = ctx.rotation or {}
    first_week = base.week_start(ctx.span_start, ctx.week_starts)
    if rotation.get("position") in sequence:
        last = sequence.index(rotation["position"])
        known_week = rotation.get("week")
        anchor = date.fromisoformat(known_week) if known_week else base.week_start(ctx.today, ctx.week_starts)
        confirmed = bool(rotation.get("confirmed"))
    else:
        last, anchor, confirmed = len(sequence) - 1, first_week, False

    found, flags, plan_rotation = [], [], None
    start = first_week
    while start <= ctx.span_end:
        weeks = (start - anchor).days // 7
        before = (last + weeks * per_week) % len(sequence)
        week_confirmed = confirmed and weeks == 0
        plan_rotation = {"position": sequence[before], "confirmed": week_confirmed, "week": start.isoformat()}
        if not week_confirmed:
            flags.append(base.week_flag("rotation_unconfirmed", (
                f"The sequence assumes {sequence[before]} was the last session trained before the week of "
                f"{start.isoformat()}; confirm the last session trained with schedule confirm --position <session>")))
        for index, day in enumerate(_slots(start, days)):
            if ctx.span_start <= day <= ctx.span_end:
                found.append((day, sequence[(before + 1 + index) % len(sequence)]))
        start += timedelta(days=7)
    return base.SchedulePlan(sessions=tuple(found), rotation=plan_rotation, flags=tuple(flags))


def problems(params, program):
    known = {session["id"] for session in program["sessions"]}
    sequence, days = params.get("sequence", []), params.get("days", [])
    found = [(f"$.sequence[{index}]", f"no program session {session_id}")
             for index, session_id in enumerate(sequence) if session_id not in known]
    if len(set(sequence)) != len(sequence):
        found.append(("$.sequence", "a session appears twice; each session appears once in the sequence"))
    if len(set(days)) != len(days):
        found.append(("$.days", "a weekday appears twice"))
    return found
