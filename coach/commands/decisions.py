from coach import decisions
from coach.commands import arg, command
from coach.errors import UsageError

_STATUSES = ("active", "expired", "withdrawn")


@command("decisions list", help="Recorded coaching decisions, each with its effective status",
         args=(arg("--kind", choices=decisions.KINDS, help="only this kind"),
               arg("--status", choices=_STATUSES, help="only decisions with this effective status")))
def list_decisions(args, ctx):
    found = [d for d in decisions.with_status(decisions.load(ctx.root), ctx.today())
             if (args.kind is None or d["kind"] == args.kind)
             and (args.status is None or d["effective_status"] == args.status)]
    return {"today": ctx.today().isoformat(), "decisions": found}


@command("decisions withdraw", help="Close a decision with the reason it no longer holds; it is never deleted",
         args=(arg("id", metavar="ID", help="decision id, e.g. d-0001"),
               arg("--reason", required=True, metavar="TEXT", help="why it is withdrawn")),
         writes=True)
def withdraw(args, ctx):
    if not args.reason.strip():
        raise UsageError("--reason must say why")
    stamp = ctx.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    closed = decisions.withdraw(ctx.root, args.id, args.reason.strip(), stamp, args.dry_run)
    return {"decision": closed, "written": not args.dry_run}
