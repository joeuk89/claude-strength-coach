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
    if not wanted or len(logged) < len(wanted):
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
    newest = judged[-1] if judged else None
    start = rung
    if newest is not None and _hit(newest, newest.prescribed) and rung < len(rungs) - 1:
        rung += 1
    state = {"rung": rung, "through": source.date.isoformat() if source else through}
    name = rungs[rung]["name"]
    if rung > start:
        reason = (f"every set reached its target reps at or under the target RPE on {newest.date.isoformat()}, so "
                  f"up from {rungs[start]['name']} to {name}")
    elif newest is not None and not newest.prescribed:
        reason = f"historical prescription unknown on {newest.date.isoformat()}, so {name} holds"
    elif judged and rung == len(rungs) - 1:
        reason = f"{name} is the top rung, so it holds"
    elif judged:
        reason = f"not every set reached its target on {newest.date.isoformat()}, so {name} holds"
    else:
        reason = f"no new exposure, so {name} holds"
    return base.Proposal(sets=_at(ctx, targets, rung), rationale=f"Assistance ladder: {reason}",
                         derived_from=source, state=state, target_note=_note(ctx, rung))


def override_state(params, state, sets):
    """The state after an approved override: on the rung whose load every overridden working set carries, so the
    coach's switch to that rung stands; an override off the rungs leaves the state as proposed."""
    loads = {s.load for s in base.working(sets)}
    if len(loads) != 1 or None in loads:
        return dict(state)
    [load] = loads
    found = [i for i, rung in enumerate(params["rungs"]) if rung.get("load") is not None
             and abs(rung["load"] - load) < 1e-9]
    return dict(state, rung=found[0]) if len(found) == 1 else dict(state)


def decay(ctx, proposal, days_off):
    """Back one rung per return band past `0-10` from the lower of the stored and the proposed rung, so a climb
    never reaches a return week; the band's set cut and RPE cap still apply."""
    band = base.return_band(days_off)
    stored = min(ctx.state.get("rung", 0), len(ctx.params["rungs"]) - 1)
    rung = max(0, min(stored, proposal.state["rung"]) - base.bands_back(days_off))
    sets = _at(ctx, proposal.sets, rung)
    if band.set_delta:
        sets = base.keep_working(sets, base.return_set_count(proposal, band.set_delta))
    if band.rpe_cap is not None:
        sets = base.rpe_capped(sets, band.rpe_cap)
    return replace(proposal, sets=sets, state=dict(proposal.state, rung=rung), target_note=_note(ctx, rung))
