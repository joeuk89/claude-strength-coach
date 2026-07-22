# Notion Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Joe's standing rule overrides everything:** after each task, stage the
> changes and STOP for his review. Never commit until he approves that
> task's diff. Never push without asking.
>
> **Sequencing:** build after the `/framework-sync` plan
> (`2026-07-22-framework-sync.md`) — it delivers this feature into
> instances. Independent of the one-off-week and niggle-log plans; if
> executed in the same session, share one publish + sync (Task 6).

**Goal:** An optional one-way mirror of coaching docs (check-ins, meal plans, recipes, optionally the routine) to Notion, so the athlete can read them on the go — with local files always written first and remaining the source of truth.

**Architecture:** A `/notion-sync` skill owns setup, backfill, and repair; the writing skills (`/check-in`, `/meal-plan`, `/recipes`) mirror their own output at close-out with a one-line addition each. Mechanics live once in `reference/notion-sync.md`. State lives in `notion-map.json` at the instance repo root (hevy-map pattern): parent page, section page per doc type, and one entry per synced file. `/setup` gains an optional Notion step and is sharpened to support reconfiguration on re-run.

**Tech Stack:** Markdown skills; whatever Notion MCP the user has connected (tool names discovered at runtime — never hardcoded).

**Design decisions already agreed with Joe (don't relitigate):**

- **One-way only.** Notion is a read view; Notion-side edits are overwritten on next sync and the docs say so. No two-way sync, ever.
- **Never block, never lose work.** Local writes happen first; no map → no Notion behaviour; MCP absent in a session → sync is pending, `/notion-sync` backfills later.
- Doc types are a per-user choice: `check-ins` · `meal-plans` + `recipes` (travel together) · `routine` (earns its place mainly for non-Hevy athletes). Profile and reference docs never sync.
- Recipes are **plain pages** under a Recipes section — no Notion database (noted as a possible later upgrade).
- Shopping lists render as **checkable to-do blocks**; repo-internal links rewrite to Notion page links when the target is mapped, plain text otherwise.
- Nothing is ever deleted in Notion; the map drops entries instead.
- `/setup` must be **idempotent and reconfigurable**: re-running it on a fully set-up workspace offers each area for changes (e.g. enabling Notion later) instead of declaring everything done.

**Repo layout reminder:** template = `~/personal/workout-template` (public); Joe's instance = `~/personal/workout` (synced via `/framework-sync`). Tasks 1–5 edit the template; Task 7 runs live in the instance with Joe's Notion.

---

### Task 1: Write the mechanics reference

**Files:**
- Create: `~/personal/workout-template/reference/notion-sync.md`

- [ ] **Step 1: Create the file** with exactly this content:

````markdown
# Notion sync — mechanics

How the optional Notion mirror works. `/notion-sync` owns setup,
backfill, and repair; `/check-in`, `/meal-plan`, and `/recipes` mirror
their own writes at close-out. Read this before any Notion write.

## The contract

- **One-way.** Repo files are the source of truth; Notion is a read
  view. Local writes always happen first and never depend on Notion.
  Notion-side edits are unsupported — the next sync of that doc
  overwrites them (the athlete is told this at setup).
- **Optional.** No `notion-map.json` → no Notion behaviour anywhere.
- **Never block.** If no Notion MCP is connected in a session, say the
  sync is pending and continue; `/notion-sync` backfills later. A
  failed Notion write never fails the local task.

## The MCP

Notion access comes from whatever Notion MCP the user connected (the
claude.ai Notion connector, the official Notion MCP server, …). Tool
names differ; the needed capabilities are the same: search, fetch,
create page, update page. Discover what's available at runtime (e.g.
ToolSearch for "notion") — never hardcode tool names. No Notion tools
in this session → sync is pending.

## notion-map.json (repo root)

```json
{
  "_comment": "Notion mirror mapping. One-way: repo -> Notion. Managed by /notion-sync; writing skills append page entries when they mirror their own output.",
  "parent_page_id": "…",
  "parent_page_title": "Training",
  "doc_types": ["check-ins", "meal-plans", "recipes"],
  "sections": {
    "check-ins": "…page id…",
    "meal-plans": "…page id…",
    "recipes": "…page id…"
  },
  "pages": {
    "check-ins/2026-07-19.md": { "page_id": "…", "synced_at": "2026-07-22" }
  }
}
```

