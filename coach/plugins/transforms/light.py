"""The light week: two thirds of the working sets at held loads, no set above RPE 8."""

from dataclasses import replace

from coach.plugins import base

API = 1
KIND = "transform"
NAME = "light"
SUMMARY = ("Keeps two thirds of each line's working sets (at least one) at the loads already lifted, with no set "
           "above RPE 8.")
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "set_factor": {"type": "number", "minimum": 0, "maximum": 1},
            "load_factor": {"type": "number", "minimum": 0, "maximum": 1},
            "rpe_cap": {"type": "number", "minimum": 1, "maximum": 10},
        },
    },
    "defaults": {"set_factor": 0.67, "load_factor": 1.0, "rpe_cap": 8},
}
FLAGS = {}
CITES = ("rn:deloads.8", "rn:deloads.10")


def apply(ctx, proposal):
    count = len(base.working(proposal.sets))
    sets = base.keep_working(proposal.sets, max(1, round(count * ctx.params["set_factor"])))
    sets = base.lightened(sets, ctx.params["load_factor"], proposal.derived_from, ctx.exercise.load_direction)
    return replace(proposal, sets=base.rpe_capped(sets, ctx.params["rpe_cap"]), round_down=True)
