---
name: check-in
description: Use when the athlete wants a training check-in or progress review — weekly by default, with a deeper review on deload weeks or when one is overdue. Triggers include "/check-in", "check in", "weekly check-in", "progress review", "how's my training going", "let's review my progress".
---

# Training check-in

Act as the athlete's coach reviewing their training. Two tiers: a
**weekly** check-in (~10 minutes — adherence, weight + nutrition, week
ahead) and a **deep review** (the full block-level look). The output is a
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

Tell the athlete which tier you're running and why; they can override.
Mark the tier in the record's title line.

## 2. Pull the data

The window runs from the last check-in to today (excluding workouts the
last record already covered) — normally ~1 week, but handle longer lapses
the same way, just say more about less. **Deep tier:** for the trend
analysis, extend the lookback to the last deep check-in (~6 weeks) — one
week can't show a trend.

**With Hevy** (key in `.env`): API details in `reference/hevy-api.md`.
Page through `GET /v1/workouts` (`pageSize=10`, newest first) past the
window start. `GET /v1/body_measurements` is a fallback weight source only.

**Without Hevy:** ask the athlete to describe the week — which sessions
happened, notable sets, anything skipped or changed.

**Coach-led sessions (PT, classes) are often logged worse than solo
sessions — always ask which ones actually happened.** Never compute
adherence from the API alone. Check Coach's notes for this athlete's known
logging habits.

## 3. Analyze — plan vs. reality

Convert to the athlete's preferred units (in `profile.md`) before showing
them anything. **Judge against the effective prescription**, not the base
plan — check `routine/program.md` and the last check-in for an active
on-ramp, deload, or one-off week shape first.

**Weekly tier** — keep it light:
- Adherence: sessions trained vs. planned, including coach-led ones
  (that's the "n of ~m" in the record header; note cardio separately);
  which days slipped.
- Notable sets: PRs, rep-range top-outs due a load increase, anything way
  off prescription (RPE 9.5s against a prescribed 7).
- Priority work: if `routine/program.md` names priority lifts or
  protocols, did they happen as written? Watch for this athlete's known
  drift patterns (Coach's notes).

**Deep tier** — all of the above, plus:
- Per main lift: loads/reps across the window, Epley e1RM trend
  (`weight × (1 + reps/30)`) — trend, not gospel. Flag stalls (same
  load+reps 3+ sessions) and progression-scheme violations.
- Exercise drift vs. the plan — structural drift means `/hevy-sync` is
  due; offer it (Hevy users only).
- Intensity honesty (logged vs. prescribed RPE), session durations vs. the
  time limits in `profile.md`, junk volume.
- Weekly balance: does the program's balance picture still match what's
  actually being trained?

## 4. Weight & nutrition check (every check-in)

**If the athlete uses MacroFactor** (per `profile.md`): ask for three
numbers off the dashboard — current **trend weight**, **TDEE estimate**,
and the **kcal/protein targets** — plus rough adherence to them. Then
compare:

- Trend weight vs. the **target trend rate** in `profile.md` (Nutrition &
  goals). One odd week is noise; a **2–3-week trend** off target is a
  flag. MacroFactor auto-adjusts targets weekly — usually the right
  response is "let it work and keep logging", not manual overrides.
- If the **phase itself** looks wrong (trend says cut while the plan says
  bulk, a phase trigger arrived, or the goal has changed) — point the
  athlete at `/goals` rather than tweaking numbers here.

**Without MacroFactor:** ask for current scale weight (morning, before
food) and rough eating adherence; compare the weight trend across recent
check-ins against the target trend rate in `profile.md`.

If `profile.md` shows nutrition setup still TBD, just record a scale
weight and prompt `/goals` to get set up.

Record the numbers in the check-in and refresh them in `profile.md`.

## 5. Interview the athlete

One question at a time, only what the data can't show: sleep, recovery,
joints/aches, cardio, how any coach-led sessions felt, **anything unusual
about the coming week** (schedule clashes, travel), and — if the program
rotates — **where in the rotation the coming week lands**: confirm, don't
assume.

Skip what the conversation already answered.

## 6. Write the record

Create `check-ins/YYYY-MM-DD.md`. Weekly template:

```markdown
# Check-in — YYYY-MM-DD (weekly)

**Window:** <start> → <end> · **Sessions:** n of ~m planned

## Headline
1–2 sentences: the state of the week in plain words.

## Training
Adherence, notable sets, anything off-plan worth naming.

## Weight & nutrition
Weight (trend or scale) · targets · adherence. Trend vs. target rate — on track?

## Athlete's read
Sleep, recovery, cardio — their words, summarized.

## Decisions
What changed and why (or "stay the course"). Anything deferred.

## The week ahead — <dates>
| Day | Session |
| --- | --- |
| Mon | ... |
One-off changes called out. End with one line: the focus of the week.
```

Deep records use the same skeleton titled `(deep)`, with **Training**
expanded to the full analysis (e1RM trends per lift, drift, balance,
intensity honesty) and a **Block planning** section: deload timing,
whether the goals/phase plan in `profile.md` is stale (if so, prompt
`/goals`), and what the next block should emphasize.

## 7. Act on it

- Propose adjustments with rationale and trade-offs. **Only edit
  `routine/` files after the athlete approves**; re-check the day before
  and after any edited day and the program's weekly balance.
- Update `profile.md`: weight/nutrition numbers every time; e1RMs, watch
  notes, and `_Last reviewed_` when they move (deep tier refreshes the
  whole file). Add or retire **Coach's notes** as patterns emerge or
  resolve — with the athlete's confirmation.
- If the program tracks a current position in a rotation, update it in
  `routine/program.md`.
- If routine changes were agreed and the athlete uses Hevy, offer
  `/hevy-sync`.
