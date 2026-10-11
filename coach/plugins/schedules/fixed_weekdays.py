"""Fixed weekdays: each session on the same weekday every week."""

from datetime import timedelta

from coach.plugins import base

API = 1
KIND = "schedule"
NAME = "fixed_weekdays"
SUMMARY = "Puts each session on the same weekday every week."
SESSION_ID = {"type": "string", "pattern": "^[a-z0-9-]+$"}
DAYS = {"type": "object", "additionalProperties": False, "properties": {day: SESSION_ID for day in base.WEEKDAYS}}
PARAMS = {
    "schema": {"type": "object", "required": ["days"], "additionalProperties": False, "properties": {"days": DAYS}},
    "defaults": {},
}
FLAGS = {}
CITES = ()


def positions(params):
    return ()


def plan(ctx):
    days = ctx.params["days"]
    found = []
    day = ctx.span_start
    while day <= ctx.span_end:
        session_id = days.get(base.WEEKDAYS[day.weekday()])
        if session_id:
            found.append((day, session_id))
        day += timedelta(days=1)
    return base.SchedulePlan(sessions=tuple(found))


def problems(params, program):
    known = {session["id"] for session in program["sessions"]}
    return [(f"$.days.{day}", f"no program session {session_id}")
            for day, session_id in params.get("days", {}).items() if session_id not in known]
