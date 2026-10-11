"""The scheme's own deload, where it has one; the standard deload otherwise."""

from coach.plugins import base

API = 1
KIND = "transform"
NAME = "scheme"
SUMMARY = "Uses each line's progression scheme's own deload, and the standard deload for schemes without one."
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
FLAGS = {}
CITES = ("rn:deloads.8",)


def apply(ctx, proposal):
    if ctx.scheme_deload is not None:
        return ctx.scheme_deload(ctx, proposal)
    return base.standard_deload(proposal, **base.STANDARD_DELOAD)