`doc_types` is the athlete's choice from: `check-ins`, `meal-plans`,
`recipes`, `routine` (`meal-plans` and `recipes` normally travel
together). File coverage per type: `check-ins/*.md` · dated
`nutrition/*.md` plans · `nutrition/menu/*.md` cards (including
`index.md`) · `routine/*.md`. Any write that creates or updates a
Notion page updates `pages` in the same operation (hevy-map rule).

## Syncing one file

1. Path in `pages` → **update** that page (replace content). Not
   there → **create** under its doc type's section page, then record
   it.
2. Page title = the file's H1 (filename if there's no H1).
3. Content = the file's markdown, with three adjustments:
   - **Links** to repo files that are in `pages` become Notion links
     to those pages; other repo-relative links are flattened to plain
     text — never ship a broken link.
   - **Shopping list tables** (meal plans) become checkable to-do
     items — one per Buy row and per staple row, quantity included.
   - Tables stay tables. Keep formatting simple: when something won't
     render cleanly, prefer plain over clever.
4. Update `pages` (`page_id`, `synced_at`) in the same operation.

## Staleness (what backfill re-syncs)

- **Stale:** a mapped file changed after its `synced_at` — last commit
  date (`git log -1 --format=%cs -- <file>`) is newer, or the file has
  uncommitted changes.
- **Unsynced:** a file of a chosen doc type with no map entry.

## Repair

- Mapped page fetch fails (deleted/moved in Notion) → recreate it,
  update the map.
- Parent or section page missing → offer to recreate the structure,
  then re-link or re-export as needed.
- Local file deleted or archived → drop its map entry; leave the
  Notion page for the athlete to tidy. **Nothing is ever deleted in
  Notion by this system.**
````

- [ ] **Step 2: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add reference/notion-sync.md
git diff --staged   # show Joe
# After approval: git commit -m "Add reference/notion-sync.md: one-way Notion mirror mechanics"
```

---

### Task 2: Write the `/notion-sync` skill

**Files:**
- Create: `~/personal/workout-template/.claude/skills/notion-sync/SKILL.md`

- [ ] **Step 1: Create the skill file** with exactly this content:

````markdown
---
name: notion-sync
description: Use when the athlete wants coaching docs mirrored to Notion — first-time Notion setup, syncing or backfilling check-ins, meal plans, recipes, or the routine, or repairing the mapping. Triggers include "/notion-sync", "sync to notion", "set up notion", "put my meal plan in notion", "why isn't this in notion".
---

# Notion sync

Set up and maintain the optional **one-way** mirror of coaching docs
to Notion. The mechanics, map format, and sync contract live in
**`reference/notion-sync.md`** — follow it exactly. This skill owns
setup, backfill, scope changes, and repair; the writing skills
(`/check-in`, `/meal-plan`, `/recipes`) mirror their own output at
close-out.

## 1. Check the MCP

Look for connected Notion tools (per the reference doc). None → tell
the athlete they need to connect a Notion MCP (e.g. the claude.ai
Notion connector) first, and stop — there's nothing useful to do
without one.

## 2. First run — setup

No `notion-map.json` yet:

- State the contract in one breath: files in this repo stay the source
  of truth, Notion is a read-only view, and anything edited on the
  Notion side gets overwritten by the next sync.
- Ask which doc types to mirror: **check-ins** · **meal plans +
  recipes** · **routine**. (Routine earns its place mainly for
  non-Hevy athletes — Hevy users already carry the program in the
  app.)
- Pick the parent page: search their Notion, confirm the exact page
  with the athlete — never guess between similarly named pages.
- Create one section page per chosen doc type under the parent.
- Write `notion-map.json`, then **bulk-export** every existing doc of
  the chosen types, recording each page in the map as it lands.
- Close out: what synced where, and the one-way warning once more.

## 3. Later runs — backfill, scope changes, repair

Map exists:

- Find **stale** and **unsynced** files for the chosen doc types (per
  the reference doc) and re-mirror them. Report updated vs created.
- Spot-check that the parent, section, and a sample of mapped pages
  still exist; repair per the reference doc if not.
- Scope changes on request: add or remove doc types (update
  `doc_types`, create the section page, backfill), or move to a new
  parent page (recreate the structure, re-export, rewrite the map).

## Rules that always apply

- Local files first, always — a Notion failure never loses local work
  and never fails the task that wrote the file.
- Nothing is ever deleted in Notion; the map drops entries instead.
- Every page create/update updates `notion-map.json` in the same
  operation.
````

- [ ] **Step 2: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/notion-sync/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "Add /notion-sync skill: optional one-way Notion mirror"
```

