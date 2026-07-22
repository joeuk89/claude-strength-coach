---
name: one-off-week
description: Use when a week (or a few days) must deviate from the standing program — a deload week, travel, illness recovery, limited equipment, a compressed schedule — and the athlete needs a concrete plan for it. Triggers include "/one-off-week", "deload week", "plan my deload", "I'm traveling next week", "next week is disrupted", "plan me a fallback week", or /check-in hitting a deload week.
---

# One-off week

Plan a week (or short span) that deviates from the standing program,
**without touching the program**. `routine/` files are never edited and
live Hevy routines are never overwritten — the one-off content lives
alongside, and normal weeks resume from the untouched program.

Two tiers — pick with the athlete from what they describe:

- **Reshuffle** — the existing sessions still work; only the calendar
  changes (a coach session moved, a day dropped, two days swapped).
  Output: a schedule of existing sessions on new days. No Hevy writes.
- **Temp sessions** — the prescriptions themselves change: a
  **deload**, or a **constrained week** (travel kit, no equipment,
  time-starved, run-down). Output: fully specified sessions, written
  to Hevy (if used) in the standing "One-off weeks" folder.

Mixed spans are fine (two days reshuffled, two constrained) — the
record shows both.

Requires `profile.md` and `routine/program.md` — with no program
there's nothing to deviate from (`/new-program` first).

## 1. Read the context

`profile.md` (training week, equipment, time limits, recovery, Coach's
notes), `routine/program.md` and its session files, the newest
check-in, and `routine/hevy-map.json` if it exists. If the program
rotates, confirm where the athlete is in the rotation — never assume.

Establish: the **span** (default: one week), the **reason** (deload /
travel / …), what's **fixed** (coach-led sessions, cardio commitments,
rest days), and the **constraints** (equipment available, time per
session, recovery state).

## 2. Design the week

**Reshuffle tier** — reorder using the program's own rules: recovery
windows between adjacent sessions, no same-pattern back-to-back days,
weekly balance including coach-led sessions and cardio. Show
before/after, iterate until the athlete would train it.

**Deload** — apply the deload policy in `routine/program.md`. If the
program has none, propose a standard one (~2/3 the sets, ~10% off
loads, everything at ~RPE 6; bodyweight work cut by sets and stopped
further from failure, ladders resumed, not restarted) and offer to
record it in `program.md` for next time. Base loads on **current
working weights** — Hevy users: GET the mapped routines and read the
live `weight_kg`; otherwise ask. Keep the program's priority protocols
alive at reduced dose. Remind the athlete to tell any coach/PT it's a
deload week, and deload whatever the profile says moves with the
lifting (conditioning etc.).

**Constrained week** — a short design conversation (what kit, what
time, what state), then sessions that keep the program's priority work
alive at a maintainable dose. Maintenance, not progress: ~⅓–½ of
normal volume holds strength and muscle for a couple of weeks — don't
program PR attempts on hotel dumbbells. The failure mode to design
against is no plan at all: sporadic maximal improvised sessions.

Every temp session must be concrete enough to train directly:
exercises, sets × reps, load or RPE, rest.

## 3. Write to Hevy (temp tier, Hevy users)

- Find the standing **"One-off weeks"** folder in
  `GET /v1/routine_folders`. Absent → create it
  (`POST /v1/routine_folders`) and record its ID in `hevy-map.json`
  under `temporary`.
- **Reuse before create.** If `temporary.routines` lists IDs, `PUT`
  this week's sessions over them (retitle to this week's names — e.g.
  "Deload Mon — Lower"); create additional routines in the folder only
  if this week needs more than exist, and add the new IDs to the map.
  The API has no delete — reuse **is** the cleanup, and leftover
  content in the folder between one-off weeks is harmless.
- Fill each exercise's `notes` with the RPE target + key cue, as
  always. Space writes a few seconds apart (rate limit); confirm with
  the athlete before writing; GET back after to verify.
- Update `temporary` in `hevy-map.json` in the same operation as any
  folder/routine creation.

**No Hevy?** Skip this — the record below is the deliverable, and the
athlete trains the temp sessions from it.

## 4. Record it

- Append to the newest check-in record:

  ```markdown
  ## Week override — added YYYY-MM-DD

  **Span:** <start> → <end> · **Reason:** <deload / travel / …> ·
  **Tier:** reshuffle / temp sessions

  | Day | Session |
  | --- | --- |

  (Temp-session prescriptions in full underneath the table. End with:
  "Normal program resumes <date>.")
  ```

  If `/check-in` invoked this skill, put the same content in the new
  check-in's "The week ahead" section instead of an addendum.
- Update the one-off pointer in `routine/program.md`'s header — same
  style as any one-off note: what's different, where the full shape
  lives, when normal layout resumes. The next `/check-in` judges the
  week against this override and clears the pointer once normal weeks
  resume.
- If this was the program's **penciled deload**, agree the next pencil
  (per the program's deload cadence) and update that line in
  `program.md` too.

## 5. Close out

Recap in plain words: what the span looks like, what was written to
Hevy (if anything), when normal service resumes. If recovery drove
this, note that the next check-in wants to hear how the week actually
went.
