"""The program: sessions, exercises keyed to the library, schedule and blocks (contract C16).

`data/program.json` is the source; `routine/*.md` are rendered from it
(ADR-0001). Loads on the pages are printed only through `units.format_load`.
"""

import copy
import json
import os
import tempfile
from pathlib import Path

from coach import config as config_module
from coach import jsonio, paths, plugins, units
from coach.errors import ConfigError, ValidationError
from coach.library import MUSCLES, Library
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "program"
SCHEMA_PROBLEM = "schema"
EXERCISE_PROBLEM = "exercise_ids"
LOAD_MODE_PROBLEM = "load_mode"
NO_E1RM_WARNING = "fixed_reps_no_e1rm"
PRIORITY_NO_E1RM_WARNING = "priority_no_e1rm"
RENDER_COMMAND = "program render"
RECONCILE_COMMAND = "program reconcile-mode"
BASES = ("old", "confirmed")
PROGRAM_PAGE = paths.ROUTINE_PROGRAM_PAGE.as_posix()

_SESSION_DEFAULTS = {"location": None, "scheme": None}
_FLOOR_DEFAULTS = {"sets": 2, "rpe": None}
MINIMUM_WEEK_STATUS = "standby"
SESSION_SCHEME_EXERCISE = "hold"
_TIMED_MODES = ("duration", "distance")
_WORKING_TYPES = ("normal", "dropset", "failure")
_SET_LABELS = {"warmup": "warm-up", "dropset": "drop set", "failure": "to failure"}
_WEEKDAYS = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}


def path_for(root):
    return Path(root) / paths.PROGRAM


def exists(root):
    return path_for(root).is_file()


def read_json(path):
    """A JSON file's content, or a ValidationError naming the file."""
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"No program yet: {path} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def normalised(doc):
    """A copy of a schema-valid program with absent optional keys filled.

    Session `location` null, `dose_targets` {}, `priority` [] with each KPI's
    `target` and `by` null and each floor 2 sets at the prescribed RPE
    (rn:minimum-effective-dose.4), and `minimum_week` null.
    """
    doc = copy.deepcopy(doc)
    doc.setdefault("dose_targets", {})
    doc.setdefault("priority", [])
    doc.setdefault("minimum_week", None)
    if doc["minimum_week"] is not None:
        doc["minimum_week"].setdefault("external_sessions", [])
    for lift in doc["priority"]:
        lift["kpi"].setdefault("target", None)
        lift["kpi"].setdefault("by", None)
        lift["floor"] = dict(_FLOOR_DEFAULTS, **lift.get("floor", {}))
    for session in doc["sessions"]:
        for key, default in _SESSION_DEFAULTS.items():
            session.setdefault(key, default)
    return doc


def load(root):
    """The program, schema-checked and normalised. Raises ValidationError when absent or malformed."""
    path = path_for(root)
    if not path.is_file():
        raise ValidationError(f"No program yet: {paths.PROGRAM} does not exist in {root}")
    return normalised(jsonio.read_doc(path, SCHEMA))


def problems(doc, config=None, library=None, root=None):
    """Every problem with a program, as (kind, Error) pairs: SCHEMA_PROBLEM, EXERCISE_PROBLEM or LOAD_MODE_PROBLEM.

    `config` resolves session locations and `library` checks exercise ids and
    confirmed load modes; either may be None to skip that part. Schemes, schedule and deload
    rules are checked against the plugins of `root` (else the config's
    instance; with neither, the framework's plugins only).
    """
    version_error = _version_error(doc)
    if version_error:
        return [(SCHEMA_PROBLEM, version_error)]
    schema_errors = validate_schema(doc, jsonio.load_schema(SCHEMA))
    found = [(SCHEMA_PROBLEM, error) for error in schema_errors]
    found += [(EXERCISE_PROBLEM, error) for error in exercise_id_errors(doc, library, load_modes=False)]
    if library is not None:
        found += [(LOAD_MODE_PROBLEM, error) for error in load_mode_errors(doc, library)]
    if schema_errors:
        return found
    doc = normalised(doc)
    found += [(SCHEMA_PROBLEM, error) for error in _structure(doc)]
    if config is not None:
        found += [(SCHEMA_PROBLEM, error) for error in _locations(doc, config)]
    if root is None and config is not None and getattr(config, "path", None) is not None:
        root = Path(config.path).parent
    registry = plugins.load(root)
    found += [(SCHEMA_PROBLEM, Error(path, message)) for path, message in plugins.program_problems(doc, registry)]
    return found


