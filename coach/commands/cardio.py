"""`cardio` commands: the week's numbers, plan reconcile, cardio flags and the record region (contract C48, C49)."""

from pathlib import Path

from coach import cardio, dates, weekflags
from coach.activity import actions, associations
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError

_WEEK_HELP = "week label (2026-W41) or any date in it"
_WEEK = arg("--week", metavar="W", help=_WEEK_HELP)
_WEEK_REQUIRED = arg("--week", required=True, metavar="W", help=_WEEK_HELP)


def _span(ctx, week=None, span=None):
    if bool(week) == bool(span):
        raise UsageError("give --week or --span")
    try:
        if week:
            return cardio.week_span(ctx.config, week)
        start, end = span.split("..")
        return dates.Span(dates.parse_date(start), dates.parse_date(end))
    except ValueError as exc:
        raise UsageError(f"{'--week' if week else '--span'}: {exc}") from None


def _warn_without_source(ctx):
    if not cardio.activity_on(ctx.config):
        ctx.warn(cardio.NO_ACTIVITY_SOURCE)


@command("cardio week", help="The week's lifting, coach-led sessions, runs, conditioning and session-RPE load",
         args=(_WEEK_REQUIRED,))
def week(args, ctx):
    span = _span(ctx, week=args.week)
    _warn_without_source(ctx)
    return cardio.week(ctx.root, span)


@command("cardio reconcile",
         help="Planned activities against logged ones: done, moved, missed, upcoming, extra, ambiguous, duplicate",
         args=(_WEEK_REQUIRED,))
def reconcile(args, ctx):
    span = _span(ctx, week=args.week)
    _warn_without_source(ctx)
    return cardio.reconcile(ctx.root, span, ctx.today())


@command("cardio flags", help="Cardio and week-level flags: logged bouts to today, plans from today on",
         args=(_WEEK, arg("--span", metavar="A..B", help="an explicit span, YYYY-MM-DD..YYYY-MM-DD")))
def flags(args, ctx):
    span = _span(ctx, args.week, args.span)
    _warn_without_source(ctx)
    today = ctx.today()
    bouts = tuple(cardio.flag_bouts(ctx.root, ctx.config, span, today))
    week_ctx = weekflags.WeekFlagContext(ctx.root, today, span, "logged", ctx.config, None, bouts)
    found = weekflags.run(week_ctx)
    return {"span": span.to_json(), "tier": ctx.config["cardio"]["tier"], "today": today.isoformat(),
            "sleep_judged_to": cardio.evaluation_date(week_ctx).isoformat(), "flags": found,
            "skipped": cardio.evaluate(week_ctx)["skipped"], "bouts": [b.to_json() for b in bouts]}


@command("cardio render", help="The week's cardio block as markdown; with --into, write it into that check-in record",
         args=(_WEEK_REQUIRED,
               arg("--into", metavar="FILE", help="the check-in record to write the cardio region into")),
         writes=True)
def render_block(args, ctx):
    span = _span(ctx, week=args.week)
    _warn_without_source(ctx)
    region = cardio.render_text(ctx.root, span, ctx.today())
    if not args.into:
        return {"week": span.label(), "text": region}
    target = Path(args.into)
    if not target.is_file():
        raise ValidationError(f"{target} does not exist; create the check-in record first")
    before = target.read_bytes().decode("utf-8")
    try:
        after = cardio.splice(before, span.label(), region)
    except ValueError as exc:
        raise ValidationError(f"{target}: {exc}") from None
    changed = after != before
    if changed and not args.dry_run:
        target.write_bytes(after.encode("utf-8"))
    return {"week": span.label(), "into": str(target), "changed": changed, "written": changed and not args.dry_run,
            "text": region}


@command("cardio associate", help="Associate an activity ID with a planned ID, or clear its association",
         args=(arg("activity_id"), arg("--planned-id"), arg("--clear", action="store_true")), writes=True)
def associate(args, ctx):
    if args.clear == (args.planned_id is not None):
        raise UsageError("give --planned-id or --clear")
    return associations.associate(actions.store_for(ctx), args.activity_id, args.planned_id, args.clear, args.dry_run)
