# Profile facts into config and data

The answers that scripts read go into config and data, not prose:

- **Question 1** → optional `[athlete] birth_year`, a positive whole year no
  later than the current year. Omitted means unknown. `python3 -m coach
  config show` returns `age` as null or explicitly approximate: the birthday
  is unknown. Reuse it; ask exact age only when a calculator needs it.
  A declined birth year goes in Coach's notes so resume does not ask again.
- **Question 3** → keep historical training, recent consistency and time off
  in Coach's notes. Confirm `[athlete] experience` as today's programming
  level (`beginner`, `intermediate`, `advanced`), then record that confirmation
  in the notes. The config's default is not confirmation. After years away,
  offer conservative beginner-style re-entry while retaining the history;
  there is no years-off-to-level formula. Old working weights are historical,
  not current start loads; use calibration unless current loads are confirmed.
- **Question 4** → `[athlete] desired_sessions` (1–7), `available_days`
  (`"mon"` .. `"sun"`) and `session_minutes`. Desired sessions are the total
  weekly target, including coach-led sessions; settle their share before
  selecting solo sessions. Pick that many days from availability with the
  athlete; availability alone creates no obligations. Coach-led sessions go
  into the program draft. A yes to runs or classes sets `[activity] enabled = true`.
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

Create a new `profile.md` from `reference/record-formats.md` → "profile.md:
the first version". For an existing profile, revise affected paragraphs and
retain other notes. Keep prose only a human reads: numbers and lists that
live in `config.toml` or `data/` are not repeated in it.

## Corrections, later disclosures and resuming

Before program selection, adoption and close-out, reconcile every new answer
with config, the program draft, niggles and the profile. The athlete's explicit
correction authorizes updating that fact; show the resulting change. For other
profile changes, obtain the confirmation required by `CLAUDE.md`.

- Replace the relevant config value or location table; remove superseded keys
  (for example a former home's dumbbell limit). Run `config validate` again.
- Replace the affected profile paragraph in place. Keep the context in words,
  with machine-owned numbers and lists only in config/data; never append a
  second, contradictory equipment or training-week account.
- A newly disclosed limitation goes through question 6's niggle command and
  replaces any incompatible "None currently" prose. Run `python3 -m coach
  niggles list` first; use `niggles update <id>` for the same existing issue,
  so resume does not create duplicates. Keep its story in the profile without
  repeating constraint numbers. If it affects the draft, agree any needed
  edits before adoption; an active program uses the normal approval gate.
- A corrected desired count or availability triggers a fresh schedule check:
  confirm only the desired sessions within the revised available days. Revise
  the draft and rerun adoption's dry run; an active program needs an agreed edit.

A profile file alone is not completion. Resolve or explicitly defer each
unanswered group; note deferred facts and confirmed current level in Coach's
notes. On resume read those notes and structured sources, show what is known,
and ask only what remains unresolved. Completion requires consistent profile
prose, validated config, recorded limitations and an agreed schedule.
