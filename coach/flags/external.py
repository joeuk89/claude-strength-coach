"""Hevy mapping requirements, kept apart from the local prescription."""

from coach.flags import register

register("hevy_template_unresolved", owner="R-14", severities=("block",),
         summary="A Hevy exercise template must be mapped before approval.")
register("hevy_routine_unmapped", owner="R-14", severities=("info",),
         summary="A session needs an explicit create or reuse action in the write brief.")
