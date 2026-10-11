"""Conditioning session flag codes (contract C20, C51)."""

from coach.flags import register

register("conditioning_dropped", owner="R-44b", severities=("info", "warn"),
         summary="An optional conditioning session was dropped from the proposal (info), or a core one would have "
                 "been (warn).")
