# Training without Hevy

This page covers training with `[hevy] enabled = false` in
`config.toml`: the session sheets you train from, how you report a
workout in chat, the manual log the coach keeps, and how to correct it.
Read it if you log on paper, in another app, or in Hevy's free tier.

**Hevy free counts as no Hevy.** The coach reads logs and writes
routines only through Hevy Pro's API, and the free tier has no API. When
`/setup` asks "Pro, free, or not at all?", a free account gets
`enabled = false`, and everything on this page applies. Every skill
works without Hevy; only `/hevy-sync` has nothing to do.

## What changes

With Hevy off there are no Hevy routines and no push. A programming pass
ends when the coach runs `python3 -m coach overlay approve <id>` on your
"go": that stamps your approval on the week's **overlay** (see [the
glossary](../../CONTEXT.md)), the per-exercise prescription in force for
the week, and it is the last write of the pass. The coach then runs
`python3 -m coach sheets render`, which writes `this-week-sheets.md`,
and publishes the week.

| With Hevy | Without Hevy |
|---|---|
| `hevy pull` fills the cache; history reads the cache | `history sync` reads the manual log |
| The prescription goes into Hevy routines | The prescription goes into `this-week-sheets.md` |
| You log sets in the app | You report the workout in chat; the coach logs it |
| `routines push`, `verify`, the audit log, `/hevy-sync` | None of these; `routines push` exits 5 naming `[hevy] enabled` |
| Loads print as `25/hand (Hevy: 50)` | Loads print as `25/hand` |
| Hevy checks run | Hevy checks report `skip`; `sheets_render_fresh` runs instead |

Publishing includes the sheets: `pages publish` regenerates
`this-week-sheets.md` from the approved overlay and commits it with the
brief, the dashboard and the progress page, so your phone shows the
week. The brief's session list links to each session's sheet.

## The session sheets

`this-week-sheets.md` holds one section per session of the week's
overlay, in date order, with a table of sets and an empty Done column
to tick. Loads show your number only (`25/hand`), never the Hevy value.
Below the table, one bullet per exercise carries its **athlete
guidance**: the focus, the target note and the cues. For example,
modelled on a test workspace's render:

```markdown
# Session sheets · week of 12 Oct

Overlay `2026-10-12-weekly` (weekly) · Mon 12 Oct – Sun 18 Oct · loads in kg

**Week focus:** Heavier top sets; stop 1–2 reps short of failure.

## Session A · Mon 12 Oct

| Exercise | Sets × reps | Load | RPE | Rest | Done |
|---|---|---|---|---|---|
| Back Squat (Barbell) | 1×5 warm-up | 60 |  |  |  |
|  | 3×5 | 100 | 7 | 180 s |  |
| Bench Press (Dumbbell) | 1×10 warm-up | 12.5/hand |  |  |  |
|  | 3×8–10 | 25/hand | 8 | 120 s |  |

- **Back Squat (Barbell)**: Note: hold at 100 this week · Cues: brace · knees out
- **Bench Press (Dumbbell)**: Focus: pause 1 s on the chest · Cues: elbows tucked · feet planted

## Session B · Thu 15 Oct

| Exercise | Sets × reps | Load | RPE | Rest | Done |
|---|---|---|---|---|---|
| Single Arm Row (Dumbbell) | 3×10 | 30 | 8 | 90 s |  |
| Pull Up | 3×8 | BW | 8 | 120 s |  |

---

To log a session, reply to the coach with what you did: the reps of every
set with a range or a +, the load you used where it says "choose the
load", how hard each exercise felt (RPE) if you can say, and anything
else that differed. "As written" covers fixed reps and loads only
("squat as written, RPE 8; bench 10, 9, 8 at RPE 9").
```

Some lines look different:

- A load you pick yourself, such as a calibration line in a starter's
  first week, prints **choose the load** in the Load column, with the
  note telling you how to pick it.
- A **rep-out set** prints as `1×5+` with `stop at 9` in the RPE column:
  at least those reps, more until the next would pass the stop, not a
  set to failure. The footer explains the `+`.
- When `[athlete] experience` is `beginner`, the footer adds a short
  key: RPE as your estimate of reps left (RPE 10 is about 0 left, RPE 8
  about 2), not a precise measure, and that any count inside a rep
  range is on plan, with the set's RPE deciding where it ends.
- An overlay not yet approved renders with a "Not approved yet" line.

The sheets show the week holding tomorrow, so on a Sunday after the
programming pass they show the coming week, as the brief does. The
`sheets_render_fresh` check warns when the file shows another overlay
than the current one and fails when it differs from a fresh render.

## Reporting a workout

After a session, tell the coach what you did, in chat. The coach builds
the log entry from the prescription and asks only for what the sheet
could not know. It runs:

```bash
python3 -m coach log prefill --session <id> --date <date>
```

Prefill returns a draft workout with the prescribed sets filled in, and
an `ask` list: one item per exercise, field and prescribed value. The
coach works through it. From the test workspace above, for Session A:

| Exercise | The coach asks | Why |
|---|---|---|
| Back Squat (Barbell), sets 1 to 4 | Did you do the reps and load as written? | The warm-up and the fixed reps and loads are prefilled, but kept only when you confirm them |
| Back Squat (Barbell), sets 2 to 4 | How hard did each set feel? The target was RPE 7 | An RPE target is never a logged RPE; a warm-up gets no RPE question |
| Bench Press (Dumbbell), set 1 | Did you warm up as written? | The warm-up's reps and load are prefilled |
| Bench Press (Dumbbell), sets 2 to 4 | How many reps in each set? The plan was 8 to 10 | A range is not a count, so reps stay empty until you give them |
| Bench Press (Dumbbell), sets 2 to 4 | Was the load as written? | As for the squat |
| Bench Press (Dumbbell), sets 2 to 4 | How hard did each set feel? The target was RPE 8 | As for the squat |

