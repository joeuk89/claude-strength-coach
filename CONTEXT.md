# Training Workspace

The active record of an athlete's training and nutrition, coached through
skills that plan in this repo and log in external apps (Hevy, MacroFactor).

## Language

**Program**:
The whole training structure an athlete follows: its sessions, how they
rotate across the calendar, how it progresses, and when it lightens.
_Avoid_: routine (Hevy's word for a session template), plan, split

**Program draft**:
A complete proposed program, plus a report of what its source could not
settle (converted loads, mixed loads, the missing schedule), that the
coach and athlete finish before it becomes the program. Every new
program, whether imported from Hevy, drawn from a starter or designed,
becomes the program only by being adopted, which validates it, archives
any old program and stages the files.
_Avoid_: proposal (a week's proposed prescriptions), candidate program, import file

**Starter**:
A tested program that ships with the framework for an athlete who has no
program of their own: full body, upper/lower, push/pull/legs, a 3-week
wave or full body by RPE. Drafting one fits it to the athlete's days,
equipment, **apparatus**, **demonstrated ability** and avoided exercises,
and its lines without a known load run a **calibration week**: no load,
and the athlete chooses one they could lift for the target reps at the
target RPE.
_Avoid_: template (the repo itself), preset, stock program

**Apparatus**:
A bench, bar or support an exercise needs beyond its equipment: a flat or
incline bench, a pull-up bar, a dip station, a Nordic anchor or a box. A
place has only the apparatus its config lists, unless it lists no kit at
all.
_Avoid_: equipment (the coarse kind: barbell, dumbbell, cable), fixture

**Demonstrated ability**:
What a skill exercise such as a pull-up, dip or Nordic curl needs before a
swap picks it: the athlete has shown they can do it for working sets.
Experience alone never confirms it.
_Avoid_: difficulty, level, clearance

**Run mode**:
The coaching mode for an athlete who wants their own program run as
written (`[coaching] mode = "run"`). Loads still progress and every
safety check still runs, but flags that propose a change to the
program's structure are shown as information, and the coach never
proposes a restructure, a swap, a new session or a redesign unless the
athlete asks. The default, **coach mode**, reviews structure as well.
_Avoid_: execute mode, hands-off mode, autopilot

**Session**:
One training day's template inside a program: the exercises, sets, reps,
intensity and rest it prescribes. A session is **core** when it carries
work nothing else covers and must land for the week to count, or
**optional** when it is bonus volume and skipping it is not a miss. A
**standby** session sits in the program unscheduled until a minimum week
calls on it.
_Avoid_: routine, workout, day

**Workout**:
One logged instance of training, as recorded in Hevy or described by the
athlete. A workout is what happened; a session is what was planned.
_Avoid_: session, log entry

**Exposure**:
One logged instance of a single exercise on a given date. Prescriptions
are derived from exposures and go stale when the exposure is old.
_Avoid_: attempt, data point

**Comparable e1RM**:
An e1RM from an exposure of ordinary training whose sets fall within the
reps-to-failure cap. Only comparable e1RMs feed a lift's best e1RM, its
change and a priority lift's e1RM KPI; light-week, return-week and
reduced work stays in the log beside them without counting as a loss.

**Model evidence**:
The comparable e1RM that limits a prescription's load, or the reason none
does: no comparable e1RM in the window, or newer over-cap work at or above
the load behind it.

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
per muscle group and per week. Programs are sized to dose. The same count
over the sets a program prescribes is the **planned dose**, so the two
compare like for like.
_Avoid_: volume (ambiguous between planned and delivered)

**Dose target**:
The weekly dose a program aims each muscle at, in fractional hard sets
(an indirect set counts as half). The program declares it. Without one, a
muscle a core session trains as a primary muscle takes the hypertrophy
starting fallback of 10, unless the dose intent records a strength or
maintenance goal: then its target is pending until the coach agrees one.
_Avoid_: volume target, set goal, MEV

**Dose intent**:
The lifting-dose goal the design conversation agreed (hypertrophy,
strength or maintenance), with the athlete's ordinary baseline per muscle
and the reason for each agreed target. A target of 0 with a reason is a
deliberate omission; a major muscle with no sets and no agreed target is
a coverage gap.
_Avoid_: training goal (the profile's words), phase (reserved for bulk/cut/maintain)

**Ordinary week**:
A week adherence is judged on: not a deload or other light week, not a
one-off or minimum week, and not inside a layoff of 11+ days. Adherence
looks at the last four, reaching back at most 12 weeks.
_Avoid_: regular week, counted week

**Planned session**:
A session the program expected on a date, which adherence counts as
trained or missed. The schedule rule plans sessions only from the day
the program was adopted, so older workouts never count as misses; an
earlier program's overlays keep their own weeks. A moved session is
planned once, on its new date. A new block changes neither.
_Avoid_: obligation, scheduled session

**Block**:
The stretch of hard training between one light week and the next,
counted in completed hard weeks rather than calendar weeks.
_Avoid_: mesocycle, cycle, phase (reserved for bulk/cut/maintain)

**Completed hard week**:
A program week in which at least three quarters of the planned core and
coach-led sessions were trained as prescribed: most of the prescribed
working sets logged, at about the target effort. It adds one to the
block's count; a light week, a return week or a week under half trained
ends the block.
_Avoid_: hard week (alone), training week, core-complete week (a different count)

**Light week**:
A week of reduced training that ends a block: a **deload** (the
program's deload rule), a **light** week (fewer sets at held loads) or a
**return** week (one set fewer after a layoff or illness). It is proposed
at the block's ceiling or on two fatigue triggers, and agreed or declined
by the athlete.
_Avoid_: rest week, recovery week, deload (one kind of light week)

**Fatigue trigger**:
One of four signs a block needs a light week: poor readiness the athlete
reports, RPE drift on a compound lift two sessions running, a niggle
aggravated under load, and poor sleep for most of the week. Two in a
week propose a light week; one is a watch.
_Avoid_: fatigue flag, warning sign

**Block ledger**:
`data/blocks.json`: every block and each week a check-in closed in it,
with the week's class, counts, signals and outcome. The block in
`data/state.json` is its summary.
_Avoid_: block log, block history

**Overlay**:
The per-exercise prescription in force for a span of days: loads, sets,
reps, intensity and notes, as approved by the athlete. Adherence is judged
against it; the brief and the Hevy routine notes are views of it. A
mid-week reprogram or a one-off week is a new overlay that supersedes the
old one for the days it covers.
_Avoid_: weekly plan, week's targets, weekly overlay

**Missed-day rule**:
The program's standing answer to one missed session, agreed before the
week starts: fold some of its exercises into a later session, shift the
whole session to a free day, or skip it. It is applied as a mid-week
overlay once the athlete says go; a miss no rule covers goes back to the
coach to reprogram.
_Avoid_: make-up rule, catch-up plan

**Fold**:
Sets from a missed session added to a later session in the same week,
for that week only. The next week is built from the program again, so a
fold never carries forward.
_Avoid_: make-up sets, carry-over

**Priority lift**:
A lift the program protects above the rest, with a KPI (best e1RM, top
load, top reps or ladder rung, optionally a target and a date) and a
floor dose. Its exposures are counted each week against plan.
_Avoid_: main lift (looser), key lift, focus lift

**Floor dose**:
The least a priority lift gets in a disrupted week: by default two hard
working sets at the prescribed load and reps. When the session carrying
the lift is missed and the program's missed-day rule doesn't keep the
lift in the week, the floor is folded into the next session that week. A
program fold that carries the lift at fewer sets is topped up to the floor.
_Avoid_: minimum sets, maintenance sets

**Minimum week**:
The program's fallback week for when the full week cannot happen: at
most two standby sessions, each within its time cap, carrying every
priority lift's floor dose and at least a third of each muscle's planned
dose in the corresponding ordinary week. Every coach-led estimate the
ordinary week counts contributes to that reference; only coach-led sessions
explicitly retained in the minimum contribute to its planned dose. The
fractional-set check is application policy, not a maintenance guarantee.
Its overlay is a weekly overlay, but the week is not an ordinary week, and
it neither adds to the block's count nor ends the block.
_Avoid_: minimum-viable week (the roadmap's phrase), fallback week, deload

**Progression scheme**:
The named rule that turns an exercise's recent exposures into its next
prescription: double progression, linear, wave, RPE-anchored, assistance
ladder, maintenance, hold. Every exercise in a program has one.
_Avoid_: progression model, autoregulation (one kind of scheme)

**Density scheme**:
The progression scheme of a whole conditioning session: an EMOM or a
circuit whose prescribed work is fixed and which steps up, holds or steps
back on the athlete's session RPE (and, for a circuit, the finish time
against its cap). Every exercise in the session holds its load. The
steps are a coaching heuristic.
_Avoid_: conditioning progression, density progression, finisher

**Training max**:
The load a wave's percentages are taken from: 90 % of the e1RM by
default, or a load the program sets, raised by a fixed increment at the
start of each wave and lowered by a return band after time off. It is
kept in the exercise's scheme state, never in the program.
_Avoid_: TM, working max, 1RM (the training max sits below it)

**Standing override**:
A coach's change to one exercise's proposed prescription that holds in
later weeks until a set end date (four weeks by default, eight at most),
so the progression scheme stops proposing it away; the scheme's own
proposal is still shown beside it. A one-week override changes only the
week it was made in.
_Avoid_: pinned line, manual hold, permanent override

**Recovery cap**:
An RPE ceiling written into an exercise's prescription to protect
recovery or a niggle: every working set stays at or under it. RPE drift
on a capped set counts like drift on a compound lift, whatever the
exercise.
_Avoid_: RPE ceiling, cap (ambiguous with a load cap)

**Niggle**:
An ache or minor injury worth watching for recurrence, logged in
`data/niggles.json` with the movement patterns and exercises it affects
and its status: aggravated, watching, easing, resolved, or **chronic**
for a lasting limitation. While it is aggravated or watching (always,
when chronic) its load limits (a recovery cap, no added load, a load
cap) apply to every matching line the proposal step writes. A niggle is
never deleted, never diagnosed, and one reported three check-ins
running, or worsening to aggravated, means recommending a qualified
professional (never for a chronic niggle, a known lasting limitation).
_Avoid_: injury (a diagnosis the coach does not make), limitation (use
chronic niggle), pain point

**Follow-up**:
A question to come back to later, with the date it was raised, where it
came from and a review date, kept in `data/followups.json`. It stays
open until it is resolved or dropped with a reason; every deep check-in
settles each open one, keeping it open with a new review date if need
be.
_Avoid_: todo, action item, open question, revisit (a decision's revisit date)

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

**Total-system e1RM**:
The e1RM of a `bodyweight` or `assisted` lift: bodyweight plus the added
load, or minus the assistance, so it estimates the mass the athlete
moves, not the load they set. It needs a bodyweight reading (a Hevy body
measurement or a nutrition reading) within 14 days of the workout, and
every display labels it "total system mass". Dumbbell split squats,
lunges and step-ups, whose dumbbells are a small share of the mass moved,
get no e1RM at all.
_Avoid_: bodyweight e1RM (ambiguous between the total and the added load)

**Exercise library**:
Every exercise the coach can prescribe, each with a stable id: the
builtin catalogue that ships with the framework, merged with the
athlete's own entries (overrides, custom exercises, the load mode the
athlete confirmed for each exercise, and exercises they avoid). Exercises
in a program, an overlay or a Hevy routine are named by library id.
_Avoid_: exercise database, exercise list, catalogue (only the builtin part)

**Managed routine**:
A Hevy routine the coach created, imported or reused for a session, so
that `data/state.json`, now or in a program archive, maps it to a
session. Sharing a folder with managed routines does not make a routine
managed. An **orphan routine** is a managed routine no current session
or temporary-routine entry uses; the coach offers to leave, reuse or
retire it, and does none of them without approval.
_Avoid_: old routine, unused routine (a retired routine is titled `(unused)`)

**Programming pass**:
One run of `/program-week` in one mode (normal, midweek, light, minimum,
constrained or reshuffle): it builds one overlay for a span of days and
ends in one approval, the athlete's "go" to the coach's brief.
_Avoid_: programming session (a session is a training day), weekly update

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

**Dashboard**:
The instance's `README.md`, rendered: where the instance stands this
week (the brief's header line, the block, the last check-in, open flags),
the week's sessions, a progress summary and links. The page GitHub shows
first on a phone.
_Avoid_: home page, status page, session-start status (what the coach sees)

**Progress page**:
`progress.md`, rendered: the best e1RM of each lift with its date, the
core-complete streak, and bodyweight by week.
_Avoid_: stats page, PR list

**Session sheets**:
`this-week-sheets.md`, rendered for an athlete without Hevy: each session
of the week's overlay as a table of sets, reps, load, RPE and rest, with
an empty Done column, then its cues. Loads show the athlete's number
only (`25/hand`). What the athlete trains from when there are no Hevy
routines.
_Avoid_: workout card, printout, routine (Hevy's word)

**Manual log**:
`data/log/workouts.jsonl`: the workouts an athlete without Hevy reports
in chat, one line each, written by the coach with `log add`. Append-only;
a correction is a void line plus a new entry. History reads it like the
Hevy log.
_Avoid_: training diary, journal, log entry (a workout is the thing logged)

**Core-complete week**:
A week in which every planned core session was trained, logged or not,
and no coach-led session is recorded as not having happened. Optional
sessions never count, and a coach-led session nobody recorded neither
counts nor breaks it. Consecutive ones make the core-complete streak.
_Avoid_: perfect week, full week, completed hard week (the block's count)

**Publish**:
After the athlete's "go", commit and push exactly the brief, the
dashboard, the progress page, the week's overlay and the newest check-in
record, plus the current session sheets when Hevy is off and the
records of the commit plan, so the phone shows the week. `/goals`
publishes the approved week again after a nutrition change. The only
push the coach makes without being asked.
_Avoid_: deploy, sync (Hevy sync and framework sync are other things)

**Commit plan**:
The training records the brief's write line names for commit with the
week, file by file: those already changed and those the approved write
steps will write. They are the manual log, state, decisions, block
ledger, history and routine pages, and the program only for a structural
change the same brief names. The athlete's "go" approves each named
record as it stands at publish; a changed record the plan did not name
stays local until they agree.
_Avoid_: backup, auto-commit

**Sunday message**:
The one message the coach sends at check-in about the week just
trained: it states what the log shows and numbers what it cannot
(sessions, coach-led content, runs, sleep, niggles, food — nutrition
readings, habits and next week's food exceptions — and anything
different next week), for the athlete to answer in
one reply. Replaces an interview.
_Avoid_: check-in form, intake, questionnaire

**Catch-up check-in**:
The check-in after more than 10 days without one. Its Sunday message
drops the per-session questions for one summary row per week of the gap,
three questions (the gap, now, next week) and the proposed return week,
which one "ok" accepts and writes. It never runs deep: a deep review that
was due moves to the next check-in.
_Avoid_: long check-in, gap review

**Return brief**:
The coach's brief for the week back after a gap (illness, travel, no
kit or a plain layoff): the gap in one sentence, what the return week
changes, each session's lines, what happens after, and the write line.
After illness it adds the safety lines of the illness rule.
_Avoid_: comeback plan, return plan

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

**Period mean**:
A wellness record entered by hand for a span, such as "about 6.5 h a
night over the last two weeks". It stays self-report and keeps its
original span. When whole, it counts toward the sleep gate's average;
it never counts as individual nights, so it cannot show short nights.
_Avoid_: weekly average (ambiguous with a computed average), sleep estimate

**Planned activity**:
A dated, planned bout of non-lifting training from a run plan, the coach
or the athlete. Its record says whether it is intervals, tempo,
threshold, hills or a race.
_Avoid_: planned session (a session is a program template), planned run

**Quality activity**:
An activity hard enough to count against the weekly quality cap and to
need an easy day either side: any conditioning; otherwise a session RPE
of 7 or more when the athlete gave one; otherwise what its matched
planned activity says; otherwise a name saying intervals, tempo,
threshold, hills, fartlek, track or race. The rule that decided is
reported with it.
_Avoid_: hard run, hard session, workout (reserved for logged lifting)

**Status day**:
A day the athlete was ill, injured or travelling, recorded as a dated
row that is withdrawn, never deleted, when wrong. An ill status day in
the gap before a session brings in the illness return rule, exactly as
an `ill` miss tag does; travel only explains the gap.
_Avoid_: sick day, day off (a rest day is not a status day), miss tag

**Cardio tier**:
Who owns the run plan: `count` (no plan; logged cardio is only counted),
`review` (an outside plan or the athlete's, reconciled against what was
logged) or `program` (the coach writes the planned activities). How much
the data says comes from the activity sources, not the tier.
_Avoid_: cardio mode, cardio level

**Interference rule**:
A program rule on spacing lifting and quality activities: lift first with
at least 6 hours before a same-day quality activity, and no quality
activity in the 24 hours before a heavy lower session. A broken rule
raises a `collision` flag; the coach and athlete decide what moves.
Easy activities never trigger one.
_Avoid_: conflict, spacing rule

**Heavy lower session**:
A lifting session with a compound squat or hinge exercise that has a
working set at RPE 7 or more, or of 6 reps or fewer when no RPE is set.
Coach-led sessions never count as one.
_Avoid_: leg day, heavy day

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
**reference mass** (current bodyweight, goal weight from rough/no-reading
cues, or fat-free mass when a credible body-fat reading exists). The
**target** is what the coach steers toward, the **stretch** an optional
higher aim, and the **floor** the minimum commitment now: recent intake plus a little, never under
1.2 g/kg of bodyweight or goal weight (~1.5 g/kg of fat-free mass) or
over the target. The floor rises after two consecutive
measured weekly averages at or over it since `floor_since`, and only
`/goals` lowers it. An app setting at or above the floor is compatible;
actual intake and app targets remain separate from that commitment.
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
sleep average under ~7 h means recomp at maintenance instead. Dated
hours asleep from the athlete or a tracker settle it once all 14 dates
are covered (`reference/nutrition-sleep.md`). With no hours source it is
recorded as `pending measurement` (short sleep reported, recomp by
default) or `not evaluated`; `/check-in` re-checks it during a deficit
once hours exist.
_Avoid_: sleep check, sleep rule, recovery gate
