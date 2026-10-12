# The coach scripts

The command-line reference for `python3 -m coach`: how to call it, what
it prints, what each exit code means, and every group and command with
its flags. Read this when the coach quotes a command and you want to know
what it did, or when you want to run a read-only command yourself.

## Invocation

```bash
python3 -m coach [--root PATH] <group> <command> [options]
```

Run it from the workspace root. The root is `--root` when given, else
the `COACH_ROOT` environment variable, else the current directory. There
are two levels only: a group, then a command. `check`, `status` and
`version` are one-word commands with no group. `python3 -m coach --help`
lists the groups, `python3 -m coach <group> --help` a group's commands,
and `python3 -m coach <group> <command> --help` a command's flags. Needs
Python 3.11 or newer and nothing outside the standard library.

The coach never computes, converts or calls Hevy by hand: it runs these
commands and quotes their output, and when one fails it says so and
quotes the error. You can run any read-only command yourself at any
time; the ones that write are the coach's to run inside a flow, after
you approve.

## The output

Every run prints exactly one JSON object on stdout:

```json
{"schema_version": 1, "ok": true, "command": "units format",
 "data": {}, "warnings": []}
```

On failure `ok` is false, `data` is absent, and an `error` object names
what went wrong:

```json
"error": {"code": "validation", "message": "one plain sentence",
          "details": [{"path": "$.sessions[0].exercises[2].load.hevy_kg",
                       "message": "expected 22.6796, found 45.3592"}]}
```

`coach check` is the one exception: it keeps `data.results` and
`data.summary` next to the error, because its report explains the
failure. Stderr carries progress and diagnostics for a human, each line
prefixed `coach: `; nothing reads it. The hook commands (`gate
pretooluse`, `hooks sessionstart`, `hooks posttooluse`) print a hook
response for Claude Code instead of the envelope.

## Exit codes

| Exit | `error.code` | Meaning | Examples |
|---|---|---|---|
| 0 | none | Success; warnings allowed | |
| 1 | `validation` | Input or data failed validation, a check failed, or a Hevy write did not verify | bad overlay arithmetic; `coach check` has a `fail` |
| 2 | `usage` | Bad command line | an unknown flag |
| 3 | `refused` | A guard refused a write | no approval; an edit after approval; a routine changed in the app since the diff; an ended span; a push with no upstream |
| 4 | `network` | Hevy unreachable or erroring after retries | timeout, a 5xx, a 429 after back-off, a failed `git push` |
| 5 | `config` | The environment or config prevents running | Python older than 3.11; `config.toml` missing or invalid; the Hevy key missing or rejected |
| 9 | `internal` | An uncaught exception, with a traceback on stderr | a bug: report it |

`coach check` never exits 5: it reports config and environment problems
as `fail` results and exits 1. See [Troubleshooting](troubleshooting.md)
for what to do with each code.

## `--dry-run`

Every command that writes anything accepts `--dry-run`. A dry run does
every read and every check, writes nothing, and returns what it would
have done. It exits with the code the real run would, so a push that
would be refused exits 3 under `--dry-run` too. The coach uses it to
preview a Hevy write before asking you, and `pages publish --dry-run` to
show the commit before making it.

## What writes where

Most commands only read. The reference below marks the rest:

- **(W)** writes local files in the workspace. Some write only the
  gitignored cache (`hevy pull`, `routines diff` and `routines verify`
  with `--refresh`), a draft folder (`starters draft`) or a rendered
  region.
- **(H)** writes to Hevy. Only three commands do: `routines push`,
  `routines create` and `routines retire`. Each is behind the approval
  gate, so Claude Code shows you what it will write and waits.
- **(G)** commits and pushes. Only `pages publish` does, and it refuses
  without an approved overlay.
- **(N)** reads from Hevy over the network without writing to it.

A command with none of these marks reads local files only.

## Reference

`--help` is the source of truth. This section was generated from it on
2026-10-12; if a flag here disagrees with `--help`, trust `--help`. Each
writing command also takes `--dry-run`, left out of the lists below. A
flag marked "(required)" must be given.

### Top-level commands

- **`check`**: Run the instance checks; exit 1 if any fails
  - `--only IDS`: comma-separated check ids to run (repeatable)
  - `--list`: list the registered checks without running them
- **`status`**: Where this instance stands now, from local files only: one section per provider
- **`version`**: Print the coach package and Python versions

### `activity`

Logged cardio and other activity from every source: manual entries, imports and syncs.

- **`add`** (W): Record an Activity by hand
  - `--kind {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}` (required)
  - `--start TIMESTAMP` (required): ISO 8601; with no offset it is local time in [athlete] timezone
  - `--duration-min MIN` (required)
  - `--distance-km KM`
  - `--distance-mi MI`
  - `--distance-m M`
  - `--rpe RPE`: session RPE, 0 to 10
  - `--avg-hr BPM`
  - `--name NAME`
  - `--notes NOTES`
  - `--indoor`
- **`anonymise`** (W): Turn a real export into a committable test fixture: dates shifted by whole weeks, ids and device names replaced, values perturbed
  - `--source NAME` (required)
  - `--file PATH` (required)
  - `--out DIR` (required): folder the fixture is written to
- **`import`** (W): Read one export file from a source, such as a 90-day manual export, and append what changed
  - `--source NAME` (required)
  - `--file PATH` (required)
- **`list`**: List resolved Activities in a span: duplicates merged, sources by precedence
  - `--from DATE`: first day (default: the start of this week)
  - `--to DATE`: last day (default: the end of this week)
  - `--kind {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}`: only this kind (repeatable)
- **`show`**: Show one Activity by any id it was merged from, with every line written for it
  - `id` (argument): record id, such as manual:2026-10-08-run-1
- **`status`**: Each enabled source: last sync, record counts, newest date, wellness gaps
- **`sync`** (W): Fetch every enabled source and append what changed; never stages or commits
  - `--source NAME`: sync only this source
- **`void`** (W): Remove an Activity record from every view; its history stays in the file
  - `id` (argument)
  - `--reason TEXT` (required)

### `block`

The block ledger: close weeks, count completed hard weeks, record light-week decisions.

- **`close`** (W): Close every week up to W: class it, count completed hard weeks, check the four fatigue triggers and propose, watch or skip a light week
  - `--week W` (required): a week label (YYYY-Www) or any date in it
  - `--readiness {poor,ok}`: the athlete's readiness this week
  - `--sleep {poor,ok}`: override the sleep measured from tracker or diary hours; needs --sleep-reason
  - `--sleep-reason TEXT`: why the override, shown with the close
  - `--deep`: this check-in is a deep review
