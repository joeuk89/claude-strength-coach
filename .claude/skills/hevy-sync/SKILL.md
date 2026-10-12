---
name: hevy-sync
description: Use when the athlete wants the program and their Hevy routines reconciled — detect discrepancies between the repo plan and the Hevy app in either direction, walk through each one, and resolve by updating the program data or pushing to Hevy. Triggers include "/hevy-sync", "sync hevy", "sync with hevy", "I changed something in the app", "push this to hevy", "are hevy and the plan in sync?".
---

# Hevy ↔ repo routine sync

The program (`data/program.json`, rendered to `routine/`) is the plan,
the overlay in force is this week's prescription of it, and the Hevy
routines are what the athlete trains from. Either side can drift. Find
the differences and resolve each **with the athlete, one at a time**.
Never bulk-resolve.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

Requires Hevy on in `config.toml` and `python3 -m coach hevy status`
showing `key: present`; if not, say so and stop (offer `/setup`).

**Loads come from `coach` output; quote them**: `units convert`,
`units format` or the `routines diff` summary, never arithmetic by hand.

## 1. Fetch and map

- Run `python3 -m coach hevy pull`. `python3 -m coach state show` holds
  the map: `hevy.routines` maps each routine id (the join key; titles
  are labels) to a program session. Compare it with
  `.coach/cache/hevy/routines.json`: a mapped id Hevy no longer has, a
  live routine in neither `hevy.routines` nor `hevy.temporary_routines`,
  or a session with no routine means the map needs healing. Settle that
  with the athlete first (edit `hevy.routines` in `data/state.json`,
  then `state show` to check it), then diff. `python3 -m coach check
  --only dangling_routine_ids` names overlay sessions whose routine is
  gone.
- Routines in `hevy.temporary_routines` (the "One-off weeks" folder,
  where `/program-week` writes the temporary routines of its light and
  constrained modes) are disposable: leave them out of the diff, never
  drift.

## 2. Diff — structure, not loads

Run `python3 -m coach overlay current` for the overlay in force, then
`python3 -m coach routines diff --overlay <its id>`. It compares each
routine with what the overlay would write, change by change:

- **`structural` changes are the discrepancies**: exercises
  added/removed/substituted, order, superset groupings, set counts,
  reps and rep ranges, rest times.
- **`prescription` changes are not drift**: every pass rewrites loads
  and notes, and in-app load edits are the athlete autoregulating.
  Mention a load only if it breaks a constraint in `profile.md` or
  `[caps]`.
- **One load exception: dumbbell convention errors.** A dumbbell load
  the diff shows at almost exactly **2× or ½ ×** the overlay's Hevy
  value is a convention error, and left alone it corrupts the history
  later e1RMs and progressions come from: raise it. Read both sides
  from the diff summary (`22.5/hand (Hevy: 45) → 25/hand (Hevy: 50)`).
  Single-arm and alternating work carries the same number per hand and
  in Hevy, so check the load mode (`library show <id>`) first.
- RPE targets reach Hevy only through the notes: never drift.

No overlay in force → compare the cached routines with `program show`
for structure only.

## 3. Resolve — one discrepancy at a time

Show both versions side by side and coach on it (a good call? does it
hurt weekly balance or the rotation?), then **stop and wait for the
athlete's reply** — they pick:

1. **Adopt Hevy** → edit the session in `data/program.json` to match,
   then run `python3 -m coach program validate` and `python3 -m coach
   program render`. The overlay in force still holds the old shape: the
   next programming pass carries the change into the week.
2. **Adopt the plan** → Hevy gets the plan's version in step 4, once
   every discrepancy is settled.
3. **Neither** — design a third option together, apply it to
   `data/program.json` as in option 1, and let it reach Hevy through
   `/program-week`.

After any program edit, re-check the days either side and the weekly
balance.

## 4. Write to Hevy

`routines push` writes an approved overlay to **every** routine in its
span that differs, so write once, after every discrepancy is settled.

- Run `python3 -m coach routines diff --overlay <id>` again and show
  the athlete every routine it lists with changes: exactly what a push
  writes, loads and notes included.
- Push only when `overlay current` shows the overlay `approved` **and**
  every routine with a structural change in that diff is one the
  athlete chose to adopt from the plan. Then run `python3 -m coach
  routines push --overlay <id>`. It rewrites each whole routine, notes
  included, so fold any Hevy note worth keeping into the program's
  `cues` first. A push that exits 3 was refused by a guard: report its
  reason, never retry it by hand.
- Any "adopt Hevy" or "neither" → don't push the overlay in force (it
  would write the old shape back): send the change through
  `/program-week`, as when no approved overlay covers the span.
- A new exercise needs a library entry with a Hevy template: `python3
  -m coach library search <name>`, or `python3 -m coach library seed`
  after the next pull if it was added in the app. `routines preflight
  --overlay <id>` lists every unresolved template. No or ambiguous
  match: `library set-template <exercise-id> <id>` with an id from
  `.coach/cache/hevy/exercise_templates.json`; rebuild the overlay before approval.
- After writing, `python3 -m coach routines verify --overlay <id>`
  confirms the change landed; quote it.
- Only when a command keeps failing and the athlete agrees, use
  `reference/hevy-api.md` → "Manual fallback".

## 5. Close out

Summarize what changed on each side. A change to the plan's intent
(not just its transcription) goes in a line in the newest check-in's
Decisions section, for the next check-in.
