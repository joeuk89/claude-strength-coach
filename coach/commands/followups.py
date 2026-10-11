from coach import dates, followups
from coach.commands import arg, command
from coach.errors import UsageError


def _date(text, flag):
    if text is None:
        return None
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


def _written(doc_item, dry_run):
    return {"item": doc_item, "written": not dry_run}


@command("followups list", help="Follow-ups, each marked due when open with its review date today or past",
         args=(arg("--open", action="store_true", help="open items only"),
               arg("--due", action="store_true", help="due items only")))
def list_followups(args, ctx):
    today = ctx.today()
    found = [dict(item, due=followups.is_due(item, today)) for item in followups.load(ctx.root)["items"]]
    if args.open:
        found = [item for item in found if item["status"] == "open"]
    if args.due:
        found = [item for item in found if item["due"]]
    return {"today": today.isoformat(), "items": found}


@command("followups add", help="Raise a question to come back to on a review date",
         args=(arg("--text", required=True, metavar="TEXT", help="the question, one sentence"),
               arg("--review-at", required=True, metavar="D", help="when to review it"),
               arg("--source", required=True, metavar="TEXT", help='where it came from, e.g. "check-in 2026-10-11"'),
               arg("--raised", metavar="D", help="the day it was raised (default today)")),
         writes=True)
def add(args, ctx):
    raised = _date(args.raised, "--raised") or ctx.today()
    doc, item = followups.add(followups.load(ctx.root), args.text, _date(args.review_at, "--review-at"), args.source,
                              raised)
    followups.save(ctx.root, doc, args.dry_run)
    return _written(item, args.dry_run)


@command("followups resolve", help="Close a follow-up as answered",
         args=(arg("id", metavar="ID", help="follow-up id, e.g. f-0001"),
               arg("--note", metavar="TEXT", help="the answer, one line")),
         writes=True)
def resolve(args, ctx):
    doc, item = followups.resolve(followups.load(ctx.root), args.id, ctx.today(), args.note)
    followups.save(ctx.root, doc, args.dry_run)
    return _written(item, args.dry_run)


@command("followups drop", help="Close a follow-up that no longer matters, with the reason",
         args=(arg("id", metavar="ID", help="follow-up id, e.g. f-0001"),
               arg("--reason", required=True, metavar="TEXT", help="why it is dropped")),
         writes=True)
def drop(args, ctx):
    if not args.reason.strip():
        raise UsageError("--reason must say why the follow-up is dropped")
    doc, item = followups.drop(followups.load(ctx.root), args.id, ctx.today(), args.reason)
    followups.save(ctx.root, doc, args.dry_run)
    return _written(item, args.dry_run)


@command("followups defer", help="Keep a follow-up open with a new review date",
         args=(arg("id", metavar="ID", help="follow-up id, e.g. f-0001"),
               arg("--to", required=True, metavar="D", help="the new review date"),
               arg("--kept", action="store_true", help="it was reviewed today and stays open (default: deferred "
                                                       "unreviewed)"),
               arg("--note", metavar="TEXT", help="why, one line")),
         writes=True)
def defer(args, ctx):
    doc, item = followups.defer(followups.load(ctx.root), args.id, ctx.today(), _date(args.to, "--to"), args.note,
                                args.kept)
    followups.save(ctx.root, doc, args.dry_run)
    return _written(item, args.dry_run)


@command("followups render", help="The deep record's follow-up section; exits 1 while an item open before the date "
                                  "has no disposition dated that day",
         args=(arg("--deep", action="store_true", required=True, help="the deep check-in's section"),
               arg("--date", required=True, metavar="D", help="the deep check-in's date")))
def render(args, ctx):
    day = _date(args.date, "--date")
    doc = followups.load(ctx.root)
    text = followups.render_deep(doc, day)
    items = [dict(item, disposition=disposition, note=note)
             for item, disposition, note in followups.deep_items(doc, day)]
    return {"date": day.isoformat(), "text": text, "items": items}
