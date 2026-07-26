---
name: program-week
description: Use when the coming week (or the rest of this week) needs programming — coach-set loads, rep targets, RPE, and per-exercise notes written to Hevy. Triggers include "/program-week", "program my week", "set my weights for this week", "bump my squat", "reprogram the rest of the week", /check-in finishing its decisions on a normal (non-deload) week, or /new-program finishing a first-time program (the opening week).
---

# Weekly programming pass

Turn the plan plus the latest review into concrete, coach-set
prescriptions for the coming week — per session, per exercise: working
load, rep target, RPE, a weekly focus where warranted, and the standing
form cues. Hevy users get it written into their routines so the app
shows exactly what the coach wants this week; everyone gets it recorded
in the check-in history as the **weekly overlay** — the effective
prescription the next check-in judges adherence against.

`routine/` stays the block-level plan — never write weekly numbers into
it. Structural changes (swaps, adds, set counts, execution changes) do
edit `routine/` — plan first, then Hevy.

Requires `profile.md` and `routine/program.md` — if missing, run
`/setup` / `/new-program` first.

## 1. Read the context

`profile.md` (units, constraints, niggle log, Coach's notes),
`routine/program.md` (progression scheme, RPE targets, rotation) and
its session files, the newest check-in (decisions, window, any overlay
already written), `routine/hevy-map.json`, and recent Hevy logs for
current working weights (`GET /v1/workouts`, newest first — API in
`reference/hevy-api.md`; no Hevy → ask the athlete for their current
weights). If the program rotates, confirm which week is next — never
assume.

**Brand-new program?** An empty `check-ins/` is normal — there's no
overlay or decisions to read. With no logged workouts yet, working
weights come from the starting loads agreed during program design (or
ask the athlete), not from logs.

**Stand down if a one-off week is active.** If `routine/program.md`'s
header carries a one-off/override pointer covering this span,
`/one-off-week` owns it — say so and stop.

**Mid-week?** Invoked standalone partway through a trained week, first
ask what prompted it (missed session, easy/hard day, schedule change),
then reprogram only the remaining days.

**First run: cue backfill.** If the session files have no `Cues:`
lines, offer a one-time backfill before programming: agree the
canonical form cues for each exercise with the athlete and add a
`Cues:` line under each exercise in `routine/*.md`.

## 2. Compute the week — per session, per exercise

Work through every session in the span, every exercise in each:

- **Load** — from the log and the program's progression rules: top of
  the rep range at or under target RPE → add load (the program's
  increment); reps missed → hold; logged RPE drifting over prescription
  → hold or back off. Reason per lift — a formula applied blindly is
  not coaching. Display in the athlete's units.
- **Rep target / RPE** — move them where the block's scheme calls for
  it.
- **Focus** — one per-exercise emphasis where warranted, drawn from
  check-in findings ("slow the eccentric", "depth fades when tired").
  Most exercises most weeks won't have one — that's fine.
- **Structural changes** — swaps or additions agreed at the check-in,
  or proposed now with rationale. These are plan changes: mark them
  separately, they land in `routine/` too.

Active niggles constrain everything: no added load on an aggravated
pattern.

## 3. Present — one approval for the whole week

One table per session: exercise · sets × reps @ load @ RPE · what
changed vs. last week · a one-line rationale where it isn't obvious.
Structural changes get their own short section with before/after and
trade-offs. The athlete approves the week **once**; iterate until they
would train it.

## 4. Write

1. **Structural changes first** — edit the affected `routine/*.md`
   files (an execution change like grip width edits that exercise's
   `Cues:` line), then re-check the day before and after each edited
   session and the program's weekly balance.
2. **Then Hevy** (key in `.env`): for each mapped routine in the span,
   GET it, update its sets (`weight_kg` converted from the athlete's
   units, `rep_range`) and each exercise's `notes` in the standard
   three-line format — Target / Focus / Cues, see
   `reference/hevy-api.md` — then PUT the whole routine back and GET to
   verify. Space writes a few seconds apart; back off ~30 s on a 429.

**No Hevy?** Skip the writes — the recorded overlay below is the
deliverable, and the athlete trains from it.

## 5. Record the overlay

Write the full per-exercise prescription into the newest check-in's
"The week ahead" section — when `/check-in` invoked this skill, that
section is being written now; fill it. Standalone runs append to the
newest check-in instead:

**No check-in record yet** (brand-new program): create
`check-ins/YYYY-MM-DD.md` with a minimal first record — a header
noting the program start date and structure, then "The week ahead"
holding the overlay. The first `/check-in` judges adherence against
it.

```markdown
## Week reprogrammed — YYYY-MM-DD

**Span:** <start> → <end> · **Reason:** <missed session / …>

(Per-session prescription tables underneath.)
```

If `notion-map.json` exists and covers check-ins, mirror the updated
record per `reference/notion-sync.md` — local file first, Notion after.

## 6. Close out

Recap in plain words: what changed this week and why, what was written
to Hevy, and the one thing to focus on. If a structural change landed,
note it for the next check-in's Decisions section.
