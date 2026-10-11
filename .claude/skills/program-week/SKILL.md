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
in the check-in history as the **overlay** — the effective
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
weights). Read each logged workout's `description` and per-exercise
`notes` too — the athlete's own account of how the sets felt ("target
too high, did back-off sets", "wiped out after yesterday's run") should
temper the next week's loads as much as the numbers do. If the program
rotates, confirm which week is next — never assume.

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

**Hevy freshness (Hevy users).** When `/check-in` invoked this skill,
reuse the routines its data pull fetched; otherwise GET every mapped
routine in the span. **The last pass** is the newest `**Written to
Hevy:**` line in `check-ins/` that names any of them (none yet → skip
both checks).

- **STALE** — a routine whose `updated_at` is before the last pass was
  not written by it, so the athlete would train from old notes. List
  each in the coach's brief as STALE with its last-written date (its
  `updated_at`).
- **Edited in the app** — compare each routine structurally with what
  the last pass wrote (its session in `routine/` with that pass's
  overlay applied): exercises, their order, set counts, rep ranges,
  rest. Any difference is an in-app edit made since the last pass.
  **Load-only edits are overwritten without comment** — the log already
  holds what was lifted, and this week's loads come from the log.
  **Structural edits** go in the coach's brief as keep-or-replace
  questions, settled by the same approval as the week.

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
5. **Hevy housekeeping** (only when there's something to say) — each
   STALE routine with its last-written date, and each structural in-app
   edit with your keep-or-replace recommendation ("You swapped leg
   press for hack squat in Lower A — keep it; I'll add it to
   `routine/lower-a.md`"). A kept edit is a structural change and lands
   in `routine/`; a replaced one is overwritten.
6. **The write line** — the brief's last line names exactly what "go"
   will write: each Hevy routine in the span by its Hevy title (every
   one, changed or not), then each `routine/` file with a structural
   change:

   `Reply "go" to train this and write: Upper A, Lower A, Upper B (Hevy) · routine/upper-a.md (structural change).`

   No structural change → drop the `routine/` part. Nothing going to
   Hevy (the athlete doesn't use it) → the line says so:
   `Reply "go" to train this and write: routine/upper-a.md (structural change). Nothing goes to Hevy (no Hevy).`
   or, with no structural change either,
   `Reply "go" to train this. Nothing goes to Hevy (no Hevy).`

Then **stop and wait for the athlete's reply. Never present and write
in the same turn** — the brief is a proposal, not a notification, and
that holds even on a hold-steady week. **"go" (or a clear yes) approves
the week and every write the line names** — don't ask again before
writing to Hevy. Anything else is a tweak: revise and present the brief
again, write line included. Iterate until they would train it.

## 4. Write

**Only enter this step after the athlete has replied "go" (or a clear
yes) to the brief above.** If no brief with a write line has been
presented and approved this session, go back to step 3. Write exactly
what the write line named — nothing more.

1. **Structural changes first** — edit the `routine/*.md` files the
   write line named (an execution change like grip width edits that
   exercise's `Cues:` line), then re-check the day before and after
   each edited session and the program's weekly balance.
2. **Then Hevy** (key in `.env`). Note the current time in UTC before
   the first write — that is this pass's timestamp. Write **every**
   mapped routine in the span, **including unchanged ones**: a routine
   left alone keeps last week's notes. For each, GET it, update its sets
   (`weight_kg` converted from the athlete's units, `rep_range`) and
   each exercise's `notes` in the standard format (see
   `reference/hevy-api.md`):
   - the **week line** on the first exercise: `Wk of <span start as D
     Mon>: <week focus>`, about 80 characters at most;
   - **Target** transcribed from the approved overlay — absolute
     sets × reps @ load @ RPE, never relative or narrative wording;
   - **Focus** where set, and **Cues** from `routine/`.

   Then PUT the whole routine back and GET to verify. Space writes a few
   seconds apart; back off ~30 s on a 429. **For dumbbell exercises
   `weight_kg` is the Hevy value** (the combined total — double the
   per-hand figure on two-arm work), and the `Target:` line states both
   numbers so the athlete enters the right one.
3. **Freshness check** — after the last write, GET every routine in the
   span again and confirm each `updated_at` is after this pass's
   timestamp. Name any that isn't in the close-out.

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

Whichever record holds the overlay, end it with one line stating when
this pass wrote to Hevy (the timestamp from step 4, ISO 8601 UTC) and
which routines it wrote — the next pass's STALE check reads it. No
Hevy writes → leave the line out.

```markdown
## Week reprogrammed — YYYY-MM-DD

**Span:** <start> → <end> · **Reason:** <missed session / …>

(Per-session prescription tables underneath.)

**Written to Hevy:** 2026-10-12T18:05:00Z · Upper A, Lower A, Upper B
```

## 6. Close out

Recap in plain words: what changed this week and why, what was written
to Hevy (and any routine the freshness check found not updated by this
pass), and the one thing to focus on. If a structural change landed,
note it for the next check-in's Decisions section.
