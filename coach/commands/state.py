from coach import paths, program, propose, state
from coach.commands import arg, command
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


@command(
    "state set-training-max",
    help="Set a wave slot's training max explicitly, with the reason the athlete agreed; preview with --dry-run",
    args=(arg("--session", required=True, metavar="S", help="program session id"),
          arg("--exercise", required=True, metavar="E", help="library exercise id"),
          arg("--value", required=True, type=float, metavar="N",
              help="the new training max (athlete units, per hand for per-hand modes)"),
          arg("--reason", required=True, metavar="TEXT", help="why it changes, as agreed with the athlete")),
    writes=True,
)
def set_training_max(args, ctx):
    return propose.set_training_max(ctx.root, args.session, args.exercise, args.value, args.reason, ctx.now(),
                                    ctx.today(), args.dry_run)
