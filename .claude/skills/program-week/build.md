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
   - `unearned_load` (block): the load is beyond failure for those reps
     at the recent e1RM. Lower it.
   - `load_cap`, `load_unrepresentable` (block): over a cap, or not a
     load the kit at the session's location makes. Snap it with `units
     round` to a load that is.
   - `load_mode_mismatch` (block): the line's load mode or load
     arithmetic disagrees with the library. Match the line to the
     library. If the athlete corrects the mode itself, record it with
     `library set-mode`, ask whether the number meant the old or new
     mode, and run `program reconcile-mode <id> --basis old|confirmed`.
   - `load_mode_unconfirmed` (block): the exercise has no confirmed
     load mode. Ask the athlete, then run the command the flag names.
     Only confirming the mode clears it; a `resolution` never does.
   - `rpe_infeasible`, `session_over_cap` (warn): name each in the
     coach's brief, with the change you made or why it stands.

   Fix, then validate and check again until no `block` flag is left. A
   block you and the athlete decide to keep needs its flag's `resolved`
   set true with a `resolution` in the overlay, or `overlay approve`
   refuses it.
4. `python3 -m coach overlay render <id> --into <check-in record>` fills
   the region: the per-session tables the brief shows.
5. **Hevy users:** `python3 -m coach routines diff --overlay <id>` lists
   every routine in the span by its Hevy title, with what "go" would
   change. A session with no routine (every temporary session, or a new
   program session) makes it exit 1 naming the session, and then it
   lists nothing, not even the routines that exist. Name them another
   way: "go" creates or reuses a routine for each session the exit-1
   message names, under its session title; every other session's
   routine keeps its own Hevy title (`state show` maps it to the
   session, and `.coach/cache/hevy/routines.json` holds the title).

A tweak to the coach's brief means: change the draft, then build,
validate, check and render again. The approval and every Hevy write and
verification are logged in `data/hevy/writes.jsonl`; nothing else needs
recording.
