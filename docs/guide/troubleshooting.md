# Troubleshooting

This doc covers what to do when something goes wrong: what each exit code
means in practice, how to read `coach check`, and the common situations
with their fixes. Read it when a command fails, a check turns red, or the
coach says it cannot proceed.

One rule sits under everything here. The coach scripts propose and verify;
when a guard refuses a write, the coach never works around it by hand. A
refusal is a message about the cause. Fix the cause, then run the command
again.

## Exit codes in practice

Every command prints one JSON envelope on stdout. On failure `ok` is
`false`, `error.code` names the kind of failure and `error.message` is one
plain sentence; `error.details` lists each problem with its path. The
exit code tells the coach what to do next. See [the coach
scripts](cli.md) for the envelope itself.

| Exit | Code | What it looks like | What you do |
|---|---|---|---|
| 1 | `validation` | Input or data failed validation, a check failed, or a Hevy write did not verify. `details` names each file, JSONPath and offending value. | Fix what the message names. For `coach check`, the envelope keeps `data.results` next to `error`, so the report is still there. |
| 2 | `usage` | A bad command line: an unknown flag, a missing argument, an unknown check id under `--only`. | Run the command with `--help` and correct it. |
| 3 | `refused` | A guard refused a write: no approval, the overlay was edited after approval, a routine changed in the app since the diff, the overlay's span has ended, a hash did not match, an unresolved `block` flag. Nothing was written. | Report the reason and fix the cause (approve, pull and review again, propose again). Never retry by hand or through a raw API call. `--dry-run` exits 3 too, so you can see a refusal before the real run. |
| 4 | `network` | Hevy is unreachable or erroring after retries: a timeout, a 5xx, a 429 after back-off. Also a `git push` that failed inside `pages publish`. | Try again later. For a failed push, the commit is kept: push it by hand. |
| 5 | `config` | Setup prevents running: Python older than 3.11, `config.toml` missing or invalid (the message names the file and the key), the Hevy key missing, or Hevy answering 401 or 403. | Fix what it names. `coach check` never exits 5: it reports these as `fail` results and exits 1. |
| 9 | `internal` | An uncaught exception, with the traceback on stderr. | A bug. Report it with the command and the traceback. |

## Reading `coach check`

`python3 -m coach check` runs every registered check against your
workspace and exits 1 if any fails. `--list` prints the registered checks
without running them. `--only ids` runs a comma-separated subset and may
be repeated; an unknown id exits 2.

Each result has an `id`, an `owner`, a `status`, a `message` and often a
`path`. The summary counts each status:

| Status | Meaning |
|---|---|
| `pass` | nothing wrong, or nothing to check |
| `warn` | worth attention, not a failure; the command still exits 0 |
| `fail` | a real problem; the command exits 1 |
| `skip` | the check had nothing to read (no such file yet, Hevy off, no `.coach/cache/`), or it needs a valid `config.toml` and there is none |

A check that crashes becomes one `fail` result with the traceback on
stderr. The session-start status quotes the summary and the ids of any
`fail` or `warn`, so most problems reach the coach before you ask.

### The registered checks

One line each: what the check catches and the usual fix. Where a message
names a command, run that command.

