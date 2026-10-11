---
name: program-week
description: Use when the coming week (or the rest of this week) needs programming — coach-set loads, rep targets, RPE, and per-exercise notes written to Hevy. Triggers include "/program-week", "program my week", "set my weights for this week", "bump my squat", "reprogram the rest of the week", /check-in finishing its decisions on a normal (non-deload) week, or /new-program finishing a first-time program (the opening week).
---

# Weekly programming pass

Turn the plan plus the latest review into concrete, coach-set
prescriptions for the coming week — per session, per exercise: working
load, rep target, RPE, a weekly focus where warranted, and the standing
form cues. The pass is recorded as the **overlay**
(`data/overlays/<id>.json`, rendered into the check-in history) — the
effective prescription the next check-in judges adherence against. Hevy
users get it written into their routines so the app shows exactly what
the coach wants this week.

The program (`data/program.json`, rendered to `routine/`) stays the
block-level plan — never write weekly numbers into it. Structural
changes (swaps, adds, set counts, execution changes) edit
`data/program.json` — plan first, then Hevy. The `routine/*.md` pages
are rendered by `program render`; never edit them by hand.

Requires `profile.md` and `data/program.json` — if missing, run
`/setup` / `/new-program` first.

**Loads come from `coach` output; quote them.** Never convert kg and
lb, split a dumbbell total or round a load by hand: `units convert`,
`units format` and `units round` do it, and the overlay's rendered
tables are the only loads the brief shows.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop.

When a command fails, tell the athlete what its exit code means, as
`CLAUDE.md` "The coach scripts" sets out.

## 1. Read the context

