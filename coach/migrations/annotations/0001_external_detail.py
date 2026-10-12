"""Annotations v1 to v2: a coach-led session may record its timing, effort, modality or a trainer cancellation (C17).

A v1 `external` annotation recorded none of these, so it keeps its meaning unchanged: `done` true is a session that
happened with the default length and effort, and `done` false one that did not happen, which stays a miss.
"""

DOC = "annotations"
FROM = 1
TO = 2


def migrate(doc):
    return doc
