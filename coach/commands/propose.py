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
                                             'seconds for a duration line, e.g. "2x35s rpe7"'),
          arg("--load", type=float, metavar="N", help="one load for every working set (athlete units, per hand for "
                                                      "per-hand modes)"),
          arg("--reason", required=True, metavar="TEXT", help="why the line changes"),
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
    return propose.override(ctx.root, ctx.config, args.proposal, args.session, args.exercise, new_sets, args.load,
                            args.reason, args.standing, until, ctx.now(), ctx.today(), args.dry_run)


@command(
    "propose resolve",
    help="Resolve one flag of a proposal with the reason it stands",
    args=(_PROPOSAL,
          arg("--flag", required=True, type=int, metavar="INDEX", help="the flag's index in the draft's flags (0 first)"),
          arg("--resolution", required=True, metavar="TEXT", help="how the flag is settled")),
    writes=True,
)
def resolve(args, ctx):
    return propose.resolve(ctx.root, args.proposal, args.flag, args.resolution, args.dry_run)


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
    return propose.finalize(ctx.root, ctx.config, args.proposal, ctx.now(), args.dry_run)