| Check | Catches | Usual fix |
|---|---|---|
| `activity_records_valid` | an activity, planned or wellness record that fails its schema (an unknown field, say) | fix the line in `data/activity/` |
| `activity_source_fresh` | a source's newest sync or import older than its `gap_warn_days` (warn) | `activity sync` |
| `activity_wellness_location` | the wellness file in the place `[activity] wellness_in_git` does not select | move the file or change the setting |
| `annotations_valid` | `data/history/annotations.json` invalid, an id used twice, or an annotation naming a workout the history lacks | fix or withdraw the annotation |
| `available_days_conflicts` | a session or shift rule planned on a weekday outside `[athlete] available_days` (warn) | add the day or move the session |
| `avoided_in_program` | an active session using an exercise you avoid (warn) | swap the exercise or clear the avoid with `library set-avoid` |
| `bare_hevy_values` | a dumbbell load figure in `profile.md`, a check-in record or overlay text with no per-hand or Hevy wording | write both numbers: `25/hand (Hevy: 50)` |
| `block_config` | `blocks.hard_weeks_ceiling` outside 4 to 8 | fix `data/program.json` |
| `block_state` | `data/blocks.json` invalid, or `state.block` disagreeing with the ledger | fix the file and key the message names |
| `cardio_config` | a negative `[cardio]` cap, a spike ratio of 1 or less, a sleep threshold out of range | fix `config.toml` |
| `checkin_record_words` | a record's prose over its tier's word ceiling (warn) | cut it, or let the data carry it |
| `checkin_records` | a record whose first line is not a Check-in or Program start title, or whose title date differs from its file name (warn) | fix the title line |
| `config` | `config.toml` missing or invalid, the file and key named | copy `config.example.toml` or fix the key |
| `dangling_exercise_ids` | an overlay line whose `exercise_id` is not in the library | fix the id, or add a `custom_` entry |
| `dangling_routine_ids` | an overlay session naming a Hevy routine the cache lacks | `hevy pull`; if the routine is gone, rebuild the overlay |
| `decisions_schema` | `data/decisions.json` invalid, such as a standing override with no `until` | fix the file |
| `env_untracked` | `.env` tracked by git, or present and not ignored | untrack it and keep it in `.gitignore` |
| `events_valid` | `data/events.json` with a bad date, a window outside its event, or a status and result that disagree | `events update` or `events complete` |
| `flag_codes_known` | an overlay flag with a code no module registers | propose the week again |
| `followups_schema` | `data/followups.json` invalid | fix the file |
| `hevy_cache_age` | no Hevy cache, or one older than `[hevy] cache_max_age_hours` (warn) | `hevy pull` |
| `history_schema` | a month file invalid, a workout dated outside its month, or one workout in two files | `history rebuild --month` |
| `history_unresolved` | a logged exercise with no confirmed load mode or no library match (warn) | `library confirm` or `library set-mode`, then `history rebuild` |
| `library_valid` | `data/exercises.json` invalid | fix the entry |
| `light_week_overlay` | an agreed light week with no deload overlay yet, or a deload overlay with no adopted decision (warn) | `/program-week` or `block decide` |
| `load_caps` | a set above its `[caps]` entry or the location's `dumbbell_max` | lower the load or raise the cap |
| `load_modes_confirmed` | an exercise in a routine or the program with no confirmed load mode | the `library` command the message names |
| `manual_log_valid` | a manual log line that repeats an id, names an unknown exercise or session, or voids a workout never logged | `log void` or fix the line |
| `meal_plan_render_fresh` | a rendered meal plan missing, hand-edited or stale | `meals render` |
| `meal_plans` | a meal plan invalid or whose file name differs from its id | fix the plan |
| `missed_rules_valid` | a missed-day rule naming a session the program lacks | fix `data/program.json` |
| `niggles_schema` | `data/niggles.json` invalid, or a pattern or exercise id the library lacks | fix the file |
| `nutrition_override` | a nutrition override expired or expiring (warn) | `/goals` |
| `nutrition_readings` | the readings series invalid, such as one date twice | fix the series |
| `nutrition_template` | a standing meal or anchor naming a card that is missing or benched | fix `config.toml` or un-bench the card |
| `overlay_arithmetic` | an overlay load whose numbers disagree, such as `hevy_total` not twice the per-hand load | rebuild the overlay |
| `overlay_folds_expired` | a folded exercise on a weekly or deload overlay, or folded more than a week before the span | build the week from the program again |
| `overlay_hevy_drift` | a cached routine that differs from the overlay in force (warn) | `routines diff`, then `/hevy-sync` or a push |
| `overlay_library_consistency` | an overlay line whose load mode or Hevy template differs from the library | rebuild the overlay, or `library set-mode` |
| `overlay_render_fresh` | a check-in's overlay region hand-edited or stale | `overlay render <id> --into <record>` |
| `overlay_schema` | an overlay failing its schema, or whose file name differs from its id | fix or rebuild it |
| `pages_fresh` | `this-week.md`, `README.md` or `progress.md` hand-edited or stale | `pages render` |
| `pages_line_ceiling` | the brief over its line ceiling | `pages render` |
| `plugins_valid` | a plugin that breaks the contract | fix what `plugins validate` lists |
| `prescription_valid` | an overlay line past its validity window or breaking a prescription rule | settle it, then `prescription check --write`; an approved overlay needs a new overlay for its remaining days |
| `program_balance` | a muscle with no planned hard sets or under its dose target (warn) | review at the next check-in; `structure balance` |
| `program_exercise_ids` | the program naming an exercise the library lacks | fix the id, or add a `custom_` entry |
| `program_schema` | `data/program.json` failing its schema: a misspelt key, a missing `load_mode` | fix the JSONPath it names |
| `python_floor` | Python older than 3.11 | install 3.11 or newer |
| `recipe_cards` | a recipe card's data block invalid | fix the card |
| `recipe_index_fresh` | `nutrition/menu/index.md` missing or differing from a fresh render | `recipes render` |
| `recipe_render_fresh` | a card's rendered region missing or differing from its data block | `recipes render` |
| `render_fresh_sweep` | any other rendered region that is stale | the render command the message names |
| `research_citations` | a claim reference that does not resolve or cites an expired note | fix the reference, or research again |
| `research_expiry` | a research area past its review date (warn) | research again and write a local note |
| `research_notes` | a note's data block or claims table invalid, such as two claims numbered 1 | fix the note |
| `research_render_fresh` | a note's rendered region missing or stale | `research render <id>` |
| `routine_render_fresh` | a routine page missing, hand-edited, for a session the program no longer has, or not rendered from the program | `program render` |
| `schema_versions` | a document newer than the coach reads, or older | `/framework-sync`, `migrate run`, or `hevy pull --full` for a cache file |
| `session_cap_ids` | `[sessions.cap_minutes]` naming a session the program lacks (warn) | fix `config.toml` |
| `sheets_render_fresh` | `this-week-sheets.md` hand-edited or stale (Hevy off) | `sheets render` |
| `state_schema` | `data/state.json` invalid | fix the path it names |
| `status_days_valid` | a status day ending before it starts, or two open-ended rows of one kind | `status-days end` or `status-days withdraw` |

