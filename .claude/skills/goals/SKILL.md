---
name: goals
description: Use when the athlete wants to set or revise their training and physique goals — target weight, phase (bulk/cut/maintain), eating strategy, protein, or MacroFactor setup. Triggers include "/goals", "revise my goals", "should I bulk or cut", "I want to get lean/shredded/bigger", "update my targets", a phase boundary arriving, a nutrition override expiring or needing renewal, or a deep check-in flagging that goals are stale.
---

# Goals & targets revision

Turn "what the athlete wants" into a recorded plan: goal weight or
body-comp outcome, phases, trend rate, protein floor, target and stretch,
the protein anchors and any MacroFactor setup. The numbers go in
`config.toml` `[nutrition]`, the reasoning in `profile.md` (step 9).

**The framework rule (nutrition app users).** MacroFactor is the
nutrition engine: it estimates expenditure from logged food and weight
and adjusts the daily targets weekly. This repo decides the *strategy*
(phase, trend rate, goal weight, protein numbers, anchors), gets
**complete logging** into the app and reads the app's numbers out.
Complete logging means every day logged; on a day the athlete couldn't
track, they log an estimate of the day or the missed meal (a quick-add
of calories and protein). Per MacroFactor's own guidance, a day logged
by halves skews its targets most; an estimate within about 30 % of what
was eaten beats a blank day, and only a day they can't guess that
closely stays blank (rn:protein-energy-deficit.13). The repo **never
states its own calorie target or calorie band** for an app user and
never runs a parallel calorie model. Any departure from the app's
numbers is a dated nutrition override (step 7).

**Without a nutrition app:** the same strategy, plus one transparent
starting calorie estimate per phase that only the weight trend moves
after that (step 6). Protein, anchors, overrides and the sleep gate apply.

## 1. Gather current state

Read `profile.md`, `routine/program.md` and the newest file in
`check-ins/` (if they exist), and run `python3 -m coach nutrition
status` for the numbers on file and the latest reading. Ask for anything
the conversation hasn't covered:

- A **fresh weigh-in** (morning, before food; in their preferred units
  with the metric value alongside). Without one to hand, agree the
  strategy now and confirm the numbers after the next morning weigh-in.
- MacroFactor's **trend weight**, **expenditure**, targets (kcal,
  protein) and **7-day average protein**, if they use it and a program
  is set up. On a first run the app may be empty: proceed on the scale
  weigh-in alone. (For Hevy users, `body_measurements` is the only other
  weight source and is usually stale — check the date.)
- **Recent protein intake** without the app: a typical day's protein,
  estimated together from two or three recent days.
- A **body-fat reading**, if they have one: number, method and date.
- **Sleep**: dated nightly hours or an explicitly identified period
  average, from manual self-report or a tracker; otherwise their words.
- How training and recovery feel; anything coming up (travel, events).

**Scope check:** a yes/no entry point ("should the bulk still start?")
runs the full flow if profile fields are TBD or stale. A planned phase
change on a current plan needs only a confirm-and-record pass, renewing an
override only step 7 and the record. Both still end with step 10.

## 2. The athlete states the goal

In their own words ("get shredded", "bulk to 200", "recomp"). Probe until
it's concrete: what success looks like, by roughly when, and what they'll
trade (a cut costs some strength progress; a bulk adds some fat).

## 3. Research, then agree the plan

Follow [plan.md](plan.md): the research procedure, the fixed points every
plan keeps, the sleep gate on deficits, and what to agree — goal weight,
phase sequence, trend rate per phase and each phase's trigger.

## 4–5. Protein numbers and anchors

Follow [protein.md](protein.md): quote `nutrition targets` for the floor,
target and stretch, explain the floor's habit progression, and agree 2–3
standing protein anchors.

## 6. Output the nutrition setup

Follow [calories.md](calories.md): MacroFactor users get exact app setup
steps with protein at or above the floor and the logging rule, and never a
calorie figure of yours; everyone else gets one transparent starting
calorie estimate per phase, after which only the weight trend moves it.

## 7. Nutrition overrides

Any period eating to a number other than the app's (or, without an app,
the trend-driven calorie target on file) is a nutrition override. Push
back first; usually the right answer is "let the app work and keep
logging". If one is agreed or renewed, follow [overrides.md](overrides.md).

## 8. Flag training implications

Say what the new phase means for the routine (volume on a cut, deload timing, cardio load);
routine edits go through the normal flow: propose, show before/after, get approval, re-check the days either side.
For a new exercise, search the library first; if none fits, follow [custom exercise creation](../../../reference/custom-exercises.md).

## 9. Record it

Two places, both with the athlete's confirmation, like any profile edit.

**The numbers go in `config.toml`.** Propose the exact TOML edit, every
changed line as it will read, and wait for approval. The keys are in the
commented `[nutrition]`, `[nutrition.protein]`, `[[nutrition.anchors]]`
(one per anchor) and `[nutrition.override]` tables of
`config.example.toml`; weights are in `[athlete] bodyweight_units`. Write
it with the Write or Edit tool and run `python3 -m coach config validate`;
it exits 5 naming the key if anything is wrong (a `kcal_target` with an
app, protein numbers out of order, an override longer than 21 days).

**What stays prose** in the **Nutrition & goals** section of `profile.md`
is what only a human reads: the goal in the athlete's words, the phase
sequence and its triggers, why that protein basis, how the anchors were
chosen, the sleep-gate status and the app setup notes. Its shape is in
`reference/record-formats.md` → "profile.md: Nutrition & goals".

**If the phase is written in more than one place, sync them all in the
same edit** (`config.toml`'s `[nutrition] phase` and `profile.md`), and
bump `profile.md`'s `_Last reviewed_` date.

## 10. Publish the pages

Every pass that changes `config.toml`, the short ones too, ends with
[publish.md](publish.md). Check-ins take it from here: weekly readings,
the trend, the floor's raises, overrides expiring.
