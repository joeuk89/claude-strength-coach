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
            flag = _judge(ctx, lift, activity)
            if flag is not None:
                found.append(flag)
    return found


def _judge(ctx, lift, activity):
    hours = ctx.params["hours"]
    if base.timed(lift) and base.timed(activity):
        gap = base.hours_between(base.bout_end(activity), lift.start)
        if not 0 <= gap < hours:
            return None
        relation = f"ended {base.hours_text(gap)} before"
    else:
        days = (lift.date - activity.date).days
        if not 1 <= days <= math.ceil(hours / 24):
            return None
        relation = "is the day before" if days == 1 else f"is {days} days before"
    return base.session_flag("collision", (
        f"quality_before_heavy_lower: {base.bout_text(ctx, activity)} {relation} {base.bout_text(ctx, lift)}, "
        f"a heavy squat or hinge session. Keep quality activities at least {base.hours_text(hours)} before heavy "
        "lower-body lifting."), lift.session_id, "warn")
