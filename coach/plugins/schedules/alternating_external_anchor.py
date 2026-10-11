"""Alternating weeks anchored to a coach-led session: one position a week, confirmed by the coach."""

from datetime import date, timedelta

from coach.plugins import base

API = 1
KIND = "schedule"
NAME = "alternating_external_anchor"
SUMMARY = ("Alternates week templates one position a week, anchored to a coach-led session; each new position "
           "stays unconfirmed until the coach confirms it.")
SESSION_ID = {"type": "string", "pattern": "^[a-z0-9-]+$"}
WEEK = {
    "type": "object", "required": ["name", "days"], "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "days": {"type": "object", "additionalProperties": False,
                 "properties": {day: SESSION_ID for day in base.WEEKDAYS}},
    },
}
PARAMS = {
    "schema": {
        "type": "object", "required": ["weeks"], "additionalProperties": False,
        "properties": {
            "weeks": {"type": "array", "minItems": 2, "items": WEEK},
            "anchor_external_id": {"type": ["string", "null"], "pattern": "^[a-z0-9-]+$"},
        },
    },
    "defaults": {"anchor_external_id": None},
}
FLAGS = {}
CITES = ()


def positions(params):
    return tuple(week["name"] for week in params.get("weeks", []))


def _position_for(ctx, names, start):
    """(position, confirmed) for the week starting `start`."""
    rotation = ctx.rotation or {}
    current = rotation.get("position")
    if current not in names:
        return names[0], False
    known_week = rotation.get("week")
    anchor = date.fromisoformat(known_week) if known_week else base.week_start(ctx.today, ctx.week_starts)
    weeks = (start - anchor).days // 7
    position = names[(names.index(current) + weeks) % len(names)]
    return position, bool(rotation.get("confirmed")) and weeks == 0


def plan(ctx):
    names = positions(ctx.params)
    days_by_name = {week["name"]: week["days"] for week in ctx.params["weeks"]}
    anchor = ctx.params.get("anchor_external_id")
    found, flags, rotation = [], [], None
    start = base.week_start(ctx.span_start, ctx.week_starts)
    while start <= ctx.span_end:
        position, confirmed = _position_for(ctx, names, start)
        rotation = {"position": position, "confirmed": confirmed, "week": start.isoformat()}
        if not confirmed:
            against = f" against {anchor}'s log" if anchor else ""
            flags.append(base.week_flag(
                "rotation_unconfirmed", (
                    f"The rotation advanced to {position} for the week of {start.isoformat()} without confirmation; "
                    f"confirm it{against} with schedule confirm --position {position}")))
        for offset in range(7):
            day = start + timedelta(days=offset)
            session_id = days_by_name[position].get(base.WEEKDAYS[day.weekday()])
            if session_id and ctx.span_start <= day <= ctx.span_end:
                found.append((day, session_id))
        start += timedelta(days=7)
    return base.SchedulePlan(sessions=tuple(found), rotation=rotation, flags=tuple(flags))


def problems(params, program):
    known = {session["id"] for session in program["sessions"]}
    externals = {external["id"] for external in program["external_sessions"]}
    found = []
    for index, week in enumerate(params.get("weeks", [])):
        for day, session_id in week.get("days", {}).items():
            if session_id not in known:
                found.append((f"$.weeks[{index}].days.{day}", f"no program session {session_id}"))
    names = positions(params)
    if len(set(names)) != len(names):
        found.append(("$.weeks", "two weeks share a name"))
    anchor = params.get("anchor_external_id")
    if anchor is not None and anchor not in externals:
        found.append(("$.anchor_external_id", f"no external session {anchor} in the program"))
    return found
