"""Resolved workout history, annotations and exposures (contract C17).

`sync` resolves every source workout into `data/history/<YYYY-MM>.json`
once: library exercise id, the load mode in force on that date, and a load
object per set beside the raw `weight_kg`. A stored workout keeps its load
interpretation; only `rebuild` reinterprets. Annotations are applied when
history is read, never written into a month file.
"""

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from coach import config as config_module
from coach import capacity, dates, history_sources, jsonio, overlay, paths, program, state, units
from coach.errors import ValidationError
from coach.history_sources import SourceWorkout
from coach.library import Library
from coach.validate import validate

MONTH_SCHEMA = "history_month"
ANNOTATIONS_SCHEMA = "annotations"
WORKING_SET_TYPES = ("normal", "dropset", "failure")
SET_TYPES = ("normal", "warmup", "dropset", "failure")
MISS_TAGS = ("time", "sleep", "ill", "family", "skipped", "other")
SLIP_RATIOS = (2.0, 0.5)
SLIP_TOLERANCE = 0.01
KIND_FIELDS = {
    "discount": ("workout_id", "exercise_id"),
    "repair": ("workout_id", "exercise_id", "set_index", "field", "value"),
    "load_mode": ("exercise_id", "span", "load_mode"),
    "unknown_convention": ("exercise_id", "span"),
    "confirm": ("workout_id", "exercise_id"),
    "miss": ("date", "session_id"),
    "external": ("date", "external_id", "done"),
    "trained_unlogged": ("date", "session_id"),
}
REPAIR_FIELDS = ("reps", "rpe", "weight_kg", "type")
_MONTH_FILE = re.compile(r"^\d{4}-\d{2}\.json$")
_ANNOTATION_ID = re.compile(r"^a-(\d+)$")


def _timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def history_dir(root):
    return Path(root) / paths.HISTORY_DIR


def month_path(root, month):
    return history_dir(root) / f"{month}.json"


def month_files(root):
    directory = history_dir(root)
    return sorted(p for p in directory.glob("*.json") if _MONTH_FILE.fullmatch(p.name)) if directory.is_dir() else []


def read_month(path):
    doc = jsonio.read_doc(path, MONTH_SCHEMA)
    if Path(path).stem != doc["month"]:
        raise ValidationError(f"{path} holds month {doc['month']}; the file must be named {doc['month']}.json")
    return doc


def _sort_key(record):
    return record["date"], record["start_time"] or "", record["workout_id"]


def stored_workouts(root):
    """Every workout in the month files, as stored (no annotations applied), oldest first."""
    found = [w for path in month_files(root) for w in read_month(path)["workouts"]]
    return sorted(found, key=_sort_key)


def annotations_path(root):
    return Path(root) / paths.ANNOTATIONS


def read_annotations(root):
    """The annotations document, or an empty one when the file does not exist."""
    path = annotations_path(root)
    if not path.is_file():
        return {"schema_version": 1, "annotations": []}
    return jsonio.read_doc(path, ANNOTATIONS_SCHEMA)


def missing_fields(annotation):
    """The fields its kind needs that the annotation lacks. A pure withdrawal needs none."""
    needed = KIND_FIELDS.get(annotation.get("kind"), ())
    absent = [name for name in needed if name not in annotation]
    if "withdraws" in annotation and len(absent) == len(needed):
        return []
    return absent


def _has_effect(annotation):
    needed = KIND_FIELDS.get(annotation["kind"], ())
    return all(name in annotation for name in needed)


def active(all_annotations):
    """The annotations in force: not withdrawn, and carrying their kind's fields."""
    withdrawn = {a["withdraws"] for a in all_annotations if "withdraws" in a}
    return [a for a in all_annotations if a["id"] not in withdrawn and _has_effect(a)]


def created_by(annotation, as_of):
    """True when the annotation existed at `as_of` (an aware datetime; None means now)."""
    return as_of is None or dates.parse_timestamp(annotation["created_at"]) <= as_of


