"""`gate pretooluse`: the approval gate as a Claude Code PreToolUse hook (contract C2, C53)."""

import json
import sys

from coach import gate
from coach.commands import command


@command(
    "gate pretooluse",
    help="Read PreToolUse hook JSON on stdin; print the hook's decision for a Hevy write, or nothing",
    network=True,
    envelope=False,
)
def pretooluse(args, ctx):
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception as exc:
        return gate.unreadable_input(f"{type(exc).__name__}: {exc}")
    return gate.decide(hook_input, env=ctx.env)
