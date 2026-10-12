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
day's weight. When `missing` names an input, ask for it and run again,
and pass on any warning it gives.

**Choose `--activity` from the whole day, not a step count.** Ask about
the job (seated, on their feet, physical), everyday walking, and how
long and how hard each training session or sport is. The three levels
are lifestyles (rn:protein-energy-deficit.15), as `--help` describes:
`sedentary` is sedentary or lightly active, which includes a seated job
with everyday walking and two or three lifting sessions a week;
`active` needs an on-your-feet job or about an hour of
moderate-to-vigorous exercise a day; `vigorous` is hard physical work
for several hours a day, or an on-your-feet job plus about two hours of
strenuous exercise a day. When the week sits between two, name both,
pick the closer one and say why.

Say plainly the estimate is a rough starting point: each level is a
range of lifestyles, not a measurement of this athlete
(rn:protein-energy-deficit.15), and the weight trend corrects it
(rn:protein-energy-deficit.16). After that, calories
change **only from the weight trend**: when a 2–3-week trend misses the
target rate, `/check-in` moves the target by ~100–150 kcal/day in the
direction the trend needs. A new estimate comes only with a new phase.
State the protein numbers and how to track both.

**Age input:** reuse `[athlete] birth_year` through `python3 -m coach config
show`. Its `age` is approximate because the birthday is unknown. When this
calculator needs `--age`, confirm the actual current age from that estimate
(or ask if unknown); pass the confirmed value under the calculator's existing
bounds. A missing birth year never supplies zero or an assumed adult age.
