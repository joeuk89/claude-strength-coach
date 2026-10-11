"""Loading and validating `config.toml` (contract C4, C54).

Tables are declared with `Key` and `Table` in modules under
`coach/config_tables/`, discovered at load time, so an item that adds a
table adds a module and edits nothing here. A module may also export
RULES, checks that span keys or tables, run once every table is valid. Validation is strict: an
unknown table or key is an error that names the file and the key.
"""

import importlib
import pkgutil
import re
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from coach import dates, paths
from coach.errors import ConfigError

SCHEMA_VERSION = 1


class _Sentinel:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


REQUIRED = _Sentinel("REQUIRED")
OMIT = _Sentinel("OMIT")


@dataclass(frozen=True)
class ByUnit:
    """A default that depends on `[athlete] units`; required for any unit not listed."""

    values: dict

    def __call__(self, units):
        return self.values.get(units, REQUIRED)


@dataclass(frozen=True)
class Key:
    """One config key.

    type: "string", "integer", "number", "boolean", "date" or "list".
    default: a value, REQUIRED, OMIT (absent stays absent), or a callable
    taking `[athlete] units` (see ByUnit).
    table: for a list, the shape of each item; the list is then an array
    of tables, written [[name]].
    check: an extra rule, called with the value; returns an error or None.
    """

    type: str
    default: object = REQUIRED
    choices: tuple = ()
    item: str = None
    item_choices: tuple = ()
    distinct: bool = False
    minimum: float = None
    positive: bool = False
    table: "Table" = None
    check: object = None


@dataclass(frozen=True)
class Table:
    """A TOML table.

    tables: fixed subtables. named: the shape of each `[<this>.<name>]`
    subtable, any number of them, names matching name_pattern. free: the
    shape of every key when the keys are open (ids matching key_pattern).
    optional: an absent table stays absent instead of taking defaults.
    """

    keys: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)
    named: "Table" = None
    name_pattern: str = r"^[a-z0-9-]+$"
    free: Key = None
    key_pattern: str = None
    optional: bool = False


