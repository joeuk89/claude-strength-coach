"""Views of an overlay: the check-in's week-ahead region and each exercise's Hevy note (contract C11, C12).

Loads are printed only through `units.format_load`; nothing here reads or
computes with a load's numbers.
"""

import re

from coach import config as config_module
from coach import dates, overlay, units
from coach.library import Library
from coach.units import format_load

REGION_KIND = "overlay"
WEEK_IN_REVIEW_HEADING = "## Week in review"
WEEK_AHEAD_HEADING = "## The week ahead"
CHOOSE_THE_LOAD = "choose the load"

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_SET_LABELS = {"warmup": "warm-up", "dropset": "drop set", "failure": "to failure"}
_MARKER = re.compile(r"<!-- coach:(begin|end) ([a-z-]+) (\S+) -->")


def short_date(day):
    day = dates.parse_date(day) if isinstance(day, str) else day
    return f"{day.day} {_MONTHS[day.month - 1]}"


def day_label(day):
    day = dates.parse_date(day) if isinstance(day, str) else day
    return f"{_DAYS[day.weekday()]} {short_date(day)}"


def begin_marker(kind, region_id):
    return f"<!-- coach:begin {kind} {region_id} -->"


def end_marker(kind, region_id):
    return f"<!-- coach:end {kind} {region_id} -->"


def _number(value):
    return str(units.json_number(value))


def _reps(set_):
    if set_.get("rep_range") is not None:
        return units.rep_range_text(set_['rep_range']['start'], set_['rep_range']['end'])
    if set_.get("reps") is not None:
        return _number(set_["reps"]) + ("+" if set_.get("rep_out") else "")
    if set_.get("duration_seconds") is not None:
        return f"{_number(set_['duration_seconds'])} s"
    if set_.get("distance_meters") is not None:
        return f"{_number(set_['distance_meters'])} m"
    return "?"


def rpe_cell(set_):
    """A set's RPE for a table cell: its target, or `stop at N` for a rep-out set's cap."""
    if set_.get("rpe") is None:
        return ""
    return f"stop at {_number(set_['rpe'])}" if set_.get("rep_out") else _number(set_["rpe"])


def _needs_load(exercise, set_):
    return exercise["load_mode"] in units.LOADED_MODES and set_.get("load") is None


def _load_text(exercise, set_, with_unit, show_hevy=True):
    load = set_.get("load")
    if load is None:
        return CHOOSE_THE_LOAD if _needs_load(exercise, set_) else None
    text = format_load(load, show_hevy=show_hevy)
    if with_unit and exercise["load_mode"] == "total":
        text = f"{text} {load['unit']}"
    return text


def _groups(sets):
    """Consecutive sets with equal type, reps, load and RPE, as (count, first set)."""
    groups = []
    for set_ in sets:
        key = (set_.get("type"), _reps(set_), set_.get("load"), set_.get("rpe"))
        if groups and groups[-1][0] == key:
            groups[-1][1] += 1
        else:
            groups.append([key, 1, set_])
    return [(count, first) for _, count, first in groups]


def target_line(exercise):
    """`Target: ...` for a line's working sets: absolute, warm-ups left out (C12)."""
    working = [s for s in exercise["sets"] if overlay.is_working(s)]
    if not working:
        return "Target: warm-up sets only"
    parts = []
    for count, set_ in _groups(working):
        part = f"{count}×{_reps(set_)}"
        load = None if _needs_load(exercise, set_) else _load_text(exercise, set_, with_unit=True)
        if load:
            part += f" @ {load}"
        if set_.get("rpe") is not None:
            part += f" (stop at RPE {_number(set_['rpe'])})" if set_.get("rep_out") else f" @ RPE {_number(set_['rpe'])}"
        parts.append(part)
    line = "Target: " + " + ".join(parts)
    if any(_needs_load(exercise, s) for s in working):
        line += f" · {CHOOSE_THE_LOAD}"
    return line


def render_hevy_note(doc, session, exercise, is_first):
    """The Hevy routine note for one exercise; `is_first` adds the dated week line."""
    lines = []
    if is_first:
        lines.append(f"Wk of {short_date(doc['span']['start'])}: {doc['focus']}")
    lines.append(target_line(exercise))
    if exercise.get("focus"):
        lines.append(f"Focus: {exercise['focus']}")
    if exercise.get("cues"):
        lines.append(f"Cues: {exercise['cues']}")
    return "\n".join(lines)


def _cell(value):
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _row(cells):
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def _unit(doc):
    for session in doc["sessions"]:
        for exercise in session["exercises"]:
            for set_ in exercise["sets"]:
                if set_.get("load"):
                    return set_["load"]["unit"]
    return None


def _exercise_id(exercise_id):
    return exercise_id


