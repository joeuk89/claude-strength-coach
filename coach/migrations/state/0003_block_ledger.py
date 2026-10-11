"""State v3 to v4: `block` takes the light-week shape and the block ledger starts from the old count (contract C42).

The old deload status maps onto the light week: `due` becomes `proposed`,
`in_progress` becomes `agreed` for the week it began, `skipped` stays, and
`not_due` and `done` become `not_due`. A proposed week's date and reason
are not in the old state, so they stay null until the next `block close`.
"""

DOC = "state"
FROM = 3
TO = 4

FIRST_BLOCK = "b-0001"
_STATUS = {"not_due": "not_due", "done": "not_due", "due": "proposed", "in_progress": "agreed", "skipped": "skipped"}


def migrate(doc):
    old = doc["block"]
    status = _STATUS[old["deload"]["status"]]
    doc["block"] = {
        "id": FIRST_BLOCK,
        "started": old["started"],
        "hard_weeks_completed": old["hard_weeks_completed"],
        "last_closed_week": None,
        "last_deep_review": None,
        "light_week": {
            "status": status,
            "type": "deload" if status in ("proposed", "agreed") else None,
            "reason": None,
            "week": old["deload"]["since"] if status == "agreed" else None,
            "decision_id": None,
        },
    }
    return doc


def creates(before, after):
    """The block ledger, seeded with the old count: written only when the instance has none."""
    block = after["block"]
    return {"data/blocks.json": {
        "schema_version": 1,
        "blocks": [{"id": FIRST_BLOCK, "started": block["started"], "seed_hard_weeks": block["hard_weeks_completed"],
                    "seed_reason": "carried over from data/state.json by the migration", "ended": None,
                    "end_reason": None, "weeks": []}],
    }}


def notes(before, after):
    old = before["block"]["deload"]["status"]
    new = after["block"]["light_week"]["status"]
    return [f"data/state.json: block deload {old} is now light week {new}; data/blocks.json starts block "
            f"{FIRST_BLOCK} at {after['block']['hard_weeks_completed']} hard weeks"]
