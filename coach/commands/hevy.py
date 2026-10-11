"""`hevy` commands: pull the cache, report on it, record test fixtures (R-12)."""

from pathlib import Path

from coach import paths
from coach.commands import arg, command
from coach.errors import ConfigError, RefusedError
from coach.hevy import envfile, transport
from coach.hevy.cache import HevyCache, age_hours
from coach.hevy.client import HevyClient
from coach.hevy.pull import pull as pull_cache
from coach.hevy.record import record


def _require_enabled(ctx):
    if not ctx.config.hevy.enabled:
        raise ConfigError("Hevy is turned off in config.toml ([hevy] enabled = false), so there is nothing to pull.")


@command(
    "hevy pull",
    help="Update the local Hevy cache: every workout once, then only what changed",
    args=(arg("--full", action="store_true", help="re-read every workout, not only the changes since the last pull"),),
    writes=True,
    network=True,
    writes_scope="cache",
)
def pull(args, ctx):
    _require_enabled(ctx)
    client = HevyClient.from_context(ctx)
    cache = HevyCache(ctx.root, clock=ctx.now)
    ctx.log("pulling from Hevy" + (" (dry run)" if args.dry_run else ""))
    return pull_cache(client, cache, ctx.now, full=args.full, dry_run=args.dry_run)


@command("hevy status", help="Report the Hevy cache's age and counts, and whether a key is set")
def status(args, ctx):
    config = ctx.config
    meta = HevyCache(ctx.root).meta()
    max_age = config.hevy.cache_max_age_hours
    data = {
        "enabled": config.hevy.enabled,
        "key": "present" if envfile.api_key(ctx.root, ctx.env) else "missing",
        "fixtures": bool(ctx.env.get(transport.FIXTURES_ENV)),
        "cache": "present" if meta else "missing",
        "cache_dir": paths.HEVY_CACHE_DIR.as_posix(),
        "max_age_hours": max_age,
        "pulled_at": None,
        "last_full_pull_at": None,
        "events_since": None,
        "age_hours": None,
        "stale": None,
        "counts": None,
    }
    if meta:
        age = age_hours(meta, ctx.now())
        data.update({
            "pulled_at": meta["last_pull_finished_at"],
            "last_full_pull_at": meta["last_full_pull_at"],
            "events_since": meta["events_since"],
            "age_hours": age,
            "stale": age > max_age,
            "counts": meta["counts"],
        })
    return data


@command(
    "hevy record-fixtures",
    help="Record anonymised test fixtures from the real Hevy account (GET requests only)",
    args=(arg("--out", required=True, metavar="DIR", help="directory for the fixture files"),),
    writes=True,
    network=True,
)
def record_fixtures(args, ctx):
    if ctx.env.get(transport.FIXTURES_ENV):
        raise RefusedError(
            f"record-fixtures reads the real Hevy API, so it refuses to run while {transport.FIXTURES_ENV} is set."
        )
    client = HevyClient.from_context(ctx)
    out_dir = Path(args.out).resolve()
    ctx.log(f"recording anonymised fixtures into {out_dir}" + (" (dry run)" if args.dry_run else ""))
    return record(client, ctx.now, out_dir, api_key=envfile.api_key(ctx.root, ctx.env), dry_run=args.dry_run)
