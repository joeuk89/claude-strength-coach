# Analyze: plan vs. reality

Show the athlete only loads in their own units, from `units convert`.
**Judge against the effective prescription**, not the base plan: the
overlay in force for each day (`python3 -m coach overlay current --date
<day>`), whatever programming pass wrote it (kind `weekly`, `midweek`,
`deload` or `one_off`). With an overlay, adherence is concrete: did the
athlete hit the prescribed load × reps @ RPE?

**Weekly tier** — keep it light:
- Adherence: run `python3 -m coach stats adherence --overlay <id>` for
  each overlay in the window. It gives each planned session's status
  (trained, missed with its miss tag or `untagged`, upcoming) and each
  exercise's result against the prescription (hit, under, over,
  missing). Sessions trained vs. planned, including coach-led ones as
  the reply confirmed them (that's the "n of ~m" in the record header);
  which days slipped, with their miss tags.
- Cardio, kept separate from lifting adherence: `python3 -m coach cardio
  week --week <the week>` for runs, conditioning and other activity, with
  each one's quality and session-RPE load (information only, never a
  ratio); `cardio reconcile --week <the week>` for planned against
  logged when the cardio tier is `review` or `program`; and `cardio
  flags --week <the week>` (`cap_breach`, `run_volume_spike`,
  `quality_stack`, `sleep_debt`, `status_active`, `niggle_link`, and
  `collision` from the program's interference rules). Name each flag in
  the Coach's read.
  An `ambiguous` reconcile row has no confident match and lends no plan
  its quality: show the athlete its `candidate_ids`, and once they say
  which run was which plan, run `python3 -m coach cardio associate
  ACTIVITY_ID --planned-id PLANNED_ID`. A `duplicate` row is a session
  another source also planned and the athlete did: never call it missed.
- When an outside running plan or endurance event is relevant, consult
  `reference/runner-review.md` for its strength and fuelling claims,
  using the Sunday reply. Otherwise skip runner-specific research and
  fuelling questions.
- Notable sets: PRs, rep-range top-outs due a load increase, anything way
  off prescription.
- RPE drift: check only **compound lifts** (multi-joint squat, hinge,
  lunge, press and pull patterns) and sets carrying a **recovery cap**.
  An exercise drifts when logged RPE is 1 or more over the target on 2
  or more working sets of one exposure. Drift on isolation work gets one
  summary line in the record ("isolation RPE ran about 1 high on curls
  and raises") and never drives a decision.
- Priority work: `python3 -m coach structure priority` gives each
  priority lift's KPI now, its trend, and its exposures per week
  against plan. Name each `priority_exposures_missed` flag (a planned
  exposure missed with no floor dose in its place) in the Coach's read.
  A KPI with `unavailable` quotes its message as the reason its newest
  exposure gave no e1RM; with no `now`, judge that lift by its logged
  reps and load. A `now` with
  `basis` `total_system` counts body mass: say "total system mass" with its number.
  For priority protocols the program holds only in prose: did they
  happen as written? Watch for this athlete's known drift patterns
  (Coach's notes).

**Deep tier** — all of the above, plus:
- Per main lift: loads/reps across the window, and the e1RM trend from
  `python3 -m coach stats e1rm --since <last deep check-in>` (each
  lift's series, best and latest change): trend, not gospel. Light-week,
  return-week, reduced and over-cap exposures stay out of the series; read
  them in `observations`, and the card's `e1rm_notes` says why. A
  `total_system` point counts body mass: say "total system mass" with
  its number. `unavailable` lists lifts with no estimate and why. Flag stalls
  (same load+reps 3+ sessions) and progression-scheme violations.
- Missed sessions since the last deep check-in: `python3 -m coach
  checkin misses` counts them by tag and by session (the deep card's
  `misses` holds the same tally). A tag that keeps coming back (`time`,
  `sleep`) is a schedule or recovery question for Block planning.
- **Sanity-check dumbbell loads before reading anything into them.** An
  exact-2× (or ½ ×) step in a dumbbell exercise at unchanged reps *and*
  unchanged RPE is a logging-convention slip, not a strength change
  (`CLAUDE.md` "Hevy" has the dumbbell rule). `python3 -m coach stats
  audit` lists every such step in the last eight weeks, with the sibling
  exercises that jumped on the same date: a slip usually shows up in
  more than one lift at once. An open candidate stays out of the e1RM series until it is
  settled. Confirm the actual per-hand weights with the athlete and
  record the answer with `python3 -m coach history annotate`: `--kind
  discount --workout <id> --exercise <id> --reason <text>` for a slip,
  `--kind confirm` for a real jump, `--kind repair --set <n> --field
  <field> --value <v>` for a mistyped value. Say which prescriptions
  were derived from the bad data.
- Exercise drift vs. the plan: structural drift means `/hevy-sync` is
  due; offer it (Hevy users only).
- Intensity honesty: the RPE drift check on each exposure in the window,
  same scope and threshold. Sustained drift means drift in consecutive
  exposures of the same lift. Isolation drift stays one summary line,
  not a decision.
- Session durations vs. the time limits in `profile.md`, junk volume.
- Weekly balance: does the program's balance picture still match what's
  actually being trained?
- Research notes: run `python3 -m coach research status` and list every
  area its `areas` marks `expired`, with the expired note ids, in one
  line in Block planning (`Research: expired <area> (<note id>), …` or
  `Research: nothing expired`). For an expired area the coming block
  depends on, offer to refresh it as a local note (`CLAUDE.md`
  "Researching current best practice").
- Follow-ups: run `python3 -m coach followups list --open` and settle
  each item raised before today with the athlete: `python3 -m coach
  followups resolve <id>`, `python3 -m coach followups drop <id>
  --reason "<why>"`, or `python3 -m coach followups defer <id> --to
  <date> --kept`. Then put the text of `python3 -m coach followups
  render --deep --date <today>` in Block planning; exit 1 names each
  item still without a disposition dated today. A question to come back
  to, at any check-in, goes in with `python3 -m coach followups add
  --text "<question>" --review-at <date> --source "check-in <date>"`.
- Niggles: run `python3 -m coach niggles list --open`. Review each
  open row's status with the athlete; list each `chronic` row in Block
  planning without asking for a resolution: it is a lasting limitation.

**Both tiers — the hard-week count.** Run `python3 -m coach block close
--week <this week> --readiness poor|ok --sleep poor|ok` (readiness from
the reply and the workout notes, sleep from the Sleep field; leave a
flag out when the reply doesn't say; add `--deep` on a deep check-in).
It classes every week since the last close by the rules in `CLAUDE.md`
"Coaching principles" → Fatigue management, updates the count, checks
the four fatigue triggers (compound RPE drift two sessions running and
an `aggravated` niggle come from the data), and proposes, watches or
skips a light week. It writes `data/blocks.json` and `block` in
`data/state.json`, re-renders `routine/program.md`, and prints the
`status_line`, `deep_review` and the block flags (`light_week_due`,
`light_week_skipped`, `fatigue_watch`, `deep_review_due`). Run it again
for the same week after a correction, or after act.md changes a
niggle's status: a second close of the same week replaces its entry.

**Both tiers — adherence.** Adherence = sessions trained ÷ sessions
planned over the **trailing four ordinary weeks**:

- Judge each week against the overlay in force that week. Coach-led
  sessions count, as the replies confirmed them; optional sessions are
  left out; a shortened session counts as trained.
- An **ordinary week** is any week except a deload or other light week,
  a one-off week (illness, travel, limited kit), a minimum week, or a
  week inside a layoff of 11+ days. Skip those and reach further back,
  at most 12 weeks. Fewer than four ordinary weeks in that span: no trigger yet.

`python3 -m coach structure adherence` works this out and raises the
flags below; `python3 -m coach structure decide` records the athlete's
answer and prints the decision line. The thresholds are coaching
heuristics, not research cut-offs:

- **Under 80 %:** propose no new recurring session — no new session or
  weekly slot, conditioning and optional sessions included — and push
  back if the athlete asks for one. Exercise swaps within a session are
  not affected. An athlete override is recorded with the adherence
  decision line (record.md), naming the session it adds.
- **Under 70 %, the adherence trigger:** the check-in must present a
  smaller schedule in its decisions: a Day / Session table sized to the
  average sessions actually trained per week over the four weeks,
  rounded up, minimum two; a before/after table of weekly hard sets per
  muscle, kept equal; each session within the time limits in
  `profile.md` and about 11 fractional hard sets per muscle (an indirect
  set counts as half; rn:volume-frequency.2, rn:volume-frequency.3); and
  anything trimmed, named. The athlete adopts, declines with a reason,
  or defers to a date; the adherence decision line records it and sets
  when the proposal comes back.
