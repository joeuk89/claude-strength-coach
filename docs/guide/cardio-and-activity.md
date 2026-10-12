# Cardio and activity

This page covers everything the coach knows about your training outside
the lifting log: runs, rides, conditioning, sleep and other health
signals. Read it when you want runs counted in your week, when you set up
an export from your phone, or when you want to know what a cardio flag
means.

## Why there is no Garmin or Strava integration

Garmin's official API is for companies only, its unofficial clients break
whenever Garmin changes its bot detection, and Strava's API now needs a
paid plan and forbids feeding its data into an AI context. So the repo
reads cardio and health data through an **activity-source layer** (see
[the glossary](../../CONTEXT.md) under "Activity source") whose sources
are a phone health export, Hevy conditioning workouts and your own hand
entries. The full reasoning is in
[ADR 0003](../adr/0003-no-unofficial-garmin-or-strava-access.md).

Every source is optional. Manual entry is always available, and when
data is missing the check-in asks you instead.

## Turning it on

Activity tracking is off until you set `[activity] enabled = true` in
`config.toml`. While it is off, the `activity`, `wellness` and `planned`
commands exit 5 naming the key, the `cardio` commands report only lifting
and coach-led sessions, and the only cardio flag that can fire is
`status_active`.

| Key | Default | What it does |
|---|---|---|
| `enabled` | `false` | turns on the activity, wellness and planned commands |
| `wellness_in_git` | `false` | `false`: wellness lives in `.coach/activity/` (gitignored); `true`: in `data/activity/` (committed) |
| `dedup_window_minutes` | `15` | records of one kind starting this close together are one Activity |
| `precedence` | `["manual", "apple_health", "hevy_conditioning"]` | which source wins each field; list `manual` and every enabled source once |
| `gap_warn_days` | `3` | `coach check` warns when an enabled source's newest day is older than this |

`precedence` must name every enabled source plus `manual`, each once, or
`config validate` exits 5. Flipping `wellness_in_git` later is a manual
move: `coach check` fails and names the exact command to run.

## The sources

Each `[sources.<name>]` table turns on one source. The sources merge at
read time: records of the same kind whose starts fall within
`dedup_window_minutes` become one Activity, the highest-precedence source
supplies each field, and lower sources fill the fields it lacks. One
source never merges with itself, so two manual runs ten minutes apart
stay two runs.

### Manual entry

Three commands record things by hand, and they work with no other
source enabled.

```bash
python3 -m coach activity add --kind run --start 2026-10-06T07:00 \
  --duration-min 40 --distance-km 7 --rpe 8 --name "Intervals"
python3 -m coach wellness add --date 2026-10-06 --sleep-hours 6.8
python3 -m coach planned add --date 2026-10-14 --kind run \
  --title "Easy 5 km" --distance-km 5 --start 06:30
```

`activity add` takes `--kind` (`run`, `ride`, `swim`, `row`, `walk`,
`hike`, `conditioning`, `sport`, `mobility` or `other`), `--start` (ISO
8601; with no offset it is local time in `[athlete] timezone`) and
`--duration-min`, plus optional `--distance-km`, `--distance-mi`,
`--distance-m`, `--rpe` (session RPE, 0 to 10), `--avg-hr`, `--name`,
`--notes` and `--indoor`. Manual ids are predictable:
`manual:2026-10-06-run-1`.

### Apple Health through Health Auto Export

The first phone adapter reads the JSON files the Health Auto Export app
writes. Set it up like this:

1. In Health Auto Export, set Export Format to JSON, Export Version to
   Export Version 2, and turn Summarize Data on.
2. Create two automations, one for Health Metrics and one for Workouts.
   Each automation exports one data type into its own folder under
   `AutoExport/`.
3. Point `path` at the `AutoExport` folder, or any folder holding both
   automation folders. On a Mac with iCloud Drive that is
   `~/Library/Mobile Documents/com~apple~CloudDocs/AutoExport`.

```toml
[sources.apple_health]
enabled = true
path = "~/Library/Mobile Documents/com~apple~CloudDocs/AutoExport"
drop_source_names = ["Hevy"]
```

