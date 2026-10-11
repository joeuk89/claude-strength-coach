---
name: setup
description: Use for first-run onboarding of this training workspace — when profile.md doesn't exist, the user is new, or they ask to get set up. Triggers include "/setup", "get me set up", "set up hevy", "initialise this", or any session in a copy of the template where profile.md is missing.
---

# First-run setup

Take a fresh copy of the template to an approved first week in about ten
replies from the athlete: three settings questions, six profile
questions, a program, then week one. Each step checks whether it's
already done and skips it, so `/setup` is safe to re-run and resumes
cleanly after a partial run. It's also how the athlete **reconfigures**
later: on a set-up workspace, report each step's state and ask what they
want to change.

Keep the messages few and full: ask each step's questions together, as
the step says, never one at a time. Every answer a script reads goes into
`config.toml` or through a `coach` command, not into prose.

## 0. State check

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. On a first run
the `config` check fails because there is no `config.toml` yet — that
is expected, and step 1 creates it. If `routine/` exists but
`data/program.json` does not, this workspace still keeps its program as
hand-written pages: say it needs its one-time bootstrap migration onto
`data/program.json` first, and stop. When a command fails, tell the
athlete what its exit code means, as `CLAUDE.md` "The coach scripts"
sets out.

Then look at what exists: `config.toml`, `profile.md`,
`data/program.json` and an approved overlay (`python3 -m coach overlay
current`). Continue from the first step that isn't done. If every step
is done, report each one's state and ask what the athlete wants to
change.

## 1. Three questions, then `config.toml`

Skip when `config.toml` exists and `python3 -m coach config validate`
exits 0. On a re-run, report the three answers from `python3 -m coach
config show` and ask what to change.

Welcome the athlete in two lines: this repo plans and reviews their
training, their logging app records it, and a weekly `/check-in` keeps
it on track. Then ask, in one message:

- **Hevy:** Pro, free, or not at all? The coach reads logs and writes
  routines only through Hevy Pro's API.
- **Units:** kg or lb?
- **Nutrition coaching:** yes, no, or later?

With the reply:

1. Run `python3 -m coach config suggest --unit <kg|lb>`. Its
   `data.values` are the settings to write; its `data.notes` say what to
   confirm with the athlete (such as the heaviest dumbbell). Fold those
   into profile question 5 rather than asking now.
