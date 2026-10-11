"""Health Auto Export files: reading the Version 2 JSON format and anonymising a real export into a fixture.

Format: https://help.healthyapps.dev/en/health-auto-export/export-format (envelope
`{"data": {"metrics": [...], "workouts": [...]}}`, dates `yyyy-MM-dd HH:mm:ss Z`).
"""

import hashlib
import json
import random
import re
import secrets
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from coach.errors import ValidationError

KEPT_SECTIONS = ("metrics", "workouts")
DROPPED_KEYS = ("route", "metadata")
DEVICE_KEYS = ("source", "device")
KEPT_DEVICE_NAMES = ("Hevy",)
OUTPUT_NAME = "health-auto-export.json"
PERTURB = 0.03
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_ANYWHERE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %z"


def is_placeholder(name):
    """Whether a file name is an iCloud placeholder for a JSON file not yet downloaded."""
    return name.endswith(".json.icloud")


def placeholder_target(path):
    """The file an iCloud placeholder stands for: `.Name.json.icloud` -> `Name.json`."""
    path = Path(path)
    return path.with_name(path.name[:-len(".icloud")].lstrip("."))


def placeholder_message(path):
    target = placeholder_target(path)
    return (f"{target.name} is still in iCloud and not downloaded; run brctl download \"{target}\" "
            "and sync again")


def csv_message(name):
    return f"{name} is a CSV export; in Health Auto Export set Export Format to JSON and export again"


def v1_message(name):
    return (f"{name} is a Version 1 export; in Health Auto Export set Export Version to "
            "Export Version 2 and export again")


def file_hash(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_export(path):
    """The `data` object of a Version 2 JSON export; ValidationError for CSV, Version 1 or anything else."""
    path = Path(path)
    if is_placeholder(path.name):
        raise ValidationError(placeholder_message(path))
    if path.suffix.lower() == ".csv":
        raise ValidationError(csv_message(path.name))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise ValidationError(f"{path.name} is not a Health Auto Export JSON file (not UTF-8 text)") from None
    except json.JSONDecodeError:
        first = path.read_text(encoding="utf-8").partition("\n")[0]
        if "," in first and not first.lstrip().startswith(("{", "[")):
            raise ValidationError(csv_message(path.name)) from None
        raise ValidationError(f"{path.name} is not valid JSON, so it is not a Health Auto Export file") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), dict):
        raise ValidationError(f"{path.name} has no top-level \"data\" object, so it is not a Health Auto Export file")
    data = doc["data"]
    for section in KEPT_SECTIONS:
        if not isinstance(data.get(section, []), list):
            raise ValidationError(f"{path.name}: data.{section} must be a list")
    if any(not isinstance(w, dict) or "id" not in w or "duration" not in w for w in data.get("workouts", [])):
        raise ValidationError(v1_message(path.name))
    return data


def parse_time(text):
    """An aware datetime for `yyyy-MM-dd HH:mm:ss Z`; ValueError otherwise."""
    if not isinstance(text, str) or not _TIMESTAMP.fullmatch(text):
        raise ValueError(f"expected a time as yyyy-MM-dd HH:mm:ss Z, found {text!r}")
    return datetime.strptime(text, _TIMESTAMP_FORMAT)


def day_of(text):
    """The calendar date a timestamp or date string names, in its own offset, as YYYY-MM-DD."""
    if isinstance(text, str) and _DATE.fullmatch(text):
        return date.fromisoformat(text).isoformat()
    return parse_time(text).date().isoformat()


