"""The protein reference mass, and the floor, target and stretch set from it (contract C35).

Every threshold and multiplier here is a claim in research/protein-energy-deficit.md.
"""

from coach import units

REF = "rn:protein-energy-deficit."
STEP_G = 5
PER_KG = {
    "fat_free_mass": {"target": 2.0, "stretch": 2.6, "stretch_high": 2.8, "floor_min": 1.5},
    "other": {"target": 1.6, "stretch": 2.2, "stretch_high": 2.2, "floor_min": 1.2},
}
HIGH_BODY_FAT_PCT = {"male": 25, "female": 35}
SEX_WORD = {"male": "men", "female": "women"}
BOTH_LINES = " and ".join(f"the ~{line} % line for {SEX_WORD[sex]}" for sex, line in HIGH_BODY_FAT_PCT.items())
HIGH_BMI = 30
GOAL_GAP_PCT = 10
FLOOR_ABOVE_INTAKE_G = 15

MISSING = {
    "bodyweight": ("--bodyweight", "every protein figure starts from bodyweight"),
    "sex": ("--sex", f"a rough body-fat reading between {BOTH_LINES} is judged against the athlete's own line"),
    "height": ("--height", "with no body-fat reading and no goal weight 10 % or more below bodyweight, BMI decides "
                           "whether body fat is high"),
    "goal_weight": ("--goal-weight", "body fat counts as high, so protein is set from goal weight"),
    "recent_intake": ("--recent-intake", "the floor starts from recent average protein intake"),
}


def _missing(name):
    flag, why = MISSING[name]
    return {"input": name, "flag": flag, "why": why}


def _refs(*numbers):
    return [f"{REF}{n}" for n in numbers]


def _shown(value):
    return units.json_number(round(value, 1))


def _reference(basis, mass, unit, reason, refs, bmi):
    return {"basis": basis, "mass": _shown(mass), "unit": unit, "mass_kg": _shown(units.mass_kg(mass, unit)),
            "reason": reason, "refs": refs, "bmi": bmi}


def reference_mass(*, unit, bodyweight, goal_weight=None, body_fat_pct=None, body_fat_source=None, sex=None,
                   height_m=None):
    """(the reference mass, None), or (None, the name of the input the rules need next)."""
    # Truncated, not rounded, so 29.97 shows as 29.9 and stays under the line.
    bmi = None if height_m is None else units.round_to_increment(
        units.mass_kg(bodyweight, unit) / height_m ** 2, 0.1, "down")
    pct = None if body_fat_pct is None else units.format_number(body_fat_pct)

    if body_fat_source == "credible":
        fat_free = bodyweight * (100 - body_fat_pct) / 100
        return _reference("fat_free_mass", fat_free, unit, f"a credible body-fat reading of {pct} %, so fat-free mass",
                          _refs(3), bmi), None

    if body_fat_source == "rough":
        if sex is not None:
            line = HIGH_BODY_FAT_PCT[sex]
            high = body_fat_pct > line
            against = f"the ~{line} % line for {SEX_WORD[sex]}"
        elif body_fat_pct > max(HIGH_BODY_FAT_PCT.values()):
            high, against = True, BOTH_LINES
        elif body_fat_pct <= min(HIGH_BODY_FAT_PCT.values()):
            high, against = False, BOTH_LINES
        else:
            return None, "sex"
        reason = f"a rough body-fat reading of {pct} %, {'above' if high else 'not above'} {against}"
        refs = _refs(3, 4)
    else:
        gap = None if goal_weight is None else round((bodyweight - goal_weight) / bodyweight * 100, 6)
        if gap is not None and gap >= GOAL_GAP_PCT:
            high = True
            reason = f"no body-fat reading, and the goal weight is {GOAL_GAP_PCT} % or more below bodyweight"
        elif bmi is None:
            return None, "height"
        else:
            high = bmi >= HIGH_BMI
            reason = (f"no body-fat reading, and BMI {units.format_number(bmi)} is {HIGH_BMI} or more" if high else
                      f"no body-fat reading, BMI {units.format_number(bmi)} is under {HIGH_BMI} and no goal weight is "
                      f"{GOAL_GAP_PCT} % or more below bodyweight")
        refs = _refs(3, 5)

    if not high:
        return _reference("bodyweight", bodyweight, unit, reason + ", so bodyweight", refs, bmi), None
    if goal_weight is None:
        return None, "goal_weight"
    return _reference("goal_weight", goal_weight, unit, reason + ", so goal weight", refs, bmi), None


def _grams(mass_kg, per_kg, direction="nearest"):
    return units.round_to_increment(mass_kg * per_kg, STEP_G, direction)


def numbers(reference, recent_intake_g):
    """The target, stretch and floor in grams; the floor's `g` is None without a recent intake."""
    mass_kg = units.mass_kg(reference["mass"], reference["unit"])
    fat_free = reference["basis"] == "fat_free_mass"
    per_kg = PER_KG["fat_free_mass" if fat_free else "other"]
    converted = _refs(6) if fat_free else []

    target_g = _grams(mass_kg, per_kg["target"])
    floor_min = _grams(mass_kg, per_kg["floor_min"], "up")
    floor = {"g": None, "g_min": floor_min, "g_per_kg_min": per_kg["floor_min"], "from_intake_g": None,
             "clamped": None, "refs": _refs(8, 7)}
    if recent_intake_g is not None:
        # The first 5 g step at or above intake + 15 g always lands 15–20 g above intake.
        from_intake = units.round_to_increment(recent_intake_g + FLOOR_ABOVE_INTAKE_G, STEP_G, "up")
        clamped = "min" if from_intake < floor_min else "target" if from_intake > target_g else None
        floor.update(g=min(max(from_intake, floor_min), target_g), from_intake_g=from_intake, clamped=clamped)
    return {
        "target": {"g": target_g, "g_per_kg": per_kg["target"], "refs": _refs(1) + converted},
        "stretch": {"g": _grams(mass_kg, per_kg["stretch"]), "g_high": _grams(mass_kg, per_kg["stretch_high"]),
                    "g_per_kg": per_kg["stretch"], "g_per_kg_high": per_kg["stretch_high"],
                    "refs": _refs(2) + converted},
        "floor": floor,
    }


def targets(*, unit, bodyweight, goal_weight=None, body_fat_pct=None, body_fat_source=None, sex=None,
            height_m=None, recent_intake_g=None):
    """The reference mass, the three numbers, and each input the rules still need."""
    missing = []
    reference = None
    if bodyweight is None:
        missing.append(_missing("bodyweight"))
    else:
        reference, needed = reference_mass(unit=unit, bodyweight=bodyweight, goal_weight=goal_weight,
                                           body_fat_pct=body_fat_pct, body_fat_source=body_fat_source, sex=sex,
                                           height_m=height_m)
        if needed:
            missing.append(_missing(needed))
    if recent_intake_g is None:
        missing.append(_missing("recent_intake"))
    return {"reference": reference, "protein": None if reference is None else numbers(reference, recent_intake_g),
            "missing": missing}
