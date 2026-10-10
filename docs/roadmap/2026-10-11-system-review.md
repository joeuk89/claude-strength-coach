# System review roadmap — 2026-10-11

A full review of the training workspace: one stock-take, one research pass
on cardio data sources, seven critiques (coaching science, system design,
data model, athlete experience, cardio and health, nutrition, devil's
advocate), synthesised into the ranked plan below.

This file is public and generic. The evidence behind each item (the
reference athlete's check-ins, lift numbers, adherence record) lives in
that athlete's private instance under `docs/reviews/2026-10-11/`. Nothing
here should name a person or quote their data.

## How to read this

- Items are grouped into phases and ranked within each phase. Phase order
  follows the author's priority ranking: **1 reliability** (no wrong or
  contradictory prescription reaches Hevy), **2 weekly effort** (less
  athlete time per check-in), **3 coaching quality**, **4 generality**.
- Each item: problem, design sketch, size (S under a day, M a few days,
  L a week or more), migration impact on an existing instance,
  dependencies, which priority it serves, and which review lens raised it.
- Phase 0 is prose-only and ships before any code. It exists because the
  review found that most recorded coaching failures were dose and judgement
  failures, which rules fix, while the arithmetic failures were narrow and
  are fixed by Phase 1.
- Every item is shippable alone and lands in instances via
  `/framework-sync`. Build one at a time; design each with the athlete
  before writing its plan.

## What the review found

1. **No computation is scripted.** Unit conversion, the dumbbell per-hand
   versus Hevy doubling, e1RM, adherence, progression decisions, deload
   transforms, date math and macro sums are all redone by the agent every
   run. The dumbbell rule is written in eight places and still produced a
   doubled load in Hevy that sat there for three weeks.
2. **Hevy writes are hand-built and unverifiable** after the fact. Routine
   notes carry stale narration and stale loads for weeks because nothing
   regenerates every note on every pass.
3. **The weekly prescription has no home of its own.** It lives in the
   newest check-in as a markdown table whose columns changed three times in
   two months, so nothing can compute adherence or drift.
4. **The program was sized to planned dose, never delivered dose.**
   Adherence ran at roughly half for weeks while the plan kept adding
   sessions. The structure question was raised four times and chained to a
   deload review that never ran. Five deloads were pencilled and none
   executed. Three post-illness on-ramps were improvised and ran long.
5. **Prescriptions have no validity window**, so loads earned before a
   layoff were carried in Hevy for a month and then called "unearned".
6. **The check-in costs 45 to 90 minutes, not the promised ten**, driven by
   a one-question-at-a-time interview that re-asks for inputs the athlete
   has never supplied (waist seven times, sleep hours never). Seven
   mid-week reprograms in one month each produced a 60 to 140 line record,
   three of them changing nothing.
7. **The loop stalls when it is needed most.** After a gap, the only
   re-entry point is a full check-in, which gets longer with the gap.
8. **Nutrition tooling was abandoned after two days of use.** Twelve
   athlete touchpoints per meal plan, a pantry prerequisite never created,
   a protein floor set at the top of the evidence range and never hit, and a
   competing calorie estimate run against the app the framework says is
   the engine.
9. **Cardio and health are blind spots.** No run history, no sleep hours,
   no structured record of coach-led sessions, and no cross-modal load
   figure, for an athlete whose stated limiter is sleep.
10. **Formats drift and migrate by hand.** No schema versions, fifteen
    facts duplicated in two or more places, a profile that has become an
    append-only log, and the Notion mirror already stale and unread.

## Decisions this roadmap builds on

Agreed with the author before the critique ran. Full text in the private
review folder (`settled-design.md`).

- Generic template for any athlete and any program style; personal data
  only in the instance. Incremental delivery.
- Python 3.11+ standard library only, unit tests in the template only.
  TOML for human-edited config (read-only in stdlib, so scripts never write
  it), JSON for machine-written data, markdown for prose humans read.
- Structured source of truth wherever a script reads or writes; markdown
  rendered from it and checked for freshness. Versioned migrations run by
  `/framework-sync` with backups and review tables.
