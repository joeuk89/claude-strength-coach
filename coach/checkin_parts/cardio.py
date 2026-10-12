"""Runs and Sleep stated from the activity sources, and the cardio flags for the window (contract C36, C49).

With no activity source on, Runs appears only when the activity files
record or plan a run in the window: lifting alone never implies running.
"""

from datetime import timedelta

from coach import cardio, dates, render, weekflags
from coach import config as config_module
from coach.activity.store import ActivityStore
from coach.checkin_parts import Contribution, Field
from coach.errors import ValidationError

FIELDS = ("runs", "sleep")
RUNS_ASK = "Any others not logged: how many, and total distance?"
RUNS_ASK_NONE = "How many, and total distance?"
SLEEP_ASK = "How did it feel?"


def contribute(ctx):
    config = config_module.load(ctx.root)
    bouts = tuple(cardio.flag_bouts(ctx.root, config, ctx.window, ctx.today))
    week_ctx = weekflags.WeekFlagContext(ctx.root, ctx.today, ctx.window, "logged", config, None, bouts)
    card_flags = weekflags.run(week_ctx)
    if not cardio.activity_on(config):
        return Contribution(fields={"runs": _runs_on_file(ctx, config)}, flags=card_flags)
    numbers = cardio.week(ctx.root, ctx.window)
    missed = [i for i in cardio.reconcile(ctx.root, ctx.window, ctx.today)["items"] if i["status"] == "missed"]
    fields = {"runs": _runs(numbers, missed)}
    sleep = _sleep(ctx, config)
    if sleep is not None:
        fields["sleep"] = sleep
    return Contribution(fields=fields, flags=card_flags)


def _runs(numbers, missed):
    run = numbers["run"]
    lines = []
    if run["count"]:
        noun = "run" if run["count"] == 1 else "runs"
        distance = f", {run['distance']:g} {numbers['distance_unit']}" if run["distance"] else ""
        quality = f" ({run['quality']} quality)" if run["quality"] else ""
        lines.append(f"Logged: {run['count']} {noun}{distance}{quality}.")
    if missed:
        lines.append("Planned, not logged: " + ", ".join(
            f"{render.day_label(dates.parse_date(i['date']))} {i['title'] or i['kind']}" for i in missed) + ".")
    return Field(prefill=" ".join(lines) or None, ask=RUNS_ASK if run["count"] else RUNS_ASK_NONE)


def _runs_on_file(ctx, config):
    try:
        found = cardio.runs_on_file(ctx.root, config, ctx.window, ctx.today)
    except ValidationError:
        # With no source on, the activity checks skip these files, so a bad line must not stop the card.
        return None
    return None if found is None else _runs(found, found["missed"])


def _sleep(ctx, config):
    """The nightly observations stated for confirmation, or None (the builtin ask) when too few nights have data."""
    settings = config["cardio"]
    nights = dates.Span(ctx.today - timedelta(days=cardio.NIGHTS - 1), ctx.today)
    store = ActivityStore(ctx.root, config)
    summary = store.sleep_summary(nights)
    if summary["nights"] < settings["sleep_min_nights"]:
        return None
    short, _, _ = cardio.sleep_judgement(store, settings, ctx.today)
    return Field(prefill=(f"Recorded: {summary['nightly_avg_asleep_hours']:g} h a night "
                          f"over {summary['nights']} nights, "
                          f"{short} under {settings['sleep_short_hours']:g} h."), ask=SLEEP_ASK)
