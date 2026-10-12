"""Rotation position from `coach.pages.header_facts`, the block status line from `coach.block` (contract C16, C38, C43, C52)."""

from coach import block as block_module
from coach import history, pages, program, summaries
from coach import state as state_module
from coach.errors import ValidationError
from coach.status import Section, provider

LIGHT_WEEK_ATTENTION = ("proposed", "agreed")


def _position_words(root, position):
    """The stored position, said as the last session trained when the schedule is a sequence."""
    program_doc = history.load_optional(program, root)
    following = summaries.session_after(program_doc["schedule"] if program_doc else None, position)
    return f"{position} last trained, {following} next" if following else position


@provider(id="program", owner="R-26b", order=40)
def program_status(ctx):
    if not state_module.exists(ctx.root):
        return None
    try:
        doc = state_module.load(ctx.root)
    except ValidationError:
        return Section("program", ["data/state.json cannot be read; see the checks above."], {}, "attention")
    rotation, block = pages.header_facts(ctx.root, ctx.now())["rotation"], doc["block"]
    lines, attention = [], False
    if rotation["position"] is not None:
        position = _position_words(ctx.root, rotation["position"])
        if rotation["confirmed"]:
            confirmed_at = doc["rotation"]["confirmed_at"]
            when = f" on {confirmed_at}" if confirmed_at else ""
            lines.append(f"Rotation: {position}, confirmed{when}.")
        else:
            lines.append(f"Rotation: {position}, not confirmed; state it for the athlete to confirm "
                         "before programming.")
            attention = True
    line = block_module.status_line(ctx.root)
    started = f" (started {block['started']})" if block.get("started") else ""
    lines.append(f"{line or 'Block ' + block['id']}{started}.")
    if block["light_week"]["status"] in LIGHT_WEEK_ATTENTION:
        attention = True
    if doc.get("one_off"):
        lines.append("A one-off week is active; see data/state.json.")
    data = {"rotation": rotation, "hard_weeks_completed": block["hard_weeks_completed"],
            "light_week": block["light_week"], "status_line": line, "one_off": doc.get("one_off")}
    return Section("program", lines, data, "attention" if attention else "info")