The files are read in place, never copied. A CSV file or a Version 1
file is refused with the setting to change; an iCloud placeholder that
has not downloaded yet is a warning naming `brctl download`. Workouts
written to Apple Health by an app in `drop_source_names` are dropped, as
are workouts whose name maps to lifting: Hevy is the lifting logbook.
With `Hevy` in the list, a workout with no source that starts within
`dedup_window_minutes` of a cached Hevy workout is dropped too. Metrics
become one wellness record per day. The phone exports only while it is
unlocked, so gaps are expected and reported rather than filled.

### Hevy conditioning workouts

```toml
[sources.hevy_conditioning]
enabled = true                # also needs [hevy] enabled = true
```

This source reads the Hevy cache and never calls the API. A Hevy workout
becomes an Activity when every exercise in it is a conditioning exercise,
or when its routine maps to a program session of kind `conditioning`.
Put `RPE 7` in the workout description and the source reads it as the
session RPE. A workout that disappears from Hevy is voided with the
reason "deleted in Hevy". `activity sync` warns when the cache is older
than `[hevy] cache_max_age_hours`, so pull first.

## Syncing and checking the sources

`activity sync` fetches every enabled source and appends what changed.
It writes local files only and never stages or commits. One source
failing is a warning; the others still land. `--source NAME` syncs one
source and `--dry-run` reads without writing.

`activity import --source NAME --file PATH` runs one export file, such as
a 90-day manual export, through a source as a backfill. The source does
not need to be enabled yet.

`activity status` shows each enabled source with its last sync, record
counts, newest date and the days in the last 14 with no wellness record.
Real output from a fixture instance:

```json
{"sources": [{"source": "manual", "last_sync_at": null,
  "counts": {"activity": 5, "wellness": 7, "planned": 5},
  "newest_date": "2026-10-11",
  "missing_days": ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01",
                   "2026-10-02", "2026-10-03", "2026-10-04"]},
 {"source": "hevy_conditioning", "last_sync_at": null,
  "counts": {"activity": 0}, "newest_date": null, "missing_days": null}],
 "window": {"start": "2026-09-28", "end": "2026-10-11"},
 "wellness_path": ".coach/activity/wellness.jsonl"}
```

`activity list [--from DATE] [--to DATE] [--kind K]` lists the resolved
Activities in a span, duplicates merged; the span defaults to this week.
`activity show <id>` shows one Activity by any id it was merged from,
with every line ever written for it. `activity void <id> --reason TEXT`
removes a record from every view; its history stays in the file.

## Wellness days

A wellness day is one calendar day of readings: sleep, resting heart
rate, steps, body mass and body fat. **Sleep belongs to the day you
woke**, so Monday night's sleep is Tuesday's record. Sleep hours are time
asleep, not time in bed; both are stored.

`wellness add` records one day (`--date`) or a span (`--from` and `--to`)
with `--sleep-hours`, `--in-bed-hours`, `--resting-hr`, `--steps`,
`--body-mass` (in your bodyweight units) and `--body-fat-pct`. Adding
again for the same day or span updates that record and keeps the
readings you did not give.

A span record is a **period mean**: "about 6.5 h a night over the last
two weeks". It stays self-report, keeps its original span, and fills only
the days no daily reading covers. When whole, it counts toward the sleep
gate's 14-day average. It never counts as individual nights, so it cannot
show short nights: the `sleep_debt` flag and the poor-sleep fatigue
trigger both need dated nightly observations.

`wellness summary [--from] [--to]` gives the sleep average with the
provenance of every night and period mean, plus a read-only `sleep_gate`
for the trailing 14 days (`passed`, `recomp` or `pending measurement`).
`wellness list` gives one resolved day per date, and `wellness void`
works like `activity void`.

While a nutrition app is enabled, body mass readings here are stored
raw; nothing derives a weight trend from them.

## Where the data lives

