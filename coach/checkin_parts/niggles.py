"""Open niggles in the Niggles field, due follow-ups as facts, escalations as flags (contract C27, C36)."""

from coach import followups, niggles
from coach.checkin_parts import Contribution, Field

FIELDS = ("niggles",)
ASK = "Anything new? For each open one: quiet, or still there?"


def contribute(ctx):
    if not niggles.exists(ctx.root) and not followups.exists(ctx.root):
        return None
    fields, card_flags = {}, []
    if niggles.exists(ctx.root):
        doc = niggles.load(ctx.root)
        open_rows = [f"{row['area']} ({row['status']})" for row in doc["niggles"] if niggles.is_open(row)]
        if open_rows:
            fields["niggles"] = Field(prefill=f"Open: {', '.join(open_rows)}.", ask=ASK)
        card_flags += niggles.escalate_flags(doc)
    due = followups.due(followups.load(ctx.root), ctx.today)
    facts = [f"Follow-up {item['id']} is due (review {item['review_at']}): {item['text']}" for item in due]
    card_flags += followups.due_flags(ctx.root, ctx.today)
    return Contribution(fields=fields, facts=facts, flags=card_flags)
