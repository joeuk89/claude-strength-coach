import json
import os
import tempfile
from datetime import timezone
from pathlib import Path

from coach import datablock, paths, recipes
from coach.checks import Result
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError

SLOT_HELP = "only cards that fit this slot"


def _rel(path_like):
    return Path(path_like).as_posix()


def _read_json(ctx, name):
    path = Path(name)
    if not path.is_absolute():
        path = ctx.root / path
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except FileNotFoundError:
        raise ValidationError(f"{path}: no such file") from None
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def write_text(path, text):
    """Write text atomically, line endings as given."""
    path = Path(path)
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


def _summary(card):
    data = card.data
    per_serving = data.get("per_serving") or {}
    return {
        "slug": card.slug,
        "path": card.rel,
        "title": data.get("title"),
        "slots": data.get("slots"),
        "status": data.get("status"),
        "prep": data.get("prep"),
        "time_min": data.get("time_min"),
        "kcal": per_serving.get("kcal"),
        "protein_g": per_serving.get("protein_g"),
        "variations": [v.get("name") for v in data.get("variations", []) if isinstance(v, dict)],
    }


def _bank_or_fail(ctx):
    """The bank, refusing (exit 1) when any card cannot be read or breaks the schema."""
    bank = recipes.load_bank(ctx.root)
    problems = [{"path": path, "message": message} for path, message in bank.broken]
    for card in bank.cards:
        problems += [{"path": card.rel, "message": f"{card.slug}: {e.path} {e.message}"}
                     for e in recipes.schema_errors(card.data)]
    if problems:
        raise ValidationError(f"{len(problems)} recipe card problem(s): {problems[0]['message']}", details=problems)
    return bank


def _card(bank, slug):
    card = bank.get(slug)
    if card is None:
        raise ValidationError(f'no recipe card "{slug}" in {paths.MENU_DIR.as_posix()}/')
    return card


@command(
    "recipes list",
    help="List the recipe cards",
    args=(arg("--slot", help=SLOT_HELP), arg("--status", choices=("active", "benched"))),
)
def list_cards(args, ctx):
    bank = _bank_or_fail(ctx)
    cards = [_summary(card) for card in bank.cards
             if (not args.slot or args.slot in card.data["slots"])
             and (not args.status or card.data["status"] == args.status)]
    return {"cards": cards}


@command("recipes show", help="Show one card's data", args=(arg("slug"),))
def show(args, ctx):
    bank = recipes.load_bank(ctx.root)
    for path, message in bank.broken:
        if Path(path).stem == args.slug:
            raise ValidationError(message)
    card = _card(bank, args.slug)
    errors = recipes.schema_errors(card.data)
    fresh = None if errors else recipes.current_region(card) == recipes.render_card_region(card)
    return {"slug": card.slug, "path": card.rel, "card": card.data, "region_fresh": fresh,
            "schema_errors": [e.to_json() for e in errors]}


def _row(slug, path, found):
    statuses = {r.status for r in found}
    status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {"slug": slug, "path": path, "status": status,
            "results": [{"status": r.status, "message": r.message} for r in found]}


def validate_bank(ctx, slug=None):
    """Return (rows, results) for every card, or the one named."""
    bank = recipes.load_bank(ctx.root)
    config = ctx.config
    broken = [(path, message) for path, message in bank.broken if not slug or Path(path).stem == slug]
    cards = [card for card in bank.cards if not slug or card.slug == slug]
    if slug and not broken and not cards:
        _card(bank, slug)
    rows, results = [], []
    for path, message in broken:
        found = [Result("fail", message, path)]
        rows.append(_row(Path(path).stem, path, found))
        results += found
    for card in cards:
        found = recipes.validate_card(card, config)
        rows.append(_row(card.slug, card.rel, found))
        results += found
    rows.sort(key=lambda row: row["slug"])
    return rows, results