---

### Task 3: Close-out mirroring in the three writing skills

**Files:**
- Modify: `~/personal/workout-template/.claude/skills/check-in/SKILL.md` (end of "## 7. Act on it")
- Modify: `~/personal/workout-template/.claude/skills/meal-plan/SKILL.md` (end of "## 7. Write and close out")
- Modify: `~/personal/workout-template/.claude/skills/recipes/SKILL.md` ("## Rules that always apply")

- [ ] **Step 1: check-in** — append as the **final bullet** of section 7 (other plans may have added bullets there; last position is the anchor):

```markdown
- If `notion-map.json` exists and covers check-ins, mirror this record
  to Notion per `reference/notion-sync.md` — local file first, Notion
  after. No Notion MCP this session → say the sync is pending
  (`/notion-sync` catches it up) and move on.
```

- [ ] **Step 2: meal-plan** — append as a new final paragraph of section 7 (after the paragraph ending "…the next `/check-in` reviews how the plan went."):

```markdown
If `notion-map.json` exists and covers meal plans, mirror the plan to
Notion per `reference/notion-sync.md` — shopping list as to-do blocks,
recipe links rewritten to their Notion pages. No Notion MCP this
session → say the sync is pending and move on.
```

- [ ] **Step 3: recipes** — in "## Rules that always apply", after the "Same-write rule" bullet, add:

```markdown
- **Notion mirror:** if `notion-map.json` exists and covers recipes,
  card writes (create/edit/bench) mirror to Notion per
  `reference/notion-sync.md`; if no Notion MCP is connected this
  session, the sync is pending — `/notion-sync` catches it up.
```

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/check-in/SKILL.md .claude/skills/meal-plan/SKILL.md .claude/skills/recipes/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "check-in/meal-plan/recipes: mirror output to Notion when configured"
```

---

### Task 4: `/setup` — Notion step + reconfiguration on re-run

**Files:**
- Modify: `~/personal/workout-template/.claude/skills/setup/SKILL.md`

- [ ] **Step 1: Sharpen idempotence.** Change the intro paragraph:

```markdown
Turn a fresh copy of the template into this athlete's training workspace.
A thin orchestrator: each step checks whether it's already done and skips
or offers to redo it, so `/setup` is safe to re-run and resumes cleanly
after a partial run.
```

to:

```markdown
Turn a fresh copy of the template into this athlete's training workspace.
A thin orchestrator: each step checks whether it's already done and skips
or offers to redo it, so `/setup` is safe to re-run and resumes cleanly
after a partial run. It's also how the athlete **reconfigures** later —
on a fully set-up workspace, report each area's state and ask what they
want to change (add an integration like Notion, refresh the profile),
rather than declaring everything done.
```

- [ ] **Step 2: State check.** Change section 0's text:

```markdown
Look at what exists: `profile.md`? `.env` with a key? `routine/program.md`?
A "Nutrition & goals" section with real content? Report what's already
done, then continue from the first missing piece.
```

to:

```markdown
Look at what exists: `profile.md`? `.env` with a key? `routine/program.md`?
A "Nutrition & goals" section with real content? `notion-map.json`?
Report what's already done, then continue from the first missing piece —
or, if nothing is missing, ask what the athlete wants to change.
```

- [ ] **Step 3: Integrations.** In section 2, after the MacroFactor block (ends "…Record yes/no."), add:

```markdown
**Notion (optional):**
- Ask whether they want their coaching docs (check-ins, meal plans,
  recipes, routine) mirrored to Notion for reading on the go. If yes,
  invoke the **notion-sync** skill's setup flow — it checks for a
  Notion MCP connection and explains how to connect one if it's
  missing. Easy to skip and add later: re-running `/setup` or
  `/notion-sync` sets it up any time.
