# Niggles, follow-ups, status days and decisions

This page covers the four records that hold what the coach must
remember between sessions: niggles and the limits they set, follow-ups,
status days (ill, injured, travel and planned breaks) and recorded
decisions. Read it when something hurts, when you will be away, or when
you want to know why the coach keeps asking about something.

## Niggles

A **niggle** is an ache or minor injury worth watching for recurrence
(see [the glossary](../../CONTEXT.md) under "Niggle"). It lives in
`data/niggles.json` with the movement patterns, exercises and activity
kinds it affects, its status and the load limits it sets. It is never a
diagnosis: the coach records what you report and programs around it. For
pain or a suspected injury the coach recommends a qualified professional.

### Statuses

| Status | Meaning |
|---|---|
| `aggravated` | flared, and the "niggle aggravated under load" fatigue trigger |
| `watching` | present, being watched (the default for a new niggle) |
| `easing` | settling |
| `resolved` | gone; the row stays, because recurrence is the signal the log exists to catch |
| `chronic` | a lasting limitation, such as no overhead pressing |

A niggle is never deleted. `niggles resolve <id>` keeps the row, and a
later report on the same area goes on it with `niggles update`, not a new
row.

### What a niggle affects and the limits it sets

A niggle applies to movement patterns (`--pattern squat,lunge`), library
exercise ids (`--exercise`) and activity kinds (`--activity-kinds run`).
Each matching program line takes the niggle's limits while they are in
force.

**Standing limits** are the niggle's usual limits, set with
`--constraint`:

- `rpe_cap=7`: a recovery cap, every working set at or under RPE 7;
- `no_added_load`: the load holds, the scheme adds nothing;
- `load_cap=<n>`: the load never goes above n.

They apply while the status is one of `--constrain-while` (default
`aggravated,watching`), and always for a chronic niggle. **Flare limits**
are tighter limits for one flare, given with the status report as
`--flare-constraint rpe_cap=6`. They sit on top of the standing limits,
last until the status changes, and then the standing limits are what
remain. The coach never tightens a standing limit for a flare.

Every limit is dated. `--date` dates a report to the day it describes,
so a flare you report on Sunday that started on Tuesday is recorded on
Tuesday, and a past date reads the limits in force then. A flare counts
toward a closed week's fatigue trigger only when dated inside that week,
so after a dated report the coach runs `block close` for that week again.

### How the proposal applies them

Each week `propose week` puts every active niggle's standing and flare
limits on its matching lines. A load the e1RM puts over an RPE cap comes
down, and the line carries a `constraint_applied` flag naming the niggle.
When no e1RM or kit can meet the cap the line flags
`rpe_ceiling_unchecked`, and the coach agrees the load with you.
`niggles constraints [--session S] [--date D]` lists each program line a
niggle constrains on a date, with the limits in force then.

### The commands

```bash
python3 -m coach niggles add --area "left knee" --status watching \
  --pattern squat,lunge --activity-kinds run --constraint rpe_cap=7 \
  --note "sore on the descent"
python3 -m coach niggles update n-0001 --mention --status aggravated \
  --flare-constraint rpe_cap=6 --note "sharp on Tuesday's squats" --date 2026-10-06
python3 -m coach niggles resolve n-0001 --note "quiet for three weeks"
python3 -m coach niggles list --open
```

- `niggles add` logs a new niggle: `--area`, `--status` (default
  watching), `--note` (the report), `--date`, what it applies to, its
  limits, `--constrain-while` and `--notes` (standing notes). An unknown
  pattern, exercise id, activity kind or constraint exits 1 naming the
  valid values.
- `niggles update <id>` records a check-in report (`--status`, `--note`,
  `--mention` bumps the mention count once a day) or changes what it
  applies to and its limits. `--clear-constraints` removes the standing
  limits from that day; `--clear-flare-constraints` ends the flare's.
- `niggles resolve <id> [--note] [--date]` marks it resolved.
- `niggles list [--open] [--status S]` shows each row with its limits in
  force today, any standing limit to confirm, and any `escalate` reason.
- `niggles constraints` is described above.
- `niggles import --from-profile [--chronic 1,2] [--dry-run]` converts
  an older `profile.md` niggle log table into rows, once. The dry run
  also numbers the lines of the "Injuries / limitations" section, and
  `--chronic` turns the numbered lines you pick into chronic rows. It
  refuses to run when `data/niggles.json` already has rows.