@command(
    "recipes validate",
    help="Check every card (schema, macro sum, protein density, variations, aisles); exit 1 on a fail",
    args=(arg("slug", nargs="?"),),
)
def validate_cards(args, ctx):
    rows, results = validate_bank(ctx, args.slug)
    for result in results:
        if result.status == "warn":
            ctx.warn(result.message)
    summary = {status: sum(1 for row in rows if row["status"] == status) for status in ("pass", "warn", "fail")}
    data = {"cards": rows, "summary": summary}
    failed = [r for r in results if r.status == "fail"]
    if failed:
        raise ValidationError(
            f"{len(failed)} recipe card problem(s): {failed[0].message}",
            details=[{"path": r.path, "message": r.message} for r in failed],
            data=data,
        )
    return data


@command(
    "recipes render",
    help="Rewrite each card's rendered region and the index from the data blocks",
    args=(arg("slug", nargs="?"),),
    writes=True,
)
def render(args, ctx):
    bank = _bank_or_fail(ctx)
    targets = [_card(bank, args.slug)] if args.slug else bank.cards
    out = {"cards": [], "index": None, "dry_run": args.dry_run}
    for card in targets:
        text = recipes.rendered_text(card)
        changed = text != card.text
        if changed and not args.dry_run:
            write_text(card.path, text)
        out["cards"].append({"slug": card.slug, "path": card.rel, "changed": changed})
    index_path = ctx.root / paths.MENU_INDEX
    if bank.cards or index_path.exists():
        text = recipes.render_index(bank, ctx.config)
        old = datablock.read_text(index_path) if index_path.exists() else None
        changed = text != old
        if changed and not args.dry_run:
            write_text(index_path, text)
        out["index"] = {"path": _rel(paths.MENU_INDEX), "changed": changed}
    return out


@command(
    "recipes import",
    help="Read a saved recipe page's schema.org JSON-LD into a draft card; writes nothing",
    args=(arg("--html", required=True, metavar="FILE", help="the saved page"),
          arg("--url", help="the page's address, recorded as the card's source")),
)
def import_page(args, ctx):
    path = Path(args.html)
    if not path.is_absolute():
        path = ctx.root / path
    try:
        page = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise ValidationError(f"{path}: no such file") from None
    try:
        draft, flags = recipes.import_jsonld(page, args.url)
    except ValidationError as exc:
        raise ValidationError(f"{path}: {exc.message}") from None
    recipe = recipes.extract_recipe(page)
    return {
        "slug": recipes.suggest_slug(draft["title"]),
        "card": draft,
        "toml": recipes.card_toml(draft),
        "prose": recipes.method_prose(recipe),
        "flags": flags,
    }


def _check_draft(ctx, slug, draft):
    if not isinstance(slug, str) or not recipes.SLUG.fullmatch(slug):
        raise ValidationError(f"slug must match {recipes.SLUG.pattern} (found {slug!r})")
    if not isinstance(draft, dict):
        raise ValidationError(f"{slug}: card must be an object")
    card = recipes.Card(slug=slug, path=ctx.root / paths.MENU_DIR / f"{slug}.md", text="", data=draft, body_start=0)
    found = recipes.validate_card(card, ctx.config)
    failed = [r for r in found if r.status == "fail"]
    if failed:
        raise ValidationError(
            f"{len(failed)} problem(s) in the draft: {failed[0].message}",
            details=[{"path": r.path, "message": r.message} for r in failed],
        )
    for result in found:
        ctx.warn(result.message)
    return found


@command(
    "recipes draft",
    help="Turn a JSON draft ({slug, card, prose}) into the full card text, validated; writes nothing",
    args=(arg("--input", required=True, metavar="FILE"),),
)
def draft(args, ctx):
    doc, path = _read_json(ctx, args.input)
    if not isinstance(doc, dict):
        raise ValidationError(f"{path}: expected an object with slug, card and prose")
    slug, card = doc.get("slug"), doc.get("card")
    found = _check_draft(ctx, slug, card)
    target = paths.MENU_DIR / f"{slug}.md"
    return {
        "slug": slug,
        "path": _rel(target),
        "exists": (ctx.root / target).exists(),
        "text": recipes.compose_card(slug, card, doc.get("prose") or ""),
        "results": [{"status": r.status, "message": r.message} for r in found],
    }


def _legacy_cards(ctx):
    found = []
    for path in recipes.card_paths(ctx.root):
        text = datablock.read_text(path)
        if recipes.is_legacy(text):
            found.append((path, text))
    return found


