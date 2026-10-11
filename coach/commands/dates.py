from coach import dates
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError

_WEEK_STARTS = arg("--week-starts", choices=dates.WEEK_STARTS,
                   help="first day of the week (default: [athlete] week_starts in config.toml)")


def _week_starts(args, ctx):
    return args.week_starts or ctx.config.athlete.week_starts


def _date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise ValidationError(f"{flag}: {exc}") from None


@command(
    "dates week",
    help="The week holding a date: its ISO week, label and span",
    args=(arg("--date", help="YYYY-MM-DD (default: today)"), _WEEK_STARTS),
)
def week(args, ctx):
    day = _date(args.date, "--date") if args.date else ctx.today()
    week_starts = _week_starts(args, ctx)
    span = dates.week_span(day, week_starts)
    return {
        "date": day.isoformat(),
        "iso_week": dates.iso_week(day),
        "week_starts": week_starts,
        "label": span.label(),
        "span": span.to_json(),
    }


@command(
    "dates span",
    help="A week from its label or any date in it, or the span between two dates",
    args=(
        arg("--week", help="a week label (YYYY-Www) or any date in the week"),
        arg("--start", help="YYYY-MM-DD, with --end"),
        arg("--end", help="YYYY-MM-DD, with --start"),
        _WEEK_STARTS,
    ),
)
def span(args, ctx):
    if args.week and (args.start or args.end):
        raise UsageError("give --week, or --start and --end, not both")
    if args.week:
        week_starts = _week_starts(args, ctx)
        try:
            found = dates.parse_week(args.week, week_starts)
        except ValueError as exc:
            raise ValidationError(f"--week: {exc}") from None
        return {"span": found.to_json(), "days": len(found.days()), "label": found.label(),
                "week_starts": week_starts}
    if not (args.start and args.end):
        raise UsageError("give --week, or both --start and --end")
    try:
        found = dates.Span(_date(args.start, "--start"), _date(args.end, "--end"))
    except ValueError as exc:
        raise ValidationError(str(exc)) from None
    return {"span": found.to_json(), "days": len(found.days())}
