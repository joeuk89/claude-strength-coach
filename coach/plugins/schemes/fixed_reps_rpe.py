"""Fixed reps at a target RPE: each set's load comes from the recent e1RM."""

from dataclasses import replace

from coach.plugins import base
from coach.stats import load_for

API = 1
KIND = "scheme"
NAME = "fixed_reps_rpe"
SUMMARY = "Keeps the program's reps and RPE and sets each load from the best e1RM of the last 42 days, rounded down."
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
LOAD_MODES = base.E1RM_MODES
CITES = ("rn:autoregulation.1",)


def propose(ctx):
    sets = base.expand(ctx.slot.sets)
    source = base.baseline(ctx.exposures)
    if ctx.e1rm is None:
        load = source.top_load if source else base.start_load(ctx)
        return base.Proposal(sets=base.with_load(sets, load),
                             rationale="Fixed reps at RPE: no e1RM in the last 42 days, so the load holds",
                             derived_from=source, state={})
    found = []
    for s in sets:
        if s.working and s.target_reps is not None:
            s = replace(s, load=load_for(ctx.e1rm, s.target_reps, s.rpe))
        found.append(s)
    first = next((s for s in found if s.working), None)
    words = (f"{first.target_reps} reps at RPE {base.number(first.rpe)}" if first and first.rpe is not None
             else "the prescribed reps")
    return base.Proposal(
        sets=tuple(found),
        rationale=f"Fixed reps at RPE: the load for {words} from the e1RM of {base.number(ctx.e1rm)}",
        derived_from=source, state={}, round_down=True,
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
