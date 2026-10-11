"""Starter programs: tested programs a new athlete can begin from, drafted onto their days and kit (contract C45).

A starter is framework data in `coach/starters/<id>.json`. `draft` turns one
into a program draft for `program adopt`; nothing here writes the program.
"""

import copy
import json
from pathlib import Path

from coach import config as config_module
from coach import jsonio, migrate, plugins, program, program_drafts, units
from coach.errors import ValidationError
from coach.library import Library
from coach.plugins.base import WEEKDAYS
from coach.validate import validate as validate_schema

SCHEMA = "starter"
STARTERS_DIR = Path(__file__).resolve().parent / "starters"


def _path(starter_id, directory):
    return Path(directory) / f"{starter_id}.json"


def ids(directory=STARTERS_DIR):
    return sorted(path.stem for path in Path(directory).glob("*.json"))


def _upgraded(doc, where):
    """The starter's program taken through the program migration chain to the current version, in memory.

    A program schema bump then never leaves a framework starter behind.
    """
    document = migrate.registry().documents[program.SCHEMA]
    version = doc.get("schema_version")
    while isinstance(version, int) and version < document.target:
        step = document.step_from(version)
        if step is None:
            raise ValidationError(f"{where}: no program migration step from version {version}")
        doc = step.migrate(copy.deepcopy(doc))
        doc["schema_version"] = version = step.to_version
    return doc


