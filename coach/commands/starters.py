from pathlib import Path

from coach import jsonio, program_drafts, starters
from coach.commands import arg, command
from coach.errors import UsageError
from coach.library import EQUIPMENT, Library


def _equipment(text):
    found = [part.strip() for part in text.split(",") if part.strip()]
    unknown = [piece for piece in found if piece not in EQUIPMENT]
    if unknown:
        raise UsageError(f"--equipment: {', '.join(unknown)} is not an equipment id ({', '.join(EQUIPMENT)})")
    return found


@command(
    "starters list",
    help="The starter programs that fit a day count and the equipment (default: [equipment] available), with the "
         "ones that suit [athlete] experience marked",
    args=(
        arg("--days", type=int, metavar="N", help="training days a week; lists starters that take N days"),
        arg("--equipment", metavar="E,...", help="equipment ids available; default: [equipment] available"),
    ),
)
def list_starters(args, ctx):
    equipment = _equipment(args.equipment) if args.equipment is not None else None
    return starters.listing(ctx.config, args.days, equipment)


@command(
    "starters show",
    help="One starter program and the session pages it renders with its default days",
    args=(arg("id", metavar="ID", help="the starter id, as starters list prints it"),),
)
def show(args, ctx):
    return starters.show(args.id, Library.load(ctx.root), ctx.config.athlete.units)


@command(
    "starters draft",
    help="Draft a starter program onto the athlete's days, start loads and equipment (default "
         ".coach/drafts/program.json) for program adopt",
    args=(
        arg("id", metavar="ID", help="the starter id, as starters list prints it"),
        arg("--days", metavar="mon,wed,fri", help="the training days; default: [athlete] available_days when set, "
                                                  "else the starter's own"),
        arg("--start-load", action="append", metavar="EXERCISE=VALUE",
            help="a known working load in your units (per hand for dumbbells); repeat for each lift"),
        arg("--out", metavar="FILE", help="where to write the draft"),
    ),
    writes=True,
)
def draft(args, ctx):
    days = starters.parse_days(args.days) if args.days is not None else None
    found, chosen = starters.draft(ctx.root, args.id, days, starters.parse_start_loads(args.start_load),
                                   now=ctx.now())
    out = Path(args.out) if args.out else Path(ctx.root) / program_drafts.DEFAULT_OUT
    jsonio.write_doc(out, found, args.dry_run)
    shown = args.out if args.out else program_drafts.DEFAULT_OUT.as_posix()
    return {"draft": found, "days": chosen, "path": shown, "written": not args.dry_run,
            "problems": program_drafts.draft_problems(found, ctx.root)}
