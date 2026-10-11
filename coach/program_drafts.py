"""Program drafts: importing Hevy routines as a draft, and adopting a draft as the program (contract C45).

Every new program, whether imported, drawn from a starter or designed,
reaches `data/program.json` only through `adopt`. Loads cross between Hevy
and the athlete's units only through `coach.units`.
"""

import copy
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from coach import config as config_module
from coach import dates, interference, jsonio, migrate, paths, plugins, program, stats, units
from coach import state as state_module
from coach.checks.instance import cap_for
from coach.errors import ConfigError, RefusedError, ValidationError
from coach.hevy.cache import HevyCache
from coach.library import Library, jsonpath
from coach.routines import UNUSED_TITLE
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "program_draft"
DEFAULT_OUT = paths.DRAFTS_DIR / "program.json"
SOURCE = "hevy_import"
IMPORT_SCHEME = {"name": "hold", "params": {}}
PLACEHOLDER_SCHEDULE = {"rule": "fixed_weekdays", "params": {"days": {}}}
DEFAULT_BLOCKS = {"hard_weeks_ceiling": 6, "deload_rule": {"name": "standard", "params": {}}}
NO_DETECTION = {"percentage_based": False, "evidence": [], "suggested_schemes": []}
SCHEDULE_MISSING = ("Ask the athlete which days each session falls on and fill schedule.params; "
                    "program adopt refuses an empty schedule.")

_WORKING = ("normal", "dropset", "failure")
_NOTE_PRESCRIPTION = ("Target:", "Focus:", "Wk of")
_WEEK_MARKER = re.compile(r"\b(?:w|wk|week)\s*(\d+)\b", re.IGNORECASE)
_KEYWORDS = (
    ("%", re.compile(r"%")),
    ("TM", re.compile(r"\bTM\b", re.IGNORECASE)),
    ("training max", re.compile(r"\btraining\s+max\b", re.IGNORECASE)),
    ("1RM", re.compile(r"\b1\s*RM\b", re.IGNORECASE)),
    ("5/3/1", re.compile(r"\b5/3/1\b")),
    ("531", re.compile(r"\b531\b")),
)
_WAVE_KEYWORDS = ("TM", "training max", "5/3/1", "531")
_MIN_ROUTINES_FOR_LOADS = 3


def _row(kind, message, session_id=None, exercise_id=None):
    return {"kind": kind, "session_id": session_id, "exercise_id": exercise_id, "message": message}


def _timestamp(now):
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(now, str):
        now = dates.parse_timestamp(now)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def import_hevy(root, routine_ids=None, folder_id=None, now=None):
    """A program draft from the cached Hevy routines (all but retired ones, or those named, or one folder's).

    Raises ConfigError with no cached routines, and ValidationError for an
    unknown routine id, an empty selection, or a routine exercise without a
    confirmed load mode.
    """
    root = Path(root)
    config = config_module.load(root)
    library = Library.load(root)
    cache = HevyCache(root)
    if cache.read("routines") is None:
        raise ConfigError("There are no cached Hevy routines to import; run python3 -m coach hevy pull first")
    routines = _selected(cache.routines(), routine_ids, folder_id)
    modes = _confirmed_modes(routines, library)

    report, sessions, hevy_routines, top_loads = [], [], {}, {}
    taken = set()
    for routine in routines:
        session_id = _session_id(routine.get("title") or "", taken)
        entries = {}
        for item in routine.get("exercises") or []:
            exercise_id = library.by_hevy_template_id(item["exercise_template_id"])["id"]
            entries.setdefault(exercise_id, []).append(item)
        exercises = []
        for exercise_id, items in entries.items():
            line, rows, top = _exercise(items, exercise_id, modes[exercise_id], session_id, library, config)
            exercises.append(line)
            report += rows
            if top is not None:
                top_loads.setdefault(exercise_id, []).append(top)
        patterns = {(library.get(e) or {}).get("pattern") for e in entries}
        sessions.append({
            "id": session_id, "title": routine.get("title") or session_id,
            "kind": "conditioning" if patterns == {"conditioning"} else "lifting",
            "tier": "core", "status": "active", "location": None, "focus": None,
            "exercises": exercises,
        })
        hevy_routines[routine["id"]] = session_id

    detected = _detect(routines, top_loads, library, config.athlete.units)
    report += [_row("percentage_evidence", item["message"], exercise_id=item["exercise_id"])
               for item in detected["evidence"]]
    report.append(_row("schedule_missing", SCHEDULE_MISSING))
    folder = folder_id if folder_id is not None else _shared_folder(routines)
    return {
        "schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)),
        "source": SOURCE,
        "created_at": _timestamp(now),
        "program": {
            "schema_version": jsonio.current_version(jsonio.load_schema(program.SCHEMA)),
            "name": _program_name(cache.folders(), folder),
            "sessions": sessions,
            "external_sessions": [],
            "schedule": copy.deepcopy(PLACEHOLDER_SCHEDULE),
            "blocks": copy.deepcopy(DEFAULT_BLOCKS),
            "missed_day_rules": [],
            "interference": interference.default_rules(),
        },
        "position": None,
        "hevy_routines": hevy_routines,
        "hevy_folder": folder,
        "report": report,
        "detected": detected,
    }


