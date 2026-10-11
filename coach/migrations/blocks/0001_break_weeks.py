"""Block ledger v1 to v2: a week may be class `break`, and each week counts its sessions on a planned break (C42).

No week before this version had a planned break, so every closed week gets `on_break` 0.
"""

DOC = "blocks"
FROM = 1
TO = 2


def migrate(doc):
    for block in doc["blocks"]:
        for week in block["weeks"]:
            week["on_break"] = 0
    return doc
