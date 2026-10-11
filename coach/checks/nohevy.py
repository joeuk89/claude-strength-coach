"""Checks for training without Hevy: the manual log and the session sheets (contract C46, C13)."""

from coach import log, sheets
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.library import Library

OWNER = "R-40c"


@check(id="manual_log_valid", owner=OWNER)
def manual_log_valid(ctx):
    if not log.exists(ctx.root):
        return [Result("skip", f"No manual log ({log.label()}).")]
    try:
        found = log.check(ctx.root, Library.load(ctx.root), ctx.config, ctx.today())
    except ValidationError as exc:
        return [Result("skip", f"cannot check the log against the library and overlays: {exc.message}")]
    if not found:
        return [Result("pass", f"Every line of {log.label()} is valid.", log.label())]
    return [Result("fail", f"{log.label()} {message}", log.label()) for _, message in found]


@check(id="sheets_render_fresh", owner=OWNER)
def sheets_render_fresh(ctx):
    if ctx.config.hevy.enabled:
        return [Result("skip", "Hevy is on, so the athlete trains from Hevy routines, not session sheets.")]
    return [Result(status, message, sheets.label()) for status, message in sheets.freshness(ctx.root, ctx.today())]
