"""Program v7 to v8: minimum weeks retain no coach-led sessions until explicitly configured."""

DOC = "program"
FROM = 7
TO = 8


def migrate(doc):
    if doc.get("minimum_week") is not None:
        doc["minimum_week"].setdefault("external_sessions", [])
    return doc
