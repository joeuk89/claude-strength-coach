"""The check registry behind `coach check` (contract C13).

Each module here declares checks with `@check(id=..., owner=...)`. A check
takes a Context and returns a list of Result.
"""

import importlib
import pkgutil
import re
import traceback
from dataclasses import dataclass

from coach.errors import ConfigError

STATUSES = ("pass", "warn", "fail", "skip")
_ID = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class Result:
    status: str
    message: str
    path: str = None

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"check status must be one of {', '.join(STATUSES)}, found {self.status!r}")


@dataclass(frozen=True)
class Check:
    id: str
    owner: str
    func: object


def check(id, owner):
    if not _ID.fullmatch(id):
        raise ValueError(f"check id {id!r} must match {_ID.pattern}")

    def decorate(func):
        func.coach_check = Check(id=id, owner=owner, func=func)
        return func

    return decorate


def discover():
    found = {}
    for module_info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        for value in vars(module).values():
            item = getattr(value, "coach_check", None)
            if isinstance(item, Check):
                if item.id in found and found[item.id] is not item:
                    raise RuntimeError(f"check {item.id!r} is declared twice")
                found[item.id] = item
    return [found[key] for key in sorted(found)]


def _run_one(item, ctx):
    try:
        results = list(item.func(ctx))
    except ConfigError as exc:
        return [Result("skip", f"needs a valid config.toml: {exc.message}", "config.toml")]
    except Exception as exc:
        ctx.log(traceback.format_exc().rstrip())
        return [Result("fail", f"the check crashed ({type(exc).__name__}: {exc})")]
    return results or [Result("pass", "no problems found")]


def run(ctx, checks):
    """Run `checks`; return (rows, summary) in the `coach check` output shape."""
    rows = []
    for item in checks:
        for result in _run_one(item, ctx):
            rows.append({"id": item.id, "owner": item.owner, "status": result.status,
                         "message": result.message, "path": result.path})
    summary = {status: sum(1 for row in rows if row["status"] == status) for status in STATUSES}
    return rows, summary
