"""The standard deload: two thirds of the working sets, loads cut 10 %, every set at RPE 6."""

from coach.plugins import base

API = 1
KIND = "transform"
NAME = "standard"
SUMMARY = ("Keeps two thirds of each line's working sets (at least one), takes 10 % off the loads and puts every "
           "set at RPE 6; bodyweight work is cut by sets and taken further from failure.")
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "set_factor": {"type": "number", "minimum": 0, "maximum": 1},
            "load_factor": {"type": "number", "minimum": 0, "maximum": 1},
            "rpe": {"type": "number", "minimum": 1, "maximum": 10},
        },
    },
    "defaults": dict(base.STANDARD_DELOAD),
}
FLAGS = {}
CITES = ("rn:deloads.8", "rn:deloads.9")


def apply(ctx, proposal):
    return base.standard_deload(proposal, ctx.params["set_factor"], ctx.params["load_factor"], ctx.params["rpe"])
