"""The cardio provider: caps, run spikes, stacked quality days, sleep debt, status days, niggles (contract C49)."""

from coach import cardio

NAME = "cardio"


def flags(ctx):
    return cardio.evaluate(ctx)["flags"]
