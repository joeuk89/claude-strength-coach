# The check-in

`/check-in` is the weekly review of your training: one message from the
coach about the week just trained, one reply from you, a dated record in
`check-ins/`, and the hand-over to programming the week ahead. Read this
when you want to know what the coach asks, what it checks, what it
writes down, and what follows from your answers.

## When to run it and what it needs

Run `/check-in` once a week, after your last session of the week. A
check-in falls due `cadence_days` (7 by default, in `config.toml`'s
`[checkin]` table) after the last record in `check-ins/`;
`python3 -m coach checkin due` says when the next one is due and which
tier it will run. The coach suggests one whenever the newest record is
over a week old.

It needs `profile.md` and `data/program.json`. Without a profile the
coach stops and runs `/setup`; a workspace whose program still lives as
hand-written pages in `routine/` needs its one-time migration first. The
coach starts every check-in with `python3 -m coach check` and reports
each failing check before doing anything else.

With Hevy on, the coach pulls your workouts first and reads every
workout description and exercise note you wrote in the app. Those notes
are the readiness signal the numbers cannot show, so they shape the
decisions. Without Hevy, it logs the workouts you report in chat (see
[Training without Hevy](training-without-hevy.md)).

## The three tiers

Every check-in runs at one of three tiers. The first line of the Sunday
message names the tier and why, and you can override it.

| Tier | What it is | When it runs |
|---|---|---|
| weekly | about ten minutes: adherence, weight and nutrition, the week ahead | the default |
| deep | the full block-level look, with extra checks and a Block planning section | see the four triggers below |
| catch-up | a shorter card for a gap, with a proposed return week | more than 10 days since the last check-in |

A **deep** check-in runs when any of these is true:

- **The 6-week clock.** The last deep review is 42 days old or more
  (rn:deloads.12), which matches the default ceiling of 6 completed hard
  weeks. The first check-in ever runs deep. A review whose title has no
  tier counts as deep; a Program start record is not a review.
- **A light week is newly proposed**: the hard-week count reached the
  ceiling, or two fatigue triggers fired (see
  [Blocks and light weeks](blocks-and-light-weeks.md)). The same proposal
  made again after you declined it stays weekly, and so does a
  one-trigger watch.
- **The adherence trigger fires**: under 70 % over the trailing four
  ordinary weeks (coach mode only).
- **You ask for one.**

A coming deload is not a trigger on its own. Before sending the Sunday
message the coach runs `python3 -m coach block close --dry-run` for the
week, whose `deep_review` applies these rules to the log. If your reply
changes the picture (a second fatigue trigger, a coach-led session that
did not happen), the real close after the reply says so, and the coach
switches to deep and tells you.

A **catch-up** check-in never runs deep. When a deep review was due, the
card defers it and the next check-in runs deep, with the reason
"deferred from catch-up <date>".

## The Sunday message

The coach sends **one** message that states what the log shows and asks
only what it cannot know, numbered so you can answer in one reply. It
replaces an interview: there are no question-by-question turns. The
coach runs `python3 -m coach checkin prepare` and sends its text, with
the wording tightened where it helps and never a figure changed.

**The first line** names the window (the day after the last review to
today) and the tier with its reason. When the days from your last
lifting workout to the first session of the coming week will be over 10,
it also says the coming week is a return week.

Then the week as data: each trained session's results against the
prescription (hit, under, over, missing), the e1RM line (an estimated
one-rep max from logged working sets, with the change since the previous
estimate), and any flags, such as a session over its time cap, an open
dumbbell convention slip, or a routine that never received the week.

**The numbered fields**, always in this order:

| Field | What it states | What it asks |
|---|---|---|
| Sessions | each planned session, trained or not, with its minutes against the cap | one tag per missed session: `time / sleep / ill / family / skipped / other`; anything trained but not logged |
| Coach-led | each coach-led session in the window and what its log shows; the inferred rotation position | what it covered (lifting, conditioning or both), how long, how hard (session RPE 0 to 10), whether the trainer cancelled it |
| Runs | the window's runs from your activity source (count, distance, quality runs) and any planned run missed | runs no source logged |
| Sleep | the last seven nights from your tracker or diary (average, short nights) | how it felt; or, with no nightly data, hours asleep each night and how it felt |
| Niggles | each open niggle (`watching` or `easing`); the week's workout notes under "Notes logged" | anything new; whether each open one is quiet or still there; whether anything in the notes is a niggle to track |
| Food | the readings the app gives (trend weight, expenditure, targets, 7-day average, days logged); the meal plan in force | the readings; anchors most days (y/n); anything in the plan that did not work; next week's food exceptions |
| Next week | the rotation position, when there is no Coach-led field | anything different: travel, schedule, kit, illness |