- Program = Sessions + Schedule rule + Blocks with a deload rule + a named
  Progression scheme per exercise. Schemes, schedule rules and deload
  transforms are plugin modules with declared parameter and state schemas.
  A `hold` scheme covers anything coach-managed, so the engine never has
  to model every protocol. **No plugin is written during a check-in**; a
  new scheme is a code change with fixture tests.
- Script proposes, coach disposes. Overrides are recorded with reasons and
  persist. Every Hevy write stays behind the athlete's approval, enforced
  mechanically, not by prose.
- A standing weekly brief at the repo root, rendered, with the focus line
  mirrored into the first exercise note of each Hevy routine (the API
  drops routine-level notes). GitHub's own markdown rendering of the
  private instance replaces Notion. Notion sync and the pantry are removed.
- Research library of dated, cited, expiring notes that the shipped rules
  cite by claim id.
- Cardio depth is a config tier meaning plan ownership (`count`, `review`,
  `program`). An activity-source layer with a local cache: Apple Health
  via Health Auto Export first, Intervals.icu as optional enrichment,
  Runna via its calendar feed, manual always available. No Strava API (its
  policy bans AI ingestion), no unofficial Garmin scraping.
- Lifting history backfilled from the Hevy API. Old check-ins archived
  unchanged.
- Vocabulary in `CONTEXT.md`: Program, Session, Workout, Block, Overlay,
  Progression scheme, Schedule rule, Exposure, Dose, Activity source,
  Brief, Research note, Core and Optional session, Sunday message.

## Phase 0 — prose only, ship first

No code. Each item edits skills, `CLAUDE.md` or reference docs and lands
with one `/framework-sync`.

### R-01 Sunday message replaces the interview
- **Problem.** The check-in asks 8 to 11 questions one at a time, then
  the athlete proof-reads a reconstruction of the week.
- **Design.** The check-in opens with one fixed intake message the athlete
  answers in one reply: sessions done including coach-led ones and their
  content, runs and distance, sleep in one line, niggles, the nutrition
  app's numbers in a fixed order (a dashboard screenshot is accepted),
  anything different next week. Missed sessions are tagged with one word
  (`time / sleep / ill / family / skipped / other`) and never litigated.
  The rotation position is inferred from the coach-led session's log and
  confirmed, not asked. A hold-steady week gets a brief of three sentences
  and "reply go".
- **Size** S. **Migration** none. **Serves** 2. **Lens** athlete, devil.

### R-02 Three coaching rules the evidence demands
- **Problem.** Returns after layoffs, structural decisions and deloads
  were each improvised every time.
- **Design.** Written into `program-week`, `check-in` and the coaching
  principles: (a) **return after layoff** scaled to days off (up to 10 days
  nothing; 11 to 21 days load minus 5 % and one set fewer; 22 to 42 days
  minus 10 %; longer re-tests at minus 15 %), with illness adding a
  symptom-free-48-hours, RPE-capped first session; (b) **adherence
  trigger**: trailing four weeks under about 70 % means the check-in must
  present a smaller schedule at equal volume and record the decision as
  adopted, declined with reason, or deferred to a date; no new session
  type is added under 80 %; (c) **deloads are fatigue-triggered with a
  cadence ceiling**, counted in completed hard weeks, with an explicit skip
  rule, and the deep review no longer depends on the deload happening.
- **Size** S. **Migration** none. **Serves** 3, 1. **Lens** coaching,
  devil, athlete.

### R-03 Hevy note hygiene and one gate
- **Problem.** Stale targets and one-week folds survive in Hevy for weeks;
  the athlete cannot tell this week's note from last month's. Approvals
  are spread over three or four turns.
- **Design.** Every programming pass rewrites every routine in the span,
  including unchanged ones. `Target` lines are never hand-typed. The
  week's focus goes in the first exercise's note (one line). Any routine
  in the coming span updated before the last pass is flagged `STALE`
  before the week starts. The brief ends with one line naming exactly
  which routines will be written; "go" approves both the brief and the
  write. Reversible file writes need no gate.
- **Size** S. **Migration** one full rewrite of all routines in the
  reference instance. **Serves** 1, 2. **Lens** athlete, system.

### R-04 Remove Notion sync and the pantry
- **Problem.** Both are unmaintained surfaces nobody runs; the Notion
  map is already stale.
