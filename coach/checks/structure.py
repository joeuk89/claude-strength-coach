"""The program's static weekly balance: dose targets met and no session over the per-session ceiling (contract C41)."""

from coach import paths, program, structure
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.plugins import PluginError

_PROGRAM = paths.PROGRAM.as_posix()


@check(id="program_balance", owner="R-30a")
def program_balance(ctx):
    if not program.exists(ctx.root):
        return [Result("skip", f"no {_PROGRAM} yet", _PROGRAM)]
    try:
        report = structure.balance(ctx.root, today=ctx.today(), now=ctx.now())
    except (ValidationError, PluginError) as exc:
        return [Result("skip", f"the balance cannot be worked out ({exc}); see program_schema", _PROGRAM)]
    return [Result("warn", f"{flag['code']}: {flag['message']}", _PROGRAM) for flag in report["flags"]]
