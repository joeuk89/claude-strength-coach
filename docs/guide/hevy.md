# Hevy: the logbook, the routines and the approval gate

This page covers how the coach uses Hevy: the API key and the local
cache, load modes and the two dumbbell numbers, the routines the coach
manages, what a programming pass writes and how every write is gated,
and `/hevy-sync`. Read it when you set Hevy up, when a routine looks
wrong in the app, or before your first "go".

If you log in Hevy's free tier, or not at all, read
[Training without Hevy](training-without-hevy.md) instead.

## What Hevy is for, and what needs Pro

Hevy is your training logbook. The coach reads your logged workouts
from it and writes each session's prescription into a Hevy routine, so
you open the app and train. Both go through Hevy's API, which **needs
Hevy Pro**. The free tier has no API, so with it the coach works as if
there were no Hevy: `[hevy] enabled = false` in `config.toml`, and you
train from session sheets instead.

The coach never calls Hevy by hand. Every read and write goes through
`python3 -m coach hevy ...` and `python3 -m coach routines ...`.

## The key

Generate a key at hevy.com, under Settings, Developer (in the app:
Profile, Settings, Developer). Copy `.env.example` to `.env` at the repo
root and paste it in yourself as `HEVY_API_KEY=...`. The coach never
echoes the key back, never prints it and never commits it; `.gitignore`
covers `.env`.

`python3 -m coach hevy status` reports whether a key is set, whether the
cache exists, its age, and what it holds. Abridged, from a workspace with
no key and a three-day-old cache:

```json
{"enabled": true, "key": "missing", "cache": "present", "max_age_hours": 24,
 "pulled_at": "2026-10-09T12:00:00Z", "age_hours": 72.0, "stale": true,
 "counts": {"workouts": 4, "routines": 2, "routine_folders": 1,
            "exercise_templates": 4, "body_measurements": 2}}
```

`key` must read `present`. Then `python3 -m coach hevy pull` proves it
works: exit 0 is success, exit 5 means Hevy rejected the key (copy it
again), exit 4 means Hevy could not be reached (try again shortly).

## Pull and the cache

`python3 -m coach hevy pull` updates the local cache under
`.coach/cache/hevy/`, which is gitignored. The first pull reads every
workout; later pulls read only what changed since the last one. `--full`
re-reads everything. Each pull also refreshes the routines, routine
folders, exercise templates and body measurements.

`[hevy] cache_max_age_hours` (24 by default) sets how old the cache may
be before `coach check` warns:

```text
The Hevy cache is 72 hours old, past the 24-hour limit; run python3 -m coach hevy pull.
```

The coach pulls at the start of `/check-in` and of every programming
pass, so the warning usually means a session started without one.

## The exercise library and load modes

Every exercise in a program, an overlay or a Hevy routine is named by
its **exercise library** id (see [the glossary](../../CONTEXT.md)). The
library is the builtin catalogue merged with your own entries in
`data/exercises.json`: your Hevy template mappings, the load mode you
confirmed for each exercise, custom exercises and exercises you avoid.

A **load mode** says how an exercise is loaded in a given program slot,
which fixes how the weight you set relates to the value Hevy stores. It
is a property of how you perform the lift, not of its name.

| Mode | The number you set | What Hevy stores | Printed as |
|---|---|---|---|
| `total` | the load on the bar or stack | the same | `80` |
| `per_hand_x2` | one dumbbell | twice it | `25/hand (Hevy: 50)` |
| `single_implement` | the one implement | the same | `25` |
| `bodyweight` | the added load, 0 if none | the added load | `BW` or `BW+10` |
| `assisted` | the assistance | the assistance | `BW-20 assist (Hevy: 20)` |
| `band` | no load | nothing | no load |
| `duration` | no load | seconds on the set | no load |
| `distance` | no load | metres on the set | no load |

**Every exercise needs a confirmed load mode before it is prescribed or
written to Hevy.** The library's default and a seeded proposal never
stand in for your confirmation. An unconfirmed exercise blocks the
week's approval and fails the `load_modes_confirmed` check:

```text
db_bench_press ('Bench Press (Dumbbell)' in routine 'Session A') has no confirmed load mode;
run python3 -m coach library confirm db_bench_press (proposed per_hand_x2),
or python3 -m coach library set-mode db_bench_press MODE
```

The commands:

