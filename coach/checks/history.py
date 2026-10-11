"""History checks: month files, unresolved exercises, annotations and session caps (contract C17, C19)."""

from coach import history, paths, program
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-20"


@check(id="session_cap_ids", owner=OWNER)
def session_cap_ids(ctx):
    caps = ctx.config["sessions"]["cap_minutes"]
    if not caps:
        return [Result("skip", "no [sessions.cap_minutes] entries")]
    if not program.exists(ctx.root):
        return [Result("skip", f"no {paths.PROGRAM} to compare the session ids with")]
    try:
        doc = program.read_json(program.path_for(ctx.root))
        known = {session["id"] for session in doc["sessions"]}
    except (ValidationError, KeyError, TypeError):
        return [Result("skip", f"{paths.PROGRAM} cannot be read; program_schema reports why")]
    return [Result("warn", f'[sessions.cap_minutes] names "{session_id}", which is not a session in {paths.PROGRAM}',
                   "config.toml")
            for session_id in sorted(caps) if session_id not in known]


def _month_results(ctx):
    """(docs, results): every month file that validates, and a fail per one that does not."""
    docs, results = [], []
    for path in history.month_files(ctx.root):
        where = path.relative_to(ctx.root).as_posix()
        try:
            doc = history.read_month(path)
        except ValidationError as exc:
            details = exc.details or [{"path": "$", "message": exc.message}]
            results += [Result("fail", f"{d['path']}: {d['message']}", where) for d in details]
            continue
        for index, workout in enumerate(doc["workouts"]):
            if workout["date"][:7] != doc["month"]:
                results.append(Result("fail", f"$.workouts[{index}].date: {workout['date']} is not in {doc['month']}",
                                      where))
        docs.append((where, doc))
    return docs, results


@check(id="history_schema", owner=OWNER)
def history_schema(ctx):
    if not history.month_files(ctx.root) and not history.annotations_path(ctx.root).is_file():
        return [Result("skip", f"no history in {paths.HISTORY_DIR}")]
    docs, results = _month_results(ctx)
    seen = {}
    for where, doc in docs:
        for workout in doc["workouts"]:
            workout_id = workout["workout_id"]
            if workout_id in seen:
                results.append(Result("fail", f"workout {workout_id} is in both {seen[workout_id]} and {where}", where))
            seen[workout["workout_id"]] = where
    if history.annotations_path(ctx.root).is_file():
        try:
            history.read_annotations(ctx.root)
        except ValidationError as exc:
            details = exc.details or [{"path": "$", "message": exc.message}]
            results += [Result("fail", f"{d['path']}: {d['message']}", paths.ANNOTATIONS.as_posix()) for d in details]
    return results


@check(id="history_unresolved", owner=OWNER)
def history_unresolved(ctx):
    if not history.month_files(ctx.root):
        return [Result("skip", f"no history in {paths.HISTORY_DIR}")]
    docs, _ = _month_results(ctx)
    results = []
    for where, doc in docs:
        for workout in doc["workouts"]:
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] is None:
                    reason = "matches no library exercise; run python3 -m coach library seed, then history rebuild"
                elif exercise["load_mode"] is None:
                    reason = (f"({exercise['exercise_id']}) has no confirmed load mode; run python3 -m coach library "
                              "confirm, then history rebuild")
                else:
                    continue
                results.append(Result("warn", f"{workout['date']} {workout['title']}: {exercise['title']} {reason} "
                                              f"--month {doc['month']}; stats skip it until then", where))
    return results


@check(id="annotations_valid", owner=OWNER)
def annotations_valid(ctx):
    where = paths.ANNOTATIONS.as_posix()
    if not history.annotations_path(ctx.root).is_file():
        return [Result("skip", f"no {where}")]
    try:
        doc = history.read_annotations(ctx.root)
        checker = history.Checker(ctx.root)
    except ValidationError as exc:
        return [Result("fail", exc.message, where)]
    results = []
    ids = set()
    for index, annotation in enumerate(doc["annotations"]):
        if annotation["id"] in ids:
            results.append(Result("fail", f"$.annotations[{index}]: id {annotation['id']} is used twice", where))
        ids.add(annotation["id"])
        for problem in checker.problems(annotation, doc["annotations"][:index]):
            results.append(Result("fail", f"$.annotations[{index}] ({annotation['id']}): {problem}", where))
    return results
