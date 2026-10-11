"""Double progression: add reps up to the top of the range, then add load and start again at the bottom."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "double_progression"
SUMMARY = ("Adds the increment once every working set reaches the top of its rep range at or under the target "
           "RPE, then drops back to the bottom of the range; otherwise holds the load and adds a rep.")
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {"increment": {"type": ["number", "null"], "minimum": 0}},
    },
    "defaults": {"increment": None},
}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ("rn:progression-training-age.2",)


def _hit_top(source, prescribed):
    logged = [s for s in source.sets if s.working]
    if not prescribed or len(logged) < len(prescribed):
        return False, "fewer working sets than prescribed"
    for wanted, got in zip(prescribed, logged):
        if (got.reps or 0) < (wanted.top_reps or 0):
            return False, "short of the top of the range"
        if wanted.rpe is not None and got.rpe is not None and got.rpe > wanted.rpe:
            return False, f"over the target RPE {base.number(wanted.rpe)}"
    return True, None


def propose(ctx):
    sets = base.expand(ctx.slot.sets)
    source = base.baseline(ctx.exposures)
    if source is None:
        load = base.start_load(ctx)
        reason = "no usable exposure yet, so the start load" if load is not None else \
            "no usable exposure and no start load, so the coach picks the first load"
        return base.Proposal(sets=base.with_load(sets, load), rationale=f"Double progression: {reason}",
                             derived_from=None, state={})

    prescribed = base.working(source.prescribed) or base.working(sets)
    working = base.working(sets)
    bottom = working[0].target_reps if working else None
    top = working[0].top_reps if working else None
    load = source.top_load
    hit, why = _hit_top(source, prescribed)
    when = source.date.isoformat()
    if hit and load is not None:
        step = base.increment(ctx)
        new_load = load + ctx.exercise.load_direction * step
        return base.Proposal(
            sets=base.with_reps(base.with_load(sets, new_load), bottom),
            rationale=(f"Double progression: every working set reached {top} reps at or under target RPE on {when}, "
                       f"so {base.load_words(ctx, load)} goes to {base.load_words(ctx, new_load)} and reps return "
                       f"to {bottom}"),
            derived_from=source, state={},
        )
    logged = [s.reps or 0 for s in source.sets if s.working]
    target = min(top, min(logged) + 1) if logged and top is not None else top
    return base.Proposal(
        sets=base.with_reps(base.with_load(sets, load), target) if target is not None else base.with_load(sets, load),
        rationale=(f"Double progression: {when} was {why}, so {base.load_words(ctx, load)} holds and the target is "
                   f"{target} reps"),
        derived_from=source, state={},
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)

