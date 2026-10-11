"""Explicit cardio identities, kept separately so source reimports cannot erase them."""

from coach import dates, jsonio, paths
from coach.errors import ValidationError

SCHEMA = "activity_associations"


def load(root):
    path = root / paths.ACTIVITY_ASSOCIATIONS
    return jsonio.read_doc(path, SCHEMA) if path.is_file() else {"schema_version": 1, "associations": {}}


def associate(store, activity_id, planned_id, clear, dry_run):
    if clear == (planned_id is not None):
        raise ValidationError("give --planned-id or --clear")
    doc = load(store.root)
    links = doc["associations"]
    activities = store.activity_groups()
    activity = next((a for a in activities if activity_id in a["merged_from"]), None)
    aliases = activity["merged_from"] if activity else [activity_id]
    if clear:
        if not any(key in links for key in aliases):
            raise ValidationError(f"no association for activity {activity_id!r}")
    else:
        plan = next((p for p in store.records("planned") if p["id"] == planned_id), None)
        if activity is None or plan is None:
            raise ValidationError("association needs a live activity ID and a live planned ID")
        gap = abs((dates.parse_date(activity["local_date"]) - dates.parse_date(plan["date"])).days)
        if activity["kind"] != plan["kind"] or gap > store.config["cardio"]["reconcile_move_days"]:
            raise ValidationError("association needs the same kind within reconcile_move_days")
        if any(value == planned_id and key not in aliases for key, value in links.items()):
            raise ValidationError("planned ID already associated; clear that association first")
    before = dict(links)
    for key in aliases:
        links.pop(key, None)
    if not clear:
        links[activity_id] = planned_id
    changed = before != links
    if changed:
        jsonio.write_doc(store.root / paths.ACTIVITY_ASSOCIATIONS, doc, dry_run)
    return {"activity_id": activity_id, "planned_id": planned_id, "changed": changed,
            "written": changed and not dry_run}