| Path | What | In git |
|---|---|---|
| `data/activity/activities.jsonl` | logged activities, append-only | yes |
| `data/activity/planned.jsonl` | planned activities, append-only | yes |
| `data/activity/associations.json` | explicit activity-to-plan links | yes |
| `data/activity/sync.json` | each source's last sync and cursor; no health values | yes |
| `data/activity/wellness.jsonl` | wellness records when `wellness_in_git = true` | yes |
| `.coach/activity/wellness.jsonl` | wellness records when `wellness_in_git = false` | no |

Lines are only ever appended. A correction is a new line, and a void is a
line that removes the record from every view while the history stays.
`coach check` runs `activity_records_valid`, `activity_wellness_location`
and `activity_source_fresh` while activity is enabled.

## Cardio tiers: who owns the run plan

`[cardio] tier` says who owns the run plan, not how much data you have.
That comes from the sources.

| Tier | Meaning |
|---|---|
| `count` | no plan: logged cardio is counted, planned activities are ignored, no reconcile |
| `review` | an outside plan or your own, reconciled against what was logged |
| `program` | the coach writes the planned activities |

`/setup` sets `review` when a running app, club, coach or race plan owns
your running, and `count` when runs are only counted. It never sets
`program`. At `count`, `/program-week` asks nothing about runs and the
coach writes no running plan.

## Planned activities and reconciliation

At `review` or `program`, each week's runs are planned before the week is
computed. `/program-week` shows `planned list` for the span and asks what
changed and what is still to come, with each run's start time and length.

`planned add` takes `--date`, `--kind` and `--title`, plus `--quality`
for intervals, tempo, threshold, hills or a race, a target
(`--distance-km`, `--distance-mi`, `--distance-m`, `--duration-min`,
`--description "Zone 2"`), `--start` (`HH:MM` on the date, or an ISO
timestamp) and `--notes`. A plan identical to one already on that day is
refused (exit 3); `--again` adds a deliberate second one. A changed run
is `planned void <id> --reason TEXT` and then a new `planned add`.
`planned list` shows a span's plans from every source.

`cardio reconcile --week W` matches plans to logged activities. Explicit
links go first, then same-kind candidates within `reconcile_move_days`
(default 3), told apart by title, target distance and duration before
date. Each row gets one status:

| Status | Meaning |
|---|---|
| `done` | matched on its planned date |
| `moved` | matched on a different date, with `moved_days` |
| `missed` | unmatched plan before today |
| `upcoming` | unmatched plan today or later |
| `extra` | logged activity with no plan |
| `ambiguous` | tied candidates; shows `candidate_ids` and `review_reason`, and inherits no plan's quality |
| `duplicate` | the same session planned by a second source; done, not missed |

The check-in shows you an ambiguous row's candidates and records your
answer with `cardio associate ACTIVITY_ID --planned-id PLANNED_ID`;
`--clear` removes a link. From the fixture instance, a long run done a day
late reads:

```json
{"status": "moved", "planned_id": "manual:2026-10-08-run-1",
 "activity_id": "manual:2026-10-09-run-1", "date": "2026-10-08",
 "activity_date": "2026-10-09", "moved_days": 1, "kind": "run",
 "title": "Long run", "target": {"distance_meters": 11000},
 "actual": {"distance_meters": 11500, "duration_seconds": 4200},
 "quality": false, "quality_basis": "rpe",
 "match_basis": ["distance_meters", "name"]}
```

## The week view

`cardio week --week W` (a label such as `2026-W41`, or any date in it)
totals the week: lifting workouts with working and hard sets and minutes,
coach-led sessions done, runs with count, distance, minutes and quality
count, conditioning, other kinds, and a session-RPE load. That load is
each bout's minutes times its session RPE, summed over the week. It is
information only (rn:running-load.3): no flag reads it and no ratio is
ever computed (rn:running-load.2). Each bout says which method gave its
RPE: `athlete` when you logged one, `planned` from a matched plan,
`lifting_sets` from the mean RPE of a lifting workout's sets,
`external_default` for a coach-led session with nothing recorded, else a
default per kind.

`cardio render --week W` prints the same week as markdown, with the
reconcile table and the flags; `--into <check-in record>` writes it into
that record's cardio region. The check-in's Coach's read quotes it.

## The cardio flags

