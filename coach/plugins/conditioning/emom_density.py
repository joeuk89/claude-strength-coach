"""EMOM density: exercises take turns each minute; reps, then minutes, rise while the session RPE stays at target."""

from coach.plugins import base

API = 1
KIND = "conditioning"
NAME = "emom_density"
SUMMARY = ("Every minute on the minute with the exercises taking turns: at or under the target session RPE the next "
           "exercise below its cap gains a rep, then minutes rise; the steps are a coaching heuristic.")
_COUNTS = {"type": "object", "additionalProperties": {"type": "integer", "minimum": 1}}
_PRESCRIPTION = {
    "type": "object", "required": ["minutes", "reps", "turn"], "additionalProperties": False,
    "properties": {"minutes": {"type": "integer", "minimum": 1}, "reps": _COUNTS,
                   "turn": {"type": "integer", "minimum": 0}},
}
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "minutes": {"type": "integer", "minimum": 1},
            "minutes_cap": {"type": "integer", "minimum": 1},
            "minutes_step": {"type": "integer", "minimum": 1},
            "reps": _COUNTS,
            "reps_cap": _COUNTS,
            "rpe_target": {"type": "number", "minimum": 1, "maximum": 10},
        },
    },
    "defaults": {"minutes": 10, "minutes_cap": 20, "minutes_step": 2, "reps": {}, "reps_cap": {}, "rpe_target": 7},
}
STATE = {
    "schema": {
        "type": "object", "required": ["current", "previous"], "additionalProperties": False,
        "properties": {"current": dict(_PRESCRIPTION, type=["object", "null"]),
                       "previous": {"type": "array", "items": _PRESCRIPTION}},
    },
    "initial": {"current": None, "previous": []},
}
FLAGS = {}
CITES = ()


def problems(params, session):
    """What PARAMS cannot say: reps for every exercise, caps at or above them, a minute for each exercise."""
    ids = [e["exercise_id"] for e in session["exercises"]]
    found = []
    missing = [i for i in ids if i not in params["reps"]]
    if missing:
        found.append(("$.reps", f"give reps for {', '.join(missing)}"))
    for key in ("reps", "reps_cap"):
        extra = sorted(set(params[key]) - set(ids))
        if extra:
            found.append((f"$.{key}", f"{', '.join(extra)} is not an exercise of this session"))
    low = [i for i in ids if i in params["reps_cap"] and params["reps_cap"][i] < params["reps"].get(i, 0)]
    if low:
        found.append(("$.reps_cap", f"the cap is below the starting reps for {', '.join(low)}"))
    if params["minutes"] > params["minutes_cap"]:
        found.append(("$.minutes", f"{params['minutes']} is above minutes_cap {params['minutes_cap']}"))
    if params["minutes"] < len(ids):
        found.append(("$.minutes", f"{len(ids)} exercises take turns, so the EMOM needs at least {len(ids)} minutes"))
    return found


def _start(ctx):
    return {"minutes": ctx.params["minutes"],
            "reps": {e.id: ctx.params["reps"][e.id] for e in ctx.exercises}, "turn": 0}


def _fits(ctx, prescription):
    return prescription is not None and set(prescription["reps"]) == {e.id for e in ctx.exercises}


def _cap(ctx, exercise_id):
    return ctx.params["reps_cap"].get(exercise_id, ctx.params["reps"][exercise_id])


def _next(ctx, current):
    """(the next prescription up, what changed), or None at every cap."""
    count = len(ctx.exercises)
    for offset in range(count):
        index = (current["turn"] + offset) % count
        exercise = ctx.exercises[index]
        before = current["reps"][exercise.id]
        if before < _cap(ctx, exercise.id):
            reps = dict(current["reps"], **{exercise.id: before + 1})
            return (dict(current, reps=reps, turn=(index + 1) % count),
                    f"{exercise.name} {before} → {before + 1} reps a minute")
    minutes, cap = current["minutes"], ctx.params["minutes_cap"]
    if minutes < cap:
        after = min(minutes + ctx.params["minutes_step"], cap)
        return dict(current, minutes=after), f"every exercise at its rep cap, so {minutes} → {after} min"
    return None


def _proposal(ctx, state, rationale, flags=()):
    current = state["current"]
    count = len(ctx.exercises)
    lines = {}
    for index, exercise in enumerate(ctx.exercises):
        owned = len(range(index, current["minutes"], count))
        lines[exercise.id] = (base.work_set(exercise, current["reps"][exercise.id]),) * owned
    order = ", ".join(e.name for e in ctx.exercises)
    focus = f"EMOM {current['minutes']} min, one exercise per minute in turn ({order}). {base.RPE_LOG_HINT}"
    return base.ConditioningProposal(lines=lines, focus=focus, rationale=rationale, state=state, flags=tuple(flags))


def _words(ctx, current):
    reps = " and ".join(f"{current['reps'][e.id]} {e.name}" for e in ctx.exercises)
    return f"EMOM {current['minutes']} min at {reps} a minute"


def propose(ctx):
    stored = ctx.state["current"]
    if not _fits(ctx, stored):
        state = {"current": _start(ctx), "previous": []}
        why = "no prescription yet" if stored is None else "the session's exercises changed"
        return _proposal(ctx, state, f"{why}, so the params' start: {_words(ctx, state['current'])}")
    verdict, said, flags = base.density_verdict(ctx, ctx.params["rpe_target"])
    state = {"current": stored, "previous": list(ctx.state["previous"])}
    if verdict == "up":
        found = _next(ctx, stored)
        if found is None:
            return _proposal(ctx, state, f"{said}, but every rep and the minutes are at their caps, so it holds "
                                         f"({base.AT_CAP}): {_words(ctx, stored)}")
        prescription, change = found
        state = base.stepped(state, prescription)
        return _proposal(ctx, state, f"{said}, so one step up ({base.HEURISTIC}): {change}, "
                                     f"{_words(ctx, prescription)}")
    if verdict == "back":
        back = base.stepped_back(state)
        if back is None:
            return _proposal(ctx, state, f"{said}, already at the start, so it holds: {_words(ctx, stored)}")
        return _proposal(ctx, back, f"{said}, so one step back ({base.HEURISTIC}): {_words(ctx, back['current'])}")
    return _proposal(ctx, state, f"{said}, so it holds ({base.HEURISTIC}): {_words(ctx, stored)}", flags)


def decay(ctx, proposal, days_off):
    stored = ctx.state if _fits(ctx, ctx.state["current"]) else {"current": _start(ctx), "previous": []}
    state, words = base.density_decay(stored, _start(ctx), days_off)
    return _proposal(ctx, state, f"{words} ({base.HEURISTIC}): {_words(ctx, state['current'])}", proposal.flags)