| Command | What it does |
|---|---|
| `library seed` | Matches every exercise in your cached routines to the library, records its Hevy template, and proposes a load mode with a confidence. Creates a `custom_` entry for an exercise the catalogue lacks and lists it under `guessed` for the coach to check |
| `library confirm <ids>` (or `--all`) | Copies the proposed mode to the confirmed one |
| `library set-mode <id> <mode>` | Records your answer directly, whatever was proposed |
| `library set-template <id> <template id>` | Chooses which cached Hevy template an exercise maps to, when the seed found none or several |
| `library show <id>` | The merged entry: muscles, pattern, equipment, substitutes, proposed and confirmed mode |

The coach puts each low-confidence proposal to you and decides from how
you perform the lift: an alternating curl is one implement. Confirming a
mode that differs from a program line's mode makes `program validate`
fail until the line is reconciled; see
[Programs](programs.md#editing-the-program-later).

## The two dumbbell numbers

Hevy stores a dumbbell set's weight as the **combined total lifted per
rep**, per its own in-app guidance ("if each arm is lifting 10 lbs, your
weight logged should be 20 lbs"). So a two-dumbbell exercise always has
two numbers:

| | What it means | Example |
|---|---|---|
| **Per hand** | What you set each dumbbell to: the coaching number | `25/hand` |
| **Hevy value** | What goes in the app | `50` |

Everything you read carries both, as `25/hand (Hevy: 50)`: routine
notes, the brief, check-in tables, the progress page. A single-implement
load prints one number (`30`), since its Hevy value is the same. The
coach converts with `python3 -m coach units convert` and never by hand.

**Convention slips.** Logging a pair as one dumbbell's weight, or one
dumbbell as the pair, is the easiest way to corrupt your log, and it is
silent when it happens. An exact 2× jump in one exercise at unchanged
reps and RPE is a slip, not progress: the coach checks sibling exercises
on the same dates before treating it as a strength change, and never
lets it set an e1RM, a PR or next week's load. When an audit finds both
conventions in one log, the coach confirms your actual per-hand weights
with you before rewriting anything. The check-in card flags a
`convention_slip`, and `/hevy-sync` raises a dumbbell load at almost
exactly 2× or ½× the plan's Hevy value.

## Managed, temporary and orphan routines

A **managed routine** is a Hevy routine the coach created, imported or
reused for a session. The map lives in `data/state.json` under `hevy`:

```json
"hevy": {
  "routines": {"00000000-0000-4000-8000-000000000001": {"session_id": "session-a"}},
  "folders": {"program": 1, "one_off": null},
  "temporary_routines": []
}
```

`routines` maps each routine id to its program session. Ids are the join
key; titles are labels you may rename in the app. `folders.program` is
the Hevy folder your program routines sit in. Sharing a folder with
managed routines does not make a routine managed.

**Temporary routines** carry the sessions of a one-off week (a light,
constrained or reshuffled week). They live in a Hevy folder titled
**One-off weeks**, recorded in `temporary_routines`. The API has no
delete, so reuse is the cleanup: the next one-off week reuses a spare
temporary routine before creating one, and `/hevy-sync` ignores them.

An **orphan routine** is a managed routine no current session or
temporary entry uses, usually after a redesign. The coach offers three
choices and does none without your approval:

- **leave** it as it is;
- **reuse** it for a new session (`routines create --reuse
  <session>=<routine id>`);
- **retire** it: `routines retire` retitles it `(unused)` with its
  exercises left in place, so an import skips it later.

If the map and the live routine list disagree (a mapped id Hevy no
longer has, a live routine in neither list, a session with no routine),
the coach heals the map with you before anything else.

## What a programming pass writes

After your "go" to the coach's brief, `python3 -m coach routines push
--overlay <id>` writes the approved overlay into **every** routine in
its span that differs. For each exercise it sends the set list (type,
Hevy weight, reps or rep range, duration, distance), the rest time and
the superset, and a note in a fixed format from
[`reference/hevy-api.md`](../../reference/hevy-api.md):

```text
Wk of 12 Oct: heavier top sets, stop 1–2 reps short of failure
Target: 3×8 @ 25/hand (Hevy: 50) @ RPE 8
Focus: pause 1s on the chest this week
Cues: elbows tucked · feet planted
```

- **The week line** goes on the first exercise of every routine the pass
  writes, and only there. Hevy drops routine-level notes, so this is the
  only place the week's focus can live, and the date lets you spot a
  stale note mid-session.
- **Target** is always present and absolute: sets × reps @ load @ RPE,
  warm-ups left out, equal sets collapsed (`1×5 @ 100 kg @ RPE 8 + 3×5 @
  90 kg @ RPE 7`). A dumbbell line gives both numbers. A rep-out set
  reads `1×5+ @ 85 kg (stop at RPE 9)`. A load you choose yourself reads
  `3×8–10 @ RPE 7 · choose the load`. Never "add 2.5 from last week":
  relative wording goes stale the moment the week ends.
- **Focus** appears only when the line has a weekly emphasis.
- **Cues** come from the exercise's `cues` in `data/program.json`.
- **Warm-up sets carry their weight** in the routine, like working sets:
  the ramp the proposal derives from the first working set (see
  [Programming the week](programming-the-week.md)), so the app shows
  this week's warm-ups, not the loads from the last time you logged the
  exercise. A warm-up with no load (a bodyweight line, or nothing lighter
  than the work sets on your kit) is sent without one.

**What it never writes.** Hevy routines cannot store an RPE target, so
RPE reaches you only through the note. Nothing writes routine-level
notes. A null load sends no weight. Loads come from the overlay's load
object, never from arithmetic in the writer.

Push rewrites each whole routine, notes included. A note you typed in
the app that is worth keeping goes into the program's `cues` first.

## Push, verify and the audit log

`routines push` follows a fixed sequence per changed routine: write it,
read it back, compare. A read-back that differs stops the push and exits
1 with the report. Running push again after success sends nothing. Then
`python3 -m coach routines verify --overlay <id>` reports, per routine,
whether Hevy matches the overlay, and the coach quotes it in the
close-out. The week is published only once every routine verifies.

Every non-GET request and every verification lands in
`data/hevy/writes.jsonl`, one JSON line each, committed with the
training records:

```json
{"schema_version":2,"at":"2026-10-11T19:05:00Z","kind":"verify",
 "routine_id":"00000000-0000-4000-8000-000000000001","overlay_id":"2026-10-12-weekly",
 "overlay_hash":"sha256:3f5fa57e…","verified":true,"diff":[]}
```

A `write` line carries the method, path, HTTP status, the request body
and its hash; a `verify` line the result and any remaining differences;
a `retire` line a retirement. The key never appears.

**Guards.** Push refuses (exit 3) before any request when the overlay is
not approved, its approval hash is broken by a later edit, a `block`
flag is unresolved, the span has already ended, or a routine's session
is already covered by another overlay in force. It also refuses when any
routine's live `updated_at` differs from the cached one: an app edit is
reviewed before anything is overwritten. The coach reports the reason
and never retries by hand.

**Edited in the app, and STALE.** At the start of a pass, `routines
verify` compares each routine with the overlay in force:

- A **structural** change (an exercise added, removed or reordered; set
  counts, reps, rep ranges, rest or supersets changed) is an edit you
  made in the app. It goes in the coach's brief as a keep-or-replace
  question, settled by the same "go" as the week.
- A **load-only** edit is you autoregulating. The log already holds what
  you lifted, so push overwrites it without comment.
- A note that no longer matches means the routine is **STALE**: it does
  not carry the overlay in force, so you would train from old notes. The
  brief lists each STALE routine.

`routines diff --overlay <id>` shows exactly what a push would write,
change by change, and its summary prints loads in both conventions.
Abridged, from a workspace whose routines were never pushed:

```text
Overlay 2026-10-12-weekly → Hevy: 2 of 2 routine(s) would change.
Session A (Mon 12 Oct): 14 change(s), 6 structural
  - bb_back_squat note: Target: 3×5 @ 100 kg @ RPE 7
  - bb_back_squat sets 2–3: 97.5 kg → 100 kg
  - db_bench_press sets 2–3: 22.5/hand (Hevy: 45) → 25/hand (Hevy: 50)
```

## The approval gate

The **approval gate** is the rule that every Hevy write waits for your
reply: presenting and writing never happen in the same turn. On a
programming pass, one "go" approves the coach's brief and every write
its closing line names. Three mechanisms enforce it.

**The overlay approval.** `python3 -m coach overlay approve <id>` stamps
your approval on the week's overlay with a hash of its content. Any
later edit breaks the hash, and push refuses until the overlay is built,
presented and approved again.

**The PreToolUse hook.** `.claude/settings.json` runs `python3 -m coach
gate pretooluse` before every shell command the coach issues. For a
`coach` command that writes to Hevy, the hook runs that command as a dry
run and puts its summary in the permission prompt, so you see exactly
what will change before you allow it. For example:

```text
Approval gate: python3 -m coach routines push writes to Hevy. Dry run:
Overlay 2026-10-12-weekly → Hevy: 1 of 2 routine(s) would change.
Session A (Mon 12 Oct): 2 change(s), 0 structural
  - bb_back_squat sets 1–3: 97.5 kg → 100 kg
Allow only if the athlete approved exactly these changes.
```

A push the dry run refuses is denied with the reason, and never reaches
Hevy. `routines create` and a named `routines retire` are denied on an
unapproved overlay, and denied unless the command carries the
`--expect-plan` hash of the exact preview the brief named, so a changed
plan or a routine changed in Hevy since the preview refuses before any
write. Read-only commands such as `hevy pull`, `routines diff` and
`routines verify` are on the settings allowlist and run without a
prompt; `routines push`, `create` and `retire` are not, so they always
prompt.

A raw HTTP write to the Hevy API (`curl -X PUT ...`) prompts with a
warning that it skips the coach's approval check, read-back and audit
log. In bypass-permissions mode every Hevy write is **denied**, because
nobody would see a prompt: run the coach with normal permissions.

**Exact-action approval.** A `routines create` or `retire` preview
returns a `plan_hash` of the exact routines, bodies and folder it would
write. The write line of the coach's brief names every create, reuse,
retirement and folder; the command then needs that hash.

## `/hevy-sync`

Either side can drift: you change a routine in the app, or the program
changes in the repo. `/hevy-sync` finds the differences and resolves
each **with you, one at a time**, never in bulk.

The coach pulls, checks the routine map, then runs `routines diff` on
the overlay in force. Only **structural** changes are discrepancies:
exercises added, removed or substituted, their order, supersets, set
counts, reps and rep ranges, rest times. **Prescription** changes
(loads and notes) are not drift: every pass rewrites them, and an
in-app load edit is you autoregulating. The coach mentions a load only
when it breaks a constraint in your profile or `[caps]`.

**The dumbbell exception.** A dumbbell load the diff shows at almost
exactly 2× or ½× the plan's Hevy value is a convention error, and left
alone it corrupts the history later loads come from, so the coach raises
it. Single-arm and alternating work carries the same number per hand
and in Hevy, so it checks the load mode first.

For each discrepancy the coach shows both versions side by side, coaches
on it (a good call? does it hurt weekly balance or the rotation?), and
waits. You pick one of three:

1. **Adopt Hevy**: the coach edits the session in `data/program.json`
   to match, validates and renders. The overlay in force keeps the old
   shape; the next programming pass carries the change into the week.
2. **Adopt the plan**: Hevy gets the plan's version, written once after
   every discrepancy is settled, with a diff you review first.
3. **Neither**: you design a third option together, apply it to the
   program, and let it reach Hevy through `/program-week`.

Push happens only when the overlay is approved and every routine with a
structural change is one you chose to adopt from the plan. Any "adopt
Hevy" or "neither" means no push of the overlay in force, which would
write the old shape back.

A new exercise needs a library entry with a Hevy template. `routines
preflight --overlay <id>` lists every unresolved template before a write
brief; `library set-template` records the mapping. A change to the
plan's intent goes in the newest check-in's Decisions section.

## Hevy body measurements as a bodyweight source

Each pull caches your Hevy body measurements. They are one of the
sources `python3 -m coach bodyweight list` reads, as scale weight: a
weigh-in kept as a wellness record wins on the same date, then Hevy,
then a nutrition reading, so a copy of the same weigh-in counts once.
The check-in treats the cached measurements as a fallback weight source
only.

## Claude Code cloud sessions

A cloud session has no `.env`, since it is not in the clone. Configure
the cloud environment at claude.ai/code (the cloud icon above the
message box, then the environment's settings):

- **Environment variables**: add `HEVY_API_KEY=<key>`. Anyone using
  that environment can read it, so keep it a personal environment.
- **Network access**: set to **Custom**, add `api.hevyapp.com`, and tick
  "Also include default list of common package managers". The default
  **Trusted** level does not allow the Hevy host, so every call fails
  without this.

Changes apply to sessions started afterwards, not ones already running.

## The manual fallback

Only when a `coach` command keeps failing, and you agree to a hand-built
call, does the coach follow "Manual fallback" in
[`reference/hevy-api.md`](../../reference/hevy-api.md). A guard refusing
with exit 3 is never a reason: the cause is fixed instead. The gate's
hook prompts on every raw write, loads still come from `coach` output,
and the coach pulls and verifies afterwards. Raw calls skip the audit
log, so the check-in record says which routine was written by hand and
why.

## Repairing a mis-logged workout

A past workout with a wrong weight or set is repaired through the API's
`PUT /v1/workouts/{id}`, which replaces the whole workout: the coach
reads it first, edits the JSON, and writes it back. This is a raw write,
so the gate prompts, and the coach confirms with you before sending it.
