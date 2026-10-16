# Programming the week

`/program-week` turns your program and the latest check-in into the
prescription for a span of days, shows it to you as a coach's brief, and
writes it to Hevy (or your session sheets) on your "go". Read this when
you want to know what a programming pass does, which mode it runs in,
what the brief contains, and what one "go" approves.

## What a programming pass is

One run of `/program-week` is one **programming pass**: one mode, one
overlay, one approval (see [the glossary](../../CONTEXT.md)). The pass
proposes, per session and per exercise, the load, reps, RPE, a focus
where warranted and the standing cues. It records them as an
**overlay** in `data/overlays/<id>.json`, the prescription the next
check-in judges adherence against, and writes them into your Hevy
routines.

The program in `data/program.json` stays the block-level plan: weekly
numbers never go into it. A **structural change** (a swap, an added
exercise, a set count, an execution change) edits the program first,
then Hevy. A **one-off week** (light, constrained or reshuffle mode)
never changes the program: its temporary sessions live in the overlay
and in temporary Hevy routines, and normal weeks resume from the
untouched program.

The pass needs `profile.md` and `data/program.json`; without them the
coach runs `/setup` or `/new-program` first. It starts with
`python3 -m coach check` and reports every failing check. Every load
you see comes from the scripts: the coach never converts units, splits
a dumbbell total or rounds a load by hand.

Before computing anything, the coach reads your profile, the program,
the state (rotation, block, any one-off week in force), the newest
check-in, and the overlay in force today. With Hevy it pulls your recent
workouts and reads each description and note, since "target too high,
did back-off sets" tempers next week's loads as much as the numbers
do. It states the rotation position for confirmation if your program
rotates, counts the days off since your last lifting workout, settles
the span's planned runs when your cardio tier is `review` or `program`,
and lists any goal event. With an overlay in force it also checks your
Hevy routines for in-app edits (see Hevy housekeeping below).

## The six modes

The coach picks the mode from what you say, the session-start status
and the state, and names it in the brief's first line.

| Mode | When it applies | Overlay kind | How the week is built |
|---|---|---|---|
| normal | the coming program week | `weekly` | the proposal pipeline: `propose week`, settle each line, `propose finalize` |
| midweek | a missed session, or a change partway through a trained week | `midweek` | `missed plan` for a miss; otherwise the pipeline with `--kind midweek` |
| light | a deload, light or return week the check-in agreed, or a return after illness | `deload` | the pipeline, with the command `block decide` printed, or `--kind deload` |
| minimum | short on time at your usual kit, with a configured `minimum_week` | `weekly` | the minimum variant's plan file, then the pipeline with `--plan` |
| constrained | travel, limited kit, or short on time without a valid minimum | `one_off` | a coach-written draft through `overlay build` |
| reshuffle | the same sessions on different days | `one_off` | the overlay in force, re-dated; nothing goes to Hevy |

A span can mix a reshuffle and a constrained week (two days moved, two
on hotel kit): one overlay, one brief. When a one-off week is already in
force, the pass continues in its mode rather than starting a normal
week.

**A planned break.** If you agree not to train at all for some days (a
trip with no gym), the coach programs nothing for them: it records the
break as travel status days marked `--no-training` and programs only
the days around it. Travel alone is not a break: if you will train while
away, constrained mode applies.

## The proposal pipeline (normal, midweek, light and minimum)

The scripts propose each line; the coach reasons about it per lift. A
formula applied blindly is not coaching.

**1. Propose the week.** `python3 -m coach propose week` writes an
editable draft under `.coach/proposals/`. Each exercise's progression
scheme proposes its line: double progression adds the increment once
every set tops the range at or under target RPE, missed reps hold, and
no load derives from an open convention slip. The core then applies
return bands, the illness cap, niggle constraints, caps and your kit.
Each line comes with its sets, its `change` from the last approved
prescription (or `first prescription`), a rationale and its flags.

**2. Read every line against the check-in.** The coach reads each line
against your notes on how sets felt, your niggles and the rotation
position, and settles its flags. The ones you will hear about most:

