# Concepts

The mental model behind the system, in plain words. Each term here is
defined formally in [the glossary](../../CONTEXT.md); this page says what
it means for you and how the pieces fit. Read it once; the other guides
assume it.

## Two kinds of file

**Data files are the truth; pages are views of them.** Anything a script
reads or writes is JSON under `data/` or TOML in `config.toml`. The
markdown you read (the dashboard, this week's brief, the session pages,
the tables in a check-in record) is rendered from that data and carries
a header line saying so. If you edit a rendered page by hand, a
freshness check fails and the coach re-renders it; the fix always goes
in the data. Prose that only a human reads (your profile, the coach's
read in a check-in, a recipe's method) stays prose.

**Scripts compute; the coach decides; you approve.** Every load,
conversion, progression step and Hevy write is done by `python3 -m
coach ...` commands that print one JSON result. The coach reads the
result, coaches on it, and shows you a brief. Nothing reaches Hevy, and
no program or profile change lands, until you say "go".

## The program and its sessions

Your **program** is the whole structure you follow: its sessions, how
they fall across the week, how each exercise progresses and when the
program lightens. It lives in `data/program.json` and is rendered to
`routine/program.md` plus one page per session. It changes only on a
structural edit (a swap, a set count, a new session), which the coach
proposes with before and after.

A **session** is one training day's template inside the program. A
**core** session carries work nothing else covers and must land for the
week to count; an **optional** session is bonus volume; a **standby**
session waits unscheduled until a minimum week calls on it.
**Coach-led** sessions (PT, team training) are in the program too, so
weekly balance and fatigue count them.

A **workout** is what happened: one logged instance of training. An
**exposure** is one logged instance of one exercise on one date.
Prescriptions are derived from exposures, which is why an old exposure
makes a prescription stale.

Each exercise has a **progression scheme**, a named rule that turns its
recent exposures into the next prescription: double progression,
linear, wave, RPE-anchored, assistance ladder, maintenance, or hold. The
program also has a **schedule rule** (fixed weekdays, templates that
alternate around a PT day, next-in-sequence, or an explicit calendar)
and optional **missed-day rules**: a standing answer to "I missed
Session B", agreed before it happens.

## The week: overlay, brief, go

A **programming pass** is one run of `/program-week`: one mode, one
overlay, one approval. Its output is an **overlay**, the per-exercise
prescription in force for a span of days: loads, sets, reps, RPE and
notes. The next check-in judges adherence against it. A mid-week
reprogram or a one-off week is a new overlay that supersedes the old one
for the days it covers. The program stays untouched: weekly numbers
never go into it.

The **coach's brief** is how a proposed week is presented: the week's
focus, what is changing and why, per-session tables, then one closing
line naming exactly what "go" will write. The **approval gate** is the
rule that content you have not seen, and every Hevy write, waits for
your reply. Presenting and writing never happen in the same turn. One
"go" approves the brief, every write its last line names and the
records it commits. In Hevy, a PreToolUse hook shows the exact write in
the permission prompt before it runs, so the gate is mechanical, not a
promise.

**This week's brief** (`this-week.md`) is the standing one-page
statement of the current week: focus, every session including PT and
runs, what changed, what to watch, what to do if you miss a day. The
**dashboard** (`README.md` in your copy) is where you stand this week:
the block, the last check-in, consistency, the sessions, the Watch
list. The **progress page** lists each lift's best e1RM, consistency
week by week and bodyweight. **Publish** is the commit and push after
your "go" that gets these to your phone.

## The check-in

A **check-in** is the weekly review. It opens with one **Sunday
message** that states what the log already shows and numbers what it
cannot see: missed-session reasons, what the PT session covered, runs,
sleep, niggles, your food numbers, anything different next week. You
answer in one reply. The result is a dated **review** record in
`check-ins/`, then the programming pass for next week.

There are two tiers. A **weekly** check-in takes about ten minutes. A
**deep** review runs every six weeks or so, when a light week is newly
proposed, or when adherence drops: it looks at the whole block. A
**catch-up** check-in runs after more than ten days without one: a
summary row per week of the gap and a proposed **return week**, which one
"ok" accepts.

A **hold-steady week** is a weekly check-in where nothing needs
deciding: the summary and the brief collapse into three sentences and
the write line, and you reply "go".

## Blocks, hard weeks and light weeks

A **block** is the stretch of hard training between one light week and
the next, counted in **completed hard weeks**, not calendar weeks. A
week counts when at least three quarters of its planned core and
coach-led sessions passed the session gate: most prescribed sets logged,
not far under the target effort. A light week, a return week or a week
under half trained ends the block. One-off, minimum and planned break
weeks neither count nor end it.

A **light week** is proposed when the count reaches the program's
ceiling (six by default) or when two **fatigue triggers** fire in one
week: poor readiness you report, RPE drift on a compound lift two
sessions running, a niggle aggravated under load, or poor sleep most of
the week. One trigger is a watch. Below three completed hard weeks no
light week is scheduled. The three kinds are a **deload** (the program's
rule), a **light** week (fewer sets at held loads) and a **return** week
(after time off or illness). You agree or decline every one.

## Loads: the numbers you set

Every exercise has a **load mode** that fixes how the weight you set
relates to the value Hevy stores. Hevy records a dumbbell set as the
total across both hands, so a two-dumbbell lift always has two numbers:
`25/hand (Hevy: 50)`. The coach writes both everywhere, and never a bare
total for paired dumbbells. A single-implement lift (a one-arm row, an
alternating curl) has one number. Load modes are confirmed once per
exercise, from how you perform the lift, not its name.

A prescription is only as current as the exposure it came from. Each
exercise has a **validity window**, its usual gap between exposures plus
a little grace. Past it, the line steps back by its **return band**: a
load cut, one working set fewer and, after long gaps, an RPE cap. A
**calibration** line has no load yet: you pick one you could lift for
the target reps at the target RPE and adjust after the first working
set.

**Dose** is what was delivered, counted in hard sets per muscle per
week, with an indirect set counting half. Programs declare a **dose
target** per muscle and are judged on dose, not on what was planned. A
**priority lift** is one the program protects with a KPI and a **floor
dose**, two hard sets at the prescribed load even in a disrupted week.
The **minimum week** is the program's fallback for a week that cannot
happen in full: at most two standby sessions carrying every priority
lift's floor and a third of each muscle's planned dose.

## Weeks that break the pattern

`/program-week` has six modes. **Normal** is the coming program week.
**Midweek** reprograms the rest of a trained week after a miss or a
change. **Light** is a deload, light or return week. **Minimum** is the
program's fallback week. **Constrained** is a one-off week on different
kit or short time, built by the coach with temporary sessions that never
enter the program. **Reshuffle** keeps the sessions and moves the days.
A **planned break** is days you agreed not to train at all: no sessions
are planned, so none are missed.

## What the coach remembers between check-ins

A **niggle** is an ache worth watching, logged with the movements it
affects and its status (aggravated, watching, easing, resolved, or
chronic for a lasting limitation). While it is active, its limits (an
RPE cap, no added load, a load cap) apply to every matching line the
coach proposes. It is never a diagnosis; one that keeps coming back
means seeing a professional. A **follow-up** is a question with a review
date; every deep check-in settles each open one. A **status day** is a
day you were ill, injured or travelling, recorded so the right return
rule applies. A **decision** is a recorded coaching choice (a light week
declined, an override that holds for four weeks) with the reason, so
the scripts stop re-proposing what was already decided.

## Coach mode and run mode

In the default **coach mode** the coach reviews the structure of your
program as well as its loads and proposes changes at check-ins. In **run
mode** (`[coaching] mode = "run"`) you run your own program as written:
loads still progress and every safety check still runs, but structural
flags are information only and the coach never proposes a swap, a new
session or a redesign unless you ask.

## Nutrition

The repo sets the **strategy**: the **phase** (bulk, cut, maintain,
recomp), the trend rate, the goal weight and the protein numbers. Your
nutrition app sets the daily calories, and the repo never states its own
calorie target for an app user. **Protein floor, target and stretch**
are three daily numbers per kg of a **reference mass**; the floor is the
commitment now, raised only once you meet it. **Protein anchors** are
two or three standing daily items that get you to the floor without
cooking. A **nutrition reading** is the app's numbers copied in at each
check-in. A **nutrition override** is a dated period eating to a
different number, with an exit condition and an expiry of at most three
weeks. The **sleep gate** turns a planned deficit into a recomp when
your trailing two weeks average under about seven hours.

Food planning works from a **standing template**, your typical eating
week described once in `config.toml`, plus each week's **plan
exceptions** given in one line. The **recipe bank** in `nutrition/menu/`
is what meal plans pick from.

## Activity and recovery signals

An **activity** is one logged bout of non-lifting training (a run, a
ride, a conditioning session) from an **activity source**: a phone
health export, Hevy conditioning workouts, or you by hand. A **wellness
day** is one day's sleep, resting heart rate, steps and body mass. The
**cardio tier** says who owns the run plan: `count` (runs are counted
only), `review` (an outside plan is reconciled with what was logged) or
`program` (the coach writes the plan). **Interference rules** keep hard
running and heavy lifting apart and raise a flag when a week breaks
them. A **goal event** is a race or other dated target with a priority
and, only if you agree one, a lighter **window** before it.

## Evidence

Every number in the coaching rules cites a **claim** in a **research
note**, written `(rn:<note>.<n>)`. `python3 -m coach research show
<ref>` prints the claim and its sources. Template notes ship with the
system and have a review-by date; the coach writes **local notes** in
`research/local/` when it researches something for you, and those never
get overwritten by an update.
