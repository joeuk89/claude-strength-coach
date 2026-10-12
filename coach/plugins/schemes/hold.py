"""Hold: the last ordinary approved prescription again.

A deload, light or return line is recovery work, not the prescription being held, so the sets it removed come back.
After a return week the line holds at the load that week logged, never above the ordinary line's.
"""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "hold"
SUMMARY = ("Repeats the last approved prescription unchanged; after a deload or return week, the last ordinary one, "
           "at the load a return week logged.")
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ()


def propose(ctx):
    source = base.baseline(ctx.exposures)
    last, ordinary = ctx.last_prescription, ctx.last_ordinary_prescription
    if last and not last.get("recovery"):
        return base.Proposal(
            sets=base.prescription_sets(last),
            rationale=f"Hold: the line approved in {last['overlay_id']} stands unchanged",
            derived_from=source, state={},
        )
    if last and ordinary:
        return _after_recovery(ctx, last, ordinary, source)
    if last:
        sets = base.with_load(base.expand(ctx.slot.sets), source.top_load if source else base.start_load(ctx))
        where = f"the load logged on {source.date.isoformat()}" if source else "its load"
        return base.Proposal(
            sets=sets, derived_from=source, state={},
            rationale=(f"Hold: the only approved line, in {last['overlay_id']}, is {last['recovery']} work, so the "
                       f"program's sets at {where}"),
        )
    load = source.top_load if source else ctx.slot.start_load
    where = f"the load logged on {source.date.isoformat()}" if source else "the program's start load"
    return base.Proposal(
        sets=base.with_load(base.expand(ctx.slot.sets), load),
        rationale=f"Hold: no approved line yet, so the program's sets at {where}",
        derived_from=source, state={},
    )


def _after_recovery(ctx, last, ordinary, source):
    sets = base.prescription_sets(ordinary)
    lead = f"Hold: the line approved in {ordinary['overlay_id']} again after the {last['recovery']} line of " \
           f"{last['overlay_id']}"
    returned = source is not None and source.week_kind == "return" and source.date.isoformat() > ordinary["date"]
    top = base.top_load(sets)
    if not returned or top is None or source.top_load is None or ctx.exercise.load_direction < 0 \
            or source.top_load >= top:
        return base.Proposal(sets=sets, rationale=f"{lead}, its sets restored", derived_from=source, state={})
    return base.Proposal(
        sets=base.scaled(sets, source.top_load / top), derived_from=source, state={}, round_down=True,
        rationale=(f"{lead}, its sets restored at the {base.load_words(ctx, source.top_load)} the return week "
                   f"logged on {source.date.isoformat()}"),
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