def validate(doc, config=None, library=None, root=None):
    return [error for _, error in problems(doc, config, library, root)]


def warnings(doc):
    """Warnings for a valid program, each starting with its code: prescriptions that cannot supply an e1RM."""
    from coach import stats
    from coach.plugins import base

    found = []
    for _, _, session, exercise in slots(doc):
        if exercise["scheme"]["name"] != "fixed_reps_rpe":
            continue
        to_failure = [stats.reps_to_failure(s.target_reps, s.rpe)
                      for s in base.expand(exercise["sets"]) if s.working and s.target_reps is not None]
        worst = max(to_failure, default=0)
        if worst > stats.MAX_REPS_TO_FAILURE:
            found.append(f"{NO_E1RM_WARNING}: {exercise['exercise_id']} in {session['id']} is "
                         f"{units.json_number(worst)} reps to failure, past the {stats.MAX_REPS_TO_FAILURE} an e1RM "
                         "allows, so fixed_reps_rpe gets no e1RM from it and holds its load; use double_progression")
    for lift in doc.get("priority", []):
        if lift["kpi"]["kind"] != "e1rm":
            continue
        exercise_id = lift["exercise_id"]
        working = [s for _, _, _, exercise in slots(doc) if exercise["exercise_id"] == exercise_id
                   for s in base.expand(exercise["sets"]) if s.working and s.target_reps is not None]
        if not any(stats.reps_to_failure(s.target_reps, s.rpe) <= stats.MAX_REPS_TO_FAILURE for s in working):
            found.append(f"{PRIORITY_NO_E1RM_WARNING}: {exercise_id}'s priority e1RM KPI has no prescribed "
                         f"working set within {stats.MAX_REPS_TO_FAILURE} reps to failure, so the KPI may have no "
                         "e1RM to show. Choose a top_load or top_reps KPI, or prescribe a working set within the cap.")
    return found


def _version_error(doc):
    if not isinstance(doc, dict):
        return Error("$", "a program is a JSON object")
    version = doc.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    current = jsonio.current_version(jsonio.load_schema(SCHEMA))
    if version > current:
        return Error("$.schema_version",
                     f"schema_version {version} is newer than this coach reads ({current}); run /framework-sync")
    if version < current:
        return Error("$.schema_version",
                     f"schema_version {version} is older than the current {current}; run python3 -m coach migrate run")
    return None


def slots(doc):
    """Yield (session index, exercise index, session, exercise) for every well-formed exercise entry."""
    sessions = doc.get("sessions") if isinstance(doc, dict) else None
    for s_index, session in enumerate(sessions if isinstance(sessions, list) else []):
        exercises = session.get("exercises") if isinstance(session, dict) else None
        for e_index, exercise in enumerate(exercises if isinstance(exercises, list) else []):
            if isinstance(exercise, dict):
                yield s_index, e_index, session, exercise


def exercise_id_errors(doc, library, load_modes=True):
    """Exercise ids the library lacks and, with `load_modes`, entries with no load mode.

    Works on a malformed program too. The schema also reports a missing
    load mode, so `problems` passes load_modes=False.
    """
    errors = []
    for s_index, e_index, _, exercise in slots(doc):
        path = f"$.sessions[{s_index}].exercises[{e_index}]"
        exercise_id = exercise.get("exercise_id")
        if library is not None and isinstance(exercise_id, str) and library.get(exercise_id) is None:
            errors.append(Error(f"{path}.exercise_id",
                                f"{exercise_id} is not in the exercise library; use a library id or add a custom_ entry"))
        if load_modes and exercise.get("load_mode") is None:
            errors.append(Error(f"{path}.load_mode", f"{exercise_id or 'this exercise'} has no load_mode"))
    return errors