def _selected(routines, routine_ids, folder_id):
    live = [r for r in routines if (r.get("title") or "").strip() != UNUSED_TITLE]
    if folder_id is not None:
        live = [r for r in live if r.get("folder_id") == folder_id]
    if routine_ids:
        by_id = {r.get("id"): r for r in live}
        unknown = [routine_id for routine_id in routine_ids if routine_id not in by_id]
        if unknown:
            raise ValidationError(f"No cached routine to import has the id {', '.join(unknown)}; "
                                  "run python3 -m coach hevy pull, or check the id")
        live = [by_id[routine_id] for routine_id in dict.fromkeys(routine_ids)]
    if not live:
        where = f" in folder {folder_id}" if folder_id is not None else ""
        raise ValidationError(f"There are no cached Hevy routines{where} to import")
    return live


def _confirmed_modes(routines, library):
    """{exercise id: confirmed load mode}; raises naming every routine exercise without one."""
    modes, unmatched, unconfirmed = {}, [], []
    for routine in routines:
        for item in routine.get("exercises") or []:
            entry = library.by_hevy_template_id(item.get("exercise_template_id"))
            if entry is None:
                unmatched.append(f"{item.get('title')} ({item.get('exercise_template_id')})")
                continue
            mode = library.effective_load_mode(entry["id"])
            if mode is None:
                unconfirmed.append(entry["id"])
            modes[entry["id"]] = mode
    problems = []
    if unmatched:
        problems.append(f"no library entry holds {', '.join(dict.fromkeys(unmatched))}")
    if unconfirmed:
        problems.append(f"no confirmed load mode for {', '.join(dict.fromkeys(unconfirmed))}")
    if problems:
        raise ValidationError(f"Cannot import yet: {'; '.join(problems)}. Run python3 -m coach library seed, "
                              "then python3 -m coach library confirm (or library set-mode) for each exercise")
    return modes


def _session_id(title, taken):
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "session"
    candidate, suffix = base, 2
    while candidate in taken or candidate == Path(program.PROGRAM_PAGE).stem:
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    taken.add(candidate)
    return candidate


def _group_key(item):
    rep_range = item.get("rep_range")
    return (item.get("type") or "normal", item.get("reps"),
            (rep_range["start"], rep_range["end"]) if rep_range else None,
            item.get("duration_seconds"), item.get("distance_meters"))


def _set_groups(sets):
    groups = []
    for item in sets:
        key = _group_key(item)
        if groups and groups[-1][0] == key:
            groups[-1][1]["count"] += 1
            continue
        kind, reps, rep_range, duration, distance = key
        group = {"count": 1, "type": kind}
        if reps is not None:
            group["reps"] = reps
        elif rep_range is not None:
            group["rep_range"] = {"start": rep_range[0], "end": rep_range[1]}
        if duration is not None:
            group["duration_seconds"] = duration
        if distance is not None:
            group["distance_meters"] = units.json_number(distance)
        groups.append((key, group))
    return [group for _, group in groups]


def _cues(notes):
    lines = [line.strip() for line in (notes or "").splitlines()]
    for line in lines:
        if line.startswith("Cues:"):
            return line[len("Cues:"):].strip() or None
    kept = [line for line in lines if line and not line.startswith(_NOTE_PRESCRIPTION)]
    return " · ".join(kept) or None


