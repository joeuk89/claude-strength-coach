"""Check for the goal-events file (contract C13, C55)."""

from coach import events, paths
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-47"


@check(id="events_valid", owner=OWNER)
def events_valid(ctx):
    """Schema, unique ids, real dates, each window inside its event, status and result agree."""
    if not events.exists(ctx.root):
        return [Result("skip", f"no {paths.EVENTS} yet")]
    try:
        events.load(ctx.root)
    except ValidationError as exc:
        if not exc.details:
            return [Result("fail", exc.message, paths.EVENTS.as_posix())]
        return [Result("fail", f"{d['path']}: {d['message']}", paths.EVENTS.as_posix()) for d in exc.details]
    return []
