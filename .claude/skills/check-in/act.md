# Act on it

- **Hold-steady week** (defined in program-week's brief): present no
  separate check-in summary: it and the coach's brief collapse into
  program-week's short brief. Deep check-ins and light weeks never take
  that path.
- Otherwise, propose adjustments with rationale and trade-offs. **Only
  change the program after the athlete approves**: on normal weeks the
  change lands in `data/program.json` through program-week's write step
  (below); re-check the day before and after any edited day and the
  program's weekly balance.
- Update `profile.md`: e1RMs (a `total_system` one with "total system
  mass" after its number) in whole units as the card shows them, watch
  notes, and `_Last reviewed_` when they move (the deep tier refreshes
  the whole file). Add or retire **Coach's notes** as patterns emerge or
  resolve, with the athlete's confirmation.
- **Maintain the niggle log** in `data/niggles.json` with the `niggles`
  commands; statuses `aggravated` / `watching` / `easing` / `resolved`,
  and `chronic` for a lasting limitation. New complaint: `python3 -m
  coach niggles add --area "<where>" --status <status> --pattern
  <patterns> --note "<report>"` (`--exercise` and `--activity-kinds`
  name anything else it affects). Repeat mention: `python3 -m coach
  niggles update <id> --mention --status <status> --note "<report>"`.
  A status the athlete reports for an earlier day (it flared Tuesday)
  takes `--date <that day>`, in date order: a flare counts toward a
  closed week's niggle trigger only when dated inside that week, so after
  a dated report run `block close` for that week again (analyze.md).
  Confirmed gone: `python3 -m coach niggles resolve <id>`, which **keeps
  the row**: recurrence is the signal this log exists to catch. Agree
  with the athlete the limit an active niggle sets. A lasting limit is a
  standing one: `--constraint` (`rpe_cap=7`, the recovery cap;
  `no_added_load`; `load_cap=<n>`), applied while the status is
  `aggravated` or `watching` (always, for `chronic`). A tighter limit for
  this flare only goes with the status report: `--status aggravated
  --flare-constraint rpe_cap=6`; it ends when the status changes, and
  the standing limit returns. Never tighten `--constraint` for a flare.
  `propose week` brings each capped load to what the e1RM allows and
  names the niggle in `constraint_applied`. A `niggles` status line
  asking to confirm a limit: agree it with the athlete and set it again
  with `--constraint`. Escalate — recommend a
  qualified professional and program around it meanwhile, never
  diagnose — when `python3 -m coach niggles list` gives a row an
  `escalate` reason (three check-ins running, or worse to
  `aggravated`), or when a niggle interferes with prescribed training.
- **A `run_volume_spike`** (analyze.md): ask about symptoms, how the
  athlete recovered and the next long run, agree an action (hold the next
  long run, shorten it, or review it next week) and record it with
  `python3 -m coach followups add --text "<action>" --review-at <date>
  --source "check-in <date>"`. A spike is not a fatigue trigger: never pass
  it to `block close`, and cut no load for it alone.
- **Update `data/state.json`:** the confirmed `rotation` (`position`,
  `confirmed`, `confirmed_at`) if the program rotates. `block` is
  written only by the `block` commands (analyze.md and below). Then run
  `python3 -m coach program validate`, `python3 -m coach state show` (it
  refuses an invalid state) and `python3 -m coach program render`, and
  write the block status line into the record (record.md).
- **A light week proposed** at the ceiling or on two triggers: present
  it with its reason. Record the answer with `python3 -m coach block
  decide --outcome adopted` (add `--type` and `--reason` to choose
  another type) or `--outcome declined --reason "<why>"`; at the
  ceiling, the next close proposes it again. To call a light week nobody
  proposed, use `--outcome adopted --type <type> --reason "<why>"`.
- **Adherence trigger adopted** (the smaller schedule, not an override):
  hand off to `/new-program`'s redesign path with the agreed smaller
  schedule. Under 80 % adherence (analyze.md), propose no new recurring
  session, here or in program-week.

## Hand over to program-week

Once decisions are agreed, invoke the **program-week** skill for the
coming week: on a normal week in normal mode; when a light week is
agreed, invoke the **program-week** skill in light mode, which builds it
with the `command` that `block decide` printed; for travel or limited
kit named in the Next week field, in constrained mode (reshuffle when
only the days move); for agreed days with no training at all, record
the planned break instead (sunday-message.md, status days). Either way
it fills this record's "The week ahead" section and handles the Hevy
writes; after a light week the count resets when the next check-in
closes that week.

**Decisions agreed at this check-in don't pre-approve the week**:
program-week still presents its coach's brief and waits for the
athlete's reply before writing anything. One "go" to that brief
approves the week and every write its closing line names (the Hevy
routines and any structural program edits), so don't ask again before
writing. Structural routine changes agreed today ride along in its
write step; `/hevy-sync` stays for reconciliation outside the pass.
Once the week's overlay is approved, refresh the record with `checkin
skeleton --refresh --overlay <id>` (record.md).