`cardio flags --week W` (or `--span A..B`) judges logged bouts up to
today and, at `review` or `program`, plans from today on. The same flags
appear in `propose week`, so a proposed week is judged with the runs
already logged in it. Each threshold lives in `[cardio]`, and
`config.example.toml` cites the claim behind it.

| Flag | Rule | Config keys and claim |
|---|---|---|
| `cap_breach` | run distance or minutes over the weekly cap, a single run over the single-run cap, or more quality activities than the cap; `0` means no cap | `weekly_run_distance`, `weekly_run_minutes`, `single_run_distance`, `single_run_minutes`, `weekly_quality = 2` (rn:running-load.5) |
| `run_volume_spike` | a run longer than `spike_ratio` times the longest run in the lookback; warn when logged, info when planned | `spike_ratio = 1.10`, `spike_lookback_days = 30` (rn:running-load.1), `spike_min_history_days = 14` (rn:running-load.4) |
| `quality_stack` | two quality activities on the same or consecutive days | the quality rule below |
| `sleep_debt` | at least `sleep_debt_nights` of the last 7 nights under `sleep_short_hours`, judged only with `sleep_min_nights` nightly observations | `sleep_short_hours = 7.0` (rn:sleep-dieting.1), `sleep_debt_nights = 4`, `sleep_min_nights = 4` |
| `status_active` | a status day overlaps the span: warn for ill or injured, info for travel | see [niggles and follow-ups](niggles-and-followups.md) |
| `niggle_link` | an active niggle lists this activity kind | the niggle's `--activity-kinds` |
| `collision` | an interference rule broken | the program's rules, below |

A spike is judged only once your activity history reaches
`spike_min_history_days` before the run; runs it cannot judge are listed
under `skipped` with the reason. A spike is a review with the coach, not
a fatigue trigger and not a load cut: the coach asks about symptoms,
recovery and the next long run, and records the agreed action as a
follow-up. Real flags from the fixture week:

```text
warn cap_breach: Run distance 18.5 km in 2026-W41 is over the 18 km weekly cap.
warn run_volume_spike: Run on 2026-10-09 is 11.5 km, more than 1.1 × the longest run in the 30 days before it (10 km). ...
warn quality_stack: Quality activities on 2026-10-06 (run, by rpe) and 2026-10-07 (conditioning, by kind): keep an easy day between quality sessions.
warn sleep_debt: 4 of the 7 nights to 2026-10-11 were under 7 h asleep (7 with data): recovery, not the program, may be the bottleneck this week.
warn niggle_link: Niggle n-0001 (left knee, watching) applies to run: 2 runs, 18.5 km in 2026-10-05 to 2026-10-11. Ask how it responded.
```

### What makes an activity a quality activity

The first rule that applies wins, and the flag reports it as
`quality_basis`:

1. kind `conditioning`, including a coach-led session you recorded as
   conditioning or mixed (`kind`);
2. a session RPE you gave, at or above `quality_rpe_min = 7`
   (rn:running-load.6) (`rpe`);
3. the quality of the planned activity it matched (`planned`);
4. a name containing interval, tempo, threshold, hill, fartlek, track or
   race (`name`);
5. otherwise not quality (`none`).

A **heavy lower session** is a lifting session with a compound squat or
hinge exercise that has a working set at RPE 7 or more, or of 6 reps or
fewer when no RPE is set. A coach-led session never counts as one.

A coach-led session with no recorded length or effort counts as
`external_session_minutes = 60` at `external_session_rpe = 6`
(rn:running-load.7); each value you do record replaces its default.

## Interference rules

The program carries two rules on spacing lifting and quality activities,
both from the concurrent-training note (see
[research](research.md)):

- `same_day`: lift first and keep at least 6 hours before a same-day
  quality activity (rn:concurrent-training.4).
- `quality_before_heavy_lower`: no quality activity in the 24 hours
  before a heavy lower session (rn:concurrent-training.5). The 24 hours
  is a cautious coaching heuristic, and the flag says so.

