"""Flag codes raised by the prescription checks (contract C20, C22)."""

from coach import validity
from coach.flags import register

register("stale_prescription", owner="R-24", severities=("block",),
         summary="Line derived from an exposure outside the validity window and not decayed to its band, or above "
                 f"the RPE {validity.ILLNESS_RPE_CAP} cap on the first session after an illness.")
register("unearned_load", owner="R-24", severities=("block",),
         summary="Load predicted beyond failure at every rep target the line allows, or, with no e1RM from "
                 "RPE-rated sets, more than two increments above the last exposure.")
register("load_cap", owner="R-24", severities=("block",),
         summary="Load above [caps] or dumbbell_max.")
register("load_unrepresentable", owner="R-24", severities=("block",),
         summary="Load cannot be built from the available increments, dumbbells, kettlebells or plates.")
register("load_mode_mismatch", owner="R-24", severities=("block",),
         summary="Line's load mode or load arithmetic disagrees with the library or C5.")
register("load_mode_unconfirmed", owner="R-24", severities=("block",),
         summary="Line's exercise has no confirmed load mode in the library; only confirming it clears the flag.")
register("rpe_infeasible", owner="R-24", severities=("warn",),
         summary="RPE target more than 1 away from the implied RPE at every rep target the line allows, or a "
                 "recovery RPE ceiling more than 1 below it.")
register("session_over_cap", owner="R-24", severities=("warn",),
         summary="Estimated session duration above its cap.")

register("load_geometry_unknown", owner="R-24", severities=("warn",),
         summary="Physical load feasibility is unknown because the equipment base mass is not configured.")
