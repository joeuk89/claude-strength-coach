"""Hold: the last approved prescription again, unchanged."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "hold"
SUMMARY = "Repeats the last approved prescription unchanged."
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ()


def propose(ctx):
    source = base.baseline(ctx.exposures)
    if ctx.last_prescription:
        return base.Proposal(
            sets=base.prescription_sets(ctx.last_prescription),
            rationale=f"Hold: the line approved in {ctx.last_prescription['overlay_id']} stands unchanged",
            derived_from=source, state={},
        )
    load = source.top_load if source else ctx.slot.start_load
    where = f"the load logged on {source.date.isoformat()}" if source else "the program's start load"
    return base.Proposal(
        sets=base.with_load(base.expand(ctx.slot.sets), load),
        rationale=f"Hold: no approved line yet, so the program's sets at {where}",
        derived_from=source, state={},
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
