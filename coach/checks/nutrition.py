"""Nutrition checks: the readings series and the override (contract C35)."""

from coach import nutrition, paths
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-33a"


@check(id="nutrition_readings", owner=OWNER)
def nutrition_readings(ctx):
    where = paths.NUTRITION_READINGS.as_posix()
    if not (ctx.root / paths.NUTRITION_READINGS).exists():
        return [Result("skip", f"no readings yet in {where}")]
    try:
        nutrition.read_doc(ctx.root)
    except ValidationError as exc:
        return [Result("fail", exc.message, where)]
    return []


@check(id="nutrition_override", owner=OWNER)
def nutrition_override(ctx):
    config = ctx.config
    if not nutrition.enabled(config):
        return []
    override = nutrition.override_view(config.nutrition, ctx.today())
    return [Result("warn", item["message"], paths.CONFIG.as_posix())
            for item in nutrition.override_flags(override, config.nutrition.app != "none")]