**Fields drop out when they cannot apply**, and the rest are renumbered
from 1:

- no coach-led session in the window, so no Coach-led field;
- no run recorded or planned in the window, so no Runs field; lifting
  alone never implies running;
- no missed or unlogged session, so Sessions is a statement with no ask;
- no anchors on file, so no anchors question; no meal plan in force, so
  no plan question; no standing weekly template, so no food-exceptions
  question;
- nutrition not enabled, so the Food field becomes **Bodyweight**: one
  morning scale weight and nothing else.

A **Hevy edits** field appears last only when you edited a routine in
the app since the coach last wrote it: keep the change (it goes into
the program) or replace it with the plan. The programming pass settles
it.

**A fact the log already answers is stated for confirmation, not
asked.** The rotation position is the clearest case: if your program
rotates, the coach infers where next week lands (from the coach-led
session's log, then the program's current position, then the newest
check-in) and states it in the Coach-led field, or in Next week when
there is no Coach-led field. It never asks the position as its own
question. If the sources disagree, it states the first and names the
disagreement.

**Deep tier only: body composition.** A deep check-in asks for waist, a
body-fat reading if you have one, and your own one-line read of your
progress photos, but only when both hold: your goals or a phase trigger
use waist, body fat or photos, or the phase is a cut or recomp; and no
deep record has a reading yet, or the last is 4 or more weeks old.
Photos stay with you and never go into the repo; the record keeps only
your one-line read. A reading you leave out is recorded once as "not
supplied" and not asked again before the next deep check-in.

**Your reply** is one message, answered by number. A missed session gets
its one-word tag and no follow-up on the reason; a miss you leave
untagged is recorded as `untagged`. The coach asks at most **one**
follow-up turn, and only for a gap that blocks programming: an
unresolved rotation position, a new niggle's severity, or nutrition
numbers it cannot read. Anything else it records once as "not supplied"
and moves on.

### An example

This Sunday message comes from a test workspace, produced with
`python3 -m coach checkin prepare` on Sunday 11 October 2026:

```text
Check-in for Mon 5 Oct – Sun 11 Oct (weekly — 7 days since the last check-in).

Results against the prescription:
- Mon 5 Oct Session A: Back Squat (Barbell) hit · Bench Press (Dumbbell) hit
- Thu 8 Oct Session B: Single Arm Row (Dumbbell) hit (RPE 0.5 above target) · Pull Up hit

e1RM, an estimated one-rep max worked out from logged working sets (change since the previous estimate): Back Squat (Barbell) 122 kg (+2) · Bench Press (Dumbbell) 32 kg/hand (±0) · Single Arm Row (Dumbbell) 42 kg (-1) · Pull Up 102 kg total system mass (+1)

Flags:
- `duration_over_cap`: 2026-10-05 Session A: 58 min against a 45 min cap

1. Sessions. Hevy shows: Mon 5 Oct Session A ✔ (58 min, over the 45 min cap), Thu 8 Oct Session B ✔ (60 min). Not logged: Sat 10 Oct Session A. Tag each miss: time / sleep / ill / family / skipped / other. Add anything you trained but didn't log.
2. Coach-led. What did PT on Tue 6 Oct cover (lifting, conditioning or both), how long and how hard (session RPE 0-10)? Say if the trainer cancelled it.
3. Runs. Logged: 1 run, 5 km. Any others not logged: how many, and total distance?
4. Sleep. Recorded: 6.98 h a night over 6 nights, 3 under 7 h. How did it feel?
5. Niggles. Anything new?
6. Food.
   a. trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein) · days logged
   b. anchors most days (y/n)?
   c. food exceptions next week: who cooks which nights, office-day changes, meals out?
7. Next week. Anything different: travel, schedule, kit, illness?
8. Hevy edits. Session B was edited in the app since the last write: Bench Press (Dumbbell) added. Keep the in-app change to Session B (it goes into the program) or replace it with the plan?
```

A reply might read: "1 sleep. 2 lower body, 45 min, RPE 7, not
cancelled. 3 none. 4 fine. 5 nothing new. 6a 81.2 · 2650 · 2300/170 ·
2280/165 · 7. 6b y. 6c out Friday. 7 no. 8 keep."

## What the coach records from your reply

