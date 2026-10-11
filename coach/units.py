"""Load modes, Hevy conversion, distances, rounding and load formatting.

This is the only module that doubles, halves or converts kg and lb, and the
only one that formats a load (contract C5). An AST test enforces it.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

LOAD_MODES = ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band", "duration", "distance")
LOADED_MODES = ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted")
PER_HAND_MODES = ("per_hand_x2", "single_implement")
UNITS = ("kg", "lb")
LB_TO_KG = 0.45359237
ROUND_DIRECTIONS = ("nearest", "down", "up")
DISTANCE_UNITS = ("m", "km", "mi", "ft")
_METRES_PER = {"m": 1, "km": 1000, "mi": 1609.344, "ft": 0.3048}

_HEVY_KG_PLACES = 4
# Hevy stores kg to 4 places, which is about 0.0001 lb; 3 places in athlete
# units absorbs that error without losing any real plate or dumbbell step.
_ATHLETE_PLACES = 3
_LOAD_KEYS = ("mode", "unit", "per_hand", "hevy_total", "hevy_kg")


def json_number(value):
    """Return an integral float as an int, so JSON writes `25`, not `25.0`."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _factor(unit):
    if unit not in UNITS:
        raise ValueError(f"unknown unit {unit!r}; expected one of {', '.join(UNITS)}")
    return 1 if unit == "kg" else LB_TO_KG


def _loaded_mode(load_mode):
    if load_mode not in LOAD_MODES:
        raise ValueError(f"unknown load mode {load_mode!r}; expected one of {', '.join(LOAD_MODES)}")
    if load_mode not in LOADED_MODES:
        raise ValueError(f"load mode {load_mode!r} carries no load")
    return load_mode


def _number(value, name="value"):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, found {value!r}")
    if value < 0:
        raise ValueError(f"{name} must not be negative, found {value!r}")
    return value


def _hevy_total(value, load_mode):
    return value * 2 if load_mode == "per_hand_x2" else value


def to_hevy_kg(value, load_mode, unit):
    """The `weight_kg` Hevy stores for a load the athlete sets to `value`.

    `value` is per hand for per-hand modes, the added load for bodyweight,
    the assistance for assisted, and the total otherwise.
    """
    _number(value)
    _loaded_mode(load_mode)
    return json_number(round(_hevy_total(value, load_mode) * _factor(unit), _HEVY_KG_PLACES))


def from_hevy_kg(weight_kg, load_mode, unit):
    """The value the athlete sets, in athlete units, for a Hevy `weight_kg`."""
    _number(weight_kg, "weight_kg")
    _loaded_mode(load_mode)
    total = round(weight_kg / _factor(unit), _ATHLETE_PLACES)
    if load_mode == "per_hand_x2":
        total = round(total / 2, _ATHLETE_PLACES)
    return json_number(total)


def _distance_factor(unit):
    if unit not in DISTANCE_UNITS:
        raise ValueError(f"unknown distance unit {unit!r}; expected one of {', '.join(DISTANCE_UNITS)}")
    return _METRES_PER[unit]


def to_meters(value, unit):
    """Metres for a distance in m, km, mi or ft, to the millimetre."""
    _number(value, "distance")
    return json_number(round(value * _distance_factor(unit), 3))


def from_meters(meters, unit):
    _number(meters, "meters")
    return json_number(round(meters / _distance_factor(unit), 6))


def mass_kg(value, unit):
    """Kilograms for a body mass in kg or lb, to the gram."""
    _number(value, "mass")
    return json_number(round(value * _factor(unit), 3))


_KCAL_PER = {"kcal": 1, "kJ": 1 / 4.184}


def energy_kcal(value, unit):
    """Kilocalories for an energy in kcal or kJ, to 0.1 kcal."""
    _number(value, "energy")
    if unit not in _KCAL_PER:
        raise ValueError(f"unknown energy unit {unit!r}; expected one of {', '.join(_KCAL_PER)}")
    return json_number(round(value * _KCAL_PER[unit], 1))


def make_load(value, load_mode, unit):
    """Build the C5 load object, or None for modes that carry no load."""
    if load_mode not in LOAD_MODES:
        raise ValueError(f"unknown load mode {load_mode!r}; expected one of {', '.join(LOAD_MODES)}")
    _factor(unit)
    if load_mode not in LOADED_MODES:
        return None
    value = json_number(_number(value))
    return {
        "mode": load_mode,
        "unit": unit,
        "per_hand": value if load_mode in PER_HAND_MODES else None,
        "hevy_total": json_number(_hevy_total(value, load_mode)),
        "hevy_kg": to_hevy_kg(value, load_mode, unit),
    }


