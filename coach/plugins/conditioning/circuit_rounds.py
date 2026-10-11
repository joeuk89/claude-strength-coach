"""Circuit rounds: fixed reps per exercise; a round is added while the session RPE and finish time stay in bounds."""

from coach.plugins import base

API = 1
KIND = "conditioning"
NAME = "circuit_rounds"
SUMMARY = ("A circuit of fixed reps against a time cap: at or under the target session RPE and inside the cap it "
           "adds a round, over either it steps back one; the steps are a coaching heuristic.")
_COUNTS = {"type": "object", "additionalProperties": {"type": "integer", "minimum": 1}}
_PRESCRIPTION = {
    "type": "object", "required": ["rounds"], "additionalProperties": False,
    "properties": {"rounds": {"type": "integer", "minimum": 1}},
}
PARAMS = {
    "schema": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "rounds": {"type": "integer", "minimum": 1},
            "rounds_cap": {"type": "integer", "minimum": 1},
            "time_cap_minutes": {"type": "number", "minimum": 1},
            "reps": _COUNTS,
            "rpe_target": {"type": "number", "minimum": 1, "maximum": 10},
        },
    },
    "defaults": {"rounds": 3, "rounds_cap": 6, "time_cap_minutes": 20, "reps": {}, "rpe_target": 7},
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
    """What PARAMS cannot say: reps for every exercise and a cap at or above the starting rounds."""
    ids = [e["exercise_id"] for e in session["exercises"]]
    found = []
    missing = [i for i in ids if i not in params["reps"]]
    if missing:
        found.append(("$.reps", f"give reps for {', '.join(missing)}"))
    extra = sorted(set(params["reps"]) - set(ids))
    if extra:
        found.append(("$.reps", f"{', '.join(extra)} is not an exercise of this session"))
    if params["rounds"] > params["rounds_cap"]:
        found.append(("$.rounds", f"{params['rounds']} is above rounds_cap {params['rounds_cap']}"))
    return found


def _start(ctx):
    return {"rounds": ctx.params["rounds"]}


def _proposal(ctx, state, rationale, flags=()):
    rounds = state["current"]["rounds"]
    lines = {e.id: (base.work_set(e, ctx.params["reps"][e.id]),) * rounds for e in ctx.exercises}
    order = ", ".join(e.name for e in ctx.exercises)
    focus = (f"Circuit, {rounds} rounds of {order} inside a {base.number(ctx.params['time_cap_minutes'])} min cap. "
             f"{base.RPE_LOG_HINT}")
    return base.ConditioningProposal(lines=lines, focus=focus, rationale=rationale, state=state, flags=tuple(flags))


def propose(ctx):
    stored = ctx.state["current"]
    if stored is None:
        state = {"current": _start(ctx), "previous": []}
        return _proposal(ctx, state, f"no prescription yet, so the params' start: {state['current']['rounds']} rounds")
    cap = ctx.params["time_cap_minutes"]
    verdict, said, flags = base.density_verdict(ctx, ctx.params["rpe_target"], cap)
    state = {"current": stored, "previous": list(ctx.state["previous"])}
    rounds = stored["rounds"]
    if verdict == "up":
        if rounds >= ctx.params["rounds_cap"]:
            return _proposal(ctx, state, f"{said}, but the rounds are at their cap, so it holds ({base.AT_CAP}): "
                                         f"{rounds} rounds")
        state = base.stepped(state, {"rounds": rounds + 1})
        return _proposal(ctx, state, f"{said}, so one round more ({base.HEURISTIC}): {rounds} → {rounds + 1} rounds")
    if verdict == "back":
        back = base.stepped_back(state)
        if back is None:
            return _proposal(ctx, state, f"{said}, already at the start, so it holds: {rounds} rounds")
        return _proposal(ctx, back, f"{said}, so one step back ({base.HEURISTIC}): {back['current']['rounds']} rounds")
    return _proposal(ctx, state, f"{said}, so it holds ({base.HEURISTIC}): {rounds} rounds", flags)


def decay(ctx, proposal, days_off):
    stored = ctx.state if ctx.state["current"] is not None else {"current": _start(ctx), "previous": []}
    state, words = base.density_decay(stored, _start(ctx), days_off)
    return _proposal(ctx, state, f"{words} ({base.HEURISTIC}): {state['current']['rounds']} rounds", proposal.flags)
