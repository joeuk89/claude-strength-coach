"""Week-level flag providers: rules that judge a whole span, not one line (contract C49).

A provider is a module here with `NAME` and `flags(ctx) -> list[dict]`
returning `coach.flags.make` results. `propose week` and `cardio flags`
run every provider; one that raises fails the command, never skipped.
"""

import importlib
import pkgutil
from dataclasses import dataclass

MODES = ("logged", "proposal")


@dataclass(frozen=True)
class WeekFlagContext:
    """mode "logged": what happened, and what is still planned from today on; "proposal": a draft overlay's week."""

    root: object
    today: object
    span: object
    mode: str
    config: object
    overlay: object
    bouts: tuple


@dataclass(frozen=True)
class Provider:
    name: str
    flags: object


def discover():
    """Every provider in module-name order."""
    found = []
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{info.name}")
        found.append(Provider(getattr(module, "NAME", info.name), module.flags))
    return found


def run(ctx):
    """Every provider's flags for the context, in provider order."""
    return [flag for provider in discover() for flag in provider.flags(ctx)]