def annotations(root, kind=None, as_of=None):
    """The annotations in force, optionally of one kind, in file order; with `as_of`, as they stood then."""
    found = active([a for a in read_annotations(root)["annotations"] if created_by(a, as_of)])
    return [a for a in found if kind is None or a["kind"] == kind]


def next_annotation_id(doc):
    numbers = [int(m.group(1)) for a in doc["annotations"] for m in [_ANNOTATION_ID.match(a["id"])] if m]
    return f"a-{max(numbers, default=0) + 1:04d}"


def add_annotations(root, items, now, dry_run=False, batch=True):
    """Check and append annotations to the annotations file in one write; returns them with ids and created_at.

    Raises ValidationError naming every problem (paths `$[n]` for a batch, `$` for one) and writes nothing then.
    """
    doc = read_annotations(root)
    checker = Checker(root)
    created_at = _timestamp(now)
    details, added = [], []
    for position, item in enumerate(items):
        fields = {k: v for k, v in item.items() if k not in ("id", "created_at")}
        annotation = {"id": next_annotation_id(doc), "kind": fields.pop("kind", None), **fields,
                      "created_at": created_at}
        where = f"$[{position}]" if batch else "$"
        tag = annotation.get("tag")
        if tag is not None and tag not in MISS_TAGS:
            raise ValidationError(f"tag {tag!r} is not a miss tag; use one of {', '.join(MISS_TAGS)}")
        errors = validate({"schema_version": 1, "annotations": [annotation]}, jsonio.load_schema(ANNOTATIONS_SCHEMA))
        details += [{"path": where + e.path.replace("$.annotations[0]", ""), "message": e.message} for e in errors]
        if not errors:
            details += [{"path": where, "message": m} for m in checker.problems(annotation, doc["annotations"])]
        doc["annotations"].append(annotation)
        added.append(annotation)
    if details:
        raise ValidationError(f"the annotation is not valid ({len(details)} problem(s)): {details[0]['message']}",
                              details=details)
    jsonio.write_doc(annotations_path(root), doc, dry_run)
    return added


def _in_span(span, day):
    return span["start"] <= day <= span["end"]


@dataclass
class _Env:
    root: Path
    unit: str
    tz: object
    library: Library
    overlays: list
    state: dict
    program: dict
    annotations: list
    now: datetime

    @classmethod
    def load(cls, root, now=None, as_of=None):
        root = Path(root)
        config = config_module.load(root)
        zone_name = config.athlete.timezone
        return cls(
            root=root, unit=config.athlete.units, tz=dates.zone(zone_name) if zone_name else None,
            library=Library.load(root), overlays=overlay.list(root),
            state=load_optional(state, root), program=load_optional(program, root),
            annotations=annotations(root, as_of=as_of), now=now or datetime.now(timezone.utc),
        )

    def local_date(self, timestamp):
        return dates.parse_timestamp(timestamp).astimezone(self.tz).date().isoformat()


def load_optional(module, root):
    """The program or state document, or None when it is absent or invalid (its own check reports why)."""
    if not module.exists(root):
        return None
    try:
        return module.load(root)
    except ValidationError:
        return None


def routine_of(doc, session, state_doc):
    """The Hevy routine a session of an overlay uses: its own id, else the one state maps it to (C12)."""
    if session.get("hevy_routine_id"):
        return session["hevy_routine_id"]
    if not state_doc:
        return None
    hevy = state_doc.get("hevy", {})
    if session.get("temporary"):
        return next((t["routine_id"] for t in hevy.get("temporary_routines", [])
                     if t["overlay_id"] == doc["id"] and t["session_id"] == session["session_id"]), None)
    return next((rid for rid, mapped in sorted(hevy.get("routines", {}).items())
                 if mapped.get("session_id") == session["session_id"]), None)


def _matching_session(env, routine_id, day):
    """(overlay, session) of the overlay in force on `day` whose session carries `routine_id`, or (None, None)."""
    if not routine_id:
        return None, None
    found = overlay.pick_in_force(env.overlays, day)
    if not found:
        return None, None
    doc = found[0]
    carrying = [s for s in doc["sessions"] if routine_of(doc, s, env.state) == routine_id]
    if not carrying:
        return None, None
    target = dates.parse_date(day)
    session = min(carrying, key=lambda s: (abs((dates.parse_date(s["date"]) - target).days), s["date"]))
    return doc, session


