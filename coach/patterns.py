"""Which exercises count as compound or isolation, and the RPE drift rule (contract C23; R-05).

`rpe_drift` is the one drift rule: the proposal's `rpe_drift` flag and the
block's fatigue trigger (R-31) both call it.
"""

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


def rpe_drift(sets, prescribed_sets, capped=None):
    """True when two or more logged working sets sit at least 1 RPE over their target.

    `sets` are one exposure's logged sets and `prescribed_sets` what was
    prescribed for it, matched by position (a logged set past the last
    prescribed one takes the last target). `capped` is the line's recovery
    cap, which lowers every target to it. Which exercises are in scope
    (compound or capped) is the caller's decision.
    """
    targets = [_field(s, "rpe") for s in _working(prescribed_sets)]
    if capped is not None:
        targets = [capped if t is None else min(t, capped) for t in targets] or [capped]
    if not targets:
        return False
    over = 0
    for index, logged in enumerate(_working(sets)):
        target = targets[min(index, len(targets) - 1)]
        rpe = _field(logged, "rpe")
        if target is not None and rpe is not None and rpe >= target + DRIFT_OVER_TARGET:
            over += 1
    return over >= DRIFT_MIN_SETS
