"""The return week: one working set fewer at the derived-from load, no set above RPE 8.

A line the core already decayed for days off (more than 10) passes through
unchanged, so a return week never cuts twice.
"""

from dataclasses import replace

from coach.plugins import base

API = 1
KIND = "transform"
NAME = "return"
SUMMARY = ("Drops one working set per line (never below one) at the load last lifted, with no set above RPE 8; "
           "lines already stepped back for days off are left as they are.")
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "set_delta": {"type": "integer", "maximum": 0},
            "rpe_cap": {"type": "number", "minimum": 1, "maximum": 10},
        },
    },
    "defaults": {"set_delta": -1, "rpe_cap": 8},
}
FLAGS = {}
CITES = ("rn:deloads.8",)


def apply(ctx, proposal):
    if ctx.days_off > base.return_band(0).upper:
        return proposal
    source = proposal.derived_from
    sets = base.keep_working(proposal.sets, base.return_set_count(proposal, ctx.params["set_delta"]))
    sets = base.scaled(sets, 1.0, source.top_load if source else None)
    return replace(proposal, sets=base.rpe_capped(sets, ctx.params["rpe_cap"]), round_down=True)
