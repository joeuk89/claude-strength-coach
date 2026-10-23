# Programs: creating, importing and redesigning

This page covers `/new-program`: the three ways a program comes into
being, what the program file holds, and how a program is replaced or
edited later. Read it before your first program, or before a redesign.

A **program** (see [the glossary](../../CONTEXT.md)) is the whole
training structure you follow: its sessions, how they land on the
calendar, how each exercise progresses, and when the block lightens. It
lives in `data/program.json`. The pages under `routine/` are rendered
from it and never edited by hand. Hevy's word for a session template is
"routine"; this repo keeps "routine" for Hevy only.

`/new-program` needs `profile.md` and `config.toml`. Without them, the
coach runs `/setup` first.

## The three paths

The coach offers three paths in one message and recommends one from
your profile and config, saying why in a line. If you have already said
which you want ("import my routines", "let's redesign"), it skips the
offer.

| Path | When it fits | What the coach does |
|---|---|---|
| **A. Import** | You already run a program, in Hevy or on paper, and want to keep it | Transcribes it as it is, then helps you finish the parts the source cannot settle |
| **B. Design** | Your week or goal needs a program built for it: coach-led sessions to plan around, a sport, unusual kit or limits. Every redesign is Path B | A full coaching conversation ending in a program you would train |
| **C. Starter** | You have no program of your own and your week fits one of the tested programs that ship with the framework | Fits a starter to your days, kit and known loads |

For Path C the coach runs `python3 -m coach starters list --days <n>`
with the number of solo sessions you want. Its `recommended_id` names
the starter that suits your `[athlete] experience` with every exercise
fitting your kit.

## What every path produces

Every path ends in a **program draft** at `.coach/drafts/program.json`.
The draft holds the complete program plus a report of what its source
could not settle. Drafts are gitignored. Nothing becomes the program
until it is adopted, and the coach never writes `data/program.json` by
hand.

The adoption step runs in this order:

1. **The dry run.** The coach runs `python3 -m coach program adopt
   --input .coach/drafts/program.json --dry-run`. It validates the draft
   and names each problem by its path in the file.
   It lists what still needs you: `unconfirmed` exercises with no
   confirmed load mode, `avoided` exercises you have said you avoid,
   sessions `without_routine` in Hevy and `orphan_routines` no session
   uses any more.
2. **The report table.** The coach shows the draft's report as one table
   with the columns kind, session, exercise and message. Its rows are
   converted loads (`Hevy 50 → 25/hand`), working sets at mixed loads,
   cues taken from Hevy notes, a missing schedule, swapped exercises,
   exercises with no fitting substitute, and evidence that the program
   is percentage-based.
3. **The load-mode table.** In the same message the coach shows every
   exercise without a confirmed load mode: the exercise, the proposed
   mode, and how you set the weight (one total, per hand, or one
   dumbbell). You confirm or correct each row once. The coach records
   the answers with `library set-mode` or `library confirm`, and never
   asks about the table again. A row you correct to a different mode
   needs one more answer: whether its start load meant the old mode or
   the corrected one ("was 20 the total, or 20 per hand?"). The coach
   runs `program reconcile-mode <id> --basis old|confirmed` with your
   answer. See [Hevy](hevy.md) for the modes.
4. **Adopt.** With your yes, the coach runs the same command without
   `--dry-run`. Adopt writes `data/program.json` and `data/state.json`,
   renders `routine/program.md` and one page per session, and stages
   those files with `git add`. It never commits: the coach offers to
   commit once you have approved.

