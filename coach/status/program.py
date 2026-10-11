"""Rotation position and block state from data/state.json (contract C16, C52)."""

from coach import state as state_module
from coach.errors import ValidationError
from coach.status import Section, provider

DELOAD_ATTENTION = ("due", "in_progress")


@provider(id="program", owner="R-26b", order=40)
def program_status(ctx):
    if not state_module.exists(ctx.root):
        return None
    try:
        doc = state_module.load(ctx.root)
    except ValidationError:
        return Section("program", ["data/state.json cannot be read; see the checks above."], {}, "attention")
    rotation, block = doc["rotation"], doc["block"]
    lines, attention = [], False
    if rotation["position"] is not None:
        if rotation["confirmed"]:
            when = f" on {rotation['confirmed_at']}" if rotation["confirmed_at"] else ""
            lines.append(f"Rotation: {rotation['position']}, confirmed{when}.")
        else:
            lines.append(f"Rotation: {rotation['position']}, not confirmed; state it for the athlete to confirm "
                         "before programming.")
            attention = True
    deload = block["deload"]["status"]
    started = f" (block started {block['started']})" if block.get("started") else ""
    lines.append(f"Hard weeks completed: {block['hard_weeks_completed']}{started}; deload {deload.replace('_', ' ')}.")
    if deload in DELOAD_ATTENTION:
        attention = True
    if doc.get("one_off"):
        lines.append("A one-off week is active; see data/state.json.")
    data = {"rotation": rotation, "hard_weeks_completed": block["hard_weeks_completed"], "deload": block["deload"],
            "one_off": doc.get("one_off")}
    return Section("program", lines, data, "attention" if attention else "info")
