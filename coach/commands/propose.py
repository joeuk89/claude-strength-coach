from coach import dates, propose
from coach.commands import arg, command
from coach.errors import UsageError

_PROPOSAL = arg("--proposal", required=True, metavar="ID", help="proposal id, from propose week")


def _date(value, flag):
    try:
        return dates.parse_date(value)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


@command(
    "propose week",
    help="Propose a week's overlay from the program, state, history and decisions; write an editable draft",
    args=(arg("--week", metavar="W", help="week label (2026-W42) or any date in it; default: the week holding tomorrow"),
          arg("--span", metavar="A..B", help="an explicit span, YYYY-MM-DD..YYYY-MM-DD, instead of a week"),
          arg("--kind", choices=propose.KINDS, default="weekly", help="weekly (default), midweek or deload"),
          arg("--transform", metavar="NAME", help="the week transform for this run (default for a deload: the "
                                                   "program's deload rule)"),
          arg("--plan", metavar="FILE", help="dated sessions from a schedule plan file instead of the schedule rule")),
    writes=True,
)
def week(args, ctx):
    if args.week and args.span:
        raise UsageError("give --week or --span, not both")
    span = propose.resolve_span(ctx.config, ctx.today(), args.week, args.span, args.kind)
    return propose.propose_week(ctx.root, ctx.config, ctx.today(), ctx.now(), span, args.kind, args.transform,
                                args.plan, args.dry_run)


@command("propose show", help="Show a proposal draft built as an overlay, its lines and what finalize would refuse",
         args=(arg("id", metavar="ID", help="proposal id"),))
def show(args, ctx):
    return propose.show(ctx.root, ctx.config, args.id, ctx.now())


@command(
    "propose override",
    help="Change one line of a proposal with a reason, keeping the original in override.proposed_sets",
    args=(_PROPOSAL,
          arg("--session", required=True, metavar="S", help="program session id"),
          arg("--exercise", required=True, metavar="E", help="library exercise id"),
          arg("--sets", metavar="SPEC", help='working sets, e.g. "3x5@100 rpe7" or "1x5@100 rpe8, 3x5@90 rpe7"; '
                                             'a rep-out set "1x5+@120" (RPE 9 stop unless rpe is given); '
                                             'seconds for a duration line, e.g. "2x35s rpe7"'),
          arg("--load", type=float, metavar="N", help="one load for every working set (athlete units, per hand for "
                                                      "per-hand modes)"),
          arg("--reason", required=True, metavar="TEXT", help="why the line changes"),
          arg("--date", metavar="D", help="change the line on this date only (default: every date of the slot)"),
          arg("--standing", action="store_true", help="keep this choice in later weeks until --until"),
          arg("--until", metavar="D", help="end date of a standing override (default four weeks; eight at most)")),
    writes=True,
)
def override(args, ctx):
    if bool(args.sets) == (args.load is not None):
        raise UsageError("give --sets SPEC or --load N")
    if args.load is not None and args.load < 0:
        raise UsageError("--load must not be negative")
    new_sets = propose.parse_sets(args.sets) if args.sets else None
    until = _date(args.until, "--until") if args.until else None
    if until is not None and not args.standing:
        raise UsageError("--until goes with --standing")
    day = _date(args.date, "--date").isoformat() if args.date else None
    return propose.override(ctx.root, ctx.config, args.proposal, args.session, args.exercise, new_sets, args.load,
                            args.reason, args.standing, until, ctx.now(), ctx.today(), args.dry_run, day)


@command(
    "propose resolve",
    help="Resolve one flag of a proposal with the reason it stands",
    args=(_PROPOSAL,
          arg("--flag", required=True, metavar="REF", help="the flag's ref (code:digest) from propose week, show or "
                                                           "override"),
          arg("--resolution", required=True, metavar="TEXT", help="how the flag is settled")),
    writes=True,
)
def resolve(args, ctx):
    return propose.resolve(ctx.root, args.proposal, args.flag, args.resolution, args.dry_run)


@command(
    "propose time",
    help="Set when one session of a proposal starts and how long it lasts, or clear it, and judge the interference "
         "rules again; finalize afterwards",
    args=(_PROPOSAL,
          arg("--session", required=True, metavar="S", help="program session id"),
          arg("--date", metavar="D", help="the session's date, when the proposal holds it twice"),
          arg("--start", metavar="TIME", help="HH:MM on the session's date in [athlete] timezone, or an ISO 8601 "
                                              "timestamp (with an offset, or local time)"),
          arg("--duration-min", type=int, metavar="MIN", help="how long the session lasts, in whole minutes"),
          arg("--clear", action="store_true", help="remove the session's start and duration")),
    writes=True,
)
def session_time(args, ctx):
    if args.clear == (args.start is not None):
        raise UsageError("give --start TIME or --clear")
    if args.clear and args.duration_min is not None:
        raise UsageError("--duration-min goes with --start")
    if args.duration_min is not None and args.duration_min < 1:
        raise UsageError("--duration-min must be at least 1")
    day = _date(args.date, "--date").isoformat() if args.date else None
    return propose.set_time(ctx.root, ctx.config, args.proposal, args.session, day, args.start, args.duration_min,
                            ctx.today(), ctx.now(), args.dry_run)


@command(
    "propose restore",
    help="Put back a conditioning session the drop rule removed from a proposal, resolving its flag with the reason",
    args=(_PROPOSAL,
          arg("--session", required=True, metavar="S", help="program session id of the dropped session"),
          arg("--reason", required=True, metavar="TEXT", help="why the session goes back in")),
    writes=True,
)
def restore(args, ctx):
    return propose.restore(ctx.root, ctx.config, args.proposal, args.session, args.reason, ctx.now(), ctx.today(),
                           args.dry_run)


@command(
    "propose finalize",
    help="Write the proposal as data/overlays/<id>.json, with its decisions and pending scheme state",
    args=(_PROPOSAL,),
    writes=True,
)
def finalize(args, ctx):
    return propose.finalize(ctx.root, ctx.config, args.proposal, ctx.now(), args.dry_run, ctx.today())


@command(
    "propose rebuild",
    help="Propose a draft's span again from the program as it is now, keeping its explained edits and resolutions",
    args=(_PROPOSAL,),
    writes=True,
)
def rebuild(args, ctx):
    return propose.rebuild(ctx.root, ctx.config, args.proposal, ctx.today(), ctx.now(), args.dry_run)


@command(
    "propose discard",
    help="Remove an abandoned draft and any unapproved overlay finalized from it; approved work stays",
    args=(_PROPOSAL,),
    writes=True,
)
def discard(args, ctx):
    return propose.discard(ctx.root, args.proposal, ctx.today(), args.dry_run)
