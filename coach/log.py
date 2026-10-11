"""The manual lifting log for athletes without Hevy (contract C46).

`data/log/workouts.jsonl` is append-only: one `workout` line per logged
workout, and a `void` line that removes one. A correction is a void plus a
new entry. Each set's `value` is the athlete's own number (per hand for
`per_hand_x2`), never a Hevy value; history builds load objects from it.
"""

import json
from datetime import timezone
from pathlib import Path

from coach import dates, history, jsonio, overlay, paths, program, render, units
from coach.activity.records import append_lines
from coach.errors import RefusedError, ValidationError
from coach.validate import Error, validate

SCHEMAS = {"workout": "manual_workout_line", "void": "manual_void_line"}
NO_LOAD_MODES = ("band", "duration", "distance")
NO_REPS_MODES = ("duration", "distance")
ADHOC = "adhoc"
_SET_LABELS = {"warmup": "warm-up", "dropset": "drop set", "failure": "to failure"}


def path(root):
    return Path(root) / paths.MANUAL_LOG


def label():
    return paths.MANUAL_LOG.as_posix()


def exists(root):
    return path(root).is_file()


def raw_lines(root):
    """(line number, parsed line or None, JSON error or None) for every non-blank line, in order."""
    if not exists(root):
        return []
    found = []
    for number, text in enumerate(path(root).read_text(encoding="utf-8").splitlines(), start=1):
        if not text.strip():
            continue
        try:
            found.append((number, json.loads(text), None))
        except json.JSONDecodeError as exc:
            found.append((number, None, exc.msg))
    return found


def schema_errors(line):
    """The schema problems with one line, as validate.Error; an unknown kind is one problem."""
    kind = line.get("kind") if isinstance(line, dict) else None
    if kind not in SCHEMAS:
        return [Error("$.kind", f"expected one of {', '.join(SCHEMAS)}, found {kind!r}")]
    return validate(line, jsonio.load_schema(SCHEMAS[kind]))


def lines(root):
    """Every line in order, validated. Raises ValidationError naming the line and JSONPath of each problem."""
    found, details = [], []
    for number, line, error in raw_lines(root):
        if error:
            details.append({"path": f"{label()}:{number}",
                            "message": f"{label()} line {number}: not valid JSON ({error})"})
            continue
        problems = schema_errors(line)
        details += [{"path": f"{label()}:{number} {p.path}",
                     "message": f"{label()} line {number}: {p.path}: {p.message}"} for p in problems]
        if not problems:
            found.append(line)
    if details:
        more = f" (and {len(details) - 1} more problem(s))" if len(details) > 1 else ""
        raise ValidationError(details[0]["message"] + more, details=details)
    return found


def live(root, found=None):
    """The workouts no void line removes, oldest first."""
    found = lines(root) if found is None else found
    voided = {line["id"] for line in found if line["kind"] == "void"}
    workouts = [line for line in found if line["kind"] == "workout" and line["id"] not in voided]
    return sorted(workouts, key=lambda w: (w["date"], w["id"]))


def next_id(found, day, session_id):
    """`manual:<date>-<session>-<n>`, n one past every id already used for that date and session, voided included."""
    prefix = f"manual:{day}-{session_id or ADHOC}-"
    taken = [int(line["id"][len(prefix):]) for line in found
             if line["kind"] == "workout" and line["id"].startswith(prefix) and line["id"][len(prefix):].isdigit()]
    return f"{prefix}{max(taken, default=0) + 1}"


def _timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nearest(sessions, day):
    target = dates.parse_date(day)
    return min(sessions, key=lambda s: (abs((dates.parse_date(s["date"]) - target).days), s["date"]))


def _draft_set(set_):
    load = set_.get("load")
    return {"type": set_["type"], "reps": set_.get("reps"), "rpe": None,
            "value": history.coaching_number(load) if load else None,
            "duration_seconds": set_.get("duration_seconds"), "distance_meters": set_.get("distance_meters")}


def prefill(root, config, session_id, day):
    """A workout line without `id` and `logged_at`, as the overlay in force on `day` prescribes `session_id`."""
    docs = overlay.list(root)
    found = overlay.pick_in_force(docs, day)
    if found is None:
        raise ValidationError(f"No overlay is in force on {day}, so there is nothing to prefill; write the draft "
                              "by hand, with overlay_id null")
    doc = found[0]
    sessions = [s for s in doc["sessions"] if s["session_id"] == session_id]
    if not sessions:
        known = ", ".join(sorted({s["session_id"] for s in doc["sessions"]}))
        raise ValidationError(f"Overlay {doc['id']}, in force on {day}, has no session {session_id}; its sessions "
                              f"are {known}")
    session = _nearest(sessions, day)
    exercises = []
    for line in session["exercises"]:
        working = [_draft_set(s) for s in line["sets"] if s.get("type") != "warmup"]
        if working:
            exercises.append({"exercise_id": line["exercise_id"], "load_mode": line["load_mode"],
                              "unit": config.athlete.units, "notes": "", "sets": working})
    return {"schema_version": 1, "kind": "workout", "date": day, "session_id": session_id,
            "overlay_id": doc["id"], "duration_minutes": None, "notes": "", "exercises": exercises}


