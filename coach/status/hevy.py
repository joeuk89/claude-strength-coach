"""How old the local Hevy cache is (contract C8, C52)."""

from coach.errors import ValidationError
from coach.hevy.cache import HevyCache, age_hours
from coach.status import Section, provider

PULL = "python3 -m coach hevy pull"


@provider(id="hevy", owner="R-26b", order=60)
def hevy(ctx):
    config = ctx.config.hevy
    if not config.enabled:
        return None
    limit = config.cache_max_age_hours
    try:
        meta = HevyCache(ctx.root).meta()
    except ValidationError as exc:
        return Section("hevy", [f"The Hevy cache cannot be read ({exc.message}); run {PULL} --full."],
                       {"age_hours": None, "limit_hours": limit}, "attention")
    if meta is None:
        return Section("hevy", [f"There is no Hevy cache yet; run {PULL} before reading logged workouts."],
                       {"age_hours": None, "limit_hours": limit}, "attention")
    age = age_hours(meta, ctx.now())
    data = {"age_hours": age, "limit_hours": limit, "last_pull_finished_at": meta["last_pull_finished_at"]}
    if age > limit:
        return Section("hevy", [f"The Hevy cache is {age:g} hours old, past the {limit:g}-hour limit; run {PULL}."],
                       data, "attention")
    return Section("hevy", [f"The Hevy cache is {age:g} hours old (limit {limit:g})."], data)
