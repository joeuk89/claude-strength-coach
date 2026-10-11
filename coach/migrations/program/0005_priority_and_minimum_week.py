"""Program v5 to v6: no priority lifts and no minimum week yet (contract C40)."""

DOC = "program"
FROM = 5
TO = 6


def migrate(doc):
    doc.setdefault("priority", [])
    doc.setdefault("minimum_week", None)
    return doc