def load_mode_mismatches(doc, library, exercise_id=None):
    """Lines whose load_mode differs from the library's confirmed one, as dicts naming the slot.

    An unconfirmed exercise is no mismatch. Works on a malformed program too.
    """
    found = []
    for s_index, e_index, session, line in slots(doc):
        line_id = line.get("exercise_id")
        if not isinstance(line_id, str) or (exercise_id is not None and line_id != exercise_id):
            continue
        confirmed = library.effective_load_mode(line_id)
        if confirmed is None or confirmed == line.get("load_mode"):
            continue
        found.append({"path": f"$.sessions[{s_index}].exercises[{e_index}].load_mode",
                      "session_id": session.get("id"), "exercise_id": line_id, "load_mode": line.get("load_mode"),
                      "confirmed": confirmed, "start_load": line.get("start_load")})
    return found


def mismatch_message(row):
    command = f"python3 -m coach {RECONCILE_COMMAND} {row['exercise_id']}"
    start = row["start_load"]
    where = f"{row['exercise_id']} in session {row['session_id']} is {row['load_mode']}"
    if _is_number(start) and row["confirmed"] in units.LOADED_MODES:
        number = units.format_number(start)
        return (f"{where} with start_load {number}, but the library's confirmed load mode is {row['confirmed']}. "
                f"Ask whether {number} was meant as {row['load_mode']} or {row['confirmed']}, then run {command} "
                f"--basis old (it was {row['load_mode']}) or --basis confirmed (it was {row['confirmed']}); "
                "add --input FILE for a draft")
    return (f"{where}, but the library's confirmed load mode is {row['confirmed']}; run {command} --basis confirmed "
            "(add --input FILE for a draft)")


def load_mode_errors(doc, library):
    """An Error at each line whose load_mode differs from the library's confirmed one."""
    return [Error(row["path"], mismatch_message(row)) for row in load_mode_mismatches(doc, library)]


def reconciled(doc, exercise_id, confirmed, basis, unit):
    """(a copy of `doc` with every `exercise_id` line in `confirmed` mode, the changes made, warnings).

    With basis "old" a start load is converted from the line's mode by
    `units.convert_mode`; with "confirmed" its number already meant the
    confirmed mode and stays. A mode that carries no load takes no start load.
    Scheme params keep their numbers; under basis "old" each load among them
    that would convert to another number gets a warning.
    """
    if basis not in BASES:
        raise ValueError(f"basis must be one of {', '.join(BASES)}, found {basis!r}")
    doc = copy.deepcopy(doc)
    changes, warnings = [], []
    for s_index, e_index, session, line in slots(doc):
        if line.get("exercise_id") != exercise_id or line.get("load_mode") == confirmed:
            continue
        before = {"load_mode": line.get("load_mode"), "start_load": line.get("start_load")}
        start = before["start_load"]
        if confirmed not in units.LOADED_MODES or start is None:
            start = None
        elif basis == "old" and before["load_mode"] in units.LOADED_MODES:
            start = units.convert_mode(start, before["load_mode"], confirmed, unit)
        line["load_mode"], line["start_load"] = confirmed, start
        path = f"$.sessions[{s_index}].exercises[{e_index}]"
        changes.append({"path": path, "session_id": session.get("id"),
                        "from": before, "to": {"load_mode": confirmed, "start_load": start}})
        if basis == "old":
            warnings += _kept_scheme_loads(path, line, before["load_mode"], confirmed, unit)
    return doc, changes, warnings


_SCHEME_LOAD_PARAMS = ("increment", "training_max", "increment_upper", "increment_lower")


