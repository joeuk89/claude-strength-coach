from coach import research
from coach.commands import arg, command
from coach.errors import ValidationError

KINDS = ("template", "local")


def _note_summary(note, today, citations):
    return {
        "id": note.id, "kind": note.kind, "topic": note.topic, "path": note.path,
        "written": note.written.isoformat(), "review_by": note.review_by.isoformat(),
        "status": research.note_status(note, today), "days_to_review": (note.review_by - today).days,
        "confidence": note.confidence, "applies_to": list(note.applies_to), "tags": list(note.tags),
        "claims": sum(1 for claim in note.claims if claim.status == "current"),
        "retired_claims": sum(1 for claim in note.claims if claim.status == "retired"),
        "cited_by": len({c.path for c in citations if c.note_id == note.id and c.path != note.path}),
        "updates": list(note.updates),
    }


def _warn_problems(ctx, problems):
    for problem in problems:
        if problem.status == "warn":
            ctx.warn(problem.message)


def _load(ctx):
    notes, problems, _ = research.load_all(ctx.root)
    research.raise_on_failures(problems)
    _warn_problems(ctx, problems)
    return notes


@command(
    "research status",
    help="List research notes with their review status, local supersessions and area status",
    args=(
        arg("--area", help="only notes covering this area"),
        arg("--kind", choices=KINDS, help="only notes of this kind"),
        arg("--expired", action="store_true", help="only expired notes"),
    ),
)
def status(args, ctx):
    today = ctx.today()
    notes = _load(ctx)
    citations = research.scan_citations(ctx.root, notes)
    rows = [_note_summary(note, today, citations) for note in notes]
    summary = {key: sum(1 for row in rows if row["status"] == key) for key in research.STATUS_ORDER}
    if args.area:
        rows = [row for row in rows if args.area in row["applies_to"]]
    if args.kind:
        rows = [row for row in rows if row["kind"] == args.kind]
    if args.expired:
        rows = [row for row in rows if row["status"] == "expired"]
    superseded = research.local_updates_from(notes, today)
    return {
        "today": today.isoformat(),
        "notes": rows,
        "superseded_locally": [{"ref": ref, "by": by} for ref, by in sorted(superseded.items())],
        "areas": research.area_statuses(notes, today),
        "summary": summary,
    }


@command("research show", help="Show one note (by id) or one claim (by rn:<note-id>.<n>) with its sources",
         args=(arg("ref", metavar="REF", help="a note id or a claim ref"),))
def show(args, ctx):
    today = ctx.today()
    notes = _load(ctx)
    parsed = research.parse_ref(args.ref) or research.parse_ref(f"rn:{args.ref}")
    note_id = parsed[0] if parsed else args.ref
    note = next((n for n in notes if n.id == note_id), None)
    claim = note.claim(parsed[1]) if note and parsed else None
    if note is None or (parsed and claim is None):
        raise ValidationError(f"{args.ref} names no research note or claim; see python3 -m coach research status")

    about = {"id": note.id, "kind": note.kind, "path": note.path, "topic": note.topic,
             "status": research.note_status(note, today), "written": note.written.isoformat(),
             "review_by": note.review_by.isoformat(), "confidence": note.confidence}
    if not parsed:
        return {"note": about, "data": note.data}
    return {
        "ref": claim.ref,
        "claim": claim.to_json(),
        "sources": [source.to_json() for source in note.sources if source.id in claim.sources],
        "note": about,
        "superseded_locally_by": research.local_updates_from(notes, today).get(claim.ref),
    }


@command("research cites", help="List every claim reference in the framework and instance files",
         args=(arg("--unresolved", action="store_true", help="only references that do not resolve"),))
def cites(args, ctx):
    notes = _load(ctx)
    citations = research.scan_citations(ctx.root, notes)
    if args.unresolved:
        citations = [c for c in citations if not c.resolved]
    return {"citations": [c.to_json() for c in citations]}


@command("research validate", help="Validate every research note; exit 1 if any is invalid")
def validate(args, ctx):
    notes = _load(ctx)
    return {"valid": len(notes), "notes": [{"id": n.id, "kind": n.kind, "path": n.path} for n in notes]}


@command("research render", help="Rewrite the rendered region of one note, or of every note; nothing else",
         args=(arg("id", nargs="?", metavar="ID", help="a note id (default: every note)"),), writes=True)
def render(args, ctx):
    notes = [research.load_one(ctx.root, args.id)] if args.id else research.load_notes(ctx.root)
    rows = []
    for note in notes:
        changed = research.write_region(ctx.root, note, args.dry_run)
        rows.append({"id": note.id, "path": note.path, "changed": changed})
    return {"dry_run": args.dry_run, "notes": rows}
