import json
from pathlib import Path

from coach import calories, dates, nutrition, paths, protein, units
from coach.commands import arg, command
from coach.config_tables.nutrition import APPS, PHASES
from coach.errors import ConfigError, ValidationError

_REPLACE = arg("--replace", action="store_true", help="overwrite a reading already on file for the same date")


def _enabled_config(ctx):
    if not nutrition.enabled(ctx.config):
        raise ConfigError("nutrition is not enabled: set [nutrition] enabled = true in config.toml (/goals sets "
                          "up the table)")
    return ctx.config


def _date(text):
    try:
        return dates.parse_date(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"--date: {exc}") from None


@command("nutrition status",
         help="Targets in force, the latest reading, the weight trend, the override and the flags; "
              "also the brief line and the food questions")
def status(args, ctx):
    return nutrition.status(ctx.root, ctx.today())


def _positive(name, value):
    if value is not None and value <= 0:
        raise ValidationError(f"{name} must be more than 0, found {value:g}")


# Plausible adult heights: a guard against a height given in metres or in the other unit.
HEIGHT_RANGE_M = (1.0, 2.5)


def _fresh(series, today, pick):
    """`pick(reading)` from the newest reading of the last STALE_AFTER_DAYS that has one, as (value, where from)."""
    for reading in reversed(series):
        if (today - dates.parse_date(reading["date"])).days > nutrition.STALE_AFTER_DAYS:
            return None
        value = pick(reading)
        if value is not None:
            return value, f"reading {reading['date']}"
    return None


def _weight(unit):
    def pick(reading):
        if reading["weight_unit"] != unit:
            return None
        return reading["trend_weight"] if reading["trend_weight"] is not None else reading["scale_weight"]
    return pick


def _height_m(height, height_unit, weight_unit):
    if height is None:
        return None
    height_unit = height_unit or ("cm" if weight_unit == "kg" else "in")
    metres = units.height_m(height, height_unit)
    if not HEIGHT_RANGE_M[0] <= metres <= HEIGHT_RANGE_M[1]:
        raise ValidationError(f"--height {height:g} {height_unit} is {metres:g} m; give the height in "
                              f"{height_unit}, or set --height-unit")
    return metres


def _given(value, fallback, **extra):
    if value is not None:
        return {"value": units.json_number(value), **extra, "from": "flag"}
    if fallback is None:
        return None
    return {"value": units.json_number(fallback[0]), **extra, "from": fallback[1]}


def _value(given):
    return None if given is None else given["value"]


def _phase(text):
    name, _, rate = text.partition(":")
    try:
        rate = float(rate)
    except ValueError:
        rate = None
    if name not in PHASES or rate is None:
        raise ValidationError(f"--phase takes PHASE:RATE, a phase of {', '.join(PHASES)} and its weekly rate in "
                              f"bodyweight units (cut:-0.5), found {text!r}")
    problem = calories.phase_problem(name, rate)
    if problem:
        raise ValidationError(f"--phase {text}: {problem}")
    return [name, units.json_number(rate)]


def _check_age(age, ctx):
    if age is None:
        return
    low, high = calories.AGE_RANGE
    if not low <= age <= high:
        raise ValidationError(f"--age is in years, between {low} and {high}; found {age:g}")
    low, high = calories.AGE_STUDIED
    if not low <= age <= high:
        ctx.warn(f"age {age:g} is outside the {low}–{high} years the resting-rate equation was built on, so treat "
                 "the calorie estimate as rougher still")


def _calories(args, table, inputs, unit):
    app = args.app or table.get("app")
    if app is None:
        return None, [{"input": "app", "flag": "--app", "why": "only an athlete with no nutrition app gets a "
                       "calorie estimate"}]
    if app != "none":
        return {"by": "app"}, []
    estimate = calories.estimates(unit=unit, sex=args.sex, bodyweight=_value(inputs["bodyweight"]),
                                  height_m=inputs["height_m"], age=args.age, activity=args.activity,
                                  phases=_value(inputs["phases"]))
    return estimate, estimate.pop("missing")


def _warn_below_resting(estimate, ctx):
    for row in (estimate or {}).get("estimates", ()):
        if row["below_resting"]:
            ctx.warn(f"the {row['phase']} estimate ({row['kcal']} kcal) is under the resting rate "
                     f"({estimate['resting_kcal']} kcal): slow the rate or check the inputs before using it")