def _working_weights(sets):
    return [item["weight_kg"] for item in sets if (item.get("type") or "normal") in _WORKING
            and item.get("weight_kg") is not None]


def _exercise(items, exercise_id, mode, session_id, library, config):
    """(program line, report rows, top load in athlete units or None) for every entry of one exercise in a routine.

    The first entry gives the rest and superset; the sets of every entry count
    toward the start load.
    """
    rows = []
    cues = next((found for found in (_cues(item.get("notes")) for item in items) if found), None)
    if cues:
        rows.append(_row("cues_from_notes", f"Cues from the Hevy note: {cues}", session_id, exercise_id))
    sets = [entry for item in items for entry in item.get("sets") or []]
    start_load, top = _start_load(sets, exercise_id, mode, session_id, library, config, rows)
    line = {
        "exercise_id": exercise_id,
        "load_mode": mode,
        "sets": [group for item in items for group in _set_groups(item.get("sets") or [])],
        "rest_seconds": items[0].get("rest_seconds"),
        "superset_id": items[0].get("superset_id"),
        "cues": cues,
        "constraints": [],
        "scheme": copy.deepcopy(IMPORT_SCHEME),
        "start_load": start_load,
    }
    return line, rows, top


def _start_load(sets, exercise_id, mode, session_id, library, config, rows):
    if mode not in units.LOADED_MODES:
        return None, None
    weights = _working_weights(sets)
    if not weights:
        return (0 if mode == "bodyweight" else None), None
    unit = config.athlete.units
    top = min(weights) if mode == "assisted" else max(weights)
    value, message = _converted(top, exercise_id, mode, library, config)
    rows.append(_row("converted_load", message, session_id, exercise_id))
    if len(set(weights)) > 1:
        loads = ", ".join(_as_text(units.from_hevy_kg(weight, mode, unit), mode, unit) for weight in weights)
        rows.append(_row("mixed_loads", f"Working sets at {loads}; the start load is the top set, "
                                        f"{_as_text(value, mode, unit)}", session_id, exercise_id))
    return value, units.from_hevy_kg(top, mode, unit)


def _as_text(value, mode, unit):
    return units.format_load(units.make_load(value, mode, unit), show_hevy=False)


def _converted(weight_kg, exercise_id, mode, library, config):
    """(start load, report message) for a Hevy weight: the athlete's number, rounded only when a unit change blurred it."""
    unit = config.athlete.units
    raw = units.from_hevy_kg(weight_kg, mode, unit)
    hevy = units.format_number(units.make_load(raw, mode, unit)["hevy_total"])
    if units.to_hevy_kg(raw, mode, unit) == weight_kg:
        return raw, f"Hevy {hevy} → {_as_text(raw, mode, unit)}"
    step = stats.load_increment(library, config, exercise_id, None)
    if not step:
        return raw, f"Hevy {hevy} → {_as_text(raw, mode, unit)}"
    value = units.round_to_increment(raw, step)
    return value, (f"Hevy {hevy} → {_as_text(value, mode, unit)}, rounded to the "
                   f"{units.format_number(step)} {unit} step")


def _shared_folder(routines):
    folders = {r.get("folder_id") for r in routines}
    return folders.pop() if len(folders) == 1 else None


def _program_name(folders, folder_id):
    title = next((f.get("title") for f in folders if f.get("id") == folder_id), None) if folder_id is not None else None
    return f"{title} (imported from Hevy)" if title else "Imported from Hevy"


