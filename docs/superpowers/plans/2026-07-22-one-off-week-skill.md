# /one-off-week Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Joe's standing rule overrides everything:** after each task, stage the
> changes and STOP for his review. Never commit until he approves that
> task's diff. Never push without asking. Never print `.env` contents.
>
> **Prerequisite:** the `/framework-sync` plan
> (`2026-07-22-framework-sync.md`) must be executed first — this plan's
> Task 6 uses `/framework-sync` to deliver the skill into Joe's instance,
> and its doc edits anchor on text that plan adds.

**Goal:** A `/one-off-week` skill that plans a week deviating from the standing program — a deload or a disrupted/constrained week — as either a reshuffled schedule of existing sessions or fully-specified temp sessions written to a standing Hevy folder, recorded in the check-in history without ever touching `routine/`.

**Architecture:** One template skill with two tiers (reshuffle / temp sessions), invoked directly by the athlete or by `/check-in` when its deload trigger fires. Temp sessions go into a standing Hevy folder ("One-off weeks") whose routines are **reused** — each new one-off week `PUT`s over the same routine IDs, because the public API has no delete. The folder and routine IDs live in a new `temporary` section of `hevy-map.json`, which `/hevy-sync` learns to ignore. Output lands as a dated addendum in the newest check-in record plus the one-off pointer line in `routine/program.md` — the convention the repo already uses for one-off weeks.

**Tech Stack:** Markdown skills, Hevy REST API (`routine_folders`, `routines`), no code.

