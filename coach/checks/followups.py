"""Checks for the follow-ups and niggles files (contract C13, C27)."""

from coach import followups, niggles, paths
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-27"


def _results(load, root, path):
    try:
        load(root)
    except ValidationError as exc:
        if not exc.details:
            return [Result("fail", exc.message, path.as_posix())]
        return [Result("fail", f"{d['path']}: {d['message']}", path.as_posix()) for d in exc.details]
    return []


@check(id="followups_schema", owner=OWNER)
def followups_schema(ctx):
    if not followups.exists(ctx.root):
        return [Result("skip", f"no {paths.FOLLOWUPS} yet")]
    return _results(followups.load, ctx.root, paths.FOLLOWUPS)


@check(id="niggles_schema", owner=OWNER)
def niggles_schema(ctx):
    """The schema, every pattern in the library's pattern list, every exercise id in the library."""
    if not niggles.exists(ctx.root):
        return [Result("skip", f"no {paths.NIGGLES} yet")]
    return _results(niggles.load, ctx.root, paths.NIGGLES)
