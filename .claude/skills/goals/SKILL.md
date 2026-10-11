---
name: goals
description: Use when the athlete wants to set or revise their training and physique goals — target weight, phase (bulk/cut/maintain), eating strategy, protein, or MacroFactor setup. Triggers include "/goals", "revise my goals", "should I bulk or cut", "I want to get lean/shredded/bigger", "update my targets", a phase boundary arriving, a nutrition override expiring or needing renewal, or a deep check-in flagging that goals are stale.
---

# Goals & targets revision

A coaching conversation that turns "what the athlete wants" into a
recorded plan: target weight (or body-comp outcome), phase sequence, trend
rate, protein floor, target and stretch, the standing protein anchors,
and — if they use MacroFactor — the exact configuration for it. The
result lives in the **Nutrition & goals** section of `profile.md`, which
check-ins read.

**The framework rule (nutrition app users).** MacroFactor is the
nutrition engine: it estimates expenditure from logged food and weight
and adjusts the daily targets weekly. This repo decides the *strategy*
(phase, trend rate, goal weight, protein numbers, anchors) and does two
things with the app: it gets **complete logging** into the app and reads
the app's numbers out. Complete logging means every day logged. On a day
the athlete couldn't track, they log an estimate of the day or of the
missed meal (a quick-add of calories and protein). This follows
MacroFactor's own guidance: a day logged by halves is what skews its
targets most; an estimate within about 30 % of what was eaten is
strongly preferred to a blank day; only a day they can't guess that
closely is better left blank. The repo **never states its
own calorie target or calorie band** for an app user and never runs a
parallel calorie model. Any departure from the app's numbers is a dated
nutrition override (step 7).

**Without a nutrition app:** the strategy is the same. The output is a
transparent starting calorie estimate, given once per phase, plus the
protein numbers; after that, calories move only from the weight trend
(step 6). Protein numbers, anchors, overrides and the sleep gate apply
unchanged.

## 1. Gather current state

- Read `profile.md`, `routine/program.md` (if it exists), and the newest
  file in `check-ins/` (if any).
- Ask the athlete for (skip anything the conversation already covered):
  - A **fresh weigh-in** (morning, before food; record in their preferred
    units with the metric value alongside). If they don't have one to
    hand, agree the strategy now and confirm the numbers after their next
    morning weigh-in.
  - MacroFactor's current **trend weight**, **expenditure**, targets
    (kcal, protein) and **7-day average protein** — **if** they use it
    and a program is already set up. On a first run MacroFactor may be
    fresh or empty: proceed on the scale weigh-in alone and let its
    estimates mature. (For Hevy users, `body_measurements` is the only
    other weight source and is usually stale — check the date.)
  - **Recent protein intake** without the app: a typical day's protein,
    estimated together from what they ate on two or three recent days.
  - A **body-fat reading**, if they have one: the number, the method
    and the date.
  - **Sleep**: the trailing 14-day average from a watch or phone that
    tracks sleep, if they have one; otherwise how they sleep, in their
    words.
  - How training and recovery feel; anything coming up (travel, events)
    that affects the timeline.