def _detect(routines, top_loads, library, unit):
    """Percentage-based signals: keywords, week-marked titles, one exercise at three or more top loads."""
    evidence, keywords = [], set()
    for routine in routines:
        texts = [(routine.get("title"), f"the title {routine.get('title')!r}"),
                 (routine.get("notes"), f"the note on {routine.get('title')!r}")]
        texts += [(item.get("notes"), f"the note on {item.get('title')} in {routine.get('title')!r}")
                  for item in routine.get("exercises") or []]
        for text, where in texts:
            for keyword, pattern in _KEYWORDS:
                if text and pattern.search(text):
                    keywords.add(keyword)
                    evidence.append({"kind": "keyword", "exercise_id": None, "message": f'"{keyword}" in {where}'})

    by_stem = {}
    for routine in routines:
        title = routine.get("title") or ""
        marker = _WEEK_MARKER.search(title)
        if marker:
            stem = " ".join(_WEEK_MARKER.sub(" ", title).lower().split())
            by_stem.setdefault(stem, []).append((marker.group(1), title))
    for found in by_stem.values():
        if len(found) >= 2 and len({number for number, _ in found}) >= 2:
            titles = ", ".join(title for _, title in found)
            evidence.append({"kind": "week_titles", "exercise_id": None,
                             "message": f"Titles differ only by a week marker: {titles}"})

    for exercise_id, found in top_loads.items():
        distinct = sorted(set(found))
        if len(found) >= _MIN_ROUTINES_FOR_LOADS and len(distinct) >= _MIN_ROUTINES_FOR_LOADS:
            loads = ", ".join(units.format_number(load) for load in distinct)
            name = (library.get(exercise_id) or {}).get("name", exercise_id)
            evidence.append({"kind": "top_loads", "exercise_id": exercise_id,
                             "message": f"{name} has {len(distinct)} different top loads ({unit}) across "
                                        f"{len(found)} routines: {loads}"})

    kinds = {item["kind"] for item in evidence}
    suggested = []
    if "week_titles" in kinds or keywords & set(_WAVE_KEYWORDS):
        suggested.append("wave_531")
    if keywords & {"%", "1RM"} or ("top_loads" in kinds and "week_titles" not in kinds):
        suggested.append("fixed_reps_rpe")
    return {"percentage_based": bool(evidence), "evidence": evidence, "suggested_schemes": suggested}


def read_draft(path):
    """A draft file's JSON, or a ValidationError naming the file."""
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"No program draft at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def _under(prefix, path):
    return prefix + path[1:]


def _draft_errors(draft, config, library, root):
    """Every problem with a draft, as Errors with JSONPaths from the draft's root."""
    if not isinstance(draft, dict):
        return [Error("$", "a program draft is a JSON object")]
    schema = jsonio.load_schema(SCHEMA)
    version = draft.get("schema_version")
    current = jsonio.current_version(schema)
    if isinstance(version, int) and not isinstance(version, bool) and version != current:
        hint = "run /framework-sync" if version > current else "write the draft again"
        return [Error("$.schema_version", f"schema_version {version} is not the current {current}; {hint}")]
    errors = validate_schema(draft, schema)
    if errors:
        return errors
    doc = draft["program"]
    errors = [Error(_under("$.program", e.path), e.message) for _, e in program.problems(doc, config, library, root)]
    if errors:
        return errors
    doc = program.normalised(doc)
    errors += _cap_errors(doc, config)
    errors += _schedule_errors(doc)
    sessions = {s["id"] for s in doc["sessions"]}
    for routine_id, session_id in draft["hevy_routines"].items():
        if session_id not in sessions:
            errors.append(Error(jsonpath("hevy_routines", routine_id), f"no program session {session_id}"))
    return errors


def _cap_errors(doc, config):
    errors = []
    for s_index, e_index, session, line in program.slots(doc):
        if line["start_load"] is None or line["load_mode"] not in units.LOADED_MODES:
            continue
        try:
            cap, source = cap_for(config, line["exercise_id"], line["load_mode"], session["location"])
        except ConfigError:
            continue
        if cap is not None and line["start_load"] > cap:
            unit = config.athlete.units
            errors.append(Error(f"$.program.sessions[{s_index}].exercises[{e_index}].start_load",
                                f"start load {_as_text(line['start_load'], line['load_mode'], unit)} is above the "
                                f"{source} cap of {units.format_number(cap)}"))
    return errors


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _schedule_errors(doc):
    sessions = {s["id"] for s in doc["sessions"]}
    if any(text in sessions for text in _strings(doc["schedule"]["params"])):
        return []
    return [Error("$.program.schedule.params",
                  f"the {doc['schedule']['rule']} schedule places no session yet; fill it with the days the "
                  "athlete agreed")]


