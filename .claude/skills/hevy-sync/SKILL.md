---
name: hevy-sync
description: Use when the athlete wants the program and their Hevy routines reconciled — detect discrepancies between the repo plan and the Hevy app in either direction, walk through each one, and resolve by updating the program data or pushing to Hevy. Triggers include "/hevy-sync", "sync hevy", "sync with hevy", "I changed something in the app", "push this to hevy", "are hevy and the plan in sync?".
---

# Hevy ↔ repo routine sync

The program (`data/program.json`, rendered to `routine/`) is the plan,
and the overlay in force is this week's prescription of it; the
athlete's Hevy routines are what they actually train from. Either side
can drift — the athlete edits in the app mid-session, or we rework the
plan here. This skill finds the differences and resolves each one **with
the athlete, one at a time**. Never bulk-resolve.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

Requires Hevy turned on in `config.toml` and a key: `python3 -m coach
hevy status` shows `key: present`. If not, say so and stop (offer
`/setup` to add it).

**Loads come from `coach` output; quote them.** Any load shown to the
athlete comes from a command (`units convert`, `units format`, the
`routines diff` summary), never from arithmetic by hand.

## 1. Fetch and map

- Run `python3 -m coach hevy pull`, which refreshes the cached
  routines, folders and workouts.
- `python3 -m coach state show` holds the map: `hevy.routines` maps each
  routine id to a program session. IDs are the join key; titles are just
  labels. Compare it with the cached routines
  (`.coach/cache/hevy/routines.json`): a mapped id Hevy no longer has,
  a live routine in neither `hevy.routines` nor
  `hevy.temporary_routines`, or a program session with no routine
  means the map needs healing — resolve that with the athlete first
  (edit `hevy.routines` in `data/state.json`, then `state show` to check
  it), then diff. `python3 -m coach check --only dangling_routine_ids`
  names overlay sessions whose routine is gone.
- Routines in `hevy.temporary_routines` (the "One-off weeks" folder
  `/one-off-week` writes deload and disrupted-week sessions into) are
  disposable by design — exclude them from the diff entirely and never
  report them as drift.

## 2. Diff — structure, not loads

Run `python3 -m coach overlay current` for the overlay in force, then
`python3 -m coach routines diff --overlay <its id>`. It compares each
routine with what the overlay would write, change by change:

- **`structural` changes are the discrepancies**: exercises
  added/removed/substituted · order changes · superset groupings · set
  counts · reps and rep ranges · rest times.
- **`prescription` changes are not drift.** Loads and notes are
  rewritten by every programming pass; in-app load edits between passes
  are the athlete autoregulating. Only mention a load if it breaks a
  stated constraint in `profile.md` or `[caps]` — e.g. a barbell lift
  at/over an equipment load cap.

**One load exception: dumbbell convention errors.** A dumbbell load the
diff shows at almost exactly **2× or ½ ×** the overlay's Hevy value is
a convention error, not autoregulation, and it *is* worth raising: left
alone it corrupts the history that later e1RMs and progressions are
computed from. The diff summary prints both sides through the units
module (`22.5/hand (Hevy: 45) → 25/hand (Hevy: 50)`), so read it from
there. Single-arm and alternating work is the exception where per hand
and the Hevy value are the same number — check the load mode
(`library show <id>`) before calling it.

RPE targets live in the overlay and reach Hevy only through the notes
(routines can't store them) — never report their absence in Hevy as
drift.

No overlay in force → compare the cached routines with `program show`
by hand for structure only, and settle each difference the same way.

## 3. Resolve — one discrepancy at a time

For each difference, show both versions side by side and coach on it: was
the Hevy-side change a good call? Does it hurt weekly balance or the
session rotation? Then **stop and wait for the athlete's reply** — they
pick:

1. **Adopt Hevy** → edit the session in `data/program.json` to match,
   then run `python3 -m coach program validate` and `python3 -m coach
   program render`. The overlay in force still holds the old shape:
   the next programming pass carries the change into the week.
2. **Adopt the plan** → Hevy gets the plan's version in step 4, once
   every discrepancy is settled.
3. **Discuss / neither** — sometimes the right answer is a third option;
   design it together, apply it to `data/program.json` as in option 1,
   and let it reach Hevy through `/program-week` (step 4).

After any program edit, re-check the day before and after (the rotation
must stay clash-free) and the program's weekly balance.

## 4. Writing to Hevy

Hevy is written only through an approved overlay, and `routines push`
has no per-routine filter: it rewrites **every** routine in the
overlay's span that differs from the overlay. So write once, after
every discrepancy is settled.

- Run `python3 -m coach routines diff --overlay <id>` again and show
  the athlete every routine it lists with changes — that is exactly
  what a push writes, loads and notes included.
- Push the overlay in force only when `overlay current` shows it
  `approved` (its approval still holds) **and** every routine with a
  structural change in that diff is one the athlete chose to adopt from
  the plan. Then run `python3 -m coach routines push --overlay <id>`.
  The permission prompt shows exactly what it will write; it rewrites
  the whole routine, notes included, so nothing the overlay lacks
  survives — fold any Hevy note worth keeping into the program's
  `cues` first. A push that exits 3 was refused by a guard: report its
  reason, never retry it by hand.
- If any discrepancy was resolved "adopt Hevy" or "neither", don't push
  the overlay in force: it still holds the old shape and would write it
  back over the routine the athlete kept. Send the plan-side changes
  through `/program-week` instead — its new overlay carries the adopted
  shape. Offer `/program-week` too when no approved overlay covers the
  span.
- New exercise in the plan? It needs a library entry with a Hevy
  template: `python3 -m coach library search <name>`, then `python3 -m
  coach library seed` after the next pull if the athlete added it in
  the app. If nothing matches, ask the athlete what the exercise is
  called in their app — it may be a custom one.
- After writing, `python3 -m coach routines verify --overlay <id>`
  confirms the change landed; quote it.
- Only when a command keeps failing and the athlete agrees, use
  `reference/hevy-api.md` → "Manual fallback".

## 5. Close out

Summarize what changed on each side. If anything was resolved by changing
the plan's intent (not just its transcription), note it for the next
check-in — append a line to the newest check-in file's Decisions section
or flag it to the athlete.
