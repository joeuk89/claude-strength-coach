"""The food line and the phase on the brief, from `nutrition status` when nutrition is on (contract C38, C35).

A soft dependency: with no `coach.nutrition` module, or nutrition off, it
adds nothing. Nothing here computes from nutrition data.
"""

import importlib

from coach.page_parts import Item

SLOTS = ("brief.header.phase", "brief.lines")


def status(root, today):
    """`nutrition status` data, or None when the module is absent or nutrition is off."""
    try:
        module = importlib.import_module("coach.nutrition")
    except ImportError:
        return None
    found = module.status(root, today)
    return found if found.get("enabled") else None


def phase_text(phase):
    return phase.replace("_", " ").capitalize() if phase else None


def contribute(ctx):
    found = status(ctx.root, ctx.today)
    if found is None:
        return None
    contribution = {}
    if found.get("brief_line"):
        contribution["brief.lines"] = [Item(found["brief_line"])]
    if found.get("phase"):
        contribution["brief.header.phase"] = [Item(phase_text(found["phase"]))]
    return contribution or None
