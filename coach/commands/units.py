from coach import units
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