Set numbers count the draft's sets, warm-ups included. A warm-up with a
load on the sheet comes into the draft as prescribed; one without a load
is left out and never asked about.

The rules behind the list:

- **Reps for a range or a rep-out set.** The actual count, per set. The
  draft leaves them empty; the plan's range or `5+` minimum is never
  recorded as what you did.
- **The load for "choose the load".** The weight you used, in your
  units and **per hand for dumbbells**: the number you set, never a
  Hevy-style total. A pair reported as one number trips a
  `looks_like_total` warning.
- **RPE for every working set.** How hard it felt. If you cannot say,
  it stays empty, and the entry warns `rpe_unknown`; the coach never
  writes the target in its place.
- **"As written"** confirms only what was prefilled: fixed reps and set
  loads. It never covers a range, a rep-out minimum or a missing load.
- Anything else that differed: a set skipped, a load dropped, a swap.
  Your own notes ("wiped out after yesterday's run") go in the entry's
  notes and shape next week's loads as much as the numbers do.

The entry can also carry when the session started and how long it took,
if you mention them. Both may stay empty.

With your answers, the coach saves the draft under `.coach/drafts/` and
runs `python3 -m coach log add --input <file>`. The command validates
the entry (a known exercise id, the slot's load mode, a date not in the
future, your units, a session the program or an overlay knows), appends
it to the manual log, and syncs history, so the dashboard, the progress
page and the check-in read it at once. It refuses (exit 3) a second
entry for the same date and session unless `--again` says it really was
a second workout. The coach shows you its one-line summary and any
warnings.

## The manual log

`data/log/workouts.jsonl` is the manual log: one JSON line per workout,
written only by `log add`. For example:

```json
{"schema_version": 2, "kind": "workout", "id": "manual:2026-10-12-session-a-1",
 "logged_at": "2026-10-12T19:05:00Z", "date": "2026-10-12", "start_time": "2026-10-12T17:50:00Z",
 "session_id": "session-a", "overlay_id": "2026-10-12-weekly",
 "duration_minutes": 55, "notes": "",
 "exercises": [
   {"exercise_id": "db_bench_press", "load_mode": "per_hand_x2", "unit": "kg", "notes": "",
    "sets": [{"type": "normal", "reps": 10, "rpe": 8, "value": 25,
              "duration_seconds": null, "distance_meters": null}]}
 ]}
```

Each set's `value` is your number: per hand for `per_hand_x2`, the
implement for `single_implement`, the total for `total`, the added load
for `bodyweight`, the assistance for `assisted`, and empty for band,
duration and distance work. Nothing in the file is a Hevy value, and
nothing doubles or halves it. Ids are `manual:<date>-<session>-<n>`; a
workout with no session gets `adhoc`.

The log is **append-only**: no line is ever edited or removed. It is
committed with the training records as part of the week's commit plan.
`python3 -m coach log list` (`--since <date>`) prints the live entries,
oldest first. The `manual_log_valid` check fails on any line that does
not validate.

## Corrections

A wrong entry is voided, then entered again:

```bash
python3 -m coach log void manual:2026-10-12-session-a-1 --reason "bench was 22.5/hand, not 25"
python3 -m coach log add --input <corrected file>
```

The void appends a line naming the entry and the reason; the original
line stays in the file. Both commands sync history, so the pages and
the next check-in read the corrected workout. The coach runs them for
you when you say what was wrong.

## How history and stats read the log

History treats a manual entry exactly like a Hevy workout: each
exercise becomes an **exposure** with its date, sets, reps, loads and
RPE, and the same rules derive e1RMs, progression, adherence, the block
count and the dashboard's consistency from it. A workout's title is its
session's title; each exercise's title is its library name. Start time
and duration, when you gave them, let the interference rules judge the
hours between a lift and a run.

If a sync fails after an entry is written, the command still exits 0
and warns `history_not_synced` with the next step. The coach follows
that step and never logs the workout again.

With Hevy **on**, `log add` still works, for a workout you forgot to log
in the app, and warns `hevy_enabled`.

## The Sunday message without Hevy

The weekly check-in starts with the **Sunday message**: one message
that states what the log shows and asks only what it cannot. Without
Hevy, "the log" is the manual log. Before sending it, the coach logs any
workout you report at the start of the check-in with `log add`, the
same way as above, so the Sessions field shows each planned session as
trained or missed from what you reported.

The message otherwise keeps its fields: a one-word tag for each miss,
coach-led sessions, runs, sleep, niggles, food or bodyweight, and
anything different next week. Two Hevy-only parts are absent: the check
that a routine is STALE, and the keep-or-replace question for a routine
edited in the app. The coach reads each logged workout's notes as it
would a Hevy description.

## Switching Hevy on later

If you move to Hevy Pro, run `/setup` again. On a re-run it reports your
current answers and asks what to change: set Hevy to Pro, and it walks
you through the key (`.env`, `hevy status`, a first `hevy pull`) and
sets `[hevy] enabled = true`. The next programming pass then seeds the
exercise library from your Hevy templates, confirms load modes with you,
and creates a routine for every session in its write brief. Your manual
log stays in history alongside the Hevy workouts that follow. See
[Hevy](hevy.md).
