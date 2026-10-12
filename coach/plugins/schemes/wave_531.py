"""5/3/1-style wave: three weeks of rising percentages of a training max, the last set as many reps as possible.

The percentages, the 90 % training max, the 40/50/60 deload and the
per-wave increments are the published 5/3/1 program's (Wendler), a
program spec rather than research findings.
"""

from dataclasses import replace
from datetime import date

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "wave_531"
SUMMARY = ("Runs three-week waves at 65/75/85, 70/80/90 and 75/85/95 % of a training max with the last set as "
           "many reps as possible, then raises the training max for the next wave; its deload is 40/50/60 %.")
WEEKS = {
    1: ((0.65, 5), (0.75, 5), (0.85, 5)),
    2: ((0.70, 3), (0.80, 3), (0.90, 3)),
    3: ((0.75, 5), (0.85, 3), (0.95, 1)),
}
DELOAD = ((0.40, 5), (0.50, 5), (0.60, 5))
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
        "type": "object", "required": ["wave_week", "training_max", "proposed_for", "proposed_on"],
        "additionalProperties": False,
        "properties": {
            "wave_week": {"type": "integer", "minimum": 0, "maximum": 3},
            "training_max": {"type": ["number", "null"], "minimum": 0},
            "proposed_for": {"type": ["string", "null"], "pattern": base.DATE_PATTERN},
            "proposed_on": {"type": ["string", "null"], "pattern": base.DATE_PATTERN},
        },
    },
    "initial": {"wave_week": 0, "training_max": None, "proposed_for": None, "proposed_on": None},
}
FLAGS = {}
LOAD_MODES = base.E1RM_MODES
CITES = ("rn:progression-training-age.4", "rn:progression-training-age.9")


def _increment(ctx):
    region = ctx.params["region"] or ("lower" if ctx.exercise.pattern in LOWER_PATTERNS else "upper")
    chosen = ctx.params[f"increment_{region}"]
    if chosen is None:
        chosen = DEFAULT_INCREMENTS[ctx.unit][region]
    return region, chosen


def _sets(ctx, training_max, scheme, amrap):
    warmups = tuple(s for s in base.expand(ctx.slot.sets) if not s.working)
    found = [base.SetSpec(type="normal", reps=reps, load=round(training_max * pct, 4)) for pct, reps in scheme]
    if amrap:
        found[-1] = replace(found[-1], type="failure")
    return warmups + tuple(found)


def _repeats(ctx):
    """True when this proposal repeats the stored wave week: any run but a weekly one, a later session of the same
    run, or a weekly run again over a week already proposed. Session dates alone can't tell, because a sequence
    or calendar schedule moves a session's weekday from week to week."""
    if ctx.week_kind != "weekly" or ctx.state.get("proposed_on") == ctx.today.isoformat():
        return True
    last = ctx.state.get("proposed_for")
    return last is not None and ctx.session_date <= date.fromisoformat(last)


def _hold(ctx, source):
    load = source.top_load if source else base.start_load(ctx)
    why = "no e1RM in the last 42 days" if ctx.exercise.e1rm_supported else base.NO_E1RM_REASON
    return base.Proposal(
        sets=base.with_load(base.expand(ctx.slot.sets), load),
        rationale=f"5/3/1 wave: no training max and {why}, so the program's sets hold at {base.load_words(ctx, load)}",
        derived_from=source, state=dict(ctx.state))


def propose(ctx):
    source = base.baseline(ctx.exposures)
    week = ctx.state.get("wave_week", 0)
    training_max = ctx.state.get("training_max")
    words = []
    proposed_for = ctx.session_date.isoformat()
    if training_max is None:
        if ctx.params["training_max"] is not None:
            training_max = ctx.params["training_max"]
            words.append(f"the training max starts at the program's {base.load_words(ctx, training_max)}")
        elif ctx.e1rm is not None:
            training_max = round(ctx.e1rm * ctx.params["training_max_pct"], 2)
            words.append(f"the training max starts at {base.number(ctx.params['training_max_pct'] * 100)} % of the "
                         f"e1RM of {base.number(ctx.e1rm)}")
        else:
            return _hold(ctx, source)
        week = 0
    if _repeats(ctx) and week:
        words.append("proposed again in the same week")
        last = ctx.state.get("proposed_for")
        proposed_for = max(last, proposed_for) if last else proposed_for
    elif week >= len(WEEKS):
        region, step = _increment(ctx)
        training_max = round(training_max + step, 2)
        week = 1
        words.append(f"a new wave, with the training max raised by the {region}-body increment of "
                     f"{base.number(step)}")
    else:
        week += 1
    percents = "/".join(base.number(pct * 100) for pct, _ in WEEKS[week])
    lead = (f"5/3/1 wave: week {week} of 3 at {percents} % of the training max of "
            f"{base.load_words(ctx, training_max)}")
    if week == len(WEEKS):
        words.append("the program's deload, or the next wave, follows")
    amrap = ctx.params["amrap"]
    return base.Proposal(
        sets=_sets(ctx, training_max, WEEKS[week], amrap),
        rationale=", ".join([lead] + words),
        derived_from=source,
        state={"wave_week": week, "training_max": training_max, "proposed_for": proposed_for,
               "proposed_on": ctx.today.isoformat()},
        target_note=f"Wave week {week} of 3" + (": last set as many reps as possible" if amrap else ""),
    )


def deload(ctx, proposal):
    """40/50/60 % of the training max the wave just ran on, before any raise for the next wave."""
    maxes = [m for m in (ctx.state.get("training_max"), proposal.state.get("training_max")) if m is not None]
    if not maxes:
        return base.standard_deload(proposal, **base.STANDARD_DELOAD)
    training_max = min(maxes)
    return replace(proposal, sets=_sets(ctx, training_max, DELOAD, False), round_down=True,
                   target_note="Deload week: 40/50/60 % of the training max, no set to failure")


def decay(ctx, proposal, days_off):
    """The lower of the stored and the proposed training max falls by the band's load factor, so a wave's raise
    never reaches a return week; the band's set cut and RPE cap apply, and no load passes the derived-from load
    times that factor."""
    maxes = [m for m in (ctx.state.get("training_max"), proposal.state.get("training_max")) if m is not None]
    if not maxes:
        return base.default_decay(ctx, proposal, days_off)
    training_max = min(maxes)
    band = base.return_band(days_off)
    lowered = round(training_max * band.load_factor, 2)
    week = proposal.state["wave_week"] or 1
    sets = _sets(ctx, lowered, WEEKS[week], False)
    if band.set_delta:
        sets = base.keep_working(sets, base.return_set_count(replace(proposal, sets=sets), band.set_delta))
    source = proposal.derived_from
    if source is not None and source.top_load is not None:
        ceiling = round(source.top_load * band.load_factor, 4)
        sets = tuple(replace(s, load=min(s.load, ceiling)) if s.working and s.load is not None else s for s in sets)
    if band.rpe_cap is not None:
        sets = base.rpe_capped(sets, band.rpe_cap)
    return replace(proposal, sets=sets, state=dict(proposal.state, training_max=lowered), round_down=True,
                   target_note=f"Wave week {week} of 3, return week: no set to failure")
