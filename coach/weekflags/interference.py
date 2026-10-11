"""The interference provider: the program's interference rules over the span (contract C51)."""

from coach import interference

NAME = "interference"


def flags(ctx):
    return interference.flags(ctx.root, ctx.config, ctx.span, ctx.mode, ctx.bouts, ctx.today, overlay=ctx.overlay)