class Section(dict):
    """A table as a dict that also allows attribute access: config.hevy.enabled."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None


class Config(Section):
    """The validated config: every known table, defaults filled in."""

    def __init__(self, data, path):
        super().__init__(data)
        self.path = Path(path)


def _sectioned(value):
    if isinstance(value, dict):
        return Section({k: _sectioned(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_sectioned(v) for v in value]
    return value


def _table_modules():
    from coach import config_tables

    for module_info in sorted(pkgutil.iter_modules(config_tables.__path__), key=lambda m: m.name):
        yield importlib.import_module(f"coach.config_tables.{module_info.name}")


def registered_tables():
    found = {}
    for module in _table_modules():
        for name, table in getattr(module, "TABLES", {}).items():
            if name in found:
                raise RuntimeError(f"config table [{name}] is declared twice")
            found[name] = table
    return found


def registered_rules():
    """Rules that span keys or tables: each takes the validated config, returns [(key path, message)]."""
    return [rule for module in _table_modules() for rule in getattr(module, "RULES", [])]


_TYPE_NAMES = {
    "string": "a string",
    "integer": "a whole number",
    "number": "a number",
    "boolean": "true or false",
    "date": "a date (YYYY-MM-DD)",
    "list": "a list",
}


def _describe(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, dict):
        return "a table"
    if isinstance(value, list):
        return "a list"
    return str(value)


def _is_type(value, type_name):
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "date":
        return isinstance(value, date) and not isinstance(value, datetime)
    if type_name == "list":
        return isinstance(value, list)
    raise ValueError(f"unknown config key type {type_name!r}")


def _quoted(options):
    return ", ".join(f'"{option}"' for option in options)


class _Validator:
    def __init__(self, path):
        self.path = path
        self.problems = []
        self.units = None

    def problem(self, where, message):
        self.problems.append((where, message))

    def key(self, table_label, dotted, name, spec, value):
        label = f"[{table_label}] {name}" if table_label else name
        where = f"{dotted}.{name}" if dotted else name
        if not _is_type(value, spec.type):
            self.problem(where, f"{label} must be {_TYPE_NAMES[spec.type]} (found {_describe(value)})")
            return
        if spec.choices and value not in spec.choices:
            self.problem(where, f"{label} must be one of {_quoted(spec.choices)} (found {_describe(value)})")
            return
        values = value if spec.type == "list" else [value]
        if spec.type == "list" and spec.item:
            for item in value:
                if not _is_type(item, spec.item):
                    self.problem(where, f"{label} must hold only {_TYPE_NAMES[spec.item]}s (found {_describe(item)})")
                    return
                if spec.item_choices and item not in spec.item_choices:
                    self.problem(
                        where, f"{label} must hold only {_quoted(spec.item_choices)} (found {_describe(item)})"
                    )
                    return
        if spec.distinct and len(set(value)) != len(value):
            self.problem(where, f"{label} must not repeat a value")
            return
        for number in values:
            if not _is_type(number, "number"):
                continue
            if spec.positive and number <= 0:
                self.problem(where, f"{label} must be above zero (found {_describe(number)})")
                return
            if spec.minimum is not None and number < spec.minimum:
                self.problem(where, f"{label} must be at least {spec.minimum} (found {_describe(number)})")
                return
        if spec.check:
            error = spec.check(value)
            if error:
                self.problem(where, f"{label} {error}")

    def default(self, table_label, dotted, name, spec):
        default = spec.default
        if callable(default):
            if self.units is None:
                return OMIT
            default = default(self.units)
            if default is REQUIRED:
                self.problem(
                    f"{dotted}.{name}",
                    f'[{table_label}] {name} is required when [athlete] units = "{self.units}"',
                )
                return OMIT
        if default is REQUIRED:
            self.problem(f"{dotted}.{name}", f"[{table_label}] {name} is required")
            return OMIT
        if isinstance(default, (list, dict)):
            return type(default)(default)
        return default

    def table_list(self, label, name, spec, value):
        where = f"{label}.{name}"
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            self.problem(where, f"[{label}] {name} must be a list of tables, written [[{where}]] "
                                f"(found {_describe(value)})")
            return value
        return [self.table(f"{where}[{index}]", item, spec) for index, item in enumerate(value)]

    def table(self, label, raw, spec):
        out = {}
        for name, value in raw.items():
            if name in spec.keys and spec.keys[name].table is not None:
                out[name] = self.table_list(label, name, spec.keys[name].table, value)
            elif name in spec.keys:
                self.key(label, label, name, spec.keys[name], value)
                out[name] = value
            elif name in spec.tables:
                if not isinstance(value, dict):
                    self.problem(f"{label}.{name}", f"[{label}] {name} must be a table (found {_describe(value)})")
                    continue
                out[name] = self.table(f"{label}.{name}", value, spec.tables[name])
            elif spec.named is not None:
                if not re.fullmatch(spec.name_pattern, name):
                    self.problem(
                        f"{label}.{name}",
                        f'name "{name}" in [{label}] must match {spec.name_pattern} '
                        "(lowercase letters, digits and hyphens)",
                    )
                    continue
                if not isinstance(value, dict):
                    self.problem(f"{label}.{name}", f"[{label}.{name}] must be a table (found {_describe(value)})")
                    continue
                out[name] = self.table(f"{label}.{name}", value, spec.named)
            elif spec.free is not None and (spec.key_pattern is None or re.fullmatch(spec.key_pattern, name)):
                self.key(label, label, name, spec.free, value)
                out[name] = value
            elif spec.free is not None:
                self.problem(f"{label}.{name}", f'key "{name}" in [{label}] must match {spec.key_pattern}')
            elif isinstance(value, dict):
                self.problem(f"{label}.{name}", f"unknown table [{label}.{name}]")
            else:
                self.problem(f"{label}.{name}", f'unknown key "{name}" in [{label}]')

        for name, key_spec in spec.keys.items():
            if name not in raw:
                value = self.default(label, label, name, key_spec)
                if value is not OMIT:
                    out[name] = value
        for name, sub in spec.tables.items():
            if name not in raw and not sub.optional:
                out[name] = self.table(f"{label}.{name}", {}, sub)
        return out


def parse(raw, path, today=None):
    path = Path(path)
    validator = _Validator(path)
    tables = registered_tables()

    version = raw.get("schema_version", REQUIRED)
    if version is REQUIRED:
        validator.problem("schema_version", "schema_version is required (schema_version = 1)")
    elif isinstance(version, bool) or not isinstance(version, int):
        validator.problem("schema_version", f"schema_version must be a whole number (found {_describe(version)})")
    elif version > SCHEMA_VERSION:
        raise ConfigError(
            f"{path}: schema_version {version} is newer than this coach reads ({SCHEMA_VERSION}); run /framework-sync"
        )
    elif version < SCHEMA_VERSION:
        validator.problem("schema_version", f"schema_version must be {SCHEMA_VERSION} (found {version})")

    for name, value in raw.items():
        if name == "schema_version":
            continue
        if name not in tables:
            if isinstance(value, dict):
                validator.problem(name, f"unknown table [{name}]")
            else:
                validator.problem(name, f'unknown key "{name}" at the top level')
        elif not isinstance(value, dict):
            validator.problem(name, f"{name} must be a table, [{name}] (found {_describe(value)})")

    athlete = raw.get("athlete")
    units = athlete.get("units") if isinstance(athlete, dict) else None
    validator.units = units if units in ("kg", "lb") else None

    data = {"schema_version": version}
    for name in sorted(tables):
        spec = tables[name]
        value = raw.get(name)
        if value is None and spec.optional:
            continue
        if value is not None and not isinstance(value, dict):
            continue
        data[name] = validator.table(name, value or {}, spec)

    if not validator.problems:
        if isinstance(today, datetime):
            name = data["athlete"]["timezone"]
            today = today.astimezone(dates.zone(name) if name else None).date()
        year = (today or date.today()).year
        birth_year = data["athlete"].get("birth_year")
        if birth_year is not None and birth_year > year:
            validator.problem("athlete.birth_year", f"[athlete] birth_year must not be in the future (after {year})")

    if not validator.problems:
        sectioned = Section({name: _sectioned(value) for name, value in data.items()})
        for rule in registered_rules():
            for where, message in rule(sectioned):
                validator.problem(where, message)

    if validator.problems:
        details = [{"path": where, "message": f"{path}: {message}"} for where, message in validator.problems]
        first = details[0]["message"]
        more = len(details) - 1
        message = first if not more else f"{first} (and {more} more problem(s))"
        raise ConfigError(message, details=details)

    return Config({name: _sectioned(value) for name, value in data.items()}, path)


def parse_file(path, today=None):
    path = Path(path)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} is not valid TOML: {exc}") from None
    return parse(raw, path, today=today)


def load(root, today=None):
    path = Path(root) / paths.CONFIG
    if not path.is_file():
        raise ConfigError(f"No config.toml in {root}: copy {paths.CONFIG_EXAMPLE} to {paths.CONFIG} and edit it.")
    return parse_file(path, today=today)


def equipment_for(config, location=None):
    """The main [equipment] table, with the named location's keys laid over it."""
    main = {k: v for k, v in config["equipment"].items() if k != "locations"}
    if location is None:
        return main
    locations = config["equipment"].get("locations", {})
    if location not in locations:
        known = ", ".join(sorted(locations)) or "none"
        raise ConfigError(
            f"{config.path}: no [equipment.locations.{location}] table for location \"{location}\" (known: {known})"
        )
    main.update(locations[location])
    return main


def approximate_age(config, today):
    birth_year = config.athlete.get("birth_year")
    if birth_year is None:
        return None
    return {"years": today.year - birth_year, "approximate": True, "as_of": today.isoformat(),
            "note": "Approximate age from birth year; birthday is unknown, so actual age may be one year less."}
