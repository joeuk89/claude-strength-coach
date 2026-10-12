from coach import block, dates
from coach.commands import arg, command
from coach.errors import UsageError


def _week(text, flag, ctx):
    try:
        return dates.parse_week(text, ctx.config.athlete.week_starts)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


def _date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


@command(
    "block status",
    help="The block's hard-week count, the light-week state, the status line and whether the next check-in is deep",
)
def status(args, ctx):
    return block.status(ctx.root, today=ctx.today(), now=ctx.now())


@command(
    "block close",
    help="Close every week up to W: class it, count completed hard weeks, check the four fatigue triggers and "
         "propose, watch or skip a light week",
    args=(arg("--week", required=True, metavar="W", help="a week label (YYYY-Www) or any date in it"),
          arg("--readiness", choices=block.READINGS, help="the athlete's readiness this week"),
          arg("--sleep", choices=block.READINGS,
              help="override the sleep measured from tracker or diary hours; needs --sleep-reason"),
          arg("--sleep-reason", metavar="TEXT", help="why the override, shown with the close"),
          arg("--deep", action="store_true", help="this check-in is a deep review")),
    writes=True,
)
def close(args, ctx):
    span = _week(args.week, "--week", ctx)
    return block.close(ctx.root, span, args.readiness, args.sleep, args.deep, args.dry_run,
                       sleep_reason=args.sleep_reason, today=ctx.today(), now=ctx.now())


@command(
    "block decide",
    help="Record the athlete's answer to a light week (adopted or declined), or the coach adopting one unprompted",
    args=(arg("--outcome", required=True, choices=block.OUTCOMES, help="what the athlete chose"),
          arg("--type", dest="week_type", choices=block.TYPES,
              help="for adopted: deload, light or return (default: the proposal's)"),
          arg("--week", metavar="W", help="for adopted: the light week (default: the proposal's)"),
          arg("--reason", metavar="TEXT",
              help="why; required to decline, to change the proposed type, or to adopt with none proposed")),
    writes=True,
)
def decide(args, ctx):
    span = _week(args.week, "--week", ctx) if args.week else None
    return block.decide(ctx.root, args.outcome, args.week_type, span, args.reason, args.dry_run, today=ctx.today(),
                        now=ctx.now())


@command(
    "block init",
    help="Start the block ledger from the completed hard weeks the athlete confirms",
    args=(arg("--hard-weeks", required=True, type=int, metavar="N", help="completed hard weeks in the current block"),
          arg("--through", metavar="W", help="the last week the count covers (default: last week)"),
          arg("--started", metavar="D", help="the block's first day (default: N weeks back from --through)"),
          arg("--reason", metavar="TEXT", help="where the count came from")),
    writes=True,
)
def init(args, ctx):
    through = _week(args.through, "--through", ctx) if args.through else None
    started = _date(args.started, "--started") if args.started else None
    return block.init(ctx.root, args.hard_weeks, started, through, args.reason, args.dry_run, today=ctx.today(),
                      now=ctx.now())
