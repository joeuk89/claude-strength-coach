---
name: check-in
description: Use when the athlete wants a training check-in or progress review — weekly by default, with a deeper review on deload weeks or when one is overdue. Triggers include "/check-in", "check in", "weekly check-in", "progress review", "how's my training going", "let's review my progress".
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

- This week or next is the penciled **deload week** in
  `routine/program.md` — deloads are the natural block boundary.
- **6+ weeks** since the last deep check-in. Records without a tier marker
  count as deep; the first check-in ever runs deep.
- The athlete asks for one.

The Sunday message's first line names the tier and why; the athlete can
override. Mark the tier in the record's title line.

## 2. Pull the data

The window runs from the last check-in to today (excluding workouts the
last record already covered) — normally ~1 week, but handle longer lapses
the same way, just say more about less. **Deep tier:** for the trend
analysis, extend the lookback to the last deep check-in (~6 weeks) — one
week can't show a trend.

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
6. **Nutrition** — MacroFactor users: trend weight · expenditure ·
   targets (kcal / protein) · last 7 days' average (kcal / protein). A
   dashboard screenshot is accepted. Without MacroFactor: this week's
   morning weigh-ins, and roughly how eating went. Nutrition setup still
   TBD in `profile.md`: one morning scale weight.
7. **Meal plan** — what stuck, what got swapped?
8. **Next week** — anything different: travel, schedule, kit, illness?

**Leave out a field that cannot apply** and renumber the rest from 1: no
coach-led sessions in the window → no Coach-led field; no cardio in the
athlete's week → no Runs field; no dated plan in `nutrition/` covering
the window → no Meal plan field. **A fact the log already answers is
stated for confirmation, not asked.** If the athlete's opening message
already covers the fields, don't send the template; leave out any single
field it already answers.

Reference template (wording may be tightened; the fields and their order
are fixed):

```
Check-in for <window> (<weekly|deep> — <reason>).
1. Sessions. Hevy shows: Mon Lower A ✔, Tue PT (logged: bench, rows), Thu Upper B ✔.
   Not logged: Wed Pull, Sat Arms. Tag each miss: time / sleep / ill / family / skipped / other.
   Add anything you trained but didn't log.
2. Coach-led. What did PT Tue cover? From the log it looks like chest/back, so next week is Week B. Correct me if not.
3. Runs. How many, and total distance?
4. Sleep. One line: average hours a night (from your watch or phone if it tracks sleep), and how it felt.
5. Niggles. Anything new? Left knee (watching): quiet or still there?
6. Nutrition. MacroFactor: trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein). A screenshot works.
   No MacroFactor: this week's morning weigh-ins, and roughly how eating went.
7. Meal plan: what stuck, what got swapped?
8. Next week. Anything different: travel, schedule, kit, illness?
```

**Deep tier:** the same message. Any deep-only asks follow the last field,
numbered on.

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
  off prescription (RPE 9.5s against a prescribed 7).
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
- Intensity honesty (logged vs. prescribed RPE), session durations vs. the
  time limits in `profile.md`, junk volume.
- Weekly balance: does the program's balance picture still match what's
  actually being trained?

## 5. Weight & nutrition check (every check-in)

**If the athlete uses MacroFactor** (per `profile.md`): take the reply's
Nutrition field — **trend weight**, **expenditure**, the **kcal/protein
targets**, and the **last 7 days' average** (adherence to those
targets). Then compare:

- Trend weight vs. the **target trend rate** in `profile.md` (Nutrition &
  goals). One odd week is noise; a **2–3-week trend** off target is a
  flag. MacroFactor auto-adjusts targets weekly — usually the right
  response is "let it work and keep logging", not manual overrides.
- If the **phase itself** looks wrong (trend says cut while the plan says
  bulk, a phase trigger arrived, or the goal has changed) — point the
  athlete at `/goals` rather than tweaking numbers here.

**Without MacroFactor:** take the morning weigh-ins and the eating read
from the Nutrition field; compare the weight trend across recent
check-ins against the target trend rate in `profile.md`.

If `profile.md` shows nutrition setup still TBD, just record the scale
weight and prompt `/goals` to get set up.

If a dated plan in `nutrition/` covers (part of) this window, the Meal
plan field said how it went — note learnings for the next `/meal-plan`
run (recipe-bank changes belong in `/recipes`, not here).

Record the numbers in the check-in and refresh them in `profile.md`.

## 6. Write the record

Create `check-ins/YYYY-MM-DD.md`. Weekly template:

```markdown
# Check-in — YYYY-MM-DD (weekly)

**Window:** <start> → <end> · **Sessions:** n of ~m planned · **Missed:** <day> <session> (<tag>), … or none

## Headline
1–2 sentences: the state of the week in plain words.

## Training
Adherence, notable sets, anything off-plan worth naming.

## Weight & nutrition
Weight (trend or scale) · targets · adherence. Trend vs. target rate — on track?

## Athlete's read
Sleep, runs, niggles, next week — their words, summarized. A field the
reply didn't answer reads "not supplied".

## Decisions
What changed and why (or "stay the course"). Anything deferred.

## The week ahead — <dates>
| Day | Session |
| --- | --- |
| Mon | ... |
One-off changes called out. On normal weeks `/program-week` expands
this section with the per-exercise prescription tables — the overlay —
followed directly by its `**Written to Hevy:**` line. The section
always ends with one line: the focus of the week.
```

Deep records use the same skeleton titled `(deep)`, with **Training**
expanded to the full analysis (e1RM trends per lift, drift, balance,
intensity honesty) and a **Block planning** section: deload timing,
whether the goals/phase plan in `profile.md` is stale (if so, prompt
`/goals`), and what the next block should emphasize.

## 7. Act on it

- **Hold-steady week** (defined in program-week step 3): present no
  separate check-in summary — it and the coach's brief collapse into
  program-week's short brief. Deep check-ins and deload weeks never take
  that path.
- Otherwise, propose adjustments with rationale and trade-offs. **Only edit
  `routine/` files after the athlete approves** — on normal weeks the
  edit lands via program-week's write step (below); re-check the day
  before and after any edited day and the program's weekly balance.
- Update `profile.md`: weight/nutrition numbers every time; e1RMs, watch
  notes, and `_Last reviewed_` when they move (deep tier refreshes the
  whole file). Add or retire **Coach's notes** as patterns emerge or
  resolve — with the athlete's confirmation.
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
- On a deload-week check-in, invoke the **one-off-week** skill (deload
  mode) to build the deload week itself — its schedule and sessions
  fill this record's "The week ahead" section, and it handles the Hevy
  writes.