| Flag | What it means | What happens |
|---|---|---|
| `rpe_drift` | logged RPE 1 or more over target on 2 or more working sets of a compound lift or a recovery-capped set | hold or back off; isolation work still progresses on reps |
| `range_effort_mismatch` | a held double-progression line whose last exposure fell below the range or 2 or more RPE over target | agree a lighter load or a different range, or keep it with a reason |
| `convention_slip` | an exact 2× jump at unchanged reps and RPE | the coach raises it with you; it is not progress |
| `return_week`, `return_after_illness` | the return band sets this week's loads, sets and RPE cap instead of the scheme | the band is named in the week focus; after illness the coach confirms 48 hours symptom-free before the flag can be resolved |
| `collision` | a quality run too close to a lifting session under the program's interference rules | the coach asks for unknown times, then you agree what moves, usually the run |
| `conditioning_dropped` | the drop rule removed an optional conditioning session (sleep debt, a status day, or a quality activity the day either side) | put it back with `propose restore` if you still want it |
| `incomplete_exposure` | fewer sets logged than prescribed, none short | the load holds; the coach asks whether the missing sets were skipped or failed |
| `load_cut_held` | the kit cannot make a reset, return or deload cut, so the load holds | agree holding it or the lighter load the flag names |
| `wave_review` | a wave week short of reps or load | the week repeats and the training max holds; a change goes through `state set-training-max`, previewed first with `--dry-run`, then the week is proposed again |
| `no_data` | a line with no logged load and no start load | the coach sets the first load with you; the line carries a calibration note |
| `event_window_heavy_lower`, `event_window_pending` | heavy lower work inside an agreed event window, or an event with no window decided | keep it with a reason, change the line, or agree a window |

**3. Settle each line.** Three tools, each with a different purpose:

- **An override with a reason**, through
  `python3 -m coach propose override`, changes one line: new working
  sets (`--sets "3x5@95 rpe7"`, seconds for a timed hold, a `+` for a
  rep-out set) or one load for every working set (`--load`). `--date`
  changes only that day's line. A **standing override** (`--standing`,
  with `--until` at most eight weeks away, four by default) keeps the
  change in later weeks so the scheme stops proposing it away; a deload
  or light week still cuts it. `--derived-from` names the logged workout
  the new sets come from, so the prescription check judges them against
  that exposure. The reason is the coach's audit and never
  reaches your pages.
