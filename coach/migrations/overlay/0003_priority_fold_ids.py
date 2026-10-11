"""Overlay v3 to v4: a fold's `rule_id` may name a priority lift's floor rule, `priority:<exercise_id>` (contract C40).

No line changes, but the version is part of the approval hash, so an
approved overlay loses its approval as in the earlier steps.
"""

from coach import overlay

DOC = "overlay"
FROM = 3
TO = 4


def migrate(doc):
    return doc


def notes(before, after):
    if not overlay.is_approved(before):
        return []
    return [f"{before['id']} loses its approval: the migration changes it, so re-approve it before pushing it again"]
