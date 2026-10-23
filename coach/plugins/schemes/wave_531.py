"""5/3/1-style wave: three weeks of rising percentages of a training max, the last wave set a rep-out (+) set.

The percentages, the 90 % training max, the 40/50/60 deload and the
per-wave increments are the published 5/3/1 program's (Wendler), a
program spec rather than research findings. The rep-out set's RPE 9 cap,
the load tolerance that matches a logged session to its wave week and the
rule that a week counts only when its wave sets were logged at their
reps and loads within their caps are coaching heuristics.
"""

import math
from dataclasses import replace

from coach.plugins import base
from coach.stats import load_for

API = 1
KIND = "scheme"
NAME = "wave_531"
SUMMARY = ("Runs three-week waves at 65/75/85, 70/80/90 and 75/85/95 % of a training max with the last wave set a "
           "rep-out (+) set, moves on a week only when that week was trained, raises the training max once a wave "
           "is completed, and deloads at 40/50/60 %.")
WEEKS = {
    1: ((0.65, 5), (0.75, 5), (0.85, 5)),
    2: ((0.70, 3), (0.80, 3), (0.90, 3)),
    3: ((0.75, 5), (0.85, 3), (0.95, 1)),
}
WAVE_SETS = 3
DELOAD = ((0.40, 5), (0.50, 5), (0.60, 5))
LOAD_TOLERANCE = 0.025
DEFAULT_INCREMENTS = {"kg": {"upper": 2.5, "lower": 5}, "lb": {"upper": 5, "lower": 10}}
LOWER_PATTERNS = frozenset({"squat", "hinge", "lunge", "knee_flexion", "knee_extension", "calf_raise",
                            "hip_abduction", "hip_adduction"})
NULLABLE_LOAD = {"type": ["number", "null"], "minimum": 0}
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "training_max": NULLABLE_LOAD,
            "training_max_pct": {"type": "number", "minimum": 0.5, "maximum": 1},
            "increment_upper": NULLABLE_LOAD,
            "increment_lower": NULLABLE_LOAD,
            "region": {"enum": ["upper", "lower", None]},
            "amrap": {"type": "boolean"},
        },
    },
    "defaults": {"training_max": None, "training_max_pct": 0.9, "increment_upper": None, "increment_lower": None,
                 "region": None, "amrap": True},
}
STATE = {
    "schema": {
        "type": "object", "required": ["completed_weeks", "training_max", "through"],
        "additionalProperties": False,
        "properties": {
            "completed_weeks": {"type": "integer", "minimum": 0, "maximum": len(WEEKS) - 1},
            "training_max": {"type": ["number", "null"], "minimum": 0},
            "through": {
                "type": ["object", "null"], "required": ["date", "workout_id"], "additionalProperties": False,
                "properties": {"date": {"type": "string", "pattern": base.DATE_PATTERN},
                               "workout_id": {"type": ["string", "null"]}},
            },
        },
    },
    "initial": {"completed_weeks": 0, "training_max": None, "through": None},
}
FLAGS = {}
LOAD_MODES = base.E1RM_MODES
CITES = ("rn:progression-training-age.4", "rn:progression-training-age.9")


def problems(params, sets):
    """(JSONPath under the slot, message) for set groups the wave cannot place without losing sets."""
    working = [(index, group) for index, group in enumerate(sets) if group.get("type") in base.WORKING_TYPES]
    if not working:
        return [("$.sets", f"wave_531 needs a working set group to hold its {WAVE_SETS} wave sets")]
    index, group = working[0]
    if group.get("count") != WAVE_SETS:
        return [(f"$.sets[{index}].count",
                 f"wave_531 puts its {WAVE_SETS} wave sets in place of the first working set group, so that group's "
                 f"count must be {WAVE_SETS}; give back-off sets their own later group")]
    return []


def _increment(ctx):
    region = ctx.params["region"] or ("lower" if ctx.exercise.pattern in LOWER_PATTERNS else "upper")
    chosen = ctx.params[f"increment_{region}"]
    if chosen is None:
        chosen = DEFAULT_INCREMENTS[ctx.unit][region]
    return region, chosen


def _rep_out_cap(ctx):
    return base.REP_OUT_RPE_CAP if ctx.params["amrap"] else None