def _scheme_loads(line):
    """(JSONPath suffix, number) for each load among the line's scheme params."""
    scheme = line.get("scheme")
    params = scheme.get("params") if isinstance(scheme, dict) else None
    if not isinstance(params, dict):
        return []
    found = [(f".scheme.params.{key}", params[key]) for key in _SCHEME_LOAD_PARAMS if _is_number(params.get(key))]
    rungs = params.get("rungs")
    for index, rung in enumerate(rungs if isinstance(rungs, list) else []):
        if isinstance(rung, dict) and _is_number(rung.get("load")):
            found.append((f".scheme.params.rungs[{index}].load", rung["load"]))
    return found


def _kept_scheme_loads(path, line, from_mode, to_mode, unit):
    if from_mode not in units.LOADED_MODES or to_mode not in units.LOADED_MODES:
        return []
    warnings = []
    for suffix, value in _scheme_loads(line):
        converted = units.convert_mode(value, from_mode, to_mode, unit)
        if converted != value:
            warnings.append(f"{path}{suffix} keeps the number {units.format_number(value)}, which now reads as "
                            f"{to_mode}; the same load in its old mode, {from_mode}, is "
                            f"{units.format_number(converted)} {to_mode}. Ask the athlete which they meant and edit "
                            "the param to match")
    return warnings


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _structure(doc):
    errors = []
    session_ids = set()
    for s_index, session in enumerate(doc["sessions"]):
        path = f"$.sessions[{s_index}]"
        if session["id"] in session_ids:
            errors.append(Error(f"{path}.id", f"session {session['id']} appears twice"))
        session_ids.add(session["id"])
        if f"{session['id']}.md" == Path(PROGRAM_PAGE).name:
            errors.append(Error(f"{path}.id", f"session id {session['id']} would overwrite {PROGRAM_PAGE}"))
        seen = set()
        for e_index, exercise in enumerate(session["exercises"]):
            line_path = f"{path}.exercises[{e_index}]"
            if exercise["exercise_id"] in seen:
                errors.append(Error(f"{line_path}.exercise_id",
                                    f"{exercise['exercise_id']} appears twice in session {session['id']}; "
                                    "give one entry several set groups instead"))
            seen.add(exercise["exercise_id"])
            errors += _exercise_errors(exercise, line_path)
        errors += _session_scheme_errors(session, path)

    external_ids = set()
    for index, external in enumerate(doc["external_sessions"]):
        path = f"$.external_sessions[{index}].id"
        if external["id"] in session_ids:
            errors.append(Error(path, f"external session {external['id']} has the id of a program session"))
        elif external["id"] in external_ids:
            errors.append(Error(path, f"external session {external['id']} appears twice"))
        external_ids.add(external["id"])

    rule_ids = set()
    for index, rule in enumerate(doc["missed_day_rules"]):
        path = f"$.missed_day_rules[{index}]"
        if rule["id"] in rule_ids:
            errors.append(Error(f"{path}.id", f"missed-day rule {rule['id']} appears twice"))
        rule_ids.add(rule["id"])
        if rule["session_id"] not in session_ids:
            errors.append(Error(f"{path}.session_id", f"no program session {rule['session_id']}"))
        errors += _rule_shape_errors(rule, path)
    errors += _priority_errors(doc)
    errors += _minimum_week_errors(doc)
    return errors


def _priority_errors(doc):
    held = {line["exercise_id"] for session in doc["sessions"] for line in session["exercises"]}
    laddered = {line["exercise_id"] for session in doc["sessions"] for line in session["exercises"]
                if line["scheme"]["name"] == "assistance_ladder"}
    errors, seen = [], set()
    for index, lift in enumerate(doc["priority"]):
        path = f"$.priority[{index}]"
        exercise_id = lift["exercise_id"]
        if exercise_id in seen:
            errors.append(Error(f"{path}.exercise_id", f"{exercise_id} is a priority lift twice"))
        seen.add(exercise_id)
        if exercise_id not in held:
            errors.append(Error(f"{path}.exercise_id",
                                f"no session holds {exercise_id}, so it cannot be a priority lift"))
        elif lift["kpi"]["kind"] == "rung" and exercise_id not in laddered:
            errors.append(Error(f"{path}.kpi.kind", f"a rung KPI needs an assistance_ladder slot; no session ladders "
                                                  f"{exercise_id}"))
    return errors


