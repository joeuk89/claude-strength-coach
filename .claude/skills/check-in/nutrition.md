# Weight and nutrition (every check-in)

**The framework rule:** for an athlete using a nutrition app, this
check-in gets **complete logging** into the app and reads the app's
numbers out. It **never states its own calorie target or calorie band**
and never runs a parallel calorie model. Fewer than 7 days logged: ask
for every day to be logged, with an estimate of the day or the missed
meal on a day they couldn't track and no half-logged days (MacroFactor's
guidance, in `/goals`). Record the days logged either way.

**Record the reading.** Turn the Food field's numbers into one reading
with `python3 -m coach nutrition record --date <check-in date>
--trend-weight X --expenditure N --target-kcal N --target-protein N
--avg-kcal N --avg-protein N --days-logged N --anchors yes|no`. Pass
only what the reply gave; without an app, pass `--scale-weight` (the
mean of the week's morning weigh-ins) and `--avg-protein` if they track
it. Weights are in `[athlete] bodyweight_units`. A reading already on
file for the date exits 1: re-run with `--replace` only to correct it.
Then run `python3 -m coach nutrition status` and work from its output.
The numbers on file (phase, target trend rate, protein floor, target and
stretch, anchors, any override) are in `config.toml`'s `[nutrition]`
table; `nutrition status` returns them.

**Weight trend.** `data.trend` gives the rate per week over the latest
span of 14 days or more, next to `target_rate_per_week`; it is a number,
not a verdict. One odd week is noise; a **2–3-week trend** off target is
a flag. **With MacroFactor**, the app auto-adjusts targets weekly:
usually the right response is "let it work and keep logging", not a
manual override. **Without MacroFactor**, when a 2–3-week trend misses
the target rate, propose moving `[nutrition] kcal_target` by ~100–150
kcal/day in the direction the trend needs. With the athlete's yes, edit
it in `config.toml` and note the reason in Nutrition & goals in
`profile.md`. Never re-derive it from an equation; a fresh estimate
comes only from `/goals` with a new phase. If the **phase itself** looks
wrong (trend says cut while the plan says bulk, a phase trigger arrived,
or the goal has changed), point the athlete at `/goals` rather than
tweaking numbers here.

**Act on each flag** in `data.flags`:

- `protein_floor_raise`: average protein met the floor at the two most
  recent readings since `floor_since`. Propose raising the floor to
  `proposed_floor_g` (the step, capped at the target). With the
  athlete's yes, set `floor_g` to `proposed_floor_g` and `floor_since`
  to `proposed_floor_since` (the day after the latest counted reading,
  so this week's reading, taken under the old floor, doesn't count
  toward the next raise) in `[nutrition.protein]` in `config.toml`;
  MacroFactor users set the app's protein to the new floor the same day.
  No flag: the floor stays. Missing it never lowers it; only `/goals`
  lowers it.
- `app_protein_mismatch`: the app's protein target is not the floor.
  Have the athlete set the app to the floor, unless the active override
  covers protein.
- `logging_incomplete`: fewer than 7 days logged. Ask for every day to
  be logged, as in the framework rule above.
- `override_expired`: on or after its expiry date the override ends.
  Remove `[nutrition.override]` from `config.toml`, tell the athlete
  they're back on the app's numbers (or, without an app, the calorie
  target on file), and record it. Its exit condition firing earlier ends
  it the same way. Renewal is not done here: it needs `/goals` with a
  fresh reason.
- `override_renewed_twice`: flag it in the record at every check-in
  while it stands, as a sign the plan itself needs changing.
- `no_recent_reading`: nothing recorded in the last 14 days. Record
  this week's reading before reading anything else into the trend.

**Anchors:** note the "anchors most days" answer. A "no" two weeks
running is a cue to revisit the anchors in `/goals`, not to lower the
floor.

**Sleep gate.** Once the athlete has a sleep source (a watch or phone
that tracks sleep), take the trailing 14-day average: the tracker's own
figure, or the mean of this and the last check-in's tracked Sleep
fields. During a **deficit**, re-check the gate: under ~7 h fails it and
sends the athlete to `/goals` to move to recomp at maintenance. A gate
recorded as `pending measurement` gets its first measurement the same
way: under ~7 h confirms recomp; at or over it, offer `/goals` to
reconsider the deficit. Update the gate status in `profile.md`.

If `nutrition status` says `enabled: false`, just note the scale weight
in the record and prompt `/goals` to get set up.

**Deep tier, body composition:** when the reply carries a reading, read
it against the goal or phase trigger that uses it and against the last
reading. A trigger that fires sends the athlete to `/goals`.

If a dated plan in `nutrition/` covers (part of) this window, the Food
field's habits question said how it went: note learnings for the next
`/meal-plan` run (recipe-bank changes belong in `/recipes`, not here).

Record the numbers in the weight and nutrition lines of the record's
Coach's read (record.md); the readings series holds them, so they no
longer go into `profile.md`.
