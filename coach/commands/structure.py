from datetime import timedelta

from coach import dates, flags, program, structure
from coach.commands import arg, command
from coach.config_tables import coaching
from coach.errors import UsageError, ValidationError
from coach.library import Library


def _date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


def _presented(report, ctx):
    return dict(report, flags=flags.for_mode(report["flags"], coaching.mode(ctx.config)))


@command(
    "structure week",
    help="One week's sessions (core, optional, coach-led) and per-muscle target, planned, delivered and bonus sets",
    args=(arg("--week", metavar="W", help="a week label (YYYY-Www) or any date in it; default: the week holding today"),),
)
def week(args, ctx):
    try:
        span = dates.parse_week(args.week, ctx.config.athlete.week_starts) if args.week else \
            dates.week_span(ctx.today(), ctx.config.athlete.week_starts)
    except ValueError as exc:
        raise UsageError(f"--week: {exc}") from None
    return _presented(structure.week(ctx.root, span, today=ctx.today(), now=ctx.now()), ctx)


@command(
    "structure adherence",
    help="Sessions trained over planned across the last four ordinary weeks, coach-led included, with its flags",
    args=(arg("--until", metavar="D", help="the last day a counted week may end on (default: today)"),),
)
def adherence(args, ctx):
    until = _date(args.until, "--until") if args.until else None
    return _presented(structure.adherence(ctx.root, until, today=ctx.today(), now=ctx.now()), ctx)


@command(
    "structure balance",
    help="Weekly sets per muscle the program plans on core and coach-led sessions, against its dose targets",
    args=(arg("--program", metavar="FILE",
              help="a candidate program to check instead, compared with data/program.json for new sessions"),
          arg("--variant", choices=structure.VARIANTS,
              help="minimum: check the minimum week (at most two sessions within their caps, every priority floor, "
                   "a third of each dose target); exit 1 names each reason it fails")),
)
def balance(args, ctx):
    candidate = None
    if args.program:
        candidate = program.read_json(args.program)
        errors = program.validate(candidate, ctx.config, Library.load(ctx.root), ctx.root)
        if errors:
            raise ValidationError(f"{args.program} is not a valid program ({len(errors)} problem(s))",
                                  details=[error.to_json() for error in errors])
        candidate = program.normalised(candidate)
    report = _presented(structure.balance(ctx.root, candidate, args.variant, today=ctx.today(), now=ctx.now()), ctx)
    if args.variant and not report["passed"]:
        raise ValidationError(f"The minimum week fails: {'; '.join(report['reasons'])}",
                              details=[{"path": "$.minimum_week", "message": reason} for reason in report["reasons"]],
                              data=report)
    return report


def _week(args, ctx, default):
    try:
        return dates.parse_week(args.week, ctx.config.athlete.week_starts) if args.week else \
            dates.week_span(default, ctx.config.athlete.week_starts)
    except ValueError as exc:
        raise UsageError(f"--week: {exc}") from None


@command(
    "structure priority",
    help="Each priority lift's KPI now and its trend, and its exposures per week against plan, with "
         "priority_exposures_missed",
    args=(arg("--since", metavar="D", help="the first day of the trend and the week rows (default: four weeks ago)"),),
)
def priority(args, ctx):
    since = _date(args.since, "--since") if args.since else None
    return _presented(structure.priority(ctx.root, since, today=ctx.today(), now=ctx.now()), ctx)


@command(
    "structure minimum",
    help="The minimum week's dated sessions for a week, as a schedule plan file for propose week --plan",
    args=(arg("--week", metavar="W", help="a week label (YYYY-Www) or any date in it; default: the week holding "
                                          "tomorrow"),
          arg("--write", action="store_true", help="write the plan to .coach/plans/<week start>-minimum.json")),
    writes=True,
    writes_scope="cache",
)
def minimum(args, ctx):
    span = _week(args, ctx, ctx.today() + timedelta(days=1))
    return structure.minimum(ctx.root, span, write=args.write, dry_run=args.dry_run, today=ctx.today(),
                             now=ctx.now())


@command(
    "structure decide",
    help="Record the athlete's answer to the adherence trigger, or an override for a new session, and print its "
         "line for the check-in record",
    args=(arg("--rule", required=True, choices=structure.RULES,
              help="restructure (the under-70 %% smaller schedule) or add_session (an under-80 %% override)"),
          arg("--outcome", required=True, choices=structure.OUTCOMES, help="what the athlete chose"),
          arg("--reason", metavar="TEXT", help="why; required when declined, and names the session an override adds"),
          arg("--revisit", metavar="D", help="for deferred: the date the proposal comes back")),
    writes=True,
)
def decide(args, ctx):
    revisit = _date(args.revisit, "--revisit") if args.revisit else None
    return structure.decide(ctx.root, args.rule, args.outcome, args.reason, revisit, today=ctx.today(),
                            now=ctx.now(), dry_run=args.dry_run)