def _annotated_mode(env, exercise_id, day):
    covering = [a for a in env.annotations if a["kind"] == "load_mode" and a["exercise_id"] == exercise_id
                and _in_span(a["span"], day)]
    return covering[-1]["load_mode"] if covering else None


def _fresh_mode(env, exercise_id, day, session):
    annotated = _annotated_mode(env, exercise_id, day)
    if annotated:
        return annotated, "annotation"
    if session:
        line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)
        if line and line.get("load_mode"):
            return line["load_mode"], "overlay"
    confirmed = env.library.effective_load_mode(exercise_id)
    if confirmed:
        return confirmed, "library"
    return None, None


def _exercise_key(exercise):
    return exercise["exercise_id"] or f"template:{exercise['hevy_template_id']}"


def _frozen_modes(record):
    """The load modes a stored workout resolved, kept across a re-resolve (C17 freezing)."""
    return {_exercise_key(e): (e["load_mode"], e["load_mode_source"])
            for e in record["exercises"] if e["load_mode"] is not None}


def hevy_load(weight_kg, load_mode, unit):
    """The load object for a raw Hevy `weight_kg` under a load mode, or None."""
    if load_mode not in units.LOADED_MODES:
        return None
    if weight_kg is None:
        return units.make_load(0, load_mode, unit) if load_mode == "bodyweight" else None
    value = round(units.from_hevy_kg(weight_kg, load_mode, unit), 2)
    return units.make_load(value, load_mode, unit)


def _match_exercise(env, raw):
    if raw.get("exercise_id"):
        return raw["exercise_id"]
    entry = env.library.by_hevy_template_id(raw["hevy_template_id"]) if raw.get("hevy_template_id") else None
    if entry is None and raw.get("title"):
        entry, _ = env.library.match_title(raw["title"])
    return entry["id"] if entry else None


def resolve(source_workout, env, frozen=None, version=""):
    """The month-file record for a source workout."""
    sw = source_workout
    day = sw.date or env.local_date(sw.start_time)
    manual = sw.source != "hevy"
    if manual:
        overlay_id, session_id = sw.overlay_id, sw.session_id
        doc = next((o for o in env.overlays if o["id"] == overlay_id), None)
        session = next((s for s in doc["sessions"] if s["session_id"] == session_id), None) if doc else None
    else:
        doc, session = _matching_session(env, sw.routine_id, day)
        overlay_id = doc["id"] if doc else None
        session_id = session["session_id"] if session else None

    minutes = sw.duration_minutes
    if minutes is None and sw.start_time and sw.end_time:
        elapsed = dates.parse_timestamp(sw.end_time) - dates.parse_timestamp(sw.start_time)
        minutes = max(0, round(elapsed.total_seconds() / 60))

    exercises = []
    for raw in sw.exercises:
        exercise_id = _match_exercise(env, raw)
        if raw.get("load_mode"):
            mode, mode_source = raw["load_mode"], "log"
        elif exercise_id is None:
            mode, mode_source = None, None
        else:
            mode, mode_source = _fresh_mode(env, exercise_id, day, session)
            kept = (frozen or {}).get(_exercise_key({"exercise_id": exercise_id,
                                                      "hevy_template_id": raw.get("hevy_template_id")}))
            if kept and mode_source != "annotation" and kept[1] != "annotation":
                mode, mode_source = kept
        sets = []
        for logged in raw["sets"]:
            if mode_source == "log":
                value = logged.get("value")
                loaded = value is not None and mode in units.LOADED_MODES
                load = units.make_load(value, mode, raw["unit"]) if loaded else None
            else:
                load = hevy_load(logged.get("weight_kg"), mode, env.unit)
            sets.append({"index": logged["index"], "type": logged["type"], "reps": logged.get("reps"),
                         "rpe": logged.get("rpe"), "weight_kg": logged.get("weight_kg"), "load": load,
                         "duration_seconds": logged.get("duration_seconds"),
                         "distance_meters": logged.get("distance_meters")})
        exercises.append({"exercise_id": exercise_id, "title": raw.get("title") or "",
                          "hevy_template_id": raw.get("hevy_template_id"), "load_mode": mode,
                          "load_mode_source": mode_source, "notes": raw.get("notes") or "", "sets": sets})

    return {
        "workout_id": sw.workout_id, "source": sw.source, "source_version": version,
        "hevy_updated_at": sw.hevy_updated_at, "resolved_at": _timestamp(env.now), "date": day,
        "start_time": sw.start_time, "end_time": sw.end_time, "duration_minutes": minutes, "title": sw.title,
        "description": sw.description, "routine_id": sw.routine_id, "session_id": session_id,
        "overlay_id": overlay_id, "exercises": exercises,
    }


