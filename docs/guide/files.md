# Files and folders

What every file and folder in your workspace is, who writes it, and which
ones git tracks. Read this when you wonder whether a file is yours to
edit, what a script owns, or why `/framework-sync` left something alone.

## The workspace at a glance

```text
my-training/
├── README.md               the dashboard, rendered
├── this-week.md            this week's brief, rendered
├── progress.md             the progress page, rendered
├── this-week-sheets.md     session sheets, rendered; only with Hevy off
├── profile.md              you in words: goals, week, limits, Coach's notes
├── config.toml             settings
├── config.example.toml     the example config the template ships
├── .env                    HEVY_API_KEY; gitignored
├── .env.example            the one-line template for .env
├── CLAUDE.md               the coach's standing instructions and principles
├── CONTEXT.md              the glossary the coach works from
├── .claude/
│   ├── settings.json       the permission allowlist and the three hooks
│   ├── settings.local.json your own overrides; gitignored
│   ├── framework-sync.json the template commit last synced to
│   └── skills/             the coaching flows: check-in, program-week, ...
├── check-ins/              one dated record per check-in
├── routine/                program.md and one page per session, rendered
├── data/                   the structured data the scripts own
├── nutrition/
│   ├── menu/               recipe cards and index.md
│   ├── plans/              rendered meal plans
│   └── archive/            dated plans from before the recipe bank, if any
├── research/               template research notes
│   └── local/              the coach's local notes for you
├── reference/              formats the coach follows (records, cards, Hevy)
├── plugins/                your own plugin code, if any
├── coach/                  the coach scripts (a Python package)
├── tests/                  the template's test suite and fixtures; keep it
├── docs/                   the template's docs, this guide included
└── .coach/                 local working area; gitignored
```

## The files you read

These are the pages written for you. Structured data is the source of
truth and these pages are rendered from it, so none of them is edited by
hand (see [Pages and publishing](pages-and-publishing.md)).

- `README.md` is the dashboard (see [the glossary](../../CONTEXT.md)):
  where you stand this week, the week's sessions, what to watch, a
  progress summary and links. It is the page GitHub shows first on a
  phone.
- `this-week.md` is this week's brief: the focus, every session of the
  week, what changed and why, what to watch, what to do if you miss a
  day, and wins.
- `progress.md` is the progress page: best e1RM per lift, consistency
  week by week, the core-complete streak and bodyweight by week.
- `this-week-sheets.md` holds the session sheets you train from when
  Hevy is off: one table per session with an empty Done column.
- `routine/program.md` and `routine/<session-id>.md` describe the
  program as written: sessions, set groups, schemes and schedule rules.
- `check-ins/<date>.md` records each check-in: the coach's prose plus
  rendered regions for the week in review and the week ahead.
- `nutrition/menu/index.md` lists the recipe bank; each
  `nutrition/menu/<slug>.md` is one card. `nutrition/plans/<id>.md` is a
  meal plan for one window.
- `research/<id>.md` and `research/local/<id>.md` are the research
  notes behind the numbers the coach uses; `python3 -m coach research
  show rn:<note>.<n>` prints one claim.

## The files you or the coach edit by hand

Scripts never write these. You edit them yourself, or the coach does with
its Write tool after you agree.

| File | What you edit |
|---|---|
| `config.toml` | Every setting; see [Configuration](configuration.md). The coach asks before changing it. |
| `profile.md` | Your goals, week, equipment, limits and the Coach's notes, in words. The coach asks before changing stats, goals or Coach's notes. |
| `check-ins/<date>.md` | The prose parts: Coach's read, Decisions, Next week. The rendered regions between markers are not yours. |
| `nutrition/menu/<slug>.md` | A recipe card's hidden data block (TOML inside an HTML comment at the top) and its prose. The rendered region between them is written by `recipes render`. |
| `research/local/<id>.md` | A local note's data block and prose; `research render` writes its region. |
| `plugins/<kind>/<name>.py`, `plugins/tests/test_<name>.py` | Your own plugin code, as a code change. |
| `.env` | Your Hevy key. |

After a hand edit of a data file, the PostToolUse hook runs that file's
checks and reports a failure straight away, so a typo in `config.toml`
or a stale region in a record never sits unnoticed.

## The data files the scripts own

Everything under `data/` is JSON or JSON Lines the coach scripts write
through their commands. You can read any of it; edit it only through a
command, so its checks run. All of it is committed.

