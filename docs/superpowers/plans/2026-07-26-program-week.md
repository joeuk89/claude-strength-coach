# `/program-week` Weekly Programming Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly programming pass — a new `program-week` skill that writes coach-set loads, rep targets, RPE, and three-line notes (Target / Focus / Cues) into Hevy each week — plus the ripple edits to check-in, hevy-sync, one-off-week, new-program, the Hevy cheatsheet, CLAUDE.md, and README.

**Architecture:** Everything is markdown — skills in `.claude/skills/*/SKILL.md`, reference docs, and repo docs. Three-layer prescription model: `routine/*.md` holds the block-level plan (now with a canonical `Cues:` line per exercise), the newest check-in's "week ahead" section holds the **weekly overlay** (per-exercise prescriptions), and Hevy carries the live version. Spec: `docs/superpowers/specs/2026-07-26-program-week-design.md`.

**Tech Stack:** Markdown only. No tests exist in this repo — verification is grep/read-back per task. House style: ~72-column wrap, sentence-case headings, bold key rules.

**Review rule (every task):** stage with `git add`, show the staged diff, and STOP for human review. Never commit — the human commits after approving each task.

---

### Task 1: Create the `program-week` skill

**Files:**
- Create: `.claude/skills/program-week/SKILL.md`

- [ ] **Step 1: Write the skill file**

Create `.claude/skills/program-week/SKILL.md` with exactly this content:

````markdown
---
name: program-week
description: Use when the coming week (or the rest of this week) needs programming — coach-set loads, rep targets, RPE, and per-exercise notes written to Hevy. Triggers include "/program-week", "program my week", "set my weights for this week", "bump my squat", "reprogram the rest of the week", or /check-in finishing its decisions on a normal (non-deload) week.
---

# Weekly programming pass

Turn the plan plus the latest review into concrete, coach-set
prescriptions for the coming week — per session, per exercise: working
load, rep target, RPE, a weekly focus where warranted, and the standing
form cues. Hevy users get it written into their routines so the app
shows exactly what the coach wants this week; everyone gets it recorded
in the check-in history as the **weekly overlay** — the effective
prescription the next check-in judges adherence against.

`routine/` stays the block-level plan — never write weekly numbers into
it. Structural changes (swaps, adds, set counts, execution changes) do
edit `routine/` — plan first, then Hevy.

Requires `profile.md` and `routine/program.md` — if missing, run
`/setup` / `/new-program` first.

## 1. Read the context

