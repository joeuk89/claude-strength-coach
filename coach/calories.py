"""One starting calorie estimate per phase, for an athlete with no nutrition app (contract C35).

An app athlete never gets one: the app owns expenditure and every calorie target. The method
and every number here are claims in research/protein-energy-deficit.md.
"""

from coach import units

REF = "rn:protein-energy-deficit."
METHOD = ("Mifflin–St Jeor resting rate × the physical activity level, plus the phase's weekly rate × "
          "7700 kcal per kg ÷ 7, rounded to the nearest 50 kcal")
SEX_OFFSET_KCAL = {"male": 5, "female": -161}
ACTIVITY_LEVEL = {"sedentary": 1.53, "active": 1.76, "vigorous": 2.25}
KCAL_PER_KG = 7700
DAYS_PER_WEEK = 7
ROUND_KCAL = 50

MISSING = {
    "bodyweight": "--bodyweight",
    "sex": "--sex",
    "height": "--height",
    "age": "--age",
    "activity": "--activity",
    "phase": "--phase",
}


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
    resting = resting_kcal(sex=sex, weight_kg=units.mass_kg(bodyweight, unit), height_m=height_m, age=age)
    maintenance = resting * ACTIVITY_LEVEL[activity]
    result.update(resting_kcal=round(resting), activity_level=ACTIVITY_LEVEL[activity],
                  maintenance_kcal=units.round_to_increment(maintenance, ROUND_KCAL))
    for phase, rate in phases:
        adjustment = _adjustment(rate, unit)
        result["estimates"].append({
            "phase": phase, "rate_per_week": units.json_number(rate), "unit": unit,
            "adjustment_kcal": round(adjustment),
            "kcal": units.round_to_increment(maintenance + adjustment, ROUND_KCAL),
        })
    return result
