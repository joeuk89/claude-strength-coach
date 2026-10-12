# The coach's brief

Talk the athlete through the span the way a coach would: narrative
first, tables second. Every mode uses the same brief.

1. **Week focus:** one or two sentences on what the span is doing and
   why, tied to the current phase and goal, with the mode named. A
   one-off week says why it deviates: the reason, what's protected (the
   program's priority work), what's deliberately dropped, and when the
   normal program resumes. Before finalizing a proposed week, put the
   athlete's line of it ("Practise a controlled squat descent") in the
   draft as its week focus, replacing the generic line (compute.md step
   3). **Athlete guidance** on a line (its note, focus or cues) is what
   the athlete reads on the record and the sheets: an instruction ("10
   per leg", "stop at RPE 9"), never the override reason. A rebuild
   keeps both. Keep the scheme's own notes (wave week, ladder rung,
   deload) as they are. A line with no logged load carries a calibration
   note; once an override sets the load, it says to adjust after the
   first working set: keep it while it holds, and never swap in an
   unexplained number. For a
   beginner, agree each session's first loaded lift's warm-up: the
   program's warm-up sets, or the qualitative ramp note the proposal
   adds (reword it with the athlete if they want); no warm-up loads or
   percentages the coach has not agreed, and never a test to failure.
   Their sheets end with a short RPE and rep-range key.
2. **What's changing:** plain-word bullets, changes only, each with its
   reason ("Squat 80 → 82.5 kg: you hit 5×5 @ RPE 7.5 last week, room
   to move"). Never restate every exercise here. If nothing changes, say
   so and why: that's still a decision worth explaining. A one-off week
   shows the Day / Session table for the span instead, with before and
   after where days moved.
3. **Per-session tables:** the rendered region from `overlay render`, as
   it stands: exercise · sets × reps · load · RPE · what changed vs. last
   week. A one-line session focus above a table only where there's
   something to say. Dumbbell loads show both numbers (`25/hand (Hevy:
   50)`) because the renderer prints them that way: never retype a load.
4. **Structural changes** (normal and midweek, if any): their own short
   section with before/after and trade-offs.
5. **Hevy housekeeping** (only when there's something to say): each
   STALE routine, and each structural in-app edit with your
   keep-or-replace recommendation ("You swapped leg press for hack squat
   in Lower A: keep it; I'll add it to the program"). A kept edit is a
   structural change and lands in `data/program.json`; a replaced one is
   overwritten. List managed orphan routines and the athlete's choice
   for each: leave, reuse for a named session, or retire. Preview any
   ended one-off retirement with `--routine <id>` for each of its
   temporary routines; exclude routines the create preview reuses.
   Retain its `plan_hash` for write.md. Reuse itself replaces the old content; it needs no
   preceding retirement.
6. **The write line:** the brief's last line names exactly what "go"
   will write: each Hevy routine in the span by its Hevy title from
   `routines diff` (every one, changed or not), or from the titles
   build.md names when it exited 1 (every routine, plus any "go"
   creates or reuses), each retirement by title and id, any new folder,
   then each structural file:

   `Reply "go" to train this and write: <routines> (Hevy) · <structural files>.`

   For example: Upper A, Lower A, Upper B (Hevy) · data/program.json
   (structural change). With no structural change, the line ends after
   `(Hevy).` With Hevy off, the line names the files only:

   `Reply "go" to train this and write: <structural files>. Nothing goes to Hevy (no Hevy).`

   With nothing to write at all (no Hevy and no structural change, or a
   reshuffle whose routines already match), the line gives the reason,
   `no Hevy` or `reshuffle only`:

   `Reply "go" to train this. Nothing goes to Hevy (<reason>).`

7. **The commit plan** ends the write line, `missed plan`'s too, but
   not a `skip` rule's (midweek.md). Run `python3 -m coach pages plan`
   with a flag for each step "go" will run, so the plan also names what
   those steps write: `--structural` with `--session <id>` for each
   session the change edits, adds or removes; `--light-week` when
   write.md step 6 will run `block decide`; `--one-off` for a one-off
   week, or when `state show` has a `one_off` that ended;
   `--create-routines` when `routines diff` named sessions with no
   routine; `--missed` for a matched missed-day rule. `include` lists
   each record to commit, changed now or `planned`. Append
   ` Commit: <each path in full>.`, or ` Commit: no training records.`
   when there are none. Config, profile, `.env` and other files never
   join it. When `program_changed` is true without a structural change
   in the brief, say `data/program.json` stays local.

## Hold-steady week: the short brief

Only a normal-mode pass started by `/check-in` at the **weekly tier**
can hold steady: never a deep check-in, a light week, another mode or a
standalone run. It is a hold-steady week when all five hold:

1. no structural change (a structural in-app edit to settle counts as
   one);
2. no new or worsening niggle;
3. no goals/phase flag from the check-in;
4. nothing different next week (the Sunday message's Next week field);
5. every prescription change is the progression scheme applied as
   written.

On a hold-steady week the check-in summary and the coach's brief
collapse into one message, in this order:

- **three sentences:** how the week went, leading with a win; what
  changes, or "nothing changes", and why; the focus;
- the offer "say 'tables' to see the full week": per-session tables are
  offered, not shown, but still go into the rendered overlay and the
  Hevy `Target:` lines;
- the write line, unchanged;
- "Reply go, or tell me what to change."

A STALE routine doesn't break hold-steady: the write line already
rewrites it, so name it in the close-out instead. "tables" shows the
tables and the write line again; it approves nothing.

## Then stop

Stop and wait for the athlete's reply. Never present and write in the
same turn: the brief is a proposal, not a notification, and that holds
on a hold-steady week too. **"go" (or a clear yes) approves the span,
every write the line names and its commit plan**: don't ask again before
writing to Hevy or committing those records. A yes that keeps the
records local ("go, but don't commit") approves the rest: drop the
commit plan. Anything else is a tweak: revise, and present the brief
again, write line included. Iterate until they would train it.