class Slots:
    """The program and overlays a logged workout is checked against."""

    def __init__(self, root):
        self.overlays = {doc["id"]: doc for doc in overlay.list(root)}
        self.program = history.load_optional(program, root)
        self.session_ids = ({s["id"] for s in self.program["sessions"]} if self.program else set()) | {
            s["session_id"] for doc in self.overlays.values() for s in doc["sessions"]}

    def session(self, line):
        """The overlay session the workout was planned as, or None."""
        doc = self.overlays.get(line.get("overlay_id"))
        if doc is None or not line.get("session_id"):
            return None
        sessions = [s for s in doc["sessions"] if s["session_id"] == line["session_id"]]
        return _nearest(sessions, line["date"]) if sessions else None

    def title(self, line):
        session = self.session(line)
        if session:
            return session["title"]
        sessions = self.program["sessions"] if self.program else []
        found = next((s for s in sessions if s["id"] == line.get("session_id")), None)
        if found:
            return found["title"]
        return line.get("session_id") or "Ad hoc workout"


def _slot_line(session, exercise_id):
    if session is None:
        return None
    return next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)


def problems(line, slots, library, config, today):
    """Plain-sentence problems with a schema-valid workout line, each with its JSONPath."""
    found = []

    def problem(where, message):
        found.append({"path": where, "message": message})

    try:
        day = dates.parse_date(line["date"])
    except ValueError as exc:
        problem("$.date", str(exc))
        day = None
    if day is not None and today is not None and day > today:
        problem("$.date", f"{line['date']} is after today ({today.isoformat()})")
    if line["session_id"] and slots.session_ids and line["session_id"] not in slots.session_ids:
        problem("$.session_id", f"session {line['session_id']} is not in the program or any overlay")
    if line["overlay_id"] and line["overlay_id"] not in slots.overlays:
        problem("$.overlay_id", f"overlay {line['overlay_id']} does not exist")
    elif line["overlay_id"] and line["session_id"] and slots.session(line) is None:
        problem("$.session_id", f"overlay {line['overlay_id']} has no session {line['session_id']}")
    session = slots.session(line)
    for e_index, exercise in enumerate(line["exercises"]):
        where = f"$.exercises[{e_index}]"
        exercise_id, mode = exercise["exercise_id"], exercise["load_mode"]
        if library.get(exercise_id) is None:
            problem(f"{where}.exercise_id", f"{exercise_id} is not in the exercise library")
            continue
        if exercise["unit"] != config.athlete.units:
            problem(f"{where}.unit", f"{exercise_id} is logged in {exercise['unit']}, but loads are in "
                                     f"{config.athlete.units} ([athlete] units)")
        slot = _slot_line(session, exercise_id)
        expected = slot["load_mode"] if slot else library.effective_load_mode(exercise_id)
        if expected and mode != expected:
            source = "its slot in the overlay" if slot else "the exercise library"
            problem(f"{where}.load_mode", f"{exercise_id} is logged as {mode}, but {source} says {expected}")
        for s_index, set_ in enumerate(exercise["sets"]):
            set_where = f"{where}.sets[{s_index}]"
            if set_["reps"] is None and mode not in NO_REPS_MODES:
                problem(f"{set_where}.reps", f"{exercise_id} set {s_index + 1} has no reps; fill in what was done")
            if set_["value"] is not None and mode in NO_LOAD_MODES:
                problem(f"{set_where}.value", f"{exercise_id} is a {mode} exercise, which carries no load; "
                                              "value must be null")
    return found


def _looks_like_total(line, slots):
    """Warnings for per-hand values equal to the prescribed Hevy total: a dumbbell pair logged as one number."""
    found = []
    session = slots.session(line)
    for exercise in line["exercises"]:
        slot = _slot_line(session, exercise["exercise_id"])
        if exercise["load_mode"] != "per_hand_x2" or slot is None:
            continue
        prescribed = [s["load"] for s in slot["sets"] if overlay.is_working(s) and s.get("load")]
        totals = {load["hevy_total"]: load for load in prescribed}
        per_hand = {load["per_hand"] for load in prescribed}
        for index, set_ in enumerate(exercise["sets"]):
            value = set_["value"]
            if value in totals and value not in per_hand:
                found.append(f"looks_like_total: {exercise['exercise_id']} set {index + 1} is logged at "
                             f"{units.json_number(value)} per hand, the Hevy total for the prescribed "
                             f"{units.format_load(totals[value], show_hevy=False)}; value is per hand")
    return found


