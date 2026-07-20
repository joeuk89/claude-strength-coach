---
name: new-program
description: Use when the athlete needs a training program created or replaced — first-time program setup, importing existing Hevy routines into the repo, or a block-boundary redesign. Triggers include "/new-program", "design me a program", "import my routines", "let's redesign my training", or /setup reaching its program step.
---

# Program creation & redesign

Produce the athlete's training program in `routine/`. **Structure is the
athlete's, not the template's** — a single weekly template, alternating
A/B weeks, PPL, upper/lower, a 3-week rotation: whatever the design
conversation lands on. Never assume a shape.

**Output contract (both paths):**
- `routine/program.md` — the program's shared rules (warm-up, RPE scale,
  progression scheme, deload policy), an **index of every session file**,
  how the sessions rotate across the calendar, and — if the program
  rotates — a "currently in …" line check-ins can update.
- Session files in `routine/` — every session concrete enough to train
  directly: exercises, sets × reps, RPE/intensity, rest, starting-load
  guidance.
- A weekly balance picture in `program.md` (muscle group × sessions,
  including any coach-led sessions), so check-ins can audit it.
- For Hevy users: `routine/hevy-map.json` mapping routine IDs → file +
  heading (see the format in `reference/hevy-api.md`).

Requires `profile.md` — if missing, run `/setup` first.

## Redesigns: archive first

If `routine/` already has a program, this is a redesign. Before writing
anything, move the current program files to `routine/archive/YYYY-MM-DD/`
(with the athlete's approval) so history survives. Carry forward what the
last block taught (check the latest deep check-in).

## Path A — Import (they already have a program)

For athletes arriving with routines in Hevy (or on paper).

1. **Fetch:** page through `GET /v1/routines` (`pageSize=10`) — or take
   the paper plan. List what's there.
2. **Interview:** which routines are active? How do they rotate across a
   week (or longer cycle)? Any coach-/PT-led sessions alongside them?
   Rest days? What progression rule do they follow, if any?
3. **Write:** `routine/program.md` + one section or file per session,
   mirroring the athlete's *actual* structure (don't reshape it during
   import). Build `hevy-map.json` from the fetched routine IDs.
4. **Review with a coaching eye:** now assess it — weekly balance gaps,
   missing progression scheme, junk volume, recovery clashes between
   adjacent days. **Propose improvements; don't force them.** Small fixes
   can land now (with approval); big ones can wait for a `/check-in` or a
   redesign.

## Path B — Design (from scratch)

A full coaching conversation, grounded in `profile.md` (goal, experience,
equipment, training week, time per session, injuries, recovery, cardio).

1. **Confirm the constraints** from the profile; ask only what's missing.
2. **Propose 2–3 structure options** that fit the constraints, with
   trade-offs (e.g. for 4 days: upper/lower vs. full-body vs. PPL+1).
   Recommend one and say why. Research current best practice where the
   choice depends on evidence; cite sources.
3. **Draft the program:** `program.md` rules first (progression scheme —
   double progression is a sensible default; RPE targets; deload policy —
   every 4–8 weeks or triggered early; warm-up protocol), then each
   session. Respect every profile constraint (equipment load caps, session
   time limits, recovery windows around coach-led sessions and cardio).
4. **Walk the athlete through it** — the reasoning, not just the tables.
   Iterate until they'd actually train it. Confirm before writing files.
5. **Offer Hevy:** for Hevy users, offer to push the program to Hevy
   (create routines via `POST /v1/routines`, notes field filled with RPE +
   key cue per exercise — see `reference/hevy-api.md`), then build
   `hevy-map.json` from the returned IDs. Confirm before writing to the
   app.

## Close out

- Recap the program in one paragraph: structure, rotation, progression,
  deload.
- Point at the rhythm: train it, log it, `/check-in` weekly — the first
  check-in after a new program pays extra attention to whether the
  starting loads and volume landed right.
- Offer to commit the new `routine/` files after the athlete approves.
