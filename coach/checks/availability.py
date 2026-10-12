"""Planned days and missed-day rule destinations against the athlete's available days (contract C37)."""

from coach import missed, paths, program, structure
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-22"
_PROGRAM = paths.PROGRAM.as_posix()
_CONFIG = paths.CONFIG.as_posix()


@check(id="available_days_conflicts", owner=OWNER)
def available_days_conflicts(ctx):
    available = ctx.config.athlete.available_days
    if not program.exists(ctx.root):
        return [Result("skip", f"no {_PROGRAM} yet", _PROGRAM)]
    if not available:
        return [Result("pass", "[athlete] available_days is empty, so every day is available", _CONFIG)]
    try:
        doc = program.load(ctx.root)
        planned = structure.scheduled_days(ctx.root, ctx.today(), ctx.now())
    except ValidationError as exc:
        return [Result("skip", f"{_PROGRAM} cannot be read ({exc.message}); see program_schema", _PROGRAM)]
    allowed = f"[athlete] available_days ({missed.weekday_list(available)})"
    titles = {s["id"]: s["title"] for s in doc["sessions"]}
    results = []
    for weekday in missed.WEEKDAYS:
        if weekday in planned and weekday not in available:
            sessions = ", ".join(titles.get(s, s) for s in planned[weekday])
            results.append(Result("warn", (
                f"The schedule plans {sessions} on {weekday.capitalize()}, which is not in {allowed}: ask the "
                "athlete whether to add the day or move the session"), _PROGRAM))
    for index, rule in enumerate(doc["missed_day_rules"]):
        if rule["action"]["kind"] != "shift":
            continue
        session = titles.get(rule["session_id"], rule["session_id"])
        for weekday in rule["action"]["to_weekdays"]:
            if weekday not in available:
                results.append(Result("warn", (
                    f"$.missed_day_rules[{index}]: rule {rule['id']} moves {session} to {weekday.capitalize()}, "
                    f"which is not in {allowed}, so it never moves there: ask the athlete whether to add the day "
                    "or change the rule"), _PROGRAM))
    return results