- **`decide`** (W): Record the athlete's answer to a light week (adopted or declined), or the coach adopting one unprompted
  - `--outcome {adopted,declined}` (required): what the athlete chose
  - `--type {deload,light,return}`: for adopted: deload, light or return (default: the proposal's)
  - `--week W`: for adopted: the light week (default: the proposal's)
  - `--reason TEXT`: why; required to decline, to change the proposed type, or to adopt with none proposed
- **`init`** (W): Start the block ledger from the completed hard weeks the athlete confirms
  - `--hard-weeks N` (required): completed hard weeks in the current block
  - `--through W`: the last week the count covers (default: last week)
  - `--started D`: the block's first day (default: N weeks back from --through)
  - `--reason TEXT`: where the count came from
- **`status`**: The block's hard-week count, the light-week state, the status line and whether the next check-in is deep

### `bodyweight`

Dated weigh-ins and the trend they support.

- **`list`**: Every dated bodyweight observation in bodyweight units, one per date and basis, and the trend it supports
  - `--last N`: only the newest N observations
- **`record`** (W): Keep one dated weigh-in as a manual wellness body mass; needs neither [nutrition] nor [activity] on, and repeating the same weigh-in writes nothing
  - `--weight X` (required): the weigh-in, in [athlete] bodyweight_units
  - `--date DATE`: the day of the weigh-in, YYYY-MM-DD (default: today)
  - `--replace`: correct a different weigh-in already recorded for the date

### `cardio`

The week's cardio load, planned-against-logged reconciliation, cardio flags and the record's cardio block.

- **`associate`** (W): Associate an activity ID with a planned ID, or clear its association
  - `activity_id` (argument)
  - `--planned-id PLANNED_ID`
  - `--clear`
- **`flags`**: Cardio and week-level flags: logged bouts to today, plans from today on
  - `--week W`: week label (2026-W41) or any date in it
  - `--span A..B`: an explicit span, YYYY-MM-DD..YYYY-MM-DD
- **`reconcile`**: Planned activities against logged ones: done, moved, missed, upcoming, extra, ambiguous, duplicate
  - `--week W` (required): week label (2026-W41) or any date in it
- **`render`** (W): The week's cardio block as markdown; with --into, write it into that check-in record
  - `--week W` (required): week label (2026-W41) or any date in it
  - `--into FILE`: the check-in record to write the cardio region into
- **`week`**: The week's lifting, coach-led sessions, runs, conditioning and session-RPE load
  - `--week W` (required): week label (2026-W41) or any date in it

### `checkin`

The check-in: when it is due, the Sunday message, the record skeleton, misses and the return brief.

- **`due`**: The last check-in record, when the next is due and which tier it runs
- **`misses`**: Missed sessions by tag and by session (default: the deep card's tally, since the last deep check-in)
  - `--since D`: first day (default: the last deep review's date, else the program's first window start)
  - `--until D`: last day (default today)
- **`prepare`**: The check-in card: the week from the log, then the numbered questions (data.text is the Sunday message)
  - `--until D`: last day of the window (default today)
  - `--tier {weekly,deep}`: run this tier whatever is due
  - `--deep-reason {first_close,six_weeks,catch_up_deferred,light_week_proposed,restructure_required}`: reason from block close deep_review.reasons; repeat for each reason
- **`return-brief`**: The return template of the coach's brief for the week back, from a proposal or a one-off overlay
  - `--proposal ID`: proposal id from propose week (illness, layoff)
  - `--overlay ID`: a coach-built one-off overlay (travel, no kit)
  - `--reason {ill,travel,no_kit,layoff}` (required): what caused the gap
- **`skeleton`** (W): Write check-ins/<date>.md with its week-review region; --refresh re-renders only the regions
  - `--date D` (required): the record's date
  - `--tier {weekly,deep,catch-up}`: the tier in the title (default: the card's mode)
  - `--overlay ID`: the overlay to render, collapsed, at the end
  - `--refresh`: re-render the regions of an existing record
- **`tag-gap`** (W): Tag every untagged missed core session since the last check-in with one miss tag
  - `--tag {time,sleep,ill,family,skipped,other}` (required): the miss tag for the whole gap

### `config`

Validate, print or suggest `config.toml` values.

- **`show`**: Print the validated config, defaults filled in
  - `--location LOCATION`: also print the equipment at this [equipment.locations] place
- **`suggest`**: Suggested [athlete] and [equipment] values for a new config.toml, and what to confirm; reads no config
  - `--unit {kg,lb}` (required): the athlete's units for loads
  - `--gym {commercial,home}`: the main place they train (default commercial)
- **`validate`**: Validate config.toml; exit 5 naming the file and key if it is wrong

### `dates`

Week labels and spans in the athlete's week.

- **`span`**: A week from its label or any date in it, or the span between two dates
  - `--week WEEK`: a week label (YYYY-Www) or any date in the week
  - `--start START`: YYYY-MM-DD, with --end
  - `--end END`: YYYY-MM-DD, with --start
  - `--week-starts {monday,sunday}`: first day of the week (default: [athlete] week_starts in config.toml)
- **`week`**: The week holding a date: its ISO week, label and span
  - `--date DATE`: YYYY-MM-DD (default: today)
  - `--week-starts {monday,sunday}`: first day of the week (default: [athlete] week_starts in config.toml)

### `decisions`

Recorded coaching decisions and their status.

- **`list`**: Recorded coaching decisions, each with its effective status
  - `--kind {override,adherence_trigger,light_week,training_max}`: only this kind
  - `--status {active,expired,withdrawn}`: only decisions with this effective status
- **`withdraw`** (W): Close a decision with the reason it no longer holds; it is never deleted
  - `ID` (argument): decision id, e.g. d-0001
  - `--reason TEXT` (required): why it is withdrawn

### `events`

Goal events such as a race, and the training window agreed before each.

- **`add`** (W): Record a goal event such as a race; no window before it is assumed
  - `--id ID` (required): a stable slug, e.g. autumn-10k
  - `--title TITLE` (required)
  - `--date D` (required): the event's local date
  - `--priority {A,B,C}` (required): A: the goal event; B and C: lesser
  - `--activity {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}`
  - `--distance-km KM`
  - `--distance-mi MI`
  - `--distance-m M`
  - `--planned-id ID`: the planned activity that is this event (planned list)
  - `--note TEXT`
- **`cancel`** (W): Cancel an event; it stays as history and its prompts stop
  - `ID` (argument): event id, e.g. autumn-10k
  - `--reason TEXT` (required)
- **`complete`** (W): Record an event's result; it stays as history and its prompts stop
  - `ID` (argument): event id, e.g. autumn-10k
  - `--result TEXT` (required): e.g. "41:30, a 2 min PB"
- **`list`**: Goal events in date order, with countdown and pending decisions
  - `--all`: include completed and cancelled events
- **`update`** (W): Change an active event, e.g. postpone it; a new date clears the window and a plan on the old date
  - `ID` (argument): event id, e.g. autumn-10k
  - `--title TITLE`
  - `--date D`
  - `--priority {A,B,C}`
  - `--activity {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}`
  - `--distance-km KM`
  - `--distance-mi MI`
  - `--distance-m M`
  - `--planned-id ID`
  - `--unlink`: drop the planned activity
  - `--note TEXT`
  - `--reason TEXT`: why it changed
- **`window`** (W): Record the window agreed before an event, record that none is kept, or clear the decision
  - `ID` (argument): event id, e.g. autumn-10k
  - `--from D`
  - `--to D`
  - `--none`: agreed: no window before this event
  - `--clear`: drop the decision; it is pending again
  - `--rationale TEXT`: why this window, or why none; with --clear, why

### `followups`

Open questions with a review date, raised at check-ins.

- **`add`** (W): Raise a question to come back to on a review date
  - `--text TEXT` (required): the question, one sentence
  - `--review-at D` (required): when to review it
  - `--source TEXT` (required): where it came from, e.g. "check-in 2026-10-11"
  - `--raised D`: the day it was raised (default today)
- **`defer`** (W): Keep a follow-up open with a new review date
  - `ID` (argument): follow-up id, e.g. f-0001
  - `--to D` (required): the new review date
  - `--kept`: it was reviewed today and stays open (default: deferred unreviewed)
  - `--note TEXT`: why, one line
- **`drop`** (W): Close a follow-up that no longer matters, with the reason
  - `ID` (argument): follow-up id, e.g. f-0001
  - `--reason TEXT` (required): why it is dropped
- **`list`**: Follow-ups, each marked due when open with its review date today or past
  - `--open`: open items only
  - `--due`: due items only
- **`render`**: The deep record's follow-up section; exits 1 while an item open before the date has no disposition dated that day
  - `--deep` (required): the deep check-in's section
  - `--date D` (required): the deep check-in's date
- **`resolve`** (W): Close a follow-up as answered
  - `ID` (argument): follow-up id, e.g. f-0001
  - `--note TEXT`: the answer, one line

### `gate`

The approval gate's PreToolUse hook (run by Claude Code, not by hand).

- **`pretooluse`** (N): Read PreToolUse hook JSON on stdin; print the hook's decision for a Hevy write, or nothing

### `hevy`

The local Hevy cache: pull it and report its age.

- **`pull`** (WN): Update the local Hevy cache: every workout once, then only what changed
  - `--full`: re-read every workout, not only the changes since the last pull
- **`record-fixtures`** (WN): Record anonymised test fixtures from the real Hevy account (GET requests only)
  - `--out DIR` (required): directory for the fixture files
- **`status`**: Report the Hevy cache's age and counts, and whether a key is set

### `history`

Resolved workouts from every log source, with corrections and facts the log lacks.

- **`annotate`** (W): Record a correction or a fact the log lacks in data/history/annotations.json
  - `--kind {confirm,discount,external,load_mode,miss,repair,trained_unlogged,unknown_convention}`: what the annotation records
  - `--workout ID`: workout id (discount, repair, confirm)
  - `--exercise ID`: library exercise id
  - `--set N`: set index; a discount without it covers the whole exposure
  - `--field {reps,rpe,weight_kg,type}`: the field a repair corrects
  - `--value V`: the corrected value (a number, or a set type)
  - `--load-mode {total,per_hand_x2,single_implement,bodyweight,assisted,band,duration,distance}`: the load mode a load_mode annotation forces
  - `--start D`: span start (load_mode, unknown_convention)
  - `--end D`: span end (load_mode, unknown_convention)
  - `--date D`: the day (miss, external, trained_unlogged)
  - `--session ID`: session id (miss, trained_unlogged)
  - `--tag TAG`: miss tag: time, sleep, ill, family, skipped, other
  - `--external ID`: coach-led session id (external)
  - `--done`: external: it happened
  - `--not-done`: external: it did not happen
  - `--trainer-cancelled REASON`: external: the trainer cancelled it, so it was not planned and is no miss
  - `--start-time T`: external: when it started, HH:MM or an ISO time
  - `--minutes N`: external: how long it lasted
  - `--rpe N`: external: the athlete's session RPE (0-10)
  - `--modality {lifting,conditioning,mixed}`: external: what it trained
  - `--note TEXT`: one line on what happened (external, trained_unlogged)
  - `--reason TEXT`: why
  - `--source TEXT`: where it came from, e.g. check-in 2026-10-11
  - `--withdraws ID`: the annotation this one withdraws
  - `--input FILE`: a JSON list of annotations to add in one go
- **`annotations`**: The annotations in force (corrections and facts the log lacks)
  - `--kind {confirm,discount,external,load_mode,miss,repair,trained_unlogged,unknown_convention}`: only this kind
  - `--all`: every annotation on file, each marked in_force (false once withdrawn, or a pure withdrawal)
- **`rebuild`** (W): Re-resolve one month under the current rules; the only way to reinterpret stored loads
  - `--month YYYY-MM` (required): the month file to rebuild
- **`show`**: Resolved workouts with annotations applied
  - `--since D`: first date, YYYY-MM-DD
  - `--until D`: last date, YYYY-MM-DD
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written
- **`sync`** (W): Resolve new and changed workouts from every history source into data/history/

### `hooks`

The SessionStart and PostToolUse hooks (run by Claude Code, not by hand).

- **`posttooluse`**: Read PostToolUse hook JSON on stdin; run the checks for a hand-edited data file and report a failure
- **`sessionstart`**: Read SessionStart hook JSON on stdin; print the status lines as the coach's context

### `interference`

The program's interference rules between lifting and cardio.

- **`check`**: Run the interference rules alone over logged workouts and planned activities; planned lifting sessions are judged by propose week. Flags, never moves
  - `--week W`: week label (2026-W41) or any date in it
  - `--span A..B`: an explicit span, YYYY-MM-DD..YYYY-MM-DD
- **`list`**: The program's interference rules with their params, and every rule available

### `library`

The exercise library: the builtin catalogue plus the athlete's own entries and load modes.

- **`confirm`** (W): Confirm the proposed load mode of the named exercises, or of every unconfirmed one with --all
  - `ID` (argument): library exercise ids
  - `--all`: every instance entry with a proposal and no confirmed mode
- **`create`** (W): Create a custom exercise from an instance-entry JSON file; preview with --dry- run
  - `id` (argument): new custom_ library exercise id
  - `--input FILE` (required): one exercise_library entry with required facts and a confirmed load_mode
- **`list`**: List every library exercise with its confirmed load mode
  - `--avoided`: only the exercises the athlete avoids, with the reason
- **`search`**: Find exercises by name, alias, Hevy title or id
  - `text` (argument): words to look for
- **`seed`** (W): Match every exercise in the cached Hevy routines to the library and record a proposed load mode
- **`set-avoid`** (W): Record that the athlete cannot or will not do an exercise, with the reason; --clear removes it
  - `id` (argument): library exercise id
  - `--reason REASON`: why the athlete avoids it, in plain words
  - `--clear`: the athlete no longer avoids it
- **`set-mode`** (W): Record the athlete's load mode for one exercise
  - `id` (argument): library exercise id
  - `mode` (argument): one of total, per_hand_x2, single_implement, bodyweight, assisted, band, duration, distance
- **`set-template`** (W): Choose a cached Hevy exercise template for a library exercise (local only)
  - `id` (argument): library exercise id
  - `template_id` (argument): cached Hevy template id
- **`show`**: Show one exercise: the catalogue entry merged with the instance file
  - `id` (argument): library exercise id
- **`validate`**: Validate the catalogue and data/exercises.json; exit 1 with the JSONPath of each problem

### `log`

The manual lifting log for athletes without Hevy.

- **`add`** (W): Validate a drafted workout, append it to the manual log and sync history
  - `--input FILE` (required): JSON workout line without id and logged_at, as log prefill gives it
  - `--again`: a second workout for the same date and session
- **`list`**: The logged workouts no void removes, oldest first
  - `--since DATE`: only workouts on or after this date
- **`prefill`**: A workout draft for one session as prescribed, and what to ask the athlete before log add
  - `--session ID` (required): session id, e.g. session-a
  - `--date DATE` (required): the day it was trained
- **`void`** (W): Remove a logged workout and sync history; its line stays in the log
  - `id` (argument): workout id, e.g. manual:2026-10-12-session-a-1
  - `--reason TEXT` (required)

### `meals`

Meal plans: the standing week, building, rendering, approving and the shopping list.

- **`approve`** (W): Stamp the athlete's approval: approved_at and the hash any later edit breaks
  - `ID` (argument): meal plan id: its first day, e.g. 2026-10-12
- **`build`** (W): Resolve a draft of the week's exceptions into data/nutrition/plans/<id>.json; returns the plan and its rendered page
  - `--input FILE` (required): the draft (meal_plan_draft schema)
- **`render`** (W): Write nutrition/plans/<id>.md from the plan
  - `ID` (argument): meal plan id: its first day, e.g. 2026-10-12
- **`shopping`**: The plan's shopping list as markdown, or as a GitHub issue title and body (approved plans only)
  - `ID` (argument): meal plan id: its first day, e.g. 2026-10-12
  - `--format {markdown,issue}`: default: markdown
- **`show`**: One meal plan and whether its approval holds
  - `ID` (argument): meal plan id: its first day, e.g. 2026-10-12
- **`template`**: The standing week from [nutrition.template] and the anchors, before any exceptions, open slots marked
  - `--week D`: any date in the week, or YYYY-Www (default: the week ahead)
- **`validate`**: Check one meal plan's schema and arithmetic
  - `ID` (argument): meal plan id: its first day, e.g. 2026-10-12

### `migrate`

Schema migrations for the data files after a framework update.

- **`run`** (W): Upgrade every data file behind its schema version: back up, migrate, validate, write, git add; never commits
- **`status`**: List each owned data file with its schema version and the version this coach reads

### `missed`

Missed sessions and the program's missed-day rules.

- **`apply`** (W): After the athlete's "go": write the miss, the mid-week overlay (unapproved) and the record lines
  - `--session S` (required): the missed session's id
  - `--date D` (required): the day it was planned
  - `--tag {time,sleep,ill,family,skipped,other}`: why it was missed
  - `--move-to D`: the athlete's choice: move the session to this free day, this week only
  - `--drop`: the athlete's choice: drop the session this week
- **`list`**: Planned sessions dated before D (default today) in the overlay in force with no workout
  - `--date D`: list sessions dated before this day (default today)
- **`plan`**: What the matching missed-day rule, or the athlete's chosen move or drop, does to the rest of the week: summary, write line, draft overlay and each later day's status for a move
  - `--session S` (required): the missed session's id
  - `--date D` (required): the day it was planned
  - `--move-to D`: the athlete's choice: move the session to this free day, this week only
  - `--drop`: the athlete's choice: drop the session this week
- **`rules`**: The program's missed-day rules, each in plain words

### `niggles`

Niggles and the load constraints they impose.

- **`add`** (W): Log a new niggle, the movements it affects and the load limits it sets
  - `--area TEXT`: where it is, e.g. "left knee"
  - `--status {aggravated,watching,easing,resolved,chronic}`: default watching
  - `--note TEXT`: the report, one line
  - `--date D`: the day the report describes, YYYY-MM-DD (default today); a week's fatigue check counts only reports dated inside it
  - `--pattern A[,B...]`: movement pattern(s) it affects, comma-separated or repeated; "" clears
  - `--exercise A[,B...]`: library exercise id(s) it affects, comma-separated or repeated; "" clears
  - `--activity-kinds K[,K...]`: activity kinds it affects (run, ride, ...); "" clears
  - `--constraint KIND[=VALUE]`: a standing load limit from the report's day, while its status applies it: rpe_cap=7, no_added_load, load_cap=20; repeat for several; replaces the standing limits
  - `--flare-constraint KIND[=VALUE]`: a temporary load limit from the report's day until the status changes, on top of the standing ones: rpe_cap=6; repeat for several
  - `--constrain-while S[,S...]`: statuses its constraints apply in (default aggravated,watching)
  - `--notes TEXT`: its standing notes
- **`constraints`**: Each program line a niggle constrains on a date (today by default), with the standing and flare limits in force then
  - `--session S`: one program session only
  - `--date YYYY-MM-DD`: the date to read; default today
- **`import`** (W): Convert profile.md's niggle log table into data/niggles.json, once; the dry run also numbers the Injuries / limitations lines for --chronic
  - `--from-profile` (required): read profile.md
  - `--chronic I[,I...]`: section lines that are lasting limitations: imported as chronic rows; unmarked lines are not imported
- **`list`**: Niggles with whether their constraints are active today and any escalation
  - `--open`: leave out resolved rows
  - `--status {aggravated,watching,easing,resolved,chronic}`: only rows with this status
- **`resolve`** (W): Mark a niggle resolved; the row is kept, since a recurrence is the signal
  - `ID` (argument): niggle id, e.g. n-0001
  - `--note TEXT`: the report, one line
  - `--date D`: the day the report describes, YYYY-MM-DD (default today); a week's fatigue check counts only reports dated inside it
- **`update`** (W): Record a check-in report on a niggle (status, note, mention) or change what it applies to and its limits
  - `ID` (argument): niggle id, e.g. n-0001
  - `--status {aggravated,watching,easing,resolved,chronic}`: its status as of the report's day
  - `--note TEXT`: the report, one line
  - `--mention`: the athlete reported it: bump mentions and last noted (once a day)
  - `--date D`: the day the report describes, YYYY-MM-DD (default today); a week's fatigue check counts only reports dated inside it
  - `--area TEXT`: rename where it is
  - `--clear-constraints`: remove every standing limit from the report's day
  - `--clear-flare-constraints`: end the flare's limits on the report's day
  - `--pattern A[,B...]`: movement pattern(s) it affects, comma-separated or repeated; "" clears
  - `--exercise A[,B...]`: library exercise id(s) it affects, comma-separated or repeated; "" clears
  - `--activity-kinds K[,K...]`: activity kinds it affects (run, ride, ...); "" clears
  - `--constraint KIND[=VALUE]`: a standing load limit from the report's day, while its status applies it: rpe_cap=7, no_added_load, load_cap=20; repeat for several; replaces the standing limits
  - `--flare-constraint KIND[=VALUE]`: a temporary load limit from the report's day until the status changes, on top of the standing ones: rpe_cap=6; repeat for several
  - `--constrain-while S[,S...]`: statuses its constraints apply in (default aggravated,watching)
  - `--notes TEXT`: its standing notes

### `nutrition`

Nutrition readings, status and protein targets.

- **`import`** (W): Merge a list of readings seeded once from archived check-ins; each is stored with source "seeded"
  - `--input FILE` (required): JSON: a list of readings, or {"readings": [...]}
  - `--replace`: overwrite a reading already on file for the same date
- **`readings`**: The nutrition readings series, oldest first
  - `--last N`: only the newest N readings
- **`record`** (W): Add one reading from the athlete's check-in reply: the app's numbers, or morning weigh-ins without one
  - `--date DATE`: the check-in date, YYYY-MM-DD (default: today)
  - `--trend-weight X`: the app's trend weight, in bodyweight units
  - `--scale-weight X`: no app: the mean of the week's morning weigh-ins
  - `--expenditure N`: the app's expenditure, kcal
  - `--target-kcal N`: the app's calorie target
  - `--target-protein N`: the app's protein target, g
  - `--avg-kcal N`: 7-day average calories
  - `--avg-protein N`: 7-day average protein, g
  - `--days-logged N`: days logged of the last 7
  - `--anchors {yes,no}`: protein anchors eaten most days
  - `--note S`: one line of context
  - `--replace`: overwrite a reading already on file for the same date
- **`status`**: Targets in force, the latest reading, the weight trend, the override and the flags; also the brief line and the food questions
- **`targets`**: The protein reference mass and the floor, target and stretch set from it; names any input still missing
  - `--bodyweight X`: bodyweight in [athlete] bodyweight_units (default: the newest weigh-in, Hevy body measurement or nutrition reading weight from the last 14 days)
  - `--goal-weight X`: goal weight (default: [nutrition] goal_weight)
  - `--body-fat PCT`: a body-fat reading, in %; needs --body-fat-source
  - `--body-fat-source {credible,rough}`: credible: DEXA, a BodPod, underwater weighing or skinfolds by an experienced tester, from the last ~3 months; rough: anything else, such as a smart scale or a tape method
  - `--sex {male,female}`: judges a rough body-fat reading
  - `--height N`: for the BMI cue with a rough or absent body-fat reading
  - `--height-unit {cm,in}`: default: cm with kg bodyweight, in with lb
  - `--recent-intake G`: recent average protein a day, g (default: the newest reading's 7-day average from the last 14 days)
  - `--app {macrofactor,none}`: the nutrition app (default: [nutrition] app); only "none" gets a calorie estimate
  - `--age YEARS`: for the calorie estimate
  - `--activity {sedentary,active,vigorous}`: for the calorie estimate, the lifestyle of a typical day judged from the job, walking and how long and how hard each session is, not from steps alone: sedentary: sedentary or lightly active, such as a seated job with everyday walking and two or three training sessions a week; active: active or moderately active, an on-your- feet job or about an hour of moderate-to-vigorous exercise a day on top of a seated one; vigorous: vigorously active, hard physical work for several hours a day, or an on-your-feet job plus about two hours of strenuous exercise a day
  - `--phase PHASE:RATE`: a phase and its weekly rate in bodyweight units, such as cut:-0.5; repeat for each phase (default: [nutrition] phase and target_rate_per_week)

### `overlay`

Overlays: list, validate, build, render and approve the week's prescription.

- **`approve`** (W): Stamp the athlete's approval: approved_at and the hash any later edit breaks
  - `ID` (argument): overlay id, e.g. 2026-10-12-weekly
- **`build`** (W): Build an overlay from a draft in athlete units and write data/overlays/<id>.json
  - `--input FILE` (required): the draft (overlay_draft schema); leave out id for a new overlay, give it to rebuild one
- **`current`**: Which overlay is in force on a date, and its sessions that day
  - `--date D`: YYYY-MM-DD (default: today)
- **`list`**: List every overlay with its span, kind and approval
- **`notes`**: The Hevy note for every exercise, per session (first exercise carries the week line)
  - `ID` (argument): overlay id, e.g. 2026-10-12-weekly
  - `--session S`: only this session id
- **`render`** (W): Render the check-in's week-ahead region; with --into, write it into that file
  - `ID` (argument): overlay id, e.g. 2026-10-12-weekly
  - `--into FILE`: the check-in record whose marked region to write
- **`validate`**: Validate one overlay (ID or --file), or every overlay in data/overlays
  - `ID` (argument): overlay id
  - `--file PATH`: an overlay file anywhere, e.g. one not yet written

### `pages`

The standing pages: render, show, plan the commit and publish.

- **`plan`**: The training records a programming pass's brief names for commit with the pages: changed now, or written by the steps its "go" approves
  - `--structural`: a structural change: data/program.json and routine/program.md
  - `--session ID`: with --structural: a session it edits, adds or removes (its routine/ page); repeat for each
  - `--light-week`: block decide records a light week: data/blocks.json, data/decisions.json, data/state.json, routine/program.md
  - `--one-off`: a one-off week is set, or an ended one cleared: data/state.json
  - `--create-routines`: routines create records new ids: data/state.json
  - `--missed`: missed apply records a matched miss: data/history/annotations.json
- **`publish`** (WG): Re-render the pages, then commit them with the approved overlay and the newest record, and push
  - `--overlay ID` (required): the approved overlay of the programming pass
  - `--record D`: the check-in record's date (default: the newest record)
  - `--include PATH`: a training-record file the approved brief's commit plan named; repeat for each
  - `--structural`: allow data/program.json, when the brief's approved structural change named it
- **`render`** (W): Render this-week.md (the brief), README.md (the dashboard) and progress.md as of now
  - `--only {brief,dashboard,progress}`: render one page
  - `--replace-readme`: replace a README.md that coach did not generate with the dashboard
- **`show`**: One page as a fresh render would write it now, without writing it
  - `{brief,dashboard,progress}` (argument): brief, dashboard or progress

### `planned`

Planned activities such as the runs on a run plan.

- **`add`** (W): Record a planned activity by hand
  - `--date DATE` (required)
  - `--kind {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}` (required)
  - `--title TITLE` (required)
  - `--quality`: intervals, tempo, threshold, hills or a race
  - `--distance-km KM`
  - `--distance-mi MI`
  - `--distance-m M`
  - `--duration-min MIN`
  - `--start TIME`: when it starts: HH:MM on --date in [athlete] timezone, or an ISO 8601 timestamp (with an offset, or local time)
  - `--description DESCRIPTION`: the target in words, such as "Zone 2"
  - `--notes NOTES`
  - `--again`: a second session identical to one already planned that day
- **`list`**: Planned activities in a span; two sources planning one day both show
  - `--from DATE`: first day (default: the start of this week)
  - `--to DATE`: last day (default: the end of this week)
  - `--kind {run,ride,swim,row,walk,hike,conditioning,sport,mobility,other}`: only this kind (repeatable)
- **`void`** (W): Remove a planned activity from every view; its history stays in the file
  - `id` (argument)
  - `--reason TEXT` (required)

### `plugins`

Instance plugins: list, show and validate them.

- **`list`**: Every plugin, framework and instance, by kind
  - `--kind {scheme,schedule,transform,interference,conditioning}`: only this kind
- **`show`**: One plugin's summary, parameters, state and cited claims
  - `NAME` (argument): plugin name
- **`test`**: Run the instance plugins' tests in plugins/tests/ (runs instance code)
- **`validate`**: Check every plugin against the contract: shape, schemas, purity, no x2, instance names and tests

### `prescription`

Prescription validity: check an overlay's loads against their exposure windows.

- **`check`** (W): Check every prescription line: still earned after days off, under cap, buildable from the kit, feasible at its RPE, in the library's load mode, and in a session that fits its time cap
  - `--overlay ID`: an overlay in data/overlays
  - `--file PATH`: an overlay or an overlay draft anywhere
  - `--write`: merge the flags into the overlay and fill each hand-built line's inferred provenance

### `program`

The program: show, validate, render, import from Hevy, adopt a draft, reconcile a load mode.

- **`adopt`** (W): Validate a program draft and make it the program: archive the old one (--replace), write program and state, render routine/, git add; never commits
  - `--input FILE` (required): the program draft
  - `--replace`: archive the existing program and replace it
  - `--position P`: the rotation position to start at; default: the draft's, else the schedule rule's first
- **`import-hevy`** (W): Turn the cached Hevy routines into a program draft (default .coach/drafts/program.json); every exercise needs a confirmed load mode
  - `--routine ID`: import only this routine; repeat for several
  - `--folder ID`: import only the routines in this Hevy folder
  - `--out FILE`: where to write the draft
- **`reconcile-mode`** (W): Bring every line of one exercise to the library's confirmed load mode, after the athlete says what its start load meant: --basis old converts it from the line's mode, --basis confirmed keeps the number
  - `id` (argument): library exercise id
  - `--basis {old,confirmed}` (required): old: the start load was meant in the line's current mode; confirmed: it already meant the confirmed mode
  - `--input FILE`: a program draft to reconcile instead of data/program.json
- **`render`** (W): Render routine/program.md and one page per session from data/program.json
- **`show`**: Show data/program.json, with absent optional keys filled
- **`validate`**: Validate data/program.json against the schema, the exercise library and config; exit 1 with JSONPaths

### `propose`

The proposal pipeline that builds a week's draft overlay.

- **`discard`** (W): Remove an abandoned draft and any unapproved overlay finalized from it; approved work stays
  - `--proposal ID` (required): proposal id, from propose week
- **`finalize`** (W): Write the proposal as data/overlays/<id>.json, with its decisions and pending scheme state
  - `--proposal ID` (required): proposal id, from propose week
- **`note`** (W): Set a proposal's week focus, or one slot's target note, focus or cues; guidance needs no override reason
  - `--proposal ID` (required): proposal id, from propose week
  - `--week-focus TEXT`: the week's focus line, on the record, sheets and brief
  - `--session S`: program session id of the line
  - `--exercise E`: library exercise id of the line
  - `--target-note TEXT`: the line's note to the athlete; an empty value clears it
  - `--focus TEXT`: the line's focus; an empty value clears it
  - `--cues TEXT`: the line's cues for this week; an empty value clears them
- **`override`** (W): Change one line of a proposal with a reason, keeping the original in override.proposed_sets
  - `--proposal ID` (required): proposal id, from propose week
  - `--session S` (required): program session id
  - `--exercise E` (required): library exercise id
  - `--sets SPEC`: working sets, e.g. "3x5@100 rpe7" or "1x5@100 rpe8, 3x5@90 rpe7"; a rep-out set "1x5+@120" (RPE 9 stop unless rpe is given); seconds for a duration line, e.g. "2x35s rpe7"
  - `--load N`: one load for every working set (athlete units, per hand for per-hand modes)
  - `--reason TEXT` (required): why the line changes
  - `--date D`: change the line on this date only (default: every date of the slot)
  - `--standing`: keep this choice in later weeks until --until
  - `--until D`: end date of a standing override (default four weeks; eight at most)
- **`rebuild`** (W): Propose a draft's span again from the program as it is now, keeping its explained edits and resolutions
  - `--proposal ID` (required): proposal id, from propose week
- **`resolve`** (W): Resolve one flag of a proposal with the reason it stands
  - `--proposal ID` (required): proposal id, from propose week
  - `--flag REF` (required): the flag's ref (code:digest) from propose week, show or override
  - `--resolution TEXT` (required): how the flag is settled
- **`restore`** (W): Put back a conditioning session the drop rule removed from a proposal, resolving its flag with the reason
  - `--proposal ID` (required): proposal id, from propose week
  - `--session S` (required): program session id of the dropped session
  - `--reason TEXT` (required): why the session goes back in
- **`show`**: Show a proposal draft built as an overlay, its lines and what finalize would refuse
  - `ID` (argument): proposal id
- **`time`** (W): Set when one session of a proposal starts and how long it lasts, or clear it, and judge the interference rules again; finalize afterwards
  - `--proposal ID` (required): proposal id, from propose week
  - `--session S` (required): program session id
  - `--date D`: the session's date, when the proposal holds it twice
  - `--start TIME`: HH:MM on the session's date in [athlete] timezone, or an ISO 8601 timestamp (with an offset, or local time)
  - `--duration-min MIN`: how long the session lasts, in whole minutes
  - `--clear`: remove the session's start and duration
- **`week`** (W): Propose a week's overlay from the program, state, history and decisions; write an editable draft
  - `--week W`: week label (2026-W42) or any date in it; default: the week holding tomorrow
  - `--span A..B`: an explicit span, YYYY-MM-DD..YYYY-MM-DD, instead of a week
  - `--kind {weekly,midweek,deload}`: weekly (default), midweek or deload
  - `--transform NAME`: the week transform for this run (default for a deload: the program's deload rule)
  - `--plan FILE`: dated sessions from a schedule plan file instead of the schedule rule

### `recipes`

The recipe bank: list, show, validate, import, draft, render and convert cards.

- **`convert`** (W): Convert old YAML cards: --parse returns drafts and a review table; --apply --input FILE writes them
  - `--parse`: read the old cards and return drafts; writes nothing
  - `--apply`: write the reviewed cards from --input, with a backup
  - `--input FILE`: the reviewed drafts: {cards: [{slug, card}]}
- **`draft`**: Turn a JSON draft ({slug, card, prose}) into the full card text, validated; writes nothing
  - `--input FILE` (required)
- **`import`**: Read a saved recipe page's schema.org JSON-LD into a draft card; writes nothing
  - `--html FILE` (required): the saved page
  - `--url URL`: the page's address, recorded as the card's source
- **`list`**: List the recipe cards
  - `--slot SLOT`: only cards that fit this slot
  - `--status {active,benched}`
- **`render`** (W): Rewrite each card's rendered region and the index from the data blocks
  - `slug` (argument)
- **`show`**: Show one card's data
  - `slug` (argument)
- **`validate`**: Check every card (schema, macro sum, protein density, variations, aisles); exit 1 on a fail
  - `slug` (argument)

### `research`

Research notes and their claims: status, show, cites, validate and render.

- **`cites`**: List every claim reference in the framework and instance files
  - `--unresolved`: only references that do not resolve
- **`render`** (W): Rewrite the rendered region of one note, or of every note; nothing else
  - `ID` (argument): a note id (default: every note)
- **`show`**: Show one note (by id) or one claim (by rn:<note-id>.<n>) with its sources
  - `REF` (argument): a note id or a claim ref
- **`status`**: List research notes with their review status, local supersessions and area status
  - `--area {volume,frequency,proximity_to_failure,progression,deload,autoregulation,concurrent_training,return_to_training,minimum_dose,bodyweight_skills,protein,energy_balance,sleep,rehab,exercise_selection}`: only notes covering this area
  - `--kind {template,local}`: only notes of this kind
  - `--expired`: only expired notes
- **`validate`**: Validate every research note; exit 1 if any is invalid

### `routines`

Hevy routines: preflight, diff, verify, push, create and retire.

- **`create`** (WH): Create the Hevy routines (and the one-off folder) an approved overlay's sessions lack; ids go in state.json
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
  - `--reuse SESSION=ROUTINE`: explicit managed routine reuse
  - `--expect-plan EXPECT_PLAN`: hash of the exact create dry-run approved in the brief
- **`diff`** (WN): Compare each routine in an overlay's span with the cached Hevy routine; empty means nothing to write
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
  - `--refresh`: re-read the overlay's routines from Hevy into the cache first
- **`preflight`**: List every local Hevy mapping requirement before the write brief
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
- **`push`** (WH): Write an approved overlay to its Hevy routines, read each back and log the result
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
  - `--refresh`: re-read the overlay's routines from Hevy into the cache first
- **`retire`** (WH): Retitle named managed orphans or an ended overlay's temporary routines "(unused)"
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
  - `--routine ROUTINE`: managed orphan or ended temporary routine id
  - `--expect-plan EXPECT_PLAN`: hash of the exact retirement dry-run approved in the brief
- **`verify`** (WN): Report, per routine, whether Hevy matches the overlay
  - `--overlay ID` (required): overlay id, e.g. 2026-10-12-weekly
  - `--refresh`: re-read the overlay's routines from Hevy into the cache first

### `schedule`

The week's schedule plan and the rotation position.

- **`confirm`** (W): Record the rotation position the athlete confirmed for a week
  - `--position P` (required): a position of the schedule rule, e.g. week-b
  - `--week W`: the week it names; default: the week holding tomorrow
- **`plan`**: The dated sessions the program's schedule rule plans for a week, and its rotation
  - `--week W`: week label or any date in it; default: the week holding tomorrow

### `sheets`

Session sheets for athletes without Hevy.

- **`render`** (W): Write this-week-sheets.md: each session of the week's overlay as per-set tables
  - `--overlay ID`: overlay id (default: the brief's overlay, else the next one)

### `starters`

Starter programs that ship with the framework.

- **`draft`** (W): Draft a starter program onto the athlete's days, start loads and equipment (default .coach/drafts/program.json) for program adopt
  - `ID` (argument): the starter id, as starters list prints it
  - `--days mon,wed,fri`: the training days; default: [athlete] available_days when set, else the starter's own
  - `--start-load EXERCISE=VALUE`: a known working load in your units (per hand for dumbbells); repeat for each lift
  - `--location NAME`: train every session at [equipment.locations.NAME] and fit the draft to its kit
  - `--out FILE`: where to write the draft
- **`list`**: The starter programs that fit a day count and the equipment (default: [equipment] available), with the swaps each needs and the ones that suit [athlete] experience and fit the kit marked
  - `--days N`: training days a week; lists starters that take N days
  - `--equipment E,...`: equipment ids available; default: [equipment] available
  - `--location NAME`: judge the kit at [equipment.locations.NAME] instead of the main place
- **`show`**: One starter program and the session pages it renders with its default days
  - `ID` (argument): the starter id, as starters list prints it

### `state`

The program state: show it, set a training max.

- **`set-training-max`** (W): Set a wave slot's training max explicitly, with the reason the athlete agreed; preview with --dry-run
  - `--session S` (required): program session id
  - `--exercise E` (required): library exercise id
  - `--value N` (required): the new training max (athlete units, per hand for per-hand modes)
  - `--reason TEXT` (required): why it changes, as agreed with the athlete
- **`show`**: Show data/state.json after checking it against the schema and the program

### `stats`

Derived statistics: e1RM, adherence, dose, durations and an audit.

- **`adherence`**: Planned sessions against logged workouts: trained, missed (with tag) or upcoming, and each exercise hit, under, over or missing
  - `--overlay ID`: one overlay's sessions
  - `--span A..B`: the sessions in force on each day of a span
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written
- **`audit`**: Dumbbell exposures that jumped exactly 2× or ½× at the same reps and RPE: likely logging slips
  - `--weeks N`: how many weeks back to look (default 8)
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written
- **`dose`**: Hard sets delivered per muscle, direct and fractional (indirect sets count half)
  - `--week W`: a week label (YYYY-Www) or any date in it
  - `--span A..B`: a span of dates
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written
- **`durations`**: Each workout's minutes against its session cap ([sessions.cap_minutes], else [athlete] session_minutes)
  - `--span A..B`: a span of dates (default: every workout)
  - `--week W`: a week label (YYYY-Www) or any date in it
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written
- **`e1rm`**: e1RM series per lift: the best set of each usable exposure (Epley, reps in reserve when RPE is logged)
  - `--exercise ID`: one library exercise id
  - `--since D`: first date, YYYY-MM-DD
  - `--include-unsynced`: also apply source changes not yet synced (new, changed and removed workouts), in memory; nothing is written

### `status-days`

Status days: ill, injured, travelling, on a planned break.

- **`add`** (W): Record days ill, injured or travelling; leave out --to while it is still going on; --no-training marks a planned break
  - `--kind {ill,injured,travel}` (required)
  - `--from D` (required): first day
  - `--to D`: last day (default: ongoing until status-days end)
  - `--note TEXT` (required): one line, e.g. "head cold"
  - `--source TEXT`: where it came from, e.g. "check-in 2026-10-11"
  - `--no-training`: the athlete agreed not to train on these days (travel or injured only); travel alone is not a break
- **`end`** (W): Give an ongoing status day its last day
  - `ID` (argument): status day id, e.g. s-0001
  - `--date D` (required): the last day
- **`list`**: Status days, oldest first
  - `--active`: only rows not withdrawn
- **`withdraw`** (W): Withdraw a wrong status day; the row stays, marked withdrawn
  - `ID` (argument): status day id, e.g. s-0001
  - `--reason TEXT` (required)

### `structure`

Structure accounting: weekly balance, adherence, priority lifts, the minimum week and structural decisions.

- **`adherence`**: Sessions trained over planned across the last four ordinary weeks, coach-led included, with its flags
  - `--until D`: the last day a counted week may end on (default: today)
- **`balance`**: Weekly sets per muscle the program plans on core and coach-led sessions, against its dose targets
  - `--program FILE`: a candidate to check instead: a program draft (.coach/drafts/program.json) or a bare program; compared with data/program.json for new sessions when one is adopted
  - `--variant {minimum}`: minimum: check the minimum week (at most two sessions within their caps, every priority floor, a third of the corresponding ordinary week's planned dose); exit 1 names each reason it fails
- **`decide`** (W): Record the athlete's answer to the adherence trigger, or an override for a new session, and print its line for the check-in record
  - `--rule {restructure,add_session}` (required): restructure (the under-70 % smaller schedule) or add_session (an under-80 % override)
  - `--outcome {adopted,declined,deferred}` (required): what the athlete chose
  - `--reason TEXT`: why; required when declined, and names the session an override adds
  - `--revisit D`: for deferred: the date the proposal comes back
- **`minimum`** (W): The minimum week's dated sessions for a week, as a schedule plan file for propose week --plan
  - `--week W`: a week label (YYYY-Www) or any date in it; default: the week holding tomorrow
  - `--write`: write the plan to .coach/plans/<week start>-minimum.json
- **`priority`**: Each priority lift's KPI now and its trend, and its exposures per week against plan, with priority_exposures_missed
  - `--since D`: the first day of the trend and the week rows (default: four weeks ago)
- **`week`**: One week's sessions (core, optional, coach-led) and per-muscle target, planned, delivered and bonus sets
  - `--week W`: a week label (YYYY-Www) or any date in it; default: the week holding today

### `units`

Load formatting, conversion and rounding, with the Hevy value where it applies.

- **`convert`**: Convert between the value the athlete sets and Hevy's weight_kg
  - `--mode {total,per_hand_x2,single_implement,bodyweight,assisted,band,duration,distance}` (required): the exercise's load mode
  - `--from-hevy-kg FROM_HEVY_KG`: Hevy's weight_kg, converted to the value the athlete sets
  - `--value VALUE`: the value the athlete sets, converted to Hevy's weight_kg
  - `--unit {kg,lb}`: athlete units (default: [athlete] units in config.toml)
- **`format`**: Build a load object and the text every page prints for it
  - `--mode {total,per_hand_x2,single_implement,bodyweight,assisted,band,duration,distance}` (required): the exercise's load mode
  - `--value VALUE`: per hand for per-hand modes, else the total
  - `--unit {kg,lb}`: athlete units (default: [athlete] units in config.toml)
  - `--no-hevy`: leave the Hevy value out, as pages do with Hevy off
- **`load-for`**: The load an e1RM gives for reps at an RPE: the unrounded model load, and with --increment the load a grid of that step makes
  - `--e1rm E1RM` (required): the e1RM, in the exercise's coaching number
  - `--reps REPS` (required)
  - `--rpe RPE`: the target RPE (1–10); without it the reps are taken to failure
  - `--increment INCREMENT`: an equipment grid step: also report the heaviest load on it no heavier than the model load
- **`round`**: Round a value to a whole number of increments
  - `--value VALUE` (required)
  - `--increment INCREMENT` (required)
  - `--direction {nearest,down,up}`

### `wellness`

Wellness records: sleep, resting heart rate, steps and body mass.

- **`add`** (W): Record wellness by hand for one day (the day you woke) or a span; adding again updates that record
  - `--date DATE`: one day
  - `--from DATE`: first day of a span, such as a week's average
  - `--to DATE`: last day of the span
  - `--sleep-hours H`: hours asleep (a span: the average per night)
  - `--in-bed-hours H`
  - `--resting-hr BPM`
  - `--steps STEPS`
  - `--body-mass MASS`: in [athlete] bodyweight_units
  - `--body-fat-pct PCT`
- **`list`**: One resolved wellness day per date in the span that has any value
  - `--from DATE`: first day (default: the start of this week)
  - `--to DATE`: last day (default: the end of this week)
- **`summary`**: Sleep average with nightly and period-mean provenance
  - `--from DATE`: first day (default: the start of this week)
  - `--to DATE`: last day (default: the end of this week)
- **`void`** (W): Remove a wellness record from every view; its history stays in the file
  - `id` (argument)
  - `--reason TEXT` (required)
