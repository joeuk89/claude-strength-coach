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