def _sets(ctx, training_max, scheme, cap, light=False, backoff_factor=1):
    """The program's set groups with the first working group replaced by the wave sets, the last of them a rep-out
    set capped at `cap` (none when `cap` is None), and every later working group kept as back-off sets.

    A back-off group with an RPE is loaded from the e1RM at its reps and RPE, times `backoff_factor`, so its load
    and its effort target agree; one without an RPE, or with no e1RM, takes the first wave set's load. When
    `light`, every back-off takes the first wave set's load and no RPE.
    """
    wave = [base.SetSpec(type="normal", reps=reps, load=round(training_max * pct, 4)) for pct, reps in scheme]
    if cap is not None:
        wave[-1] = replace(wave[-1], rep_out=True, rpe=cap)
    found, placed = [], False
    for group in ctx.slot.sets:
        sets = base.expand((group,))
        if not sets[0].working:
            found += sets
        elif not placed:
            found += wave
            placed = True
        elif light:
            found += [replace(s, load=wave[0].load, rpe=None) for s in sets]
        else:
            found += [replace(s, load=_backoff_load(ctx, s, wave[0].load, backoff_factor)) for s in sets]
    return tuple(found)


def _from_e1rm(ctx, spec):
    return spec.rpe is not None and spec.target_reps is not None and ctx.e1rm is not None


def _backoff_load(ctx, spec, first_load, factor):
    if not _from_e1rm(ctx, spec):
        return first_load
    load = load_for(ctx.e1rm, spec.target_reps, spec.rpe) * factor
    step = ctx.exercise.increment
    return math.floor(load / step + 1e-9) * step if step else round(load, 4)


def _backoff_words(ctx, sets):
    backoffs = base.working(sets)[WAVE_SETS:]
    if not backoffs:
        return None
    count, from_e1rm = len(backoffs), sum(1 for s in backoffs if _from_e1rm(ctx, s))
    first = "at the first wave set's load"
    if not from_e1rm:
        return f"{count} back-off set{'s' if count > 1 else ''} {first}"
    loaded = f"loaded from the e1RM of {base.number(ctx.e1rm)} at their reps and RPE"
    if from_e1rm == count:
        return f"{count} back-off set{'s' if count > 1 else ''} {loaded}"
    return f"{count} back-off sets: {from_e1rm} {loaded} and {count - from_e1rm} {first}"


def _marker(exposure):
    return {"date": exposure.date.isoformat(), "workout_id": exposure.workout_id}


def _after(exposure, through):
    if through is None:
        return True
    day = exposure.date.isoformat()
    if day != through["date"]:
        return day > through["date"]
    return through["workout_id"] is not None and exposure.workout_id > through["workout_id"]


def _tolerance(ctx, training_max):
    return max(ctx.exercise.increment or 0, LOAD_TOLERANCE * training_max)


def _return_work(exposure):
    return exposure.decayed or exposure.week_kind == "return"


def _trains_week(ctx, exposure, week, training_max):
    """True when the exposure's prescription was this wave week's sets at this training max."""
    if _return_work(exposure) or exposure.week_kind == "deload":
        return False
    main = base.working(exposure.prescribed)[:WAVE_SETS]
    if len(main) < WAVE_SETS:
        return False
    tolerance = _tolerance(ctx, training_max)
    return all(spec.reps == reps and spec.load is not None and abs(spec.load - training_max * pct) <= tolerance
               for spec, (pct, reps) in zip(main, WEEKS[week]))


def _shortfalls(ctx, exposure, training_max):
    """What kept a matching exposure's wave sets from counting: a short set (reps, or a load lighter than its
    prescription past the matching tolerance), a passed RPE cap, or missing sets. A heavier or unrecorded load is
    no shortfall."""
    main = base.working(exposure.prescribed)[:WAVE_SETS]
    logged = base.working(exposure.sets)[:WAVE_SETS]
    tolerance = _tolerance(ctx, training_max)
    short = []
    for number, (spec, got) in enumerate(zip(main, logged), start=1):
        name = f"wave set {number} ({spec.reps}{'+' if spec.rep_out else ''})"
        if (got.reps or 0) < spec.reps:
            short.append(f"{name} logged {got.reps or 0} reps")
        elif got.load is not None and spec.load - got.load > tolerance:
            short.append(f"{name} logged at {base.load_words(ctx, got.load)}, under its prescribed "
                         f"{base.load_words(ctx, spec.load)}")
        elif spec.rpe is not None and got.rpe is not None and got.rpe > spec.rpe:
            short.append(f"{name} logged RPE {base.number(got.rpe)}, past its cap of {base.number(spec.rpe)}")
    missing = f"{len(logged)} of its {WAVE_SETS} wave sets logged" if len(logged) < WAVE_SETS else None
    if short:
        return "review", "; ".join(short + ([missing] if missing else []))
    if missing:
        return "incomplete", missing
    return None, None