```

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/setup/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "setup: optional Notion step; support reconfiguration on re-run"
```

---

### Task 5: Document the command and the map file

**Files:**
- Modify: `~/personal/workout-template/CLAUDE.md` ("The commands" list; "The files" table)
- Modify: `~/personal/workout-template/README.md` ("The commands" list)

- [ ] **Step 1: CLAUDE.md commands** — append after the final command bullet in the list (whatever the last one is at execution time — earlier plans append here too):

```markdown
- **`/notion-sync`** — optional one-way mirror of coaching docs
  (check-ins, meal plans, recipes, routine) to Notion. First run picks
  a parent page and creates `notion-map.json`; later runs backfill and
  repair. Local files stay the source of truth.
```

- [ ] **Step 2: CLAUDE.md files table** — after the `routine/hevy-map.json` row, add:

```markdown
| `notion-map.json` | Notion mirror mapping (parent page, section pages, file → page IDs) — only exists if the athlete enabled Notion sync. Managed by `/notion-sync`; mechanics in `reference/notion-sync.md`. |
```

- [ ] **Step 3: README commands** — append after the final command bullet:

```markdown
- **`/notion-sync`** — optionally mirror your check-ins, meal plans,
  and recipes to Notion, to read on your phone. Files in this repo stay
  the source of truth.
```

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add CLAUDE.md README.md
git diff --staged   # show Joe
# After approval: git commit -m "Document /notion-sync and notion-map.json"
```

---

### Task 6: Publish and sync

- [ ] **Step 1:** If executing in the same session as the one-off-week / niggle-log plans, fold into their shared publish + sync (one push, one `/framework-sync` run, Joe approving each). Otherwise:

```bash
cd ~/personal/workout-template
git log origin/main..main --oneline   # show Joe what's about to publish
git push origin main                  # only after Joe approves
```

Then run `/framework-sync` in `~/personal/workout` (Joe's rule: stage and show; he approves the commit).

---

### Task 7: Live acceptance — Joe's Notion

Joe has a Notion MCP connected. Real writes to his Notion — get his
go-ahead at each write step.

**Files:**
- Create: `~/personal/workout/notion-map.json` (written by the skill's setup flow)

- [ ] **Step 1: Run `/notion-sync` setup** in `~/personal/workout`: Joe picks the parent page and doc types (his call — likely check-ins + meal plans + recipes). Section pages created; existing docs bulk-exported (at minimum `check-ins/2026-07-19.md`; nutrition docs if the bank is seeded by then).

- [ ] **Step 2: Verify rendering in Notion** (Joe eyeballs, or fetch the pages back): the check-in's tables render as tables; if a meal plan exists, its shopping list is to-do blocks and its recipe links point at the recipe pages.

- [ ] **Step 3: Backfill-not-duplicate test:** make a trivial local change to the synced check-in file (e.g. amend a line, or use any genuinely pending edit), run `/notion-sync` again, and confirm the **same** page updated (`page_id` unchanged in the map, no duplicate page in Notion). Revert the trivial change if it was synthetic.

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout
git add notion-map.json
git diff --staged   # show Joe
# After approval: git commit -m "Enable Notion sync (notion-map.json)"
```

---

## Done when

- `reference/notion-sync.md` and `/notion-sync` exist; the three writing skills mirror at close-out; `/setup` offers Notion and supports reconfiguration on re-run; CLAUDE.md and README document it all.
- Published and synced into Joe's instance via `/framework-sync`.
- Joe's Notion has the parent/section structure with his existing docs exported, rendering verified, backfill updating rather than duplicating, and `notion-map.json` committed.