@command(
    "nutrition targets",
    help="The protein reference mass and the floor, target and stretch set from it; names any input still missing",
    args=(
        arg("--bodyweight", type=float, metavar="X", help="bodyweight in [athlete] bodyweight_units (default: the "
            "newest reading's weight from the last 14 days)"),
        arg("--goal-weight", type=float, metavar="X", help="goal weight (default: [nutrition] goal_weight)"),
        arg("--body-fat", type=float, metavar="PCT", help="a body-fat reading, in %%; needs --body-fat-source"),
        arg("--body-fat-source", choices=("credible", "rough"), help="credible: DEXA, a BodPod, underwater "
            "weighing or skinfolds by an experienced tester, from the last ~3 months; rough: anything else, such "
            "as a smart scale or a tape method"),
        arg("--sex", choices=tuple(protein.HIGH_BODY_FAT_PCT), help="judges a rough body-fat reading"),
        arg("--height", type=float, metavar="N", help="for the BMI cue with a rough or absent body-fat reading"),
        arg("--height-unit", choices=units.HEIGHT_UNITS, help="default: cm with kg bodyweight, in with lb"),
        arg("--recent-intake", type=float, metavar="G", help="recent average protein a day, g (default: the newest "
            "reading's 7-day average from the last 14 days)"),
        arg("--app", choices=APPS, help="the nutrition app (default: [nutrition] app); only \"none\" gets a "
            "calorie estimate"),
        arg("--age", type=float, metavar="YEARS", help="for the calorie estimate"),
        arg("--activity", choices=tuple(calories.ACTIVITY_LEVEL), help="for the calorie estimate: sedentary (a "
            "seated job, little activity beyond training), active (an hour or so of exercise or walking most days), "
            "vigorous (hard physical work or several hours of sport a day)"),
        arg("--phase", action="append", metavar="PHASE:RATE", help="a phase and its weekly rate in bodyweight "
            "units, such as cut:-0.5; repeat for each phase (default: [nutrition] phase and target_rate_per_week)"),
    ),
)
def targets(args, ctx):
    if (args.body_fat is None) != (args.body_fat_source is None):
        raise ValidationError("--body-fat and --body-fat-source go together: give both or neither")
    if args.body_fat is not None and not 0 < args.body_fat < 100:
        raise ValidationError(f"--body-fat is a percentage between 0 and 100, found {args.body_fat:g}")
    for name, value in (("--bodyweight", args.bodyweight), ("--goal-weight", args.goal_weight),
                        ("--height", args.height), ("--recent-intake", args.recent_intake)):
        _positive(name, value)
    _check_age(args.age, ctx)
    phases = [_phase(text) for text in args.phase or ()]

    unit = ctx.config["athlete"]["bodyweight_units"]
    table = ctx.config.get("nutrition") or {}
    goal_on_file = table.get("goal_weight")
    phase_on_file = None
    if table.get("phase") is not None and table.get("target_rate_per_week") is not None:
        phase_on_file = ([[table["phase"], units.json_number(table["target_rate_per_week"])]], "config")
    series = nutrition.readings(ctx.root)
    today = ctx.today()
    weight = _fresh(series, today, _weight(unit))
    inputs = {
        "bodyweight": _given(args.bodyweight, weight, unit=unit),
        "goal_weight": _given(args.goal_weight, None if goal_on_file is None else (goal_on_file, "config"),
                              unit=unit),
        "body_fat": None if args.body_fat is None else {"pct": units.json_number(args.body_fat),
                                                        "source": args.body_fat_source},
        "sex": args.sex,
        "height_m": _height_m(args.height, args.height_unit, unit),
        "recent_intake_g": _given(args.recent_intake,
                                  _fresh(series, today, lambda reading: reading["avg_protein_g"])),
        "age": None if args.age is None else units.json_number(args.age),
        "activity": args.activity,
        "phases": _given(phases or None, phase_on_file),
    }
    result = protein.targets(unit=unit, bodyweight=_value(inputs["bodyweight"]),
                             goal_weight=_value(inputs["goal_weight"]), body_fat_pct=args.body_fat,
                             body_fat_source=args.body_fat_source, sex=args.sex, height_m=inputs["height_m"],
                             recent_intake_g=_value(inputs["recent_intake_g"]))
    result["calories"], needed = _calories(args, table, inputs, unit)
    _warn_below_resting(result["calories"], ctx)
    named = {item["input"] for item in result["missing"]}
    result["missing"] += [item for item in needed if item["input"] not in named]
    return {"inputs": inputs, **result}


@command("nutrition readings", help="The nutrition readings series, oldest first",
         args=(arg("--last", type=int, metavar="N", help="only the newest N readings"),))
