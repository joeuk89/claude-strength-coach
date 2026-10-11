"""State v1 to v2: each temporary routine records the overlay session it carries (contract C16)."""

DOC = "state"
FROM = 1
TO = 2


def migrate(doc):
    hevy = doc["hevy"]
    hevy["temporary_routines"] = [
        {"routine_id": routine_id, "overlay_id": None, "session_id": None}
        for routine_id in hevy["temporary_routines"]
    ]
    return doc