def _backup_dir(ctx):
    stamp = ctx.now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = ctx.root / paths.BACKUPS_DIR / stamp
    candidate, n = base, 1
    while candidate.exists():
        n += 1
        candidate = base.with_name(f"{stamp}-{n}")
    return candidate


@command(
    "recipes convert",
    help="Convert old YAML cards: --parse returns drafts and a review table; --apply --input FILE writes them",
    args=(arg("--parse", action="store_true", help="read the old cards and return drafts; writes nothing"),
          arg("--apply", action="store_true", help="write the reviewed cards from --input, with a backup"),
          arg("--input", metavar="FILE", help="the reviewed drafts: {cards: [{slug, card}]}")),
    writes=True,
)
def convert(args, ctx):
    if args.parse == args.apply:
        raise UsageError("recipes convert: give exactly one of --parse or --apply")
    if args.parse:
        if args.input:
            raise UsageError("recipes convert: --input goes with --apply")
        return _convert_parse(ctx)
    if not args.input:
        raise UsageError("recipes convert: --apply needs --input FILE")
    return _convert_apply(ctx, args)


def _convert_parse(ctx):
    cards, rows = [], []
    for path, text in _legacy_cards(ctx):
        try:
            draft, row = recipes.convert_yaml_card(text, slug=path.stem)
        except ValidationError as exc:
            raise ValidationError(f"{(paths.MENU_DIR / path.name).as_posix()}: {exc.message}") from None
        if row["slug"] != path.stem:
            row["notes"].append(f'front matter name "{row["slug"]}" differs from the file name; the file name wins')
            row["slug"] = path.stem
        cards.append({"slug": path.stem, "card": draft, "toml": recipes.card_toml(draft)})
        rows.append(row)
    return {"cards": cards, "review": rows, "table": recipes.review_table(rows), "dry_run": True}


def _convert_apply(ctx, args):
    doc, input_path = _read_json(ctx, args.input)
    entries = doc.get("cards") if isinstance(doc, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValidationError(f"{input_path}: expected {{\"cards\": [{{\"slug\", \"card\"}}, ...]}}")
    menu = ctx.root / paths.MENU_DIR
    planned = []
    for entry in entries:
        slug = entry.get("slug") if isinstance(entry, dict) else None
        card = entry.get("card") if isinstance(entry, dict) else None
        _check_draft(ctx, slug, card)
        path = menu / f"{slug}.md"
        if not path.is_file():
            raise ValidationError(f"{_rel(paths.MENU_DIR / path.name)}: no such card to convert")
        old = datablock.read_text(path)
        if not recipes.is_legacy(old):
            raise ValidationError(f"{_rel(paths.MENU_DIR / path.name)} is not an old YAML card")
        planned.append((slug, path, old, recipes.compose_card(slug, card, recipes.legacy_prose(old))))

    converted = {slug for slug, *_ in planned}
    remaining = [path.stem for path, _ in _legacy_cards(ctx) if path.stem not in converted]
    backup = _backup_dir(ctx)
    index_path = ctx.root / paths.MENU_INDEX
    out = {
        "backup_dir": _rel(backup.relative_to(ctx.root)),
        "written": [_rel(paths.MENU_DIR / f"{slug}.md") for slug, *_ in planned],
        "still_old_format": remaining,
        "index": None,
        "dry_run": args.dry_run,
    }
    if args.dry_run:
        return out

    for _, path, old, _ in planned:
        write_text(backup / paths.MENU_DIR / path.name, old)
    if index_path.exists():
        write_text(backup / paths.MENU_INDEX, datablock.read_text(index_path))
    for _, path, _, text in planned:
        write_text(path, text)
    if remaining:
        out["index"] = {"path": _rel(paths.MENU_INDEX), "changed": False,
                        "skipped": f"{len(remaining)} card(s) are still in the old format"}
    else:
        bank = _bank_or_fail(ctx)
        for card in bank.cards:
            text = recipes.rendered_text(card)
            if text != card.text:
                write_text(card.path, text)
        text = recipes.render_index(bank, ctx.config)
        old_index = datablock.read_text(index_path) if index_path.exists() else None
        if text != old_index:
            write_text(index_path, text)
        out["index"] = {"path": _rel(paths.MENU_INDEX), "changed": text != old_index}
    return out
