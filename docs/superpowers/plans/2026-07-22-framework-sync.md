# /framework-sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Joe's standing rule overrides everything:** after each task, stage the
> changes and STOP for his review. Never commit until he approves that
> task's diff. Never push without asking.

**Goal:** A `/framework-sync` skill that updates an instance workspace's framework files from the template repo's `main` — one direction, one command, auto-committed — so any instance owner can pull published framework improvements.

**Architecture:** A pure skill (markdown instructions, no scripts) added to the template at `.claude/skills/framework-sync/SKILL.md`. It fetches a `template` git remote (auto-added if missing), computes changes from a per-instance marker file (`.claude/framework-sync.json`, records the last-synced template commit) via `git diff --name-status`, warns once about locally-drifted files, applies copies and deletions, updates the marker, and commits everything as one commit. The framework set is "everything tracked in `template/main`" minus `docs/**` and `.gitkeep` files — the template repo is its own manifest.

**Tech Stack:** Git plumbing only (`fetch`, `diff --name-status`, `checkout <ref> -- <path>`, `rm`, `ls-tree`). No code, no dependencies.

**Design decisions already agreed with Joe (don't relitigate):**

- One direction only: template → instance. No reverse sync, no per-file interactive resolution, no version pinning, no branch selection — `template/main` is the only source.
- Drift policy: **warn, then overwrite** — one confirmation for the whole batch, abort cleanly if declined.
- Commit policy: the skill **auto-commits** the sync (one commit), with an escape hatch noting that a user's own review-before-commit instructions win. It offers to push, never pushes unasked.
- The marker file lives at `.claude/framework-sync.json` in each instance, is committed there, and never exists in the template repo itself.
- Personal files can never be touched: they aren't tracked in the template, and deletions only come from template-history diffs.

**Repo layout reminder:** the template is `~/personal/workout-template` (GitHub: `joeuk89/claude-strength-coach`, public). Joe's instance is `~/personal/workout` (GitHub: `joeuk89/my-training`, private), which already has a `template` remote pointing at the template's GitHub URL. The two repos share **no git history** — framework files are synced by copy, never merge. All build work in Tasks 1–4 happens in the **template** repo.

---

### Task 1: Write the skill

**Files:**
- Create: `~/personal/workout-template/.claude/skills/framework-sync/SKILL.md`

- [ ] **Step 1: Create the skill file** with exactly this content:

````markdown
---
name: framework-sync
description: Use when the user wants to update this workspace's framework files from the shared template — pull the latest published skills, coaching docs, and reference formats. Triggers include "/framework-sync", "sync the framework", "update the framework", "pull template updates", "get the latest version of the system".
---

# Framework sync (template → this workspace)

Update this workspace's **framework files** from the template repo's
`main` branch. One direction only: the template is the source of truth
for the framework, this workspace is the source of truth for the
athlete's data — and this skill never touches the data.

**The framework set:** every file tracked in `template/main` **except**
`docs/**` (the template's own development history) and `.gitkeep`
placeholders. There is no separate manifest — the template repo is the
manifest. Personal files (`profile.md`, `routine/`, `check-ins/`,
`nutrition/`, athlete-specific docs in `reference/`, `.env`) are not
tracked in the template, so the sync cannot touch them.

**The marker:** `.claude/framework-sync.json` records the template
commit this workspace last synced to:

```json
{ "template_commit": "<full sha>", "synced_at": "YYYY-MM-DD" }
```

It is committed in this workspace. The template repo itself never
contains one.

## 1. Preconditions

Must be a git repo with a **clean working tree** (`git status
--porcelain` empty). If not, stop and ask the user to commit or stash
first — the sync makes its own commit and must not sweep up unrelated
changes.

## 2. Fetch the template

- Use the existing `template` remote if there is one; otherwise add it:

  ```bash
  git remote add template https://github.com/joeuk89/claude-strength-coach.git
  ```

- `git fetch template`. If the fetch fails (offline, repo moved), say so
  plainly and stop — nothing has changed locally.

## 3. Work out what changed

Read the marker. Confirm its sha is known to the fetched history
(`git cat-file -e <sha>^{commit}`).

**Marker valid:** `git diff --name-status <marker sha> template/main`,
filtered to the framework set. `A`/`M` entries (and rename targets) are
copies; `D` entries (and rename sources) are deletions. Empty after
filtering → tell the user they're already up to date and stop.

**No marker, or its sha is unknown to the fetched history:** full copy —
every framework-set file in `template/main`
(`git ls-tree -r --name-only template/main`, minus the exclusions) that
differs from the working copy, plus any that don't exist locally. Note
to the user that deletions can't be detected on this run.

## 4. Drift check — warn before overwriting

Framework files are meant to be edited in the template, never locally —
but it happens. Before writing anything, find local edits: for each file
about to be overwritten or deleted, `git diff <marker sha> -- <path>` —
non-empty output means the working copy drifted from what the last sync
delivered.

- Drifted files: list them, say plainly that their local edits will be
  **overwritten** (recoverable from git history), and get **one
  confirmation for the whole batch**. If declined, stop — nothing has
  changed, and suggest porting the local edits to the template instead.
- First run (no marker): there's no baseline to detect drift against, so
  list every file the sync will change and confirm once.

## 5. Apply and commit

- Copies: `git checkout template/main -- "<path>"` per file.
- Deletions: `git rm "<path>"` per file.
- Write the marker: `template_commit` from
  `git rev-parse template/main`, `synced_at` today.
- **One commit** for everything, marker included:
  - Subject: `Sync from template: <one-line gist of what came in>`
  - Body: the template commit subjects being pulled in
    (`git log --reverse --format='- %s' <marker sha>..template/main`);
    on a first run, `Baseline sync at <short sha>` instead.
- Offer to push to `origin`; never push unasked.

(If the user's own standing instructions require human review before
commits, stage and show the diff instead of committing — user rules
win over this skill.)

## 6. Close out

- Summarize what came in, in plain words ("check-in skill updated, new
  deload skill added") — not just filenames.
- If this skill's own file was among the updates, say so: the new
  instructions take effect from the **next** run, not this one.
````

- [ ] **Step 2: Sanity-check the skill against the design decisions** at the top of this plan — direction, drift policy, commit policy, marker location, exclusions. Fix any mismatch now.

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/framework-sync/SKILL.md
git diff --staged   # show Joe
# After Joe approves: git commit -m "Add /framework-sync skill: one-way template → instance updates"
```

---

### Task 2: Wire the skill into the template docs

**Files:**
- Modify: `~/personal/workout-template/CLAUDE.md` (commands list, after the `/hevy-sync` entry ending near line 99)
- Modify: `~/personal/workout-template/README.md` (commands list after the `/hevy-sync` entry at lines 59–61, and the whole "Updating your copy" section at lines 85–98)

- [ ] **Step 1: CLAUDE.md** — in "The commands", directly after the `/hevy-sync` bullet (`…Editing routines in the app mid-block is normal, not an error.`), add:

```markdown
- **`/framework-sync`** — update this workspace's framework files
  (skills, docs, reference formats) from the shared template repo. One
  direction: template → here; personal files are never touched.
```

- [ ] **Step 2: README.md commands list** — after the `/hevy-sync` bullet, add:

```markdown
- **`/framework-sync`** — update your copy to the latest version of the
  framework (skills, docs). Your personal files are never touched.
```

- [ ] **Step 3: README.md "Updating your copy"** — replace the entire section (currently a manual `git remote add` / `git fetch` / `git merge --allow-unrelated-histories` walkthrough — **that advice is wrong for this repo layout and must go**) with:

```markdown
## Updating your copy

Run **`/framework-sync`**. It fetches the template's latest `main` and
updates your framework files (skills, CLAUDE.md, reference docs) in one
commit. Your personal files — profile, routine, check-ins, nutrition —
are never touched, and it warns you first if you've edited a framework
file locally.
```

- [ ] **Step 4: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add CLAUDE.md README.md
git diff --staged   # show Joe
# After Joe approves: git commit -m "Document /framework-sync in CLAUDE.md and README"
```

---

### Task 3: Acceptance-test the skill in a scratch instance

No code means no unit tests — the test is walking the skill's own
instructions in a simulated instance and checking every behavior. Use a
scratch directory (the session's scratchpad dir, or `mktemp -d`). Do
**not** make test commits in the real template repo — clone it and make
test commits in the clone.

**Files:** none in either real repo (fixes discovered here are edits to
Task 1/2 files, re-staged under those tasks).

- [ ] **Step 1: Build the fixtures.** A scratch clone of the template acts as the remote (so we can add test commits freely); a fresh unrelated-history repo acts as the brother's instance (GitHub's "Use this template" produces exactly that — a copy with no shared history):

```bash
S=$(mktemp -d)
git clone ~/personal/workout-template "$S/template"

mkdir "$S/instance" && cd "$S/instance" && git init -b main
git -C "$S/template" archive HEAD~2 | tar -x -C .   # an older template state
git add -A && git commit -m "Simulated 'Use this template' copy"
echo "# Test athlete" > profile.md
mkdir -p routine && echo "# Test program" > routine/program.md
git add -A && git commit -m "Simulated personal data"
```

(`HEAD~2` just needs to predate the framework-sync skill so the first
sync has real changes to deliver; any older commit works.)

- [ ] **Step 2: First-run path (no marker, no remote).** In `$S/instance`, follow the SKILL.md steps exactly as written, with one stated deviation: where the skill adds the GitHub URL as the `template` remote, use `$S/template` instead (GitHub doesn't have the new commits yet; the real URL path is exercised in Task 5). Verify all of:
  - Clean-tree precondition actually blocks: dirty the tree (`echo x >> profile.md`), confirm the skill's step 1 stops, then `git checkout profile.md` and continue.
  - The full-copy path fires (no marker), lists the files it will change, and asks one confirmation.
  - After applying: every framework-set file matches the template (`git diff template/main --stat -- <framework paths>` is empty), `docs/` and `.gitkeep` files were **not** copied in, `profile.md` and `routine/` are untouched, `.claude/framework-sync.json` exists with the template's HEAD sha, and exactly one new commit contains it all with a `Baseline sync at <sha>` body.

- [ ] **Step 3: Diff path — update, deletion, rename, drift, up-to-date.** Make test commits in `$S/template`:

```bash
cd "$S/template"
echo "<!-- test edit -->" >> .claude/skills/check-in/SKILL.md
git rm reference/recipe-sources.md
git mv reference/recipe-cards.md reference/recipe-card-format.md
git add -A && git commit -m "Test: edit check-in, delete recipe-sources, rename recipe-cards"
```

Then in `$S/instance`, create drift on a file the diff will touch (the warn only covers files being changed):

```bash
cd "$S/instance"
echo "local hack" >> .claude/skills/check-in/SKILL.md
git commit -am "Simulated local drift"
```

Re-run the skill flow and verify:
  - The diff path fires (marker valid), scoped to exactly the three changed paths.
  - The drift warn lists `check-in/SKILL.md` (and only it), asks once, and declining aborts with a clean tree and no commit.
  - Accepting: check-in file overwritten, `recipe-sources.md` deleted, rename applied as delete + add, marker advanced, one commit whose body lists the test commit's subject.
  - Run the flow once more with no new template commits → "already up to date", no commit.

- [ ] **Step 4: Fix what the test shook out.** Any ambiguity or wrong command found in SKILL.md gets fixed in the real template file (Task 1's file) and re-staged. Re-run the affected test step to confirm the fix. Then delete the scratch dir (`rm -rf "$S"`).

- [ ] **Step 5: Stage and stop for review** — present the test results summary and any SKILL.md fixes to Joe; commits for Tasks 1–3 happen here if he hasn't approved them already.

---

### Task 4: Push the template to GitHub

- [ ] **Step 1: Confirm with Joe, then push** (the skill can only fetch what's published):

```bash
cd ~/personal/workout-template
git log origin/main..main --oneline   # show Joe what's about to publish
git push origin main                  # only after Joe approves
```

---

### Task 5: First real sync — Joe's instance

This is the production first-run: `~/personal/workout` has the `template`
remote already, no marker, and is currently byte-identical to the
pre-framework-sync template — so the sync should deliver exactly the new
skill file, the CLAUDE.md/README updates, and the marker.

- [ ] **Step 1: Run `/framework-sync` in `~/personal/workout`** following the skill as shipped (this doubles as the test of the published-GitHub fetch path). **Deviation per Joe's standing rule: stage and show instead of auto-commit.**

- [ ] **Step 2: Verify** — staged changes are exactly: `.claude/skills/framework-sync/SKILL.md` (new), `CLAUDE.md`, `README.md` (modified), `.claude/framework-sync.json` (new, sha = template HEAD). Nothing personal touched. Show Joe; he approves the commit (`Sync from template: add /framework-sync`).

---

### Task 6: Update project memory

**Files:**
- Modify: `~/.claude/projects/-Users-joeabousselam-personal-workout/memory/template-instance-split.md`

- [ ] **Step 1:** Update the memory so the standing rule reads: framework files are edited in the template first, pushed to GitHub, then pulled into instances with `/framework-sync` (which replaced the manual copy step on 2026-07-22; marker file `.claude/framework-sync.json`). Keep the rest of the fact (unrelated histories, personal content goes in profile/routine) intact. Update the corresponding line in `MEMORY.md` only if its one-line hook no longer fits.

---

## Done when

- `/framework-sync` exists in the template, documented in CLAUDE.md + README, README's stale merge advice gone.
- All Task 3 acceptance checks pass in the scratch instance.
- Template pushed; Joe's instance synced via the skill itself, marker in place.
- Project memory reflects the new sync mechanism.
