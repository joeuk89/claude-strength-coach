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

**Schedule rule**:
The named rule that decides which session lands on which day: fixed
weekdays, alternating templates anchored to an external session,
next-in-sequence, or an explicit calendar.
_Avoid_: rotation (one kind of schedule rule), split

**Coach's brief**:
The narrative presentation of a proposed training week, given to the
athlete for approval before anything is written: week focus, what's
changing and why, then per-session tables.
_Avoid_: summary, proposal, plan preview

**Brief** (this week's brief):
The standing one-page statement of the current week: focus, sessions,
what changed, what to watch, what to do if a day is missed. Rewritten
every programming pass; the thing the athlete reads during the week.
_Avoid_: dashboard, summary, this-week doc

**Sunday message**:
The athlete's single check-in reply covering the week just trained:
sessions done, runs, sleep, niggles, nutrition readings, and anything
different next week. Replaces an interview.
_Avoid_: check-in form, intake, questionnaire

**Approval gate**:
The rule that presenting proposed content (a coach's brief, a recipe
card) and writing it (to Hevy or repo files) never happen in the same
turn — the athlete must reply first.
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

**Pantry**:
What's actually in the house — perishables, partial packs, staple
states — recorded in `nutrition/pantry.md`. Distinct from the recipe
bank: the bank is what the athlete can make; the pantry is what they
have. Scheduled for removal (see `docs/roadmap/2026-10-11-system-review.md`, R-04).
_Avoid_: food bank, stock
