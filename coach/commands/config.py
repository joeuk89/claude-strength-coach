from coach import config as config_module
from coach.commands import arg, command


@command(
    "config show",
    help="Print the validated config, defaults filled in",
    args=(arg("--location", help="also print the equipment at this [equipment.locations] place"),),
)
def show(args, ctx):
    cfg = ctx.config
    data = {"path": cfg.path, "config": cfg,
            "age": config_module.approximate_age(cfg, ctx.today())}
    if args.location:
        data["location"] = args.location
        data["equipment"] = config_module.equipment_for(cfg, args.location)
    return data


@command("config validate", help="Validate config.toml; exit 5 naming the file and key if it is wrong")
def validate(args, ctx):
    return {"path": ctx.config.path, "valid": True}
