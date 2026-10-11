"""Page part discovery: how later items add to the standing pages without editing coach.pages (contract C38).

A part is a module here with `SLOTS` (the slots it fills) and
`contribute(ctx) -> dict[slot, list[Item]] | None`. Parts are pure reads
and run in module-name order. A replace slot has at most one part.
"""

import importlib
import pkgutil
from dataclasses import dataclass

from coach.errors import ValidationError

REPLACE = "replace"
APPEND = "append"
MERGE = "merge"
SLOT_KINDS = {
    "brief.header.phase": REPLACE,
    "brief.lines": APPEND,
    "brief.sessions_footer": APPEND,
    "brief.watch": MERGE,
    "brief.wins": MERGE,
    "brief.if_you_miss": REPLACE,
    "dashboard.status": APPEND,
    "progress.sections": APPEND,
    "progress.bodyweight": REPLACE,
}
DEFAULT_PRIORITY = 50


@dataclass(frozen=True)
class Item:
    """One line (or, in `progress.sections`, one section's markdown); lower priority sorts first."""

    text: str
    priority: int = DEFAULT_PRIORITY


@dataclass(frozen=True)
class PageContext:
    root: object
    as_of: object
    today: object
    overlay: dict
    program: dict
    state: dict


@dataclass(frozen=True)
class Part:
    name: str
    slots: tuple
    contribute: object


def discover():
    """Every page part in module-name order. Raises ValidationError for an unknown slot or a shared replace slot."""
    parts, replacers = [], {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{info.name}")
        slots = tuple(getattr(module, "SLOTS", ()))
        for slot in slots:
            if slot not in SLOT_KINDS:
                raise ValidationError(f"page part {module.__name__} names slot {slot!r}, which does not exist; "
                                      f"the slots are {', '.join(SLOT_KINDS)}")
            if SLOT_KINDS[slot] == REPLACE:
                if slot in replacers:
                    raise ValidationError(f"page parts {replacers[slot]} and {module.__name__} both replace slot "
                                          f"{slot!r}; a replace slot has one part")
                replacers[slot] = module.__name__
        parts.append(Part(module.__name__, slots, module.contribute))
    return parts


def collect(ctx, parts=None):
    """{slot: [Item]} from every part, each slot's items in part order."""
    found = {}
    for part in discover() if parts is None else parts:
        contribution = part.contribute(ctx)
        if not contribution:
            continue
        for slot, items in contribution.items():
            if slot not in part.slots:
                raise ValidationError(f"page part {part.name} fills slot {slot!r}, which it does not declare; "
                                      f"its SLOTS are {', '.join(part.slots) or 'empty'}")
            found.setdefault(slot, []).extend(items)
    return found