def load(starter_id, directory=STARTERS_DIR):
    """One starter, schema-checked, with its program at the current program version.

    Raises ValidationError naming the known ids when there is no such starter.
    """
    path = _path(starter_id, directory)
    if not path.is_file():
        known = ", ".join(ids(directory)) or "none"
        raise ValidationError(f"No starter {starter_id!r}; starters: {known}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path.name} is not valid JSON: {exc}") from None
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA))
    if errors:
        raise ValidationError(f"{path.name} is not a valid starter ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    if doc["id"] != path.stem:
        raise ValidationError(f"{path.name} has the id {doc['id']}; a starter's id is its file name")
    doc["program"] = _upgraded(doc["program"], path.name)
    return doc


def load_all(directory=STARTERS_DIR):
    return [load(starter_id, directory) for starter_id in ids(directory)]


def _kit(config):
    return list(config_module.equipment_for(config).get("available") or [])


def _row(starter, experience):
    return {
        "id": starter["id"], "title": starter["title"], "summary": starter["summary"], "level": starter["level"],
        "days": starter["days"], "minutes": starter["minutes_per_session"],
        "equipment_required": starter["equipment_required"],
        "recommended": experience in starter["level"],
    }


def _order(starter):
    return len(starter["days"]["default"]), starter["id"]


def listing(config, days=None, equipment=None, directory=STARTERS_DIR):
    """Starters that fit `days` and `equipment` (default: `[equipment] available`; empty means every piece).

    `recommended` marks each starter whose level suits `[athlete] experience`
    and `recommended_id` names the first of them in list order; it is advice
    and filters nothing.
    """
    kit = _kit(config) if equipment is None else list(equipment)
    experience = config.athlete.experience
    found = []
    for starter in sorted(load_all(directory), key=_order):
        if days is not None and not starter["days"]["min"] <= days <= starter["days"]["max"]:
            continue
        if kit and any(piece not in kit for piece in starter["equipment_required"]):
            continue
        found.append(_row(starter, experience))
    recommended = next((row["id"] for row in found if row["recommended"]), None)
    return {"starters": found, "days": days, "equipment": kit, "experience": experience,
            "recommended_id": recommended}


def show(starter_id, library, unit, directory=STARTERS_DIR):
    """The starter and the pages its program renders with its default days."""
    starter = load(starter_id, directory)
    return {"starter": starter, "pages": program.render_doc(program.normalised(starter["program"]), library, unit)}


def parse_days(text):
    """Weekday ids from "tue,thu,sat", in week order; raises ValidationError on an unknown or repeated day."""
    found = [part.strip().lower() for part in text.split(",") if part.strip()]
    unknown = [day for day in found if day not in WEEKDAYS]
    if unknown:
        raise ValidationError(f"--days: {', '.join(unknown)} is not a weekday id ({', '.join(WEEKDAYS)})")
    repeated = sorted({day for day in found if found.count(day) > 1}, key=WEEKDAYS.index)
    if repeated:
        raise ValidationError(f"--days: {', '.join(repeated)} is listed twice")
    return sorted(found, key=WEEKDAYS.index)


def parse_start_loads(pairs):
    """{exercise id: load} from ["bb_back_squat=60", ...]; raises ValidationError on a malformed pair."""
    found = {}
    for pair in pairs or ():
        exercise_id, _, value = pair.partition("=")
        exercise_id = exercise_id.strip()
        try:
            load = float(value)
        except ValueError:
            load = None
        if not exercise_id or load is None or load < 0:
            raise ValidationError(f"--start-load {pair!r}: write EXERCISE=VALUE, a library id and a load of 0 or more "
                                  "in your units")
        found[exercise_id] = units.json_number(load)
    return found


def _days_for(starter, days, config):
    chosen = days or list(config.athlete.available_days or []) or list(starter["days"]["default"])
    chosen = sorted(chosen, key=WEEKDAYS.index)
    low, high = starter["days"]["min"], starter["days"]["max"]
    if not low <= len(chosen) <= high:
        allowed = f"{low}" if low == high else f"{low} to {high}"
        source = "--days" if days else "[athlete] available_days" if config.athlete.available_days else "the default"
        raise ValidationError(f"{starter['id']} takes {allowed} training days; {source} gives {len(chosen)} "
                              f"({', '.join(chosen)}). Pass --days with {allowed} days")
    return chosen


def minimum_week_days(days):
    """The two days a minimum week uses: the first training day and the one halfway along the list."""
    middle, _ = divmod(len(days) + 1, 2)
    return [days[0], days[middle]]


def _remapped_schedule(schedule, days):
    params = schedule["params"]
    if schedule["rule"] == "fixed_weekdays":
        ordered = [params["days"][day] for day in sorted(params["days"], key=WEEKDAYS.index)]
        return {"rule": "fixed_weekdays", "params": {"days": dict(zip(days, ordered))}}
    if schedule["rule"] == "next_in_sequence":
        return {"rule": "next_in_sequence", "params": dict(params, days=list(days))}
    raise ValidationError(f"A starter's schedule rule is fixed_weekdays or next_in_sequence, not {schedule['rule']}")


def _remap_minimum_week(minimum, days):
    if minimum is None:
        return None
    sessions = [minimum["schedule"]["params"]["days"][day]
                for day in sorted(minimum["schedule"]["params"]["days"], key=WEEKDAYS.index)]
    return {"sessions": list(minimum["sessions"]),
            "schedule": {"rule": "fixed_weekdays",
                         "params": {"days": dict(zip(minimum_week_days(days), sessions))}}}


def _position(schedule):
    """For a sequence, the last session, so the first week opens on the sequence's first session."""
    if schedule["rule"] == "next_in_sequence":
        return schedule["params"]["sequence"][-1]
    return None


def _why_not(entry, library, kit):
    """Why a line cannot stay as it is (avoided, or kit the athlete lacks), or None."""
    avoid = library.avoided(entry["id"])
    if avoid:
        return f"marked avoid in the exercise library ({avoid['reason']})"
    if kit and entry["equipment"] not in kit:
        return f"needs {entry['equipment']}, which [equipment] available does not list"
    return None


def _load_mode(library, entry):
    return library.effective_load_mode(entry["id"]) or entry["load_mode_default"]


def _fits(candidate, library, kit, taken, scheme_modes):
    if candidate is None or candidate["id"] in taken or _why_not(candidate, library, kit):
        return False
    return scheme_modes is None or _load_mode(library, candidate) in scheme_modes


def _substitute(session, line, library, kit, registry, rows):
    """Swap one line for its first fitting library substitute, or report that none fits. Returns the new id or None."""
    entry = library.get(line["exercise_id"])
    reason = _why_not(entry, library, kit)
    if reason is None:
        return None
    plugin = registry.get("scheme", line["scheme"]["name"])
    scheme_modes = getattr(plugin.module, "LOAD_MODES", None) if plugin else None
    taken = {other["exercise_id"] for other in session["exercises"]}
    for candidate_id in entry["substitutes"]:
        candidate = library.get(candidate_id)
        if _fits(candidate, library, kit, taken, scheme_modes):
            mode = _load_mode(library, candidate)
            line.update(exercise_id=candidate_id, load_mode=mode, cues=None,
                        start_load=0 if mode == "bodyweight" else None)
            rows.append(program_drafts.report_row(
                "swapped_exercise", f"{entry['name']} → {candidate['name']}: {entry['name']} {reason}; set the "
                                    "cues with the athlete", session["id"], entry["id"]))
            return candidate_id
    rows.append(program_drafts.report_row(
        "no_substitute", f"{entry['name']} {reason}, and none of its library substitutes fits; swap or drop it with "
                         "the athlete", session["id"], entry["id"]))
    return None


def _swap_all(doc, library, kit, registry):
    """(report rows, {old id: new id}) after swapping every line the athlete's kit or avoid list rules out."""
    rows, swapped = [], {}
    for session in doc["sessions"]:
        for line in session["exercises"]:
            old = line["exercise_id"]
            new = _substitute(session, line, library, kit, registry, rows)
            if new is not None and session["status"] == "active":
                swapped.setdefault(old, new)
    return rows, swapped


def _follow_priority(doc, swapped):
    held = {line["exercise_id"] for _, _, _, line in program.slots(doc)}
    found, seen = [], set()
    for lift in doc.get("priority") or []:
        exercise_id = lift["exercise_id"]
        if exercise_id not in held and exercise_id in swapped:
            exercise_id = swapped[exercise_id]
        if exercise_id in seen:
            continue
        seen.add(exercise_id)
        found.append(dict(lift, exercise_id=exercise_id))
    doc["priority"] = found


def _apply_start_loads(doc, start_loads):
    lines = {}
    for _, _, _, line in program.slots(doc):
        lines.setdefault(line["exercise_id"], []).append(line)
    for exercise_id, load in start_loads.items():
        if exercise_id not in lines:
            held = ", ".join(sorted(lines))
            raise ValidationError(f"--start-load {exercise_id}: the draft has no {exercise_id}; its exercises are "
                                  f"{held}")
        if any(line["load_mode"] not in units.LOADED_MODES for line in lines[exercise_id]):
            raise ValidationError(f"--start-load {exercise_id}: it is not a loaded exercise, so it takes no start load")
        for line in lines[exercise_id]:
            line["start_load"] = load


def draft(root, starter_id, days=None, start_loads=None, now=None, directory=STARTERS_DIR, config=None):
    """A program draft from a starter, on the athlete's days and kit, for `program adopt`.

    Raises ValidationError (exit 1) for an unknown starter, a day count the
    starter does not take, required equipment the athlete lacks, or a start
    load for an exercise the draft does not hold.
    """
    root = Path(root)
    config = config if config is not None else config_module.load(root, today=now)
    library = Library.load(root)
    starter = load(starter_id, directory)
    chosen = _days_for(starter, days, config)
    kit = _kit(config)
    missing = [piece for piece in starter["equipment_required"] if kit and piece not in kit]
    if missing:
        raise ValidationError(f"{starter_id} needs {', '.join(missing)} for its main lifts, and [equipment] available "
                              f"lists only {', '.join(kit)}; pick a starter that fits the kit")

    doc = copy.deepcopy(starter["program"])
    doc["name"] = starter["title"]
    doc["schedule"] = _remapped_schedule(doc["schedule"], chosen)
    doc["minimum_week"] = _remap_minimum_week(doc.get("minimum_week"), chosen)
    rows, swapped = _swap_all(doc, library, kit, plugins.load(root))
    _follow_priority(doc, swapped)
    _apply_start_loads(doc, start_loads or {})
    return {
        "schema_version": jsonio.current_version(jsonio.load_schema(program_drafts.SCHEMA)),
        "source": f"starter:{starter_id}",
        "created_at": program_drafts.timestamp(now),
        "program": doc,
        "position": _position(doc["schedule"]),
        "hevy_routines": {},
        "hevy_folder": None,
        "report": rows,
        "detected": copy.deepcopy(program_drafts.NO_DETECTION),
    }, chosen
