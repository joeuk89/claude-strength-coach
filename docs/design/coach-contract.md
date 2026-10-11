# `coach` package contract

The interfaces every Phase 1 to Phase 4 roadmap item (R-10 to R-46) builds
against, so items built separately fit together. Agreed in triage on
2026-10-11. See `docs/roadmap/2026-10-11-system-review.md` for the items and
`docs/adr/` for the decisions behind them.

Anything not defined here is internal to the item that builds it. Changing
anything here is a change to this file, made in the PR that needs it and
called out in its description.

**Skills follow the commands.** An item whose command replaces a step a
skill does by hand rewrites that step in the same PR: the skill names the
command and says what to do with its output. It changes nothing else in the
skill. R-26 merges and shrinks the skills at the end of Phase 2; it does not
do every item's wiring.

Section numbers are fixed, because issue briefs cite them. C47 is unused.

## C1. Package layout and file ownership

```
coach/                       # framework: synced to instances
  __init__.py                # __version__ only; no syntax newer than 3.6
  __main__.py                # Python floor check, then coach.cli.main()
  cli.py                     # argparse root, command discovery, envelope, exit codes   (R-10)
  errors.py                  # ExitCode + exception classes                              (R-10)
  paths.py                   # every well-known path, defined once                       (R-10)
  jsonio.py                  # read/write JSON, schema_version gate, atomic write, canonical hash (R-10)
  validate.py                # JSON-Schema-subset validator                              (R-10)
  config.py                  # config.toml loader and validator, equipment_for (C54)     (R-10)
  config_tables/__init__.py  # config table discovery (C4)                               (R-10)
  config_tables/<item>.py    # one module per item that adds config tables; R-10's is core.py
  context.py                 # Context: root, env, config, now(), today(), warn(), log() (R-10)
  dates.py                   # ISO dates, weeks, spans                                   (R-10)
  units.py                   # the ONLY place for x2, /2, kg<->lb, rounding, load formatting (R-10)
  datablock.py               # hidden data block parser (C11)                            (R-32a or R-33b, first to merge)
  checks/__init__.py         # check registry + auto-discovery                           (R-10)
  checks/<item>.py           # one module per item that adds checks; R-10's is environment.py
  commands/__init__.py       # @command declaration helper + auto-discovery              (R-10)
  commands/<group>.py        # one module per CLI group, auto-discovered
  schemas/<name>.schema.json # one file per JSON document type; envelope.schema.json (C3) is R-10's
  catalogue/exercises.json   # builtin exercise catalogue                                (R-11)
  library.py                                                                             (R-11)
  hevy/{client,transport,cache,ratelimit,anonymise,envfile,pull,record}.py              (R-12)
  overlay.py, render.py                                                                  (R-13)
  routines.py                # diff, push, verify, retire; create                        (R-14, R-14b)
  gate.py                    # PreToolUse hook logic                                     (R-15)
  program.py, state.py, migrate.py, migrations/<doc>/NNNN_<slug>.py                      (R-17a)
                             # program.py also holds import_hevy and adopt               (R-41a)
  history.py                 # resolve workouts, annotations, exposures                  (R-20)
  history_sources/<name>.py  # one module per history input: hevy (R-20), manual (R-40c)
  stats.py                   # e1RM, adherence, dose, durations, audit                   (R-20)
  flags/__init__.py          # flag registry + auto-discovery                            (R-20)
  flags/<topic>.py           # one module per item that registers codes                  (each item)
  validity.py                # validity window, return bands, prescription checks        (R-24)
  patterns.py                # COMPOUND_PATTERNS, is_compound(), rpe_drift()             (R-23a)
  plugins/__init__.py        # plugin loader: framework + instance, kinds by subpackage  (R-23a)
  plugins/base.py            # context and proposal types, default_decay                 (R-23a)
  plugins/schemes/<name>.py, plugins/schedules/<name>.py, plugins/transforms/<name>.py  (R-23a, R-23b, R-31)
  plugins/interference/<name>.py                                                         (R-44a)
  plugins/conditioning/<name>.py                                                         (R-44b)
  propose.py, decisions.py, constraints.py                                               (R-23a)
  followups.py, niggles.py                                                               (R-27)
  checkin.py                 # records, due date, card model, render, misses, skeleton   (R-21a)
  checkin_catchup.py         # catch-up card, gap tagging, return brief                  (R-21b)
  checkin_parts/__init__.py  # card part discovery                                       (R-21a)
  checkin_parts/<topic>.py   # one module per item that adds card fields                 (each item)
  missed.py                  # missed-day rule matching and application                  (R-22)
  pages.py                   # brief, dashboard, progress renderers, publish             (R-25)
  page_parts/__init__.py     # page part discovery                                       (R-25)
  page_parts/<topic>.py      # one module per item that adds page items                  (each item)
  nudge.py                   # scheduled run, channels, recipes                          (R-45)
  status/__init__.py         # status provider registry + auto-discovery                 (R-26b)
  status/<topic>.py          # one module per item that adds status lines                (R-26b and later items)
  hooks.py                   # SessionStart and PostToolUse hook logic                   (R-26b)
  research.py                # research notes, claim refs, citation scan                 (R-32a)
  structure.py               # dose targets, structure accounting, priority, minimum week (R-30a, R-30b)
  block.py                   # block ledger, light weeks, status line                    (R-31)
  nutrition.py               # nutrition config, readings, status                        (R-33a)
  recipes.py                 # recipe cards, index, import                               (R-33b)
  meals.py                   # meal plans, shopping list                                 (R-33c)
  log.py, sheets.py          # manual log and session sheets                             (R-40c)
  starters.py                # starter programs                                          (R-41b)
  starters/<id>.json         # framework starter programs                                (R-41b)
  activity/store.py          # ActivityStore: resolved activities, planned, wellness     (R-42a)
  activity/adapters/<name>.py  # one module per activity source                          (R-42a, R-42b, R-42d)
  cardio.py                  # weekly load, bouts, reconcile, cardio flags               (R-43)
  statusdays.py              # status days                                               (R-43)
  weekflags/<name>.py        # week-level flag providers: cardio (R-43), interference (R-44a)
config.example.toml          # framework: every key, commented                           (R-10, then each item adds its tables)
research/<id>.md             # framework: template research notes                        (R-32b1-b3, R-46)
tests/                       # template only, never synced
  test_<module>.py
  support/                   # shared test helpers (fake Hevy lives here, R-12)
  fixtures/instances/<name>/ # minimal instance trees
  fixtures/hevy/             # recorded or synthetic API responses
```

Rules that stop parallel agents colliding:

- **Add files; don't edit shared registries.** CLI groups, checks, config
  tables, flag codes, plugins, history sources, card parts, page parts, status
  providers, activity adapters and week-flag providers are discovered with
  `pkgutil.iter_modules` over their package. No item edits `cli.py`, a
  registry's `__init__.py` or another item's module.
- **R-10 owns these shared files and fills them for all of Phase 1 up
  front:** `paths.py` (all paths in C6), `config.example.toml` (the Phase 1
  keys and the profile-fact keys in C4), `.gitignore` (C6), `errors.py`. A
  later item that needs a new path or key adds it in its own PR and says so
  in the PR description; it never renames an existing one.
- Code runs on Python 3.11. Builders may run newer Pythons, so R-10 adds a test that parses every `coach/**/*.py` with
  `ast.parse(src, feature_version=(3, 11))`. Also banned: stdlib APIs added
  after 3.11 (`itertools.batched`, `pathlib.Path.walk`, `datetime` 3.12
  additions). No third-party imports anywhere, including tests.

## C2. CLI shape

- Invocation: `python3 -m coach [--root PATH] <group> <command> [options]`,
  run from the instance root. Root resolution: `--root`, then env
  `COACH_ROOT`, then the current directory.
- Two levels only: group, then command.
- Commands are declared with `coach.commands.command` (R-10):
  `@command("units format", help=..., args=(arg("--mode", ...), ...),
  writes=False, hevy_write=False, network=False, git_write=False,
  writes_scope=None)` on a function `(args, ctx) -> dict` that returns the
  envelope's `data`. A one-word name is a top-level command (`check`,
  `version`). The helper adds `--dry-run` to every command with `writes`,
  `hevy_write` or `git_write`, and `Command.metadata()` gives the five
  flags R-15 reads. `ctx` is `coach.context.Context`.
- Every command module declares, per command: `writes` (touches local
  files), `hevy_write` (sends a non-GET request to Hevy), `network` (calls
  Hevy at all), `git_write` (commits or pushes; R-25) and `writes_scope`
  (R-45: `"cache"` when every local write lands under `.coach/`, else
  `"data"`, the default for any command with `writes`). R-15's allowlist
  test reads this metadata. A `git_write` command stays off the allowlist
  unless it refuses to run without an approved overlay; `pages publish`
  (C38) is the only one. R-45
  marks `hevy pull` and `nudge run` as `"cache"`.
- **Every command with `writes`, `hevy_write` or `git_write` accepts
  `--dry-run`.** Dry run does every read and every check, writes nothing,
  and returns what it would have done. It exits with the code the real run
  would have (so a push that would be refused exits 3 under `--dry-run`
  too). A test in R-10 asserts every writing command accepts the flag; each
  item's tests assert their dry run writes nothing.
- Test-only environment overrides: `COACH_NOW` (ISO timestamp, fixes "now"
  and "today") and `COACH_HEVY_FIXTURES` (one or more fixture-set
  directories joined with `os.pathsep`; makes the Hevy client replay
  fixtures instead of calling the network, R-12; C15).
- Runtime switch: `COACH_READ_ONLY=1` refuses every data, Hevy and git
  write (C39, R-45).
- Each owner adds its read-only and local-write commands to the R-15
  allowlist in its own PR and says so. `plugins test` is never allowlisted
  (it runs instance code). `pages publish`, `program import-hevy`,
  `program adopt`, `starters` and `nudge` are allowlisted. Commands marked
  H stay behind the R-15 gate.

Command inventory (owner in brackets). Read-only unless marked W
(writes local files), H (writes to Hevy) or G (commits or pushes).

| Command | Owner | |
|---|---|---|
| `units format --mode M --value V [--unit U] [--no-hevy]`, `units convert --mode M (--from-hevy-kg X \| --value V) [--unit U]`, `units round --value V --increment I [--direction nearest\|down\|up]` | R-10 (`--no-hevy`: R-40c) | |
| `dates week [--date D] [--week-starts S]`, `dates span (--week W \| --start D --end D) [--week-starts S]` | R-10 | |
| `config show [--location NAME]`, `config validate` | R-10 | |
| `check [--only ids] [--list]` | R-10 (framework), each item adds checks | |
| `version` | R-10 | |
| `library list [--avoided]`, `library show`, `library search`, `library validate` | R-11 | |
| `library seed`, `library confirm`, `library set-mode`, `library set-avoid` | R-11 | W |
| `hevy status` | R-12 | |
| `hevy pull [--full]` | R-12 | W (gitignored cache only) |
| `hevy record-fixtures --out DIR` | R-12 | W (GET only, needs a real key) |
| `overlay list`, `overlay current [--date D]`, `overlay validate [ID \| --file PATH]` (no argument: every overlay), `overlay notes ID [--session S]` | R-13 | |
| `overlay build --input FILE`, `overlay render ID [--into FILE]`, `overlay approve ID` | R-13 | W |
| `routines diff --overlay ID`, `routines verify --overlay ID` | R-14 | |
| `routines push --overlay ID`, `routines retire --overlay ID` | R-14 | H |
| `routines create --overlay ID [--dry-run]` | R-14b | H |
| `gate pretooluse` | R-15 | |
| `program show`, `program validate`, `state show`, `migrate status` | R-17a | |
| `program render`, `migrate run` | R-17a | W |

Phase 2 to 4 command inventory. No command here writes to Hevy.

| Command | Owner | |
|---|---|---|
| `history show [--since D] [--until D]`, `history annotations` | R-20 | |
| `history sync`, `history rebuild --month YYYY-MM`, `history annotate ...` | R-20 | W |
| `stats e1rm`, `stats adherence`, `stats dose`, `stats durations`, `stats audit` | R-20 | |
| `prescription check (--overlay ID \| --file PATH)` | R-24 | W with `--write` |
| `plugins list`, `plugins show NAME`, `plugins validate` | R-23a | |
| `plugins test` | R-23a | runs instance plugin tests; never allowlisted |
| `schedule plan --week W`, `decisions list`, `propose show ID` | R-23a | |
| `schedule confirm --position P`, `propose week`, `propose override`, `propose resolve`, `propose finalize`, `decisions withdraw ID` | R-23a | W |
| `propose restore --proposal ID --session S --reason TEXT` | R-44b | W |
| `followups list`, `niggles list`, `niggles constraints` | R-27 | |
| `followups add\|resolve\|drop\|defer\|render`, `niggles add\|update\|resolve\|import` | R-27 | W |
| `checkin prepare [--until D] [--tier weekly\|deep]`, `checkin misses [--since D] [--until D]`, `checkin due` | R-21a | |
| `checkin skeleton --date D [--tier T] [--overlay ID] [--refresh]` | R-21a | W |
| `checkin return-brief (--proposal ID \| --overlay ID) --reason R` | R-21b | |
| `checkin tag-gap --tag T` | R-21b | W |
| `missed list [--date D]`, `missed plan --session S --date D`, `missed rules` | R-22 | |
| `missed apply --session S --date D [--tag T]` | R-22 | W |
| `pages show KIND` | R-25 | |
| `pages render [--only brief\|dashboard\|progress] [--replace-readme]` | R-25 | W |
| `pages publish --overlay ID [--record D]` | R-25 | W, G |
| `nudge status`, `nudge recipe --kind launchd\|cron` | R-45 | |
| `nudge run` | R-45 | W (`writes_scope` cache) |
| `status` | R-26b | |
| `hooks sessionstart`, `hooks posttooluse` | R-26b | |
| `research status [--area AREA] [--kind template\|local] [--expired]`, `research show REF`, `research cites [--unresolved]`, `research validate` | R-32a | |
| `research render [ID]` | R-32a | W (the rendered region only) |
| `structure week --week W`, `structure adherence [--until D]`, `structure balance [--program FILE] [--variant minimum]` | R-30a | |
| `structure decide --rule restructure\|add_session --outcome adopted\|declined\|deferred [--reason T] [--revisit D]` | R-30a | W |
| `structure priority [--since D]`, `structure minimum --week W` | R-30b | W with `--write` |
| `block status` | R-31 | |
| `block close --week W [--readiness poor\|ok] [--sleep poor\|ok] [--deep]`, `block decide`, `block init` | R-31 | W |
| `nutrition status`, `nutrition readings [--last N]` | R-33a | |
| `nutrition record`, `nutrition import --input FILE` | R-33a | W |
| `recipes list`, `recipes show`, `recipes validate`, `recipes import --html FILE`, `recipes draft --input FILE`, `recipes convert --parse` | R-33b | |
| `recipes render [SLUG]`, `recipes convert --apply --input FILE` | R-33b | W |
| `meals template [--week D]`, `meals show ID`, `meals validate ID`, `meals shopping ID [--format markdown\|issue]` | R-33c | |
| `meals build --input FILE`, `meals render ID`, `meals approve ID` | R-33c | W |
| `config suggest --unit kg\|lb [--gym commercial\|home]` | R-40a | |
| `log list`, `log prefill` | R-40c | |
| `log add`, `log void`, `sheets render` | R-40c | W |
| `program import-hevy`, `program adopt` | R-41a | W |
| `starters list`, `starters show` | R-41b | |
| `starters draft` | R-41b | W (`.coach/drafts/` only) |
| `activity list`, `activity show ID`, `activity status` | R-42a | |
| `activity sync [--source NAME]`, `activity add`, `activity void ID --reason TEXT` | R-42a | W |
| `activity import --source NAME --file PATH` | R-42b | W |
| `activity anonymise --source NAME --file PATH --out DIR` | R-42b | W (output directory only) |
| `wellness list`, `wellness summary`, `planned list` | R-42a | |
| `wellness add`, `wellness void ID --reason TEXT`, `planned add`, `planned void ID --reason TEXT` | R-42a | W |
| `cardio week --week W`, `cardio reconcile --week W`, `cardio flags (--week W \| --span A..B)` | R-43 | |
| `cardio render --week W [--into FILE]` | R-43 | W with `--into` |
| `status-days list [--active]` | R-43 | |
| `status-days add`, `status-days end ID --date D`, `status-days withdraw ID --reason TEXT` | R-43 | W |
| `interference list`, `interference check (--week W \| --span A..B)` | R-44a | |

## C3. Output envelope and exit codes

stdout carries exactly one JSON object per run, UTF-8, followed by a newline:

```json
{"schema_version": 1, "ok": true, "command": "units format",
 "data": {}, "warnings": []}
```

On failure `ok` is false, `data` is absent (except for a command whose
result is a report that explains the failure: `coach check` keeps
`data.results` and `data.summary` next to `error`), and:

```json
"error": {"code": "validation", "message": "one plain sentence",
          "details": [{"path": "$.sessions[0].exercises[2].load.hevy_kg",
                       "message": "expected 22.6796, found 45.3592"}]}
```

stderr carries human-readable diagnostics and progress, each line prefixed
`coach: `. Nothing on stderr is parsed by anything.

