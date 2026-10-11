"""The last check-in, when the next is due and how it runs, from `coach.pages.header_facts` (C52, C38)."""

from coach import pages
from coach.status import Section, provider


@provider(id="checkin", owner="R-26b", order=50)
def checkin_status(ctx):
    facts = pages.header_facts(ctx.root, ctx.now())["checkin"]
    if facts["last"] is None:
        due = facts["due_date"]
        if due is None:
            return Section("checkin", ["No check-in recorded yet; the first due date is unknown."], facts)
        level = "attention" if due <= ctx.today().isoformat() else "info"
        return Section("checkin", [f"No check-in recorded yet; the first is due {due} (deep)."], facts, level)
    since = facts["days_since"]
    ago = "today" if since == 0 else f"{since} day{'s' if since != 1 else ''} ago"
    runs = "catch-up" if facts["mode"] == "catch_up" else facts["tier"]
    if facts["due_date"] <= ctx.today().isoformat():
        return Section("checkin", [f"Check-in due: the last was {facts['last']}, {ago}; it runs {runs}."], facts,
                       "attention")
    return Section("checkin", [f"Last check-in {facts['last']} ({ago}); the next is due {facts['due_date']} "
                               f"({facts['tier']})."], facts)
