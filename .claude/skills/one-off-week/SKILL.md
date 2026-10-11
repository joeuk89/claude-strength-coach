---
name: one-off-week
description: Use when a week (or a few days) must deviate from the standing program — a deload week, travel, illness recovery, limited equipment, a compressed schedule — and the athlete needs a concrete plan for it. Triggers include "/one-off-week", "deload week", "plan my deload", "I'm traveling next week", "next week is disrupted", "plan me a fallback week", or /check-in agreeing a light week.
---

# One-off week

Plan a week (or short span) that deviates from the standing program,
**without touching the program**. `data/program.json` and `routine/` are
never edited and the program's Hevy routines never carry a temp
session — the one-off content is its own overlay (kind `deload` or
`one_off`), its temp sessions live in temporary Hevy routines, and
normal weeks resume from the untouched program.

Two tiers — pick with the athlete from what they describe:

- **Reshuffle** — the existing sessions still work; only the calendar
  changes (a coach session moved, a day dropped, two days swapped).
  Output: the program's sessions on new days, each carrying the
  prescription it already has.
- **Temp sessions** — the prescriptions themselves change: a
  **deload**, or a **constrained week** (travel kit, no equipment,
  time-starved, run-down). Output: fully specified sessions, written
  to Hevy (if used) as temporary routines in the standing "One-off
  weeks" folder.

Mixed spans are fine (two days reshuffled, two constrained) — the
record shows both.

Requires `profile.md` and `data/program.json` — with no program there's
nothing to deviate from (`/new-program` first).

**Loads come from `coach` output; quote them.** Never convert kg and
lb, split a dumbbell total or round a load by hand: `units convert`,
`units format` and `units round` do it, and the overlay's rendered
tables are the only loads the brief shows.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

## 1. Read the context

`profile.md` (training week, equipment, time limits, recovery, Coach's
notes), `python3 -m coach program show`, `python3 -m coach state show`
(rotation, block, any earlier one-off week), the newest check-in, and
`python3 -m coach overlay current` (the overlay in force). Hevy users:
run `python3 -m coach hevy pull` (skip it when `/check-in` just pulled).
If the program rotates, confirm where the athlete is in the rotation —
never assume.

Establish: the **span** (default: one week), the **reason** (deload /
travel / …), what's **fixed** (coach-led sessions, cardio commitments,
rest days), and the **constraints** (equipment available, time per
session, recovery state).

## 2. Design the week

**Reshuffle tier** — reorder using the program's own rules: recovery
windows between adjacent sessions, no same-pattern back-to-back days,
weekly balance including coach-led sessions and cardio. Each moved
session keeps its lines from the overlay in force
(`data/overlays/<id>.json`), re-dated.

**Deload** — run `python3 -m coach propose week --kind deload --week
<label>`. It applies the program's deload rule (`blocks.deload_rule` in
`program show`) to every program session in the span; the standard rule
keeps two thirds of each line's working sets, takes 10 % off loads from
the current working weights and puts every set at RPE 6, with bodyweight
work cut by sets and taken further from failure. Its sessions are temp
sessions (`"temporary": true`, titled "Deload — <session title>") that
keep their program session ids. Review each line, change one with
`python3 -m coach propose override` and a reason, settle a flag with
`python3 -m coach propose resolve`, then run `python3 -m coach propose
finalize --proposal <id>`, which writes the overlay. Then go to step 3
with that id: its draft and `overlay build` items are already done, so
start at "Where it renders", then carry on from its validate item. Keep
the program's priority protocols alive at reduced dose (ladders resumed,
not restarted). Remind the athlete to tell any coach/PT it's a deload
week, and deload whatever the profile says moves with the lifting
(conditioning etc.).

**Illness** — a week back after illness follows the return rule in
`CLAUDE.md` "Coaching principles": its illness conditions (when
training may restart, the first session's cap, when the athlete checks
with a qualified professional first) and, after a long gap, its
matching band.

**Constrained week** — a short design conversation (what kit, what
time, what state), then sessions that keep the program's priority work
alive at a maintainable dose. Maintenance, not progress: ~⅓–½ of
normal volume holds strength and muscle for a couple of weeks — don't
program PR attempts on hotel dumbbells. The failure mode to design
against is no plan at all: sporadic maximal improvised sessions. Name
the place's kit as an `[equipment.locations.*]` table in `config.toml`
when it differs from home, so caps and loads use it.

Every temp session must be concrete enough to train directly:
exercises, sets × reps, load or RPE, rest. Unfamiliar dumbbells (a
hotel rack, a different increment) are exactly when a doubled entry
slips in unnoticed, so snap each load to the kit with `python3 -m coach
units round --value <load> --increment <step>` and let the renderer
print both numbers.

## 3. Build the overlay

