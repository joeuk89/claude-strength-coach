"""The training-record commit plan of a programming pass's close-out (C38).

The brief names the training records the athlete's "go" commits: those
already changed and those its approved write steps will write. `pages
publish --include` then commits exactly those files with the pages.
The allowlist decides eligibility only: each record is named as a file,
never staged as a directory or pattern.
"""

import subprocess
from pathlib import Path, PurePosixPath

from coach import paths, program
from coach.errors import RefusedError, UsageError

ELIGIBLE_FILES = tuple(p.as_posix() for p in (paths.STATE, paths.DECISIONS, paths.BLOCKS))
ELIGIBLE_DIRS = tuple(p.as_posix() for p in (paths.MANUAL_LOG.parent, paths.HISTORY_DIR, paths.ROUTINE_DIR))
STRUCTURAL = paths.PROGRAM.as_posix()
STATUS_SCOPE = (paths.DATA_DIR.as_posix(), paths.ROUTINE_DIR.as_posix())
ELIGIBLE_TEXT = ", ".join((*ELIGIBLE_FILES, *(f"{d}/" for d in ELIGIBLE_DIRS), f"{STRUCTURAL} (--structural)"))
STEP_WRITES = {
    "light_week": (paths.DECISIONS, paths.STATE, paths.ROUTINE_PROGRAM_PAGE),
    "one_off": (paths.STATE,),
    "create_routines": (paths.STATE,),
    "missed": (paths.ANNOTATIONS,),
}


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


def git(root, *argv, env=None):
    """Run git in `root`; pathspecs are literal, so a path never matches as a pattern."""
    return subprocess.run(["git", "-C", str(root), "--literal-pathspecs", *argv], capture_output=True, text=True,
                          env=env, timeout=120)


def changes(root, env=None):
    """{path: "added" | "modified" | "deleted"} for every uncommitted change under data/ and routine/.

    A rename counts as its two halves, so the deleted source is never committed unnamed.
    """
    out = git(root, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all", "--",
              *STATUS_SCOPE, env=env).stdout
    found = {}
    for entry in out.split("\0"):
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if "D" in code:
            found[path] = "deleted"
        elif code == "??" or "A" in code:
            found[path] = "added"
        else:
            found[path] = "modified"
    return found


def planned(structural=False, sessions=(), steps=()):
    """The records the approved write steps will write, whether or not they have changed yet."""
    if sessions and not structural:
        raise UsageError("--session names a session page a structural change edits, adds or removes; "
                         "add --structural")
    found = {p.as_posix() for step in steps for p in STEP_WRITES[step]}
    if structural:
        found |= {STRUCTURAL, paths.ROUTINE_PROGRAM_PAGE.as_posix()}
    for session_id in sessions:
        page = normalise(program.page_path(session_id))
        if page is None or not eligible(page):
            raise UsageError(f"--session {session_id!r} is not a session id")
        found.add(page)
    return sorted(found)


def plan(root, structural=False, sessions=(), steps=(), env=None):
    """The training records the brief names for the athlete's approval: changed now, or written by an approved step.

    A record not yet changed shows as "planned".
    """
    changed = changes(root, env)
    will_write = planned(structural, sessions, steps)
    rows = {path: change for path, change in changed.items() if eligible(path, structural)}
    rows.update({path: "planned" for path in will_write if path not in rows})
    records = [{"path": path, "change": change} for path, change in sorted(rows.items())]
    return {"records": records, "include": [row["path"] for row in records], "planned": will_write,
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
