"""Program v8 to v9: an optional `dose_intent`; a program without one keeps the hypertrophy fallback (contract C40)."""

DOC = "program"
FROM = 8
TO = 9


def migrate(doc):
    return doc
