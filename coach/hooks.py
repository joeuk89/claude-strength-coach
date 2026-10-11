"""The SessionStart and PostToolUse hooks (contract C53).

`sessionstart` puts the `coach status` lines in the coach's context at the
start of a session. `posttooluse` runs the checks for a data file the coach
just wrote or edited by hand, and feeds a failure back. Both read local
files only, never write, and never raise.
"""

import io
import os
import traceback
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from coach import checks, status
from coach.context import Context

DETAIL = "Detail: python3 -m coach status"
MAX_LINES = 12
MAX_CHARS = 1000
FIX = "Fix the data file or re-render; don't leave it."
MAX_REPORTED = 5

_PROGRAM_CHECKS = ("program_schema", "program_exercise_ids", "avoided_in_program", "state_schema",
                   "routine_render_fresh")
_ACTIVITY_CHECKS = ("activity_records_valid", "activity_wellness_location")
_RESEARCH_CHECKS = ("research_notes", "research_render_fresh")

PATH_MAP = (
    ("config.toml", ("config",)),
    ("profile.md", ("bare_hevy_values", "research_citations")),
    ("data/exercises.json", ("library_valid", "load_modes_confirmed")),
    ("data/program.json", _PROGRAM_CHECKS),
    ("data/state.json", _PROGRAM_CHECKS),
    ("routine/*.md", ("routine_render_fresh",)),
    ("data/overlays/*.json", ("overlay_schema", "overlay_arithmetic", "overlay_render_fresh", "load_caps",
                              "dangling_exercise_ids")),
    ("data/hevy/writes.jsonl", ("schema_versions",)),
    ("check-ins/*.md", ("overlay_render_fresh", "bare_hevy_values", "research_citations")),
    ("data/activity/activities.jsonl", _ACTIVITY_CHECKS),
    ("data/activity/planned.jsonl", _ACTIVITY_CHECKS),
    ("data/activity/sync.json", _ACTIVITY_CHECKS),
    ("data/activity/wellness.jsonl", _ACTIVITY_CHECKS),
    (".coach/activity/wellness.jsonl", _ACTIVITY_CHECKS),
    ("data/nutrition/readings.json", ("nutrition_readings",)),
    ("data/nutrition/plans/*.json", ("meal_plans", "meal_plan_render_fresh")),
    ("nutrition/plans/*.md", ("meal_plan_render_fresh",)),
    ("nutrition/menu/index.md", ("recipe_index_fresh",)),
    ("nutrition/menu/*.md", ("recipe_cards", "recipe_render_fresh", "recipe_index_fresh")),
    ("research/local/*.md", _RESEARCH_CHECKS + ("research_citations",)),
    ("research/*.md", _RESEARCH_CHECKS),
)


def checks_for(relative):
    """The check ids for an instance-relative path (first matching row), or () when unmapped."""
    parts = PurePosixPath(relative).parts
    for pattern, ids in PATH_MAP:
        pattern_parts = PurePosixPath(pattern).parts
        if len(parts) == len(pattern_parts) and all(map(fnmatchcase, parts, pattern_parts)):
            return ids
    return ()


def unavailable_text(reason):
    return f"Coach status unavailable: the coach scripts failed ({reason}). Run python3 -m coach status to see why."


def session_response(text):
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def sessionstart(hook_input, root=None, env=None, stderr=None):
    """The SessionStart response: the status lines, attention first; None in the template repo."""
    env = os.environ if env is None else env
    stderr = io.StringIO() if stderr is None else stderr
    try:
        root = Path(root or os.getcwd())
        if status.instance_kind(root) == status.TEMPLATE:
            return None
        today = Context(root, env, stderr).today()
        sections = status.collect(root, today, env=env, stderr=stderr)
        return session_response(context_text(sections, today))
    except Exception as exc:
        _log(stderr, traceback.format_exc())
        return session_response(unavailable_text(f"{type(exc).__name__}: {exc}"))


def context_text(sections, today):
    ordered = sorted(sections, key=lambda s: s.level != "attention")
    body = [line for section in ordered for line in section.lines]
    head = f"Coach status for {today.isoformat()} (items needing attention first):"
    room = MAX_LINES - 2
    kept = body if len(body) <= room else body[:room - 1]
    while kept and len("\n".join([head, *kept, DETAIL])) > MAX_CHARS:
        kept = kept[:-1]
    dropped = len(body) - len(kept)
    if dropped:
        kept.append(f"...and {dropped} more line{'s' if dropped != 1 else ''}.")
    return "\n".join([head, *kept, DETAIL])


def posttooluse(hook_input, root=None, env=None, stderr=None):
    """The PostToolUse response for a hand edit of a mapped data file, or None."""
    env = os.environ if env is None else env
    stderr = io.StringIO() if stderr is None else stderr
    try:
        root = Path(root or os.getcwd())
        relative = _relative(hook_input, root)
        ids = checks_for(relative) if relative else ()
        if not ids:
            return None
        registered = {item.id: item for item in checks.discover()}
        rows, _ = checks.run(Context(root, env, stderr), [registered[check_id] for check_id in ids])
        failed = [row for row in rows if row["status"] == "fail"]
        if failed:
            return {"decision": "block", "reason": _reason(relative, "failed", failed)}
        warned = [row for row in rows if row["status"] == "warn"]
        if warned:
            return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                           "additionalContext": _reason(relative, "has a warning from", warned)}}
        return None
    except Exception as exc:
        _log(stderr, f"the PostToolUse hook failed ({type(exc).__name__}: {exc})")
        return None


def _relative(hook_input, root):
    tool_input = hook_input.get("tool_input") if isinstance(hook_input, dict) else None
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(hook_input.get("cwd") or root) / path
    try:
        return Path(os.path.realpath(path)).relative_to(os.path.realpath(root)).as_posix()
    except ValueError:
        return None


def _reason(relative, verb, rows):
    shown = [f"{row['id']}: {row['message'].rstrip('.')}" for row in rows[:MAX_REPORTED]]
    if len(rows) > MAX_REPORTED:
        shown.append(f"and {len(rows) - MAX_REPORTED} more (python3 -m coach check)")
    return f"{relative} {verb} {'; '.join(shown)}. {FIX}"


def _log(stderr, message):
    for line in str(message).rstrip().splitlines():
        stderr.write(f"coach: {line}\n")
