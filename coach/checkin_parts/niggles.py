"""Open niggles and the window's logged notes in the Niggles field, due follow-ups as facts, escalations as flags
(contract C27, C36).

A logged note is the athlete's report, put to them for confirmation: the
card never turns one into a niggle, a diagnosis or a constraint.
"""

from coach import followups, niggles, render
from coach.checkin_parts import Contribution, Field

FIELDS = ("niggles",)
ASK = "Anything new? For each open one: quiet, or still there?"
NOTES_ASK = "Is anything in those notes a niggle to track, or was it nothing?"


def _notes_text(notes):
    logged = dict.fromkeys(f"{render.day_label(note['date'])} {note['title']}" for note in notes)
    return f"You logged notes on {', '.join(logged)} (above)."


def contribute(ctx):
    notes = ctx.card.get("notes") or []
    if not niggles.exists(ctx.root) and not followups.exists(ctx.root) and not notes:
        return None
    fields, card_flags, open_rows = {}, [], []
    if niggles.exists(ctx.root):
        doc = niggles.load(ctx.root)
        open_rows = [f"{row['area']} ({row['status']})" for row in doc["niggles"] if niggles.is_open(row)]
        card_flags += niggles.escalate_flags(doc)
    stated = ([f"Open: {', '.join(open_rows)}."] if open_rows else []) + ([_notes_text(notes)] if notes else [])
    if stated:
        asks = [ASK if open_rows else "Anything new?"] + ([NOTES_ASK] if notes else [])
        fields["niggles"] = Field(prefill=" ".join(stated), ask=" ".join(asks))
    due = followups.due(followups.load(ctx.root), ctx.today)
    facts = [f"Follow-up {item['id']} is due (review {item['review_at']}): {item['text']}" for item in due]
    card_flags += followups.due_flags(ctx.root, ctx.today)
    return Contribution(fields=fields, facts=facts, flags=card_flags)
