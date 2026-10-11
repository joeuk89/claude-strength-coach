from coach import paths, program, state
from coach.commands import command
from coach.errors import ValidationError


def _program_or_none(ctx):
    if not program.exists(ctx.root):
        return None
    try:
        return program.load(ctx.root)
    except ValidationError as exc:
        ctx.warn(f"state ids were not checked against the program: {exc.message}")
        return None


@command("state show", help="Show data/state.json after checking it against the schema and the program")
def show(args, ctx):
    doc = state.read_json(state.path_for(ctx.root))
    errors = state.problems(doc, _program_or_none(ctx))
    if errors:
        raise ValidationError(f"{paths.STATE} is not valid ({len(errors)} problem(s))",
                              details=[error.to_json() for error in errors])
    return {"path": paths.STATE.as_posix(), "state": doc}
