---
name: check-in
description: Use when the athlete wants a training check-in or progress review — weekly by default, with a deeper review when one is overdue, a light week is being proposed, or adherence has dropped. Triggers include "/check-in", "check in", "weekly check-in", "progress review", "how's my training going", "let's review my progress".
---

# Training check-in

Act as the athlete's coach reviewing their training. Two tiers: a
**weekly** check-in (~10 minutes — adherence, weight + nutrition, week
ahead) and a **deep review** (the full block-level look). Both open with
one **Sunday message** the athlete answers in one reply. The output is a
dated record in `check-ins/` plus any agreed updates.

If `profile.md` doesn't exist, stop and run `/setup` first.

## 1. Read the context and pick the tier

Read `profile.md` (including **Coach's notes**), `routine/program.md`, the
session files it indexes, and the newest file in `check-ins/` (plus the
newest **deep** one, if the newest is weekly).

Run a **deep** check-in when any of these is true, otherwise run **weekly**:

- **6+ weeks** since the last deep check-in. Records without a tier marker
  count as deep; the first check-in ever runs deep.
- **A light week is being proposed** (step 4: the hard-week count
  reached the ceiling, or two fatigue triggers fired).
- **The adherence trigger fires** (step 4: under 70 %).
- The athlete asks for one.

The coming week being a deload is not a trigger on its own. Judge the
light-week and adherence triggers from the log before sending the Sunday
message; if the reply changes the picture (a second fatigue trigger, a
coach-led session that didn't happen), switch to deep and say so.

The Sunday message's first line names the tier and why; the athlete can
override. Mark the tier in the record's title line.

**One-time conversion.** If `routine/program.md`'s header still carries a
scheduled deload date from the old calendar cadence and no block status
line (step 6), estimate the hard-week count from the check-in history
since the last deload. State the estimate for confirmation after the
Sunday message's last field, numbered on; step 7 writes the status line
in place of the dated one.

## 2. Pull the data

The window runs from the last check-in to today (excluding workouts the
last record already covered) — normally ~1 week. **Deep tier:** for the
trend analysis, extend the lookback to the last deep check-in (~6 weeks)
— one week can't show a trend. **Adherence and the hard-week count** need
more history: read the check-in records and logs back as far as step 4
needs.

**Gap check.** Count the days from the last lifting workout of any
kind — solo, or coach-led as the log or the reply shows it — to the
first session of the coming week, the same count program-week makes.
Over 10 days means the coming week is a **return week** under the
return rule in `CLAUDE.md` "Coaching principles": say so in the Sunday
message's first line ("… — 16 days off by Tuesday's session, so next
week is a return week"). An `ill` miss tag or reported illness in the
gap brings in that rule's illness conditions too. Program-week applies
the rule.

**With Hevy** (key in `.env`): API details in `reference/hevy-api.md`.
Page through `GET /v1/workouts` (`pageSize=10`, newest first) past the
window start. **Read every workout's `description` and each exercise's
`notes`** — these are the athlete's own words on how the session went
(fatigue, sleep, a target that was too high, a niggle, why sets were
dropped). They're the readiness signal the numbers can't show, so quote
them in the analysis and let them shape the decisions. `GET
/v1/body_measurements` is a fallback weight source only.

**STALE check (Hevy).** GET the mapped routines for the coming week's
sessions and judge each against its own baseline: the newest overlay
in `check-ins/` with a table for its session. A routine is **STALE**
when that overlay's `**Written to Hevy:**` line doesn't name it, or
names it with a timestamp after the routine's `updated_at`: that pass
didn't write it, so it still holds older notes. A mid-week reprogram's
line names only the days it rewrote, so it never makes the other
routines STALE. List each STALE routine with its last-written date
(its `updated_at`). No `**Written to Hevy:**` line in `check-ins/` yet
→ skip the check. On a normal week the list appears in program-week's
coach's brief (on a hold-steady week, its close-out), which reuses
these routines for its in-app edit check; the pass rewrites every
routine in the span either way. Skip the check when the coming week is
a deload or other one-off week — `/one-off-week` writes fresh temp
routines for it.

**Without Hevy:** there is no log to pre-fill, so the Sessions field of
the Sunday message asks the athlete to describe the week — which sessions
happened, notable sets, anything skipped or changed.

**Coach-led sessions (PT, classes) are often logged worse than solo
sessions** — the Coach-led field of the Sunday message confirms which
ones happened. Never compute adherence from the API alone. Check Coach's
notes for this athlete's known logging habits.

## 3. Send the Sunday message

Send **one** message that pre-fills what the log shows and asks only what
it can't, then wait for the athlete's single reply. They answer by number.
This replaces an interview: no question-by-question turns.

The first line names the window and the tier with its reason. Then the
fields, always in this order:

1. **Sessions** — logged vs. planned for the window, day by day. List each
   planned session with no logged workout and ask for one tag per miss:
   `time / sleep / ill / family / skipped / other`. Optional sessions need
   no tag. Ask for anything trained but not logged.
2. **Coach-led** — ask what each coach-led session in the window covered.
   State what its log shows and the inferred rotation position for
   confirmation.
3. **Runs** — count and total distance. Runs the athlete logged as Hevy
   workouts are read from the log and stated, not asked.
4. **Sleep** — always asked, in one line: "average hours a night (from
   your watch or phone if it tracks sleep), and how it felt".
5. **Niggles** — anything new? Name each open niggle-log row (`watching`
   or `easing`) and ask whether it is quiet or still there.
6. **Food** — the food questions, worded as `python3 -m coach nutrition
   status` gives them in `data.questions`, one line each:
   1. Readings: the app's numbers (trend weight · expenditure · targets
      (kcal/protein) · 7-day average (kcal/protein) · days logged), or,
      without an app, this week's morning weigh-ins and average daily
      protein if they track it. A dashboard screenshot is accepted.
   2. Habits: anchors most days (y/n)? Anything in the plan that didn't
      work? The anchors ask is left out when no anchors are on file.
   3. Next week: food exceptions — who cooks which nights, office-day
      changes, meals out. Asked **only when a standing weekly template
      exists** (`[nutrition.template]` in `config.toml`); `data.questions`
      leaves it out otherwise.

   Nutrition not enabled (`data.enabled` is false): one morning scale
   weight instead.
