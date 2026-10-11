"""Starter programs: tested programs a new athlete can begin from, drafted onto their days and kit (contract C45).

A starter is framework data in `coach/starters/<id>.json`. `draft` turns one
into a program draft for `program adopt`; nothing here writes the program.
"""

import copy
import json
from pathlib import Path

from coach import config as config_module
from coach import fit, jsonio, migrate, niggles, plugins, program, program_drafts, structure, units
from coach.errors import ValidationError
from coach.library import Library
from coach.plugins.base import WEEKDAYS
from coach.validate import validate as validate_schema

SCHEMA = "starter"
STARTERS_DIR = Path(__file__).resolve().parent / "starters"
MAJOR_MUSCLES = ("chest", "upper_back", "lats", "front_delts", "side_delts", "quadriceps", "hamstrings", "glutes",
                 "biceps", "triceps")
OTHER_TARGET_CAP = 6


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


def _fit(root, config, library, location=None, available=None, day=None):
    kit = fit.Kit(config, location, available)
    rows = niggles.load(root, library)["niggles"] if niggles.exists(root) else []
    return fit.Fit(library, kit, rows, day)


def _lacking(starter, kit):
    return [piece for piece in starter["equipment_required"] if kit.available and piece not in kit.available]


def _row(starter, experience, report):
    swaps = sum(row["kind"] == "swapped_exercise" for row in report)
    unmatched = sum(row["kind"] == "no_substitute" for row in report)
    return {
        "id": starter["id"], "title": starter["title"], "summary": starter["summary"], "level": starter["level"],
        "days": starter["days"], "minutes": starter["minutes_per_session"],
        "equipment_required": starter["equipment_required"], "swaps": swaps, "unmatched": unmatched,
        "recommended": experience in starter["level"] and unmatched == 0,
    }


def _order(starter):
    return len(starter["days"]["default"]), starter["id"]


def listing(root, config, days=None, equipment=None, location=None, today=None, directory=STARTERS_DIR):
    """Starters that fit `days` and the kit (default: `[equipment] available`; empty means every piece).

    Each row counts the lines a draft would swap (`swaps`) and those with no
    fitting substitute (`unmatched`). `recommended` marks each starter whose
    level suits `[athlete] experience` and whose every line fits, directly
    or by a swap; `recommended_id` names the first of them in list order. It
    is advice and filters nothing.
    """
    library = Library.load(root)
    fitter = _fit(root, config, library, location, equipment, today)
    registry = plugins.load(root)
    experience = config.athlete.experience
    found = []
    for starter in sorted(load_all(directory), key=_order):
        if days is not None and not starter["days"]["min"] <= days <= starter["days"]["max"]:
            continue
        if _lacking(starter, fitter.kit):
            continue
        report, _ = _swap_all(copy.deepcopy(starter["program"]), library, fitter, registry)
        found.append(_row(starter, experience, report))
    recommended = next((row["id"] for row in found if row["recommended"]), None)
    return {"starters": found, "days": days, "equipment": fitter.kit.available, "location": location,
            "experience": experience, "recommended_id": recommended}


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


def _load_mode(library, entry):
    return library.effective_load_mode(entry["id"]) or entry["load_mode_default"]


def _passed_over(passed):
    return f" (passed over {'; '.join(passed)})" if passed else ""


def _substitute(session, line, library, fitter, registry, rows):
    """Swap one line for its first fitting library substitute, or report that none fits. Returns the new id or None.

    The report row names every substitute passed over and why.
    """
    entry = library.get(line["exercise_id"])
    reason = fitter.why_not(entry)
    if reason is None:
        return None
    scheme = line["scheme"]["name"]
    plugin = registry.get("scheme", scheme)
    scheme_modes = getattr(plugin.module, "LOAD_MODES", None) if plugin else None
    taken = {other["exercise_id"] for other in session["exercises"]}
    passed = []
    for candidate_id in entry["substitutes"]:
        candidate = library.get(candidate_id)
        if candidate_id in taken:
            why = "already in this session"
        else:
            why = fitter.why_not(candidate, replacing=entry)
        mode = _load_mode(library, candidate)
        if why is None and scheme_modes is not None and mode not in scheme_modes:
            why = f"the {scheme} scheme does not take its load mode {mode}"
        if why:
            passed.append(f"{candidate['name']}: {why}")
            continue
        line.update(exercise_id=candidate_id, load_mode=mode, cues=None, start_load=0 if mode == "bodyweight" else None)
        rows.append(program_drafts.report_row(
            "swapped_exercise", f"{entry['name']} → {candidate['name']}: {entry['name']} {reason}"
                                f"{_passed_over(passed)}; set the cues with the athlete", session["id"], entry["id"]))
        return candidate_id
    rows.append(program_drafts.report_row(
        "no_substitute", f"{entry['name']} {reason}, and none of its library substitutes fits{_passed_over(passed)}; "
                         "swap or drop it with the athlete", session["id"], entry["id"]))
    return None


