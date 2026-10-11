from coach import migrate
from coach.commands import command


@command("migrate status", help="List each owned data file with its schema version and the version this coach reads")
def status(args, ctx):
    rows = migrate.status(ctx.root)
    return {"files": rows, "behind": sum(1 for row in rows if row["state"] == "behind")}


@command("migrate run",
         help="Upgrade every data file behind its schema version: back up, migrate, validate, write, git add; "
              "never commits",
         writes=True)
def run(args, ctx):
    report = migrate.run(ctx.root, dry_run=args.dry_run, now=ctx.now())
    for warning in report.pop("warnings"):
        ctx.warn(warning)
    return report
