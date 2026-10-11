---
name: new-program
description: Use when the athlete needs a training program created or replaced — first-time program setup, importing existing Hevy routines into the repo, or a block-boundary redesign. Triggers include "/new-program", "design me a program", "import my routines", "let's redesign my training", or /setup reaching its program step.
---

# Program creation & redesign

Produce the athlete's training program as `data/program.json`. **Structure
is the athlete's, not the template's** — a single weekly template,
alternating A/B weeks, PPL, upper/lower, a 3-week rotation: whatever the
design conversation lands on. Never assume a shape.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

## Output contract (both paths)

- `data/program.json` (schema `coach/schemas/program.schema.json`) —
  every session concrete enough to train directly: exercises by
  exercise library id with their load mode, set groups (sets × reps,
  RPE), rest, a start load per exercise in the athlete's units (per hand
  for dumbbell work), a progression scheme per exercise, and `cues` per
  exercise — the canonical form cues, the single source of truth for
  how each lift is performed (changing execution later, e.g. grip
  width, edits this field first). Plus the schedule rule (how the
  sessions rotate across the calendar), coach-led sessions as
  `external_sessions`, the light-week policy in `blocks` (a hard-week
  ceiling within the allowed range and a deload rule) and any
  missed-day rules.
- `data/state.json` (schema `coach/schemas/state.schema.json`; its
  `schema_version` is the schema's const) — the rotation position if
  the program rotates, the block (`started`, `hard_weeks_completed` 0,
  `deload` not due), `one_off` null, an empty `scheme_state`, and for
  Hevy users `hevy.routines` mapping each routine id to its session.
- After every write: `python3 -m coach program validate`, `python3 -m
  coach state show` (it refuses an invalid state) and `python3 -m coach
  program render`, which renders `routine/program.md` and one page per
  session. Those pages are rendered — never edit them by hand.
- A weekly balance picture (muscle group × sessions, including any
  coach-led sessions), shown in the walk-through so check-ins can audit
  it.

**Loads come from `coach` output; quote them.** A load read from Hevy
is a Hevy value: `python3 -m coach units convert --mode <load mode>
--from-hevy-kg <value>` turns it into the athlete's number, and the
rendered pages print both numbers for dumbbell work.

Requires `profile.md` and `config.toml` — if missing, run `/setup`
first.

## Redesigns: archive first

If `data/program.json` exists, this is a redesign. Before writing
anything, copy the current `data/program.json` and `data/state.json` to
`data/archive/programs/YYYY-MM-DD/` (with the athlete's approval) so
history survives; `program render` removes pages for sessions the new
program drops. Carry forward what the last block taught (check the
latest deep check-in).

Under 80 % adherence (as `/check-in` step 4 defines it), the redesign
adds no new recurring session — no new session or weekly slot,
conditioning and optional ones included — and you push back if the
athlete asks for one; exercise swaps are fine. A redesign the adherence
trigger started builds the smaller schedule the check-in agreed.

## Path A — Import (they already have a program)

For athletes arriving with routines in Hevy (or on paper).

1. **Fetch:** run `python3 -m coach hevy pull` and list the cached
   routines (`.coach/cache/hevy/routines.json`) — or take the paper
   plan.
2. **Interview:** which routines are active? How do they rotate across a
   week (or longer cycle)? Any coach-/PT-led sessions alongside them?
   Rest days? What progression rule do they follow, if any?
3. **Load modes:** run `python3 -m coach library seed`. It matches
   every exercise in the routines to the exercise library and proposes
   how each is loaded. Put each `low`-confidence proposal and each
   `guessed` custom entry to the athlete — decide from how the lift is
   actually performed, not its name (an alternating curl is one
   implement) — and record the answers with `python3 -m coach library
   set-mode <id> <mode>`; confirm the rest with `python3 -m coach
   library confirm <ids>` (or `--all` once every one is right).
4. **Write:** `data/program.json` with one session per active routine,
   mirroring the athlete's *actual* structure (don't reshape it during
   import), and `data/state.json` with `hevy.routines` mapping each
   routine id to its session and `hevy.folders.program` set to the
   routines' folder id. Start loads are each routine's working-set Hevy
   values through `units convert` with the confirmed load mode; check
   each dumbbell result against the athlete's actual dumbbells before
   trusting it. Agree `cues` per exercise as you go — existing Hevy
   exercise notes are the starting point. Then validate and render as
   above.
5. **Review with a coaching eye:** now assess it — weekly balance gaps,
   missing progression scheme, junk volume, recovery clashes between
   adjacent days. **Propose improvements; don't force them.** Small fixes
   can land now (with approval); big ones can wait for a `/check-in` or a
   redesign.

## Path B — Design (from scratch)

A full coaching conversation, grounded in `profile.md` (goal, experience,
equipment, training week, time per session, injuries, recovery, cardio)
and `config.toml` (units, equipment and its increments).

1. **Confirm the constraints** from the profile; ask only what's missing.
2. **Propose 2–3 structure options** that fit the constraints, with
   trade-offs (e.g. for 4 days: upper/lower vs. full-body vs. PPL+1).
   Recommend one and say why. Where the choice depends on evidence,
   follow `CLAUDE.md` "Researching current best practice": read the notes
   for the area first, research and save a local note when none answers
   it, and cite claim ids.
3. **Draft the program:** the rules first (progression scheme — double
   progression is a sensible default; RPE targets; the light-week
   policy — a hard-week ceiling and the fatigue triggers from
   `CLAUDE.md` "Coaching principles", the ceiling set for this athlete
   within the allowed range; warm-up protocol), then each session, every
   exercise picked from the exercise library (`python3 -m coach library
   search <name>`). Respect every profile constraint (equipment load
   caps, session time limits, recovery windows around coach-led
   sessions and cardio).
4. **Walk the athlete through it** — the reasoning, not just the tables.
   Iterate until they'd actually train it. Confirm before writing files,
   then write `data/program.json` and `data/state.json` and validate
   and render them as above.
5. **Hevy:** the program's routines are created by the opening week's
   programming pass. `/program-week` names each new routine in its
   write line, and after the athlete's "go" runs `routines create`,
   which makes each routine in the program folder and records its id in
   `data/state.json`.

## Close out

- Recap the program in one paragraph: structure, rotation, progression,
  deload.
- **Offer to program the opening week** — invoke the **program-week**
  skill (`/program-week`) to set concrete starting loads, rep targets,
  RPE, and notes for week one. It writes the first check-in record to
  hold the overlay, so the first `/check-in` has a prescription
  to judge against. Applies to both paths — imported and designed
  programs.
- Point at the rhythm: train it, log it, `/check-in` weekly — the first
  check-in after a new program pays extra attention to whether the
  starting loads and volume landed right.
- Offer to commit the new `data/` files and rendered `routine/` pages
  after the athlete approves.