def _swap_all(doc, library, fitter, registry):
    """(report rows, {old id: new id}) after swapping every line the kit, the athlete or the avoid list rules out."""
    rows, swapped = [], {}
    for session in doc["sessions"]:
        for line in session["exercises"]:
            old = line["exercise_id"]
            new = _substitute(session, line, library, fitter, registry, rows)
            if new is not None and session["status"] == "active":
                swapped.setdefault(old, new)
    return rows, swapped


def _weekly_dose(doc, library):
    """Fractional hard sets per muscle a week on the program's active core lifting sessions, at its schedule."""
    params = doc["schedule"]["params"]
    if doc["schedule"]["rule"] == "fixed_weekdays":
        per_week = {}
        for session_id in params["days"].values():
            per_week[session_id] = per_week.get(session_id, 0) + 1
    else:
        share = len(params["days"]) / len(params["sequence"])
        per_week = {}
        for session_id in params["sequence"]:
            per_week[session_id] = per_week.get(session_id, 0) + share
    totals = {}
    for session in doc["sessions"]:
        if session["status"] != "active" or session["tier"] != "core" or session["kind"] != "lifting":
            continue
        for muscle, sets in structure.session_dose(library, session).items():
            totals[muscle] = totals.get(muscle, 0.0) + sets * per_week.get(session["id"], 0)
    return totals


def _retarget(doc, library):
    """Re-derive the starter's targets for muscles other than the major ones after swaps.

    As the starter files do: each other primary muscle of an active exercise
    gets its planned weekly sets, capped, so it never falls back to the
    default target; a muscle no longer trained as a primary loses its target.
    """
    weekly = _weekly_dose(doc, library)
    primary = {muscle for session in doc["sessions"] if session["status"] == "active"
               for line in session["exercises"] for muscle in library.get(line["exercise_id"])["muscles"]["primary"]}
    targets = {muscle: value for muscle, value in (doc.get("dose_targets") or {}).items() if muscle in MAJOR_MUSCLES}
    for muscle in primary - set(MAJOR_MUSCLES):
        targets[muscle] = min(units.json_number(round(weekly.get(muscle, 0.0), 1)), OTHER_TARGET_CAP)
    doc["dose_targets"] = dict(sorted(targets.items()))


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


def draft(root, starter_id, days=None, start_loads=None, now=None, directory=STARTERS_DIR, config=None,
          location=None, today=None):
    """A program draft from a starter, on the athlete's days and kit, for `program adopt`.

    With `location`, that place's kit decides the swaps and every session
    trains there. Niggles open on `today` (default: the date of `now`) keep
    a swap from bringing in a movement they cover. Raises ValidationError
    (exit 1) for an unknown starter, a day count the starter does not take,
    required equipment the athlete lacks, or a start load for an exercise
    the draft does not hold.
    """
    root = Path(root)
    config = config if config is not None else config_module.load(root, today=now)
    library = Library.load(root)
    starter = load(starter_id, directory)
    chosen = _days_for(starter, days, config)
    created_at = program_drafts.timestamp(now)
    fitter = _fit(root, config, library, location, day=today or created_at[:10])
    missing = _lacking(starter, fitter.kit)
    if missing:
        raise ValidationError(f"{starter_id} needs {', '.join(missing)} for its main lifts, and {fitter.kit.table} "
                              f"available lists only {', '.join(fitter.kit.available)}; pick a starter that fits "
                              "the kit")

    doc = copy.deepcopy(starter["program"])
    doc["name"] = starter["title"]
    doc["schedule"] = _remapped_schedule(doc["schedule"], chosen)
    doc["minimum_week"] = _remap_minimum_week(doc.get("minimum_week"), chosen)
    if location is not None:
        for session in doc["sessions"]:
            session["location"] = location
    rows, swapped = _swap_all(doc, library, fitter, plugins.load(root))
    if swapped:
        _retarget(doc, library)
    _follow_priority(doc, swapped)
    _apply_start_loads(doc, start_loads or {})
    return {
        "schema_version": jsonio.current_version(jsonio.load_schema(program_drafts.SCHEMA)),
        "source": f"starter:{starter_id}",
        "created_at": created_at,
        "program": doc,
        "position": _position(doc["schedule"]),
        "hevy_routines": {},
        "hevy_folder": None,
        "report": rows,
        "detected": copy.deepcopy(program_drafts.NO_DETECTION),
    }, chosen
