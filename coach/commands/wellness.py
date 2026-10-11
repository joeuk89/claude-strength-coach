"""`wellness` commands: sleep and daily health readings (contract C29, C30)."""

from datetime import timedelta

from coach import dates, units
from coach.activity import actions
from coach.commands import arg, command
from coach.commands.activity import SPAN_ARGS
from coach.errors import ValidationError

FIELDS = ("sleep_hours", "in_bed_hours", "resting_hr", "steps", "body_mass", "body_fat_pct")


@command("wellness list", help="One resolved wellness day per date in the span that has any value", args=SPAN_ARGS)
def list_days(args, ctx):
    store = actions.store_for(ctx)
    span = actions.span(args, ctx)
    return {"span": span.to_json(), "days": store.wellness_days(span)}


@command("wellness summary", help="Sleep average with nightly and period-mean provenance", args=SPAN_ARGS)
def summary(args, ctx):
    store = actions.store_for(ctx)
    span = actions.span(args, ctx)
    sleep = store.sleep_summary(span)
    nights = [{"date": day["date"], "asleep_hours": day["sleep"].get("asleep_hours"),
               "in_bed_hours": day["sleep"].get("in_bed_hours"), "source": day["field_sources"]["sleep"],
               "provenance": day["field_provenance"]["sleep"]}
              for day in store.wellness_days(span) if day["sleep"] is not None
              and day["field_provenance"]["sleep"]["kind"] == "nightly"]
    trailing = dates.Span(ctx.today() - timedelta(days=13), ctx.today())
    gate = {"status": "pending measurement", "span": trailing.to_json(),
            "basis": "low-confidence coaching heuristic", "claim": "rn:sleep-dieting.3"}
    if span != trailing:
        gate["reason"] = "request the trailing 14-day span shown here"
    elif not sleep["complete"]:
        gate["reason"] = "incomplete hours coverage; retain the missing dates and original source spans"
    else:
        gate["status"] = "recomp" if sleep["avg_asleep_hours"] < 7 else "passed"
        gate["reason"] = "maintenance" if gate["status"] == "recomp" else "offer goals review before a deficit"
    return {"span": span.to_json(), "sleep": sleep, "nights": nights, "sleep_gate": gate}


@command(
    "wellness add",
    help="Record wellness by hand for one day (the day you woke) or a span; adding again updates that record",
    args=(
        arg("--date", metavar="DATE", help="one day"),
        arg("--from", dest="start", metavar="DATE", help="first day of a span, such as a week's average"),
        arg("--to", dest="end", metavar="DATE", help="last day of the span"),
        arg("--sleep-hours", type=float, metavar="H", help="hours asleep (a span: the average per night)"),
        arg("--in-bed-hours", type=float, metavar="H"),
        arg("--resting-hr", type=float, metavar="BPM"),
        arg("--steps", type=int),
        arg("--body-mass", type=float, metavar="MASS", help="in [athlete] bodyweight_units"),
        arg("--body-fat-pct", type=float, metavar="PCT"),
    ),
    writes=True,
)
def add(args, ctx):
    store = actions.store_for(ctx)
    if args.date and (args.start or args.end):
        raise ValidationError("give --date for one day or --from and --to for a span, not both")
    if args.date:
        start = end = actions.parse_date(args.date, "--date").isoformat()
        record_id = f"manual:{start}-wellness"
    elif args.start and args.end:
        span = actions.span(args, ctx)
        start, end = span.start.isoformat(), span.end.isoformat()
        record_id = f"manual:{start}-wellness" if start == end else f"manual:{start}..{end}-wellness"
    else:
        raise ValidationError("give --date, or --from and --to")
    if all(getattr(args, name) is None for name in FIELDS):
        raise ValidationError("give at least one reading, such as --sleep-hours")

    current = store.latest("wellness").get(record_id)
    item = dict(current) if current is not None and current["op"] == "upsert" else {}
    sleep = dict(item.get("sleep") or {"asleep_hours": None, "in_bed_hours": None, "start": None, "end": None})
    if args.sleep_hours is not None:
        sleep["asleep_hours"] = args.sleep_hours
    if args.in_bed_hours is not None:
        sleep["in_bed_hours"] = args.in_bed_hours
    item.update({"id": record_id, "start": start, "end": end,
                 "sleep": sleep if any(v is not None for v in sleep.values()) else None})
    for name, value in (("resting_hr_bpm", args.resting_hr), ("steps", args.steps),
                        ("body_fat_pct", args.body_fat_pct)):
        if value is not None:
            item[name] = value
    if args.body_mass is not None:
        try:
            item["body_mass_kg"] = units.to_hevy_kg(args.body_mass, "total", ctx.config.athlete.bodyweight_units)
        except ValueError as exc:
            raise ValidationError(f"--body-mass: {exc}") from None
    return actions.write(store, "wellness", actions.build_manual(ctx, "wellness", item), args.dry_run)


@command("wellness void", help="Remove a wellness record from every view; its history stays in the file",
         args=(arg("id"), arg("--reason", required=True, metavar="TEXT")), writes=True)
def void(args, ctx):
    return actions.void(ctx, actions.store_for(ctx), "wellness", args.id, args.reason, args.dry_run)
