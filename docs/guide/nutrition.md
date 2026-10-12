# Nutrition: goals, protein and the check-in readings

This doc covers `/goals` and the nutrition part of every `/check-in`: who
sets what, the framework rule for app users, the protein numbers and
anchors, the readings the check-in records, overrides, the sleep gate and
what happens with no app or with nutrition switched off. Read it before
your first `/goals` run, or when a check-in raises a nutrition flag.

## Who sets what

The repo sets the strategy and the app runs the numbers. MacroFactor, if
you use it, estimates your expenditure from logged food and weight and
adjusts your daily targets weekly. The repo decides the phase, the trend
rate, the goal weight, the protein numbers and the anchors, and reads the
app's numbers back at each check-in.

Three skills share the nutrition settings in `config.toml`:

| Skill | Owns | Doc |
| --- | --- | --- |
| `/goals` | `[nutrition]`: phase, rate, protein, anchors, any override | this doc |
| `/meal-plan` | `[nutrition.template]`: your standing eating week | [Recipes and meal plans](recipes-and-meal-plans.md) |
| `/recipes` | the recipe bank in `nutrition/menu/` | [Recipes and meal plans](recipes-and-meal-plans.md) |

`python3 -m coach nutrition status` prints the numbers in force, and the
coach quotes it rather than working anything out by hand.

## The framework rule for app users

If you use a nutrition app, the repo gets complete logging into the app
and reads the app's numbers out. Complete logging means every day logged.
On a day you could not track, log an estimate of the day or the missed
meal as a quick-add of calories and protein. Per MacroFactor's own
guidance, a day logged by halves skews its targets most. An estimate
within about 30 % of what you ate beats a blank day, and only a day you
cannot guess that closely stays blank (rn:protein-energy-deficit.13).

The repo never states its own calorie target or calorie band for an app
user, and never runs a parallel calorie model. Any period eating to a
number other than the app's is a dated nutrition override, described
below. `config validate` refuses a `kcal_target` while an app is set.

## What `/goals` asks and does

Run `/goals` to set or revise your goals, when a phase boundary arrives,
when an override expires or needs renewing, or when a deep check-in flags
your goals as stale. A yes/no question such as "should the bulk still
start?" runs the full flow if your profile's goal fields are still to be
decided or stale. A planned phase change on a current plan needs only a
confirm-and-record pass.

1. **Weigh-in first.** The coach asks for a fresh morning weigh-in before
   food, in your units, and keeps it with
   `python3 -m coach bodyweight record --date <day> --weight X`. It works
   whether nutrition is on or off, and `nutrition targets` reads it. With
   none to hand, the coach agrees the strategy now and confirms the
   numbers after your next weigh-in.
2. **The app's numbers.** If you use MacroFactor and have a program set
   up: trend weight, expenditure, the kcal and protein targets and your
   7-day average protein. On a first run the app may be empty, so the
   coach proceeds on the scale weigh-in alone.
3. **Recent protein intake** without the app: a typical day's protein,
   estimated together from two or three recent days.
4. **A body-fat reading** if you have one: the number, the method and the
   date.
5. **Sleep**: dated nightly hours or a period average from a tracker or
   your own notes, otherwise your words.
6. **Your goal in your own words** ("get shredded", "bulk to 200",
   "recomp"). The coach probes until it is concrete: what success looks
   like, by roughly when, and what you will trade. A cut costs some
   strength progress; a bulk adds some fat.
7. **Research, then the plan.** The coach reads the research notes for
   protein, energy balance and sleep, researches online when none answers
   the question, and cites claim ids. You agree a goal weight or body-comp
   outcome, a phase sequence with rough dates, a target trend rate per
   phase and what triggers the next phase: a date, a weight, a look or a
   strength milestone. A goal or trigger that uses waist, body fat or
   photos is measured at deep check-ins only, when the last reading is 4
   or more weeks old.
8. **The sleep gate** before any deficit, described below.
9. **Protein numbers and anchors**, described below.
10. **The nutrition setup.** With MacroFactor, exact app setup steps and
    the logging rule. Without an app, one starting calorie estimate per
    phase.