- **Scope check:** even a yes/no entry point ("should the bulk still
  start?") runs the full flow if profile fields are TBD or stale. If the
  plan on file is current and the athlete is only confirming a planned
  phase change, a light confirm-and-record pass is enough. A renewal of
  an expiring nutrition override needs only step 7 and the record.

## 2. The athlete states the goal

In their own words ("get shredded", "bulk to 200", "recomp"). Probe until
it's concrete: what does success look like, by roughly when, and what are
they willing to trade (a cut costs some strength progress; a bulk adds
some fat).

## 3. Research, then agree the plan

Research current best practice online for the specific decision (rates,
target ranges for their stats) and cite sources — don't rely on memory
alone. Fixed points that must survive any research:

- No extreme cuts or bulks. Sustainable only.
- Bulk: ~+0.25–0.5 lb/week. Cut: lose no faster than ~0.5–1%
  bodyweight/week, slower when close to the goal. Recomp at maintenance is
  a legitimate choice for a returning or newer lifter with elevated body
  fat.
- Protein follows step 4: three numbers from a reference mass, never
  one figure per kg of whatever the scale says.
- The weekly weigh-in + check-in loop, not the initial estimate, is the
  real measurement instrument — the plan corrects as the trend comes in.

**Sleep gate on deficits.** Before agreeing a deficit (a cut, or any
phase that eats below maintenance), check sleep:

- **With a sleep source** (a watch or phone that tracks sleep): a
  trailing 14-day average under ~7 h means **recomp at maintenance**
  instead of a deficit. At or over ~7 h, the gate passes.
- **No sleep source:** ask how they sleep. Reported short sleep, or a
  sleep limiter in the profile's **Recovery** section, defaults to recomp
  at maintenance with the gate recorded as `pending measurement`.
  Otherwise the deficit can go ahead with the gate recorded as
  `not evaluated`.

Why: in a 14-day crossover trial under the same moderate deficit, 5.5 h
of sleep opportunity instead of 8.5 h cut the fat lost by 55 % and raised
fat-free mass lost by 60 % (Nedeltcheva et al. 2010, *Ann Intern Med*
153:435–441, https://doi.org/10.7326/0003-4819-153-7-201010050-00006).
The ~7 h line is the AASM/SRS adult minimum (Watson et al. 2015, *J Clin
Sleep Med* 11:591–592, https://doi.org/10.5664/jcsm.4758). The athlete
can still choose the deficit; record that choice and its reason beside
the gate status. `/check-in` re-checks the gate during a deficit once a
sleep source exists.

Agree with the athlete: **goal weight** (or body-comp outcome), **phase
sequence** with rough dates, **target trend rate per phase**, and **what
triggers the next phase** (a date, a weight, a look, a strength
milestone). Conditional triggers are fine — record the condition, and the
check-in that observes it fire records the phase change.

**A goal or trigger that uses waist, body fat or progress photos is
measured at deep check-ins only** — when the last reading is 4 or more
weeks old, never weekly. Say so when agreeing it, so the athlete knows
when it will be checked. Photos stay with the athlete; the coach records
only their one-line read.

## 4. Set protein: reference mass, floor, target, stretch

**Pick the reference mass** — the mass every protein figure is
multiplied by. Take the first rule that applies:

1. **Fat-free mass** when a credible body-fat reading exists (DEXA, a
   BodPod or underwater weighing, or skinfolds by an experienced tester,
   from the last ~3 months): bodyweight × (1 − body-fat fraction).
2. **Goal weight** when body fat is high: above ~25 % for men or ~32 %
   for women on a rougher reading (a smart scale, a tape method). With
   no reading at all, treat body fat as high when BMI is 30 or more, or
   when the goal weight is 10 % or more below current bodyweight.
3. **Current bodyweight** otherwise.

Per kg of bodyweight, protein overshoots for an athlete carrying a lot of
fat; goal weight or fat-free mass keeps the number reachable. Record the
basis and why (the reading and its source).

**From that mass, record three numbers:**

| Number | Bodyweight or goal weight | Fat-free mass |
| --- | --- | --- |
| **Target** | 1.6 g/kg | ~2.0 g/kg |
| **Stretch** | 2.2 g/kg | ~2.6–2.8 g/kg |
| **Floor** | recent average intake + ~15–20 g, no lower than 1.2 g/kg and no higher than the target | same rule, no lower than ~1.5 g/kg |

The fat-free-mass column is the first column converted at ~15–20 % body
fat.

- The **target** is the number to coach toward; the **stretch** is the
  most that still adds anything (useful on a hard cut); the **floor** is
  the reachable number the athlete is held to this week.
- **MacroFactor users:** the floor is the protein number set in the app
  (step 6). The app's protein figure and the floor on file are always
  the same number.
- Round to the nearest 5 g.

Sources: Morton et al. 2018 (*Br J Sports Med* 52:376–384,
https://doi.org/10.1136/bjsports-2017-097608) found gains in fat-free
mass stopped rising at ~1.6 g/kg/day (95 % CI up to 2.2), which sets the
target and the stretch. Helms et al. 2014 (*Int J Sport Nutr Exerc
Metab* 24:127–138, https://doi.org/10.1123/ijsnem.2013-0054) put needs
during a deficit at 2.3–3.1 g/kg of fat-free mass for lean trained
lifters, which brackets the fat-free-mass stretch. The ISSN position
stand (Jäger et al. 2017, *JISSN* 14:20,
https://doi.org/10.1186/s12970-017-0177-8) gives 1.4–2.0 g/kg for most
exercising people. For the floor, Weijs & Wolfe 2016 (*Clin Nutr*
35:394–398, https://doi.org/10.1016/j.clnu.2015.02.016) found muscle gain
during weight loss more likely above 1.2 g/kg (1.9 g/kg of fat-free
mass), and Kokura et al. 2024 (*Clin Nutr ESPEN* 63:417–426,
https://doi.org/10.1016/j.clnesp.2024.06.030) tied intakes under
1.0 g/kg to more muscle loss in dieting adults with overweight or
obesity. The ~25 %/~32 % body-fat lines are ACE's "obese" categories;
research often uses ~25 % for men and ~35 % for women (Romero-Corral et
al. 2008, *Int J Obes* 32:959–966, https://doi.org/10.1038/ijo.2008.11),
which also found BMI ≥ 30 misses over half of people with excess fat —
hence the goal-weight fallback.

**Habit progression.** The floor moves up as the habit sticks: when
the weekly average protein meets or beats the floor at **two
consecutive check-ins** since the floor last changed, the floor rises by
~10–15 g, **never above the target**. Missing the floor never lowers it;
only `/goals` lowers it, with a reason. `/check-in` applies the raise.
For MacroFactor users the athlete sets the app's protein to the new
floor the same day.

## 5. Agree the protein anchors

Protein is coached through **2–3 standing protein anchors**, not a daily
meal plan. An anchor is a fixed daily item in a set slot that:

- carries **~25 g protein or more**;
- needs **no cooking** (a shake, a pot of high-protein yogurt, cottage
  cheese, a ready-to-eat protein snack, milk with a scoop); and
- together with the athlete's typical meals, gets them to the floor.

Propose candidates from what the athlete already eats and likes, check
the sum (anchors + a typical day's meals ≥ floor), and agree each
anchor's name, slot (breakfast, lunch, dinner, snack) and days (daily,
office days, named weekdays). Record them as a table (step 9).
`/meal-plan` treats them as fixed blocks; `/check-in` asks whether they
happened most days.

## 6. Output the nutrition setup

**MacroFactor users:** give exact setup steps — goal type
(gain/lose/maintain; recomp is maintain), rate, macro program, the
**protein setting at the floor**, and **calorie shifting** so
higher-output days (per the schedule in `profile.md`) get more calories
if the athlete wants that. Their app UI is the source of truth — walk it
with them and adjust names to what they actually see. Then state the
logging rule: log every day; on a day they couldn't track, log an
estimate of the day or the missed meal; never leave a day half-logged.
Calories are whatever the app sets; never state a calorie target or
band of your own.

**Everyone else:** give **one starting calorie estimate per phase**,
from a transparent method — a quick bodyweight × activity-factor figure,
or a standard equation like Mifflin–St Jeor from the profile stats —
plus the phase adjustment, with the method shown. Say plainly it's a
rough starting point. After that, calories change **only from the
weight trend**: when a 2–3-week trend misses the target rate,
`/check-in` moves the target by ~100–150 kcal/day in the direction the
trend needs. Never re-derive it from an equation mid-phase; a new
estimate comes only with a new phase. State the protein numbers and how
to track both.

## 7. Nutrition overrides

A **nutrition override** is any period in which the athlete eats to a
number other than the app's (or, without an app, other than the
trend-driven calorie target on file): holding calories at expenditure
instead of the app's deficit, a manual calorie band, a protein figure
other than the floor. Push back first; usually the right answer is "let
the app work and keep logging". If one is agreed, record it in
`profile.md` → Nutrition & goals → **Active override** with every field:

- **Start** date;
- **What** is overridden, with the number the athlete eats to;
- **Reason**;
- **Exit condition** — what ends it early;
- **Expires** — no later than **21 days** after the start;
- **Renewal** — 0 for a first override, 1 once renewed, 2 for a second
  consecutive renewal.

Only **one override at a time**. `/check-in` expires it on or after its
expiry date and returns the athlete to the app's numbers. Renewing it
needs this skill, a fresh reason and a new expiry no later than 21 days
from the renewal. A second consecutive renewal is flagged to the athlete
as a sign the plan itself needs changing (usually the phase or the trend
rate), and `/check-in` keeps flagging it while it stands.

## 8. Flag training implications

Say what the new phase means for the routine (volume on a cut, deload
timing, cardio load) — but route actual routine edits through the normal
flow: propose, show before/after, get approval, re-check the days either
side.

## 9. Record it

Update the **Nutrition & goals** section of `profile.md` — with the
athlete's confirmation, like any profile edit. A goal or trigger that
uses waist, body fat or photos is recorded with "(measured at deep
check-ins)" beside it. The section holds:

```markdown
## Nutrition & goals

- **Apps:** Hevy: … · MacroFactor: yes / no
- **Goal:** <in the athlete's words> · **Phase:** <phase> (from <date>) → <next phase and its trigger>
- **Target trend rate:** <rate per week>
- **Calories:** set by MacroFactor (<goal type, rate, calorie shifting>)
  — or, no app: starting estimate <kcal> (<method>, <date>) · current target <kcal> (last changed <date>: <trend reason>)
- **Protein reference mass:** <mass> · basis: bodyweight | goal weight | fat-free mass (<why: the reading, its method and date>)
- **Protein:** floor <g> (since <date>; app users: = the app's protein setting) · target <g> · stretch <g>
- **Sleep gate:** passed (<14-day avg>, <date>) | recomp (<14-day avg>, <date>) | pending measurement (<what was reported>) | not evaluated · <athlete's choice and reason, if they overrode it>

### Protein anchors
| Anchor | Slot | Days | Protein | kcal |
| --- | --- | --- | --- | --- |
| <name> | snack | daily | 30 g | 150 |

### Active override
None.

(While one is active, the "None." line is replaced by:)
**Start:** <date> · **Expires:** <date, ≤ start + 21 days> · **What:** <…> · **Reason:** <…> · **Exit condition:** <…> · **Renewal:** 0 | 1 | 2

_Revised: YYYY-MM-DD_
```

**If the phase is written in more than one place, sync them all in the
same edit** (e.g. a phase word in `routine/program.md`'s header). Bump
`profile.md`'s `_Last reviewed_` date. Check-ins take it from here: they
track the trend against this plan, apply the floor's habit progression,
expire overrides, and send the athlete back to `/goals` when the phase
plan itself needs rethinking.
