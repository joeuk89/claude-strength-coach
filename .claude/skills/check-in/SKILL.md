---
name: check-in
description: Use when the athlete wants a training check-in or progress review — weekly by default, with a deeper review when one is overdue, a light week is being proposed, or adherence has dropped. Triggers include "/check-in", "check in", "weekly check-in", "progress review", "how's my training going", "let's review my progress".
---

# Training check-in

Act as the athlete's coach reviewing their training. Two tiers: a
**weekly** check-in (~10 minutes — adherence, weight + nutrition, week
ahead) and a **deep review** (the full block-level look). Both open with
one **Sunday message** the athlete answers in one reply. The output is a
dated record in `check-ins/` plus any agreed updates.

If `profile.md` doesn't exist, stop and run `/setup` first.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

**Loads come from `coach` output; quote them.** A load read from the
log is a Hevy value: `python3 -m coach units convert --mode <load mode>
--from-hevy-kg <value>` turns it into the athlete's number. Never
convert or split a load by hand.

## 1. Read the context and pick the tier

Read `profile.md` (including **Coach's notes**), `python3 -m coach
program show` and `python3 -m coach state show` (rotation, block, any
one-off week), `routine/program.md` for the program at a glance, and
the newest file in `check-ins/` (plus the newest **deep** one, if the
newest is weekly).

Run a **deep** check-in when any of these is true, otherwise run **weekly**:

- **6+ weeks** since the last deep check-in. Records without a tier marker
  count as deep; the first check-in ever runs deep.
- **A light week is being proposed** (step 4: the hard-week count
  reached the ceiling, or two fatigue triggers fired).
- **The adherence trigger fires** (step 4: under 70 %).
- The athlete asks for one.

The coming week being a deload is not a trigger on its own. Before
sending the Sunday message, run `python3 -m coach block close --week
<this week> --dry-run`: its `deep_review` (`due`, `reasons`) applies
these rules to the log. If the reply changes the picture (a second
fatigue trigger, a coach-led session that didn't happen), the real close
in step 4 says so: switch to deep and tell the athlete.

The Sunday message's first line names the tier and why; the athlete can
override. Mark the tier in the record's title line.

**Run mode.** With `mode = "run"` in `config.toml`'s `[coaching]`
table, the athlete wants their own program run as written. Progression,
return weeks, validity checks, light weeks and every `block` flag work
as in coach mode. Structural flags (`restructure_required`,
`add_session_type_blocked`, `volume_undershoot`, `session_volume_high`)
come out of `checkin prepare` and the `structure` commands at `info`,
their message starting "run mode: ": mention them as information only.
Still report adherence from `structure adherence`, but do not present a
restructure or a smaller schedule and do not call `structure decide`,
unless the athlete asks for a restructure themselves. The adherence
trigger never makes a run-mode check-in deep. Skip the deep tier's
structure review (weekly balance, junk volume, what the next block
should change), propose no swap, new session or redesign, and never
offer `/new-program`.

## 2. Pull the data

The window runs from the last check-in to today (excluding workouts the
last record already covered) — normally ~1 week. **Deep tier:** for the
trend analysis, extend the lookback to the last deep check-in (~6 weeks)
— one week can't show a trend. **Adherence and the hard-week count** need
more history: read the check-in records and logs back as far as step 4
needs.

**Gap check.** Count the days from the last lifting workout of any
kind — solo, or coach-led as the log or the reply shows it — to the
first session of the coming week, the same count program-week makes.
Over 10 days means the coming week is a **return week** under the
return rule in `CLAUDE.md` "Coaching principles": say so in the Sunday
message's first line ("… — 16 days off by Tuesday's session, so next
week is a return week"). An `ill` miss tag or reported illness in the
gap brings in that rule's illness conditions too. Program-week applies
the rule.

**With Hevy:** run `python3 -m coach hevy pull`, then `python3 -m coach
history sync` to resolve the new workouts into `data/history/` (it lists
any exercise it could not match in `data.unresolved`), then `python3 -m
coach hevy status` for the cache's age and counts. Read the window's workouts
from the cache (`.coach/cache/hevy/workouts/`). **Read every workout's
`description` and each exercise's `notes`** — these are the athlete's
own words on how the session went (fatigue, sleep, a target that was
too high, a niggle, why sets were dropped). They're the readiness
signal the numbers can't show, so quote them in the analysis and let
them shape the decisions. The cached body measurements are a fallback
weight source only.

**STALE check (Hevy).** Run `python3 -m coach overlay current` and, with
an overlay in force, `python3 -m coach routines verify --overlay <its
id>`. A routine it reports with `verified: false` and a `prescription`
change to an exercise's notes is **STALE**: it doesn't carry the
overlay in force, so it still holds older notes. A `structural` change
is an in-app edit, which program-week settles. No overlay yet → skip
the check. On a normal week the list appears in program-week's coach's
brief (on a hold-steady week, its close-out), which reuses this
verify; the pass rewrites every routine in the span either way. Skip
the check when the coming week is a deload or other one-off week —
`/one-off-week` writes fresh temp routines for it.

**Without Hevy:** the workouts are in the manual log, one `log add` per
workout the athlete reported. Log any they report now the same way
(`CLAUDE.md` "Hevy" → "No Hevy?"), then run `python3 -m coach history
sync` so `checkin prepare` pre-fills the Sunday message from them. Read
each logged workout's `notes` as you would a Hevy description.

**Coach-led sessions (PT, classes) are often logged worse than solo
sessions** — the Coach-led field of the Sunday message confirms which
ones happened. Never compute adherence from the API alone. Check Coach's
notes for this athlete's known logging habits.

## 3. Send the Sunday message

Send **one** message that pre-fills what the log shows and asks only what
it can't, then wait for the athlete's single reply. They answer by number.
This replaces an interview: no question-by-question turns.

Run `python3 -m coach checkin prepare` and send its `data.text` as the
Sunday message. You may tighten the wording, and drop a field that
cannot apply or that the athlete's opening message already answers,
renumbering the rest. Never change the card's figures or the order of
the fields. `data.card` holds the same week as data: the
window (the day after the last record to today), each planned session
trained, missed (with any tag on file) or trained but not logged, with
durations against the session cap; each exercise's result against the
prescription; e1RM changes; flags (`convention_slip`,
`duration_over_cap`, `stale_routine`); and each Hevy routine's state
(`edited_in_app` routines end the card with a keep-or-replace field,
settled in program-week). The card picks the tier (`mode`, with
`tier_reasons`: no record yet, or the last deep record 42 or more days
old). When step 1 picks deep for a reason the card can't see, run it
with `--tier deep`; `--tier weekly` overrides a due deep review. Mode
`catch_up` means more than 10 days since the last check-in: send the
catch-up card instead (**Catch-up card** below).

The first line names the window and the tier with its reason. Then the
fields, always in this order:

1. **Sessions** — logged vs. planned for the window, day by day. List each
   planned session with no logged workout and ask for one tag per miss:
   `time / sleep / ill / family / skipped / other`. Optional sessions need
   no tag. Ask for anything trained but not logged.
2. **Coach-led** — ask what each coach-led session in the window covered.
   State what its log shows and the inferred rotation position for
   confirmation.
3. **Runs** — with an activity source, the card states the window's
   runs from `python3 -m coach cardio week` (count, distance, quality
   runs) and any planned activity `cardio reconcile` found missed, and asks
   only for runs no source logged. Without one, ask count and total
   distance.
4. **Sleep** — with a sleep source and enough tracked nights, the card
   states the last seven nights (average and short nights) and asks how
   it felt. Otherwise ask, in one line: "average hours a night (from
   your watch or phone if it tracks sleep), and how it felt".
5. **Niggles** — anything new? Name each open niggle-log row (`watching`
   or `easing`) and ask whether it is quiet or still there.
6. **Food** — the food questions, worded as `python3 -m coach nutrition
   status` gives them in `data.questions`, one line each:
   1. Readings: the app's numbers (trend weight · expenditure · targets
      (kcal/protein) · 7-day average (kcal/protein) · days logged), or,
      without an app, this week's morning weigh-ins and average daily
      protein if they track it. A dashboard screenshot is accepted.
   2. Habits: anchors most days (y/n)? Anything in the plan that didn't
      work? The anchors ask is left out when no anchors are on file.
   3. Next week: food exceptions — who cooks which nights, office-day
      changes, meals out. Asked **only when a standing weekly template
      exists** (`[nutrition.template]` in `config.toml`); `data.questions`
      leaves it out otherwise.

   Nutrition not enabled (`data.enabled` is false): one morning scale
   weight instead.
7. **Next week** — anything different: travel, schedule, kit, illness?

**Leave out a field that cannot apply** and renumber the rest from 1: no
coach-led sessions in the window → no Coach-led field; no cardio in the
athlete's week → no Runs field. **A fact the log already answers is
stated for confirmation, not asked.** If the athlete's opening message
already covers the fields, don't send the template; leave out any single
field it already answers.

**Deep tier:** the same message. Any deep-only asks follow the last field,
numbered on.

**Body composition** (waist, body fat, progress photos) is a deep-only
ask, never a weekly one. Ask it only when both hold:

- the goals or a phase trigger in `profile.md` use waist, body fat or
  photos, or the phase is a cut or recomp; and
- no deep record has a reading yet, or the last reading is 4 or more
  weeks old (the newest deep record's **Body composition** line says).

Ask for waist, a body-fat reading if they have one, and their own
one-line read of their progress photos. **Photos stay with the athlete
and never go into the repo** — record only their read. A reading the
reply leaves out is recorded once as "not supplied" and not asked again
before the next deep check-in.

**Rotation position.** If the program rotates, infer where the coming
week lands and state it for confirmation — never ask it as its own
question. Sources, in order: the coach-led session's log,
`rotation.position` in `state show`, the newest check-in. State
it in the Coach-led field, or in the Next week field when there is no
Coach-led field. If the sources disagree, state the first one and name
the disagreement.

**Missed sessions** get the one-word tag and nothing more: no follow-up on
the reason. A miss the reply leaves untagged is recorded as `untagged`.

**Record the reply** in one batch before analysing it. Write the facts
it gives as a JSON list to `.coach/drafts/checkin-<date>-reply.json` and
run `python3 -m coach history annotate --input <that file>`, with
`"source": "check-in <date>"` on each:

- `{"kind": "miss", "date": D, "session_id": S, "tag": T}` for each
  tagged miss (no annotation for one left untagged);
- `{"kind": "trained_unlogged", "date": D, "session_id": S, "note": N}`
  for a planned session trained but not logged: it counts as trained,
  with no results and no e1RM;
- `{"kind": "external", "date": D, "external_id": E, "done": true|false,
  "note": N}` for each coach-led session, the note one line on what it
  covered.

Exit 1 names each annotation that doesn't fit; fix the file and run it
again. Days the reply says the athlete was ill, injured or away go in as
status days: `python3 -m coach status-days add --kind ill|injured|travel
--from D --to D --note "<one line>" --source "check-in <date>"` (leave
out `--to` while it is still going on; `status-days end <id> --date D`
closes it later, `status-days withdraw <id> --reason <text>` takes back a
wrong one). An ill status day in the gap brings in the illness return
rule, exactly as an `ill` miss tag does. Then run `checkin prepare`
again: the card now carries the reply.

**At most one follow-up turn**, and only for a gap that blocks
programming: an unresolved rotation position, a new niggle's severity, or
nutrition numbers you can't read. Ask every such gap in that one turn.
Record any other gap once as "not supplied" and move on.

**Catch-up card.** When `data.card.mode` is `catch_up`, this is a
catch-up check-in: send `data.text` as the whole message. It has no
per-session fields: one summary row per week since the last record, the
return week (`card.catch_up.return_week`: band, days off, load and set
change, RPE cap, each session's lines and flags), three numbered
questions (the gap, now, next week), then the write line and "Reply ok
to accept all of this, or answer 1–3." Then stop and wait for the
athlete's reply. A catch-up never runs deep; when one was due, the card
has `deep_deferred: true` and the next check-in runs deep, with the
reason "deferred from catch-up <date>". Write its record with `checkin
skeleton` as in step 6; its title says `(catch-up)`.

- **One tag for the whole gap:** run `python3 -m coach checkin tag-gap
  --tag <tag>`. It writes one `miss` annotation per untagged missed core
  session in the window. Tags per session go through `history annotate
  --input` as above. Then run `checkin prepare` again: an `ill` tag
  brings in the illness rule (`return_after_illness`, the first session
  capped), so the return week changes and is presented again.
- **"ok" alone** is a complete check-in: misses stay untagged, nothing
  new to report, and the return week as shown, written to Hevy (no
  Hevy: approved only). Run
  `python3 -m coach propose week --week <return_week.week>` and compare
  its `data.lines_digest` with the card's `return_week.lines_digest`.
  Equal: run `python3 -m coach propose finalize --proposal <id>`, then
  `python3 -m coach overlay approve <id>` and `python3 -m coach routines
  push --overlay <id>` as program-week's write step describes, without
  asking again. Different: something changed since the card, so present
  the new return week and wait for the reply.
- **A reply that mentions illness, travel or no kit:** present `python3
  -m coach checkin return-brief` output as the coach's brief. Use
  `--proposal <id> --reason ill` (or `layoff`) for a proposed return
  week, or `--overlay <id> --reason travel|no_kit` for a one-off week
  you built with `overlay build`. Its `data.text` is the return
  brief: the gap, what the return week does, each session's lines,
  what happens after, and the write line; `ill` adds the illness rule's
  safety lines from `CLAUDE.md`. If it returns warnings, the lines do
  not carry the return band's change or the illness cap, and the brief
  leaves that claim out: fix the week as each warning says (propose it
  again, or rebuild the overlay), then run `checkin return-brief` again
  before presenting. Edit the words if you like, never the figures. One
  "go" approves it and every write its last line names.

## 4. Analyze — plan vs. reality

Show the athlete only loads in their own units, from `units convert`.
**Judge against the effective prescription**, not the base plan — the
overlay in force for each day (`python3 -m coach overlay current --date
<day>`): the overlay `/program-week` wrote (kind `weekly`), or the deload
or one-off overlay `/one-off-week` wrote. With an overlay, adherence is
concrete: did the athlete hit the prescribed load × reps @ RPE?

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
  For priority protocols the program holds only in prose: did they
  happen as written? Watch for this athlete's known drift patterns
  (Coach's notes).

**Deep tier** — all of the above, plus:
- Per main lift: loads/reps across the window, and the e1RM trend from
  `python3 -m coach stats e1rm --since <last deep check-in>` (each
  lift's series, best and latest change) — trend, not gospel. Flag
  stalls (same load+reps 3+ sessions) and progression-scheme violations.
- Missed sessions since the last deep check-in: `python3 -m coach
  checkin misses` counts them by tag and by session (the deep card's
  `misses` holds the same tally). A tag that keeps coming back (`time`,
  `sleep`) is a schedule or recovery question for Block planning.
- **Sanity-check dumbbell loads before reading anything into them.** An
  exact-2× (or ½ ×) step in a dumbbell exercise at unchanged reps *and*
  unchanged RPE is a logging-convention slip, not a strength change —
  Hevy stores the combined total across both arms, and single-arm work is
  the exception. `python3 -m coach stats audit` lists every such step in
  the last eight weeks, with the sibling exercises that jumped on the
  same date: a slip usually shows up in more than one lift at once. An
  open candidate stays out of the e1RM series until it is settled. When
  history looks contaminated, confirm the actual per-hand weights with
  the athlete and record the answer with `python3 -m coach history
  annotate`: `--kind discount --workout <id> --exercise <id> --reason
  <text>` for a slip, `--kind confirm` for a real jump, `--kind repair
  --set <n> --field <field> --value <v>` for a mistyped value. Say which
  prescriptions were derived from the bad data.
- Exercise drift vs. the plan — structural drift means `/hevy-sync` is
  due; offer it (Hevy users only).
- Intensity honesty: the RPE drift check on each exposure in the
  window, same scope and threshold — compound lifts and recovery-capped
  sets, 1 or more over the target on 2 or more working sets of one
  exposure. Sustained drift means drift in consecutive exposures of the
  same lift. Isolation drift stays one summary line, not a decision.
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
  each item raised before today with the athlete — `python3 -m coach
  followups resolve <id>`, `python3 -m coach followups drop <id>
  --reason "<why>"`, or `python3 -m coach followups defer <id> --to
  <date> --kept`. Then put the text of `python3 -m coach followups
  render --deep --date <today>` in Block planning; exit 1 names each
  item still without a disposition dated today. A question to come back
  to, at any check-in, goes in with `python3 -m coach followups add
  --text "<question>" --review-at <date> --source "check-in <date>"`.
- Niggles: run `python3 -m coach niggles list --open`. Review each
  open row's status with the athlete; list each `chronic` row in Block
  planning without asking for a resolution — it is a lasting
  limitation.

**Both tiers — the hard-week count.** Run
`python3 -m coach block close --week <this week> --readiness poor|ok
--sleep poor|ok` (readiness from the reply and the workout notes, sleep
from the Sleep field; leave a flag out when the reply doesn't say; add
`--deep` on a deep check-in). It classes every week since the last close
by the rules in `CLAUDE.md` "Coaching principles" → Fatigue management,
updates the count, checks the four fatigue triggers (compound RPE drift
two sessions running and an `aggravated` niggle come from the data), and
proposes, watches or skips a light week. It writes `data/blocks.json`
and `block` in `data/state.json`, re-renders `routine/program.md`, and
prints the `status_line`, `deep_review` and the block flags
(`light_week_due`, `light_week_skipped`, `fatigue_watch`,
`deep_review_due`). Run it again for the same week after a correction,
or after step 7 changes a niggle's status: a second close of the same
week replaces its entry.

**Both tiers — adherence.** Adherence = sessions trained ÷ sessions
planned over the **trailing four ordinary weeks**:

- Judge each week against the overlay in force that week. Coach-led
  sessions count, as the replies confirmed them; optional sessions are
  left out; a shortened session counts as trained.
- An **ordinary week** is any week except a deload or other light week,
  a one-off week (illness, travel, limited kit), or a week inside a
  layoff of 11+ days. Skip those and reach further back, at most 12
  weeks. Fewer than four ordinary weeks in that span → no trigger yet.

`python3 -m coach structure adherence` works this out and raises the flags below; `python3 -m coach structure decide` records the athlete's answer and prints the decision line.

Adherence thresholds are coaching heuristics, not research cut-offs:

- **Under 80 %:** propose no new recurring session — no new session or
  weekly slot, conditioning and optional sessions included — and push
  back if the athlete asks for one. Exercise swaps within a session are
  not affected. An athlete override is recorded with the adherence
  decision line (step 6), naming the session it adds.
- **Under 70 % — the adherence trigger.** The check-in must present a
  smaller schedule in its decisions:
  - a Day / Session table sized to the average sessions actually trained
    per week over the four weeks, rounded up, minimum two;
  - a before/after table of weekly hard sets per muscle, kept equal;
  - each session within the time limits in `profile.md` and about 11
    fractional hard sets per muscle (an indirect set counts as half);
  - anything trimmed, named.

  The athlete adopts, declines with a reason, or defers to a date.
  Record it with the adherence decision line (step 6), which also sets
  when the proposal comes back.

## 5. Weight & nutrition check (every check-in)

**The framework rule:** for an athlete using a nutrition app, this
check-in gets **complete logging** into the app and reads the app's
numbers out. It **never states its own calorie target or calorie band**
and never runs a parallel calorie model. Fewer than 7 days logged → ask
for every day to be logged, with an estimate of the day or the missed
meal on a day they couldn't track and no half-logged days
(MacroFactor's guidance, in `/goals`). Record the days logged either
way.

**Record the reading.** Turn the Food field's numbers into one
reading:

```bash
python3 -m coach nutrition record --date <check-in date> \
  --trend-weight X --expenditure N --target-kcal N --target-protein N \
  --avg-kcal N --avg-protein N --days-logged N --anchors yes|no
```

Pass only what the reply gave; without an app, pass `--scale-weight`
(the mean of the week's morning weigh-ins) and `--avg-protein` if they
track it. Weights are in `[athlete] bodyweight_units`. A reading already
on file for the date exits 1: re-run with `--replace` only to correct
it. Then run `python3 -m coach nutrition status` and work from its
output. The numbers on file (phase, target trend rate, protein floor,
target and stretch, anchors, any override) are in `config.toml`'s
`[nutrition]` table; `nutrition status` returns them.

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

- `protein_floor_raise` — average protein met the floor at the two most
  recent readings since `floor_since`. Propose raising the floor to
  `proposed_floor_g` (the step, capped at the target). With the
  athlete's yes, set `floor_g` to `proposed_floor_g` and `floor_since`
  to `proposed_floor_since` (the day after the latest counted reading,
  so this week's reading, taken under the old floor, doesn't count
  toward the next raise) in `[nutrition.protein]` in `config.toml`;
  MacroFactor users set the app's protein to the new floor the same
  day. No flag → the floor
  stays: missing it never lowers it; only `/goals` lowers it.
- `app_protein_mismatch` — the app's protein target is not the floor.
  Have the athlete set the app to the floor, unless the active override
  covers protein.
- `logging_incomplete` — fewer than 7 days logged: ask for every day to
  be logged, as in the framework rule above.
- `override_expired` — on or after its expiry date the override ends:
  remove `[nutrition.override]` from `config.toml`, tell the athlete
  they're back on the app's numbers (or, without an app, the calorie
  target on file), and record it. Its exit condition firing earlier ends
  it the same way. Renewal is not done here: it needs `/goals` with a
  fresh reason.
- `override_renewed_twice` — flag it in the record at every check-in
  while it stands, as a sign the plan itself needs changing.
- `no_recent_reading` — nothing recorded in the last 14 days: record
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
field's habits question said how it went — note learnings for the next
`/meal-plan` run (recipe-bank changes belong in `/recipes`, not here).

Record the numbers in the weight and nutrition lines of the record's
Coach's read (step 6); the readings series holds them, so they no longer go into `profile.md`.

## 6. Write the record

Run `python3 -m coach history sync`, then `python3 -m coach checkin
skeleton --date <today>`. It writes `check-ins/<today>.md`, titled with
the card's tier (`--tier` overrides), holding:

- **Week in review** — a rendered region: the window, sessions n of m
  core, the `Missed:` line with each miss's tag, the sessions, results
  and e1RM tables, and the flags; on a deep record, the misses since the
  last deep check-in. It reads synced history only, so the command warns
  when a workout in the window is not synced yet.
- **Coach's read**, **Decisions** and **Next week** — empty, for your
  prose. Deep records add **Block planning** after Decisions.

Exit 1 means the record exists. Never edit inside a rendered region:
correct the data (`history annotate`), then run `checkin skeleton --date
<today> --refresh`, which re-renders the regions and leaves every other
byte as it was. Once the week's overlay is approved (step 7), run it
with `--refresh --overlay <id>` to put the prescription in a collapsed
appendix; it also collapses a region `overlay render --into` already
wrote.

Add the cardio block with `python3 -m coach cardio render --week <the
week> --into check-ins/<today>.md`: the week's numbers, the reconcile
and the cardio flags. It is a snapshot, which no check re-renders, so
run it again only when the week's data changes before the record is
committed.

Write the prose, each section short:

- **Coach's read** — 1–2 sentences on the state of the week, then what
  the region can't say: adherence as the reply confirmed it, notable
  sets, anything off-plan; the athlete's read (sleep, runs, niggles, next
  week — a field the reply didn't answer reads "not supplied"); and
  weight and nutrition:

  ```markdown
  Weight (trend or scale) · targets · adherence. Trend vs. target rate — on track?
  Protein: <7-day avg> g vs floor <g> (<n> of 2 toward a raise | raised to <g> | under) · days logged <n>/7 · anchors most days: y/n
  Override: none | active, expires <date> | expired <date> | renewal flagged · Sleep gate: <status> (deficit only)
  ```

- **Decisions** — first the block status line, then what changed and why
  (or "stay the course"), anything deferred, and the adherence decision
  line when it applies:

  ```markdown
  Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>
  Adherence trigger: <n> % over 4 weeks: adopted | declined: <reason> | deferred to <date>
  ```

- **Next week** — a Day / Session table, one-off changes called out, and
  one closing line: the focus of the week.

Keep the prose outside the regions under 600 words (1,000 on a deep
record); `python3 -m coach check` warns past that.

**The block status line** opens Decisions: copy `status_line` from the
last `block close` or `block decide` you ran (`python3 -m coach block
status` prints it again). Never write it by hand.

**The adherence decision line** goes in Decisions only when the
adherence trigger was presented or an under-80 % override was agreed, in
that fixed shape, e.g. `Adherence trigger: 58 % over 4 weeks: deferred to
2026-11-02`. An override adds the session after the outcome: `Adherence
trigger: 76 % over 4 weeks: adopted (override: adds Sat conditioning)`.
A **declined** proposal isn't presented again until four ordinary weeks
have passed since the decision; a **deferred** one is presented again at
the first check-in on or after its date; an **adopted** one goes to
`/new-program`'s redesign path and isn't presented again for four
ordinary weeks. These rules and the hand-off apply only to the
smaller-schedule decision. An override line (one with `(override: …)`)
records the added session only: it never holds back or starts the
under-70 % trigger, and never goes to `/new-program`.

Deep records use the same skeleton titled `(deep)`, with **Coach's read**
expanded to the full analysis (e1RM trends per lift, drift, balance,
intensity honesty) and a **Block planning** section: the light-week
outlook from the hard-week count, whether the goals/phase plan in
`profile.md` is stale (if so, prompt `/goals`), what the next block
should emphasize, and the research line (step 4). When body
composition applies (step 3), Block planning ends with one line that
says when the next reading is due — the next check-in reads it:

```markdown
**Body composition:** waist <reading, "not supplied" or "not due"> · body fat <reading, "not supplied" or "not due"> · photos: <"athlete's one-line read", "not supplied" or "not due"> · **Last reading:** <date> · **Next reading due:** first deep check-in on or after <last reading + 4 weeks>
```

A reading taken today makes today the **Last reading** date. "Not
supplied" means it was asked and the reply left it out; "not due" means
it wasn't asked (step 3). Either way, carry the previous **Last reading**
date forward; with no reading ever, write "none" and make the next deep
check-in the due one.

## 7. Act on it

- **Hold-steady week** (defined in program-week step 4): present no
  separate check-in summary — it and the coach's brief collapse into
  program-week's short brief. Deep check-ins and deload weeks never take
  that path.
- Otherwise, propose adjustments with rationale and trade-offs. **Only
  change the program after the athlete approves** — on normal weeks the
  change lands in `data/program.json` via program-week's write step
  (below); re-check the day before and after any edited day and the
  program's weekly balance.
- Update `profile.md`: e1RMs, watch notes, and `_Last reviewed_` when
  they move (deep tier refreshes the whole file). Add or retire
  **Coach's notes** as patterns emerge or resolve — with the athlete's
  confirmation.
- **Maintain the niggle log** in `data/niggles.json` with the `niggles`
  commands; statuses `aggravated` / `watching` / `easing` / `resolved`,
  and `chronic` for a lasting limitation. New complaint → `python3 -m
  coach niggles add --area "<where>" --status <status> --pattern
  <patterns> --note "<report>"` (`--exercise` and `--activity-kinds`
  name anything else it affects); repeat mention → `python3 -m coach
  niggles update <id> --mention --status <status> --note "<report>"`;
  confirmed gone → `python3 -m coach niggles resolve <id>`, which
  **keeps the row** — recurrence is the signal this log exists to
  catch. Agree with the athlete the limit an active niggle sets and add
  it with `--constraint` (`rpe_cap=7`, the recovery cap;
  `no_added_load`; `load_cap=<n>`): `propose week` applies it to every
  matching line while the status is `aggravated` or `watching` (always,
  for `chronic`) and names the niggle in `constraint_applied`. Escalate
  — recommend a qualified professional and program around it
  meanwhile, never diagnose — when `python3 -m coach niggles list`
  gives a row an `escalate` reason (three check-ins running, or worse
  to `aggravated`), or when a niggle interferes with prescribed
  training.
- **Update `data/state.json`:** the confirmed `rotation` (`position`,
  `confirmed`, `confirmed_at`) if the program rotates. `block` is
  written only by the `block` commands (step 4 and below). Then run `python3 -m coach program validate`,
  `python3 -m coach state show` (it refuses an invalid state) and
  `python3 -m coach program render`, and write the block status line
  into the record's header (step 6).
- **A light week proposed** at the ceiling or on two triggers: present
  it with its reason. Record the answer with `python3 -m coach block
  decide --outcome adopted` (add `--type` and `--reason` to choose
  another type) or `--outcome declined --reason "<why>"`; at the
  ceiling, the next close proposes it again. To call a light week
  nobody proposed, use `--outcome adopted --type <type> --reason
  "<why>"`. Agreed → invoke the **one-off-week** skill in deload mode
  (below).
- **Adherence trigger adopted** (the smaller schedule, not an
  override) → hand off to `/new-program`'s redesign path with the agreed
  smaller schedule. Under 80 % adherence (step 4), propose no new
  recurring session, here or in program-week.
- On a normal (non-deload) week, once decisions are agreed, invoke the
  **program-week** skill — it computes per-exercise targets for the
  coming week, writes them to Hevy, and fills this record's "The week
  ahead" section. **Decisions agreed at this check-in don't pre-approve
  the week** — program-week still presents its coach's brief and waits
  for the athlete's reply before writing anything. One "go" to that
  brief approves the week and every write its closing line names — the
  Hevy routines and any structural program edits — so don't ask
  again before writing. Structural routine changes agreed today ride
  along in its write step; `/hevy-sync` stays for reconciliation outside
  the pass.
- When a light week is agreed, invoke the **one-off-week** skill
  (deload mode) to build it with the `command` `block decide` printed —
  its schedule and sessions fill this record's "The week ahead"
  section, and it handles the Hevy writes. The count resets when the
  next check-in closes that week.
