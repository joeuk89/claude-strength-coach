# Build and check the overlay

Every mode comes here with an overlay id: from compute.md's finalize or
from `overlay build --input <draft>`.

1. **Where it renders.** When `/check-in` started this pass, its new
   record's "The week ahead" section takes the overlay, and the
   check-in's week-focus line follows the region and ends the section.
   Standalone, add a section to the newest check-in record, or create
   the first record when there is none, as `reference/record-formats.md`
   → "Standalone reprogram or one-off week" lays out.
2. `python3 -m coach overlay validate <id>`: exit 1 lists each problem by
   JSONPath. Fix the draft, put the id in it, and run `overlay build`
   again (a proposed week: override or resolve, then finalize again).
3. **Check every prescription before the brief.** Run `python3 -m coach
   history sync`, then `python3 -m coach prescription check --overlay
   <id> --write` (`--file <draft>` checks a draft without building it).
   It stores its flags in the overlay and records, for each line you
   wrote by hand, the exposure it came from. Per line it reports
   `days_off` and the return `band`. Settle each flag:
   - `stale_prescription` (block): the lift's days off fall in a return
     band, or an `ill` gap caps the first session back at RPE 7. Decay
     the line to that band as a return week does (compute.md), and
     record it in the line's `provenance.decay` (`days_off`, `band`,
     `load_factor`, `set_delta`, `rpe_cap`) with `derived_from` set to
     the exposure it came from.
   - `unearned_load` (block): even the fewest reps the line allows are
     beyond failure at the recent e1RM, or, with no e1RM from RPE-rated
     sets, the load is over two increments above the last exposure.
     Lower it; `python3 -m coach units load-for --e1rm <e1RM> --reps <n>
     --rpe <target> --increment <step>` gives the model load and the
     load on that step no heavier than it. The weekly proposal already
     holds a linear or double-progression step the model rejects at the
     heaviest load last logged that it accepts, and its rationale says
     so. Each line's `feasibility` says whether the model judged it
     (`checked`), only as a lower bound, or not at all (`unavailable`,
     `not_judged`); the brief says which.
   - `load_cap`, `load_unrepresentable` (block): over a cap, or not a
     load the session's kit makes. Correct the load or equipment declaration;
     explicit ladder rungs need an agreed rung edit, never silent snapping.
   - `load_geometry_unknown` (warn): confirm the unloaded mass of the Smith,
     EZ or trap bar and set the key the flag names at that location, then recheck.
   - `load_mode_mismatch` (block): the line's load mode or load
     arithmetic disagrees with the library. Match the line to the
     library. If the athlete corrects the mode itself, record it with
     `library set-mode`, ask whether the number meant the old or new
     mode, and run `program reconcile-mode <id> --basis old|confirmed`.
   - `load_mode_unconfirmed` (block): the exercise has no confirmed
     load mode. Ask the athlete, then run the command the flag names.
     Only confirming the mode clears it; a `resolution` never does.
   - `rpe_infeasible`, `session_over_cap` (warn): name each in the
     coach's brief, with the change you made or why it stands. A rep
     range passes when any whole rep target in it fits the RPE; a deload,
     light or return line's RPE, or a post-illness or RPE-capped set's at
     or over its cap, is a ceiling, flagged only when the load is too hard.

   Fix, then validate and check again until no `block` flag is left. A
   block you and the athlete decide to keep needs its flag's `resolved`
   set true with a `resolution` in the overlay, or `overlay approve`
   refuses it.
4. `python3 -m coach overlay render <id> --into <check-in record>` fills
   the region: the per-session tables the brief shows.
5. **Hevy users:** run `python3 -m coach routines preflight --overlay
   <id>`. Settle every unresolved template, including lines in sessions
   without routines: `library show <exercise>` and the cached templates
   (`id` and `title` in `.coach/cache/hevy/exercise_templates.json`)
   identify choices; `python3 -m coach library set-template <exercise>
   <cached-id>` records the chosen mapping locally. Rebuild
   the proposal/overlay after mapping, then preflight again until ready.
   For sessions without routines, run `python3 -m coach routines create
   --overlay <id> --dry-run` before approval. It names each new or reused
   routine, any new folder, and a `plan_hash`. Orphan routines come only
   from managed mapping history; offer leave, reuse (`--reuse
   <session>=<routine-id>`) or retire (`routines retire --overlay <id>
   --routine <routine-id> --dry-run`). Re-run the chosen previews and
   retain their hashes for write.md. Run `routines diff --overlay <id>`
   for the existing routines; if it exits 1 on unmapped sessions, use
   the create preview plus cached titles for the other sessions. The
   write line must name every create, reuse, retirement and folder.

A tweak to the coach's brief means: change the draft, then build,
validate, check and render again. The approval and every Hevy write and
verification are logged in `data/hevy/writes.jsonl`; nothing else needs
recording.
