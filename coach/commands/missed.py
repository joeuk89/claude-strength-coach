from coach import dates, history, missed
from coach.commands import arg, command
from coach.errors import UsageError


def _date(text, flag):
    if text is None:
        return None
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


@command(
    "missed list",
    help="Planned sessions dated before D (default today) in the overlay in force with no workout",
    args=(arg("--date", metavar="D", help="list sessions dated before this day (default today)"),),
)
def list_missed(args, ctx):
    day = _date(args.date, "--date") or ctx.today()
    return {"date": day.isoformat(), "missed": missed.missed_sessions(ctx.root, ctx.today(), day, ctx.now())}


@command("missed rules", help="The program's missed-day rules, each in plain words")
def list_rules(args, ctx):
    found = missed.rules(ctx.root)
    return {"rules": [{"id": rule["id"], "session_id": rule["session_id"], "kind": rule["action"]["kind"],
                       "description": missed.describe(rule, ctx.root), "rule": rule} for rule in found]}


CHOICE = (arg("--move-to", metavar="D", help="the athlete's choice: move the session to this free day, this week only"),
          arg("--drop", action="store_true", help="the athlete's choice: drop the session this week"))


@command(
    "missed plan",
    help="What the matching missed-day rule, or the athlete's chosen move or drop, does to the rest of the week: "
         "summary, write line, draft overlay and each later day's status for a move",
    args=(arg("--session", required=True, metavar="S", help="the missed session's id"),
          arg("--date", required=True, metavar="D", help="the day it was planned"), *CHOICE),
)
def plan(args, ctx):
    return missed.plan(ctx.root, args.session, _date(args.date, "--date"), ctx.now(),
                       _date(args.move_to, "--move-to"), args.drop)


@command(
    "missed apply",
    help='After the athlete\'s "go": write the miss, the mid-week overlay (unapproved) and the record lines',
    args=(arg("--session", required=True, metavar="S", help="the missed session's id"),
          arg("--date", required=True, metavar="D", help="the day it was planned"),
          arg("--tag", choices=history.MISS_TAGS, help="why it was missed"), *CHOICE),
    writes=True,
)
def apply(args, ctx):
    found = missed.apply(ctx.root, args.session, _date(args.date, "--date"), args.tag, args.dry_run, ctx.now(),
                         _date(args.move_to, "--move-to"), args.drop)
    if found["record"] is None:
        ctx.warn("No check-in record yet, so the mid-week lines were not written anywhere")
    return found
