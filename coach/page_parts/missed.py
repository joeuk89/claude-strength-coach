"""The brief's "If you miss a day" lines, from the program's missed-day rules in words (contract C37, C38)."""

from coach import missed
from coach.library import Library
from coach.page_parts import Item

SLOTS = ("brief.if_you_miss",)


def contribute(ctx):
    rules = (ctx.program or {}).get("missed_day_rules") or []
    if not rules:
        return None
    library = Library.load(ctx.root)
    return {"brief.if_you_miss": [Item(missed.describe(rule, program_doc=ctx.program, library=library))
                                  for rule in rules]}
