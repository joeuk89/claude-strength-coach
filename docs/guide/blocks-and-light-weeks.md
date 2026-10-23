# Blocks and light weeks

A block is the stretch of hard training between one light week and the
next, counted in completed hard weeks rather than calendar weeks. Read
this to understand how the coach counts those weeks, what makes it
propose a light week, the three kinds of light week, how it brings you
back after a layoff or illness, and why an old prescription goes stale.
Every numbered rule here cites the research claim behind it as
`(rn:<note>.<n>)`; `python3 -m coach research show <ref>` prints the
claim and its sources.

## The block and its ledger

A **block** (see [the glossary](../../CONTEXT.md)) runs from the week
after one light week to the next light week. Its length is not fixed:
it ends when a light week is taken, or when a week is lost (under half
trained, or a layoff). What the coach counts is **completed hard
weeks**, so a travel week or a planned break does not move the count.

Two files hold it:

- **The block ledger**, `data/blocks.json`: every block and each week a
  check-in closed in it, with the week's class, its planned and trained
  sessions, how many passed the hard-week gate, its fatigue signals, the
  triggers that fired, the count after it, and the outcome.
- **The summary** in `data/state.json` under `block`: the block's id and
  start, the completed hard weeks, the last closed week, the last deep
  review, and the light-week state (`not_due`, `watch`, `skipped`,
  `proposed`, `agreed` or `declined`, with its type and reason).

The block status line is what you see on the program page, the
dashboard and the session-start status, and it opens every check-in
record's Decisions section:

```text
Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>
```

From a test workspace: `Block 1 · 2 of 6 hard weeks · triggers 0 of 4 ·
light week: not due`.

## Completed hard weeks and the session gate

A **completed hard week** is a normal program week in which at least
75 % of planned sessions, coach-led ones included, passed the hard-week
session gate (rn:deloads.2).

A session passes the **hard-week session gate** when at least two thirds
of its prescribed working sets were logged and its mean logged RPE was
no more than 1.5 below target (rn:deloads.11). A set with no logged RPE
counts as on target, and a rep-out set's cap counts as its target. A
coach-led session passes when it happened; one the trainer cancelled
was never planned, so it neither passes nor fails. A session you trained
but did not log has no logged sets, so it does not pass.

The gate is a fatigue count, not proof the prescription was met: a
session with failed reps or a grind past its target still passes. The
close reports those apart, as `reps_missed`, `effort_above_target` or
`effort_below_target` on the lines concerned, and the coach takes them
into the load review.

Each closed week gets one class:

| Class | What it is | Effect on the block |
|---|---|---|
| hard | at least 75 % of planned core and coach-led sessions passed the gate | adds one to the count |
| partial | between 50 % and 75 % trained, or nothing left planned after trainer cancellations | neither counts nor resets (rn:deloads.2) |
| low | under 50 % of planned sessions trained | ends the block; the next starts at zero (rn:deloads.2) |
| light | a deload or light week | ends the block |
| return | a return week after a layoff of 11+ days | ends the block |
| one_off | a constrained one-off week with temporary sessions | neither counts nor resets (rn:deloads.13) |
| minimum | a minimum week | neither counts nor resets (rn:deloads.13) |
| break | a planned no-training break covering every planned session | neither counts nor resets (rn:deloads.13) |

A reshuffle week is an ordinary week: its sessions are classed like any
other week's. An illness week (training missed while ill) is classed by
these rules too; adherence leaves it out, but the block keeps the
training it had. The pause for one-off, minimum and break weeks is
bookkeeping: it never shortens the days off that the return bands count.

## The ceiling

The coach proposes a light week when the count reaches the program's
ceiling: 6 completed hard weeks by default, settable from 4 to 8 in the
program's `blocks.hard_weeks_ceiling` (rn:deloads.3). At the ceiling it
is proposed whatever else is true. If you decline, the coach records the
reason and proposes it again at the next check-in; the status line then
reads `declined (<reason>), proposed again next check-in`.

## The four fatigue triggers

A light week is also proposed on fatigue, before the ceiling. The coach
checks four triggers when it closes each week:

| Trigger | Exact definition |
|---|---|
| readiness | poor readiness you report, from your reply and your workout notes |
| RPE drift | a compound lift (or a set under a recovery cap) drifting two sessions running, each set judged against its own prescription, after an earlier session at the prescription that did not drift (rn:autoregulation.4). Drift is logged RPE 1 or more over target on 2 or more working sets of one exposure; extra, heavier, longer or more-rep sets, and deload, light or return work, prove nothing |
| niggle | a niggle aggravated under load at any point in the week: a row with an `aggravated` entry dated in the week, or still `aggravated` on the week's first day |
| sleep | poor sleep for most of the week, measured from tracker or diary nights alike; how you felt is readiness, not sleep |

**Two triggers in the same week propose a light week; one is recorded
as a watch** (rn:deloads.5). The status line shows the count and the
names, `triggers 1 of 4 (sleep)`.

Some signals look like triggers but are not:

- **Calibration.** Two drifting exposures with no steady exposure before
  them are calibration, not a trigger: the prescription was probably too
  high from the start. The close flags it as `drift_calibration` and the
  coach reviews the load instead.
- **A run spike** is reviewed with you at the check-in and is never a
  trigger: the coach asks about symptoms and your next long run, agrees
  an action, and records it as a follow-up.
- **Sleep without nightly data** is `unknown`, not poor. Only a reasoned
  override (`block close --sleep poor --sleep-reason "<why>"`) replaces
  the measurement, and the ledger records it as an override.
- **A niggle reported late.** A flare you report at the check-in for an
  earlier day is dated to that day, so it counts toward the week it
  happened in, and the coach closes that week again.

## The skip rule

Below three completed hard weeks, no light week is scheduled, even on
two triggers (rn:deloads.4). The status line records it as
`light week: skipped (<n> hard weeks)`. The triggers are still on
record, and the coach still reviews the loads and recovery behind them.

These rules, the 75 % and 50 % lines, the session gate, the ceiling,
the four triggers with the two-trigger rule, the three-week skip rule
and the weeks that pause the count, are coaching heuristics, not
research cut-offs.

## The three kinds of light week

| Kind | What it does | When the coach proposes it |
|---|---|---|
| deload | the program's own deload rule; the standard rule keeps two thirds of each line's working sets, takes 10 % off the working loads as a target before the kit rounds it, and caps every set at RPE 6 (rn:deloads.9) | the ceiling, or two triggers that include RPE drift or an aggravated niggle |
| light | fewer sets at held loads | two triggers from readiness and sleep only |
| return | one working set fewer, with the return band's load cut and RPE cap | a week under 50 % trained with an `ill` miss and more than 10 days off to the first session back |

The coach may choose another type with a recorded reason, and may call
a light week nobody proposed. Either way it is built in `/program-week`'s
light mode, with temporary sessions titled "Deload — <title>",
"Light — <title>" or "Return — <title>", so your normal routines are
untouched.

**What the next week progresses from.** After a return week, the normal
progression scheme resumes from the loads the return week logged, with
the program's sets back, and a wave scheme keeps its training max. A
deload's or light week's loads are never the next week's baseline: they
stay in the log beside the ordinary exposures without counting as a
loss, and the scheme reads the exposures before them.

## Where you meet the block commands

You do not run these yourself; the coach runs them at set points and
quotes the output.

| Command | When the coach runs it | What it does |
|---|---|---|
| `python3 -m coach block close --week <W>` | at every check-in, after your reply, with `--readiness poor\|ok` from what you said and `--deep` on a deep review; as a dry run before the Sunday message to pick the tier | classes every week since the last close, updates the count, checks the four triggers, and proposes, watches or skips a light week; writes the ledger and the state, re-renders the program page, and prints the status line and each week's review |
| `python3 -m coach block decide --outcome adopted\|declined` | when a light week is proposed and you answer; or when the coach calls one unprompted, with `--type` and `--reason` | records the decision, and for an adopted week prints the exact `propose week` command that builds it |
| `python3 -m coach block init --hard-weeks N` | only when a ledger with no closed week must start from a count you confirm, such as a workspace migrated from an older version; no skill runs it on its own | starts the ledger from that count, with the last week it covers, the block's first day, and where the count came from |
| `python3 -m coach block status` | whenever the status line is needed again; the session-start status and the dashboard read it | the count, the light-week state, the status line, and whether the next check-in is deep |

The check-in that closes a light, return or low week ends the block, and
the next block starts at zero. `/program-week` leaves the count alone
when it plans a light week: the reset happens only when the check-in
closes that week.

