"""Flag codes raised by the proposal pipeline (contract C20, C24)."""

from coach.flags import register

OWNER = "R-23a"

register("no_data", owner=OWNER, severities=("warn",),
         summary="No usable exposure and no start load; load left empty for the coach.")
register("stalled", owner=OWNER, severities=("warn",),
         summary="No load or rep gain over three exposures running.")
register("rpe_drift", owner=OWNER, severities=("warn",),
         summary="Compound or recovery-capped exercise: logged RPE at least 1 over target on two or more working "
                 "sets of the last exposure (R-05).")
register("return_week", owner=OWNER, severities=("info",),
         summary="Decay applied; names the band and days off.")
register("return_after_illness", owner=OWNER, severities=("warn",),
         summary="An ill miss or status day in the gap: confirm 48 hours symptom-free; first session capped at "
                 "RPE 7 (R-02).")
register("constraint_applied", owner=OWNER, severities=("info",),
         summary="A cap, a slot constraint or a niggle constraint changed the proposal.")
register("override_standing", owner=OWNER, severities=("info",),
         summary="A standing override was applied again instead of the scheme's proposal.")
register("scheme_reset", owner=OWNER, severities=("warn",),
         summary="A slot's scheme changed; its state restarted.")
register("rotation_unconfirmed", owner=OWNER, severities=("warn",),
         summary="The schedule rule advanced the rotation without confirmation.")