| Exit | `error.code` | Meaning | Examples |
|---|---|---|---|
| 0 | — | Success (warnings allowed) | |
| 1 | `validation` | Input or data failed validation; a check failed; a Hevy write did not verify | bad overlay arithmetic, `coach check` has a `fail` |
| 2 | `usage` | Bad command line (argparse's own code) | unknown flag |
| 3 | `refused` | A write was refused by a guard | no approval, hash mismatch, unresolved `block` flag, routine changed in the app since the diff, overlay expired, read-only run (C39) |
| 4 | `network` | Hevy unreachable or erroring after retries | timeout, 5xx, 429 after back-off, a failed `git push` (C38) |
| 5 | `config` | Environment or config prevents running | Python < 3.11, `config.toml` missing or invalid (file and key named), Hevy key missing, HTTP 401/403 |
| 9 | `internal` | Uncaught exception (traceback on stderr) | a bug |

`coach check` never exits 5: it reports config and environment problems as
`fail` results and exits 1.

## C4. Config: `config.toml`

- Lives at the instance root. Human-edited, committed in the instance,
  never written by any script (ADR-0001). The template ships
  `config.example.toml` and never tracks `config.toml`.
- Unknown keys and unknown tables are errors (ADR-0002: "a typo in a
  parameter name is an error"). Messages name the file, the key and the
  expected type. This holds inside `[equipment.locations.<name>]` tables
  too.
- Commands that need config and find none exit 5 with "copy
  config.example.toml to config.toml". `units` commands take `--unit` and
  work without config.
- **Required keys and defaults** (R-10): `schema_version` and `[athlete]
  units` are required. Every other key takes the value shown below when
  left out, except that `bodyweight_units` defaults to `units`, and with
  `units = "lb"` the `[equipment]` increments, `dumbbell_max`,
  `bar_weight` and `plates` have no default and must be set. Absent
  `[caps]` and `[equipment.locations]` are empty. Keys inside a location
  table have no defaults: a key left out keeps the main table's value.
- **Declaring a table** (R-10): each top-level table is declared in a
  module under `coach/config_tables/` that exports `TABLES = {"name":
  Table(...)}`, built from `coach.config.Key` and `Table`. An item that
  adds a table adds its own module; it does not edit `config.py`. A table
  marked `optional=True` stays absent when the file leaves it out, so
  `"nutrition" in config` tells a reader whether nutrition is enabled.
- `coach.config.load(root) -> Config`. `Config` is a dict with attribute
  access (`config.athlete.units`, `config["equipment"]`) and a `path`.
- `plates` lists the plate sizes the athlete has in pairs, one per side;
  `units.plate_breakdown` uses any number of each size and returns the
  fewest plates, heaviest first.

Phase 1 and profile-fact keys (R-10 defines all of them; later items read
them; C54 says who reads the profile facts):

```toml
schema_version = 1

[athlete]
units = "kg"              # "kg" | "lb" — loads
bodyweight_units = "kg"   # "kg" | "lb"
week_starts = "monday"    # "monday" | "sunday"
timezone = ""             # IANA name; empty = system local time
experience = "intermediate"   # "beginner" | "intermediate" | "advanced"
available_days = []       # weekday ids "mon".."sun"; empty = not stated
session_minutes = 60      # default time cap per session; 0 = no cap; [sessions.cap_minutes] overrides (C19)

[hevy]
enabled = true
cache_max_age_hours = 24  # coach check warns past this

[equipment]               # the main place the athlete trains; all in athlete units
available = []            # R-11 equipment enum values; empty = every piece assumed (not checked)
dumbbells = []            # per-hand dumbbell weights available; empty = not checked
dumbbell_increment = 2.0  # per hand
dumbbell_max = 40.0       # per hand; a cap
barbell_increment = 2.5   # smallest total jump
bar_weight = 20.0
plates = [25, 20, 15, 10, 5, 2.5, 1.25]   # per side, pairs available
machine_increment = 5.0
cable_increment = 2.5

[equipment.locations.home]  # optional; any number of named places (name ^[a-z0-9-]+$)
available = ["dumbbell", "bench", "band", "bodyweight"]
dumbbells = [5, 10, 15, 20] # any [equipment] key may appear; it overrides the main table at this place
dumbbell_max = 20.0

[caps]                    # optional: library exercise id = max load, athlete units
                          # (per hand for per-hand modes, total otherwise)
```

Tables later items add, each in its own PR:

| Table | Owner | Defined in |
|---|---|---|
| `[sessions]` | R-20 | C19 |
| `[checkin]` | R-21a | below |
| `[nudge]` | R-45 | below |
| `[nutrition]` and its subtables | R-33a, R-33b, R-33c | below |
| `[coaching]` | R-40b | C44 |
| `[activity]`, `[sources.<name>]` | R-42a; each adapter adds its own source table | C32 |
| `[cardio]` | R-43 | C48 |

```toml
[checkin]                   # R-21a
cadence_days = 7            # days between check-ins; the due date is the last record's date + this

[nudge]                     # R-45; optional; absent = no scheduled run configured
channel = "none"            # "none" | "macos" | "github_issue"
time = "18:00"              # local time the recipe runs, daily
after_days = 2              # first nudge when days since the last check-in reach cadence_days + after_days
```

**Nutrition keys** (R-33a, R-33b, R-33c). An absent `[nutrition]` table
means nutrition is disabled. Weights are in `[athlete] bodyweight_units`.
No key holds a calorie figure the nutrition app owns.

```toml
[nutrition]                     # R-33a
enabled = true
app = "macrofactor"             # "macrofactor" | "none"
phase = "recomp"                # "bulk" | "cut" | "maintain" | "recomp"
target_rate_per_week = 0.0      # bodyweight units per week; negative = loss
# goal_weight = 78.0            # optional
# kcal_target = 2400            # only when app = "none"; an error otherwise

[nutrition.protein]             # R-33a; set by /goals (R-06 rules)
reference_basis = "bodyweight"  # "bodyweight" | "goal_weight" | "fat_free_mass"
reference_mass = 80.0
floor_g = 110                   # the number entered in the app
target_g = 128
stretch_g = 176
floor_since = 2026-09-28        # readings before this date don't count toward a raise
floor_step_g = 10

[[nutrition.anchors]]           # R-33a; 2–3 standing protein anchors
name = "Whey shake"
slot = "snack"
days = ["daily"]                # "daily" | "office" | "home" | weekday names
kcal = 150                      # R-33c: or recipe = "<card slug>" instead of kcal/protein_g
protein_g = 30

# [nutrition.override]          # R-33a; optional, at most one
# start = 2026-10-11
# expires = 2026-11-01          # at most 21 days after start
# what = "app protein target held at 120"
# reason = "..."
# exit_condition = "..."
# renewal = 0                   # 0 first; 1 renewed once; 2 is flagged

[nutrition.bank]                # R-33b
aisles = ["produce", "bakery", "meat-fish", "dairy-eggs", "chilled",
          "frozen", "tins-jars-dry", "snacks", "drinks", "household"]  # walk order
min_protein_per_100kcal = {breakfast = 5.0, lunch = 5.0, dinner = 5.0, snack = 0.0}  # a heuristic
macro_sum_warn_pct = 10
macro_sum_fail_pct = 20

[nutrition.bank.slot_notes]     # R-33b; optional, printed under each index section
# breakfast = "must be fast or it gets skipped"

[nutrition.template]            # R-33c
slots = ["breakfast", "lunch", "dinner", "snack"]
office_days = ["tue", "thu"]
staples = ["eggs", "oats", "olive oil"]
# plan_style = "loose"          # "loose" | "strict"; default: loose when a dinner is covered
kcal_tolerance_pct = 15
shopping_issue = false

[[nutrition.template.standing]] # R-33c; exactly one of recipe, pool, cover
days = ["daily"]
slot = "breakfast"
recipe = "overnight-oats"

[[nutrition.template.standing]]
days = ["office"]
slot = "lunch"
pool = ["chicken-rice-bowl"]

[[nutrition.template.standing]]
days = ["mon", "tue", "wed", "thu"]
slot = "dinner"
cover = "family"
kcal = 700
protein_g = 35
```

Which R-06 nutrition facts are data and which stay prose (ADR-0001; C54
covers the rest of the profile):

| In `[nutrition]` (a script reads it) | Stays prose in `profile.md` (only a human reads it) |
|---|---|
| app in use, phase, target trend rate, goal weight, no-app kcal target | the goal in the athlete's words, phase sequence and its triggers |
| reference basis and mass; floor, target, stretch; floor date and step | why that basis (the body-fat reading and its source) |
| anchors: name, slot, days, macros or card | how the anchors were chosen; what the athlete likes |
| the active override: dates, what, reason, exit condition, renewal count | — |
| staples, office days, standing coverage, plan style (R-33c) | food likes, dislikes, allergies, cooking appetite, shopping style |
| — | sleep-gate status and reasoning (until an activity source, C29) |
| — | the MacroFactor setup summary and revision notes |

## C5. Load modes and the load object

Load mode is a property of how an exercise is performed in a given program
slot, not of its name. Enum (from R-11):

| `load_mode` | `per_hand` | `hevy_total` | Hevy field | `format_load` prints |
|---|---|---|---|---|
| `total` | null | load on the bar/stack | `weight_kg` | `80` |
| `per_hand_x2` | one dumbbell | 2 × per_hand | `weight_kg` | `25/hand (Hevy: 50)` |
| `single_implement` | the one implement | = per_hand | `weight_kg` | `25 (Hevy: 25)` |
| `bodyweight` | null | added load, 0 if none | `weight_kg` | `BW` or `BW+10` |
| `assisted` | null | assistance | `weight_kg` | `BW-20 assist (Hevy: 20)` |
| `band` | — | — | none | load is null |
| `duration` | — | — | `duration_seconds` on the set | load is null |
| `distance` | — | — | `distance_meters` on the set | load is null |

The load object, used wherever a prescribed weight appears (overlay sets,
program start loads):

```json
{"mode": "per_hand_x2", "unit": "lb", "per_hand": 25, "hevy_total": 50, "hevy_kg": 22.6796}
```

- `unit` is in the object so its arithmetic can be checked alone.
- `hevy_kg = round(hevy_total × factor, 4)`, factor 1 for kg and
  0.45359237 for lb. Validators recompute and require exact equality.
- Numbers are JSON numbers; integral values are written as integers.
- Only `units.make_load(value, load_mode, unit)` builds a load object. Only
  `units.to_hevy_kg(value, load_mode, unit)` and
  `units.from_hevy_kg(weight_kg, load_mode, unit)` convert. The Hevy writer
  reads `hevy_kg` only. Renderers print via `units.format_load(load)` and
  compute nothing.
- `per_hand` is null for every mode but `per_hand_x2` and
  `single_implement`. `check_load(load)` returns one message per problem,
  shaped `"<field>: expected <x>, found <y>"`.
- `from_hevy_kg` rounds the athlete-units total to 3 decimals before
  halving, which absorbs the 4-decimal kg rounding (`22.6796` → `25`/hand
  in lb).
- `format_load` never prints a unit; table headers and surrounding text
  carry it. It prints at most two decimals, rounding halves up, and strips
  trailing zeros (`22.5`, `1.25`, `25`). It raises on a null load; callers
  print what a null load means in their context (C12).
- `format_load(load, show_hevy=True)` (R-40c). With `show_hevy` false,
  `per_hand_x2` prints `25/hand`, `single_implement` prints `25`, and
  `assisted` prints `BW-20 assist`. Renderers pass `config.hevy.enabled`;
  `units format --no-hevy` sets it false.
- Enforced by an AST test (R-10): no `coach/**/*.py` other than
  `coach/units.py` contains a multiplication by the constant 2, 2.0 or 0.5,
  a division or floor division by 2 or 2.0 (including augmented
  assignment), or the literals `0.45359237` or `2.20462`. The test carries
  an explicit allowlist of `(path, source line)` pairs, empty at the start;
  extending it means editing the test, which shows in review.

## C6. Instance file layout

| Path | What | Git | Written by |
|---|---|---|---|
| `config.toml` | settings | committed (instance) | the human or the coach with the Write tool |
| `data/exercises.json` | instance library: overrides, custom entries, confirmed load modes, avoided exercises (C54) | committed | R-11 |
| `data/overlays/<id>.json` | one overlay per programming pass | committed | R-13; R-23a (`propose finalize`); R-22 (midweek) |
| `data/hevy/writes.jsonl` | append-only audit of every Hevy write and verification | committed | R-12 (writes), R-14 (verify, retire), R-14b (create) |
| `data/program.json`, `data/state.json` | program and state | committed | R-17a; R-41a (`program adopt`); R-31 (`state.block`) |
| `data/archive/programs/<YYYY-MM-DD>/` | previous `program.json` and `state.json` | committed | R-41a |
| `routine/*.md` | rendered session pages | committed, never hand-edited | R-17a |
| `data/history/<YYYY-MM>.json` | resolved workouts for one month | committed | R-20 |
| `data/history/annotations.json` | corrections and facts the log lacks | committed | R-20 (`history annotate`), R-21a, R-21b, R-22 |
| `data/decisions.json` | recorded coaching decisions, overrides | committed | R-23a, R-30a, R-31 |
| `data/followups.json`, `data/niggles.json` | open questions; niggles with constraints | committed | R-27 |
| `data/blocks.json` | block ledger | committed | R-31 |
| `data/status-days.json` | status days | committed | R-43 |
| `data/log/workouts.jsonl` | manual lifting log for athletes without Hevy, append-only | committed | R-40c |
| `data/activity/activities.jsonl`, `planned.jsonl`, `sync.json` | activity records, planned activities, sync map (C29) | committed | R-42a and adapters |
| `data/activity/wellness.jsonl` | wellness records, when `[activity] wellness_in_git = true` | committed | R-42a and adapters |
| `.coach/activity/wellness.jsonl` | wellness records, when `wellness_in_git = false` (the default) | **gitignored** | R-42a and adapters |
| `data/nutrition/readings.json` | nutrition readings series | committed | R-33a |
| `data/nutrition/plans/<id>.json` | one meal plan per window | committed | R-33c |
| `nutrition/plans/<id>.md` | rendered meal plan | committed, never hand-edited | R-33c |
| `nutrition/menu/<slug>.md` | recipe card: hidden data block (coach-written), rendered region, prose | committed | the coach; R-33b renders the region |
| `nutrition/menu/index.md` | recipe index | committed, never hand-edited | R-33b |
| `nutrition/archive/` | pre-R-33 dated plans, unchanged | committed | moved once by hand (R-33d) |
| `check-ins/<date>.md` | check-in record: prose plus rendered regions | committed | the coach; R-21a (skeleton and regions); R-22 (mid-week lines); R-43 (cardio region) |
| `this-week.md` | the brief, rendered | committed | R-25 |
| `progress.md` | progress page, rendered | committed | R-25 |
| `README.md` | the dashboard, rendered (instance only; see below) | committed | R-25 |
| `this-week-sheets.md` | rendered session sheets, only when `[hevy] enabled = false` | committed, never hand-edited | R-40c |
| `research/<id>.md` | template research notes | framework: tracked in the template, synced | R-32b (data block), `research render` (region) |
| `research/local/<id>.md` | local research notes | committed (instance) | the coach with the Write tool (data block), `research render` (region) |
| `plugins/<kind>/<name>.py`, `plugins/tests/test_<name>.py` | instance plugins and their tests | committed | the athlete, as a code change |
| `.coach/cache/hevy/` | raw Hevy cache, rebuildable with `hevy pull --full` | **gitignored** | R-12 |
| `.coach/backups/<UTC timestamp>/` | pre-migration copies | gitignored | R-17a |
| `.coach/proposals/<id>.json`, `<id>.proposed.json` | editable proposal draft and its untouched original | gitignored | R-23a |
| `.coach/plans/<week start>-<name>.json` | schedule plans handed to `propose week --plan` | gitignored | R-30b; R-22 may |
| `.coach/drafts/` | drafts the coach edits before a command applies them (program drafts, log drafts), and the scheduled run's `checkin-<date>.md` | gitignored | R-40c, R-41a, R-41b, R-45 |
| `.coach/nudge.json` | nudge state | gitignored | R-45 |
| `.coach/logs/nudge.log` | scheduled run output | gitignored | the recipe (R-45) |

- `.gitignore` gains `/.coach/`, `__pycache__/` and `*.pyc` (R-10). The
  `.coach` pattern is **root-anchored** so test fixtures under
  `tests/fixtures/instances/*/.coach/` stay tracked. Fixtures never contain
  a file named `.env` (the existing pattern ignores it at any depth); tests
  that need one create it in a temp directory.
- **Instance namespaces** that the template never tracks, so
  `/framework-sync` can never write them: `config.toml`, `data/**`,
  `routine/**`, `profile.md`, `check-ins/**` (except `.gitkeep`),
  `nutrition/**` (except `.gitkeep`), `plugins/**`, `research/local/**`,
  `this-week.md`, `progress.md`, `this-week-sheets.md`, `.coach/**`,
  `.env`. R-10 adds a test that fails if `git ls-files` in the template
  lists any of them; each item that adds a namespace extends that test.
- **Sync exclusions**: R-10 edits `.claude/skills/framework-sync/SKILL.md`
  so the framework set excludes `tests/**` as well as `docs/**` and
  `.gitkeep`. Its tests check the skill text names `tests/**`. R-25 adds
  `README.md` to the exclusions and edits the skill and its test: the
  template's README stays the template's front page, and an instance's
  README is its dashboard, which `/framework-sync` never touches.
  `README.md` cannot join the namespace list because the template tracks
  it.

## C7. JSON conventions

- Every JSON document the package owns has an integer top-level
  `schema_version`, starting at 1. Every JSONL line has one too.
- Any change to a schema bumps its version. Validators are strict
  (`additionalProperties: false`). A reader that finds a newer version
  exits 1 with "run /framework-sync"; an older version exits 1 with "run
  python3 -m coach migrate run" (the runner arrives in R-17a; until then
  the message still names it).
- Schemas are files in `coach/schemas/<name>.schema.json`, checked by
  `coach/validate.py`, which supports this subset of JSON Schema: `type`
  (including type lists for nullable), `enum`, `const`, `required`,
  `properties`, `additionalProperties`, `items`, `minItems`, `minimum`,
  `maximum`, `pattern`, `$ref` to `#/$defs/...`. Errors carry a JSONPath
  (`$.a[0].b`).
- On-disk format: `indent=2`, `ensure_ascii=False`, trailing newline,
  written atomically (temp file plus `os.replace`).
- Canonical form for hashing: `json.dumps(obj, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False).encode("utf-8")`, hashed with
  SHA-256 and written `"sha256:<hex>"`. One helper in `jsonio.py`.
- Dates are `YYYY-MM-DD`. Timestamps are UTC ISO 8601 with `Z`
  (`2026-10-11T19:02:00Z`). Spans are `{"start": date, "end": date}`,
  inclusive at both ends.
- **Weeks** follow `[athlete] week_starts` through `coach.dates` (R-10);
  no code assumes an ISO Monday week. `coach.dates.week_span(date,
  week_starts)` gives the span of the week holding a date. A week's label
  is `YYYY-Www`, the ISO week of the one Monday inside it. `--week`
  accepts a label or any date in the week. Stored documents name a week by
  its start date (`"week": "2026-10-05"`); command output and region ids
  may use the label. Fixtures use `week_starts = "monday"`; each item that
  works in weeks repeats one test with `"sunday"`.
- Identifier patterns: library exercise ids `^[a-z0-9_]+$` (custom ones
  start `custom_`); session ids `^[a-z0-9-]+$`; overlay ids
  `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`. Record ids with a letter prefix
  (`a-NNNN`, `d-NNNN`, `f-NNNN`, `n-NNNN`, `b-NNNN`, `s-NNNN`) are never
  reused.

## C8. Hevy cache layout (R-12 writes, others read)

```
.coach/cache/hevy/
  meta.json                 {"schema_version":1,"last_pull_started_at":ts,"last_pull_finished_at":ts,
                             "last_full_pull_at":ts,"events_since":ts,"counts":{...}}
  workouts/<workout_id>.json
  routines.json
  routine_folders.json
  exercise_templates.json
  body_measurements.json
```

Every cache file wraps the raw API payload unchanged:
`{"schema_version": 1, "fetched_at": ts, "source": "hevy", "data": <raw>}`.
Collections hold a list in `data`; workout files hold one object. Readers
in R-11, R-14 and R-16 use `coach.hevy.cache.HevyCache` once R-12 merges;
before that, they read these files directly from fixtures in this format.
Schemas: `hevy_cache_file` and `hevy_cache_meta`.

- `hevy pull` with no `meta.json`, or with `--full`, pages every workout
  and rewrites the set (removing files for workouts Hevy no longer has).
  Otherwise it reads `/v1/workouts/events` from `events_since` minus a
  10-minute overlap (re-applying an event changes nothing) and applies
  them oldest first. Either way it refreshes the four collections and sets
  `events_since` to the time this pull started.
- `HevyCache.workouts(since)` returns workouts oldest first; a date
  `since` means midnight UTC.
- R-12 registers the check `hevy_cache_age` (C13): `warn` past
  `[hevy] cache_max_age_hours` or with no cache, `skip` when Hevy is off.

## C9. Audit log line (`data/hevy/writes.jsonl`)

```json
{"schema_version":1,"at":ts,"kind":"write","method":"PUT","path":"/v1/routines/<id>",
 "status":200,"routine_id":"<id>","overlay_id":"<id>|null","overlay_hash":"sha256:..|null",
 "request_body":{...},"request_sha256":"sha256:.."}
{"schema_version":1,"at":ts,"kind":"verify","routine_id":"<id>","overlay_id":"<id>",
 "overlay_hash":"sha256:..","verified":true,"diff":[]}
```

`kind` is `write`, `verify` or `retire`. The client appends a `write` line
for every non-GET request, success or failure, once its retries are over.
`status` is the final HTTP status, or null when no response arrived
(timeout, unreachable). Schema: `hevy_write_line` (R-14 adds the `verify`
and `retire` line schemas). The API key never appears.

## C10. Overlay document (R-13 owns; R-14, R-15, R-16 read)

```json
{
  "schema_version": 1,
  "id": "2026-10-12-weekly",
  "kind": "weekly",
  "created_at": "2026-10-11T19:00:00Z",
  "span": {"start": "2026-10-12", "end": "2026-10-18"},
  "supersedes": "2026-10-05-weekly",
  "focus": "One line for the week.",
  "flags": [
    {"code": "stale_prescription", "severity": "block", "session_id": "mon-lower",
     "exercise_id": "db_bench_press", "message": "...", "resolved": false, "resolution": null}
  ],
  "approval": null,
  "sessions": [
    {
      "session_id": "mon-lower",
      "date": "2026-10-12",
      "title": "Mon — Lower",
      "hevy_routine_id": "uuid-or-null",
      "temporary": false,
      "location": null,
      "focus": null,
      "exercises": [
        {
          "exercise_id": "db_bench_press",
          "hevy_template_id": "3601968B",
          "load_mode": "per_hand_x2",
          "rest_seconds": 120,
          "superset_id": null,
          "cues": "elbows tucked · feet planted",
          "focus": null,
          "target_note": "add 2.5 from last week",
          "change": "22.5 → 25/hand",
          "override": null,
          "sets": [
            {"type": "warmup", "reps": 10, "load": {"mode":"per_hand_x2","unit":"kg","per_hand":12.5,"hevy_total":25,"hevy_kg":25.0}},
            {"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 8,
             "load": {"mode":"per_hand_x2","unit":"kg","per_hand":25,"hevy_total":50,"hevy_kg":50.0}}
          ]
        }
      ]
    }
  ]
}
```

- `kind`: `weekly`, `midweek`, `deload`, `one_off`.
- Set keys: `type` (`normal`, `warmup`, `dropset`, `failure`), exactly one
  of `reps` or `rep_range`, optional `rpe`, `load` (null or absent for
  `band`, `duration`, `distance`), `duration_seconds`, `distance_meters`.
  Absent and null are equivalent in the overlay; the Hevy writer omits
  them (Hevy rejects nulls). A `duration` set needs `duration_seconds` and
  a `distance` set needs `distance_meters`; for those two modes `reps` and
  `rep_range` are optional (at most one). `rep_range.start` is at most
  `end`. `rpe` is 1 to 10. Working sets are `normal`, `dropset` and
  `failure`.
- Loads: every load object passes `units.check_load`, its `mode` equals
  the line's `load_mode` and its `unit` equals `[athlete] units`. The
  validator reports each problem at the field's JSONPath
  (`...load.hevy_total`).
- **Null load on a loaded mode.** A working set of `total`,
  `per_hand_x2`, `single_implement`, `bodyweight` (added load) or
  `assisted` may carry `load: null` only when its line has a `no_data`
  flag (R-23a) or is a calibration line (R-41b week one). R-13's validator
  accepts it only with that flag on the line; otherwise it is a validation
  error. A warm-up set may leave its load null without a flag. R-14's
  writer omits `weight_kg` for such a set.
- Session `location`: null or a `[equipment.locations.*]` name (C54),
  defaulting to the program session's location. A constrained one-off week
  (hotel, home) sets it so caps, representable loads and substitution use
  that kit.
- `override`: null or `{"reason": "non-empty", "proposed_sets": [...]}`.
- `approval`: null or `{"approved_at": ts, "hash": "sha256:..."}`. The hash
  is the canonical hash (C7) of the whole document with `approval`
  removed. Any edit after approval, including resolving a flag, breaks it.
- Flag `severity`: `info`, `warn`, `block`. Push refuses any `block` flag
  with `resolved: false`, and so does `overlay approve` (exit 3). Flag codes
  are registered (C20). A flag naming an exercise names its session too,
  and both exist in the overlay. A resolved flag has a non-empty
  `resolution`; an unresolved one has null.
- `superset_id`: null or a non-negative integer (Hevy's shape).
- **Overlay in force** for a date D: of the overlays whose span contains D
  and which have a session dated D, the one with the latest `created_at`.
  On a day none of them has a session (a rest day), the latest-created
  overlay whose span contains D is in force with no session. Ties on
  `created_at` go to the later id. `supersedes` is an audit link;
  resolution does not depend on it. `coach.overlay.in_force(root, date)`
  returns `(overlay, session)`, with session None on a rest day, or None
  when no span contains D.
- File name is `data/overlays/<id>.json`; id is `<span.start>-<kind>`,
  with `-2`, `-3` on collision. The kind's underscore becomes a hyphen in
  the id, because ids match `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`:
  `2026-10-12-one-off`.
- **Draft** (`coach/schemas/overlay_draft.schema.json`). The coach writes
  the overlay's shape in athlete units, each set's `load` a number (per
  hand for per-hand modes, added load for `bodyweight`, assistance for
  `assisted`, else the total) or null. `overlay build --input FILE`
  fills what the draft leaves out: `id` (from span and kind, next free
  suffix), `created_at` (now), `supersedes` null, `flags` [] (each flag
  `resolved` false, `resolution` null), `approval` null, session
  `hevy_routine_id` null, `temporary` false, `location` from the program
  session of the same id when `data/program.json` exists (else null),
  and null for every optional line field. A draft that names an existing
  `id` rebuilds that overlay, unless it is approved (exit 3).
- `overlay approve ID` validates first (exit 1), refuses unresolved `block`
  flags (exit 3), and leaves an overlay whose approval still holds
  untouched.
- Later versions: v2 adds line `provenance` (R-24, C21); v3 adds line
  `fold` and session `moved_from` (R-22, C37).

## C11. Rendered markdown markers (R-13, R-16, R-17a; later renderers follow it)

- A whole rendered file starts with
  `<!-- generated by coach from <source path>; edit the data, then run: python3 -m coach <command> -->`.
  The header may carry an as-of time after the source path:
  `<!-- generated by coach from <source path> as of <timestamp>; edit the data, then run: python3 -m coach <command> -->`.
  A renderer that reads history renders as of that time, so a fresh render
  is reproducible and a page goes stale only when its inputs change, not
  when a day passes (R-25 pages).
- A rendered region inside a prose file (the check-in's "The week ahead")
  sits between `<!-- coach:begin <kind> <id> -->` and
  `<!-- coach:end <kind> <id> -->`. Region kinds: `overlay <overlay id>`
  (R-13), `week-review <record date>` (R-21a), `research <note id>`
  (R-32a), `card <slug>` (R-33b), `cardio <week label>` (R-43).
- Freshness means the bytes equal a fresh render. Each renderer exposes
  `render_<kind>(root, id) -> str` so `coach check` can compare; R-13's is
  `coach.render.render_overlay(root, id)`. The region's bytes run from the
  start of the begin marker to the end of the end marker.
- `coach.render.find_regions(text, kind)` and `coach.render.splice_region(text,
  kind, id, region)` (R-13) find and replace marked regions for every
  renderer. `splice_region` replaces the region in place; when the file has
  none, it adds the region at the end of the `## The week ahead` section,
  or at the end of the file, and changes nothing else.
- **Archive rule:** `week-review` regions in any record but the newest are
  archive. `render_week_review(id)` returns them unchanged, so R-16's sweep
  never fails an old record because history was later corrected. `cardio`
  regions are snapshots with no freshness check (late syncs must not fail
  old records).
- **Hidden data block.** A markdown file whose structured part a human
  edits (a research note, C28; a recipe card, C33) starts with a TOML block
  inside an HTML comment, which GitHub hides. The file's first line is
  exactly `<!-- coach:<kind>` (`note`, `card`); the block ends at the first
  line that is exactly `-->`; the text between is TOML. The TOML must not
  contain `-->`. Everything after the block is markdown: prose, rendered
  regions or both.
- One parser reads every kind: `coach.datablock.read(path, kind) ->
  (data: dict, rest: str)`, raising a validation error that names the file
  for a missing opener, a missing closer, a wrong kind or invalid TOML.
  Whichever of R-32a and R-33b merges first adds it; the other reuses it.
- Scripts never rewrite a hidden data block (ADR-0001: scripts don't write
  TOML). A command that needs one prints its text for the coach to write.
  The exceptions are named in the owning section.

## C12. Hevy routine note (R-13 renders, R-14 writes)

```
Wk of 12 Oct: <week focus>        (first exercise of each routine only)
Target: 3×8–10 @ 25/hand (Hevy: 50) @ RPE 8
Focus: <exercise focus, only when set>
Cues: <cues>
```

- Warm-up sets are left out of the Target line. Consecutive working sets
  with equal reps or range, load and RPE collapse to `N×reps`; groups join
  with ` + `. A `total` load carries its unit (`3×5 @ 100 kg @ RPE 7`, as
  in `reference/hevy-api.md`); every other load prints exactly as
  `format_load` gives it.
- The Target line is absolute. It never carries `target_note` or `change`:
  relative wording ("add 2.5 from last week") goes stale in the app. Those
  fields appear in the brief and the check-in only.
- A working set with a null load on a loaded mode (C10) prints the sets,
  reps and RPE followed by ` · choose the load`:
  `Target: 3×8–10 @ RPE 7 · choose the load`. The suffix appears once, at
  the end of the line.
- The first exercise's note carries an extra first line, because Hevy
  drops routine-level notes on PUT: `Wk of <span.start as D Mon>: ` then the
  overlay `focus`, about 80 characters at most. The date lets the athlete
  spot a stale note mid-session. It is always the week focus; a session's
  own emphasis goes in its exercises' `Focus:` lines.

## C13. Checks (R-10 registry; every item adds its own)

```python
@check(id="overlay_arithmetic", owner="R-13")
def overlay_arithmetic(ctx) -> list[Result]: ...
# Result(status="pass"|"warn"|"fail"|"skip", message=str, path=str|None)
```

`coach check` output: `data.results` (list of `{id, owner, status,
message, path}`) and `data.summary` (`{pass, warn, fail, skip}`). Exit 1 if
any `fail`. Every check ships with a passing and a failing fixture
instance under `tests/fixtures/instances/`.

The registry (R-10) runs each check with a `Context`. A check that raises
`ConfigError` (it read `ctx.config` and there is none, or it is invalid)
becomes one `skip` result; any other exception becomes one `fail` result
with the traceback on stderr; an empty list becomes one `pass` result.
`--only` takes comma-separated ids and may repeat; an unknown id exits 2.
R-10 registers `python_floor` and `config` in `coach/checks/environment.py`.

The sections from C17 on name the checks their owners register. R-32a
registers `research_notes`, `research_citations`, `research_render_fresh`
and `research_expiry`.

## C14. Shared test fixture ids

So fixtures from parallel items line up, the shared valid instance
`tests/fixtures/instances/valid/` uses these ids. Each item adds its own
files to it; nobody edits another item's files.

| Thing | Value |
|---|---|
| units | kg |
| exercises (`id`, mode, Hevy template id) | `bb_back_squat` total `F0000001`; `db_bench_press` per_hand_x2 `F0000002`; `db_single_arm_row` single_implement `F0000003`; `pull_up` bodyweight `F0000004` |
| routines | `00000000-0000-4000-8000-000000000001` "Session A" (squat, DB bench); `...0002` "Session B" (row, pull-up) |
| sessions | `session-a`, `session-b` |
| overlay | `2026-10-12-weekly`, span 2026-10-12 to 2026-10-18, approved; Session A 2026-10-12 (squat 100, DB bench 25/hand (Hevy: 50)), Session B 2026-10-15 (row 30 (Hevy: 30), pull-up BW); built from `tests/fixtures/overlay/draft-kg.json` |
| check-in (R-13) | `check-ins/2026-10-11.md` holding the rendered region of `2026-10-12-weekly` |
| `COACH_NOW` | `2026-10-11T18:00:00Z` |
| activities (R-42a) | `manual:2026-10-08-run-1` run 5 km, 30 min, RPE 6; Hevy workout `00000000-0000-4000-8000-0000000000c1` "Conditioning", all-conditioning, starting 6 min after `manual:2026-10-10-conditioning-1` (the dedup pair) |
| wellness (R-42a) | daily device-style records 2026-10-05 to 2026-10-10 with sleep; one manual span record 2026-10-05 to 2026-10-11 at 7.0 h |
| planned (R-42a) | `manual:2026-10-14-run-1` "Easy 5 km", `manual:2026-10-16-run-1` "Intervals" `quality: true` |
| nutrition (R-33a) | `[nutrition]` app macrofactor, phase recomp, reference mass 80, floor 110, target 128, stretch 176, `floor_since` 2026-09-28, one anchor "Whey shake" 150 kcal / 30 g daily snack |
| readings (R-33a) | 2026-09-28 (avg protein 104), 2026-10-04 (112), 2026-10-11 (115), app target protein 110 |
| cards (R-33b) | `chicken-rice-bowl` lunch 610/50/55/18 with `light` variation; `overnight-oats` breakfast; `whey-shake` snack |
| meal plan (R-33c) | `2026-10-12`, span 2026-10-12 to 2026-10-18 |
| research (R-32a) | template note `research/fixture-dose.md` (area `volume`, claims 1 and 2 current, `review_by` 2028-03-01); local note `research/local/local-fixture-knee.md` (area `rehab`, `updates = ["rn:fixture-dose.2"]`); `reference/fixture-guide.md` citing claim 1 of `fixture-dose`; record `check-ins/2026-08-30.md` (weekly) citing claim 1 of `local-fixture-knee` |

Logged workouts in the valid instance (R-20 adds them as synthetic Hevy
workouts; ids `10000000-0000-4000-8000-00000000000N`):

| N | Date | Routine | Logged |
|---|---|---|---|
| 1 | 2026-09-28 | Session A | squat 3×5 @ 95 RPE 7; DB bench 3×10 @ Hevy 45 (22.5/hand) RPE 8 |
| 2 | 2026-10-01 | Session B | row 3×10 @ 30 RPE 8; pull-up 3×8 BW |
| 3 | 2026-10-05 | Session A | squat 3×5 @ 97.5 RPE 7.5; DB bench 3×10 @ Hevy 45 RPE 8 |
| 4 | 2026-10-08 | Session B | row 3×10 @ 30 RPE 8.5; pull-up 3×8 BW |

Further fixture instances, each owned by the item that first needs it.
Unless stated, each is a copy of `valid/` plus what is listed.

| Instance | Owner | Holds |
|---|---|---|
| `layoff/` | R-24 | same program; last workout 2026-09-14, so 28 days off before 2026-10-12 |
| `slip/` | R-20 | DB bench logged Hevy 45 on 2026-09-28 and Hevy 90 on 2026-10-05 at the same reps and RPE, and DB shoulder press doubling on the same date |
| `checkin/` | R-21a | external session `pt-tue` (Tue) in the program; approved overlay `2026-10-05-weekly` (span 2026-10-05..2026-10-11: Session A 2026-10-05 squat 3×5 @ 97.5 RPE 7.5, DB bench 3×10 @ 22.5/hand (Hevy: 45) RPE 8; Session B 2026-10-08 row 3×10 @ 30 RPE 8, pull-up 3×8 BW; Session A 2026-10-10 as on 10-05); records `check-ins/2026-09-06.md` (deep) and `check-ins/2026-10-04.md` (weekly); `[sessions.cap_minutes] session-a = 45`; `writes.jsonl` verify lines for both routines at 2026-10-04T19:00:00Z; cached routine `...0002` with `updated_at` 2026-10-07T07:00:00Z and one extra exercise |
| `gap/` | R-21b | same program as `checkin/`; record `check-ins/2026-09-13.md` (weekly); last workout 2026-09-14 (squat 3×5 @ 100), none after; no overlay after 2026-09-20 |
| `missed/` | R-22 | program with rules `miss-b` (fold row, 2 sets, into Session A), `miss-a` (shift to sat, then thu); approved overlay `2026-10-12-weekly` re-dated: Session A 2026-10-12, Session B 2026-10-14, Session A 2026-10-17; workout for Session A on 2026-10-12 only |
| `dose/` | R-30a | program with `pt-tue` estimated at `{"chest": 3, "lats": 3}`; weekly overlays for 2026-W36 to 2026-W41; workouts and `external` annotations giving the weeks below (planned = Session A, Session B, PT = 3) |
| `block/` | R-31 | program with `hard_weeks_ceiling` 6 and `pt-tue`; a ledger with block `b-0001` started 2026-08-31 and no closed weeks; weekly overlays for 2026-W36 to W41; workouts matching each overlay (every core session at the prescribed sets and RPE) plus `external` done annotations. Closing W36 to W41 gives six hard weeks |
| `nohevy/` | R-40c | the valid program and overlay; `[hevy] enabled = false`; no Hevy cache; `data/log/workouts.jsonl` holding the two Session A workouts of the logged-workouts table, logged by hand (squat 3×5 @ 95 RPE 7, DB bench 3×10 @ 22.5/hand RPE 8; the same on 2026-10-05 at 97.5) |
| `empty/` | R-41a | `config.toml` and an instance library only: no program, no state. Not a copy of `valid/` |
| `hevy-fresh/` | R-12 | `valid/`'s `config.toml` and a cache `meta.json` with the last pull at 2026-10-11T12:00:00Z (6 hours before `COACH_NOW`) |
| `hevy-stale/` | R-12 | the same with the last pull at 2026-10-09T12:00:00Z (54 hours) |
| `cardio/` | R-43 | see C50 |
| `research-bad/` | R-32a | not a copy of `valid/`: the valid config; `fixture-dose` with a hand-edited claims table; `fixture-broken` with two claims numbered 1; `fixture-old` expired 2026-10-01 (area `sleep`); `reference/fixture-guide.md` citing a missing claim |
| `interference/` | R-44a | a planned quality run on 2026-10-11 and Session A (squat at RPE 7) on 2026-10-12 |
| `overlay-bad-schema/`, `overlay-bad-arithmetic/`, `overlay-stale-render/` | R-13 | `config.toml` plus the valid overlay with one fault each: Session B dated outside the span; DB bench working sets at `hevy_total` 25 for 25/hand; a hand-edited check-in region |

`dose/` weeks:

| Week | Trained | Note |
|---|---|---|
| W36 | 3 | |
| W37 | 3 | |
| W38 | 1 | Session B `miss` tag `time`; PT not done |
| W39 | 2 | Session A missed, untagged |
| W40 | 2 | PT not done |
| W41 | 2 | Session B missed, tag `sleep` |

Trailing four ordinary weeks to 2026-10-11 (W38–W41): 7 of 12 = 58 %.

Synthetic Hevy fixture set `tests/fixtures/hevy/wave/` (R-41a; its
`routines.json`, layered over `synthetic/`, C15): four routines "W1
Squat Day", "W2 Squat Day", "W3 Squat Day", "Bench Day", squat top loads
85, 90, 95, with "TM 100" in a note.

## C15. Hevy fixtures and anonymisation (R-12)

- **A fixture set is a directory** with one file per collection:
  `workouts.json`, `workout_events.json`, `routines.json`,
  `routine_folders.json`, `exercise_templates.json`,
  `body_measurements.json`, each `{"x-synthetic": true, "<stem>": [...]}`
  holding the raw items. A missing file is an empty collection.
  `FixtureTransport` serves Hevy's pages (newest first; page sizes past
  the API's limits are a 400), single-item GETs, `/v1/workouts/count`, and
  events filtered by `since`; it answers any write with a 405. Several
  directories joined with `os.pathsep` layer: for each file, the last
  directory that has it wins.
- `tests/fixtures/hevy/synthetic/` holds the C14 exercises, routines (in
  folder 1 "Program"), the four C14 workouts and two body measurements.
  `tests/fixtures/hevy/synthetic-later/` holds one updated and one deleted
  workout event dated 2026-10-12, for layering over it.
- `tests/support/fake_hevy.py` (`FakeHevy`, `FakeClock`) is a stateful fake
  seeded from a fixture set: it stores writes, drops routine-level
  `notes`, answers a `null` set field with a 400, answers 429 to an eighth
  write inside 10 seconds, and bumps `updated_at` on every write. Tests
  inject it by patching `coach.hevy.transport.from_env`.
- Synthetic fixtures (hand-written from the documented API shape) are
  marked `"x-synthetic": true` at the top of the fixture file and are what
  every agent uses. The API shape comes from
  `https://api.hevyapp.com/docs/swagger-ui-init.js`, which needs no key.
- Recorded fixtures come from `hevy record-fixtures`, run by a human with a
  real key, GET requests only. The anonymiser:
  - replaces routine, workout and custom-template ids with
    deterministic fake UUIDs (salted hash, so joins survive), and folder
    ids, which Hevy gives as integers, with deterministic fake integers;
  - keeps built-in exercise template ids and titles (public catalogue);
  - replaces workout titles, routine titles, folder titles and custom
    exercise titles with `Workout N`, `Routine N`, `Folder N`,
    `Custom exercise N`;
  - replaces every `description` and `notes` with `note N` (non-empty
    stays non-empty, empty stays empty);
  - shifts every timestamp and date by a whole number of weeks (keeps
    weekdays and gaps);
  - keeps sets, reps, weights and RPE; replaces body-measurement values
    with synthetic ones; drops `/v1/user/info` entirely;
  - asserts the output contains none of: the API key, any original id, any
    original title or note text (titles that equal a built-in exercise
    title are public and allowed);
  - refuses a collection it has no rule for. The salt is random per run
    and never stored. Recorded files are marked `"x-anonymised": true`.

## C16. Program and state documents (R-17a owns; R-22, R-23a, R-30a, R-31, R-41a, R-44a read)

A starting design, not a fixed one. The R-17a builder may change or improve
it where building it shows a better shape; the change goes in this section in
the same PR and is listed in the PR description under "Schema changes".

`data/program.json`:

```json
{
  "schema_version": 1,
  "name": "Upper/lower, 4 days",
  "sessions": [
    {
      "id": "session-a",
      "title": "Mon — Lower",
      "kind": "lifting",
      "tier": "core",
      "status": "active",
      "location": null,
      "focus": null,
      "exercises": [
        {
          "exercise_id": "bb_back_squat",
          "load_mode": "total",
          "sets": [
            {"count": 1, "type": "normal", "reps": 5, "rpe": 8},
            {"count": 3, "type": "normal", "reps": 5, "rpe": 7}
          ],
          "rest_seconds": 180,
          "superset_id": null,
          "cues": "brace · knees out",
          "constraints": [],
          "scheme": {"name": "double_progression", "params": {}},
          "start_load": 100
        }
      ]
    }
  ],
  "external_sessions": [
    {"id": "pt-tue", "title": "PT", "weekday": "tue", "estimated_sets": {"chest": 3}}
  ],
  "schedule": {"rule": "fixed_weekdays", "params": {}},
  "blocks": {"hard_weeks_ceiling": 6, "deload_rule": {"name": "standard", "params": {}}},
  "missed_day_rules": [
    {"id": "miss-a", "session_id": "session-a", "condition": "...", "action": "..."}
  ]
}
```

- `kind`: `lifting`, `conditioning`. `tier`: `core`, `optional`. `status`:
  `active`, `parked`, `standby`.
- `location`: null (the main `[equipment]` table) or the name of a
  `[equipment.locations.*]` table (C54); `program validate` fails on a name
  config does not define.
- `sets` is a list of set groups. Each group has `count`, `type` (as in
  C10), exactly one of `reps` or `rep_range`, and optional `rpe`,
  `duration_seconds`, `distance_meters`. A plain 3×5 is one group.
- `start_load` is in athlete units and per hand for per-hand modes, like
  every load a human writes; code builds load objects from it (C5).
- `schedule.rule`: `fixed_weekdays`, `alternating_external_anchor`,
  `next_in_sequence`, `explicit_calendar`.
- Scheme, schedule and deload names are checked against a fixed list; their
  `params` are free-form objects in v1. R-23a adds a schema per plugin and
  bumps the version (C23).
- Missed-day rules are free text in v1; R-22 makes them executable (C37).

`data/state.json`:

```json
{
  "schema_version": 1,
  "rotation": {"position": "week-a", "confirmed": true, "confirmed_at": "2026-10-11"},
  "block": {
    "started": "2026-09-01",
    "hard_weeks_completed": 3,
    "deload": {"status": "not_due", "since": null}
  },
  "one_off": null,
  "scheme_state": {"session-a/bb_back_squat": {}},
  "hevy": {
    "routines": {"00000000-0000-4000-8000-000000000001": {"session_id": "session-a"}},
    "folders": {"program": null, "one_off": null},
    "temporary_routines": []
  }
}
```

- `deload.status`: `not_due`, `due`, `in_progress`, `done`, `skipped`.
  R-31 replaces `block` with the C42 shape.
- `one_off`: null or `{"overlay_id": id, "span": span}`.
- `hevy.routines` replaces `routine/hevy-map.json`. R-14b's `routines
  create` records new routine ids here, never in the overlay.

**Schema versions.** R-17a ships program and state v1; R-23a takes both to
v2 (C23). Every later bump takes the next free version when it merges and
adds one step to the R-17a migration chain, so the chain stays linear.
Program bumps: R-22 (executable `missed_day_rules`, C37), R-30a
(`dose_targets`, C40), R-30b (`priority`, `minimum_week`, C40), R-44a
(`interference`, C51), R-44b (session `scheme`, C51). State bump: R-31
(`block`, C42). Overlay: R-24 takes it to v2 (C21) and R-22 to v3 (C37). A
brief or section that names a version number means the next free one.

## C17. History cache (R-20 writes; R-21a, R-23a, R-24, R-25, R-30a, R-31, R-43 read)

Resolved workouts are durable instance data, not a cache to rebuild at
will: the per-set load is resolved once, with the load mode in force on
that date, so a later change to the library or the program cannot
reinterpret old sets. The raw Hevy cache (C8) and the manual log (C46)
stay the inputs.

`data/history/<YYYY-MM>.json`, one per calendar month of the workout's
local start date (`[athlete] timezone`):

```json
{
  "schema_version": 1,
  "month": "2026-10",
  "workouts": [
    {
      "workout_id": "10000000-0000-4000-8000-000000000003",
      "source": "hevy",
      "hevy_updated_at": "2026-10-05T18:40:00Z",
      "resolved_at": "2026-10-11T18:00:00Z",
      "date": "2026-10-05",
      "start_time": "2026-10-05T17:30:00Z",
      "end_time": "2026-10-05T18:28:00Z",
      "duration_minutes": 58,
      "title": "Session A",
      "description": "",
      "routine_id": "00000000-0000-4000-8000-000000000001",
      "session_id": "session-a",
      "overlay_id": "2026-09-28-weekly",
      "exercises": [
        {
          "exercise_id": "db_bench_press",
          "hevy_template_id": "F0000002",
          "load_mode": "per_hand_x2",
          "load_mode_source": "overlay",
          "notes": "",
          "sets": [
            {"index": 0, "type": "normal", "reps": 10, "rpe": 8, "weight_kg": 45,
             "load": {"mode": "per_hand_x2", "unit": "kg", "per_hand": 22.5, "hevy_total": 45, "hevy_kg": 45.0},
             "duration_seconds": null, "distance_meters": null}
          ]
        }
      ]
    }
  ]
}
```

- `source`: `hevy` or `manual`. Manual workouts (C46) have
  `hevy_updated_at` and `routine_id` null, and `workout_id` is the log id
  (`manual:2026-10-12-session-a-1`).
- `session_id` and `overlay_id`: from the overlay in force on `date`
  (C10) whose session carries this `routine_id`; else null. A manual
  workout carries its own `session_id` and `overlay_id`. A workout with no
  routine (an ad hoc or coach-led log) has both null.
- `load_mode_source`: `annotation` > `overlay` > `library` (first that
  answers wins); manual workouts use `log` (the mode written on the line).
  An exercise with no library match keeps `exercise_id: null` and
  `load_mode: null`; stats skip it and the `history_unresolved` check warns.
- `weight_kg` is the raw logged value; null for manual workouts. `load` is
  built with `units.from_hevy_kg` then `units.make_load`, with the
  per-hand or total value rounded to 2 decimals first; for manual workouts
  with `units.make_load(value, load_mode, unit)`. No other code converts.
- **Sources.** `history sync` gathers input workouts from source modules
  in `coach/history_sources/` (C1 registry rule). R-20 ships `hevy`; R-40c
  adds `manual`. A source module exposes `workouts(root) ->
  list[SourceWorkout]` and `version(workout) -> str`; a changed version
  re-resolves the workout.
- **Freezing.** `history sync` resolves source workouts not yet in a month
  file, and re-resolves one only when its version (`hevy_updated_at` for
  Hevy) changed; a re-resolve keeps each exercise's stored `load_mode`
  unless a `load_mode` annotation now covers it. A workout deleted at the
  source is removed and reported. `history rebuild --month M` re-resolves
  a month under current rules; it is the only path that can reinterpret,
  and `--dry-run` shows the per-set differences.
- `exercises[].sets[]` keeps every set as logged, warm-ups included.
  Annotations are applied when reading (below), never written into the
  month file, so the file stays a faithful copy of the log.
- Workouts whose `session_id` resolves to a session of `kind:
  conditioning` are left out of e1RM, exposures, dose and exercise
  adherence (C18); the session's trained status comes from its matched
  Activity (C51). R-20 builds this; R-44b adds it if R-20 has not.

`data/history/annotations.json` replaces prose warnings about the log:

```json
{
  "schema_version": 1,
  "annotations": [
    {"id": "a-0001", "kind": "discount", "created_at": "2026-10-11T18:00:00Z",
     "source": "check-in 2026-10-11", "reason": "logged Hevy 90 for 22.5/hand",
     "workout_id": "…", "exercise_id": "db_bench_press", "set_index": null},
    {"id": "a-0002", "kind": "repair", "workout_id": "…", "exercise_id": "bb_back_squat",
     "set_index": 2, "field": "reps", "value": 5, "reason": "typo: 55", "created_at": "…", "source": "coach"},
    {"id": "a-0003", "kind": "load_mode", "exercise_id": "db_curl", "span": {"start": "2026-08-01", "end": "2026-08-31"},
     "load_mode": "single_implement", "reason": "alternated all August", "created_at": "…", "source": "coach"},
    {"id": "a-0004", "kind": "unknown_convention", "exercise_id": "db_row", "span": {"start": "…", "end": "…"},
     "reason": "cannot tell per-hand from total", "created_at": "…", "source": "audit"},
    {"id": "a-0005", "kind": "confirm", "workout_id": "…", "exercise_id": "db_bench_press",
     "reason": "real jump: moved to heavier dumbbells", "created_at": "…", "source": "check-in 2026-10-11"},
    {"id": "a-0006", "kind": "miss", "date": "2026-10-07", "session_id": "session-b", "tag": "sleep",
     "created_at": "…", "source": "check-in 2026-10-11", "reason": null},
    {"id": "a-0007", "kind": "external", "date": "2026-10-06", "external_id": "pt-tue", "done": true,
     "note": "chest and back", "created_at": "…", "source": "check-in 2026-10-11", "reason": null},
    {"id": "a-0008", "kind": "trained_unlogged", "date": "2026-10-09", "session_id": "session-b",
     "note": "trained at the hotel gym, phone dead", "created_at": "…", "source": "check-in 2026-10-11", "reason": null}
  ]
}
```

| `kind` | Effect when read | Written by |
|---|---|---|
| `discount` | the set (or whole exposure when `set_index` null) is left out of e1RM, PRs, audit and progression; still counts for dose | coach, R-21a |
| `repair` | the corrected `field` (`reps`, `rpe`, `weight_kg`, `type`) replaces the logged value everywhere; the month file keeps the raw value | coach |
| `load_mode` | forces the load mode for that exercise in the span; applied by `history sync` (re-resolves the affected workouts and reports it) | coach |
| `unknown_convention` | loads in the span are left out of e1RM and progression; sets still count for dose | coach, audit |
| `confirm` | closes a `convention_slip` candidate as genuine | coach, R-21a |
| `miss` | a planned session not trained; `tag` in `time`, `sleep`, `ill`, `family`, `skipped`, `other` (R-01). No tag recorded means `untagged` | R-21a, R-21b, R-22 |
| `external` | a coach-led session from `program.external_sessions` happened (`done` true) or not, with a one-line note of its content | R-21a; R-30a reads |
| `trained_unlogged` | a planned session was trained but not logged (`date`, `session_id`, `note`). Adherence counts it `trained` with `unlogged: true`; its exercises are `unknown`; it adds no dose and no e1RM point | R-21a (from the reply to the Sunday message), coach |

- Ids are `a-NNNN`, never reused. Annotations are appended; a wrong one is
  withdrawn by a later annotation of the same kind with `"withdraws": "a-0003"`.
- `history annotate` takes flags (`--kind`, `--workout`, `--exercise`,
  `--set`, `--date`, `--session`, `--tag`, `--reason` ...) or `--input FILE`
  for a batch. Claude Code's Bash tool has no stdin, so no prompt reads it.
- Check `annotations_valid`: every referenced workout, exercise and
  session exists; tags are in the enum.

**Exposure** (glossary term) in code: one exercise in one resolved
workout with at least one non-warm-up set left after annotations.

```python
coach.history.workouts(root, since=None, until=None, include_unsynced=False) -> list[ResolvedWorkout]   # annotations applied
coach.history.exposures(root, exercise_id, before=None) -> list[Exposure]       # newest first
# Exposure: date, workout_id, session_id, exercise_id, load_mode, sets (working sets only),
#           suspect (open convention_slip candidate), excluded (discount / unknown_convention)
coach.history.last_lifting_date(root, before) -> date | None                    # any workout with a lifting exercise
coach.history.annotations(root, kind=None) -> list[dict]
```

`include_unsynced=True` (on `workouts` and every `coach.stats` function)
resolves source workouts not yet in a month file in memory, by the same
rules as `history sync`, and returns them with `unsynced: true`; nothing is
written. `checkin prepare` and the scheduled run use it to read fresh data
without touching committed files.

## C18. Derived stats (R-20; R-21a, R-23a, R-24, R-25, R-30a, R-31, R-43 read)

All stats read C17 with annotations applied. Loads are in athlete units
and are the **coaching number**: `per_hand` for `per_hand_x2` and
`single_implement`, the total for `total`, the added load for
`bodyweight`, the assistance for `assisted`.

**e1RM** (one formula, one module; R-23a and R-24 import it):

```python
coach.stats.e1rm(load, reps, rpe=None) -> float | None
coach.stats.load_for(e1rm, reps, rpe) -> float          # inverse; R-23a schemes, R-24 feasibility
coach.stats.implied_rpe(e1rm, load, reps) -> float       # R-24
```

- Reps to failure `n = reps + (10 − rpe)` when RPE is logged, else
  `n = reps`. `e1rm = load` when `n ≤ 1`, else `load × (1 + n/30)`
  (Epley). Sets with `n > 12` give no e1RM. Method recorded per point:
  `epley_rir` or `epley`.
- Inverse: `load_for(e1rm, reps, rpe)` = `e1rm` when `n ≤ 1`, else
  `e1rm / (1 + n/30)`. `implied_rpe(e1rm, load, reps)` = `10 − (n − reps)`
  with `n = max(1, 30 × (e1rm/load − 1))` when `load ≤ e1rm`, and
  `n = 30 × (e1rm/load − 1)` (negative: beyond failure) when `load > e1rm`.
  So a single at the e1RM implies RPE 10.
- Only `total`, `per_hand_x2`, `single_implement` lifts get a series.
  Bodyweight and assisted lifts get one only when a body-measurement
  weight exists within 14 days (`bodyweight + added`, `bodyweight − assist`).
- Excluded: warm-ups, discounted sets, `unknown_convention` spans, open
  `convention_slip` candidates, conditioning-session workouts (C17).

`stats e1rm [--exercise ID] [--since D]` →
`data.series[exercise_id] = [{date, e1rm, method, workout_id, set_index, load, reps, rpe}]`
(best set per exposure), plus `best` `{e1rm, date}` over the window and
`delta` (latest minus previous point).

**Adherence per overlay.** `stats adherence (--overlay ID | --span A..B)`:

- Planned sessions: those of the overlay in force on each date (C10),
  up to today; later ones are `upcoming`.
- Session `status`: `trained` (a workout with the session's routine id,
  or for a manual workout its `session_id`, inside the overlay span,
  matched once, nearest date first; `moved: true` when the date differs;
  or a `trained_unlogged` annotation, with `unlogged: true`), `missed`
  (with `tag` from a `miss` annotation, else `untagged`), `upcoming`.
  Workouts matching no planned session are listed as `extra`.
- Exercise `status` for a trained session, comparing working sets in order:
  `missing` (no logged working set of that exercise), `under` (any
  prescribed set absent, reps below the target or the range's start, or
  load below prescription by more than half the increment), `over` (no
  set under, and load above prescription by more than half the increment
  or extra working sets), else `hit`. Reps above a range's top are `hit`.
  Every exercise of a `trained_unlogged` session is `unknown`.
- Each exercise also carries `rpe_delta` (mean logged minus target over
  sets with both) and `sets_prescribed`, `sets_logged`.
- `data.summary`: sessions planned, trained, missed (by tag), and
  exercise counts by status.

**Delivered sets per muscle (dose).** `stats dose (--week W | --span A..B)`:

- A hard set is a logged working set (`normal`, `failure`, `dropset`) not
  logged at RPE 5 or below; each drop counts as one set.
- `coach.stats.set_weights(entry) -> dict[muscle, float]`: 1.0 for each
  primary muscle and 0.5 for each secondary muscle of an R-11 library
  entry. Delivered dose here and planned dose (C41) both call it.
- `direct`: hard sets where the muscle is a primary muscle of the
  exercise. `fractional`: hard sets weighted by `set_weights`.
- Output per week and per workout:
  `{"week": "2026-W41", "muscles": {"chest": {"direct": 6, "fractional": 7.5}}, "by_workout": {...}}`.
- Logged workouts only. Coach-led sessions not logged in Hevy are added
  from `program.external_sessions` estimates by R-30a (C41), not here.

**Durations.** `stats durations --span A..B` → per workout
`{workout_id, date, session_id, minutes, cap_minutes, over_cap}` (cap from
C19). A logged workout over its cap gets flag `duration_over_cap` (info).

**Convention-jump audit.** `stats audit [--weeks 8]`:

- Scope: exercises with load mode `per_hand_x2` or `single_implement`
  over the last N weeks (default 8).
- Candidate: an exposure whose top working load is 2× (±1 %) or 0.5×
  (±1 %) the previous exposure's, at the same top-set reps and the same
  RPE (or both unlogged).
- Each candidate lists `siblings`: other candidates on the same date.
- Status `open` until a `discount` or `confirm` annotation names it.
  Open candidates are `suspect` exposures (C17) and raise
  `convention_slip` (warn).

**Python API**, mirrored by the commands:
`coach.stats.e1rm_series`, `adherence`, `dose`, `durations`, `audit`,
`set_weights`.

## C19. Config: session caps (R-20 adds; R-21a, R-24, R-25, R-30a read)

```toml
[sessions.cap_minutes]       # optional: session id = minutes; overrides [athlete] session_minutes
# session-a = 60
```

- A session's cap is its `[sessions.cap_minutes]` entry, else `[athlete]
  session_minutes` (C4). A cap of 0 means no cap.
- `[sessions.cap_minutes]` takes arbitrary session-id keys, like `[caps]`.
  Any other key under `[sessions]` is an error. `coach check` warns
  (`session_cap_ids`) on an id that is not in `program.json` when one
  exists.

## C20. Flag registry (R-20 builds; every item registers its own codes)

The flag object is C10's, unchanged:
`{code, severity, session_id, exercise_id, message, resolved, resolution}`.
Severities: `info`, `warn`, `block`. Push refuses an unresolved `block`
(R-14). Week-level flags carry `session_id: null` and `exercise_id: null`.

```python
# coach/flags/<topic>.py
from coach.flags import register
register("stale_prescription", owner="R-24", severities=("block",),
         summary="Line derived from an exposure outside the validity window and not decayed.",
         structural=False)

coach.flags.make(code, severity=None, *, session_id=None, exercise_id=None, message) -> dict
# raises on an unknown code or a severity not in the code's list; default = first listed
coach.flags.for_mode(flags, mode) -> list[dict]     # R-40b; C44
```

Rules:

- Codes are lowercase snake case, `^[a-z][a-z0-9_]*$`. Unique across the
  registry; a test fails on a duplicate, including the same code
  registered twice with different `structural` values.
- **Template items** add codes by adding a `coach/flags/<topic>.py`
  module in their own PR. The table below lists every reserved code with
  its owner and severities; a brand-new code adds its row in the PR that
  registers it. A test (R-20) asserts every registered code appears in
  the table with matching owner, severities and structural value; rows not
  yet registered are allowed. Each owning item's tests assert its own
  codes are registered.
- **Structural** codes propose a change to the program's structure rather
  than to a week's loads. Run mode shows them at `info` (C44).
- **Instance plugins** declare extra codes in their `FLAGS` dict; every
  such code starts `custom_`. Nothing else adds codes, and none is ever
  added during a check-in.
- Check `flag_codes_known` (R-20): every flag in every overlay uses a
  registered code (fail).
- Meal-plan flags (C34) and `nutrition status` flags (C35) are their own
  vocabularies, listed in those sections; they are not overlay flags and
  not in this registry.

Reserved codes:

| Code | Severities | Owner | Structural | Meaning |
|---|---|---|---|---|
| `convention_slip` | warn | R-20 | | Dumbbell exposure jumped exactly 2× or ½× at the same reps and RPE; excluded from e1RM and progression until annotated. |
| `duration_over_cap` | info | R-20 | | A logged workout ran longer than its session cap. |
| `stale_prescription` | block | R-24 | | Line derived from an exposure outside the validity window and not decayed to its band. |
| `unearned_load` | block | R-24 | | Load predicted beyond failure for the prescribed reps, or, with no e1RM, more than two increments above the last exposure. |
| `load_cap` | block | R-24 | | Load above `[caps]` or `dumbbell_max`. |
| `load_unrepresentable` | block | R-24 | | Load cannot be built from the available increments, dumbbells or plates. |
| `load_mode_mismatch` | block | R-24 | | Line's load mode or load arithmetic disagrees with the library or C5. |
| `rpe_infeasible` | warn | R-24 | | RPE target more than 1 away from the RPE implied by load, reps and current e1RM. |
| `session_over_cap` | warn | R-24 | | Estimated session duration above its cap. |
| `no_data` | warn | R-23a | | No usable exposure and no start load; load left empty for the coach. |
| `stalled` | warn | R-23a | | No load or rep gain over three exposures running. |
| `rpe_drift` | warn | R-23a | | Compound or recovery-capped exercise: logged RPE at least 1 over target on two or more working sets of the last exposure (R-05). |
| `return_week` | info | R-23a | | Decay applied; names the band and days off. |
| `return_after_illness` | warn | R-23a | | An `ill` miss or status day in the gap: confirm 48 hours symptom-free; first session capped at RPE 7 (R-02). |
| `constraint_applied` | info | R-23a | | A cap, a slot constraint or a niggle constraint changed the proposal. |
| `override_standing` | info | R-23a | | A standing override was applied again instead of the scheme's proposal. |
| `scheme_reset` | warn | R-23a | | A slot's scheme changed; its state restarted. |
| `rotation_unconfirmed` | warn | R-23a | | The schedule rule advanced the rotation without confirmation. |
| `niggle_escalate` | warn | R-27 | | Niggle reported three check-ins running, or worse: recommend a qualified professional. |
| `followup_due` | info | R-27 | | An open follow-up is past its review date. |
| `evidence_expired` | info | R-32 (module added by R-32a if R-20 has merged, otherwise by R-23a) | | A plugin's cited research note has expired; the rationale says the evidence is under review. |
| `stale_routine` | warn | R-21a | | A routine for an active session does not hold the newest approved overlay's content: the last pass did not write and verify it. |
| `missed_day_rule` | info | R-22 | | A missed-day rule changed this line or session; the message names the rule. |
| `missed_rule_unmatched` | info | R-22 | | No missed-day rule matched; reprogram the rest of the week with `propose week --kind midweek` and a coach's brief. |
| `adherence_low` | warn | R-30a | | Trailing four ordinary weeks below 70 % of planned core and coach-led sessions. |
| `add_session_type_blocked` | warn | R-30a | yes | Adherence below 80 %: no new recurring session without a recorded override. |
| `restructure_required` | warn | R-30a | yes | Adherence below 70 % and no decision in effect: the check-in presents a smaller schedule. |
| `volume_undershoot` | warn | R-30a | yes | A muscle below its dose target, planned on core plus coach-led, or delivered in three of four ordinary weeks. |
| `session_volume_high` | warn, info | R-30a | yes | More than 11 fractional sets for one muscle in one session (warn planned, info logged). |
| `priority_exposures_missed` | warn | R-30b | | A priority lift missed its planned exposure in a week and no floor dose replaced it. |
| `light_week_due` | warn | R-31 | | Ceiling reached, or two fatigue triggers with three or more hard weeks; names the reason and proposed type. |
| `light_week_skipped` | info | R-31 | | Two triggers fired below three hard weeks; light week skipped with the count. |
| `fatigue_watch` | info | R-31 | | One fatigue trigger fired; names it. |
| `deep_review_due` | info | R-31 | | The next check-in is deep; lists the reasons. |
| `cap_breach` | warn | R-43 | | A weekly run, single-run or weekly-quality cap is exceeded, logged or planned. |
| `run_volume_spike` | warn, info | R-43 | | A run is more than `spike_ratio` × the longest run in the lookback (warn logged, info planned). |
| `quality_stack` | warn | R-43 | | Two quality activities on the same or consecutive days. |
| `collision` | warn, info | R-43 (registers), R-44a (emits) | | An interference rule is broken (C51). |
| `sleep_debt` | warn | R-43 | | Most nights of the last seven were short. |
| `status_active` | warn, info | R-43 | | A status day overlaps the span (warn ill/injured, info travel). |
| `niggle_link` | warn | R-43 | | Activity of a kind an active niggle applies to. |
| `conditioning_dropped` | info, warn | R-44b | | An optional conditioning session was dropped from the proposal (info), or a core one would have been (warn). |

## C21. Overlay v2: line provenance (R-24 bumps; R-23a fills; R-21a, R-22, R-25 read)

Overlay `schema_version` 2 adds one nullable object per exercise line
(C10 `sessions[].exercises[]`), also allowed in the R-13 draft schema:

```json
"provenance": {
  "scheme": "double_progression",
  "derived_from": {"date": "2026-10-05", "workout_id": "10000000-0000-4000-8000-000000000003"},
  "inferred": false,
  "decay": {"days_off": 28, "band": "22-42", "load_factor": 0.9, "set_delta": -1, "rpe_cap": null},
  "rationale": "Hit 3×10 at RPE 8: +2.5/hand, reps back to 8."
}
```

- `provenance` null: a hand-built line. The R-24 validator then infers
  `derived_from` (latest exposure of the exercise before the overlay's
  `created_at`); with `prescription check --write` it stores the result
  with `inferred: true`.
- `derived_from` null inside a non-null `provenance`: no exposure (first
  time, start load).
- `decay` null: no decay applied. `band` is one of the C22 band ids.
- `scheme` and `rationale` are filled by R-23a; null in hand-built lines.
- Migration `overlay` 1 → 2 (R-24, through the R-17a runner) adds
  `provenance: null` to every line. It changes the document, so an
  approved overlay loses its approval; the migration's report lists
  them. Already-pushed weeks are unaffected; re-pushing one needs a new
  approval.
- Anyone else needing an overlay field bumps to the next version in its
  own PR (R-22's `fold` marker is v3, C37); nobody edits v2 after R-24
  merges.

## C22. Validity window and return bands (R-24; R-21b, R-23a, R-31 read)

`coach/validity.py` is the only place these numbers live in code. The
prose copy lives once in `CLAUDE.md` "Coaching principles" (R-02); a test
asserts the two agree.

```python
RETURN_BANDS = (   # days_off upper bound inclusive, id, load_factor, set_delta, rpe_cap, retest
    (10,   "0-10",  1.00,  0, None, False),
    (21,   "11-21", 0.95, -1, None, False),
    (42,   "22-42", 0.90, -1, None, False),
    (None, "43+",   0.85, -1, 7,    True),
)
GRACE_DAYS = 10

coach.validity.band_for(days_off) -> Band
coach.validity.interval_days(exposures) -> int     # median of the last ≤4 gaps, clamped 7..14; 7 with <2 gaps
coach.validity.days_off(root, exercise_id, session_date) -> int
#   = max(layoff_days, exposure_age − interval_days)
#   layoff_days  = session_date − last_lifting_date(before=session_date)   (R-02: any lifting workout)
#   exposure_age = session_date − date of the newest non-excluded exposure of the exercise (any slot)
coach.validity.window_ok(...) -> bool               # exposure_age ≤ interval_days + GRACE_DAYS
coach.validity.check_overlay(root, doc) -> list[flag]
coach.validity.estimate_minutes(root, session) -> int
```

- **Valid line**: `days_off` falls in band `0-10`, or the line's
  `provenance.decay.band` equals `band_for(days_off)` and its working
  load is at most the derived-from load × `load_factor` (plus one
  increment for rounding). Anything else is `stale_prescription`.
- Days off are measured to the line's session date. The band's set and
  RPE parts are checked as well as the load.
- Illness (R-02): when an `ill` miss annotation or an `ill` status day
  (C50; `coach.statusdays.ill_in(root, span)`, added by R-43) falls in the
  gap, the first session of the span must cap every set at RPE 7; R-23a
  applies it and raises `return_after_illness`; R-24 checks it.
- **Feasibility** uses C18's `implied_rpe` with the best e1RM point in
  the last 42 days (none older): implied RPE above 10.5 is
  `unearned_load`; an RPE target more than 1 from the implied RPE is
  `rpe_infeasible`.
- **Duration estimate** per session: Σ over sets of (reps × 4 s, or
  `duration_seconds`) + `rest_seconds` between sets, + 60 s per exercise,
  + 300 s warm-up; scaled by the median of actual ÷ estimated minutes over
  the session's last four logged workouts (when two or more exist),
  clamped 0.7 to 1.5. Above the C19 cap is `session_over_cap`.
- **Equipment** comes from `coach.config.equipment_for(config,
  location)` (C54) with the overlay session's `location`.
- **Caps** follow the R-16 `load_caps` rule exactly: `[caps]` id first,
  else `dumbbell_max` per hand for per-hand modes.
- **Representable**: barbell totals have a `units.plate_breakdown`;
  per-hand loads are in `dumbbells` when that list is non-empty (C4;
  empty means not checked, since racks are not regular multiples of one
  increment). Machine and cable loads are not checked.
- `load_mode_mismatch` reuses R-13's `overlay.validate` and R-11's
  `effective_load_mode`; R-24 adds no new arithmetic.

`prescription check (--overlay ID | --file PATH) [--write] [--dry-run]`
returns `data.flags` and per-line `days_off`, `band`, `derived_from`.
`--write` merges its flags into the overlay (replacing earlier R-24 flags,
keeping `resolved` and `resolution` on identical ones) and fills inferred
provenance; it refuses (exit 3) on an approved overlay. Check
`prescription_valid`: overlays in force today or later have no unresolved
R-24 `block` finding (fail).

## C23. Plugin contract (R-23a; R-23b, R-30a, R-31, R-41b, R-43, R-44a, R-44b read)

A plugin is one Python module. Kinds are subpackages of `coach/plugins/`;
each kind's `__init__.py` declares the functions its plugins must define.
Phase 2 kinds: `schemes`, `schedules`, `transforms`. Later kinds:
`interference` (R-44a) and `conditioning` (R-44b), both in C51; each is a
new subpackage.

Module shape:

```python
API = 1
KIND = "scheme"                      # "scheme" | "schedule" | "transform" | "interference" | "conditioning"
NAME = "double_progression"          # equals the file stem
SUMMARY = "One plain sentence."
PARAMS = {"schema": {...}, "defaults": {...}}   # C7 schema subset; defaults merged before validation
STATE = {"schema": {...}, "initial": {...}}     # schemes and conditioning only
FLAGS = {}                           # instance plugins only: {"custom_x": {"severities": ["warn"], "summary": "..."}}
CITES = ()                           # template research claim refs, e.g. ("rn:deloads.3",) (C28)

def propose(ctx: SchemeContext) -> Proposal                          # schemes
def decay(ctx: SchemeContext, proposal: Proposal, days_off: int) -> Proposal   # schemes; may return base.default_decay(...)
def deload(ctx: SchemeContext, proposal: Proposal) -> Proposal       # schemes, optional (used by the `scheme` transform)
def plan(ctx: ScheduleContext) -> SchedulePlan                       # schedules
def apply(ctx: SchemeContext, proposal: Proposal) -> Proposal        # transforms
```

**Purity.** Plugins do no I/O: no `open`, no imports beyond `coach.plugins.base`,
`coach.stats` (e1RM functions), `math`, `dataclasses`, `typing`,
`datetime`. They never build load objects or convert units. An AST test
covers `coach/plugins/**`; `plugins validate` runs the same scanner on
instance plugins, plus the C5 ×2 scan.

**Units.** Every load a plugin sees or returns is the coaching number in
athlete units (C18). The core then applies, in order: decay, the week's
transform, constraints (C26), caps, rounding to increments (down when
the load is below the derived-from load, nearest otherwise), and only
then `units.make_load`. A plugin therefore cannot double a load.

```python
@dataclass(frozen=True)
class SchemeContext:
    today: date; session_date: date; unit: str; week_kind: str   # weekly | midweek | deload
    exercise: ExerciseInfo        # id, pattern, muscles, equipment, load_mode, increment, is_compound,
                                  # load_direction (+1; −1 for assisted)
    slot: SlotInfo                # session_id, set groups, rest_seconds, cues, constraints, start_load
    params: dict                  # validated, defaults filled
    state: dict                   # validated; INITIAL when absent or after a scheme change
    exposures: tuple[Exposure, ...]          # all slots, newest first; suspect/excluded marked
    e1rm: float | None            # best point in 42 days (C18)
    last_prescription: dict | None # this slot's line in the newest approved overlay, ignoring lines
                                   # that carry `fold` (C37; R-22 adds the filter)
    last_override: dict | None    # C25
    days_off: int                 # C22
    constraints: tuple[dict, ...] # active C26 constraints, for information; the core enforces them

@dataclass(frozen=True)
class Proposal:
    sets: tuple[SetSpec, ...]     # type, reps | rep_range, rpe, load (coaching number | None), duration, distance
    rationale: str                # one plain sentence
    derived_from: Exposure | None
    state: dict                   # validated against STATE before it is kept
    flags: tuple[dict, ...]       # coach.flags.make(...)
    target_note: str | None = None
    focus: str | None = None
```

`base.default_decay` applies C22's band: load × `load_factor`, one set
fewer per exercise (never below one), RPE capped for `43+`. A scheme
overrides `decay` only when load is the wrong lever (a ladder steps back
rungs; a wave lowers its training max).

R-23a also exposes its drift rule as `coach.patterns.rpe_drift(sets,
prescribed_sets, capped) -> bool`, so R-31 calls the same function the
`rpe_drift` flag uses.

**Schedules.** `plan(ctx)` returns dated sessions for a span and the
rotation it implies:
`SchedulePlan(sessions=[(date, session_id)], rotation={"position", "confirmed"}, flags=[...])`.
Schedule state is `state.rotation` (C16 shape unchanged); a plugin's
`positions(params)` lists the valid positions. A `SchedulePlan` written as
JSON is what `propose week --plan` reads (C24).

| Rule | Params (example) |
|---|---|
| `fixed_weekdays` | `{"days": {"mon": "session-a", "thu": "session-b"}}` |
| `alternating_external_anchor` | `{"weeks": [{"name": "week-a", "days": {...}}, {"name": "week-b", "days": {...}}], "anchor_external_id": "pt-tue"}`; advances one position a week, unconfirmed until `schedule confirm` |
| `next_in_sequence` | `{"sequence": ["session-a", "session-b", "session-c"], "days": ["mon", "wed", "fri"]}`; continues after the last trained session |
| `explicit_calendar` | `{"dates": {"2026-10-12": "session-a"}}` |

**Transforms** (`blocks.deload_rule` names one; `propose week --transform`
picks one for a run):

| Transform | Owner | Params | Effect |
|---|---|---|---|
| `standard` | R-23a | `set_factor` 0.67, `load_factor` 0.9, `rpe` 6 | bodyweight work cut by sets and taken further from failure |
| `scheme` | R-23a | — | calls the scheme's `deload`, else `standard` |
| `light` | R-31 | `set_factor` 0.67, `load_factor` 1.0, `rpe_cap` 8 | two thirds of the sets (at least one), loads held, no set above RPE 8 |
| `return` | R-31 | `set_delta` −1, `rpe_cap` 8 | one set fewer, load held at the derived-from exposure, no set above RPE 8; a line with `ctx.days_off` over 10 is returned unchanged (the core already decayed it) |

**Evidence.** A plugin's areas are the research areas of the notes its
`CITES` refs resolve to (`coach.research.resolve`, C28). When R-32a is
present, `propose week` calls `coach.research.expired_by_area(root,
today)`; a line whose plugin cites a note in an expired area gets
`evidence_expired` (info, owned by R-32) and its rationale says "evidence
under review (<note> expired <date>)" instead of citing the claim. Nothing
is blocked. An area a current local note covers is not reported as
expired (C28); when `coach.research.local_updates(root, today)` maps a
cited claim to a local note, the rationale may cite that note. `CITES`
holds template claims only, never `rn:local-*` refs. Before R-32a merges,
`CITES` stays empty and the step is skipped.

**Schemes shipped**: `hold`, `linear`, `double_progression`,
`fixed_reps_rpe` (R-23a); `rpe_anchored`, `wave_531`,
`assistance_ladder`, `maintenance` (R-23b); `emom_density`,
`circuit_rounds` (R-44b, kind `conditioning`, C51).

**Instance plugins** live in `plugins/<kind>/<name>.py` (C6 instance
namespace, never synced). Their `NAME` starts `custom_`; a name that
matches a framework plugin is an error, never a silent override. Each
ships `plugins/tests/test_<name>.py`; `plugins validate` fails without it
and `plugins test` runs them. Loaded with
`importlib.util.spec_from_file_location`. Check `plugins_valid` runs
`plugins validate`.

**Program and state v2** (R-23a bumps C16, migration steps through R-17a):

- `program.json` 2: `scheme.name`, `schedule.rule` and
  `blocks.deload_rule.name` are any registered plugin name of the right
  kind (no fixed enum); each `params` is validated against that plugin's
  `PARAMS` by `program validate`; exercise `constraints` items take the
  C26 shape. Migration: names unchanged, `constraints` emptied with a
  report row for any v1 free-form entry.
- `state.json` 2: `scheme_state["<session_id>/<exercise_id>"]` becomes
  `{"scheme": name, "data": {...}, "pending": null | {"overlay_id": id, "data": {...}}}`;
  `data` validated against the scheme's `STATE`. Migration wraps v1
  entries.
- Scheme state advances only through approval: `propose finalize` writes
  `pending`; the next `propose week` promotes `pending` to `data` when
  that overlay is approved with a matching hash, and drops it otherwise.

## C24. Proposal pipeline and `coach propose` (R-23a; R-21b, R-22, R-25, R-26, R-30b, R-31, R-40a, R-41a, R-43, R-44a, R-44b, R-45 read)

```
propose week  ──►  .coach/proposals/<id>.json (+ .proposed.json)  ──►  coach edits / propose override / propose resolve
              ──►  propose finalize  ──►  data/overlays/<id>.json (C10 v2)  ──►  overlay approve (R-13)  ──►  routines push (R-14)
```

`propose week [--week W | --span A..B] [--kind weekly|midweek|deload] [--transform NAME] [--plan FILE] [--dry-run]`:

1. Settle scheme state (C23).
2. Plan dated sessions with the schedule rule (midweek: dates ≥ span
   start only), or read them from `--plan FILE`, a C23 `SchedulePlan`
   JSON file (rotation unchanged). R-23a builds `--plan`; R-30b and R-22
   write such files (`.coach/plans/`, C6).
3. Per exercise line: build `SchemeContext`; `propose`; then decay
   (when `days_off` > 10), the deload transform (kind `deload`: the
   program's `blocks.deload_rule`, or `--transform NAME` for this run),
   constraints, caps, rounding, standing override (C25).
4. Core flags: `no_data`, `stalled`, `rpe_drift`, `convention_slip`,
   `return_week`, `return_after_illness`, `constraint_applied`,
   `override_standing`, `scheme_reset`, `rotation_unconfirmed`.
5. Build through `coach.overlay.build` and run `coach.validity.check_overlay`.
   - 5a. Week-level flags (R-43): every provider in `coach/weekflags/`
     returns flags for the overlay span (C49); they are appended to the
     overlay's `flags`.
   - 5b. Drop rule (R-44b): optional conditioning sessions dropped on the
     C51 triggers; `data.dropped` lists them.
6. Write the draft and an untouched `.proposed.json` copy.

Output: `data.overlay` is the complete C10 overlay (approval null,
flags filled, every line's `provenance` filled), and `data.lines` is a
compact list `{session_id, exercise_id, text, change, rationale, flags}`
with `text` from `units.format_load` for the coach's brief. The overlay
id follows C10.

- `propose override --proposal ID --session S --exercise E (--sets SPEC | --load N) --reason TEXT [--standing [--until D]]`
  changes one line, keeps the original in the line's C10 `override.proposed_sets`,
  and records a C25 decision when standing.
- `propose resolve --proposal ID --flag INDEX --resolution TEXT` resolves
  one flag on the draft.
- `propose restore --proposal ID --session S --reason TEXT` (R-44b) puts
  a dropped conditioning session back and resolves its flag with the
  reason; finalize accepts it.
- `propose finalize --proposal ID [--dry-run]` re-runs step 5. It exits
  1 if any line differs from `.proposed.json` without `override.reason`,
  and exits 3 if a `block` flag is unresolved. Otherwise it writes the
  overlay, decisions and pending scheme state.

A hand edit of the draft is allowed; finalize catches unexplained
changes. One-off weeks (travel, limited kit) stay coach-built through
`overlay build` until R-26 merges the skills.

## C25. Decisions file and `last_override` (R-23a; R-25, R-30a, R-31 read and append)

`data/decisions.json`:

```json
{
  "schema_version": 1,
  "decisions": [
    {"id": "d-0001", "kind": "override", "made_at": "2026-10-11T19:02:00Z",
     "overlay_id": "2026-10-12-weekly",
     "scope": {"session_id": "session-a", "exercise_id": "bb_back_squat"},
     "outcome": "adopted", "reason": "knee settles at 5 reps; hold 100 until the PT clears it",
     "standing": true, "until": "2026-11-08", "revisit_on": null,
     "proposed_sets": [...], "chosen_sets": [...], "details": null,
     "status": "active", "closed_at": null, "closed_reason": null}
  ]
}
```

- `kind`: `override` (R-23a), `adherence_trigger` (R-30a), `light_week`
  (R-31). The enum holds all three from v1 so R-30a and R-31 need no bump.
- `scope`: `{session_id, exercise_id}` for overrides; `{}` for program-wide kinds.
- `outcome`: `adopted`, `declined`, `deferred`. `revisit_on` is the date a
  declined or deferred decision is presented again (R-02).
- `proposed_sets`, `chosen_sets`: overrides only, null otherwise; set
  specs in athlete units as the coach writes them (no load objects).
- `details`: null for `override`; for the other kinds an object validated
  per kind. `adherence_trigger` (R-30a):
  `{"rule": "restructure", "adherence_pct": 58, "weeks": ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"]}`,
  `rule` `restructure` or `add_session`, `weeks` the ordinary weeks used.
  `light_week` (R-31):
  `{"type": "deload", "week": "2026-10-12", "reason": "ceiling", "triggers": [], "hard_weeks": 6}`.
  The field is part of decisions v1.
- `status`: `active`, `expired`, `withdrawn`. Expiry is computed when
  read (`until` passed); `decisions withdraw ID --reason` closes one.
  Records are never deleted.
- **`last_override`** for a slot = the newest `override` decision for
  that scope with effective status `active`, or null. When `standing`,
  the core keeps `chosen_sets` (re-deriving loads only through decay and
  caps), puts the scheme's own proposal in the rationale, and raises
  `override_standing`. A one-week override (not standing) is only
  information to the scheme.
- Standing overrides need an `until` date, default four weeks after
  `made_at`, at most eight.

## C26. Load constraints (R-23a defines and enforces; R-27 adds the niggle source; R-31, R-43, R-44a read)

One shape, used on program exercise slots (`constraints`, C16 v2) and on
niggle rows (C27):

```json
{"kind": "rpe_cap", "value": 7, "reason": "left knee"}
{"kind": "no_added_load", "value": null, "reason": "lower back"}
{"kind": "load_cap", "value": 20, "reason": "elbow"}
```

- `rpe_cap`: every working set's RPE target at most `value`. This is the
  glossary's **recovery cap** (R-05); `rpe_drift` scope includes these sets.
- `no_added_load`: working load at most the newest non-excluded
  exposure's load (no progression in load; reps may still progress).
- `load_cap`: working load at most `value` (coaching number, athlete units).
- On a slot, a constraint applies to that line. On a niggle, it applies
  to every line whose exercise matches `applies_to` (C27).
- The core clips the proposal and raises `constraint_applied` naming the
  source (`slot`, `cap`, or the niggle id). It never removes or swaps an
  exercise; swaps are the coach's call.
- "Constraint" here means a load limit on an exercise. Session placement
  rules are **interference rules** (C51), a separate plugin kind.

`coach.constraints.active(root, session_id, exercise_id, on_date) -> list[dict]`
is the single function R-23a's pipeline, R-31's niggle trigger and R-43's
`niggle_link` call.

## C27. Follow-ups and niggles (R-27; R-21a, R-25, R-31, R-40a, R-43 read)

`data/followups.json`:

```json
{
  "schema_version": 1,
  "items": [
    {"id": "f-0001", "raised": "2026-10-11", "source": "check-in 2026-10-11",
     "text": "Re-test the pull-up ladder once the elbow settles.",
     "review_at": "2026-11-08", "status": "open",
     "events": [{"date": "2026-10-11", "action": "raised", "note": null}]}
  ]
}
```

- `status`: `open`, `resolved`, `dropped`. `events[].action`: `raised`,
  `deferred`, `resolved`, `dropped`, `kept` (reviewed, still open, new
  `review_at`).
- `followups list [--open] [--due]`; due = open with `review_at` ≤ today.
  A due item raises `followup_due` (info) in `propose week` and the R-21a card.
- **Deep check-in must resolve each.** `followups render --deep --date D`
  prints the deep record's follow-up section and exits 1 while any item
  open before D has no event dated D. Each needs one of resolve, drop
  (with reason), or defer/keep (with a new `review_at`).

`data/niggles.json`:

```json
{
  "schema_version": 1,
  "niggles": [
    {"id": "n-0001", "area": "left knee", "first_noted": "2026-09-14", "last_noted": "2026-10-11",
     "mentions": 3, "status": "watching", "notes": "deep flexion under load",
     "applies_to": {"patterns": ["squat", "lunge"], "exercises": [], "activity_kinds": ["run"]},
     "constraints": [{"kind": "rpe_cap", "value": 7, "reason": "left knee"}],
     "constrain_while": ["aggravated", "watching"],
     "history": [{"date": "2026-10-11", "status": "watching", "note": "quiet on squats at RPE 7"}]}
  ]
}
```

- `status`: `aggravated`, `watching`, `easing`, `resolved`, `chronic`.
  Rows are never deleted (recurrence is the signal).
- `chronic` is a lasting limitation (e.g. no overhead pressing). Its
  constraints are always active whatever `constrain_while` says; it never
  raises `niggle_escalate`; the deep check-in lists it but does not ask
  for a resolution.
- `applies_to.patterns` use the R-11 pattern enum; `exercises` are
  library ids; `activity_kinds` use the C30 activity kind enum (R-43 reads
  it for `niggle_link`; `niggles add|update` take `--activity-kinds`).
  Constraints are active while `status` is in `constrain_while` (default
  `["aggravated", "watching"]`).
- `niggle_escalate` (warn) when the last three check-in entries in
  `history` are all `aggravated` or `watching`, or the status moved to
  `aggravated` from a better one.
- R-31 reads `aggravated` as its "niggle under load" fatigue trigger.
- `niggles import --from-profile [--dry-run]` parses the template's
  `### Niggle log` table (`Area · First noted · Last noted · Mentions ·
  Status · Notes`) into rows with no constraints, for the coach to add.
  An "Injuries / limitations" line the coach marks as permanent maps to
  `chronic`.
- R-27 builds `activity_kinds` and `chronic` into niggles v1. If R-27 has
  merged without `activity_kinds`, R-43 adds it with a schema bump (an
  empty list on every row).

## C28. Research notes and claim ids (R-32a owns; R-32b, R-32c, R-23a, R-46 read)

A research note answers one coaching question with dated, sourced,
numbered claims. Shipped schemes, flag thresholds, skills and the coaching
principles cite claims by id instead of citing sources inline. The coach
also writes notes in an instance whenever it researches something.

**Two kinds.**

| Kind | Path | Id | Git | Data block written by |
|---|---|---|---|---|
| template | `research/<id>.md` | `^[a-z0-9]+(-[a-z0-9]+)*$`, not starting `local-` | framework: tracked in the template, synced; refreshed in the template | the PR author |
| local | `research/local/<id>.md` | `^local-[a-z0-9]+(-[a-z0-9]+)*$` | instance namespace (C6); sync never writes it | the coach, with the Write tool |

`id` equals the file stem. A local note never edits or replaces a template
note.

**File layout.** The file starts with a hidden data block (C11) of kind
`note`, then the rendered region, then prose:

```
<!-- coach:note
schema_version = 1
id = "deloads"
topic = "Deloads"
question = "When should a lifter take a lighter week, and what should it contain?"
written = 2026-10-20            # date of the last full review
review_by = 2028-04-20          # written + 18 months; + 12 for low confidence; max + 24
confidence = "moderate"         # high | moderate | low
applies_to = ["deload", "autoregulation"]
tags = []                       # optional, free-form
updates = []                    # local notes only: template claim refs this note supersedes here

[[sources]]
id = "bell-2023"
citation = "Bell L, et al. Integrating deloading into strength and physique sports training programmes: an international Delphi consensus approach. Sports Med Open. 2023;9:87."
url = "https://doi.org/10.1186/s40798-023-00633-0"
type = "consensus"
year = 2023

[[claims]]
n = 1
text = "Deloads are better triggered by fatigue signals than fixed on the calendar."
basis = "consensus"             # evidence | consensus | heuristic
sources = ["bell-2023"]
status = "current"              # current | retired
-->
<!-- coach:begin research deloads -->
(status line, claims table, sources table)
<!-- coach:end research deloads -->

## Answer
...
```

- The block is read only through `coach.datablock.read(path, "note")`
  (C11). Scripts never write it (ADR-0001).
- The rendered region follows C11 (`<!-- coach:begin research <id> -->`
  ... `<!-- coach:end research <id> -->`). `research render` writes only
  this region. Freshness: the region equals `render_research(id)`.
- Source keys: `id` (`^[a-z0-9-]+$`, unique in the note), `citation`,
  `url` (https; a DOI URL when one exists), `type`, `year`; optional
  `accessed` (date, for `educator` pages). `type`: `meta-analysis`,
  `systematic-review`, `rct`, `observational`, `consensus`,
  `position-stand`, `narrative-review`, `preprint`, `educator`.
- Claim keys: `n` (positive integer, unique, never reused), `text` (one
  sentence; numbers in it are the numbers the code uses), `basis`,
  `sources` (source ids in this note; non-empty unless `basis` is
  `heuristic`), `status`; optional `confidence` when the claim is weaker
  than the note (e.g. it rests on a preprint), which `research show` and
  the rendered claims table display; for retired claims `retired_on`
  (date) and optional `superseded_by` (a claim ref).
- `confidence`: `high` when several meta-analyses agree; `moderate` for one
  meta-analysis or consistent trials; `low` for few or indirect trials,
  expert opinion alone, or a claim resting on a preprint not yet peer
  reviewed.
- `applies_to` areas: `volume`, `frequency`, `proximity_to_failure`,
  `progression`, `deload`, `autoregulation`, `concurrent_training`,
  `return_to_training`, `minimum_dose`, `bodyweight_skills`, `protein`,
  `energy_balance`, `sleep`, `rehab`, `exercise_selection`. Adding an area
  is a schema change. Template notes need at least one area. A local note
  may have none if it has at least one tag.
- `tags`: optional on both kinds; each matches `^[a-z0-9]+(-[a-z0-9]+)*$`;
  no fixed list.
- `updates`: local notes only. Each entry is a template claim ref.
- **Rehab disclaimer.** A note whose `applies_to` includes `rehab` has, in
  its body, the exact line
  `This note does not replace assessment by a qualified professional.`
- The prose has `## Answer` (three sentences at most), `## Evidence`
  (discussion keyed to claim numbers), `## Applying it`, `## Open
  questions`. Nothing parses the prose.
- Validation: the block, with dates as ISO strings, passes
  `coach/schemas/research_note.schema.json`; `written <= review_by <=
  written + 24 months`; claim and source ids unique; every claim source id
  exists in the note; id rules by kind; the rehab line when required; a
  retired claim has `retired_on`, and a current claim has neither
  `retired_on` nor `superseded_by`; every `updates` entry names a
  template claim. `applies_to`, `tags`, `updates` and `sources` may be
  left out and default to empty. A local note whose `updates` names a
  claim that is missing or retired is valid but warns.

**Claim reference.** `rn:<note-id>.<n>`, matched by
`\brn:([a-z0-9]+(?:-[a-z0-9]+)*)\.([0-9]+)\b`. Prose writes it in brackets
after the statement it supports: "default ceiling 6 completed hard weeks
(rn:deloads.3)". Python carries it in a string, typically a module or
plugin constant `CITES = ("rn:deloads.3",)`; never in a comment. A
reference **resolves** when its note exists and has a claim with that `n`
and `status = "current"`.

**Citation scan.** Two sets of globs, from the root, defined once in
`paths.py`:

| Scope | Globs | May cite | Missing | Retired | `rn:local-*` |
|---|---|---|---|---|---|
| framework | `CLAUDE.md`, `README.md`, `config.example.toml`, `.claude/skills/**/*.md`, `reference/**/*.md`, `research/*.md`, `coach/**/*.py`, `coach/**/*.json` | template claims | fail | fail | fail |
| instance | `profile.md`, `check-ins/**/*.md`, `data/**/*.json`, `data/**/*.jsonl`, `research/local/*.md`, `plugins/**/*.py` | template and local claims | warn | warn; pass under `check-ins/**` | allowed |

**Note status** on date D: `expired` when `review_by < D`; `due_soon` when
`review_by - 60 days <= D`; otherwise `current`. A template claim listed
in the `updates` of a current local note is `superseded_locally`. In this
rule and the area rule below, a *current* local note is one whose status
is `current` or `due_soon`: a local note supersedes and covers until it
expires.

**Area status.** An area is `expired` when a template or local note
covering it is expired and no current local note covers it, either by
listing the area in `applies_to` or by `updates` naming a claim of the
expired note. Otherwise the worst of `current` and `due_soon` among its
notes.

**`research status`** `data`:

```json
{"today": "2026-10-11",
 "notes": [{"id": "deloads", "kind": "template", "topic": "Deloads", "path": "research/deloads.md",
            "written": "2026-10-20", "review_by": "2028-04-20",
            "status": "current", "days_to_review": 557, "confidence": "moderate",
            "applies_to": ["deload", "autoregulation"], "tags": [],
            "claims": 6, "retired_claims": 0, "cited_by": 4, "updates": []}],
 "superseded_locally": [{"ref": "rn:deloads.3", "by": "local-deload-timing"}],
 "areas": {"deload": "current", "autoregulation": "current"},
 "summary": {"current": 10, "due_soon": 0, "expired": 1}}
```

`--area`, `--kind` and `--expired` filter `notes`; `summary` and `areas`
always cover every note. `claims` counts current claims; `cited_by` counts
the files, other than the note itself, that cite any of its claims. Exit
0; exit 1 only if a note fails validation.

**`research show REF`**: REF is a note id (data block, status, path) or a
claim ref (claim, its sources in full, its note's status, and the local
note superseding it, if any). Unknown REF exits 1.

**`research cites [--unresolved]`**: every reference found by the scan as
`{ref, path, line, scope, resolved, retired}`.

**`research validate`**: `{valid, notes: [{id, kind, path}]}`; exit 1 with
one detail per problem when any note is invalid.

**Checks** (`coach/checks/research.py`; all four `skip` when there is no
`research/` directory): `research_notes` (fail per invalid note, warn per
`updates` entry that no longer resolves), `research_citations` (the
citation scan table above; a ref into a note that fails validation is left
to `research_notes`), `research_render_fresh` (fail per valid note whose
region is missing, malformed or stale), `research_expiry` (warn per
`expired` area).

**`research render [ID] [--dry-run]`**: renders one note's region, or all
notes' regions with no ID. Writes nothing else. A note with no region
gets one inserted directly after the data block. `data`: `{dry_run,
notes: [{id, path, changed}]}`. The region holds no date-dependent text
(the status line names kind, dates, confidence, areas, tags and
`updates`, not `current` or `expired`), so it goes stale only when the
data block changes.

**Python interface** (`coach/research.py`):

- `load_notes(root) -> list[Note]` (both kinds; raises on invalid notes,
  exit 1)
- `resolve(ref, notes) -> Claim | None` (None when missing or retired)
- `note_status(note, today) -> "current" | "due_soon" | "expired"`
- `expired_by_area(root, today) -> dict[str, list[str]]`: each `expired`
  area (area status above) to the ids of the expired notes no current
  local note covers; other areas are absent.
- `local_updates(root, today) -> dict[str, str]`: template claim ref to the
  id of the current local note superseding it.
- Both read only the notes that pass validation, so one broken note never
  stops a proposal; `coach check` reports the broken one.
- `scan_citations(root) -> list[Citation]`
- `render_research(root, id) -> str` (C11; the region with its markers
  and no trailing newline). It takes the root like every other function
  here, because the note's path depends on it.

**Proposals and expired notes (for R-23a).** A proposal decision is
evidence-backed only when every claim it cites resolves and its area is
not `expired`. Otherwise the rationale says "evidence under review
(<note id> expired <review_by>)" instead of citing the claim, and the
line carries an `info` flag `evidence_expired`. Nothing is blocked. A
plugin declares its claims as `CITES = ("rn:deloads.3",)`; its areas are
the areas of the notes those refs resolve to (C23 "Evidence"). When
`local_updates` maps a cited claim to a local note, the rationale may cite
the local note. `evidence_expired` is listed in the C20 table with owner
R-32 and is registered in `coach/flags/research.py`.

## C29. Activity-source files (R-42a owns; R-31, R-42b, R-42d, R-43, R-44b, R-46 read or write)

| Path | What | Git | Written by |
|---|---|---|---|
| `data/activity/activities.jsonl` | activity records, append-only | committed | R-42a, adapters |
| `data/activity/planned.jsonl` | planned-activity records, append-only | committed | R-42a (manual), R-42d (Runna), R-46 (coach) |
| `data/activity/wellness.jsonl` | wellness records, when `[activity] wellness_in_git = true` | committed | R-42a, adapters |
| `.coach/activity/wellness.jsonl` | wellness records, when `wellness_in_git = false` (the default) | **gitignored** | R-42a, adapters |
| `data/activity/sync.json` | per-source sync map (C31) | committed | R-42a |

- Every line is one record with `schema_version` (C7). Lines are only ever
  appended. For each `id`, the last line wins. `op` is `upsert` or `void`;
  a `void` line carries `id`, `source`, `recorded_at` and a non-empty
  `reason`, and removes the record from every view.
- `id` is `<source>:<source-specific id>`, pattern
  `^[a-z_]+:[A-Za-z0-9._:-]+$`. Source names match the `[sources.<name>]`
  tables (C32) plus `manual` and, for planned activities, `coach`. Manual
  ids are deterministic: `manual:<local_date>-<kind>-<n>`.
- `recorded_at` is when the line was written (UTC). `content_hash` is the
  canonical hash (C7) of the record without `op`, `recorded_at` and
  `content_hash`. A sync appends only when it differs from the last line
  for that id.
- Dedup and precedence are a read-time view, never a rewrite: records of
  the same kind whose starts lie within `dedup_window_minutes` form one
  Activity; the highest-precedence source (C32) supplies each field, and
  lower ones fill fields it lacks. Wellness resolves per day and per field
  by the same precedence; a span record fills only days with no daily
  value.
- Readers never parse the files themselves. They use
  `coach.activity.store.ActivityStore(root, config)`:
  - `activities(span, kinds=None) -> list[dict]`: resolved Activities
    (C30), deduplicated, sorted by `start`.
  - `planned(span, kinds=None) -> list[dict]`: resolved planned activities.
  - `wellness_days(span) -> list[dict]`: one resolved day per date in the
    span that has any value.
  - `sleep_summary(span) -> {"avg_asleep_hours": float|null, "nights": int,
    "nights_in_span": int, "sources": [str]}`, averaged over nights with a
    value (a span record counts once per covered day without a daily value).
  - `records(kind, include_void=False)`: raw lines, for audits and tests.
- Readers: R-43 (activities, planned, wellness for `sleep_debt`), R-44b
  (conditioning Activities), R-46 (writes planned records with `source:
  "coach"`; reads run history), R-31 (`sleep_summary` through R-43's
  `sleep_debt`), R-21a and R-45 (`activity sync` and `activity status` for
  the card's runs and sleep lines).
- With `[activity] enabled = false`, the activity, wellness and planned
  commands exit 5 naming the key, and activity checks report `skip`.

## C30. Activity record schemas (R-42a owns; R-43, R-44b read)

Activity record (`coach/schemas/activity_record.schema.json`):

```json
{"schema_version": 1, "op": "upsert", "id": "apple_health:9F1C...", "source": "apple_health",
 "source_id": "9F1C...", "recorded_at": "2026-10-09T07:10:00Z",
 "kind": "run", "name": "Outdoor Run", "indoor": false,
 "start": "2026-10-09T05:30:00Z", "end": "2026-10-09T06:02:00Z", "utc_offset": "+01:00",
 "local_date": "2026-10-09", "duration_seconds": 1920, "distance_meters": 5000,
 "elevation_gain_meters": 31, "avg_hr": 148, "max_hr": 171, "active_kcal": 390,
 "rpe": null, "device": "Garmin Connect", "notes": null,
 "content_hash": "sha256:..."}
```

- Required: `schema_version`, `op`, `id`, `source`, `recorded_at`, `kind`,
  `start`, `local_date`, `duration_seconds`, `content_hash`. Every other
  field is nullable.
- `kind`: `run`, `ride`, `swim`, `row`, `walk`, `hike`, `conditioning`,
  `sport`, `mobility`, `other`. A source workout that maps to lifting is
  dropped at normalise with a counted reason (Hevy is the lifting logbook).
- `rpe` is session RPE (0–10) as the athlete gave it; nothing here estimates
  it (R-43 does, and labels the method).
- `local_date` uses `utc_offset`, else `[athlete] timezone`, so travel
  days land correctly. Distances are metres, durations seconds, mass kg;
  distance conversions live in `coach/units.py`.

Resolved Activity (returned by `activities()`; not stored): the activity
fields plus `"id"` of the winning record, `"merged_from": [ids]` (all
records in the group, winner first) and `"field_sources": {field: source}`
for every non-null field.

Wellness record (`wellness_record.schema.json`):

```json
{"schema_version": 1, "op": "upsert", "id": "apple_health:2026-10-09", "source": "apple_health",
 "recorded_at": "2026-10-09T07:10:00Z",
 "span": {"start": "2026-10-09", "end": "2026-10-09"},
 "sleep": {"asleep_hours": 6.8, "in_bed_hours": 7.4,
           "start": "2026-10-08T22:31:00Z", "end": "2026-10-09T05:55:00Z"},
 "resting_hr_bpm": 52, "hrv_ms": null, "steps": 9120,
 "body_mass_kg": null, "body_fat_pct": null, "device": "Garmin Connect",
 "content_hash": "sha256:..."}
```

- A device record covers one day (`span.start == span.end`), and the day is
  the date the athlete woke. A manual record may cover a span (the Sunday
  message's "average hours a night").
- `sleep` is null or an object whose fields are each nullable. Sleep hours
  are asleep time, not time in bed (both stored).
- `body_mass_kg` and `body_fat_pct` are raw readings. While a nutrition
  app is enabled, no reader derives a weight trend from them.
- No HRV, sleep stages or readiness score are computed or flagged
  (ADR-0003); `hrv_ms` stays nullable so a future source fits without a
  bump.

Resolved wellness day: `{"date", "sleep", "resting_hr_bpm", "hrv_ms",
"steps", "body_mass_kg", "body_fat_pct", "field_sources": {field: source}}`.

Planned-activity record (`planned_record.schema.json`):

```json
{"schema_version": 1, "op": "upsert", "id": "runna:20261014-easy", "source": "runna",
 "recorded_at": "2026-10-11T18:00:00Z",
 "date": "2026-10-14", "kind": "run", "title": "Easy 5 km", "quality": false,
 "target": {"distance_meters": 5000, "duration_seconds": null, "description": "Zone 2"},
 "notes": null, "content_hash": "sha256:..."}
```

- A planned activity is a dated activity the athlete or a plan intends.
  `quality` is true for intervals, tempo, threshold, hills and races (R-43
  counts them, R-44a schedules around them).
- Planned activities are not deduplicated across sources; two sources
  planning the same day is the athlete's conflict to see, and `planned()`
  returns both.

## C31. Adapters and the sync map (R-42a owns; R-42b, R-42d add adapters)

```python
# coach/activity/adapters/<name>.py, discovered with pkgutil.iter_modules
NAME = "apple_health"            # matches [sources.<NAME>], or "manual"
KINDS = ("activity", "wellness") # which files it writes: activity | wellness | planned
NETWORK = False                  # True only for adapters that fetch over HTTP

def fetch(ctx, sync_state: dict) -> FetchResult: ...
    # reads the source; never writes. FetchResult(items, sync_state, warnings)
def normalise(item, ctx) -> list[dict]: ...
    # pure: one raw item -> zero or more C30 records (without content_hash/recorded_at).
    # Drops are returned as warnings with a reason, never silently.
```

- `activity sync` runs every enabled adapter: `fetch`, `normalise`, hash,
  append changed records, then write the adapter's returned `sync_state`
  into the sync map. One adapter failing reports a warning and leaves the
  others' results and its own previous sync state untouched. It writes
  local files only; it never stages or commits.
- `data/activity/sync.json`:

```json
{"schema_version": 1,
 "sources": {
   "hevy_conditioning": {"last_sync_at": "2026-10-11T18:00:00Z", "state": {"seen_workout_ids": ["..."]}},
   "apple_health": {"last_sync_at": "2026-10-11T18:00:00Z",
                    "state": {"files": {"HealthAutoExport-2026-10-10.json": "sha256:..."}}}
 }}
```

  `state` is the adapter's own object; nothing else reads it. The file
  holds file names, hashes and cursors, no health values.
- Gaps are reported, not filled: `activity status` lists, per enabled source,
  `last_sync_at`, record counts, the newest dated record, and the days in the
  last 14 with no wellness record from that source.
- **`hevy_conditioning` adapter** (R-42a). It reads the C8 cache only and
  never calls the API; `activity sync` warns when the cache is older than
  `[hevy] cache_max_age_hours`. A Hevy workout is an Activity when every
  exercise resolves to a library entry with `pattern: conditioning` (or,
  for unmatched templates, Hevy's primary muscle group `cardio`), or when
  its `routine_id` maps (`state.hevy.routines`) to a session of `kind:
  conditioning`, whatever its exercise patterns. Kind comes from a small
  table keyed by library id (running and treadmill to `run`, bike to
  `ride`, rower to `row`), default `conditioning`. Duration is the
  workout's end minus start; distance is the sum of set `distance_meters`;
  `rpe` is parsed from `RPE n` in the workout description (first match,
  0–10, halves allowed). A workout that disappears from the cache gets a
  `void` line ("deleted in Hevy"). R-42a builds the routine rule and the
  `RPE n` parsing; R-44b adds them if R-42a has not.

## C32. Activity config (R-42a defines; each adapter adds its source table)

```toml
[activity]
enabled = false
wellness_in_git = false        # false: wellness lives in .coach/activity/ (gitignored)
dedup_window_minutes = 15      # starts this close, same kind = one Activity
precedence = ["manual", "apple_health", "hevy_conditioning"]
gap_warn_days = 3              # coach check warns when an enabled source's newest day is older

[sources.hevy_conditioning]
enabled = true                 # also needs [hevy] enabled

[sources.apple_health]         # R-42b
enabled = false
path = ""                      # folder Health Auto Export writes to
drop_source_names = ["Hevy"]   # workouts these apps wrote to Apple Health are dropped

[sources.runna]                # R-42d; the feed URL is a secret: RUNNA_CALENDAR_URL in .env
enabled = false
```

- `precedence` must list every enabled source plus `manual`, each once;
  otherwise `config validate` exits 5 naming the key.
- `manual` is always available and has no table.
- Each later adapter adds its own `[sources.<name>]` table in its PR.
- Moving the wellness file when `wellness_in_git` flips is a manual step:
  the check fails and names the exact `mv` (and `git rm --cached` when
  moving out of git).

## C33. Recipe card (R-33b owns; R-33c reads)

`nutrition/menu/<slug>.md`. The slug (`^[a-z0-9-]+$`) is the identity. The
file starts with a hidden data block (C11) of kind `card`:

```
<!-- coach:card
schema_version = 1
title = "Chicken + rice bowl"
slots = ["lunch"]                # breakfast | lunch | dinner | snack (config slots)
servings = 1                     # portions the ingredient quantities make
prep = "assemble"                # assemble | quick-cook | cook | eat-out
time_min = 5
status = "active"                # active | benched
nutrition = "estimated"          # estimated | published
source = "https://..."           # optional
tags = ["post-workout"]          # meal-kit cards: "meal-kit" plus a provider tag

[per_serving]
kcal = 610
protein_g = 50
carbs_g = 55
fat_g = 18

[[ingredients]]                  # absent for prep = "eat-out"
qty = 170
unit = "g"                       # g | ml | each | tsp | tbsp
item = "chicken breast, cooked"  # lowercase; the shopping-list key with unit
aisle = "meat-fish"              # one of [nutrition.bank] aisles

[[variations]]
name = "light"
label = "half the rice pouch"
changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]
delta = {kcal = -105, protein_g = 0, carbs_g = -22, fat_g = 0}
-->
<!-- coach:begin card chicken-rice-bowl -->
# Chicken + rice bowl
(stats table, Ingredients, Variations: rendered)
<!-- coach:end card chicken-rice-bowl -->

## Method
1. ...
```

- Scripts never rewrite the block. `recipes draft` and `recipes import`
  print it as text; the coach writes it. The exception is
  `recipes convert --apply`, which writes it once, with a backup.
- A `change` with a negative `qty` reduces or removes an existing
  ingredient. A change naming a new item adds it and must carry `aisle`.
  Two variations that change the same item cannot stack.
- Checks: `recipe_cards` (schema, macro sum, density per slot,
  variations), `recipe_render_fresh`, `recipe_index_fresh`.

## C34. Meal plan (R-33c owns; R-25 and R-45 read)

The coach writes a draft, the exceptions to the standing template plus its
picks for open slots:

```json
{"span": {"start": "2026-10-12", "end": "2026-10-18"},
 "exceptions": [
   {"date": "2026-10-14", "slot": "dinner", "entry": {"cover": "out", "kcal": 900, "protein_g": 40}, "note": "birthday"},
   {"date": "2026-10-16", "office": false}],
 "assignments": [
   {"date": "2026-10-12", "slot": "lunch",
    "entry": {"recipe": "chicken-rice-bowl", "variations": ["light"], "covered_by": null, "lock": "post-run, must be quick"}}],
 "use_up": [{"item": "spinach", "qty": 100, "unit": "g"}],
 "notes": "Batch the chilli on Sunday."}
```

`meals build` resolves it into `data/nutrition/plans/<id>.json`:

```json
{
  "schema_version": 1,
  "id": "2026-10-12",
  "span": {"start": "2026-10-12", "end": "2026-10-18"},
  "created_at": "2026-10-11T19:00:00Z",
  "style": "loose",
  "targets": {"kcal": 2400, "kcal_source": "reading 2026-10-11", "protein_floor_g": 110},
  "input": {"exceptions": [], "assignments": [], "use_up": [], "notes": null},
  "days": [
    {"date": "2026-10-12", "office": false,
     "items": [{"slot": "breakfast", "source": "template", "recipe": "overnight-oats",
                "variations": [], "covered_by": null, "cover": null, "lock": null,
                "kcal": 450, "protein_g": 30}],
     "totals": {"kcal": 2310, "protein_g": 128}}
  ],
  "pool": [{"recipe": "chicken-rice-bowl", "variations": ["light"], "count": 2, "covered_by": null}],
  "shopping": {
    "buy": [{"aisle": "meat-fish", "item": "chicken breast, cooked", "qty": 340, "unit": "g", "for": ["chicken-rice-bowl"]}],
    "check": [{"item": "eggs", "qty": 6, "unit": "each"}],
    "used_up": [{"item": "spinach", "qty": 100, "unit": "g"}]
  },
  "flags": [{"code": "protein_below_floor", "severity": "warn", "date": "2026-10-14",
             "message": "...", "resolved": false, "resolution": null}],
  "approval": null
}
```

- A meal entry is `{recipe, variations, covered_by, lock}`, or
  `{cover, kcal, protein_g}`, or `{"skip": true}`. Item `source` is
  `template`, `exception`, `assignment` or `anchor`.
- `days[].totals` equal the sum of their items; the validator recomputes
  and requires equality. Items snapshot macros at build time.
- `shopping` covers items with a `recipe` and no `covered_by`; batches per
  (recipe, variation set) = ceil(count ÷ servings).
- Flag codes: `protein_below_floor`, `kcal_off_target`, `slot_open`,
  `recipe_unknown`, `variation_unknown`, `variation_conflict`,
  `recipe_benched`, `use_up_unmatched`, `units_mixed`, `no_target`.
  Severities as in C10. `meals approve` refuses unresolved `block` flags.
- `approval` is as in C10. `meals shopping --format issue` refuses an
  unapproved plan (exit 3).
- Rendered to `nutrition/plans/<id>.md` (C11 header). Check:
  `meal_plans` (schema, arithmetic), `meal_plan_render_fresh`,
  `nutrition_template` (template and anchors name existing, active cards).

## C35. Nutrition readings series (R-33a owns; R-21a, R-25, R-33c read)

`data/nutrition/readings.json`, one entry per check-in, sorted by date,
dates unique:

```json
{
  "schema_version": 1,
  "readings": [
    {"date": "2026-10-11", "source": "app",
     "window": {"start": "2026-10-05", "end": "2026-10-11"},
     "weight_unit": "kg", "trend_weight": 82.4, "scale_weight": null,
     "expenditure_kcal": 2650, "target_kcal": 2400, "target_protein_g": 110,
     "avg_kcal": 2380, "avg_protein_g": 112, "days_logged": 6,
     "anchors_most_days": true, "note": null}
  ]
}
```

- `source`: `app` (read off the nutrition app), `scale` (no app: the mean
  of the week's morning weigh-ins), `seeded` (imported once from archived
  check-in prose; the one sanctioned history not taken from an API).
- Every field after `weight_unit` may be null. At least one of
  `trend_weight`, `scale_weight` or `avg_protein_g` is set. `window` is
  optional.
- Written only by `nutrition record` and `nutrition import`. Nothing
  computes expenditure or a calorie target; those fields are the app's
  numbers.
- `nutrition status` flags: `protein_floor_raise`, `override_expired`,
  `override_renewed_twice`, `app_protein_mismatch`, `logging_incomplete`,
  `no_recent_reading`. It returns `data.brief_line` and `data.questions`;
  R-25 and R-21a print them when nutrition is enabled (a soft dependency:
  absent or `{"enabled": false}` means nothing is printed).
- Checks: `nutrition_readings` (schema), `nutrition_override` (warn when
  expired or renewed twice).
- Readers: R-25 reads C4 `phase` and may read C35 weights for
  `progress.md`'s bodyweight trend; R-40a reads `[nutrition] enabled` and
  writes the table at setup; R-45 reads the card's nutrition question and
  whether a template exists.

## C36. Check-in records, the card, catch-up mode (R-21a, R-21b; R-25, R-26, R-30a, R-31, R-33a, R-42a, R-43, R-45 read)

The card is the scripted Sunday message: the week as data, then the
questions the data cannot answer, numbered so the athlete answers in one
reply.

**Records.** A check-in record is `check-ins/YYYY-MM-DD.md` whose first line
is `# Check-in — YYYY-MM-DD (<tier>)`, tier `weekly`, `deep` or `catch-up`.
A record with no tier marker counts as deep (the current skill's rule).
Other markdown files in `check-ins/` are ignored.

```python
coach.checkin.records(root) -> list[Record]        # Record(date, tier, path), oldest first
coach.checkin.due(root, today) -> Due
# Due(last: Record | None, days_since: int | None, due_date: date | None,
#     overdue_days: int, mode: "first" | "weekly" | "deep" | "catch_up", tier_reasons: list[str])
CATCH_UP_AFTER_DAYS = 10    # R-02's first return band ends at 10 days
```

- **Window**: day after the last record's date to today (`--until` sets
  the end). No record: from the program's first overlay span start.
- **Mode**: `catch_up` when `days_since > CATCH_UP_AFTER_DAYS` (R-21b; until
  it merges, R-21a reports `weekly` with a `catch_up_pending` warning).
  Otherwise `deep` when there is no record, the last deep record is 42 or
  more days old, a card part adds a reason, or `--tier deep`; else
  `weekly`. A catch-up never runs deep; it sets `deep_deferred: true`, and
  the next non-catch-up check-in is deep with reason "deferred from
  catch-up <date>" when a deep was due.
- `due_date` = last record date + `[checkin] cadence_days`.

**Card document** (`checkin prepare` → `data.card`; `data.text` is the
markdown from `coach.checkin.render_card(card)`). It reads history with
`include_unsynced=True` (C17):

```json
{
  "schema_version": 1,
  "date": "2026-10-11",
  "window": {"start": "2026-10-05", "end": "2026-10-11"},
  "mode": "weekly", "tier_reasons": [], "deep_deferred": false,
  "days_since_last": 7, "unsynced": 0,
  "sessions": {
    "planned_core": 3, "trained_core": 2, "optional_trained": 0,
    "rows": [{"date": "2026-10-05", "session_id": "session-a", "title": "Session A", "tier": "core",
              "status": "trained", "moved": false, "unlogged": false, "tag": null,
              "workout_id": "…", "minutes": 58, "cap_minutes": 45}],
    "external": [{"date": "2026-10-06", "external_id": "pt-tue", "title": "PT", "done": null, "note": null}],
    "extra": []
  },
  "exercises": [{"date": "2026-10-05", "session_id": "session-a", "exercise_id": "bb_back_squat",
                 "prescribed": "3×5 @ 97.5 @ RPE 7.5", "logged": "5, 5, 5 @ 97.5 @ RPE 7.5",
                 "status": "hit", "rpe_delta": 0}],
  "e1rm": [{"exercise_id": "bb_back_squat", "date": "2026-10-05", "e1rm": 121.88, "delta": 1.54, "method": "epley_rir"}],
  "hevy": [{"routine_id": "…0002", "title": "Session B", "state": "edited_in_app",
            "changes": [{"class": "structural", "path": "…", "before": null, "after": "…"}]}],
  "flags": [],
  "fields": [{"id": "sessions", "n": 1, "prefill": "…", "ask": "…"}],
  "misses": null,
  "catch_up": null
}
```

- `sessions`: C18 adherence over the window (span form), the overlay in
  force per date. `planned_core` counts core sessions; optional sessions
  appear only when trained and are never a miss. `external` lists
  `program.external_sessions` dates in the window with any `external`
  annotation. Durations and caps from C18/C19.
- `exercises`: one row per prescribed exercise of a trained session.
  `prescribed` and `logged` text use `units.format_load`; status and
  `rpe_delta` from C18.
- `e1rm`: exercises with a C18 point in the window; `delta` = C18 `delta`.
  Compounds first (`coach.patterns.is_compound` once R-23a exists; library
  order before), at most eight rows.
- `hevy`: per routine of an active session (`state.hevy.routines`),
  comparing the cache with the newest approved overlay holding that session
  through R-14's `coach.routines.diff`, offline. `edited_in_app`: a
  `structural` change and a cached `updated_at` after the routine's last
  C9 `verify` line; becomes a keep-or-replace question (R-03).
  `not_written`: no `verify: true` line for this routine and that overlay;
  raises `stale_routine`. Load-only edits are listed as a fact, not asked
  (R-03 overwrites them). Skipped when `[hevy] enabled` is false.
- `flags`: C20 objects for the window: `convention_slip` (open audit
  candidates), `duration_over_cap`, `stale_routine`, plus part flags.
  Presented through `coach.flags.for_mode` (C44).
- `misses` (deep tier only): `coach.checkin.misses(root, since=last deep
  record date, until=window end)` →
  `{"by_tag": {"time": 0, "sleep": 2, "ill": 0, "family": 0, "skipped": 0, "other": 0, "untagged": 1},
    "by_session": {"session-a": 2}, "sessions_missed": 3}`. Counts `miss`
  annotations and untagged missed planned sessions (C18).

**Fields.** Ids and order are R-01's Sunday message: `sessions`,
`coach_led`, `runs`, `sleep`, `niggles`, `nutrition`, `meal_plan`,
`next_week`, then `hevy_edits` (only when a routine is `edited_in_app`).
Each field is `{id, n, prefill, ask}`: `prefill` states what the data
shows for confirmation, `ask` is the question. Fields that cannot apply are
left out and the rest renumbered from 1 (no external sessions → no
`coach_led`; no unlogged or missed sessions → `sessions` is a statement
with no ask). Builtin fields:

| Id | Builtin content |
|---|---|
| `sessions` | trained and missed rows; asks for one tag per missed core session (`time / sleep / ill / family / skipped / other`) and for anything trained but not logged (recorded as `trained_unlogged`, C17) |
| `coach_led` | each external date; asks what it covered; states `state.rotation` and asks to confirm (R-21b: the position from `schedule plan`) |
| `runs` | asks count and total distance; states Hevy-logged runs |
| `sleep` | R-01 wording |
| `niggles` | asks for anything new |
| `nutrition`, `meal_plan` | R-01 wording (R-06's two additions included) |
| `next_week` | R-01 wording; states `state.rotation` for confirmation when there is no `coach_led` field |

**Card parts** (`coach/checkin_parts/<topic>.py`), the way later items
change the card without editing R-21a's modules:

```python
FIELDS = ("nutrition", "meal_plan")    # field ids this part owns; may be empty
def contribute(ctx: CardContext) -> Contribution | None
# CardContext: root, today, window, mode, card (read-only so far)
# Contribution(fields: dict[str, Field | None] = {},   # None = omit that field
#              facts: list[str] = [], flags: list[dict] = [],
#              tier_reasons: list[str] = [], nudge_lines: list[str] = [])
```

- Two parts owning the same field id is an error at discovery (exit 1,
  both modules named). A part's `Field` replaces the builtin; returning
  `None` for a contribution falls back to the builtin.
- Parts are pure reads and run in a fixed order (module name).
- R-21a ships one part itself, `nutrition`: when `coach.nutrition` exists
  and `nutrition status` says enabled, it replaces `nutrition` with
  `data.questions` (pre-fills included), omits `meal_plan`, and passes the
  food-exceptions question as a `nudge_lines` entry. When the module is
  absent or reports `{"enabled": false}`, it returns None and R-01's
  builtin fields stay. A soft dependency on R-33a: nothing is computed
  from nutrition data here.
- Expected parts from later items: R-27 (`niggles` field from `niggles
  list`; due follow-ups as facts; `niggle_escalate`), R-30a and R-31
  (`tier_reasons`), R-42a and R-43 (`runs`, `sleep` stated from activity
  sources).

**Record skeleton.** `checkin skeleton --date D [--tier T] [--overlay ID]`
writes `check-ins/D.md` when absent (exit 1 when present, unless
`--refresh`, which re-renders only the regions and leaves every other byte
as it was):

```markdown
# Check-in — 2026-10-11 (weekly)

## Week in review
<!-- coach:begin week-review 2026-10-11 -->
**Window:** 2026-10-05 → 2026-10-11 · **Sessions:** 2 of 3 core · **Missed:** Sat 10 Oct Session A (sleep)

(sessions table · results vs prescription · e1RM · flags)
<!-- coach:end week-review 2026-10-11 -->

## Coach's read

## Decisions

## Next week

<details>
<summary>Prescription</summary>

<!-- coach:begin overlay 2026-10-12-weekly -->
<!-- coach:end overlay 2026-10-12-weekly -->

</details>
```

- The week-review region is the card's data part, rendered as of the
  record date (no questions). The overlay region is R-13's `overlay render`.
- Coach's read, Decisions and Next week are prose the coach writes. R-01's
  `Missed:` line lives in the region; R-02's adherence decision line and
  block status line are prose in Decisions until R-30a and R-31 script
  them.
- Deep records add `## Block planning` after Decisions, and `misses` in
  the region.
- Check `checkin_record_words` (warn): prose outside rendered regions and
  `<details>` over 600 words (weekly) or 1,000 (deep). Check
  `checkin_records` (warn): a file in `check-ins/` named like a record
  whose first line does not parse.
- Hevy sync details never go in the record: C9's `writes.jsonl` is the log.

**Catch-up mode** (R-21b). When `mode` is `catch_up`, `fields` is empty and
`catch_up` holds:

```json
{
  "layoff_days": 28,
  "summary": [{"week": "2026-W38", "planned_core": 3, "trained_core": 0, "missed_by_tag": {"untagged": 3},
               "optional_trained": 0, "external_done": null, "workouts": 0, "planned_from": "schedule"}],
  "questions": [{"id": "gap", "n": 1, "ask": "…"}, {"id": "now", "n": 2, "ask": "…"}, {"id": "next_week", "n": 3, "ask": "…"}],
  "return_week": {"proposal_id": "…", "overlay_id": "2026-10-12-weekly", "band": "22-42", "days_off": 28,
                  "load_factor": 0.9, "set_delta": -1, "rpe_cap": null,
                  "sessions": [{"date": "2026-10-12", "title": "Session A", "lines": ["Squat 2×5 @ 90"]}],
                  "flags": [], "lines_digest": "sha256:…"},
  "write_line": "Reply \"go\" to train this and write: Session A, Session B (Hevy)."
}
```

- `summary`: one row per week in the window (C7 weeks; `week` is the
  label). Planned sessions come from the overlay in force, else from
  `schedule plan` for that week (`planned_from: "schedule"`).
- `return_week`: `propose week --dry-run` for the week after today
  (R-23a), which applies C22 decay. `lines_digest` = C7 canonical hash of
  `data.lines`. After "ok", the real `propose week` must give the same
  digest; if not, the coach presents again.
- The card ends with the write line (R-03's shape) and "Reply ok to accept
  all of this, or answer 1–3." "ok" alone means: misses stay untagged,
  nothing new to report, the return week as shown, written to Hevy.
- Parts contribute `facts` and `nudge_lines` in catch-up mode; their
  fields are ignored.
- `checkin tag-gap --tag T` writes one `miss` annotation per untagged
  missed planned core session in the window.
- `checkin return-brief (--proposal ID | --overlay ID) --reason ill|travel|no_kit|layoff`
  returns `data.text`, the return template of the coach's brief: (1) one
  sentence on the gap (days off, reason); (2) what the return week does
  (band, load and set change, RPE cap); (3) per-session lines; (4) what
  happens after (normal progression from the logged loads, R-02); (5) the
  write line. `ill` adds R-02's safety lines (48 hours symptom-free first;
  first session at RPE 7 or below; fever, chest symptoms or a slow recovery
  mean checking with a qualified professional first). `travel` and
  `no_kit` take a coach-built one-off overlay. Read-only; the coach may
  edit the words before presenting.

## C37. Missed-day rules (R-22; R-23a, R-25, R-30b read)

R-22's program bump (C16 schema versions) replaces C16's free-text
`missed_day_rules` with:

```json
"missed_day_rules": [
  {"id": "miss-b", "session_id": "session-b", "text": null,
   "when": {"min_days_left": 1},
   "action": {"kind": "fold", "into": "session-a",
              "exercises": [{"exercise_id": "db_single_arm_row", "sets": 2}]}},
  {"id": "miss-a", "session_id": "session-a", "text": null, "when": {},
   "action": {"kind": "shift", "to_weekdays": ["sat", "thu"]}},
  {"id": "miss-c", "session_id": "session-c", "text": null, "when": {}, "action": {"kind": "skip"}},
  {"id": "miss-0004", "session_id": "session-a", "text": "If you miss Mon, …", "when": {},
   "action": {"kind": "manual"}}
]
```

- Migration: each free-text rule becomes a `manual` rule with a report row.
- **Match**: the first rule in list order whose `session_id` is the missed
  session and whose `when` holds. `when.min_days_left`: days left in the
  overlay span after the missed date. No match, or `manual`: unmatched.
- **`fold`**: copies the listed exercises from the missed session's lines
  in the overlay in force into the next planned date of `into` in the
  span, after its last exercise, with `sets` working sets (default 2,
  never more than prescribed) at the prescribed reps and load, and at the
  prescribed RPE or the item's optional `rpe` if lower. `into` is a
  session id, or `"next"` for the next planned session of any kind. No
  such later date in the span: unmatched.
- **`shift`**: moves the whole session to the first weekday in
  `to_weekdays`, in list order, that falls after the missed date, inside
  the span, with no session already planned, and on a day in `[athlete]
  available_days` when that list is non-empty. None free: unmatched. The
  rule's author checks recovery windows when writing the rule; the script
  does not search for days.
- **`skip`**: the week continues unchanged; the miss is recorded.
- **`manual`**: always unmatched; used for migrated free text.
- `text`: optional wording for the brief; when null, `coach.missed.describe(rule)`
  writes it ("Miss Session B: 2 sets of Single-arm row go into the next
  Session A, this week only.").

**Overlay `schema_version` 3** adds, per exercise line, `fold`:
`null | {"rule_id": "miss-b", "from_session_id": "session-b", "from_date": "2026-10-14", "scope": "one_week"}`,
and per session `moved_from: null | date`. Migration 2 → 3 adds nulls;
approved overlays lose approval and the report lists them (as C21).

**Applying a rule** builds a `midweek` overlay through `coach.overlay.build`:
span from the next planned date after the miss to the end of the overlay in
force, `supersedes` it, sessions copied from it with the rule applied;
changed lines and moved sessions carry `missed_day_rule` (info). It runs
`coach.validity.check_overlay` (R-24) before returning.

- `coach.missed.apply_rule(root, overlay, session_id, date, rule) -> draft`
  applies any rule object, including a synthetic one built by another item
  (R-30b builds a `fold` rule for a priority lift's floor dose and applies
  it ahead of the program's rules, C40). Matching and application stay
  separate so callers can do this without copying either.
- `missed list [--date D]`: planned sessions in the overlay in force dated
  before D with no matching workout and no `trained_unlogged` annotation (C18).
- `missed plan --session S --date D`: read-only. `data.matched`, `data.rule`,
  `data.summary` (at most five lines, loads via `format_load`),
  `data.write_line` (R-03 shape), `data.draft` (the midweek draft). Unmatched:
  `missed_rule_unmatched` and no draft.
- `missed apply --session S --date D [--tag T]`: run after the athlete's
  "go". Writes the `miss` annotation (untagged when no `--tag`), the
  midweek overlay (unapproved), and appends three lines under
  `## Mid-week` in the newest record:

  ```
  - Missed Wed 14 Oct Session B (sleep).
  - Rule miss-b: Single-arm row 2×10 @ 30 (Hevy: 30) added to Sat 17 Oct Session A, this week only.
  - Overlay 2026-10-17-midweek; Hevy: Session A.
  ```
  The coach then runs `overlay approve` and `routines push` as for any
  overlay.
- **Unfolding** needs no command: the next weekly overlay is built from the
  program, and `last_prescription` ignores `fold` lines (C23; R-22 adds
  the filter to R-23a's code and tests that the next weekly proposal does
  not carry a fold forward).
- Checks: `missed_rules_valid` (sessions, exercises and `into` exist and
  are active; weekdays valid; fold sets ≥ 1); `overlay_folds_expired`
  (fail: a `weekly` or `deload` overlay holds a `fold` line, or a fold's
  `from_date` is more than 6 days before the overlay's span start).

## C38. Standing pages and publishing (R-25; R-22, R-23b, R-26, R-27, R-30a, R-31, R-33a, R-40c, R-45 read)

Three pages at the instance root, rendered whole, each with the C11 header
carrying its as-of time. Nothing writes them but `pages render`.

| Page | Source path in the header | Renderer |
|---|---|---|
| `this-week.md` (the brief) | the overlay in force | `render_brief(as_of)` |
| `README.md` (the dashboard) | `data/state.json` | `render_dashboard(as_of)` |
| `progress.md` | `data/history/` | `render_progress(as_of)` |

`coach.pages.header_facts(root, as_of) -> dict` computes the brief
header's facts once, for the brief, the dashboard and R-26b's `status`:

```json
{"week": "2026-W42", "week_start": "2026-10-12", "overlay_id": "2026-10-12-weekly",
 "rotation": {"position": "week-b", "confirmed": true},
 "phase": "recomp",
 "checkin": {"last": "2026-10-11", "due_date": "2026-10-18", "tier": "weekly",
             "days_since": 3, "mode": "weekly"}}
```

`week` is the C7 label and `week_start` the configured week's first day.
`phase` comes from R-33a's `nutrition status` when present (null when
absent or disabled); `checkin` from C36 `due()`; `overlay_id` null when no
overlay is in force.

`as_of` bounds history (workouts started and annotations created at or
before it); "today" inside a render is `as_of`'s local date. Program,
state, overlays and decisions are read as they are now, so a change to them
makes the page stale, which is intended.

**Brief layout**, at most 60 lines; sections appear in this order with
these headings:

```markdown
**Week of 12 Oct** · Week B (confirmed) · Recomp · Check-in due Sun 18 Oct (weekly)

## Focus
<overlay focus>

## Sessions
| Day | Session | Tier | Key | Done |
|---|---|---|---|---|
| Mon 12 | Session A | core | Squat 3×5 @ 100 | ✔ |

## Changed
- DB bench 22.5 → 25/hand (Hevy: 50): hit 3×10 at RPE 8.

## Watch
- …

## If you miss a day
- …

## Wins
- …
```

- Header: week start; `state.rotation` position and whether confirmed;
  phase (from a part; omitted until R-33a); next check-in date and tier
  (C36 `due`).
- Sessions: every session of the overlay in force for the week, by date;
  Tier from the program; Key = first exercise's name and its working
  sets in C12 Target form without RPE; Done = ✔ trained, ✗ missed, blank
  upcoming (C18, as of).
- Changed: lines whose `change` is set, by date then exercise order, at
  most five, then "and N more in the check-in". Reason: `override.reason`,
  else `provenance.rationale` (C21), else `target_note`.
- Watch: at most three items by priority: unresolved `block`, then `warn`
  flags on the overlay (through `coach.flags.for_mode`, C44), then part
  items.
- If you miss a day: one line per `program.missed_day_rules` entry (v1:
  `condition → action`); R-22's part replaces the slot with `describe`.
- Wins: at most three: a new best e1RM in the last seven days; a
  core-complete streak of two weeks or more; every core session trained
  last week; part items.
- Over 60 lines: cut Wins, then Watch, then Changed to fit; Sessions and
  Focus are never cut.

**Dashboard** (`README.md`): first, a status block of at most six lines
(the brief's header line; block `hard_weeks_completed` and
`deload.status` from state; last check-in date, tier and link; open flag
count; last publish time), then the Sessions table, then a progress
summary of at most five lines (top three e1RM bests, streak, latest
bodyweight), then links (`this-week.md`, `progress.md`, latest record,
`routine/program.md`, `check-ins/`, and the template's README on GitHub
for "how this works"). The Sessions table header is within the first 12
lines.

**Progress** (`progress.md`): a table of every lift with a C18 series
(best e1RM and date, latest, change over 28 days); part sections (ladder
state, priority lifts); core-complete streak (current, longest, and the
last 12 weeks as ✔/✗); bodyweight (part, else the Hevy body-measurement
cache as weekly means labelled "scale (Hevy)"; the section says "no
bodyweight source" when neither exists).

**Core-complete week**: every planned core session of the overlay in force
trained (including `trained_unlogged`), and every external session with an
`external` annotation marked done. External sessions with no annotation
neither count nor break the streak. Optional sessions never count.

**Page parts** (`coach/page_parts/<topic>.py`):

```python
SLOTS = ("brief.watch",)
def contribute(ctx: PageContext) -> dict[str, list[Item]] | None
# PageContext: root, as_of, overlay (in force), program, state
# Item(text: str, priority: int = 50)     # lower sorts first
```

| Slot | Semantics |
|---|---|
| `brief.header.phase` | replace (one item) |
| `brief.lines` | append one-liners after Focus |
| `brief.sessions_footer` | append lines after the Sessions table (R-40c's session-sheet link) |
| `brief.watch`, `brief.wins` | merge with builtin, sort by priority, cap |
| `brief.if_you_miss` | replace (R-22) |
| `dashboard.status` | append lines to the status block (counts toward its six) |
| `progress.sections` | append sections (`text` holds the section markdown) |
| `progress.bodyweight` | replace (R-33a) |

Two parts replacing the same slot is an error at discovery.

R-25 ships one part itself, `nutrition`: when `coach.nutrition` exists and
`nutrition status` says enabled, it adds `data.brief_line` to
`brief.lines` (once) and the phase to `brief.header.phase`; absent or
disabled, it adds nothing. A soft dependency on R-33a, computing nothing.

R-25 prints every load through one call site, so R-40c's `show_hevy`
change (C5) is one line.

**README ownership.** `pages render` refuses (exit 3) to overwrite a
`README.md` that does not start with the C11 header, unless
`--replace-readme` is given; that first replacement is reported. Checks
`pages_fresh` (fail: a page differs from a fresh render at its own as-of
time; skip when absent) and the 60-line ceiling (fail).

**Publishing** (roadmap decision 1). `pages publish --overlay ID [--record D]`:

1. Refuses (exit 3) unless the overlay is approved with a matching hash
   (C10), or in read-only mode (C39).
2. Renders all three pages and refreshes the newest record's regions
   (`checkin skeleton --refresh`).
3. Refuses (exit 3) when the git index already holds staged changes to any
   other path; names them.
4. Stages exactly `this-week.md`, `README.md`, `progress.md`,
   `data/overlays/<ID>.json` and `check-ins/<D>.md` (D defaults to the
   newest record), commits with the message
   `coach: publish week of <span.start> (<ID>)`, and pushes the current
   branch to its upstream (never `--force`). A failed push exits 4 and
   keeps the commit; the message says to push by hand.
5. `--dry-run` reports the paths and message and changes nothing.

Metadata: `writes`, `git_write`. It is allowlisted (C2).

## C39. Scheduled run and read-only mode (R-45; R-26, R-40a read)

**Read-only mode.** With `COACH_READ_ONLY=1` in the environment:

- the CLI refuses (exit 3, `refused`, "read-only run") any command whose
  metadata has `hevy_write` or `git_write`, or `writes` with
  `writes_scope` `"data"`, before it does anything;
- `HevyClient.put` and `post` raise the refusal whatever the caller (R-45
  adds this to R-12's client);
- commands with `writes_scope` `"cache"` run normally.

**`nudge run`** sets read-only mode on itself, then:

1. `hevy pull` (incremental; skipped when `[hevy] enabled` is false; on a
   network failure it continues from the cache and says so in the draft
   and the envelope's warnings, exit 0).
2. Builds the card with `include_unsynced=True` (C17) and writes
   `.coach/drafts/checkin-<today>.md`: a first line "Draft from the
   scheduled run at <time>; not a check-in record. Run /check-in.", then
   the card text. Overwrites today's draft; keeps the last 8 drafts.
3. Decides whether to nudge from `.coach/nudge.json`
   (`{"schema_version":1,"window_start":date,"sent":[{"at":ts,"kind":"overdue|catch_up|repeat","channel":"…"}]}`):
   - `overdue` once per window when `days_since ≥ cadence_days + after_days`;
   - `catch_up` once per window when `days_since > 10` (C36);
   - `repeat` every 7 days after the last nudge while no new record exists;
   - a new record resets the window.
4. Sends through `[nudge] channel`:
   - `none`: records the decision only;
   - `macos`: `osascript -e 'display notification …'`, text at most 200
     characters: days since the last check-in, sessions trained and
     missed, the mode, and the first card part `nudge_lines` entry;
   - `github_issue`: through `gh` in the instance root. One open issue
     labelled `coach-nudge` at a time: created with title
     `Check-in due: week of <window start>` and the draft as body, or
     commented on when open. A missing or unauthenticated `gh` is a
     warning, not a failure.

Output: `data` = `{"due", "days_since", "mode", "nudged", "kind", "channel", "draft", "unsynced", "warnings"}`.
The run writes only under `.coach/`; the working tree's tracked files are
never touched, and it never calls Claude.

**`nudge recipe --kind launchd|cron`** prints, and writes nothing:

- launchd: a user agent plist, label `coach.nudge.<instance dir name>`,
  `ProgramArguments` `[<sys.executable>, "-m", "coach", "nudge", "run"]`,
  `WorkingDirectory` the instance root, `EnvironmentVariables`
  `{"COACH_READ_ONLY": "1"}`, `StartCalendarInterval` from `[nudge] time`,
  stdout and stderr to `.coach/logs/nudge.log`;
- cron: one crontab line with the same command, `COACH_READ_ONLY=1`, and
  the log redirect.

**`nudge status`**: config, last run time (from the log's last envelope),
the nudge state and whether a recipe looks installed (launchd: the plist
exists in `~/Library/LaunchAgents`; cron: not detected).

`reference/scheduled-checkin.md` (framework doc) holds the install,
uninstall and log steps for a human, and states what the run never does:
write to Hevy, commit, push, or start Claude.

The `check-in` skill reads the athlete's comment on an open `coach-nudge`
issue as the reply to the Sunday message and closes the issue after the
record (R-45).

## C40. Dose targets, priority lifts and the minimum week (R-30a, R-30b; R-31, R-41b read)

**Dose targets** (R-30a). R-30a's program bump (C16 schema versions) adds
an optional top-level object; migration adds `{}`:

```json
"dose_targets": {"chest": 10, "lats": 10, "quads": 8, "calves": 6}
```

- Keys are R-11 muscle names; values are fractional hard sets per week,
  0 to 40. A muscle with no key gets the default 10 when it is a primary
  muscle of any exercise in an active core session, and no target
  otherwise.
- `coach.structure.targets(program) -> dict[muscle, float]` returns the
  effective targets. Nothing else applies the default.
- Targets are what weekly balance is judged on. They are coaching numbers,
  set when the program is designed and changed only by a program edit.

**Priority lifts and the minimum week** (R-30b). R-30b's program bump adds
two top-level members; migration adds `priority: []` and `minimum_week:
null`:

```json
"priority": [
  {"exercise_id": "bb_back_squat",
   "kpi": {"kind": "e1rm", "target": 130, "by": "2027-01-31"},
   "floor": {"sets": 2, "rpe": null}}
],
"minimum_week": {"sessions": ["min-a", "min-b"],
                 "schedule": {"rule": "fixed_weekdays", "params": {"days": {"tue": "min-a", "fri": "min-b"}}}}
```

- `kpi.kind`: `e1rm` (C18 best point), `top_load`, `top_reps` (heaviest or
  most reps in a working set at the newest exposure), `rung`
  (`assistance_ladder` state, R-23b). `target` and `by` nullable.
- `floor.sets` default 2; `floor.rpe` null = the current prescription's RPE.
  `program validate` rejects a priority `exercise_id` that no session
  holds.
- `coach.structure.priority_floor(root, missed_session_id, date) -> rule | None`
  builds a synthetic C37 fold rule for the priority lifts the missed
  session carried, or None when it carried none:
  `{"id": "priority:<exercise_id>", "session_id": "<missed>", "when": {},
  "action": {"kind": "fold", "into": "next", "exercises": [{"exercise_id": "<id>", "sets": <floor.sets>, "rpe": <floor.rpe>}]}}`.
  Loads and reps come from the approved prescription (no progression);
  `rpe` applies only when lower than the prescribed RPE.
- R-30b applies it through `coach.missed.apply_rule(root, overlay,
  session_id, date, rule)` ahead of the program's own rules, adding that
  one call to R-22's plan and apply path (named in the PR). Folded lines
  get R-22's `fold` marker (`scope: one_week`, overlay v3) and its
  `missed_day_rule` flag, five-line summary and write line.
- When `apply_rule` returns unmatched (no later session in the span),
  `priority_exposures_missed` is raised for that week and nothing is
  inserted; the next week's own session carries the lift.
- `minimum_week.sessions` are session ids with `status: standby`.
  `structure balance --variant minimum` checks: at most two sessions, each
  within its C19 cap, every priority floor present, every target at least
  one third met. `structure minimum --week W --write` writes the plan file
  `.coach/plans/<week start>-minimum.json` (C6), a C23 `SchedulePlan` for
  `propose week --plan`. The overlay stays kind `weekly`; adherence is
  judged against it like any other overlay.

## C41. Structure accounting and `coach structure` (R-30a; R-21a, R-25, R-31, R-40b read)

```python
coach.structure.week(root, week_start) -> WeekReport     # week_start from coach.dates.week_span
coach.structure.adherence(root, until=None) -> AdherenceReport
coach.structure.balance(root, program=None) -> BalanceReport
coach.structure.planned_dose(root, sessions) -> dict[muscle, float]
coach.structure.ordinary_weeks(root, until, n=4, reach=12) -> list[str]
```

- Planned dose uses the same weights as delivered dose
  (`coach.stats.set_weights`, C18). Planned dose for a date comes from the
  overlay in force; with no overlay, from `schedule plan` on the program.
  Working sets only.
- Coach-led sessions: planned from `program.external_sessions` placed by
  the schedule's weekday; delivered when an `external` annotation for that
  date says `done: true`, using `estimated_sets` as fractional sets. No
  annotation = `unconfirmed`, left out of both sides of adherence and
  shown as such.
- Optional sessions: left out of planned dose and adherence; their
  delivered sets count in delivered dose ("bonus").
- **Adherence** (R-02): sessions trained over sessions planned over the
  trailing four ordinary weeks, coach-led included, optional excluded, any
  logged workout matching the session counted as trained (shortened
  sessions count).
- **Ordinary week**: not a light week (overlay kind `deload`, or an
  adopted `light_week` decision covering it), not a `one_off` week, not
  inside a layoff gap of 11+ days. The window reaches back at most 12
  weeks; with fewer than four ordinary weeks it reports
  `insufficient_weeks` and raises no adherence flag.

**`structure week --week 2026-W41`** →

```json
{"week": "2026-10-05", "span": {"start": "2026-10-05", "end": "2026-10-11"}, "kind": "ordinary",
 "sessions": [
   {"session_id": "session-a", "date": "2026-10-05", "tier": "core", "status": "trained", "moved": false},
   {"session_id": "session-b", "date": "2026-10-08", "tier": "core", "status": "missed", "tag": "sleep"},
   {"external_id": "pt-tue", "date": "2026-10-06", "status": "done"}
 ],
 "planned": 3, "trained": 2,
 "muscles": {"chest": {"target": 10, "planned": 6.0, "delivered": 6.0, "bonus": 0.0}},
 "by_session": {"session-a": {"quads": 3.0, "chest": 3.0}},
 "flags": []}
```

- `kind`: `ordinary`, `light`, `one_off`, `layoff`. Session `status` from
  C18 adherence; external `status` `done`, `not_done`, `unconfirmed`.
- `planned` counts core and external sessions, `unconfirmed` excluded.
  `trained` counts core sessions with status `trained` and external
  sessions `done`. Optional sessions appear with `tier: optional` and count
  in neither.
- `muscles[m].planned`: core sessions and external estimates;
  `delivered`: logged core workouts plus `done` external estimates;
  `bonus`: logged optional and `extra` workouts.
- `by_session` and `session_volume_high` (info) use logged workouts.

**`structure adherence [--until D]`** → `{weeks: [...], planned, trained,
pct, insufficient_weeks, flags, decision}`, using the last four ordinary
weeks ending on or before D (default today). `decision` is the newest
`adherence_trigger` decision in effect, or null. Raises `adherence_low`
(below 70 %), `add_session_type_blocked` (below 80 %),
`restructure_required` and the delivered form of `volume_undershoot`.

- `restructure_required`: `adherence_low` holds and no
  `adherence_trigger` decision (rule `restructure`) suppresses it.
  Declined suppresses until four ordinary weeks have closed after
  `made_at`; deferred suppresses until `revisit_on`; adopted suppresses
  for four ordinary weeks.
- `volume_undershoot`: a muscle below its dose target, either planned on
  core plus coach-led (`structure balance`) or delivered in at least three
  of the trailing four ordinary weeks (`structure adherence`). The message
  says which.

**`structure balance [--program FILE]`** → per position of the schedule
cycle: planned dose per muscle on core sessions plus external estimates,
the cycle average, the targets, and `session_volume_high` (warn) per
planned session. A target is met when the cycle average meets it. Raises
the planned form of `volume_undershoot`. With FILE (a candidate program
compared with `data/program.json`), a new active session (any kind or
tier) or external session under 80 % adherence raises
`add_session_type_blocked`, unless an `adherence_trigger` decision with
rule `add_session` and outcome `adopted` was made in the last 28 days.
Exercise swaps are not affected.

- `session_volume_high`: more than 11.0 fractional sets for one muscle in
  one session, the per-session figure from Remmert, Pelland et al. 2025
  (SportRxiv preprint, doi 10.51224/SRXIV.537). Warn on a planned session
  (program or overlay), info on a logged workout.
- `structure decide` appends the C25 `adherence_trigger` decision and
  prints R-02's line ("Adherence trigger: 58 % over 4 weeks: deferred to
  2026-11-02") for the check-in record.
- Check `program_balance` (warn) runs the static balance on
  `data/program.json`.
- R-30a's flags are registered in `coach/flags/structure.py` (C20). Its
  `structure` reports present flags through `coach.flags.for_mode` (C44).

## C42. Block ledger and state (R-31; R-21a, R-25, R-26 read)

`data/blocks.json`:

```json
{
  "schema_version": 1,
  "blocks": [
    {"id": "b-0001", "started": "2026-08-31", "seed_hard_weeks": 0, "seed_reason": null,
     "ended": null, "end_reason": null,
     "weeks": [
       {"week": "2026-08-31", "class": "hard", "planned": 3, "trained": 3, "as_prescribed": 3,
        "signals": {"readiness": "ok", "sleep": "ok", "sleep_source": "athlete",
                    "rpe_drift": false, "niggle": false},
        "triggers": [], "count_after": 1,
        "outcome": "none", "deep": false, "closed_at": "2026-09-06T18:00:00Z"}
     ]}
  ]
}
```

- Block ids `b-NNNN`, never reused. `end_reason`: `light`, `return`, `low`.
- `class`: `hard`, `partial`, `low`, `light`, `return`, `one_off`.
- `signals.readiness` and `signals.sleep`: `poor`, `ok`, `unknown`;
  `sleep_source`: `athlete`, `sleep_debt`, `none`.
- `triggers`: the fired subset of `readiness`, `rpe_drift`, `niggle`,
  `sleep`.
- `outcome`: `none`, `watch`, `due`, `skipped`.

R-31's state bump (C16 schema versions) replaces `state.json` `block` with:

```json
"block": {
  "id": "b-0001",
  "started": "2026-08-31",
  "hard_weeks_completed": 6,
  "last_closed_week": "2026-10-05",
  "last_deep_review": "2026-09-27",
  "light_week": {"status": "proposed", "type": "deload", "reason": "ceiling",
                 "week": "2026-10-12", "decision_id": null}
}
```

- `light_week.status`: `not_due`, `watch`, `skipped`, `proposed`, `agreed`,
  `declined`. `type`: `deload`, `light`, `return`, or null. `reason`:
  `ceiling`, `triggers`, `coach`, or null.
- When the agreed week closes as class `light`, the block ends and this
  object resets to `not_due`.
- Migration: `hard_weeks_completed` kept; `deload.status` `not_due` and
  `done` → `not_due`, `due` → `proposed`, `in_progress` → `agreed`,
  `skipped` → `skipped`; `data/blocks.json` created with one block whose
  `seed_hard_weeks` is the old count.

C25 `light_week` decision `details`:
`{"type": "deload", "week": "2026-10-12", "reason": "ceiling", "triggers": [], "hard_weeks": 6}`.

```python
coach.block.close(root, week_start, readiness, sleep, deep, dry_run) -> CloseReport   # week_start from coach.dates.week_span
coach.block.status(root) -> StatusReport     # state summary, status_line, deep_review, flags
coach.block.status_line(root) -> str
coach.block.classify(root, week_start) -> str   # pure read; used by close and by tests
```

Checks: `block_state` (fail: `state.block` disagrees with the ledger),
`block_config` (fail: ceiling outside 4–8), `light_week_overlay` (warn).

## C43. Light weeks, triggers and `coach block` (R-31; R-21a, R-25, R-26 read)

Rules (R-02's prose, scripted; the prose stays the human copy):

- **Trained as prescribed**: a trained session counts toward a hard week
  when at least two thirds of its prescribed working sets were logged and
  its mean logged RPE (over sets with both values) is no more than 1.5
  below target; sets without a logged RPE count as on target. A coach-led
  session counts when its `external` annotation says done. Session counts
  come from `coach.structure.week` (C41).
- **Hard week**: not light, return or one-off; at least 75 % of planned
  core and coach-led sessions trained as prescribed. Under 50 % trained
  ends the block.
- **Ceiling**: `program.blocks.hard_weeks_ceiling`, default 6, allowed 4–8.
- **Triggers** (four): athlete-reported readiness, compound RPE drift two
  sessions running (`coach.patterns.rpe_drift`), an `aggravated` niggle
  (C27), poor sleep (the athlete's report, or `coach.cardio.sleep_debt`
  over the closed week when R-43 is present; None means no source).
- A light week is due at the ceiling, or on two fired triggers with at
  least three hard weeks; skipped with a recorded reason below three; one
  trigger is a watch. A declined light week at the ceiling is proposed
  again at the next close.
- **Type**: ceiling reached, or two triggers including RPE drift or an
  aggravated niggle → `deload` (the program's `deload_rule`); two triggers
  from readiness and sleep only → `light`; a closed week under 50 % with an
  `ill` miss tag → `return`. The coach may choose another type with a
  recorded reason. `propose week --kind deload --transform <type>` builds
  it (C23 transforms).
- Closing a light, return or low week ends the block; the next block
  starts at zero. A week whose overlay carries a `22-42` decay classes as
  `return`.
- The next check-in is deep (`deep_review.due`) when six weeks have passed
  since the last deep close, a light week is being proposed, R-30a's
  structural flags are raised, or on the first close; never because of the
  light week itself.

Status line format:

```
Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>
```

`<state>`: `not due`, `watch`, `skipped (<n> hard weeks)`,
`proposed for <week> (<type>, <reason>)`, `agreed: <type>, <week>`,
`declined (<reason>), proposed again next check-in`; `<week>` is shown as
`wk of <start as D Mon>`. `routine/program.md` renders it from
`coach.block.status_line`.

Flags (registered in `coach/flags/block.py`; rows in C20):
`light_week_due`, `light_week_skipped`, `fatigue_watch`,
`deep_review_due`.

## C44. Coaching mode and config suggestions (R-40a, R-40b; R-21a, R-25, R-30a, R-31 read)

```toml
[coaching]                # R-40b
mode = "coach"            # "coach" | "run"
```

- `mode = "run"`: the athlete wants their own program executed.
  Progression, validity, decay, light weeks and every non-structural flag
  run as in `coach` mode. Structural flags (C20) are shown at `info` with
  the message prefixed "run mode: ", and the check-in never proposes an
  `adherence_trigger` decision. `structure adherence` still reports
  adherence; `structure decide` still works if the athlete asks for a
  restructure.
- `coach.flags.for_mode(flags, mode) -> list[flag]` is the one place the
  downgrade happens. It never touches `block` flags. Presenters (R-21a
  card, R-25 brief, R-30a `structure` reports) call it; stored overlays
  keep the original severity.

`config suggest --unit kg|lb [--gym commercial|home]` returns
`data.values` (`[athlete]` and `[equipment]` keys with suggested values)
and `data.notes` (what to confirm with the athlete, such as the heaviest
dumbbell). It reads no config and writes nothing; `/setup` copies
`config.example.toml` and edits values with the Edit tool (C4). Suggested
values:

| Key | kg | lb |
|---|---|---|
| `bar_weight` | 20 | 45 |
| `plates` | 25, 20, 15, 10, 5, 2.5, 1.25 | 45, 35, 25, 10, 5, 2.5 |
| `barbell_increment` | 2.5 | 5 |
| `dumbbell_increment` | 2 (home 2.5) | 5 |
| `dumbbell_max` | commercial 50, home asked | commercial 120, home asked |
| `machine_increment` | 5 | 10 |
| `cable_increment` | 2.5 | 5 |

## C45. Program drafts, adoption, import and starters (R-41a, R-41b; R-40a, R-40c read)

A **program draft** is what `program adopt` takes. Every program source
(starter, import or a hand-written design) goes through it; no skill
writes `data/program.json` directly.

```json
{
  "schema_version": 1,
  "source": "hevy_import",
  "created_at": "2026-10-11T18:00:00Z",
  "program": { "...": "a complete program.json document (C16 / C23 v2 or later)" },
  "position": null,
  "hevy_routines": {"00000000-0000-4000-8000-000000000001": "session-a"},
  "report": [
    {"kind": "converted_load", "session_id": "session-a", "exercise_id": "db_bench_press",
     "message": "Hevy 50 → 25/hand"},
    {"kind": "schedule_missing", "session_id": null, "exercise_id": null,
     "message": "Ask the athlete which days each session falls on."}
  ],
  "detected": {"percentage_based": false, "evidence": [], "suggested_schemes": []}
}
```

- `source`: `starter:<id>`, `hevy_import`, `design`.
- `report[].kind`: `converted_load`, `mixed_loads`, `cues_from_notes`,
  `schedule_missing`, `swapped_exercise`, `no_substitute`,
  `percentage_evidence`. The skill shows the report as one table.
- `detected` is filled by import only; empty for other sources.
- Schema file `program_draft.schema.json`; the `program` member is
  validated with the program schema and the plugin `PARAMS` (C23).

`program adopt --input FILE [--replace] [--position P] [--dry-run]`:

1. Validate the draft and its program (`program validate` rules, library
   ids, `[caps]` for start loads). Exit 1 with JSONPaths on failure.
2. With an existing program: exit 3 without `--replace`; with it, copy
   both files to `data/archive/programs/<today>/`.
3. Write `data/program.json` and `data/state.json` (block started
   today, zero hard weeks, rotation position from `--position` or the
   schedule rule's first position, confirmed; scheme state kept only for
   slots whose exercise and scheme are unchanged; `hevy.routines` from the
   draft).
4. Run `program render`. Stage the written files; never commit.
5. Return `data.unconfirmed`: program exercises with no confirmed load
   mode in the instance library. Adopt does not confirm on the athlete's
   behalf; the skill runs `library confirm` or `library set-mode`.

An avoided exercise (C54) is treated like missing equipment: substituted
and reported.

`program import-hevy [--routine ID ...] [--folder ID] [--out FILE] [--dry-run]`
reads the C8 cache and writes a draft (default
`.coach/drafts/program.json`):

- Refuses (exit 1) while any routine exercise lacks a confirmed load mode,
  naming `library seed` and `library confirm`.
- One routine becomes one session; session ids are slugs of the titles
  (`-2` on collision). Routines titled "(unused)" (R-14's retire marker)
  are skipped; `--folder ID` limits the import to one folder. A routine
  whose exercises are all `conditioning` pattern becomes a session with
  `kind: "conditioning"`.
- Set groups come from consecutive routine sets with the same type and
  reps or rep range. Warm-up sets are kept.
- Start load is the top working set's `weight_kg` through
  `units.from_hevy_kg` with the confirmed load mode, then
  `units.round_to_increment`; every conversion is a `converted_load` row.
  Working sets with different loads keep the top load and get a
  `mixed_loads` row.
- Cues come from the note's `Cues:` line when present; otherwise the note
  text with `Target:`, `Focus:` and `Wk of` lines removed
  (`cues_from_notes`).
- Every imported exercise gets scheme `hold`. Schedule is a
  `fixed_weekdays` placeholder with no days; adopt fails until the coach
  fills it (`schedule_missing`).
- Percentage detection only reports (`detected`, `percentage_evidence`):
  `%`, "TM", "training max", "1RM", "5/3/1" or "531" in titles and notes;
  two or more routines whose titles differ only by a week marker (`W1`,
  `Week 2`, `Wk3`); the same exercise in three or more routines with three
  or more distinct top loads. It suggests `wave_531` or `fixed_reps_rpe`
  and never assigns a scheme.

A program adopted with sessions that have no Hevy routine gets them from
R-14b's `routines create`; adopt itself never calls Hevy.

**Starters** (R-41b) live in `coach/starters/<id>.json`:

```json
{
  "schema_version": 1,
  "id": "full-body-3",
  "title": "Full body, 3 days",
  "summary": "One plain sentence.",
  "level": ["beginner"],
  "days": {"min": 3, "max": 3, "default": ["mon", "wed", "fri"]},
  "minutes_per_session": 60,
  "equipment_required": ["barbell"],
  "cites": [],
  "program": { "...": "a complete, valid program.json document with the default days" }
}
```

| id | Days | Main-lift scheme | Accessories | Level |
|---|---|---|---|---|
| `full-body-3` | 3 fixed | `linear` | `double_progression` | beginner |
| `upper-lower-4` | 4 fixed | `double_progression` | `double_progression` | beginner to intermediate |
| `push-pull-legs` | 3–6 rolling | `double_progression` | `double_progression` | intermediate |
| `wave-3wk` ("3-week wave (5/3/1-style)") | 4 fixed | `wave_531` | `double_progression` | intermediate, barbell |
| `rpe-full-body-3` | 3 fixed | `rpe_anchored` | `fixed_reps_rpe` | intermediate to advanced |

- Each starter declares its main lifts in `priority`, its weekly dose in
  `dose_targets` and a `minimum_week` (C40); `structure balance --variant
  minimum` must pass on it.
- Calibration lines (no data, no start load) carry `load: null` on a
  loaded mode with a `no_data` flag (C10).
- `starters list [--days N] [--equipment E,...]` returns id, title,
  summary, level, days, minutes and required equipment.
- `starters show ID` returns the starter and its rendered session pages.
- `starters draft ID [--days mon,wed,fri] [--start-load EXERCISE=VALUE ...] [--out FILE] [--dry-run]`
  remaps the schedule to the given days (default: `[athlete]
  available_days` when set, else the starter's defaults), applies any
  start loads (coaching numbers, athlete units), swaps exercises whose
  equipment is not in `available` (from `equipment_for`, C54) or that are
  avoided for the first library substitute that fits, and writes a draft
  with `source: "starter:<id>"`. Exit 1 when the day count is outside
  `days` or `equipment_required` is not available.
- `cites` holds template research claim refs (C28); empty until the notes
  exist.

## C46. Training without Hevy: manual log and session sheets (R-40c; R-20, R-21a, R-25 read)

`data/log/workouts.jsonl`, one JSON object per line, append-only;
corrections are a `void` line plus a new entry:

```json
{"schema_version": 1, "kind": "workout", "id": "manual:2026-10-12-session-a-1",
 "logged_at": "2026-10-12T19:05:00Z", "date": "2026-10-12",
 "session_id": "session-a", "overlay_id": "2026-10-12-weekly",
 "duration_minutes": 55, "notes": "",
 "exercises": [
   {"exercise_id": "db_bench_press", "load_mode": "per_hand_x2", "unit": "kg", "notes": "",
    "sets": [{"type": "normal", "reps": 10, "rpe": 8, "value": 25,
              "duration_seconds": null, "distance_meters": null}]}
 ]}
{"schema_version": 1, "kind": "void", "id": "manual:2026-10-12-session-a-1",
 "logged_at": "2026-10-12T19:20:00Z", "reason": "logged twice"}
```

- `value` is the coaching number in `unit`: per hand for `per_hand_x2`,
  the implement for `single_implement`, the total for `total`, the added
  load for `bodyweight`, the assistance for `assisted`; null for `band`,
  `duration`, `distance`. Never a Hevy value. History builds load objects
  with `units.make_load` (C17); nothing doubles or halves.
- Ids are `manual:<date>-<session_id>-<n>` (`adhoc` for no session);
  `n` counts from 1 per date and session, voided ids included.
- `session_id` and `overlay_id` may be null (an unplanned workout).
- `log prefill --session S --date D` returns `data.draft`: a workout
  line without `id` and `logged_at`, built from the overlay in force on D.
  Fixed reps and loads are filled as prescribed; a `rep_range` leaves
  `reps` null; `rpe` is null. Warm-up sets are left out.
- `log add --input FILE [--again] [--dry-run]` validates and appends one
  line. Exit 1 for: an unknown exercise id; a load mode different from
  the slot's effective mode; a null `reps` on a rep-based set; a date
  after today; a `value` on a null-load mode. Exit 3 when the date and
  session already have a live entry, unless `--again`. Warning
  `looks_like_total` when a per-hand `value` is exactly twice the
  prescribed per-hand load. Returns the id and a one-line summary printed
  with `units.format_load(..., show_hevy=False)`.
- `log void ID --reason TEXT [--dry-run]` appends a void line. `log list
  [--since D]` returns live entries.
- Check `manual_log_valid`: every line validates, ids are unique, every
  void names a live workout, exercise and session ids exist.
- With `[hevy] enabled = true`, `log add` still works (for a workout the
  athlete forgot to log in Hevy) and warns `hevy_enabled`.
- With Hevy off (`[hevy] enabled = false`, which includes Hevy free),
  `overlay approve` is the last step of a programming pass; `routines
  push` exits 5 naming `[hevy] enabled`, and Hevy checks report `skip`.

`sheets render [--overlay ID] [--dry-run]` writes `this-week-sheets.md`
(C11 whole-file header) from the overlay in force today, else the next
one. One section per session in date order, anchored by session id:
title and date, the session focus, then one row per exercise
`| Exercise | Sets × reps | Load | RPE | Rest | Done |` with warm-ups on
their own row, then the cues line. Loads print with
`format_load(load, show_hevy=False)`. A footer says how to log ("reply
with what you did; differences only"). Check `sheets_render_fresh`
(skips when Hevy is enabled). A page-part module
`coach/page_parts/sheets.py` (C38) contributes one `brief.sessions_footer`
item when Hevy is off: "Session sheets: this-week-sheets.md", with
per-session anchors `#<session_id>` in the sheets file.

## C47. Unused.

## C48. Cardio config, quality and weekly load (R-43; R-21a, R-25, R-31, R-44a, R-44b, R-46 read)

```toml
[cardio]
tier = "count"                 # count | review | program — who owns the plan
distance_unit = "km"           # km | mi; caps and rendered distances
weekly_run_distance = 0        # caps; 0 = no cap
weekly_run_minutes = 0
single_run_distance = 0
single_run_minutes = 0
weekly_quality = 2             # quality activities per week, runs and conditioning together
spike_ratio = 1.10             # run_volume_spike above this × the longest run in the lookback
spike_lookback_days = 30
sleep_short_hours = 7.0        # a night below this is short
sleep_debt_nights = 4          # short nights of the last 7 that raise sleep_debt
sleep_min_nights = 4           # nights with data needed to judge
reconcile_move_days = 3
quality_rpe_min = 7
external_session_minutes = 60
external_session_rpe = 6
```

- `tier` is plan ownership: `count` (no plan: planned records ignored, no
  reconcile), `review` (an outside plan or the athlete's: reconcile on),
  `program` (the coach writes planned activities, R-46). Data depth comes
  from the sources.
- Distances in config and rendered output use `distance_unit`; stored
  values stay metres (C30). Conversion through `coach.units`.
- Every week here is a C7 week; `--week` takes a label or a date.
- With `[activity] enabled = false`, cardio commands still report lifting
  and coach-led sessions, say "no activity source" in warnings, and skip
  activity-based flags.
- **Quality activity** (glossary): first rule that applies wins, and the
  rule is reported as `quality_basis`:
  1. kind `conditioning` → quality (`kind`);
  2. `rpe` present → quality when `rpe ≥ quality_rpe_min` (`rpe`);
  3. matched to a planned activity (C49) → its `quality` (`planned`);
  4. `name` contains, case-insensitive, `interval`, `tempo`, `threshold`,
     `hill`, `fartlek`, `track` or `race` → quality (`name`);
  5. otherwise not quality (`none`).
  A planned activity is quality when its record says so (C30).
- **Session-RPE load** per bout = `rpe × minutes` (CR-10 scale), with
  `method`:

| Method | When | RPE used |
|---|---|---|
| `athlete` | the activity record has `rpe` | that value |
| `planned` | matched to a planned activity | 7 if quality, else 3 |
| `lifting_sets` | a lifting workout where ≥ half the working sets carry RPE | mean of those RPEs |
| `external_default` | a coach-led session annotated done (C17 `external`) | `external_session_rpe`, for `external_session_minutes` |
| `kind_default` | otherwise | `lifting` 6, `run` 4, `ride` 4, `swim` 4, `row` 5, `walk` 2, `hike` 3, `conditioning` 7, `sport` 6, `mobility` 1, `other` 4 |

- The combined figure is information only. No flag reads it, and no ratio
  of it is ever computed.
- `coach.cardio.week(root, week) -> dict`, mirrored by `cardio week`:

```json
{"week": "2026-W41", "tier": "review", "distance_unit": "km",
 "lifting": {"workouts": 2, "hard_sets": 26, "minutes": 115},
 "external": {"done": 0},
 "run": {"count": 2, "distance": 18.5, "minutes": 110, "quality": 1},
 "conditioning": {"count": 1, "minutes": 20},
 "other": {"ride": {"count": 1, "minutes": 45}},
 "srpe": {"total": 1810, "by_method": {"athlete": 3, "lifting_sets": 2, "kind_default": 1}},
 "bouts": [{"ref": "manual:2026-10-06-run-1", "date": "2026-10-06", "kind": "run",
            "minutes": 40, "distance": 7, "quality": true, "quality_basis": "rpe",
            "srpe": {"rpe": 8, "load": 320, "method": "athlete"}}]}
```

  `hard_sets` is the week's total of C18 hard sets (not a per-muscle sum).
  `minutes` for lifting come from C18 durations.

## C49. Bouts, reconcile and cardio flags (R-43; R-21a, R-25, R-31, R-44a, R-44b read)

**Bouts.** One timeline every week-level rule reads:

```python
@dataclass(frozen=True)
class Bout:
    date: date
    start: datetime | None        # None for planned bouts (no times are planned)
    end: datetime | None
    kind: str                     # "lifting" | "external" | a C30 activity kind
    source: str                   # "logged" | "planned"
    ref: str                      # workout id | activity id | planned id | "<overlay id>/<session id>" | external id
    session_id: str | None        # program session, for lifting, external and conditioning sessions
    minutes: float | None
    distance_meters: float | None
    quality: bool
    quality_basis: str | None

coach.cardio.bouts(root, span, mode, overlay=None) -> list[Bout]
#   mode "logged":   C17 workouts, C30 activities, C17 `external` annotations marked done
#   mode "proposal": the overlay's sessions, planned activities (tier review|program),
#                    external sessions placed by the schedule rule
coach.cardio.match(planned, logged, move_days) -> list[dict]   # the reconcile matcher; R-44b reuses it
```

**Reconcile** (`cardio reconcile --week W`, tiers `review` and
`program`; at `count` it returns `{"tier": "count", "items": []}`):

- Pass 1: same kind, same local date → `done`. Pass 2: same kind within
  `reconcile_move_days`, nearest first, ties to the earlier activity →
  `moved` (with `moved_days`). Unmatched planned before today → `missed`;
  today or later → `upcoming`. Unmatched activities → `extra`.
- Each item: `{status, planned_id, activity_id, date, kind, title,
  target: {...}, actual: {distance_meters, duration_seconds},
  delta: {distance_meters, duration_seconds}, quality}`.
- Planned activities from several sources are not merged (C30); each
  matches on its own, so a duplicate plan shows one `done` and one
  `missed`.

**Flags** (`cardio flags (--week W | --span A..B)`; also the `cardio`
week-flag provider in `propose week`; registered in
`coach/flags/cardio.py`, rows in C20):

| Code | Rule |
|---|---|
| `cap_breach` | Logged week, and planned week at `review`/`program`: run distance or minutes above the weekly cap; any single run above the single-run cap; quality activities above `weekly_quality`. One flag per cap broken, naming value, cap and unit. A planned record with only a duration target is checked on minutes only. |
| `run_volume_spike` | A run whose distance (else minutes) exceeds `spike_ratio` × the longest logged run in the `spike_lookback_days` before its date. Warn logged, info planned. No reference run, or store history shorter than the lookback: listed in `data.skipped`, not flagged. |
| `quality_stack` | Two quality bouts on the same or consecutive local dates, logged or planned. Lifting is not part of it; lifting against runs is `collision` (C51). |
| `sleep_debt` | Over the 7 nights ending on the evaluation date (C30 wellness, resolved): at least `sleep_min_nights` with a value and at least `sleep_debt_nights` below `sleep_short_hours`. Evaluation date: the week's last day for `--week`, today for proposals. |
| `status_active` | A status day overlaps the span or today. Warn `ill`/`injured` (`injured` adds "check with a qualified professional"), info `travel`. |
| `niggle_link` | An active niggle's `applies_to.activity_kinds` holds the kind of a logged or planned activity in the span. The message gives the count and distance of those activities. |

`coach.cardio.sleep_debt(root, span) -> bool | None` is the one reader of
the sleep rule: it judges the 7 nights ending on `span.end` of whatever
span the caller passes (R-31 passes the configured week from
`coach.dates`), returns None when `[activity]` is off or fewer than
`sleep_min_nights` nights have data, and the `sleep_debt` flag is raised
exactly when it returns True. R-31 calls it for its poor-sleep trigger.

**Week-flag providers.** `coach/weekflags/<name>.py`, discovered with
`pkgutil.iter_modules`:

```python
NAME = "cardio"
def flags(ctx: WeekFlagContext) -> list[dict]     # coach.flags.make(...) results
# WeekFlagContext: root, today, span, mode ("logged" | "proposal"), config,
#                  overlay (the draft, proposal mode only), bouts (list[Bout])
```

`propose week` runs every provider at C24 step 5a and appends their flags
to the overlay. `cardio flags` runs them over the span with logged bouts
dated up to today and, at `review`/`program`, planned bouts dated today or
later. A provider that raises fails the command (exit 9); it is never
skipped silently.

**Render.** `cardio render --week W [--into FILE]` prints the weekly
numbers, the reconcile table (when the tier has one) and the flags, as
markdown. With `--into` it replaces the region between
`<!-- coach:begin cardio <week label> -->` and
`<!-- coach:end cardio <week label> -->` (C11), appending the region when
absent. No freshness check: the block is a snapshot.

## C50. Status days (R-43; R-23a, R-24, R-30a, R-31, R-44b read)

`data/status-days.json`:

```json
{"schema_version": 1,
 "days": [
   {"id": "s-0001", "kind": "ill", "span": {"start": "2026-10-01", "end": "2026-10-02"},
    "note": "head cold", "created_at": "2026-10-11T18:00:00Z", "source": "check-in 2026-10-11",
    "withdrawn": null}
 ]}
```

- `kind`: `ill`, `injured`, `travel`. `span.end` null means ongoing until
  `status-days end`. `withdrawn`: null or `{"at": ts, "reason": "..."}`.
- Ids `s-NNNN`, never reused. Rows are never deleted; a wrong one is
  withdrawn.
- `status-days add --kind K --from D [--to D] --note TEXT [--source TEXT]`,
  `status-days end ID --date D`, `status-days withdraw ID --reason TEXT`,
  `status-days list [--active]`.
- `coach.statusdays.active(root, span) -> list[dict]` and
  `coach.statusdays.ill_in(root, span) -> bool` are the only readers
  other items call.
- Return rule: an `ill` status day overlapping the gap before a session
  counts exactly like an `ill` miss annotation for C22 and
  `return_after_illness`. Travel only explains the gap. Days off stay days
  off.
- Check `status_days_valid`: schema, unique ids, `start ≤ end`, at most one
  open-ended row per kind.

**Fixture instance `cardio/`** (R-43): a copy of `valid/` (keeping R-20's
logged workouts) with its activity, wellness and planned records removed,
plus:

- config: `[activity] enabled = true`; `[cardio] tier = "review"`,
  `weekly_run_distance = 18`, other caps default.
- activities (manual): 2026-09-21 run 10 km 60 min RPE 5; 2026-10-05 ride
  45 min; 2026-10-06 run "Intervals" 7 km 40 min RPE 8; 2026-10-07
  conditioning 20 min; 2026-10-09 run 11.5 km 70 min RPE 4.
- planned (manual): 2026-10-06 "Intervals" quality; 2026-10-08 "Long run"
  11 km; 2026-10-10 "Easy 5 km"; 2026-10-14 "Easy 5 km"; 2026-10-16
  "Tempo" quality.
- wellness (manual, daily asleep hours) 2026-10-05 to 2026-10-11: 6.5, 6.8,
  7.2, 6.0, 6.9, 7.5, 7.1.
- status days: `s-0001` ill 2026-10-01 to 2026-10-02; `s-0002` travel
  2026-10-15 to 2026-10-16.
- niggle `n-0001` left knee, `watching`, `applies_to.activity_kinds`
  `["run"]`.

## C51. Interference rules and conditioning sessions (R-44a, R-44b; R-25, R-46 read)

**Interference rules** (R-44a). Plugin kind `interference`
(`coach/plugins/interference/`):

```python
API = 1
KIND = "interference"
NAME = "same_day"
SUMMARY = "Lift first and keep at least six hours before a same-day quality activity."
PARAMS = {"schema": {...}, "defaults": {"min_gap_hours": 6, "lift_first": True}}
FLAGS = {}                      # instance plugins only, custom_ codes
CITES = ()                      # template research claim refs (C28)

def evaluate(ctx: InterferenceContext) -> list[dict]

@dataclass(frozen=True)
class InterferenceContext:
    mode: str                   # "logged" | "proposal"
    span: Span
    params: dict
    bouts: tuple[Bout, ...]     # C49, sorted by date then start
    heavy_lower: frozenset[str] # refs of lifting bouts that count as heavy lower under this rule's params
```

- Same purity rules as C23. Rules emit only `collision` (framework) or
  `custom_` codes (instance).
- The core computes `heavy_lower` per rule from the overlay lines
  (proposal) or resolved workouts (logged): a compound
  (`coach.patterns.is_compound`) `squat` or `hinge` exercise with a working
  set at RPE ≥ `heavy_rpe`, or with reps ≤ `heavy_max_reps` when no RPE.
- Easy activities (not quality, C48) never trigger a rule. Coach-led
  sessions count as lifting bouts for `same_day` and are never heavy lower.
- R-44a's program bump (C16 schema versions) adds the rules chosen for
  the program; migration adds the two framework rules with defaults. An
  empty list turns rules off. A rule the program lists but no plugin
  provides fails `program validate` (exit 1).

```json
"interference": [
  {"name": "same_day", "params": {"min_gap_hours": 6, "lift_first": true}},
  {"name": "quality_before_heavy_lower", "params": {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6}}
]
```

| Rule | Proposal mode | Logged mode |
|---|---|---|
| `same_day` | lifting or coach-led bout and a quality activity on one date → `collision` info ("same day: lift first, keep at least 6 h between") | gap between the earlier bout's end and the later's start < `min_gap_hours`, or (`lift_first`) the quality activity starts first → `collision` warn |
| `quality_before_heavy_lower` | quality activity on the date before a heavy-lower bout → `collision` warn | quality activity ending < `hours` before a heavy-lower bout starts → `collision` warn |

- `collision` messages name both bouts (title, date, time when known), the
  rule and the actual gap. The flag's `session_id` is the lifting session.
  The proposal step flags and never moves, drops or reorders anything.
- Rules run through an `interference` week-flag provider (C49), so they
  appear in `propose week` and `cardio flags` without edits to either.
- `interference list` shows the program's rules and params;
  `interference check` runs them alone for a span.

**Conditioning sessions** (R-44b). R-44b's program bump lets a session of
`kind: conditioning` carry `"scheme": {"name": "emom_density", "params":
{...}}`; migration adds `scheme: null` to every session. When set, every
exercise in the session uses scheme `hold` and the session scheme writes
their sets. Plugin kind `conditioning` (`coach/plugins/conditioning/`):

```python
def propose(ctx: ConditioningContext) -> ConditioningProposal
def decay(ctx: ConditioningContext, proposal: ConditioningProposal, days_off: int) -> ConditioningProposal

@dataclass(frozen=True)
class ConditioningContext:
    today: date; session_date: date; session_id: str
    exercises: tuple[ExerciseInfo, ...]   # program order
    params: dict; state: dict
    bouts: tuple[dict, ...]               # matched conditioning Activities, newest first:
                                          # {date, activity_id, duration_seconds, rpe}
    last_prescription: dict | None
    days_off: int

@dataclass(frozen=True)
class ConditioningProposal:
    lines: dict[str, tuple[SetSpec, ...]] # exercise_id -> sets (reps or duration; load from the slot)
    focus: str                            # one line, goes in the first exercise's Focus:
    rationale: str
    state: dict
    flags: tuple[dict, ...]
```

- `emom_density`: exercises alternate minutes in program order. Params
  `minutes` 10, `minutes_cap` 20, `minutes_step` 2, `reps` and `reps_cap`
  (per exercise id), `rpe_target` 7. Step up: the next exercise in turn
  below its rep cap gains one rep; when all are capped, minutes rise by the
  step up to the cap. Each exercise line gets one set per minute it owns.
- `circuit_rounds`: params `rounds` 3, `rounds_cap` 6, `time_cap_minutes`
  20, `reps` (per exercise id), `rpe_target` 7. Step up: one round. Each
  exercise line gets one set per round.
- Both: last matched bout's session RPE ≤ target (and, for circuits,
  duration ≤ time cap) → step up; RPE ≥ target + 2 or over the time cap →
  step back one; otherwise hold. No RPE → hold and `no_data`. No bout since
  the last prescription → hold. At the cap → hold with an info line "at
  cap: coach to change". Steps and caps are in `STATE`, so a step back
  restores the previous prescription exactly.
- Decay: 11–42 days off → one step back; 43+ → back to the params' start.
  Loads stay as written on the exercise (`hold`).
- State key `scheme_state["<session_id>/_session"]` (C23 v2 wrapper,
  promoted on approval like any scheme).
- A conditioning session's bouts come from `coach.cardio.match()` (C49)
  against conditioning Activities in the overlay span. Its Hevy workouts
  become Activities (C31) and are left out of dose, e1RM, exposures and
  exercise adherence (C17).
- Rendering: the first exercise's `Focus:` line carries the format, e.g.
  "EMOM 12 min, alternate minutes. Put 'RPE 7' in the workout
  description." C12 is otherwise unchanged.
- **Drop rule** (C24 step 5b): an optional conditioning session is removed
  from the draft when `sleep_debt` is active today, a status day (C50)
  covers its date, or keeping it would raise `quality_stack` with another
  planned quality bout. `data.dropped = [{session_id, date, trigger,
  reason}]`, and flag `conditioning_dropped` (info) names the reason. A
  core conditioning session is never dropped; it gets the same flag at
  warn instead. `cap_breach` is not a drop trigger. `propose restore`
  reverses one drop.
- R-44b adds no session to any instance; adding one is a program change
  under R-02's 80 % rule.

## C52. `coach status` (R-26b builds; later items add providers)

`status` answers "where does this instance stand right now" from local
files only. It never calls Hevy and never writes.

```python
# coach/status/<topic>.py
from coach.status import provider

@provider(id="overlay", owner="R-26b", order=30)
def overlay(ctx) -> Section | None: ...
# Section(id=str, lines=list[str], data=dict, level="info"|"attention")
# None when the provider has nothing to say (its source is absent).
```

- Providers are discovered with `pkgutil.iter_modules` over
  `coach/status/`, like checks (C13). An item adds a module; it never
  edits another provider or the registry.
- `lines` are plain sentences for a human, at most three per provider,
  loads only through `units.format_load`. `level` is `attention` when
  the coach should raise it in the first reply.
- A provider that raises is reported as one `attention` line
  ("<id>: unavailable (<error class>)") and the rest still run. A missing
  file or module drops its lines, not the command.
- Output: `data.sections` (in `order`), `data.instance`
  (`template`, `uninitialised` or `instance`) and `data.today`. The
  template repo is recognised by a `tests/` directory with no
  `profile.md`.

Providers R-26b ships:

| id | Says |
|---|---|
| `instance` | uninitialised (no `config.toml` or no `profile.md`): "run /setup"; files behind their schema version: "run python3 -m coach migrate run" |
| `checks` | the `coach check` summary and the ids of any `fail` or `warn` |
| `hevy` | cache age against `[hevy] cache_max_age_hours`; skipped when Hevy is disabled |
| `overlay` | the overlay in force today (id, kind, span), whether it is approved, pushed and verified (from `writes.jsonl`), the next one or two planned sessions, and whether any day of the coming week has no overlay |
| `program` | rotation position and whether it is confirmed (from R-25's `header_facts` when present, else C16 `state.json`); hard weeks completed and deload status (`state.json`) |
| `checkin` | last check-in, days since, due date, tier and mode (`first`, `weekly`, `deep`, `catch_up`) from R-25's `header_facts`; before R-25 merges, the newest record in `check-ins/` and "due" at 7 or more days |

Later items add a provider when they own a fact the coach should see at
session start: R-21b (next check-in runs in catch-up mode), R-23a (an
unfinalised proposal draft), R-27 (follow-ups due, aggravated niggles),
R-31 (light week proposed), R-32a (expired research notes), R-33a
(nutrition override expiring), R-42a (source sync age).

Once R-25 merges, the `checkin` and `program` providers read
`coach.pages.header_facts` (C38) and stop computing those facts
themselves; whichever of R-25 and R-26b merges second makes that switch.
`status` passes `as_of` = now.

## C53. Session hooks (R-26b; R-15 owns the `PreToolUse` hook)

`.claude/settings.json` gains two hook entries next to R-15's
`PreToolUse` gate. Both run `cd "$CLAUDE_PROJECT_DIR" && python3 -m coach
hooks <event>` (hooks start in Claude's current directory, which may not
be the instance root), read the hook JSON on stdin, print a hook
response JSON or nothing, and **always exit 0**. Neither needs an allow
rule (hooks run outside the permission layer); `status` gets one. R-15's
`PreToolUse` entry uses the same `cd` form.

- **`hooks sessionstart`** (all session sources: `startup`, `resume`,
  `clear`, `compact`). Prints
  `{"hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "<text>"}}`, where the text is the `status`
  lines, `attention` first, at most 12 lines and about 1,000
  characters, ending "Detail: python3 -m coach status". In the template
  repo it prints nothing. On any failure, including Python older than
  3.11, it prints one line saying the coach scripts are unavailable and
  why.
- **`hooks posttooluse`** (matcher `Write|Edit`; hand edits only, since
  `coach` commands validate their own output). Reads
  `tool_input.file_path`, makes it relative to the root (it may arrive
  absolute) and looks it up in the path map:

  | Path | Checks run (`check --only`) |
  |---|---|
  | `config.toml` | config |
  | `data/exercises.json` | R-11's library checks |
  | `data/program.json`, `data/state.json` | R-17a's program and state checks |
  | `routine/*.md` | `routine_render_fresh` |
  | `data/overlays/*.json` | R-13's overlay checks, `load_caps`, `dangling_exercise_ids` |
  | `check-ins/*.md` | `overlay_render_fresh`, `bare_hevy_values` |
  | `profile.md` | `bare_hevy_values` |

  Any `fail`: `{"decision": "block", "reason": "<path> failed <id>:
  <message>. Fix the data file or re-render; don't leave it."}`, which
  reaches the coach next to the tool result (the edit has already
  happened; the hook cannot undo it). `warn` only: the same text as
  `additionalContext`. All pass, an unmapped path, or a hook error:
  nothing on stdout (errors get one `coach:` line on stderr). Only
  checks that read local files are mapped.
- The path map lives in `coach/hooks.py`, built on C13's `--only`, so no
  item edits the check registry. An item that adds a data path in C6 adds
  its row to the map in its own PR. A test asserts every mapped check id
  is registered.

## C54. Profile facts (R-10, R-11 own; R-17a, R-20, R-22, R-23a, R-24, R-30a, R-40a, R-41a, R-41b read)

Rule (ADR-0001): a profile fact that a script reads is config or data;
prose in `profile.md` is only what a human reads.

| Fact | Where | Owner |
|---|---|---|
| experience, available training days, default session length | `[athlete] experience`, `available_days`, `session_minutes` (C4) | R-10 |
| equipment at the main place and at other places | `[equipment]`, `[equipment.locations.<name>]` (C4) | R-10 |
| which place a session or a one-off week uses | session `location` in `program.json` (C16) and the overlay (C10) | R-17a, R-13 |
| per-session time caps | `[sessions.cap_minutes]` (C19) | R-20 |
| coach-led sessions | `program.external_sessions` (C16) | R-17a |
| injuries and lasting limitations | niggles, `chronic` for a permanent one (C27) | R-27 |
| exercises the athlete cannot or will not do | `avoid` in the instance library (below) | R-11 |
| nutrition strategy | `[nutrition]` (C4, which also lists what stays prose) | R-33a |

Stays prose: the goal narrative, height, age, recovery habits, food
preferences and the coach's notes.

**Equipment resolver.** `coach.config.equipment_for(config, location=None)
-> dict` is the one resolver: the main `[equipment]` table with the named
location's keys laid over it. An unknown location is a config error
naming it. Every reader of equipment calls it: R-24 (caps and
representable loads, C22), R-23a (caps and rounding), R-41b (substitution
in `starters draft`), R-40a, `config suggest`.

**Readers of the other keys.**

- `session_minutes`: the default session cap; `[sessions.cap_minutes]`
  overrides it for a session id (C19). R-20's readers fall back to it.
- `available_days`: R-41b `starters draft` default days, R-30a's
  smaller-schedule proposal, R-22 `shift` rules (a shift never lands on a
  day outside `available_days` when it is non-empty, C37), R-40a.
- `experience`: R-41b starter recommendation, R-40a.

**Avoided exercises** (R-11). Instance library entries
(`data/exercises.json`) may carry `"avoid": null | {"reason": "non-empty
text"}`. Commands: `library set-avoid ID --reason TEXT`, `library
set-avoid ID --clear` (W, `--dry-run`), `library list --avoided`.

- R-41b `starters draft` and R-41a `program adopt` treat an avoided
  exercise like missing equipment: substitute and report.
- R-17a adds a warn check `avoided_in_program` when an active program slot
  uses one.
- The proposal step never swaps exercises; swaps stay the coach's call.

---

## Build order and ownership

Phase 1:

| Item | Depends on | Notes |
|---|---|---|
| R-10 | nothing | Owns the shared files in C1, the check registry (C13) and the Python and config checks. Defines the profile-fact keys (C4, C54). |
| R-11, R-12, R-13 | R-10 | Can be built in parallel. R-13 owns `overlay approve` and the approval hash (C10). R-11 owns `avoid` (C54). |
| R-14 | R-12, R-13 | Enforces approval; does not build it. |
| R-17a | R-11 | Program and state schemas, renderer, migration runner. Owns the `avoided_in_program` check (C54). |
| R-15 | R-14 | The permission layer only: allowlist and `PreToolUse` hook. |
| R-16 | R-11, R-12, R-13, R-14 | Cross-cutting checks only; each item registers its own checks. |
| R-17b | R-17a, R-11, R-12, R-13, R-14, R-26a | Bootstrap migration of a real instance, run with the athlete. |

Phases 2 to 4 (issue numbers in brackets; "human" items need the
athlete's instance, a real key, a live session or a purchase):

| Item | Depends on | Notes |
|---|---|---|
| R-14b (#51) | R-14, R-15, R-17a | `routines create`, gated like push. Before R-26a. |
| R-26a (#52) | R-14b, R-15, R-16, R-17a | Skills call the Phase 1 commands. Before R-17b runs, and before R-20, R-23a and R-24 merge. |
| R-26b (#53) | R-15, R-16, R-17a | `coach status` and session hooks (C52, C53). Parallel with R-26a. |
| R-26b follow-up (#54) | R-26b | Human: verify the hooks in a live session. |
| R-20 (#16) | R-11, R-12, R-13 | History, stats, session caps, flag registry (C17–C20). Merges after R-26a (it rewires skills R-26a also edits). |
| R-24 (#20) | R-11, R-13, R-17a, R-20 | Overlay v2 and validity (C21, C22). Lands before R-23a. Merges after R-26a (it rewires skills R-26a also edits). |
| R-23a (#19) | R-17a, R-20, R-24 | Plugins, proposal pipeline, decisions, load constraints (C23–C26); program and state v2. Merges after R-26a (it rewires skills R-26a also edits). |
| R-23b (#37) | R-23a | Remaining schemes and schedule rules. |
| R-27 (#23) | R-17a, R-23a | Follow-ups and niggles (C27). |
| R-21a (#17) | R-13, R-14, R-17a, R-20 | Card, records, skeleton (C36). |
| R-21b (#49) | R-21a, R-23a | Catch-up mode and the return brief (C36). |
| R-22 (#18) | R-13, R-14, R-17a, R-23a | Missed-day rules (C37); program and overlay bumps; builds the C23 `fold` filter. |
| R-25 (#21) | R-13, R-17a, R-20, R-21a | Pages and publishing (C38). Parallel with R-21b and R-24. |
| R-32a (#26) | R-10 | Research notes and commands (C28). Parallel with Phase 1. |
| R-32b1 (#44), R-32b2 (#45), R-32b3 (#46) | R-32a; b2 also R-02, b3 also R-06 | Seed notes. Parallel with each other. |
| R-32c (#47) | R-32b1, R-32b2, R-32b3, R-02, R-06 | Coaching principles rewritten against the notes. Before R-26. |
| R-26 (#22) | R-26a, R-20, R-21a, R-21b, R-22, R-23a, R-24, R-25, R-32c; R-27 either order | needs-info. Skill merge and `CLAUDE.md` shrink; last in Phase 2. |
| R-30a (#24) | R-17a, R-20, R-23a | Dose targets and structure accounting (C40, C41). |
| R-30b (#48) | R-30a, R-22 | Priority lifts and the minimum week (C40). |
| R-31 (#25) | R-17a, R-23a, R-27, R-30a | Block ledger and light weeks (C42, C43); state bump. Not parallel with R-30b. |
| R-33a (#41) | R-10, R-06 | Nutrition config and readings (C4, C35). R-21a and R-25 depend on it softly. |
| R-33b (#42) | R-10, R-04 | Recipe cards (C33). Parallel with R-33a. |
| R-33c (#43) | R-33a, R-33b | Meal plans (C34). |
| R-33d (#27) | R-33a, R-33b, R-33c, R-17b | Human: move the reference instance's nutrition onto the new formats. |
| R-42a (#30) | R-10, R-11, R-12 | Activity store, sync map, manual and Hevy-conditioning adapters (C29–C32). Parallel with Phases 2 and 3. |
| R-42b (#38) | R-42a | Health Auto Export adapter from the documented format. |
| R-42c (#39) | R-42b | Human: real export check and 90-day backfill. |
| R-42d (#40) | R-42a | needs-info. Runna calendar-feed adapter for planned activities. |
| R-43 (#31) | R-42a, R-20, R-23a, R-27 | Cardio config, bouts, reconcile, flags, status days (C48–C50). |
| R-43b (#55) | R-43, R-42c, R-32a | needs-info. Resting-HR trend flag. |
| R-44a (#32) | R-17a, R-23a, R-43 | Interference rules (C51). Before R-44b. |
| R-44b (#56) | R-44a, R-43, R-42a, R-23a | Conditioning sessions and density schemes (C51). |
| R-45 (#33) | R-12, R-15, R-21a, R-21b | Scheduled draft and nudge, read-only mode (C39). |
| R-45 follow-up (#50) | R-45, #35 | Human: install and verify the scheduled run. |
| R-40b (#58) | R-23a, R-26a, R-30a, R-31 | Run mode (C44). |
| R-40c (#59) | R-13, R-20, R-25, R-26a | Training without Hevy (C46). Can land before Phase 3. |
| R-41a (#29) | R-11, R-12, R-14b, R-17a, R-23a, R-26a | Program drafts, adoption, Hevy import (C45). |
| R-41b (#57) | R-41a, R-23b, R-30b | Starter programs (C45). |
| R-40a (#28) | R-26a, R-41a, R-41b, R-33a, R-40b | Onboarding: config, six-question profile, program pick. Reads R-42a's `[activity]` when merged. |
| R-40d (#60) | R-40a, with R-40b, R-40c, R-41a, R-41b | Human: live onboarding trial. Last of R-40. |
| R-46 (#34) | R-42a, R-43, R-44a, R-32a, R-23a, and a maintainer go-ahead | needs-info. Program tier for running. |
