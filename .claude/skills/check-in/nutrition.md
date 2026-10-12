# Weight and nutrition (every check-in)

**The framework rule:** for an athlete using a nutrition app, this
check-in gets **complete logging** into the app and reads the app's
numbers out. It **never states its own calorie target or calorie band**
and never runs a parallel calorie model. Fewer than 7 days logged: ask
for every day to be logged, with an estimate of the day or the missed
meal on a day they couldn't track and no half-logged days (MacroFactor's
guidance, in `/goals`). Record the days logged either way.

**Nutrition off.** Run `python3 -m coach nutrition status` first. If it
says `enabled: false`, keep any weigh-in with `python3 -m coach bodyweight
record --date <day> --weight X` in place of `nutrition record`, note it in
the record, prompt `/goals` to get set up, and go straight to the sleep
gate below.

**Record the reading.** Turn the Food field's numbers into one reading
with `python3 -m coach nutrition record --date <check-in date>
--trend-weight X --expenditure N --target-kcal N --target-protein N
--avg-kcal N --avg-protein N --days-logged N --anchors yes|no`. Pass
only what the reply gave; without an app, pass `--scale-weight` (the
mean of the week's morning weigh-ins) and `--avg-protein` if they track
it as an observed weekly average. Keep one-day estimates in `--note`,
not `--avg-protein`; anchors alone supply no grams. Weights are in
`[athlete] bodyweight_units`. A reading already on file for the date exits 1: re-run with `--replace` only to correct it.
Then run `python3 -m coach nutrition status` and work from its output.
The numbers on file (phase, target trend rate, protein floor, target and
stretch, anchors, any override) are in `config.toml`'s `[nutrition]`
table; `nutrition status` returns them.

**Weight trend.** Read `data.trend.basis`, `span`, `days`, rate and
`target_rate_per_week` from `nutrition status`. A `fallback: true` trend
is raw scale weight standing in for an app trend that covers under 14
days: say so. `sources` and `python3 -m coach bodyweight list` name where
each weight came from. Confirm the observation:
source, dates, comparable weigh-ins, logging and temporary weight shifts.
The endpoint trend is not proof that every intervening day was measured.
One odd week does not automatically change calories; use a supported
**2–3-week trend** and the athlete's agreed phase intent.

**Maintenance recomp targets zero**, whether chosen voluntarily or by
the sleep gate. For example, a confirmed -0.45 kg/week over 14 days is a
review of the maintenance estimate, not automatically desirable cut progress. Sustained
positive drift gets the converse review. Ask whether continued loss is
intended: if so, route to `/goals` to review the goal/phase and sleep gate.
For any phase, a changed goal, reached phase trigger or trend contradicting
the plan also goes to `/goals` before changing the phase.

**With MacroFactor**, the app owns calorie adjustments: review its trend,
confirm complete logging and let it work. Never supply a competing target
or calorie adjustment. **Without an app**, after confirming a sustained
miss of the agreed rate, propose the existing ~100–150 kcal/day adjustment
in the direction the trend needs (at maintenance: upward for maintenance
loss, downward for maintenance gain). This small
step is a coaching heuristic, not a new weight-noise cutoff. Obtain the
athlete's yes before editing `[nutrition] kcal_target` and recording why
in `profile.md`. Never re-derive an equation here; a fresh estimate or
phase change belongs in `/goals`.

**Act on each flag** in `data.flags`:

- `protein_floor_raise`: average protein met the floor at the two most
  recent readings since `floor_since`. Propose raising the floor to
  `proposed_floor_g` (the step, capped at the target). With the
  athlete's yes, set `floor_g` to `proposed_floor_g` and `floor_since`
  to `proposed_floor_since` (the day after the latest counted reading,
  so this week's reading, taken under the old floor, doesn't count
  toward the next raise) in `[nutrition.protein]` in `config.toml`;
  MacroFactor users raise their app setting only if below the new floor;
  retain a compatible higher setting. Review any active protein override
  before changing agreed values.
  No flag: the floor stays. Missing it never lowers it; only `/goals`
  lowers it.
- `app_protein_mismatch`: the app's protein target is below the floor.
  Review increasing it to at least the floor, unless the active override
  covers protein. The floor is a minimum commitment, the target a coaching
  aim, and the app setting and actual intake may be higher.
- `protein_unmeasured`: three consecutive no-app readings since
  `floor_since` have no measured weekly protein average and the floor is
  below target. Offer optional calibration, explicit `/goals` review or
  a deliberate hold. Anchor adherence cannot qualify a numerical raise
  (rn:protein-energy-deficit.20).
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

**Sleep gate.** During a deficit or while `pending measurement`, follow
`reference/nutrition-sleep.md` for manual/tracker evidence, activity setup,
trailing 14-day coverage, the retained heuristic and profile provenance.
Complete manual coverage resolves pending to the actual result; a period
mean stays self-report and supplies no individual short-night count.

**Deep tier, body composition:** when the reply carries a reading, read
it against the goal or phase trigger that uses it and against the last
reading. A trigger that fires sends the athlete to `/goals`.

If a dated plan in `nutrition/` covers (part of) this window, the Food
field's habits question said how it went: note learnings for the next
`/meal-plan` run (recipe-bank changes belong in `/recipes`, not here).

Record the numbers in the weight and nutrition lines of the record's
Coach's read (record.md); the readings series holds them, so they no
longer go into `profile.md`.
