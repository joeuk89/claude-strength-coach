"""No quality activity in the hours before a heavy squat or hinge session (contract C51)."""

import math

from coach.plugins import base

API = 1
KIND = "interference"
NAME = "quality_before_heavy_lower"
SUMMARY = "Keep quality activities at least 24 hours before a heavy squat or hinge session."
PARAMS = {
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["hours", "heavy_rpe", "heavy_max_reps"],
        "properties": {
            "hours": {"type": "number", "minimum": 1, "maximum": 72},
            "heavy_rpe": {"type": "number", "minimum": 1, "maximum": 10},
            "heavy_max_reps": {"type": "integer", "minimum": 1},
        },
    },
    "defaults": {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6},
}
FLAGS = {}
CITES = ("rn:concurrent-training.5",)


def evaluate(ctx):
    found = []
    heavy = [b for b in ctx.bouts if base.is_lift(b) and b.ref in ctx.heavy_lower]
    for lift in heavy:
        for activity in base.quality_activities(ctx.bouts):
            if activity is lift:
                continue
            flag = _judge(ctx, lift, activity)
            if flag is not None:
                found.append(flag)
    return found


def _judge(ctx, lift, activity):
    hours = ctx.params["hours"]
    lift_text, activity_text = base.bout_text(ctx, lift), base.bout_text(ctx, activity)
    advice = (f"Keep quality activities at least {base.hours_text(hours)} before heavy lower-body lifting, a cautious "
              "coaching heuristic")
    activity_end = base.bout_end(activity)
    if lift.start is not None and activity_end is not None:
        gap = base.hours_between(activity_end, lift.start)
        if not 0 <= gap < hours:
            return None
        return base.session_flag("collision", (
            f"quality_before_heavy_lower: {activity_text} ended {base.hours_text(gap)} before {lift_text}, a heavy "
            f"squat or hinge session. {advice}."), lift.session_id, "warn")
    days = (lift.date - activity.date).days
    if not 1 <= days <= math.ceil(hours / 24):
        return None
    relation = "is the day before" if days == 1 else f"is {days} days before"
    missing = base.timing_gaps(((lift, lift_text, False), (activity, activity_text, True)))
    return base.session_flag("collision", (
        f"quality_before_heavy_lower: {activity_text} {relation} {lift_text}, a heavy squat or hinge session. The "
        f"gap in hours is unknown ({missing}), so it may or may not be under {base.hours_text(hours)}. {advice}; "
        "give the missing times to judge the actual gap."), lift.session_id, "warn")
