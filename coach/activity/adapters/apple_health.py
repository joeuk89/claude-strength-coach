"""Apple Health through Health Auto Export's Version 2 JSON files (contract C31, C32).

`activity sync` reads every new `*.json` file under `[sources.apple_health]
path` (iCloud Drive's AutoExport folder, which holds one folder per
automation) in place; `activity import` reads one file, such as a 90-day
manual export. Workouts become Activities and daily metrics become one
wellness record per day. Lifting workouts, and workouts
an app in `drop_source_names` wrote, are dropped with a counted reason.
"""

import os
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

from coach import dates, units
from coach.activity import health_auto_export as hae
from coach.activity import records
from coach.activity.adapters import Drop, FetchResult
from coach.activity.store import WELLNESS_FIELDS, ActivityStore
from coach.config import Key
from coach.errors import ConfigError, ValidationError
from coach.hevy.cache import HevyCache

NAME = "apple_health"
KINDS = ("activity", "wellness")
NETWORK = False
CONFIG = {
    "enabled": Key("boolean", default=False),
    "path": Key("string", default=""),
    "drop_source_names": Key("list", default=["Hevy"], item="string"),
}

# Every mapping the vendor docs do not pin down lives here, so a check
# against a real export corrects one table. Workout kinds: the first entry
# whose words appear in the lower-cased workout name wins; "lifting" drops it.
MAPPING = {
    "workout_kinds": (
        (("strength", "core training"), "lifting"),
        (("run",), "run"),
        (("cycl", "bike", "biking"), "ride"),
        (("swim",), "swim"),
        (("row",), "row"),
        (("walk",), "walk"),
        (("hik",), "hike"),
        (("interval", "cardio", "cross training", "elliptical", "stair", "jump rope", "boxing",
          "kickboxing", "bootcamp", "circuit"), "conditioning"),
        (("yoga", "pilates", "flexibility", "cooldown", "mind and body", "tai chi", "stretch",
          "mobility", "barre"), "mobility"),
        (("soccer", "football", "tennis", "basketball", "badminton", "squash", "golf", "hockey",
          "rugby", "volleyball", "cricket", "climbing", "martial arts", "skiing", "snowboarding",
          "table tennis", "padel", "pickleball", "baseball", "softball", "lacrosse"), "sport"),
    ),
    "indoor_locations": {"Indoor": True, "Pool": True, "Outdoor": False, "Open Water": False},
    # metric name -> (wellness field, how a day's entries combine, accepted units)
    "metrics": {
        "sleep_analysis": ("sleep", "sleep", ("hr",)),
        "resting_heart_rate": ("resting_hr_bpm", "last", ("bpm", "count/min")),
        "heart_rate_variability": ("hrv_ms", "last", ("ms",)),
        "step_count": ("steps", "sum", ("count",)),
        "weight_&_body_mass": ("body_mass_kg", "last", ("kg", "lb")),
        "weight_body_mass": ("body_mass_kg", "last", ("kg", "lb")),
        "body_fat_percentage": ("body_fat_pct", "last", ("%",)),
    },
    # Aggregated sleep_analysis entries: asleep is totalSleep (Health Auto
    # Export's "asleep" is the uncategorised phase only), in bed is inBed when
    # above zero, and the night belongs to the date of sleepEnd, else `date`.
    "sleep": {
        "asleep_hours": ("totalSleep", "asleep"),
        "in_bed_hours": ("inBed",),
        "start": "sleepStart",
        "end": "sleepEnd",
        "day_from": ("sleepEnd", "date"),
    },
}

LIFTING = "lifting workout; Hevy is the lifting logbook"
NEAR_HEVY = "no source, and it starts within {minutes} minutes of a Hevy workout"
WRITTEN_BY = "written to Apple Health by {app}, which is in drop_source_names"
BAD_ID = "workout id cannot be used in a record id"
_ID = re.compile(r"^[A-Za-z0-9._:-]+$")


def workout_kind(name):
    """The C30 kind for a Health Auto Export workout name, or "lifting"."""
    text = (name or "").lower()
    for words, kind in MAPPING["workout_kinds"]:
        if any(word in text for word in words):
            return kind
    return "other"


