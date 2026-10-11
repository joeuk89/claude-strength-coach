"""`sheets render`: session sheets to train from without Hevy (contract C46)."""

from coach import sheets
from coach.commands import arg, command


@command("sheets render", help="Write this-week-sheets.md: each session of the week's overlay as per-set tables",
         args=(arg("--overlay", metavar="ID", help="overlay id (default: the brief's overlay, else the next one)"),),
         writes=True)
def render(args, ctx):
    data = sheets.write(ctx.root, ctx.today(), args.overlay, dry_run=args.dry_run)
    if ctx.config.hevy.enabled:
        ctx.warn("hevy_enabled: Hevy is on ([hevy] enabled = true), so the athlete trains from Hevy routines and "
                 "nothing checks these sheets")
    if not data["approved"]:
        ctx.warn(f"overlay {data['overlay_id']} is not approved yet; the sheets say so")
    return data
