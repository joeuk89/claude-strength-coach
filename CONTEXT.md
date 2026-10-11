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
(sessions, coach-led content, runs, sleep, niggles, nutrition readings,
meal plan, anything different next week), for the athlete to answer in
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

**Activity source**:
Where logged cardio and health signals come from: a phone health export,
a training-analysis service, a run-plan calendar feed, or the athlete by
hand. Every source is optional; manual entry is always available.
_Avoid_: integration (reserved for Hevy and the nutrition app), feed

**Activity**:
One logged bout of non-lifting training (a run, a ride, a conditioning
session) from any activity source.
_Avoid_: workout (reserved for logged lifting), cardio session

**Research note**:
A dated, cited answer to one coaching question, with a confidence and a
review-by date, that the coach consults before deciding in that area.
_Avoid_: reference, evidence doc, wiki page

**Recipe bank**:
The athlete's set of approved recipe cards in `nutrition/menu/`, plus
its index — what `/meal-plan` selects from.
_Avoid_: food bank, menu (ambiguous with the directory name)
