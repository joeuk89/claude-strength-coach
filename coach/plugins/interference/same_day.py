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
            if activity is lift:
                continue
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
    """A same-date pair, or a pair across midnight whose measured spacing is under the gap; None when it passes."""
    params = ctx.params
    min_gap = params["min_gap_hours"]
    lift_text, activity_text = base.bout_text(ctx, lift), base.bout_text(ctx, activity)
    same_date = activity.date == lift.date
    if lift.start is None or activity.start is None:
        if not same_date:
            return None
        missing = base.timing_gaps(((lift, lift_text, False), (activity, activity_text, False)))
        return base.session_flag("collision", (
            f"same_day: {lift_text} and {activity_text} are on one day; their order and gap are unknown "
            f"({missing}). {_advice(params)}"), lift.session_id, "info")
    activity_first = activity.start < lift.start
    first, second = (activity, lift) if activity_first else (lift, activity)
    first_text = activity_text if activity_first else lift_text
    end = base.bout_end(first)
    spacing = base.hours_between(end if end is not None else first.start, second.start)
    if not same_date and spacing >= min_gap:
        return None
    out_of_order = activity_first and params["lift_first"]
    if end is not None:
        if not out_of_order and spacing >= min_gap:
            return None
        gap = base.hours_text(max(spacing, 0))
        if activity_first:
            what = f"{activity_text} came before {lift_text}, ending {gap} before it started"
        else:
            what = f"{activity_text} started {gap} after {lift_text} ended"
        return base.session_flag("collision", f"same_day: {what}. {_advice(params)}", lift.session_id, "warn")
    order = "started before" if activity_first else f"started {base.hours_text(spacing)} after"
    what = f"{activity_text} {order} {lift_text} started; the gap after {first_text} ends is unknown (no duration)"
    if out_of_order or spacing < min_gap:
        return base.session_flag("collision", f"same_day: {what}. {_advice(params)}", lift.session_id, "warn")
    return base.session_flag("collision", f"same_day: {what}. {_advice(params)}", lift.session_id, "info")
