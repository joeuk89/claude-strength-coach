"""Dated bodyweight observations from every store that holds one, under one precedence and basis (contract C35).

A weigh-in kept in the repo is a wellness body mass (`bodyweight record`, `wellness add`); Hevy keeps body
measurements; a nutrition reading holds the app's trend weight or the week's mean scale weight. Raw scale
weights and the app's smoothed trend weight are different quantities, so a rate never mixes the two.
"""

from datetime import timedelta

from coach import dates, nutrition, units
from coach.activity.store import ActivityStore
from coach.hevy.cache import HevyCache

SCALE, TREND = "scale_weight", "trend_weight"
BASES = (TREND, SCALE)
SOURCES = ("wellness", "hevy", "nutrition")
LABELS = {SCALE: "scale weight", TREND: "trend weight"}
TREND_MIN_DAYS = 14
FULL_WEEK = 7


def preferred_basis(config):
    """Trend weight for an athlete whose nutrition app supplies one, else scale weight."""
    return TREND if nutrition.enabled(config) and config["nutrition"]["app"] != "none" else SCALE


def _in_unit(value, from_unit, unit):
    return value if from_unit == unit else units.mass_from_kg(units.mass_kg(value, from_unit), unit)


def _candidates(root, config, unit):
    for item in ActivityStore(root, config).body_masses():
        yield {"date": item["date"], "basis": SCALE, "value": units.mass_from_kg(item["body_mass_kg"], unit),
               "source": "wellness", "ref": f"wellness {item['provenance']['id']}"}
    for measurement in HevyCache(root).body_measurements() or []:
        day = (measurement.get("date") or "")[:10]
        if measurement.get("weight_kg") and day:
            yield {"date": dates.parse_date(day).isoformat(), "basis": SCALE,
                   "value": units.from_hevy_kg(measurement["weight_kg"], "total", unit),
                   "source": "hevy", "ref": f"hevy {day}"}
    for reading in nutrition.readings(root):
        for basis in BASES:
            if reading[basis] is not None:
                yield {"date": reading["date"], "basis": basis,
                       "value": _in_unit(reading[basis], reading["weight_unit"], unit),
                       "source": "nutrition", "ref": f"reading {reading['date']}"}


def observations(root, config, unit, until=None):
    """Every observation dated by `until`, in `unit`, oldest first: one per date and basis.

    On one date and basis the wellness record wins, then Hevy, then the nutrition reading; the
    others are listed in `duplicates` and add no weight.
    """
    grouped = {}
    for found in _candidates(root, config, unit):
        if until is None or found["date"] <= until:
            grouped.setdefault((found["date"], found["basis"]), []).append(found)
    kept = []
    for key in sorted(grouped, key=lambda pair: (pair[0], BASES.index(pair[1]))):
        first, *rest = sorted(grouped[key], key=lambda item: SOURCES.index(item["source"]))
        kept.append(dict(first, duplicates=[{"source": item["source"], "value": item["value"], "ref": item["ref"]}
                                            for item in rest]))
    return kept


def series(found, basis):
    return [item for item in found if item["basis"] == basis]


def rate(points):
    """{rate_per_week, span, days}: from the newest point back to the newest one at least 14 days before it."""
    result = {"rate_per_week": None, "span": None, "days": None}
    if not points:
        return result
    end = points[-1]
    end_day = dates.parse_date(end["date"])
    earlier = [item for item in points if (end_day - dates.parse_date(item["date"])).days >= TREND_MIN_DAYS]
    if not earlier:
        return result
    start = earlier[-1]
    days = (end_day - dates.parse_date(start["date"])).days
    result.update(rate_per_week=round((end["value"] - start["value"]) / days * FULL_WEEK, 2),
                  span={"start": start["date"], "end": end["date"]}, days=days)
    return result


def select(found, preferred):
    """(basis, fallback): the series a trend or a chart reads.

    Trend weight while it supports a rate, else scale weight that does, else whichever has points;
    scale weight whenever it has points. `fallback` is true when the other basis stands in.
    """
    def has(basis):
        return bool(series(found, basis))

    def supported(basis):
        return rate(series(found, basis))["rate_per_week"] is not None

    if preferred == TREND:
        order = ((TREND, supported), (SCALE, supported), (TREND, has), (SCALE, has))
    else:
        order = ((SCALE, has), (TREND, has))
    for basis, test in order:
        if test(basis):
            return basis, basis != preferred
    return preferred, False


def trend(found, preferred, target_rate=None):
    """The rate within the selected basis, with what selected it and where its points came from."""
    basis, fallback = select(found, preferred)
    points = series(found, basis)
    return {"basis": basis, **rate(points), "target_rate_per_week": target_rate, "preferred_basis": preferred,
            "fallback": fallback, "sources": [source for source in SOURCES
                                              if any(item["source"] == source for item in points)]}


def _point_order(item):
    return SOURCES.index(item["source"]), BASES.index(item["basis"])


def nearest(found, day, window_days):
    """The observation nearest `day` within the window; a tie goes to the earlier date, then by source order."""
    near = [((abs((dates.parse_date(item["date"]) - day).days), item["date"], *_point_order(item)), item)
            for item in found if abs((dates.parse_date(item["date"]) - day).days) <= window_days]
    return min(near, key=lambda pair: pair[0])[1] if near else None


def newest(found, today, window_days):
    """The newest observation dated in the `window_days` up to `today`, by source order on that date."""
    since = (today - timedelta(days=window_days)).isoformat()
    recent = [item for item in found if since <= item["date"] <= today.isoformat()]
    if not recent:
        return None
    day = max(item["date"] for item in recent)
    return min((item for item in recent if item["date"] == day), key=_point_order)
