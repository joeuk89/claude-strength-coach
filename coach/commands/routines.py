"""`routines` commands for an overlay's Hevy routines (contract C2, C3, C9)."""

from coach import routines
from coach.commands import arg, command

_OVERLAY = arg("--overlay", required=True, metavar="ID", help="overlay id, e.g. 2026-10-12-weekly")
_REFRESH = arg("--refresh", action="store_true",
               help="re-read the overlay's routines from Hevy into the cache first")


@command(
    "routines diff",
    help="Compare each routine in an overlay's span with the cached Hevy routine; empty means nothing to write",
    args=(_OVERLAY, _REFRESH),
    writes=True,
    network=True,
)
def diff(args, ctx):
    return routines.diff_report(ctx, args.overlay, refresh=args.refresh, dry_run=args.dry_run)


@command(
    "routines verify",
    help="Report, per routine, whether Hevy matches the overlay",
    args=(_OVERLAY, _REFRESH),
    writes=True,
    network=True,
)
def verify(args, ctx):
    return routines.verify(ctx, args.overlay, refresh=args.refresh, dry_run=args.dry_run)


@command(
    "routines push",
    help="Write an approved overlay to its Hevy routines, read each back and log the result",
    args=(_OVERLAY, _REFRESH),
    writes=True,
    hevy_write=True,
    network=True,
)
def push(args, ctx):
    return routines.push(ctx, args.overlay, args.dry_run, refresh=args.refresh)


@command(
    "routines retire",
    help='Retitle named managed orphans or an ended overlay\'s temporary routines "(unused)"',
    args=(_OVERLAY,
          arg("--routine", action="append", default=[], help="managed orphan or ended temporary routine id"),
          arg("--expect-plan", help="hash of the exact retirement dry-run approved in the brief")),
    writes=True,
    hevy_write=True,
    network=True,
)
def retire(args, ctx):
    return routines.retire(ctx, args.overlay, args.dry_run, routine_ids=args.routine, expect_plan=args.expect_plan)


@command(
    "routines create",
    help="Create the Hevy routines (and the one-off folder) an approved overlay's sessions lack; ids go in state.json",
    args=(_OVERLAY,
          arg("--reuse", action="append", default=[], metavar="SESSION=ROUTINE", help="explicit managed routine reuse"),
          arg("--expect-plan", help="hash of the exact create dry-run approved in the brief")),
    writes=True,
    hevy_write=True,
    network=True,
)
def create(args, ctx):
    return routines.create(ctx, args.overlay, args.dry_run, args.reuse, args.expect_plan)


@command("routines preflight", help="List every local Hevy mapping requirement before the write brief",
         args=(_OVERLAY,))
def preflight(args, ctx):
    from coach.external import hevy_requirements, orphan_routines

    doc = routines._load(ctx, args.overlay)
    report = hevy_requirements(ctx.root, doc, ctx.config.hevy.enabled)
    report["orphan_routines"] = orphan_routines(ctx.root) if ctx.config.hevy.enabled else []
    return report
