import os
import tempfile
from pathlib import Path

from coach import paths, program
from coach.commands import command
from coach.errors import ValidationError
from coach.library import Library


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


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
    return {"valid": True, "path": paths.PROGRAM.as_posix(), "sessions": [s["id"] for s in doc["sessions"]]}


@command("program render",
         help="Render routine/program.md and one page per session from data/program.json",
         writes=True)
def render(args, ctx):
    pages = program.render_all(ctx.root)
    existing = program.routine_pages(ctx.root)
    changed = sorted(path for path, text in pages.items() if existing.get(path) != text)
    unchanged = sorted(path for path in pages if path not in changed)
    stale = sorted(path for path, text in existing.items() if path not in pages and program.is_generated(text))
    not_generated = sorted(path for path, text in existing.items() if path not in pages and path not in stale)
    for path in not_generated:
        ctx.warn(f"{path} was not rendered from {paths.PROGRAM}; routine_render_fresh fails until it is moved "
                 "out of routine/")
    data = {"pages": sorted(pages), "written": [], "unchanged": unchanged, "removed": [],
            "not_generated": not_generated}
    if args.dry_run:
        data.update(would_write=changed, would_remove=stale)
        return data
    for path in changed:
        _write_text(Path(ctx.root) / path, pages[path])
    for path in stale:
        (Path(ctx.root) / path).unlink()
    data.update(written=changed, removed=stale)
    return data
