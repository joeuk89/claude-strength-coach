"""Flag codes raised by the check-in card (contract C20, C36)."""

from coach.flags import register

register("stale_routine", owner="R-21a", severities=("warn",),
         summary="A routine for an active session does not hold the newest approved overlay's content: "
                 "the last pass did not write and verify it.")
