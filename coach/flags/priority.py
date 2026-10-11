"""Flag code raised when a priority lift loses a planned exposure (contract C20, C40)."""

from coach.flags import register

register("priority_exposures_missed", owner="R-30b", severities=("warn",),
         summary="A priority lift missed its planned exposure in a week and no floor dose replaced it.")
