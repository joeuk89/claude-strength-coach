"""Linear: add the increment after every exposure that hits its prescribed reps; reset after repeated misses."""

from datetime import date

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "linear"
SUMMARY = ("Adds the increment after every exposure that hits all its prescribed reps, holds after a miss, and "
           "resets to a fraction of the load after misses in a row.")
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "increment": {"type": ["number", "null"], "minimum": 0},
            "misses_before_reset": {"type": "integer", "minimum": 1},
            "reset_factor": {"type": "number", "minimum": 0.5, "maximum": 1},
        },
    },
    "defaults": {"increment": None, "misses_before_reset": 2, "reset_factor": 0.9},
}
STATE = {
    "schema": {
        "type": "object", "required": ["misses", "through"], "additionalProperties": False,
        "properties": {
            "misses": {"type": "integer", "minimum": 0},
            "through": {"type": ["string", "null"], "pattern": base.DATE_PATTERN},
        },
    },
    "initial": {"misses": 0, "through": None},
}
FLAGS = {}
CITES = ("rn:progression-training-age.3",)


def propose(ctx):
    sets = base.expand(ctx.slot.sets)
    source = base.baseline(ctx.exposures)
    if source is None:
        load = base.start_load(ctx)
        reason = "no usable exposure yet, so the start load" if load is not None else \
            "no usable exposure and no start load, so the coach picks the first load"
        return base.Proposal(sets=base.with_load(sets, load), rationale=f"Linear: {reason}", derived_from=None,
                             state=dict(ctx.state))

    through = ctx.state.get("through")
    misses = ctx.state.get("misses", 0)
    for exposure in base.usable_oldest_first(ctx.exposures, date.fromisoformat(through) if through else None):
        missed = base.missed(exposure)
        misses = misses + 1 if missed is True else 0
    state = {"misses": misses, "through": source.date.isoformat()}
    load = source.top_load
    limit = ctx.params["misses_before_reset"]
    if load is None:
        return base.Proposal(sets=base.with_load(sets, load), rationale="Linear: the last exposure logged no load",
                             derived_from=source, state=state)
    if not source.prescribed:
        return base.Proposal(sets=base.with_load(sets, load),
                             rationale="Linear: historical prescription unknown, so the last logged load holds",
                             derived_from=source, state=state)
    if misses >= limit:
        factor = ctx.params["reset_factor"]
        new_load = load * factor
        state["misses"] = 0
        review = ()
        if (ctx.slot.start_load is not None
                and (new_load - ctx.slot.start_load) * ctx.exercise.load_direction < 0):
            review = (base.flag(ctx, "linear_below_start",
                                f"Linear reset to {base.load_words(ctx, new_load)} is below the program's "
                                f"starting load {base.load_words(ctx, ctx.slot.start_load)}; review progression"),)
        return base.Proposal(
            sets=base.with_load(sets, new_load),
            rationale=(f"Linear: prescribed reps missed {misses} exposures running, so the load resets to "
                       f"{base.number(factor * 100)} % of {base.load_words(ctx, load)}"),
            derived_from=source, state=state, round_down=True, flags=review,
        )
    if misses:
        return base.Proposal(
            sets=base.with_load(sets, load),
            rationale=(f"Linear: prescribed reps missed on {source.date.isoformat()} (miss {misses} of {limit}), so "
                       f"{base.load_words(ctx, load)} holds"),
            derived_from=source, state=state,
        )
    new_load = load + ctx.exercise.load_direction * base.increment(ctx)
    return base.Proposal(
        sets=base.with_load(sets, new_load),
        rationale=(f"Linear: every prescribed rep was hit on {source.date.isoformat()}, so "
                   f"{base.load_words(ctx, load)} goes to {base.load_words(ctx, new_load)}"),
        derived_from=source, state=state,
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