def _set_text(exercise, set_):
    if set_["reps"] is not None:
        text = str(set_["reps"])
    elif set_["duration_seconds"] is not None:
        text = f"{units.json_number(set_['duration_seconds'])} s"
    elif set_["distance_meters"] is not None:
        text = f"{units.json_number(set_['distance_meters'])} m"
    else:
        text = "?"
    if set_["value"] is not None and exercise["load_mode"] in units.LOADED_MODES:
        load = units.make_load(set_["value"], exercise["load_mode"], exercise["unit"])
        shown = units.format_load(load, show_hevy=False)
        text += f" @ {shown} {exercise['unit']}" if exercise["load_mode"] == "total" else f" @ {shown}"
    if set_["rpe"] is not None:
        text += f" RPE {units.json_number(set_['rpe'])}"
    if set_["type"] in _SET_LABELS:
        text += f" {_SET_LABELS[set_['type']]}"
    return text


def summary(line, title, library):
    """One line: `Session A, Mon 12 Oct: Back Squat (Barbell) 3×5 @ 100 kg RPE 7; ...`."""
    parts = []
    for exercise in line["exercises"]:
        groups = []
        for set_ in exercise["sets"]:
            text = _set_text(exercise, set_)
            if groups and groups[-1][0] == text:
                groups[-1][1] += 1
            else:
                groups.append([text, 1])
        entry = library.get(exercise["exercise_id"])
        name = entry["name"] if entry else exercise["exercise_id"]
        parts.append(f"{name} " + ", ".join(f"{count}×{text}" for text, count in groups))
    return f"{title}, {render.day_label(line['date'])}: " + "; ".join(parts)


def add(root, config, library, draft, today, now, again=False, dry_run=False):
    """Validate a drafted workout and append it; return (data, warnings)."""
    if not isinstance(draft, dict):
        raise ValidationError("The input must be one JSON object: a workout line without id and logged_at")
    given = [key for key in ("id", "logged_at") if key in draft]
    if given:
        raise ValidationError(f"log add assigns {' and '.join(given)}; leave {'them' if len(given) > 1 else 'it'} "
                              "out of the input")
    found = lines(root)
    line = {"schema_version": 1, "kind": "workout", "id": None, "logged_at": _timestamp(now)}
    line.update(draft)
    if isinstance(line.get("date"), str) and (line.get("session_id") is None or isinstance(line["session_id"], str)):
        line["id"] = next_id(found, line["date"], line["session_id"])
    errors = schema_errors(line)
    if errors:
        raise ValidationError(f"The workout is not valid: {errors[0].path}: {errors[0].message}",
                              details=[e.to_json() for e in errors])
    slots = Slots(root)
    found_problems = problems(line, slots, library, config, today)
    if found_problems:
        raise ValidationError(f"The workout is not valid: {found_problems[0]['message']}", details=found_problems)
    if line["session_id"] and not again:
        twin = next((w for w in live(root, found)
                     if w["date"] == line["date"] and w["session_id"] == line["session_id"]), None)
        if twin:
            raise RefusedError(f"{twin['id']} already logs {line['session_id']} on {line['date']}; void it and add "
                               "the corrected workout, or pass --again for a second workout that day")
    warnings = _looks_like_total(line, slots)
    if config.hevy.enabled:
        warnings.append("hevy_enabled: Hevy is on ([hevy] enabled = true); if this workout is also in Hevy, "
                        "history counts it twice, so void this entry")
    if not dry_run:
        append_lines(path(root), [line])
    return {"id": line["id"], "summary": summary(line, slots.title(line), library), "line": line,
            "path": label(), "written": not dry_run, "dry_run": dry_run}, warnings


def void(root, workout_id, reason, now, dry_run=False):
    """Append a void line for a live workout."""
    if not reason.strip():
        raise ValidationError("--reason must not be empty")
    found = lines(root)
    if not any(line["kind"] == "workout" and line["id"] == workout_id for line in found):
        raise ValidationError(f"No logged workout has the id {workout_id!r}; see python3 -m coach log list")
    if workout_id not in {w["id"] for w in live(root, found)}:
        raise ValidationError(f"{workout_id} is already void")
    line = {"schema_version": 1, "kind": "void", "id": workout_id, "logged_at": _timestamp(now),
            "reason": reason.strip()}
    if not dry_run:
        append_lines(path(root), [line])
    return {"void": line, "path": label(), "written": not dry_run, "dry_run": dry_run}


def check(root, library, config, today):
    """(line number, message) for every problem in the log (C46 `manual_log_valid`)."""
    found = []
    slots = Slots(root)
    seen, voided = {}, set()
    for number, line, error in raw_lines(root):
        if error:
            found.append((number, f"line {number} is not valid JSON ({error})"))
            continue
        errors = schema_errors(line)
        if errors:
            found += [(number, f"line {number}: {e.path}: {e.message}") for e in errors]
            continue
        if line["kind"] == "void":
            if line["id"] not in seen:
                found.append((number, f"line {number} voids {line['id']}, which no earlier line logs"))
            elif line["id"] in voided:
                found.append((number, f"line {number} voids {line['id']}, which is already void"))
            voided.add(line["id"])
            continue
        if line["id"] in seen:
            found.append((number, f"line {number} uses the id {line['id']} twice (first on line {seen[line['id']]})"))
        else:
            seen[line["id"]] = number
        found += [(number, f"line {number}: {p['path']}: {p['message']}")
                  for p in problems(line, slots, library, config, today)]
    return found
