# Read the context

Every mode starts here.

Read `profile.md` (training week, equipment, time limits, constraints,
niggle log, Coach's notes), `python3 -m coach program show` (sessions,
set groups, progression schemes, start loads, cues, `minimum_week`,
`blocks.deload_rule`), `python3 -m coach state show` (rotation, block,
any one-off week), `routine/program.md` for the program at a glance,
the newest check-in (decisions, window, any overlay already rendered),
and `python3 -m coach overlay current` (the overlay in force today).

**A one-off week** (light, constrained or reshuffle mode): also settle
the **span** (default: one week), the **reason** (deload, travel, …),
what's **fixed** (coach-led sessions, cardio commitments, rest days)
and the **constraints** (kit, time per session, recovery state).

## Logged workouts

**Hevy users:** run `python3 -m coach hevy pull`, then `python3 -m coach
hevy status` for the cache's age and counts. When `/check-in` started
this pass, its pull is fresh: don't pull again. Read recent workouts
from the cache (`.coach/cache/hevy/workouts/`, newest first) for current
working weights, turning each logged Hevy value into the athlete's
number with `python3 -m coach units convert --mode <load mode>
--from-hevy-kg <value>` (the load mode from `python3 -m coach library
show <id>`).

**No Hevy:** run `python3 -m coach history sync`, then `python3 -m coach
log list --since <date>` for the workouts the athlete reported; each
set's `value` is already their number.

Read each workout's `description` (`notes` in the manual log) and each
exercise's `notes` too. The athlete's own account of how the sets felt
("target too high, did back-off sets", "wiped out after yesterday's
run") tempers next week's loads as much as the numbers do.

**Brand-new program?** An empty `check-ins/` is normal: there's no
overlay or decisions to read. With no logged workouts yet, working
weights come from the program's start loads (`program show`) or the
athlete, not from logs.

## Rotation position

If the program rotates, infer which week is next and state it for
confirmation: never ask it as its own question, and never assume it
silently. Sources, in order: the coach-led session's log,
`rotation.position` in `state show`, the newest check-in. When
`/check-in` started this pass, its Sunday message already stated the
position and the reply confirmed or corrected it: use that. Standalone,
state it in the brief's week focus ("Week B, going by Tuesday's PT log
— say if not"). If the sources disagree, state the first one and name
the disagreement.

## Days off

Count the days from the last lifting workout of any kind — solo, or
coach-led as the log, the newest check-in or the athlete says — to the
first session of the span. Do this on every run, standalone included;
with no workout logged yet, skip it. Over 10 days makes this a **return
week**: compute.md applies the return rule in `CLAUDE.md` "Coaching
principles", matching band and all. An `ill` miss tag or illness in the
gap adds that rule's illness conditions; standalone, ask whether
illness caused the gap.

## Hevy freshness (Hevy users)

With an overlay in force, run `python3 -m coach routines verify
--overlay <its id>` after the pull; no overlay yet, skip it. Each
routine it reports with `verified: false` carries its `changes`:

- **Edited in the app:** any change of class `structural` (exercises,
  their order, set counts, reps or rep ranges, rest, supersets) is an
  in-app edit made since that pass. Each goes in the coach's brief as a
  keep-or-replace question, settled by the same approval as the week.
- **Load-only edits:** `prescription` changes to set loads only are
  overwritten without comment: the log already holds what was lifted,
  and this week's loads come from the log.
- **STALE:** a `prescription` change to an exercise's notes means the
  routine doesn't carry the overlay in force, so the athlete would
  train from old notes. List each in the coach's brief (on a
  hold-steady week, its close-out) as STALE.

## First run: cue backfill

If the program's exercises have no `cues`, offer a one-time backfill
before programming: agree the canonical form cues for each exercise
with the athlete, write them into each exercise's `cues` in
`data/program.json`, then run `python3 -m coach program validate` and
`python3 -m coach program render`.