- **Design.** Delete the two skills, their reference docs, the `/setup`
  steps and the `CLAUDE.md` rows. `meal-plan` keeps one question:
  "anything in the house to use up?" Git history keeps the code.
- **Size** S. **Migration** delete `notion-map.json` in instances.
  **Serves** 2. **Lens** all.

### R-05 Stop asking for what never arrives
- **Problem.** Waist asked weekly and never supplied; sleep hours never
  recorded; isolation-set RPE drift flagged as hard as compound drift.
- **Design.** Waist and photos become a monthly ask at deep check-ins
  only. Sleep and runs come from a source when one exists, else one line
  in the Sunday message. The RPE-drift check fires only on compounds or
  sets carrying a recovery cap; isolation drift is one summary line.
- **Size** S. **Serves** 2, 3. **Lens** athlete, coaching, cardio.

### R-06 Nutrition reset
- **Problem.** A protein target above the evidence range for the
  athlete's body composition, missed every recorded week; a manual calorie
  band that contradicts the trend-rate target; the nutrition app overridden
  for ten weeks with a first-principles estimate; the only prescription
  that moved intake ("two protein anchors a day") lives in check-in prose.
- **Design.** `/goals` sets protein as floor, target and stretch from
  fat-free mass or goal weight when body fat is high, with a habit
  progression (floor hit two weeks running becomes the new floor). Protein
  is coached as a daily scaffold of standing anchors, not a daily plan.
  Any override of the nutrition app's numbers is a dated state with an
  exit condition that expires after three weeks. The framework rule reads
  strictly: the repo gets complete logging into the app (log an estimate
  on untracked days) and reads its numbers out; it never runs a parallel
  calorie model. A sleep gate on deficits is written now and evaluated
  once a sleep source exists.
- **Size** S. **Migration** a `/goals` pass in the reference instance.
  **Serves** 3, 2. **Lens** nutrition, coaching.

## Phase 1 — reliability core

The `coach` package. Serves priority 1 end to end by the end of R-15.

### R-10 Package skeleton, config, units
- **Design.** `python3 -m coach <group> <command>`, JSON on stdout,
  diagnostics on stderr, exit codes for validation failure, refused write
  and network failure, `--dry-run` on every writing command. Modules:
  config loader and validator (`tomllib`, Python 3.11 floor stated in
  plain words), dates (ISO weeks, spans, "which week is this"), and
  `units.py` holding the **only** dumbbell conversion function
  (`to_hevy_kg(load, load_mode)`), plate and increment rounding, and the
  formatter that always prints `25/hand (Hevy: 50)`. A test asserts no
  other file multiplies by two. Tests live in the template only and are
  excluded from the framework sync set.
- **Size** M. **Depends** nothing. **Serves** 1, 4. **Lens** system, data.

### R-11 Exercise library with a required load mode
- **Design.** Template ships a builtin catalogue plus a mapping from
  Hevy template ids to coaching attributes (Hevy's own endpoint carries
  title, type, muscle groups and equipment only). Each entry: stable id,
  aliases, muscles, movement pattern, equipment, `load_mode_default`
  (`total`, `per_hand_x2`, `single_implement`, `bodyweight`, `assisted`,
  `band`, `duration`, `distance`), increment, substitutes. The instance
  file holds overrides and custom entries that sync never touches.
  Seeding from Hevy proposes a load mode per exercise; the athlete confirms
  the table once; `coach check` fails on any missing value.
- **Size** M. **Migration** alias-match the instance's program rows, a
  handful of confirmations. **Serves** 1, 4. **Lens** data, system.

### R-12 Hevy client and cache
- **Design.** Key from the environment or `.env`, never logged. Pull
  pages all workouts once, then uses the events cursor endpoint for
  incremental updates; caches routines, exercise templates and body
  measurements; appends every write to a `writes.jsonl` audit log.
  Token-bucket rate limit on writes with back-off on 429. Fixture recorder
  for tests with anonymised responses.
- **Size** M. **Depends** R-10. **Serves** 1, 2. **Lens** system.

