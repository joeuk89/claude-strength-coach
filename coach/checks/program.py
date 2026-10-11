"""Program and state checks: schemas, exercise ids, fresh routine pages, avoided exercises (contract C13, C54)."""

from coach import paths, program, state
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.library import Library

_PROGRAM = paths.PROGRAM.as_posix()
_STATE = paths.STATE.as_posix()


def _no_program(ctx):
    if program.exists(ctx.root):
        return None
    return [Result("skip", f"no {_PROGRAM} yet", _PROGRAM)]


def _raw_program(ctx):
    try:
        return program.read_json(program.path_for(ctx.root)), None
    except ValidationError as exc:
        return None, [Result("fail", exc.message, _PROGRAM)]


def _library(ctx):
    try:
        return Library.load(ctx.root), None
    except ValidationError as exc:
        return None, [Result("fail", f"cannot read the exercise library ({exc.message}); see library_valid",
                             paths.EXERCISES.as_posix())]


@check(id="program_schema", owner="R-17a")
def program_schema(ctx):
    skipped = _no_program(ctx)
    if skipped:
        return skipped
    doc, failed = _raw_program(ctx)
    if failed:
        return failed
    return [Result("fail", f"{error.path}: {error.message}", _PROGRAM)
            for kind, error in program.problems(doc, ctx.config) if kind == program.SCHEMA_PROBLEM]


@check(id="program_exercise_ids", owner="R-17a")
def program_exercise_ids(ctx):
    skipped = _no_program(ctx)
    if skipped:
        return skipped
    doc, failed = _raw_program(ctx)
    if failed:
        return failed
    library, failed = _library(ctx)
    if failed:
        return failed
    return [Result("fail", f"{error.path}: {error.message}", _PROGRAM)
            for error in program.exercise_id_errors(doc, library)]


@check(id="avoided_in_program", owner="R-17a")
def avoided_in_program(ctx):
    skipped = _no_program(ctx)
    if skipped:
        return skipped
    doc, failed = _raw_program(ctx)
    if failed:
        return failed
    library, failed = _library(ctx)
    if failed:
        return failed
    return [Result("warn", f"active session {session_id} uses {exercise_id}, which the athlete avoids "
                           f"({reason}); swap it or park the session", _PROGRAM)
            for session_id, exercise_id, reason in program.avoided_slots(doc, library)]


@check(id="state_schema", owner="R-17a")
def state_schema(ctx):
    if not state.exists(ctx.root):
        return [Result("skip", f"no {_STATE} yet", _STATE)]
    try:
        doc = state.read_json(state.path_for(ctx.root))
    except ValidationError as exc:
        return [Result("fail", exc.message, _STATE)]
    try:
        program_doc = program.load(ctx.root) if program.exists(ctx.root) else None
    except ValidationError:
        program_doc = None
    return [Result("fail", f"{error.path}: {error.message}", _STATE) for error in state.problems(doc, program_doc)]


@check(id="routine_render_fresh", owner="R-17a")
def routine_render_fresh(ctx):
    skipped = _no_program(ctx)
    if skipped:
        return skipped
    try:
        pages = program.render_all(ctx.root)
    except ValidationError as exc:
        return [Result("fail", f"the routine pages cannot be rendered: {exc.message}", _PROGRAM)]
    existing = program.routine_pages(ctx.root)
    command = f"python3 -m coach {program.RENDER_COMMAND}"
    results = []
    for path, text in sorted(pages.items()):
        if path not in existing:
            results.append(Result("fail", f"{path} is missing; run {command}", path))
        elif existing[path] != text:
            results.append(Result("fail", f"{path} was edited by hand or is out of date; edit {_PROGRAM}, "
                                          f"then run {command}", path))
    for path, text in sorted(existing.items()):
        if path in pages:
            continue
        if program.is_generated(text):
            results.append(Result("fail", f"{path} is a page for a session the program no longer has; run {command}",
                                  path))
        else:
            results.append(Result("fail", f"{path} is not rendered from {_PROGRAM}; move its content into the "
                                          "program or out of routine/", path))
    return results