def sleep_day(entry):
    """The date the athlete woke, for an aggregated sleep_analysis entry; None when it has no usable date."""
    for key in MAPPING["sleep"]["day_from"]:
        try:
            return hae.day_of(entry.get(key))
        except ValueError:
            continue
    return None


def _folder(ctx):
    text = ctx.config["sources"][NAME]["path"]
    if not text:
        raise ConfigError(f"[sources.{NAME}] path is empty in config.toml; set it to the Health Auto Export folder")
    folder = Path(os.path.expanduser(text))
    if not folder.is_absolute():
        folder = ctx.root / folder
    if not folder.is_dir():
        raise ConfigError(f"[sources.{NAME}] path {text!r} is not a folder; check the Health Auto Export folder")
    return folder


def _folder_files(folder):
    """Every file under folder, as (path, key relative to folder), skipping hidden folders; sorted by key."""
    found = []
    for parent, subfolders, names in os.walk(folder):
        subfolders[:] = [name for name in subfolders if not name.startswith(".")]
        for name in names:
            path = Path(parent) / name
            found.append((path, path.relative_to(folder).as_posix()))
    return sorted(found, key=lambda pair: pair[1])


def fetch(ctx, sync_state):
    folder = _folder(ctx)
    files = dict(sync_state.get("files", {}))
    seen = set(files.values())
    warnings, exports, read = [], [], []
    for path, key in _folder_files(folder):
        if not path.is_file():
            continue
        if hae.is_placeholder(path.name):
            warnings.append(hae.placeholder_message(path))
            continue
        if path.suffix.lower() == ".csv":
            warnings.append(hae.csv_message(path.name))
            continue
        if path.suffix.lower() != ".json" or path.name.startswith("."):
            continue
        digest = hae.file_hash(path)
        if digest in seen:
            continue
        try:
            exports.append(hae.read_export(path))
        except ValidationError as exc:
            warnings.append(exc.message)
            continue
        files[key] = digest
        read.append(key)
    items, more = _items(ctx, exports)
    return FetchResult(items, {"files": files}, warnings + more, info={"files_read": read})


def fetch_file(ctx, path, sync_state):
    path = Path(path)
    if hae.is_placeholder(path.name):
        raise ValidationError(hae.placeholder_message(path))
    if not path.is_file():
        raise ValidationError(f"{path} is not a file")
    files = dict(sync_state.get("files", {}))
    digest = hae.file_hash(path)
    if digest in files.values():
        return FetchResult([], {"files": files}, [f"{path.name} was imported before; nothing to do"],
                           info={"file": path.name, "already_seen": True})
    data = hae.read_export(path)
    files[path.name] = digest
    items, warnings = _items(ctx, [data])
    return FetchResult(items, {"files": files}, warnings, info={"file": path.name, "already_seen": False})


def anonymise(ctx, path, out_dir, dry_run):
    return hae.anonymise(path, out_dir, dry_run=dry_run)


def _items(ctx, exports):
    warnings = _Warnings()
    workouts = {}
    days = {}
    for data in exports:
        for raw in data.get("workouts", []):
            workouts[str(raw["id"])] = raw
        for metric in data.get("metrics", []):
            if isinstance(metric, dict):
                _add_metric(metric, days, warnings)
    hevy_starts = _hevy_starts(ctx, workouts.values(), warnings)
    items = [_workout_item(raw, hevy_starts, warnings) for raw in workouts.values()]
    previous = ActivityStore(ctx.root, ctx.config).latest("wellness") if days else {}
    for day in sorted(days):
        found = days[day]
        last = previous.get(f"{NAME}:{day}")
        items.append({"type": "day", "date": day, "readings": found["readings"],
                      "devices": sorted(found["devices"]),
                      "previous": last if last is not None and last["op"] == "upsert" else None})
    return items, warnings.lines()


