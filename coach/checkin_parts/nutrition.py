"""The food questions on the card, from `nutrition status` when nutrition is on (contract C36, C35).

A soft dependency: with no `coach.nutrition` module, or nutrition off, the
card keeps its builtin field, one morning scale weight. Nothing here
computes from nutrition data.
"""

import importlib
import string
from datetime import timedelta

from coach import render
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


def _coverage(ctx, days):
    """A catch-up's readings are the latest `days` days only; the gap before them stays unmeasured."""
    start = ctx.today - timedelta(days=days - 1)
    return (f"Readings for the last {days} days ({render.day_label(start)} – {render.day_label(ctx.today)}) only, "
            f"not the whole gap since {render.day_label(ctx.window.start)}.")


def contribute(ctx):
    module = _module()
    if module is None:
        return None
    status = module.status(ctx.root, ctx.today)
    if not status.get("enabled"):
        return None
    lines, prefills = [], []
    if ctx.mode == "catch_up":
        prefills.append(_coverage(ctx, module.FULL_WEEK))
    if status.get("plan"):
        prefills.append(f"Meal plan: {status['plan']}.")
    for letter, item in zip(string.ascii_lowercase, status.get("questions") or []):
        prefill, ask = _question(item)
        if prefill:
            prefills.append(prefill)
        lines.append(f"{letter}. {ask}")
    food = Field(prefill=" ".join(prefills) or None, ask="\n".join(lines) or None, label="Food")
    return Contribution(fields={"nutrition": food, "meal_plan": None})
