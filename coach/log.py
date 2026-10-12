"""The manual lifting log for athletes without Hevy (contract C46).

`data/log/workouts.jsonl` is append-only: one `workout` line per logged
workout, and a `void` line that removes one. A correction is a void plus a
new entry. Each set's `value` is the athlete's own number (per hand for
`per_hand_x2`), never a Hevy value; history builds load objects from it.
Each line records what the athlete reported: a rep range, a rep-out
minimum or an RPE target is a prescription, never a logged count or effort.
"""

import json
from datetime import timezone
from pathlib import Path

from coach import dates, history, jsonio, overlay, paths, program, render, timing, units
from coach.activity.records import append_lines, utc_text
from coach.errors import CoachError, RefusedError, ValidationError
from coach.validate import Error, validate

SCHEMAS = {"workout": "manual_workout_line", "void": "manual_void_line"}
WORKOUT_VERSION = 2
ADDED_IN = {2: ("start_time",)}
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
    version = line.get("schema_version")
    if kind == "workout" and isinstance(version, int) and not isinstance(version, bool):
        if version > WORKOUT_VERSION:
            return [Error("$.schema_version", f"version {version} is newer than this coach reads "
                                              f"({WORKOUT_VERSION}); run /framework-sync")]
        if 1 <= version < WORKOUT_VERSION:
            return validate(line, jsonio.line_schema(SCHEMAS[kind], version, ADDED_IN))
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
    reps = None if set_.get("rep_out") else set_.get("reps")
    return {"type": set_["type"], "reps": reps, "rpe": None,
            "value": history.coaching_number(load) if load else None,
            "duration_seconds": set_.get("duration_seconds"), "distance_meters": set_.get("distance_meters")}


def _set_numbers(numbers):
    """`set 2`, `sets 1–3` or `sets 1, 3`: one-based set numbers as a reader names them."""
    if len(numbers) == 1:
        return f"set {numbers[0]}"
    if numbers == list(range(numbers[0], numbers[-1] + 1)):
        return f"sets {numbers[0]}–{numbers[-1]}"
    return "sets " + ", ".join(str(n) for n in numbers)


def _range_text(rep_range):
    return f"{rep_range['start']}–{rep_range['end']}"


def _open_reps(set_):
    """Why a planned set's reps are not a count to prefill (its range or rep-out minimum), or None when they are."""
    if set_.get("rep_range") is not None:
        return f"the plan was a range ({_range_text(set_['rep_range'])}), not a count"
    if set_.get("rep_out"):
        return (f"the plan was a + set (at least {units.json_number(set_['reps'])}, then more up to the RPE stop), "
                "not a count")
    return None


def _name(library, exercise_id):
    entry = library.get(exercise_id)
    return entry["name"] if entry else exercise_id


def _grouped(pairs):
    """[(key, [set numbers])] from (key, set number) pairs, keys in first-seen order."""
    groups = {}
    for key, number in pairs:
        groups.setdefault(key, []).append(number)
    return list(groups.items())


def _prefilled(mode, set_, open_reps):
    """The fields `_draft_set` fills from one prescribed working set, as a reader names them."""
    fields = []
    if not open_reps and mode not in NO_REPS_MODES and set_.get("reps") is not None:
        fields.append("reps")
    if set_.get("load") is not None:
        fields.append("load")
    if set_.get("duration_seconds") is not None:
        fields.append("duration")
    if set_.get("distance_meters") is not None:
        fields.append("distance")
    return tuple(fields)