Before analysing anything, the coach writes the facts your reply gives
into the training records in one batch:

- **Annotations** on the history, through
  `python3 -m coach history annotate`: a `miss` with its tag for each
  tagged miss; `trained_unlogged` for a planned session you trained but
  did not log (it counts as trained, with no results and no e1RM); and
  an `external` entry for each coach-led session, done or not, with the
  one-line note on what it covered and only the detail you gave:
  duration, session RPE, modality (`lifting`, `conditioning` or
  `mixed`) and start time. A session the trainer cancelled is recorded
  as a cancellation, not a miss; one that just did not happen is a miss.
- **Status days** for days you were ill, injured or away, with
  `python3 -m coach status-days add`. An `ill` day in the gap before a
  session brings in the illness return rule, and no session is planned
  on its days. Days you agree not to train at all are a planned break
  (`--no-training`): their sessions need no tag, and the week neither
  counts toward nor resets the block. See
  [Niggles and follow-ups](niggles-and-followups.md).
- **Sleep**: the nightly hours you give go in with
  `python3 -m coach wellness add`, because only nightly hours feed the
  fatigue check.
- **Goal events** you name, and each event's agreed window or result.

Then it runs `checkin prepare` again so the card carries your reply.

## What the review checks

The coach judges the week against the **effective prescription**: the
overlay in force each day, whatever programming pass wrote it (see
[the glossary](../../CONTEXT.md) for overlay). With an overlay,
adherence is concrete: did you hit the prescribed load, reps and RPE?
Loads are shown in your own units, converted by the scripts, never by
hand.

**Every check-in:**

- **Adherence this week**: `python3 -m coach stats adherence` per
  overlay in the window gives each session's status (trained, missed
  with its tag, upcoming) and each exercise's result. Coach-led sessions
  count as your reply confirmed them, never from the API alone.
- **Cardio**, kept separate from lifting adherence: the week's runs,
  conditioning and other activity, planned against logged when your
  cardio tier is `review` or `program`, and the cardio flags. See
  [Cardio and activity](cardio-and-activity.md).
- **Notable sets**: PRs, rep-range top-outs due a load increase,
  anything far off prescription.
- **RPE drift** on compound lifts and recovery-capped sets: logged RPE 1
  or more over target on 2 or more working sets of one exposure, each
  set judged against its own prescription (rn:autoregulation.4).
  Isolation drift gets one record line and drives no decision.
- **Priority work**: each priority lift's KPI, its trend, and its
  exposures per week against plan, with a flag for a planned exposure
  missed with no floor dose in its place.
- **Convention slips**: an exact doubling or halving of a dumbbell load
  at unchanged reps and RPE is a logging slip, not a strength change.
  The coach confirms the real per-hand weight with you and records the
  answer; an open slip stays out of the e1RM series until settled.
- **The hard-week count and fatigue triggers**, through
  `python3 -m coach block close` for the week, with your readiness from
  the reply and workout notes. It classes every week since the last
  close, updates the count, checks the four fatigue triggers and
  proposes, watches or skips a light week. The gate counts training
  stress, not a met prescription: the close also reports sessions that
  missed reps or logged effort over or under target, which feed the load
  review. [Blocks and light weeks](blocks-and-light-weeks.md) has the
  rules.
- **Adherence over the trailing four ordinary weeks**: sessions trained
  divided by sessions planned, from `python3 -m coach structure
  adherence`. An ordinary week is any week except a light, constrained
  one-off, minimum, planned break, layoff (11+ days) or illness week; a
  reshuffle stays ordinary. It reaches back at most 12 weeks, and under
  four ordinary weeks there is no trigger.
- **Weight and nutrition**: the reading from the Food field is recorded,
  the trend read, each nutrition flag acted on and the sleep gate
  checked. With nutrition off, the weigh-in is recorded and the coach
  prompts `/goals`. [Nutrition](nutrition.md) covers this in full.

**The deep tier adds:**

- the e1RM trend per main lift since the last deep check-in, as a
  trend, not gospel; light-week, return-week and over-cap exposures stay
  out of the series; stalls (the same load and reps 3+ sessions) and
  progression-scheme violations;
- missed sessions since the last deep check-in, counted by tag and by
  session; a tag that keeps coming back (`time`, `sleep`) is a schedule
  or recovery question;
- a dumbbell-load audit over the last eight weeks for convention slips;
- exercise drift against the plan (with Hevy, `/hevy-sync` if
  structural), intensity honesty, session durations against your time
  limits, junk volume, and whether the weekly balance still matches what
  you train;
