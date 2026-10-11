"""The Phase 1 and profile-fact tables (contract C4, C54)."""

from dataclasses import replace

from coach import library
from coach.config import OMIT, ByUnit, Key, Table
from coach.dates import WEEK_STARTS, zone

UNITS = ("kg", "lb")
EXPERIENCE = ("beginner", "intermediate", "advanced")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _time_zone(value):
    if value == "":
        return None
    try:
        zone(value)
    except ValueError:
        return f'must be an IANA time zone name such as "Europe/London", or "" for local time (found "{value}")'
    return None


ATHLETE = Table(
    keys={
        "units": Key("string", choices=UNITS),
        "bodyweight_units": Key("string", default=lambda units: units, choices=UNITS),
        "week_starts": Key("string", default="monday", choices=WEEK_STARTS),
        "timezone": Key("string", default="", check=_time_zone),
        "birth_year": Key("integer", default=OMIT, minimum=1),
        "desired_sessions": Key("integer", default=OMIT, minimum=1,
                                check=lambda value: "must be at most 7" if value > 7 else None),
        "experience": Key("string", default="intermediate", choices=EXPERIENCE),
        "available_days": Key("list", default=[], item="string", item_choices=WEEKDAYS, distinct=True),
        "session_minutes": Key("integer", default=60, minimum=0),
    }
)

HEVY = Table(
    keys={
        "enabled": Key("boolean", default=True),
        "cache_max_age_hours": Key("number", default=24, positive=True),
    }
)

EQUIPMENT_KEYS = {
    "available": Key("list", default=[], item="string", item_choices=library.EQUIPMENT, distinct=True),
    "dumbbells": Key("list", default=[], item="number", distinct=True, positive=True),
    "dumbbell_increment": Key("number", default=ByUnit({"kg": 2.0}), positive=True),
    "dumbbell_max": Key("number", default=ByUnit({"kg": 40.0}), positive=True),
    "barbell_increment": Key("number", default=ByUnit({"kg": 2.5}), positive=True),
    "bar_weight": Key("number", default=ByUnit({"kg": 20.0}), minimum=0),
    "plates": Key("list", default=ByUnit({"kg": [25, 20, 15, 10, 5, 2.5, 1.25]}), item="number", distinct=True,
                  positive=True),
    "machine_increment": Key("number", default=ByUnit({"kg": 5.0}), positive=True),
    "cable_increment": Key("number", default=ByUnit({"kg": 2.5}), positive=True),
}

LOCATION = Table(keys={name: replace(spec, default=OMIT) for name, spec in EQUIPMENT_KEYS.items()})

EQUIPMENT = Table(keys=EQUIPMENT_KEYS, tables={"locations": Table(named=LOCATION)})

CAPS = Table(free=Key("number", positive=True), key_pattern=r"^[a-z0-9_]+$")

TABLES = {
    "athlete": ATHLETE,
    "hevy": HEVY,
    "equipment": EQUIPMENT,
    "caps": CAPS,
}