def _minimum_week_errors(doc):
    minimum = doc["minimum_week"]
    if minimum is None:
        return []
    status = {session["id"]: session["status"] for session in doc["sessions"]}
    errors, seen = [], set()
    for index, session_id in enumerate(minimum["sessions"]):
        path = f"$.minimum_week.sessions[{index}]"
        if session_id in seen:
            errors.append(Error(path, f"{session_id} is listed twice"))
        seen.add(session_id)
        if session_id not in status:
            errors.append(Error(path, f"no program session {session_id}"))
        elif status[session_id] != MINIMUM_WEEK_STATUS:
            errors.append(Error(path, f"{session_id} is {status[session_id]}; a minimum-week session is "
                                      f"{MINIMUM_WEEK_STATUS}"))
    externals = {external["id"] for external in doc["external_sessions"]}
    seen = set()
    for index, external_id in enumerate(minimum.get("external_sessions", [])):
        path = f"$.minimum_week.external_sessions[{index}]"
        if external_id in seen:
            errors.append(Error(path, f"{external_id} is listed twice"))
        seen.add(external_id)
        if external_id not in externals:
            errors.append(Error(path, f"no external session {external_id}"))
    return errors


def _session_scheme_errors(session, path):
    """A session scheme needs a conditioning session whose every exercise holds (contract C51)."""
    if session["scheme"] is None:
        return []
    if session["kind"] != "conditioning":
        return [Error(f"{path}.scheme", f"a session scheme needs kind conditioning; session {session['id']} is "
                                        f"{session['kind']}")]
    return [Error(f"{path}.exercises[{index}].scheme.name",
                  f"{exercise['exercise_id']} uses {exercise['scheme']['name']}; under the session scheme "
                  f"{session['scheme']['name']} every exercise uses {SESSION_SCHEME_EXERCISE}")
            for index, exercise in enumerate(session["exercises"])
            if exercise["scheme"]["name"] != SESSION_SCHEME_EXERCISE]


_ACTION_KEYS = {"fold": ("into", "exercises"), "shift": ("to_weekdays",), "skip": (), "manual": ()}


def _rule_shape_errors(rule, path):
    """What each action kind needs and allows (contract C37); references are `missed_rules_valid`'s."""
    action = rule["action"]
    kind = action["kind"]
    needed = _ACTION_KEYS[kind]
    errors = [Error(f"{path}.action", f"a {kind} rule needs {key}") for key in needed if key not in action]
    errors += [Error(f"{path}.action.{key}", f"a {kind} rule takes no {key}")
               for key in ("into", "exercises", "to_weekdays") if key in action and key not in needed]
    if kind == "manual" and rule["text"] is None:
        errors.append(Error(f"{path}.text", "a manual rule needs its text: it is the rule"))
    seen = set()
    for index, item in enumerate(action.get("exercises", [])):
        if item["exercise_id"] in seen:
            errors.append(Error(f"{path}.action.exercises[{index}].exercise_id",
                                f"{item['exercise_id']} appears twice in this rule"))
        seen.add(item["exercise_id"])
    return errors


def _exercise_errors(exercise, path):
    errors = []
    mode = exercise["load_mode"]
    timed = mode in _TIMED_MODES
    for index, group in enumerate(exercise["sets"]):
        group_path = f"{path}.sets[{index}]"
        reps, rep_range = group.get("reps"), group.get("rep_range")
        if reps is not None and rep_range is not None:
            errors.append(Error(group_path, "give reps or rep_range, not both"))
        elif reps is None and rep_range is None and not timed:
            errors.append(Error(group_path, "give reps or rep_range"))
        if rep_range is not None and rep_range["start"] > rep_range["end"]:
            errors.append(Error(f"{group_path}.rep_range",
                                f"start {rep_range['start']} is above end {rep_range['end']}"))
        if mode == "duration" and group.get("duration_seconds") is None:
            errors.append(Error(group_path, "a duration set group needs duration_seconds"))
        if mode == "distance" and group.get("distance_meters") is None:
            errors.append(Error(group_path, "a distance set group needs distance_meters"))
    if mode not in units.LOADED_MODES and exercise["start_load"] is not None:
        errors.append(Error(f"{path}.start_load", f"load mode {mode} carries no load; leave start_load null"))
    for index, constraint in enumerate(exercise["constraints"]):
        errors += _constraint_errors(constraint, f"{path}.constraints[{index}]")
    return errors