- expired research notes for areas the coming block depends on;
- every open follow-up, settled with you (resolved, dropped with a
  reason, or deferred to a date), and every open niggle reviewed.

## The record

The coach writes `check-ins/YYYY-MM-DD.md` with
`python3 -m coach checkin skeleton`, titled
`# Check-in — YYYY-MM-DD (weekly)`, `(deep)` or `(catch-up)`. Its
sections:

| Section | Who writes it |
|---|---|
| Week in review | rendered: the window, sessions n of m core, the `Missed:` line with each tag, the sessions, results and e1RM tables, the flags, the week's notes and the cardio snapshot; on a deep record, the misses since the last deep check-in |
| Coach's read | the coach's prose: one or two sentences on the week, then adherence as you confirmed it, notable sets, anything off-plan, your read (sleep, runs, niggles, next week), and the three weight and nutrition lines |
| Decisions | the coach's prose, opening with the block status line, then what changed and why (or "stay the course"), anything deferred, and the adherence decision line when it applies |
| Block planning | deep records only: the light-week outlook, whether the goals and phase plan in `profile.md` is stale, what the next block should emphasise, the research line, and the body composition line |
| The week ahead | a Day / Session table, one-off changes called out, one closing line on the week's focus, and the approved prescription in a collapsed appendix |

Rendered regions are never edited by hand: the coach corrects the data
and re-renders with `checkin skeleton --refresh`, which leaves every
other byte as it was. Prose outside the regions stays under 600 words on
a weekly or catch-up record and 1,000 on a deep one; `coach check`
warns past that.

The hand-written lines follow
[`reference/record-formats.md`](../../reference/record-formats.md). The
block status line is copied from the last `block close` or
`block decide`, never written by hand:

```markdown
Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>
```

The adherence decision line follows it only when the adherence trigger
was presented or an under-80 % override was agreed, as
`python3 -m coach structure decide` prints it:

```markdown
Adherence trigger: <n> % over 4 weeks: adopted | declined: <reason> | deferred to <date>
```

An override adds the session after the outcome, for example
`Adherence trigger: 76 % over 4 weeks: adopted (override: adds Sat
conditioning)`.

## What follows

**A hold-steady week** (a weekly-tier check-in with no structural
change, no new or worsening niggle, no goals or phase flag, nothing
different next week, and only progression-scheme changes) gets no
separate check-in summary: it and the coach's brief collapse into one
short message. Deep check-ins and light weeks never take that path.

**Otherwise the coach proposes adjustments** with rationale and
trade-offs, and changes the program only after you approve. It updates
`profile.md` (e1RMs, watch notes, the last-reviewed date, and Coach's
notes with your confirmation), maintains the niggle log, records the
confirmed rotation position, and re-renders the program pages.

**A light week proposed** at the ceiling or on two triggers is presented
with its reason. Your answer is recorded with
`python3 -m coach block decide --outcome adopted` or
`--outcome declined --reason "<why>"`. A decline at the ceiling is
proposed again at the next check-in.

**The adherence decisions:**

- **Under 70 %**, the check-in must present a smaller schedule with the
  same weekly hard sets per muscle (rn:deloads.6): a Day / Session table
  sized to the average sessions you trained per week over the four
  weeks, rounded up, minimum two; a before/after table of weekly hard
  sets per muscle, kept equal; each session within your time limits and
  about 11 fractional hard sets per muscle (an indirect set counts as
  half; rn:volume-frequency.2, rn:volume-frequency.3); and anything
  trimmed, named. You adopt, decline with a reason, or defer to a date.
  A declined proposal is not presented again until four ordinary weeks
  have passed; a deferred one comes back at the first check-in on or
  after its date; an adopted one goes to `/new-program`'s redesign path.
- **Under 80 %**, the coach proposes no new recurring session, including
  conditioning and optional sessions, and pushes back if you ask for one
  (rn:deloads.7). Exercise swaps within a session are fine. If you
  override, the adherence decision line records the session it adds.

Both thresholds are coaching heuristics, not research cut-offs.

**The hand-over.** Once decisions are agreed, the coach starts
`/program-week` for the coming week: normal mode on a normal week, light
mode when a light week is agreed, constrained mode for travel or limited
kit you named in Next week (reshuffle when only the days move), and a
recorded planned break for days with no training at all. Decisions
agreed at the check-in do not pre-approve the week: the programming
pass still presents its coach's brief and waits for your "go", which
then approves every write its closing line names. Once the week's
overlay is approved, the record is refreshed with its prescription.
[Programming the week](programming-the-week.md) covers that pass.