| Path | What it holds |
|---|---|
| `data/program.json` | The program: sessions, set groups, schemes, schedule rules, blocks, missed-day rules. `program validate` and `program render` follow every edit. |
| `data/state.json` | The program state: rotation position, the block summary, light-week state, a one-off week, routine ids. |
| `data/exercises.json` | Your exercise library entries: overrides, custom exercises, confirmed load modes, exercises you avoid. |
| `data/overlays/<id>.json` | One overlay per programming pass: the prescription in force for a span of days, with its approval stamp. |
| `data/hevy/writes.jsonl` | Append-only audit of every Hevy write and verification. |
| `data/history/<YYYY-MM>.json` | Resolved workouts for one month, from Hevy or the manual log. |
| `data/history/annotations.json` | Corrections and facts the log lacks: misses, coach-led sessions, repairs, load-mode notes. |
| `data/decisions.json` | Recorded coaching decisions and overrides. |
| `data/followups.json`, `data/niggles.json` | Open questions with review dates; niggles with their load constraints. |
| `data/blocks.json` | The block ledger: every block and each week a check-in closed in it. |
| `data/status-days.json` | Status days: ill, injured, travel, planned breaks. |
| `data/events.json` | Goal events and the windows agreed before them. |
| `data/log/workouts.jsonl` | The manual lifting log for training without Hevy, append-only. |
| `data/activity/activities.jsonl`, `planned.jsonl`, `sync.json` | Activity records, planned activities and the sync map for each source. |
| `data/activity/associations.json` | Explicit links from a logged activity to a planned one. |
| `data/activity/wellness.jsonl` | Wellness records, only when `[activity] wellness_in_git = true`. |
| `data/nutrition/readings.json` | The nutrition readings series from check-ins. |
| `data/nutrition/plans/<id>.json` | One meal plan per window. |
| `data/archive/programs/<YYYY-MM-DD>/` | The previous `program.json` and `state.json`, archived when a program is replaced. A second replacement on the same day gets `-2`, then `-3`. |

## Rendered files and the checks that guard them

A rendered file starts with a marker line naming its source and the
command that rewrites it, for example:

```text
<!-- generated by coach from data/program.json; edit the data, then run: python3 -m coach program render -->
```

Whole rendered files are `README.md`, `this-week.md`, `progress.md`,
`this-week-sheets.md`, every page under `routine/`, every page under
`nutrition/plans/` and `nutrition/menu/index.md`. Rendered regions sit
between `<!-- coach:begin <kind> <id> -->` and `<!-- coach:end <kind>
<id> -->` inside files you otherwise edit: check-in records, recipe cards
and research notes.

`coach check` compares each of them with a fresh render and fails when
the bytes differ: `pages_fresh` and `pages_line_ceiling` for the three
root pages, `sheets_render_fresh` for the session sheets,
`routine_render_fresh` for the routine pages, `meal_plan_render_fresh`
and `recipe_index_fresh` for the nutrition pages, `recipe_render_fresh`,
`research_render_fresh` and `overlay_render_fresh` for the regions, and
`render_fresh_sweep` for any other marked region in the workspace. The
fix is always the same: change the data, then run the command the marker
names.

## The local working area

`.coach/` is gitignored and holds nothing you need to keep. Everything in
it can be rebuilt or is a draft on its way to a committed file.

| Path | What it holds |
|---|---|
| `.coach/cache/hevy/` | The raw Hevy cache: workouts, routines, templates. Rebuild it with `python3 -m coach hevy pull --full`. |
| `.coach/backups/<UTC timestamp>/` | Copies taken before a schema migration, and old recipe cards before conversion. |
| `.coach/proposals/<id>.json`, `<id>.proposed.json`, `<id>.meta.json` | A programming pass's editable draft, its untouched original and the run's facts, until `propose finalize` turns it into an overlay. |
| `.coach/plans/<week start>-<name>.json` | Schedule plans handed to `propose week --plan`. |
| `.coach/drafts/` | Drafts the coach edits before a command applies them: program drafts, log drafts, custom-exercise entries, recipe drafts and saved recipe pages. |
| `.coach/activity/wellness.jsonl` | Wellness records, with the default `wellness_in_git = false`. |

`.env` is gitignored too, and lives at the root rather than in `.coach/`.

## Framework files and personal files

Your workspace holds two kinds of file. **Framework files** are the
system: `CLAUDE.md`, `CONTEXT.md`, `.claude/`, `coach/`, `reference/`,
`research/<id>.md`, `config.example.toml` and `.env.example`. The
template is their source of truth, and `/framework-sync` copies the
template's current version over yours (see [Updating](updating.md)).
Editing one locally works until the next sync overwrites it, which the
sync warns about first.

**Personal files** are yours, and the template never tracks them, so the
sync cannot touch them: `config.toml`, `profile.md`, `.env`, everything
under `data/`, `routine/`, `check-ins/`, `nutrition/`, `plugins/`,
`research/local/` and `.coach/`, plus `this-week.md`, `progress.md` and
`this-week-sheets.md`. A file you add under `reference/` is personal for
the same reason. `README.md` is a special case: the template's README is
its front page, your `README.md` is the dashboard, and the sync leaves it
alone.

The template's own files travel with your copy but need nothing from
you: `tests/` (the test suite and fixtures; keep it, nothing needs
deleting), `docs/` (this guide, the design contract, the decision
records and `docs/agents/`, which are for people developing the
template), and `.gitkeep` placeholders. `CONTEXT.md` is the glossary the
coach works from; read it when a term is unclear, but you never edit it.

## Check-in record names

A check-in record is `check-ins/YYYY-MM-DD.md`, dated the day of the
review, with a first line of `# Check-in — YYYY-MM-DD (weekly)`,
`(deep)` or `(catch-up)`. The record `/setup` writes is `# Program start
— YYYY-MM-DD`. The title's date must match the filename; a record whose
title does not parse is kept but ignored for review timing. See
[Check-in](check-in.md).
