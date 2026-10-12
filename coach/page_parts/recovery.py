"""The brief's Watch items for open niggles and the block's fatigue watch and light week (contract C38, C27, C43)."""

from coach import week_view
from coach.page_parts import Item

SLOTS = ("brief.watch",)


def contribute(ctx):
    found = week_view.niggle_watch(ctx.root, ctx.today) + week_view.block_watch(ctx.root)
    return {"brief.watch": [Item(text, priority, (key,)) for key, text, priority in found]} if found else None
