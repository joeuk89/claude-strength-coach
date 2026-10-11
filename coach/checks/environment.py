"""Checks that the scripts can run here at all: Python version and config."""

import sys

from coach import paths
from coach.checks import Result, check
from coach.errors import ConfigError

FLOOR = (3, 11)


@check(id="python_floor", owner="R-10")
def python_floor(ctx):
    found = ".".join(str(part) for part in sys.version_info[:3])
    if tuple(sys.version_info[:2]) < FLOOR:
        return [Result("fail", f"Python {found} is older than 3.11; the coach scripts need 3.11 or newer.")]
    return [Result("pass", f"Python {found} meets the 3.11 floor.")]


@check(id="config", owner="R-10")
def config(ctx):
    try:
        ctx.config
    except ConfigError as exc:
        return [Result("fail", exc.message, str(paths.CONFIG))]
    return [Result("pass", "config.toml is valid.", str(paths.CONFIG))]
