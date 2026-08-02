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
  **Dumbbell exercises carry two numbers** — per hand and the Hevy value
  (`25/hand (Hevy: 50)`) — because Hevy stores the combined total across
  both arms. Get the per-hand figure out of the logged value *before*
  applying a progression rule, or the increment lands on the wrong
  number. Rules and the two-arm/single-implement split:
  `reference/hevy-api.md` → "Dumbbell loads". If the log shows an exact
  2× jump at unchanged reps and RPE, that's a convention slip, not
  progress — don't progress off it, raise it with the athlete.
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

## 3. Present the coach's brief — and stop

Talk the athlete through the week the way a coach would: narrative
first, tables second.

1. **Week focus** — 1–2 sentences: what this week is doing and why,
   tied to the current phase and goal.
2. **What's changing** — plain-word bullets, changes only, each with
   its reason ("Squat 80 → 82.5 kg — you hit 5×5 @ RPE 7.5 last week,
   room to move"). Never restate every exercise here. If nothing
   changes, say so and why — that's still a decision worth explaining.
3. **Per-session tables** — one per session: exercise · sets × reps @
   load @ RPE · what changed vs. last week. A one-line session focus
   above a table only where there's something to say — most sessions
   most weeks won't have one. Dumbbell loads show both numbers
   (`25/hand (Hevy: 50)`) — never a bare one, here or in the recorded
   overlay.
4. **Structural changes** (if any) — their own short section with
   before/after and trade-offs.
5. End with an open question ("Happy to train this, or want anything
   tweaked?"). Don't mention Hevy yet.

Then **stop and wait for the athlete's reply. Never present and write
in the same turn** — the brief is a proposal, not a notification, and
that holds even on a hold-steady week. Tweaks loop back into a revised
brief presented the same way. The athlete approves the week **once**;
iterate until they would train it.

## 4. Write

**Only enter this step after the athlete has approved the brief
above.** "OK to write to Hevy?" is not a substitute for presenting the
week — if no brief has been presented and approved this session, go
back to step 3.

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
   **For dumbbell exercises `weight_kg` is the Hevy value** (the
   combined total — double the per-hand figure on two-arm work), and the
   `Target:` line states both numbers so the athlete enters the right
   one.

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
