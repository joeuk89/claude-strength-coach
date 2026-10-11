"""`activity` commands: logged cardio from every activity source (contract C29 to C31)."""

from coach.activity import actions, records, sync
from coach.commands import arg, command
from coach.errors import ValidationError

SPAN_ARGS = (
    arg("--from", dest="start", metavar="DATE", help="first day (default: the start of this week)"),
    arg("--to", dest="end", metavar="DATE", help="last day (default: the end of this week)"),
)


@command("activity list", help="List resolved Activities in a span: duplicates merged, sources by precedence",
         args=(*SPAN_ARGS, arg("--kind", action="append", choices=records.KINDS, help="only this kind (repeatable)")))
def list_activities(args, ctx):
    store = actions.store_for(ctx)
    span = actions.span(args, ctx)
    found = store.activities(span, kinds=args.kind)
    return {"span": span.to_json(), "activities": found, "count": len(found)}


@command("activity show", help="Show one Activity by any id it was merged from, with every line written for it",
         args=(arg("id", help="record id, such as manual:2026-10-08-run-1"),))
def show(args, ctx):
    store = actions.store_for(ctx)
    lines = store.history("activity", args.id)
    if not lines:
        raise ValidationError(f"no activity record has the id {args.id!r}; see python3 -m coach activity list")
    found = next((a for a in store.activity_groups() if args.id in a["merged_from"]), None)
    return {"activity": found, "voided": found is None, "lines": lines}


@command("activity status", help="Each enabled source: last sync, record counts, newest date, wellness gaps")
def status(args, ctx):
    return actions.status(ctx, actions.store_for(ctx))


@command("activity sync", help="Fetch every enabled source and append what changed; never stages or commits",
         args=(arg("--source", metavar="NAME", help="sync only this source"),), writes=True)
def sync_sources(args, ctx):
    store = actions.store_for(ctx)
    return {"sources": sync.run(ctx, store, only=args.source, dry_run=args.dry_run), "dry_run": args.dry_run}


@command(
    "activity add",
    help="Record an Activity by hand",
    args=(
        arg("--kind", required=True, choices=records.KINDS),
        arg("--start", required=True, metavar="TIMESTAMP",
            help="ISO 8601; with no offset it is local time in [athlete] timezone"),
        arg("--duration-min", type=float, required=True, metavar="MIN"),
        arg("--distance-km", type=float, metavar="KM"),
        arg("--distance-mi", type=float, metavar="MI"),
        arg("--distance-m", type=float, metavar="M"),
        arg("--rpe", type=float, help="session RPE, 0 to 10"),
        arg("--avg-hr", type=int, metavar="BPM"),
        arg("--name"),
        arg("--notes"),
        arg("--indoor", action="store_true", default=None),
    ),
    writes=True,
)
def add(args, ctx):
    store = actions.store_for(ctx)
    try:
        records.parse_local(args.start, ctx.timezone())
    except ValueError as exc:
        raise ValidationError(f"--start: {exc}") from None
    item = {"id": "manual:pending", "kind": args.kind, "start": args.start,
            "duration_seconds": actions.minutes_to_seconds(args.duration_min, "--duration-min"),
            "distance_meters": actions.distance_meters(args), "rpe": args.rpe, "avg_hr": args.avg_hr,
            "name": args.name, "notes": args.notes, "indoor": args.indoor}
    draft = actions.build_manual(ctx, "activity", item)
    item["id"] = actions.next_manual_id(store, "activity", draft["local_date"], args.kind)
    return actions.write(store, "activity", actions.build_manual(ctx, "activity", item), args.dry_run)


@command("activity void", help="Remove an Activity record from every view; its history stays in the file",
         args=(arg("id"), arg("--reason", required=True, metavar="TEXT")), writes=True)
def void(args, ctx):
    return actions.void(ctx, actions.store_for(ctx), "activity", args.id, args.reason, args.dry_run)
