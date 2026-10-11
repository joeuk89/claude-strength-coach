"""One starting calorie estimate per phase, for an athlete with no nutrition app (contract C35).

An app athlete never gets one: the app owns expenditure and every calorie target. The method
and every number here are claims in research/protein-energy-deficit.md.
"""

import math

from coach import units
from coach.errors import ValidationError

REF = "rn:protein-energy-deficit."
SEX_OFFSET_KCAL = {"male": 5, "female": -161}
ACTIVITY_LEVEL = {"sedentary": 1.53, "active": 1.76, "vigorous": 2.25}
KCAL_PER_KG = 7700
DAYS_PER_WEEK = 7
ROUND_KCAL = 50
RATE_SIGN = {"cut": -1, "bulk": 1, "maintain": 0, "recomp": 0}
MAX_RATE_PCT = {"cut": 1, "bulk": 0.5}
# The equation's sample was 19–78 years old; outside AGE_RANGE an age is a typo, not an athlete.
AGE_STUDIED = (19, 78)
AGE_RANGE = (13, 120)
METHOD = (f"Mifflin–St Jeor resting rate × the physical activity level, rounded to the nearest {ROUND_KCAL} kcal "
          f"for maintenance, plus the phase's weekly rate × {KCAL_PER_KG} kcal per kg ÷ {DAYS_PER_WEEK}, rounded "
          f"to the nearest {ROUND_KCAL} kcal")

MISSING = {
    "bodyweight": "--bodyweight",
    "sex": "--sex",
    "height": "--height",
    "age": "--age",
    "activity": "--activity",
    "phase": "--phase",
}


def phase_problem(phase, rate, bodyweight=None):
    """Why a weekly rate doesn't fit its phase, or None; the speed is checked only with a bodyweight."""
    if not math.isfinite(rate):
        return f"the {phase} rate must be a number, found {rate}"
    sign = (rate > 0) - (rate < 0)
    if sign != RATE_SIGN[phase]:
        wanted = {-1: "below 0", 1: "above 0", 0: "0"}[RATE_SIGN[phase]]
        return f"a {phase} rate must be {wanted}, found {rate:g}"
    if bodyweight is not None and phase in MAX_RATE_PCT:
        pct = abs(rate) / bodyweight * 100
        if round(pct, 6) > MAX_RATE_PCT[phase]:
            return (f"a {phase} rate of {units.format_number(abs(rate))} a week is {units.format_number(pct)} % "
                    f"of bodyweight, over the {units.format_number(MAX_RATE_PCT[phase])} % most a {phase} uses")
    return None


def resting_kcal(*, sex, weight_kg, height_m, age):
    height_cm = height_m * 100
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + SEX_OFFSET_KCAL[sex]


def _adjustment(rate, unit):
    """kcal a day for a weekly rate in bodyweight units; negative for a loss."""
    sign = -1 if rate < 0 else 1
    return sign * units.mass_kg(abs(rate), unit) * KCAL_PER_KG / DAYS_PER_WEEK


def estimates(*, unit, sex, bodyweight, height_m, age, activity, phases):
    """Maintenance and one estimate per (phase, weekly rate), or each input still missing."""
    given = {"bodyweight": bodyweight, "sex": sex, "height": height_m, "age": age, "activity": activity,
             "phase": phases or None}
    missing = [{"input": name, "flag": MISSING[name], "why": "the starting calorie estimate needs it"}
               for name, value in given.items() if value is None]
    result = {"by": "estimate", "method": METHOD, "resting_kcal": None, "activity_level": None,
              "maintenance_kcal": None, "estimates": [], "refs": [f"{REF}{n}" for n in (14, 15, 16)],
              "missing": missing}
    if missing:
        return result
    for phase, rate in phases:
        problem = phase_problem(phase, rate, bodyweight)
        if problem:
            raise ValidationError(f"the {phase} phase (--phase, or [nutrition] phase and target_rate_per_week): "
                                  f"{problem}")
    resting = round(resting_kcal(sex=sex, weight_kg=units.mass_kg(bodyweight, unit), height_m=height_m, age=age))
    if resting <= 0:
        raise ValidationError(f"the inputs give a resting rate of {resting} kcal; check the height, weight and age")
    maintenance = units.round_to_increment(resting * ACTIVITY_LEVEL[activity], ROUND_KCAL)
    result.update(resting_kcal=resting, activity_level=ACTIVITY_LEVEL[activity], maintenance_kcal=maintenance)
    for phase, rate in phases:
        adjustment = round(_adjustment(rate, unit))
        kcal = units.round_to_increment(maintenance + adjustment, ROUND_KCAL)
        result["estimates"].append({
            "phase": phase, "rate_per_week": units.json_number(rate), "unit": unit,
            "adjustment_kcal": adjustment, "kcal": kcal, "below_resting": kcal < resting,
        })
    return result