2. Copy `config.example.toml` to `config.toml` and set, with the Edit
   tool:
   - `[athlete]`: `units` and `bodyweight_units` from `data.values`.
     Leave `week_starts` and `timezone` as the example has them (Monday;
     this computer's local time) unless the athlete says otherwise.
   - `[equipment]`: every key in `data.values`, uncommenting it. Step 4
     sets `available` and `dumbbells`.
   - `[hevy]`: `enabled` — `true` for Pro, `false` for free or none
     (free has no API, so the coach works as if there were no Hevy).
   - Nutrition: on a yes, leave `[nutrition]` out; step 7 sets it up
     after week one. On a no, add a `[nutrition]` table holding only
     `enabled = false`. On a later, leave it out. For a no or a later,
     note "`/goals` sets up nutrition coaching whenever you want it" for
     the close-out.
3. Run `python3 -m coach config validate`. Exit 5 names the file and key
   to fix; fix it and run it again until it exits 0.

## 2. Hevy key (Pro only)

Skip without Hevy Pro, or when `python3 -m coach hevy status` already
reads `key` `present`.

- Send them to **hevy.com → Settings → Developer → generate API key**
  (or in the app: Profile → Settings → Developer). Have them create
  `.env` (copy `.env.example`) and paste the key as `HEVY_API_KEY=...`
  themselves; never echo the key back.
- If they also want to coach from **Claude Code on the web**: the key
  goes in the cloud environment's variables (never in git), and the
  Hevy API's host must be on a **Custom** network allowlist or every
  call fails.
- Once they say it's in: `python3 -m coach hevy status` — `key` must
  read `present` (else the key isn't in `.env` yet). Then `python3 -m
  coach hevy pull` checks the key works: exit 0 is success, exit 5
  means Hevy rejected the key (re-copy it), exit 4 means Hevy couldn't
  be reached (try again shortly).

## 3. Profile: six questions

Skip when `profile.md` exists (offer a refresh instead). Ask these six,
named in one list, in at most two messages: 1 to 3, then 4 to 6.

1. **Name.** Units are known from step 1.
2. **Goal:** what they want from training, in their own words.
3. **Training experience and known working weights:** how long they've
   trained consistently, and any working weights they know for their
   main lifts (weight and reps).
4. **The training week:** which days, about how many minutes per
   session, any coach-led sessions (PT, team training) and their days,
   any classes, any runs.
5. **Equipment, per place they train:** the main place and what it has,
   and each other place with what differs; plus whatever
   `config suggest`'s notes said to confirm.
6. **Injuries and limitations:** anything that hurts or limits training
   now or keeps coming back, and any exercise they cannot or will not
   do.

Don't ask bodyweight, height, age, sleep or recovery here: the first
`/check-in` asks.

## 4. Profile facts into config and data, then `profile.md`

The answers that scripts read go into config and data, not prose:

- **Question 3** → `[athlete] experience`: `"beginner"` under about a
  year of consistent training, `"intermediate"` for steady progress over
  a few years, `"advanced"` beyond that. Keep the working weights for
  step 5's start loads.
- **Question 4** → `[athlete] available_days` (`"mon"` .. `"sun"`) and
  `session_minutes`. Coach-led sessions go into the program in step 5.
  A yes to runs or classes sets `[activity] enabled = true`.
- **Question 5** → `[equipment]` for the main place: `available` (from
  `barbell`, `ez_bar`, `trap_bar`, `dumbbell`, `kettlebell`, `machine`,
  `smith_machine`, `cable`, `plate`, `band`, `suspension`, `bodyweight`,
  `cardio_machine` and `other`; an empty list assumes every piece), `dumbbells` (per-hand
  weights, when the set is limited), `dumbbell_max` and `plates`. If the
  main place is a home gym, run `python3 -m coach config suggest --unit
  <kg|lb> --gym home` and use its values instead. Each other place gets
  one `[equipment.locations.<name>]` table (lowercase letters, digits
  and hyphens) holding only the keys that differ from `[equipment]`.
- **Question 6** → a lasting limitation becomes a niggle: `python3 -m
  coach niggles add --area "<where>" --status chronic --pattern
  <patterns> --constraint <kind=value> --constrain-while chronic --notes
  "<its story>"`. A current, short-term one uses `--status watching`.
  For pain or a suspected injury, also recommend a qualified
  professional (`CLAUDE.md` "Safety & scope"). An exercise they cannot
  or will not do: `python3 -m coach library set-avoid <id> --reason
  "<why>"`, finding the id with `python3 -m coach library search
  <name>`.

Run `python3 -m coach config validate` again until it exits 0.

Then write `profile.md` from this skeleton: prose only a human reads.
Numbers and lists that live in `config.toml` or `data/` are not repeated
in it. Show it in step 5's message, so a correction rides along with the
athlete's next reply.

```markdown
# <Name> — Athlete Profile

The goal, the week and the limits in words. Units, training days,
session length, equipment, niggles and avoided exercises live in
`config.toml` and `data/`.

_Last reviewed: YYYY-MM-DD_

## Goal

(In the athlete's words, plus what it means for the program.)

## Training week

(The weekly shape in words: coach-led sessions and who runs them,
classes, runs, which days are fixed and which can move.)

## Equipment

(Where they train and anything about the kit the config can't say.)

## Injuries / limitations

(Each limitation's story in a line or two. "None currently" is an
answer.)

## Coach's notes

(Per-athlete patterns the coach learns over time. Starts empty.)
```

## 5. Program: three paths

Skip when `data/program.json` exists. Run `python3 -m coach starters
list --days <number of available days>`, then make the **new-program**
skill's three-path offer in one message, with the profile from step 4,
and recommend one path from the answers:

- **A starter:** no program of their own, and a week a starter fits.
  Name `starters list`'s `recommended_id`.
- **An import from Hevy:** they already run a program in Hevy Pro.
- **A design:** the week or goal needs a program built for it, such as
  coach-led sessions to plan around, a sport, or unusual kit or limits.

Then follow that path in the **new-program** skill:

- **Starter path** (its Path C): `python3 -m coach starters draft <id>
  --dry-run`, then the same without `--dry-run`, adding `--start-load
  <exercise id>=<load>` for each working weight from question 3, by the
  ids in the preview's `program.priority`. Don't ask for the weights
  again.
- **Import path** (its Path A): `python3 -m coach library seed`,
  `python3 -m coach library confirm`, then `python3 -m coach program
  import-hevy`. Ask once: **run it as written, or coach it?** Write
  `[coaching] mode` from the answer: `"run"` to run their program as
  written, `"coach"` (the default) to have it reviewed and improved.
  Then finish the draft as Path A says.
- **Design path** (its Path B): the design conversation, ending in a
  draft at `.coach/drafts/program.json`.

On every path, add each coach-led session from question 4 to the
draft's `program.external_sessions` (the shape is in
`coach/schemas/program.schema.json`). Then run `python3 -m coach program
adopt --input .coach/drafts/program.json --dry-run` and show, in one
message, the draft's report as one table and the load-mode table from
step 6, and ask to adopt. On a yes, run it without `--dry-run`. Never
write `data/program.json` yourself.

## 6. Week one

**Confirm the load-mode table once.** Adopt's `unconfirmed` lists every
exercise without a confirmed load mode. Show it as one table (exercise,
load mode, and how the athlete sets the weight: one total, per hand, or
one dumbbell) in step 5's adopt message. With their yes, record every
row: `python3 -m coach library set-mode <id> <mode>`, or `python3 -m
coach library confirm <ids>` for rows an import proposed, changing any
row they correct. Never ask about it again.

Then run week one through the **program-week** skill: it runs `python3
-m coach propose week`, builds and checks the overlay, presents the
coach's brief and stops at the approval gate. The athlete's "go"
approves the week and its writes.

## 7. Nutrition (only when the athlete said yes in step 1)

Skip this step unless the athlete said yes to nutrition coaching in
step 1. It runs after week one is approved, never before. Invoke the
**goals** skill (`/goals`): it asks the nutrition questions, sets
`[nutrition]` in `config.toml` and adds the "Nutrition & goals" section
to `profile.md`.

## 8. Close out

- Recap in a few lines: settings, profile, program and the approved
  week one.
- Name what was deferred: anything step 1 noted, any step the athlete
  postponed, and that the first `/check-in` asks bodyweight and
  recovery.
- State the weekly rhythm: train and log everything (coach-led sessions
  too), `/check-in` weekly.
- If they set up a Hevy key, remind them `.env` stays uncommitted
  (already gitignored).
- Offer to commit: `git add -A` and show what's staged; commit with
  message `Initial setup: settings, profile and program` after they
  approve.