def _hevy_starts(ctx, workouts, warnings):
    """Start times of cached Hevy workouts, when sourceless workouts need checking against them."""
    names = [n.lower() for n in ctx.config["sources"][NAME]["drop_source_names"]]
    if "hevy" not in names or not any(not w.get("source") for w in workouts):
        return []
    cache = HevyCache(ctx.root)
    if cache.meta() is None:
        if ctx.config["hevy"]["enabled"]:
            warnings.once("there is no Hevy cache, so workouts without a source were not checked against Hevy "
                          "workouts; run python3 -m coach hevy pull")
        return []
    return [dates.parse_timestamp(w["start_time"]) for w in cache.workouts() if w.get("start_time")]


def _workout_item(raw, hevy_starts, warnings):
    item = {"type": "workout", "raw": raw, "kind": workout_kind(raw.get("name")), "hevy_gaps": []}
    try:
        start = hae.parse_time(raw.get("start"))
        end = hae.parse_time(raw["end"]) if raw.get("end") else None
    except ValueError:
        item["kind"] = None
        return item
    item.update(start=start, end=end)
    item["hevy_gaps"] = [abs(start - hevy) for hevy in hevy_starts] if not raw.get("source") else []
    item["fields"] = {
        "distance_meters": _quantity(raw.get("distance"), units.to_meters, "distance", warnings),
        "elevation_gain_meters": _quantity(raw.get("elevationUp"), units.to_meters, "elevationUp", warnings),
        "active_kcal": _quantity(raw.get("activeEnergyBurned"), units.energy_kcal, "activeEnergyBurned", warnings),
        "avg_hr": _heart_rate(raw, "avg", "avgHeartRate"),
        "max_hr": _heart_rate(raw, "max", "maxHeartRate"),
    }
    return item


def _quantity(value, convert, label, warnings):
    if not isinstance(value, dict) or value.get("qty") is None:
        return None
    try:
        return convert(value["qty"], value.get("units"))
    except ValueError as exc:
        warnings.count(f"left out workout {label} readings it cannot convert ({exc})")
        return None


