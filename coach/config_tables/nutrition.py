"""The [nutrition] table (contract C4). R-33b declares [nutrition.bank]."""

from coach.config import Key, Table

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


TABLES = {
    "nutrition": Table(optional=True, tables={"bank": BANK}),
}
