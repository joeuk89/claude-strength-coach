from coach import checks
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError


@command(
    "check",
    help="Run the instance checks; exit 1 if any fails",
    args=(
        arg("--only", action="append", metavar="IDS", help="comma-separated check ids to run (repeatable)"),
        arg("--list", action="store_true", help="list the registered checks without running them"),
    ),
)
def run_checks(args, ctx):
    registered = checks.discover()
    if args.list:
        return {"checks": [{"id": item.id, "owner": item.owner} for item in registered]}

    selected = registered
    if args.only:
        wanted = [part.strip() for value in args.only for part in value.split(",") if part.strip()]
        known = {item.id for item in registered}
        unknown = [name for name in wanted if name not in known]
        if unknown:
            raise UsageError(f"unknown check id(s): {', '.join(unknown)}; see python3 -m coach check --list")
        selected = [item for item in registered if item.id in wanted]

    rows, summary = checks.run(ctx, selected)
    data = {"results": rows, "summary": summary}
    failed = [row for row in rows if row["status"] == "fail"]
    if failed:
        ids = ", ".join(dict.fromkeys(row["id"] for row in failed))
        raise ValidationError(
            f"{len(failed)} check result(s) failed: {ids}.",
            details=[{"path": row["path"], "message": f"{row['id']}: {row['message']}"} for row in failed],
            data=data,
        )
    return data
