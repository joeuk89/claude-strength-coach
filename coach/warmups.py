"""Warm-up loads: a ramp into each line's first working set, on the kit (contract C24).

Every load here is the coaching number in athlete units (C18); the core
builds the load objects afterwards, as it does for working sets.
"""

from dataclasses import replace

from coach import units

MODES = ("total", "per_hand_x2", "single_implement")
RAMP = {1: (60,), 2: (50, 75), 3: (40, 60, 80)}
RAMP_FLOOR, RAMP_CEILING = 40, 80


def percents(count):
    """The ramp for `count` warm-ups as percents of the first working load: 60; 50 and 75; 40, 60 and 80; four or
    more spread evenly from 40 to 80."""
    if count in RAMP:
        return RAMP[count]
    step = (RAMP_CEILING - RAMP_FLOOR) / (count - 1)
    return tuple(RAMP_FLOOR + i * step for i in range(count))


def pins(groups):
    """One entry per warm-up set of the program's set groups, in order: `{"load": n}`, `{"percent": n}` or None."""
    found = []
    for group in groups:
        if (group.get("type") or "normal") != "warmup":
            continue
        pin = None
        if group.get("warmup_load") is not None:
            pin = {"load": group["warmup_load"]}
        elif group.get("warmup_percent") is not None:
            pin = {"percent": group["warmup_percent"]}
        found += [pin] * group.get("count", 1)
    return found


def _targets(sets, pins, first):
    """(index, pinned load or None, percent) for each warm-up set, its pin by position in the program's warm-ups.

    A pinned load at or above the first working load (a cut week) gives way to the position's ramp percent.
    """
    warmups = [i for i, s in enumerate(sets) if s.type == "warmup"]
    found = []
    for position, (index, percent) in enumerate(zip(warmups, percents(len(warmups)) if warmups else ())):
        pin = pins[position] if position < len(pins) else None
        pinned = pin["load"] if pin and pin.get("load") is not None and pin["load"] < first else None
        found.append((index, pinned, pin["percent"] if pin and pin.get("percent") is not None else percent))
    return found


def applies(sets, mode, available):
    """True when the line ramps: a barbell, dumbbell or single-implement line with a first working load set."""
    return (mode in MODES and available is not None and any(s.type == "warmup" for s in sets)
            and next((s.load for s in sets if s.working), None) is not None)


def with_loads(sets, mode, available, pins=()):
    """The sets with each warm-up at its ramp load, derived from the first working set's load.

    Bodyweight, assisted, banded and timed lines keep their warm-ups as they are, as does a line whose first
    working load is not set yet. A warm-up's target is its pin, else its ramp percent of the first working load;
    its load is the kit's heaviest no heavier than that target, else the lightest the kit makes (the bare bar,
    the first dumbbell), even when that is the first working load or an earlier warm-up's load: a warm-up left
    without a load lets Hevy fill in whatever the exercise last logged. It is None only when the kit lists no
    loads or has no load step.
    """
    if not applies(sets, mode, available):
        return tuple(sets)
    found = list(sets)
    for index, _, _, load, _ in _derived(sets, pins, available):
        found[index] = replace(sets[index], load=load)
    return tuple(found)


def _derived(sets, pins, available):
    """(index, pinned load, percent, load, why off the ramp) per warm-up; `why` is None for a warm-up on its ramp,
    `repeat` of an earlier warm-up's load, `none` lighter than the first working set, or `no_step`."""
    first = next(s.load for s in sets if s.working)
    found, seen = [], []
    for index, pinned, percent in _targets(sets, pins, first):
        target = pinned if pinned is not None else first * percent / 100
        load, why = _snapped(target, first, available)
        if why is None and any(abs(load - earlier) < 1e-9 for earlier in seen):
            why = "repeat"
        if load is not None:
            seen.append(load)
        found.append((index, pinned, percent, load, why))
    return found


def _snapped(target, first, available):
    """(load, why open) for `target`: an enumerated kit (rack, belt plates, plate-built bar) through `select`;
    otherwise the increment grid, and no load at all (`no_step`) without an increment, so no raw percent ever
    reaches the athlete. `none` when nothing the kit makes is lighter than the first working load: the load is
    then the lightest the kit makes (the bare bar, the first dumbbell), or None when the kit lists none."""
    chosen = available.select(target, "down", first)
    if chosen is None:
        chosen = available.select(target, "up", first)
    enumerated = not available.geometry_warning and (available.rack or available.belt_loaded or available.plate_built)
    if chosen is not None and not enumerated:
        if not available.increment:
            return None, "no_step"
        chosen = units.round_to_increment(chosen, available.increment, "down")
    if chosen is None or chosen >= first - 1e-9:
        lightest = available.select(0, "up", first)
        return (units.json_number(lightest) if lightest else None), "none"
    return units.json_number(chosen), None


def words(sets, mode, available, pins, load_text):
    """A rationale clause for the warm-up loads, or None when the line has none to explain.

    "warm-ups 50 (50 %) and 75 (75 %), percents of the first working set"; a pinned load reads "60 (pinned)", a
    warm-up the kit cannot make lighter than the first working set reads "20 (nothing lighter than the first
    working set)", and one that repeats an earlier warm-up's load reads "20 again".
    """
    if not applies(sets, mode, available):
        return None
    parts, ramped = [], False
    for _, pinned, percent, load, why in _derived(sets, pins, available):
        if why == "none" and load is None:
            parts.append("none lighter than the first working set")
        elif why == "none":
            parts.append(f"{load_text(load)} (nothing lighter than the first working set)")
        elif why == "no_step":
            parts.append("none (no load step is set for this kit)")
        elif why == "repeat":
            parts.append(f"{load_text(load)} again")
        elif pinned is not None:
            parts.append(f"{load_text(load)} (pinned)")
        else:
            parts.append(f"{load_text(load)} ({units.format_number(percent)} %)")
            ramped = True
    joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return f"warm-ups {joined}" + (", percents of the first working set" if ramped else "")
