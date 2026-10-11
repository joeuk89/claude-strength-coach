"""ISO dates, weeks and spans (contract C7).

Weeks follow `[athlete] week_starts`. A week's label is the ISO week of the
one Monday inside it, so a Sunday-start week shares its label with the ISO
week that starts the next day.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEK_STARTS = ("monday", "sunday")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEK_LABEL = re.compile(r"^(\d{4})-W(\d{2})$")


def parse_date(text):
    if not isinstance(text, str) or not _DATE.fullmatch(text):
        raise ValueError(f"expected a date as YYYY-MM-DD, found {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a real date") from None


def parse_timestamp(text):
    """Parse an ISO 8601 timestamp; a naive one is taken as UTC."""
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError(f"expected an ISO 8601 timestamp, found {text!r}") from None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown time zone {name!r}") from None


def iso_week(day):
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


@dataclass(frozen=True)
class Span:
    """Inclusive at both ends."""

    start: date
    end: date

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError(f"span ends ({self.end}) before it starts ({self.start})")

    def contains(self, day):
        return self.start <= day <= self.end

    def overlaps(self, other):
        return self.start <= other.end and other.start <= self.end

    def days(self):
        return [self.start + timedelta(days=n) for n in range((self.end - self.start).days + 1)]

    def label(self):
        """The `YYYY-Www` label of a one-week span."""
        if (self.end - self.start).days != 6:
            raise ValueError(f"only a one-week span has a label; {self.start}..{self.end} is not one")
        return iso_week(next(d for d in self.days() if d.weekday() == 0))

    def to_json(self):
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def week_span(day, week_starts):
    if week_starts not in WEEK_STARTS:
        raise ValueError(f"week_starts must be one of {', '.join(WEEK_STARTS)}, found {week_starts!r}")
    days_back = day.weekday() if week_starts == "monday" else (day.weekday() + 1) % 7
    start = day - timedelta(days=days_back)
    return Span(start, start + timedelta(days=6))


def parse_week(text, week_starts):
    """A week from its `YYYY-Www` label or from any date inside it."""
    match = _WEEK_LABEL.fullmatch(text) if isinstance(text, str) else None
    if match:
        try:
            monday = date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            raise ValueError(f"{text!r} is not a real ISO week") from None
        return week_span(monday, week_starts)
    try:
        return week_span(parse_date(text), week_starts)
    except ValueError:
        raise ValueError(f"expected a week label (YYYY-Www) or a date (YYYY-MM-DD), found {text!r}") from None


def today(ctx):
    """Today's date in the athlete's time zone, honouring `COACH_NOW`.

    `ctx` provides `now()` (an aware datetime) and `timezone()` (a tzinfo,
    or None for the system's local time).
    """
    return ctx.now().astimezone(ctx.timezone()).date()
