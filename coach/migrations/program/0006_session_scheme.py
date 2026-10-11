"""Program v6 to v7: a conditioning session may carry a session-level density scheme; none does yet (contract C51)."""

DOC = "program"
FROM = 6
TO = 7


def migrate(doc):
    for session in doc["sessions"]:
        session["scheme"] = None
    return doc
