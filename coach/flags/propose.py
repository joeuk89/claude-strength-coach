"""Flag codes raised by the proposal pipeline (contract C20, C24)."""

from coach import validity
from coach.flags import register

OWNER = "R-23a"

register("no_data", owner=OWNER, severities=("warn",),
         summary="No usable exposure and no start load; load left empty for the coach.")
register("stalled", owner=OWNER, severities=("warn",),
         summary="No metric or matched-work effort gain over three comparable exposures; a coaching heuristic.")
register("prescription_unknown", owner=OWNER, severities=("warn",),
         summary="Historical prescription unknown; no prescribed hit or miss inferred.")
register("incomplete_exposure", owner=OWNER, severities=("warn",),
         summary="Fewer working sets logged than prescribed and none fell short: progression holds and no miss is "
                 "counted; a coaching heuristic.")
register("linear_below_start", owner=OWNER, severities=("info",),
         summary="Linear reset fell below the starting load; review progression without automatic adjustment.")
register("load_cut_held", owner=OWNER, severities=("info", "warn"),
         summary="A reset, return band or deload load cut that the kit cannot make holds the load: info when the "
                 "line's set or effort cuts still apply, warn when nothing is cut and the coach chooses the load or "
                 "when the kit makes nothing that light and the load rises.")
register("rpe_drift", owner=OWNER, severities=("warn",),
         summary="Compound or recovery-capped exercise: logged RPE at least 1 over target on two or more working "
                 "sets of the last exposure.")
register("range_effort_mismatch", owner=OWNER, severities=("warn",),
         summary="Double progression held a load whose derived-from exposure fell below the program's rep range "
                 "or 2 or more RPE over its target; review the load or the range with the athlete.")
register("return_week", owner=OWNER, severities=("info",),
         summary="Decay applied; names the band and days off.")
register("return_after_illness", owner=OWNER, severities=("warn",),
         summary=f"An ill miss or status day in the gap: confirm {validity.SYMPTOM_FREE_HOURS} hours symptom-free; "
                 f"first session capped at RPE {validity.ILLNESS_RPE_CAP}.")
register("constraint_applied", owner=OWNER, severities=("info",),
         summary="A cap, a slot constraint or a niggle constraint changed the proposal.")
register("override_standing", owner=OWNER, severities=("info",),
         summary="A standing override was applied again instead of the scheme's proposal.")
register("scheme_reset", owner=OWNER, severities=("warn",),
         summary="A slot's scheme changed; its state restarted.")
register("rotation_unconfirmed", owner=OWNER, severities=("warn",),
         summary="The schedule rule advanced the rotation without confirmation.")
