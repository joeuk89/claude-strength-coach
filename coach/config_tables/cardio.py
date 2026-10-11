"""`[cardio]`: who owns the cardio plan, the caps and the cardio flag thresholds (contract C48).

Ranges that only make sense together (a spike ratio above 1, nights out
of 7) are the `cardio_config` check's, so a bad value shows in `coach
check` next to the key's other problems.
"""

from coach.config import Key, Table

TIERS = ("count", "review", "program")
DISTANCE_UNITS = ("km", "mi")
CAP_KEYS = ("weekly_run_distance", "weekly_run_minutes", "single_run_distance", "single_run_minutes",
            "weekly_quality")

CARDIO = Table(
    keys={
        "tier": Key("string", default="count", choices=TIERS),
        "distance_unit": Key("string", default="km", choices=DISTANCE_UNITS),
        "weekly_run_distance": Key("number", default=0),
        "weekly_run_minutes": Key("number", default=0),
        "single_run_distance": Key("number", default=0),
        "single_run_minutes": Key("number", default=0),
        "weekly_quality": Key("integer", default=2),
        "spike_ratio": Key("number", default=1.10),
        "spike_lookback_days": Key("integer", default=30),
        "spike_min_history_days": Key("integer", default=14),
        "sleep_short_hours": Key("number", default=7.0),
        "sleep_debt_nights": Key("integer", default=4),
        "sleep_min_nights": Key("integer", default=4),
        "reconcile_move_days": Key("integer", default=3),
        "quality_rpe_min": Key("number", default=7),
        "external_session_minutes": Key("number", default=60),
        "external_session_rpe": Key("number", default=6),
    }
)

TABLES = {"cardio": CARDIO}