def _constraint_errors(constraint, path):
    kind, value = constraint["kind"], constraint["value"]
    if kind == "no_added_load" and value is not None:
        return [Error(f"{path}.value", "no_added_load takes no value; leave it null")]
    if kind != "no_added_load" and value is None:
        return [Error(f"{path}.value", f"{kind} needs a value")]
    if kind == "rpe_cap" and not 1 <= value <= 10:
        return [Error(f"{path}.value", f"an RPE cap is 1 to 10, found {value}")]
    return []


def constraint_text(constraint):
    """A load constraint in words: "RPE cap 7 (left knee)"."""
    value = units.json_number(constraint["value"]) if constraint["value"] is not None else None
    words = {"rpe_cap": f"RPE cap {value}", "load_cap": f"load cap {value}", "no_added_load": "no added load"}
    return f"{words[constraint['kind']]} ({constraint['reason']})"


def _locations(doc, config):
    errors = []
    for s_index, session in enumerate(doc["sessions"]):
        location = session["location"]
        if location is None:
            continue
        try:
            config_module.equipment_for(config, location)
        except ConfigError:
            errors.append(Error(f"$.sessions[{s_index}].location",
                                f'no [equipment.locations.{location}] table in config.toml for location "{location}"'))
    return errors


def avoided_slots(doc, library):
    """(session id, exercise id, reason) for each active session's exercise the library marks avoid."""
    found = []
    for _, _, session, exercise in slots(doc):
        if session.get("status") != "active":
            continue
        avoid = library.avoided(exercise.get("exercise_id")) if isinstance(exercise.get("exercise_id"), str) else None
        if avoid:
            found.append((session.get("id"), exercise["exercise_id"], avoid.get("reason")))
    return found


def page_path(session_id):
    return (paths.ROUTINE_DIR / f"{session_id}.md").as_posix()


def header():
    return (f"<!-- generated by coach from {paths.PROGRAM.as_posix()}; edit the data, then run: "
            f"python3 -m coach {RENDER_COMMAND} -->")


def is_generated(text):
    return text.startswith(header())


def render_all(root):
    """{relative path: text} for routine/program.md and one page per session.

    Raises ValidationError when the program is missing, malformed or names
    an exercise the library lacks.
    """
    root = Path(root)
    doc = load(root)
    config = config_module.load(root)
    library = Library.load(root)
    errors = validate(doc, config, library)
    if errors:
        raise ValidationError(f"{paths.PROGRAM} is not valid ({len(errors)} problem(s)); "
                              "run python3 -m coach program validate",
                              details=[error.to_json() for error in errors])
    from coach import block
    return render_doc(doc, library, config.athlete.units, block.status_line(root))


def render_doc(doc, library, unit, status_line=None):
    """{relative path: text} for a valid, normalised program document; `status_line` is the block's (C43)."""
    pages = {PROGRAM_PAGE: render_program_page(doc, library, status_line)}
    for session in doc["sessions"]:
        pages[page_path(session["id"])] = render_session_page(session, library, unit)
    return pages


