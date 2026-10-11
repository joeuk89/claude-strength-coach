"""The training-record commit plan of a programming pass's close-out (C38).

The brief names the changed training records the athlete's "go" commits;
`pages publish --include` then commits exactly those files with the pages.
The allowlist decides eligibility only: each record is named as a file,
never staged as a directory or pattern.
"""

import subprocess
from pathlib import Path, PurePosixPath

from coach import paths
from coach.errors import RefusedError

ELIGIBLE_FILES = tuple(p.as_posix() for p in (paths.STATE, paths.DECISIONS, paths.BLOCKS))
ELIGIBLE_DIRS = tuple(p.as_posix() for p in (paths.MANUAL_LOG.parent, paths.HISTORY_DIR, paths.ROUTINE_DIR))
STRUCTURAL = paths.PROGRAM.as_posix()
STATUS_SCOPE = (paths.DATA_DIR.as_posix(), paths.ROUTINE_DIR.as_posix())
ELIGIBLE_TEXT = ", ".join((*ELIGIBLE_FILES, *(f"{d}/" for d in ELIGIBLE_DIRS), f"{STRUCTURAL} (--structural)"))


def eligible(path, structural=False):
    """Is `path` (a normalised posix path) a training record close-out may commit?"""
    if path == STRUCTURAL:
        return structural
    return path in ELIGIBLE_FILES or any(path.startswith(f"{d}/") for d in ELIGIBLE_DIRS)


def normalise(text):
    """`text` as a clean relative posix path, or None when it is absolute, escapes the root or names a directory."""
    if not text or text.startswith("/") or text.endswith("/") or "\\" in text:
        return None
    parts = [part for part in PurePosixPath(text).parts if part != "."]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _git(root, *argv, env=None):
    return subprocess.run(["git", "-C", str(root), "--literal-pathspecs", *argv], capture_output=True, text=True,
                          env=env, timeout=120)


def changes(root, env=None):
    """{path: "added" | "modified" | "deleted"} for every uncommitted change under data/ and routine/."""
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *STATUS_SCOPE, env=env).stdout
    fields = iter(out.split("\0"))
    found = {}
    for entry in fields:
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            next(fields, None)
        if "D" in code:
            found[path] = "deleted"
        elif code == "??" or "A" in code:
            found[path] = "added"
        else:
            found[path] = "modified"
    return found


def plan(root, structural=False, env=None):
    """The changed training records, by path: what the brief names for the athlete's approval."""
    changed = changes(root, env)
    records = [{"path": path, "change": change} for path, change in sorted(changed.items())
               if eligible(path, structural)]
    return {"records": records, "include": [row["path"] for row in records],
            "program_changed": STRUCTURAL in changed, "structural": structural}


def select(root, include, structural=False, env=None):
    """Split the approved paths into changed and unchanged, and list the changed records left out.

    Refuses (exit 3) a path that is not an eligible training record file, before anything is written.
    """
    chosen = []
    for text in include:
        path = normalise(text)
        if path is None or (Path(root) / path).is_dir():
            raise RefusedError(f"--include {text!r} is not one training-record file; name each changed file the "
                               f"brief listed (eligible: {ELIGIBLE_TEXT})")
        if path == STRUCTURAL and not structural:
            raise RefusedError(f"{STRUCTURAL} is committed only with --structural, after the athlete approved the "
                               "structural change and its commit in the brief")
        if not eligible(path, structural):
            raise RefusedError(f"{path} is not a training record that close-out commits (eligible: {ELIGIBLE_TEXT}); "
                               "commit it separately, only when the athlete agrees")
        if path not in chosen:
            chosen.append(path)
    changed = changes(root, env)
    return {
        "included": [{"path": p, "change": changed[p]} for p in sorted(chosen) if p in changed],
        "unchanged": sorted(p for p in chosen if p not in changed),
        "local": [{"path": p, "change": c} for p, c in sorted(changed.items())
                  if p not in chosen and eligible(p, structural=True)],
    }