`profile.md` (units, constraints, niggle log, Coach's notes),
`routine/program.md` (progression scheme, RPE targets, rotation) and
its session files, the newest check-in (decisions, window, any overlay
already written), `routine/hevy-map.json`, and recent Hevy logs for
current working weights (`GET /v1/workouts`, newest first — API in
`reference/hevy-api.md`; no Hevy → ask the athlete for their current
weights). If the program rotates, confirm which week is next — never
assume.

**Stand down if a one-off week is active.** If `routine/program.md`'s
header carries a one-off/override pointer covering this span,
`/one-off-week` owns it — say so and stop.

**Mid-week?** Invoked standalone partway through a trained week, first
ask what prompted it (missed session, easy/hard day, schedule change),
then reprogram only the remaining days.

**First run: cue backfill.** If the session files have no `Cues:`
lines, offer a one-time backfill before programming: agree the
canonical form cues for each exercise with the athlete and add a
`Cues:` line under each exercise in `routine/*.md`.

## 2. Compute the week — per session, per exercise

Work through every session in the span, every exercise in each:

- **Load** — from the log and the program's progression rules: top of
  the rep range at or under target RPE → add load (the program's
  increment); reps missed → hold; logged RPE drifting over prescription
  → hold or back off. Reason per lift — a formula applied blindly is
  not coaching. Display in the athlete's units.
- **Rep target / RPE** — move them where the block's scheme calls for
  it.
- **Focus** — one per-exercise emphasis where warranted, drawn from
  check-in findings ("slow the eccentric", "depth fades when tired").
  Most exercises most weeks won't have one — that's fine.
- **Structural changes** — swaps or additions agreed at the check-in,
  or proposed now with rationale. These are plan changes: mark them
  separately, they land in `routine/` too.

Active niggles constrain everything: no added load on an aggravated
pattern.

## 3. Present — one approval for the whole week

One table per session: exercise · sets × reps @ load @ RPE · what
changed vs. last week · a one-line rationale where it isn't obvious.
Structural changes get their own short section with before/after and
trade-offs. The athlete approves the week **once**; iterate until they
would train it.

## 4. Write

1. **Structural changes first** — edit the affected `routine/*.md`
   files (an execution change like grip width edits that exercise's
   `Cues:` line), then re-check the day before and after each edited
   session and the program's weekly balance.
2. **Then Hevy** (key in `.env`): for each mapped routine in the span,
   GET it, update its sets (`weight_kg` converted from the athlete's
   units, `rep_range`) and each exercise's `notes` in the standard
   three-line format — Target / Focus / Cues, see
   `reference/hevy-api.md` — then PUT the whole routine back and GET to
   verify. Space writes a few seconds apart; back off ~30 s on a 429.

**No Hevy?** Skip the writes — the recorded overlay below is the
deliverable, and the athlete trains from it.

## 5. Record the overlay

Write the full per-exercise prescription into the newest check-in's
"The week ahead" section — when `/check-in` invoked this skill, that
section is being written now; fill it. Standalone runs append to the
newest check-in instead:

```markdown
## Week reprogrammed — YYYY-MM-DD

**Span:** <start> → <end> · **Reason:** <missed session / …>

(Per-session prescription tables underneath.)
```

If `notion-map.json` exists and covers check-ins, mirror the updated
record per `reference/notion-sync.md` — local file first, Notion after.

## 6. Close out

Recap in plain words: what changed this week and why, what was written
to Hevy, and the one thing to focus on. If a structural change landed,
note it for the next check-in's Decisions section.
````

- [ ] **Step 2: Verify the file parses as a skill**

Run: `head -4 .claude/skills/program-week/SKILL.md`
Expected: YAML frontmatter opening `---`, `name: program-week`, a `description:` line, closing `---`.

Run: `grep -c "Cues" .claude/skills/program-week/SKILL.md`
Expected: a count ≥ 4 (cue backfill, compute, write, overlay references).

- [ ] **Step 3: Stage and stop for human review**

```bash
git add .claude/skills/program-week/SKILL.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "Add /program-week: weekly programming pass skill"
```

---

### Task 2: Document the three-line note format in the Hevy cheatsheet

**Files:**
- Modify: `reference/hevy-api.md` (add a section before "Facts that bite"; update one bullet inside it)

- [ ] **Step 1: Add the note-format section**

In `reference/hevy-api.md`, insert this new section between the endpoint table and the `## Facts that bite` heading (i.e. immediately before the line `## Facts that bite`):

````markdown
## Routine note format (standard)

Every routine exercise `notes` field this repo writes uses this
three-line format — hard cap three lines; a note nobody reads between
sets is wasted:

```
Target: 3×8 @ RPE 8 — add 2.5 kg from last week
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

- **Target** — always. This week's sets × reps @ RPE plus the load
  instruction. Written weekly by `/program-week`; `/new-program` and
  `/one-off-week` write their own targets at creation time.
- **Focus** — only when there's a weekly emphasis. Omit the line
  otherwise.
- **Cues** — always. The canonical form cues, copied from the
  exercise's `Cues:` line in `routine/*.md` (that line is the single
  source of truth — changing how a lift is performed edits it there
  first).

````

- [ ] **Step 2: Update the RPE bullet in "Facts that bite"**

Replace this bullet:

```markdown
- **Routine templates cannot store an RPE target** (logged workout sets *do*
  carry `rpe`). RPE prescriptions live in the `routine/` files — and, as a
  standing rule, go into each routine exercise's `notes` field (with the key
  form cue) whenever a routine is written to Hevy, so the athlete sees them
  mid-session.
```

with:

```markdown
- **Routine templates cannot store an RPE target** (logged workout sets *do*
  carry `rpe`). RPE prescriptions live in the `routine/` files and the
  weekly overlay — and reach the athlete via each routine exercise's
  `notes` field in the standard three-line format (see "Routine note
  format" above) whenever a routine is written to Hevy.
```

- [ ] **Step 3: Verify**

Run: `grep -n "Routine note format" reference/hevy-api.md`
Expected: two hits — the section heading and the cross-reference in the RPE bullet.

- [ ] **Step 4: Stage and stop for human review**

```bash
git add reference/hevy-api.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "hevy-api: standard three-line routine note format"
```

---

### Task 3: Wire `/program-week` into the check-in skill

**Files:**
- Modify: `.claude/skills/check-in/SKILL.md` (three edits: analysis baseline, record template, act-on-it step)

- [ ] **Step 1: Point the analysis at the weekly overlay**

In section `## 3. Analyze — plan vs. reality`, replace (exact text
including the line wraps — it starts mid-sentence after "Convert to the
athlete's preferred units…"):

```markdown
them anything. **Judge against the effective prescription**, not the base
plan — check `routine/program.md` and the last check-in for an active
on-ramp, deload, or one-off week shape first.
```

with:

```markdown
them anything. **Judge against the effective prescription**, not the base
plan — the last check-in's week-ahead overlay (per-exercise targets, if
`/program-week` wrote one) plus any active on-ramp, deload, or one-off
week shape in `routine/program.md`. With an overlay, adherence is
concrete: did the athlete hit the prescribed load × reps @ RPE?
```

- [ ] **Step 2: Note in the record template that the overlay fills the week-ahead section**

In the section-6 weekly template, replace:

```markdown
## The week ahead — <dates>
| Day | Session |
| --- | --- |
| Mon | ... |
One-off changes called out. End with one line: the focus of the week.
```

with:

```markdown
## The week ahead — <dates>
| Day | Session |
| --- | --- |
| Mon | ... |
One-off changes called out. On normal weeks `/program-week` expands
this section with the per-exercise prescription tables — the weekly
overlay. End with one line: the focus of the week.
```

- [ ] **Step 3: Invoke program-week from "Act on it"**

In section `## 7. Act on it`, replace this bullet:

```markdown
- If routine changes were agreed and the athlete uses Hevy, offer
  `/hevy-sync`.
```

with:

```markdown
- On a normal (non-deload) week, once decisions are agreed, invoke the
  **program-week** skill — it computes per-exercise targets for the
  coming week, writes them to Hevy (with approval), and fills this
  record's "The week ahead" section. Structural routine changes agreed
  today ride along in its write step; `/hevy-sync` stays for
  reconciliation outside the pass.
```

- [ ] **Step 4: Verify**

Run: `grep -n "program-week" .claude/skills/check-in/SKILL.md`
Expected: three hits (sections 3, 6, 7).

- [ ] **Step 5: Stage and stop for human review**

```bash
git add .claude/skills/check-in/SKILL.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "check-in: invoke /program-week; judge against the weekly overlay"
```

---

### Task 4: Teach hevy-sync about the weekly overlay

**Files:**
- Modify: `.claude/skills/hevy-sync/SKILL.md` (section 2)

- [ ] **Step 1: Add the overlay to the diff baseline**

In section `## 2. Diff — structure, not loads`, replace the opening line:

```markdown
Compare per session, Hevy (kg → the athlete's units) vs. the markdown:
```

with:

```markdown
The expected state is **base plan + weekly overlay**: if the newest
check-in's week-ahead section (or a "Week reprogrammed" addendum)
carries per-exercise prescriptions from `/program-week`, judge Hevy
against those for the current week — coach-set rep targets and
three-line notes (Target / Focus / Cues, per `reference/hevy-api.md`)
are prescriptions, not drift.

Compare per session, Hevy (kg → the athlete's units) vs. that expected
state:
```

- [ ] **Step 2: Update the loads paragraph**

In the same section, replace:

```markdown
**Don't flag working loads.** The markdown's starting loads are
estimates; Hevy carries the live weights, which drift upward by design as
the progression scheme does its job. Only mention a load if it breaks a
stated constraint in `profile.md` — e.g. a barbell lift at/over an
equipment load cap.
```

with:

```markdown
**Don't flag working loads.** The markdown's starting loads are
estimates, and coach-set weekly loads are recomputed by the next
`/program-week` pass anyway — in-app load edits between passes are the
athlete autoregulating, not drift. Only mention a load if it breaks a
stated constraint in `profile.md` — e.g. a barbell lift at/over an
equipment load cap.
```

- [ ] **Step 3: Verify**

Run: `grep -n "weekly overlay" .claude/skills/hevy-sync/SKILL.md`
Expected: one hit in section 2.

- [ ] **Step 4: Stage and stop for human review**

```bash
git add .claude/skills/hevy-sync/SKILL.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "hevy-sync: diff against base plan + weekly overlay"
```

---

### Task 5: Adopt the note format in one-off-week

**Files:**
- Modify: `.claude/skills/one-off-week/SKILL.md` (one bullet in section 3)

- [ ] **Step 1: Update the notes bullet**

In section `## 3. Write to Hevy (temp tier, Hevy users)`, replace:

```markdown
- Fill each exercise's `notes` with the RPE target + key cue, as
  always. Space writes a few seconds apart (rate limit); confirm with
  the athlete before writing; GET back after to verify.
```

with:

```markdown
- Fill each exercise's `notes` in the standard three-line format
  (Target / Focus / Cues — see `reference/hevy-api.md`), as always.
  Space writes a few seconds apart (rate limit); confirm with the
  athlete before writing; GET back after to verify.
```

- [ ] **Step 2: Verify**

Run: `grep -n "three-line" .claude/skills/one-off-week/SKILL.md`
Expected: one hit.

- [ ] **Step 3: Stage and stop for human review**

```bash
git add .claude/skills/one-off-week/SKILL.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "one-off-week: adopt the three-line note format"
```

---

### Task 6: Require `Cues:` lines in new-program

**Files:**
- Modify: `.claude/skills/new-program/SKILL.md` (output contract + Path B step 5)

- [ ] **Step 1: Add cues to the output contract**

Replace this bullet:

```markdown
- Session files in `routine/` — every session concrete enough to train
  directly: exercises, sets × reps, RPE/intensity, rest, starting-load
  guidance.
```

with:

```markdown
- Session files in `routine/` — every session concrete enough to train
  directly: exercises, sets × reps, RPE/intensity, rest, starting-load
  guidance, and a `Cues:` line per exercise — the canonical form cues,
  the single source of truth for how each lift is performed (changing
  execution later, e.g. grip width, edits this line first).
```

- [ ] **Step 2: Update the Hevy push step**

In Path B step 5, replace:

```markdown
5. **Offer Hevy:** for Hevy users, offer to push the program to Hevy
   (create routines via `POST /v1/routines`, notes field filled with RPE +
   key cue per exercise — see `reference/hevy-api.md`), then build
   `hevy-map.json` from the returned IDs. Confirm before writing to the
   app.
```

with:

```markdown
5. **Offer Hevy:** for Hevy users, offer to push the program to Hevy
   (create routines via `POST /v1/routines`, each exercise's notes in
   the standard three-line format — see `reference/hevy-api.md`), then
   build `hevy-map.json` from the returned IDs. Confirm before writing
   to the app.
```

- [ ] **Step 3: Verify**

Run: `grep -n "Cues" .claude/skills/new-program/SKILL.md`
Expected: one hit in the output contract.

- [ ] **Step 4: Stage and stop for human review**

```bash
git add .claude/skills/new-program/SKILL.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "new-program: canonical Cues: line per exercise; three-line notes"
```

---

### Task 7: Document `/program-week` in CLAUDE.md and README

**Files:**
- Modify: `CLAUDE.md` (commands list, files table, Hevy section)
- Modify: `README.md` (weekly rhythm, flows)

- [ ] **Step 1: Add the command to CLAUDE.md's command list**

In `## The commands`, insert after the `/check-in` bullet:

```markdown
- **`/program-week`** — the weekly programming pass: coach-set loads,
  rep targets, RPE, and per-exercise notes for the coming week, written
  to Hevy and recorded as the weekly overlay in the newest check-in.
  `/check-in` runs it automatically on normal weeks; run it standalone
  to reprogram mid-week.
```

- [ ] **Step 2: Mention the overlay in CLAUDE.md's files table**

In `## The files`, replace the `check-ins/` row:

```markdown
| `check-ins/` | Dated check-in records (`YYYY-MM-DD.md`) — the progress history. |
```

with:

```markdown
| `check-ins/` | Dated check-in records (`YYYY-MM-DD.md`) — the progress history. The newest record's week-ahead section carries the **weekly overlay**: the per-exercise prescription `/program-week` wrote for the current week. |
```

- [ ] **Step 3: Update CLAUDE.md's Hevy note rule**

In `## Hevy`, replace:

```markdown
- **When writing any routine to Hevy, fill each exercise's `notes` field**
  with its RPE target and the key cue from the plan — that's how
  prescriptions the app can't store structurally reach the athlete
  mid-session.
```

with:

```markdown
- **When writing any routine to Hevy, fill each exercise's `notes`
  field** in the standard three-line format (Target / Focus / Cues —
  see `reference/hevy-api.md`) — that's how prescriptions the app can't
  store structurally reach the athlete mid-session.
```

- [ ] **Step 4: Update README's weekly rhythm and flows**

In `## The weekly rhythm`, replace step 3:

```markdown
3. **`/check-in`** once a week (~10 min). It reviews the week against the
   plan, asks a few questions, saves a dated record to `check-ins/`, and
   hands you the plan for the week ahead. Every ~6 weeks it runs deeper,
   as a block-level review.
```

with:

```markdown
3. **`/check-in`** once a week (~10 min). It reviews the week against the
   plan, asks a few questions, saves a dated record to `check-ins/`, then
   programs the week ahead — exact loads, rep targets, and coaching notes
   set in your Hevy routines, one approval for the whole week. Every ~6
   weeks it runs deeper, as a block-level review.
```

In `### Your training`, insert after the `/new-program` bullet:

```markdown
- **`/program-week`** — the weekly programming pass `/check-in` runs for
  you: this week's loads, rep targets, RPE, and notes set per exercise in
  Hevy. Run it directly to reprogram mid-week ("I missed Tuesday",
  "today felt easy").
```

- [ ] **Step 5: Verify**

Run: `grep -n "program-week" CLAUDE.md README.md`
Expected: CLAUDE.md ≥ 2 hits (commands list, files table); README.md ≥ 1 hit (flows).

- [ ] **Step 6: Stage and stop for human review**

```bash
git add CLAUDE.md README.md
git diff --staged   # show this to the human for review
# After the human approves:
# git commit -m "Document /program-week and the weekly overlay"
```
