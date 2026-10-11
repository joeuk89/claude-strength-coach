"""Nutrition config, the readings series and `nutrition status` (contract C4, C35).

A reading is what the athlete read off the nutrition app (or the scale)
at one check-in. The app owns expenditure and every calorie target: this
module stores its numbers and never computes one. `status` turns the
config and the series into numbers and flags; the coach proposes, the
athlete approves, and config changes go through /goals (ADR-0002).
"""

import copy
import json
from datetime import date, timedelta
from pathlib import Path

from coach import config as config_module
from coach import dates, jsonio, paths, units
from coach.errors import ValidationError
from coach.validate import Error, validate

SCHEMA = "nutrition_readings"
SCHEMA_VERSION = 1
READING_FIELDS = ("trend_weight", "scale_weight", "expenditure_kcal", "target_kcal", "target_protein_g",
                  "avg_kcal", "avg_protein_g", "days_logged", "anchors_most_days", "note")
NEEDS_ONE_OF = ("trend_weight", "scale_weight", "avg_protein_g")
FULL_WEEK = 7
TREND_MIN_DAYS = 14
STALE_AFTER_DAYS = 14

QUESTION_READINGS_APP = ("trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein) · "
                         "days logged")
QUESTION_READINGS_NO_APP = "this week's morning weigh-ins · average daily protein, if you track it"
QUESTION_ANCHORS = "anchors most days (y/n)?"
QUESTION_PLAN = "Anything in the plan that didn't work?"
QUESTION_NEXT_WEEK = "food exceptions next week: who cooks which nights, office-day changes, meals out?"


def enabled(config):
    nutrition = config.get("nutrition") if config is not None else None
    return bool(nutrition and nutrition.get("enabled"))


def config(root):
    """The validated [nutrition] table, or None when nutrition is not enabled."""
    loaded = config_module.load(root)
    return loaded["nutrition"] if enabled(loaded) else None


def _schema():
    return jsonio.load_schema(SCHEMA)


def problems(doc):
    """What the schema cannot say: real dates, order, uniqueness, and a reading worth keeping."""
    found = []
    previous = None
    for index, reading in enumerate(doc["readings"]):
        where = f"$.readings[{index}]"
        try:
            day = dates.parse_date(reading["date"])
        except ValueError as exc:
            found.append(Error(f"{where}.date", str(exc)))
            continue
        if previous is not None and day <= previous:
            what = "repeats" if day == previous else "comes before"
            found.append(Error(f"{where}.date", f"{reading['date']} {what} the reading above it; "
                                                "readings are sorted by date with one per date"))
        previous = day
        if all(reading.get(key) is None for key in NEEDS_ONE_OF):
            found.append(Error(where, f"a reading sets at least one of {', '.join(NEEDS_ONE_OF)}"))
        window = reading.get("window")
        if window:
            try:
                dates.Span(dates.parse_date(window["start"]), dates.parse_date(window["end"]))
            except ValueError as exc:
                found.append(Error(f"{where}.window", str(exc)))
    return found


def _check(doc, label):
    errors = validate(doc, _schema()) or problems(doc)
    if errors:
        raise ValidationError(f"{label} is not a valid nutrition readings series ({len(errors)} problem(s)): "
                              f"{errors[0].path}: {errors[0].message}",
                              details=[error.to_json() for error in errors])


def read_doc(root):
    path = root / paths.NUTRITION_READINGS
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "readings": []}
    doc = jsonio.read_doc(path, SCHEMA)
    _check(doc, paths.NUTRITION_READINGS.as_posix())
    return doc


def readings(root):
    return read_doc(root)["readings"]


def new_reading(values, *, day, source, weight_unit):
    """A reading in C35 field order; fields the values leave out are null."""
    reading = {"date": day, "source": source}
    if values.get("window") is not None:
        reading["window"] = values["window"]
    reading["weight_unit"] = weight_unit
    for key in READING_FIELDS:
        value = values.get(key)
        reading[key] = units.json_number(value) if isinstance(value, float) else value
    return reading


def merge(existing, incoming, replace):
    """Add `incoming` to `existing` by date; return (sorted readings, replaced dates)."""
    by_date = {reading["date"]: reading for reading in existing}
    clashes = [reading["date"] for reading in incoming if reading["date"] in by_date]
    if clashes and not replace:
        raise ValidationError(f"a reading already exists for {', '.join(clashes)}; pass --replace to overwrite it")
    for reading in incoming:
        by_date[reading["date"]] = reading
    return [by_date[key] for key in sorted(by_date)], clashes


def write(root, series, dry_run):
    doc = {"schema_version": SCHEMA_VERSION, "readings": series}
    _check(doc, paths.NUTRITION_READINGS.as_posix())
    jsonio.write_doc(root / paths.NUTRITION_READINGS, doc, dry_run)
    return not dry_run


