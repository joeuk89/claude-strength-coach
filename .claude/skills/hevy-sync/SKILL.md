---
name: hevy-sync
description: Use when the athlete wants the routine/ plan and their Hevy routines reconciled — detect discrepancies between the repo plan and the Hevy app in either direction, walk through each one, and resolve by updating the markdown or pushing to Hevy. Triggers include "/hevy-sync", "sync hevy", "sync with hevy", "I changed something in the app", "push this to hevy", "are hevy and the plan in sync?".
---

# Hevy ↔ repo routine sync

The `routine/` files (session files, rules in `program.md`) are the plan;
the athlete's Hevy routines are what they actually train from. Either side
can drift — the athlete edits in the app mid-session, or we rework the
plan here. This skill finds the differences and resolves each one **with
the athlete, one at a time**. Never bulk-resolve.

Requires a Hevy API key in `.env` — if there isn't one, say so and stop
(offer `/setup` to add it). API details: `reference/hevy-api.md`.

## 1. Fetch and map

- Read **`routine/hevy-map.json`** — the routine-ID → plan-location
  mapping. IDs are the join key; titles are just labels. (If the file
  doesn't exist yet, `/new-program` builds it — offer that instead.)
- Page through `GET /v1/routines` (`pageSize=10`) and verify the map
  against the live list: a mapped ID that no longer exists, a live routine
  not in the map, or a moved/renamed routine means the map needs healing —
  resolve that with the athlete first (update `hevy-map.json` and its
  `fetched_at`), then diff.
- Anything in the map's `unmapped` list, or newly unmatchable, is a
  discrepancy in itself — raise it.
- Routines in the map's `temporary` section (the "One-off weeks"
  folder `/one-off-week` writes deload and disrupted-week sessions
  into) are disposable by design — exclude them from the diff entirely
  and never report them as drift.
- `updated_at` on each routine tells you which side likely moved since the
  last sync. The newest check-in or a previous sync note gives the
  baseline date if one exists.

## 2. Diff — structure, not loads

Compare per session, Hevy (kg → the athlete's units) vs. the markdown:

**Flag these:** exercises added/removed/substituted · order changes ·
superset groupings (`supersets_id`) · set counts · rep ranges
(`rep_range` vs. the markdown's `8–10`) · rest times · exercise notes
that contradict the plan's instructions.

**Don't flag working loads.** The markdown's starting loads are
estimates; Hevy carries the live weights, which drift upward by design as
the progression scheme does its job. Only mention a load if it breaks a
stated constraint in `profile.md` — e.g. a barbell lift at/over an
equipment load cap.

RPE targets exist only in the markdown (the API can't store them on
routines) — never report their absence in Hevy as drift.

## 3. Resolve — one discrepancy at a time

For each difference, show both versions side by side and coach on it: was
the Hevy-side change a good call? Does it hurt weekly balance or the
session rotation? Then let the athlete pick:

1. **Adopt Hevy** → edit the session file (and any affected notes, plus
   the program's balance picture in `routine/program.md`).
2. **Adopt the plan** → push to Hevy (step 4).
3. **Discuss / neither** — sometimes the right answer is a third option;
   design it together, then apply to both sides.

After any markdown edit, re-check the day before and after (the rotation
must stay clash-free) and the program's weekly balance.

## 4. Writing to Hevy

- **PUT `/v1/routines/{id}` replaces the whole routine** — GET it first,
  modify the JSON, PUT everything back. Build sets with `rep_range` for
  ranged prescriptions, `weight_kg` converted from the athlete's units.
- New exercise? Find its `exercise_template_id` via
  `GET /v1/exercise_templates?pageSize=100` (page through; match the Hevy
  title, e.g. "Bench Press (Barbell)"). If nothing matches, ask the
  athlete what the exercise is called in their app — it may be a custom
  one.
- **Always populate each exercise's `notes` field** when creating or
  updating a routine — the athlete reads these mid-session, so they carry
  what the app can't hold in structured fields. Compose from the markdown
  plan, in this order of priority: the RPE target, the progression cue if
  it deviates from the program's default scheme, and the one form or
  execution cue that matters most for that lift. Keep it to 1–2 short
  lines — a note nobody reads between sets is wasted. Don't blank an
  existing Hevy note that has content the plan lacks; fold it in or ask.
- **Confirm with the athlete before every PUT/POST** — writes overwrite
  what's in their app. After writing, GET the routine back and verify the
  change landed.

## 5. Close out

Summarize what changed on each side. If anything was resolved by changing
the plan's intent (not just its transcription), note it for the next
check-in — append a line to the newest check-in file's Decisions section
or flag it to the athlete.
