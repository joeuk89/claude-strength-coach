# The weekly rhythm

A week with the coach, day by day, with the messages you will actually
see. Everything else in this guide hangs off this loop: train and log,
answer one message on Sunday, read the brief, say "go".

The examples are illustrative. They follow the real formats, but your
sessions, loads and dates will differ.

## Monday to Saturday: train and log

Open the Hevy routine for the day. The coach wrote this week's
prescription into it, with a note on every exercise:

```text
Wk of 12 Oct: heavier top sets, stop 1–2 reps short of failure
Target: 3×8 @ 25/hand (Hevy: 50) @ RPE 8
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

The week line sits on the first exercise only and carries the week's
focus. `Target:` is the absolute prescription: sets × reps, load, RPE.
Dumbbell targets always give both numbers, because you read this note
while entering the set. A calibration line reads `· choose the load`
instead of a number: pick a weight you could lift for those reps at
that RPE, then adjust after the first working set.

Log every set in Hevy, RPE included where you can. Log PT sessions and
classes too, or tell the coach about them on Sunday; unlogged sessions
skew the review. Runs come in through an activity source or your
Sunday reply.

Without Hevy you train from `this-week-sheets.md`, a table per session
with an empty Done column, and report each workout in chat
([Training without Hevy](training-without-hevy.md)).

On your phone, your repo's `README.md` is the dashboard and
`this-week.md` is the brief. The brief shows the whole week on one
page:

```markdown
**Week of 12 Oct** · Week B (confirmed) · Recomp · Check-in due Sun 18 Oct (weekly)

## Focus
Second week at these loads: own the top sets, stop 1–2 reps short.

## Sessions
| Day | Session | Tier | Key | Done |
|---|---|---|---|---|
| Mon 12 | Upper A | core | Bench Press 3×8 @ 25/hand (Hevy: 50) | ✔ |
| Tue 13 | Lower A | core | Back Squat 3×5 @ 100 kg | |
| Wed 14 | PT | coach-led | | |
| Thu 15 | Upper B | core | Overhead Press 4×6 @ 45 kg | |
| Sat 17 | Easy run | run | easy (planned), 40 min | |

## Changed
- Bench Press 22.5 → 25/hand (Hevy: 50): hit 3×10 at RPE 8.

## Watch
- Left knee (watching): squats capped at RPE 8.

## If you miss a day
- Lower A: fold the squat and RDL into Thu (program rule).
```

## Any day: say what changed

You never need a command for the small stuff. Tell the coach in plain
words and it picks the flow:

| You say | What happens |
|---|---|
| "I missed Tuesday" | The program's missed-day rule, if one covers it: fold some sets into a later session, shift the session, or skip it. With no rule, you choose a move to a free day, a reshuffle, or a drop. Either way the coach shows the rest of the week before writing it. |
| "Today felt heavy" / "bump my squat" | A mid-week change to the lines left this week. If the lift has no session left, it becomes a follow-up the next proposal raises. |
| "Travelling Tue–Fri, hotel dumbbells" | A constrained week: temporary sessions on the kit you name, priority lifts kept at a maintainable dose, the program untouched. Days you agree not to train at all are a planned break with nothing missed. |
| "My knee's sore on squats" | A niggle, logged with the movements it affects and a limit (an RPE cap, no added load) that every proposal respects until it eases. Pain that persists gets a professional recommended. |
| "Swap the leg press for hack squat" | A structural change: before and after, the effect on weekly balance, then an edit to the program and the week. |
| "I changed Lower A in the app" | `/hevy-sync`: the structural difference, side by side, and your choice to keep it or restore the plan. |
| "Why this rep range?" / "What should I eat post-workout?" | Coaching. No files change. |

Each of these ends the same way: the coach shows you what it will
write and waits for "go".

## Sunday: `/check-in`

Run `/check-in` (or "check in"). The coach runs the workspace checks,
reads your profile, program and the last record, pulls the Hevy log,
and sends **one message**. It states what the log shows and numbers
what it cannot see. You answer by number, in one reply.

```text
Check-in for 5–11 Oct (weekly: last deep review 3 weeks ago).

1. Sessions — Upper A Mon ✔, Lower A Tue ✔, Upper B Thu ✔, Lower B Sat:
   no workout logged. Tag the miss: time / sleep / ill / family /
   skipped / other. Anything trained but not logged?
2. Coach-led — PT Wed: nothing on file. What did it cover, how long,
   how hard (RPE), or did the trainer cancel? Next week lands on Week B
   of the rotation: confirm.
3. Sleep — hours asleep each night (diary or tracker), or the average
   with its dates and source, and how it felt?
4. Niggles — anything new? Open: left knee (watching): quiet, or still
   there?
5. Food — readings: trend weight · expenditure · targets (kcal/protein)
   · 7-day average (kcal/protein) · days logged. Anchors most days
   (y/n)? Anything in the plan that didn't work? Next week: who cooks
   which nights, office-day changes, meals out?
