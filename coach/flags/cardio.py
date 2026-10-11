"""Cardio flag codes: caps, run spikes, stacked quality days, sleep debt, status days, niggles (contract C20, C49)."""

from coach.flags import register

OWNER = "R-43"

register("cap_breach", owner=OWNER, severities=("warn",),
         summary="A weekly run, single-run or weekly-quality cap is exceeded, logged or planned.")
register("run_volume_spike", owner=OWNER, severities=("warn", "info"),
         summary="A run is more than spike_ratio × the longest run in the lookback (warn logged, info planned).")
register("quality_stack", owner=OWNER, severities=("warn",),
         summary="Two quality activities on the same or consecutive days.")
register("collision", owner=OWNER, severities=("warn", "info"),
         summary="An interference rule is broken (C51); R-44a emits it.")
register("sleep_debt", owner=OWNER, severities=("warn",),
         summary="Most nights of the last seven were short.")
register("status_active", owner=OWNER, severities=("warn", "info"),
         summary="A status day overlaps the span (warn ill/injured, info travel).")
register("niggle_link", owner=OWNER, severities=("warn",),
         summary="Activity of a kind an active niggle applies to.")