## Common situations

### I edited a rendered page by hand

Rendered pages (`routine/*.md`, `this-week.md`, `README.md`,
`progress.md`, the overlay region in a check-in, recipe regions) are
written from data and checked for freshness. When the coach edits one with
the Write or Edit tool, a hook runs the matching checks straight after
and reports a failure back, so the coach sees it at once: "routine/
session-a.md was edited by hand or is out of date; edit
data/program.json, then run python3 -m coach program render". The hook
cannot undo the edit. Make the change in the data file, then re-render:
`program render` for routine pages, `pages render` for the brief,
dashboard and progress, `overlay render <id> --into <record>` for a
check-in region.

### I changed a routine in the Hevy app

Nothing breaks. On the next pull, `routines verify` reports the routine
with `verified: false` and lists each change. A `structural` change
(exercises, order, set counts, reps, rest, supersets) is an in-app edit:
the coach's brief raises it as a keep-or-replace question, and your "go"
settles it with the week. A kept edit lands in `data/program.json`; a
replaced one is overwritten on the push. Load-only edits are overwritten
without comment, since the log already holds what you lifted. A routine
whose notes do not carry the overlay in force is STALE: the brief lists
it, and the pass rewrites it. To reconcile outside a programming pass,
run `/hevy-sync`, which walks each discrepancy with you one at a time.

### The gate denied a command

A hook reviews every Bash command before it runs. A `coach` command that
writes to Hevy gets a dry run, and the permission prompt shows its
summary, so you approve exactly those changes. Three things get denied
rather than asked:

- **Bypass-permissions mode.** Nobody would see a prompt, so every Hevy
  write is denied. Run the session with normal permissions.
- **A push the dry run refuses.** The denial carries the refusal's
  reason: an unapproved overlay, a missing `--expect-plan` hash. Fix the
  cause.
