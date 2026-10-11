import os
import tempfile
from pathlib import Path

from coach import dates, jsonio, meals
from coach.commands import arg, command
from coach.errors import RefusedError, UsageError

_ID = arg("id", metavar="ID", help="meal plan id: its first day, e.g. 2026-10-12")


def _relative(ctx, path):
    try:
        return Path(path).resolve().relative_to(ctx.root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


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


@command(
    "meals template",
    help="The standing week from [nutrition.template] and the anchors, before any exceptions, open slots marked",
    args=(arg("--week", metavar="D", help="any date in the week, or YYYY-Www (default: the week ahead)"),),
)
def template(args, ctx):
    week_starts = ctx.config.athlete.week_starts
    if args.week:
        try:
            span = dates.parse_week(args.week, week_starts)
        except ValueError as exc:
            raise UsageError(f"--week: {exc}") from None
    else:
        span = meals.week_ahead(ctx.today(), week_starts)
    return meals.template_week(ctx.root, span, ctx.config)


@command(
    "meals build",
    help="Resolve a draft of the week's exceptions into data/nutrition/plans/<id>.json",
    args=(arg("--input", required=True, metavar="FILE", help="the draft (meal_plan_draft schema)"),),
    writes=True,
)
def build(args, ctx):
    draft = meals.read_json(args.input)
    doc = meals.build(draft, ctx.root, now=ctx.now(), config=ctx.config)
    path = meals.path_for(ctx.root, doc["id"])
    if path.exists():
        existing = meals.read_json(path)
        if isinstance(existing, dict) and existing.get("approval"):
            raise RefusedError(f"Meal plan {doc['id']} is approved, so it is not rebuilt; start the draft's span on "
                               "another day for a new plan.")
    jsonio.write_doc(path, doc, args.dry_run)
    return {"id": doc["id"], "path": _relative(ctx, path), "written": not args.dry_run, "plan": doc}


@command("meals show", help="One meal plan and whether its approval holds", args=(_ID,))
def show(args, ctx):
    doc = meals.load(ctx.root, args.id)
    return {"id": args.id, "path": _relative(ctx, meals.path_for(ctx.root, args.id)),
            "approved": meals.is_approved(doc), "plan": doc}


@command("meals validate", help="Check one meal plan's schema and arithmetic", args=(_ID,))
def validate(args, ctx):
    doc = meals.load(ctx.root, args.id)
    if doc["approval"] and not meals.is_approved(doc):
        ctx.warn(f"{args.id} was edited after approval; run meals approve {args.id} again once the athlete agrees")
    return {"id": args.id, "valid": True, "approved": meals.is_approved(doc)}


@command("meals render", help="Write nutrition/plans/<id>.md from the plan", args=(_ID,), writes=True)
def render_plan(args, ctx):
    doc = meals.load(ctx.root, args.id)
    text = meals.render_plan(doc)
    path = ctx.root / meals.rendered_path(args.id)
    changed = not path.is_file() or path.read_bytes() != text.encode("utf-8")
    if changed and not args.dry_run:
        _write_text(path, text)
    return {"id": args.id, "path": meals.rendered_path(args.id).as_posix(), "changed": changed,
            "written": changed and not args.dry_run, "text": text}


@command(
    "meals approve",
    help="Stamp the athlete's approval: approved_at and the hash any later edit breaks",
    args=(_ID,),
    writes=True,
)
def approve(args, ctx):
    doc = meals.load(ctx.root, args.id)
    path = meals.path_for(ctx.root, args.id)
    if meals.is_approved(doc):
        return {"id": args.id, "hash": doc["approval"]["hash"], "approved_at": doc["approval"]["approved_at"],
                "already_approved": True, "written": False}
    blocks = meals.unresolved_blocks(doc)
    if blocks:
        raise RefusedError(
            f"Meal plan {args.id} has {len(blocks)} unresolved block flag(s); fix the draft and build again.",
            details=[{"path": None, "message": f"{flag['code']}: {flag['message']}"} for flag in blocks],
        )
    approved = meals.approve(doc, ctx.now())
    jsonio.write_doc(path, approved, args.dry_run)
    return {"id": args.id, "hash": approved["approval"]["hash"], "approved_at": approved["approval"]["approved_at"],
            "already_approved": False, "written": not args.dry_run, "path": _relative(ctx, path)}


@command(
    "meals shopping",
    help="The plan's shopping list as markdown, or as a GitHub issue title and body (approved plans only)",
    args=(_ID, arg("--format", choices=("markdown", "issue"), default="markdown", help="default: markdown")),
)
def shopping(args, ctx):
    doc = meals.load(ctx.root, args.id)
    if args.format == "markdown":
        return {"id": args.id, "format": "markdown", "text": meals.shopping_markdown(doc)}
    if not meals.is_approved(doc):
        raise RefusedError(f"Meal plan {args.id} is not approved; run meals approve {args.id} after the athlete's "
                           "\"go\".")
    title, body = meals.shopping_issue(doc)
    shopping_issue = ctx.config["nutrition"].get("template", {}).get("shopping_issue", False)
    return {"id": args.id, "format": "issue", "title": title, "body": body, "shopping_issue": shopping_issue}
