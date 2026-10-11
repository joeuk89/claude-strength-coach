"""The [activity] table and one [sources.<name>] table per synced activity adapter (contract C32)."""

from coach.activity import adapters
from coach.config import Key, Table

DEFAULT_PRECEDENCE = ["manual", "apple_health", "hevy_conditioning"]


def _source_names(value):
    bad = [name for name in value if not adapters.NAME_PATTERN.fullmatch(name)]
    if bad:
        return f"must hold source names (lowercase letters and underscores), found \"{bad[0]}\""
    return None


ACTIVITY = Table(
    keys={
        "enabled": Key("boolean", default=False),
        "wellness_in_git": Key("boolean", default=False),
        "dedup_window_minutes": Key("integer", default=15, minimum=0),
        "precedence": Key("list", default=DEFAULT_PRECEDENCE, item="string", distinct=True, check=_source_names),
        "gap_warn_days": Key("integer", default=3, minimum=1),
    }
)

SOURCES = Table(
    tables={name: Table(keys=dict(module.CONFIG))
            for name, module in adapters.discover().items() if adapters.is_source(module)}
)

TABLES = {"activity": ACTIVITY, "sources": SOURCES}


def _precedence_lists_enabled_sources(config):
    activity = config.get("activity")
    if not activity or not activity.get("enabled"):
        return []
    precedence = activity.get("precedence", [])
    wanted = ["manual", *adapters.enabled_sources(config)]
    missing = [name for name in wanted if name not in precedence]
    if not missing:
        return []
    names = ", ".join(f'"{name}"' for name in missing)
    return [("activity.precedence",
             f'[activity] precedence must list "manual" and every enabled source once; add {names}')]


RULES = [_precedence_lists_enabled_sources]
