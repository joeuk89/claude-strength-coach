"""`hooks sessionstart` and `hooks posttooluse`: Claude Code hook commands (contract C2, C53)."""

import json
import sys

from coach import hooks
from coach.commands import command


def _read_input():
    try:
        value = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


@command(
    "hooks sessionstart",
    help="Read SessionStart hook JSON on stdin; print the status lines as the coach's context",
    envelope=False,
)
def sessionstart(args, ctx):
    return hooks.sessionstart(_read_input(), root=ctx.root, env=ctx.env, stderr=ctx.stderr)


@command(
    "hooks posttooluse",
    help="Read PostToolUse hook JSON on stdin; run the checks for a hand-edited data file and report a failure",
    envelope=False,
)
def posttooluse(args, ctx):
    return hooks.posttooluse(_read_input(), root=ctx.root, env=ctx.env, stderr=ctx.stderr)
