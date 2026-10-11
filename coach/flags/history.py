"""Flag codes raised from the workout history (contract C18, C20)."""

from coach.flags import register

register("convention_slip", owner="R-20", severities=("warn",),
         summary="Dumbbell exposure jumped exactly 2× or ½× at the same reps and RPE; excluded from e1RM and "
                 "progression until annotated.")
register("duration_over_cap", owner="R-20", severities=("info",),
         summary="A logged workout ran longer than its session cap.")
