# Output the nutrition setup

**MacroFactor users:** give exact setup steps — goal type
(gain/lose/maintain; recomp is maintain), rate, macro program, the
**protein setting at or above the floor**, and **calorie shifting** so
higher-output days (per the schedule in `profile.md`) get more calories
if the athlete wants that. Their app UI is the source of truth — walk it
with them and adjust names to what they actually see. Then state the
logging rule: log every day; on a day they couldn't track, log an
estimate of the day or the missed meal; never leave a day half-logged.
Calories are whatever the app sets; never state a calorie target or
band of your own.

**Everyone else:** run `python3 -m coach nutrition targets --app none`
with `--sex`, `--age`, `--activity` and `--phase PHASE:RATE` for the
phase starting now, and quote its `calories` estimate with the `method`
and inputs shown. Run it again when each later phase starts, from that
day's weight. `--help` describes each activity level; ask the athlete
which fits their week. When `missing` names an input, ask for it and
run again, and pass on any warning it gives. Say plainly it's a rough
starting point. After that, calories change **only from the weight
trend**: when a 2–3-week trend misses the target rate, `/check-in` moves
the target by ~100–150 kcal/day in the direction the trend needs. A new
estimate comes only with a new phase. State the protein numbers and how
to track both.
