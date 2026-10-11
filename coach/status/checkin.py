"""The last check-in and when the next is due: 7 days after the newest record in check-ins/ (C52)."""

import re
from datetime import timedelta
from pathlib import Path

from coach import dates, paths
from coach.status import Section, provider

DUE_AFTER_DAYS = 7
_RECORD = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@provider(id="checkin", owner="R-26b", order=50)
def checkin_status(ctx):
    today = ctx.today()
    directory = Path(ctx.root) / paths.CHECKINS_DIR
    records = []
    if directory.is_dir():
        for path in directory.glob("*.md"):
            if _RECORD.fullmatch(path.stem):
                try:
                    records.append(dates.parse_date(path.stem))
                except ValueError:
                    continue
    records = [day for day in records if day <= today]
    if not records:
        return Section("checkin", ["No check-in recorded yet; the first one is due."],
                       {"last": None, "days_since": None, "due": today.isoformat(), "mode": "first"}, "attention")
    last = max(records)
    since = (today - last).days
    due = last + timedelta(days=DUE_AFTER_DAYS)
    data = {"last": last.isoformat(), "days_since": since, "due": due.isoformat(), "mode": "weekly"}
    ago = "today" if since == 0 else f"{since} day{'s' if since != 1 else ''} ago"
    if since >= DUE_AFTER_DAYS:
        return Section("checkin", [f"Check-in due: the last was {last.isoformat()}, {ago}."], data, "attention")
    return Section("checkin", [f"Last check-in {last.isoformat()} ({ago}); the next is due {due.isoformat()}."], data)
