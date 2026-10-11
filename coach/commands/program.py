from pathlib import Path

from coach import jsonio, paths, program, program_drafts
from coach.commands import arg, command
from coach.errors import ValidationError
from coach.library import Library


@command("program show", help="Show data/program.json, with absent optional keys filled")
def show(args, ctx):
    return {"path": paths.PROGRAM.as_posix(), "program": program.load(ctx.root)}


@command("program validate",
         help="Validate data/program.json against the schema, the exercise library and config; exit 1 with JSONPaths")
def validate(args, ctx):
    doc = program.read_json(program.path_for(ctx.root))
    errors = program.validate(doc, ctx.config, Library.load(ctx.root))
    if errors:
        raise ValidationError(f"{paths.PROGRAM} is not valid ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    for warning in program.warnings(doc):
        ctx.warn(warning)
    return {"valid": True, "path": paths.PROGRAM.as_posix(), "sessions": [s["id"] for s in doc["sessions"]]}


@command("program render",
         help="Render routine/program.md and one page per session from data/program.json",
         writes=True)
def render(args, ctx):
    pages = program.render_all(ctx.root)
    result = program.sync_pages(ctx.root, pages, args.dry_run)
    for path in result["not_generated"]:
        ctx.warn(f"{path} was not rendered from {paths.PROGRAM}; routine_render_fresh fails until it is moved "
                 "out of routine/")
    data = {"pages": sorted(pages), "written": [], "unchanged": result["unchanged"], "removed": [],
            "not_generated": result["not_generated"]}
    if args.dry_run:
        data.update(would_write=result["written"], would_remove=result["removed"])
        return data
    data.update(written=result["written"], removed=result["removed"])
    return data


@command(
    "program import-hevy",
    help="Turn the cached Hevy routines into a program draft (default .coach/drafts/program.json); "
         "every exercise needs a confirmed load mode",
    args=(
        arg("--routine", action="append", metavar="ID", help="import only this routine; repeat for several"),
        arg("--folder", type=int, metavar="ID", help="import only the routines in this Hevy folder"),
        arg("--out", metavar="FILE", help="where to write the draft"),
    ),
    writes=True,
)
def import_hevy(args, ctx):
    draft = program_drafts.import_hevy(ctx.root, args.routine, args.folder, now=ctx.now())
    out = Path(args.out) if args.out else Path(ctx.root) / program_drafts.DEFAULT_OUT
    jsonio.write_doc(out, draft, args.dry_run)
    shown = program_drafts.DEFAULT_OUT.as_posix() if not args.out else args.out
    return {"draft": draft, "path": shown, "written": not args.dry_run,
            "problems": program_drafts.draft_problems(draft, ctx.root)}


@command(
    "program adopt",
    help="Validate a program draft and make it the program: archive the old one (--replace), write program and "
         "state, render routine/, git add; never commits",
    args=(
        arg("--input", required=True, metavar="FILE", help="the program draft"),
        arg("--replace", action="store_true", help="archive the existing program and replace it"),
        arg("--position", metavar="P", help="the rotation position to start at; default: the draft's, else the "
                                            "schedule rule's first"),
    ),
    writes=True,
)
def adopt(args, ctx):
    draft = program_drafts.read_draft(args.input)
    result = program_drafts.adopt(ctx.root, draft, replace=args.replace, position=args.position,
                                  dry_run=args.dry_run, today=ctx.today())
    for warning in result.pop("warnings"):
        ctx.warn(warning)
    return result