def _heart_rate(raw, key, fallback):
    overall = raw.get("heartRate")
    summary = (overall.get(key) if isinstance(overall, dict) else None) or raw.get(fallback)
    value = summary.get("qty") if isinstance(summary, dict) else None
    return round(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else None


def _add_metric(metric, days, warnings):
    name = metric.get("name")
    spec = MAPPING["metrics"].get(name)
    if spec is None:
        warnings.unknown(name)
        return
    field, how, accepted = spec
    unit = metric.get("units")
    if unit not in accepted:
        warnings.count(f"left out {name} readings in units {unit!r}; expected {', '.join(accepted)}")
        return
    for entry in metric.get("data") or []:
        if not isinstance(entry, dict):
            continue
        if how == "sleep":
            _add_sleep(entry, days, warnings)
            continue
        try:
            day = hae.day_of(entry.get("date"))
        except ValueError:
            warnings.count(f"left out {name} readings with an unreadable date")
            continue
        value = _reading(field, entry.get("qty"), unit)
        if value is None:
            warnings.count(f"left out {name} readings outside the range a {field} can hold")
            continue
        slot = days.setdefault(day, {"readings": {}, "devices": set()})
        if how == "sum":
            slot["readings"][field] = slot["readings"].get(field, 0) + value
        else:
            slot["readings"][field] = value
        _note_devices(slot, entry)


def _reading(field, qty, unit):
    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty < 0:
        return None
    if field == "body_mass_kg":
        return units.mass_kg(qty, unit)
    if field == "body_fat_pct":
        value = qty * 100 if qty <= 1 else qty
        return units.json_number(round(value, 2)) if value <= 100 else None
    if field == "steps":
        return round(qty)
    return units.json_number(round(qty, 1))


def _add_sleep(entry, days, warnings):
    rule = MAPPING["sleep"]
    if "value" in entry or "startDate" in entry:
        warnings.once("sleep_analysis holds sleep segments, not nightly totals; turn on Summarize Data in "
                      "Health Auto Export to read sleep")
        return
    day = sleep_day(entry)
    if day is None:
        warnings.count("left out sleep_analysis entries with an unreadable date")
        return
    asleep = next((entry[k] for k in rule["asleep_hours"] if _hours(entry.get(k)) is not None), None)
    in_bed = next((entry[k] for k in rule["in_bed_hours"] if _hours(entry.get(k))), None)
    sleep = {"asleep_hours": _hours(asleep), "in_bed_hours": _hours(in_bed),
             "start": _utc(entry.get(rule["start"])), "end": _utc(entry.get(rule["end"]))}
    if sleep["asleep_hours"] is None and sleep["in_bed_hours"] is None:
        warnings.count("left out sleep_analysis entries with no usable hours")
        return
    slot = days.setdefault(day, {"readings": {}, "devices": set()})
    slot["readings"]["sleep"] = sleep
    _note_devices(slot, entry)


def _hours(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 24:
        return None
    return units.json_number(round(value, 2))


def _utc(text):
    try:
        return records.utc_text(hae.parse_time(text))
    except ValueError:
        return None


def _note_devices(slot, entry):
    source = entry.get("source")
    if isinstance(source, str):
        slot["devices"].update(part for part in source.split("|") if part)


class _Warnings:
    def __init__(self):
        self._once = []
        self._counts = Counter()
        self._unknown = set()

    def once(self, message):
        if message not in self._once:
            self._once.append(message)

    def count(self, message):
        self._counts[message] += 1

    def unknown(self, name):
        self._unknown.add(str(name))

    def lines(self):
        found = list(self._once)
        found += [message if n == 1 else f"{message} ({n} times)" for message, n in sorted(self._counts.items())]
        if self._unknown:
            names = sorted(self._unknown)
            found.append(f"ignored {len(names)} metric(s) the adapter does not read: {', '.join(names)}")
        return found


def normalise(item, ctx):
    if item["type"] == "day":
        return [_wellness(item)]
    return [_activity(item, ctx)]


def _activity(item, ctx):
    raw = item["raw"]
    if item["kind"] is None:
        raise Drop("unreadable start or end time")
    source = raw.get("source")
    if isinstance(source, str):
        dropped = {n.lower(): n for n in ctx.config["sources"][NAME]["drop_source_names"]}
        app = next((dropped[part.lower()] for part in source.split("|") if part.lower() in dropped), None)
        if app is not None:
            raise Drop(WRITTEN_BY.format(app=app))
    if item["kind"] == "lifting":
        raise Drop(LIFTING)
    window = ctx.config.activity.dedup_window_minutes
    if any(gap <= timedelta(minutes=window) for gap in item.get("hevy_gaps", [])):
        raise Drop(NEAR_HEVY.format(minutes=window))
    if not isinstance(raw.get("id"), str) or not _ID.fullmatch(raw["id"]):
        raise Drop(BAD_ID)
    start, end = item["start"], item["end"]
    utc_offset = records.offset_text(start.utcoffset())
    duration = raw.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
        duration = (end - start).total_seconds() if end else 0
    indoor = raw.get("isIndoor")
    if not isinstance(indoor, bool):
        indoor = MAPPING["indoor_locations"].get(raw.get("location"))
    fields = item["fields"]
    return {
        "id": f"{NAME}:{raw['id']}", "source": NAME, "source_id": raw["id"],
        "kind": item["kind"], "name": raw.get("name") or None, "indoor": indoor,
        "start": records.utc_text(start), "end": records.utc_text(end) if end else None, "utc_offset": utc_offset,
        "local_date": records.local_date(start, utc_offset, None).isoformat(),
        "duration_seconds": max(0, round(duration)),
        "distance_meters": fields["distance_meters"], "elevation_gain_meters": fields["elevation_gain_meters"],
        "avg_hr": fields["avg_hr"], "max_hr": fields["max_hr"], "active_kcal": fields["active_kcal"],
        "rpe": None, "device": source if isinstance(source, str) and source else None, "notes": None,
    }


def _wellness(item):
    previous = item["previous"] or {}
    readings = item["readings"]
    record = {"id": f"{NAME}:{item['date']}", "source": NAME, "span": {"start": item["date"], "end": item["date"]}}
    for field in WELLNESS_FIELDS:
        record[field] = readings[field] if field in readings else previous.get(field)
    record["device"] = "|".join(item["devices"]) or previous.get("device")
    return record