- **Athlete guidance**, through `python3 -m coach propose note`, needs
  no reason: the week focus, and a line's target note, focus or cues.
  This is what you read on the record and the session sheets ("10 per
  leg", "stop at RPE 9"). A line with no logged load carries a
  calibration note: pick a load you expect to fit the target reps within
  the RPE shown, then adjust after the first working set. Beginners get
  a qualitative warm-up ramp note on each session's first loaded lift,
  with no loads or percentages the coach has not agreed.
- **Resolving a flag**, through `python3 -m coach propose resolve`,
  keeps a flag you and the coach decide to accept, with the reason it
  stands. A `load_mode_unconfirmed` flag cannot be resolved: only
  confirming how you load the exercise clears it.

Niggle limits are already on the lines: a standing limit (an RPE cap,
no added load, a load cap) while the niggle is aggravated or watching,
and a tighter flare limit while a flare lasts. A load the e1RM puts over
an RPE ceiling comes down, and the flag names the niggle.

**4. Finalize.** `python3 -m coach propose finalize` writes the overlay
to `data/overlays/<id>.json`. It refuses with exit 1 if any line changed
without an override reason, and with exit 3 while a `block` flag is
unresolved or the draft has gone stale (its span ended, or a newer
approved overlay covers it). A refusal writes nothing.

**5. Build and check the overlay.** Every mode arrives here with an
overlay id. The coach validates it, then runs
`python3 -m coach prescription check --overlay <id> --write`, which
judges every line: still earned after its days off, under cap,
buildable from the kit, feasible at its RPE, in the library's load mode,
and in a session that fits its time cap. Blocking findings
(`stale_prescription`, `unearned_load`, `load_cap`,
`load_unrepresentable`, `load_mode_mismatch`, `load_mode_unconfirmed`)
are fixed and checked again until none is left; a block you both decide
to keep needs a recorded resolution or approval refuses it. Warnings
(`rpe_infeasible`, `session_over_cap`, `load_geometry_unknown`) are
named in the brief with the change made or why the line stands. Then
`overlay render --into` fills the check-in record's "The week ahead"
region with the per-session tables the brief shows.

**6. Hevy preflight.** With Hevy on, `python3 -m coach routines
preflight` lists every exercise still without a Hevy template mapping,
and `routines diff` compares each routine in the span with the cache.
For a session with no routine yet, `routines create --dry-run` previews
what "go" would create or reuse, and its plan hash is what the write
step later checks against. See [Hevy](hevy.md) for managed, temporary
and orphan routines.

## Light mode

A light week the check-in agreed arrives with the command
`block decide` printed. Standalone, the coach runs
`python3 -m coach propose week --kind deload`, adding
`--transform light` for a light week or `--transform return` for a
return week, such as a return after illness.

A deload applies the program's own deload rule to every session in the
span. The standard rule keeps two thirds of each line's working sets,
takes 10 % off the current working loads (a target before the kit
rounds it) and caps every set at RPE 6 (rn:deloads.9); these numbers
are a coaching heuristic. Bodyweight work is cut by sets and taken
further from failure. The sessions are temporary, titled
"Deload — <title>", "Light — <title>" or "Return — <title>", and keep
their program session ids. Priority protocols stay alive at a reduced
dose. The coach reminds you to tell any coach or PT it is a deload
week, and deloads whatever your profile says moves with the lifting.
[Blocks and light weeks](blocks-and-light-weeks.md) explains when a
light week is proposed, the three kinds, and the return rule.

## Minimum mode

When you are short on time at your usual kit and the program has a
configured minimum week (at most two standby sessions carrying every
priority lift's floor dose), the coach checks it with
`python3 -m coach structure balance --variant minimum`, writes its plan
with `structure minimum --week <label> --write`, and proposes the week
from that plan. The overlay is a weekly overlay, but the week neither
counts toward nor resets the block. Setting up a minimum week is covered
in [Programs](programs.md). Without a valid minimum, the coach offers
constrained mode instead.

## Constrained and reshuffle modes: the one-off path

A one-off week the scripts do not propose: the coach designs it with you
and writes the overlay draft itself. The program, its pages and its Hevy
routines never carry it.

**Reshuffle.** The existing sessions still work; only the calendar
changes (a coach session moved, a day dropped, two days swapped). The
coach reorders using the program's own rules: recovery windows between
adjacent sessions, no same-pattern sessions on back-to-back days, and
weekly balance including coach-led sessions and cardio. Each moved
session keeps its lines from the overlay in force, re-dated, so
`routines diff` lists no change and nothing goes to Hevy. A reshuffle
week stays an ordinary week: a missed session still counts.

**Constrained.** The prescriptions change for travel kit, no equipment,
or a time-starved or run-down week. After a short design conversation
(what kit, what time, what state) the coach builds temporary sessions
that keep the program's priority work alive at a maintainable dose.
Maintenance, not progress: about a third to a half of normal volume
holds strength and muscle for a couple of weeks, so no PR attempts on
hotel dumbbells. The failure mode to design against is no plan at all.

Each temporary session must be concrete enough to train directly:
exercises, sets × reps, load or RPE, rest. The place's kit goes in
`config.toml` as an `[equipment.locations.*]` table when it differs
from home, so caps and loads use it. **Before the draft, the coach
confirms the load mode of every exercise new to you** (push-ups on the
hotel floor, dumbbell RDLs in place of the barbell): how you load it,
recorded with `python3 -m coach library set-mode` or `library confirm`.
An unconfirmed exercise blocks approval.

The coach writes the draft to `.coach/drafts/overlay-<span start>.json`
in your units, then `python3 -m coach overlay build --input <draft>`
writes the overlay and gives its id, and the pass continues at build
and check above.

## Midweek mode and missed days

Started partway through a trained week, the coach first asks what
prompted it: a missed session, a change to a lift, an easy or hard day,
a schedule change.

**A missed session.** `python3 -m coach missed list` shows the planned
sessions with no workout, and `python3 -m coach missed plan --session
<id> --date <date>` says what the program's **missed-day rule** does
with it. The program's rules, agreed before the week starts, are of
three kinds:

| Rule | What it does |
|---|---|
| fold | copies named exercises from the missed session into a later session this week, with 2 working sets by default (never more than prescribed; rn:minimum-effective-dose.5) at the prescribed reps and load, this week only |
| shift | moves the whole session to the first free weekday in its list, inside the span and on one of your available days |
| skip | the week continues unchanged; the miss is recorded |

When a rule matches, the coach presents the plan's own summary and
write line instead of the full brief. This one comes from a test
workspace:

```text
Missed Wed 14 Oct Session B; rule miss-b applies (fold).
Single-arm row 2×10 @ 30 @ RPE 8 added to Sat 17 Oct Session A, this week only.
Mid-week overlay 2026-10-17-midweek: Sat 17 Oct to Sun 18 Oct, over 2026-10-12-weekly on those days.
Prescription check: no block or warn flags.
Reply "go" to train this and write: Session A (Hevy).
```

After "go", the coach runs `python3 -m coach missed apply` with your
miss tag, approves the midweek overlay and pushes it. A `skip` rule
writes no overlay, so nothing is published. A fold never carries
forward: next week is built from the program again.

**No rule applies** (no rule for that session, a shift with no free day,
or a miss planned once the days have passed). Then the session's lifts
leave the week only when you choose that. The coach shows each later
day's status (`free`, `occupied`, `elapsed` or `unavailable`) and
offers three choices:

- **Move it** to a free day: `missed plan ... --move-to <date>`,
  presented like a matched rule.
- **Reshuffle**, when the move needs other sessions moved too: the
  reshuffle mode above.
- **Drop it**: `missed plan ... --drop`; the rest of the week stays as
  planned.

An `unavailable` day is your `[athlete] available_days` speaking; the
coach changes that list only on your confirmed answer.

**The priority-lift floor dose.** A priority lift keeps a floor of 2
hard sets at its prescribed load in a disrupted week
(rn:minimum-effective-dose.4). When the missed session carried one and
a `skip` rule or your drop takes it out of the week, the floor is
folded into the next session this week; a program fold that carries the
lift short is topped up. The summary says so. Only when no later session
is left does the lift wait for next week, and the check-in flags the
missed exposure.

**A lift with no session left this week** ("bump my squat" the day after
its only session): its next exposure is next week's own session, so the
change becomes a follow-up. The coach reads the lift's latest exposure,
agrees the change with you, and records it with
`python3 -m coach followups add` dated for the day next week is planned.
The next weekly proposal raises it as `followup_due` and applies it as
that line's override.

**Other midweek changes** go through the pipeline with
`propose week --kind midweek`: only the days left, less any session
trained today, keeping the week focus and the line guidance you agreed
for those days. Guidance the scripts cannot tell from scheme text is
listed for review, and the coach asks whether it still holds.

## The coach's brief

Every mode ends with the same brief: narrative first, tables second.

1. **Week focus.** One or two sentences on what the span is doing and
   why, tied to your phase and goal, with the mode named. A one-off week
   says why it deviates, what is protected, what is deliberately
   dropped, and when the normal program resumes. The focus line is also
   the one you read on the record and the sheets. Then the rest of the
   week: each coach-led session and planned run by day, quality runs
   named as quality, and any unresolved collision beside the days it
   ties together, so you see the whole week the lifting fits around.
2. **What's changing.** Plain-word bullets, changes only, each with its
   reason. If nothing changes, the brief says so and why. A one-off week
   shows the Day / Session table for the span instead, with before and
   after where days moved.
3. **Per-session tables.** The rendered region, as it stands: exercise ·
   sets × reps · load · RPE · what changed vs. last week. Dumbbell loads
   show both numbers, `25/hand (Hevy: 50)`, because the renderer prints
   them that way and the coach never retypes a load.
4. **Structural changes** (normal and midweek), if any: their own short
   section with before/after and trade-offs. They land in
   `data/program.json` as well as Hevy.
5. **Hevy housekeeping**, only when there is something to say: each
   STALE routine (one that never received the overlay in force, so you
   would train from old notes); each structural in-app edit with the
   coach's keep-or-replace recommendation (a kept edit becomes a
   structural change; a replaced one is overwritten); and each orphan
   routine with your choice to leave, reuse or retire it. Load-only
   edits you made in the app are overwritten without comment, since the
   log already holds what you lifted.
6. **The write line.** The brief's last line names exactly what "go"
   will write: each Hevy routine in the span by its Hevy title (every
   one, changed or not), each retirement, any new folder, then each
   structural file. Its exact forms:

   ```text
   Reply "go" to train this and write: <routines> (Hevy) · <structural files>.
   ```

   With no structural change, the line ends after `(Hevy).` With Hevy
   off, it names the files only:

   ```text
   Reply "go" to train this and write: <structural files>. Nothing goes to Hevy (no Hevy).
   ```

   With nothing to write at all (no Hevy and no structural change, or a
   reshuffle whose routines already match), it gives the reason:

   ```text
   Reply "go" to train this. Nothing goes to Hevy (<reason>).
   ```

7. **The commit plan** ends the write line: the training records to
   commit with the week, from `python3 -m coach pages plan`, as
   ` Commit: <each path in full>.` or ` Commit: no training records.`
   Config, your profile and `.env` never join it. See
   [Pages and publishing](pages-and-publishing.md).

### The hold-steady short brief

Only a normal-mode pass that `/check-in` started at the weekly tier can
hold steady: never a deep check-in, a light week, another mode or a
standalone run. It is a hold-steady week when all five hold:

1. no structural change (a structural in-app edit to settle counts as
   one);
2. no new or worsening niggle;
3. no goals or phase flag from the check-in;
4. nothing different next week (the Sunday message's Next week field);
5. every prescription change is the progression scheme applied as
   written.

Then the check-in summary and the coach's brief collapse into one
message: three sentences (how the week went, leading with a win; what
changes, or "nothing changes", and why; the focus), the offer "say
'tables' to see the full week", the write line unchanged, and "Reply
go, or tell me what to change." The tables still go into the overlay
and the Hevy notes. "tables" shows them and the write line again; it
approves nothing. A STALE routine does not break hold-steady: the write
line already rewrites it.

## The approval gate

The brief is a proposal, not a notification. The coach presents it and
stops; presenting and writing never happen in the same turn, on a
hold-steady week too.

**"go"** (or a clear yes) approves the span, every write the line names
and its commit plan. The coach does not ask again before writing to
Hevy or committing those records. "go, but don't commit" approves the
rest and drops the commit plan. Anything else is a tweak: the coach
revises and presents the brief again, write line included, until you
would train it. A tweak means the draft is changed, then built,
validated, checked and rendered again.

Decisions agreed at the check-in do not pre-approve the week, and a
Hevy write outside an approved brief is asked for separately.

## What happens after "go"

The coach writes exactly what the write line named, in this order:

1. **Structural changes first** (normal and midweek): it edits
   `data/program.json`, validates and re-renders the program pages,
   re-checks the day before and after each edited session and the
   weekly balance, then rebuilds and finalizes the week's draft so the
   overlay holds the change.
2. **Approve.** `python3 -m coach overlay approve <id>` stamps your
   approval and the hash any later edit breaks. It refuses (exit 3) on
   an unresolved block flag or an unconfirmed load mode; the coach then
   settles it and presents the brief again.
3. **An ended one-off week.** If a one-off span ended before today, its
   temporary routines named in the brief are retired and the one-off is
   cleared from the state.
4. **Push.** With Hevy, routines are created or reused for sessions that
   had none, against the plan hash you reviewed, then
   `python3 -m coach routines push --overlay <id>` writes every routine
   in the span that differs from the overlay, notes included, and logs
   a verification for each one already right. A push refused by a guard
   (exit 3) is reported, never retried by hand; a routine edited in the
   app since the diff is the usual cause, settled with you and pushed
   again.
5. **Verify.** `python3 -m coach routines verify --overlay <id>` reports
   each routine, and the close-out quotes it.
6. **A one-off week** is recorded in the state so the next check-in
   judges the span against it. A light week nobody recorded yet is
   recorded with `block decide`; the check-in that closes the week ends
   the block.
7. **Publish.** Once every routine verifies (or, without Hevy, once
   `python3 -m coach sheets render` has written `this-week-sheets.md`),
   `python3 -m coach pages publish --overlay <id>` re-renders the
   pages, commits the brief, the dashboard, the progress page, the
   overlay, the newest check-in record and the commit plan's records,
   and pushes, so your phone shows the week. It needs the branch to have
   an upstream. A record that changed after approval but was not in the
   plan stays local until you agree.

The recap then says what changed and why, what was written to Hevy,
what was committed and what stayed local, and the one thing to focus
on. A one-off week says when the normal program resumes.

**Without Hevy**, approval is the last write of the pass: every Hevy
command is skipped, `sheets render` writes the per-set sheets you train
from, and the write line says so. See
[Training without Hevy](training-without-hevy.md).

## Run mode

With `mode = "run"` in `config.toml`'s `[coaching]` table, the coach
proposes no structural change in any mode and makes only the ones you
ask for. Loads and checks work exactly as in coach mode: `propose week`
gives the same lines in both.