def anonymise(path, out_dir, dry_run=False, seed=None):
    """Write an anonymised copy of a Version 2 export to out_dir; return a report.

    Keeps shapes and units. Shifts every date by a whole number of weeks
    (weekdays and gaps survive), replaces ids with salted fake ones, replaces
    device and source names other than Hevy with `Device N`, drops routes,
    metadata and every section the adapter does not read, and perturbs
    every number by up to 3 %. The salt is random per run and never stored.
    """
    data = read_export(path)
    in_file = set(_DATE_ANYWHERE.findall(Path(path).read_text(encoding="utf-8")))
    seed = secrets.randbits(64) if seed is None else seed
    rng = random.Random(seed)
    salt = f"{seed:x}"
    kept = {section: data.get(section, []) for section in KEPT_SECTIONS}
    found = _originals(kept)
    weeks = _shift_weeks(found["days"] | in_file, rng)
    devices = {name: f"Device {n}" for n, name in enumerate(sorted(found["devices"]), start=1)}
    walker = _Anonymiser(rng, salt, weeks, devices)
    out = {"x-anonymised": True, "data": walker.walk(kept)}
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    _assert_clean(text, found, in_file)
    target = Path(out_dir) / OUTPUT_NAME
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return {
        "path": str(target), "written": not dry_run,
        "workouts": len(kept["workouts"]), "metrics": len(kept["metrics"]),
        "dropped_sections": sorted(set(data) - set(KEPT_SECTIONS)),
    }


def _originals(node, found=None, key=None):
    found = found if found is not None else {"ids": set(), "stamps": set(), "days": set(), "devices": set()}
    if isinstance(node, dict):
        for name, value in node.items():
            if name not in DROPPED_KEYS:
                _originals(value, found, name)
    elif isinstance(node, list):
        for value in node:
            _originals(value, found, key)
    elif isinstance(node, str):
        if key == "id":
            found["ids"].add(node)
        elif key in DEVICE_KEYS:
            found["devices"].update(part for part in node.split("|") if part and part not in KEPT_DEVICE_NAMES)
        elif _TIMESTAMP.fullmatch(node):
            found["stamps"].add(node)
            found["days"].add(node[:10])
        elif _DATE.fullmatch(node):
            found["days"].add(node)
    return found


def _shift_weeks(days, rng):
    """Enough whole weeks that no shifted date lands on any date in the original file."""
    parsed = sorted(filter(None, map(_valid_date, days)))
    if not parsed:
        return rng.randint(1, 26)
    return (parsed[-1] - parsed[0]).days // 7 + 1 + rng.randint(1, 26)


def _valid_date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class _Anonymiser:
    def __init__(self, rng, salt, weeks, devices):
        self.rng = rng
        self.salt = salt
        self.shift = timedelta(weeks=weeks)
        self.devices = devices

    def walk(self, node, key=None):
        if isinstance(node, dict):
            return {name: self.walk(value, name) for name, value in node.items() if name not in DROPPED_KEYS}
        if isinstance(node, list):
            return [self.walk(value, key) for value in node]
        if isinstance(node, bool) or node is None:
            return node
        if isinstance(node, (int, float)):
            return self.number(node)
        if isinstance(node, str):
            return self.text(node, key)
        return node

    def number(self, value):
        moved = value * (1 + self.rng.choice((-1, 1)) * self.rng.uniform(PERTURB / 6, PERTURB))
        if isinstance(value, int):
            moved = round(moved)
            return moved + 1 if moved == value and value else moved
        return round(moved, 3)

    def text(self, value, key):
        if key == "id":
            return self.fake_id(value)
        if key in DEVICE_KEYS:
            return "|".join(self.devices.get(part, part) for part in value.split("|"))
        if _TIMESTAMP.fullmatch(value):
            return (parse_time(value) - self.shift).strftime(_TIMESTAMP_FORMAT)
        if _DATE.fullmatch(value):
            return (date.fromisoformat(value) - self.shift).isoformat()
        return value

    def fake_id(self, value):
        digest = hashlib.sha256(f"{self.salt}:{value}".encode("utf-8")).digest()
        fake = str(uuid.UUID(bytes=digest[:16], version=4))
        return fake.upper() if value.upper() == value else fake


def _assert_clean(text, found, in_file):
    leaks = [("id", value) for value in found["ids"]]
    leaks += [("timestamp", value) for value in found["stamps"]]
    leaks += [("date", value) for value in found["days"] | in_file]
    leaks += [("source name", value) for value in found["devices"]]
    for kind, value in sorted(leaks):
        if value in text:
            raise ValidationError(f"the anonymised export still holds an original {kind}, so nothing was written")