## The deep review link

A newly proposed light week makes the next check-in deep: the full
block-level review, not the ten-minute weekly one. An unchanged repeat
of a proposal you declined, and a one-trigger watch, stay weekly. The
deep review also falls due on its own clock, 42 days after the last one
(rn:deloads.12), which matches the default ceiling of 6 hard weeks. See
[The check-in](check-in.md).

## Return after a layoff

Days off are the days from your last lifting workout of any kind, solo
or coach-led, to the first session back. A layoff over 10 days gets one
**return week** (rn:detraining-return.3); after it, the normal
progression scheme resumes from the loads the return week logged.

| Days off | Return week |
| --- | --- |
| up to 10 | no change (rn:detraining-return.3) |
| 11–21 | loads −5 %, one working set fewer per exercise (rn:detraining-return.3) |
| 22–42 | loads −10 %, one working set fewer per exercise (rn:detraining-return.3) |
| 43+ | a re-test: every load −15 % from its pre-layoff working load, every set at RPE 7 or below, one working set fewer; next week's loads come from what this week logged (rn:detraining-return.3) |

The bands are coaching heuristics: the cuts are deeper than the measured
strength loss, to ease you back in, and the next week's progression
corrects them from what the return week logged (rn:detraining-return.3).
Each cut is a target before rounding: the load is the nearest your kit
makes no heavier than the pre-layoff load, and when the kit holds the
load, the set cut and RPE cap still apply (rn:detraining-return.3). The
coach names the band in the week focus. A catch-up check-in (more than
10 days since the last one) carries the proposed return week in its card
and one "ok" accepts it.

The cut is measured once, from the pre-layoff working load: the lift's
newest logged exposure before the layoff, in any session (a workout
matched to no session counts), else the program's start load. Planning
the same week again, midweek or with `propose rebuild`, gives the same
loads: a return-week line is never cut from again, and `prescription
check` judges every line against the same exposure the proposal cut
from. A lift the program has never logged, with no start load, still
gets its first load from you.

**Illness adds a rule of its own.** After a mild illness with symptoms
above the neck only, no training until 48 hours symptom-free, and every
exercise in the first session back capped at RPE 7, whatever the gap
(rn:detraining-return.4). This is a coaching heuristic too: no study
sets a fixed symptom-free period. An `ill` miss tag or an `ill` status
day in the gap brings it in; no session is planned on an ill day, and
the coach resolves the illness flag only when you confirm the 48 hours,
never because the ill days ended. With 10 days or fewer off, the
first-session cap is the whole return.

**When to see a professional.** Fever, chest symptoms, other whole-body
symptoms or a slow recovery mean checking with a qualified professional
before training again. The coach is not a doctor or physiotherapist: for
pain, a suspected injury or a medical question it recommends one.

## Prescription validity

A prescription is only as current as the exposure it came from. Strength
changes little in the first 2 weeks without training and fades after
that (rn:detraining-return.1), so a lift's load decays by the return
bands above.

Each lift has a **validity window**: its usual gap between exposures
(the median of its recent gaps, held between 7 and 14 days) plus 10
days' grace. A lift's **days off** are the longer of the layoff and the
time since its newest exposure beyond its usual gap. So a lift that
rotated out for a month decays even when you never stopped training,
and a two-week holiday decays every lift at once. The coach never
carries a load forward past the band those days fall in.

The prescription check enforces this on every overlay before the brief.
A line whose days off fall in a return band but which still carries the
old load is `stale_prescription`, a blocking flag. From a test workspace
after 28 days off:

```text
stale_prescription: bb_back_squat in session-a on 2026-10-12: its days off fall in return band 22-42, and the line is not decayed to it
```

The coach decays the line to that band and records where it came from.
The proposal pipeline does this itself; the check catches lines written
by hand. A lift with no exposure at all (a first load) is never stale,
since no exposure measures it. One stale lift rotating back in never
ends a block: a week classes as `return` only when the layoff itself
passed 10 days.

The same check also judges whether a load is still earned: a load that
even the fewest reps allowed would put beyond failure at the recent e1RM
is `unearned_load` and comes down. On a deload, light or return line,
the RPE is a ceiling, not a target: the check flags a load too hard for
it and never calls the work too easy.
