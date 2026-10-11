"""Command declaration and discovery (contract C2).

Each module here declares its commands with `@command`; the CLI finds them
by scanning the package, so adding a command never edits a shared file.
"""

import importlib
import pkgutil
import re
from dataclasses import dataclass

WRITES_SCOPES = ("cache", "data")
_NAME = re.compile(r"^[a-z][a-z0-9-]*( [a-z][a-z0-9-]*)?$")


@dataclass(frozen=True)
class Command:
    """One command and what it may touch.

    name: "<group> <command>", or one word for a top-level command.
    writes: touches local files. hevy_write: sends a non-GET request to
    Hevy. network: calls Hevy at all. git_write: commits or pushes.
    writes_scope: "cache" when every local write lands under .coach/,
    else "data". envelope: False for a Claude Code hook command, which
    prints the dict it returns (or nothing for None) instead of the
    envelope and exits 0.
    """

    name: str
    func: object
    help: str
    args: tuple = ()
    writes: bool = False
    hevy_write: bool = False
    network: bool = False
    git_write: bool = False
    writes_scope: str = None
    envelope: bool = True

    @property
    def accepts_dry_run(self):
        return self.writes or self.hevy_write or self.git_write

    def metadata(self):
        return {
            "writes": self.writes,
            "hevy_write": self.hevy_write,
            "network": self.network,
            "git_write": self.git_write,
            "writes_scope": self.writes_scope,
        }


def arg(*flags, **kwargs):
    """One argparse argument: arg("--mode", required=True, choices=...)."""
    return flags, kwargs


def command(name, *, help, args=(), writes=False, hevy_write=False, network=False, git_write=False,
            writes_scope=None, envelope=True):
    """Declare a command. The function takes (args, ctx) and returns the envelope's data dict.

    A command that writes (locally, to Hevy or to git) gets --dry-run.
    """
    if not _NAME.fullmatch(name):
        raise ValueError(f"command name {name!r} must be one or two lowercase words")
    if hevy_write and not network:
        raise ValueError(f"command {name!r} writes to Hevy, so it must declare network=True")
    if writes_scope is not None and writes_scope not in WRITES_SCOPES:
        raise ValueError(f"command {name!r}: writes_scope must be one of {', '.join(WRITES_SCOPES)}")
    if writes_scope is not None and not writes:
        raise ValueError(f"command {name!r}: writes_scope needs writes=True")
    if writes and writes_scope is None:
        writes_scope = "data"

    def decorate(func):
        func.coach_command = Command(
            name=name, func=func, help=help, args=tuple(args), writes=writes, hevy_write=hevy_write,
            network=network, git_write=git_write, writes_scope=writes_scope, envelope=envelope,
        )
        return func

    return decorate


def discover():
    found = {}
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        for value in vars(module).values():
            cmd = getattr(value, "coach_command", None)
            if isinstance(cmd, Command):
                if cmd.name in found and found[cmd.name] is not cmd:
                    raise RuntimeError(f"command {cmd.name!r} is declared twice")
                found[cmd.name] = cmd
    return sorted(found.values(), key=lambda c: c.name)