- **Unreadable effects in bypass mode.** A loop, a shell variable or a
  nested script the gate cannot read is asked about in normal mode and
  denied in bypass mode. Use individual direct commands, such as
  `python3 -m coach overlay list`, instead.

A raw `curl` or `wget` write to `api.hevyapp.com` is never denied
outright in normal mode, but it prompts with a warning that it skips the
approval check, read-back and audit log. Use `routines push` or
`routines create` instead.

### The Hevy cache is stale

`coach check` warns through `hevy_cache_age` when the cache is older than
`[hevy] cache_max_age_hours` (default 24), and `hevy status` reports
`stale: true` with the age. Run `python3 -m coach hevy pull`; it reads
every workout once, then only what changed. `hevy pull --full` re-reads
everything, which is also the fix when a cache file is on an old schema.
The cache lives under `.coach/cache/hevy/` and is gitignored, so it is
always rebuildable.

### A push exited 3

`routines push` was refused by a guard and wrote nothing. The message
says which: the overlay is not approved, or was edited after approval; a
routine changed in the app since the diff ("pull and review again"); the
overlay's span has ended; the write plan hash you passed does not match
the dry run. Each one has a cause to fix before the push can run. An
expired or edited overlay means a new programming pass. A changed routine
means `hevy pull`, then `routines diff` again, then the push. The coach
never completes a refused push by hand or through the API.

### `config validate` exits 5

The message names the file and the key:

```text
coach: No config.toml in /path: copy config.example.toml to config.toml and edit it.
```

An unknown table or key is also an error, as `unknown key "foo" in
[hevy]` or `unknown table [cardio_extra]`. Compare your file against
`config.example.toml`, which comments every key, and see
[Configuration](configuration.md). Every command that reads config fails
the same way until it is fixed.

### A dumbbell load looks doubled

Hevy stores the total across both hands, so a per-hand load typed into
Hevy as a per-hand number halves it, and a Hevy total read as per-hand
doubles it. That is a convention slip, not a strength change. `python3 -m
coach stats audit` lists every dumbbell exposure in the last 8 weeks that
jumped exactly 2× or ½× at the same reps and RPE, with the sibling lifts
that jumped on the same date. An open candidate stays out of the e1RM
series until it is settled. Confirm the real per-hand weights, then
record the answer with `history annotate`: `--kind discount` for a slip,
`--kind confirm` for a real jump, `--kind repair --set <n> --field <field>
--value <v>` for a mistyped value. Stored loads are reinterpreted only by
`history rebuild --month YYYY-MM`.

### The check-in says STALE, or the Sunday message is wrong

STALE means a routine does not carry the overlay in force: `routines
verify` found a `prescription` change to its notes, so you would train
from old notes. The next programming pass rewrites every routine in the
span, STALE or not, so it clears itself; the coach lists it so you know.

The Sunday message is built from `checkin prepare`. Its figures come from
the history, so a wrong figure means wrong data behind it: a missed
session recorded under the wrong tag, a workout logged twice, a load on
the wrong convention. Tell the coach what is wrong. The fix goes in with
`history annotate` (a miss, an unlogged session, a discount or repair) and
the card is rebuilt; the coach never edits the card's figures by hand.

### My data file is on a newer or older schema

`coach check` fails `schema_versions` with one of two messages. Newer:

```text
data/overlays/2026-10-12-weekly.json has schema_version 7, newer than this coach reads (6); run /framework-sync
```

Older:

```text
data/overlays/2026-10-12-weekly.json has schema_version 0, older than the current 6; run python3 -m coach migrate run
```

Newer means your framework is behind the file: run `/framework-sync`.
Older means the framework moved on: run `python3 -m coach migrate run
--dry-run`, then `migrate run`, which backs the file up under
`.coach/backups/` and stages the upgraded file. See
[Updating](updating.md). A Hevy cache file on an old version is
rebuilt with `hevy pull --full` instead.

### I hand-edited `data/program.json` and validate fails

`python3 -m coach program validate` checks the program against its
schema, the exercise library and your config, and exits 1 with a JSONPath
per problem: `$.sessions[0].exercises[2].load_mode` and the message. A
misspelt key is an error (validators are strict), a missing `load_mode`
is an error, an exercise id the library lacks is an error, a scheme name
no plugin provides lists the known schemes. Fix each path it names, run
validate again, then `program render` so the routine pages match. The
hook runs the same checks straight after the edit, so the coach usually
sees the problem before you do.