11. **Training implications.** The coach says what the phase means for
    the routine: volume on a cut, deload timing, cardio load. Routine
    edits go through the normal programming flow, with before and after.
12. **Recording it.** The numbers go in `config.toml` and the reasoning
    in `profile.md`. The coach shows every changed TOML line and waits
    for your approval, then runs `python3 -m coach config validate`,
    which exits 5 naming the key if anything is wrong.
13. **Publishing the pages.** The brief and the dashboard show the phase
    and the protein floor, so the coach renders and publishes the pages
    again (see [Pages and publishing](pages-and-publishing.md)).

Fixed points survive any research: no extreme cuts or bulks. A bulk gains
about 0.25–0.5 % of bodyweight a week, nearer the low end for advanced
lifters (rn:protein-energy-deficit.12). A cut loses no faster than about
0.5–1 % of bodyweight a week, slower when close to the goal
(rn:protein-energy-deficit.11). Recomp at maintenance is a legitimate
choice for a returning or newer lifter with elevated body fat, and its
target trend rate is zero. The weekly weigh-in and check-in loop is the
real measuring instrument: the plan corrects as the trend comes in.

### What stays prose

`profile.md` gets a **Nutrition & goals** section that holds what only a
human reads: the goal in your words, the phase sequence and its triggers,
why that protein basis, how the anchors were chosen, the sleep-gate
status and the app setup notes. The coach bumps its revision date in the
same edit. Its shape is in
[reference/record-formats.md](../../reference/record-formats.md).

`config.toml` and `profile.md` stay out of the page publish. The coach
commits them only when you ask, staging just those two files.

## Protein: floor, target and stretch

`/goals` sets three daily protein numbers (see
[the glossary](../../CONTEXT.md)), each per kg of a **reference mass**:

- the **target** is what the coach steers toward;
- the **stretch** is an optional higher aim, not a benefit cap;
- the **floor** is your minimum commitment now, built from recent intake.

The reference mass is your current bodyweight, your goal weight, or your
fat-free mass when a credible body-fat reading exists. A credible reading
is DEXA, a BodPod, underwater weighing or skinfolds by an experienced
tester, from the last three months or so. With a rough or absent reading
the script combines cues: a rough body fat above 25 % for men or 35 % for
women, a goal weight at least 10 % below bodyweight, or a BMI of 30 or
more. Any positive cue selects goal weight; otherwise bodyweight. These
selection gates are coaching heuristics.

`python3 -m coach nutrition targets` computes the numbers. It reads, never
writes, and runs with nutrition off. By default it takes bodyweight from
the newest weight on file in the last 14 days, recent intake from the
newest reading's 7-day average, and goal weight from `[nutrition]`. The
coach passes what you told it: `--body-fat` with `--body-fat-source`,
`--sex`, `--height`, `--goal-weight`, `--recent-intake`, and
`--bodyweight` only for a what-if weight. When `missing` names an input,
the coach asks you for it and runs again. The valid fixture, with height
and sex supplied, returns:

```json
"reference": {"basis": "bodyweight", "mass": 82.4, "unit": "kg",
  "reason": "no body-fat reading; BMI 25.4 is under 30, so bodyweight", ...},
"protein": {
  "target": {"g": 130, "g_per_kg": 1.6, ...},
  "stretch": {"g": 180, "g_high": 180, "g_per_kg": 2.2, ...},
  "floor": {"g": 130, "g_min": 100, "g_per_kg_min": 1.2,
            "from_intake_g": 130, "clamped": null, ...}}
```

The target is 1.6 g/kg and the stretch 2.2 g/kg (rn:protein-energy-deficit.17,
rn:protein-energy-deficit.18). With fat-free mass the target is 2.0 g/kg
and the stretch a range from 2.6 to 2.8 g/kg, so you agree a number
between `g` and `g_high` (rn:protein-energy-deficit.6). Each is rounded
to the nearest 5 g.

The floor starts at recent intake plus 15–20 g: the first 5 g step at or
above intake plus 15 g (rn:protein-energy-deficit.8). It stays between two
bounds, and `clamped` says which applied:

| `clamped` | Meaning |
| --- | --- |
| `null` | neither bound; the floor is `from_intake_g` |
| `"min"` | intake plus 15 g falls short of `g_min`, 1.2 g/kg of bodyweight or goal weight (1.5 g/kg of fat-free mass), because muscle loss while losing weight is more likely below it (rn:protein-energy-deficit.7). The anchors close the gap. |
| `"target"` | intake plus 15 g passes the target, so the floor is the target. Intake above the target stays compatible; the coach never tells you to eat less protein. |

With MacroFactor, keep the app's protein setting at or above the floor. A
setting below it is flagged at check-in; a higher one stays. The coach
records the app's actual number and keeps floor, target and stretch in
order rather than raising the floor to match.

### The floor rises as the habit sticks

When your measured weekly average protein meets or beats the floor at two
consecutive check-ins since `floor_since`, the floor rises by
`floor_step_g` (10 g by default; the coach sets it at 10–15 g), never
above the target
(rn:protein-energy-deficit.9). `/check-in` proposes and applies the raise.
Missing the floor never lowers it; only `/goals` lowers it, with a reason.

Whenever `/goals` changes `floor_g`, it sets `floor_since` to the day
after the newest reading on file, or today if later. A reading already on
file measured the old floor and must not count toward the next raise.

Without an app, three check-ins since `floor_since` with no measured
weekly average, while the floor is below the target, raise
`protein_unmeasured`. The coach offers optional calibration, a `/goals`
review or a deliberate hold (rn:protein-energy-deficit.20). Anchor
adherence cannot qualify a gram-based raise.

## Protein anchors

Protein is coached through 2–3 standing protein anchors, not a daily meal
plan. An anchor is a fixed daily item in a set slot that carries about
25 g protein or more, needs no cooking (a shake, a pot of high-protein
yogurt, cottage cheese, milk with a scoop), and with your typical meals
gets you to the floor.

The coach proposes candidates from what you already eat and like, checks
that anchors plus a typical day's meals reach the floor, and agrees each
anchor's name, slot (breakfast, lunch, dinner, snack) and days: daily,
office days, home days or named weekdays. An anchor may link a recipe
card instead of carrying `kcal` and `protein_g`, so `/meal-plan` can shop
its ingredients; the coach confirms the card with you rather than
matching its name. `/meal-plan` treats anchors as fixed blocks, and
`/check-in` asks whether they happened most days. A "no" two weeks
running is a cue to revisit the anchors in `/goals`, not to lower the
floor.

## Without a nutrition app

The same strategy applies, plus one transparent starting calorie
estimate per phase. The coach runs `nutrition targets --app none` with
`--sex`, `--age`, `--activity` and `--phase PHASE:RATE` and quotes the
`calories` result with its method and inputs. Resting rate comes from
Mifflin–St Jeor, times an activity level (`sedentary` 1.53, `active`
1.76, `vigorous` 2.25), rounded to the nearest 50 kcal; the phase
adjustment is the weekly rate in kg × 7700 ÷ 7 (rn:protein-energy-deficit.14,
rn:protein-energy-deficit.15, rn:protein-energy-deficit.16). The script
exits 1 for a cut over 1 % or a bulk over 0.5 % of bodyweight a week.

The coach chooses `--activity` from your whole day, not a step count:
your job, everyday walking, and how long and hard each session is. Each
level is a range of lifestyles, not a measurement of you, so the estimate
is a rough starting point that the weight trend corrects. After that,
calories move only from the trend: when a 2–3-week trend misses the
target rate, `/check-in` proposes a change of about 100–150 kcal a day in
the direction the trend needs, and edits `kcal_target` with your yes. A
new estimate comes only with a new phase.

## Nutrition readings at every check-in

The Sunday message's Food field asks for the readings, worded as
`nutrition status` gives them: trend weight, expenditure, the kcal and
protein targets, the 7-day averages and days logged. It asks whether the
anchors happened most days, whether anything in the current meal plan did
not work, and, once a standing template exists, next week's food
exceptions. A dashboard screenshot is accepted. See
[Check-in](check-in.md) for the rest of the message.