6. Next week — anything different: travel, schedule, kit, illness?
```

Fields that cannot apply are left out: no PT in the window, no Coach-led
field; no cardio in your week, no Runs field; nutrition off, Food becomes
one morning weigh-in. A fact the log already answers is stated for
confirmation, not asked. A reply like this is complete:

```text
1 time. 2 lower body, 50 min, RPE 7; Week B yes. 3 about 7 h, fine.
4 quiet. 5 78.4 · 2650 · 2300/160 · 2280/152 · 7 days; anchors yes;
nothing; Thursday out. 6 no.
```

The coach records the reply (miss tags, the PT session, status days,
events), asks at most one follow-up and only for a gap that blocks
programming, then reviews the week: sessions trained against planned,
each exercise against its prescription, e1RM changes, convention slips,
adherence over the trailing four ordinary weeks, the block's hard-week
count and the four fatigue triggers, your weight trend and protein. It
writes a dated record to `check-ins/2026-10-11.md`: the rendered week
review, then its own Coach's read, Decisions and The week ahead.

Every six weeks or so, or when a light week is newly proposed or
adherence drops, the same message runs **deep**: a few more questions
(body composition if your goal uses it), a block-level review of
balance and progress, every open follow-up settled, and what the next
block should change. After a gap of more than ten days it runs as a
**catch-up** instead: one summary row per week missed, a proposed return
week, and "ok" accepts the lot. See [Check-in](check-in.md).

## Sunday, part two: the brief and "go"

The check-in hands over to the programming pass. The coach runs the
proposal for next week, settles each flagged line, checks every
prescription against your kit, caps and days off, and presents the
coach's brief:

```text
Week of 12 Oct (normal). Focus: second week at these loads: own the
top sets, stop 1–2 reps short of failure.

What's changing
- Bench press 22.5 → 25/hand (Hevy: 50): you hit 3×10 at RPE 8.
- Back squat holds at 100 kg: Tuesday's top set was RPE 9, and the
  knee is still on watch (cap RPE 8).
- Lower B moves to Fri: you're out Thursday.

Upper A — Mon 12
| Exercise | Sets × reps | Load | RPE | vs last week |
|---|---|---|---|---|
| Bench press | 3×8–10 | 25/hand (Hevy: 50) | 8 | +2.5/hand |
| One-arm row | 3×10 | 30 | 8 | same |
...

Reply "go" to train this and write: Upper A, Lower A, Upper B, Lower B
(Hevy). Commit: data/state.json, data/history/annotations.json.
```

The tables are rendered by the scripts, never retyped, so a dumbbell
load always shows both numbers. The last line names every Hevy routine
"go" will write, any structural file, and the training records that will
be committed with the week.

Reply **"go"**, or say what to change ("keep squats at 3 sets", "move
Lower B to Saturday"): the coach revises and presents the brief again.
On "go" it approves the overlay, writes each routine, reads each one
back to verify, re-renders the brief, dashboard and progress page, and
commits and pushes them with the week's overlay and the check-in
record. Your phone shows next week within a minute. Nothing is written
before "go", and nothing is written that the line did not name.

On a week where nothing needs deciding, the check-in summary and the
brief collapse into three sentences and the same write line, with the
tables offered rather than shown. "go" still approves it.

## Sunday, part three: food (if you plan meals)

With a standing template set up, the Food field's "next week" answer is
the one line `/meal-plan` needs. Run it to get the week's meals from
your recipe bank, a day-by-day table with totals, the flags, a shopping
list by aisle, and one closing line naming what "go" writes. See
[Recipes and meal plans](recipes-and-meal-plans.md).

## What the coach sees when a session starts

Every Claude Code session in your workspace opens with a few status
lines from `python3 -m coach status`: the overlay in force and whether
it reached Hevy, failing checks, the age of the Hevy cache, the block's
count, the next check-in date and anything that needs raising first.
The coach raises those items before anything else, so starting a session
with "hi" is enough to be told what is due.

## When the rhythm breaks

- **A gap of 11 days or more** (holiday, illness, life): the next
  check-in is a catch-up with a return week sized to the days off, from
  a 5% load cut and one set fewer up to a full re-test after six weeks
  ([Blocks and light weeks](blocks-and-light-weeks.md)).
- **Illness**: no training until 48 hours symptom-free, and the first
  session back capped at RPE 7. Fever or chest symptoms mean checking
  with a professional first.
- **Adherence under 70 %** over the trailing four ordinary weeks: the
  check-in presents a smaller schedule with the same weekly hard sets
  per muscle. Under 80 %, no new recurring session is proposed.
- **A deload is due**: the block reached its ceiling, or two fatigue
  triggers fired. The coach proposes the light week; you agree or
  decline, and a decline is recorded and proposed again next week.
