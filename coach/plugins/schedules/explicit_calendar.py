"""Explicit calendar: the sessions on the dates the params name, and nothing else."""

from datetime import date

from coach.plugins import base

API = 1
KIND = "schedule"
NAME = "explicit_calendar"
SUMMARY = "Puts each session on the dates the program lists, and plans nothing on any other day."
SESSION_ID = {"type": "string", "pattern": "^[a-z0-9-]+$"}
PARAMS = {
    "schema": {
        "type": "object", "required": ["dates"], "additionalProperties": False,
        "properties": {"dates": {"type": "object", "additionalProperties": SESSION_ID}},
    },
    "defaults": {},
}
FLAGS = {}
CITES = ()


def positions(params):
    return ()


def _day(text):
    try:
        return date.fromisoformat(text) if len(text) == 10 else None
    except ValueError:
        return None


def plan(ctx):
    found = []
    for text, session_id in ctx.params["dates"].items():
        day = _day(text)
        if day is not None and ctx.span_start <= day <= ctx.span_end:
            found.append((day, session_id))
    return base.SchedulePlan(sessions=tuple(sorted(found)))


def problems(params, program):
    known = {session["id"] for session in program["sessions"]}
    found = []
    for text, session_id in params.get("dates", {}).items():
        if _day(text) is None:
            found.append((f"$.dates.{text}", f"{text} is not a date (YYYY-MM-DD)"))
        if session_id not in known:
            found.append((f"$.dates.{text}", f"no program session {session_id}"))
    return found
