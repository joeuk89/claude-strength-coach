# Path C — Starter (a tested program to begin from)

For an athlete with no program of their own who would rather start from
a tested one than design one from scratch.

1. **Pick a starter with the athlete:** run `python3 -m coach starters
   list` (`--days N` for their training days; `--location <name>` when
   they will train it at another place; equipment defaults to that
   place's `available`). Show each one's title, summary, days, minutes,
   required equipment and `swaps`. `recommended` marks the starters that
   suit `[athlete] experience` with every line fitting the kit
   (`unmatched` 0): advice, not a filter. `python3 -m coach starters show
   <id>` prints a starter's session pages.
2. **Preview the draft:** run `python3 -m coach starters draft <id>
   --dry-run`, with `--days mon,wed,fri` when they train on days other
   than `[athlete] available_days` and the same `--location` as step 1.
   It exits 1 when the day count is
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
   message), before adoption. A `swapped_exercise` row is an exercise
   the kit, an unconfirmed apparatus or ability, or the avoid list rules
   out, swapped for its first fitting library substitute; its message
   names each substitute passed over and why. Agree its cues. A
   `no_substitute` row has no fitting substitute: agree a swap or drop
   it, and edit the draft. When the athlete confirms a missing bench,
   bar or support (`[equipment] apparatus`) or shows they can do a skill
   exercise (`[athlete] demonstrated_exercises`), update `config.toml`
   and draft again. Swaps can move the weekly dose: run `python3 -m coach
   structure balance --program .coach/drafts/program.json` and settle its
   flags as design.md step 4 sets out. The starters program no direct
   abdominal work, so expect that coverage gap. The starter's own targets
   stay as they are unless you and the athlete review them.
6. **Adopt:** run `python3 -m coach program adopt --input
   .coach/drafts/program.json --dry-run`, then without `--dry-run`, as
   SKILL.md step 2 sets out; then Path B step 5 (design.md) for the
   Hevy routines.