def readings(args, ctx):
    series = nutrition.readings(ctx.root)
    if args.last is not None:
        if args.last < 1:
            raise ValidationError("--last must be 1 or more")
        series = series[-args.last:]
    return {"path": paths.NUTRITION_READINGS, "readings": series, "count": len(series)}


@command(
    "nutrition record",
    help="Add one reading from the athlete's check-in reply: the app's numbers, or morning weigh-ins without one",
    args=(
        arg("--date", help="the check-in date, YYYY-MM-DD (default: today)"),
        arg("--trend-weight", type=float, metavar="X", help="the app's trend weight, in bodyweight units"),
        arg("--scale-weight", type=float, metavar="X", help="no app: the mean of the week's morning weigh-ins"),
        arg("--expenditure", type=float, metavar="N", help="the app's expenditure, kcal"),
        arg("--target-kcal", type=float, metavar="N", help="the app's calorie target"),
        arg("--target-protein", type=float, metavar="N", help="the app's protein target, g"),
        arg("--avg-kcal", type=float, metavar="N", help="7-day average calories"),
        arg("--avg-protein", type=float, metavar="N", help="7-day average protein, g"),
        arg("--days-logged", type=int, metavar="N", help="days logged of the last 7"),
        arg("--anchors", choices=("yes", "no"), help="protein anchors eaten most days"),
        arg("--note", metavar="S", help="one line of context"),
        _REPLACE,
    ),
    writes=True,
)
def record(args, ctx):
    cfg = _enabled_config(ctx)
    values = {
        "trend_weight": args.trend_weight, "scale_weight": args.scale_weight,
        "expenditure_kcal": args.expenditure, "target_kcal": args.target_kcal,
        "target_protein_g": args.target_protein, "avg_kcal": args.avg_kcal, "avg_protein_g": args.avg_protein,
        "days_logged": args.days_logged,
        "anchors_most_days": None if args.anchors is None else args.anchors == "yes",
        "note": args.note,
    }
    day = _date(args.date) if args.date else ctx.today().isoformat()
    source = "app" if cfg.nutrition.app != "none" else "scale"
    reading = nutrition.new_reading(values, day=day, source=source, weight_unit=cfg.athlete.bodyweight_units)
    series, replaced = nutrition.merge(nutrition.readings(ctx.root), [reading], args.replace)
    written = nutrition.write(ctx.root, series, args.dry_run)
    return {"path": paths.NUTRITION_READINGS, "reading": reading, "replaced": bool(replaced), "written": written}


def _load_input(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValidationError(f"--input: no file at {path}") from None
    except json.JSONDecodeError as exc:
        raise ValidationError(f"--input: {path} is not valid JSON: {exc}") from None
    items = raw.get("readings") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise ValidationError(f"--input: {path} must hold a list of readings, or an object with a readings list")
    return items


_IMPORT_KEYS = {"date", "source", "window", "weight_unit", *nutrition.READING_FIELDS}


@command(
    "nutrition import",
    help="Merge a list of readings seeded once from archived check-ins; each is stored with source \"seeded\"",
    args=(arg("--input", required=True, metavar="FILE", help="JSON: a list of readings, or {\"readings\": [...]}"),
          _REPLACE),
    writes=True,
)
def import_readings(args, ctx):
    cfg = _enabled_config(ctx)
    incoming, problems = [], []
    for index, item in enumerate(_load_input(args.input)):
        where = f"$[{index}]"
        unknown = sorted(set(item) - _IMPORT_KEYS)
        if unknown:
            problems.append({"path": where, "message": f"unknown field(s): {', '.join(unknown)}"})
            continue
        if item.get("source", "seeded") != "seeded":
            problems.append({"path": f"{where}.source",
                             "message": f"import only adds seeded readings (found {item['source']!r})"})
            continue
        if not isinstance(item.get("date"), str):
            problems.append({"path": f"{where}.date", "message": "every reading needs a date, YYYY-MM-DD"})
            continue
        incoming.append(nutrition.new_reading(item, day=item["date"], source="seeded",
                                              weight_unit=item.get("weight_unit", cfg.athlete.bodyweight_units)))
    seen = [reading["date"] for reading in incoming]
    repeated = sorted({day for day in seen if seen.count(day) > 1})
    if repeated:
        problems.append({"path": "$", "message": f"the input repeats {', '.join(repeated)}"})
    if problems:
        raise ValidationError(f"--input: {problems[0]['path']}: {problems[0]['message']}", details=problems)
    series, replaced = nutrition.merge(nutrition.readings(ctx.root), incoming, args.replace)
    written = nutrition.write(ctx.root, series, args.dry_run)
    return {"path": paths.NUTRITION_READINGS, "readings": incoming, "replaced": replaced, "written": written}
