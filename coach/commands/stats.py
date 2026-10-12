from coach import dates, stats
from coach.commands import arg, command
from coach.errors import UsageError

_UNSYNCED = arg("--include-unsynced", action="store_true",
                help="also apply source changes not yet synced (new, changed and removed workouts), in memory; "
                     "nothing is written")


def _span(text):
    start, separator, end = (text or "").partition("..")
    if not separator:
        raise UsageError(f"--span: expected A..B (two dates), found {text!r}")
    try:
        return dates.Span(dates.parse_date(start), dates.parse_date(end))
    except ValueError as exc:
        raise UsageError(f"--span: {exc}") from None


def _week(text, ctx):
    try:
        return dates.parse_week(text, ctx.config.athlete.week_starts)
    except ValueError as exc:
        raise UsageError(f"--week: {exc}") from None


@command(
    "stats e1rm",
    help="e1RM series per lift: the best set of each usable exposure (Epley, reps in reserve when RPE is logged)",
    args=(arg("--exercise", metavar="ID", help="one library exercise id"),
          arg("--since", metavar="D", help="first date, YYYY-MM-DD"), _UNSYNCED),
)
def e1rm(args, ctx):
    since = None
    if args.since:
        try:
            since = dates.parse_date(args.since)
        except ValueError as exc:
            raise UsageError(f"--since: {exc}") from None
    return stats.e1rm_series(ctx.root, args.exercise, since, args.include_unsynced, ctx.now())


@command(
    "stats adherence",
    help="Planned sessions against logged workouts: trained, missed (with tag) or upcoming, and each exercise "
         "hit, under, over or missing",
    args=(arg("--overlay", metavar="ID", help="one overlay's sessions"),
          arg("--span", metavar="A..B", help="the sessions in force on each day of a span"), _UNSYNCED),
)
def adherence(args, ctx):
    if bool(args.overlay) == bool(args.span):
        raise UsageError("give --overlay ID or --span A..B")
    span = _span(args.span) if args.span else None
    return stats.adherence(ctx.root, args.overlay, span, args.include_unsynced, ctx.today(), ctx.now())


@command(
    "stats dose",
    help="Hard sets delivered per muscle, direct and fractional (indirect sets count half)",
    args=(arg("--week", metavar="W", help="a week label (YYYY-Www) or any date in it"),
          arg("--span", metavar="A..B", help="a span of dates"), _UNSYNCED),
)
def dose(args, ctx):
    if bool(args.week) == bool(args.span):
        raise UsageError("give --week W or --span A..B")
    if args.week:
        return stats.dose(ctx.root, week=_week(args.week, ctx), include_unsynced=args.include_unsynced, now=ctx.now())
    return stats.dose(ctx.root, span=_span(args.span), include_unsynced=args.include_unsynced, now=ctx.now())


@command(
    "stats durations",
    help="Each workout's minutes against its session cap ([sessions.cap_minutes], else [athlete] session_minutes)",
    args=(arg("--span", metavar="A..B", help="a span of dates (default: every workout)"),
          arg("--week", metavar="W", help="a week label (YYYY-Www) or any date in it"), _UNSYNCED),
)
def durations(args, ctx):
    if args.week and args.span:
        raise UsageError("give --week W or --span A..B, not both")
    span = _week(args.week, ctx) if args.week else _span(args.span) if args.span else None
    return stats.durations(ctx.root, span, args.include_unsynced, ctx.now())


@command(
    "stats audit",
    help="Dumbbell exposures that jumped exactly 2× or ½× at the same reps and RPE: likely logging slips",
    args=(arg("--weeks", type=int, default=8, metavar="N", help="how many weeks back to look (default 8)"),
          _UNSYNCED),
)
def audit(args, ctx):
    if args.weeks < 1:
        raise UsageError("--weeks must be 1 or more")
    return stats.audit(ctx.root, args.weeks, args.include_unsynced, ctx.today(), ctx.now())
