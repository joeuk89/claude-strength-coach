"""Planned and logged start times: parsing what the athlete says into a C7 timestamp (contract C51).

A start is optional everywhere. Text with an offset keeps it; text without
one is local time in `[athlete] timezone`; a bare `HH:MM` is that time on
the record's own date. The start must fall on the record's date, so a start
never moves a session or a run to another day: the date is judged in the
text's own offset when it names one other than UTC (a travel day), else in
`[athlete] timezone`. A stored C7 timestamp has lost its travel offset, so it
reads back when any real UTC offset (-12:00 to +14:00) puts it on the date.
"""

import re
from datetime import date, datetime, timedelta, timezone

from coach.activity import records

_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
_STORED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_WESTMOST, _EASTMOST = timedelta(hours=-12), timedelta(hours=14)


def parse_start(text, day, zone):
    """An aware datetime for `text` on `day` (a date or YYYY-MM-DD); ValueError names what is wrong."""
    day = day if isinstance(day, date) else date.fromisoformat(day)
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"expected a time of day HH:MM or an ISO 8601 timestamp, found {text!r}")
    clock = _CLOCK.match(text.strip())
    if clock:
        hour, minute = int(clock.group(1)), int(clock.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"expected a time of day HH:MM, found {text!r}")
        naive = datetime(day.year, day.month, day.day, hour, minute)
        start = naive.replace(tzinfo=zone) if zone else naive.astimezone()
    else:
        start = records.parse_local(text.strip(), zone)
    offset = start.utcoffset()
    travel = not clock and _names_offset(text) and offset != timedelta(0)
    local = (start.astimezone(timezone.utc) + offset).date() if travel else start.astimezone(zone).date()
    if local != day and not _stored_on(text.strip(), start, day):
        raise ValueError(f"the start {text!r} falls on {local.isoformat()}, not {day.isoformat()}")
    return start


def _stored_on(text, start, day):
    if not _STORED.match(text):
        return False
    moment = start.astimezone(timezone.utc)
    return (moment + _WESTMOST).date() <= day <= (moment + _EASTMOST).date()


def _names_offset(text):
    return datetime.fromisoformat(text.strip().replace("Z", "+00:00")).tzinfo is not None


def end_of(start, minutes):
    """`start` plus `minutes` of elapsed time, whatever daylight-saving change lies between."""
    if start is None or minutes is None:
        return None
    return (start.astimezone(timezone.utc) + timedelta(minutes=minutes)).astimezone(start.tzinfo)
