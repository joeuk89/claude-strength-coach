"""Flag codes raised by the block ledger: light weeks, fatigue triggers and the deep review (contract C20, C43)."""

from coach.flags import register

OWNER = "R-31"

register("light_week_due", owner=OWNER, severities=("warn",),
         summary="Ceiling reached, or two fatigue triggers with three or more hard weeks; names the reason and "
                 "proposed type.")
register("light_week_skipped", owner=OWNER, severities=("info",),
         summary="Two triggers fired below three hard weeks; light week skipped with the count.")
register("fatigue_watch", owner=OWNER, severities=("info",), summary="One fatigue trigger fired; names it.")
register("deep_review_due", owner=OWNER, severities=("info",), summary="The next check-in is deep; lists the reasons.")
register("effort_below_target", owner=OWNER, severities=("info",),
         summary="A logged line's mean RPE is more than 1.5 under its targets; review the loads.")
register("effort_above_target", owner=OWNER, severities=("info",),
         summary="A logged line's mean RPE is more than 1.5 over its targets; review the loads and recovery.")
register("reps_missed", owner=OWNER, severities=("info",),
         summary="A logged working set fell short of its prescribed reps; names each line and its logged reps.")
