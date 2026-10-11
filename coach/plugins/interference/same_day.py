"""Lift first and keep a gap before a quality activity on the same day (contract C51)."""

from coach.plugins import base

API = 1
KIND = "interference"
NAME = "same_day"
SUMMARY = "Lift first and keep at least six hours before a same-day quality activity."
PARAMS = {
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["min_gap_hours", "lift_first"],
        "properties": {
            "min_gap_hours": {"type": "number", "minimum": 0, "maximum": 24},
            "lift_first": {"type": "boolean"},
        },
    },
    "defaults": {"min_gap_hours": 6, "lift_first": True},
}
FLAGS = {}
CITES = ("rn:concurrent-training.4",)


def evaluate(ctx):
    found = []
    for lift in (b for b in ctx.bouts if base.is_lift(b)):
        for activity in base.quality_activities(ctx.bouts):
            if activity.date == lift.date:
                flag = _judge(ctx, lift, activity)
                if flag is not None:
                    found.append(flag)
    return found


def _advice(params):
    gap = base.hours_text(params["min_gap_hours"])
    if params["lift_first"]:
        return f"Same day: lift first, keep at least {gap} between."
    return f"Same day: keep at least {gap} between."


def _judge(ctx, lift, activity):
    params = ctx.params
    lift_text, activity_text = base.bout_text(ctx, lift), base.bout_text(ctx, activity)
    if not (base.timed(lift) and base.timed(activity)):
        return base.session_flag("collision", (
            f"same_day: {lift_text} and {activity_text} are on one day. {_advice(params)}"), lift.session_id, "info")
    if activity.start < lift.start:
        gap = base.hours_between(base.bout_end(activity), lift.start)
        what = f"{activity_text} came before {lift_text}, ending {base.hours_text(max(gap, 0))} before it started"
        broken = params["lift_first"] or gap < params["min_gap_hours"]
    else:
        gap = base.hours_between(base.bout_end(lift), activity.start)
        what = f"{activity_text} started {base.hours_text(max(gap, 0))} after {lift_text} ended"
        broken = gap < params["min_gap_hours"]
    if not broken:
        return None
    return base.session_flag("collision", f"same_day: {what}. {_advice(params)}", lift.session_id, "warn")
