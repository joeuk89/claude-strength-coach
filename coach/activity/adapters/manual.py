"""The manual source: what the athlete enters with `activity add`, `wellness add` and `planned add` (contract C31).

It has no config table and nothing to fetch. `normalise` turns one command's
values into a C30 record; the command chooses the id.
"""

from datetime import timedelta

from coach.activity import records
from coach.activity.adapters import FetchResult

NAME = "manual"
KINDS = ("activity", "wellness", "planned")
NETWORK = False


def fetch(ctx, sync_state):
    return FetchResult(items=[], sync_state=dict(sync_state))


def normalise(item, ctx):
    build = {"activity": _activity, "wellness": _wellness, "planned": _planned}[item["file"]]
    return [build(item, ctx)]


def _activity(item, ctx):
    start = records.parse_local(item["start"], ctx.timezone())
    utc_offset = records.offset_text(start.utcoffset())
    seconds = item["duration_seconds"]
    return {
        "id": item["id"], "source": NAME, "source_id": None,
        "kind": item["kind"], "name": item.get("name"), "indoor": item.get("indoor"),
        "start": records.utc_text(start), "end": records.utc_text(start + timedelta(seconds=seconds)),
        "utc_offset": utc_offset, "local_date": records.local_date(start, utc_offset, None).isoformat(),
        "duration_seconds": seconds, "distance_meters": item.get("distance_meters"),
        "elevation_gain_meters": None, "avg_hr": item.get("avg_hr"), "max_hr": None, "active_kcal": None,
        "rpe": item.get("rpe"), "device": None, "notes": item.get("notes"),
    }


def _wellness(item, ctx):
    return {
        "id": item["id"], "source": NAME,
        "span": {"start": item["start"], "end": item["end"]},
        "sleep": item.get("sleep"),
        "resting_hr_bpm": item.get("resting_hr_bpm"), "hrv_ms": None, "steps": item.get("steps"),
        "body_mass_kg": item.get("body_mass_kg"), "body_fat_pct": item.get("body_fat_pct"), "device": None,
    }


def _planned(item, ctx):
    return {
        "id": item["id"], "source": NAME,
        "date": item["date"], "kind": item["kind"], "title": item["title"], "quality": item["quality"],
        "target": item.get("target"), "notes": item.get("notes"),
    }
