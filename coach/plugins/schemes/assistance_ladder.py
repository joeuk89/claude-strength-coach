"""Assistance ladder: a bodyweight skill climbed one rung at a time, each rung an assistance amount or a variation."""

from dataclasses import replace
from datetime import date

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "assistance_ladder"
SUMMARY = ("Climbs an ordered list of rungs, assistance amounts or harder variations, one rung after an exposure "
           "with every set at its target reps at or under the target RPE; a return band steps back rungs "
           "instead of cutting load.")
RUNG = {
    "type": "object", "required": ["name"], "additionalProperties": False,
    "properties": {"name": {"type": "string"}, "load": {"type": ["number", "null"], "minimum": 0}},
}
PARAMS = {
    "schema": {
        "type": "object", "required": ["rungs"], "additionalProperties": False,
        "properties": {
            "rungs": {"type": "array", "minItems": 1, "items": RUNG},
            "reps": {"type": ["integer", "null"], "minimum": 1},
            "sets": {"type": ["integer", "null"], "minimum": 1},
            "rpe": {"type": ["number", "null"], "minimum": 1, "maximum": 10},
        },
    },
    "defaults": {"reps": None, "sets": None, "rpe": None},
}
STATE = {
    "schema": {
        "type": "object", "required": ["rung", "through"], "additionalProperties": False,
        "properties": {
            "rung": {"type": "integer", "minimum": 0},
            "through": {"type": ["string", "null"], "pattern": base.DATE_PATTERN},
        },
    },
    "initial": {"rung": 0, "through": None},
}
FLAGS = {}
LOAD_MODES = ("bodyweight", "assisted", "band")
CITES = ("rn:bodyweight-skill-progression.3",)


def _targets(ctx):
    """The prescribed sets before the rung's load: the program's, with the params' reps, set count and RPE."""
    sets = base.expand(ctx.slot.sets)
    params = ctx.params
    if params["sets"]:
        working = base.working(sets)
        template = working[0] if working else base.SetSpec()
        sets = tuple(s for s in sets if not s.working) + (template,) * params["sets"]
    if params["reps"]:
        sets = base.with_reps(sets, params["reps"])
    if params["rpe"] is not None:
        sets = tuple(replace(s, rpe=params["rpe"]) if s.working else s for s in sets)
    return sets


def _hit(exposure, targets):
    """True when every target set was logged at its target reps (the top of a range) at or under its RPE."""
    wanted = base.working(targets)
    logged = [s for s in exposure.sets if s.working]
    if len(logged) < len(wanted):
        return False
    for target, got in zip(wanted, logged):
        if (got.reps or 0) < (target.top_reps or 0):
            return False
        if target.rpe is not None and got.rpe is not None and got.rpe > target.rpe:
            return False
    return True


def _rung_load(ctx, rung):
    load = rung.get("load")
    if load is None and ctx.exercise.load_mode == "bodyweight":
        return 0
    return load


def _note(ctx, index):
    rungs = ctx.params["rungs"]
    return f"Rung {index + 1} of {len(rungs)}: {rungs[index]['name']}"


def _at(ctx, sets, index):
    return base.with_load(sets, _rung_load(ctx, ctx.params["rungs"][index]))


def propose(ctx):
    rungs = ctx.params["rungs"]
    targets = _targets(ctx)
    rung = min(ctx.state.get("rung", 0), len(rungs) - 1)
    through = ctx.state.get("through")
    source = base.baseline(ctx.exposures)
    if through is None:
        judged = [source] if source is not None else []
    else:
        judged = base.usable_oldest_first(ctx.exposures, date.fromisoformat(through))
    start, moved = rung, []
    for exposure in judged:
        if _hit(exposure, targets) and rung < len(rungs) - 1:
            rung += 1
            moved.append(exposure.date.isoformat())
    state = {"rung": rung, "through": source.date.isoformat() if source else through}
    name = rungs[rung]["name"]
    if moved:
        reason = (f"every set reached its target reps at or under the target RPE on {', '.join(moved)}, so up "
                  f"from {rungs[start]['name']} to {name}")
    elif judged and rung == len(rungs) - 1:
        reason = f"{name} is the top rung, so it holds"
    elif judged:
        reason = f"not every set reached its target on {judged[-1].date.isoformat()}, so {name} holds"
    else:
        reason = f"no new exposure, so {name} holds"
    return base.Proposal(sets=_at(ctx, targets, rung), rationale=f"Assistance ladder: {reason}",
                         derived_from=source, state=state, target_note=_note(ctx, rung))


def decay(ctx, proposal, days_off):
    """Back one rung per return band past `0-10`; the band's set cut and RPE cap still apply."""
    band = base.return_band(days_off)
    rung = max(0, proposal.state["rung"] - base.bands_back(days_off))
    sets = _at(ctx, proposal.sets, rung)
    if band.set_delta:
        sets = base.keep_working(sets, base.return_set_count(proposal, band.set_delta))
    if band.rpe_cap is not None:
        sets = base.rpe_capped(sets, band.rpe_cap)
    return replace(proposal, sets=sets, state=dict(proposal.state, rung=rung), target_note=_note(ctx, rung))
