"""Missed-day rules name real, active sessions and exercises; folds never outlive their week (contract C37)."""

from datetime import timedelta

from coach import dates, missed, overlay, paths, program
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-22"
FOLD_DAYS = 6
_PROGRAM = paths.PROGRAM.as_posix()


def problems(doc):
    """(JSONPath, message) for each rule naming a missing or inactive session, or an exercise its session lacks."""
    sessions = {s["id"]: s for s in doc["sessions"]}
    found = []
    for index, rule in enumerate(doc["missed_day_rules"]):
        path = f"$.missed_day_rules[{index}]"
        source = sessions.get(rule["session_id"])
        if source is None:
            found.append((f"{path}.session_id", f"rule {rule['id']} names no program session {rule['session_id']}"))
        elif source["status"] != "active":
            found.append((f"{path}.session_id",
                          f"rule {rule['id']} names {rule['session_id']}, which is not active ({source['status']})"))
        action = rule["action"]
        into = action.get("into")
        if into is not None and into != missed.NEXT:
            target = sessions.get(into)
            if target is None:
                found.append((f"{path}.action.into", f"rule {rule['id']} folds into {into}, which is no program "
                                                     "session; use a session id or \"next\""))
            elif target["status"] != "active":
                found.append((f"{path}.action.into",
                              f"rule {rule['id']} folds into {into}, which is not active ({target['status']})"))
        if source is not None:
            own = {e["exercise_id"] for e in source["exercises"]}
            for e_index, item in enumerate(action.get("exercises", [])):
                if item["exercise_id"] not in own:
                    found.append((f"{path}.action.exercises[{e_index}].exercise_id",
                                  f"rule {rule['id']} folds {item['exercise_id']}, which {rule['session_id']} "
                                  "does not have"))
    return found


@check(id="missed_rules_valid", owner=OWNER)
def missed_rules_valid(ctx):
    if not program.exists(ctx.root):
        return [Result("skip", f"no {_PROGRAM} yet", _PROGRAM)]
    try:
        doc = program.read_json(program.path_for(ctx.root))
        shape = program.validate(doc)
    except ValidationError as exc:
        return [Result("skip", f"{_PROGRAM} cannot be read ({exc.message}); see program_schema", _PROGRAM)]
    if shape:
        return [Result("skip", f"{_PROGRAM} fails its schema; see program_schema", _PROGRAM)]
    return [Result("fail", f"{path}: {message}", _PROGRAM) for path, message in problems(doc)]


def _live(ctx):
    today = ctx.today().isoformat()
    found = []
    for overlay_id in overlay.ids(ctx.root):
        try:
            doc = overlay.load(ctx.root, overlay_id)
        except ValidationError:
            continue
        if doc["span"]["end"] >= today:
            found.append(doc)
    return found


@check(id="overlay_folds_expired", owner=OWNER)
def overlay_folds_expired(ctx):
    docs = _live(ctx)
    if not docs:
        return [Result("skip", "No overlay's span ends today or later.", paths.OVERLAYS_DIR.as_posix())]
    results = []
    for doc in docs:
        where = overlay.path_for(ctx.root, doc["id"]).relative_to(ctx.root).as_posix()
        oldest = dates.parse_date(doc["span"]["start"]) - timedelta(days=FOLD_DAYS)
        for s_index, session in enumerate(doc["sessions"]):
            for e_index, line in enumerate(session["exercises"]):
                fold = line.get("fold")
                if not fold:
                    continue
                at = f"$.sessions[{s_index}].exercises[{e_index}].fold"
                if doc["kind"] in ("weekly", "deload"):
                    results.append(Result("fail", (
                        f"{at}: a {doc['kind']} overlay holds {line['exercise_id']} folded by rule {fold['rule_id']}; "
                        "a fold lasts one week, so build the week from the program again"), where))
                elif dates.parse_date(fold["from_date"]) < oldest:
                    results.append(Result("fail", (
                        f"{at}: {line['exercise_id']} was folded from {fold['from_date']}, more than {FOLD_DAYS} days "
                        f"before the span starts on {doc['span']['start']}; a fold lasts one week"), where))
    return results