7. **Next week** — anything different: travel, schedule, kit, illness?

**Leave out a field that cannot apply** and renumber the rest from 1: no
coach-led sessions in the window → no Coach-led field; no cardio in the
athlete's week → no Runs field. **A fact the log already answers is
stated for confirmation, not asked.** If the athlete's opening message
already covers the fields, don't send the template; leave out any single
field it already answers.

Reference template (wording may be tightened; the fields and their order
are fixed; the Food field's a/b/c wording comes from `data.questions`):

```
Check-in for <window> (<weekly|deep> — <reason>).
1. Sessions. Hevy shows: Mon Lower A ✔, Tue PT (logged: bench, rows), Thu Upper B ✔.
   Not logged: Wed Pull, Sat Arms. Tag each miss: time / sleep / ill / family / skipped / other.
   Add anything you trained but didn't log.
2. Coach-led. What did PT Tue cover? From the log it looks like chest/back, so next week is Week B. Correct me if not.
3. Runs. How many, and total distance?
4. Sleep. One line: average hours a night (from your watch or phone if it tracks sleep), and how it felt.
5. Niggles. Anything new? Left knee (watching): quiet or still there?
6. Food.
   a. MacroFactor: trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein) · days logged. A screenshot works.
      (No app: this week's morning weigh-ins · average daily protein, if you track it.)
   b. Anchors most days (y/n)? Anything in the plan that didn't work?
   c. (only with a standing weekly template) Food exceptions next week: who cooks which nights, office-day changes, meals out?
7. Next week. Anything different: travel, schedule, kit, illness?
```

**Deep tier:** the same message. Any deep-only asks follow the last field,
numbered on.

**Body composition** (waist, body fat, progress photos) is a deep-only
ask, never a weekly one. Ask it only when both hold:

- the goals or a phase trigger in `profile.md` use waist, body fat or
  photos, or the phase is a cut or recomp; and
- no deep record has a reading yet, or the last reading is 4 or more
  weeks old (the newest deep record's **Body composition** line says).

Ask for waist, a body-fat reading if they have one, and their own
one-line read of their progress photos. **Photos stay with the athlete
and never go into the repo** — record only their read. A reading the
reply leaves out is recorded once as "not supplied" and not asked again
before the next deep check-in.

**Rotation position.** If the program rotates, infer where the coming
week lands and state it for confirmation — never ask it as its own
question. Sources, in order: the coach-led session's log, the
current-position line in `routine/program.md`, the newest check-in. State
it in the Coach-led field, or in the Next week field when there is no
Coach-led field. If the sources disagree, state the first one and name
the disagreement.

**Missed sessions** get the one-word tag and nothing more: no follow-up on
the reason. A miss the reply leaves untagged is recorded as `untagged`.

**At most one follow-up turn**, and only for a gap that blocks
programming: an unresolved rotation position, a new niggle's severity, or
nutrition numbers you can't read. Ask every such gap in that one turn.
Record any other gap once as "not supplied" and move on.

## 4. Analyze — plan vs. reality

Convert to the athlete's preferred units (in `profile.md`) before showing
them anything. **Judge against the effective prescription**, not the base
plan — the last check-in's week-ahead overlay (per-exercise targets, if
`/program-week` wrote one) plus any active on-ramp, deload, or one-off
week shape in `routine/program.md`. With an overlay, adherence is
concrete: did the athlete hit the prescribed load × reps @ RPE?

**Weekly tier** — keep it light:
- Adherence: sessions trained vs. planned, including coach-led ones as
  the reply confirmed them (that's the "n of ~m" in the record header;
  note cardio separately); which days slipped, with their miss tags.
- Notable sets: PRs, rep-range top-outs due a load increase, anything way
  off prescription.
- RPE drift: check only **compound lifts** (multi-joint squat, hinge,
  lunge, press and pull patterns) and sets carrying a **recovery cap**.
  An exercise drifts when logged RPE is 1 or more over the target on 2
  or more working sets of one exposure. Drift on isolation work gets one
  summary line in the record ("isolation RPE ran about 1 high on curls
  and raises") and never drives a decision.
- Priority work: if `routine/program.md` names priority lifts or
  protocols, did they happen as written? Watch for this athlete's known
  drift patterns (Coach's notes).

**Deep tier** — all of the above, plus:
- Per main lift: loads/reps across the window, Epley e1RM trend
  (`weight × (1 + reps/30)`) — trend, not gospel. Flag stalls (same
  load+reps 3+ sessions) and progression-scheme violations.
- **Sanity-check dumbbell loads before reading anything into them.** An
  exact-2× (or ½ ×) step in a dumbbell exercise at unchanged reps *and*
  unchanged RPE is a logging-convention slip, not a strength change —
  Hevy stores the combined total across both arms, and single-arm work is
  the exception. Cross-check sibling exercises on the same dates: a slip
  usually shows up in more than one lift at once. Never let one set an
  e1RM or a PR. When history looks contaminated, confirm the actual
  per-hand weights with the athlete, correct the record, and say which
  prescriptions were derived from the bad data.
  See `reference/hevy-api.md` → "Dumbbell loads".
- Exercise drift vs. the plan — structural drift means `/hevy-sync` is
  due; offer it (Hevy users only).
- Intensity honesty: the RPE drift check on each exposure in the
  window, same scope and threshold — compound lifts and recovery-capped
  sets, 1 or more over the target on 2 or more working sets of one
  exposure. Sustained drift means drift in consecutive exposures of the
  same lift. Isolation drift stays one summary line, not a decision.
- Session durations vs. the time limits in `profile.md`, junk volume.
- Weekly balance: does the program's balance picture still match what's
  actually being trained?

**Both tiers — the hard-week count.** Class each week the window closes
by the rules in `CLAUDE.md` "Coaching principles" → Fatigue management:
a completed hard week adds one, a reset week ends the block and starts
the next one at zero, anything else leaves it. Then check this week's
four fatigue triggers: readiness from the reply and the workout notes,
compound RPE drift from the drift check above (two sessions running), a
niggle the Niggles field says was aggravated under load, and poor sleep
from the Sleep field. The same rules say when a light week is proposed,
watched or skipped.

**Both tiers — adherence.** Adherence = sessions trained ÷ sessions
planned over the **trailing four ordinary weeks**:

- Judge each week against the overlay in force that week. Coach-led
  sessions count, as the replies confirmed them; optional sessions are
  left out; a shortened session counts as trained.
- An **ordinary week** is any week except a deload or other light week,
  a one-off week (illness, travel, limited kit), or a week inside a
  layoff of 11+ days. Skip those and reach further back, at most 12
  weeks. Fewer than four ordinary weeks in that span → no trigger yet.

Adherence thresholds are coaching heuristics, not research cut-offs:

- **Under 80 %:** propose no new recurring session — no new session or
  weekly slot, conditioning and optional sessions included — and push
  back if the athlete asks for one. Exercise swaps within a session are
  not affected. An athlete override is recorded with the adherence
  decision line (step 6), naming the session it adds.
- **Under 70 % — the adherence trigger.** The check-in must present a
  smaller schedule in its decisions:
  - a Day / Session table sized to the average sessions actually trained
    per week over the four weeks, rounded up, minimum two;
  - a before/after table of weekly hard sets per muscle, kept equal;
  - each session within the time limits in `profile.md` and about 11
    fractional hard sets per muscle (an indirect set counts as half);
  - anything trimmed, named.

  The athlete adopts, declines with a reason, or defers to a date.
  Record it with the adherence decision line (step 6), which also sets
  when the proposal comes back.

## 5. Weight & nutrition check (every check-in)

**The framework rule:** for an athlete using a nutrition app, this
check-in gets **complete logging** into the app and reads the app's
numbers out. It **never states its own calorie target or calorie band**
and never runs a parallel calorie model. Fewer than 7 days logged → ask
for every day to be logged, with an estimate of the day or the missed
meal on a day they couldn't track and no half-logged days
(MacroFactor's guidance, in `/goals`). Record the days logged either
way.

**Record the reading.** Turn the Food field's numbers into one
reading:

```bash
python3 -m coach nutrition record --date <check-in date> \
  --trend-weight X --expenditure N --target-kcal N --target-protein N \
  --avg-kcal N --avg-protein N --days-logged N --anchors yes|no
```

Pass only what the reply gave; without an app, pass `--scale-weight`
(the mean of the week's morning weigh-ins) and `--avg-protein` if they
track it. Weights are in `[athlete] bodyweight_units`. A reading already
on file for the date exits 1: re-run with `--replace` only to correct
it. Then run `python3 -m coach nutrition status` and work from its
output. The numbers on file (phase, target trend rate, protein floor,
target and stretch, anchors, any override) are in `config.toml`'s
`[nutrition]` table; `nutrition status` returns them.

**Weight trend.** `data.trend` gives the rate per week over the latest
span of 14 days or more, next to `target_rate_per_week`; it is a number,
not a verdict. One odd week is noise; a **2–3-week trend** off target is
a flag. **With MacroFactor**, the app auto-adjusts targets weekly:
usually the right response is "let it work and keep logging", not a
manual override. **Without MacroFactor**, when a 2–3-week trend misses
the target rate, propose moving `[nutrition] kcal_target` by ~100–150
kcal/day in the direction the trend needs. With the athlete's yes, edit
it in `config.toml` and note the reason in Nutrition & goals in
`profile.md`. Never re-derive it from an equation; a fresh estimate
comes only from `/goals` with a new phase. If the **phase itself** looks
wrong (trend says cut while the plan says bulk, a phase trigger arrived,
or the goal has changed), point the athlete at `/goals` rather than
tweaking numbers here.

**Act on each flag** in `data.flags`:

- `protein_floor_raise` — average protein met the floor at the two most
  recent readings since `floor_since`. Propose raising the floor to
  `proposed_floor_g` (the step, capped at the target). With the
  athlete's yes, set `floor_g` to `proposed_floor_g` and `floor_since`
  to `proposed_floor_since` (the day after the latest counted reading,
  so this week's reading, taken under the old floor, doesn't count
  toward the next raise) in `[nutrition.protein]` in `config.toml`;
  MacroFactor users set the app's protein to the new floor the same
  day. No flag → the floor
  stays: missing it never lowers it; only `/goals` lowers it.
- `app_protein_mismatch` — the app's protein target is not the floor.
  Have the athlete set the app to the floor, unless the active override
  covers protein.
- `logging_incomplete` — fewer than 7 days logged: ask for every day to
  be logged, as in the framework rule above.
- `override_expired` — on or after its expiry date the override ends:
  remove `[nutrition.override]` from `config.toml`, tell the athlete
  they're back on the app's numbers (or, without an app, the calorie
  target on file), and record it. Its exit condition firing earlier ends
  it the same way. Renewal is not done here: it needs `/goals` with a
  fresh reason.
- `override_renewed_twice` — flag it in the record at every check-in
  while it stands, as a sign the plan itself needs changing.
- `no_recent_reading` — nothing recorded in the last 14 days: record
  this week's reading before reading anything else into the trend.

**Anchors:** note the "anchors most days" answer. A "no" two weeks
running is a cue to revisit the anchors in `/goals`, not to lower the
floor.

**Sleep gate.** Once the athlete has a sleep source (a watch or phone
that tracks sleep), take the trailing 14-day average: the tracker's own
figure, or the mean of this and the last check-in's tracked Sleep
fields. During a **deficit**, re-check the gate: under ~7 h fails it and
sends the athlete to `/goals` to move to recomp at maintenance. A gate
recorded as `pending measurement` gets its first measurement the same
way: under ~7 h confirms recomp; at or over it, offer `/goals` to
reconsider the deficit. Update the gate status in `profile.md`.

If `nutrition status` says `enabled: false`, just note the scale weight
in the record and prompt `/goals` to get set up.

**Deep tier, body composition:** when the reply carries a reading, read
it against the goal or phase trigger that uses it and against the last
reading. A trigger that fires sends the athlete to `/goals`.

If a dated plan in `nutrition/` covers (part of) this window, the Food
field's habits question said how it went — note learnings for the next
`/meal-plan` run (recipe-bank changes belong in `/recipes`, not here).

Record the numbers in the check-in's Weight & nutrition section; the
readings series holds them, so they no longer go into `profile.md`.

## 6. Write the record

Create `check-ins/YYYY-MM-DD.md`. Weekly template:

```markdown
# Check-in — YYYY-MM-DD (weekly)

**Window:** <start> → <end> · **Sessions:** n of ~m planned · **Missed:** <day> <session> (<tag>), … or none
Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>

## Headline
1–2 sentences: the state of the week in plain words.

## Training
Adherence, notable sets, anything off-plan worth naming.

## Weight & nutrition
Weight (trend or scale) · targets · adherence. Trend vs. target rate — on track?
Protein: <7-day avg> g vs floor <g> (<n> of 2 toward a raise | raised to <g> | under) · days logged <n>/7 · anchors most days: y/n
Override: none | active, expires <date> | expired <date> | renewal flagged · Sleep gate: <status> (deficit only)

## Athlete's read
Sleep, runs, niggles, next week — their words, summarized. A field the
reply didn't answer reads "not supplied".

## Decisions
What changed and why (or "stay the course"). Anything deferred.
Adherence trigger: <n> % over 4 weeks: adopted | declined: <reason> | deferred to <date>

## The week ahead — <dates>
| Day | Session |
| --- | --- |
| Mon | ... |
One-off changes called out. On normal weeks `/program-week` expands
this section with the per-exercise prescription tables — the overlay —
followed directly by its `**Written to Hevy:**` line. The section
always ends with one line: the focus of the week.
```

**The block status line** is the second header line, copied from
`routine/program.md`'s header after this check-in updates it (step 7).
`<names>` lists the fatigue triggers that fired this week (none → `triggers
0 of 4`). `<state>` is one of: `not due`, `watch`, `skipped (<n> hard
weeks)`, `proposed for wk of <D Mon> (<type>, <reason>)`, `agreed:
<type>, wk of <D Mon>`, or `declined (<reason>), proposed again next
check-in`.

**The adherence decision line** goes in Decisions only when the
adherence trigger was presented or an under-80 % override was agreed, in
that fixed shape, e.g. `Adherence trigger: 58 % over 4 weeks: deferred to
2026-11-02`. An override adds the session after the outcome: `Adherence
trigger: 76 % over 4 weeks: adopted (override: adds Sat conditioning)`.
A **declined** proposal isn't presented again until four ordinary weeks
have passed since the decision; a **deferred** one is presented again at
the first check-in on or after its date; an **adopted** one goes to
`/new-program`'s redesign path and isn't presented again for four
ordinary weeks. These rules and the hand-off apply only to the
smaller-schedule decision. An override line (one with `(override: …)`)
records the added session only: it never holds back or starts the
under-70 % trigger, and never goes to `/new-program`.

Deep records use the same skeleton titled `(deep)`, with **Training**
expanded to the full analysis (e1RM trends per lift, drift, balance,
intensity honesty) and a **Block planning** section: the light-week
outlook from the hard-week count, whether the goals/phase plan in
`profile.md` is stale (if so, prompt `/goals`), and what the next block should emphasize. When body
composition applies (step 3), Block planning ends with one line that
says when the next reading is due — the next check-in reads it:

```markdown
**Body composition:** waist <reading, "not supplied" or "not due"> · body fat <reading, "not supplied" or "not due"> · photos: <"athlete's one-line read", "not supplied" or "not due"> · **Last reading:** <date> · **Next reading due:** first deep check-in on or after <last reading + 4 weeks>
```

A reading taken today makes today the **Last reading** date. "Not
supplied" means it was asked and the reply left it out; "not due" means
it wasn't asked (step 3). Either way, carry the previous **Last reading**
date forward; with no reading ever, write "none" and make the next deep
check-in the due one.

## 7. Act on it

- **Hold-steady week** (defined in program-week step 3): present no
  separate check-in summary — it and the coach's brief collapse into
  program-week's short brief. Deep check-ins and deload weeks never take
  that path.
- Otherwise, propose adjustments with rationale and trade-offs. **Only edit
  `routine/` files after the athlete approves** — on normal weeks the
  edit lands via program-week's write step (below); re-check the day
  before and after any edited day and the program's weekly balance.
- Update `profile.md`: e1RMs, watch notes, and `_Last reviewed_` when
  they move (deep tier refreshes the whole file). Add or retire
  **Coach's notes** as patterns emerge or resolve — with the athlete's
  confirmation.
- **Maintain the niggle log** in `profile.md` (Injuries / limitations →
  a `### Niggle log` table: `Area · First noted · Last noted · Mentions
  · Status · Notes`; statuses `watching` / `easing` / `resolved`;
  create the subsection on its first entry). New complaint → new row;
  repeat mention → bump Last noted and Mentions; confirmed gone →
  `resolved`, but **keep the row** — recurrence is the signal this log
  exists to catch. Escalate — recommend a qualified professional and
  program around it meanwhile, never diagnose — when a niggle runs ~3
  consecutive check-ins, worsens, or interferes with prescribed
  training. Active niggles inform any routine change proposed today:
  no added load on an aggravated pattern.
- If the program tracks a current position in a rotation, update it in
  `routine/program.md`.
- **Update the block status line** in `routine/program.md`'s header —
  one line in the record's format (step 6), holding the hard-week count
  and trigger status — then copy it into the record's header. On the
  one-time conversion (step 1), the status line replaces the dated
  deload line.
- **A light week proposed** at the ceiling or on two triggers: present
  it with its reason. Agreed → invoke the **one-off-week** skill in
  deload mode (below). Declined → record the reason in the status line;
  at the ceiling, propose it again next check-in.
- **Adherence trigger adopted** (the smaller schedule, not an
  override) → hand off to `/new-program`'s redesign path with the agreed
  smaller schedule. Under 80 % adherence (step 4), propose no new
  recurring session, here or in program-week.
- On a normal (non-deload) week, once decisions are agreed, invoke the
  **program-week** skill — it computes per-exercise targets for the
  coming week, writes them to Hevy, and fills this record's "The week
  ahead" section. **Decisions agreed at this check-in don't pre-approve
  the week** — program-week still presents its coach's brief and waits
  for the athlete's reply before writing anything. One "go" to that
  brief approves the week and every write its closing line names — the
  Hevy routines and any structural `routine/` edits — so don't ask
  again before writing. Structural routine changes agreed today ride
  along in its write step; `/hevy-sync` stays for reconciliation outside
  the pass.
- When a light week is agreed, invoke the **one-off-week** skill
  (deload mode) to build it — its schedule and sessions fill this
  record's "The week ahead" section, it handles the Hevy writes, and it
  resets the hard-week count.
