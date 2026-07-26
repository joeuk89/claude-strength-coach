# Weekly programming pass (`/program-week`) — design

**Date:** 2026-07-26
**Status:** approved in discussion; ready for implementation planning

## Problem

The check-in reviews the week but leaves the prescriptions in Hevy static.
It notices progression signals ("top of rep range, due a load increase")
but never writes the new target anywhere the athlete sees mid-session.
Notes in Hevy (RPE + one cue) are written only when a routine is created
or edited, never refreshed. The result: the review produces observations,
not coaching, and the program doesn't visibly evolve as the athlete gets
stronger.

## Goal

After each check-in, the coach systematically programs the coming week —
per session, per exercise: working load, rep target, RPE, a weekly focus
note, and standing form cues — and writes it to Hevy so the athlete opens
the app and sees exactly what the coach wants, as if the coach were there.
Routines stay true to the plan in `routine/`, but the coach has license to
tune weekly and to propose structural upgrades that keep the program
evolving toward the athlete's goals.

## The three-speed model

| Speed | What changes | Where it lands |
| --- | --- | --- |
| **Weekly** | Loads, rep targets, RPE, focus notes, cue emphasis | Check-in record ("week ahead" overlay) + Hevy |
| **Within-block** | Swaps, adds, set counts, execution changes (e.g. grip width) | `routine/*.md` first, then Hevy |
| **Block boundary** | Full redesign | `/new-program`, fed by the deep check-in |

`routine/*.md` never carries weekly numbers — it stays the block-level
plan. The newest check-in's "week ahead" section is the **weekly
overlay**: the written record of what was prescribed, and what the next
check-in judges adherence against.

## 1. New skill: `/program-week`

**Purpose:** turn the plan + the latest review into concrete, coach-set
prescriptions in Hevy for the coming week.

**Flow:**

1. **Read context** — `profile.md`, `routine/program.md` + session files,
   the newest check-in (decisions and window), `routine/hevy-map.json`,
   and recent Hevy logs for current working weights. Confirm rotation
   position if the program rotates — never assume.
2. **Stand down if a one-off week is active** (override pointer in
   `routine/program.md`) — `/one-off-week` owns those writes; say so and
   stop.
3. **Compute the week — per session, per exercise:**
   - **Load** — from the log and the program's progression rules (top of
     rep range at target RPE → add load; missed reps → hold; RPE drifting
     up → hold or back off). Coach reasons per lift; no blind formula.
   - **Rep target / RPE** — where the block calls for movement.
   - **Focus** — one per-exercise emphasis where warranted, drawn from
     check-in findings.
   - **Structural changes** — swaps/adds agreed at check-in, or proposed
     now. Marked as plan changes, presented separately.
4. **Present the whole week compactly** — one table per session:
   exercise, sets × reps @ load @ RPE, what changed vs. last week,
   one-line rationale where not obvious. Structural changes flagged in
   their own short section. **One approval for the whole week**
   (option A).
5. **Write:** structural changes → edit `routine/*.md` first. Then Hevy:
   GET each mapped routine, update sets (`weight_kg`, `rep_range`) and
   notes, PUT with a few seconds' spacing (rate limit), GET back to
   verify. Loads convert from the athlete's units to kg.
6. **Record:** full per-exercise prescription into the newest check-in's
   "week ahead" section. Mid-week standalone runs append a dated
   "Week reprogrammed" addendum instead (same pattern as one-off-week's
   override addendum).

**Mid-week mode:** invoked standalone, it reprograms only the remaining
days and first asks what prompted it (missed session, easy/hard day,
schedule change).

**No Hevy:** same computation; the prescription in the check-in record is
the deliverable.

## 2. Note format (standard, documented in `reference/hevy-api.md`)

```
Target: 3×8 @ RPE 8 — add 2.5 kg from last week
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

- **Target** — always. This week's sets × reps @ RPE plus the load
  instruction.
- **Focus** — only when there is one.
- **Cues** — always; the standing form reminders.
- Hard cap: three lines. A note nobody reads between sets is wasted.

## 3. Session files: canonical `Cues:` line per exercise

`routine/*.md` gains a `Cues:` line under each exercise — the single
source of truth for how each lift is performed. `/new-program` writes
them for new programs; `/program-week` offers a one-time backfill on its
first run for existing athletes. An execution change (wide → narrow
grip) edits this line — that's what makes it a plan change rather than a
weekly tweak.

## 4. Ripple changes to existing skills

- **`/check-in`** — after decisions are agreed, invoke `/program-week`
  (deload weeks keep invoking `/one-off-week` instead). The adherence
  analysis judges against last week's *programmed* targets — "did you
  hit 82.5 × 8" rather than "roughly the plan" — via the weekly overlay
  in the previous record.
- **`/hevy-sync`** — diffs Hevy against **base plan + newest weekly
  overlay**, so coach-set weekly targets stop reading as drift. Working
  loads stay exempt (the next pass recomputes them). Notes matching the
  standard three-line format aren't drift.
- **`/one-off-week`** — unchanged, except temp-session notes adopt the
  three-line format.
- **CLAUDE.md / README** — document the new command; describe the
  weekly overlay in the weekly rhythm and file tables.

## 5. Out of scope

- No per-session prep command — the weekly pass covers it; mid-week mode
  handles exceptions.
- No load-progression automation beyond the program's stated rules.
- `routine/*.md` never carries weekly numbers.
- No changes to logging/tracking — Hevy remains the logbook.

## Decisions made in discussion

- Coach sets actual working loads (`weight_kg`) in Hevy, with the RPE
  note as the autoregulation escape hatch.
- Approval: one compact approval for the whole week (option A), not
  per-session, not autonomous.
- Standalone skill invoked by `/check-in` (option 1), enabling mid-week
  reprogramming without a full check-in.
