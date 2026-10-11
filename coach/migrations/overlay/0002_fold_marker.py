"""Overlay v2 to v3: lines gain a nullable `fold` and sessions a nullable `moved_from` (contract C37)."""

from coach import overlay

DOC = "overlay"
FROM = 2
TO = 3


def migrate(doc):
    for session in doc["sessions"]:
        session["moved_from"] = None
        for line in session["exercises"]:
            line["fold"] = None
    return doc


def notes(before, after):
    if not overlay.is_approved(before):
        return []
    return [f"{before['id']} loses its approval: the migration changes it, so re-approve it before pushing it again"]
