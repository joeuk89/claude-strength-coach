"""The food questions on the card, from `nutrition status` when nutrition is on (contract C36, C35).

A soft dependency: with no `coach.nutrition` module, or nutrition off, the
card keeps R-01's nutrition and meal-plan fields. Nothing here computes
from nutrition data.
"""

import importlib
import string

from coach.checkin_parts import Contribution, Field

FIELDS = ("nutrition", "meal_plan")


def _module():
    try:
        return importlib.import_module("coach.nutrition")
    except ImportError:
        return None


def _question(item):
    if isinstance(item, dict):
        return item.get("prefill"), item.get("ask")
    return None, item


def contribute(ctx):
    module = _module()
    if module is None:
        return None
    status = module.status(ctx.root, ctx.today)
    if not status.get("enabled"):
        return None
    lines, prefills = [], []
    for letter, item in zip(string.ascii_lowercase, status.get("questions") or []):
        prefill, ask = _question(item)
        if prefill:
            prefills.append(prefill)
        lines.append(f"{letter}. {ask}")
    next_week = getattr(module, "QUESTION_NEXT_WEEK", None)
    nudge = [_question(item)[1] for item in status.get("questions") or [] if _question(item)[1] == next_week]
    food = Field(prefill=" ".join(prefills) or None, ask="\n".join(lines) or None, label="Food")
    return Contribution(fields={"nutrition": food, "meal_plan": None}, nudge_lines=nudge)
