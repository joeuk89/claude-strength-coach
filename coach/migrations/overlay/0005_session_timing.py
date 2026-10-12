"""Overlay v5 to v6: sessions gain a nullable planned `start` and `duration_minutes` (contract C10, C51)."""

from coach import overlay

DOC = "overlay"
FROM = 5
TO = 6


def migrate(doc):
    for session in doc["sessions"]:
        session["start"] = None
        session["duration_minutes"] = None
    return doc


def notes(before, after):
    if not overlay.is_approved(before):
        return []
    return [f"{before['id']} loses its approval: the migration changes it, so re-approve it before pushing it again"]