def _source_from_record(record):
    """A stored Hevy workout as its source gave it, so it can be resolved again without the cache."""
    exercises = [{
        "exercise_id": None, "title": e["title"], "hevy_template_id": e["hevy_template_id"], "load_mode": None,
        "unit": None, "notes": e["notes"],
        "sets": [dict(s, value=None) for s in e["sets"]],
    } for e in record["exercises"]]
    return SourceWorkout(
        source=record["source"], workout_id=record["workout_id"], date=record["date"],
        start_time=record["start_time"], end_time=record["end_time"], duration_minutes=record["duration_minutes"],
        title=record["title"], description=record["description"], routine_id=record["routine_id"],
        hevy_updated_at=record["hevy_updated_at"], exercises=exercises,
    )


def _needs_reinterpreting(env, record):
    """True when a load_mode annotation now covers an exercise differently from how it was stored."""
    if record["source"] != "hevy":
        return False
    for exercise in record["exercises"]:
        if exercise["exercise_id"] is None:
            continue
        annotated = _annotated_mode(env, exercise["exercise_id"], record["date"])
        if annotated and (exercise["load_mode"], exercise["load_mode_source"]) != (annotated, "annotation"):
            return True
        if not annotated and exercise["load_mode_source"] == "annotation":
            return True
    return False


def _mode_changes(before, after):
    old = {_exercise_key(e): e["load_mode"] for e in before["exercises"]}
    return [{"exercise_id": e["exercise_id"], "from": old.get(_exercise_key(e)), "to": e["load_mode"]}
            for e in after["exercises"] if old.get(_exercise_key(e)) != e["load_mode"]]


def _unresolved(records):
    return [{"workout_id": r["workout_id"], "date": r["date"], "title": e["title"], "exercise_id": e["exercise_id"]}
            for r in records for e in r["exercises"] if e["exercise_id"] is None or e["load_mode"] is None]


def _month_docs(records):
    months = {}
    for record in records:
        months.setdefault(record["date"][:7], []).append(record)
    return {month: {"schema_version": 1, "month": month, "workouts": sorted(found, key=_sort_key)}
            for month, found in months.items()}


def _write_months(root, before, after, dry_run):
    """Write each month whose text changed; return the months written (or that would be)."""
    schema = jsonio.load_schema(MONTH_SCHEMA)
    old_docs, new_docs = _month_docs(before), _month_docs(after)
    for month in old_docs:
        new_docs.setdefault(month, {"schema_version": 1, "month": month, "workouts": []})
    written = []
    for month in sorted(new_docs):
        doc = new_docs[month]
        errors = validate(doc, schema)
        if errors:
            raise ValidationError(f"the resolved history for {month} is not valid ({len(errors)} problem(s))",
                                  details=[e.to_json() for e in errors])
        path = month_path(root, month)
        if path.is_file() and path.read_text(encoding="utf-8") == jsonio.dumps(doc):
            continue
        jsonio.write_doc(path, doc, dry_run)
        written.append(month)
    return written


