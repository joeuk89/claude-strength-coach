# Constrained and reshuffle modes

A one-off week the scripts don't propose: you design it with the
athlete and write the overlay draft yourself. `data/program.json`,
`routine/` and the program's Hevy routines never carry it.

## Design the span

**Reshuffle:** the existing sessions still work; only the calendar
changes (a coach session moved, a day dropped, two days swapped).
Reorder using the program's own rules: recovery windows between
adjacent sessions, no same-pattern sessions on back-to-back days, and
weekly balance including coach-led sessions and cardio. Each moved
session keeps its lines from the overlay in force
(`data/overlays/<id>.json`), re-dated. Its routines already carry those
lines, so `routines diff` lists no change and nothing goes to Hevy.

**Constrained:** the prescriptions change for travel kit, no equipment,
or a time-starved or run-down week. A short design conversation (what
kit, what time, what state), then sessions that keep the program's
priority work alive at a maintainable dose. Maintenance, not progress:
~⅓–½ of normal volume holds strength and muscle for a couple of weeks,
so don't program PR attempts on hotel dumbbells. The failure mode to design
against is no plan at all: sporadic, maximal, improvised sessions.
Name the place's kit as an `[equipment.locations.*]` table in
`config.toml` when it differs from home, so caps and loads use it.

Every temporary session must be concrete enough to train directly:
exercises, sets × reps, load or RPE, rest. Unfamiliar dumbbells (a
hotel rack, a different increment) are exactly when a doubled entry
slips in unnoticed, so snap each load to the kit with `python3 -m coach
units round --value <load> --increment <step>` and let the renderer
print both numbers.

## Write the draft

Write `.coach/drafts/overlay-<span start>.json` in the athlete's units
(`coach/schemas/overlay_draft.schema.json`):

- `kind` `one_off`, the `span`, and the week `focus`: what the span is
  for ("travel week: keep the main lifts at two hard sets each").
- A reshuffled session keeps its program `session_id` and title, with
  its new `date`.
- Each temporary session gets a new `session_id` (`travel-a`),
  `"temporary": true`, the title its Hevy routine will carry ("Travel A
  — Full body") and, on a constrained week, its `location`.
- Per exercise: `exercise_id`, `hevy_template_id` (from `library
  show`), `load_mode`, `rest_seconds`, `cues` (from the program),
  `focus`, `target_note` and `change` (the brief's relative wording;
  these never reach Hevy), and `sets`, each load a number: per hand for
  per-hand modes, the added load for bodyweight, else the total.

Then run `python3 -m coach overlay build --input <draft>`, which writes
`data/overlays/<id>.json` and gives the id, and go to build.md. A draft
that names an unapproved overlay's id rebuilds it, which is how a tweak
to the brief lands.
