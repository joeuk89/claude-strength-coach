"""The [nutrition] table (contract C4).

Nutrition is on only with `enabled = true`. A table that sets only
[nutrition.bank] configures the recipe bank and leaves nutrition off.
"""

import re
from datetime import timedelta

from coach.config import OMIT, Key, Table
from coach.config_tables.core import WEEKDAYS

SLOT_PATTERN = r"^[a-z][a-z0-9-]*$"

DEFAULT_AISLES = [
    "produce", "bakery", "meat-fish", "dairy-eggs", "chilled",
    "frozen", "tins-jars-dry", "snacks", "drinks", "household",
]
DEFAULT_MIN_PROTEIN_PER_100KCAL = {"breakfast": 5.0, "lunch": 5.0, "dinner": 5.0, "snack": 0.0}
DEFAULT_MACRO_SUM_WARN_PCT = 10
DEFAULT_MACRO_SUM_FAIL_PCT = 20

BANK = Table(
    keys={
        "aisles": Key("list", default=DEFAULT_AISLES, item="string", distinct=True),
        "macro_sum_warn_pct": Key("number", default=DEFAULT_MACRO_SUM_WARN_PCT, minimum=0),
        "macro_sum_fail_pct": Key("number", default=DEFAULT_MACRO_SUM_FAIL_PCT, minimum=0),
    },
    tables={
        "min_protein_per_100kcal": Table(
            keys={slot: Key("number", default=value, minimum=0)
                  for slot, value in DEFAULT_MIN_PROTEIN_PER_100KCAL.items()},
            free=Key("number", minimum=0),
            key_pattern=SLOT_PATTERN,
        ),
        "slot_notes": Table(free=Key("string"), key_pattern=SLOT_PATTERN),
    },
)


def bank_defaults():
    """[nutrition.bank] as it reads when the file leaves it out."""
    return {
        "aisles": list(DEFAULT_AISLES),
        "macro_sum_warn_pct": DEFAULT_MACRO_SUM_WARN_PCT,
        "macro_sum_fail_pct": DEFAULT_MACRO_SUM_FAIL_PCT,
        "min_protein_per_100kcal": dict(DEFAULT_MIN_PROTEIN_PER_100KCAL),
        "slot_notes": {},
    }


APPS = ("macrofactor", "none")
PHASES = ("bulk", "cut", "maintain", "recomp")
REFERENCE_BASES = ("bodyweight", "goal_weight", "fat_free_mass")
ANCHOR_DAYS = ("daily", "office", "home") + WEEKDAYS
OVERRIDE_MAX_DAYS = 21
DEFAULT_FLOOR_STEP_G = 10

PROTEIN = Table(
    optional=True,
    keys={
        "reference_basis": Key("string", choices=REFERENCE_BASES),
        "reference_mass": Key("number", positive=True),
        "floor_g": Key("number", positive=True),
        "target_g": Key("number", positive=True),
        "stretch_g": Key("number", positive=True),
        "floor_since": Key("date"),
        "floor_step_g": Key("number", default=DEFAULT_FLOOR_STEP_G, positive=True),
    },
)

ANCHOR = Table(
    keys={
        "name": Key("string"),
        "slot": Key("string", check=lambda value: None if re.fullmatch(SLOT_PATTERN, value)
                    else f"must match {SLOT_PATTERN} (found \"{value}\")"),
        "days": Key("list", item="string", item_choices=ANCHOR_DAYS, distinct=True,
                    check=lambda value: None if value else "must name at least one day"),
        "kcal": Key("number", minimum=0),
        "protein_g": Key("number", minimum=0),
    },
)

OVERRIDE = Table(
    optional=True,
    keys={
        "start": Key("date"),
        "expires": Key("date"),
        "what": Key("string"),
        "reason": Key("string"),
        "exit_condition": Key("string"),
        "renewal": Key("integer", default=0, minimum=0,
                       check=lambda value: None if value <= 2 else f"must be 0, 1 or 2 (found {value})"),
    },
)

STRATEGY_KEYS = ("app", "phase", "target_rate_per_week")


def _enabled_rules(config):
    nutrition = config.get("nutrition")
    if nutrition is None:
        return []
    problems = []
    set_keys = [key for key in STRATEGY_KEYS + ("goal_weight", "kcal_target", "protein", "anchors", "override")
                if key in nutrition and (key != "anchors" or nutrition[key])]
    if "enabled" not in nutrition:
        if set_keys:
            problems.append(("nutrition.enabled", "[nutrition] enabled is required when [nutrition] sets "
                                                  f"{', '.join(set_keys)}: write enabled = true, or false to "
                                                  "keep the numbers but switch nutrition off"))
        return problems
    if not nutrition["enabled"]:
        return problems
    for key in STRATEGY_KEYS:
        if key not in nutrition:
            problems.append((f"nutrition.{key}", f"[nutrition] {key} is required when enabled = true"))
    if "protein" not in nutrition:
        problems.append(("nutrition.protein", "[nutrition.protein] is required when enabled = true (set by /goals)"))
    return problems


def _kcal_target_only_without_an_app(config):
    nutrition = config.get("nutrition") or {}
    if "kcal_target" in nutrition and nutrition.get("app", "none") != "none":
        return [("nutrition.kcal_target",
                 f'[nutrition] kcal_target is only for app = "none"; with app = "{nutrition["app"]}" the app '
                 "sets the calorie target, so remove nutrition.kcal_target")]
    return []


def _protein_in_order(config):
    protein = (config.get("nutrition") or {}).get("protein")
    if not protein:
        return []
    floor, target, stretch = protein["floor_g"], protein["target_g"], protein["stretch_g"]
    if floor <= target <= stretch:
        return []
    return [("nutrition.protein.target_g",
             f"[nutrition.protein] must have floor_g <= target_g <= stretch_g "
             f"(found floor_g {floor}, target_g {target}, stretch_g {stretch})")]


def _override_within_cap(config):
    override = (config.get("nutrition") or {}).get("override")
    if not override:
        return []
    start, expires = override["start"], override["expires"]
    if expires <= start:
        return [("nutrition.override.expires",
                 f"[nutrition.override] expires ({expires}) must be after start ({start})")]
    if expires > start + timedelta(days=OVERRIDE_MAX_DAYS):
        return [("nutrition.override.expires",
                 f"[nutrition.override] expires ({expires}) must be at most {OVERRIDE_MAX_DAYS} days after "
                 f"start ({start}); renew it through /goals instead")]
    return []


RULES = [_enabled_rules, _kcal_target_only_without_an_app, _protein_in_order, _override_within_cap]

TABLES = {
    "nutrition": Table(
        optional=True,
        keys={
            "enabled": Key("boolean", default=OMIT),
            "app": Key("string", default=OMIT, choices=APPS),
            "phase": Key("string", default=OMIT, choices=PHASES),
            "target_rate_per_week": Key("number", default=OMIT),
            "goal_weight": Key("number", default=OMIT, positive=True),
            "kcal_target": Key("number", default=OMIT, positive=True),
            "anchors": Key("list", default=[], table=ANCHOR),
        },
        tables={"bank": BANK, "protein": PROTEIN, "override": OVERRIDE},
    ),
}
