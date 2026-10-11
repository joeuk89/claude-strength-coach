"""Checks for the status-days file and the `[cardio]` ranges (contract C13, C48, C50)."""

from coach import paths, statusdays
from coach.checks import Result, check
from coach.config_tables.cardio import CAP_KEYS
from coach.errors import ValidationError

OWNER = "R-43"


@check(id="status_days_valid", owner=OWNER)
def status_days_valid(ctx):
    """Schema, unique ids, start on or before end, at most one open-ended row per kind."""
    if not statusdays.exists(ctx.root):
        return [Result("skip", f"no {paths.STATUS_DAYS} yet")]
    try:
        statusdays.load(ctx.root)
    except ValidationError as exc:
        if not exc.details:
            return [Result("fail", exc.message, paths.STATUS_DAYS.as_posix())]
        return [Result("fail", f"{d['path']}: {d['message']}", paths.STATUS_DAYS.as_posix()) for d in exc.details]
    return []


def _problems(cardio):
    found = [(key, "must be 0 (no cap) or more") for key in CAP_KEYS if cardio[key] < 0]
    if cardio["spike_ratio"] <= 1:
        found.append(("spike_ratio", "must be above 1: a run longer than this × the longest recent run is a spike"))
    if cardio["spike_lookback_days"] < 1:
        found.append(("spike_lookback_days", "must be at least 1"))
    if not 0 <= cardio["spike_min_history_days"] <= cardio["spike_lookback_days"]:
        found.append(("spike_min_history_days", "must be 0 to spike_lookback_days"))
    if not 0 < cardio["sleep_short_hours"] <= 24:
        found.append(("sleep_short_hours", "must be above 0 and at most 24"))
    for key in ("sleep_debt_nights", "sleep_min_nights"):
        if not 1 <= cardio[key] <= 7:
            found.append((key, "must be 1 to 7 (nights of the last seven)"))
    if cardio["reconcile_move_days"] < 0:
        found.append(("reconcile_move_days", "must be 0 or more"))
    for key in ("quality_rpe_min", "external_session_rpe"):
        if not 0 <= cardio[key] <= 10:
            found.append((key, "must be 0 to 10 (session RPE, CR-10 scale)"))
    if cardio["external_session_minutes"] < 0:
        found.append(("external_session_minutes", "must be 0 or more"))
    return found


@check(id="cardio_config", owner=OWNER)
def cardio_config(ctx):
    """Caps not negative, a spike ratio above 1, sleep thresholds in range."""
    cardio = ctx.config["cardio"]
    return [Result("fail", f"[cardio] {key} {message} (found {cardio[key]:g})", "config.toml")
            for key, message in _problems(cardio)]
