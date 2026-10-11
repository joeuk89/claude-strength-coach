---
name: new-program
description: Use when the athlete needs a training program created or replaced — first-time program setup, importing existing Hevy routines into the repo, or a block-boundary redesign. Triggers include "/new-program", "design me a program", "import my routines", "let's redesign my training", or /setup reaching its program step.
---

# Program creation & redesign

Produce the athlete's training program as `data/program.json`. **Structure
is the athlete's, not the template's** — a single weekly template,
alternating A/B weeks, PPL, upper/lower, a 3-week rotation: whatever the
design conversation lands on. Never assume a shape. Requires `profile.md`
and `config.toml` — if missing, run `/setup` first.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

**Loads come from `coach` output; quote them.** `program import-hevy`
turns each Hevy value into the athlete's number with the confirmed load
mode and reports every conversion; the rendered pages print both
numbers for dumbbell work.

## 1. Offer the three paths

Unless the athlete has already picked one ("import my routines", a
redesign), offer the three paths in one message and recommend one from
`profile.md` and `config.toml`, saying why in a line:

- **Path A — Import:** they already run a program in Hevy (or on paper)
  and want to keep it. Follow [import.md](import.md).
- **Path B — Design:** the week or goal needs a program built for it,
  such as coach-led sessions to plan around, a sport, or unusual kit or
  limits; and every redesign. Follow [design.md](design.md).
- **Path C — Starter:** no program of their own, and a week a starter
  fits. `python3 -m coach starters list --days <n>` names the one that
  suits `[athlete] experience` as `recommended_id`. Follow
  [starter.md](starter.md).

## 2. The output (every path)

- `data/program.json` (schema `coach/schemas/program.schema.json`):
  every session concrete enough to train directly — exercises by
  exercise library id with their load mode, set groups (sets × reps,
  RPE), rest, a start load per exercise in the athlete's units (per hand
  for dumbbell work), a progression scheme and `cues` per exercise (the
  canonical form cues; changing execution later, e.g. grip width, edits
  this field first). Plus the schedule rule, coach-led sessions as
  `external_sessions`, the light-week policy in `blocks` (a hard-week
  ceiling within the allowed range and a deload rule) and any missed-day
  rules.
- **Every path ends in a program draft** at `.coach/drafts/program.json`
  (schema `coach/schemas/program_draft.schema.json`, v2: the program under
  `program`, plus `source`, `hevy_routines` and a `report`). Show the
  athlete the draft. On resume with a v1 draft, update only its top-level
  `schema_version` to 2; preserve its source, program and report. Run
  `python3 -m coach program adopt --input
  .coach/drafts/program.json --dry-run` and, once they agree, the same
  without `--dry-run`. Adopt validates the draft (exit 1 names each
  problem by JSONPath), writes `data/program.json` and `data/state.json`
  (the current block carried over, or one started today; the rotation at
  `--position` or the schedule rule's first position; `hevy.routines`
  from the draft), renders `routine/program.md` and one page per
  session, and stages the files without committing. Never write a new
  `data/program.json` or `data/state.json` yourself.
- Adopt's output lists what still needs the athlete:
  - `unconfirmed` — exercises without a confirmed load mode: ask how
    each is performed, then `python3 -m coach library set-mode <id>
    <mode>` or `python3 -m coach library confirm <ids>`.
  - `avoided` — exercises the athlete avoids, with the reason. Adopt
    keeps them; propose a swap from `python3 -m coach library show <id>`
    (its `substitutes`) and agree it with the athlete.
  - `without_routine` — sessions with no Hevy routine yet; the opening
    week's programming pass creates them (design.md step 5).
- Later edits to `data/program.json` (a swap, a fix): edit it, then
  `python3 -m coach program validate` and `python3 -m coach program
  render`. The pages are rendered — never edit them by hand.
- A weekly balance picture (muscle group × sessions, coach-led ones
  included), shown in the walk-through so check-ins can audit it.

## 3. Redesigns: adopt with `--replace`

If `data/program.json` exists, this is a redesign (Path B). `program
adopt` refuses (exit 3) until you add `--replace`, with the athlete's
approval: it then archives the current `data/program.json` and
`data/state.json` under `data/archive/programs/<today>/`, keeps the
progression state of every exercise whose session, exercise and scheme
are unchanged, and removes the pages of sessions the new program drops.
Carry forward what the last block taught (the latest deep check-in).

Under 80 % adherence (as `/check-in` step 4 defines it), the redesign
adds no new recurring session — no new session or weekly slot,
conditioning and optional ones included — and you push back if the
athlete asks for one; exercise swaps are fine. A redesign the adherence
trigger started builds the smaller schedule the check-in agreed.

**Run mode.** With `mode = "run"` in `config.toml`'s `[coaching]`
table, the athlete wants their own program run as written. Import it and
finish the draft as Path A says, mapping their own progression rule to a
scheme, but in its review step propose no improvements: mention balance
gaps or recovery clashes as information only. Never offer a redesign;
build one only when the athlete asks for it.

## 4. Close out

- Recap the program in one paragraph: structure, rotation, progression,
  deload.
- **Offer to program the opening week**, on every path: invoke the
  **program-week** skill (`/program-week`) to set concrete starting
  loads, rep targets, RPE and notes for week one. It writes the first
  check-in record to hold the overlay, so the first `/check-in` has a
  prescription to judge against.
- Point at the rhythm: train it, log it, `/check-in` weekly — the first
  check-in after a new program pays extra attention to whether the
  starting loads and volume landed right.
- Adopt staged the new `data/` files and rendered `routine/` pages;
  offer to commit them after the athlete approves.