def sync(root, now=None, dry_run=False):
    """Resolve new and changed source workouts into the month files; report what changed."""
    env = _Env.load(root, now)
    before = stored_workouts(root)
    stored = {r["workout_id"]: r for r in before}
    records = dict(stored)
    added, updated, removed, reinterpreted = [], [], [], []

    for name, module in history_sources.discover().items():
        found = module.workouts(root)
        if found is None:
            continue
        seen = set()
        for source_workout in found:
            seen.add(source_workout.workout_id)
            version = module.version(source_workout)
            old = stored.get(source_workout.workout_id)
            if old is None:
                records[source_workout.workout_id] = resolve(source_workout, env, version=version)
                added.append(source_workout.workout_id)
            elif old["source_version"] != version:
                records[source_workout.workout_id] = resolve(source_workout, env, _frozen_modes(old), version)
                updated.append(source_workout.workout_id)
        for workout_id, record in stored.items():
            if record["source"] == name and workout_id not in seen:
                del records[workout_id]
                removed.append(workout_id)

    touched = set(added) | set(updated)
    for workout_id, record in sorted(records.items()):
        if workout_id in touched or not _needs_reinterpreting(env, record):
            continue
        again = resolve(_source_from_record(record), env, _frozen_modes(record), record["source_version"])
        records[workout_id] = again
        reinterpreted.append({"workout_id": workout_id, "date": record["date"],
                              "exercises": _mode_changes(record, again)})
        touched.add(workout_id)

    after = sorted(records.values(), key=_sort_key)
    written = _write_months(root, before, after, dry_run)
    return {
        "added": added, "updated": updated, "removed": sorted(removed), "reinterpreted": reinterpreted,
        "unchanged": len(after) - len(touched), "months_written": written,
        "unresolved": _unresolved([r for r in after if r["workout_id"] in touched]), "dry_run": dry_run,
    }


def rebuild(root, month, now=None, dry_run=False):
    """Re-resolve one month's workouts under the current rules; report every per-set difference."""
    path = month_path(root, month)
    if not path.is_file():
        raise ValidationError(f"No history for {month}: {path} does not exist")
    env = _Env.load(root, now)
    doc = read_month(path)
    rebuilt, differences = [], []
    for record in doc["workouts"]:
        if record["source"] != "hevy":
            rebuilt.append(record)
            continue
        again = resolve(_source_from_record(record), env, version=record["source_version"])
        found = _set_differences(record, again)
        differences += found
        rebuilt.append(again if found else record)
    written = False
    if differences:
        others = [r for r in stored_workouts(root) if r["date"][:7] != month]
        written = bool(_write_months(root, others + doc["workouts"], others + rebuilt, dry_run)) and not dry_run
    return {"month": month, "differences": differences, "written": written, "dry_run": dry_run}


def _set_differences(before, after):
    found = []
    for old_exercise, new_exercise in zip(before["exercises"], after["exercises"]):
        for old_set, new_set in zip(old_exercise["sets"], new_exercise["sets"]):
            old = {"exercise_id": old_exercise["exercise_id"], "load_mode": old_exercise["load_mode"],
                   "load": old_set["load"]}
            new = {"exercise_id": new_exercise["exercise_id"], "load_mode": new_exercise["load_mode"],
                   "load": new_set["load"]}
            if old != new:
                found.append({"workout_id": before["workout_id"], "date": before["date"],
                              "exercise_id": new["exercise_id"] or old["exercise_id"], "title": new_exercise["title"],
                              "set_index": new_set["index"], "before": old, "after": new})
    return found


def _unsynced(root, env, stored_ids):
    found = []
    for module in history_sources.discover().values():
        for source_workout in module.workouts(root) or []:
            if source_workout.workout_id not in stored_ids:
                found.append(resolve(source_workout, env, version=module.version(source_workout)))
    return found


def is_conditioning(record, program_doc):
    """True when the workout's session is a `kind: conditioning` session of the program (C17)."""
    if not program_doc or not record.get("session_id"):
        return False
    session = next((s for s in program_doc["sessions"] if s["id"] == record["session_id"]), None)
    return bool(session) and session["kind"] == "conditioning"


