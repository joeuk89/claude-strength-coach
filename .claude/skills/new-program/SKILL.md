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
- **Every new program goes through a program draft.** Both paths end
  with a draft at `.coach/drafts/program.json` (schema
  `coach/schemas/program_draft.schema.json`: the complete program under
  `program`, plus `source`, `hevy_routines` and a `report`). Show the
  athlete the draft, then run `python3 -m coach program adopt --input
  .coach/drafts/program.json --dry-run` and, once they agree, the same
  without `--dry-run`. Adopt validates the draft (exit 1 names each
  problem by JSONPath), writes `data/program.json` and
  `data/state.json` (the current block carried over, or one started
  today for a first program; the rotation at `--position`
  or the schedule rule's first position, `hevy.routines` from the
  draft), renders `routine/program.md` and one page per session, and
  stages the files without committing. Never write a new
  `data/program.json` or `data/state.json` yourself.
- Adopt's output lists what still needs the athlete:
  - `unconfirmed` — exercises without a confirmed load mode: ask how
    each is performed, then `python3 -m coach library set-mode <id>
    <mode>` or `python3 -m coach library confirm <ids>`.
  - `avoided` — exercises the athlete avoids, with the reason. Adopt
    keeps them; propose a swap from `python3 -m coach library show <id>`
    (its `substitutes`) and agree it with the athlete.
  - `without_routine` — sessions with no Hevy routine yet (see Path B
    step 5).
- Later edits to `data/program.json` (a swap, a fix): edit it, then
  `python3 -m coach program validate` and `python3 -m coach program
  render`. The pages are rendered — never edit them by hand.
- A weekly balance picture (muscle group × sessions, including any
  coach-led sessions), shown in the walk-through so check-ins can audit
  it.

**Loads come from `coach` output; quote them.** `program import-hevy`
turns each Hevy value into the athlete's number with the confirmed load
mode and reports every conversion; the rendered pages print both
numbers for dumbbell work.

Requires `profile.md` and `config.toml` — if missing, run `/setup`
first.

## Redesigns: adopt with `--replace`

If `data/program.json` exists, this is a redesign. `program adopt`
refuses (exit 3) until you add `--replace`, with the athlete's
approval: it then archives the current `data/program.json` and
`data/state.json` under `data/archive/programs/<today>/`, keeps the
progression state of every exercise whose session, exercise and scheme
are unchanged, and removes the pages of sessions the new program drops.
Carry forward what the last block taught (check the latest deep
check-in).

Under 80 % adherence (as `/check-in` step 4 defines it), the redesign
adds no new recurring session — no new session or weekly slot,
conditioning and optional ones included — and you push back if the
athlete asks for one; exercise swaps are fine. A redesign the adherence
trigger started builds the smaller schedule the check-in agreed.

## Path A — Import (they already have a program)

For athletes arriving with routines in Hevy (or on paper).

1. **Fetch:** run `python3 -m coach hevy pull` — or take the paper
   plan, and write the draft as in Path B.
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
4. **Import:** run `python3 -m coach program import-hevy` (`--routine
   <id>` for each active routine, or `--folder <id>`). It writes the
   draft with one session per routine, mirroring the athlete's *actual*
   structure (don't reshape it during import): set groups, rest,
   supersets, a start load from each routine's top working set, cues
   from the exercise notes, and `hevy_routines` mapping each routine to
   its session. It exits 1 naming any exercise still without a
   confirmed load mode; settle it as in step 3 and run it again.
5. **Show the draft's report as one table** (kind, session, exercise,
   message): every converted load (check each dumbbell number against
   the athlete's actual dumbbells), working sets at mixed loads, cues
   taken from notes, and the missing schedule. When
   `detected.percentage_based` is true, show its evidence too.
6. **Finish the draft with the athlete:** the schedule rule and its
   days (adopt refuses an empty schedule), coach-led sessions, the
   light-week policy, and a progression scheme per exercise. Import sets
   every scheme to `hold`; a percentage-based program's
   `suggested_schemes` are a starting point for that conversation, never
   applied for you. Agree `cues` per exercise as you go.
7. **Adopt:** run `python3 -m coach program adopt --input
   .coach/drafts/program.json --dry-run`, then without `--dry-run`, as
   the output contract sets out.
8. **Review with a coaching eye:** now assess it — weekly balance gaps,
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
   then write the draft to `.coach/drafts/program.json` and adopt it as
   the output contract sets out. The schema lists every key; set these
   as follows:
   - `source` `design`, `hevy_folder` null (adopt then keeps the
     current program folder), `report` `[]`, and `detected`
     `{"percentage_based": false, "evidence": [], "suggested_schemes": []}`.
   - `hevy_routines` `{}` for a first program. For a redesign, adopt
     builds `hevy.routines` only from the draft, so carry the mapping
     over: take each `hevy.routines` entry from `python3 -m coach state
     show` whose `session_id` the new program keeps, and write it as
     `"<routine id>": "<session id>"`. Leave sessions that are new out;
     step 5 gives them routines. A kept session left out gets a second
     routine and its old one goes stale.
5. **Hevy:** adopt lists the sessions without a routine in
   `without_routine`; the opening week's programming pass creates them.
   `/program-week` names each new routine in its write line, and after
   the athlete's "go" runs `python3 -m coach routines create --overlay
   <id>` behind the approval gate, which makes each routine in the
   program folder and records its id in `data/state.json`. Without Hevy
   (`[hevy] enabled = false`) skip this step.

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
- Adopt staged the new `data/` files and rendered `routine/` pages;
  offer to commit them after the athlete approves.
