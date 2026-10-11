# Path C — Starter (a tested program to begin from)

For an athlete with no program of their own who would rather start from
a tested one than design one from scratch.

1. **Pick a starter with the athlete:** run `python3 -m coach starters
   list` (`--days N` for their training days; equipment defaults to
   `[equipment] available`). Show each one's title, summary, days,
   minutes and required equipment. `recommended` marks the starters that
   suit `[athlete] experience`: advice, not a filter. `python3 -m coach
   starters show <id>` prints a starter's session pages.
2. **Preview the draft:** run `python3 -m coach starters draft <id>
   --dry-run`, with `--days mon,wed,fri` when they train on days other
   than `[athlete] available_days`. It exits 1 when the day count is
   outside the starter's range or the kit lacks the equipment its main
   lifts need: pick other days or another starter. The draft's
   `program.priority` lists the main lifts after any swap for the kit or
   the avoid list, so `db_bench_press` can stand where the starter has
   `bb_bench_press`.
3. **Ask once whether they know their working weights** for those
   priority lifts. Any they give become start loads, in their units and
   per hand for dumbbells. Every other loaded line runs a calibration
   week with no load: its note asks them to choose a load they could
   lift for the target reps at the target RPE.
4. **Draft:** run the same command without `--dry-run`, adding
   `--start-load <exercise id>=<load>` for each known weight, by the
   ids in the preview's `program.priority`. It writes
   `.coach/drafts/program.json`.
5. **Show the draft's report as one table** (kind, session, exercise,
   message). A `swapped_exercise` row is an exercise the kit cannot
   support, or one the athlete avoids, swapped for its first fitting
   library substitute: agree its cues. A `no_substitute` row has no
   fitting substitute: agree a swap or drop it, and edit the draft.
6. **Adopt:** run `python3 -m coach program adopt --input
   .coach/drafts/program.json --dry-run`, then without `--dry-run`, as
   SKILL.md step 2 sets out; then Path B step 5 (design.md) for the
   Hevy routines.
