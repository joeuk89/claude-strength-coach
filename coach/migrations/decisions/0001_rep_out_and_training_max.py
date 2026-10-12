"""Decisions v1 to v2: override sets may be rep-out sets, and a `training_max` decision records an explicit change
to a wave's training max (contract C25). No record changes."""

DOC = "decisions"
FROM = 1
TO = 2


def migrate(doc):
    return doc
