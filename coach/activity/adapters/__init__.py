"""Activity-source adapters (contract C31), found by scanning this package.

Each module defines NAME, KINDS (the files it writes: "activity",
"wellness", "planned"), NETWORK, `fetch(ctx, sync_state) -> FetchResult`
and `normalise(item, ctx) -> list[dict]`. A module that is a synced source
also defines CONFIG, the keys of its `[sources.<NAME>]` table; `manual`
has no table and is never synced. Optional: `is_enabled(config)` when the
source needs more than its own switch, and `FRESH_BY = "sync"` when its
freshness is the last sync rather than the newest record it wrote;
`fetch_file(ctx, path, sync_state) -> FetchResult` when the source can
import one file (`activity import`); `anonymise(ctx, path, out_dir,
dry_run) -> dict` when it can turn a real export into a fixture
(`activity anonymise`).
"""

import importlib
import pkgutil
import re
from dataclasses import dataclass, field

FILE_KINDS = ("activity", "wellness", "planned")
NAME_PATTERN = re.compile(r"^[a-z_]+$")


@dataclass
class FetchResult:
    items: list
    sync_state: dict
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)


class Drop(Exception):
    """Raised by `normalise` for an item that is not a record; sync counts drops by reason."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def discover():
    """{NAME: module} for every adapter in the package."""
    found = {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{info.name}")
        name = getattr(module, "NAME", None)
        if name is None:
            continue
        if not NAME_PATTERN.fullmatch(name):
            raise RuntimeError(f"activity adapter {info.name}: NAME {name!r} must match {NAME_PATTERN.pattern}")
        unknown = set(module.KINDS) - set(FILE_KINDS)
        if unknown:
            raise RuntimeError(f"activity adapter {name}: unknown KINDS {sorted(unknown)}")
        if name in found:
            raise RuntimeError(f"activity adapter {name!r} is declared twice")
        found[name] = module
    return found


def is_source(module):
    return hasattr(module, "CONFIG")


def is_enabled(module, config):
    if not is_source(module):
        return True
    custom = getattr(module, "is_enabled", None)
    if custom is not None:
        return bool(custom(config))
    return bool(config.get("sources", {}).get(module.NAME, {}).get("enabled"))


def enabled_sources(config):
    """{NAME: module} for every synced source that config turns on."""
    return {name: module for name, module in discover().items() if is_source(module) and is_enabled(module, config)}