In `data/state.json`, adopt records the adoption date, starts the block
at zero completed hard weeks (or carries the current block over on a
redesign), sets the rotation position (`--position`, else the draft's,
else the schedule rule's first position), and maps each Hevy routine the
draft names to its session.

Missed-day rules are optional. The coach explains them once, before
adopting, and adds one only when you want it.

## The program file

`data/program.json` is plain JSON. You rarely edit it directly, but it
helps to know what is in it. For example, abridged to one session:

```json
{
  "schema_version": 9,
  "name": "Upper/lower, 4 days",
  "sessions": [
    {
      "id": "lower-a",
      "title": "Lower A",
      "kind": "lifting",
      "tier": "core",
      "status": "active",
      "location": null,
      "focus": null,
      "exercises": [
        {
          "exercise_id": "bb_back_squat",
          "load_mode": "total",
          "sets": [
            {"count": 2, "type": "warmup", "reps": 5},
            {"count": 1, "type": "normal", "reps": 5, "rpe": 8},
            {"count": 3, "type": "normal", "reps": 5, "rpe": 7}
          ],
          "rest_seconds": 180,
          "superset_id": null,
          "cues": "brace before you descend · knees track over toes",
          "constraints": [],
          "scheme": {"name": "double_progression", "params": {}},
          "start_load": 100
        },
        {
          "exercise_id": "db_romanian_deadlift",
          "load_mode": "per_hand_x2",
          "sets": [
            {"count": 3, "type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 8}
          ],
          "rest_seconds": 120,
          "superset_id": null,
          "cues": "hips back · soft knees · bar close to the legs",
          "constraints": [],
          "scheme": {"name": "double_progression", "params": {}},
          "start_load": 25
        }
      ]
    }
  ],
  "external_sessions": [
    {"id": "pt-tue", "title": "PT", "weekday": "tue", "estimated_sets": {"chest": 3}}
  ],
  "schedule": {
    "rule": "fixed_weekdays",
    "params": {"days": {"mon": "lower-a", "tue": "upper-a", "thu": "lower-b", "fri": "upper-b"}}
  },
  "blocks": {"hard_weeks_ceiling": 6, "deload_rule": {"name": "standard", "params": {}}},
  "missed_day_rules": [
    {"id": "miss-lower-a", "session_id": "lower-a", "text": null, "when": {},
     "action": {"kind": "shift", "to_weekdays": ["sat"]}}
  ],
  "dose_targets": {"chest": 10, "quadriceps": 10, "hamstrings": 10},
  "dose_intent": {"goal": "hypertrophy", "baseline": {}, "reasons": {}},
  "interference": [
    {"name": "same_day", "params": {"min_gap_hours": 6, "lift_first": true}},
    {"name": "quality_before_heavy_lower", "params": {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6}}
  ],
  "priority": [
    {"exercise_id": "bb_back_squat", "kpi": {"kind": "e1rm", "target": 130, "by": "2027-01-31"},
     "floor": {"sets": 2, "rpe": null}}
  ],
  "minimum_week": null
}
```

### Sessions

A **session** is one training day's template. Each has an id (the slug
other files refer to), a title, a `kind` (`lifting` or `conditioning`),
a `tier` and a `status`:

- **Tier `core`** carries work nothing else covers; it must land for the
  week to count. **Tier `optional`** is bonus volume, and skipping it is
  not a miss.
- **Status `active`** is in the schedule. **`standby`** sits unscheduled
  until a minimum week calls on it. **`parked`** is the third status;
  the coach decides with you when a session takes it.

`location` names one of your `[equipment.locations.*]` tables when a
session is trained somewhere other than your main place, so its loads
are checked against that kit. A conditioning session may carry its own
`scheme`, a density scheme (`emom_density` or `circuit_rounds`) that
progresses the whole session on your session RPE.

### Exercises and set groups

Every exercise is named by its **exercise library** id (`bb_back_squat`,
`db_bench_press`) with the **load mode** it is performed in. The library
is the builtin catalogue merged with your own entries; `python3 -m coach
library search "<name>"` finds an id.

`sets` is a list of set groups. Each group has a `count`, a `type`
(`normal`, `warmup`, `dropset` or `failure`), exactly one of `reps` or
`rep_range`, and an optional `rpe`. A plain 3×5 is one group. A top set
and back-offs are two groups on one exercise. A `duration` exercise
needs `duration_seconds`; a `distance` exercise needs `distance_meters`.

**Warm-up loads** are not written in the program: each week the coach
scripts derive them from the line's first working load, after any
return cut or deload, and round them to your kit. One warm-up is 60 %
of it; two are 50 % and 75 %; three are 40 %, 60 % and 80 %; more
spread evenly from 40 % to 80 %. A barbell warm-up never drops below
`bar_weight`, a dumbbell warm-up lands on your rack, and no warm-up is
as heavy as the first working set (when nothing lighter exists, the
warm-up has no load). On a coarse rack or a heavy bar two warm-ups can
land on the same load; then only the first keeps it. A bar whose own
mass config does not declare (`smith_base_weight`, `ez_bar_weight`,
`trap_bar_weight`) rounds to its increment instead. Bodyweight, assisted
and banded exercises keep load-less warm-ups. To fix a warm-up instead, pin it on its group:
`"warmup_load": 40` (your units, per hand for dumbbells) or
`"warmup_percent": 70`. A pinned load that a cut week brings level with
the working sets falls back to the ramp for that position.

