# Training Workspace

The active record of an athlete's training and nutrition, coached through
skills that plan in this repo and log in external apps (Hevy, MacroFactor).

## Language

**Program**:
The whole training structure an athlete follows: its sessions, how they
rotate across the calendar, how it progresses, and when it lightens.
_Avoid_: routine (Hevy's word for a session template), plan, split

**Session**:
One training day's template inside a program: the exercises, sets, reps,
intensity and rest it prescribes. A session is **core** when it carries
work nothing else covers and must land for the week to count, or
**optional** when it is bonus volume and skipping it is not a miss.
_Avoid_: routine, workout, day

**Workout**:
One logged instance of training, as recorded in Hevy or described by the
athlete. A workout is what happened; a session is what was planned.
_Avoid_: session, log entry

**Exposure**:
One logged instance of a single exercise on a given date. Prescriptions
are derived from exposures and go stale when the exposure is old.
_Avoid_: attempt, data point

**Validity window**:
How long an exercise's newest exposure keeps its prescription current:
the exercise's usual gap between exposures plus a short grace period.
Past it, the line must step back by its return band.
_Avoid_: freshness, expiry

**Return band**:
The step back a lift takes after time off, picked by its days off (the
longer of the layoff and how far its newest exposure is past its usual
gap): a load cut, one working set fewer and, after the longest gaps, an
RPE cap. The bands are set out once, in `CLAUDE.md` "Coaching
principles".
_Avoid_: decay level, detraining band

**Provenance**:
What an overlay line was derived from: the exposure, the progression
scheme, any return-band decay and the reason. A line the coach wrote by
hand gets the exposure inferred and marked as inferred.
_Avoid_: source, origin, derivation

**Dose**:
What was delivered, not what was planned: sets actually trained, counted
per muscle group and per week. Programs are sized to dose.
_Avoid_: volume (ambiguous between planned and delivered)

**Block**:
The stretch of hard training between one light week and the next,
counted in completed hard weeks rather than calendar weeks.
_Avoid_: mesocycle, cycle, phase (reserved for bulk/cut/maintain)

**Overlay**:
The per-exercise prescription in force for a span of days: loads, sets,
reps, intensity and notes, as approved by the athlete. Adherence is judged
against it; the brief and the Hevy routine notes are views of it. A
mid-week reprogram or a one-off week is a new overlay that supersedes the
old one for the days it covers.
_Avoid_: weekly plan, week's targets, weekly overlay

**Progression scheme**:
The named rule that turns an exercise's recent exposures into its next
prescription: double progression, linear, wave, RPE-anchored, assistance
ladder, hold. Every exercise in a program has one.
_Avoid_: progression model, autoregulation (one kind of scheme)

**Recovery cap**:
An RPE ceiling written into an exercise's prescription to protect
recovery or a niggle: every working set stays at or under it. RPE drift
on a capped set counts like drift on a compound lift, whatever the
exercise.
_Avoid_: RPE ceiling, cap (ambiguous with a load cap)

**Schedule rule**:
The named rule that decides which session lands on which day: fixed
weekdays, alternating templates anchored to an external session,
next-in-sequence, or an explicit calendar.
_Avoid_: rotation (one kind of schedule rule), split

**Load mode**:
How an exercise is loaded in a given program slot, which fixes how the
weight the athlete sets relates to the **Hevy value** (the `weight_kg`
Hevy stores). With two dumbbells (`per_hand_x2`) the **per-hand** load is
what each dumbbell weighs and the Hevy value is twice it: 25/hand is Hevy
50. With one implement (`single_implement`) the two numbers match. The
other modes are `total` (bar or stack), `bodyweight` (added load),
`assisted` (assistance), and `band`, `duration` and `distance`, which
carry no load. A property of the slot, not of the exercise's name.
_Avoid_: load type, dumbbell weight (ambiguous between per-hand and Hevy value)

**Exercise library**:
Every exercise the coach can prescribe, each with a stable id: the
builtin catalogue that ships with the framework, merged with the
athlete's own entries (overrides, custom exercises, the load mode the
athlete confirmed for each exercise, and exercises they avoid). Exercises
in a program, an overlay or a Hevy routine are named by library id.
_Avoid_: exercise database, exercise list, catalogue (only the builtin part)

**Coach's brief**:
The narrative presentation of a proposed training week, given to the
athlete for approval before anything is written: week focus, what's
changing and why, per-session tables, then one closing line naming
exactly what approval will write.
_Avoid_: summary, proposal, plan preview

