"""`status-days` commands: days ill, injured or travelling (contract C50)."""

from coach import dates, paths, statusdays
from coach.activity.records import utc_text
from coach.commands import arg, command
from coach.errors import UsageError

_ID = arg("id", metavar="ID", help="status day id, e.g. s-0001")


def _date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


def _written(row, dry_run):
    return {"day": row, "path": paths.STATUS_DAYS.as_posix(), "written": not dry_run}


@command("status-days list", help="Status days, oldest first",
         args=(arg("--active", action="store_true", help="only rows not withdrawn"),))
def list_days(args, ctx):
    found = statusdays.load(ctx.root)["days"]
    if args.active:
        found = [row for row in found if statusdays.is_live(row)]
    return {"days": found, "count": len(found)}


@command(
    "status-days add",
    help="Record days ill, injured or travelling; leave out --to while it is still going on",
    args=(arg("--kind", required=True, choices=statusdays.KINDS),
          arg("--from", dest="start", required=True, metavar="D", help="first day"),
          arg("--to", dest="end", metavar="D", help="last day (default: ongoing until status-days end)"),
          arg("--note", required=True, metavar="TEXT", help="one line, e.g. \"head cold\""),
          arg("--source", default="coach", metavar="TEXT", help='where it came from, e.g. "check-in 2026-10-11"')),
    writes=True,
)
def add(args, ctx):
    end = _date(args.end, "--to") if args.end else None
    doc, row = statusdays.add(statusdays.load(ctx.root), args.kind, _date(args.start, "--from"), end, args.note,
                              args.source, utc_text(ctx.now()))
    statusdays.save(ctx.root, doc, args.dry_run)
    return _written(row, args.dry_run)


@command("status-days end", help="Give an ongoing status day its last day",
         args=(_ID, arg("--date", required=True, metavar="D", help="the last day")), writes=True)
def end(args, ctx):
    doc, row = statusdays.end(statusdays.load(ctx.root), args.id, _date(args.date, "--date"))
    statusdays.save(ctx.root, doc, args.dry_run)
    return _written(row, args.dry_run)


@command("status-days withdraw", help="Withdraw a wrong status day; the row stays, marked withdrawn",
         args=(_ID, arg("--reason", required=True, metavar="TEXT")), writes=True)
def withdraw(args, ctx):
    doc, row = statusdays.withdraw(statusdays.load(ctx.root), args.id, args.reason, utc_text(ctx.now()))
    statusdays.save(ctx.root, doc, args.dry_run)
    return _written(row, args.dry_run)
