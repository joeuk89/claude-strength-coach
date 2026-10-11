"""`hevy record-fixtures`: read a real account with GET requests and keep an anonymised copy."""

import secrets
from datetime import timedelta

from coach import jsonio
from coach.hevy.anonymise import anonymise
from coach.hevy.client import timestamp
from coach.hevy.pull import COLLECTION_SOURCES

EVENTS_LOOKBACK = timedelta(weeks=8)


def fetch(client, now):
    """Every collection a fixture set holds, as {stem: [raw items]}; GET requests only."""
    responses = {"workouts": list(client.paginate("/v1/workouts", "workouts", page_size=10))}
    since = timestamp(now() - EVENTS_LOOKBACK)
    responses["workout_events"] = list(
        client.paginate("/v1/workouts/events", "events", page_size=10, params={"since": since})
    )
    for name, (path, key, page_size) in COLLECTION_SOURCES.items():
        responses[name] = list(client.paginate(path, key, page_size=page_size))
    return responses


def record(client, now, out_dir, *, api_key, dry_run=False):
    """Fetch, anonymise with a fresh random salt (never stored) and write one file per collection."""
    anonymised = anonymise(fetch(client, now), secrets.token_hex(16), secrets=[api_key] if api_key else [])
    files = []
    for stem, items in anonymised.items():
        path = out_dir / f"{stem}.json"
        files.append(path.name)
        jsonio.write_doc(path, {"x-anonymised": True, stem: items}, dry_run=dry_run)
    return {"out": str(out_dir), "dry_run": dry_run, "files": sorted(files),
            "counts": {stem: len(items) for stem, items in anonymised.items()}}
