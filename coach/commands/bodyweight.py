"""`bodyweight` commands: keep a weigh-in without nutrition or activity set up, and list every source (C35)."""

from coach import bodyweight, dates, units
from coach.activity import actions
from coach.activity.store import ActivityStore
from coach.commands import arg, command
from coach.errors import ValidationError


@command(
    "bodyweight record",
    help="Keep one dated weigh-in as a manual wellness body mass; needs neither [nutrition] nor [activity] on, "
         "and repeating the same weigh-in writes nothing",
    args=(
        arg("--weight", type=float, required=True, metavar="X", help="the weigh-in, in [athlete] bodyweight_units"),
        arg("--date", help="the day of the weigh-in, YYYY-MM-DD (default: today)"),
        arg("--replace", action="store_true", help="correct a different weigh-in already recorded for the date"),
    ),
    writes=True,
)
def record(args, ctx):
    if args.weight <= 0:
        raise ValidationError(f"--weight must be more than 0, found {args.weight:g}")
    day = actions.parse_date(args.date, "--date").isoformat() if args.date else ctx.today().isoformat()
    unit = ctx.config.athlete.bodyweight_units
    kg = units.to_hevy_kg(args.weight, "total", unit)
    store = ActivityStore(ctx.root, ctx.config)
    record_id = f"manual:{day}-wellness"
    current = store.latest("wellness").get(record_id)
    item = dict(current) if current is not None and current["op"] == "upsert" else {}
    before = item.get("body_mass_kg")
    if before is not None and before != kg and not args.replace:
        raise ValidationError(f"{day} already has a weigh-in of {units.mass_from_kg(before, unit):g} {unit}; "
                              "pass --replace to correct it")
    item.update({"id": record_id, "start": day, "end": day, "body_mass_kg": kg})
    result = actions.write(store, "wellness", actions.build_manual(ctx, "wellness", item), args.dry_run)
    return {**result, "weigh_in": {"date": day, "value": units.json_number(args.weight), "unit": unit},
            "replaced": before is not None and before != kg}


@command(
    "bodyweight list",
    help="Every dated bodyweight observation in bodyweight units, one per date and basis, and the trend it supports",
    args=(arg("--last", type=int, metavar="N", help="only the newest N observations"),),
)
def list_observations(args, ctx):
    if args.last is not None and args.last < 1:
        raise ValidationError("--last must be 1 or more")
    unit = ctx.config.athlete.bodyweight_units
    found = bodyweight.observations(ctx.root, ctx.config, unit, until=ctx.today().isoformat())
    trend = bodyweight.trend(found, bodyweight.preferred_basis(ctx.config))
    shown = found[-args.last:] if args.last else found
    return {"unit": unit, "observations": shown, "count": len(shown), "trend": trend}