**Brief** (this week's brief):
The standing one-page statement of the current week: focus, sessions,
what changed, what to watch, what to do if a day is missed. Rewritten
every programming pass; the thing the athlete reads during the week.
_Avoid_: dashboard, summary, this-week doc

**Sunday message**:
The one message the coach sends at check-in about the week just
trained: it states what the log shows and numbers what it cannot
(sessions, coach-led content, runs, sleep, niggles, food — nutrition
readings, habits and next week's food exceptions — and anything
different next week), for the athlete to answer in
one reply. Replaces an interview.
_Avoid_: check-in form, intake, questionnaire

**Hold-steady week**:
A weekly-tier check-in week, not a deload, with no structural change, no
new or worsening niggle, no goals or phase flag, nothing different next
week, and only progression-scheme changes. Its coach's brief shrinks to
three sentences and the closing line; the tables are offered, not shown.
_Avoid_: quiet week, maintenance week

**Approval gate**:
The rule that content the athlete has not yet seen (a coach's brief, a
recipe card) and every Hevy write wait for the athlete's reply:
presenting and writing never happen in the same turn. On a programming
pass one reply, "go", approves the coach's brief and every write its
closing line names. Reversible writes to git-tracked records need no
gate.
_Avoid_: confirmation step, sign-off

**Session-start status**:
The few lines of `coach status` the coach sees at the start of every
session: where the instance stands now (the overlay in force and whether
it reached Hevy, failing checks, the cache age, the block, the next
check-in), with the items that need raising first. Read from local files
only.
_Avoid_: briefing, dashboard (the rendered `README.md`), status line (a
check-in record's line)

**Activity source**:
Where logged cardio and health signals come from: a phone health export,
a training-analysis service, a run-plan calendar feed, or the athlete by
hand. Every source is optional; manual entry is always available.
_Avoid_: integration (reserved for Hevy and the nutrition app), feed

**Activity**:
One logged bout of non-lifting training (a run, a ride, a conditioning
session) from any activity source.
_Avoid_: workout (reserved for logged lifting), cardio session

**Wellness day**:
One calendar day of the athlete's health readings (sleep, resting heart
rate, steps, body mass), resolved across activity sources. Sleep belongs
to the day the athlete woke. A record entered by hand may cover a span,
such as a week's average sleep, and fills only the days no daily reading
covers.
_Avoid_: readiness (nothing computes a readiness score), health day

**Planned activity**:
A dated, planned bout of non-lifting training from a run plan, the coach
or the athlete. Its record says whether it is intervals, tempo,
threshold, hills or a race.
_Avoid_: planned session (a session is a program template), planned run

**Research note**:
A dated, cited answer to one coaching question, with a confidence and a
review-by date (`review_by`), that the coach consults before deciding in
that area. Comes in two kinds with one format: a **template note**
(`research/<id>.md`), shipped and refreshed in the template, and a
**local note**. A note past its review-by date is expired; its area stays
current only while a local note covers it.
_Avoid_: reference, evidence doc, wiki page

**Claim**:
One numbered, one-sentence statement inside a research note, with its
basis (evidence, consensus or heuristic), its sources and a status
(current or retired). Cited as `rn:<note-id>.<n>`; a claim's number is
never reused, and a claim that no longer holds is retired, not deleted.
_Avoid_: finding, fact, citation (the reference to a claim, not the claim)

**Local note**:
A research note the coach writes in an instance, at
`research/local/local-<slug>.md`, whenever it researches something for
this athlete. Framework sync never touches it. It may supersede template
claims for this instance by listing them in `updates`, and never edits a
template note.
_Avoid_: instance note, personal research, override note

**Recipe bank**:
The athlete's set of approved recipe cards in `nutrition/menu/`, plus
its index — what `/meal-plan` selects from.
_Avoid_: food bank, menu (ambiguous with the directory name)

**Protein floor / target / stretch**:
The three daily protein numbers `/goals` sets, each per kg of a
**reference mass** (current bodyweight, goal weight when body fat is
high, or fat-free mass when a credible body-fat reading exists). The
**target** is what the coach steers toward, the **stretch** is the most
that still adds anything, and the **floor** is the reachable number the
athlete is held to now: recent intake plus a little, never under
1.2 g/kg of bodyweight or goal weight (~1.5 g/kg of fat-free mass) or
over the target. The floor rises after two consecutive
check-ins at or over it and only `/goals` lowers it. For a nutrition app
user the floor is the protein number set in the app.
_Avoid_: protein goal, protein minimum, macro target, g/kg bodyweight (without the reference mass)

**Protein anchor**:
One of 2–3 standing daily items, each carrying ~25 g protein or more
and needing no cooking, eaten in a fixed slot on set days so that with
typical meals the athlete reaches the protein floor. Agreed in `/goals`;
`/meal-plan` places anchors as fixed blocks.
_Avoid_: protein snack, top-up, staple (an item kept in stock, not one eaten daily)

**Standing template**:
The athlete's typical eating week, described once in `config.toml`
(`[nutrition.template]`): the meal slots, office days, staples, plan
style, and one standing row per slot and set of days that names a recipe,
a pool of recipes to pick from each week, or a cover (someone else
decides, with an estimated kcal and protein). Every weekly meal plan
starts from it, with the protein anchors placed in their slots.
_Avoid_: meal template, default week, usual plan

**Plan exception**:
One way a week's meal plan departs from the standing template: a slot
filled differently on one date (a meal out, a skipped lunch, someone
else cooking) or a day's office status changed. An exception replaces
everything the template puts in that slot that day, anchors included. A
plan is its exceptions, the coach's picks for open and pool slots, and
the items to use up; the athlete gives the exceptions in one line.
_Avoid_: override (reserved for the nutrition override), swap, change

**Nutrition override**:
A dated period in which the athlete eats to a number other than the
nutrition app's (or, without an app, the trend-driven calorie target):
start date, what is overridden, reason, exit condition, and an expiry no
more than 21 days after the start. At most one at a time; `/check-in`
expires it, renewal needs `/goals`, and a second consecutive renewal is
flagged.
_Avoid_: manual targets, calorie band, adjustment (a trend-driven change, not an override)

**Nutrition reading**:
The numbers recorded at one check-in about eating and bodyweight: the
nutrition app's trend weight, expenditure, targets, 7-day averages and
days logged, or, without an app, the mean of the week's morning
weigh-ins; plus whether the protein anchors happened most days. One per
check-in date, kept as a series in `data/nutrition/readings.json`. A
reading copies the app's numbers; nothing in the repo computes them.
_Avoid_: weigh-in (one scale reading), nutrition log (the app is the log), check-in numbers

**Sleep gate**:
The check `/goals` runs before agreeing a deficit: a trailing 14-day
sleep average under ~7 h means recomp at maintenance instead. With no
sleep source it is recorded as `pending measurement` (short sleep
reported, recomp by default) or `not evaluated`; `/check-in` re-checks it
during a deficit once a source exists.
_Avoid_: sleep check, sleep rule, recovery gate
