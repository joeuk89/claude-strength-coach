# Compute the week (normal, midweek, light and minimum modes)

The scripts compute each line; you coach it. Reason per lift: a formula
applied blindly is not coaching.

## 1. Propose

Run `python3 -m coach history sync`, then the proposal for the mode:

- **normal:** `python3 -m coach propose week --week <label>`.
- **midweek:** the same with `--kind midweek`, which re-proposes only
  the remaining days of the week.
- **light:** the `command` that `block decide` printed for the light week
  the check-in agreed. Standalone, with no light week agreed in `state
  show`, run the command it would print: `python3 -m coach propose week
  --kind deload --week <label>`, adding `--transform light` for a light
  week or `--transform return` for a return week, such as a return after
  illness; write.md records the week after "go". A deload applies the
  program's deload rule (`blocks.deload_rule` in `program show`) to
  every program session in the span; the standard rule keeps two thirds of each line's working
  sets, takes 10 % off loads from the current working weights and puts
  every set at RPE 6 (rn:deloads.9); these numbers are a coaching
  heuristic. It cuts bodyweight work by sets and takes it further from
  failure. Its sessions are temporary (`"temporary": true`, titled
  "Deload — <session title>") and keep their program session ids. Keep
  the program's priority protocols alive at a reduced dose (ladders
  resumed, not restarted). Remind the athlete to tell any coach or PT
  it's a deload week, and deload whatever the profile says moves with
  the lifting (conditioning and the like). A week back after illness
  follows the return rule in `CLAUDE.md` "Coaching principles": its
  illness conditions (when training may restart, the first session's
  cap, when the athlete checks with a qualified professional first)
  and, after a long gap, its matching band.
- **minimum:** validate the configured minimum and write its plan as
  [short-week.md](short-week.md) says, then `python3 -m coach propose
  week --week <label> --plan <the path structure minimum printed>`
  proposes the week from it as a weekly overlay.

`propose week` plans the span's dated sessions with the program's
schedule rule and asks each exercise's progression scheme for its line,
in the athlete's units and the load mode's own number. Each scheme reads
the log: double progression keeps the program's rep range and target
RPE and adds the increment once every set reaches the top of the range
(at or under target RPE, except uncapped isolation work), missed reps
hold, and loads never derive from an open convention slip. The core
then decays a lift past its validity window to its return band, caps
every set of the first session after illness at RPE 7, applies the
slot's load constraints and the caps and kit at the session's location,
and rounds each load to the kit. It writes an editable draft
(`.coach/proposals/<id>.json`) and prints `data.lines`: per line its
sets (loads through `units format`), the `change`, a one-sentence
`rationale` and its flags.

## 2. Read every line against the check-in

Read each line against the athlete's notes on how sets felt, niggles
and the rotation position, and settle its flags:

- `rpe_drift` (logged RPE 1 or more over target on 2 or more working
  sets of a compound lift or a set carrying a **recovery cap**): hold or
  back off. RPE drift alone never holds back isolation work: it
  progresses on reps as the scheme says, unless the athlete's notes
  report pain or form breakdown.
- `range_effort_mismatch` (a held double-progression line whose last
  exposure fell below the rep range or 2 or more RPE over target):
  agree a lighter load or a different rep range with the athlete and
  override the line, or resolve the flag with the reason the load
  stands (step 4).
- `convention_slip`: an exact 2× jump at unchanged reps and RPE is a
  convention slip, not progress. Raise it with the athlete.
- `return_week`, `return_after_illness`: in a return week the matching
  return band sets this week's loads, set counts and any RPE cap instead
  of the progression scheme, measured from the pre-layoff working loads;
  with illness, the first session back carries the illness cap. Name
  the band in the week focus; with illness, ask whether the symptoms
  stayed above the neck and confirm 48 hours symptom-free
  (rn:detraining-return.4); whole-body symptoms mean a qualified
  professional first. The next pass progresses from what the return
  week logged.
- `collision` (an interference rule: a quality activity on a lifting
  day, or in the 24 hours before a heavy squat or hinge session; the
  message names the rule, both bouts and the gap): the script never
  moves anything. Agree with the athlete what moves, usually the run,
  or keep the plan and resolve the flag with the reason (step 4).
  `python3 -m coach interference list` shows the program's rules.
- `conditioning_dropped` (the drop rule: sleep debt, a status day on the
  date, or a quality activity the day either side): at info, an optional
  conditioning session left the draft, listed in `data.dropped` with its
  trigger. If the athlete still wants it, put it back with
  `python3 -m coach propose restore --proposal <id> --session <session>
  --reason "<why>"`, which resolves the flag. At warn, a core conditioning
  session stayed: agree whether to ease or move it, then resolve the
  flag (step 4).
- `incomplete_exposure` (fewer sets logged than prescribed, none short):
  no miss counts. If the misses already counted reach the line's
  `misses_before_reset`, the line resets anyway and needs no question.
  Otherwise the load holds: ask whether the missing sets were skipped or
  failed. A failed set is a miss: when it reaches `misses_before_reset`,
  override the line to the reset load (step 3); below it the load holds
  and nothing records the miss, so name it at the next check-in.
- `no_data` (set the first load with the athlete), `stalled`,
  `constraint_applied`, `override_standing`, `scheme_reset`,
  `rotation_unconfirmed` (state the position for confirmation, as
  context.md says); build.md's check settles its own flags.

## 3. Change a line

Run `python3 -m coach propose override --proposal <id> --session
<session> --exercise <exercise> (--sets "3x5@95 rpe7" | --load <n>)
--reason "<why>"`; a timed hold takes seconds, `--sets "2x35s rpe7"`.
Add `--standing` (and `--until <date>`, eight weeks at most; four by
default) when the change should hold in later weeks — a niggle, an
agreed hold — so the scheme stops proposing it away. A per-exercise
**focus** drawn from check-in findings ("slow the eccentric") may go
into the draft line, with an `override` reason saying why; any line
changed without a reason is refused. An override onto another rung of
an assistance ladder moves the ladder to that rung once the week is
approved.

Niggle limits are already in the proposal: `propose week` applies each
active niggle's constraints to every matching line and names the niggle
in `constraint_applied`; `python3 -m coach niggles constraints` lists
them. A `niggle_escalate` flag means recommend a qualified professional
and keep programming around it, never diagnose; a `followup_due` flag
names a follow-up to raise with the athlete.

## 4. Keep a flag

Keep a flag you and the athlete decide to accept with `python3 -m coach
propose resolve --proposal <id> --flag <index> --resolution "<why>"`.
A `load_mode_unconfirmed` flag cannot be kept: ask the athlete how they
load the exercise, then run the command its message names.

## 5. Structural changes (normal and midweek)

Swaps or additions agreed at the check-in, or proposed now with
rationale, are plan changes: mark them separately in the brief; they
land in `data/program.json` too. Under 80 % adherence (as `/check-in`
step 4 defines it), propose no new recurring session — no new session
or weekly slot, conditioning and optional ones included — and push back
if the athlete asks; exercise swaps within a session are fine. An
override goes in the next check-in's adherence decision line.

## 6. Finalize

`python3 -m coach propose finalize --proposal <id>` writes
`data/overlays/<id>.json`. Exit 1 names each line changed without an
override reason; exit 3 names each unresolved `block` flag. A refused
finalize writes nothing: fix what it names and run it again. Then go to
build.md with that id, starting at "Where it renders". A tweak to the
coach's brief later means: override or resolve in the draft, finalize
again, then check and render again.
