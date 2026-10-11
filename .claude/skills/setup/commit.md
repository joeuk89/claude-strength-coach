# Commit setup before publishing week one

`program adopt` stages its outputs and never commits. Complete this
step before entering **program-week**, whose publisher refuses unrelated
staged files. Approval to adopt is separate from approval to commit.

1. Inspect `git status --short` and the diffs. Build an explicit path
   list from adoption's `written`, `removed`, `archived` and `staged`
   reports, plus the specific files setup created or changed, such as
   `config.toml`, `profile.md`, `data/exercises.json` or
   `data/niggles.json`. On a resumed run without the report, reconstruct
   that setup-only list from the diffs. List files individually,
   including removed paths; leave `.env`, caches, drafts and unrelated
   changes out.
2. Show the exact paths and their diff and ask the athlete to approve
   the commit. Check `git diff --cached --name-only`; if it names a path
   outside that list, stop and ask the athlete to settle that staged
   change separately. Do not sweep it into setup or unstage it silently.
3. After approval, run `git add -- <each approved path>`, inspect
   `git diff --cached`, and verify its paths match the approved list
   before `git commit -m "Initial setup: settings, profile and program"`.
   If nothing from setup has changed, skip the commit. If the athlete
   defers it, explain that first publication waits; leave adoption's
   staged files intact.
4. Verify the branch has an upstream with `git rev-parse
   --abbrev-ref --symbolic-full-name '@{upstream}'`. A normal clone from
   the README already has one. A zip download or freshly initialised
   repository needs a remote and upstream: agree the destination and
   permission to push with the athlete, add it with `git remote add
   <remote> <url>` if absent, then `git push -u <remote> <branch>`.
   With no upstream, `pages publish` exits 3 before writes or commits;
   establish it before the first publish.

Continue when the setup commit is complete and the upstream exists.
For later setup changes, repeat the same path review and approval with
an appropriate commit message.