At `/setup`, a lasting limitation becomes a chronic niggle with
`--constrain-while chronic`, and a current short-term one starts as
`watching`. An exercise you cannot or will not do is not a niggle: it is
`library set-avoid <id> --reason TEXT`.

### When the coach recommends a professional

`niggles list` gives a row an `escalate` reason, and `propose week` and
the check-in card raise `niggle_escalate`, when the last three check-in
reports are all aggravated or watching, or the status moved to aggravated
from a better one. Then the coach recommends a qualified professional
and programs around the niggle meanwhile, never diagnosing. A chronic
niggle never escalates: it is a known lasting limitation, listed at each
deep check-in without asking for a resolution.

### Niggles in the check-in

The Sunday message's Niggles field asks whether anything is new, names
each open row (watching or easing) and asks whether it is quiet or still
there. It also quotes the window's workout and exercise notes once, under
"Notes logged", and asks whether anything in them is a niggle to track. A
note is your report, not a diagnosis, so the card never records a niggle
from a note alone; the coach adds one only once your reply confirms it.

A niggle reported as **aggravated** is one of the four fatigue triggers:
"a niggle aggravated under load at any point in the week". One trigger in
a week is recorded as a watch; two propose a light week (see
[blocks and light weeks](blocks-and-light-weeks.md)).

## Follow-ups

A **follow-up** is a question to come back to later: the date it was
raised, where it came from and a review date, kept in
`data/followups.json`. It stays open until it is resolved or dropped
with a reason.

```bash
python3 -m coach followups add --text "Re-test the pull-up ladder once the elbow settles." \
  --review-at 2026-11-08 --source "check-in 2026-10-11"
python3 -m coach followups defer f-0001 --to 2026-11-22 --kept --note "elbow still easing"
python3 -m coach followups resolve f-0001 --note "ladder re-tested at rung 3"
```

| Command | What it does |
|---|---|
| `followups add --text T --review-at D --source S [--raised D]` | raises one |
| `followups resolve ID [--note T]` | closes it as answered |
| `followups drop ID --reason T` | closes it as no longer mattering |
| `followups defer ID --to D [--kept] [--note T]` | keeps it open with a new review date; `--kept` means it was reviewed today |
| `followups list [--open] [--due]` | lists them; due means open with a review date today or past |
| `followups render --deep --date D` | prints the deep record's follow-up section |

A due follow-up raises `followup_due` in `propose week` and the check-in
card, and the session-start status names it. **Every deep check-in
settles each open follow-up** raised before that day: resolve, drop or
defer. `followups render --deep --date D` exits 1 while any open item has
no disposition dated that day, so the record cannot be finished with one
forgotten.

Follow-ups also catch work that cannot land yet. When you ask for a lift
change mid-week after its only session that week ("bump my squat" the day
after squat day), its next exposure is next week's own session, so the
coach records the agreed change as a follow-up with the source
`mid-week request <date>` and a review date on the day next week is
planned. The next weekly proposal raises it as `followup_due`, the coach
applies it as that line's override and resolves it. A `run_volume_spike`
review and a question from an outside running plan are recorded the same
way.

## Status days

A **status day** is a day you were ill, injured or travelling, recorded
in `data/status-days.json` as a dated row. A wrong row is withdrawn,
never deleted.

```bash
python3 -m coach status-days add --kind ill --from 2026-10-01 --to 2026-10-02 \
  --note "head cold" --source "check-in 2026-10-04"
python3 -m coach status-days add --kind travel --from 2026-10-15 \
  --note "work trip" --no-training
python3 -m coach status-days end s-0002 --date 2026-10-19
python3 -m coach status-days withdraw s-0001 --reason "wrong dates"
```

- `status-days add --kind ill|injured|travel --from D [--to D] --note
  TEXT [--source TEXT] [--no-training]`. Leave out `--to` while it is
  still going on; a second ongoing row of one kind is refused.
- `status-days end ID --date D` gives an ongoing row its last day.
- `status-days withdraw ID --reason TEXT` takes back a wrong one; the row
  stays, marked withdrawn.
- `status-days list [--active]` lists them oldest first.

The check-in records the days your Sunday reply names, and the
`status_active` cardio flag warns while an ill or injured row overlaps
the week (injured adds "check with a qualified professional"); travel is
information.