### R-13 Overlay as structured prescription
- **Design.** One JSON file per programming pass with a span, a
  `supersedes` link, the focus line, per-session per-set prescriptions,
  and a tagged load object `{mode, per_hand, hevy_total, hevy_kg}` whose
  arithmetic the validator checks. The Hevy writer reads `hevy_kg` only;
  the renderer prints `per_hand` and `hevy_total` and computes nothing.
  Mid-week reprograms and one-off weeks are overlays too. The check-in's
  week-ahead table, the brief and the Hevy notes are all rendered from it.
  Coach overrides of a proposal are stored on the exercise with a reason.
- **Size** M. **Migration** only the newest overlay is back-converted;
  older check-ins stay prose. One known early table mixes per-hand and
  Hevy numbers and is marked unrecoverable. **Serves** 1, 2. **Lens**
  data, system, athlete.

### R-14 Hevy push with verification
- **Design.** `routines diff` builds the intended body for every routine
  in the overlay's span and compares structurally against the cache (an
  empty diff means nothing to write). `push` does PUT, GET, diff again,
  logs the hash and verification, skips verified routines on re-run, and
  refuses an overlay with unresolved `block` flags or without approval.
  `verify` replaces the prose "GET-verified" line. Finished temporary
  routines are retitled "(unused)".
- **Size** M. **Depends** R-12, R-13. **Serves** 1. **Lens** system.

### R-15 Mechanical approval gate
- **Design.** The template's `.claude/settings.json` allowlists read-only
  `coach` commands and never the push. A `PreToolUse` hook on the push
  turns the permission prompt into the dry-run diff summary (routines, set
  changes, dumbbell loads). `overlay approve` stamps a hash; push refuses
  an overlay edited after approval. A scheduled or headless run therefore
  cannot write to Hevy, which is the intended behaviour.
- **Size** S. **Depends** R-13, R-14. **Serves** 1. **Lens** system,
  devil.

### R-16 `coach check`
- **Design.** Whole-instance validation: Python floor, config keys, every
  JSON schema version, dangling exercise and routine ids, missing load
  modes, loads above caps, overlay-versus-Hevy drift, rendered files
  matching a fresh render, cache age, `.env` untracked, no bare Hevy
  value in prose. Each check has a failing fixture.
- **Size** M. **Depends** R-10 to R-13. **Serves** 1. **Lens** system.

### R-17 Program and state as data, migration runner
- **Design.** `program.json`: sessions (with `kind`, `tier` core or
  optional, `status` active, parked or standby), exercises keyed to the
  library with required `load_mode`, cues, constraints, per-exercise
  scheme and parameters, schedule rule and parameters (including an
  external-confirmation anchor for programs keyed to a coach-led session),
  blocks and deload rule, external sessions with estimated set counts,
  missed-day rules. `state.json`: rotation position with a confirmed
  flag, block counters, deload status, active one-off span, scheme state,
  Hevy ids and folders. `routine/*.md` becomes rendered; hand edits fail
  `coach check`; the Hevy map file is retired. A versioned migration
  runner (`schema_version` everywhere, numbered steps, dry run, backup,
  validate, stage and stop) with one interactive bootstrap migration that
  parses an existing markdown instance and produces review tables for the
  athlete to confirm once per table. Instance namespaces (plugins, custom
  exercises, protocols, config) are never written by sync.
- **Size** L. **Migration** this is the migration. **Serves** 1, 4.
  **Lens** data, system.

## Phase 2 — weekly effort

### R-20 History cache and stats
- **Design.** Monthly workout files resolved at cache time: exercise id
  from the library, load mode from the overlay in force, the resolved
  per-set load stored so a later single-arm switch cannot reinterpret old
  sets. An annotations file replaces prose warnings (discounted readings,
  repaired typos, unknown conventions). Derived: e1RM series per lift,
  adherence per overlay (hit, under, over, missing), delivered sets per
  muscle (direct and fractional), a convention-jump audit over the last
  eight weeks, session duration versus cap.
- **Size** M. **Depends** R-11 to R-13. **Serves** 1, 3. **Lens** data,
  coaching.

