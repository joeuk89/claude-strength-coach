"""Aggravated niggles, niggles that need a qualified professional and standing limits to confirm (contract C27,
C52)."""

from coach import niggles
from coach.status import MAX_LINES, Section, provider


@provider(id="niggles", owner="R-27", order=56)
def niggles_status(ctx):
    if not niggles.exists(ctx.root):
        return None
    doc = niggles.load(ctx.root)
    aggravated = [row for row in doc["niggles"] if row["status"] == "aggravated"]
    escalating = [(row, reason) for row in doc["niggles"] for reason in [niggles.escalation(row)] if reason]
    today = ctx.today()
    confirm = [(row, text) for row in doc["niggles"] if niggles.is_open(row)
               for text in [niggles.unconfirmed(row, today)] if text]
    lines = [_aggravated_line(row, today) for row in aggravated]
    lines += [niggles.escalate_message(row, reason) for row, reason in escalating]
    lines += [f"Niggle {row['id']} {row['area']}: {text}." for row, text in confirm]
    if not lines:
        return None
    return Section("niggles", lines[:MAX_LINES],
                   {"aggravated": [row["id"] for row in aggravated], "escalate": [row["id"] for row, _ in escalating],
                    "confirm": [row["id"] for row, _ in confirm]},
                   "attention")


def _aggravated_line(row, today):
    head = f"Niggle {row['id']} {row['area']} is aggravated"
    version = niggles.standing_on(row, today)
    if niggles.flare_on(row, today)[0]:
        return f"{head}: its flare limits and any standing ones apply to every proposal."
    if version is None or not version["constraints"]:
        return (f"{head} with no limit set; add one: python3 -m coach niggles update {row['id']} --constraint ... "
                "(standing) or --flare-constraint ... (until the status changes)")
    if not niggles.constraints_active(row, today):
        return (f"{head} but its limits are not in force; "
                f"set when they apply: python3 -m coach niggles update {row['id']} --constrain-while ...")
    return f"{head}: its constraints apply to every proposal."
