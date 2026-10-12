# Updating your copy

This doc covers `/framework-sync`, the flow that pulls the latest framework
into your workspace, and the data migrations that may follow it. Read it
when the coach says a data file is newer than the scripts read, when you
want a new skill or fix the template has shipped, or when you want to know
which version you are on.

## What the framework is

The framework is every file the template tracks on its `main` branch,
except four things: `docs/**` (the template's own development history and
these guide pages), `tests/**` (the template's test suite and fixtures),
`README.md` (the template's front page; in your workspace `README.md` is
the dashboard that `pages render` writes) and `.gitkeep` placeholders.
The template repo is the manifest: whatever it tracks, minus those
exclusions, is what the sync copies. In practice that means the skills in
`.claude/skills/`, `CLAUDE.md`, the `coach` package, the research notes in
`research/`, `config.example.toml`, `reference/` docs the template ships,
and `.claude/settings.json`.

Everything personal is never touched, because the template does not track
it. The sync copies files from the template, so a path the template never
has cannot be written:

| Personal path | What it holds |
|---|---|
| `config.toml` | your settings |
| `profile.md` | the athlete in words |
| `data/**` | the program, state, overlays, history, decisions, everything structured |
| `routine/**` | the rendered session pages |
| `check-ins/**` | your check-in records |
| `nutrition/**` | your recipe bank and meal plans |
| `plugins/**` | any plugins you wrote |
| `research/local/**` | your local research notes |
| `this-week.md`, `progress.md`, `this-week-sheets.md` | the rendered pages |
| `.coach/**` | the local cache, drafts and backups (gitignored) |
| `.env` | your Hevy key (gitignored) |

A test in the template fails if any of those paths is ever tracked there,
so the rule holds by construction, not by care.

Because `docs/**` is excluded, these guide pages do not reach your
workspace. Read them on GitHub, in the template repo.

## The marker

`.claude/framework-sync.json` records the template commit your workspace
last synced to:

```json
{ "template_commit": "<full sha>", "synced_at": "2026-10-12" }
```

It is committed in your workspace. The template never contains one, so a
fresh copy made from "Use this template" has no marker until its first
sync.

## Which version you are on

Two things tell you. `python3 -m coach version` prints the package version
and the Python it runs on:

```json
{"schema_version": 1, "ok": true, "command": "version",
 "data": {"version": "0.1.0", "python": "3.14.5"}, "warnings": []}
```

The marker tells you the exact template commit. Together they say what
code you run and where it came from.

## When to sync

Run `/framework-sync` whenever you want what the template has shipped. The
coach will also point you at it: when a data file carries a schema version
newer than the scripts read, `coach check` fails `schema_versions` with a
message ending "run /framework-sync", and the session-start status says
the same. That happens when a file was written by a newer framework than
the one in your workspace, for example after you pulled a commit from
another machine.

## What the sync does, step by step

The sync is one direction only. The template is the source of truth for
the framework; your workspace is the source of truth for your data. The
skill never edits your data by hand. Its only data change is the
migration in step 5.

### 1. Preconditions

Your workspace must be a git repo with a clean working tree. If
`git status --porcelain` shows anything, the coach stops and asks you to
commit or stash first. The sync makes its own commit, and it must not
sweep up unrelated changes.

### 2. Fetch the template

The coach uses the `template` remote if you already have one, otherwise it
adds it:

```bash
git remote add template https://github.com/joeuk89/claude-strength-coach.git
git fetch template
```

If the fetch fails because you are offline or the repo moved, the coach
says so and stops. Nothing has changed locally.

### 3. Work out what changed

The coach reads the marker and checks that its commit exists in the
fetched history.

With a valid marker, the change set is `git diff --name-status <marker sha>
template/main`, filtered to the framework set. Added and modified files
are copied; deleted files are removed. A skill the template removed or
merged into another goes this way, as a deleted folder under
`.claude/skills/`. If nothing is left after filtering, the coach tells you
that you are already up to date and stops.

With no marker, or a marker whose commit the fetched history does not
know, the coach does a full copy: every framework file in `template/main`
that differs from your working copy, plus any that do not exist locally.
Deleted files cannot be detected on such a run, with one exception. A
folder in `.claude/skills/` that `template/main` lacks is a skill the
template removed or merged, unless you wrote it, so the coach lists those
and offers to remove them in the same batch.

### 4. The drift check

Framework files are meant to be edited in the template, never locally,
but it happens. Before writing anything, the coach runs `git diff <marker
sha> -- <path>` for each file about to be overwritten or deleted. Any
output means your working copy drifted from what the last sync delivered.

The coach lists every drifted file and says plainly that its local edits
will be overwritten. You give one confirmation for the whole batch. If you
decline, the coach stops with nothing changed and suggests porting your
edits to the template instead, which is the right home for them. An
overwritten edit is recoverable from your git history, since the drifted
version was committed before the sync began.

On a first run there is no marker to compare against, so the coach lists
every file the sync will change and asks you to confirm once.

### 5. Apply and migrate

Each copy is `git checkout template/main -- "<path>"`, each deletion is
`git rm "<path>"`, and the marker is rewritten with `template_commit` from
`git rev-parse template/main` and today's date. Those changes are now
staged.

The new framework may read a newer schema version of your data files
(`data/**/*.json`), so the coach brings them up to it before committing.
See [Data migrations](#data-migrations) below for what you see and what
can go wrong.

### 6. The commit

Everything lands in one commit: the framework files, the marker and any
migrated data files. Its subject is `Sync from template: <one-line gist of
what came in>`. Its body lists the template commit subjects being pulled
in, from `git log --reverse --format='- %s' <marker sha>..template/main`.
On a first run the body is `Baseline sync at <short sha>` instead.

The coach offers to push to `origin` and never pushes unasked.

If your own standing instructions require human review before commits,
the coach stages and shows you the diff instead of committing. Your rules
win over the skill.

### 7. Close-out

The coach summarises what came in, in plain words rather than filenames:
"check-in skill updated, an old skill removed". If the sync skill's own
file was among the updates, the coach says so. The new instructions take
effect from the next run, not this one, because the coach was already
following the old version when the files changed.

## Data migrations

Every JSON document the scripts own carries an integer `schema_version`.
When the framework changes a document's shape, the schema's version goes
up and a migration step ships with it. A reader that finds an older
version than it expects exits 1 and tells you to run `python3 -m coach
migrate run`. A reader that finds a newer version exits 1 and tells you to
run `/framework-sync`.

### Seeing where you stand

`python3 -m coach migrate status` lists each owned data file with its
version and the version this coach reads. From a test workspace with one
overlay behind its version:

```json
{"schema_version": 1, "ok": true, "command": "migrate status",
 "data": {"files": [
   {"path": "data/exercises.json", "doc": "exercise_library",
    "version": 1, "target": 1, "state": "current"},
   {"path": "data/overlays/2026-10-12-weekly.json", "doc": "overlay",
    "version": 0, "target": 6, "state": "behind"}],
  "behind": 1}, "warnings": []}
```

The `state` is `current`, `behind`, `ahead` or `unreadable`. Only
`behind` files are migrated. `ahead` means the file came from a newer
framework than yours, so sync first.

### The dry run

The coach runs `python3 -m coach migrate run --dry-run` first and shows
you which files move from which version to which, plus any notes a step
reports about what it changed. An empty `files` list means nothing to
migrate. The dry run does every read and every check and writes nothing.

### The real run

`python3 -m coach migrate run` then:

- backs every file it will change up under `.coach/backups/<UTC
  timestamp>/`, at the same relative path (`.coach/` is gitignored, so the
  backup never reaches a commit);
- applies each step in order and validates the result against the
  current schema;
- writes the upgraded files only when every one validates, and if a write
  fails part way it restores every file from the backup;
- stages the written files with `git add` and never commits.

The sync's single commit then takes the migrated files along with the
framework files.

### When it exits 1

A migration can refuse to run. The dry run on a test workspace whose
overlay sits at a version with no step from it:

```json
{"schema_version": 1, "ok": false, "command": "migrate run",
 "error": {"code": "validation", "message": "1 file(s) cannot be migrated",
  "details": [{"path": "data/overlays/2026-10-12-weekly.json",
   "message": "no step from version 0 for overlay; the framework is missing a migration"}]},
 "warnings": []}
```

Other reasons are a file that is not a JSON object with an integer
`schema_version`, a file ahead of the version the coach reads, or a step
that produced a document the schema rejects (then the originals are
unchanged and the message names the backup).

When this happens mid-sync, the coach stops before committing and shows
you the problems. No data file has been written, but the framework files
from step 5 are staged and not committed. You have two choices:

- report the named problems (a missing step is a framework bug worth an
  issue), or
- back out the whole sync with `git reset --hard`, which drops the staged
  framework files and leaves your workspace as it was before the sync
  started.

### Running a migration on its own

You do not need a sync to migrate. If a command tells you to run `migrate
run`, run `python3 -m coach migrate run --dry-run`, read what it would
change, then `python3 -m coach migrate run`. The files are staged and
waiting for a commit of your own. Both commands are on the allowlist, so
the coach runs them without a permission prompt.
