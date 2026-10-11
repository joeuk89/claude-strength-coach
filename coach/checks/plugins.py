"""Checks for plugins and the decisions file (contract C23, C25)."""

from coach import decisions, paths, plugins
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-23a"


@check(id="plugins_valid", owner=OWNER)
def plugins_valid(ctx):
    """Every framework and instance plugin meets the contract (`plugins validate`)."""
    return [Result("fail", f"{p['name']}: {p['message']}", p["path"]) for p in plugins.load(ctx.root).problems()]


@check(id="decisions_schema", owner=OWNER)
def decisions_schema(ctx):
    if not decisions.path_for(ctx.root).is_file():
        return [Result("skip", f"no {paths.DECISIONS} yet")]
    try:
        decisions.load(ctx.root)
    except ValidationError as exc:
        if not exc.details:
            return [Result("fail", exc.message, paths.DECISIONS.as_posix())]
        return [Result("fail", f"{d['path']}: {d['message']}", paths.DECISIONS.as_posix()) for d in exc.details]
    return []
