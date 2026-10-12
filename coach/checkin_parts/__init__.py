"""Card part discovery: how later items change the check-in card without editing coach.checkin (contract C36).

A part is a module here with `FIELDS` (the field ids it owns, possibly
none) and `contribute(ctx) -> Contribution | None`. Parts are pure reads
and run in module-name order. Two parts owning one field id is an error.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field

from coach.errors import ValidationError


@dataclass(frozen=True)
class Field:
    """A field's content; the card gives it its id and number."""

    prefill: str = None
    ask: str = None
    label: str = None


def field_lines(field):
    """A numbered field or question in the message: `n. Label. prefill ask`, or, for a multi-line ask, the
    prefill and each ask line on their own lines under the label."""
    ask_lines = (field["ask"] or "").split("\n")
    if len(ask_lines) == 1:
        body = " ".join(part for part in (field["prefill"], field["ask"]) if part)
        return [f"{field['n']}. {field['label']}. {body}".rstrip()]
    lines = ([field["prefill"]] if field["prefill"] else []) + ask_lines
    return [f"{field['n']}. {field['label']}."] + [f"   {line}" for line in lines]


@dataclass(frozen=True)
class Contribution:
    """What one part adds. A field mapped to None leaves that field out of the card."""

    fields: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    tier_reasons: list = field(default_factory=list)


@dataclass(frozen=True)
class CardContext:
    root: object
    today: object
    window: object
    mode: str
    card: dict


@dataclass(frozen=True)
class Part:
    name: str
    fields: tuple
    contribute: object


def discover():
    """Every card part in module-name order. Raises ValidationError when two own the same field id."""
    parts, owners = [], {}
    for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{info.name}")
        owned = tuple(getattr(module, "FIELDS", ()))
        for field_id in owned:
            if field_id in owners:
                raise ValidationError(
                    f"card parts {owners[field_id]} and {module.__name__} both own field {field_id!r}; "
                    "one field has one owner"
                )
            owners[field_id] = module.__name__
        parts.append(Part(module.__name__, owned, module.contribute))
    return parts
