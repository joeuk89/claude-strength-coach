"""`interference` commands: the program's interference rules and a check over a span (contract C51)."""

from coach import cardio, dates, interference
from coach.commands import arg, command
from coach.errors import UsageError


def _span(ctx, week, span):
    if bool(week) == bool(span):
        raise UsageError("give --week or --span")
    try:
        if week:
            return cardio.week_span(ctx.config, week)
        start, end = span.split("..")
        return dates.Span(dates.parse_date(start), dates.parse_date(end))
    except ValueError as exc:
        raise UsageError(f"{'--week' if week else '--span'}: {exc}") from None


@command("interference list", help="The program's interference rules with their params, and every rule available")
def list_rules(args, ctx):
    return interference.listing(ctx.root)


@command("interference check",
         help="Run the interference rules alone over logged workouts and planned activities; planned lifting "
              "sessions are judged by propose week. Flags, never moves",
         args=(arg("--week", metavar="W", help="week label (2026-W41) or any date in it"),
               arg("--span", metavar="A..B", help="an explicit span, YYYY-MM-DD..YYYY-MM-DD")))
def check(args, ctx):
    span = _span(ctx, args.week, args.span)
    if not cardio.activity_on(ctx.config):
        ctx.warn(cardio.NO_ACTIVITY_SOURCE)
    today = ctx.today()
    bouts = tuple(cardio.flag_bouts(ctx.root, ctx.config, span, today))
    found = interference.flags(ctx.root, ctx.config, span, "logged", bouts, today)
    return {"span": span.to_json(), "today": today.isoformat(),
            "rules": [rule["name"] for rule in interference.program_rules(ctx.root)], "flags": found}
