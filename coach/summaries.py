"""Plugin settings in words for athlete pages: schedule rules, progression schemes, deload rules and session schemes.

A summary never prints JSON, a `null` or a bare session or exercise id the
caller can name; a setting this module has no words for prints as its key in
words and its value. The program document keeps the machine-readable form.
"""

from coach import units

_DAY_NAMES = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
_MONDAY_FIRST = tuple(_DAY_NAMES)
_SHOWN_RUNGS = 4
_INCREMENT_WHEN = {"linear": "after each exposure that hits all its reps",
                   "double_progression": "once every set reaches the top of the range"}


def _number(value):
    return str(units.json_number(value))


def _percent(value):
    return f"{units.format_number(value * 100)} %"


def _plural(count, word, plural=None):
    return f"{_number(count)} {word if count == 1 else plural or word + 's'}"


def week_days(week_starts="monday"):
    """The weekday keys in the athlete's week order."""
    return _MONDAY_FIRST[-1:] + _MONDAY_FIRST[:-1] if week_starts == "sunday" else _MONDAY_FIRST


class Names:
    """How a summary names sessions, exercises and loads: titles and library names, the athlete's unit."""

    def __init__(self, sessions=None, exercises=None, unit=None, week_starts="monday"):
        self.sessions = sessions or {}
        self.exercises = exercises or {}
        self.unit = unit
        self.week_starts = week_starts

    def session(self, session_id):
        return self.sessions.get(session_id, session_id)

    def exercise(self, exercise_id):
        return self.exercises.get(exercise_id, exercise_id)

    def load(self, value, load_mode=None):
        text = _number(value) + (f" {self.unit}" if self.unit else "")
        return text + (" per hand" if load_mode == "per_hand_x2" else "")


def _value(value, names):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        return names.session(value) if value in names.sessions else names.exercise(value)
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and "name" in item for item in value):
            return " → ".join(str(item["name"]) for item in value)
        return ", ".join(_value(item, names) for item in value if item is not None)
    if isinstance(value, dict):
        return ", ".join(f"{_value(key, names)} {_value(item, names)}" for key, item in value.items()
                         if item is not None)
    return str(value)


def _generic(key, value, names):
    return f"{key.replace('_', ' ')} {_value(value, names)}"


def _days_text(days, names):
    order = week_days(names.week_starts)
    return " · ".join(f"{_DAY_NAMES[day]} {names.session(days[day])}" for day in order if days.get(day))


def schedule_text(rule, params, names):
    """`Mon Session A · Thu Session B`: a schedule rule's week, days in week order, sessions by title."""
    params = params or {}
    if rule == "fixed_weekdays" and isinstance(params.get("days"), dict):
        return f"fixed weekdays: {_days_text(params['days'], names)}"
    if rule == "next_in_sequence" and isinstance(params.get("sequence"), list):
        sequence = " → ".join(names.session(s) for s in params["sequence"])
        days = [_DAY_NAMES[d] for d in week_days(names.week_starts) if d in (params.get("days") or [])]
        return f"next in sequence: {sequence} in turn, on {', '.join(days)}, continuing after the last session trained"
    if rule == "explicit_calendar" and isinstance(params.get("dates"), dict):
        dated = " · ".join(f"{day} {names.session(session_id)}" for day, session_id in sorted(params["dates"].items()))
        return f"explicit calendar: {dated}"
    if rule == "alternating_external_anchor" and isinstance(params.get("weeks"), list):
        weeks = "; ".join(f"{_position(week['name'])}: {_days_text(week.get('days') or {}, names)}"
                          for week in params["weeks"])
        anchor = params.get("anchor_external_id")
        return f"alternating weeks: {weeks}" + (f"; anchored to {names.session(anchor)}" if anchor else "")
    return _named(rule, params, names, {})


def _position(name):
    words = name.replace("-", " ").replace("_", " ").split()
    return " ".join(w.upper() if len(w) == 1 else w.capitalize() for w in words)


