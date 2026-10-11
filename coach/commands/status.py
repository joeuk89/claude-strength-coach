from coach import status
from coach.commands import command


@command("status", help="Where this instance stands now, from local files only: one section per provider")
def show(args, ctx):
    today = ctx.today()
    sections = status.collect(ctx.root, today, env=ctx.env, stderr=ctx.stderr)
    return {"instance": status.instance_kind(ctx.root), "today": today.isoformat(),
            "sections": [section.to_json() for section in sections]}
