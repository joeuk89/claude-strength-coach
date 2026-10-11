"""The block ledger agrees with the state, the ceiling is in range, and an agreed light week has its overlay (contract C42)."""

import json

from coach import block, dates, decisions, overlay, paths, program
from coach import state as state_module
from coach.checks import Result, check
from coach.errors import ValidationError

_BLOCKS = paths.BLOCKS.as_posix()
_STATE = paths.STATE.as_posix()
_PROGRAM = paths.PROGRAM.as_posix()


@check(id="block_state", owner="R-31")
def block_state(ctx):
    if not block.exists(ctx.root):
        return [Result("skip", f"no {_BLOCKS} yet; the first block close starts it", _BLOCKS)]
    try:
        ledger = block.load(ctx.root)
    except ValidationError as exc:
        return [Result("fail", f"{exc.message}: " + "; ".join(f"{d['path']}: {d['message']}" for d in exc.details),
                       _BLOCKS)]
    if not state_module.exists(ctx.root):
        return [Result("fail", f"{_BLOCKS} exists but {_STATE} does not", _STATE)]
    try:
        state = state_module.load(ctx.root)["block"]
    except ValidationError:
        return [Result("skip", f"{_STATE} cannot be read; see state_schema", _STATE)]
    current = ledger["blocks"][-1]
    newest = block.newest_week(ledger)
    expected = {"id": current["id"], "started": current["started"], "hard_weeks_completed": block.count_of(current)}
    if newest is not None:
        expected["last_closed_week"] = newest.isoformat()
    found = []
    for key, value in expected.items():
        if state[key] != value:
            found.append(Result("fail", f"state.block.{key} is {state[key]!r} but {_BLOCKS} says {value!r}; "
                                        "run python3 -m coach block close again for the newest week", _STATE))
    return found


@check(id="block_config", owner="R-31")
def block_config(ctx):
    path = program.path_for(ctx.root)
    if not path.is_file():
        return [Result("skip", f"no {_PROGRAM} yet", _PROGRAM)]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [Result("skip", f"{_PROGRAM} is not JSON; see program_schema", _PROGRAM)]
    ceiling = ((doc.get("blocks") if isinstance(doc, dict) else None) or {}).get("hard_weeks_ceiling")
    low, high = block.CEILING_RANGE
    if isinstance(ceiling, bool) or not isinstance(ceiling, int) or not low <= ceiling <= high:
        return [Result("fail", f"blocks.hard_weeks_ceiling is {ceiling!r}; it must be a whole number from {low} to "
                               f"{high}", _PROGRAM)]
    return []


@check(id="light_week_overlay", owner="R-31")
def light_week_overlay(ctx):
    if not state_module.exists(ctx.root):
        return [Result("skip", f"no {_STATE} yet", _STATE)]
    try:
        light = state_module.load(ctx.root)["block"]["light_week"]
        docs = overlay.list(ctx.root)
        recorded = decisions.load(ctx.root)
    except ValidationError:
        return [Result("skip", "the state, an overlay or the decisions cannot be read; see their checks", _STATE)]
    found = []
    deloads = [d for d in docs if d["kind"] == "deload"]
    if light["status"] == "agreed" and light["week"]:
        week = light["week"]
        if not any(d["span"]["start"] <= week <= d["span"]["end"] for d in deloads):
            command = block.propose_command(light)
            found.append(Result("warn", f"the agreed {light['type']} light week of {week} has no deload overlay yet; "
                                        f"build it with {command}", _STATE))
    adopted = [dates.parse_date(d["details"]["week"]) for d in recorded["decisions"]
               if d["kind"] == "light_week" and d["outcome"] == "adopted" and d["status"] != "withdrawn"]
    today = ctx.today().isoformat()
    for doc in deloads:
        if doc["span"]["end"] < today:
            continue
        span = dates.Span(dates.parse_date(doc["span"]["start"]), dates.parse_date(doc["span"]["end"]))
        if not any(span.contains(day) for day in adopted):
            found.append(Result("warn", f"deload overlay {doc['id']} has no adopted light-week decision; record it "
                                        "with python3 -m coach block decide --outcome adopted",
                                f"{paths.OVERLAYS_DIR.as_posix()}/{doc['id']}.json"))
    return found
