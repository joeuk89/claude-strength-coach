"""`[sessions]`: per-session time caps (contract C19)."""

from coach.config import Key, Table

SESSIONS = Table(
    tables={"cap_minutes": Table(free=Key("integer", minimum=0), key_pattern=r"^[a-z0-9-]+$")},
)

TABLES = {"sessions": SESSIONS}


def cap_minutes(config, session_id):
    """The session's time cap in minutes, or None for no cap (0 in config)."""
    caps = config["sessions"]["cap_minutes"]
    minutes = caps.get(session_id) if session_id else None
    if minutes is None:
        minutes = config["athlete"]["session_minutes"]
    return minutes or None
