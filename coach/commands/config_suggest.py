from coach import onboarding
from coach.commands import arg, command


@command(
    "config suggest",
    help="Suggested [athlete] and [equipment] values for a new config.toml, and what to confirm; reads no config",
    args=(
        arg("--unit", required=True, choices=onboarding.UNITS, help="the athlete's units for loads"),
        arg("--gym", choices=onboarding.GYMS, default="commercial", help="the main place they train "
                                                                          "(default commercial)"),
    ),
)
def suggest(args, ctx):
    return onboarding.suggest(args.unit, args.gym)