A **rep-out set**, written `5+` on your pages, is at least those reps
and then as many more as you can before its RPE stop (9 by default). It
is not a set to failure. The program file holds no rep-out marker: the
wave scheme writes one as the last wave set of each week, and the coach
can set one by override.

`rest_seconds` and `superset_id` are what Hevy shows. `start_load` is in
your units and **per hand for dumbbell work**. Null on a loaded exercise
means the coach picks the first load with you (a calibration line).
`cues` are the canonical form cues; changing how you perform a lift
edits this field first, and every Hevy note and session sheet copies it.
`constraints` carry a standing RPE cap, a no-added-load rule or a load
cap, each with its reason.

### Progression schemes

Every exercise names a **progression scheme**, the rule that turns its
recent exposures into next week's prescription. `python3 -m coach
plugins list --kind scheme` lists them, and `plugins show <name>` prints
a scheme's parameters.

| Scheme | What it does |
|---|---|
| `double_progression` | Prescribes the program's rep range at its target RPE and adds the increment once every working set reaches the top of the range at or under the target RPE; otherwise holds the load. A sensible default. |
| `linear` | Adds the increment after every exposure that hits all its prescribed reps, holds after a miss, and resets to a fraction of the load after misses in a row. |
| `fixed_reps_rpe` | Keeps the program's reps and RPE and sets each load from the best e1RM of the last 42 days, rounded down. |
| `rpe_anchored` | Loads one top set from the e1RM at its target reps and RPE, recalibrates the e1RM from the newest logged top set, then loads the back-off sets from the same e1RM at a lower RPE. |
| `wave_531` | Runs three-week waves at 65/75/85, 70/80/90 and 75/85/95 % of a training max, the last wave set a rep-out set; moves on a week only when that week was trained, raises the training max once a wave is completed, and deloads at 40/50/60 %. |
| `assistance_ladder` | Climbs an ordered list of rungs (assistance amounts or harder variations) one rung after an exposure with every set at its target reps at or under the target RPE. For bodyweight, assisted and band work. |
| `maintenance` | Repeats the last valid exposure's load and reps at the program's set count and RPE, never progressing. |
| `hold` | Repeats the last approved prescription unchanged. Every imported exercise starts here. |

The wave's **training max** is kept in state, not in the program; only
an explicit change you agree lowers it for good.

### Schedule rules

The **schedule rule** decides which session lands on which day.

| Rule | How it works | Params, for example |
|---|---|---|
| `fixed_weekdays` | Each session on the same weekday every week | `{"days": {"mon": "lower-a", "thu": "upper-a"}}` |
| `alternating_external_anchor` | Week templates alternate one position a week, anchored to a coach-led session; each new position stays unconfirmed until the coach confirms it with you | `{"weeks": [{"name": "week-a", "days": {...}}, {"name": "week-b", "days": {...}}], "anchor_external_id": "pt-tue"}` |
| `next_in_sequence` | Sessions in sequence order on the given weekdays, continuing after the last trained session whatever day it fell on | `{"sequence": ["push", "pull", "legs"], "days": ["mon", "wed", "fri"]}` |
| `explicit_calendar` | Each session on the dates listed, nothing on any other day | `{"dates": {"2026-10-12": "lower-a"}}` |

When the program rotates, the coach infers the position (the coach-led
session's log, then the state file, then the newest check-in) and
states it for your confirmation rather than asking it alone.

### Coach-led sessions

`external_sessions` are the sessions someone else runs: PT, a class, a
club night. Each has a weekday (or null when the day varies) and an
estimate of hard sets per muscle. They add volume and fatigue, so the
coach counts them in weekly balance and the check-in asks what happened
in them.

### Blocks and light weeks

`blocks.hard_weeks_ceiling` is the number of completed hard weeks after
which the coach proposes a light week: 6 by default, settable from 4 to
8. `blocks.deload_rule` names how a deload week is built:

| Deload rule | Effect |
|---|---|
| `standard` | Keeps two thirds of each line's working sets (at least one), aims 10 % off the loads and puts every set at RPE 6 |
| `scheme` | Uses each exercise's own scheme's deload (the wave's 40/50/60 % week), and the standard deload for schemes without one |
| `light` | Keeps two thirds of the sets at the loads already lifted, with no set above RPE 8 |

The triggers, the count and the skip rule are in
[Blocks and light weeks](blocks-and-light-weeks.md).

### Missed-day rules

A **missed-day rule** is the program's standing answer to one missed
session, agreed before the week starts. Each names a session and an
action:

- **`fold`**: some of its exercises (2 working sets each by default,
  never more than prescribed) go into a later session that week, for
  that week only.
- **`shift`**: the whole session moves to the first free day in a list,
  each day inside your `[athlete] available_days`.
- **`skip`**: the session is dropped for the week.
- **`manual`**: a rule in words only, decided when it happens.

Rules are optional. For a miss no rule covers, you choose when it
happens: move the session, reshuffle the week, or drop it. `python3 -m
coach missed rules` prints the current rules in plain words.

### Dose targets and dose intent

Programs are sized to **dose**: sets actually trained, counted per
muscle and per week in fractional hard sets, where an indirect set
counts as half. `dose_targets` declares the weekly target per muscle.
`dose_intent` records the goal the design conversation agreed
(`hypertrophy`, `strength` or `maintenance`), your ordinary `baseline`
per muscle, and the `reasons` behind each agreed target. A target of 0
with a reason is a deliberate omission.

A muscle with no target that a core session trains as a primary muscle
takes the hypertrophy starting fallback of 10. Under a strength or
maintenance goal there is no fallback: its target is pending until you
and the coach agree one. `python3 -m coach structure balance` compares
the planned weekly sets per muscle, coach-led sessions included, with
the targets, and raises a coverage gap for a major muscle with no sets
and no agreed target.

### Priority lifts and the minimum week

A **priority lift** is one the program protects above the rest. Each
has a KPI (`e1rm`, `top_load`, `top_reps` or `rung`, optionally with a
target and a date) and a **floor dose**, by default 2 hard working sets
at the prescribed load and reps. When the session carrying the lift is
missed and dropped from the week, the floor is folded into the next
session that week.

`minimum_week` names at most two `standby` sessions and their schedule:
the fallback for a week the full program cannot happen. It must carry
every priority lift's floor and at least a third of each muscle's
ordinary planned dose. A minimum week neither adds to the block count
nor ends the block.

### Interference rules

`interference` lists the rules that keep hard cardio and heavy lifting
apart. Two ship with the framework, and a first program takes both with
their defaults:

| Rule | Default |
|---|---|
| `same_day` | Lift first and keep at least 6 hours before a same-day quality activity |
| `quality_before_heavy_lower` | No quality activity in the 24 hours before a heavy squat or hinge session (a working set at RPE 7 or more, or of 6 reps or fewer with no RPE set) |

A broken rule raises a flag in the week's proposal; the coach and you
decide what moves. An empty list turns the rules off. `python3 -m coach
interference list` shows the program's rules and every rule available.

## The starters

A **starter** is a tested program that ships with the framework.
`python3 -m coach starters list` prints each one with its days, minutes,
required equipment, the swaps your kit needs, and whether it is
recommended for your experience. `starters show <id>` prints its session
pages.

| Id | Title | Days | Summary |
|---|---|---|---|
| `full-body-3` | Full body, 3 days | 3 | Three full-body sessions built on the squat, bench press, deadlift and overhead press, adding load every session while the lifts keep moving; without a barbell, draft swaps in dumbbell and bodyweight variants |
| `upper-lower-4` | Upper/lower, 4 days | 4 | Two upper-body and two lower-body sessions, every muscle trained twice, with reps added inside a range before the load goes up |
| `push-pull-legs` | Push/pull/legs, 3 to 6 days | 3 to 6 | Push, pull and leg sessions taken in turn on whichever days you train, so each muscle is trained twice a week at 6 days and about once a week at 3 |
| `wave-3wk` | 3-week wave (5/3/1-style), 4 days | 4 | One barbell lift leads each session, run as three-week waves of rising percentages of a training max with the last set taken for as many reps as you can |
| `rpe-full-body-3` | Full body by RPE, 3 days | 3 | Three full-body sessions where each main lift works up to one top set at a target RPE, the load follows how that set felt, and back-off sets follow from the same e1RM |

Every starter declares its main lifts as priority lifts, its weekly dose
targets and a two-session minimum week. None programs direct abdominal
work, so expect that coverage gap in `structure balance`.

**Drafting a starter.** The coach runs `python3 -m coach starters draft
<id> --dry-run`, with `--days mon,wed,fri` when you train on days other
than `[athlete] available_days`, and `--location <name>` to fit it to
another place's kit. It exits 1 when the day count is outside the
starter's range or your kit lacks the equipment its main lifts need. The
draft swaps any exercise your kit, an unconfirmed apparatus or ability,
or your avoid list rules out for the first library substitute that fits,
and reports each swap with every substitute it passed over and why. An
exercise with no fitting substitute gets a `no_substitute` row for you
and the coach to settle.

The coach then asks once whether you know your working weights for the
priority lifts. Each you give becomes a start load, passed as
`--start-load <exercise id>=<load>` in your units and per hand for
dumbbells. The coach guesses no number for you.

**The calibration week.** Every other loaded line starts with no load.
In week one its athlete guidance asks you to pick a load you expect to
lift for the target reps within the RPE shown, then adjust it after the
first working set. The next week's loads come from what you logged.

## Importing from Hevy

The Hevy route keeps your actual structure; the coach does not reshape
it during the import.

1. **Run or coach?** The coach asks once whether you want your program
   run as written or coached, and records `[coaching] mode` in
   `config.toml`. See [Run mode and coach mode](#run-mode-and-coach-mode).
2. **Pull.** `python3 -m coach hevy pull` fills the local cache.
3. **Interview.** The coach asks which routines are active, how they
   rotate across a week or longer cycle, whether any coach-led sessions
   sit alongside them, where the rest days fall, and what progression
   rule you follow.
4. **Load modes.** `python3 -m coach library seed` matches every
   exercise in your routines to the library and proposes how each is
   loaded. The coach puts each low-confidence proposal and each guessed
   custom entry to you, deciding from how you perform the lift (an
   alternating curl is one implement), and records the answers with
   `library set-mode` or `library confirm`. Nothing is confirmed on your
   behalf.
5. **Import.** `python3 -m coach program import-hevy` (`--routine <id>`
   for each active routine, or `--folder <id>`) writes the draft with
   one session per routine: set groups, rest, supersets, a start load
   from each routine's top working set converted with the confirmed load
   mode, and cues from the exercise notes. It exits 1 naming any
   exercise still without a confirmed load mode. Routines titled
   `(unused)` are skipped.
6. **The report.** The coach shows the report as one table: every
   converted load (check each dumbbell number against your actual
   dumbbells), working sets at mixed loads, cues taken from notes, and
   the missing schedule. When the import detects a percentage-based
   program (`%`, "TM", "5/3/1", week-marked titles, spread top loads),
   it shows the evidence and the schemes it suggests, and applies none.
7. **Finishing the draft.** With you, the coach settles the schedule
   rule and its days (adopt refuses an empty schedule), coach-led
   sessions, the light-week policy and a progression scheme per
   exercise. **Import sets every scheme to `hold`**; the coach maps your
   own progression rule to a scheme with you. Cues are agreed as you go.
8. **Adopt**, as above.
9. **A coaching review.** The coach runs `structure balance` on the
   draft, agrees dose targets and dose intent with your own numbers as
   the ordinary baseline, then assesses balance gaps, missing
   progression, junk volume and recovery clashes between adjacent days.
   It proposes improvements and forces none. In run mode it mentions
   them as information only.

## Importing from paper

The paper route needs no Hevy. The coach transcribes your program's
sessions, exercise order, working and warm-up set groups, rep targets,
rest, supersets, cues and progression rules into a draft, resolving ids
with `library search`. It asks only for what is missing or ambiguous:
days, rotation, loads, progression, the light-week policy. A progression
rule no scheme represents is explained, and a representation agreed,
before adoption. A missing load can use calibration; a load you supply
stays once confirmed. The coach shows the transcription beside your
original and names every agreed addition or change, then adopts as
above. With Hevy off, you train week one from the session sheets.

## Designing a program

Path B is a coaching conversation grounded in `profile.md` and
`config.toml`:

1. **Constraints.** The coach confirms goal, experience, equipment,
   training week, time per session, injuries, recovery and cardio from
   your profile, and asks only what is missing.
2. **Structure options.** It proposes two or three structures that fit,
   with trade-offs (for four days: upper/lower, full body, or PPL plus
   one), and recommends one with its reason. Where a choice depends on
   evidence, it reads the research notes first and cites the claim.
3. **The draft.** Rules first: the progression scheme (double
   progression is the sensible default), RPE targets, the hard-week
   ceiling for you, the warm-up protocol. Then each session, every
   exercise from the library, with a custom exercise created first when
   none fits. A start load you do not know stays null for a calibration
   week. Every profile constraint is respected: load caps, session time
   limits, recovery windows around coach-led sessions and cardio. The
   interference rules take their defaults for a first program. Missed-day
   rules are explained and added only when you want them.
4. **The walk-through.** The coach explains the reasoning, not just the
   tables, and iterates until you would actually train it. Before
   showing the draft it runs `structure balance` on it and settles each
   coverage gap (a target, or a 0 with its reason), each pending target
   and each volume undershoot with you.
5. **Hevy.** Adopt lists sessions without a routine and orphan routines.
   The routines themselves are created in the opening programming pass,
   with a preview you approve. See [Hevy](hevy.md).

## Redesigns

A redesign is Path B with a program already in place. `program adopt`
refuses (exit 3) until the coach adds `--replace` with your approval.
With it, adopt archives the current `data/program.json` and
`data/state.json` under `data/archive/programs/<today>/`, keeps the
progression state of every exercise whose session, exercise and scheme
are unchanged, carries the current block over, and removes the pages of
sessions the new program drops. The coach carries forward what the last
block taught, from the latest deep check-in, and keeps the interference
rules you had tuned.

The Hevy routine map is carried over for sessions the new program keeps.
Managed routines no session uses any more become orphans: the coach
offers to leave, reuse or retire each, and does none of it without your
approval.

**The adherence rule.** Under 80 % adherence over the trailing four
ordinary weeks, a redesign adds no new recurring session, conditioning
and optional ones included, and the coach pushes back if you ask for
one. Exercise swaps within a session are fine. A redesign the adherence
trigger started builds the smaller schedule the check-in agreed.

## Run mode and coach mode

`[coaching] mode` in `config.toml` is `"coach"` by default: the coach
reviews the program's structure and proposes changes. With `"run"`, you
want your own program run as written. Loads still progress and every
safety check still runs, but flags that propose a structural change are
shown as information, and the coach never proposes a restructure, a
swap, a new session or a redesign unless you ask. The import path asks
you which you want; a default config value alone is not a choice.

## Editing the program later

A swap, a cue change or a fix is an edit to `data/program.json`,
followed by `python3 -m coach program validate` and `python3 -m coach
program render`. Validate checks the schema, the library ids, the
confirmed load modes and your config, and exits 1 with the path of each
problem. Render rewrites `routine/program.md` and the session pages,
removing pages for sessions the program no longer has. **Never edit the
`routine/` pages by hand**: a check fails when a page differs from a
fresh render.

The coach confirms before editing `data/program.json`. "Go" to a coach's
brief that names a structural change confirms exactly that change.

A load mode corrected after adoption works like a correction in the
draft: `library set-mode` lists the program lines left in the old mode,
`program validate` fails on each, and the coach asks what each start
load meant before running `program reconcile-mode <id> --basis
old|confirmed`, which also re-renders the pages.

## Custom, avoided and skill exercises

**Custom exercises.** When no library entry fits, the coach follows
[`reference/custom-exercises.md`](../../reference/custom-exercises.md):
it agrees the name, muscles, pattern, equipment and load mode with you,
previews the entry with `python3 -m coach library create custom_<slug>
--input <file> --dry-run`, and creates it only after you confirm the
exact entry. Creation writes `data/exercises.json` only. With Hevy on, a
custom exercise still needs a real Hevy template mapped before a routine
can be written; the coach never invents one.

**Avoided exercises.** `python3 -m coach library set-avoid <id> --reason
"<why>"` records an exercise you cannot or will not do. A starter draft
swaps it out; adopt keeps it in an imported or designed program but
reports it, and the coach proposes a swap from the entry's substitutes.
`--clear` removes the avoidance.

**Apparatus and demonstrated ability.** An exercise may need a bench,
bar or support beyond its equipment (`[equipment] apparatus` in
`config.toml`), or be a skill exercise such as a pull-up, dip or Nordic
curl that needs **demonstrated ability**: you have shown you can do it
for working sets, listed in `[athlete] demonstrated_exercises`. A swap
picks such an exercise only when the config confirms it. When you
confirm a missing bench or show you can do a skill exercise, the coach
updates `config.toml` and drafts again.

## After adoption

The coach recaps the structure, rotation, progression and deload in one
paragraph, then offers to program the opening week with `/program-week`.
That pass sets concrete starting loads, rep targets, RPE and notes for
week one, creates any Hevy routines the sessions lack, and writes a
**Program start record** in `check-ins/` to hold the week's overlay, so
the first `/check-in` has a prescription to judge against. The first
check-in after a new program pays extra attention to whether the
starting loads and volume landed right.

Adopt staged the new `data/` files and the rendered `routine/` pages.
The coach offers to commit them once you approve.