def _judge(ctx, completed, training_max, through):
    """Move the wave on through the usable exposures after `through`, oldest first: each that trained the next wave
    week with every wave set at its reps and load within its cap completes that week, and a completed third week
    raises the training max once. Returns (completed, training max, through, words, flags)."""
    words, flags = [], []
    unmatched = None
    for exposure in reversed(ctx.exposures):
        if not exposure.usable or not _after(exposure, through):
            continue
        through = _marker(exposure)
        week = completed + 1
        if exposure.week_kind == "deload":
            continue
        if not _trains_week(ctx, exposure, week, training_max):
            unmatched = exposure
            continue
        kind, detail = _shortfalls(ctx, exposure, training_max)
        day = exposure.date.isoformat()
        if kind == "incomplete":
            words.append(f"week {week} on {day} had {detail}, so it repeats")
            flags.append(base.flag(ctx, "incomplete_exposure", (
                f"{ctx.exercise.name}: {detail} on {day}, so wave week {week} repeats and the training max holds "
                "(a coaching heuristic); confirm whether the missing sets were skipped or failed")))
            continue
        if kind == "review":
            words.append(f"week {week} on {day} fell short ({detail}), so it repeats and the training max holds "
                         "for review")
            flags.append(base.flag(ctx, "wave_review", (
                f"{ctx.exercise.name}: wave week {week} on {day}: {detail}. The week repeats at the training max of "
                f"{base.load_words(ctx, training_max)} and no raise is earned (a coaching heuristic); review the "
                "training max with the athlete")))
            continue
        completed += 1
        if completed < len(WEEKS):
            words.append(f"week {week} was completed on {day}")
            continue
        region, step = _increment(ctx)
        training_max = round(training_max + step, 2)
        completed = 0
        words.append(f"the wave was completed on {day}, so a new wave starts with the training max raised by the "
                     f"{region}-body increment of {base.number(step)}")
    if not words and through is not None:
        week = completed + 1
        if unmatched is not None and _return_work(unmatched):
            words.append(f"week {week} again after the return week on {unmatched.date.isoformat()}")
        elif unmatched is not None:
            words.append(f"week {week} again: the session on {unmatched.date.isoformat()} was not prescribed "
                         f"week {week}'s wave sets at this training max")
        else:
            words.append(f"week {week} again, as no session since {through['date']} has trained it")
    return completed, training_max, through, words, flags


def _hold(ctx, source):
    load = source.top_load if source else base.start_load(ctx)
    why = "no e1RM in the last 42 days" if ctx.exercise.e1rm_supported else base.NO_E1RM_REASON
    return base.Proposal(
        sets=base.with_load(base.expand(ctx.slot.sets), load),
        rationale=f"5/3/1 wave: no training max and {why}, so the program's sets hold at {base.load_words(ctx, load)}",
        derived_from=source, state=dict(ctx.state))


