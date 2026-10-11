---
name: goals
description: Use when the athlete wants to set or revise their training and physique goals — target weight, phase (bulk/cut/maintain), eating strategy, protein, or MacroFactor setup. Triggers include "/goals", "revise my goals", "should I bulk or cut", "I want to get lean/shredded/bigger", "update my targets", a phase boundary arriving, a nutrition override expiring or needing renewal, or a deep check-in flagging that goals are stale.
---

# Goals & targets revision

A coaching conversation that turns "what the athlete wants" into a
recorded plan: target weight (or body-comp outcome), phase sequence, trend
rate, protein floor, target and stretch, the standing protein anchors,
and — if they use MacroFactor — the exact configuration for it. The
numbers live in the `[nutrition]` table of `config.toml`, which scripts
and check-ins read; the reasoning behind them lives in the **Nutrition &
goals** section of `profile.md` (step 9).

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
closely is better left blank (rn:protein-energy-deficit.13). The repo
**never states its own calorie target or calorie band** for an app user
and never runs a parallel calorie model. Any departure from the app's
numbers is a dated nutrition override (step 7).

**Without a nutrition app:** the strategy is the same. The output is a
transparent starting calorie estimate, given once per phase, plus the
protein numbers; after that, calories move only from the weight trend
(step 6). Protein numbers, anchors, overrides and the sleep gate apply
unchanged.

## 1. Gather current state

- Read `profile.md`, `routine/program.md` (if it exists), and the newest
  file in `check-ins/` (if any). Run `python3 -m coach nutrition status`
  for the numbers on file and the latest reading.
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

When the specific decision (rates, target ranges for their stats) needs
evidence, follow `CLAUDE.md` "Researching current best practice": read
the notes for the area (`protein`, `energy_balance`, `sleep`) first,
research and save a local note when none answers it, and cite claim ids.
Fixed points that must survive any research:

- No extreme cuts or bulks. Sustainable only.
- Bulk: gain ~0.25–0.5 % of bodyweight per week, nearer the low end for
  advanced lifters (rn:protein-energy-deficit.12). Cut: lose no
  faster than ~0.5–1% bodyweight/week, slower when close to the goal
  (rn:protein-energy-deficit.11). Recomp at maintenance is
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
  instead of a deficit. At or over ~7 h, the gate passes
  (rn:sleep-dieting.3).
- **No sleep source:** ask how they sleep. Reported short sleep, or a
  sleep limiter in the profile's **Recovery** section, defaults to recomp
  at maintenance with the gate recorded as `pending measurement`.
  Otherwise the deficit can go ahead with the gate recorded as
  `not evaluated` (rn:sleep-dieting.4).

Why: under the same moderate deficit, 5.5 h of sleep opportunity
instead of 8.5 h cut the fat lost by 55 % and raised fat-free mass lost
by 60 % (rn:sleep-dieting.2). The ~7 h line is the adult minimum
(rn:sleep-dieting.1). `/check-in` re-checks the gate during a deficit
once a sleep source exists.

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
2. **Goal weight** when body fat is high: above ~25 % for men or ~35 %
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
  (step 6). The app's protein figure and the floor on file are the same
  number unless an active nutrition override covers protein (step 7).
- Round to the nearest 5 g.

Why these numbers: gains in fat-free mass stop rising at ~1.6 g/kg/day,
which sets the target (rn:protein-energy-deficit.1), and the top of the
95 % confidence interval around that plateau, 2.2 g/kg, sets the stretch
(rn:protein-energy-deficit.2). The fat-free-mass stretch sits inside the
2.3–3.1 g/kg of fat-free mass that lean lifters likely need in a deficit
(rn:protein-energy-deficit.6). The floor never drops under 1.2 g/kg
because muscle loss during weight loss is more likely at lower intakes
(rn:protein-energy-deficit.7), and starts from recent intake so it is
reachable this week (rn:protein-energy-deficit.8). The reference mass
keeps every figure reachable for an athlete carrying a lot of fat
(rn:protein-energy-deficit.3). The ~25 %/~35 % body-fat lines are the
WHO obesity lines that research uses (rn:protein-energy-deficit.4),
and BMI ≥ 30 alone misses over half of people with excess fat — hence
the goal-weight fallback (rn:protein-energy-deficit.5).

