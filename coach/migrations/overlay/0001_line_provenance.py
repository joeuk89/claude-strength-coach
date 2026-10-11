"""Overlay v1 to v2: every exercise line gains a nullable `provenance` (contract C21)."""

from coach import overlay

DOC = "overlay"
FROM = 1
TO = 2


def migrate(doc):
    for session in doc["sessions"]:
        for line in session["exercises"]:
            line["provenance"] = None
    return doc


def notes(before, after):
    if not overlay.is_approved(before):
        return []
    return [f"{before['id']} loses its approval: the migration changes it, so re-approve it before pushing it again"]
