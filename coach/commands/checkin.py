from coach import block, checkin, checkin_catchup, dates, history
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
    "checkin prepare",
    help="The check-in card: the week from the log, then the numbered questions (data.text is the Sunday message)",
    args=(arg("--until", metavar="D", help="last day of the window (default today)"),
          arg("--tier", choices=checkin.CARD_TIERS, help="run this tier whatever is due"),
          arg("--deep-reason", action="append", default=[], choices=tuple(block.DEEP_REASON_WORDS),
              help="reason from block close deep_review.reasons; repeat for each reason")),
)
def prepare(args, ctx):
    card = checkin.prepare(ctx.root, ctx.today(), _date(args.until, "--until"), args.tier, ctx.now(),
                           deep_review_reasons=args.deep_reason)
    problem = (card["catch_up"] or {}).get("return_week_problem")
    if problem:
        ctx.warn(f"no return week on the catch-up card: {problem}")
    if card["unsynced"]:
        ctx.warn(f"{card['unsynced']} workout(s) in the window are not in data/history yet; the card reads them "
                 "from the Hevy cache. Run python3 -m coach history sync before writing the record")
    return {"card": card, "text": checkin.card_text(card, ctx.config.athlete.units)}


@command(
    "checkin misses",
    help="Missed sessions by tag and by session (default: the deep card's tally, since the last deep check-in)",
    args=(arg("--since", metavar="D",
              help="first day (default: the last deep review's date, else the program's first window start)"),
          arg("--until", metavar="D", help="last day (default today)")),
)
def misses(args, ctx):
    until = _date(args.until, "--until") or ctx.today()
    since = _date(args.since, "--since")
    if since is None:
        since = checkin.misses_since(ctx.root, until)
    if since > until:
        raise UsageError(f"--since {since} is after --until {until}")
    return checkin.misses(ctx.root, since, until, ctx.now())


@command("checkin due", help="The last check-in record, when the next is due and which tier it runs")
def due(args, ctx):
    return checkin.due(ctx.root, ctx.today()).to_json()


@command(
    "checkin skeleton",
    help="Write check-ins/<date>.md with its week-review region; --refresh re-renders only the regions",
    args=(arg("--date", required=True, metavar="D", help="the record's date"),
          arg("--tier", choices=checkin.TIERS, help="the tier in the title (default: the card's mode)"),
          arg("--overlay", metavar="ID", help="the overlay to render, collapsed, at the end"),
          arg("--refresh", action="store_true", help="re-render the regions of an existing record")),
    writes=True,
)
def skeleton(args, ctx):
    day = _date(args.date, "--date")
    report = checkin.skeleton(ctx.root, day, args.tier, args.overlay, args.refresh, args.dry_run, ctx.now())
    unsynced = checkin.unsynced_in_window(ctx.root, day, ctx.now())
    if unsynced:
        ctx.warn(f"{len(unsynced)} workout(s) in the window are not in data/history yet, so the "
                 f"{checkin.REGION_KIND} region leaves them out; run python3 -m coach history sync, then "
                 f"checkin skeleton --date {day} --refresh")
    report["unsynced"] = len(unsynced)
    return report


@command(
    "checkin tag-gap",
    help="Tag every untagged missed core session since the last check-in with one miss tag",
    args=(arg("--tag", required=True, choices=history.MISS_TAGS, help="the miss tag for the whole gap"),),
    writes=True,
)
def tag_gap(args, ctx):
    return checkin.tag_gap(ctx.root, ctx.today(), args.tag, ctx.now(), args.dry_run)


@command(
    "checkin return-brief",
    help="The return template of the coach's brief for the week back, from a proposal or a one-off overlay",
    args=(arg("--proposal", metavar="ID", help="proposal id from propose week (illness, layoff)"),
          arg("--overlay", metavar="ID", help="a coach-built one-off overlay (travel, no kit)"),
          arg("--reason", required=True, choices=checkin_catchup.REASONS, help="what caused the gap")),
)
def return_brief(args, ctx):
    if (args.proposal is None) == (args.overlay is None):
        raise UsageError("give --proposal ID or --overlay ID")
    report = checkin_catchup.return_brief(ctx.root, ctx.config, ctx.now(), args.proposal, args.overlay, args.reason)
    for warning in report["warnings"]:
        ctx.warn(warning)
    return report
