"""Program v7 to v8: a minimum week retains no coach-led sessions until it lists them (contract C40)."""

DOC = "program"
FROM = 7
TO = 8


def migrate(doc):
    if doc.get("minimum_week") is not None:
        doc["minimum_week"].setdefault("external_sessions", [])
    return doc
