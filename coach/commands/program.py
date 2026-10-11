from pathlib import Path

from coach import jsonio, paths, program, program_drafts
from coach.commands import arg, command
from coach.errors import ValidationError
from coach.library import Library
from coach.validate import Error


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
    draft = program_drafts.import_hevy(ctx.root, args.routine, args.folder, now=ctx.now(),
                                       config=ctx.config)
    out = Path(args.out) if args.out else Path(ctx.root) / program_drafts.DEFAULT_OUT
    jsonio.write_doc(out, draft, args.dry_run)
    shown = program_drafts.DEFAULT_OUT.as_posix() if not args.out else args.out
    return {"draft": draft, "path": shown, "written": not args.dry_run,
            "problems": program_drafts.draft_problems(draft, ctx.root, config=ctx.config)}


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
                                  dry_run=args.dry_run, today=ctx.today(), config=ctx.config)
    for warning in result.pop("warnings"):
        ctx.warn(warning)
    return result


def _problem_set(doc, ctx, library):
    return {(error.path, error.message) for error in program.validate(doc, ctx.config, library, ctx.root)}


@command(
    "program reconcile-mode",
    help="Bring every line of one exercise to the library's confirmed load mode, after the athlete says what its "
         "start load meant: --basis old converts it from the line's mode, --basis confirmed keeps the number",
    args=(
        arg("id", help="library exercise id"),
        arg("--basis", required=True, choices=program.BASES,
            help="old: the start load was meant in the line's current mode; confirmed: it already meant the "
                 "confirmed mode"),
        arg("--input", metavar="FILE", help="a program draft to reconcile instead of data/program.json"),
    ),
    writes=True,
)
def reconcile_mode(args, ctx):
    library = Library.load(ctx.root)
    if library.get(args.id) is None:
        raise ValidationError(f"no library exercise has the id {args.id!r}; see python3 -m coach library search TEXT")
    confirmed = library.effective_load_mode(args.id)
    if confirmed is None:
        raise ValidationError(f"{args.id} has no confirmed load mode to reconcile to; ask the athlete how it is "
                              f"loaded and run python3 -m coach library set-mode {args.id} MODE first")
    if args.input:
        path, prefix = Path(args.input), "$.program"
        container = program_drafts.read_draft(path)
        if not isinstance(container, dict) or not isinstance(container.get("program"), dict):
            raise ValidationError(f"{path} is not a program draft: it has no program object")
        doc = container["program"]
    else:
        path, prefix = program.path_for(ctx.root), "$"
        container = doc = program.read_json(path)
    shown = args.input or paths.PROGRAM.as_posix()

    try:
        new_doc, changes = program.reconciled(doc, args.id, confirmed, args.basis, ctx.config.athlete.units)
    except ValueError as exc:
        raise ValidationError(f"cannot convert a start load of {args.id}: {exc}") from None
    result = {"path": shown, "exercise_id": args.id, "load_mode": confirmed, "basis": args.basis,
              "changed": changes, "written": False, "rendered": []}
    if not changes:
        return result
    added = _problem_set(new_doc, ctx, library) - _problem_set(doc, ctx, library)
    if added:
        details = [Error(prefix + where[1:], message).to_json() for where, message in sorted(added)]
        raise ValidationError(f"Reconciling {args.id} to {confirmed} would make the program invalid; nothing was "
                              "written", details=details)
    if args.dry_run:
        return result

    if args.input:
        container = dict(container, program=new_doc)
        jsonio.write_doc(path, container, False)
    else:
        jsonio.write_doc(path, new_doc, False)
    result["written"] = True
    if not args.input:
        try:
            pages = program.render_all(ctx.root)
        except ValidationError as exc:
            ctx.warn(f"the routine pages were not rendered: {exc.message}")
        else:
            result["rendered"] = program.sync_pages(ctx.root, pages, dry_run=False)["written"]
    return result
