"""Flag codes raised by structure accounting: adherence, dose targets and per-session dose (contract C20, C41)."""

from coach.flags import register

OWNER = "R-30a"

register("adherence_low", owner=OWNER, severities=("warn",),
         summary="Trailing four ordinary weeks below 70 % of planned core and coach-led sessions.")
register("add_session_type_blocked", owner=OWNER, severities=("warn",), structural=True,
         summary="Adherence below 80 %: no new recurring session without a recorded override.")
register("restructure_required", owner=OWNER, severities=("warn",), structural=True,
         summary="Adherence below 70 % and no decision in effect: the check-in presents a smaller schedule.")
register("volume_undershoot", owner=OWNER, severities=("warn",), structural=True,
         summary="A muscle below its dose target, planned on core plus coach-led, or delivered in three of four "
                 "ordinary weeks.")
register("session_volume_high", owner=OWNER, severities=("warn", "info"), structural=True,
         summary="More than 11 fractional sets for one muscle in one session (warn planned, info logged) "
                 "(rn:volume-frequency.3).")
