"""First-load warnings: the lifecycle of a line's `no_data` flag (contract C24).

A loaded line with no usable exposure and no start load is proposed with
empty working loads and a `no_data` flag naming its session date. The flag
follows its own line: it retires once every working set of that date's line
has a load, and opens again when one loses it. A resolution the coach wrote
with `propose resolve` stays as written.
"""

import re

from coach import overlay, units

CODE = overlay.NO_DATA
RESOLVED = "first load set: "
_DATE = re.compile(r" on (\d{4}-\d{2}-\d{2}): ")


def message(name, day, why):
    """A first-load flag's message; the date ties the flag to one occurrence of its slot."""
    return f"{name} on {day}: {why}, so the load is left for the coach to set"


def is_first_load(flag):
    return flag["code"] == CODE and flag["exercise_id"] is not None


def is_automatic(flag):
    """True for a resolution `settle` wrote, which the line's loads can take back."""
    return flag["resolved"] and (flag["resolution"] or "").startswith(RESOLVED)


def occurrences(flag, sessions):
    """The (session, line) pairs a first-load flag stands for.

    That is the line on the date its message names, or every line of its
    slot when the message names no date the slot has: a flag written before
    messages carried dates, or one a missed-day rule moved to another day.
    """
    found = [(session, line) for session in sessions if session["session_id"] == flag["session_id"]
             for line in session["exercises"] if line["exercise_id"] == flag["exercise_id"]]
    match = _DATE.search(flag["message"])
    dated = [(session, line) for session, line in found if match and session["date"] == match.group(1)]
    return dated or found


def missing_load(line):
    """True when a working set of a loaded line has no load."""
    return line["load_mode"] in units.LOADED_MODES and any(
        overlay.is_working(s) and s.get("load") is None for s in line["sets"])


def settle(found, sessions):
    """`found` with each first-load flag settled against its lines in `sessions` (a built overlay's)."""
    return [_settled(flag, occurrences(flag, sessions)) if is_first_load(flag) else flag for flag in found]


def belongs(flag, session, line, sessions):
    """True when `flag` is about this session's line: a first-load flag only for its own occurrence."""
    if (flag["session_id"], flag["exercise_id"]) != (session["session_id"], line["exercise_id"]):
        return False
    return not is_first_load(flag) or any(s["date"] == session["date"] for s, _ in occurrences(flag, sessions))


def _settled(flag, lines):
    if not lines:
        return flag
    if any(missing_load(line) for _, line in lines):
        return dict(flag, resolved=False, resolution=None) if is_automatic(flag) else flag
    if flag["resolved"] and not is_automatic(flag):
        return flag
    return dict(flag, resolved=True, resolution=_resolution(lines))


def _resolution(lines):
    parts = []
    for session, line in lines:
        loads = [units.format_load(s["load"]) for s in line["sets"] if overlay.is_working(s)]
        parts.append(f"{', '.join(dict.fromkeys(loads))} on {session['date']}")
    return f"{RESOLVED}{'; '.join(parts)}, not yet trained"