def _iso(value):
    return value.isoformat() if isinstance(value, date) else value


def _plain(section):
    return {key: _iso(value) for key, value in section.items()}


def _override_state(override, today):
    if today >= override["expires"]:
        return "expired"
    if today < override["start"]:
        return "upcoming"
    return "active"


def _trend(series, basis, weight_unit, target_rate):
    points = [(dates.parse_date(r["date"]), r[basis]) for r in series
              if r[basis] is not None and r["weight_unit"] == weight_unit]
    trend = {"basis": basis, "rate_per_week": None, "span": None, "days": None,
             "target_rate_per_week": target_rate}
    if not points:
        return trend
    end_day, end_weight = points[-1]
    earlier = [(day, weight) for day, weight in points if (end_day - day).days >= TREND_MIN_DAYS]
    if not earlier:
        return trend
    start_day, start_weight = earlier[-1]
    days = (end_day - start_day).days
    trend.update(rate_per_week=round((end_weight - start_weight) / days * FULL_WEEK, 2),
                 span={"start": start_day.isoformat(), "end": end_day.isoformat()}, days=days)
    return trend


def _num(value):
    value = units.json_number(value)
    return f"{round(value, 1):g}" if isinstance(value, float) else str(value)


def override_view(nutrition, today):
    """The [nutrition.override] table with its state, or None when there is none."""
    if "override" not in nutrition:
        return None
    view = _plain(nutrition["override"])
    view["state"] = _override_state(nutrition["override"], today)
    return view


def override_flags(override, has_app):
    if override is None:
        return []
    flags = []
    if override["state"] == "expired":
        back_to = "the app's numbers" if has_app else "the calorie target on file"
        flags.append({
            "code": "override_expired",
            "message": f"The nutrition override ({override['what']}) expired on {override['expires']}. "
                       f"Tell the athlete they are back on {back_to} and remove [nutrition.override]; "
                       "renewing it needs /goals.",
            "expires": override["expires"],
        })
    if override["renewal"] >= 2:
        flags.append({
            "code": "override_renewed_twice",
            "message": "The nutrition override is on its second consecutive renewal: a sign the plan itself "
                       "needs changing (usually the phase or the trend rate). Flag it at every check-in "
                       "while it stands.",
            "renewal": override["renewal"],
        })
    return flags


def _flags(nutrition, series, override, today):
    protein = nutrition["protein"]
    floor, target, step = protein["floor_g"], protein["target_g"], protein["floor_step_g"]
    has_app = nutrition["app"] != "none"
    flags = []
    latest = series[-1] if series else None
    active = override is not None and override["state"] == "active"
    since_floor = [r for r in series if dates.parse_date(r["date"]) >= protein["floor_since"]]
    counted = since_floor[-2:]
    if (floor < target and len(counted) == 2
            and all(r["avg_protein_g"] is not None and r["avg_protein_g"] >= floor for r in counted)):
        proposed = min(floor + step, target)
        # The counted readings measured weeks under the old floor, so the new floor's count starts after them.
        since = (dates.parse_date(counted[-1]["date"]) + timedelta(days=1)).isoformat()
        shown = ", ".join(f"{r['date']}: {_num(r['avg_protein_g'])} g" for r in counted)
        app_note = ""
        if has_app:
            app_target = latest["target_protein_g"]
            if app_target is None:
                app_note = "; check the app target and raise it only if below the new floor"
            elif app_target < proposed:
                app_note = f"; propose raising the app's protein to at least {_num(proposed)} g"
            else:
                app_note = f"; retain the app's compatible {_num(app_target)} g protein target"
        if active:
            app_note += "; review whether the active override covers protein before changing agreed values"
        flags.append({
            "code": "protein_floor_raise",
            "message": f"Average protein met the {_num(floor)} g floor at the last two check-ins ({shown}). "
                       f"Propose raising the floor to {_num(proposed)} g in [nutrition.protein] floor_g, with "
                       f"floor_since = {since}{app_note}.",
            "floor_g": floor, "proposed_floor_g": proposed, "proposed_floor_since": since,
            "dates": [r["date"] for r in counted],
        })

    unmeasured = since_floor[-3:]
    if (not has_app and floor < target and len(unmeasured) == 3
            and all(r["source"] == "scale" and r["avg_protein_g"] is None for r in unmeasured)):
        flags.append({
            "code": "protein_unmeasured",
            "message": "The last three no-app check-ins have no measured weekly protein average. "
                       "Anchor adherence cannot establish grams or qualify a floor raise. Offer optional "
                       "protein calibration, an explicit /goals review, or a deliberate hold at the current floor. "
                       "Keep a one-day estimate in notes, not in the measured weekly average.",
            "floor_g": floor, "target_g": target, "dates": [r["date"] for r in unmeasured],
            "refs": ["rn:protein-energy-deficit.20"],
        })

    flags += override_flags(override, has_app)

    if latest is not None and has_app and latest["target_protein_g"] is not None \
            and latest["target_protein_g"] < floor:
        flags.append({
            "code": "app_protein_mismatch",
            "message": f"The app's protein target ({_num(latest['target_protein_g'])} g) is below the floor "
                       f"({_num(floor)} g). Review raising the app target to at least the floor"
                       + (", unless the active override covers protein." if active else "."),
            "app_protein_g": latest["target_protein_g"], "floor_g": floor, "override_active": active,
        })
    if latest is not None and latest["days_logged"] is not None and latest["days_logged"] < FULL_WEEK:
        flags.append({
            "code": "logging_incomplete",
            "message": f"{latest['days_logged']} of {FULL_WEEK} days logged. Ask for every day logged, with an "
                       "estimate of the day or the missed meal on a day they couldn't track, and no "
                       "half-logged days.",
            "days_logged": latest["days_logged"],
        })
    if latest is None or (today - dates.parse_date(latest["date"])).days > STALE_AFTER_DAYS:
        since = "no reading is on file" if latest is None else f"the last reading is from {latest['date']}"
        flags.append({
            "code": "no_recent_reading",
            "message": f"No nutrition reading in the last {STALE_AFTER_DAYS} days: {since}. Record one with "
                       "python3 -m coach nutrition record.",
            "last_reading": latest["date"] if latest else None,
        })
    return flags


