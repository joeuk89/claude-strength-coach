"""State v5 to v6: a 5/3/1 wave moves on from trained work, not from approval (contract C23).

The old wave state counted the week last approved, trained or not, so the
migration keeps its training max and counts the weeks before that one as
completed. The week last approved is judged again from the sessions logged
after the run that proposed it; history up to that day is marked judged.
"""

DOC = "state"
FROM = 5
TO = 6
OLD_KEYS = {"wave_week", "training_max", "proposed_for", "proposed_on"}


def _wave(data):
    return isinstance(data, dict) and set(data) == OLD_KEYS


def _migrated(data):
    completed = min(max(data["wave_week"] - 1, 0), 2)
    marker = data["proposed_on"] or data["proposed_for"]
    return {"completed_weeks": completed, "training_max": data["training_max"],
            "through": {"date": marker, "workout_id": None} if marker else None}


def migrate(doc):
    for entry in doc["scheme_state"].values():
        if _wave(entry.get("data")):
            entry["data"] = _migrated(entry["data"])
        pending = entry.get("pending")
        if pending and _wave(pending.get("data")):
            pending["data"] = _migrated(pending["data"])
    return doc


def notes(before, after):
    """One note per wave slot, naming the pending week when there is one: approving its overlay settles it."""
    found = []
    for slot, entry in before["scheme_state"].items():
        pending = entry.get("pending")
        if pending and _wave(pending.get("data")):
            old, new = pending["data"], after["scheme_state"][slot]["pending"]["data"]
            week = f"pending wave week {old['wave_week']} (overlay {pending['overlay_id']})"
        elif _wave(entry.get("data")):
            old, new = entry["data"], after["scheme_state"][slot]["data"]
            week = f"wave week {old['wave_week']}"
        else:
            continue
        if not old["wave_week"]:
            continue
        since = f"logged after {new['through']['date']}" if new["through"] else "logged"
        found.append(f"data/state.json: {slot}'s {week} counts as done only once a session {since} trained it")
    return found
