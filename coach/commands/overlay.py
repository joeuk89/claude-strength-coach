import os
import tempfile
from pathlib import Path

from coach import dates, jsonio, overlay, render, validity
from coach.commands import arg, command
from coach.errors import RefusedError, UsageError, ValidationError
from coach.validate import Error

_ID = arg("id", metavar="ID", help="overlay id, e.g. 2026-10-12-weekly")


def _relative(ctx, path):
    try:
        return Path(path).resolve().relative_to(ctx.root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _invalid(what, errors):
    return ValidationError(f"{what} is not valid ({len(errors)} problem(s))",
                           details=[error.to_json() for error in errors])


def _load_valid(ctx, overlay_id):
    doc = overlay.read_json(overlay.path_for(ctx.root, overlay_id))
    errors = overlay.validate(doc, ctx.root, ctx.config)
    if errors:
        raise _invalid(f"Overlay {overlay_id}", errors)
    if doc["id"] != overlay_id:
        raise ValidationError(f"The file for {overlay_id} holds overlay {doc['id']}")
    return doc


def _summary(doc):
    return {
        "id": doc["id"], "kind": doc["kind"], "span": doc["span"], "created_at": doc["created_at"],
        "supersedes": doc["supersedes"], "approved": overlay.is_approved(doc),
        "sessions": [{"session_id": s["session_id"], "date": s["date"], "title": s["title"]} for s in doc["sessions"]],
    }


def _write_text(path, text):
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


@command(
    "overlay build",
    help="Build an overlay from a draft in athlete units and write data/overlays/<id>.json",
    args=(arg("--input", required=True, metavar="FILE",
              help="the draft (overlay_draft schema); leave out id for a new overlay, give it to rebuild one"),),
    writes=True,
)
def build(args, ctx):
    draft = overlay.read_json(args.input)
    doc = overlay.build(draft, ctx.config, root=ctx.root, now=ctx.now())
    path = overlay.path_for(ctx.root, doc["id"])
    if path.exists():
        existing = overlay.read_json(path)
        if isinstance(existing, dict) and existing.get("approval"):
            raise RefusedError(
                f"Overlay {doc['id']} is approved, so it is not rebuilt; leave id out of the draft to build a new one."
            )
    jsonio.write_doc(path, doc, args.dry_run)
    try:
        unconfirmed = validity.unconfirmed_flags(ctx.root, doc)
    except ValidationError:
        unconfirmed = []
    for flag in unconfirmed:
        ctx.warn(flag["message"])
    return {"id": doc["id"], "path": _relative(ctx, path), "written": not args.dry_run, "overlay": doc}


@command(
    "overlay validate",
    help="Validate one overlay (ID or --file), or every overlay in data/overlays",
    args=(arg("id", nargs="?", metavar="ID", help="overlay id"),
          arg("--file", metavar="PATH", help="an overlay file anywhere, e.g. one not yet written")),
)
def validate(args, ctx):
    if args.id and args.file:
        raise UsageError("give an overlay ID or --file, not both")
    if args.file:
        targets = [(None, Path(args.file))]
    elif args.id:
        targets = [(args.id, overlay.path_for(ctx.root, args.id))]
    else:
        targets = [(i, overlay.path_for(ctx.root, i)) for i in overlay.ids(ctx.root)]

    results, details = [], []
    for expected_id, path in targets:
        doc = overlay.read_json(path)
        errors = overlay.validate(doc, ctx.root, ctx.config)
        if not errors and expected_id and doc["id"] != expected_id:
            errors.append(Error("$.id", f"the file is named {expected_id}.json but holds {doc['id']}"))
        doc_id = doc.get("id") if isinstance(doc, dict) else None
        approved = not errors and overlay.is_approved(doc)
        if not errors and doc.get("approval") and not approved:
            ctx.warn(f"{doc_id} was edited after approval; run overlay approve {doc_id} again once the athlete agrees")
        results.append({"id": doc_id, "path": _relative(ctx, path), "valid": not errors, "approved": approved})
        prefix = f"{_relative(ctx, path)}: " if len(targets) > 1 else ""
        details += [{"path": e.path, "message": prefix + e.message} for e in errors]
    if details:
        bad = [r["path"] for r in results if not r["valid"]]
        raise ValidationError(f"{', '.join(bad)} failed validation ({len(details)} problem(s))", details=details)
    return {"results": results}


@command("overlay list", help="List every overlay with its span, kind and approval")
def list_overlays(args, ctx):
    return {"overlays": [_summary(doc) for doc in overlay.list(ctx.root)]}


@command(
    "overlay current",
    help="Which overlay is in force on a date, and its sessions that day",
    args=(arg("--date", metavar="D", help="YYYY-MM-DD (default: today)"),),
)
def current(args, ctx):
    try:
        day = dates.parse_date(args.date) if args.date else ctx.today()
    except ValueError as exc:
        raise UsageError(str(exc)) from None
    found = overlay.in_force(ctx.root, day)
    data = {"date": day.isoformat(), "overlay_id": None, "kind": None, "span": None, "approved": None,
            "sessions": []}
    if found:
        doc, _ = found
        data.update(overlay_id=doc["id"], kind=doc["kind"], span=doc["span"], approved=overlay.is_approved(doc),
                    sessions=[{"session_id": s["session_id"], "title": s["title"],
                               "hevy_routine_id": s["hevy_routine_id"]} for s in overlay.sessions_on(doc, day)])
    return data


@command(
    "overlay render",
    help="Render the check-in's week-ahead region; with --into, write it into that file",
    args=(_ID, arg("--into", metavar="FILE", help="the check-in record whose marked region to write")),
    writes=True,
)
def render_region(args, ctx):
    doc = _load_valid(ctx, args.id)
    region = render.render_week_ahead(doc)
    if not args.into:
        return {"id": args.id, "text": region}
    target = Path(args.into)
    if not target.is_file():
        raise ValidationError(f"{target} does not exist; create the check-in record first")
    before = target.read_bytes().decode("utf-8")
    try:
        after = render.splice_region(before, render.REGION_KIND, args.id, region)
    except ValueError as exc:
        raise ValidationError(f"{target}: {exc}") from None
    changed = after != before
    if changed and not args.dry_run:
        _write_text(target, after)
    return {"id": args.id, "into": _relative(ctx, target), "changed": changed,
            "written": changed and not args.dry_run, "text": region}


@command(
    "overlay notes",
    help="The Hevy note for every exercise, per session (first exercise carries the week line)",
    args=(_ID, arg("--session", metavar="S", help="only this session id")),
)
def notes(args, ctx):
    doc = _load_valid(ctx, args.id)
    sessions = [s for s in doc["sessions"] if not args.session or s["session_id"] == args.session]
    if not sessions:
        raise ValidationError(f"Overlay {args.id} has no session {args.session}")
    return {
        "id": doc["id"],
        "sessions": [
            {
                "session_id": s["session_id"], "date": s["date"], "title": s["title"],
                "hevy_routine_id": s["hevy_routine_id"],
                "exercises": [
                    {"exercise_id": e["exercise_id"], "hevy_template_id": e["hevy_template_id"],
                     "note": render.render_hevy_note(doc, s, e, index == 0)}
                    for index, e in enumerate(s["exercises"])
                ],
            }
            for s in sessions
        ],
    }


def _approval_blocks(ctx, doc):
    """The unresolved blocks, with each missing load mode judged against the library as it is now.

    A stored flag whose mode has since been confirmed still blocks: push refuses
    on stored flags, and only a prescription re-check replaces them.
    """
    fresh = validity.unconfirmed_flags(ctx.root, doc)
    fresh_lines = {(f["session_id"], f["exercise_id"]) for f in fresh}
    blocks = []
    for flag in overlay.unresolved_blocks(doc):
        if flag["code"] != validity.UNCONFIRMED:
            blocks.append(flag)
        elif (flag["session_id"], flag["exercise_id"]) not in fresh_lines:
            blocks.append(dict(flag, message=(
                f"{flag['exercise_id']} now has a confirmed load mode; run python3 -m coach prescription check "
                f"--overlay {doc['id']} --write to re-check the overlay against it")))
    return blocks + fresh


@command(
    "overlay approve",
    help="Stamp the athlete's approval: approved_at and the hash any later edit breaks",
    args=(_ID,),
    writes=True,
)
def approve(args, ctx):
    doc = _load_valid(ctx, args.id)
    path = overlay.path_for(ctx.root, args.id)
    if overlay.is_approved(doc):
        return {"id": args.id, "hash": doc["approval"]["hash"], "approved_at": doc["approval"]["approved_at"],
                "already_approved": True, "written": False}
    blocks = _approval_blocks(ctx, doc)
    if blocks:
        raise RefusedError(
            f"Overlay {args.id} has {len(blocks)} unresolved block flag(s); resolve them before approval.",
            details=[{"path": None, "message": f"{f['code']} ({f['session_id']} / {f['exercise_id']}): {f['message']}"}
                     for f in blocks],
        )
    approved = overlay.approve(doc, ctx.now())
    jsonio.write_doc(path, approved, args.dry_run)
    return {"id": args.id, "hash": approved["approval"]["hash"], "approved_at": approved["approval"]["approved_at"],
            "already_approved": False, "written": not args.dry_run, "path": _relative(ctx, path)}