def _asks(name, line, working):
    """What the athlete must tell the coach about one prefilled exercise before `log add` (C46 `ask`)."""
    found = []
    mode = line["load_mode"]

    def ask(field, numbers, prescribed, message):
        found.append({"exercise_id": line["exercise_id"], "field": field, "sets": numbers,
                      "prescribed": prescribed, "message": f"{name} {_set_numbers(numbers)}: {message}"})

    ranged = {n: s["rep_range"] for n, s in enumerate(working, 1)
              if mode not in NO_REPS_MODES and s.get("rep_range") is not None}
    rep_outs = {n: s["reps"] for n, s in enumerate(working, 1)
                if mode not in NO_REPS_MODES and s.get("rep_out") and s.get("reps") is not None}
    for (start, end), numbers in _grouped(((r["start"], r["end"]), n) for n, r in ranged.items()):
        rep_range = {"start": start, "end": end}
        ask("reps", numbers, rep_range,
            f"ask for the reps done in each set; the plan is a range ({_range_text(rep_range)}), which is not a "
            "count, so reps stay null until the athlete gives them")
    for minimum, numbers in _grouped((m, n) for n, m in rep_outs.items()):
        ask("reps", numbers, {"at_least": minimum},
            f"ask for the reps done; the plan is a + set (at least {units.json_number(minimum)}, then more up to "
            "the RPE stop), which is not a count, so reps stay null until the athlete gives them")
    unloaded = [n for n, s in enumerate(working, 1) if mode in units.LOADED_MODES and s.get("load") is None]
    if unloaded:
        used = "the added load they used (0 for bodyweight alone)" if mode == "bodyweight" else "what they used"
        ask("value", unloaded, None,
            f"no load was prescribed ({render.CHOOSE_THE_LOAD}), so value stays null until the athlete says "
            f"{used}; ask for it")
    for fields, numbers in _grouped((_prefilled(mode, s, n in ranged or n in rep_outs), n)
                                    for n, s in enumerate(working, 1)):
        if fields:
            ask("as_written", numbers, list(fields),
                f"{' and '.join(fields)} {'is' if len(fields) == 1 else 'are'} prefilled as written; keep "
                f"{'it' if len(fields) == 1 else 'them'} only when the athlete confirms they did exactly that, "
                "otherwise ask what they did")
    for (target, stop), numbers in _grouped(((s.get("rpe"), bool(s.get("rep_out"))), n)
                                            for n, s in enumerate(working, 1)):
        word = "stop" if stop else "target"
        if target is None:
            aim = "no RPE target was set"
        elif stop:
            aim = f"the plan said stop at {units.json_number(target)}"
        else:
            aim = f"the target was {units.json_number(target)}"
        ask("rpe", numbers, target,
            f"ask how hard each set felt (RPE; {aim}); leave rpe null when the athlete cannot say, never the {word}")
    return found


def prefill(root, config, session_id, day, library):
    """(draft, ask): a workout line without `id` and `logged_at`, as the overlay in force on `day` prescribes
    `session_id`, and what the athlete must still say about it."""
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
    exercises, asks = [], []
    for line in session["exercises"]:
        working = [s for s in line["sets"] if s.get("type") != "warmup"]
        if working:
            exercises.append({"exercise_id": line["exercise_id"], "load_mode": line["load_mode"],
                              "unit": config.athlete.units, "notes": "", "sets": [_draft_set(s) for s in working]})
            asks += _asks(_name(library, line["exercise_id"]), line, working)
    draft = {"schema_version": WORKOUT_VERSION, "kind": "workout", "date": day, "start_time": None,
             "session_id": session_id, "overlay_id": doc["id"], "duration_minutes": None, "notes": "",
             "exercises": exercises}
    return draft, asks


class Slots:
    """The program and overlays a logged workout is checked against."""

    def __init__(self, root):
        self.overlays = {doc["id"]: doc for doc in overlay.list(root)}
        self.program = history.load_optional(program, root)
        self.session_ids = ({s["id"] for s in self.program["sessions"]} if self.program else set()) | {
            s["session_id"] for doc in self.overlays.values() for s in doc["sessions"]}

    def session(self, line):
        """The overlay session the workout was planned as, or None (also when its date is not a real date)."""
        doc = self.overlays.get(line.get("overlay_id"))
        if doc is None or not line.get("session_id"):
            return None
        sessions = [s for s in doc["sessions"] if s["session_id"] == line["session_id"]]
        try:
            return _nearest(sessions, line["date"]) if sessions else None
        except ValueError:
            return None

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


def _working_slot_sets(slot):
    return [s for s in slot["sets"] if overlay.is_working(s)] if slot else []


def _planned_set(planned, logged_sets, index):
    """The prescribed working set a logged set lines up with, counting working sets only; {} when there is none."""
    if logged_sets[index]["type"] == "warmup":
        return {}
    position = sum(1 for s in logged_sets[:index] if s["type"] != "warmup")
    return planned[position] if position < len(planned) else {}


def _unknown_effort(line, slots, library):
    """Warnings for working sets logged without an RPE: their effort is unknown, never the prescribed target."""
    found = []
    session = slots.session(line)
    for exercise in line["exercises"]:
        numbers = [n for n, s in enumerate(exercise["sets"], 1) if s["type"] != "warmup" and s["rpe"] is None]
        if not numbers:
            continue
        planned = _working_slot_sets(_slot_line(session, exercise["exercise_id"]))
        targets = {_planned_set(planned, exercise["sets"], n - 1).get("rpe") for n in numbers} - {None}
        assumed = (f"; the target ({', '.join(str(units.json_number(t)) for t in sorted(targets))}) is not assumed"
                   if targets else "")
        found.append(f"rpe_unknown: {_name(library, exercise['exercise_id'])} {_set_numbers(numbers)} logged "
                     f"without an RPE, so effort was not recorded{assumed}")
    return found