The coach turns your answer into one reading with
`python3 -m coach nutrition record --date <check-in date>` and the flags
`--trend-weight`, `--expenditure`, `--target-kcal`, `--target-protein`,
`--avg-kcal`, `--avg-protein`, `--days-logged` and `--anchors yes|no`,
passing only what you gave. Without an app it passes `--scale-weight`,
the mean of the week's morning weigh-ins, and `--avg-protein` only if you
track it as a weekly average; a one-day estimate goes in `--note`. A
reading already on file for the date exits 1, and `--replace` corrects
it. The series lives in `data/nutrition/readings.json`, one entry per
check-in, sorted by date, with `source` `app`, `scale` or `seeded` (a
one-off import from archived check-ins with `nutrition import`). A
reading copies the app's numbers; nothing in the repo computes them.

The coach then reads `nutrition status`. Its `trend` runs from the newest
weight of one basis back to its newest point at least 14 days earlier,
per 7 days, and is null while the series covers under 14 days. A
`fallback: true` trend is raw scale weight standing in for an app trend
that covers under 14 days, and the coach says so. One odd week does not
change calories: the coach uses a supported 2–3-week trend and your agreed
phase intent. Maintenance recomp targets zero, so a confirmed loss at
maintenance is a review of the maintenance estimate, not cut progress.

The check-in acts on each flag `nutrition status` raises:

| Flag | When | What the coach does |
| --- | --- | --- |
| `protein_floor_raise` | average protein met the floor at the two most recent readings since `floor_since` | proposes `proposed_floor_g` and `proposed_floor_since`; with your yes, edits `[nutrition.protein]` |
| `app_protein_mismatch` | the app's protein target is below the floor | reviews raising it to at least the floor, unless an active override covers protein |
| `protein_unmeasured` | three no-app readings since `floor_since` with no weekly average, floor below target | offers calibration, a `/goals` review or a deliberate hold |
| `logging_incomplete` | fewer than 7 days logged | asks for every day to be logged, estimates included |
| `override_expired` | today is on or after the override's expiry | removes `[nutrition.override]` and returns you to the app's numbers |
| `override_renewed_twice` | `renewal` is 2 | flags it in the record every check-in while it stands |
| `no_recent_reading` | no reading in the last 14 days | records this week's reading before reading the trend |

The record's Coach's read ends with three nutrition lines: weight and
trend against the target rate, protein against the floor with the count
toward a raise, days logged and anchors, then the override and the
sleep-gate status. The brief's food line shows the floor, last week's
average, the anchors and any override; the status line from the valid
fixture reads:

```text
Food: protein floor 110 g, last week 115 g · anchors: Whey shake · override: none · plan: nutrition/plans/2026-10-12.md
```

## Nutrition overrides

A nutrition override is any period eating to a number other than the
app's, or, without an app, other than the trend-driven calorie target on
file: calories held at expenditure instead of the app's deficit, a manual
calorie band, a protein figure below the floor. The coach pushes back
first; usually the right answer is to let the app work and keep logging.

If one is agreed, it is recorded as `[nutrition.override]` in
`config.toml` with every field: `start`, `what` (with the number you eat
to), `reason`, `exit_condition` (what ends it early), `expires` no later
than 21 days after the start (`config validate` refuses a later date),
and `renewal`: 0 for a first override, 1 once renewed, 2 for a second
consecutive renewal.

Only one override exists at a time. `/check-in` expires it on or after
its expiry date, or when its exit condition fires, and returns you to the
app's numbers. Renewing it needs `/goals`, a fresh reason and a new expiry
no later than 21 days from the renewal. A second consecutive renewal is
flagged as a sign the plan itself needs changing, usually the phase or
the trend rate. In the `nutrition-override` fixture, `nutrition status`
returns the active override as:

```json
"override": {"start": "2026-10-01", "expires": "2026-10-22",
  "what": "calories held at expenditure", "reason": "...",
  "exit_condition": "back on the usual routine", "renewal": 1,
  "state": "active"}
```

## The sleep gate

