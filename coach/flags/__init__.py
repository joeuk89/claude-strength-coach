"""The flag registry: every overlay flag code, its owner and severities (contract C20).

Each module here registers its codes with `register(...)` at import. The
registry imports every module in the package on first use, so adding a
code adds a module and edits nothing here.
"""

import importlib
import pkgutil
import re
from dataclasses import dataclass

SEVERITIES = ("info", "warn", "block")
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