def _apply_annotations(record, found, unit):
    workout = copy.deepcopy(record)
    for exercise in workout["exercises"]:
        exercise["discounted"] = False
        exercise["convention_unknown"] = False
        for logged in exercise["sets"]:
            logged.update(discounted=False, convention_unknown=False, repaired=[])

    def sets_of(annotation):
        exercise = next((e for e in workout["exercises"] if e["exercise_id"] == annotation["exercise_id"]), None)
        if exercise is None:
            return None, []
        index = annotation.get("set_index")
        return exercise, [s for s in exercise["sets"] if index is None or s["index"] == index]

    for annotation in found:
        kind = annotation["kind"]
        if kind in ("repair", "discount") and annotation["workout_id"] == workout["workout_id"]:
            exercise, chosen = sets_of(annotation)
            for logged in chosen:
                if kind == "discount":
                    logged["discounted"] = True
                    continue
                field, value = annotation["field"], annotation["value"]
                logged[field] = value
                logged["repaired"].append(field)
                if field == "weight_kg":
                    logged["load"] = hevy_load(value, exercise["load_mode"], unit)
            if kind == "discount" and exercise is not None and annotation.get("set_index") is None:
                exercise["discounted"] = True
        elif kind == "unknown_convention" and _in_span(annotation["span"], workout["date"]):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == annotation["exercise_id"]:
                    exercise["convention_unknown"] = True
                    for logged in exercise["sets"]:
                        logged["convention_unknown"] = True
    return workout


def _started_by(record, as_of, env):
    if as_of is None:
        return True
    if record.get("start_time"):
        return dates.parse_timestamp(record["start_time"]) <= as_of
    return record["date"] <= as_of.astimezone(env.tz).date().isoformat()


def workouts(root, since=None, until=None, include_unsynced=False, now=None, as_of=None):
    """Resolved workouts with annotations applied, oldest first.

    With include_unsynced, source workouts not yet in a month file are
    resolved in memory and returned with `unsynced: true`; nothing is written.
    With `as_of`, only workouts started and annotations created by then count.
    """
    env = _Env.load(root, now, as_of)
    records = [dict(r, unsynced=False) for r in stored_workouts(root)]
    if include_unsynced:
        stored_ids = {r["workout_id"] for r in records}
        records += [dict(r, unsynced=True) for r in _unsynced(root, env, stored_ids)]
    since = str(since) if since else None
    until = str(until) if until else None
    chosen = [r for r in sorted(records, key=_sort_key)
              if (since is None or r["date"] >= since) and (until is None or r["date"] <= until)
              and _started_by(r, as_of, env)]
    result = []
    for record in chosen:
        workout = _apply_annotations(record, env.annotations, env.unit)
        workout["conditioning"] = is_conditioning(record, env.program)
        result.append(workout)
    return result


def coaching_number(load):
    """The number a coach reads off a load: per hand for per-hand modes, else the total (C18)."""
    if load is None:
        return None
    return load["per_hand"] if load["mode"] in units.PER_HAND_MODES else load["hevy_total"]


def _exposures_of(found_workouts):
    exposures = []
    for workout in found_workouts:
        if workout["conditioning"]:
            continue
        for exercise in workout["exercises"]:
            working = [s for s in exercise["sets"] if s["type"] in WORKING_SET_TYPES]
            if exercise["exercise_id"] is None or not working:
                continue
            exposures.append({
                "date": workout["date"], "workout_id": workout["workout_id"], "session_id": workout["session_id"],
                "exercise_id": exercise["exercise_id"], "load_mode": exercise["load_mode"], "sets": working,
                "overlay_id": workout.get("overlay_id"),
                "suspect": False, "excluded": exercise["discounted"] or exercise["convention_unknown"],
                "discounted": exercise["discounted"], "convention_unknown": exercise["convention_unknown"],
            })
    return exposures


def _top_set(exposure):
    usable = [s for s in exposure["sets"]
              if (exposure["discounted"] or not s["discounted"]) and coaching_number(s["load"])]
    return max(usable, key=lambda s: coaching_number(s["load"])) if usable else None


def _closing(found, workout_id, exercise_id):
    closing = [a for a in found if a["kind"] in ("discount", "confirm") and a["workout_id"] == workout_id
               and a["exercise_id"] == exercise_id]
    return closing[-1] if closing else None