def propose(ctx):
    source = base.baseline(ctx.exposures)
    training_max = ctx.state.get("training_max")
    completed = ctx.state.get("completed_weeks", 0)
    through = ctx.state.get("through")
    flags = ()
    if training_max is None:
        if ctx.params["training_max"] is not None:
            training_max = ctx.params["training_max"]
            words = [f"the training max starts at the program's {base.load_words(ctx, training_max)}"]
        elif ctx.e1rm is not None:
            training_max = round(ctx.e1rm * ctx.params["training_max_pct"], 2)
            words = [f"the training max starts at {base.number(ctx.params['training_max_pct'] * 100)} % of the "
                     f"e1RM of {base.number(ctx.e1rm)}"]
        else:
            return _hold(ctx, source)
        completed = 0
        newest = base.newest(ctx.exposures)
        through = _marker(newest) if newest is not None else None
    else:
        completed, training_max, through, words, flags = _judge(ctx, completed, training_max, through)
    week = completed + 1
    cap = _rep_out_cap(ctx)
    sets = _sets(ctx, training_max, WEEKS[week], cap)
    percents = "/".join(base.number(pct * 100) for pct, _ in WEEKS[week])
    lead = (f"5/3/1 wave: week {week} of 3 at {percents} % of the training max of "
            f"{base.load_words(ctx, training_max)}")
    backoffs = _backoff_words(ctx, sets)
    if backoffs:
        words.append(backoffs)
    if week == len(WEEKS):
        words.append("the program's deload, or the next wave, follows")
    return base.Proposal(
        sets=sets,
        rationale=", ".join([lead] + words),
        derived_from=source,
        state={"completed_weeks": completed, "training_max": training_max, "through": through},
        flags=tuple(flags),
        target_note=f"Wave week {week} of 3",
    )


def _maxes(ctx, proposal):
    return [m for m in (ctx.state.get("training_max"), proposal.state.get("training_max")) if m is not None]


def deload(ctx, proposal):
    """40/50/60 % × 5 of the training max the wave just ran on, before any raise for the next wave, with no rep-out
    set; a deload never moves the wave on."""
    maxes = _maxes(ctx, proposal)
    if not maxes:
        return base.standard_deload(proposal, **base.STANDARD_DELOAD)
    training_max = min(maxes)
    week = proposal.state["completed_weeks"] + 1
    resumes = f"the wave resumes at week {week} of 3 after it"
    raised = proposal.state["training_max"]
    if raised is not None and raised > training_max:
        resumes += f" with the training max raised to {base.load_words(ctx, raised)}"
    sets = _sets(ctx, training_max, DELOAD, None, light=True)
    words = [f"5/3/1 deload: 40/50/60 % of the training max of {base.load_words(ctx, training_max)}, 5 reps each "
             f"and no + set", resumes]
    backoffs = _backoff_words(ctx, sets)
    if backoffs:
        words.append(backoffs)
    return replace(proposal, sets=sets, load_cut=True, state=dict(ctx.state), rationale=", ".join(words),
                   target_note="Deload week: 40/50/60 % of the training max, no + set")


def decay(ctx, proposal, days_off):
    """A temporary return week: the week's percentages of the lower of the stored and the proposed training max
    times the band's load factor, with no rep-out set, the band's set cut and RPE cap, and no load past the
    derived-from load times that factor. The stored training max is kept, so the next ordinary week resumes it.
    A kept override carries no wave state, so it takes the standard return band."""
    maxes = _maxes(ctx, proposal)
    if not maxes or "completed_weeks" not in proposal.state:
        return base.default_decay(ctx, proposal, days_off)
    band = base.return_band(days_off)
    training_max = min(maxes)
    lowered = round(training_max * band.load_factor, 2)
    week = proposal.state["completed_weeks"] + 1
    sets = _sets(ctx, lowered, WEEKS[week], None, backoff_factor=band.load_factor)
    if band.set_delta:
        own = base.own_exposure(ctx, proposal.derived_from)
        sets = base.keep_working(sets, base.return_set_count(replace(proposal, sets=sets), band.set_delta, own))
    source = proposal.derived_from
    if source is not None and source.top_load is not None:
        ceiling = round(source.top_load * band.load_factor, 4)
        sets = tuple(replace(s, load=min(s.load, ceiling)) if s.working and s.load is not None else s for s in sets)
    if band.rpe_cap is not None:
        sets = base.rpe_capped(sets, band.rpe_cap)
    rationale = (f"{proposal.rationale.rstrip('. ')}, taken as a return week at "
                 f"{base.number(band.load_factor * 100)} % of the training max of "
                 f"{base.load_words(ctx, training_max)} with no + set, and the next ordinary week resumes the training "
                 f"max of {base.load_words(ctx, proposal.state['training_max'])}")
    return replace(proposal, sets=sets, load_cut=True, rationale=rationale,
                   target_note=(f"Wave week {week} of 3, return week at {base.number(band.load_factor * 100)} % of "
                                "the training max: no + set"))