def current_plan(root, today):
    """The rendered path of the meal plan whose span holds `today` (the latest-starting one), or None."""
    directory = Path(root) / paths.MEAL_PLANS_DATA_DIR
    covering = []
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            span = json.loads(path.read_text(encoding="utf-8"))["span"]
            start, end = dates.parse_date(span["start"]), dates.parse_date(span["end"])
        except (ValueError, KeyError, TypeError):
            continue
        if start <= today <= end:
            covering.append((start, path.stem))
    if not covering:
        return None
    return (paths.MEAL_PLANS_DIR / f"{max(covering)[1]}.md").as_posix()


def status(root, today):
    loaded = config_module.load(root)
    if not enabled(loaded):
        return {"enabled": False, "brief_line": None, "questions": []}
    nutrition = loaded["nutrition"]
    weight_unit = loaded["athlete"]["bodyweight_units"]
    series = readings(root)
    has_app = nutrition["app"] != "none"

    override = override_view(nutrition, today)

    data = {
        "enabled": True,
        "app": nutrition["app"],
        "phase": nutrition["phase"],
        "weight_unit": weight_unit,
        "target_rate_per_week": nutrition["target_rate_per_week"],
        "goal_weight": nutrition.get("goal_weight"),
        "kcal_target": nutrition.get("kcal_target"),
        "protein": _plain(nutrition["protein"]),
        "anchors": [copy.deepcopy(dict(anchor)) for anchor in nutrition["anchors"]],
        "override": override,
        "template": "template" in nutrition,
        "latest_reading": copy.deepcopy(series[-1]) if series else None,
        "trend": _trend(series, "trend_weight" if has_app else "scale_weight", weight_unit,
                        nutrition["target_rate_per_week"]),
        "flags": _flags(nutrition, series, override, today),
        "plan": current_plan(root, today),
    }
    data["brief_line"] = brief_line(data)
    data["questions"] = questions(data)
    return data


def brief_line(status):
    """One line for the standing brief, or None when nutrition is off."""
    if not status.get("enabled"):
        return None
    latest = status["latest_reading"]
    if latest is None:
        last_week = "no reading yet"
    elif latest["avg_protein_g"] is None:
        last_week = "last week not tracked"
    else:
        last_week = f"last week {_num(latest['avg_protein_g'])} g"
    anchors = ", ".join(anchor["name"] for anchor in status["anchors"]) or "none"
    override = status["override"]
    if override is None:
        override_text = "none"
    elif override["state"] == "expired":
        override_text = f"expired {override['expires']}"
    elif override["state"] == "upcoming":
        override_text = f"{override['what']}, from {override['start']}"
    else:
        override_text = f"{override['what']}, until {override['expires']}"
    line = (f"Food: protein floor {_num(status['protein']['floor_g'])} g, {last_week} · anchors: {anchors} · "
            f"override: {override_text}")
    if status.get("plan"):
        line += f" · plan: {status['plan']}"
    return line


def questions(status):
    """The Sunday message's food questions; the third only with a standing weekly template."""
    if not status.get("enabled"):
        return []
    habits = f"{QUESTION_ANCHORS} {QUESTION_PLAN}" if status["anchors"] else QUESTION_PLAN
    found = [QUESTION_READINGS_APP if status["app"] != "none" else QUESTION_READINGS_NO_APP, habits]
    if status.get("template"):
        found.append(QUESTION_NEXT_WEEK)
    return found