def slip_candidates(exposures, found_annotations):
    """Convention-slip candidates over a list of exposures (C18 audit), oldest first.

    A candidate is a per-hand exposure whose top working load is 2× or ½×
    (±1 %) the previous usable exposure's, at the same top-set reps and RPE.
    Exposures in an unknown_convention span are skipped; discounted
    exposures and open or discounted candidates are never baselines.
    """
    candidates = []
    by_exercise = {}
    for exposure in sorted(exposures, key=lambda e: (e["date"], e["workout_id"])):
        if exposure["load_mode"] in units.PER_HAND_MODES and not exposure["convention_unknown"]:
            by_exercise.setdefault(exposure["exercise_id"], []).append(exposure)
    for exercise_id, found in by_exercise.items():
        baseline = None
        for exposure in found:
            top = _top_set(exposure)
            if top is None:
                continue
            candidate = None
            if baseline is not None:
                base_top = baseline[1]
                ratio = coaching_number(top["load"]) / coaching_number(base_top["load"])
                if (any(abs(ratio - r) <= r * SLIP_TOLERANCE for r in SLIP_RATIOS)
                        and top["reps"] == base_top["reps"] and top["rpe"] == base_top["rpe"]):
                    closing = _closing(found_annotations, exposure["workout_id"], exercise_id)
                    status = "open" if closing is None else ("confirmed" if closing["kind"] == "confirm"
                                                             else "discounted")
                    candidate = {
                        "exercise_id": exercise_id, "date": exposure["date"], "workout_id": exposure["workout_id"],
                        "session_id": exposure["session_id"], "load_mode": exposure["load_mode"],
                        "top_load": coaching_number(top["load"]), "reps": top["reps"], "rpe": top["rpe"],
                        "ratio": round(ratio, 2),
                        "previous": {"date": baseline[0]["date"], "workout_id": baseline[0]["workout_id"],
                                     "top_load": coaching_number(base_top["load"])},
                        "status": status, "annotation_id": closing["id"] if closing else None, "siblings": [],
                    }
                    candidates.append(candidate)
            usable = candidate is None or candidate["status"] == "confirmed"
            if usable and not exposure["discounted"]:
                baseline = (exposure, top)
    for candidate in candidates:
        candidate["siblings"] = sorted(c["exercise_id"] for c in candidates
                                       if c["date"] == candidate["date"] and c is not candidate)
    return sorted(candidates, key=lambda c: (c["date"], c["exercise_id"]))


def all_exposures(root, include_unsynced=False, now=None, as_of=None):
    """Every exposure, oldest first, with `suspect` set from open convention-slip candidates."""
    found = workouts(root, include_unsynced=include_unsynced, now=now, as_of=as_of)
    exposures = _exposures_of(found)
    found_annotations = annotations(root, as_of=as_of)
    open_slips = {(c["workout_id"], c["exercise_id"]) for c in slip_candidates(exposures, found_annotations)
                  if c["status"] == "open"}
    context = capacity.Context(root, as_of)
    for exposure in exposures:
        exposure["capacity_context"] = context.for_exposure(exposure)
        exposure["suspect"] = (exposure["workout_id"], exposure["exercise_id"]) in open_slips
    return exposures


def exposures(root, exercise_id, before=None, include_unsynced=False, now=None):
    """One exercise's exposures, newest first; `before` (a date) keeps those dated earlier."""
    before = str(before) if before else None
    found = [e for e in all_exposures(root, include_unsynced, now) if e["exercise_id"] == exercise_id
             and (before is None or e["date"] < before)]
    return sorted(found, key=lambda e: (e["date"], e["workout_id"]), reverse=True)


def _is_lifting(exercise, library):
    if exercise["exercise_id"] is None:
        return False
    entry = library.get(exercise["exercise_id"])
    return entry is not None and entry["pattern"] != "conditioning"


def last_lifting_date(root, before, include_unsynced=False, now=None):
    """The newest workout date before `before` with a lifting exercise, or None."""
    library = Library.load(root)
    before = str(before)
    dated = [w["date"] for w in workouts(root, include_unsynced=include_unsynced, now=now)
             if w["date"] < before and not w["conditioning"]
             and any(_is_lifting(e, library) for e in w["exercises"])]
    return dates.parse_date(max(dated)) if dated else None


