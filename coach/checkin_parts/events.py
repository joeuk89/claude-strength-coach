"""Goal events on the card: countdown and agreed window as facts, pending decisions in the Events field (contract C36, C55)."""

from coach import config as config_module
from coach import dates, events
from coach.checkin_parts import Contribution, Field

FIELDS = ("events",)


def contribute(ctx):
    if not events.exists(ctx.root):
        return None
    unit = events.distance_unit(config_module.load(ctx.root))
    upcoming = events.views(ctx.root, ctx.today)
    facts = [events.line(item, unit) for item in upcoming]
    facts += [f"Event {events.label(row, unit)} on {row['date']} completed: {row['result']['text']}."
              for row in events.ordered(events.load(ctx.root)["events"])
              if row["status"] == "completed" and ctx.window.contains(dates.parse_date(row["date"]))]
    asks = [_ask(item, unit) for item in upcoming if item["pending"]]
    fields = {"events": Field(ask=" ".join(asks), label="Events")} if asks else {}
    return Contribution(fields=fields, facts=facts)


def _ask(item, unit):
    name = events.label(item, unit)
    if events.PENDING_RESULT in item["pending"]:
        return f"How did {name} go?"
    return f"For {name}: is there a window before it to keep lighter, with dates and why, or none?"