def _rotation(doc, position, today, config, registry):
    rule = doc["schedule"]["rule"]
    plugin = registry.get("schedule", rule)
    params, _ = plugins.merged_params(plugin, doc["schedule"]["params"])
    positions = list(plugin.module.positions(params))
    if not positions:
        if position is not None:
            raise ValidationError(f"The {rule} schedule rule has no rotation, so it takes no position; "
                                  f"drop --position {position}")
        return {"position": None, "confirmed": True, "confirmed_at": None, "week": None}
    if position is None:
        position = positions[0]
    if position not in positions:
        raise ValidationError(f"{position} is not a position of {rule}; positions: {', '.join(positions)}")
    week = dates.week_span(today + timedelta(days=1), config.athlete.week_starts)
    return {"position": position, "confirmed": True, "confirmed_at": today.isoformat(),
            "week": week.start.isoformat()}


def _slot_schemes(doc):
    return {f"{session['id']}/{line['exercise_id']}": line["scheme"]["name"]
            for _, _, session, line in program.slots(doc)}


def _scheme_state(old_state, old_program, new_program):
    """(kept entries, kept keys, dropped keys): an entry survives only when its slot keeps its exercise and scheme."""
    if not old_state:
        return {}, [], []
    before = _slot_schemes(old_program) if old_program else {}
    after = _slot_schemes(new_program)
    kept, dropped = {}, []
    for key, entry in old_state["scheme_state"].items():
        scheme = after.get(key)
        if scheme is not None and before.get(key) == scheme and entry.get("scheme") in (None, scheme):
            kept[key] = copy.deepcopy(entry)
        else:
            dropped.append(key)
    return kept, sorted(kept), sorted(dropped)


def _status_line(root, new_state, doc):
    from coach import block, decisions
    try:
        return block.status_line_for(new_state["block"], block.ceiling_of(doc), block.load(root), decisions.load(root))
    except ValidationError:
        return None


def _new_state(draft, doc, old_state, old_program, rotation, today):
    scheme_state, kept, dropped = _scheme_state(old_state, old_program, doc)
    old_hevy = (old_state or {}).get("hevy") or {}
    old_folders = old_hevy.get("folders") or {}
    folder = draft["hevy_folder"] if draft["hevy_folder"] is not None else old_folders.get("program")
    state = {
        "schema_version": jsonio.current_version(jsonio.load_schema(state_module.SCHEMA)),
        "rotation": rotation,
        "block": copy.deepcopy(old_state["block"]) if old_state else {
            "id": "b-0001", "started": today.isoformat(), "hard_weeks_completed": 0, "last_closed_week": None,
            "last_deep_review": None,
            "light_week": {"status": "not_due", "type": None, "reason": None, "week": None, "decision_id": None}},
        "one_off": copy.deepcopy((old_state or {}).get("one_off")),
        "scheme_state": scheme_state,
        "hevy": {
            "routines": {routine_id: {"session_id": session_id}
                         for routine_id, session_id in draft["hevy_routines"].items()},
            "folders": {"program": folder, "one_off": old_folders.get("one_off")},
            "temporary_routines": copy.deepcopy(old_hevy.get("temporary_routines") or []),
        },
    }
    return state, {"kept": kept, "dropped": dropped}


def _readable(load, root, present, warnings):
    """The current document, or None when absent or invalid; an invalid one is archived as it is but carries nothing over."""
    if not present:
        return None
    try:
        return load(root)
    except ValidationError as exc:
        warnings.append(f"{exc.message}; it is archived as it is, and nothing in it carries over")
        return None


def _archive_dir(root, today):
    base = Path(root) / paths.PROGRAM_ARCHIVE_DIR
    candidate, suffix = base / today.isoformat(), 2
    while candidate.exists():
        candidate, suffix = base / f"{today.isoformat()}-{suffix}", suffix + 1
    return candidate


def _grouped(slots):
    found = {}
    for session_id, exercise_id, extra in slots:
        entry = found.setdefault(exercise_id, {"exercise_id": exercise_id, "sessions": [], **extra})
        if session_id not in entry["sessions"]:
            entry["sessions"].append(session_id)
    return list(found.values())


def _unconfirmed(doc, library):
    return _grouped((session["id"], line["exercise_id"], {}) for _, _, session, line in program.slots(doc)
                    if library.effective_load_mode(line["exercise_id"]) is None)