### The session-start status is missing or says the coach scripts failed

At session start a hook puts the `coach status` lines in the coach's
context. Three cases:

- **Nothing at all** in the template repo is correct: the hook prints
  nothing there. In your workspace, see "the workspace is treated as the
  template" below.
- **"Coach status unavailable: the coach scripts failed (...)"** names the
  error. Run `python3 -m coach status` yourself to see the full message,
  then `coach check`.
- **"Coach status unavailable: the coach scripts need Python 3.11 or
  newer"** is the Python floor; see the next item.

The hook always exits 0, so it never blocks the session.

### Python version too old

The scripts need Python 3.11 or newer. On an older interpreter every
command exits 5 with "The coach scripts need Python 3.11 or newer, and
this is Python 3.9.6" (for example), and `coach check` fails
`python_floor`. Install a
newer Python and make sure `python3` on your PATH is it:
`python3 --version`.

### The workspace is treated as the template

With neither `profile.md` nor `config.toml` present, `coach status` and
the session-start hook decide whether a checkout is the template from its
own local git config: `coach.workspace = template`, or no setting and an
`origin` on the canonical template repository. A fresh clone of your own
copy has neither file yet and may inherit the template's origin if you
cloned the template directly. Mark it:

```bash
git config --local coach.workspace athlete
```

Git never commits or clones this setting, so set it in each new clone.
Once `/setup` has written `config.toml` and `profile.md`, the files alone
make it an instance.

### A cloud session cannot reach Hevy

A Claude Code cloud session has no `.env`, because the file is not in the
clone. Configure the cloud environment at claude.ai/code: add
`HEVY_API_KEY` under environment variables, set network access to
Custom, add `api.hevyapp.com`, and tick the option that also includes the
default package managers. The default Trusted level does not allow
`api.hevyapp.com`, so every call fails without this. Changes apply to
sessions started afterwards. See [Hevy](hevy.md) and
`../../reference/hevy-api.md`.

### I want to undo a programming pass

What you can undo depends on how far it got. A proposal draft lives
under `.coach/proposals/` until it is finalized; an unapproved overlay is
a file in `data/overlays/` that no push or publish will accept. `python3
-m coach propose discard --proposal <id>` removes an abandoned draft and
any unapproved overlay finalized from it, and leaves approved work alone.
A stale draft (its span ended, or a newer approved overlay covers it)
exits 3 on finalize and is discarded the same way.

Once you have said "go", the overlay is approved and may have been pushed
to Hevy and published. That work stays. A new programming pass, in
midweek mode, writes a new overlay that supersedes the old one for the
days it covers.

### I voided or corrected a manual workout

Without Hevy, the log is append-only. A wrong workout is not edited:
`python3 -m coach log void <id> --reason <text>` removes it from history
and leaves its line in the log with the void recorded, then you add the
correct workout with `log add`. The history re-resolves on each change,
so the pages and the check-in read the corrected log at once.

### `pages publish` failed to push

Exit 4 from `pages publish` means the commit was made and the push
failed: "git push to origin failed (...); the commit <sha> is kept: push
it by hand with git push". Your records are committed locally. Push when
you are back online:

```bash
git push
```

Exit 3 from publish is different and earlier: the overlay is not
approved or not the brief's overlay, the branch has no upstream, the
index already holds staged changes to other files, or an included path is
not a training record. Nothing was committed; fix the cause.

### An old workspace still has hand-written routine pages

If `routine/` exists but `data/program.json` does not, the workspace
still keeps its program as hand-written pages from before the program
became data. Every coaching skill checks for this first and stops with
the same message: it needs its one-time bootstrap migration onto
`data/program.json` first. The coach stops rather than guess at a
program from prose. The migration is a one-time job done with the coach;
one route to a `data/program.json` is `/new-program`, which can import
your Hevy routines into a program draft. After it, the pages are rendered
from the data and never hand-edited again.