def sync_pages(root, pages, dry_run):
    """Write `pages` into routine/ and delete generated pages the program no longer has.

    Returns written, removed, unchanged and not_generated paths (pages in
    routine/ that no render made); with dry_run, written and removed are
    what a real run would write and remove, and nothing changes on disk.
    """
    existing = routine_pages(root)
    changed = sorted(path for path, text in pages.items() if existing.get(path) != text)
    stale = sorted(path for path, text in existing.items() if path not in pages and is_generated(text))
    result = {
        "written": changed,
        "removed": stale,
        "unchanged": sorted(path for path in pages if path not in changed),
        "not_generated": sorted(path for path in existing if path not in pages and path not in stale),
    }
    if dry_run:
        return result
    for path in changed:
        _write_text(Path(root) / path, pages[path])
    for path in stale:
        (Path(root) / path).unlink()
    return result


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def _cell(value):
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _row(cells):
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def _number(value):
    return str(units.json_number(value))


def _params(params):
    if not params:
        return ""
    return "; ".join(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}"
                     for key, value in sorted(params.items()))


def _named(name, params):
    text = name.replace("_", " ")
    detail = _params(params)
    return f"{text} ({detail})" if detail else text


def _reps(group):
    if group.get("rep_range") is not None:
        return f"{group['rep_range']['start']}–{group['rep_range']['end']}"
    if group.get("reps") is not None:
        return _number(group["reps"])
    if group.get("duration_seconds") is not None:
        return f"{_number(group['duration_seconds'])} s"
    if group.get("distance_meters") is not None:
        return f"{_number(group['distance_meters'])} m"
    return "?"


def _sets_text(group):
    text = f"{group['count']}×{_reps(group)}"
    if group["type"] in _SET_LABELS:
        text += f" {_SET_LABELS[group['type']]}"
    return text


def _start_load(exercise, unit):
    if exercise["load_mode"] not in units.LOADED_MODES:
        return "—"
    if exercise["start_load"] is None:
        return "coach picks"
    return units.format_load(units.make_load(exercise["start_load"], exercise["load_mode"], unit))


def _exercise_rows(exercise, library, unit):
    entry = library.get(exercise["exercise_id"])
    name = entry["name"] if entry else exercise["exercise_id"]
    if exercise["superset_id"] is not None:
        name += f" (superset {exercise['superset_id']})"
    groups = exercise["sets"]
    load_row = next((i for i, group in enumerate(groups) if group["type"] in _WORKING_TYPES), 0)
    rows = []
    for index, group in enumerate(groups):
        rpe = _number(group["rpe"]) if group.get("rpe") is not None else ""
        load = _start_load(exercise, unit) if index == load_row else ""
        if index == 0:
            rest = f"{exercise['rest_seconds']} s" if exercise["rest_seconds"] is not None else ""
            scheme = _named(exercise["scheme"]["name"], exercise["scheme"]["params"])
            rows.append(_row([name, _sets_text(group), rpe, load, rest, scheme]))
        else:
            rows.append(_row(["", _sets_text(group), rpe, load, "", ""]))
    return rows


def render_session_page(session, library, unit):
    lines = [header(), f"# {session['title']}", "",
             f"Session `{session['id']}` · {session['kind']} · {session['tier']} · {session['status']}"]
    if session["location"]:
        lines += ["", f"Location: {session['location']}"]
    if session["focus"]:
        lines += ["", f"Focus: {session['focus']}"]
    if session["scheme"] is not None:
        lines += ["", f"Session scheme: {_named(session['scheme']['name'], session['scheme']['params'])}. It sets "
                      "every exercise's sets each week; loads hold as written."]
    lines += ["", f"Start loads in {unit}: where each exercise begins. Each week's loads come from the overlay.", ""]
    lines.append(_row(["Exercise", "Sets × reps", "RPE", "Start load", "Rest", "Progression scheme"]))
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for exercise in session["exercises"]:
        lines += _exercise_rows(exercise, library, unit)

    notes = []
    for exercise in session["exercises"]:
        entry = library.get(exercise["exercise_id"])
        name = entry["name"] if entry else exercise["exercise_id"]
        if exercise["cues"]:
            notes.append(f"- **{name}** · cues: {exercise['cues']}")
        for constraint in exercise["constraints"]:
            notes.append(f"- **{name}** · constraint: {constraint_text(constraint)}")
    if notes:
        lines += ["", "## Cues and constraints", ""] + notes
    return "\n".join(lines) + "\n"


