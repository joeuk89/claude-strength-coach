"""RPE-anchored: one top set loaded from the e1RM at a target RPE, then back-off sets at a share of its load."""

import math
from dataclasses import replace

from coach.plugins import base
from coach.stats import e1rm, load_for

API = 1
KIND = "scheme"
NAME = "rpe_anchored"
SUMMARY = ("Loads one top set from the e1RM at its target reps and RPE, with the newest logged top set "
           "recalibrating the e1RM, then puts the back-off sets at a share of the top set's load.")
NULLABLE_COUNT = {"type": ["integer", "null"], "minimum": 1}
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "top_reps": NULLABLE_COUNT,
            "top_rpe": {"type": ["number", "null"], "minimum": 5, "maximum": 10},
            "backoff_sets": {"type": ["integer", "null"], "minimum": 0},
            "backoff_reps": NULLABLE_COUNT,
            "backoff_pct": {"type": "number", "minimum": 0.5, "maximum": 1},
        },
    },
    "defaults": {"top_reps": None, "top_rpe": None, "backoff_sets": None, "backoff_reps": None, "backoff_pct": 0.9},
}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
LOAD_MODES = base.E1RM_MODES
CITES = ("rn:progression-training-age.6", "rn:autoregulation.1")


def _shape(ctx):
    """(warm-ups, top SetSpec, back-off count, back-off reps): params first, else the program's set groups."""
    sets = base.expand(ctx.slot.sets)
    warmups = tuple(s for s in sets if not s.working)
    program_working = base.working(sets)
    first = program_working[0] if program_working else base.SetSpec()
    params = ctx.params
    top_reps = params["top_reps"] or first.target_reps
    top_rpe = params["top_rpe"] if params["top_rpe"] is not None else first.rpe
    count = params["backoff_sets"] if params["backoff_sets"] is not None else max(0, len(program_working) - 1)
    groups = [g for g in ctx.slot.sets if (g.get("type") or "normal") in base.WORKING_TYPES]
    program_backoff_reps = base.SetSpec.from_dict(groups[1]).target_reps if len(groups) > 1 else None
    backoff_reps = params["backoff_reps"] or program_backoff_reps or top_reps
    top = base.SetSpec(type="normal", reps=top_reps, rpe=top_rpe)
    return warmups, top, count, backoff_reps


def _calibration(ctx, source):
    """(e1RM, words) from the newest logged top set with reps and an RPE, else the 42-day best, else (None, None)."""
    if source is not None:
        logged = [s for s in source.sets if s.working and s.load is not None and s.reps]
        if logged:
            top = max(logged, key=lambda s: s.load)
            value = e1rm(top.load, top.reps, top.rpe) if top.rpe is not None else None
            if value is not None:
                return value, (f"the e1RM of {base.number(value)} from the top set of {source.date.isoformat()} "
                               f"({base.load_words(ctx, top.load)} × {top.reps} at RPE {base.number(top.rpe)})")
    if ctx.e1rm is not None:
        return ctx.e1rm, f"the best e1RM of the last 42 days, {base.number(ctx.e1rm)}"
    return None, None


def _floored(load, step):
    """Floored to the increment, so the back-offs are a share of the load the top set will carry."""
    if not step:
        return load
    return math.floor(load / step + 1e-9) * step


def propose(ctx):
    source = base.baseline(ctx.exposures)
    warmups, top, count, backoff_reps = _shape(ctx)
    pct = ctx.params["backoff_pct"]
    value, words = _calibration(ctx, source)
    if value is None or top.reps is None or top.rpe is None:
        load = source.top_load if source else base.start_load(ctx)
        why = "no e1RM in the last 42 days" if value is None else "no top-set reps or RPE target"
        rationale = f"RPE-anchored: {why}, so the top set holds at {base.load_words(ctx, load)}"
        round_down = False
    else:
        load = _floored(load_for(value, top.reps, top.rpe), ctx.exercise.increment)
        rationale = (f"RPE-anchored: top set {top.reps} at RPE {base.number(top.rpe)} from {words}, then "
                     f"{count}×{backoff_reps} at {base.number(pct * 100)} % of it")
        round_down = True
    backoff = round(load * pct, 4) if load is not None else None
    sets = warmups + (replace(top, load=load),) + (base.SetSpec(type="normal", reps=backoff_reps, load=backoff),) * count
    return base.Proposal(sets=sets, rationale=rationale, derived_from=source, state={}, round_down=round_down)


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