def _avoided(doc, library):
    return _grouped((session_id, exercise_id, {"reason": reason})
                    for session_id, exercise_id, reason in program.avoided_slots(doc, library))


def _as_date(today):
    if today is None:
        return date.today()
    return dates.parse_date(today) if isinstance(today, str) else today


def adopt(root, draft, replace=False, position=None, dry_run=False, today=None):
    """Validate a draft and make it the program: archive the old one, write program and state, render, stage.

    Raises ValidationError (exit 1) for an invalid draft or position,
    RefusedError (exit 3) when a program exists and `replace` is false.
    Never commits and never calls Hevy. The result lists exercises without a
    confirmed load mode, avoided exercises (reported, never swapped) and
    sessions with no Hevy routine.
    """
    root = Path(root)
    today = _as_date(today)
    config = config_module.load(root)
    library = Library.load(root)
    errors = _draft_errors(draft, config, library, root)
    if errors:
        raise ValidationError(f"The program draft is not valid ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    doc = program.normalised(draft["program"])
    registry = plugins.load(root)
    rotation = _rotation(doc, position if position is not None else draft["position"], today, config, registry)

    existing = program.exists(root)
    if existing and not replace:
        raise RefusedError(f"{paths.PROGRAM} already holds a program; adopt with --replace to archive it "
                           f"under {paths.PROGRAM_ARCHIVE_DIR}/{today.isoformat()}/ and replace it")
    warnings = []
    old_program = _readable(program.load, root, existing, warnings)
    old_state = _readable(state_module.load, root, state_module.exists(root), warnings)
    new_state, scheme_report = _new_state(draft, doc, old_state, old_program, rotation, today)
    state_errors = state_module.problems(new_state, doc)
    if state_errors:
        raise ValidationError("The new state is not valid", details=[e.to_json() for e in state_errors])

    archive = _archive_dir(root, today) if existing else None
    archived = [] if archive is None else [
        (archive / source.name).relative_to(root).as_posix()
        for source in (program.path_for(root), state_module.path_for(root)) if source.is_file()]
    pages = program.render_doc(doc, library, config.athlete.units, _status_line(root, new_state, doc))
    result = {
        "program": paths.PROGRAM.as_posix(), "sessions": [s["id"] for s in doc["sessions"]],
        "rotation": rotation, "scheme_state": scheme_report,
        "archived": [], "written": [], "removed": [], "staged": [], "warnings": warnings,
        "unconfirmed": _unconfirmed(doc, library),
        "avoided": _avoided(doc, library),
        "without_routine": [s["id"] for s in doc["sessions"] if s["id"] not in draft["hevy_routines"].values()]
        if config.hevy.enabled else [],
    }
    for item in result["avoided"]:
        result["warnings"].append(
            f"{item['exercise_id']} is marked avoid ({item['reason']}) in the exercise library and is in "
            f"{', '.join(item['sessions'])}; swap it with the athlete")
    if dry_run:
        rendered = program.sync_pages(root, pages, dry_run=True)
        result.update(would_archive=archived, would_write=[paths.PROGRAM.as_posix(), paths.STATE.as_posix()]
                      + rendered["written"], would_remove=rendered["removed"])
        return result

    if archive is not None:
        archive.mkdir(parents=True)
        for relative in archived:
            shutil.copy2(root / paths.DATA_DIR / Path(relative).name, root / relative)
    jsonio.write_doc(program.path_for(root), draft["program"], False)
    jsonio.write_doc(state_module.path_for(root), new_state, False)
    rendered = program.sync_pages(root, pages, dry_run=False)
    result.update(archived=archived, written=[paths.PROGRAM.as_posix(), paths.STATE.as_posix()] + rendered["written"],
                  removed=rendered["removed"])
    result["staged"], warning = migrate.stage(root, archived + result["written"] + result["removed"],
                                              "adopted program files")
    if warning:
        result["warnings"].append(warning)
    return result


def draft_problems(draft, root):
    """The adopt-time problems of a draft's program other than its schedule, for the import's report."""
    root = Path(root)
    config = config_module.load(root)
    errors = _draft_errors(draft, config, Library.load(root), root)
    return [e.to_json() for e in errors if not e.path.startswith("$.program.schedule")]
