# Write, then close out

**Only start this after the athlete has replied "go" (or a clear yes)
to the brief.** If no brief with a write line has been presented and
approved this session, go back to the brief. Write exactly what the
write line named, nothing more.

1. **Structural changes first** (normal and midweek only): edit
   `data/program.json` as the write line named (an execution change like
   grip width edits that exercise's `cues`), then run `python3 -m coach
   program validate` and `python3 -m coach program render`. Re-check the
   day before and after each edited session and the program's weekly
   balance.
2. `python3 -m coach overlay approve <id>` stamps the athlete's
   approval. It exits 3 on an unresolved `block` flag, or on a
   `load_mode_unconfirmed` line whose exercise still has no confirmed
   load mode: tell the athlete why, settle it, and present the brief
   again.
3. **An ended one-off week.** If `state show` has a `one_off` whose span
   ended before today, execute only the leftover retirements named in
   the brief: `python3 -m coach routines retire --overlay <its overlay_id>
   --routine <leftover-id> --expect-plan <approved-retire-hash>` (repeat
   `--routine` for each selected leftover). Routines step 4 reuses stay
   untouched until reuse. Then set `one_off` to null in
   `data/state.json` and run `python3 -m coach state show` to check it.
4. **Hevy users.** If `routines diff` named sessions with no routine,
   run `python3 -m coach routines create --overlay <id> --expect-plan
   <approved-create-hash>` first, including exactly the `--reuse` choices
   from the reviewed preview. Explicit orphan retirements use `routines
   retire --overlay <id> --routine <id> --expect-plan <approved-retire-hash>`.
   Run only actions the athlete's write line named. A changed plan exits
   3: preview and present the revised brief before retrying. It gives
   each program session a routine in the program folder, and each
   temporary session one in the "One-off weeks" folder: it reuses a
   spare temporary routine before it creates one, creates the folder
   when there is none, and records every id in `data/state.json`. The
   API has no delete, so reuse is the cleanup. Then run `python3 -m
   coach routines push --overlay <id>`: the permission prompt shows what
   it will write, which is what the athlete approved. It writes
   **every** routine in the span that differs from the overlay, notes
   included (the week line, Target, Focus and Cues all come from the
   overlay), and logs a verification for each routine already right. A
   push that **exits 3** was refused by a guard: report its reason to
   the athlete and never retry it by hand. A routine edited in the app
   since the diff is the usual one: run `python3 -m coach routines diff
   --overlay <id> --refresh`, settle the edit with the athlete, and push
   again. Exit 1 means a routine didn't read back as written; report
   it. Only when a command keeps failing and the athlete agrees, use
   `reference/hevy-api.md` → "Manual fallback".
5. `python3 -m coach routines verify --overlay <id>`: the close-out
   quotes its result for each routine.
6. **A one-off week** (light, constrained or reshuffle mode): set
   `one_off` in `data/state.json` to `{"overlay_id": "<id>", "span":
   {"start": "<start>", "end": "<end>"}}`. The next `/check-in` judges
   the span against this overlay, and the first pass after the span ends
   retires its routines and clears `one_off` (step 3). A light week
   leaves `block` alone: unless `state show` already has the light week
   agreed (`/check-in` records it), record it with `python3 -m coach
   block decide --outcome adopted` (add `--type` and `--reason` when
   nobody proposed it). The check-in that closes the week (`block
   close`) ends the block and starts the next at zero, by the rules in
   `CLAUDE.md` "Coaching principles" → Fatigue management. Then run
   `python3 -m coach state show`, which refuses an invalid state.

**No Hevy:** skip `routines retire` in step 3 (an ended one-off week
still gets `one_off` set to null) and steps 4 and 5, and run `python3 -m
coach sheets render --overlay <id>`.

## Close out

**Publish the week.** Hevy users: only once `routines verify` reports
every routine verified; a routine left unverified means no publish, and
the recap says why. No Hevy: once `sheets render` has written the
sheets. Before publishing, verify the branch's upstream with `git
rev-parse --abbrev-ref --symbolic-full-name '@{upstream}'`. A normal
README clone already has one; a zip download or freshly initialised
repository needs an agreed remote and `git push -u <remote> <branch>`
(add the remote first if absent). Without it, publishing exits 3 before
writing or committing. During setup, finish its approved setup commit
first. Run `python3 -m coach pages render`, then `python3 -m coach
pages publish --overlay <id>` with `--include <path>` for each path of
the approved commit plan (`--structural` too when it names
`data/program.json`; no `--include` when the athlete kept the records
local). Run it with `--dry-run` first: a path in `records.local` that
the plan did not name changed after approval, so list those paths and
include them only after the athlete's yes. The approved plan itself
needs no second question. Publishing commits exactly the brief
(`this-week.md`), the dashboard (`README.md`), `progress.md`, the overlay,
the newest check-in record and the included records, plus
`this-week-sheets.md` when Hevy is off. It refreshes those sheets from
the approved overlay and pushes them so the athlete's phone shows the
week. If `pages render` exits 3 because `README.md` is still
the template's copy, ask once whether the dashboard may replace it, then
run `python3 -m coach pages render --replace-readme`. A publish that
exits 3 (overlay not approved or not the brief's overlay, missing
upstream, another file already staged, a path outside the training
records) is reported,
never worked around; exit 4 means the push failed and the commit is
kept: tell the athlete to push by hand.

Recap in plain words: what changed this week and why, what was written
to Hevy (quote `routines verify`: each routine verified, or not and
why, plus, on a hold-steady week, any routine that was STALE before
it), the records the commit included, each record `records.local`
names as kept only on this computer (uncommitted), and the one thing to
focus on. A one-off week says when the normal
program resumes; when recovery drove it, say the next check-in wants to
hear how the week went. If a structural change landed, note it for the
next check-in's Decisions section.