def _exercise_rows(exercise, name=_exercise_id, show_hevy=True):
    notes = []
    if exercise.get("focus"):
        notes.append(f"Focus: {exercise['focus']}")
    if exercise.get("target_note") and exercise["target_note"] != exercise.get("focus"):
        notes.append(exercise["target_note"])
    rows = []
    for index, (count, set_) in enumerate(_groups(exercise["sets"])):
        sets = f"{count}×{_reps(set_)}"
        if set_.get("type") in _SET_LABELS:
            sets += f" {_SET_LABELS[set_['type']]}"
        load = _load_text(exercise, set_, with_unit=False, show_hevy=show_hevy) or "—"
        rpe = rpe_cell(set_)
        if index == 0:
            rest = f"{exercise['rest_seconds']} s" if exercise.get("rest_seconds") is not None else ""
            rows.append(_row([name(exercise["exercise_id"]), sets, load, rpe, rest, exercise.get("change"),
                              " · ".join(notes)]))
        else:
            rows.append(_row(["", sets, load, rpe, "", "", ""]))
    return rows


def render_week_ahead(doc, name=None, show_hevy=True):
    """The marked week-ahead region for a check-in: per-session tables, then any flags.

    `name` turns an exercise id into the name the athlete reads; without it the id is printed. With `show_hevy`
    false the loads leave out the Hevy value.
    """
    name = name or _exercise_id
    span = doc["span"]
    kind = doc["kind"].replace("_", " ")
    header = f"**Overlay** `{doc['id']}` ({kind}) · {day_label(span['start'])} – {day_label(span['end'])}"
    unit = _unit(doc)
    if unit:
        header += f" · loads in {unit}"
    lines = [begin_marker(REGION_KIND, doc["id"]), header, "", f"**Week focus:** {doc['focus']}"]
    for session in doc["sessions"]:
        lines += ["", f"### {day_label(session['date'])} · {session['title']}", ""]
        if session.get("location"):
            lines += [f"Location: {session['location']}", ""]
        if session.get("focus"):
            lines += [f"Focus: {session['focus']}", ""]
        lines.append(_row(["Exercise", "Sets × reps", "Load", "RPE", "Rest", "Change", "Notes"]))
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for exercise in session["exercises"]:
            lines += _exercise_rows(exercise, name, show_hevy)
    current = [_flag_line(flag, flag["message"]) for flag in doc["flags"] if not flag["resolved"]]
    if current:
        lines += ["", "**Flags**", ""] + current
    resolved = [_flag_line(flag, flag["resolution"]) for flag in doc["flags"] if flag["resolved"]]
    if resolved:
        lines += ["", "**Resolved flags**", ""] + resolved
    lines.append(end_marker(REGION_KIND, doc["id"]))
    return "\n".join(lines)


def _flag_line(flag, text):
    where = " / ".join(part for part in (flag["session_id"], flag["exercise_id"]) if part)
    return f"- {flag['severity']} · `{flag['code']}`" + (f" · {where}" if where else "") + f": {text}"


def render_overlay_doc(root, doc):
    """The region for an overlay document, with the instance's exercise names and Hevy setting."""
    library = Library.load(root)

    def name(exercise_id):
        entry = library.get(exercise_id)
        return entry["name"] if entry else exercise_id

    return render_week_ahead(doc, name, config_module.load(root).hevy.enabled)


def render_overlay(root, overlay_id):
    """A fresh render of the region for `overlay_id`, for freshness checks (C11)."""
    return render_overlay_doc(root, overlay.load(root, overlay_id))


def find_regions(text, kind):
    """(id, start, end) for every `kind` region in `text`; `text[start:end]` runs from marker to marker.

    Raises ValueError for a region that opens without closing or closes without opening.
    """
    regions, open_ = [], None
    for match in _MARKER.finditer(text):
        edge, found_kind, region_id = match.groups()
        if found_kind != kind:
            continue
        if edge == "begin":
            if open_:
                raise ValueError(f"region {kind} {open_[0]} opens again before it closes")
            open_ = (region_id, match.start())
        else:
            if not open_ or open_[0] != region_id:
                raise ValueError(f"region {kind} {region_id} closes without opening")
            regions.append((region_id, open_[1], match.end()))
            open_ = None
    if open_:
        raise ValueError(f"region {kind} {open_[0]} has no end marker")
    return regions


def splice_region(text, kind, region_id, region, heading=WEEK_AHEAD_HEADING):
    """Replace an existing region or append within `heading`, falling back to the end of the file."""
    for found_id, start, end in find_regions(text, kind):
        if found_id == region_id:
            return text[:start] + region + text[end:]
    position = len(text)
    match = re.search(rf"^{re.escape(heading)}\b.*$", text, flags=re.MULTILINE)
    if match:
        following = re.search(r"^## ", text[match.end():], flags=re.MULTILINE)
        if following:
            position = match.end() + following.start()
    before, after = text[:position], text[position:]
    if before and not before.endswith("\n"):
        before += "\n"
    if before and not before.endswith("\n\n"):
        before += "\n"
    return before + region + "\n" + ("\n" if after else "") + after
