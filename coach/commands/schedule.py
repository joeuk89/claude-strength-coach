from datetime import timedelta

from coach import dates, jsonio, plugins, propose
from coach import state as state_module
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError


@command("schedule plan", help="The dated sessions the program's schedule rule plans for a week, and its rotation",
         args=(arg("--week", metavar="W", help="week label or any date in it; default: the week holding tomorrow"),))
def plan(args, ctx):
    span = propose.resolve_span(ctx.config, ctx.today(), args.week)
    run = propose.Run(ctx.root, ctx.config, ctx.today(), ctx.now())
    return dict(propose.plan_json(run, span, propose.plan_schedule(run, span)), week=span.label())


@command(
    "schedule confirm",
    help="Record the rotation position the athlete confirmed for a week",
    args=(arg("--position", required=True, metavar="P", help="a position of the schedule rule, e.g. week-b"),
          arg("--week", metavar="W", help="the week it names; default: the week holding tomorrow")),
    writes=True,
)
def confirm(args, ctx):
    run = propose.Run(ctx.root, ctx.config, ctx.today(), ctx.now())
    rule = run.program["schedule"]["rule"]
    plugin = run.registry.get("schedule", rule)
    params, _ = plugins.merged_params(plugin, run.program["schedule"]["params"])
    positions = list(plugin.module.positions(params))
    if not positions:
        raise ValidationError(f"The schedule rule {rule} has no rotation to confirm")
    if args.position not in positions:
        raise ValidationError(f"{args.position} is not a position of {rule}; positions: {', '.join(positions)}")
    try:
        week = dates.parse_week(args.week, ctx.config.athlete.week_starts) if args.week else \
            dates.week_span(ctx.today() + timedelta(days=1), ctx.config.athlete.week_starts)
    except ValueError as exc:
        raise UsageError(f"--week: {exc}") from None
    doc = run.state
    doc["rotation"] = {"position": args.position, "confirmed": True, "confirmed_at": ctx.today().isoformat(),
                       "week": week.start.isoformat()}
    errors = state_module.problems(doc, run.program)
    if errors:
        raise ValidationError("The confirmed state is not valid", details=[e.to_json() for e in errors])
    jsonio.write_doc(state_module.path_for(ctx.root), doc, args.dry_run)
    return {"rotation": doc["rotation"], "week": week.label(), "written": not args.dry_run}
