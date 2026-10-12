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


def _shape(spec):
    return spec.target_reps, spec.top_reps, spec.rpe


def _groups(program_sets):
    """(first set number, the sets) for each run of working sets asking for the same reps and RPE."""
    found = []
    for number, spec in enumerate(program_sets, 1):
        if found and _shape(found[-1][1][-1]) == _shape(spec):
            found[-1][1].append(spec)
        else:
            found.append((number, [spec]))
    return found


def _range_text(spec):
    if spec.target_reps == spec.top_reps:
        return f"{spec.target_reps}"
    return f"{spec.target_reps}–{spec.top_reps}"


def _target_text(program_sets):
    parts = []
    for _, specs in _groups(program_sets):
        rpe = specs[0].rpe
        parts.append(f"{_range_text(specs[0])} reps" + (f" at RPE {base.number(rpe)}" if rpe is not None else ""))
    return ", then ".join(parts)


def _set_numbers(first, count):
    return f"set {first}" if count == 1 else f"sets {first}–{first + count - 1}"


def _where(ctx, load):
    return "on the band" if ctx.exercise.load_mode == "band" else f"at {base.load_words(ctx, load)}"


def _held_and_easier(ctx, load):
    """What the hold keeps and the easier option the coach reviews, in this load mode's words."""
    if ctx.exercise.load_mode == "band":
        return "the band", "an easier band"
    if ctx.exercise.load_direction < 0:
        return "the load", "more assistance"
    if ctx.exercise.load_mode == "bodyweight" and not load:
        return "the load", "an easier variation"
    return "the load", "a lighter load"


def _mismatch(ctx, source, program_sets, load):
    """A flag when the held load's exposure fell below a set group's range or 2 or more RPE over target, else None.

    A slot of one set group names its location once; a slot of several
    names each short group's sets and logged load.
    """
    logged = base.working(source.sets)[:len(program_sets)]
    groups = _groups(program_sets)
    single = len(groups) == 1
    found = []
    for first, specs in groups:
        got = logged[first - 1:first - 1 + len(specs)]
        bottom = specs[0].target_reps
        if bottom is None or not any(s.reps is not None and s.reps < bottom for s in got):
            continue
        reps = ", ".join(str(s.reps) if s.reps is not None else "?" for s in got)
        where = "" if single else f" on {_set_numbers(first, len(got))} {_where(ctx, base.top_load(got))}"
        found.append(f"{reps} reps{where}, below the program's {_range_text(specs[0])}")
    over = [(got.rpe, program_sets[i].rpe, i) for i, got in enumerate(logged)
            if got.rpe is not None and program_sets[i].rpe is not None
            and got.rpe >= program_sets[i].rpe + MISMATCH_RPE_OVER]
    if over:
        rpe, target, index = max(over)
        where = "" if single else f" on set {index + 1} {_where(ctx, logged[index].load)}"
        found.append(f"RPE {base.number(rpe)}{where} against the target RPE {base.number(target)}")
    if not found:
        return None
    held, easier = _held_and_easier(ctx, load)
    where = f" {_where(ctx, load)}" if single else ""
    message = (f"{ctx.exercise.name}: {source.date.isoformat()} logged {' and '.join(found)}{where}; "
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
    single = len(_groups(program_sets)) == 1
    reached = (f"every working set reached {program_sets[0].top_reps} reps" if single
               else "every working set reached the top of its range")
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
