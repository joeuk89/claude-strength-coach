"""Follow-ups due for review (contract C27, C52)."""

from coach import followups
from coach.status import MAX_LINES, Section, provider


@provider(id="followups", owner="R-27", order=55)
def followups_status(ctx):
    if not followups.exists(ctx.root):
        return None
    due = followups.due(followups.load(ctx.root), ctx.today())
    if not due:
        return None
    lines = [f"Follow-up {item['id']} is due (review {item['review_at']}): {item['text']}"
             for item in due[:MAX_LINES - 1]]
    if len(due) >= MAX_LINES:
        lines.append(f"{len(due) - len(lines)} more due: python3 -m coach followups list --due.")
    return Section("followups", lines, {"due": [item["id"] for item in due]}, "attention")
