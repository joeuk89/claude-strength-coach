"""`hevy pull`: fill the cache once, then keep it current from the workout events feed."""

from datetime import timedelta

from coach import dates
from coach.hevy.cache import CACHE_VERSION, HevyCache
from coach.hevy.client import timestamp
from coach.hevy.transport import event_time

# Events are re-read from a little before the last pull, so a clock that runs
# ahead of Hevy's cannot skip one; re-applying an event changes nothing.
EVENTS_OVERLAP = timedelta(minutes=10)

# Cache collection -> (endpoint, response key, page size).
COLLECTION_SOURCES = {
    "routines": ("/v1/routines", "routines", 10),
    "routine_folders": ("/v1/routine_folders", "routine_folders", 10),
    "exercise_templates": ("/v1/exercise_templates", "exercise_templates", 100),
    "body_measurements": ("/v1/body_measurements", "body_measurements", 10),
}
_DELETED = object()


def _all_workouts(client):
    return {w["id"]: w for w in client.paginate("/v1/workouts", "workouts", page_size=10)}


def _events(client, since):
    query = timestamp(dates.parse_timestamp(since) - EVENTS_OVERLAP)
    events = list(client.paginate("/v1/workouts/events", "events", page_size=10, params={"since": query}))
    latest = {}
    for event in sorted(events, key=event_time):
        if event.get("type") == "deleted":
            latest[event["id"]] = _DELETED
        else:
            latest[event["workout"]["id"]] = event["workout"]
    return latest, len(events)


def pull(client, cache: HevyCache, now, *, full=False, dry_run=False):
    """Pull from Hevy into the cache and return the command's data.

    `now` returns an aware datetime. A pull with no previous one is full.
    With dry_run, every GET still happens and nothing is written.
    """
    started = timestamp(now())
    meta = cache.meta()
    full = full or meta is None
    cached_ids = set(cache.workout_ids())

    writes, removes = [], []
    if full:
        incoming = _all_workouts(client)
        removes = sorted(cached_ids - set(incoming))
        event_count = None
    else:
        incoming, event_count = _events(client, meta["events_since"])
        removes = sorted(i for i, w in incoming.items() if w is _DELETED and i in cached_ids)
        incoming = {i: w for i, w in incoming.items() if w is not _DELETED}
    added = updated = 0
    for workout_id, workout in sorted(incoming.items()):
        if workout_id not in cached_ids:
            added += 1
            writes.append(workout)
        elif cache.workout(workout_id) != workout:
            updated += 1
            writes.append(workout)

    collections, changed = {}, {}
    for name, (path, key, page_size) in COLLECTION_SOURCES.items():
        collections[name] = list(client.paginate(path, key, page_size=page_size))
        doc = cache.read(name)
        changed[name] = doc is None or doc["data"] != collections[name]

    finished = timestamp(now())
    counts = {"workouts": len(cached_ids) + added - len(removes)}
    counts.update({name: len(items) for name, items in collections.items()})
    new_meta = {
        "schema_version": CACHE_VERSION,
        "last_pull_started_at": started,
        "last_pull_finished_at": finished,
        "last_full_pull_at": started if full else meta["last_full_pull_at"],
        "events_since": started,
        "counts": counts,
    }
    if not dry_run:
        for workout in writes:
            cache.write_workout(workout, started)
        for workout_id in removes:
            cache.remove_workout(workout_id)
        for name, items in collections.items():
            cache.write_collection(name, items, started)
        cache.write_meta(new_meta)

    data = {
        "mode": "full" if full else "incremental",
        "dry_run": dry_run,
        "pulled_at": finished,
        "events_since": started,
        "counts": counts,
        "changes": {
            "workouts": {"added": added, "updated": updated, "removed": len(removes)},
            "collections": changed,
        },
    }
    if event_count is not None:
        data["events"] = event_count
    return data
