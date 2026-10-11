"""State v2 to v3: each slot's scheme state is wrapped with its scheme and pending state; rotation names its week (contract C23).

The scheme is not known from the state alone, so it is null until the next
`propose week` adopts the slot's current scheme.
"""

DOC = "state"
FROM = 2
TO = 3


def migrate(doc):
    doc["scheme_state"] = {
        slot: {"scheme": None, "data": data, "pending": None} for slot, data in doc["scheme_state"].items()
    }
    doc["rotation"]["week"] = None
    return doc