**Design decisions already agreed with Joe (don't relitigate):**

- Name: `/one-off-week`. One skill, two tiers; the tier is picked with the athlete from what they describe, not a flag.
- Live Hevy routines are **never** overwritten or moved; deload loads derive from live Hevy working weights, not the markdown's starting estimates.
- Standing folder titled `One-off weeks`, created once, routines reused (PUT over) forever; no placeholder routines are pre-created — slots are created at first real use.
- The deload transform comes from the athlete's `routine/program.md` deload policy; the skill proposes a standard default only when a program has no policy, and offers to record it.
- Output: addendum in the newest check-in record + pointer in `program.md`; when `/check-in` invokes the skill, the content fills that check-in's "week ahead" section instead. Nothing is written into `routine/`.
- Works without Hevy: the record is the deliverable.
- YAGNI: no multi-week overrides beyond a stated span, no folder deletion/archiving, no library of past one-off weeks, no nutrition changes.

**Repo layout reminder:** template = `~/personal/workout-template` (GitHub `joeuk89/claude-strength-coach`, public); Joe's instance = `~/personal/workout` (private, unrelated history, synced by `/framework-sync`). Tasks 1–4 edit the **template**; Tasks 5–7 run in the **instance**.

---

### Task 1: Verify the folder API, update the cheatsheet

The cheatsheet documents `GET /v1/routine_folders` but not creation. Verify before the skill relies on it. **Read-only** — no writes to Joe's account in this task.

**Files:**
- Modify: `~/personal/workout-template/reference/hevy-api.md` (endpoint table, lines 24–36; "Facts that bite" final bullet, lines 60–63)

- [ ] **Step 1: Confirm the endpoints in the API spec:**

```bash
cd ~/personal/workout
curl -s https://api.hevyapp.com/docs/swagger-ui-init.js | grep -o '"/v1/routine_folders[^"]*"' | sort -u
curl -s https://api.hevyapp.com/docs/swagger-ui-init.js | python3 -c "import sys,re; s=sys.stdin.read(); i=s.find('routine_folders'); print(s[i-200:i+3000])"
```

Expected: `POST /v1/routine_folders` exists; note its exact request body shape (likely `{"routine_folder": {"title": "…"}}`). Also confirm the `POST /v1/routines` body accepts `folder_id`. If POST folders does **not** exist, stop and flag to Joe — the design needs a rethink (fallback: athlete creates the folder by hand in the app, skill only fills it).

- [ ] **Step 2: Live read sanity check** (uses the key; never print it):

```bash
set -a && source .env && set +a
curl -s -H "api-key: $HEVY_API_KEY" "https://api.hevyapp.com/v1/routine_folders?page=1&pageSize=10"
```

Expected: Joe's three folders (Week A, Week B, Conditioning) — confirms the endpoint shape matches the map's numeric folder IDs.

- [ ] **Step 3: Update `reference/hevy-api.md`** in the template. In the endpoint table, directly below the `GET /v1/routine_folders` row, add (adjusting the body note to what Step 1 actually found):

```markdown
| `POST /v1/routine_folders` | Create a routine folder (body `{"routine_folder": {"title": "…"}}`). `POST /v1/routines` takes a `folder_id` to file the new routine | — |
```

And extend the final "Facts that bite" bullet (the `hevy-map.json` one) — after "…heal the map with the athlete before doing anything else.", append:

```markdown
  A `temporary` section holds the "One-off weeks" folder ID and its
  reusable routine IDs (written by `/one-off-week`) — `/hevy-sync`
  ignores those routines entirely.
```

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add reference/hevy-api.md
git diff --staged   # show Joe
# After approval: git commit -m "hevy-api: document folder creation + map temporary section"
```

---

### Task 2: Write the skill

**Files:**
- Create: `~/personal/workout-template/.claude/skills/one-off-week/SKILL.md`

- [ ] **Step 1: Create the skill file** with exactly this content:

````markdown
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
````

- [ ] **Step 2: Check the skill against the agreed decisions** in this plan's header — tiers, reuse-not-delete, live-load derivation, output locations, no-Hevy path. Fix mismatches now.

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/one-off-week/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "Add /one-off-week skill: deload + disrupted-week planning"
```

---

### Task 3: Teach `/check-in` and `/hevy-sync` about it

**Files:**
- Modify: `~/personal/workout-template/.claude/skills/check-in/SKILL.md` (section 7, final bullet ends "…offer `/hevy-sync`.")
- Modify: `~/personal/workout-template/.claude/skills/hevy-sync/SKILL.md` (section 1, after the `unmapped` bullet)

- [ ] **Step 1: check-in** — in "## 7. Act on it", after the bullet ending "…and the athlete uses Hevy, offer `/hevy-sync`.", add:

```markdown
- On a deload-week check-in, invoke the **one-off-week** skill (deload
  mode) to build the deload week itself — its schedule and sessions
  fill this record's "The week ahead" section, and it handles the Hevy
  writes.
```

- [ ] **Step 2: hevy-sync** — in "## 1. Fetch and map", after the bullet "Anything in the map's `unmapped` list, or newly unmatchable, is a discrepancy in itself — raise it.", add:

```markdown
- Routines in the map's `temporary` section (the "One-off weeks"
  folder `/one-off-week` writes deload and disrupted-week sessions
  into) are disposable by design — exclude them from the diff entirely
  and never report them as drift.
```

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/check-in/SKILL.md .claude/skills/hevy-sync/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "check-in/hevy-sync: wire in /one-off-week"
```

---

### Task 4: Document the command

**Files:**
- Modify: `~/personal/workout-template/CLAUDE.md` ("The commands" list — after the `/framework-sync` bullet added by the framework-sync plan)
- Modify: `~/personal/workout-template/README.md` ("The commands" list — same anchor)

- [ ] **Step 1: CLAUDE.md** — after the `/framework-sync` bullet, add:

```markdown
- **`/one-off-week`** — plan a week that deviates from the program — a
  deload, or a disrupted/constrained week (travel, limited kit) —
  without touching `routine/`. Temp sessions go to a standing Hevy
  folder; the record lands in the check-in history.
```

- [ ] **Step 2: README.md** — after the `/framework-sync` bullet, add:

```markdown
- **`/one-off-week`** — plan a deload week, or a disrupted week
  (travel, limited kit): concrete sessions for the blip, your program
  untouched.
```

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add CLAUDE.md README.md
git diff --staged   # show Joe
# After approval: git commit -m "Document /one-off-week in CLAUDE.md and README"
```

---

### Task 5: Dry-run acceptance test (nothing written anywhere)

Walk the skill against Joe's real data with **all writes disabled** —
no Hevy writes, no file edits. This both tests the prose and previews
the real ~24 Aug deload.

- [ ] **Step 1: Reshuffle scenario.** In `~/personal/workout`, simulate: "my PT session moves to Wednesday evening next week". Follow the skill: context read, tier pick (expect reshuffle), schedule table produced, and it must re-check the recovery windows around the moved day (Wed morning home session + lunchtime run + evening PT is a triple — the skill should catch and resolve it). Show Joe the output table.

- [ ] **Step 2: Deload scenario.** Simulate the penciled ~24 Aug deload: confirm rotation position, fetch live loads from the mapped Hevy routines (`GET /v1/routines`, read-only), apply the program's deload policy, and produce the full week — every session concrete. Verify loads are derived from live `weight_kg` values (converted to lb), not the markdown estimates, and that pull-up/bodyweight work follows the program's bodyweight deload rules. Show Joe.

- [ ] **Step 3: Fix what the dry run shook out** — any ambiguity in the SKILL.md gets fixed in the template file and re-staged under Task 2. Re-run the affected scenario step to confirm.

---

### Task 6: Publish and sync

- [ ] **Step 1: Push the template** (with Joe's explicit approval — public repo):

```bash
cd ~/personal/workout-template
git log origin/main..main --oneline   # show Joe what's about to publish
git push origin main                  # only after Joe approves
```

- [ ] **Step 2: Run `/framework-sync` in `~/personal/workout`** (per Joe's standing rule: stage and show instead of auto-commit). Expected delivery: the new skill file, the check-in/hevy-sync skill edits, hevy-api.md, CLAUDE.md, README, marker advanced. Joe approves the commit.

---

### Task 7: Seed the standing folder in Joe's Hevy

First live write — needs Joe's explicit go-ahead (it creates a visible
folder in his app). Routine slots are **not** pre-created; the first
real use (the ~24 Aug deload) creates them.

**Files:**
- Modify: `~/personal/workout/routine/hevy-map.json`

- [ ] **Step 1: Create the folder** (body shape as verified in Task 1):

```bash
cd ~/personal/workout
set -a && source .env && set +a
curl -s -X POST -H "api-key: $HEVY_API_KEY" -H "Content-Type: application/json" \
  -d '{"routine_folder": {"title": "One-off weeks"}}' \
  "https://api.hevyapp.com/v1/routine_folders"
```

Expected: the created folder JSON with a numeric `id`. Verify with a GET that it now lists.

- [ ] **Step 2: Record it in `hevy-map.json`** — add a top-level `temporary` key after `"folders"` (folder ID from Step 1):

```json
"temporary": {
  "_comment": "One-off weeks folder — disposable deload/disrupted-week routines written by /one-off-week. Reused (PUT over) each run; /hevy-sync ignores everything in here.",
  "folder_id": 0,
  "routines": []
}
```

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout
git add routine/hevy-map.json
git diff --staged   # show Joe
# After approval: git commit -m "hevy-map: add One-off weeks folder (temporary section)"
```

---

## Done when

- `/one-off-week` exists in the template; check-in, hevy-sync, hevy-api.md, CLAUDE.md, and README all reference it correctly.
- Both dry-run scenarios produced trainable output from Joe's real data with no writes.
- Template pushed; Joe's instance synced via `/framework-sync`.
- The "One-off weeks" folder exists in Joe's Hevy and `hevy-map.json` records it with an empty `routines` list.
- First real use is the ~24 Aug 2026 deload, via `/check-in` → `/one-off-week`.