def check_load(load):
    """Return the arithmetic errors in a load object; empty when it is sound."""
    if not isinstance(load, dict):
        return [f"load must be an object, found {load!r}"]
    errors = []
    missing = [k for k in _LOAD_KEYS if k not in load]
    extra = sorted(k for k in load if k not in _LOAD_KEYS)
    if missing:
        errors.append(f"missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"unknown keys: {', '.join(extra)}")
    if errors:
        return errors

    mode, unit = load["mode"], load["unit"]
    if mode not in LOADED_MODES:
        return [f"mode: expected one of {', '.join(LOADED_MODES)}, found {mode!r}"]
    if unit not in UNITS:
        return [f"unit: expected one of {', '.join(UNITS)}, found {unit!r}"]

    per_hand, hevy_total = load["per_hand"], load["hevy_total"]
    try:
        _number(hevy_total, "hevy_total")
        _number(load["hevy_kg"], "hevy_kg")
        if per_hand is not None:
            _number(per_hand, "per_hand")
    except ValueError as exc:
        return [str(exc)]

    if mode in PER_HAND_MODES:
        if per_hand is None:
            return [f"per_hand: required for mode {mode}"]
        expected_total = _hevy_total(per_hand, mode)
        if hevy_total != expected_total:
            errors.append(f"hevy_total: expected {_raw(expected_total)}, found {_raw(hevy_total)}")
    elif per_hand is not None:
        errors.append(f"per_hand: must be null for mode {mode}, found {_raw(per_hand)}")

    expected_kg = round(hevy_total * _factor(unit), _HEVY_KG_PLACES)
    if load["hevy_kg"] != expected_kg:
        errors.append(f"hevy_kg: expected {_raw(expected_kg)}, found {_raw(load['hevy_kg'])}")
    return errors


def _raw(value):
    return repr(json_number(value))


def _text(value):
    """At most two decimals, trailing zeros stripped, half rounded up."""
    quantised = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(quantised, "f").rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def format_load(load, show_hevy=True):
    """The text a renderer prints for a load. Never prints a unit.

    With `show_hevy` false (an athlete without Hevy) the Hevy value is left out.
    """
    if load is None:
        raise ValueError("no load to format")
    errors = check_load(load)
    if errors:
        raise ValueError(f"invalid load: {'; '.join(errors)}")
    mode = load["mode"]
    total = _text(load["hevy_total"])
    hevy = f" (Hevy: {total})" if show_hevy else ""
    if mode == "total":
        return total
    if mode == "per_hand_x2":
        return f"{_text(load['per_hand'])}/hand{hevy}"
    if mode == "single_implement":
        return f"{_text(load['per_hand'])}{hevy}"
    if mode == "bodyweight":
        return "BW" if load["hevy_total"] == 0 else f"BW+{total}"
    return f"BW-{total} assist{hevy}"


def round_to_increment(value, increment, direction="nearest"):
    """Round `value` to a whole number of `increment`s; halves round up."""
    _number(value)
    if isinstance(increment, bool) or not isinstance(increment, (int, float)) or increment <= 0:
        raise ValueError(f"increment must be a positive number, found {increment!r}")
    if direction not in ROUND_DIRECTIONS:
        raise ValueError(f"direction must be one of {', '.join(ROUND_DIRECTIONS)}, found {direction!r}")
    steps = round(value / increment, 9)
    if direction == "down":
        whole = math.floor(steps)
    elif direction == "up":
        whole = math.ceil(steps)
    else:
        whole = math.floor(steps + 0.5)
    return json_number(round(whole * increment, 6))


_PLATE_SCALE = 1000


def _scaled(value):
    scaled = round(value * _PLATE_SCALE)
    if abs(value * _PLATE_SCALE - scaled) > 1e-6:
        return None
    return scaled


def plate_breakdown(total, bar_weight, plates):
    """Plates for one side of the bar that make `total`, or None if none do.

    `plates` lists the plate sizes available in pairs; any number of each
    size may be used. The answer uses the fewest plates, heaviest first.
    """
    _number(total, "total")
    _number(bar_weight, "bar_weight")
    per_side = (total - bar_weight) / 2
    if per_side < 0:
        return None
    target = _scaled(per_side)
    sizes = sorted({_scaled(_number(p, "plate")) for p in plates if p > 0} - {None}, reverse=True)
    if target is None:
        return None
    if target == 0:
        return []
    if not sizes:
        return None
    step = math.gcd(*sizes)
    if target % step:
        return None
    target //= step
    sizes = [s // step for s in sizes]

    fewest = [0] + [math.inf] * target
    for amount in range(1, target + 1):
        for size in sizes:
            if size <= amount and fewest[amount - size] + 1 < fewest[amount]:
                fewest[amount] = fewest[amount - size] + 1
    if fewest[target] == math.inf:
        return None

    chosen, remaining = [], target
    while remaining:
        size = next(s for s in sizes if s <= remaining and fewest[remaining - s] == fewest[remaining] - 1)
        chosen.append(json_number(size * step / _PLATE_SCALE))
        remaining -= size
    return chosen
