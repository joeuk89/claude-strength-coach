from coach import stats, units
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError

_MODE = arg("--mode", required=True, choices=units.LOAD_MODES, help="the exercise's load mode")
_UNIT = arg("--unit", choices=units.UNITS, help="athlete units (default: [athlete] units in config.toml)")


def _unit(args, ctx):
    return args.unit or ctx.config.athlete.units


def _load(value, mode, unit):
    if value is None and mode in units.LOADED_MODES:
        raise UsageError(f"--value is required for load mode {mode}")
    try:
        return units.make_load(value, mode, unit)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None


@command(
    "units format",
    help="Build a load object and the text every page prints for it",
    args=(_MODE, arg("--value", type=float, help="per hand for per-hand modes, else the total"), _UNIT,
          arg("--no-hevy", action="store_true", help="leave the Hevy value out, as pages do with Hevy off")),
)
def units_format(args, ctx):
    load = _load(args.value, args.mode, _unit(args, ctx))
    return {"text": units.format_load(load, show_hevy=not args.no_hevy) if load else None, "load": load}


@command(
    "units convert",
    help="Convert between the value the athlete sets and Hevy's weight_kg",
    args=(
        _MODE,
        arg("--from-hevy-kg", type=float, help="Hevy's weight_kg, converted to the value the athlete sets"),
        arg("--value", type=float, help="the value the athlete sets, converted to Hevy's weight_kg"),
        _UNIT,
    ),
)
def units_convert(args, ctx):
    if (args.from_hevy_kg is None) == (args.value is None):
        raise UsageError("give exactly one of --from-hevy-kg and --value")
    if args.mode not in units.LOADED_MODES:
        raise UsageError(f"load mode {args.mode} carries no load")
    unit = _unit(args, ctx)
    value = args.value
    if args.from_hevy_kg is not None:
        try:
            value = units.from_hevy_kg(args.from_hevy_kg, args.mode, unit)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
    load = _load(value, args.mode, unit)
    return {"value": units.json_number(value), "hevy_kg": load["hevy_kg"], "load": load}


@command(
    "units round",
    help="Round a value to a whole number of increments",
    args=(
        arg("--value", type=float, required=True),
        arg("--increment", type=float, required=True),
        arg("--direction", choices=units.ROUND_DIRECTIONS, default="nearest"),
    ),
)
def units_round(args, ctx):
    try:
        rounded = units.round_to_increment(args.value, args.increment, args.direction)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None
    return {"value": rounded, "increment": units.json_number(args.increment), "direction": args.direction}


@command(
    "units load-for",
    help="The load an e1RM gives for reps at an RPE: the unrounded model load, and with --increment the load a "
         "grid of that step makes",
    args=(
        arg("--e1rm", type=float, required=True, help="the e1RM, in the exercise's coaching number"),
        arg("--reps", type=int, required=True),
        arg("--rpe", type=float, help="the target RPE (1–10); without it the reps are taken to failure"),
        arg("--increment", type=float, help="an equipment grid step: also report the heaviest load on it no heavier "
                                            "than the model load"),
    ),
)
def units_load_for(args, ctx):
    if args.e1rm <= 0 or args.reps < 1:
        raise ValidationError("--e1rm must be above 0 and --reps at least 1")
    if args.rpe is not None and not 1 <= args.rpe <= 10:
        raise ValidationError("--rpe must be from 1 to 10")
    if args.increment is not None and args.increment <= 0:
        raise ValidationError("--increment must be above 0")
    n = stats.reps_to_failure(args.reps, args.rpe)
    model = {"e1rm": units.json_number(args.e1rm), "reps": args.reps,
             "rpe": units.json_number(args.rpe) if args.rpe is not None else None,
             "reps_to_failure": units.json_number(n), "load": None,
             "calculation": "Epley inverse, e1RM ÷ (1 + reps to failure ÷ 30), to 2 decimals and not rounded to "
                            "any equipment", "reason": None}
    if n > stats.MAX_REPS_TO_FAILURE:
        model["reason"] = (f"{units.json_number(n)} reps to failure is past the model's {stats.MAX_REPS_TO_FAILURE}, "
                           "so it gives no load")
        return {"model": model, "equipment": None}
    model["load"] = units.json_number(round(stats.load_for(args.e1rm, args.reps, args.rpe), 2))
    equipment = None
    if args.increment is not None:
        equipment = {"increment": units.json_number(args.increment), "direction": "down",
                     "load": units.round_to_increment(model["load"], args.increment, "down"),
                     "rounding": "the heaviest load on this grid no heavier than the model load, so the set is "
                                 "no harder than its RPE"}
    return {"model": model, "equipment": equipment}
