"""Program v2 to v3: an empty set of weekly dose targets, so every muscle takes the default (contract C40)."""

DOC = "program"
FROM = 2
TO = 3


def migrate(doc):
    doc.setdefault("dose_targets", {})
    return doc