Before agreeing any deficit, the coach checks your sleep. A trailing
14-day average under about 7 hours means recomp at maintenance instead;
at or above 7 hours passes the gate (rn:sleep-dieting.3). This is a
low-confidence coaching heuristic: 7 hours is not a medically proven
boundary for dieting, and the evidence supports caution rather than a
rule (rn:sleep-dieting.1, rn:sleep-dieting.2). The full procedure is in
[reference/nutrition-sleep.md](../../reference/nutrition-sleep.md).

The evidence is hours asleep, not time in bed or "sleep felt fine". The
coach accepts dated nightly hours from you or a tracker, or a period
average with its start and end dates, and labels a manual period mean as
self-report. It records them with `python3 -m coach wellness add`, which
needs `[activity] enabled = true` (see
[Cardio and activity](cardio-and-activity.md)); manual entry needs no
device. A period mean is recorded once as a span, never expanded into
invented nights. `wellness summary` over the 14 calendar dates ending
today settles the gate; any other span stays pending.

The outcomes, recorded in `profile.md` with the assessment date, the
average, the covered dates, the source and any missing coverage:

- **passed** or **recomp**: complete coverage settled it. At 6.4 h the
  coach agrees maintenance; at 7.2 h it offers to reconsider a deficit.
- **pending measurement**: coverage is incomplete, or you have no hours
  source and reported short sleep or a sleep limiter. The default while
  pending is maintenance.
- **not evaluated**: no hours source and no reported short sleep, so a
  deficit may proceed (rn:sleep-dieting.4).

During a deficit, or while pending, `/check-in` re-checks the gate once
hours exist. A failed gate routes you to `/goals` to agree maintenance;
passing it changes nothing. The gate is separate from the fatigue
trigger for poor sleep, which counts individual short nights; a period
mean cannot supply that count.

## Bodyweight observations

Every reader of bodyweight in the repo, from the trend to the e1RM of a
bodyweight lift, uses one set of dated observations. Each has a source
and a basis:

| Source | Basis | Comes from |
| --- | --- | --- |
| wellness | scale weight | `bodyweight record`, or a tracker's body mass |
| Hevy | scale weight | a Hevy body measurement |
| nutrition reading | trend weight, or scale weight without an app | `nutrition record` |

Scale weight and trend weight are different quantities, so a rate is
always taken within one basis. On one date and basis the wellness record
wins, then Hevy, then the nutrition reading, so a copy of the same
weigh-in counts once. With an app the preferred basis is trend weight and
scale weight is the fallback; without one it is the other way round.
`python3 -m coach bodyweight list` shows every observation with its
source and the trend it supports.

## Nutrition off

With `[nutrition]` left out or `enabled = false`, the Food field of the
Sunday message becomes a Bodyweight field asking for one morning scale
weight and nothing else. The coach keeps it with `bodyweight record`,
notes it in the record and prompts `/goals` to get set up. `nutrition
record` exits 5 while nutrition is off and names `bodyweight record`.

## The config tables

`/goals` writes four tables, with your approval. From
[config.example.toml](../../config.example.toml):

```toml
[nutrition]
enabled = true
app = "macrofactor"             # "macrofactor" | "none"
phase = "recomp"                # "bulk" | "cut" | "maintain" | "recomp"
target_rate_per_week = 0.0      # bodyweight units a week; negative = loss
# goal_weight = 78.0
# kcal_target = 2400            # only with app = "none"

[nutrition.protein]
reference_basis = "bodyweight"  # "bodyweight" | "goal_weight" | "fat_free_mass"
reference_mass = 80.0
floor_g = 110                   # the number entered in the app
target_g = 128
stretch_g = 176
floor_since = 2026-09-28
floor_step_g = 10

[[nutrition.anchors]]
name = "Whey shake"
slot = "snack"
days = ["daily"]
kcal = 150
protein_g = 30

# [nutrition.override]
# start = 2026-10-11
# expires = 2026-11-01
# what = "app protein target held at 120"
# reason = "..."
# exit_condition = "..."
# renewal = 0
```

Weights are in `[athlete] bodyweight_units`. An anchor's `days` takes
`"daily"`, `"office"`, `"home"` or weekday ids `"mon"` to `"sun"`, and
`recipe = "<slug>"` can replace `kcal` and `protein_g`. See
[Configuration](configuration.md) for the other tables.