### What an ill status day triggers

An ill status day in the gap before a session brings in the illness
return rule, exactly as an `ill` miss tag does. After a mild illness with
symptoms above the neck only, there is no training until 48 hours
symptom-free, and every exercise in the first session back is capped at
RPE 7 whatever the gap (rn:detraining-return.4). Fever, chest symptoms,
other whole-body symptoms or a slow recovery mean checking with a
qualified professional before training again. The coach asks you to
confirm the symptoms and the 48 hours before it resolves the
`return_after_illness` flag; the status day ending is not that
confirmation. No session is planned on a day an ill row covers, and a
week that lost planned training to illness is left out of adherence.

### What travel means

Travel alone only explains the gap. Its sessions are still planned and
still count, so a week away with no kit is a constrained one-off week in
`/program-week`, or a reshuffle when only the days move. A trip of 11 or
more days without lifting still brings a return week, because days off
count from your last lifting workout.

### Planned breaks

`--no-training` on a travel or injured row records that you agreed not to
train on those days: a **planned break**. Its sessions are not planned
work, so they need no programming and no miss tag, and a week whose every
planned session falls on the break is a planned break week, which
neither counts as a hard week nor resets the block (rn:deloads.13). The
dashboard's Focus and the session-start status show the break and the
day training resumes. An ill row cannot carry `--no-training`: illness
keeps its own return rule. Withdrawing or ending the row puts the days
after it back to ordinary planning, and a session you train on a break
day still counts as trained.

## Recorded decisions

`data/decisions.json` keeps the coaching decisions that later weeks must
respect, each with an effective status (`active`, `expired` once its end
date passes, or `withdrawn`). Records are never deleted.

| Kind | Recorded by | What it holds |
|---|---|---|
| `override` | `propose override` | one exercise's chosen sets against the scheme's proposal, with the reason |
| `light_week` | `block decide` | a light week adopted or declined, with its type, week, reason and triggers |
| `adherence_trigger` | `structure decide` | the smaller-schedule proposal adopted, declined or deferred, with the adherence percentage and weeks |
| `training_max` | `state set-training-max` | an explicit training-max change |

A **standing override** is an override with `--standing`, which holds in
later weeks until its end date (`--until`, four weeks by default, eight
at most) so the progression scheme stops proposing it away; a deload or
light week still cuts it. Renewing one is another standing override.
A declined or deferred decision carries a revisit date and is presented
again then; a declined light week at the ceiling is proposed again at the
next check-in.

`decisions list [--kind K] [--status S]` shows them with their effective
status, and `decisions withdraw ID --reason TEXT` closes one that no
longer holds.

### The check-in record's Decisions section

Every check-in record has a Decisions section. It opens with the block
status line that `block close` or `block decide` printed, then says what
changed and why (or "stay the course") and anything deferred, then the
adherence decision line when the adherence trigger was presented or an
under-80 % override was agreed, as `structure decide` prints it. For
example:

```markdown
Block 2 · 4 of 6 hard weeks · triggers 1 of 4 (sleep) · light week: watch
Adherence trigger: 76 % over 4 weeks: adopted (override: adds Sat conditioning)
```

When the coach decides against a current research claim without newer
evidence, the Decisions section records it as
`contradicts rn:<note>.<n>: <reason>` (see [research](research.md)).

## Where all of this shows up

**The session-start status** is what the coach reads first in every
session. Its `followups` section names each due follow-up, its `niggles`
section names each aggravated niggle, each one that needs a qualified
professional and each standing limit still to confirm, its `program`
section carries the block status line and flags a proposed or agreed
light week, its `overlay` section shows each planned break and the day
training resumes, and its `events` section lists active goal events.
Each of these is marked for attention, so the coach raises it in its
first reply.

**The dashboard's Watch** (`README.md`, shared with the week's brief)
lists at most three items by priority: unresolved block and warn flags
on the week's overlays, then each niggle aggravated, watching or easing
on the page's date with its area, status, since when and what it applies
to (an escalating one says to have it assessed by a qualified
professional; a chronic one shows while its limits are in force), then
the block's state: a fatigue watch, a proposed light week with its type
and reason, a declined one with its reason, or a skipped one with its
triggers. A resolved niggle drops out; its rows stay. An overlay flag and
the live item it matches show once.
