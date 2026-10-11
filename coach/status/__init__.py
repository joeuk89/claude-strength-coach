"""The status provider registry behind `coach status` (contract C52).

Each module here declares providers with `@provider(id=..., owner=...,
order=...)`. A provider takes a Context and returns a Section, or None when
its source is absent. Providers read local files only.
"""

import importlib
import io
import os
import pkgutil
import re
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from coach import paths
from coach.context import Context
from coach.errors import ConfigError

LEVELS = ("info", "attention")
MAX_LINES = 3
TEMPLATE, UNINITIALISED, INSTANCE = "template", "uninitialised", "instance"
_ID = re.compile(r"^[a-z0-9_]+$")


@dataclass
class Section:
    id: str
    lines: list
    data: dict = field(default_factory=dict)
    level: str = "info"

    def __post_init__(self):
        if self.level not in LEVELS:
            raise ValueError(f"section level must be one of {', '.join(LEVELS)}, found {self.level!r}")
        if len(self.lines) > MAX_LINES:
            raise ValueError(f"section {self.id!r} has {len(self.lines)} lines; the most is {MAX_LINES}")

    def to_json(self):
        return {"id": self.id, "level": self.level, "lines": list(self.lines), "data": self.data}


@dataclass(frozen=True)
class Provider:
    id: str
    owner: str
    order: int
    func: object


def provider(id, owner, order):
    if not _ID.fullmatch(id):
        raise ValueError(f"status provider id {id!r} must match {_ID.pattern}")

    def decorate(func):
        func.coach_status_provider = Provider(id=id, owner=owner, order=order, func=func)
        return func

    return decorate


def discover():
    found = {}
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        for value in vars(module).values():
            item = getattr(value, "coach_status_provider", None)
            if isinstance(item, Provider):
                if item.id in found and found[item.id] is not item:
                    raise RuntimeError(f"status provider {item.id!r} is declared twice")
                found[item.id] = item
    return sorted(found.values(), key=lambda p: (p.order, p.id))


def instance_kind(root):
    """`template` (a tests/ directory and no profile.md), `uninitialised` or `instance`."""
    root = Path(root)
    has_profile = (root / paths.PROFILE).is_file()
    if (root / "tests").is_dir() and not has_profile:
        return TEMPLATE
    if not has_profile or not (root / paths.CONFIG).is_file():
        return UNINITIALISED
    return INSTANCE


class StatusContext(Context):
    """A Context whose today() is the day `status` reports on."""

    def __init__(self, root, env, stderr, today):
        super().__init__(root, env, stderr)
        self._today = today

    def today(self):
        return self._today


def unavailable(item, exc):
    return Section(item.id, [f"{item.id}: unavailable ({type(exc).__name__})"],
                   {"error": f"{type(exc).__name__}: {exc}"}, "attention")


def run_one(item, ctx):
    try:
        section = item.func(ctx)
    except ConfigError:
        return None
    except Exception as exc:
        ctx.log(traceback.format_exc().rstrip())
        return unavailable(item, exc)
    if section is not None and section.id != item.id:
        return unavailable(item, ValueError(f"provider returned section {section.id!r}"))
    return section


def collect(root, today, env=None, stderr=None, providers=None):
    """Every provider's section, in order. A provider that raises becomes one `attention` line.

    A provider that raises ConfigError (no config.toml, or an invalid one)
    drops its section: the `instance` and `checks` providers report that.
    """
    env = os.environ if env is None else env
    ctx = StatusContext(root, env, stderr if stderr is not None else io.StringIO(), today)
    sections = []
    for item in discover() if providers is None else providers:
        section = run_one(item, ctx)
        if section is not None:
            sections.append(section)
    return sections