def _rungs(rungs, names):
    shown = [str(r["name"]) for r in rungs]
    if len(shown) > _SHOWN_RUNGS:
        shown = shown[:2] + ["…"] + shown[-1:]
    return f"{_plural(len(rungs), 'rung')}: {' → '.join(shown)}"


def _scheme_words(scheme_name, load_mode):
    def load(names, value):
        return names.load(value, load_mode)

    when = _INCREMENT_WHEN.get(scheme_name)
    return {
        "increment": lambda n, v: f"add {load(n, v)} {when}" if when else f"increment {load(n, v)}",
        "misses_before_reset": lambda n, v: f"reset after {_plural(v, 'miss', 'misses')} in a row",
        "reset_factor": lambda n, v: f"a reset drops the load to {_percent(v)}",
        "rungs": lambda n, v: _rungs(v, n),
        "reps": lambda n, v: (_generic("reps", v, n) if isinstance(v, dict) else _plural(v, "rep")),
        "sets": lambda n, v: _plural(v, "set"),
        "rpe": lambda n, v: f"RPE {_number(v)}",
        "training_max": lambda n, v: f"starting training max {load(n, v)}",
        "training_max_pct": lambda n, v: f"first training max at {_percent(v)} of the e1RM when none is set",
        "increment_upper": lambda n, v: f"upper-body training max raise {load(n, v)} a wave",
        "increment_lower": lambda n, v: f"lower-body training max raise {load(n, v)} a wave",
        "region": lambda n, v: f"{v}-body increments",
        "amrap": lambda n, v: "last wave set a + set" if v else "no + set",
        "top_reps": lambda n, v: f"top set of {_plural(v, 'rep')}",
        "top_rpe": lambda n, v: f"top set at RPE {_number(v)}",
        "backoff_sets": lambda n, v: _plural(v, "back-off set"),
        "backoff_reps": lambda n, v: f"back-offs of {_plural(v, 'rep')}",
        "backoff_rpe": lambda n, v: f"back-offs at RPE {_number(v)}",
        "backoff_pct": lambda n, v: f"back-offs at {_percent(v)} of the top set",
        "set_factor": lambda n, v: f"{_percent(v)} of the sets",
        "load_factor": lambda n, v: f"{_percent(v)} of the load",
        "rpe_cap": lambda n, v: f"RPE cap {_number(v)}",
        "set_delta": lambda n, v: f"{_number(v)} working set{'' if abs(v) == 1 else 's'}",
        "rpe_target": lambda n, v: f"RPE target {_number(v)}",
    }


def _named(name, params, names, words):
    parts = []
    for key in sorted(params or {}):
        value = params[key]
        if value is None or value == {} or value == []:
            continue
        parts.append(words[key](names, value) if key in words else _generic(key, value, names))
    text = name.replace("_", " ")
    return f"{text} ({'; '.join(parts)})" if parts else text


def scheme_text(scheme, names, load_mode=None):
    """`linear (add 5 kg after each exposure that hits all its reps)`: a progression or session scheme in words."""
    return _named(scheme["name"], scheme.get("params"), names, _scheme_words(scheme["name"], load_mode))


def rule_text(rule, names):
    """A deload rule or other named rule with its settings in words."""
    return _named(rule["name"], rule.get("params"), names, _scheme_words(rule["name"], None))


def session_after(schedule, position):
    """The session a `next_in_sequence` rotation trains next when `position` was the last trained, else None.

    For that rule the stored position is the last session trained, not the next one (contract C23).
    """
    if not schedule or schedule.get("rule") != "next_in_sequence":
        return None
    sequence = (schedule.get("params") or {}).get("sequence") or []
    if position not in sequence:
        return None
    return sequence[(sequence.index(position) + 1) % len(sequence)]


def position_label(position, names):
    """A rotation position as the athlete reads it: a session's title, or a week template's name (`Week B`)."""
    return names.session(position) if position in names.sessions else _position(position)
