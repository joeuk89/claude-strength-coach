# Profile facts into config and data

The answers that scripts read go into config and data, not prose:

- **Question 3** → `[athlete] experience`: `"beginner"` under about a
  year of consistent training, `"intermediate"` for steady progress over
  a few years, `"advanced"` beyond that. Keep the working weights for
  the program's start loads.
- **Question 4** → `[athlete] available_days` (`"mon"` .. `"sun"`) and
  `session_minutes`. Coach-led sessions go into the program draft. A yes
  to runs or classes sets `[activity] enabled = true`.
- **Question 5** → `[equipment]` for the main place: `available` (from
  `barbell`, `ez_bar`, `trap_bar`, `dumbbell`, `kettlebell`, `machine`,
  `smith_machine`, `cable`, `plate`, `band`, `suspension`, `bodyweight`,
  `cardio_machine` and `other`; an empty list assumes every piece),
  `dumbbells` (per-hand weights, when the set is limited), `dumbbell_max`
  and `plates`. If the main place is a home gym, run `python3 -m coach
  config suggest --unit <kg|lb> --gym home` and use its values instead.
  Each other place gets one `[equipment.locations.<name>]` table
  (lowercase letters, digits and hyphens) holding only the keys that
  differ from `[equipment]`.
- **Question 6** → a lasting limitation becomes a niggle: `python3 -m
  coach niggles add --area "<where>" --status chronic --pattern
  <patterns> --constraint <kind=value> --constrain-while chronic --notes
  "<its story>"`. A current, short-term one uses `--status watching`.
  For pain or a suspected injury, also recommend a qualified
  professional (`CLAUDE.md` "Safety & scope"). An exercise they cannot
  or will not do: `python3 -m coach library set-avoid <id> --reason
  "<why>"`, finding the id with `python3 -m coach library search
  <name>`.

Then write `profile.md` from the skeleton in `reference/record-formats.md`
→ "profile.md: the first version": prose only a human reads. Numbers and
lists that live in `config.toml` or `data/` are not repeated in it.
