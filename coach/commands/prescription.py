from pathlib import Path

from coach import jsonio, overlay, validity
from coach.commands import arg, command
from coach.errors import RefusedError, UsageError, ValidationError
from coach.validate import validate as validate_schema


def _relative(ctx, path):
    try:
        return Path(path).resolve().relative_to(ctx.root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _from_file(ctx, path):
    """An overlay from a file holding an overlay or an overlay draft (built in memory, never written)."""
    raw = overlay.read_json(path)
    if not validate_schema(raw, jsonio.load_schema(overlay.DRAFT_SCHEMA)):
        return overlay.build(raw, ctx.config, root=ctx.root, now=ctx.now()), "draft"
    return raw, "overlay"


@command(
    "prescription check",
    help="Check every prescription line: still earned after days off, under cap, buildable from the kit, "
         "feasible at its RPE, in the library's load mode, and in a session that fits its time cap",
    args=(arg("--overlay", metavar="ID", help="an overlay in data/overlays"),
          arg("--file", metavar="PATH", help="an overlay or an overlay draft anywhere"),
          arg("--write", action="store_true",
              help="merge the flags into the overlay and fill each hand-built line's inferred provenance")),
    writes=True,
)
def check(args, ctx):
    if bool(args.overlay) == bool(args.file):
        raise UsageError("give --overlay ID or --file PATH")
    if args.write and not args.overlay:
        raise UsageError("--write takes --overlay; a draft is written by overlay build")
    if args.overlay:
        path = overlay.path_for(ctx.root, args.overlay)
        doc, source = overlay.read_json(path), "overlay"
        if isinstance(doc, dict) and doc.get("id") != args.overlay:
            raise ValidationError(f"The file for {args.overlay} holds overlay {doc.get('id')}")
    else:
        path = Path(args.file)
        doc, source = _from_file(ctx, path)

    found = validity.report(ctx.root, doc, ctx.config)
    data = {
        "overlay_id": doc["id"], "source": source, "path": _relative(ctx, path), "flags": found["flags"],
        "lines": found["lines"],
        "summary": {severity: sum(1 for f in found["flags"] if f["severity"] == severity)
                    for severity in ("block", "warn", "info")},
        "written": False,
    }
    if not args.write:
        return data
    if doc["approval"] is not None:
        raise RefusedError(f"Overlay {doc['id']} is approved, so prescription check does not write to it; "
                           "build a new overlay to change it")
    updated = validity.fill_provenance(dict(doc, flags=validity.merge_flags(doc, found["flags"])), found["lines"])
    errors = overlay.validate(updated, ctx.root, ctx.config)
    if errors:
        raise ValidationError(f"The checked overlay is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path, updated, args.dry_run)
    data.update(flags=updated["flags"], written=not args.dry_run)
    return data