1. **Where it renders.** When `/check-in` invoked this skill, its new
   record's "The week ahead" section takes it. Otherwise append to the
   newest check-in record:

   ```markdown
   ## Week override — added YYYY-MM-DD

   **Span:** <start> → <end> · **Reason:** <deload / travel / …> ·
   **Tier:** reshuffle / temp sessions

   | Day | Session |
   | --- | --- |
   ```

   followed by the overlay's two region markers (`<!-- coach:begin
   overlay <id> -->` and `<!-- coach:end overlay <id> -->`, each on its
   own line) once `overlay build` gives the id, and then "Normal program
   resumes <date>."
2. **Write the draft** at `.coach/drafts/overlay-<span start>.json`, in
   the athlete's units (`coach/schemas/overlay_draft.schema.json`):
   `kind` `deload` for a deload or other light week, else `one_off`;
   the `span`; the week `focus` (what the span is for — "deload — fewer
   sets at RPE 6, recover for next block"). Reshuffled sessions keep
   their program `session_id` and title. Each temp session gets a new
   `session_id` (`deload-mon`, `travel-a`), `"temporary": true`, the
   title its Hevy routine will carry ("Deload Mon — Lower") and, on a
   constrained week, its `location`. Per exercise: `exercise_id`,
   `hevy_template_id` (from `library show`), `load_mode`,
   `rest_seconds`, `cues`, `focus`, `target_note`, `change`, and
   `sets`, each load a number: per hand for per-hand modes, the added
   load for bodyweight, else the total.
3. `python3 -m coach overlay build --input <draft>` writes
   `data/overlays/<id>.json` and gives the id.
4. `python3 -m coach overlay validate <id>` — exit 1 lists each problem
   by JSONPath. Fix the draft, put the id in it, and build again.
5. `python3 -m coach overlay render <id> --into <check-in record>`
   fills the region.
6. **Hevy users:** `python3 -m coach routines diff --overlay <id>`. With
   every session mapped to a routine, it lists each routine in the span
   by its Hevy title. Temp sessions have no routine yet, so it exits 1
   naming them — and then it lists nothing, not even the routines that
   exist. Name them another way: "go" creates or reuses a routine for
   each session the exit-1 message names, under the session's title;
   every other session's routine keeps its own Hevy title (`state
   show` maps it to the session, and `.coach/cache/hevy/routines.json`
   holds the title).

A tweak to the brief means: edit the draft, then build, validate and
render again.

## 4. Present the week's brief — and stop

Talk the athlete through the span the way a coach would, narrative
first:

1. **Why this week deviates** — 1–2 sentences: the reason, what's
   being protected (the program's priority work), what's deliberately
   dropped, and when the normal program resumes.
2. **The schedule** — the Day / Session table for the span, with
   before/after where days moved.
3. **Temp sessions in full** (temp tier) — the rendered tables from
   `overlay render`, concrete enough to train directly.
4. **The write line** — the brief's last line names exactly what "go"
   will write: each routine by the Hevy title it will carry, from
   `routines diff`, or from the titles step 3.6 names when it exited 1.

   `Reply "go" to train this and write: Deload Mon — Lower, Deload Wed — Upper (Hevy).`

   Nothing going to Hevy (a reshuffle whose routines already match, or
   no Hevy) → the line says so:
   `Reply "go" to train this. Nothing goes to Hevy (reshuffle only).`

Then **stop and wait for the athlete's reply. Never present and write
in the same turn** — the brief is a proposal, not a notification.
**"go" (or a clear yes) approves the week and every write the line
names** — don't ask again before writing to Hevy. Anything else is a
tweak: revise and present the brief again, write line included.
Iterate until the athlete would train it.

## 5. Write

**Only enter this step after the athlete has replied "go" (or a clear
yes) to the brief above** — if no brief with a write line has been
presented and approved this session, go back to step 4. Write exactly
the routines the write line named.

1. `python3 -m coach overlay approve <id>` stamps the approval. It exits
   3 on an unresolved `block` flag: tell the athlete why, settle it, and
   present the brief again.
2. **Hevy users.** An earlier one-off week in `state show` whose span
   has ended: run `python3 -m coach routines retire --overlay <its
   overlay_id>` first, which retitles its routines `(unused)`.
3. `python3 -m coach routines create --overlay <id>` gives every temp
   session a routine in the "One-off weeks" folder: it reuses a spare
   temporary routine before it creates one, creates the folder when
   there is none, and records every id in `data/state.json`. The API
   has no delete — reuse **is** the cleanup.
4. `python3 -m coach routines push --overlay <id>` writes the rest — a
   reshuffled session's routine — and logs a verification for each
   routine already right. The permission prompt shows what it will
   write. A command that **exits 3** was refused by a guard: report its
   reason to the athlete and never retry it by hand. Only when a
   command keeps failing and the athlete agrees, use
   `reference/hevy-api.md` → "Manual fallback".
5. `python3 -m coach routines verify --overlay <id>` — the close-out
   quotes its result for each routine.

**No Hevy?** Skip steps 2–5 — the rendered overlay is the deliverable,
and the athlete trains the temp sessions from it.

## 6. Record it

- The overlay is in the record already (step 3). If `/check-in` invoked
  this skill, check-in's week-focus line follows the region and ends
  the section.
- Set `one_off` in `data/state.json` to `{"overlay_id": "<id>", "span":
  {"start": "<start>", "end": "<end>"}}`. The next `/check-in` judges
  the week against this overlay, and the first programming pass after
  the span ends retires its routines and clears `one_off`.
- If this was a **deload or other light week**, reset the hard-week
  count in the same edit: `block.hard_weeks_completed` to 0 and
  `block.deload` to `{"status": "in_progress", "since": "<span
  start>"}`. Keep the block's `started` date: the check-in that closes
  the light week starts the next block. The rules are in `CLAUDE.md`
  "Coaching principles" → Fatigue management.
- Then run `python3 -m coach state show`, which refuses an invalid
  state.

## 7. Close out

Recap in plain words: what the span looks like, what was written to
Hevy (quote `routines verify`), when normal service resumes. If
recovery drove this, note that the next check-in wants to hear how the
week actually went.