def _unknown_load(line, library):
    """Warnings for working sets on a loaded mode logged without a load (bodyweight alone needs none)."""
    found = []
    for exercise in line["exercises"]:
        if exercise["load_mode"] not in units.LOADED_MODES or exercise["load_mode"] == "bodyweight":
            continue
        numbers = [n for n, s in enumerate(exercise["sets"], 1) if s["type"] != "warmup" and s["value"] is None]
        if numbers:
            found.append(f"load_unknown: {_name(library, exercise['exercise_id'])} {_set_numbers(numbers)} logged "
                         f"without a load on a {exercise['load_mode']} exercise, so the load was not recorded; "
                         "ask what they used (a correction is a void plus a new entry)")
    return found


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
    elif day is not None and line["overlay_id"] and line["session_id"] and slots.session(line) is None:
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
        planned = _working_slot_sets(slot)
        for s_index, set_ in enumerate(exercise["sets"]):
            set_where = f"{where}.sets[{s_index}]"
            if set_["reps"] is None and mode not in NO_REPS_MODES:
                open_reps = _open_reps(_planned_set(planned, exercise["sets"], s_index))
                why = f"; {open_reps}, so ask for the reps done" if open_reps else "; fill in what was done"
                problem(f"{set_where}.reps", f"{exercise_id} set {s_index + 1} has no reps{why}")
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
    line = {"schema_version": WORKOUT_VERSION, "kind": "workout", "id": None, "logged_at": _timestamp(now),
            "start_time": None}
    line.update(draft)
    line["schema_version"] = WORKOUT_VERSION
    if isinstance(line.get("date"), str) and (line.get("session_id") is None or isinstance(line["session_id"], str)):
        line["id"] = next_id(found, line["date"], line["session_id"])
    if isinstance(line["start_time"], str) and isinstance(line.get("date"), str):
        zone = dates.zone(config.athlete.timezone) if config.athlete.timezone else None
        try:
            line["start_time"] = utc_text(timing.parse_start(line["start_time"], line["date"], zone))
        except ValueError as exc:
            raise ValidationError(f"The workout is not valid: $.start_time: {exc}",
                                  details=[{"path": "$.start_time", "message": str(exc)}]) from None
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
    warnings = (_looks_like_total(line, slots) + _unknown_load(line, library)
                + _unknown_effort(line, slots, library))
    if config.hevy.enabled:
        warnings.append("hevy_enabled: Hevy is on ([hevy] enabled = true); if this workout is also in Hevy, "
                        "history counts it twice, so void this entry")
    synced = None
    if not dry_run:
        append_lines(path(root), [line])
        synced = _sync_history(root, now, f"{line['id']} is logged", warnings)
    return {"id": line["id"], "summary": summary(line, slots.title(line), library), "line": line,
            "path": label(), "written": not dry_run, "dry_run": dry_run, "history": synced}, warnings


def _sync_history(root, now, done, warnings):
    """Resolve the log into history at once, so pages and block counts read the change (C17 `history sync`)."""
    try:
        report = history.sync(root, now)
    except CoachError as exc:
        step = ("fix that problem, then run python3 -m coach history sync; do not repeat this log command, "
                "which is already written")
        warnings.append(f"history_not_synced: {done}, but history sync failed ({exc.message}), so weekly pages "
                        f"and block counts do not show it yet; {step}")
        return {"synced": False, "error": exc.message, "next_step": step}
    return {"synced": True,
            **{key: report[key] for key in ("added", "updated", "removed", "reinterpreted", "unresolved")}}


def void(root, workout_id, reason, now, dry_run=False):
    """Append a void line for a live workout; return (data, warnings)."""
    if not reason.strip():
        raise ValidationError("--reason must not be empty")
    found = lines(root)
    if not any(line["kind"] == "workout" and line["id"] == workout_id for line in found):
        raise ValidationError(f"No logged workout has the id {workout_id!r}; see python3 -m coach log list")
    if workout_id not in {w["id"] for w in live(root, found)}:
        raise ValidationError(f"{workout_id} is already void")
    line = {"schema_version": 1, "kind": "void", "id": workout_id, "logged_at": _timestamp(now),
            "reason": reason.strip()}
    warnings, synced = [], None
    if not dry_run:
        append_lines(path(root), [line])
        synced = _sync_history(root, now, f"{workout_id} is void", warnings)
    return {"void": line, "path": label(), "written": not dry_run, "dry_run": dry_run, "history": synced}, warnings


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
