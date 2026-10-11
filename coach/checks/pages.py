"""Standing page checks: each page equals a fresh render at its own as-of time; the brief fits a phone (C38)."""

from coach import pages, paths
from coach.checks import Result, check

OWNER = "R-25"


@check(id="pages_fresh", owner=OWNER)
def pages_fresh(ctx):
    found = pages.freshness(ctx.root)
    if not found:
        return [Result("skip", "No generated pages yet (this-week.md, README.md, progress.md).")]
    return [Result(status, message, path) for path, status, message in found]


@check(id="pages_line_ceiling", owner=OWNER)
def pages_line_ceiling(ctx):
    path = ctx.root / paths.BRIEF
    rel = paths.BRIEF.as_posix()
    if not path.is_file():
        return [Result("skip", f"No {rel} yet.", rel)]
    lines = len(path.read_text(encoding="utf-8").splitlines())
    if lines > pages.BRIEF_LINE_CEILING:
        return [Result("fail", f"{rel} has {lines} lines, over the {pages.BRIEF_LINE_CEILING}-line ceiling; "
                               "re-render it with python3 -m coach pages render", rel)]
    return [Result("pass", f"{rel} has {lines} lines.", rel)]
