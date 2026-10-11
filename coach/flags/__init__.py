"""The flag registry: every overlay flag code, its owner and severities (contract C20).

Each module here registers its codes with `register(...)` at import. The
registry imports every module in the package on first use, so adding a
code adds a module and edits nothing here.
"""

import importlib
import pkgutil
import re
from dataclasses import dataclass

from coach.config_tables.coaching import COACH, MODES

SEVERITIES = ("info", "warn", "block")
RUN_PREFIX = "run mode: "
_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
_REGISTRY = {}
_discovered = False


@dataclass(frozen=True)
class FlagCode:
    code: str
    owner: str
    severities: tuple
    summary: str
    structural: bool = False


def register(code, owner, severities, summary, structural=False):
    """Register a flag code. A structural code proposes a change to the program's structure, not a week's loads."""
    if not isinstance(code, str) or not _CODE.fullmatch(code):
        raise ValueError(f"flag code {code!r} must match {_CODE.pattern}")
    severities = tuple(severities)
    if not severities or any(s not in SEVERITIES for s in severities):
        raise ValueError(f"flag code {code!r}: severities must be some of {', '.join(SEVERITIES)}, "
                         f"found {severities!r}")
    if code in _REGISTRY:
        raise ValueError(f"flag code {code!r} is registered twice")
    _REGISTRY[code] = FlagCode(code, owner, severities, summary, bool(structural))
    return _REGISTRY[code]


def _discover():
    global _discovered
    if _discovered:
        return
    _discovered = True
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        importlib.import_module(f"{__name__}.{module_info.name}")


def registry():
    """{code: FlagCode} for every registered code."""
    _discover()
    return _REGISTRY


def is_known(code):
    return code in registry()


def make(code, severity=None, *, session_id=None, exercise_id=None, message):
    """A C10 flag object. Raises ValueError on an unknown code or a severity the code does not allow."""
    entry = registry().get(code)
    if entry is None:
        raise ValueError(f"unknown flag code {code!r}; register it in a coach/flags/ module first")
    if severity is None:
        severity = entry.severities[0]
    if severity not in entry.severities:
        raise ValueError(f"flag {code!r} takes severity {', '.join(entry.severities)}, not {severity!r}")
    return {"code": code, "severity": severity, "session_id": session_id, "exercise_id": exercise_id,
            "message": message, "resolved": False, "resolution": None}


def for_mode(flags, mode):
    """The flags as `mode` presents them: in run mode a structural flag below `block` shows at info, prefixed.

    Returns new flag objects; stored flags keep their own severity (C44).
    """
    if mode not in MODES:
        raise ValueError(f"coaching mode must be one of {', '.join(MODES)}, not {mode!r}")
    if mode == COACH:
        return list(flags)
    known = registry()
    shown = []
    for flag in flags:
        entry = known.get(flag["code"])
        if entry is None or not entry.structural or flag["severity"] == "block":
            shown.append(flag)
            continue
        message = flag["message"]
        if not message.startswith(RUN_PREFIX):
            message = RUN_PREFIX + message
        shown.append(dict(flag, severity="info", message=message))
    return shown
