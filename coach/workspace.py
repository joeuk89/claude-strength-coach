"""Local repository identity, independent of bundled framework content."""

import re
import subprocess
from pathlib import Path


def _git(root, *args):
    try:
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def is_template(root):
    root = Path(root)
    if not (root / ".git").exists():
        return False
    identity = _git(root, "config", "--local", "--get", "coach.workspace")
    if identity:
        return identity == "template"
    origin = _git(root, "remote", "get-url", "origin")
    return re.fullmatch(
        r"(?:https?://github\.com/|ssh://git@github\.com/|git@github\.com:)"
        r"joeuk89/claude-strength-coach(?:\.git)?/?", origin, re.IGNORECASE
    ) is not None
