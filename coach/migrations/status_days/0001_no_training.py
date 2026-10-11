"""Status days v1 to v2: each row says whether it is a planned break with no training (contract C50).

No row was a planned break before, so every row gets `no_training` false.
"""

DOC = "status_days"
FROM = 1
TO = 2


def migrate(doc):
    for row in doc["days"]:
        row["no_training"] = False
    return doc
