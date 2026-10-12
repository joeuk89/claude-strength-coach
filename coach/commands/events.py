"""`events` commands: goal events, their agreed windows and results (contract C55)."""

from coach import dates, events, paths
from coach.activity import actions, records
from coach.activity.records import utc_text
from coach.commands import arg, command
from coach.errors import UsageError

_ID = arg("id", metavar="ID", help="event id, e.g. autumn-10k")
_DISTANCE = (arg("--distance-km", type=float, metavar="KM"), arg("--distance-mi", type=float, metavar="MI"),
             arg("--distance-m", type=float, metavar="M"))


def _date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


def _written(ctx, row, dry_run, **extra):
    shown = events.view(ctx.root, ctx.config, row, ctx.today())
    return {"event": shown, "path": paths.EVENTS.as_posix(), "written": not dry_run, **extra}


def _save(ctx, doc, row, dry_run):
    if row["planned_id"] is not None:
        events.check_link(actions.store_for(ctx), doc, row)
    events.save(ctx.root, doc, dry_run)


@command("events list", help="Goal events in date order, with countdown and pending decisions",
         args=(arg("--all", action="store_true", help="include completed and cancelled events"),))
def list_events(args, ctx):
    found = events.views(ctx.root, ctx.today(), include_all=args.all)
    return {"today": ctx.today().isoformat(), "events": found, "count": len(found)}


@command(
    "events add",
    help="Record a goal event such as a race; no window before it is assumed",
    args=(arg("--id", dest="event_id", required=True, metavar="ID", help="a stable slug, e.g. autumn-10k"),
          arg("--title", required=True),
          arg("--date", required=True, metavar="D", help="the event's local date"),
          arg("--priority", required=True, choices=events.PRIORITIES, help="A: the goal event; B and C: lesser"),
          arg("--activity", choices=records.KINDS),
          *_DISTANCE,
          arg("--planned-id", metavar="ID", help="the planned activity that is this event (planned list)"),
          arg("--note", metavar="TEXT")),
    writes=True,
)
def add(args, ctx):
    doc, row = events.add(events.load(ctx.root), event_id=args.event_id, title=args.title,
                          day=_date(args.date, "--date"), priority=args.priority, activity=args.activity,
                          distance_meters=actions.distance_meters(args), planned_id=args.planned_id,
                          note=args.note, created_at=utc_text(ctx.now()))
    _save(ctx, doc, row, args.dry_run)
    return _written(ctx, row, args.dry_run)


@command(
    "events update",
    help="Change an active event, e.g. postpone it; a new date clears the window and a plan on the old date",
    args=(_ID, arg("--title"), arg("--date", metavar="D"), arg("--priority", choices=events.PRIORITIES),
          arg("--activity", choices=records.KINDS), *_DISTANCE,
          arg("--planned-id", metavar="ID"), arg("--unlink", action="store_true", help="drop the planned activity"),
          arg("--note", metavar="TEXT"), arg("--reason", metavar="TEXT", help="why it changed")),
    writes=True,
)
def update(args, ctx):
    if args.planned_id and args.unlink:
        raise UsageError("give --planned-id or --unlink, not both")
    fields = {key: value for key, value in (("title", args.title), ("priority", args.priority),
                                            ("activity", args.activity), ("note", args.note),
                                            ("planned_id", args.planned_id)) if value is not None}
    if args.date:
        fields["date"] = _date(args.date, "--date")
    distance = actions.distance_meters(args)
    if distance is not None:
        fields["distance_meters"] = distance
    if args.unlink:
        fields["planned_id"] = None
    if not fields:
        raise UsageError("give at least one field to change")
    doc, row, cleared = events.update(events.load(ctx.root), args.id, fields, args.reason, utc_text(ctx.now()))
    _save(ctx, doc, row, args.dry_run)
    return _written(ctx, row, args.dry_run, cleared=cleared)


@command(
    "events window",
    help="Record the window agreed before an event, record that none is kept, or clear the decision",
    args=(_ID, arg("--from", dest="start", metavar="D"), arg("--to", dest="end", metavar="D"),
          arg("--none", action="store_true", help="agreed: no window before this event"),
          arg("--clear", action="store_true", help="drop the decision; it is pending again"),
          arg("--rationale", metavar="TEXT", help="why this window, or why none; with --clear, why")),
    writes=True,
)
def window(args, ctx):
    chosen = [bool(args.start or args.end), args.none, args.clear]
    if sum(chosen) != 1:
        raise UsageError("give --from D --to D, --none or --clear")
    if chosen[0] and not (args.start and args.end):
        raise UsageError("give both --from and --to")
    doc, at = events.load(ctx.root), utc_text(ctx.now())
    if args.clear:
        doc, row = events.clear_window(doc, args.id, args.rationale or "cleared", at)
    elif args.none:
        doc, row = events.set_window(doc, args.id, None, None, args.rationale, at)
    else:
        doc, row = events.set_window(doc, args.id, _date(args.start, "--from"), _date(args.end, "--to"),
                                     args.rationale, at)
    events.save(ctx.root, doc, args.dry_run)
    return _written(ctx, row, args.dry_run)


@command("events complete", help="Record an event's result; it stays as history and its prompts stop",
         args=(_ID, arg("--result", required=True, metavar="TEXT", help='e.g. "41:30, a 2 min PB"')), writes=True)
def complete(args, ctx):
    doc, row = events.complete(events.load(ctx.root), args.id, args.result, ctx.today(), utc_text(ctx.now()))
    events.save(ctx.root, doc, args.dry_run)
    return _written(ctx, row, args.dry_run)


@command("events cancel", help="Cancel an event; it stays as history and its prompts stop",
         args=(_ID, arg("--reason", required=True, metavar="TEXT")), writes=True)
def cancel(args, ctx):
    doc, row = events.cancel(events.load(ctx.root), args.id, args.reason, utc_text(ctx.now()))
    events.save(ctx.root, doc, args.dry_run)
    return _written(ctx, row, args.dry_run)

