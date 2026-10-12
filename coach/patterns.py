"""Which exercises count as compound or isolation, and the RPE drift rule (contract C23; R-05).

`rpe_drift` is the one drift rule: the proposal's `rpe_drift` flag and the
block's fatigue trigger (R-31) both call it, and `drift_reading` says which
sets it compared and which it set aside.
"""

from dataclasses import dataclass

from coach import units

COMPOUND_PATTERNS = frozenset({
    "squat", "hinge", "lunge", "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
})
ISOLATION_PATTERNS = frozenset({
    "elbow_flexion", "elbow_extension", "shoulder_raise", "knee_flexion", "knee_extension", "hip_abduction",
    "hip_adduction", "calf_raise",
})
DRIFT_OVER_TARGET = 1
DRIFT_MIN_SETS = 2
WORKING_TYPES = ("normal", "dropset", "failure")


def is_compound(entry):
    """True for a library entry with a multi-joint squat, hinge, lunge, press or pull pattern."""
    return bool(entry) and entry.get("pattern") in COMPOUND_PATTERNS


def is_isolation(entry):
    """True for a library entry with a single-joint pattern; core, carry and unclassified work are neither."""
    return bool(entry) and entry.get("pattern") in ISOLATION_PATTERNS


def _field(item, name):
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _working(sets):
    return [s for s in sets if (_field(s, "type") or "normal") in WORKING_TYPES]


@dataclass(frozen=True)
class DriftReading:
    """One exposure's working sets against their own prescribed sets.

    `compared` counts the sets matched by position to a prescribed working set with a target RPE, logged with an
    RPE, and no harder than prescribed. `over` holds the positions (1-based, working sets only) of compared sets
    logged `DRIFT_OVER_TARGET` or more over target; `set_aside` pairs each other position with why it was left out.
    """

    compared: int
    over: tuple
    set_aside: tuple

    @property
    def drifted(self):
        return len(self.over) >= DRIFT_MIN_SETS

    @property
    def steady(self):
        """Enough compared sets to have shown drift, and no drift: an at-prescription exposure."""
        return self.compared >= DRIFT_MIN_SETS and not self.drifted


def _top_reps(item):
    reps = _field(item, "reps")
    if reps is not None:
        return reps
    found = _field(item, "rep_range")
    if isinstance(found, dict):
        return found.get("end")
    return found[1] if found else None


def _harder(logged, target, load_mode):
    """Why a logged set is harder than, or not comparable with, its prescribed set; None when it is comparable."""
    direction = -1 if load_mode == "assisted" else 1
    want, got = _field(target, "load"), _field(logged, "load")
    if load_mode in ("bodyweight", "assisted"):
        want, got = want or 0, got or 0
    if load_mode in units.LOADED_MODES or want is not None:
        if want is None or got is None:
            return "no_load"
        if (got - want) * direction > 1e-9:
            return "heavier"
    top, reps = _top_reps(target), _field(logged, "reps")
    if top is not None and reps is not None and reps > top:
        return "more_reps"
    for name in ("duration_seconds", "distance_meters"):
        want, got = _field(target, name), _field(logged, name)
        if want is not None and got is not None and got > want:
            return "longer"
    return None


def drift_reading(sets, prescribed_sets, capped=None, load_mode=None):
    """Each logged working set against the prescribed working set at its position.

    `capped` is the line's recovery cap, which lowers every target to it. A set past the last prescribed one, one
    heavier, longer or with more reps than prescribed, and one with no target, load or logged RPE is set aside, so
    it can neither show drift nor rule it out. Which exercises are in scope (compound or capped) is the caller's
    decision.
    """
    prescribed = _working(prescribed_sets)
    over, set_aside, compared = [], [], 0
    for position, logged in enumerate(_working(sets), start=1):
        if position > len(prescribed):
            set_aside.append((position, "extra"))
            continue
        target = prescribed[position - 1]
        goal = _field(target, "rpe")
        if capped is not None:
            goal = capped if goal is None else min(goal, capped)
        why = "no_target" if goal is None else _harder(logged, target, load_mode)
        rpe = _field(logged, "rpe")
        if why is None and rpe is None:
            why = "no_rpe"
        if why is not None:
            set_aside.append((position, why))
            continue
        compared += 1
        if rpe >= goal + DRIFT_OVER_TARGET:
            over.append(position)
    return DriftReading(compared=compared, over=tuple(over), set_aside=tuple(set_aside))


def rpe_drift(sets, prescribed_sets, capped=None, load_mode=None):
    """True when two or more compared working sets sit at least 1 RPE over their own targets (`drift_reading`)."""
    return drift_reading(sets, prescribed_sets, capped, load_mode).drifted