`profile.md` (constraints, niggle log, Coach's notes), `python3 -m coach
program show` (sessions, set groups, progression schemes, start loads,
cues) and `python3 -m coach state show` (rotation, block, any one-off
week), `routine/program.md` for the program at a glance, the newest
check-in (decisions, window, any overlay already rendered), and
`python3 -m coach overlay current` (the overlay in force today).

**Logged workouts (Hevy users).** Run `python3 -m coach hevy pull`, then
`python3 -m coach hevy status` for the cache's age and counts — when
`/check-in` invoked this skill, its pull is fresh; don't pull again.
Read recent workouts from the cache (`.coach/cache/hevy/workouts/`,
newest first) for current working weights, turning each logged Hevy
value into the athlete's number with `python3 -m coach units convert
--mode <load mode> --from-hevy-kg <value>` (the load mode from `python3
-m coach library show <id>`). No Hevy → ask the athlete for their
current weights. Read each logged workout's `description` and
per-exercise `notes` too — the athlete's own account of how the sets
felt ("target too high, did back-off sets", "wiped out after
yesterday's run") should temper the next week's loads as much as the
numbers do.

**Rotation position.** If the program rotates, infer which week is next
and state it for confirmation — never ask it as its own question, and
never assume it silently. Sources, in order: the coach-led session's log,
`rotation.position` in `state show`, the newest check-in.
When `/check-in` invoked this skill, its Sunday message already stated
the position and the reply confirmed or corrected it — use that.
Standalone, state it in the brief's week focus ("Week B, going by
Tuesday's PT log — say if not"). If the sources disagree, state the
first one and name the disagreement.

**Days off.** Count the days from the last lifting workout of any kind
— solo, or coach-led as the log, the newest check-in or the athlete
says — to the first session of the span. Do this on every run,
standalone included; with no workout logged yet, skip it. Over 10 days
makes this a **return week**: step 2 applies the return rule in
`CLAUDE.md` "Coaching principles", matching band and all. An `ill` miss tag or illness in the gap adds that rule's
illness conditions; standalone, ask whether illness caused the gap.

**Brand-new program?** An empty `check-ins/` is normal — there's no
overlay or decisions to read. With no logged workouts yet, working
weights come from the program's start loads (`program show`) or the
athlete, not from logs.

**Stand down if a one-off week is active.** If `state show` has a
`one_off` whose span covers this span, `/one-off-week` owns it — say so
and stop.

**Mid-week?** Invoked standalone partway through a trained week, first
ask what prompted it (missed session, easy/hard day, schedule change),
then reprogram only the remaining days.

**Hevy freshness (Hevy users).** With an overlay in force, run
`python3 -m coach routines verify --overlay <its id>` after the pull; no
overlay yet → skip it. Each routine it reports with `verified: false`
carries its `changes`:

- **Edited in the app** — any change of class `structural` (exercises,
  their order, set counts, reps or rep ranges, rest, supersets) is an
  in-app edit made since that pass. **Structural edits** go in the
  coach's brief as keep-or-replace questions, settled by the same
  approval as the week.
- **Load-only edits** — `prescription` changes to set loads only are
  overwritten without comment: the log already holds what was lifted,
  and this week's loads come from the log.
- **STALE** — a `prescription` change to an exercise's notes: the
  routine doesn't carry the overlay in force, so the athlete would
  train from old notes. List each in the coach's brief (on a
  hold-steady week, its close-out) as STALE.

**First run: cue backfill.** If the program's exercises have no `cues`,
offer a one-time backfill before programming: agree the canonical form
cues for each exercise with the athlete, write them into each
exercise's `cues` in `data/program.json`, then run `python3 -m coach
program validate` and `python3 -m coach program render`.

## 2. Compute the week — per session, per exercise

Work through every session in the span, every exercise in each:

- **Load** — from the log and the program's progression rules: top of
  the rep range at or under target RPE → add load (the program's
  increment); reps missed → hold; RPE drift (logged RPE 1 or more over
  the target on 2 or more working sets of one exposure) on a compound
  lift or a set carrying a **recovery cap** → hold or back off. Compound
  means a multi-joint squat, hinge, lunge, press or pull pattern. RPE drift
  alone never holds back isolation work: it progresses on reps as the
  scheme says, unless the athlete's notes report pain or form breakdown.
  Reason per lift — a formula applied blindly is not coaching. Work in
  the athlete's units and the load mode's own number — per hand for
  dumbbell work — taken from `units convert`, so the increment lands on
  the right number; snap a new load to the kit with `python3 -m coach
  units round --value <load> --increment <step>`. If the log shows an
  exact 2× jump at unchanged reps and RPE, that's a convention slip,
  not progress — don't progress off it, raise it with the athlete.
- **Rep target / RPE** — move them where the block's scheme calls for
  it.
- **Focus** — one per-exercise emphasis where warranted, drawn from
  check-in findings ("slow the eccentric", "depth fades when tired").
  Most exercises most weeks won't have one — that's fine.
- **Return week** — when step 1 found a return week, the matching
  return band sets this week's loads, set counts and any RPE
  cap instead of the progression scheme, measured from the pre-layoff
  working loads; with illness, the first session back carries the
  illness cap. Name the band in the week focus. The next pass
  progresses from what the return week logged.
- **Structural changes** — swaps or additions agreed at the check-in,
  or proposed now with rationale. These are plan changes: mark them
  separately, they land in `data/program.json` too. Under 80 % adherence (as
  `/check-in` step 4 defines it), propose no new recurring session —
  no new session or weekly slot, conditioning and optional ones
  included — and push back if the athlete asks; exercise swaps within a
  session are fine. An override goes in the next check-in's adherence
  decision line.

Active niggles constrain everything: no added load on an aggravated
pattern.

## 3. Build the overlay

1. **Where it renders.** When `/check-in` invoked this skill, its new
   record's "The week ahead" section takes the overlay. Standalone, add
   a section to the newest check-in — `## Week reprogrammed —
   YYYY-MM-DD`, then `**Span:** <start> → <end> · **Reason:** <missed
   session / …>`, then the new overlay's two region markers
   (`<!-- coach:begin overlay <id> -->` and `<!-- coach:end overlay
   <id> -->`, each on its own line) once `overlay build` gives the id. **No
   check-in record yet** (brand-new program): create
   `check-ins/YYYY-MM-DD.md` with a minimal first record — a header
   noting the program start date and structure, then `## The week
   ahead`. The first `/check-in` judges adherence against it.
2. **Write the draft** at `.coach/drafts/overlay-<span start>.json`, in
   the athlete's units (`coach/schemas/overlay_draft.schema.json`):
   `kind` `weekly` (`midweek` for a mid-week reprogram), `span`, the
   week `focus`, and per session its program `session_id`, `date` and
   `title`; per exercise `exercise_id`, `hevy_template_id` (from
   `library show`), `load_mode`, `rest_seconds`, `cues` (from the
   program), `focus`, `target_note` and `change` (the brief's relative
   wording — these never reach Hevy), and `sets`, each load a number:
   per hand for per-hand modes, the added load for bodyweight, else the
   total.
3. `python3 -m coach overlay build --input <draft>` writes
   `data/overlays/<id>.json` and gives the id.
4. `python3 -m coach overlay validate <id>` — exit 1 lists each problem
   by JSONPath. Fix the draft, put the id in it, and build again: a
   draft that names an unapproved overlay rebuilds it.

   **Then check every prescription before the brief.** Run `python3 -m
   coach history sync`, then `python3 -m coach prescription check
   --overlay <id> --write` (`--file <draft>` checks a draft without
   building it). It stores its flags in the overlay and records, for
   each line you wrote by hand, the exposure it came from. Per line it
   reports `days_off` and the return `band`. Settle each flag:

   - `stale_prescription` (block) — the lift's days off fall in a
     return band, or an `ill` gap caps the first session back at RPE 7.
     Decay the line to that band as step 2's return week says, and
     record it in the line's `provenance.decay` (`days_off`, `band`,
     `load_factor`, `set_delta`, `rpe_cap`) with `derived_from` set to
     the exposure it came from.
   - `unearned_load` (block) — the load is beyond failure for those
     reps at the recent e1RM. Lower it.
   - `load_cap`, `load_unrepresentable` (block) — over a cap, or not a
     load the kit at the session's location makes. Snap it with `units
     round` to a load that is.
   - `load_mode_mismatch` (block) — the line's load mode or load
     arithmetic disagrees with the library. Fix the line, or settle the
     load mode with the athlete (`library set-mode`).
   - `rpe_infeasible`, `session_over_cap` (warn) — name each in the
     coach's brief, with the change you made or why it stands.

   Fix the draft, then build, validate and check again until no
   `block` flag is left. A block you and the athlete decide to keep
   needs its flag's `resolved` set true with a `resolution` in the
   overlay, or `overlay approve` refuses it.
5. `python3 -m coach overlay render <id> --into <check-in record>`
   fills the week-ahead region — the per-session tables the brief
   shows.
6. **Hevy users:** `python3 -m coach routines diff --overlay <id>`
   lists every routine in the span by its Hevy title, with what "go"
   would change. A session with no routine makes it exit 1 naming the
   session — and then it lists nothing, not even the routines that
   exist. Name them another way: "go" creates a routine for each
   session the exit-1 message names, under its session title; every
   other session's routine keeps its own Hevy title (`state show` maps
   it to the session, and `.coach/cache/hevy/routines.json` holds the
   title).

A tweak to the coach's brief (step 4) means: edit the draft, then
build, validate, check and render again.

## 4. Present the coach's brief — and stop

Talk the athlete through the week the way a coach would: narrative
first, tables second.

1. **Week focus** — 1–2 sentences: what this week is doing and why,
   tied to the current phase and goal.
2. **What's changing** — plain-word bullets, changes only, each with
   its reason ("Squat 80 → 82.5 kg — you hit 5×5 @ RPE 7.5 last week,
   room to move"). Never restate every exercise here. If nothing
   changes, say so and why — that's still a decision worth explaining.
3. **Per-session tables** — the rendered region from `overlay render`,
   as it stands: exercise · sets × reps · load · RPE · what changed vs.
   last week. A one-line session focus above a table only where there's
   something to say — most sessions most weeks won't have one. Dumbbell
   loads show both numbers (`25/hand (Hevy: 50)`) because the renderer
   prints them that way — never retype a load.
4. **Structural changes** (if any) — their own short section with
   before/after and trade-offs.
5. **Hevy housekeeping** (only when there's something to say) — each
   STALE routine, and each structural in-app edit with your
   keep-or-replace recommendation ("You swapped leg press for hack
   squat in Lower A — keep it; I'll add it to the program"). A kept
   edit is a structural change and lands in `data/program.json`; a
   replaced one is overwritten.
6. **The write line** — the brief's last line names exactly what "go"
   will write: each Hevy routine in the span by its Hevy title from
   `routines diff` (every one, changed or not), or from the titles step
   3.6 names when it exited 1 (every routine, plus any "go" creates),
   then `data/program.json` when there's a structural change:

   `Reply "go" to train this and write: Upper A, Lower A, Upper B (Hevy) · data/program.json (structural change).`

   No structural change → drop the `data/program.json` part. Nothing
   going to Hevy (the athlete doesn't use it) → the line says so:
   `Reply "go" to train this and write: data/program.json (structural change). Nothing goes to Hevy (no Hevy).`
   or, with no structural change either,
   `Reply "go" to train this. Nothing goes to Hevy (no Hevy).`

**Hold-steady week: the short brief.** Only a pass invoked by
`/check-in` at the **weekly tier**, on a week that is **not a deload**,
can hold steady — never a deep check-in, a deload week, or a standalone
run. It is a
hold-steady week when all five hold:

1. no structural change (a structural in-app edit to settle counts as
   one);
2. no new or worsening niggle;
3. no goals/phase flag from the check-in;
4. nothing different next week (the Sunday message's Next week field);
5. every prescription change is the progression scheme applied as
   written.

On a hold-steady week the check-in summary and the coach's brief
collapse into one message, in this order:

- **three sentences** — how the week went, leading with a win; what
  changes, or "nothing changes", and why; the focus;
- the offer: "say 'tables' to see the full week" — per-session tables
  are offered, not shown, but still go into the rendered overlay and
  the Hevy `Target:` lines;
- the write line above, unchanged;
- "Reply go, or tell me what to change."

A STALE routine doesn't break hold-steady: the write line already
rewrites it, so name it in the close-out instead. "tables" shows the
tables and the write line again — it approves nothing.

Then **stop and wait for the athlete's reply. Never present and write
in the same turn** — the brief is a proposal, not a notification, and
that holds even on a hold-steady week. **"go" (or a clear yes) approves
the week and every write the line names** — don't ask again before
writing to Hevy. Anything else is a tweak: revise and present the brief
again, write line included. Iterate until they would train it.

## 5. Write

**Only enter this step after the athlete has replied "go" (or a clear
yes) to the brief above.** If no brief with a write line has been
presented and approved this session, go back to step 4. Write exactly
what the write line named — nothing more.

1. **Structural changes first** — edit `data/program.json` as the write
   line named (an execution change like grip width edits that
   exercise's `cues`), then run `python3 -m coach program validate` and
   `python3 -m coach program render`. Re-check the day before and after
   each edited session and the program's weekly balance.
2. `python3 -m coach overlay approve <id>` stamps the athlete's
   approval. It exits 3 on an unresolved `block` flag: tell the athlete
   why, settle it, and present the brief again.
3. **Hevy users.** If `routines diff` named sessions with no routine,
   run `python3 -m coach routines create --overlay <id>` first. Then
   `python3 -m coach routines push --overlay <id>`: the permission
   prompt shows what it will write, which is what the athlete approved.
   It writes **every** routine in the span that differs from the
   overlay, notes included: the week line, Target, Focus and Cues all
   come from the overlay. A push that **exits 3** was
   refused by a guard: report its reason to the athlete and never retry
   it by hand. A routine edited in the app since the diff is the usual
   one — run `python3 -m coach routines diff --overlay <id> --refresh`,
   settle the edit with the athlete, and push again. Exit 1 means a
   routine didn't read back as written; report it. Only when a command
   keeps failing and the athlete agrees, use `reference/hevy-api.md` →
   "Manual fallback".
4. `python3 -m coach routines verify --overlay <id>` — the close-out
   quotes its result for each routine.
5. **An ended one-off week.** If `state show` has a `one_off` whose span
   ended before today, run `python3 -m coach routines retire --overlay
   <its overlay_id>` to retitle its temporary routines `(unused)`, then
   set `one_off` to null in `data/state.json` and run `python3 -m coach
   state show` to check it.

**No Hevy?** Skip steps 3–5's Hevy commands — the rendered overlay is
the deliverable, and the athlete trains from it.

## 6. Record the overlay

The overlay is already in the record: `overlay render --into` wrote the
region in step 3. In a check-in's "The week ahead" section, the
week-focus line follows the region and ends the section. The approval
and every Hevy write and verification are logged in
`data/hevy/writes.jsonl`; nothing else needs recording.

## 7. Close out

**Publish the week.** Hevy users: only once `routines verify` reports
every routine verified; a routine left unverified means no publish, and
the recap says why. No Hevy: once `overlay approve` has stamped the
approval. Run `python3 -m coach pages render`, then `python3 -m coach
pages publish --overlay <id>`: it commits exactly the brief
(`this-week.md`), the dashboard (`README.md`), `progress.md`, the overlay
and the newest check-in record, and pushes them so the athlete's phone
shows the week. If `pages render` exits 3 because `README.md` is still
the template's copy, ask once whether the dashboard may replace it, then
run `python3 -m coach pages render --replace-readme`. A publish that
exits 3 (overlay not approved, another file already staged) is reported,
never worked around; exit 4 means the push failed and the commit is
kept: tell the athlete to push by hand.

Recap in plain words: what changed this week and why, what was written
to Hevy (quote `routines verify`: each routine verified, or not and
why, plus, on a hold-steady week, any routine that was STALE before
it), and the one thing to focus on. If a structural change landed,
note it for the next check-in's Decisions section.
