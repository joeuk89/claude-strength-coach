---
name: goals
description: Use when the athlete wants to set or revise their training and physique goals — target weight, phase (bulk/cut/maintain), eating strategy, or MacroFactor setup. Triggers include "/goals", "revise my goals", "should I bulk or cut", "I want to get lean/shredded/bigger", "update my targets", a phase boundary arriving, or a deep check-in flagging that goals are stale.
---

# Goals & targets revision

A coaching conversation that turns "what the athlete wants" into a
recorded plan: target weight (or body-comp outcome), phase sequence, trend
rate, eating strategy, and — if they use MacroFactor — the exact
configuration for it. The result lives in the **Nutrition & goals**
section of `profile.md`, which check-ins read.

**Division of labour (MacroFactor users):** MacroFactor is the nutrition
engine — it estimates TDEE from logged food + weight and auto-adjusts
daily targets weekly. This repo decides the *strategy* (phase, trend rate,
protein floor, goal weight) and records it. Never build a competing
calorie calculator; if a number needs computing, MacroFactor computes it.

**Without MacroFactor:** the strategy is the same, but the output is plain
targets (daily calories, protein) the athlete tracks however they like,
and check-ins lean on scale-weight trend to correct course.

## 1. Gather current state

- Read `profile.md`, `routine/program.md` (if it exists), and the newest
  file in `check-ins/` (if any).
- Ask the athlete for (skip anything the conversation already covered):
  - A **fresh weigh-in** (morning, before food; record in their preferred
    units with the metric value alongside). If they don't have one to
    hand, agree the strategy now and confirm the numbers after their next
    morning weigh-in.
  - MacroFactor's current **trend weight**, **TDEE estimate**, and targets
    (kcal, protein) — **if** they use it and a program is already set up.
    On a first run MacroFactor may be fresh or empty: proceed on the scale
    weigh-in alone and let its estimates mature. (For Hevy users,
    `body_measurements` is the only other weight source and is usually
    stale — check the date.)
  - How training and recovery feel; anything coming up (travel, events)
    that affects the timeline.
- **Scope check:** even a yes/no entry point ("should the bulk still
  start?") runs the full flow if profile fields are TBD or stale. If the
  plan on file is current and the athlete is only confirming a penciled
  phase change, a light confirm-and-record pass is enough.

## 2. The athlete states the goal

In their own words ("get shredded", "bulk to 200", "recomp"). Probe until
it's concrete: what does success look like, by roughly when, and what are
they willing to trade (a cut costs some strength progress; a bulk adds
some fat).

## 3. Research, then agree the plan

Research current best practice online for the specific decision (rates,
target ranges for their stats) and cite sources — don't rely on memory
alone. Anchors that must survive any research:

- No extreme cuts or bulks. Sustainable only.
- Bulk: ~+0.25–0.5 lb/week. Cut: lose no faster than ~0.5–1%
  bodyweight/week, slower when close to the goal. Recomp at maintenance is
  a legitimate choice for a returning or newer lifter with elevated body
  fat.
- Protein ~1.6–2.2 g/kg (top of range while cutting).
- The weekly weigh-in + check-in loop, not the initial estimate, is the
  real measurement instrument — the plan corrects as the trend comes in.

Agree with the athlete: **goal weight** (or body-comp outcome), **phase
sequence** with rough dates, **target trend rate per phase**, and **what
triggers the next phase** (a date, a weight, a look, a strength
milestone). Conditional triggers are fine — record the condition, and the
check-in that observes it fire records the phase change.

## 4. Output the nutrition setup

**MacroFactor users:** give exact setup steps — goal type
(gain/lose/maintain), rate, macro program and protein setting, and
**calorie shifting** so higher-output days (per the schedule in
`profile.md`) get more calories if the athlete wants that. Their app UI is
the source of truth — walk it with them and adjust names to what they
actually see.

**Everyone else:** compute the maintenance estimate from a transparent
method — a quick bodyweight × activity-factor figure, or a standard
equation like Mifflin–St Jeor from the profile stats — then state the
daily calorie target (that estimate ± the phase adjustment), the protein
target, and how to track them. Say plainly it's a rough starting point
the weekly weigh-in trend will correct. (The "no calculator" rule above
is a MacroFactor division of labour — with no MacroFactor, a transparent
estimate here is exactly right.)

## 5. Flag training implications

Say what the new phase means for the routine (volume on a cut, deload
timing, cardio load) — but route actual routine edits through the normal
flow: propose, show before/after, get approval, re-check the days either
side.

## 6. Record it

Update the **Nutrition & goals** section of `profile.md` (phase, goal,
trend rate, targets, app config summary, revision date) — with the
athlete's confirmation, like any profile edit. **If the phase is written
in more than one place, sync them all in the same edit** (e.g. a phase
word in `routine/program.md`'s header). Bump `profile.md`'s
`_Last reviewed_` date. Check-ins take it from here: they track the trend
against this plan and send the athlete back to `/goals` when the phase
plan itself needs rethinking.