### R-21 Pre-filled check-in card and catch-up mode
- **Design.** `coach checkin prepare` renders the week as a card: planned
  versus logged with durations, per-exercise result versus prescription,
  e1RM deltas, flags, stale routines in the coming span, the questions the
  data cannot answer. The athlete confirms or corrects in one message.
  Window over ten days switches to catch-up: one summary table, three
  questions, a return week proposed; "ok" end to end is a valid check-in.
  Illness, travel or no-kit in the reply switches the brief to the return
  template with the same single gate. Miss reason tags are tallied for the
  deep review.
- **Size** L. **Depends** R-20. **Serves** 2, 1. **Lens** athlete.

### R-22 Missed-day rules applied by script
- **Design.** The program carries a missed-day rules table (the "if you
  miss a day" lines of the brief). A mid-week miss applies the matching
  rule, prints a five-line diff, writes on "go", appends three lines to
  the current record, and marks folds `one_week` so the next pass unfolds
  them automatically. Only an unmatched case falls back to a brief.
- **Size** M. **Depends** R-13, R-14, R-17. **Serves** 1, 2. **Lens**
  athlete.

### R-23 Proposal generator and plugins
- **Design.** `coach propose` emits a proposed overlay with per-exercise
  rationale and flags from the exercise's scheme plugin. Plugin contract:
  pure `propose(ctx)` over per-hand athlete units (the core applies caps,
  rounding and formatting afterwards, so a plugin cannot double a load);
  declared `PARAMS` and `STATE` schemas validated against the program and
  state files; every scheme implements `decay(days_off)`. Shipped schemes:
  linear, double progression, fixed-reps-at-RPE, 5/3/1-style wave,
  RPE-anchored, assistance ladder for bodyweight skills, maintenance, and
  `hold`. Schedule rules: fixed weekdays, alternating with an external
  anchor, next-in-sequence, explicit calendar. Deload transforms: standard
  and scheme-defined. Flags with severities; `block` flags stop the push.
  Reserved codes include `unearned_load`, `stale_prescription`,
  `load_cap`, `rpe_drift`, `stalled`, `convention_slip`, `no_data`.
  Overrides persist via a decisions file so the scheme sees
  `last_override` and does not re-fight a standing constraint.
- **Size** L. **Depends** R-17, R-20. **Serves** 1, 2, 3, 4. **Lens**
  system, coaching, data.

### R-24 Prescription validator
- **Design.** Before any brief: every line carries the exposure date it
  was derived from and is within the validity window or decayed; load
  under cap and representable with available increments; RPE target
  feasible for the rep range and known max (no "RPE 8 singles" at a 1RM);
  load mode conversion applied; estimated session duration under the slot
  cap.
- **Size** M. **Depends** R-11, R-13, R-20. **Serves** 1. **Lens**
  coaching.

### R-25 Renderers: brief, dashboard, check-in skeleton, progress
- **Design.** `this-week.md`: header line (week, rotation, phase, tier,
  check-in due), Focus (one or two sentences), Sessions table (day,
  session, core or optional, key number, done), Changed (up to five
  bullets, old to new with reason), Watch (up to three), If-you-miss
  rules, Wins; sixty-line ceiling; rendered, never authored. `README.md`
  dashboard: status block and sessions table above the fold on the GitHub
  mobile app, progress summary, links. Check-in record: four prose
  sections under about 600 words (week in review card, coach's read
  leading with a win, decisions, next week) plus a collapsed generated
  prescription appendix; sync details go to a log file, not prose.
  `progress.md`: best e1RMs with dates, priority-lift ladder state,
  core-complete streak, bodyweight trend. Publishing to the phone needs a
  push; see open decision 1.
- **Size** M. **Depends** R-13, R-20. **Serves** 2, 3. **Lens** athlete,
  system.

### R-26 Skills rewrite and CLAUDE.md shrink
- **Design.** Twelve skills become nine: one-off-week merges into
  program-week as modes (normal, deload, constrained, reshuffle,
  midweek); pantry and notion-sync go. Each `SKILL.md` under about 120
  lines holding only when it applies, the conversation steps, the exact
  `coach` commands and what to do with their output, and the approval
  sentence; no templates, arithmetic or API calls. `CLAUDE.md` from about
  260 lines to about 90 with the script rule ("never compute, convert or
  call Hevy by hand; run `coach` and quote its output"). Hooks:
  `SessionStart` prints `coach status`; `PostToolUse` on data files runs a
  quick check. Template-only sections move to a local file.
- **Size** M. **Depends** R-10 to R-25 for the commands. **Serves** 1, 2,
  4. **Lens** system.

### R-27 Follow-ups and niggles as data
- **Design.** A follow-ups file with raised date, source, review-at and
  status; the deep check-in renders open items and must resolve each. A
  niggles file whose rows carry constraints keyed to movement patterns
  (`no added load`, RPE cap) that the proposal step applies and flags.
- **Size** S. **Depends** R-17, R-23. **Serves** 3, 1. **Lens** data.

## Phase 3 — coaching quality and nutrition

### R-30 Delivered-dose accounting and structural triggers
- **Design.** Weekly table of delivered sets per muscle versus planned,
  trailing adherence, per-session volume. Flags: `adherence_low`,
  `volume_undershoot`, `session_volume_high` (above about eleven
  fractional sets for one muscle in one session), `restructure_required`,
  `add_session_type_blocked`, `priority_exposures_missed`. Sessions carry
  a `tier`; weekly balance must pass on core sessions plus coach-led ones
  alone; optional sessions are bonus volume and skipping one is not a
  miss. Priority lifts declare a KPI and a floor dose inserted into the
  next session when their carrying session is missed. Each starter
  program ships a minimum-viable-week variant.
- **Size** M. **Depends** R-20, R-23. **Serves** 3, 2. **Lens** coaching,
  athlete.

### R-31 Block and light-week state machine
- **Design.** Block state counts hard weeks completed (a week counts at
  about 75 % of planned sessions at prescribed RPE). A light week is
  proposed when the count reaches the ceiling or two fatigue triggers fire
  (readiness, compound RPE drift two sessions running, a niggle under load,
  sleep debt when a source exists), and is skipped automatically with a
  recorded reason below three hard weeks. Three light-week types as
  transforms: return, light, deload. The deload "pencil" becomes trigger
  status in the brief. The deep review runs on hard weeks or a structural
  flag, never on the deload.
- **Size** M. **Depends** R-17, R-23, R-30. **Serves** 3. **Lens**
  coaching, athlete.

### R-32 Research library with cited claims
- **Design.** Notes with TOML frontmatter (topic, question, written,
  review_by, confidence, applies_to, sources) and numbered claims. Shipped
  schemes, flag thresholds and the coaching principles cite claim ids; a
  test asserts every cited id exists; `coach research status` lists
  expired notes and the proposal step will not call a decision
  evidence-based against an expired note in its area. A note is refreshed
  by a subagent when expired or when a decision contradicts it. Seed set:
  volume and frequency, proximity to failure, progression by training age,
  deloads, autoregulation, concurrent training, protein and energy
  deficit, detraining and return, minimum effective dose, bodyweight-skill
  progression, sleep and dieting. The coaching principles are rewritten
  against the evidence: frequency as a scheduling choice bounded by
  per-session volume, fatigue-triggered deloads, minimum and maintenance
  dose, return-to-training, concurrent separation, prescription validity,
  reachable targets.
- **Size** M. **Depends** nothing hard. **Serves** 3, 4. **Lens**
  coaching, data, devil (narrowed).

### R-33 Nutrition rebuilt around a standing scaffold
- **Design.** `[nutrition]` config holds the targets, a standing weekly
  template (who covers which slot, office days, lunch pool, staples) and
  the daily protein scaffold. A weekly plan is a small JSON of exceptions
  to the template; a script computes per-day totals and flags, renders the
  week table, and builds a shopping list of non-covered meals grouped in
  supermarket walk order with staples under "check you have", optionally
  as a tickable GitHub issue. Athlete effort: one exceptions line and one
  approval. Recipe cards move to TOML frontmatter with structured
  ingredients, aisles and variation deltas; the stats block and index are
  rendered; a validator checks the macro sum and protein density per slot.
  Nutrition app readings are one line at check-in stored as a series.
  JSON-LD import covers meal-kit sites. The brief carries one food line;
  the check-in asks three food questions. Plan style `loose` is the
  default where someone else decides dinner.
- **Size** L (three M builds). **Migration** cards converted by script
  with a review table; old plans archived; the nutrition series seeded
  once from check-in prose (the one sanctioned exception to "history from
  the API"). **Serves** 2, 1, 3. **Lens** nutrition, athlete, system.

## Phase 4 — generality and cardio

### R-40 Config-driven onboarding and a "run my program" mode
- **Design.** `/setup` writes `config.toml` from a commented example and
  asks only what cannot be defaulted; a six-question profile; then pick a
  starter program, import from Hevy, or design. About ten turns to a
  trainable week. `coaching.mode = "run"` suppresses redesign proposals for
  athletes who want their own program executed. Non-Hevy athletes train
  from the brief, which expands each session to a sheet, and log through a
  small helper rather than free text. No nutrition questions unless
  nutrition is enabled.
- **Size** L. **Depends** R-17, R-23, R-41. **Serves** 4, 2. **Lens**
  athlete.

### R-41 Starter program library and import
- **Design.** Full-body three days, upper/lower four, push/pull/legs,
  5/3/1-style wave, RPE-autoregulated; each validated by a test that
  renders it and runs `propose` on empty history; each with a
  minimum-viable-week variant. Import from Hevy halves dumbbell loads by
  confirmed load mode, detects percentage-based programs, and leaves the
  scheme as `hold` for the coach to assign.
- **Size** M. **Depends** R-17, R-23. **Serves** 4. **Lens** system,
  coaching.

### R-42 Activity-source layer
- **Design.** Three append-only caches: activities, wellness days,
  planned sessions, each with a schema and a per-source sync map. Adapters
  with one interface (`fetch`, `normalise`): Apple Health via Health Auto
  Export JSON on iCloud Drive (format verified against the vendor's
  documentation; the automation runs only while the phone is unlocked, so
  the sync tolerates gaps), Hevy conditioning workouts, manual entry;
  then Runna's calendar feed after inspecting what its events contain;
  Intervals.icu later as enrichment (its Garmin content is the part at
  risk). Dedup by kind and start proximity with precedence from config;
  Apple Health entries written by Hevy are dropped. A privacy switch keeps
  the wellness file out of git. Backfill from one 90-day manual export.
- **Size** M. **Depends** R-10. **Serves** 2, 3. **Lens** cardio, data.

### R-43 Cardio tiers, reconciliation and load flags
- **Design.** Tier means plan ownership; data depth comes from sources.
  Config carries weekly and single-run caps and a quality-run cap. A
  reconcile step matches planned runs to activities (done, moved, missed,
  extra) and renders one block in the check-in. Per-modality weekly
  numbers (hard sets, run km and minutes and quality count, conditioning
  minutes) plus a combined session-RPE-minutes figure with its estimation
  method labelled on every activity. Flags: `CAP_BREACH`,
  `RUN_VOLUME_SPIKE`, `QUALITY_STACK`, `COLLISION`, `SLEEP_DEBT`,
  `STATUS_ACTIVE`, `NIGGLE_LINK`; resting-HR and HRV flags only after a
  60-day baseline from a reliable source. No acute:chronic ratio, no daily
  readiness score, no sleep-stage data. Status days (sick, injured, travel)
  feed the return rule.
- **Size** M. **Depends** R-42, R-23. **Serves** 3, 2. **Lens** cardio.

### R-44 Interference constraints and conditioning as sessions
- **Design.** A constraints plugin with evidence-backed defaults: same-day
  gap of six hours, lift first, no quality run within 24 hours before a
  heavy hinge or squat, easy runs same day allowed, conditioning counts as
  quality. The proposal step flags collisions and never moves sessions
  itself. Conditioning sessions are optional Sessions with density-first
  schemes (EMOM density, circuit rounds) and are logged as activities so
  placeholder reps stop mattering; the script drops them with a stated
  reason when sleep debt, a quality stack or a status day fires.
- **Size** M. **Depends** R-17, R-23, R-43. **Serves** 3, 4. **Lens**
  cardio.

### R-45 Scheduled Sunday draft and nudge
- **Design.** An instance-optional recipe (launchd, cron or a cloud
  routine) that runs the pull and `checkin prepare`, writes a draft
  check-in with the questions it cannot answer, and nudges the athlete
  when the window exceeds the cadence by two days. Hevy read-only by
  construction (R-15). For nutrition, the nudge carries the one exceptions
  question.
- **Size** S to M. **Depends** R-15, R-21. **Serves** 2. **Lens** athlete,
  devil, nutrition.

### R-46 Program tier for running
- **Design.** Later. Reduces to writing planned sessions in the R-42
  schema plus a run-progression scheme and a research note. Needs eight
  weeks of run history, a goal, an intensity anchor and available days.
  The only sanctioned path to a Garmin watch is Intervals.icu events, which
  depends on Garmin leaving the partner sync alone.
- **Size** L. **Depends** R-42, R-43, R-32. **Serves** 4. **Lens** cardio.

## Decisions taken by the author (2026-10-11)

1. **Auto-commit exception for rendered files.** Agreed. After the athlete's
   "go" on a programming pass, the close-out may commit and push only
   rendered outputs (the brief, the dashboard, the progress page, the
   overlay file, the check-in record) with a fixed message. Everything
   else stays stage-and-stop.
2. **Core and optional sessions.** Agreed for the reference instance at the
   next deep check-in. The tiers say what a week is judged on, not how
   many days the athlete trains; optional sessions are there to be done.
3. **Nutrition targets.** Agreed: a reachable floor, target and stretch
   with a habit progression, calories held at the app's expenditure as a
   recomp until measured sleep supports a deficit, and the rule that
   overrode the app retired. Applied through R-06.
4. **Phase 3 order.** Nutrition tooling (R-33) stays in Phase 3; the prose
   reset (R-06) in Phase 0 restarts eating to target without code.
5. **Health Auto Export.** Bought when R-42 starts; its manual export
   backfills 90 days.
6. **Personal data in the public template.** The plan and spec documents
   under `docs/superpowers/` move to the author's private instance and
   leave the template.
7. **ADRs.** Three written in `docs/adr/`: structured data as the source of
   truth with rendered markdown; script proposes and coach disposes behind
   a mechanical gate; no unofficial Garmin or Strava access.

## Rejected or deferred, with reasons

- **GitHub Pages**: needs a paid plan and the site would be public.
- **Notion mirror**: unread and stale; removed.
- **Pantry tracking**: never run; its model assumes the athlete's plan is
  the only thing emptying the fridge; a staples list and a use-up line
  cover the need.
- **Strava API**: policy bans feeding API data to AI; paid.
- **Unofficial Garmin clients**: broke in March 2026, intermittent
  blocks since, terms risk.
- **HRV-driven daily readiness**: single-night device error exceeds the
  training signal; weekly trend only, later.
- **Acute:chronic workload ratio**: statistical artefact per the
  methodological literature.
- **Full autopilot** (script writes straight to Hevy): rejected; the gate
  stays.
- **Plugins written mid-session**: untested code trusted because it is a
  script; a new scheme is a code change with tests.
- **An MCP server for Hevy**: a CLI is testable with fixtures and
  agent-agnostic; no server process.
- **A hub built on Intervals.icu first**: its Garmin content may be cut
  off; Apple Health is the durable backbone.
- **Rewriting all historical check-ins into data**: archive unchanged;
  only the current overlay is converted.

## Risks

- A 3 to 4 month build under a weekly production load. Mitigation: Phase
  0 first, every item shippable alone, the old skills keep working until
  R-26.
- Hevy API quirks frozen into code (null rep ranges rejected, routine
  notes dropped, rate limits). Keep the client thin, keep the fixtures
  current, keep a documented manual fallback.
- A wrong `config.toml` stops every script. Fail loud with the file and
  key named; skills keep a prose fallback for the first mistake.
- Tests synced into instances prove nothing. They live only in the
  template.
- Health data in git grows with the wellness cache. Privacy switch before
  the first nightly commit.
- A scheduled run with the Hevy key. Read-only by construction via the
  gate; it writes a draft file only.

## Sources

The seven critiques, the stock-take, the settled design and the cardio
data-source research, with their citations, are in the reference
instance's `docs/reviews/2026-10-11/`. Research citations will enter the
template through R-32 as research notes.