Easy activities never trigger either rule. A broken rule raises a
`collision` flag that names both bouts, the rule and the gap. Gaps are
elapsed hours between known start and end times. Without them the flag
says the gap is unknown and asks for the times; it never claims a
measured breach from dates alone. `/program-week` therefore asks when a
lifting session starts and how long it runs whenever a quality run sits
within a day of it, and records the answer with
`propose time --proposal <id> --session <s> --start HH:MM --duration-min N`.

Nothing moves by itself. The coach and you agree what moves, usually the
run, or the flag is kept with a reason. `interference list` shows the
program's rules and their params; `interference check --week W` runs
them alone over logged workouts and planned activities. An empty
`interference` list in `data/program.json` turns the rules off.

## Conditioning sessions in the program

A program session of kind `conditioning` can carry a density scheme,
`emom_density` or `circuit_rounds`, which writes its sets each week. The
scheme steps up when your last matched bout's session RPE was at or
under the target (7 by default), steps back when the RPE was 2 or more
over it or the time cap was passed, and holds otherwise; with no RPE it
holds and flags `no_data`. Its Hevy workouts become Activities, so the
session's Focus line reminds you to put `RPE 7` in the workout
description. An optional conditioning session is dropped from a proposed
week by sleep debt, a status day on its date or a quality activity the
day either side (`conditioning_dropped`); `propose restore` puts it back
if you still want it.

## Goal events

A goal event is a dated race or other event you train towards, kept in
`data/events.json` with a stable id, a priority (`A` the goal, `B` and
`C` lesser) and a status: active, completed with its result, or
cancelled. Rows are history and are never deleted.

```bash
python3 -m coach events add --id autumn-10k --title "Autumn 10K" \
  --date 2026-10-21 --priority A --activity run --distance-km 10
python3 -m coach events window autumn-10k --from 2026-10-15 \
  --to 2026-10-20 --rationale "keep the legs fresh"
python3 -m coach events complete autumn-10k --result "41:30, a 2 min PB"
```

- `events add` needs `--id`, `--title`, `--date` and `--priority`;
  `--activity`, a distance and `--planned-id` are optional.
- `events update ID` changes an active event; a new date clears the
  window and a plan left on the old date.
- `events window ID` records the agreed window (`--from`, `--to` and a
  `--rationale`), an agreed decision to keep none (`--none`), or clears
  the decision (`--clear`).
- `events complete ID --result TEXT` and `events cancel ID --reason TEXT`
  close it; `events list [--all]` shows active events with a countdown
  and any pending decision.

**No window is ever assumed**, of any length. Until you agree one the
event carries a pending decision, which the Sunday message's Events field
asks and `propose week` flags as `event_window_pending`. Once the date
passes, the pending decision is the result. A heavy lower session inside
an agreed window raises `event_window_heavy_lower` for review; nothing is
moved or changed automatically. Linking a planned activity with
`--planned-id` makes the plan the event, so the logged race counts once,
as the activity that reconciles with it. Events never pause or reset the
block count.

## Runs and sleep in the check-in

The Sunday message states what the sources already show and asks only
for the rest. With an activity source on, the Runs field states the
window's runs from `cardio week` and any plan `cardio reconcile` found
missed, and asks for runs no source logged. With no source on, it states
the runs the activity files record or plan; with none recorded or
planned, there is no Runs field. Lifting alone never implies running.

The Sleep field states the last seven nights, average and short nights,
when enough dated nightly observations exist, and asks how it felt.
Otherwise it asks for hours asleep each night, from a diary or tracker,
or failing that the average with its dates and source. The coach enters
nightly hours with `wellness add --date <night> --sleep-hours <h>`, and
only nightly hours feed the poor-sleep fatigue trigger.

## Reviewing an outside running plan

When you follow a running plan or train for an endurance event, the
coach follows `reference/runner-review.md`: it reads the
strength-for-running and endurance-fuelling notes, reviews how your
lifting supports the running priority, and reviews fuelling only when
nutrition coaching is enabled. It works from your Sunday reply and never
starts a new interview; a question to come back to becomes a follow-up.
This is review-tier support: you or the outside plan own the running
progression, and routine changes still go through the normal brief and
approval.

The evidence behind these reviews ships as the `strength-for-running`,
`endurance-fuelling` and `running-load` notes in `research/`.