def _known_sessions(program_doc, overlays):
    found = {s["id"] for s in program_doc["sessions"]} if program_doc else set()
    return found | {s["session_id"] for doc in overlays for s in doc["sessions"]}


def _value_problem(field, value):
    if field == "type":
        return None if value in SET_TYPES else f"a repaired type must be one of {', '.join(SET_TYPES)}"
    if field == "rpe" and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"a repaired {field} must be a number"
    if field == "reps" and (value < 0 or value != int(value)):
        return "repaired reps must be a whole number, 0 or more"
    if field == "rpe" and not 1 <= value <= 10:
        return "a repaired rpe must be from 1 to 10"
    if field == "weight_kg" and value < 0:
        return "a repaired weight_kg must not be negative"
    return None


class Checker:
    """Checks annotations against the instance: references exist, values fit (C17 `annotations_valid`)."""

    def __init__(self, root):
        self.root = Path(root)
        self.records = {r["workout_id"]: r for r in stored_workouts(root)}
        self.program = load_optional(program, root)
        self.overlays = overlay.list(root)
        self.library = Library.load(root)
        self.sessions = _known_sessions(self.program, self.overlays)

    def problems(self, annotation, existing=()):
        """Plain-sentence problems with one annotation; `existing` are the annotations already on file."""
        found = []
        kind = annotation.get("kind")
        missing = missing_fields(annotation)
        if missing:
            found.append(f"a {kind} annotation needs {', '.join(missing)}")
        if "tag" in annotation and annotation["tag"] is not None and annotation["tag"] not in MISS_TAGS:
            found.append(f"tag {annotation['tag']!r} is not one of {', '.join(MISS_TAGS)}")
        if "withdraws" in annotation:
            target = next((a for a in existing if a["id"] == annotation["withdraws"]), None)
            if target is None:
                found.append(f"it withdraws {annotation['withdraws']}, which is not on file")
            elif target["kind"] != kind:
                found.append(f"it withdraws {target['id']}, a {target['kind']} annotation, but is a {kind} one")
        record = None
        if "workout_id" in annotation:
            record = self.records.get(annotation["workout_id"])
            if record is None:
                found.append(f"workout {annotation['workout_id']} is not in {paths.HISTORY_DIR}; "
                             "run python3 -m coach history sync first")
        if record is not None and "exercise_id" in annotation:
            exercise = next((e for e in record["exercises"] if e["exercise_id"] == annotation["exercise_id"]), None)
            if exercise is None:
                found.append(f"workout {record['workout_id']} has no exercise {annotation['exercise_id']}")
            elif annotation.get("set_index") is not None and not any(
                    s["index"] == annotation["set_index"] for s in exercise["sets"]):
                found.append(f"{annotation['exercise_id']} in workout {record['workout_id']} has no set "
                             f"{annotation['set_index']}")
        elif "workout_id" not in annotation and "exercise_id" in annotation:
            if self.library.get(annotation["exercise_id"]) is None:
                found.append(f"exercise {annotation['exercise_id']} is not in the exercise library")
        if kind == "repair" and annotation.get("set_index") is None and "set_index" in annotation:
            found.append("a repair names one set (--set)")
        if kind == "repair" and "field" in annotation and "value" in annotation:
            problem = _value_problem(annotation["field"], annotation["value"])
            if problem:
                found.append(problem)
        if "span" in annotation and annotation["span"]["start"] > annotation["span"]["end"]:
            found.append("its span ends before it starts")
        if "session_id" in annotation and self.sessions and annotation["session_id"] not in self.sessions:
            found.append(f"session {annotation['session_id']} is not in the program or any overlay")
        if "external_id" in annotation and self.program is not None:
            externals = {s["id"] for s in self.program["external_sessions"]}
            if annotation["external_id"] not in externals:
                found.append(f"{annotation['external_id']} is not a coach-led session of the program")
        return found
