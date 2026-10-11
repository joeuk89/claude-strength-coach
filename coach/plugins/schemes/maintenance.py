"""Maintenance: the last valid exposure's load and reps again, at the program's set count."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "maintenance"
SUMMARY = ("Repeats the last valid exposure's load and reps at the program's set count and RPE, never "
           "progressing.")
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ("rn:minimum-effective-dose.1",)


def _reps_at_top(source):
    """The fewest reps logged at the exposure's top load, so maintenance never asks for more than was done."""
    reps = [s.reps for s in source.sets if s.working and s.load == source.top_load and s.reps is not None]
    return min(reps) if reps else None


def propose(ctx):
    sets = base.expand(ctx.slot.sets)
    source = base.baseline(ctx.exposures)
    if source is None:
        load = base.start_load(ctx)
        reason = "no valid exposure yet, so the program's sets at the start load" if load is not None else \
            "no valid exposure and no start load, so the coach picks the load"
        return base.Proposal(sets=base.with_load(sets, load), rationale=f"Maintenance: {reason}",
                             derived_from=None, state={})
    load = source.top_load
    reps = _reps_at_top(source)
    sets = base.with_load(sets, load)
    if reps is not None:
        sets = base.with_reps(sets, reps)
    words = f"{base.load_words(ctx, load)} × {reps}" if reps is not None else base.load_words(ctx, load)
    return base.Proposal(
        sets=sets,
        rationale=(f"Maintenance: {words} from {source.date.isoformat()} again at the program's "
                   f"{len(base.working(sets))} working sets, with no progression"),
        derived_from=source, state={},
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