## The catch-up check-in

When more than 10 days have passed since the last check-in, the Sunday
message becomes a catch-up card. It has no per-session fields: one
summary row per week of the gap, the proposed **return week** (its
band, days off, load and set change, RPE cap, and each session's lines),
the numbered questions (the gap, now, Food or Bodyweight, next week),
then the write line and "Reply ok to accept all of this, or answer any
of 1–n."

This card comes from a test workspace after a 28-day gap:

```text
Check-in for Mon 14 Sep – Sun 11 Oct (catch_up — 28 days since the last check-in, over 10).

| Week of | Core trained | Missed | Coach-led done | Workouts |
| --- | --- | --- | --- | --- |
| 14 Sep | 1 of 2 | untagged 1 | — | 1 |
| 21 Sep | 0 of 2 | untagged 2 | — | 0 |
| 28 Sep | 0 of 2 | untagged 2 | — | 0 |
| 5 Oct | 0 of 2 | untagged 2 | — | 0 |

Weeks with no overlay in force are planned from the schedule rule.

Return week from Mon 12 Oct: return band 22-42 after 28 days off, so loads −10 % and one working set fewer per exercise.
- Mon 12 Oct Session A: Back Squat (Barbell) 2×5 @ 90 RPE 7 · Bench Press (Dumbbell) 2×8–10 @ 22.5/hand (Hevy: 45) RPE 8
- Thu 15 Oct Session B: Single Arm Row (Dumbbell) 2×10 @ 27.5 RPE 8 · Pull Up 2×8 @ BW RPE 8

Flags: `stale_prescription` (Back Squat (Barbell), Bench Press (Dumbbell), Single Arm Row (Dumbbell), Pull Up).

1. The gap. One tag for the whole gap (time / sleep / ill / family / skipped / other), or one per session if it was mixed. If you were ill: have you been 48 hours symptom-free?
2. Now. Anything hurting, or different about kit, travel or schedule?
3. Food.
   Readings for the last 7 days (Mon 5 Oct – Sun 11 Oct) only, not the whole gap since Mon 14 Sep.
   a. trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein) · days logged
   b. anchors most days (y/n)?
   c. food exceptions next week: who cooks which nights, office-day changes, meals out?
4. Next week. Which days can you train next week?

Reply "go" to train this and write: Session A, Session B (Hevy).
Reply ok to accept all of this, or answer any of 1–4.
```

**"ok" alone is a complete check-in**: the misses stay untagged, nothing
new to report, the Food readings not supplied, and the return week as
shown, written to Hevy (without Hevy, approved only). The coach proposes
the return week for real, checks it matches the card line for line,
then approves it and pushes it without asking again. If anything changed
since the card, it presents the new return week and waits.

One tag for the whole gap goes in with
`python3 -m coach checkin tag-gap --tag <tag>`; tags per session go in
as a normal reply does. An `ill` tag brings in the illness rule, so the
return week changes and is presented again, and the card then ends
"Answer any of 1–n." instead: a bare "ok" confirms nothing until you
say you have been 48 hours symptom-free. Food readings cover the last 7
days only, recorded as one reading dated the check-in, and nothing for
the earlier weeks of the gap.

A reply that mentions illness, travel or no kit gets the **return
brief** from `python3 -m coach checkin return-brief`: the gap in one
sentence, what the return week does, each session's lines, what happens
after (normal progression from the loads the return week logs), and the
write line. After illness it adds the illness rule's safety lines. One
"go" approves it and every write its last line names. The return bands
themselves are in [Blocks and light weeks](blocks-and-light-weeks.md).

## Run mode

With `mode = "run"` in `config.toml`'s `[coaching]` table, you run your
own program as written. Progression, return weeks, validity checks,
light weeks and every block rule work exactly as in coach mode. What
changes:

- Structural flags (a restructure required, a blocked new session, a
  volume undershoot, a session's volume high, a dose coverage gap, a
  pending dose target) come out at `info` with a message starting
  "run mode: ", and the coach mentions them as information only.
- Adherence is still reported, but the coach presents no restructure or
  smaller schedule and records no adherence decision unless you ask for
  a restructure yourself. The adherence trigger never makes a run-mode
  check-in deep.
- The deep tier skips its structure review (weekly balance, junk volume,
  what the next block should change), proposes no swap, new session or
  redesign, and never offers `/new-program`.
