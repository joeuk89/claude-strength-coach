"""The events provider: a proposal's heavy lower-body work in an agreed event window, and pending windows (contract C55)."""

from coach import events

NAME = "events"


def flags(ctx):
    if ctx.mode != "proposal":
        return []
    return events.proposal_flags(ctx.root, ctx.overlay, ctx.span, ctx.today)
