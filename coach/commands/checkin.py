from coach import checkin, dates
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
          arg("--tier", choices=checkin.CARD_TIERS, help="run this tier whatever is due")),
)
def prepare(args, ctx):
    card = checkin.prepare(ctx.root, ctx.today(), _date(args.until, "--until"), args.tier, ctx.now())
    days = card["days_since_last"]
    if args.tier is None and days is not None and days > checkin.CATCH_UP_AFTER_DAYS:
        ctx.warn(f"catch_up_pending: {days} days since the last check-in, over {checkin.CATCH_UP_AFTER_DAYS}; "
                 "catch-up mode is not built yet, so the card runs weekly")
    if card["unsynced"]:
        ctx.warn(f"{card['unsynced']} workout(s) in the window are not in data/history yet; the card reads them "
                 "from the Hevy cache. Run python3 -m coach history sync before writing the record")
    return {"card": card, "text": checkin.card_text(card)}


@command(
    "checkin misses",
    help="Missed sessions by tag and by session (default: since the last deep check-in)",
    args=(arg("--since", metavar="D", help="first day (default: the last deep record's date)"),
          arg("--until", metavar="D", help="last day (default today)")),
)
def misses(args, ctx):
    until = _date(args.until, "--until") or ctx.today()
    since = _date(args.since, "--since")
    if since is None:
        found = [r for r in checkin.records(ctx.root) if r.date < until]
        deep = [r for r in found if r.tier == "deep"]
        since = deep[-1].date if deep else (found[0].date if found else until)
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
