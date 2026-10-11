"""Aggravated niggles and niggles that need a qualified professional (contract C27, C52)."""

from coach import niggles
from coach.status import MAX_LINES, Section, provider


@provider(id="niggles", owner="R-27", order=56)
def niggles_status(ctx):
    if not niggles.exists(ctx.root):
        return None
    doc = niggles.load(ctx.root)
    aggravated = [row for row in doc["niggles"] if row["status"] == "aggravated"]
    escalating = [(row, reason) for row in doc["niggles"] for reason in [niggles.escalation(row)] if reason]
    lines = [f"Niggle {row['id']} {row['area']} is aggravated: its constraints apply to every proposal."
             for row in aggravated]
    lines += [niggles.escalate_message(row, reason) for row, reason in escalating]
    if not lines:
        return None
    return Section("niggles", lines[:MAX_LINES],
                   {"aggravated": [row["id"] for row in aggravated], "escalate": [row["id"] for row, _ in escalating]},
                   "attention")
