"""Every well-known instance path, relative to the instance root (contract C6).

Join with the root: `root / paths.OVERLAYS_DIR / f"{overlay_id}.json"`.
"""

from pathlib import PurePosixPath as _P

CONFIG = _P("config.toml")
CONFIG_EXAMPLE = _P("config.example.toml")
ENV_FILE = _P(".env")
PROFILE = _P("profile.md")

DATA_DIR = _P("data")
EXERCISES = DATA_DIR / "exercises.json"
OVERLAYS_DIR = DATA_DIR / "overlays"
HEVY_WRITES = DATA_DIR / "hevy" / "writes.jsonl"
PROGRAM = DATA_DIR / "program.json"
STATE = DATA_DIR / "state.json"
PROGRAM_ARCHIVE_DIR = DATA_DIR / "archive" / "programs"
HISTORY_DIR = DATA_DIR / "history"
ANNOTATIONS = HISTORY_DIR / "annotations.json"
DECISIONS = DATA_DIR / "decisions.json"
FOLLOWUPS = DATA_DIR / "followups.json"
NIGGLES = DATA_DIR / "niggles.json"
BLOCKS = DATA_DIR / "blocks.json"
STATUS_DAYS = DATA_DIR / "status-days.json"
MANUAL_LOG = DATA_DIR / "log" / "workouts.jsonl"
ACTIVITY_DIR = DATA_DIR / "activity"
ACTIVITIES = ACTIVITY_DIR / "activities.jsonl"
PLANNED = ACTIVITY_DIR / "planned.jsonl"
ACTIVITY_SYNC = ACTIVITY_DIR / "sync.json"
ACTIVITY_ASSOCIATIONS = ACTIVITY_DIR / "associations.json"
WELLNESS_COMMITTED = ACTIVITY_DIR / "wellness.jsonl"
NUTRITION_READINGS = DATA_DIR / "nutrition" / "readings.json"
MEAL_PLANS_DATA_DIR = DATA_DIR / "nutrition" / "plans"

ROUTINE_DIR = _P("routine")
ROUTINE_PROGRAM_PAGE = ROUTINE_DIR / "program.md"
CHECKINS_DIR = _P("check-ins")
NUTRITION_DIR = _P("nutrition")
MEAL_PLANS_DIR = NUTRITION_DIR / "plans"
MENU_DIR = NUTRITION_DIR / "menu"
MENU_INDEX = MENU_DIR / "index.md"
NUTRITION_ARCHIVE_DIR = NUTRITION_DIR / "archive"
BRIEF = _P("this-week.md")
PROGRESS = _P("progress.md")
DASHBOARD = _P("README.md")
SESSION_SHEETS = _P("this-week-sheets.md")
RESEARCH_DIR = _P("research")
RESEARCH_LOCAL_DIR = RESEARCH_DIR / "local"
PLUGINS_DIR = _P("plugins")
PLUGIN_TESTS_DIR = PLUGINS_DIR / "tests"

CACHE_ROOT = _P(".coach")
HEVY_CACHE_DIR = CACHE_ROOT / "cache" / "hevy"
WELLNESS_LOCAL = CACHE_ROOT / "activity" / "wellness.jsonl"
BACKUPS_DIR = CACHE_ROOT / "backups"
PROPOSALS_DIR = CACHE_ROOT / "proposals"
PLANS_DIR = CACHE_ROOT / "plans"
DRAFTS_DIR = CACHE_ROOT / "drafts"

CITATION_SCAN_FRAMEWORK = (
    "CLAUDE.md",
    "README.md",
    "config.example.toml",
    ".claude/skills/**/*.md",
    "reference/**/*.md",
    "research/*.md",
    "coach/**/*.py",
    "coach/**/*.json",
)
CITATION_SCAN_INSTANCE = (
    "profile.md",
    "check-ins/**/*.md",
    "data/**/*.json",
    "data/**/*.jsonl",
    "research/local/*.md",
    "plugins/**/*.py",
)
