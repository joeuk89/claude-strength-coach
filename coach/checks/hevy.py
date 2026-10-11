"""Checks on the local Hevy cache (R-12)."""

from coach import paths
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.hevy.cache import META, HevyCache, age_hours

PULL = "python3 -m coach hevy pull"


@check(id="hevy_cache_age", owner="R-12")
def hevy_cache_age(ctx):
    hevy = ctx.config.hevy
    path = (paths.HEVY_CACHE_DIR / META).as_posix()
    if not hevy.enabled:
        return [Result("skip", "Hevy is turned off in config.toml.")]
    try:
        meta = HevyCache(ctx.root).meta()
    except ValidationError as exc:
        return [Result("fail", exc.message, path)]
    if meta is None:
        return [Result("warn", f"There is no Hevy cache yet; run {PULL}.", path)]
    age = age_hours(meta, ctx.now())
    limit = hevy.cache_max_age_hours
    if age > limit:
        return [Result("warn", f"The Hevy cache is {age:g} hours old, past the {limit:g}-hour limit; run {PULL}.", path)]
    return [Result("pass", f"The Hevy cache is {age:g} hours old (limit {limit:g}).", path)]
