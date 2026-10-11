"""The brief's link to the session sheets, when the athlete trains without Hevy (contract C46, C38)."""

from coach import config as config_module
from coach import paths, sheets
from coach.page_parts import Item

SLOTS = ("brief.sessions_footer",)


def contribute(ctx):
    if ctx.overlay is None or config_module.load(ctx.root).hevy.enabled:
        return None
    target = paths.SESSION_SHEETS.as_posix()
    links = " · ".join(f"[{session['title']}]({target}#{anchor})" for session, anchor in sheets.anchors(ctx.overlay))
    return {"brief.sessions_footer": [Item(f"Session sheets: [{target}]({target})" + (f" ({links})" if links else ""))]}
