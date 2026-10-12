"""Double progression: the program's rep range at its target RPE, adding load once every set reaches the top."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "double_progression"
SUMMARY = ("Prescribes the program's rep range at its target RPE and adds the increment once every working set "
           "reaches the top of the range, at or under the target RPE unless the line is uncapped isolation work; "
           "otherwise holds the load and flags work below the range or 2 or more RPE over target.")
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
LOAD_MODES = ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band")
MISMATCH_RPE_OVER = base.RPE_STEP_BACK


def _at(values, index):
    """The value for working set `index`; a set past the last one takes the last."""
    return values[min(index, len(values) - 1)] if values else None


def _capped(ctx):
    return any(c.get("kind") == "rpe_cap" for c in ctx.constraints)


def _load_step(ctx, source, prescribed, program_sets):
    """(add load, why not, effort note): reps judged against the program's range tops, RPE against `prescribed`.

    RPE over target holds the load unless the line is isolation work with
    no recovery cap; the note then names the effort the step went past.
    """
    logged = base.working(source.sets)
    if not prescribed:
        return False, "historical prescription unknown", None
    tops = [s.top_reps for s in program_sets]
    if not tops or len(logged) < len(prescribed):
        return False, "fewer working sets than prescribed", None
    if any((got.reps or 0) < (_at(tops, index) or 0) for index, got in enumerate(logged[:len(prescribed)])):
        return False, "short of the top of the range", None
    over = [(got.rpe, wanted.rpe) for wanted, got in zip(prescribed, logged)
            if wanted.rpe is not None and got.rpe is not None and got.rpe > wanted.rpe]
    if not over:
        return True, None, None
    target = base.number(over[0][1])
    if _capped(ctx):
        return False, f"over the target RPE {target} under a recovery cap", None
    if not ctx.exercise.is_isolation:
        return False, f"over the target RPE {target}", None
    rpe, wanted = max(over)
    return True, None, f"RPE {base.number(rpe)} over the target RPE {base.number(wanted)} does not hold isolation work"


def _range_text(program_sets):
    first = program_sets[0]
    if first.target_reps == first.top_reps:
        return f"{first.target_reps}"
    return f"{first.target_reps}–{first.top_reps}"


def _target_text(program_sets):
    rpe = program_sets[0].rpe
    return f"{_range_text(program_sets)} reps" + (f" at RPE {base.number(rpe)}" if rpe is not None else "")


def _where(ctx, load):
    return "on the band" if ctx.exercise.load_mode == "band" else f"at {base.load_words(ctx, load)}"


def _mismatch(ctx, source, program_sets, load):
    """A flag when the held load's exposure fell below the range or 2 or more RPE over target, else None."""
    logged = base.working(source.sets)[:len(program_sets)]
    bottoms = [s.target_reps for s in program_sets]
    targets = [s.rpe for s in program_sets]
    below = any(got.reps is not None and _at(bottoms, i) is not None and got.reps < _at(bottoms, i)
                for i, got in enumerate(logged))
    over = [(got.rpe, _at(targets, i)) for i, got in enumerate(logged)
            if got.rpe is not None and _at(targets, i) is not None and got.rpe >= _at(targets, i) + MISMATCH_RPE_OVER]
    if not below and not over:
        return None
    found = []
    if below:
        reps = ", ".join(str(got.reps) if got.reps is not None else "?" for got in logged)
        found.append(f"{reps} reps, below the program's {_range_text(program_sets)}")
    if over:
        rpe, target = max(over)
        found.append(f"RPE {base.number(rpe)} against the target RPE {base.number(target)}")
    band = ctx.exercise.load_mode == "band"
    held, easier = ("the band", "an easier band") if band else ("the load", "a lighter load")
    message = (f"{ctx.exercise.name}: {source.date.isoformat()} logged {' and '.join(found)} {_where(ctx, load)}; "
               f"holding {held} at the program's range does not make it reachable, so review {easier} or a "
               f"different rep range with the athlete")
    return base.flag(ctx, "range_effort_mismatch", message)


def propose(ctx):
    sets = base.expand(ctx.slot.sets)
    source = base.baseline(ctx.exposures)
    if source is None:
        load = base.start_load(ctx)
        reason = "no usable exposure yet, so the start load" if load is not None else \
            "no usable exposure and no start load, so the coach picks the first load"
        return base.Proposal(sets=base.with_load(sets, load), rationale=f"Double progression: {reason}",
                             derived_from=None, state={})

    program_sets = base.working(sets)
    load = source.top_load
    when = source.date.isoformat()
    if not program_sets:
        return base.Proposal(sets=sets, rationale="Double progression: the slot has no working sets to progress",
                             derived_from=source, state={})
    target = _target_text(program_sets)
    hit, why, note = _load_step(ctx, source, base.working(source.prescribed), program_sets)
    reached = f"every working set reached {program_sets[0].top_reps} reps"
    reached += f" ({note})" if note else " at or under the target RPE"
    if hit and ctx.exercise.load_mode == "band":
        return base.Proposal(
            sets=base.with_load(sets, None),
            rationale=(f"Double progression: {reached} on {when}; band work carries no load number, so the target "
                       f"stays {target} and the coach picks a harder band"),
            derived_from=source, state={},
        )
    if hit and load is None:
        hit, why = False, "logged without a load"
    if hit:
        new_load = load + ctx.exercise.load_direction * base.increment(ctx)
        return base.Proposal(
            sets=base.with_load(sets, new_load),
            rationale=(f"Double progression: {reached} on {when}, so {base.load_words(ctx, load)} goes to "
                       f"{base.load_words(ctx, new_load)} and the target is {target}"),
            derived_from=source, state={},
        )
    held = "the band" if ctx.exercise.load_mode == "band" else base.load_words(ctx, load)
    mismatch = _mismatch(ctx, source, program_sets, load)
    return base.Proposal(
        sets=base.with_load(sets, load),
        rationale=f"Double progression: {when} was {why}, so {held} holds and the target is {target}",
        derived_from=source, state={}, flags=(mismatch,) if mismatch else (),
    )


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
