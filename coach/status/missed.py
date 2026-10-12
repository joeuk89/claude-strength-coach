"""Planned sessions left unlogged and unrecorded, with the recovery the program's rule offers today (C37, C52)."""

from coach import missed, program, render
from coach.errors import ValidationError
from coach.status import MAX_LINES, Section, provider


def _option(found, today):
    if found is None or found["reason"] is not None:
        why = found["reason"] if found else "no overlay is in force that day"
        return f"no missed-day rule applies ({why}): move it, drop it or reshuffle the week"
    rule = f"rule {found['rule_id']}"
    if found["kind"] == "skip":
        return f"{rule} skips it, so record the miss"
    when = render.day_label(found["to"])
    if found["to"] == today.isoformat():
        when = f"today, {when}"
    if found["kind"] == "shift":
        return f"{rule} moves it to {when}"
    return f"{rule} adds its work to {when} {found['to_title']}"


def _line(row, found, today):
    return (f"{render.day_label(row['date'])} {row['title']} is not logged; {_option(found, today)}. Log it if it was "
            f"trained, else settle it with /program-week (python3 -m coach missed plan --session {row['session_id']} "
            f"--date {row['date']}).")


@provider(id="missed", owner="R-22", order=32)
def missed_status(ctx):
    if not program.exists(ctx.root):
        return None
    today = ctx.today()
    try:
        program_doc = program.load(ctx.root)
        rows = [r for r in missed.missed_sessions(ctx.root, today, now=ctx.now()) if not r["recorded"]]
    except ValidationError:
        return None
    if not rows:
        return None
    shown = rows if len(rows) <= MAX_LINES else rows[:MAX_LINES - 1]
    options = []
    for row in shown:
        try:
            options.append(missed.recovery(ctx.root, row["session_id"], row["date"], today, program_doc=program_doc,
                                           config=ctx.config))
        except ValidationError:
            options.append(None)
    lines = [_line(row, found, today) for row, found in zip(shown, options)]
    if len(rows) > len(shown):
        lines.append(f"{len(rows) - len(shown)} more unlogged sessions: python3 -m coach missed list.")
    data = {"count": len(rows), "missed": [dict(row, recovery=found) for row, found in zip(shown, options)]}
    return Section("missed", lines, data, "attention")
