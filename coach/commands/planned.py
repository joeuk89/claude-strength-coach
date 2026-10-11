"""`planned` commands: planned activities from a run plan, the coach or the athlete (contract C29, C30)."""

from coach.activity import actions, records
from coach.commands import arg, command
from coach.commands.activity import SPAN_ARGS


@command("planned list", help="Planned activities in a span; two sources planning one day both show",
         args=(*SPAN_ARGS, arg("--kind", action="append", choices=records.KINDS, help="only this kind (repeatable)")))
def list_planned(args, ctx):
    store = actions.store_for(ctx)
    span = actions.span(args, ctx)
    found = store.planned(span, kinds=args.kind)
    return {"span": span.to_json(), "planned": found, "count": len(found)}


@command(
    "planned add",
    help="Record a planned activity by hand",
    args=(
        arg("--date", required=True, metavar="DATE"),
        arg("--kind", required=True, choices=records.KINDS),
        arg("--title", required=True),
        arg("--quality", action="store_true", help="intervals, tempo, threshold, hills or a race"),
        arg("--distance-km", type=float, metavar="KM"),
        arg("--distance-mi", type=float, metavar="MI"),
        arg("--distance-m", type=float, metavar="M"),
        arg("--duration-min", type=float, metavar="MIN"),
        arg("--description", help="the target in words, such as \"Zone 2\""),
        arg("--notes"),
    ),
    writes=True,
)
def add(args, ctx):
    store = actions.store_for(ctx)
    day = actions.parse_date(args.date, "--date").isoformat()
    target = {"distance_meters": actions.distance_meters(args),
              "duration_seconds": actions.minutes_to_seconds(args.duration_min, "--duration-min"),
              "description": args.description}
    item = {"id": actions.next_manual_id(store, "planned", day, args.kind), "date": day, "kind": args.kind,
            "title": args.title, "quality": args.quality,
            "target": target if any(v is not None for v in target.values()) else None, "notes": args.notes}
    return actions.write(store, "planned", actions.build_manual(ctx, "planned", item), args.dry_run)


@command("planned void", help="Remove a planned activity from every view; its history stays in the file",
         args=(arg("id"), arg("--reason", required=True, metavar="TEXT")), writes=True)
def void(args, ctx):
    return actions.void(ctx, actions.store_for(ctx), "planned", args.id, args.reason, args.dry_run)
