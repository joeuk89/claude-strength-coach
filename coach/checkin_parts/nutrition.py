"""The food questions on the card, from `nutrition status` when nutrition is on (contract C36, C35).

A soft dependency: with no `coach.nutrition` module, or nutrition off, the
card keeps its builtin field, one morning scale weight. Nothing here
computes from nutrition data.
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
    if status.get("plan"):
        prefills.append(f"Meal plan: {status['plan']}.")
    for letter, item in zip(string.ascii_lowercase, status.get("questions") or []):
        prefill, ask = _question(item)
        if prefill:
            prefills.append(prefill)
        lines.append(f"{letter}. {ask}")
    food = Field(prefill=" ".join(prefills) or None, ask="\n".join(lines) or None, label="Food")
    return Contribution(fields={"nutrition": food, "meal_plan": None})
