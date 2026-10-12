"""Goal events: the countdown, the agreed window and each pending decision (contract C52, C55)."""

from coach import events
from coach.status import MAX_LINES, Section, provider


@provider(id="events", owner="R-47", order=45)
def events_status(ctx):
    found = events.views(ctx.root, ctx.today())
    if not found:
        return None
    unit = events.distance_unit(ctx.config)
    shown = found if len(found) <= MAX_LINES else found[:MAX_LINES - 1]
    lines = [events.line(item, unit) for item in shown]
    if len(found) > len(shown):
        lines.append(f"{len(found) - len(shown)} more events: python3 -m coach events list.")
    level = "attention" if any(item["pending"] or item["window_sessions"] for item in found) else "info"
    return Section("events", lines, {"events": found}, level)
