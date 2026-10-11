# Program: three paths

Run `python3 -m coach starters list --days <number of available days>`,
then make the **new-program** skill's three-path offer in one message,
with the profile from step 4, and recommend one path from the answers:

- **A starter:** no program of their own, and a week a starter fits.
  Name `starters list`'s `recommended_id`.
- **An import from Hevy:** they already run a program in Hevy Pro.
- **A design:** the week or goal needs a program built for it, such as
  coach-led sessions to plan around, a sport, or unusual kit or limits.

Then follow that path in the **new-program** skill:

- **Starter path** (its Path C): `python3 -m coach starters draft <id>
  --dry-run`, then the same without `--dry-run`, adding `--start-load
  <exercise id>=<load>` for each working weight from question 3, by the
  ids in the preview's `program.priority`. Don't ask for the weights
  again.
- **Import path** (its Path A): `python3 -m coach library seed`; then
  its load-mode confirmation: `python3 -m coach library set-mode <id>
  <mode>` for each `low`-confidence or `guessed` row, and `python3 -m
  coach library confirm <ids>` (or `--all`) for the rest; then `python3
  -m coach program import-hevy`. Ask once: **run it as written, or coach
  it?** Write `[coaching] mode` from the answer: `"run"` to run their
  program as written, `"coach"` (the default) to have it reviewed and
  improved. Then finish the draft as Path A says.
- **Design path** (its Path B): the design conversation, ending in a
  draft at `.coach/drafts/program.json`.

On every path, add each coach-led session from question 4 to the
draft's `program.external_sessions` (the shape is in
`coach/schemas/program.schema.json`). Then run `python3 -m coach program
adopt --input .coach/drafts/program.json --dry-run` and show, in one
message, the draft's report as one table and the load-mode table below,
and ask to adopt. On a yes, run it without `--dry-run`. Never write
`data/program.json` yourself.

**Confirm the load-mode table once.** Adopt's `unconfirmed` lists every
exercise without a confirmed load mode. Show it as one table (exercise,
load mode, and how the athlete sets the weight: one total, per hand, or
one dumbbell) in the adopt message. With their yes, record every row
with `python3 -m coach library set-mode <id> <mode>`, changing any row
they correct. The import path confirmed its load modes before the
import, so its table holds only exercises added while finishing the
draft. Never ask about it again.
