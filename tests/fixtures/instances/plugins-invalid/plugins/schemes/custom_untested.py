"""A synthetic instance scheme that ships without its test file."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "custom_untested"
SUMMARY = "Holds the program's start load."
PARAMS = {"schema": base.EMPTY_SCHEMA, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ()


def propose(ctx):
    return base.Proposal(sets=base.with_load(base.expand(ctx.slot.sets), ctx.slot.start_load),
                         rationale="Start load", derived_from=None, state={})


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