def _sets_by_muscle(estimated):
    return ", ".join(f"{muscle.replace('_', ' ')} {estimated[muscle]}" for muscle in MUSCLES if muscle in estimated)


def render_program_page(doc, library=None, status_line=None):
    lines = [header(), f"# {doc['name']}", "", "## Sessions", ""]
    lines.append(_row(["Session", "Id", "Kind", "Tier", "Status", "Location"]))
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for session in doc["sessions"]:
        link = f"[{_cell(session['title'])}]({Path(page_path(session['id'])).name})"
        lines.append("| " + " | ".join([link] + [_cell(v) for v in (
            f"`{session['id']}`", session["kind"], session["tier"], session["status"], session["location"] or "main",
        )]) + " |")

    schedule = doc["schedule"]
    lines += ["", "## Schedule", "", f"Schedule rule: {_named(schedule['rule'], schedule['params'])}"]

    lines += ["", "## Coach-led sessions", ""]
    if doc["external_sessions"]:
        lines.append(_row(["Session", "Id", "Day", "Estimated hard sets"]))
        lines.append("| --- | --- | --- | --- |")
        for external in doc["external_sessions"]:
            lines.append(_row([external["title"], f"`{external['id']}`", _WEEKDAYS.get(external["weekday"], ""),
                               _sets_by_muscle(external["estimated_sets"])]))
    else:
        lines.append("None.")

    blocks = doc["blocks"]
    lines += ["", "## Blocks and light weeks", "",
              f"Light week after at most {blocks['hard_weeks_ceiling']} completed hard weeks. "
              f"Deload rule: {_named(blocks['deload_rule']['name'], blocks['deload_rule']['params'])}."]
    if status_line:
        lines += ["", f"Status: {status_line}"]

    lines += _priority_lines(doc, library)
    lines += ["", "## If a day is missed", ""]
    if doc["missed_day_rules"]:
        from coach import missed

        for rule in doc["missed_day_rules"]:
            lines.append(f"- `{rule['id']}`: {missed.describe(rule, program_doc=doc, library=library)}")
    else:
        lines.append("No rules yet.")
    return "\n".join(lines) + "\n"


_KPI_WORDS = {"e1rm": "e1RM", "top_load": "top load", "top_reps": "top reps", "rung": "ladder rung"}


def _priority_lines(doc, library):
    """The priority lifts and the minimum week, only when the program has them, so older pages stay as they were."""
    lines = []
    if doc["priority"]:
        lines += ["", "## Priority lifts", ""]
        for lift in doc["priority"]:
            entry = library.get(lift["exercise_id"]) if library else None
            name = entry["name"] if entry else lift["exercise_id"]
            kpi = lift["kpi"]
            words = f"KPI {_KPI_WORDS[kpi['kind']]}"
            if kpi["target"] is not None:
                words += f", target {_number(kpi['target'])}"
                if kpi["by"]:
                    words += f" by {kpi['by']}"
            floor = lift["floor"]
            rpe = f"RPE {_number(floor['rpe'])} at most" if floor["rpe"] is not None else "the prescribed RPE"
            lines.append(f"- {name}: {words}; floor {floor['sets']} working sets at {rpe}")
    minimum = doc["minimum_week"]
    if minimum:
        lines += ["", "## Minimum week", "",
                  f"Sessions: {', '.join(f'`{session_id}`' for session_id in minimum['sessions'])}. "
                  f"Schedule rule: {_named(minimum['schedule']['rule'], minimum['schedule']['params'])}."]
        if minimum.get("external_sessions"):
            retained = ', '.join(f'`{external_id}`' for external_id in minimum['external_sessions'])
            lines.append(f"Retained coach-led sessions: {retained}.")
    return lines


def routine_pages(root):
    """Every routine/*.md file as {relative path: text}."""
    directory = Path(root) / paths.ROUTINE_DIR
    if not directory.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes().decode("utf-8") for p in sorted(directory.glob("*.md"))}