**Habit progression.** The floor moves up as the habit sticks: when
the weekly average protein meets or beats the floor at **two
consecutive check-ins** since the floor last changed, the floor rises by
~10–15 g, **never above the target** (rn:protein-energy-deficit.9).
Missing the floor never lowers it; only `/goals` lowers it, with a
reason. `/check-in` applies the raise. For MacroFactor users the athlete
sets the app's protein to the new floor the same day. Whenever `/goals`
changes `floor_g`, set `floor_since` to the day after the newest reading
on file (`python3 -m coach nutrition readings --last 1`), or today if
that is later: a reading already on file measured the old floor and must
not count toward the next raise.

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
office days, named weekdays). Record them in `config.toml` (step 9).
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
the app work and keep logging". If one is agreed, record it as the
`[nutrition.override]` table in `config.toml` (step 9) with every field:

- `start` date;
- `what` is overridden, with the number the athlete eats to;
- `reason`;
- `exit_condition` — what ends it early;
- `expires` — no later than **21 days** after the start (`config
  validate` refuses a later date);
- `renewal` — 0 for a first override, 1 once renewed, 2 for a second
  consecutive renewal.

Only **one override at a time**. `/check-in` expires it on or after its
expiry date (`nutrition status` flags `override_expired`) and returns the
athlete to the app's numbers. Renewing it
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

Two places, both with the athlete's confirmation, like any profile edit.

**The numbers go in `config.toml`.** Propose the exact TOML edit to the
`[nutrition]` table — every changed line as it will read — and wait for
the athlete's approval. Then write it with the Write or Edit tool and
run `python3 -m coach config validate`; it exits 5 naming the key if
anything is wrong (a `kcal_target` with an app, protein numbers out of
order, an override longer than 21 days). The table holds the floor,
target and stretch, the reference mass and basis, the anchors and any
override, plus the app, phase and trend rate:

```toml
[nutrition]
enabled = true
app = "macrofactor"             # or "none"
phase = "recomp"                # "bulk" | "cut" | "maintain" | "recomp"
target_rate_per_week = 0.0      # bodyweight units a week; negative = loss
# goal_weight = 78.0            # when the goal is a weight
# kcal_target = 2400            # no app only: the current calorie target

[nutrition.protein]
reference_basis = "bodyweight"  # "bodyweight" | "goal_weight" | "fat_free_mass"
reference_mass = 80.0
floor_g = 110                   # app users: the protein number set in the app
target_g = 128
stretch_g = 176
floor_since = 2026-09-28        # readings dated on or after this count toward a raise
floor_step_g = 10               # how far the floor rises (step 4: 10–15 g)

[[nutrition.anchors]]           # one table per anchor
name = "Whey shake"
slot = "snack"
days = ["daily"]                # "daily" | "office" | "home" | "mon" .. "sun"
kcal = 150
protein_g = 30

[nutrition.override]            # only while one is active; delete it when it ends
start = 2026-10-11
expires = 2026-11-01
what = "app protein target held at 120"
reason = "..."
exit_condition = "..."
renewal = 0
```

The numbers are placeholders; weights are in `[athlete]
bodyweight_units`.

**What stays prose** in the **Nutrition & goals** section of
`profile.md` is what only a human reads: the goal in the athlete's
words, the phase sequence and its triggers, why that protein basis (the
body-fat reading and its source), how the anchors were chosen and what
the athlete likes, the sleep-gate status and its reasoning, and the
MacroFactor setup summary and revision notes. It holds:

```markdown
## Nutrition & goals

The numbers (phase, trend rate, protein, anchors, any override) are in `config.toml` → `[nutrition]`.

- **Apps:** Hevy: … · MacroFactor: yes / no
- **Goal:** <in the athlete's words> → <phase sequence, with the trigger for each next phase>
- **Calories:** set by MacroFactor (<goal type, rate, calorie shifting>)
  — or, no app: starting estimate (<method>, <date>); trend changes since: <date: reason>, …
- **Protein basis:** <why this reference mass: the body-fat reading, its method and date>
- **Anchors:** <how they were chosen; what the athlete likes>
- **Override:** <the story behind an active one, if any>
- **Sleep gate:** passed (<14-day avg>, <date>) | recomp (<14-day avg>, <date>) | pending measurement (<what was reported>) | not evaluated

_Revised: YYYY-MM-DD_
```

**If the phase is written in more than one place, sync them all in the
same edit** (`config.toml`'s `[nutrition] phase` and `profile.md`). Bump
`profile.md`'s `_Last reviewed_` date. Check-ins take it from here: they
record a reading each week, track the trend against this plan, apply the
floor's habit progression, expire overrides, and send the athlete back
to `/goals` when the phase plan itself needs rethinking.
