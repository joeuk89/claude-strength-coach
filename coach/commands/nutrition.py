import json
from pathlib import Path

from coach import dates, nutrition, paths
from coach.commands import arg, command
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
