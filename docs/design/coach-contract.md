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
  program.py, state.py, migrate.py, migrations/<doc>/{__init__,NNNN_<slug>}.py           (R-17a)
  program_drafts.py          # import_hevy and adopt; reads stats and routines, which import program.py (R-41a)
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
  status/__init__.py         # status provider registry + auto-discovery                 (R-26b)
  status/<topic>.py          # one module per item that adds status lines                (R-26b and later items)
  hooks.py                   # SessionStart and PostToolUse hook logic                   (R-26b)
  workspace.py               # template vs athlete-copy identity from local Git          (C52)
  research.py                # research notes, claim refs, citation scan                 (R-32a)
  structure.py               # dose targets, structure accounting, priority, minimum week (R-30a, R-30b)
  block.py                   # block ledger, light weeks, status line                    (R-31)
  nutrition.py               # nutrition config, readings, status                        (R-33a)
  protein.py                 # protein reference mass, floor, target, stretch            (R-33a)
  calories.py                # no-app starting calorie estimate per phase                (R-33a)
  recipes.py                 # recipe cards, index, import                               (R-33b)
  meals.py                   # meal plans, shopping list                                 (R-33c)
  log.py, sheets.py          # manual log and session sheets                             (R-40c)
  starters.py                # starter programs                                          (R-41b)
  onboarding.py              # `config suggest` values and notes                         (R-40a)
  starters/<id>.json         # framework starter programs                                (R-41b)
  activity/store.py          # ActivityStore: resolved activities, planned, wellness     (R-42a)
  activity/adapters/<name>.py  # one module per activity source                          (R-42a, R-42b, R-42d)
  cardio.py                  # weekly load, bouts, reconcile, cardio flags               (R-43)
  interference.py            # program rules, heavy lower, lead-in days, emitted-code check (R-44a)
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
  envelope=True)` on a function `(args, ctx) -> dict` that returns the
  envelope's `data`. A Claude Code hook command (`gate pretooluse`, R-26b's
  `hooks` commands) declares `envelope=False`: the CLI prints the dict it
  returns as the hook response, or nothing for None, and exits 0 (C3, C53). A one-word name is a top-level command (`check`,
  `version`). The helper adds `--dry-run` to every command with `writes`,
  `hevy_write` or `git_write`, and `Command.metadata()` gives the four
  flags R-15 reads. `ctx` is `coach.context.Context`.
- Every command module declares, per command: `writes` (touches local
  files), `hevy_write` (sends a non-GET request to Hevy), `network` (calls
  Hevy at all) and `git_write` (commits or pushes; R-25). R-15's allowlist
  test reads this metadata. A `git_write` command stays off the allowlist
  unless it refuses to run without an approved overlay; `pages publish`
  (C38) is the only one.
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
- Each owner adds its read-only and local-write commands to the R-15
  allowlist in its own PR and says so. The allowlist is
  `permissions.allow` in `.claude/settings.json`: one prefix rule per
  command, `Bash(python3 -m coach <group> <command>:*)` (`check` and
  `version` have one word), never a group or broader prefix.
  `tests/test_gate.py` asserts every rule names a registered command with
  `hevy_write` false and `git_write` false (`pages publish` excepted),
  and that no rule matches a `hevy_write` command. It also checks that every
  eligible registered command has its exact rule, so new commands cannot be
  omitted. Hooks (`envelope=False`), `hevy record-fixtures` and `plugins test`
  stay off the allowlist (the latter runs instance code). `pages publish`,
  `program import-hevy`, `program adopt` and `starters` are allowlisted. Commands marked
  H stay behind the R-15 gate.
- The gate distinguishes a known Hevy write whose dry-run summary failed
  from a command whose effects cannot be determined. Unreadable commands
  ask for review, or are denied in bypass-permissions mode, with guidance
  to use individual direct commands. Malformed hook input follows the same
  conservative policy when its permission mode is readable. Disabling Hevy
  does not bypass protection for unknown effects or direct external writes.

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
| `library seed`, `library confirm`, `library set-mode`, `library set-avoid`, `library create ID --input FILE [--dry-run]` | R-11 | W |
| `hevy status` | R-12 | |
| `hevy pull [--full]` | R-12 | W (gitignored cache only) |
| `hevy record-fixtures --out DIR` | R-12 | W (GET only, needs a real key) |
| `overlay list`, `overlay current [--date D]`, `overlay validate [ID \| --file PATH]` (no argument: every overlay), `overlay notes ID [--session S]` | R-13 | |
| `overlay build --input FILE`, `overlay render ID [--into FILE]`, `overlay approve ID` | R-13 | W |
| `routines diff --overlay ID [--refresh]`, `routines verify --overlay ID [--refresh]` | R-14 | W with `--refresh` (gitignored cache only) |
| `routines push --overlay ID [--refresh]`, `routines retire --overlay ID [--refresh]` | R-14 | H |
| `routines create --overlay ID [--dry-run]` | R-14b | H |
| `gate pretooluse` | R-15 | |
| `program show`, `program validate`, `state show`, `migrate status` | R-17a | |
| `program render`, `migrate run` | R-17a | W |

Phase 2 to 4 command inventory. No command here writes to Hevy.

| Command | Owner | |
|---|---|---|
| `history show [--since D] [--until D] [--include-unsynced]`, `history annotations [--kind K] [--all]` | R-20 | |
| `history sync`, `history rebuild --month YYYY-MM`, `history annotate ...` | R-20 | W |
| `stats e1rm [--exercise ID] [--since D]`, `stats adherence (--overlay ID \| --span A..B)`, `stats dose (--week W \| --span A..B)`, `stats durations [--week W \| --span A..B]`, `stats audit [--weeks N]`; each takes `--include-unsynced` | R-20 | |
| `prescription check (--overlay ID \| --file PATH)` | R-24 | W with `--write` |
| `plugins list`, `plugins show NAME`, `plugins validate` | R-23a | |
| `plugins test` | R-23a | runs instance plugin tests; never allowlisted |
| `schedule plan --week W`, `decisions list`, `propose show ID` | R-23a | |
| `schedule confirm --position P`, `propose week`, `propose override`, `propose resolve`, `propose finalize`, `decisions withdraw ID` | R-23a | W |
| `propose restore --proposal ID --session S --reason TEXT [--dry-run]` | R-44b | W |
| `followups list`, `followups render`, `niggles list`, `niggles constraints` | R-27 | |
| `followups add\|resolve\|drop\|defer`, `niggles add\|update\|resolve\|import` | R-27 | W |
| `checkin prepare [--until D] [--tier weekly\|deep]`, `checkin misses [--since D] [--until D]`, `checkin due` | R-21a | |
| `checkin skeleton --date D [--tier T] [--overlay ID] [--refresh]` | R-21a | W |
| `checkin return-brief (--proposal ID \| --overlay ID) --reason R` | R-21b | |
| `checkin tag-gap --tag T` | R-21b | W |
| `missed list [--date D]`, `missed plan --session S --date D`, `missed rules` | R-22 | |
| `missed apply --session S --date D [--tag T]` | R-22 | W |
| `pages show KIND` | R-25 | |
| `pages render [--only brief\|dashboard\|progress] [--replace-readme]` | R-25 | W |
| `pages publish --overlay ID [--record D]` | R-25 | W, G |
| `status` | R-26b | |
| `hooks sessionstart`, `hooks posttooluse` | R-26b | |
| `research status [--area AREA] [--kind template\|local] [--expired]`, `research show REF`, `research cites [--unresolved]`, `research validate` | R-32a | |
| `research render [ID]` | R-32a | W (the rendered region only) |
| `structure week --week W`, `structure adherence [--until D]`, `structure balance [--program FILE] [--variant minimum]` | R-30a | |
| `structure decide --rule restructure\|add_session --outcome adopted\|declined\|deferred [--reason T] [--revisit D]` | R-30a | W |
| `structure priority [--since D]`, `structure minimum --week W` | R-30b | W with `--write` |
| `block status` | R-31 | |
| `block close --week W [--readiness poor\|ok] [--sleep poor\|ok] [--deep]`, `block decide --outcome adopted\|declined [--type deload\|light\|return] [--week W] [--reason T]`, `block init --hard-weeks N [--through W] [--started D] [--reason T]` | R-31 | W |
| `nutrition status`, `nutrition readings [--last N]` | R-33a | |
| `nutrition targets [--bodyweight X] [--goal-weight X] [--body-fat PCT --body-fat-source credible\|rough] [--sex male\|female] [--height N [--height-unit cm\|in]] [--recent-intake G] [--app macrofactor\|none] [--age N] [--activity sedentary\|active\|vigorous] [--phase PHASE:RATE]...` | R-33a | |
| `nutrition record`, `nutrition import --input FILE` | R-33a | W |
| `recipes list`, `recipes show`, `recipes validate`, `recipes import --html FILE`, `recipes draft --input FILE` | R-33b | |
| `recipes render [SLUG]`, `recipes convert (--parse \| --apply --input FILE)` | R-33b | W (`--parse` writes nothing; one command, so it carries `writes`) |
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

stdout carries exactly one JSON object per run, UTF-8, followed by a newline
(a hook command declared with `envelope=False`, C2, prints a hook response
or nothing instead):

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
| 3 | `refused` | A write was refused by a guard | no approval, hash mismatch, unresolved `block` flag, routine changed in the app since the diff, overlay expired |
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
  marked `optional=True` stays absent when the file leaves it out. A key
  declared `Key("list", table=Table(...))` is an array of tables
  (`[[name]]`), each item validated like a table, its path written
  `nutrition.anchors[0].name` (R-33a). Whether nutrition is on is
  `coach.nutrition.enabled(config)`, not `"nutrition" in config`: a
  `[nutrition]` table holding only `[nutrition.bank]` leaves it off.
- **Rules across keys** (R-42a, R-33a): a `config_tables` module may also
  export `RULES`, a list of functions that take the validated config and
  return `[(key path, message)]`. They run once every table is valid, and
  their problems exit 5 like any other. R-42a's rule checks `[activity]
  precedence` against the enabled sources (C32); R-33a's check the
  `[nutrition]` cross-key rules (C4).
- `coach.config.load(root, today=None) -> Config`. `Config` is a dict with attribute
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
experience = "intermediate"   # current level, explicitly confirmed during setup
# birth_year = 1980           # optional positive whole year, not in the future
# desired_sessions = 4        # optional weekly session target, 1..7; not availability
demonstrated_exercises = []   # catalogue ids with "ability": "demonstrated" the athlete has shown (C45)
available_days = []       # weekday ids "mon".."sun"; empty = not stated
session_minutes = 60      # default time cap per session; 0 = no cap; [sessions.cap_minutes] overrides (C19)

[hevy]
enabled = true
cache_max_age_hours = 24  # coach check warns past this

[equipment]               # the main place the athlete trains; all in athlete units
available = []            # R-11 equipment enum values; empty = every piece assumed
apparatus = []            # R-11 apparatus enum values; empty with available empty = every piece assumed
dumbbells = []            # per-hand dumbbell weights available; empty = not checked
dumbbell_increment = 2.0  # per hand
dumbbell_max = 40.0       # per hand; a cap
barbell_increment = 2.5   # smallest total jump
bar_weight = 20.0
plates = [25, 20, 15, 10, 5, 2.5, 1.25]   # per side, pairs available
machine_increment = 5.0
cable_increment = 2.5

[equipment.locations.home]  # optional; any number of named places (name ^[a-z0-9-]+$)
available = ["dumbbell", "band", "bodyweight"]
dumbbells = [5, 10, 15, 20] # any [equipment] key may appear; it overrides the main table at this place
dumbbell_max = 20.0         # a place that sets available and no apparatus has none (equipment_for, C54)

[caps]                    # optional: library exercise id = max load, athlete units
                          # (per hand for per-hand modes, total otherwise)
```

Tables later items add, each in its own PR:

| Table | Owner | Defined in |
|---|---|---|
| `[sessions]` | R-20 | C19 |
| `[checkin]` | R-21a | below |
| `[nutrition]` and its subtables | R-33a, R-33b, R-33c | below |
| `[coaching]` | R-40b | C44 |
| `[activity]`, `[sources.<name>]` | R-42a; each adapter adds its own source table | C32 |
| `[cardio]` | R-43 | C48 |

```toml
[checkin]                   # R-21a
cadence_days = 7            # days between check-ins; the due date is the last record's date + this
```

**Nutrition keys** (R-33a, R-33b, R-33c). Nutrition is enabled only by
`[nutrition] enabled = true`. An absent table, `enabled = false`, or a
table holding only `[nutrition.bank]` means disabled. A table that sets
any R-33a key (`app`, `phase`, `target_rate_per_week`, `goal_weight`,
`kcal_target`, `[nutrition.protein]`, anchors or `[nutrition.override]`)
must say `enabled`, so the numbers are never silently ignored. With
`enabled = true`, `app`, `phase`, `target_rate_per_week` and
`[nutrition.protein]` are required. Rules across keys (R-33a `RULES`):
`kcal_target` with `app` other than `"none"` is an error at
`nutrition.kcal_target`; `floor_g <= target_g <= stretch_g`; an
override's `expires` is after `start` and at most 21 days after it;
`renewal` is 0, 1 or 2; an anchor names at least one day. Weights are
in `[athlete] bodyweight_units`. R-33c's rules: an anchor gives `kcal`
and `protein_g`, or `recipe` (a card slug), not both; a standing row
sets exactly one of `recipe`, `pool` or `cover`, a cover row carries
`kcal` and `protein_g` and no other row does; with a template, every
standing row's and anchor's `slot` is one of its `slots`; and two
standing rows whose days meet (`daily` is every day, `office` the
`office_days`, `home` the rest) may not fill the same slot, an error at
the later row that names both. `[nutrition.template]` defaults: `slots`
the four below, `office_days` and `staples` empty, `kcal_tolerance_pct`
15, `shopping_issue` false, `standing` empty; `plan_style` has no
default value in config (C34 says how the plan picks one).
No key holds a calorie figure the nutrition app owns. All three items
declare their keys in one module, `coach/config_tables/nutrition.py`
(R-33b created it with `[nutrition.bank]`; R-33a and R-33c add theirs to
it). The recipe bank works with nutrition disabled: with no
`[nutrition.bank]` table, `coach.recipes.bank_settings(config)` returns
the defaults below. `min_protein_per_100kcal` keeps its four defaults
for any slot left out and accepts other configured slots;
`slot_notes` keys are slots. The slots come from `[nutrition.template]
slots`, which defaults to `breakfast`, `lunch`, `dinner`, `snack`.

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
| staples, office days, standing coverage, plan style (R-33c) | food likes, dislikes, allergies/intolerances, cooking appetite, shopping pattern |
| — | sleep-gate status and reasoning (until an activity source, C29) |
| — | the MacroFactor setup summary and revision notes |

Before the first `/meal-plan` setup, the athlete's answers for the R-33c
row sit in `profile.md` → Food & eating as prose that no script reads.
The approval that writes `[nutrition.template]` replaces them with a
pointer line, so those facts are never in both places; later changes are
template edits. `reference/record-formats.md` → "profile.md: Food &
eating" defines the fields, the grouped interview and the mapping.

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
  `format_number(value)` (R-41a) prints a bare number the same way.
- `format_load(load, show_hevy=True)` (R-40c; R-41a's import report uses it too). With `show_hevy` false,
  `per_hand_x2` prints `25/hand`, `single_implement` prints `25`, and
  `assisted` prints `BW-20 assist`. Renderers pass `config.hevy.enabled`;
  `units format --no-hevy` sets it false.
- Enforced by an AST test (R-10): no `coach/**/*.py` other than
  `coach/units.py` contains a multiplication by the constant 2, 2.0 or 0.5,
  a division or floor division by 2 or 2.0 (including augmented
  assignment), or the literals `0.45359237` or `2.20462`. The test carries
  an explicit allowlist of `(path, source line)` pairs, empty at the start;
  extending it means editing the test, which shows in review.

**Exercise library (R-11).** The catalogue `coach/catalogue/exercises.json`
(schema `exercise_catalogue`) ships with the framework. The instance
library `data/exercises.json` (schema `exercise_library`) belongs to the
athlete and sync never touches it. `coach.library.Library.load(root)`
merges them; with no instance file the catalogue stands alone.

- Catalogue entry: `id`, `name`, `aliases[]`, `hevy_titles[]`,
  `hevy_template_ids[]`, `muscles {primary[], secondary[]}`, `pattern`,
  `equipment`, `load_mode_default`, `increment {kg, lb} | null`,
  `substitutes[]`, and optionally `requires[]` and `ability`, which
  only the catalogue carries (an instance entry cannot set them; a custom
  entry has `requires: []` and `ability: null`). `requires` lists the
  apparatus an exercise needs beyond its equipment; `ability:
  "demonstrated"` marks an exercise an athlete must have shown they can
  do before a swap picks it (C45). The catalogue is schema v3 and
  carries no migration (C7). Enums, agreed in triage:
  - `pattern`: `squat`, `hinge`, `lunge`, `horizontal_push`,
    `vertical_push`, `horizontal_pull`, `vertical_pull`, `elbow_flexion`,
    `elbow_extension`, `shoulder_raise`, `knee_flexion`,
    `knee_extension`, `hip_abduction`, `hip_adduction`, `calf_raise`,
    `core`, `carry`, `conditioning`.
  - Muscles: Hevy's muscle groups with `shoulders` split into
    `front_delts`, `side_delts` and `rear_delts`: `abdominals`, the three
    delts, `biceps`, `triceps`, `forearms`, `quadriceps`, `hamstrings`,
    `calves`, `glutes`, `abductors`, `adductors`, `lats`, `upper_back`,
    `traps`, `lower_back`, `chest`, `cardio`, `neck`, `full_body`,
    `other`.
  - `equipment`: `barbell`, `ez_bar`, `trap_bar`, `dumbbell`,
    `kettlebell`, `machine`, `smith_machine`, `cable`, `plate`, `band`,
    `suspension`, `bodyweight`, `cardio_machine`, `other`.
  - Apparatus (`library.APPARATUS`): `flat_bench`, `incline_bench`,
    `pull_up_bar`, `dip_station`, `nordic_anchor`, `box` (a sturdy box,
    step or chair). A listed bench also serves as a `box`.
- `increment` is the entry's progression step in each unit: per hand for
  the per-hand modes, the total otherwise, null for `band`, `duration`
  and `distance`. `Library.increment(id, unit)` returns null when the
  entry has none; the caller then uses the equipment increment from
  `equipment_for` (C54).
- Instance file, keyed by library id:

  ```json
  {"schema_version": 1, "exercises": {
    "db_bench_press": {"hevy_template_id": "F0000002", "load_mode": "per_hand_x2",
                       "load_mode_proposed": "per_hand_x2", "confidence": "high", "avoid": null},
    "custom_tyre_flip": {"name": "Tyre Flip", "muscles": {"primary": ["full_body"], "secondary": []},
                         "pattern": "conditioning", "equipment": "other", "load_mode_default": "total",
                         "hevy_template_id": "C0000001", "load_mode": null}}}
  ```

- **Merge rule.** An instance entry for a catalogue id overrides each
  catalogue field it carries, whole: a list or object replaces the
  catalogue's, it never merges into it. An id the catalogue lacks starts
  `custom_` and must carry `name`, `muscles`, `pattern`, `equipment` and
  `load_mode_default`; its other catalogue fields default to empty lists
  and a null increment.
- Instance-only fields, all optional and nullable: `hevy_template_id`
  (the athlete's Hevy template, added to the merged
  `hevy_template_ids`), `load_mode` (confirmed by the athlete),
  `load_mode_proposed` and `confidence` (`high` | `low`, written by
  `library seed`), and `avoid` (C54).
- **Effective load mode** is the confirmed `load_mode` only.
  `Library.effective_load_mode(id)` returns null until the athlete
  confirms; `load_mode_default` and `load_mode_proposed` never stand in
  for it.
- **Local creation.** `library create ID --input FILE` (W, `--dry-run`)
  accepts one existing instance-entry object, requires every custom field
  above and a non-null confirmed `load_mode`, and creates only a new
  `custom_` id. It refuses `hevy_template_id`, `hevy_template_ids`,
  `load_mode_proposed`, `confidence` and `avoid`: those come from separate
  steps. A conflicting existing custom id fails before any other check; the
  schema and merged-library checks then run before the atomic write.
  Catalogue collisions and conflicts fail without changes; an identical
  retry succeeds with `unchanged: true` and `written: false`. Output
  includes the proposed merged `exercise`, `path`, `unchanged` and
  `written`; dry-run writes nothing. No required facts or Hevy ids are
  guessed. Local creation does not establish Hevy readiness: a real
  template mapping is a separate requirement when Hevy is enabled.
  The search, review and approval workflow is in
  `reference/custom-exercises.md`.
- **Match key.** Names are compared lower-cased, punctuation dropped,
  `db`, `bb` and `kb` spelled out, words sorted, so "Bench Press
  (Dumbbell)" and "dumbbell bench press" are the same name.
- Validation exits 1 with a JSONPath per problem: the schema, then an
  unknown id without `custom_`, a custom entry missing a required field,
  a substitute that is not another library id, a name, alias or Hevy
  title that already names another entry (by match key), and a Hevy
  template id on two entries.
- Readers: `get(id)` (the merged entry plus `source` `catalogue` |
  `custom`, `overridden` and `effective_load_mode`),
  `by_hevy_template_id(tid)`, `search(text)`, `effective_load_mode(id)`,
  `increment(id, unit)`, `avoided(id)`.

**Seeding** (`library seed [--dry-run]`). It reads the C8 cache's
`routines.json` and `exercise_templates.json`; with no cached routines it
exits 5 naming `hevy pull`. For each distinct `exercise_template_id`, in
routine order, it finds a library entry by template id, then Hevy title,
then alias or name (both by match key), and proposes a load mode from the
first row that applies:

| Rule | When | Proposed | Confidence |
|---|---|---|---|
| `hevy_type` | Hevy type `duration`, `distance_duration`, `bodyweight_assisted_reps`, `bodyweight_reps` or `reps_only` | `duration`, `distance`, `assisted`, `bodyweight`; `reps_only` gives `band` for band equipment, else `bodyweight` | high; low when a matched entry's default differs |
| `alternating` | dumbbell or kettlebell, and the title says alternating | `single_implement` | high |
| `one_arm` | dumbbell or kettlebell, and the title says single arm or one arm | `single_implement` | high |
| `custom` | matched a custom entry | its `load_mode_default` | low |
| `matched` | matched by template id or Hevy title | the entry's `load_mode_default` | high when it fits Hevy's equipment, else low |
| `alias` | matched by alias or name only | the entry's `load_mode_default` | low |
| `equipment` | no match | dumbbell `per_hand_x2`, kettlebell `single_implement`, band `band`, none or suspension `bodyweight`, anything else `total` | low |

A mode fits Hevy's equipment when: dumbbell or kettlebell and a per-hand
mode; barbell or plate and `total`; machine and `total` or `assisted`;
none and `bodyweight`, `assisted`, `duration` or `distance`; band and
`band`. Other and suspension fit any mode.

- A matched entry gets `hevy_template_id` (or one more
  `hevy_template_ids` item when it already has one), `load_mode_proposed`
  and `confidence`. An entry with a confirmed `load_mode` keeps it.
- No match makes a `custom_<slug of the title>` entry from the template:
  name and Hevy title from its title; muscles from Hevy's groups
  (`shoulders` becomes rear, side or front delts by the title); equipment
  mapped (`none` to `bodyweight`, `resistance_band` to `band`, a cardio
  machine to `cardio_machine`); pattern guessed from the primary muscle
  group. `data.guessed` lists each one for the coach to check.
- Output: `data.proposals[]` with `hevy_template_id`, `hevy_title`,
  `routines`, `matched_id`, `matched_by` (`template_id` | `hevy_title` |
  `alias` | `custom`), `load_mode_proposed`, `confidence`, `rule` and
  `action` (`created` | `updated` | `unchanged` | `confirmed`).
- Confidence tells the coach which proposals to put to the athlete; it
  never confirms anything. `library confirm (IDS | --all)` copies
  `load_mode_proposed` to `load_mode`; `library set-mode ID MODE` records
  the athlete's answer directly, and an invalid mode exits 1 listing the
  eight.
- Checks: `library_valid` (catalogue and instance file validate; one
  `fail` per problem, with its JSONPath) and `load_modes_confirmed`
  (every exercise in the cached Hevy routines and in every overlay has a
  confirmed load mode; a routine exercise whose template id no entry
  holds fails naming `library seed`).

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
| `.coach/backups/<UTC timestamp>/` | pre-migration copies; old recipe cards and index before conversion | gitignored | R-17a; R-33b (`recipes convert --apply`) |
| `.coach/proposals/<id>.json`, `<id>.proposed.json`, `<id>.meta.json` | editable proposal draft (an overlay draft, C10), its untouched original, and the run's facts (kind, span, transform, rotation, each slot's proposed scheme state) | gitignored | R-23a |
| `.coach/plans/<week start>-<name>.json` | schedule plans handed to `propose week --plan` | gitignored | R-30b; R-22 may |
| `.coach/drafts/` | drafts the coach edits before a command applies them (program drafts, log drafts, custom-exercise entries, recipe drafts and saved recipe pages) | gitignored | R-40c, R-41a, R-41b; the coach (R-33b recipe pages) |

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
- **Where versioned documents live** (R-16). The documents the migration
  runner owns are found through its registry (C16 `FILES`). A schema for
  any other instance document (append-only JSONL logs, `.coach/` caches,
  and committed documents no runner subpackage declares yet: the
  readings series and the activity sync map) carries a top-level
  `"x-coach-paths"`: globs relative to the instance root
  (`["data/hevy/writes.jsonl"]`). The validator treats it as an
  annotation, so adding it bumps no version. `schema_versions` reads both;
  when several schemas claim one JSONL file, each line goes to the schema
  whose constant fields (`kind`, `op`) it matches. An item that adds an
  instance document either declares it to the runner or adds the key to
  its schema; a document neither names is not version-checked. Framework
  files (the catalogue), drafts and the envelope carry neither.
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
(timeout, unreachable). Schemas: `hevy_write_line`, `hevy_verify_line` and
`hevy_retire_line` (R-14). The API key never appears.

- A `retire` line has the `verify` line's shape with `kind: "retire"`. Its
  `overlay_hash` is the overlay's C10 content hash (equal to
  `approval.hash` while the approval holds), so an unapproved one-off
  overlay can still be retired.
- `diff` holds the changes left after the read-back: empty exactly when
  `verified` is true. A change is
  `{routine_id, class, path, before, after}`: `path` is relative to the
  routine (`title`, `exercises[1].notes`, `exercises[1].sets[2].weight_kg`,
  or `exercises[1].sets[3]` for a whole set added or removed), `before` is
  Hevy's value and `after` the intended one. `class` is `prescription`
  for `weight_kg` and `notes`, which every programming pass rewrites, and
  `structural` for everything else: title, folder, exercises, their
  order, set count, set type, reps, rep range, duration, distance, rest
  and superset (R-03's in-app edit check).
- `routines push` appends a `write` and a `verify` line per routine it
  writes. A routine that already matched gets one `verify` line, the first
  time it is pushed for that overlay and hash, so every routine in the
  span has a `verified: true` line once a push succeeds. `routines
  verify` appends nothing.
- `routines create` (R-14b) appends a `write` line for each POST or PUT,
  the one-off folder's POST included, and a `verify` line per routine it
  creates or reuses, carrying the overlay's id and approval hash. The
  `write` line of a `POST /v1/routines` names the new routine's id, taken
  from Hevy's answer (`coach.hevy.client.created_routine`, which accepts
  the routine bare or in a one-item list); it is null only when the
  answer names none.

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
  or at the end of the file, and changes nothing else. A recipe card
  (C33) finds its region with `find_regions` but places a missing one
  right after its data block, so it does not use `splice_region`.
- **Archive rule:** `week-review` regions in any record but the newest are
  archive. `render_week_review(id)` returns them unchanged, so R-16's sweep
  never fails an old record because history was later corrected. `cardio`
  regions are snapshots with no freshness check (late syncs must not fail
  old records).
- **The sweep** (R-16 `render_fresh_sweep`) reads every `*.md` under the
  root outside dot-directories, except the bundled root `tests/` tree
  (regardless of framework-sync metadata) and framework files tracked at
  the template commit `.claude/framework-sync.json` records. The athlete
  cannot fix framework content because the next sync overwrites it.
  Athlete-owned Markdown in other locations, including custom notes,
  remains eligible. A marker is
  a region marker only when it starts its own line (up to three spaces
  of indent) outside a fenced code block and an inline code span, so
  docs that show markers as examples hold no regions. It finds a kind's
  renderer as the first
  top-level `coach` module (alphabetical) defining `render_<kind>`, with
  hyphens as underscores; R-33b has no `render_card(root, id)`, so the
  sweep builds one from `coach.recipes`. It leaves a region to its owner's
  check where one looks (an `overlay` region in `check-ins/*.md`, a
  `research` region in its own note, a `card` region in its own card), so
  one stale region fails one check; every other region it renders and
  compares (fail when stale). Unbalanced markers fail; a region of a kind
  no renderer knows, or whose data cannot render, warns. Whole rendered
  files stay with their owners' checks (`recipe_index_fresh`, R-17a's
  `routine_render_fresh`, R-25's pages).
- **Hidden data block.** A markdown file whose structured part a human
  edits (a research note, C28; a recipe card, C33) starts with a TOML block
  inside an HTML comment, which GitHub hides. The file's first line is
  exactly `<!-- coach:<kind>` (`note`, `card`); the block ends at the first
  line that is exactly `-->`; the text between is TOML. The TOML must not
  contain `-->`. Everything after the block is markdown: prose, rendered
  regions or both.
- One parser reads every kind: `coach.datablock.read(path, kind) ->
  (data: dict, rest: str)`, raising a validation error that names the file
  for a missing opener, a missing closer, a wrong kind, a `-->` inside the
  block, or invalid TOML. Whichever of R-32a and R-33b merges first adds
  it; the other reuses it. (R-32a added it; R-33b reuses it unchanged and
  finds where a card's block ends as `len(text) - len(rest)`.)
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

**Routine body, diff and push (R-14).** `coach.routines`:

- `intended_body(overlay, session, cached_routine)` is the PUT body
  `{"routine": {...}}`. Title: the session's for a `temporary` session,
  else the routine's own. `folder_id` is kept from the cached routine
  when it has one, since a PUT may move a routine. Each exercise sends
  `exercise_template_id` (the line's `hevy_template_id`; a line without
  one is a validation error), `superset_id` and `rest_seconds` when set,
  the C12 note, and its sets. A set sends `type`, `weight_kg` (the load's
  `hevy_kg` only), `reps` or `rep_range`, `duration_seconds`,
  `distance_meters`, each only when it has a value. No set sends
  `weight_kg` for a null load or an unweighted `bodyweight` load
  (`hevy_kg` 0). The body never holds a null or a routine-level `notes`.
- `diff(intended, actual)` compares by position (C9 change shape).
  Absent equals null, and `weight_kg` matches within 0.001 kg. A
  different template at a position is one structural change for the
  whole exercise. Hevy fields the body never sends (`custom_metric`,
  `index`, exercise `title`) are not compared.
- **Which routine a session has** (`session_routines(root, overlay)`,
  R-14b). The overlay's `hevy_routine_id` first. When it is null,
  `data/state.json` decides (C16): a `temporary` session takes the
  `hevy.temporary_routines` entry whose `overlay_id` is this overlay and
  whose `session_id` is the session's; any other session takes the
  `hevy.routines` id mapped to its session id. Two routines for one
  session is a validation error (exit 1). State is read only when a
  session's id is null. `diff`, `verify`, `push`, `retire` and the
  `overlay_hevy_drift` check all resolve this way.
- **Which session a routine carries.** One routine per id in the
  overlay's span. A routine that serves several sessions carries the
  next one dated today or later, or the last one when all have passed,
  and the command warns. A session with no routine either way makes
  `diff`, `verify` and `push` exit 1, naming `routines create`.
- **Push guards** (exit 3, before any request, and under `--dry-run`
  too): no approval; approval hash broken; an unresolved `block` flag;
  span ended before today; a routine's chosen session dated today or
  later is in force (C10) under a different overlay. Then push GETs
  every routine in the span. It refuses (exit 3) before any PUT if any
  live `updated_at` differs from the cached one, with or without
  `--refresh`: an app edit is reviewed with `routines diff --refresh`
  before any push. `--refresh` only fills a routine missing from the
  cache and, once the guard passes, writes the live routines into the
  cache (unless `--dry-run`). A PUT, GET back and diff follow per changed routine,
  in overlay order. The read-back replaces the cached routine. A
  read-back that differs logs `verified: false`, stops the push and
  exits 1 with the report in `data`. Re-running after success sends no
  PUT.
- `routines diff` and `routines verify` read the cache. With `--refresh`
  they GET the span's routines first and write them into the cache
  (unless `--dry-run`). `verify` exits 0 and reports `verified` per
  routine and overall.
- **`routines create --overlay ID`** (R-14b; H, gated like push). It
  gives every session with no routine one, one routine per session id.
  Same refusals as push, before any request and under `--dry-run` (exit
  3), with the sessions to be created counted in the supersession check.
  It needs `data/state.json` (exit 1 when absent), and a non-temporary
  session must be a session of `data/program.json` when one exists (exit
  1). A `temporary` session reuses the first `hevy.temporary_routines`
  entry, in state order, that carries no session of this overlay and no
  session dated today or later of another overlay in force that day; it
  GETs that routine and PUTs the session over it (`intended_body` with
  the live routine, so the folder is kept). A spare that GET answers 404
  is skipped, listed in the report's `stale`, and dropped from
  `temporary_routines` (not under `--dry-run`). With none left it POSTs a new
  routine to `hevy.folders.one_off`, POSTing the folder `One-off weeks`
  first when that is null. Any other session gets a new routine in
  `hevy.folders.program` (no `folder_id` when null). The folder follows
  the session's `temporary` flag rather than the overlay kind, so a
  deload overlay of program sessions files a missing program routine
  with the program. Each new id goes into state.json at once (the folder
  in `folders.one_off`, a program routine in `hevy.routines`, a
  temporary one as its `temporary_routines` entry with this overlay and
  session), never into the overlay, so the approval hash holds. Each
  routine is then read back, cached and verified as push does; a
  read-back that differs exits 1 with the report, the ids already
  recorded kept. A second run finds every session and writes nothing.
  The report adds `folder` (`title`, `id`, `status`: `not_needed`,
  `exists`, `would_create`, `created`) and, per routine, `reuse` (null
  or the reused routine's old `title`), `folder_id` and `targets` (each
  exercise's C12 Target line); `routine_id` is null for a routine not
  yet created. Statuses: `would_create`, `would_reuse`, `created`,
  `reused`, `failed`, `not_reached`.
- `routines retire` refuses (exit 3) unless the overlay's span ended
  before today. For each `temporary` session's routine it GETs the live
  routine and PUTs it back titled `(unused)` with its exercises as they
  are, then reads it back. It skips a routine already titled `(unused)`
  and a routine that any overlay whose span has not ended still names.
- The report (`data`) holds `action`, `overlay_id`, `overlay_hash`,
  `approved`, `unit`, `dry_run`, `routines` (per routine: `routine_id`,
  `session_id`, `date`, `carries`, `title`, `temporary`, `status`,
  `verified`, `changes`, `exercises`), `changes` (every routine's,
  flattened), `writes`, `summary`, and `verified` for `verify`.
  `summary(report)` is the plain text R-15 shows. It names each changed
  routine and prints old Hevy values through `units.from_hevy_kg` and new
  loads through `units.format_load`, so a dumbbell line reads
  `22.5/hand (Hevy: 45) → 25/hand (Hevy: 50)`.

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

C5 (the exercise library, R-11) and the sections from C17 on name the checks their owners register. R-32a
registers `research_notes`, `research_citations`, `research_render_fresh`
and `research_expiry`. R-14 registers `overlay_hevy_drift`: per routine of
the overlay in force today (else the next to start), `warn` when the cached
routine differs from it; `skip` when Hevy is off, there is no routine
cache or no such overlay.

R-16 registers the cross-cutting checks in `coach/checks/instance.py`.
Checks about a prescription read only overlays whose span ends today or
later: an ended overlay is history, and an approved one cannot be edited
without breaking its approval. Each failing result names the file, the
JSONPath or line, and the offending value.

| Check | Overlays | Fails when | Skips when |
|---|---|---|---|
| `schema_versions` | all | a document the runner owns or an `x-coach-paths` glob claims (C7) has a newer version ("run /framework-sync"), an older one ("run python3 -m coach migrate run"; a Hevy cache file: "rebuild the cache with python3 -m coach hevy pull --full"), none, or is not JSON. A JSONL line fails only when newer: lines keep the version they were written at (C29) | no versioned documents |
| `dangling_exercise_ids` | all | an overlay line's `exercise_id` is not in the library | no overlays; invalid library |
| `dangling_routine_ids` | span not ended | a session's `hevy_routine_id` is not in the cached routines | Hevy off; no `.coach/cache/`; no cached routines; no such overlay |
| `overlay_library_consistency` | span not ended | a line's `load_mode` differs from the confirmed one (unconfirmed is `load_modes_confirmed`'s), or its `hevy_template_id` is not one of the entry's | no such overlay; invalid library |
| `load_caps` | span not ended | a set's load is above the C22 cap: `[caps]` id first (per hand for per-hand modes, total otherwise), else `dumbbell_max` of the session's location for per-hand modes | no such overlay |
| `env_untracked` | — | `.env` is tracked, or exists and is not ignored (warn when absent and not ignored) | not a git working tree; no git |
| `bare_hevy_values` | span not ended | a `per_hand_x2` load figure is not in the two-number form (below) | — |
| `render_fresh_sweep` | — | see C11 "The sweep" | — |

**Bare Hevy values.** A load figure is a number with a weight unit
(`50 kg`), a number in a table column whose header says load, weight, kg
or lb (and not Hevy), or a number in an arrow chain (`45 → 50`). It is
in the two-number form when it, or another figure in its chain, says per
hand (`/hand`, `per hand`, `each`) or gives the Hevy value (`(Hevy: 50)`).
In a table, a figure is also in the two-number form when its column
header says per hand (`Per hand (kg)`, `Load/hand (kg)`), when it sits
in a Hevy-headed column, or, in a load column, when the same row has a
number in a Hevy-headed column (`| DB bench press | 25 | 50 |` under
`| Exercise | Per hand (kg) | Hevy (kg) |`). Ranges, dates, sets × reps,
RPE, durations and distances are not load figures. The check reads a
`per_hand_x2` overlay line's `target_note`, `change`, `cues`, `focus`
and `override.reason`, and the prose of `profile.md` and
`check-ins/*.md` outside rendered regions. In prose a figure belongs to
the nearest exercise named before it on its line, and to no exercise
when none is. A table row's figures belong to the exercise named before
them on the row, else to the exercise in the row's exercise cell (the
column headed exercise, lift or movement, else the first). A row whose
exercise cell is empty continues the row above and takes its exercise;
a row whose exercise cell names nothing the library knows has none.
Library names, aliases, Hevy titles and ids name exercises, and
"dumbbell" or "DB" alone means `per_hand_x2`. Only `per_hand_x2`
figures can be bare: a single implement's two numbers match.

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
| program and state (R-17a) | `data/program.json`: Session A squat 3×5 RPE 7 from 100, DB bench 3×8–10 RPE 8 from 25/hand; Session B row 3×10 RPE 8 from 30, pull-up 3×8 RPE 8 at BW; `fixed_weekdays` mon/thu; no external sessions; `data/state.json` mapping both C14 routines, folder 1; `routine/` pages rendered from it |
| overlay | `2026-10-12-weekly`, span 2026-10-12 to 2026-10-18, approved; Session A 2026-10-12 (squat 100, DB bench 25/hand (Hevy: 50)), Session B 2026-10-15 (row 30 (Hevy: 30), pull-up BW); built from `tests/fixtures/overlay/draft-kg.json` |
| check-in (R-13) | `check-ins/2026-10-11.md` holding the rendered region of `2026-10-12-weekly` |
| profile (R-26b) | `profile.md`: two lines of synthetic prose, no load figures and no claim references, so `status` sees a set-up instance |
| `COACH_NOW` | `2026-10-11T18:00:00Z` |
| activities (R-42a) | `manual:2026-10-08-run-1` run 5 km, 30 min, RPE 6; Hevy workout `00000000-0000-4000-8000-0000000000c1` "Conditioning", all-conditioning, starting 6 min after `manual:2026-10-10-conditioning-1` (the dedup pair); `[activity] enabled = true` in `config.toml`; `data/activity/sync.json` with the Hevy workout seen at 2026-10-11T12:00:00Z. The Hevy workout lives in `tests/fixtures/hevy/conditioning/` (below), not in a cache in `valid/` |
| wellness (R-42a) | in `.coach/activity/wellness.jsonl`: daily `apple_health` records 2026-10-05 to 2026-10-10 with sleep; one manual span record `manual:2026-10-05..2026-10-11-wellness` at 7.0 h |
| planned (R-42a) | `manual:2026-10-14-run-1` "Easy 5 km", `manual:2026-10-16-run-1` "Intervals" `quality: true` |
| nutrition (R-33a) | `[nutrition]` enabled, app macrofactor, phase recomp, target rate 0.0, reference mass 80, floor 110, target 128, stretch 176, `floor_since` 2026-09-28, one anchor "Whey shake" 150 kcal / 30 g daily snack |
| readings (R-33a) | 2026-09-28 (avg protein 104), 2026-10-04 (112), 2026-10-11 (115), app target protein 110; trend weights 82.6, 82.5, 82.4; 7 days logged and anchors yes each week. Seed input for `nutrition import`: `tests/fixtures/nutrition/seed.json` (2026-09-07, 09-14, 09-21) |
| cards (R-33b) | `chicken-rice-bowl` lunch 610/50/55/18 with `light` variation; `overnight-oats` breakfast; `whey-shake` snack. R-33c adds `spinach-omelette` (breakfast, dinner; 3 eggs, 80 g spinach) and `turkey-chilli` (lunch, dinner; `servings = 4`) |
| template (R-33c) | `[nutrition.template]`: office days tue, thu; staples eggs, rolled oats, olive oil; standing breakfast `overnight-oats` daily, office lunch pool `chicken-rice-bowl`, dinner covered by `family` (900 kcal, 40 g) Monday to Thursday |
| meal plan (R-33c) | `2026-10-12`, span 2026-10-12 to 2026-10-18, built from `tests/fixtures/meals/draft-2026-10-12.json` and rendered, not approved |
| research (R-32a) | template note `research/fixture-dose.md` (area `volume`, claims 1 and 2 current, `review_by` 2028-03-01); local note `research/local/local-fixture-knee.md` (area `rehab`, `updates = ["rn:fixture-dose.2"]`); `reference/fixture-guide.md` citing claim 1 of `fixture-dose`; record `check-ins/2026-08-30.md` (weekly) citing claim 1 of `local-fixture-knee` |

Logged workouts in the valid instance (R-20 adds them as synthetic Hevy
workouts; ids `10000000-0000-4000-8000-00000000000N`):

| N | Date | Routine | Logged |
|---|---|---|---|
| 1 | 2026-09-28 | Session A | squat 3×5 @ 95 RPE 7; DB bench 3×10 @ Hevy 45 (22.5/hand) RPE 8 |
| 2 | 2026-10-01 | Session B | row 3×10 @ 30 RPE 8; pull-up 3×8 BW |
| 3 | 2026-10-05 | Session A | squat 3×5 @ 97.5 RPE 7.5; DB bench 3×10 @ Hevy 45 RPE 8; 18:00 to 18:58 UTC (58 minutes) |
| 4 | 2026-10-08 | Session B | row 3×10 @ 30 RPE 8.5; pull-up 3×8 BW |

Further fixture instances, each owned by the item that first needs it.
Unless stated, each is a copy of `valid/` plus what is listed.

| Instance | Owner | Holds |
|---|---|---|
| `layoff/` | R-24 | same program and overlay (approved, null provenance); no Hevy cache; `data/history/2026-08.json` and `2026-09.json` resolved by `history sync` from synthetic workouts `...0021` to `...0025`: Session A 2026-08-31, 09-07 and 09-14 (squat 3×5 @ 95, 97.5, then 100, RPE 7; DB bench 3×10 @ Hevy 45 RPE 8), Session B 2026-09-03 and 09-10 (row 3×10 @ 30 RPE 8; pull-up 3×8 BW). Last workout 2026-09-14, so 28 days off before 2026-10-12 |
| `slip/` | R-20 | DB bench logged Hevy 45 on 2026-09-28 and Hevy 90 on 2026-10-05 at the same reps and RPE, and DB shoulder press (template `F0000005`, confirmed `per_hand_x2`) Hevy 30 then 60 on the same dates. Not a full copy: `valid/`'s config, program, state and overlay, the library plus DB shoulder press, and `data/history/2026-09.json` and `2026-10.json` resolved by `history sync`; no Hevy cache |
| `history-bad-schema/`, `history-unresolved/`, `annotations-invalid/` | R-20 | not copies of `valid/`: `valid/`'s config and `slip/`'s `2026-10.json`, with one fault each: a set with an unknown key `weight`; workout 3's squat as an unmatched "Mystery Lift"; an annotation discounting a workout the history lacks |
| `flag-unknown/` | R-20 | not a copy of `valid/`: its config and its overlay, unapproved, carrying a flag with the unregistered code `no_such_code` |
| `checkin/` | R-21a | external session `pt-tue` (Tue) in the program; approved overlay `2026-10-05-weekly` (span 2026-10-05..2026-10-11: Session A 2026-10-05 squat 3×5 @ 97.5 RPE 7.5, DB bench 3×10 @ 22.5/hand (Hevy: 45) RPE 8; Session B 2026-10-08 row 3×10 @ 30 RPE 8, pull-up 3×8 BW; Session A 2026-10-10 as on 10-05); `valid/`'s two records replaced by `check-ins/2026-09-06.md` (deep) and `check-ins/2026-10-04.md` (weekly, holding its week-review region); `[sessions.cap_minutes] session-a = 45`; `writes.jsonl` verify lines for both routines, `2026-10-05-weekly` and its approval hash, at 2026-10-04T19:00:00Z; a Hevy cache holding the four C14 workouts and the two routines as that overlay writes them, `...0002` with `updated_at` 2026-10-07T07:00:00Z and one extra exercise (DB bench); `data/history/2026-09.json` and `2026-10.json` from `history sync`; `miss` annotations 2026-09-14 Session A `sleep`, 2026-09-17 Session B `sleep`, 2026-09-21 Session A `time` |
| `gap/` | R-21b | `layoff/`'s history (last workout 2026-09-14, squat 3×5 @ 100, none after) with `checkin/`'s program (`pt-tue`, mon/thu); no overlays; records `check-ins/2026-08-30.md` (weekly, the research record), `2026-09-06.md` (deep) and `2026-09-13.md` (weekly), so at `COACH_NOW` no deep review is due |
| `missed/` | R-22 | program with rules `miss-b` (fold row, 2 sets, into Session A, `min_days_left` 1), `miss-a` (shift to sat, then thu); the library names `db_single_arm_row` "Single-arm row"; approved overlay `2026-10-12-weekly` re-dated: Session A 2026-10-12, Session B 2026-10-14, Session A 2026-10-17; `data/history/` as in `pages/`, so the workout for Session A on 2026-10-12 is the only one in that week; the record's overlay region and `routine/` re-rendered |
| `missed-bad-rule/`, `missed-weekly-fold/` | R-22 | not copies of `valid/`: `missed/`'s config and library, with one fault each: `miss-b` folding into `session-z`; the weekly overlay holding a folded row on Session A 2026-10-17 |
| `dose/` | R-30a | program with `pt-tue` estimated at `{"chest": 3, "lats": 3}`; approved weekly overlays for 2026-W36 to 2026-W41 built from `tests/fixtures/overlay/draft-kg.json` re-dated (Session A Monday, Session B Thursday, each created the Sunday before at 19:00Z); `data/history/2026-08.json` to `2026-10.json` from `history sync` of synthetic workouts `...0301` to `...0309` (Session A squat 3×5 @ 95 RPE 7, DB bench 3×10 @ Hevy 45 RPE 8; Session B row 3×10 @ 30 RPE 8, pull-up 3×8 BW), no Hevy cache; `miss` and `external` annotations made at each week's Sunday check-in, giving the weeks below (planned = Session A, Session B, PT = 3) |
| `block/` | R-31 | program with `hard_weeks_ceiling` 6 and `pt-tue`; a ledger with block `b-0001` started 2026-08-31 and no closed weeks; no weekly overlays, so W36 to W41 are judged against the program sessions; workouts matching them (every core session at the prescribed sets and RPE) plus `external` done annotations. Closing W36 to W41 gives six hard weeks. A test that needs an overlay week builds W42 with `propose week` |
| `nohevy/` | R-40c | the valid program and overlay; `[hevy] enabled = false`; no Hevy cache; `data/log/workouts.jsonl` holding the two Session A workouts of the logged-workouts table, logged by hand (squat 3×5 @ 95 RPE 7, DB bench 3×10 @ 22.5/hand RPE 8; the same on 2026-10-05 at 97.5), with `overlay_id` null; `this-week-sheets.md` rendered at 2026-10-11T18:00:00Z |
| `manual-log-invalid/` | R-40c | not a copy of `valid/`: `nohevy/`'s config, library, program and overlay, and a log whose line 2 repeats line 1's id, line 3 logs `no_such_lift` in session `session-z`, and line 4 voids `manual:2026-09-21-session-a-1`, which no line logs |
| `sheets-stale/` | R-40c | not a copy of `valid/`: `nohevy/`'s config, library, overlay and sheets, with Session A's squat working sets hand-edited from 100 to 105 |
| `library-seed/` | R-11 | not a copy of `valid/`: config, and a synthetic Hevy cache (C8) holding Session A and Session B with the four `valid/` exercises plus the custom template `C0000001` "Tyre Flip"; no instance library |
| `library-unconfirmed/` | R-11 | not a copy of `valid/`: config, cached Session A, and an instance library where `db_bench_press` has a proposal but no confirmed load mode |
| `library-invalid/` | R-11 | not a copy of `valid/`: config and an instance library with an unknown field on `db_bench_press` |
| `empty/` | R-41a | `config.toml` (`valid/`'s without `[activity]` and `[nutrition]`) and `valid/`'s instance library with `db_bench_press` proposed but not confirmed: no program, no state. Not a copy of `valid/` |
| `pages/`, `pages-stale/`, `pages-long-brief/` | R-25 | not copies of `valid/`: its config without `[activity]` and `[nutrition]`, library, program, state, overlay and record `check-ins/2026-10-11.md`; `data/history/2026-09.json` and `2026-10.json` from `history sync` of the C14 workouts plus Session A on 2026-10-12 (squat 3×5 @ 100 RPE 7, DB bench 3×10 @ Hevy 50 RPE 8); no Hevy cache; the three pages rendered at 2026-10-14T18:00:00Z. `pages-stale/` hand-edits the brief's focus; `pages-long-brief/` pads the brief to 61 lines |
| `hevy-fresh/` | R-12 | `valid/`'s `config.toml` and a cache `meta.json` with the last pull at 2026-10-11T12:00:00Z (6 hours before `COACH_NOW`) |
| `hevy-stale/` | R-12 | the same with the last pull at 2026-10-09T12:00:00Z (54 hours) |
| `cardio/` | R-43 | see C50 |
| `cardio-invalid/` | R-43 | not a copy of `valid/`: its config with `[cardio] spike_ratio = 1.0` and `sleep_debt_nights = 8`, and a `data/status-days.json` with a row ending before it starts and two open-ended `injured` rows |
| `activity-bad-record/` | R-42a | not a copy of `valid/`: the valid config and an `activities.jsonl` whose line 2 has an unknown field `heart_zone` |
| `activity-wellness-misplaced/` | R-42a | not a copy of `valid/`: the valid config (`wellness_in_git` left false) and the wellness file at `data/activity/wellness.jsonl` |
| `research-bad/` | R-32a | not a copy of `valid/`: the valid config; `fixture-dose` with a hand-edited claims table; `fixture-broken` with two claims numbered 1; `fixture-old` expired 2026-10-01 (area `sleep`); `reference/fixture-guide.md` citing a missing claim |
| `interference/` | R-44a | `[cardio] tier = "review"` and the planned quality run `manual:2026-10-11-run-1` "Tempo" (40 min) on 2026-10-11, the day before Session A (squat 3×5 at RPE 7) on 2026-10-12 |
| `nutrition-bad-readings/` | R-33a | the valid config; a readings series with 2026-10-04 twice, the second with no weight and no protein |
| `nutrition-override/` | R-33a | the valid config plus `[nutrition.override]` 2026-10-01 to 2026-10-22, renewal 1; no readings |
| `meals-template-overlap/` | R-33c | not a copy of `valid/`: the valid config plus a fourth standing row filling Monday dinner |
| `meals-bad-template/` | R-33c | not a copy of `valid/`: the valid config with the standing breakfast naming the missing card `porridge` and the anchor naming the benched card `protein-bar`; a menu of `chicken-rice-bowl` and `protein-bar` |
| `meals-bad-arithmetic/`, `meals-stale-render/` | R-33c | not copies of `valid/`: the valid config and the valid plan, with one fault each: Monday's kcal total 100 over its items; a hand-edited Monday row in the rendered plan |
| `overlay-bad-schema/`, `overlay-bad-arithmetic/`, `overlay-stale-render/` | R-13 | `config.toml` plus the valid overlay with one fault each: Session B dated outside the span; DB bench working sets at `hevy_total` 25 for 25/hand; a hand-edited check-in region |
| `routines-drift/`, `routines-pushed/` | R-14 | not copies of `valid/`: its `config.toml`, the valid overlay and a Hevy cache (`meta.json`, `routines.json`). `routines-drift/` caches the synthetic routines as pulled; `routines-pushed/` caches them after `routines push` of the valid overlay to the fake |
| `plugins-invalid/` | R-23a | not a copy of `valid/`: its config and an instance scheme `plugins/schemes/custom_untested.py` with no test file |
| `decisions-invalid/` | R-23a | not a copy of `valid/`: its config and a `data/decisions.json` holding one standing override with no `until` |
| `program-bad-schema/`, `program-misspelt-key/`, `program-unknown-exercise/`, `program-avoided/`, `program-stale-render/`, `program-top-set/`, `state-bad-schema/` | R-17a | not copies of `valid/`: `config.toml` plus the valid program with one change each: DB bench without `load_mode`; squat `rest_secs`; squat as `no_such_exercise`; an instance library marking DB bench `avoid`; the valid routine pages with one character of `session-a.md` edited; squat as a 1×3 top set and 3×5 back-offs; a state with deload status `pending` |
| `schema-version-log/`, `schema-newer/`, `schema-older/`, `dangling-exercise/`, `dangling-routine/`, `overlay-library-mismatch/`, `load-over-cap/`, `bare-hevy-value/`, `render-stale-sweep/` | R-16 | not copies of `valid/`: its `config.toml`, library and overlay, with one fault each: an audit-log line at schema version 2; the overlay at version 2; at 0; DB bench as `db_bench_pres`; Session B naming an uncached routine (with `routines-drift/`'s cache); DB bench naming template `F0000003`; DB bench working sets at 45/hand (Hevy: 90); DB bench `target_note` "go to 50 kg"; a hand-edited overlay region in `profile.md`. Overlays are re-approved. `env_untracked` builds its git repositories in temp directories, since fixtures hold no `.env` (C6) |

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

Synthetic Hevy fixture set `tests/fixtures/hevy/conditioning/` (R-42a; a
complete set, not layered): the C14 routines plus "Conditioning" `...0003`
(kettlebell swing, burpee); conditioning exercise templates (`F00000A1`
Rowing Machine, `F00000A2` Burpee, `F00000A3` Kettlebell Swing, `F00000A4`
Treadmill, custom `C00000A1` "Bike Erg Sprints" with primary muscle
`cardio`); workouts `...0c1` (the C14 conditioning workout: rower and
burpees), `...0c2` (a lifting workout with a rower finisher), `...0c3`
(swings and burpees from routine `...0003`, "EMOM 12 min, RPE 7"), `...0c4`
(the same from Session A), `...0c5` (the custom cardio template) and `...0c6`
(a treadmill run). `tests/support/activity.py` writes it as a C8 cache.

Synthetic Hevy fixture set `tests/fixtures/hevy/wave/` (R-41a; its
`routines.json`, layered over `synthetic/`, C15): four routines "W1
Squat Day", "W2 Squat Day", "W3 Squat Day", "Bench Day", squat top loads
85, 90, 95, with "TM 100" in a note.

Synthetic Hevy fixture set `tests/fixtures/hevy/pushed/` (R-41a; its
`routines.json`, layered over `synthetic/`): the two C14 routines as
`routines push` of the valid overlay leaves them (`routines-pushed/`'s
cache): squat 1 warm-up and 3×5 at 100, DB bench 1 warm-up and 3×8–10 at
Hevy 50, row 3×10 at 30, pull-up 3×8, each with its C12 note. The
program draft `tests/fixtures/program/draft.json` is `program
import-hevy` of it on `valid/`, with the days `mon` Session A and `thu`
Session B filled in.

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

Built by R-17a; the schemas are `coach/schemas/program.schema.json` and
`coach/schemas/state.schema.json`. Later items change them only through a
version bump (below).

`data/program.json`:

```json
{
  "schema_version": 3,
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
  "dose_targets": {"chest": 10, "quadriceps": 8},
  "schedule": {"rule": "fixed_weekdays", "params": {}},
  "blocks": {"hard_weeks_ceiling": 6, "deload_rule": {"name": "standard", "params": {}}},
  "missed_day_rules": [
    {"id": "miss-a", "session_id": "session-a", "condition": "...", "action": "..."}
  ],
  "interference": [{"name": "same_day", "params": {"min_gap_hours": 6, "lift_first": true}}]
}
```

- Every key shown is required except session `location`, session
  `scheme` (v7, C51), `dose_targets`, `priority` and `minimum_week`
  (C40). A session without `location` or `scheme` reads as null, a
  program without `dose_targets` reads as `{}`, without `priority` as
  `[]` and without `minimum_week` as null; `coach.program.load(root)`
  fills them, so readers always see the keys.
- `kind`: `lifting`, `conditioning`. `tier`: `core`, `optional`. `status`:
  `active`, `parked`, `standby`. A session needs at least one exercise.
- Session ids are unique and never `program` (its page would overwrite
  `routine/program.md`). An exercise appears at most once per session:
  a top set and back-offs are one entry with two set groups, which keeps
  `<session_id>/<exercise_id>` a unique slot key.
- `location`: null (the main `[equipment]` table) or the name of a
  `[equipment.locations.*]` table (C54); `program validate` fails on a name
  config does not define, at the session's JSONPath.
- `sets` is a list of set groups. Each group has `count`, `type` (as in
  C10), exactly one of `reps` or `rep_range`, and optional `rpe`,
  `duration_seconds`, `distance_meters`. A plain 3×5 is one group. As in
  C10, a `duration` group needs `duration_seconds`, a `distance` group
  needs `distance_meters`, and for those two modes `reps` and `rep_range`
  are optional.
- `start_load` is in athlete units and per hand for per-hand modes, like
  every load a human writes; code builds load objects from it (C5). Null
  on a loaded mode means the coach picks the first load; it must be null
  for `band`, `duration` and `distance`.
- `constraints` items are free text in v1 (R-23a's v2 gives them the C26
  shape).
- `external_sessions`: `weekday` is a weekday id or null (no fixed day);
  `estimated_sets` keys are the C5 muscle ids, values whole hard sets.
  External ids may not repeat a session id.
- `schedule.rule`: `fixed_weekdays`, `alternating_external_anchor`,
  `next_in_sequence`, `explicit_calendar`.
- `blocks.hard_weeks_ceiling` is 4 to 8 (`CLAUDE.md` "Fatigue management
  & deloads"). `blocks.deload_rule.name`: `standard`, `scheme`, `light`
  (C23 transforms).
- Scheme names: the C23 schemes of kind `scheme` (`hold`, `linear`,
  `double_progression`, `fixed_reps_rpe`, `rpe_anchored`, `wave_531`,
  `assistance_ladder`, `maintenance`). Scheme, schedule and deload names
  are checked against these fixed lists; their `params` are free-form
  objects in v1. R-23a adds a schema per plugin and bumps the version
  (C23).
- Missed-day rules are free text in v1; each names a program session.
  R-22 makes them executable (C37).

`data/state.json`:

```json
{
  "schema_version": 3,
  "rotation": {"position": "week-a", "confirmed": true, "confirmed_at": "2026-10-11", "week": "2026-10-12"},
  "block": {
    "started": "2026-09-01",
    "hard_weeks_completed": 3,
    "deload": {"status": "not_due", "since": null}
  },
  "one_off": null,
  "scheme_state": {"session-a/bb_back_squat": {"scheme": "double_progression", "data": {}, "pending": null}},
  "hevy": {
    "routines": {"00000000-0000-4000-8000-000000000001": {"session_id": "session-a"}},
    "folders": {"program": 1, "one_off": 2},
    "temporary_routines": [
      {"routine_id": "00000000-0000-4000-8000-0000000000a1", "overlay_id": "2026-10-19-one-off",
       "session_id": "travel-a"}
    ]
  }
}
```

- `rotation.position` is null when the schedule has no rotation
  (`fixed_weekdays`); `confirmed_at` is a date or null.
- `deload.status`: `not_due`, `due`, `in_progress`, `done`, `skipped`.
  R-31 replaces `block` with the C42 shape.
- `one_off`: null or `{"overlay_id": id, "span": span}`.
- `scheme_state` keys are `<session_id>/<exercise_id>` and name a slot the
  program has, or `<session_id>/_session` for a `conditioning` session's
  density scheme (C51); values are free-form objects in v1 and v2, and
  take the C23 shape in v3.
- `hevy.routines` replaces `routine/hevy-map.json`; each `session_id`
  names a program session. Folder ids are Hevy's integers or null. R-14b's
  `routines create` records new routine ids here, never in the overlay.
- `hevy.temporary_routines` (v2, R-14b): the reusable temporary routines,
  in reuse order. Each entry is `{"routine_id", "overlay_id",
  "session_id"}`: the overlay session it last carried, or both null when
  it has carried none. The migration from v1 turns each id into an entry
  with both null.

**Reading and validating.** `coach.program.load(root)` and
`coach.state.load(root)` return the schema-checked document (ValidationError,
exit 1, when absent, malformed or at another version).
`coach.program.problems(doc, config, library)` adds the cross-checks
(duplicate ids, set groups, start loads, locations, library ids) as
`(kind, Error)` pairs; `coach.state.problems(doc, program)` adds dates and
references into the program. `program validate` reports all of them;
`state show` refuses an invalid state the same way.
`coach.program.warnings(doc)` lists what a valid program may keep but
should not, each warning starting with its code. `program validate`
puts them in the envelope's `warnings` and still exits 0. One code so
far: `fixed_reps_no_e1rm`, for a `fixed_reps_rpe` slot with a working
group past `stats.MAX_REPS_TO_FAILURE` reps to failure (its reps, or
its range's start, plus 10 − RPE). Its sets give no e1RM, so its load
holds unless another line of the exercise supplies one. The warning
names the exercise, the session and the reps to failure, and suggests
`double_progression`.

**Rendered pages.** `coach.program.render_all(root) -> {path: text}` gives
`routine/program.md` (sessions with links, schedule rule, coach-led
sessions, block ceiling and deload rule, missed-day rules) and
`routine/<session id>.md` for every session (one table row per set
group; start loads through `units.format_load` on the first working
group's row; cues and constraints listed below). It renders from
`data/program.json`, the exercise library (names) and `[athlete] units`
only, never from state, so a weekly state change never makes a page
stale. The one exception is the block status line (C43) on
`routine/program.md`, which reads `data/state.json` and
`data/blocks.json`; every `block` command that writes re-renders that
page. Each page starts with the C11 header naming `data/program.json`
and `program render`. `program render` writes changed pages, deletes
generated pages for sessions the program no longer has, and leaves any
other `routine/*.md` in place with a warning.

**Checks** (R-17a): `program_schema` (schema and cross-checks, one `fail`
per problem), `state_schema`, `program_exercise_ids` (every exercise id
in the library, every `load_mode` set; reads the raw file, so it works on
a program the schema rejects), `routine_render_fresh` (every page equals
a fresh render; a missing page, a stale generated page or any other
`routine/*.md` fails, naming the file), and `avoided_in_program` (`warn`
for each active session's exercise the library marks `avoid`, C54). All
skip when there is no `data/program.json` (`state_schema`: no
`data/state.json`).

**Migration runner** (`coach/migrate.py`; commands `migrate status`,
`migrate run [--dry-run]`).

- An owned document type is a subpackage `coach/migrations/<schema name>/`
  whose `__init__.py` sets `FILES`, a tuple of glob patterns from the
  instance root. R-17a declares `program` (`data/program.json`), `state`,
  `overlay` (`data/overlays/*.json`) and `exercise_library`
  (`data/exercises.json`). Meal plans declare `data/nutrition/plans/*.json`
  under `meal_plan` (C34). An item that adds a committed JSON document
  adds its own subpackage (C1: add files). Append-only JSONL logs keep
  each line at the version it was written (readers handle old lines),
  and the gitignored `.coach/` caches are rebuilt rather than migrated,
  so neither is declared.
- A step is a module `NNNN_<slug>.py` in that subpackage defining `DOC`
  (the subpackage name), `FROM`, `TO` (= `FROM` + 1) and `migrate(doc) ->
  doc`, plus optionally `notes(before, after) -> list[str]` for lines the
  report should carry (R-24 lists the overlays that lose their approval)
  and `creates(before, after) -> {path: doc}` for documents the step
  brings into being (R-31's state step seeds `data/blocks.json`). A
  created file is validated against the owned document whose `FILES`
  match its path, written with the migrated files only where no file
  exists yet, staged with them, and listed in the report's `created`.
  The runner sets `schema_version` to `TO` after each step. The target
  version is the `schema_version` const of `coach/schemas/<schema
  name>.schema.json`. Discovery rejects a step past that version, two
  steps from one version, a `DOC` that does not match its directory and
  a misnamed file.
- `migrate status`: one row per owned file with `version`, `target` and
  `state` (`current`, `behind`, `ahead`, `unreadable`), plus `behind`, the
  count behind.
- `migrate run`: plans the step chain for every file behind; a file ahead
  ("run /framework-sync"), unreadable, or missing a step exits 1 before
  anything is written. It then copies each file to be migrated to
  `.coach/backups/<YYYYMMDDTHHMMSSZ>/<its path>` (`-2`, `-3` on a clash),
  migrates every file in memory and validates each result against its
  schema. Any invalid result exits 1 with each problem as
  `<file>: <JSONPath>` and writes nothing. Otherwise it writes every file
  (restoring all of them from the backup if a write fails) and runs `git
  add` on them. It never commits. Outside a git work tree it writes and
  warns that nothing is staged. Output: `files` (path, doc, from, to,
  steps), `notes`, `backup`, `written`, `staged`.
- `--dry-run` does the same reads, migration and validation in memory,
  writes no backup and no file, and exits as the real run would.
- `/framework-sync` runs the dry run after copying files, shows it, runs
  `migrate run`, and commits the staged files with the framework.

**Schema versions.** R-17a ships program and state v1. R-14b takes state
to v2 (`temporary_routines` entries). R-23a took program to v2 and state
to v3 (C23). R-30a took program to v3 (`dose_targets`, C40). R-22 took
program to v4 and overlay (and its draft) to v3 (C37). R-44a took
program to v5 (`interference`, C51). R-30b took program to v6
(`priority`, `minimum_week`, C40) and overlay (and its draft) to v4 (a
fold's `rule_id` may be a priority floor rule's id, C40). R-44b took
program to v7 (session `scheme`, C51). Every later
bump takes the next free version when it merges and adds one step to the
R-17a migration chain, so the chain stays linear.
Program bumps: R-22 (executable `missed_day_rules`, C37), R-30b (`priority`, `minimum_week`, C40), R-44a
(`interference`, C51), R-44b (session `scheme`, C51). State bump: R-31
took state to v4 (`block`, C42). Overlay: R-24 takes it to v2 (C21), R-22 to v3 (C37) and R-30b to v4 (C40). A
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
      "source_version": "2026-10-05T18:40:00Z",
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
          "title": "Bench Press (Dumbbell)",
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
- `source_version` is the source module's `version(workout)` when it was
  resolved (`hevy_updated_at` for Hevy), so a changed manual entry is
  noticed too. Exercise `title` is the logged title, so `history rebuild`
  can match an exercise by title without the cache, and an unresolved one
  can be named.
- `session_id` matching: of the overlay in force on `date`, the session
  whose routine is `routine_id` (its `hevy_routine_id`, else the routine
  `data/state.json` maps to it, as C12 resolves it), nearest in date when
  several carry it.
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
  list[SourceWorkout] | None` and `version(workout) -> str`; a changed
  version re-resolves the workout. The module's name is its workouts'
  `source`. `None` means the source holds no data in this instance (Hevy:
  no cache `meta.json`), so sync removes nothing it stored from that
  source: clearing the gitignored cache never deletes committed history.
  `SourceWorkout` (in `coach/history_sources/__init__.py`) carries the
  record's fields before resolution; a manual exercise gives its own
  `exercise_id`, `load_mode` and `unit`, and each set its `value`.
- **Freezing.** `history sync` resolves source workouts not yet in a month
  file, and re-resolves one only when its version (`hevy_updated_at` for
  Hevy) changed; a re-resolve keeps each exercise's stored `load_mode`
  unless a `load_mode` annotation now covers it, or the stored mode came
  from an annotation that no longer covers it. A workout deleted at the
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
  A withdrawing annotation that carries its kind's fields also takes
  effect (a corrected repair); one without them only withdraws.
  `coach.history.annotations()` returns the annotations in force;
  `history annotations --all` lists every one, each marked `in_force`.
- Fields per kind: `discount` `workout_id`, `exercise_id`, `set_index`
  (null: the whole exposure); `repair` those plus `field` and `value`;
  `load_mode` `exercise_id`, `span`, `load_mode`; `unknown_convention`
  `exercise_id`, `span`; `confirm` `workout_id`, `exercise_id`; `miss`
  `date`, `session_id`, `tag` (null: untagged); `external` `date`,
  `external_id`, `done`, `note`; `trained_unlogged` `date`, `session_id`,
  `note`. Every annotation has `id`, `kind`, `created_at`, `source` and
  `reason` (nullable). `set_index` is the set's `index` in the month file.
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
#           suspect (open convention_slip candidate), excluded (discount / unknown_convention),
#           discounted, convention_unknown (which of the two)
# Read workouts and their sets carry discounted, convention_unknown and repaired (the fields a
# repair replaced); each workout carries unsynced and conditioning (C17 conditioning rule).
coach.history.last_lifting_date(root, before) -> date | None                    # any workout with a lifting exercise
coach.history.annotations(root, kind=None) -> list[dict]
```

`include_unsynced=True` (on `workouts` and every `coach.stats` function)
resolves source workouts not yet in a month file in memory, by the same
rules as `history sync`, and returns them with `unsynced: true`; nothing is
written. `checkin prepare` uses it to read fresh data
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
  (Epley). Sets with `n > 12` give no e1RM (rn:autoregulation.5).
  Method recorded per point: `epley_rir` or `epley`.
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
(best set per exposure, oldest first), plus `data.best[exercise_id]`
`{e1rm, date}` over the window and `data.delta[exercise_id]` (latest
minus previous point, null with one point). `e1rm` and `load` are
rounded half up to 2 decimals; `load` is the number the formula used
(bodyweight plus added load for `bodyweight`). Body-measurement weights
come from the Hevy cache.

**Adherence per overlay.** `stats adherence (--overlay ID | --span A..B)`:

- Planned sessions: those of the overlay in force on each date (C10),
  up to today; later ones are `upcoming`.
- Session `status`: `trained` (a workout with the session's routine id,
  or for a manual workout its `session_id`, inside the overlay span,
  matched once, nearest date first; `moved: true` when the date differs;
  or a `trained_unlogged` annotation, with `unlogged: true`), `missed`
  (with `tag` from a `miss` annotation for that session inside the
  overlay span, each matched once, nearest date first; else `untagged`),
  `upcoming`.
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
- "Half the increment" uses `Library.increment`, else the equipment
  increment for the session's location (`equipment_for`, C54).
- Each session row: `session_id`, `date`, `title`, `overlay_id`,
  `status`, `workout_id`, `workout_date`, `moved`, `unlogged`, `tag` and
  `exercises`. A matching `miss` or `trained_unlogged` annotation names
  the session and a date inside its overlay's span. A conditioning
  session (C17) has `conditioning: true` and no exercises.
- `data.summary`: `planned` (sessions dated today or earlier),
  `trained`, `missed` (counts by tag), `missed_total`, `upcoming`, and
  `exercises` (counts by status). `data.extra` lists workouts in the
  window that matched no planned session.

**Delivered sets per muscle (dose).** `stats dose (--week W | --span A..B)`:

- A hard set is a logged working set (`normal`, `failure`, `dropset`) not
  logged at RPE 5 or below (rn:proximity-to-failure.5); each drop counts
  as one set.
- `coach.stats.set_weights(entry) -> dict[muscle, float]`: 1.0 for each
  primary muscle and 0.5 for each secondary muscle of an R-11 library
  entry. Delivered dose here and planned dose (C41) both call it.
- `direct`: hard sets where the muscle is a primary muscle of the
  exercise. `fractional`: hard sets weighted by `set_weights`.
- Output per week and per workout:
  `{"week": "2026-W41", "muscles": {"chest": {"direct": 6, "fractional": 7.5}}, "by_workout": {...}}`,
  plus `span` and `weeks` (one entry per week the span touches); `week`
  is null for a span that is not one week. A muscle with no hard set is
  left out.
- Logged workouts only. Coach-led sessions not logged in Hevy are added
  from `program.external_sessions` estimates by R-30a (C41), not here.

**Durations.** `stats durations [--week W | --span A..B]` (default:
every workout) → per workout
`{workout_id, date, title, session_id, minutes, cap_minutes, over_cap}`
(cap from C19; null for no cap). A logged workout over its cap gets flag
`duration_over_cap` (info), in `data.flags`.

**Convention-jump audit.** `stats audit [--weeks 8]`:

- Scope: exercises with load mode `per_hand_x2` or `single_implement`
  over the last N weeks (default 8).
- Candidate: an exposure whose top working load is 2× (±1 %) or 0.5×
  (±1 %) the previous exposure's, at the same top-set reps and the same
  RPE (or both unlogged).
- Each candidate lists `siblings`: the exercise ids of other candidates
  on the same date.
- Status `open` until a `discount` or `confirm` annotation names it
  (`discounted`, `confirmed`). Open candidates are `suspect` exposures
  (C17) and raise `convention_slip` (warn), in `data.flags`. Suspect
  exposures are found over the whole history; the command lists those
  in the window.
- The previous exposure is the newest earlier one that is a usable
  baseline: not discounted, not in an `unknown_convention` span, and not
  an open or discounted candidate.
- A candidate: `exercise_id`, `date`, `workout_id`, `session_id`,
  `load_mode`, `top_load`, `reps`, `rpe`, `ratio`, `previous` `{date,
  workout_id, top_load}`, `status`, `annotation_id`, `siblings`.

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
| `stale_prescription` | block | R-24 | | Line derived from an exposure outside the validity window and not decayed to its band, or above the `ILLNESS_RPE_CAP` (7) cap on the first session after an illness. |
| `unearned_load` | block | R-24 | | Load predicted beyond failure for the prescribed reps, or, with no e1RM, more than two increments above the last exposure. |
| `load_cap` | block | R-24 | | Load above `[caps]` or `dumbbell_max`. |
| `load_unrepresentable` | block | R-24 | | Load cannot be built from the available increments, dumbbells or plates. |
| `load_mode_mismatch` | block | R-24 | | Line's load mode or load arithmetic disagrees with the library or C5. |
| `rpe_infeasible` | warn | R-24 | | RPE target more than 1 away from the RPE implied by load, reps and current e1RM. |
| `session_over_cap` | warn | R-24 | | Estimated session duration above its cap. |
| `no_data` | warn | R-23a | | No usable exposure and no start load; load left empty for the coach. |
| `stalled` | warn | R-23a | | No metric or matched-work effort gain over three comparable slot exposures; a coaching heuristic, not a diagnosis. Suppressed when the final proposal advances load. |
| `prescription_unknown` | warn | R-23a | | Historical prescription unknown; no prescribed hit or miss inferred. Prescription validation still runs. |
| `linear_below_start` | info | R-23a | | Linear reset fell below the starting load; review progression without automatic adjustment. |
| `rpe_drift` | warn | R-23a | | Compound or recovery-capped exercise: logged RPE at least 1 over target on two or more working sets of the last exposure. |
| `return_week` | info | R-23a | | Decay applied; names the band and days off. A lifting line's flag adds the load change (`loads × 0.9`, or `assistance held` on an `assisted` line), the set change and any RPE cap. |
| `return_after_illness` | warn | R-23a | | An `ill` miss or status day in the gap: confirm `SYMPTOM_FREE_HOURS` (48) hours symptom-free; first session capped at RPE `ILLNESS_RPE_CAP` (7). |
| `constraint_applied` | info | R-23a | | A cap, a slot constraint or a niggle constraint changed the proposal. |
| `override_standing` | info | R-23a | | A standing override was applied again instead of the scheme's proposal. |
| `scheme_reset` | warn | R-23a | | A slot's scheme changed; its state restarted. |
| `rotation_unconfirmed` | warn | R-23a | | The schedule rule advanced the rotation without confirmation. |
| `niggle_escalate` | warn | R-27 | | Niggle reported three check-ins running, or worse: recommend a qualified professional. |
| `followup_due` | info | R-27 | | An open follow-up is past its review date. |
| `evidence_expired` | info | R-32 (module `coach/flags/research.py` added by R-23a) | | A plugin's cited research note has expired; the rationale says the evidence is under review. |
| `stale_routine` | warn | R-21a | | A routine for an active session does not hold the newest approved overlay's content: the last pass did not write and verify it. |
| `missed_day_rule` | info | R-22 | | A missed-day rule changed this line or session; the message names the rule. |
| `missed_rule_unmatched` | info | R-22 | | No missed-day rule matched; reprogram the rest of the week with `propose week --kind midweek` and a coach's brief. |
| `adherence_low` | warn | R-30a | | Trailing four ordinary weeks below 70 % of planned core and coach-led sessions. |
| `add_session_type_blocked` | warn | R-30a | yes | Adherence below 80 %: no new recurring session without a recorded override. |
| `restructure_required` | warn | R-30a | yes | Adherence below 70 % and no decision in effect: the check-in presents a smaller schedule. |
| `volume_undershoot` | warn | R-30a | yes | A muscle below its dose target, planned on core plus coach-led, or delivered in three of four ordinary weeks. |
| `session_volume_high` | warn, info | R-30a | yes | More than 11 fractional sets for one muscle in one session (warn planned, info logged) (rn:volume-frequency.3). |
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

- `provenance` is a required key on every v2 line, null or an object
  carrying all five keys above. In the draft it is optional.
- `provenance` null: a hand-built line. The R-24 validator then infers
  `derived_from` (the latest exposure of the exercise neither excluded
  nor `suspect` (C17), dated on or before the overlay's `created_at`
  date and before the line's session date); with `prescription check --write` it stores the result
  with `inferred: true`, and `scheme`, `decay` and `rationale` null.
- `derived_from` null inside a non-null `provenance`: no exposure (first
  time, start load).
- `decay` null: no decay applied. `band` is one of the C22 band ids.
- `scheme` and `rationale` are filled by R-23a; null in hand-built lines.
- The draft schema (`overlay_draft`) takes `schema_version` 2 with the
  overlay, since it changed too; a draft may leave the key out.
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
ILLNESS_RPE_CAP = 7
SYMPTOM_FREE_HOURS = 48    # R-21b; R-02's illness rule

coach.validity.band_for(days_off) -> Band
coach.validity.interval_days(exposures) -> int     # median of the last ≤4 gaps, clamped 7..14; 7 with <2 gaps
coach.validity.days_off(root, exercise_id, session_date) -> int | None
#   = max(layoff_days, exposure_age − interval_days), never below 0; None with no lifting workout and no exposure
#   layoff_days  = session_date − last_lifting_date(before=session_date)   (R-02: any lifting workout)
#   exposure_age = session_date − date of the newest non-excluded exposure of the exercise (any slot; suspect counts)
coach.validity.window_ok(exposure_age, interval) -> bool   # exposure_age ≤ interval_days + GRACE_DAYS
coach.validity.check_overlay(root, doc) -> list[flag]
coach.validity.report(root, doc, config=None) -> {"flags": [...], "lines": [...]}   # what the command prints
coach.validity.merge_flags(doc, flags), unresolved_blocks(doc, flags), fill_provenance(doc, lines)
coach.validity.estimate_minutes(root, session) -> int
```

- **Valid line**: `days_off` falls in band `0-10`, or the line's
  `provenance.decay.band` equals `band_for(days_off)` and its working
  load is at most the derived-from load × `load_factor` (plus one
  increment for rounding). For an `assisted` line, where more assistance
  is a lighter lift, the band cuts no assistance: its least working
  assistance is at least the derived-from exposure's least assistance
  minus one increment, and the message says the assistance is below the
  pre-layoff assistance. Anything else is `stale_prescription`. An
  exercise with no exposure (first time, start load) is never stale.
  A decayed line of an exercise that has exposures is stale when its
  `derived_from` is null, names a workout the history doesn't hold, or
  names a `suspect` exposure (C17): its load and sets can't be checked.
- Days off are measured to the line's session date. The band's set and
  RPE parts are checked as well as the load: at most `max(1, n +
  set_delta)` working sets, `n` being the derived-from exposure's
  working sets, and every working set at or under `rpe_cap` when the
  band has one. Loads compared are the coaching number (C18), the top
  working load on each side (the least assistance for `assisted`).
- A line with a `no_data` flag (C10) gets no R-24 flag but
  `load_mode_mismatch`.
- Illness (R-02, rn:detraining-return.4, a heuristic for mild illness
  above the neck): when an `ill` miss annotation or an `ill` status day
  (C50; `coach.statusdays.ill_in(root, span)`, added by R-43) falls in the
  gap, the first session of the span must cap every set at
  `ILLNESS_RPE_CAP` (RPE 7); R-23a applies it and raises
  `return_after_illness`; R-24 checks it and raises `stale_prescription`
  on each line of that session with a working set over the cap or
  without an RPE. Text the athlete reads takes the 48 hours and the cap
  from `SYMPTOM_FREE_HOURS` and `ILLNESS_RPE_CAP`, never a literal. The
  gap runs from the day after the last lifting workout to the day before
  that session.
  R-24 reads `coach.statusdays` only once R-43 has added it.
- **Feasibility** uses C18's `implied_rpe` with the best e1RM point in
  the 42 days before the session date (none older): implied RPE above
  10.5 is `unearned_load`; otherwise an RPE target more than 1 from the
  implied RPE is `rpe_infeasible` (rn:autoregulation.6). Only working
  sets of `total`, `per_hand_x2` and `single_implement` lines are judged
  this way; a rep range is judged at its start. With no e1RM point (and for
  `bodyweight` lines, whose added load has no e1RM), a top working load
  more than two increments (`Library.increment`, else the equipment
  increment) above the newest exposure neither excluded nor `suspect`
  is `unearned_load`. `assisted`
  lines are not judged.
- **Duration estimate** per session: Σ over sets of (reps × 4 s, or
  `duration_seconds`) + `rest_seconds` between sets, + 60 s per exercise,
  + 300 s warm-up; scaled by the median of actual ÷ estimated minutes over
  the session's last four logged workouts (when two or more exist),
  clamped 0.7 to 1.5. Above the C19 cap is `session_over_cap`. A rep
  range counts its end. A logged workout is estimated from its logged
  sets with the overlay session's rest for each exercise (the mean of
  its rests for an exercise it lacks). The session's logged workouts
  are those carrying its `session_id` or one of its routines (its
  `hevy_routine_id`, or a routine `data/state.json` maps to it), dated
  before it. Every constant here is a heuristic, not a measured value.
- **Equipment** comes from `coach.config.equipment_for(config,
  location)` (C54) with the overlay session's `location`.
- **Caps** follow the R-16 `load_caps` rule exactly: `[caps]` id first,
  else `dumbbell_max` per hand for per-hand modes.
- **Representable**: barbell totals have a `units.plate_breakdown`;
  per-hand loads are in `dumbbells` when that list is non-empty (C4;
  empty means not checked, since racks are not regular multiples of one
  increment). Which applies follows the library entry's `equipment`:
  `barbell` with `total`, `dumbbell` with a per-hand mode. Other
  equipment (machine, cable, kettlebell, other bars) is not checked. A
  load already over its cap is flagged `load_cap` only.
- `load_mode_mismatch` reuses R-13's `overlay.validate` and R-11's
  `effective_load_mode`; R-24 adds no new arithmetic.

`prescription check (--overlay ID | --file PATH) [--write] [--dry-run]`
returns `data.flags`, `data.summary` (counts by severity) and
`data.lines`, one per line: `session_id`, `date`, `exercise_id`,
`days_off`, `band`, `derived_from` and `inferred`. It exits 0 whatever
it finds. `--file` takes an overlay or an overlay draft; a draft is
built in memory, as `overlay build` would, and never written. A schema
problem exits 1; load arithmetic problems become `load_mode_mismatch`
flags. `--write` takes `--overlay` only (exit 2 otherwise); it merges
its flags into the overlay (replacing earlier R-24 flags, keeping
`resolved` and `resolution` on identical ones, which match on code,
severity, session, exercise and message) and fills inferred provenance;
it refuses (exit 3) on an overlay with any `approval`. Check
`prescription_valid`: overlays in force on some day from today on have
no R-24 `block` finding that the overlay does not hold as an identical,
resolved flag (fail).

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
the pure e1RM functions `coach.stats.e1rm`, `load_for` and
`implied_rpe` (not the module, whose other functions read the
instance), `math`, `dataclasses`, `typing`, `datetime`. A dotted
`import a.b` needs `as <name>`, since it would bind the whole `a`
package. They never build load objects or convert units. An AST test
covers `coach/plugins/**`; `plugins validate` runs the same scanner on
instance plugins, plus the C5 ×2 scan.

**Units.** Every load a plugin sees or returns is the coaching number in
athlete units (C18). The core then applies, in order: decay, the week's
transform, constraints (C26), caps, rounding to increments (toward the
lighter lift when the load is below the derived-from load, nearest
otherwise), and only then `units.make_load`. A plugin therefore cannot
double a load.

```python
@dataclass(frozen=True)
class SchemeContext:
    today: date; session_date: date; unit: str; week_kind: str   # weekly | midweek | deload
    exercise: ExerciseInfo        # id, pattern, muscles, equipment, load_mode, increment, is_compound,
                                  # load_direction (+1; −1 for assisted)
    slot: SlotInfo                # session_id, set groups, rest_seconds, cues, constraints, start_load
    params: dict                  # validated, defaults filled
    state: dict                   # validated; INITIAL when absent or after a scheme change
    exposures: tuple[Exposure, ...]          # same session/exercise/load mode, newest first; suspect/excluded marked
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
fewer per exercise (never below one), RPE capped for `43+`. Assistance
is never cut: an `assisted` line (`load_direction` −1) keeps at least
the derived-from exposure's least assistance instead. A scheme
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
| `standard` | R-23a | `set_factor` 0.67, `load_factor` 0.9, `rpe` 6 | bodyweight work cut by sets and taken further from failure; assisted work keeps its assistance |
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

**Program v2 and the next state version** (R-23a bumps C16, migration steps through R-17a):

- `program.json` 2: `scheme.name`, `schedule.rule` and
  `blocks.deload_rule.name` are any registered plugin name of the right
  kind (no fixed enum); each `params` is validated against that plugin's
  `PARAMS` by `program validate`; exercise `constraints` items take the
  C26 shape. Migration: names unchanged, `constraints` emptied with a
  report row for any v1 free-form entry.
- `state.json` 3 (R-14b took 2): `scheme_state["<session_id>/<exercise_id>"]` becomes
  `{"scheme": name, "data": {...}, "pending": null | {"overlay_id": id, "data": {...}}}`;
  `data` validated against the scheme's `STATE`. Migration wraps v2
  entries with `scheme: null`, since the state alone does not name the
  scheme; the next `propose week` adopts the slot's current scheme
  (its `data` when it fits the scheme's `STATE`, else `initial`, with no
  `scheme_reset`). `rotation` gains `week`: the start date of the week
  its `position` names, or null (read as the week holding today).
- Scheme state advances only through approval: `propose finalize` writes
  `pending`; the next `propose week` promotes `pending` to `data` when
  that overlay is approved with a matching hash, and drops it otherwise.
  A deload run writes no pending state: a deload never advances a
  scheme.

**Built with R-23a** (additions to the shapes above):

- `SchemeContext` also carries `scheme` (the slot's scheme name) and
  `scheme_deload` (that scheme's `deload`, or None), so the `scheme`
  transform needs no import. A transform's `apply` gets the context with
  `params` replaced by the transform's own merged `PARAMS`.
- `Proposal` also carries `round_down` (default false): a scheme whose
  load is an estimate (`fixed_reps_rpe`) asks for its loads rounded
  down; decay and the deload transforms set it too.
- The `Exposure` a plugin sees is `coach.plugins.base.Exposure`: C17's
  fields with every load as the coaching number, plus `prescribed` (the
  working sets the overlay in force that day asked for; empty when unknown)
  and `week_kind` (that overlay's kind). Logged sets retain reps, duration
  and distance as well as load and RPE. Unknown historical prescriptions
  are never filled from today's program: linear and ladder hold, double
  progression holds load, and `prescription_unknown` makes the uncertainty
  explicit.
  `base.missed` returns None for unknown prescriptions. Progression history
  matches the session, exercise and load mode; e1RM and layoff evidence
  remain exercise-wide. The three-exposure stall heuristic compares equal
  working-set counts with known metrics: more load (less assistance), more
  reps at that load, more duration/distance, or lower RPE at otherwise
  matched work. Missing metrics or a changed load mode/set count cannot
  establish a stall. A final advancing load suppresses the warning.
  `base.baseline(exposures)` is the exposure loads derive from: the
  newest neither excluded, `suspect` nor trained in a `deload` week. The
  core refuses a proposal derived from an excluded or suspect exposure.
- `last_prescription` is `{overlay_id, session_id, date, exercise_id,
  load_mode, sets, override}` with `sets` as `base.SetSpec`s.
- A scheme may define `LOAD_MODES`, a tuple of the load modes it can
  program (absent: every mode). `program validate` refuses a slot whose
  `load_mode` it leaves out, at `$.sessions[i].exercises[j].scheme.name`,
  and `plugins show` lists it as `load_modes`. `fixed_reps_rpe` takes
  `base.E1RM_MODES` (`total`, `per_hand_x2`, `single_implement`): a
  bodyweight or assisted e1RM is of the system load, not the added load
  or assistance the line prescribes.
- `double_progression` judges "reached the top" against the slot's
  program rep range, and takes only the RPE targets and set count from
  the exposure's `prescribed`: its own overlay lines ask for fixed reps
  below the top.
- The pipeline reads caps through `coach.checks.instance.cap_for(config,
  exercise_id, mode, location)` (R-16's `load_caps` rule) and increments
  through `coach.stats.load_increment(library, config, exercise_id,
  location)`; R-24's validator calls the same two.
- A schedule rule may define `problems(params, program) -> [(path,
  message)]` for what its schema cannot say (session ids the program
  lacks); `program validate` reports them under `$.schedule.params`.
  A plan's `rotation` is `{position, confirmed, week}`.
- `base.default_decay` cuts each working load from the lower of the
  proposal and the derived-from load, so a return week never carries a
  progression; it keeps `max(1, min(proposal sets, derived-from sets) +
  set_delta)` working sets. The load cut goes through
  `base.lightened(sets, factor, source, load_direction=1)`, which the
  `standard`, `light` and `return` transforms use too: for `assisted`
  it raises each working set to at least the derived-from least
  assistance and applies no factor.
  `base.standard_deload(proposal, set_factor, load_factor, rpe,
  load_direction=1)` takes the line's direction the same way.
- **Rounding** (step 3 of C24): a load equal to one the slot already
  knows (the derived-from load, a load of the last approved line, the
  start load) stays as it is. Otherwise a per-hand dumbbell load snaps to
  the location's `dumbbells` when that list is set; any other load
  rounds to the increment (`Library.increment`, else the equipment
  increment) on a grid anchored at the derived-from load (else the last
  approved load, else the start load, else 0). A load below the
  derived-from load, or one the proposal marks `round_down`, rounds
  toward the lighter lift: down, or up for `assisted`, where more
  assistance is a lighter lift. A load clipped by a cap or a load
  constraint is not rounded toward the heavier lift. No rounding goes
  past the cap, even when that leaves assistance below the derived-from
  least assistance.

**Built with R-23b** (the remaining schemes and schedule rules):

- `coach.plugins.base` gains three public helpers, so a scheme with its
  own `decay` reads C22's numbers without importing `coach.validity`:
  `return_band(days_off)` (the band), `bands_back(days_off)` (0 for
  `0-10`, 1 for `11-21`, and so on) and `return_set_count(proposal,
  set_delta)` (the `max(1, min(proposal, derived-from) + set_delta)`
  rule `default_decay` also uses).
- `rpe_anchored` params: `top_reps`, `top_rpe`, `backoff_sets`,
  `backoff_reps` (each null by default: the program's first working set
  is the top set, its other working sets the back-offs, their reps those
  of a second working set group, else the top set's), `backoff_rpe`
  (null: the RPE of a second working set group, else `top_rpe` − 1),
  `backoff_pct` (null).
  The e1RM comes from the newest valid exposure's heaviest working set
  when it logged reps and an RPE (C18 `e1rm`), else `ctx.e1rm`. The top
  set is `load_for(e1rm, top_reps, top_rpe)` floored to the increment.
  Each back-off is `load_for(e1rm, backoff_reps, backoff_rpe)` floored
  to the increment and never above the top-set load; a set `backoff_pct`
  overrides that, loading the back-offs at `backoff_pct` of the floored
  top-set load. Either way the back-offs carry `rpe = backoff_rpe`, and
  the rationale names the rule that set their load.
  With no e1RM, or no top-set reps or RPE, the top set holds at the last
  or start load and the back-offs sit at `backoff_pct` (0.9 when null)
  of it. When the back-offs have a programmed effort target (the
  `backoff_rpe` param, or an RPE on any program working set after the
  first), they carry the same `backoff_rpe` as with an e1RM; otherwise
  they carry none. With no e1RM the rationale calls the loads
  provisional; with no load to hold it leaves the first loads to the
  coach.
  `round_down` is set when the e1RM sets the loads. State is empty.
  `LOAD_MODES` is `E1RM_MODES`.
- `wave_531` params: `training_max` (null: `training_max_pct`, 0.9, of
  `ctx.e1rm`), `increment_upper` and `increment_lower` (null: 2.5 and 5
  in kg, 5 and 10 in lb), `region` (null: lower for the squat, hinge,
  lunge, knee, calf and hip patterns, else upper), `amrap` (true: the
  last set of each wave week is type `failure`, its `reps` the minimum).
  State `{wave_week 0..3, training_max, proposed_for, proposed_on}`:
  `proposed_for` is the latest session date proposed at this wave week,
  `proposed_on` the `today` of that run. A `weekly` run advances one
  wave week. It repeats the week for a later session of the same run
  (`proposed_on` is today) and for a session on or before
  `proposed_for` (a weekly run again over a week already proposed). A
  `midweek` or `deload` run always repeats it. Session-date distance
  alone can't decide, because `next_in_sequence`,
  `alternating_external_anchor` and `explicit_calendar` move a
  session's weekday from week to week. Two weekly runs on the same day
  for consecutive weeks therefore repeat the week in the second.
  After week 3 the next proposal starts week 1 with the training max
  raised. A deload run (`scheme` transform) calls its `deload`: 40/50/60 %
  × 5 of the lower of the stored and the proposed training max, so the
  raise waits for the next wave. Its `decay` takes the lower of the
  stored and the proposed training max, so a return week never carries
  a wave's raise, and lowers it by the band's `load_factor` (kept in
  state). It rebuilds the week without a `failure` set, keeps `return_set_count` sets, caps each load at the
  derived-from load × `load_factor` and applies the band's RPE cap, so
  the line passes R-24's decay check. With no training max and no
  e1RM it holds the program's sets at the last or start load.
  `LOAD_MODES` is `E1RM_MODES`.
- `assistance_ladder` params: `rungs` (ordered easiest first, each
  `{name, load}`; `load` is the assistance for `assisted`, the added load
  for `bodyweight`, where null means 0, and null for `band`), `reps`,
  `sets`, `rpe` (null: the program's). State `{rung, through}`. A
  proposal moves up at most one rung, to the top rung at most: when the
  newest valid exposure after `through` (the newest overall when
  `through` is null) logged every target set at its target reps (the
  top of a range) at or under the target RPE. A slot trained twice a
  week therefore climbs one rung a week, never two. `target_note` names
  the rung. `decay` steps back `bands_back(days_off)` rungs from the
  lower of the stored and the proposed rung (never below the first),
  so a climb never reaches a return week, with the band's set cut and
  RPE cap and no load cut. `LOAD_MODES` is `bodyweight`, `assisted`
  and `band`.
- `maintenance` repeats the newest valid exposure's top load with the
  fewest reps logged at that load, at the program's working set count
  and RPE targets; with none, the start load. State is empty.
- `next_in_sequence`: `rotation.position` is the session last trained
  before the week `rotation.week` starts, and `positions` is the
  sequence. A span week `n` weeks after `rotation.week` assumes every
  slot in between was trained (`n × len(days)` sessions on) and raises
  `rotation_unconfirmed`, as does a missing or unknown position (the
  sequence then starts at its first session). Slots run in calendar
  order from the week start; a midweek span keeps the week's earlier
  slots. `schedule confirm --position S --week W` records S as the last
  session trained before W (the week holding tomorrow by default).
  `problems` reports unknown and repeated sessions and repeated days.
- `explicit_calendar` plans exactly its `dates` inside the span, has no
  positions, and its `problems` report keys that are not
  `YYYY-MM-DD` dates and unknown sessions.
- No new flag codes, no change to the loader, pipeline, contexts,
  decisions or constraints.

## C24. Proposal pipeline and `coach propose` (R-23a; R-21b, R-22, R-25, R-26, R-30b, R-31, R-40a, R-41a, R-43, R-44a, R-44b read)

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
id follows C10. `data.lines_digest` (R-21b) is the C7 canonical hash of
`data.lines`; `propose show` returns it too.

- `propose override --proposal ID --session S --exercise E (--sets SPEC | --load N) --reason TEXT [--standing [--until D]]`
  changes one line, keeps the original in the line's C10 `override.proposed_sets`,
  and records a C25 decision when standing.
- `propose resolve --proposal ID --flag INDEX --resolution TEXT` resolves
  one flag on the draft.
- `propose restore --proposal ID --session S --reason TEXT [--dry-run]` (R-44b) puts
  a dropped conditioning session back and resolves its flag with the
  reason; finalize accepts it.
- `propose finalize --proposal ID [--dry-run]` re-runs step 5. It exits
  1 if any line differs from `.proposed.json` without `override.reason`,
  and exits 3 if a `block` flag is unresolved. Otherwise it writes the
  overlay, decisions and pending scheme state.

A hand edit of the draft is allowed; finalize catches unexplained
changes. One-off weeks for travel or limited kit (`program-week`'s
constrained mode) stay coach-built through `overlay build`.

**Built with R-23a** (details the steps above leave open):

- Default span: the week holding tomorrow. `--kind midweek` starts the
  span at today when today falls inside the week. A run that plans no
  active session exits 1.
- `--kind deload` writes overlay kind `deload` whose sessions keep their
  program session ids, are `temporary: true` (so R-14b gives them
  temporary routines, as `program-week`'s light mode expects) and are titled
  `Deload — <session title>`. `--transform NAME` applies that transform
  to any kind; a deload with none uses the program's `deload_rule`.
- The `--plan FILE` shape is `schedule plan`'s output:
  `{"sessions": [{"date", "session_id"}], "flags": [...]}`; other keys
  are ignored and the rotation is left unchanged.
- `propose override` takes `--sets SPEC`, comma-separated groups
  `COUNTxREPS[-REPS][@LOAD][ rpeN]` (`"3x5@95 rpe7"`), which replace the
  line's working sets and keep its warm-ups, or `--load N`. It re-runs
  the R-24 check and stores the merged flags in the draft, so a block an
  override creates can be resolved there. A standing override's decision
  is appended when the command runs.
- `propose finalize` also appends a one-week override decision
  (`standing: false`, `until` the overlay's span end) for each line whose
  `override` no decision yet records.
- `propose show ID` returns the built overlay, `lines`, `unexplained`
  (what finalize would refuse with exit 1) and `unresolved_blocks`.
- `schedule confirm --position P [--week W]` records the position for
  the week holding tomorrow by default, with `confirmed_at` today.
- Steps 5a and 5b are left to R-43 and R-44b, which own those providers.
- R-23a adds the status provider `proposal` (C52, order 35): drafts in
  `.coach/proposals/` with no overlay yet, at `attention`.

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
  the core keeps `chosen_sets` (re-deriving loads only through decay,
  the load constraints, the illness cap, caps and rounding), puts the scheme's own proposal in the rationale, and raises
  `override_standing`. A one-week override (not standing) is only
  information to the scheme.
- Standing overrides need an `until` date, default four weeks after
  `made_at`, at most eight. Renewing one is another `propose override
  --standing`: the newest active decision for a scope wins.
- `details` per kind, checked by `coach.decisions.problems` (the JSON
  schema subset has no per-kind branching): `adherence_trigger` requires
  `rule`, `adherence_pct` (0–100) and `weeks` (dates); `light_week`
  requires `type` (`deload`, `light`, `return`), `week` (a date),
  `reason`, `triggers` (strings) and `hard_weeks` (integer). An override
  scope names both ids; other kinds' scope is `{}` and they carry no
  sets. Check `decisions_schema`: the file passes the schema and these
  rules (skip when there is no file).

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
  (with reason), or defer/keep (with a new `review_at`). `render` only
  prints (read-only); the coach puts its text in the record.
- `coach.followups.due(doc, today)` and `coach.followups.render_deep(doc,
  day)` take the loaded document first, as `active_constraints` does.
- Commands (R-27): `followups add --text T --review-at D --source S
  [--raised D]`, `followups resolve ID [--note]`, `followups drop ID
  --reason T`, `followups defer ID --to D [--kept] [--note]`. Events are
  dated today. `defer` records `kept` with `--kept` (reviewed, still
  open) and `deferred` without it. A closed item takes no further
  events.

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
  `aggravated` from a better one (the entry before it is `watching`,
  `easing` or `resolved`). It is a week-level flag in `propose week` and
  the R-21a card, and `niggles list` gives each row's `escalate` reason.
- `history` holds one entry per check-in day: `niggles update ID
  [--status S] [--note T] [--mention]` adds today's entry, or replaces
  it when today already has one. `--mention` bumps `mentions` and
  `last_noted` once a day. `niggles resolve ID` sets `resolved`. The
  newest entry's status equals `status`.
- Whether a row's constraints apply on a date reads its status on that
  date: the newest `history` entry on or before it (none: not yet
  noted). `coach.niggles.active_constraints(doc, entry, on_date)` returns
  the matching constraints with `source` set to the niggle id; a row
  matches a library entry by `applies_to.exercises` (its id) or
  `applies_to.patterns` (its pattern). `niggles constraints [--session
  S]` lists each program line a niggle constrains today.
- `niggles add|update` set `applies_to` with `--pattern`, `--exercise`
  and `--activity-kinds` (comma-separated; an empty value clears) and
  constraints with `--constraint KIND[=VALUE]` (repeatable; `reason` is
  the niggle's area; `update --clear-constraints` removes them). An
  unknown pattern, exercise id, activity kind or constraint exits 1
  naming the valid values. Check `niggles_schema` fails on the same.
- R-31 reads `aggravated` as its "niggle under load" fatigue trigger.
- `niggles import --from-profile [--chronic I[,I...]] [--dry-run]`
  parses the template's `### Niggle log` table (`Area · First noted ·
  Last noted · Mentions · Status · Notes`) into rows with no
  constraints, for the coach to add; each row's one history entry is
  dated its Last noted. Its output also numbers every other line of the
  "Injuries / limitations" section (`lines`, from 1); `--chronic` turns
  those lines into `chronic` rows (area = the line, noted today, empty
  `applies_to`), and unmarked lines are not imported. It refuses (exit
  1) when `data/niggles.json` already has rows, and never edits
  `profile.md`.
- R-27 builds `activity_kinds` and `chronic` into niggles v1. If R-27 has
  merged without `activity_kinds`, R-43 adds it with a schema bump (an
  empty list on every row).
- R-27 also ships the C36 card part `niggles` (the Niggles field names
  each open row; due follow-ups as facts; `followup_due` and
  `niggle_escalate` flags) and the C52 status providers `followups`
  (order 55, due items) and `niggles` (order 56, aggravated and
  escalating rows), both at `attention`. Checks: `followups_schema`,
  `niggles_schema`. Both files are migration-runner documents (C16).

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
text = "Deloads may be pre-planned or triggered by fatigue at any point in a block."
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
0; exit 1 only if a note fails validation. An unknown `--area` is a usage
error (exit 2) naming the schema's valid areas. A valid area with no notes
returns an empty `notes` list successfully; it is not claimed as current.

**`research show REF`**: REF is a note id (data block, status, path) or a
claim ref, with or without its `rn:` prefix (claim, its sources in full,
its note's status, and the local note superseding it, if any). Unknown
REF exits 1.

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
  appended, and each keeps the version it was written at: `migrate run`
  never touches these files. A version bump keeps a reader for every
  older line version; a line newer than the coach reads fails with "run
  /framework-sync". For each `id`, the last line wins. `op` is `upsert` or `void`;
  a `void` line carries `id`, `source`, `recorded_at`, a non-empty
  `reason` and `by` (`athlete` from a `void` command, `sync` from an
  adapter), and removes the record from every view. Schema:
  `activity_void`, shared by all three files.
- `id` is `<source>:<source-specific id>`, pattern
  `^[a-z_]+:[A-Za-z0-9._:-]+$`. Source names match the `[sources.<name>]`
  tables (C32) plus `manual` and, for planned activities, `coach`. Manual
  ids are deterministic: `manual:<local_date>-<kind>-<n>` for activities
  and planned activities (`n` is the next number never used for that date
  and kind), and `manual:<date>-wellness` or
  `manual:<start>..<end>-wellness` for wellness. `wellness add` for a day
  or span that already has a manual record updates it, keeping the
  readings it was not given.
- `recorded_at` is when the line was written (UTC). `content_hash` is the
  canonical hash (C7) of the record without `op`, `recorded_at` and
  `content_hash`. A sync appends only when it differs from the last line
  for that id. When that last line is a void, an athlete's void stands
  until the source changes the record (the hash differs from the last
  upsert before the void), and a sync's void gives way as soon as the
  record comes back. A sync appends a void only for a live record.
- Dedup and precedence are a read-time view, never a rewrite: records of
  the same kind whose starts lie within `dedup_window_minutes` of the
  group's earliest start form one Activity, and one source never merges
  with itself (two manual runs ten minutes apart stay two). The
  highest-precedence source (C32) supplies each field, and lower ones fill
  fields it lacks; sources not in `precedence` rank last, and within one
  source the newest `recorded_at` wins. Wellness resolves per day and per
  field by the same precedence; `sleep` is one field (an object with
  either hours set counts as a value); a span record fills only days with
  no daily value.
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
  - `records(kind, include_void=False)`: the last raw line per id, voided
    ids left out unless `include_void`; `lines(kind)` gives every line
    in file order and `history(kind, id)` one id's lines, for audits and
    tests. `kind` is `activity`, `wellness` or `planned`.
- A file that fails validation makes every reader exit 1, naming the
  file, the line number and the JSONPath.
- Readers: R-43 (activities, planned, wellness for `sleep_debt`), R-44b
  (conditioning Activities), R-46 (writes planned records with `source:
  "coach"`; reads run history), R-31 (`sleep_summary` through R-43's
  `sleep_debt`), R-21a (activity records for the card's runs and sleep
  lines).
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

- Readers get records without `schema_version`, `op`, `recorded_at` and
  `content_hash`; resolved Activities and wellness days are built from
  those fields only. `field_sources` leaves out `id`, `source` and
  `source_id`, which are the winner's.

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
CONFIG = {"enabled": Key("boolean", default=False), "path": Key("string", default="")}
                                 # the [sources.<NAME>] keys; absent only for "manual"
FRESH_BY = "records"             # optional: "sync" judges freshness by the last sync
def is_enabled(config) -> bool: ...  # optional: when the source needs more than its own switch
def fetch_file(ctx, path, sync_state) -> FetchResult: ...  # optional: `activity import` of one file
def anonymise(ctx, path, out_dir, dry_run) -> dict: ...     # optional: `activity anonymise`

def fetch(ctx, sync_state: dict) -> FetchResult: ...
    # reads the source; never writes. FetchResult(items, sync_state, warnings, info),
    # from coach.activity.adapters; `info` is merged into the source's report row.
def normalise(item, ctx) -> list[dict]: ...
    # pure: one raw item -> zero or more C30 records (without content_hash/recorded_at),
    # or a void {"op": "void", "id", "source", "reason"}.
    # A drop raises coach.activity.adapters.Drop(reason), never passes silently.
```

- `coach/config_tables/activity.py` builds `[sources.<NAME>]` from every
  adapter's `CONFIG`, so a new adapter is one new file: its config table,
  sync and status come with it.
- A normalised record goes to the file its shape names: `span` is
  wellness, `date` is planned, anything else is an activity. A void goes
  to whichever of the adapter's `KINDS` files holds the id. Every line is
  validated before anything is appended; an invalid record, or a file
  outside `KINDS`, fails that adapter.
- `activity sync` reports, per source, `records` (`{file kind: count}` of
  the upserts the source normalised, changed or not), `appended`,
  `voided`, `dropped` (`{reason: count}`), `last_sync_at` and the keys of
  the adapter's `info`, and warns once per drop reason with its count.
- `activity import --source NAME --file PATH [--dry-run]` runs one file
  through the source's `fetch_file` and appends exactly as a sync does.
  The source need not be enabled (a backfill can come before the folder
  is set up). It writes the returned state to the sync map, with
  `last_sync_at` set to now, only when the state or a record changed; a
  source without `fetch_file` is exit 2. Errors in the file are exit 1,
  not a warning. `activity anonymise` needs `[activity] enabled` like
  every activity command, and a source without `anonymise` is exit 2.

- `activity sync` runs every enabled adapter: `fetch`, `normalise`, hash,
  append changed records, then write the adapter's returned `sync_state`
  into the sync map. One adapter failing reports a warning and leaves the
  others' results and its own previous sync state untouched. It writes
  local files only; it never stages or commits.
- `data/activity/sync.json` (schema `activity_sync`):

```json
{"schema_version": 1,
 "sources": {
   "hevy_conditioning": {"last_sync_at": "2026-10-11T18:00:00Z", "state": {"seen_workout_ids": ["..."]}},
   "apple_health": {"last_sync_at": "2026-10-11T18:00:00Z",
                    "state": {"files": {"Metrics/HealthAutoExport-2026-10-10.json": "sha256:...",
                                        "Workouts/HealthAutoExport-2026-10-10.json": "sha256:..."}}}
 }}
```

  `state` is the adapter's own object; nothing else reads it. The file
  holds file names, hashes and cursors, no health values.
- Gaps are reported, not filled: `activity status` lists `manual` and each
  enabled source with `last_sync_at` (null for `manual`), live record
  counts per file it writes, the newest dated record (activity
  `local_date` or wellness `span.end`), and the days in the last 14 with
  no wellness record from that source (`missing_days`, null for a source
  that writes no wellness).
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
  `RPE n` parsing.
  - Library match is by Hevy template id, then by title. A workout's
    kind comes from the table only when every exercise maps to the same
    kind; the routine rule always gives `conditioning`.
  - Its sync state is `seen_workout_ids`, the workouts that are
    Activities now. A seen id that stops being one is voided: "deleted in
    Hevy" when it left the cache, "no longer a conditioning workout in
    Hevy" when it is still there. With no cache at all it warns and
    changes nothing.
  - It reads `data/state.json` and `data/program.json` through R-17a's
    loaders when both exist, and applies no routine rule when either is
    absent. A malformed one fails the source, so it never voids the
    routine-mapped Activities.
  - Lifting workouts are dropped with the reason "lifting workout; Hevy is
    the lifting logbook".
  - `FRESH_BY = "sync"`: its freshness is the last sync, since a week
    without conditioning is not a broken source.

- **`apple_health` adapter** (R-42b). Reads Health Auto Export's Version 2
  JSON (vendor format pages: Export Format, Health Metrics, Workouts,
  Manual Export, Sync to iCloud Drive at help.healthyapps.dev).
  - Each Health Auto Export automation exports one data type (Health
    Metrics or Workouts) into its own folder, `AutoExport/<automation
    name>/`, so `path` names `AutoExport/` or any folder holding both
    automation folders. `activity sync` reads every `*.json` under
    `[sources.apple_health] path`, subfolders included (`~` expanded;
    relative to the instance root; hidden folders skipped), whose
    content hash is not a value in the sync state, in relative-path
    order and in place. Its state is `{"files": {<relative path>:
    "sha256:..."}}`, keyed by each file's path relative to `path`, so
    two automations' same-named day files never share a key; `info` is
    `files_read`, in the same relative paths. `activity import` keys the
    file by its base name and reports `file` and `already_seen`.
  - Refused with the setting to change: a CSV file ("set Export Format to
    JSON") and a Version 1 file, told apart by a workout without `id` or
    `duration` ("set Export Version to Export Version 2"). In a folder
    sync each is a warning and the file stays unread; on import, exit 1.
    An iCloud placeholder (`.<name>.json.icloud`) is a warning naming
    `brctl download`.
  - Workouts become Activities with id `apple_health:<workout id>`,
    `utc_offset` from the start's offset, distance and elevation through
    `coach.units`, `active_kcal` from kcal or kJ, `avg_hr`/`max_hr` from
    `heartRate` (else `avgHeartRate`/`maxHeartRate`), `indoor` from
    `isIndoor` (else `location`), `device` the workout's `source`.
    Drops, in order: a `source` naming an app in `drop_source_names`
    ("written to Apple Health by <app>, which is in drop_source_names");
    a name the table maps to lifting ("lifting workout; Hevy is the
    lifting logbook"); with `Hevy` in `drop_source_names`, a workout with
    no `source` starting within `dedup_window_minutes` of any cached Hevy
    workout's start ("no source, and it starts within N minutes of a Hevy
    workout"). With no Hevy cache that last check is skipped with a
    warning.
  - Metrics become one wellness record per day, id `apple_health:<date>`.
    A day's record keeps the previous `apple_health` record's readings
    for fields this file does not carry, so a file holding only some
    metrics never erases the rest. Unknown metric names are ignored with
    one summary warning; unsummarised sleep segments are ignored with a
    warning naming Summarize Data; readings in units the table does not
    accept are left out with a counted warning. Mass is stored in kg
    through `coach.units`.
  - Every mapping the vendor docs leave open (workout names to kinds,
    metric names to wellness fields with their units and how a day's
    entries combine, the sleep fields and the sleep-date rule) lives in
    the one `MAPPING` table in the adapter, for R-42c to correct against
    a real export.
  - The anonymiser (`activity anonymise`) writes
    `<out>/health-auto-export.json` marked `"x-anonymised": true`. It
    keeps only `metrics` and `workouts`; drops `route` and `metadata`;
    shifts every date by more whole weeks than the dates anywhere in the
    file span, so no shifted date equals an original; replaces every
    `id` with a salted fake UUID (deterministic within a run) and every
    `source`/`device` name part other than `Hevy` with `Device N`; and
    moves every number by 0.5 to 3 % (integers stay integers). It
    refuses to write when any original id, timestamp or source name
    survives, or any `yyyy-MM-dd` substring of the original file, so a
    date in a format it does not shift (an ISO `T` timestamp, fractional
    seconds, a date inside longer text) blocks the fixture instead of
    leaking. The salt is random per run and never stored.
  - Fixtures: `tests/fixtures/apple_health/` (synthetic, `"x-synthetic":
    true`).

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
  otherwise `config validate` exits 5 naming the key. The rule (a C4
  `RULES` entry) applies only while `[activity] enabled = true`; a
  repeat is always an error. Names of sources this install does not have
  yet (`apple_health` before R-42b) are allowed.
- `manual` is always available and has no table.
- Each later adapter adds its own `[sources.<name>]` table in its PR.
- Moving the wellness file when `wellness_in_git` flips is a manual step:
  the check fails and names the exact `mv` (and `git rm --cached` when
  moving out of git), or `cat src >> dst && rm src` when both files exist.
- Checks (R-42a): `activity_records_valid` (every line of the activity,
  planned and both wellness files, and `sync.json`; one `fail` per
  problem, naming file, line and JSONPath), `activity_wellness_location`,
  `activity_source_fresh` (`warn` per enabled source past
  `gap_warn_days`). All three `skip` while `[activity] enabled = false`.
- `activity list`, `wellness list|summary` and `planned list` take
  `--from`/`--to`; either left out falls back to the week holding today.

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

Settled while building R-33b (`coach/schemas/recipe_card.schema.json` is
the block after TOML parsing):

- Required keys: `schema_version`, `title`, `slots` (at least one),
  `servings` (integer, at least 1), `prep`, `time_min` (integer), `status`,
  `nutrition`, `per_serving`. Optional: `source` (http or https URL),
  `tags` (`^[a-z0-9]+(-[a-z0-9]+)*$`), `ingredients`, `variations`. Item
  strings have no capitals; aisles are lowercase with hyphens; a variation
  `name` matches `^[a-z0-9+][a-z0-9+-]*$` (so `+egg` is allowed); every
  table is closed (`additionalProperties: false`).
- Macro sum: `gap = |kcal − (4·protein + 4·carbs + 9·fat)|`, a percentage
  of the stated `kcal`. Warn when `gap > kcal × warn_pct / 100`, fail when
  `gap > kcal × fail_pct / 100`. A variation `delta` is checked the same
  way, with both limits raised to at least 20 kcal.
- Density: protein per 100 kcal against each slot of the card; a warn,
  never a fail.
- Ingredients: an item appears once per card; a `prep = "eat-out"` card
  has none and every other card has at least one. A change to an existing
  item uses that item's unit and may not take it below zero; a change to
  an unknown item must be positive and carry `aisle`. A variation of a
  non-eat-out card with no `changes` warns (shopping lists ignore it).
  Aisles outside `[nutrition.bank] aisles` warn.
- Slots outside the configured slots fail.
- The rendered region sits after the block; `recipes render` inserts it
  there when a card has none. `render_card_region(card)` is the freshness
  reference and, as in C11, runs from the start of the begin marker to the
  end of the end marker; the line ending after the end marker belongs to
  the prose. `coach.render.find_regions` locates it. A begin or end marker
  naming another slug, or a second region, is an error.
- The index (C11 header, source `nutrition/menu/`, command `recipes
  render`) has one `## ` section per configured slot in order, the slot
  note under it, then a table of the cards in that slot: active cards by
  title, then benched cards. A slot with no cards says so.
- `recipes import` returns `data: {slug, card, toml, prose, flags}`.
  `slug` is a suggestion from the title; `card` is the draft block;
  `prose` is the method as `## Method` steps. Flag codes:
  `unparsed_ingredients` (with `lines`), `missing_nutrition`,
  `per_serving_doubt`, `macro_sum` (with `severity`), `slot_guessed`,
  `servings_missing`, `time_missing`, `active_time_uncertain` (with raw
  `source_times`), `aisle_guessed`, `incompatible_ingredient_units` (with
  `items` and source `lines`). Compound quantities that cannot be read
  exactly remain in `unparsed_ingredients`; supported preparation clauses
  leave shopping identity, while cooked/raw and colour distinctions stay.
  Duplicate item/unit quantities sum after supported unit normalization;
  incompatible units remain separate for review and reconciliation before
  card validation. Specific food phrases take priority over misleading
  aisle tokens. `time_min` means active minutes: prepTime is only a flagged
  starting estimate (zero if absent), never proven total active time;
  totalTime is not imported as active time. Resolve flags before athlete
  approval and writing a card. A draft without
  all four macros leaves out `per_serving`. A page host of a known meal
  kit (`gousto`, `hellofresh`) adds the tags `meal-kit` and the provider.
- `recipes draft --input FILE` takes `{slug, card, prose}` (the import
  output works as is) and returns `{slug, path, exists, text, results}`;
  a failing draft exits 1.
- `recipes convert --parse` returns `{cards: [{slug, card, toml}], review,
  slot_notes, slot_notes_toml, slot_notes_unplaced, table}`. Each review
  row: `slug`, `title`, the four macros, `ingredients` (count), `unparsed`
  (lines), `guessed_aisles` (`{item, aisle, matched}`), `variations`
  (count), `variations_to_fill` (names; none on eat-out cards), `notes`
  (including every front-matter line it could not read and every key it
  does not carry over). `slot_notes` maps each configured slot to the prose
  under its heading in the old hand-kept index; `slot_notes_toml` is that
  map as a `[nutrition.bank.slot_notes]` table for the coach to add to
  `config.toml`; `slot_notes_unplaced` lists `{heading, note}` for prose
  under no slot heading. The table lists the slot notes after the cards.
  `--apply --input FILE` takes `{cards: [{slug, card}]}`, refuses (exit 1,
  nothing written) a card that fails validation or is not an old YAML
  card, backs up the old cards and index, and keeps every section of the
  old body except the title, stats table, `## Ingredients` and
  `## Variations`. It re-renders the index only once no old cards remain,
  and lists the rest under `still_old_format`. It warns about, and returns
  as `slot_notes_missing`, each old slot note that config lacks.
- An old YAML card fails `recipe_cards` with a message that names
  `recipes convert`.

## C34. Meal plan (R-33c owns; R-25 reads)

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
  "schema_version": 2,
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
  `recipe_benched`, `use_up_unmatched`, `units_mixed`, `no_target`,
  `anchor_shopping_unknown`.
  Severities as in C10. `meals approve` refuses unresolved `block` flags.
- `approval` is as in C10. `meals shopping --format issue` refuses an
  unapproved plan (exit 3).
- Rendered to `nutrition/plans/<id>.md` (C11 header). Check:
  `meal_plans` (schema, arithmetic), `meal_plan_render_fresh`,
  `nutrition_template` (template and anchors name existing, active cards).

Settled while building R-33c (`coach/schemas/meal_plan.schema.json`,
`coach/schemas/meal_plan_draft.schema.json`):

- **Draft.** `span` is required; `exceptions`, `assignments`, `use_up`
  and `notes` are optional, and an optional `schema_version` is 1. An
  exception is `{date, slot, entry, note}` or `{date, office, note}`,
  never both; at most one per date and slot and one office change per
  date. An exception replaces everything the template puts in its slot
  that day, anchors included. An assignment `{date, slot, entry, note}`
  adds an item to its slot, so several may share a slot (a top-up beside
  a covered dinner); it fills a pool slot, and it may not land on a
  slot an exception skips. An entry sets exactly one of `recipe`,
  `cover` (with `kcal` and `protein_g`) or `skip: true`; `variations`,
  `covered_by` and `lock` belong only with `recipe`. Dates lie in the
  span and slots in `[nutrition.template] slots`. Any of these problems
  exits 1 before anything is built. An office change that makes two
  standing rows meet on a date exits 1 unless an exception covers that
  slot.
- **Item.** Every item carries `slot`, `source`, `recipe`, `title` (the
  card's, snapshotted), `variations`, `covered_by`, `cover`, `name` (an
  anchor's), `skip`, `lock`, `note` (the exception's or assignment's),
  `kcal` and `protein_g`. A recipe's macros are its per-serving numbers
  plus the deltas of the variations that apply. An unknown recipe has
  null macros, counted as 0 in totals. Macros and totals are rounded to
  0.01.
- **Pool.** One entry per (recipe, sorted variations, `covered_by`):
  `recipe`, `title`, `variations`, `count`, `covered_by`, `servings`,
  `batches` (null when covered or the card is unknown), and the
  per-serving `kcal` and `protein_g`. Anchors that name a card are in the
  pool and the shopping list for scheduled occurrences only, using the
  same batch, coverage and pantry rules. Inline anchors keep their macros
  but contribute no inferred ingredients; each planned occurrence emits
  `anchor_shopping_unknown`, naming the anchor, date and slot and asking
  for a confirmed recipe link or separate shopping arrangements. Exceptions
  replace anchors before pooling and flagging. Setup offers a recipe link
  only for an explicitly confirmed matching card, never a guessed name.
- **Shopping.** Variations apply to a batch's ingredients in order; one
  that conflicts with an earlier one is skipped. `use_up` comes off the
  matching (item, unit) line; `used_up` records the amount taken off.
  A use-up item the plan needs only in another unit gives `units_mixed`
  and takes nothing off; one the plan does not need gives
  `use_up_unmatched`. An item needed in two units gives one
  `units_mixed` and keeps a line per unit. Staples match items exactly
  and are listed in `staples` order; `buy` follows `[nutrition.bank]
  aisles`, unknown aisles last, then item name.
- **Targets.** `kcal` is the `target_kcal` of the newest reading that
  has one (`kcal_source` `"reading <date>"`) when an app is in use, or
  `kcal_target` (`"kcal_target"`) without one, else null with a
  `no_target` flag. `protein_floor_g` is `[nutrition.protein] floor_g`.
  `kcal_off_target` fires when a day's total is further from `kcal` than
  `kcal_tolerance_pct`.
- **Flags** are `{code, severity, date, slot, message, resolved,
  resolution}`. Severities are fixed per code: `recipe_unknown`,
  `variation_unknown` and `variation_conflict` are `block`, the rest
  `warn`. `slot_open` fires for a slot with no item and for a pool slot
  with no assignment. `anchor_shopping_unknown` is a warning that leaves
  a bare anchor valid; dry runs and plan renders show it, and standalone
  shopping markdown and issue bodies include unresolved coverage warnings.
  Meal plan v2 adds this flag. The migration from v1 changes only the
  version, preserving saved meals, shopping, flags and approval stamps.
  The version changes the approval hash: a previously approved plan needs
  the athlete's agreement and `meals approve` again before its shopping
  issue can be published. Migration notes name that loss of approval and
  the `meals render` command. Historical flags stay as saved; build a new
  plan to receive coverage warnings from current inputs.
- **Style.** `plan_style` when set; otherwise `loose` when a standing
  row covers dinner, else `strict`.
- **Commands.** `meals template` defaults to the first whole week after
  today and returns `span`, `week`, `style`, `slots`, `office_days`,
  `staples`, `kcal_tolerance_pct`, `shopping_issue`, `targets`, `days`
  (each slot's template and anchor `entries` and `open`) and
  `open_slots`. `meals build` reads `--input` relative to the working
  directory, returns `{id, path, written, plan, rendered}`, and refuses
  (exit 3) to rebuild a plan that carries an approval. `meals shopping`
  returns `{text}` for markdown, or `{title, body, shopping_issue}` for
  an issue; the body's Buy lines are `- [ ] ` items under `### <aisle>`
  headings, then a `### Check you have` section. Neither `meals
  render`'s output nor the issue body reads a card: a card edited after
  the build changes nothing.

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
  computes expenditure or a calorie target for an app user; those fields
  are the app's numbers. The one calorie figure the package computes is
  `nutrition targets`' starting estimate for `app = "none"`, and only
  `coach/calories.py` names a calorie equation.
- `nutrition status` flags: `protein_floor_raise`, `protein_unmeasured`,
  `override_expired`, `override_renewed_twice`, `app_protein_mismatch`, `logging_incomplete`,
  `no_recent_reading`. It returns `data.brief_line` and `data.questions`;
  R-25 and R-21a print them when nutrition is enabled (a soft dependency:
  absent or `{"enabled": false}` means nothing is printed).
- Checks: `nutrition_readings` (schema), `nutrition_override` (warn when
  expired or renewed twice).
- `nutrition record` stores `source: "app"` when `[nutrition] app` is
  set and `"scale"` with `app = "none"`; `weight_unit` is `[athlete]
  bodyweight_units`; it never writes `window`. `nutrition import`
  takes a JSON list of readings, or `{"readings": [...]}`; each item
  needs `date`, may omit any other field (stored as null), and may carry
  `source` only as `"seeded"`. A date already on file exits 1 for
  either command unless `--replace` is given.
- `nutrition status` data, when enabled: `enabled`, `app`, `phase`,
  `weight_unit`, `target_rate_per_week`, `goal_weight`, `kcal_target`,
  `protein` (the `[nutrition.protein]` table), `anchors`, `override`
  (the table plus `state`: `upcoming`, `active` or `expired`; null when
  none), `template` (whether `[nutrition.template]` exists),
  `latest_reading`, `trend`, `flags`, `plan` (R-33c: the rendered path
  of the meal plan whose span holds today, the latest-starting one when
  several do, else null), `brief_line`, `questions`.
  Disabled: `{"enabled": false, "brief_line": null, "questions": []}`.
- `trend`: `{basis, rate_per_week, span, days, target_rate_per_week}`.
  `basis` is `trend_weight` with an app and `scale_weight` without one.
  The rate runs from the newest weight back to the newest earlier
  weight at least 14 days before it, in `weight_unit`, per 7 days,
  rounded to 0.01; null (with `span` and `days`) when the readings cover
  under 14 days. A number only: no flag judges it.
- A flag is `{code, message, ...}` with the numbers it names.
  `protein_floor_raise` (`floor_g`, `proposed_floor_g`,
  `proposed_floor_since`, `dates`): the two most recent readings dated
  on or after `floor_since` both have `avg_protein_g >= floor_g`, and
  the floor is under the target; it proposes `min(floor_g +
  floor_step_g, target_g)`, with `floor_since` set to the day after the
  later of `dates` so neither counted reading counts again. App targets
  at or above the new floor stay unchanged; only a below-floor setting
  prompts an increase. Active overrides are reviewed before changing
  agreed values. `protein_unmeasured` (`floor_g`, `target_g`, `dates`,
  `refs`): the three latest readings since `floor_since` all have
  `source: "scale"` and null `avg_protein_g`, with no app and floor below
  target. Offer optional calibration, explicit goals review or a deliberate
  hold (claim 20); anchors and one-day estimates cannot qualify a raise.
  Store a one-day estimate in `note`, not `avg_protein_g`.
  `override_expired` (`expires`): today is on or after `expires`. `override_renewed_twice`
  (`renewal`): `renewal` is 2. `app_protein_mismatch` (`app_protein_g`,
  `floor_g`, `override_active`): an app is in use and the latest
  reading's `target_protein_g` is below `floor_g`; equal and higher settings
  are compatible. The reading retains the app's actual target, while config
  keeps `floor_g <= target_g <= stretch_g`.
  `logging_incomplete` (`days_logged`): the latest reading logged fewer
  than 7 days. `no_recent_reading` (`last_reading`): no reading, or the
  latest is more than 14 days old.
- `questions` are plain strings in order: the readings question (the
  app's numbers in R-01's order, or, without an app, "this week's
  morning weigh-ins · average daily protein, if you track it"), the
  habits question ("anchors most days (y/n)? Anything in the plan that
  didn't work?", or only "Anything in the plan that didn't work?" when
  `anchors` is empty), and the food-exceptions question only when
  `template` is true. `brief_line` reads `Food: protein floor <g> g,
  last week <g> g · anchors: <names or none> · override: <none | what,
  until D | what, from D | expired D>`; with no reading it says "no
  reading yet", with no protein figure "last week not tracked". With a
  `plan`, the line ends ` · plan: <path>` (R-33c).
- `nutrition targets` (`coach/protein.py`, `coach/calories.py`) computes
  the protein numbers and the no-app calorie estimate `/goals` quotes; it
  reads, never writes, and runs with nutrition off.
  Inputs: each flag, else bodyweight from the newest reading of the last
  14 days with a weight in `bodyweight_units` (its `trend_weight`, else
  its `scale_weight`), recent intake from the newest reading of the last
  14 days with `avg_protein_g`, and goal weight from `[nutrition]
  goal_weight`. `--height-unit` defaults to cm with kg bodyweight and in
  with lb. `--body-fat` and `--body-fat-source` come together. A bad
  value exits 1, including a height outside 1.0–2.5 m (a unit slip).
  Data: `inputs` (`bodyweight` and `goal_weight` as `{value, unit,
  from}`, `recent_intake_g` as `{value, from}`, `from` being `flag`,
  `config` or `reading D`; `body_fat` `{pct, source}`; `sex`;
  `height_m`; `age`; `activity`; `phases` as `{value: [[phase,
  rate]...], from}`, from `--phase` or `[nutrition] phase` and
  `target_rate_per_week`; each null when absent), `reference`,
  `protein`, `calories` and `missing`.
  - `reference`: `{basis, mass, unit, mass_kg, reason, refs, bmi}`. The
    first rule that applies: a credible reading gives `fat_free_mass`
    (bodyweight × (1 − body fat)). For rough or absent readings, combine
    available cues: rough body fat above 25 % for `male` or 35 % for
    `female`, goal weight at least 10 % below bodyweight, or BMI at least
    30. Any positive cue gives `goal_weight`, with the cues in `reason`;
    otherwise `bodyweight`. With no positive cue, an ambiguous rough
    reading needs `--sex`; without a usable rough cue, BMI needs height.
    A positive cue needs goal weight if absent. Nothing is invented.
    `bmi` is truncated to 0.1 and null without height. `basis` takes the
    `reference_basis` values. These selection gates are heuristics.
  - `protein`: `target` `{g, g_per_kg, refs}`, `stretch` `{g, g_high,
    g_per_kg, g_per_kg_high, refs}` and `floor` `{g, g_min, g_per_kg_min,
    from_intake_g, clamped, refs}`, computed from `mass` as shown.
    Target 1.6 g/kg and stretch 2.2, or with fat-free mass target 2.0
    and stretch 2.6 to 2.8 (`g` and `g_high`), each rounded to the nearest
    5 g. `g_min` is 1.2 g/kg (1.5 of fat-free mass) rounded up to 5 g.
    The floor is the first 5 g step at or above recent intake + 15 g,
    raised to `g_min` (`clamped: "min"`) or cut to the target (`clamped:
    "target"`); `g` and `from_intake_g` are null with no intake. Null
    when `reference` is.
  - `calories`: the app comes from `--app`, else `[nutrition] app`. An
    app set gives `{"by": "app"}` and no figure; no app known gives null
    and names `app` in `missing`. `app = "none"` gives `{by: "estimate",
    method, resting_kcal, activity_level, maintenance_kcal, estimates,
    refs}`: resting rate by Mifflin–St Jeor from bodyweight, height, age
    and sex (rounded to 1 kcal), times the activity level (`sedentary`
    1.53, `active` 1.76, `vigorous` 2.25) and rounded to the nearest
    50 kcal for `maintenance_kcal`, and one `{phase, rate_per_week, unit,
    adjustment_kcal, kcal, below_resting}` per phase: the adjustment is
    the rate in kg × 7700 ÷ 7 (rounded to 1 kcal) and `kcal` is
    `maintenance_kcal` plus it, rounded to the nearest 50 kcal. A `kcal`
    under `resting_kcal` sets `below_resting` and adds a warning. The
    numbers are null and `estimates` empty while an input is missing.
    Refs: claims 14–16.
  - Exit 1 for a phase rate that isn't finite, a sign that doesn't fit
    the phase (`cut` below 0, `bulk` above 0, `maintain` and `recomp`
    0), or, with a bodyweight, a `cut` over 1 % or a `bulk` over 0.5 % of
    bodyweight a week (claims 11, 12); for an `--age` outside 13–120. An
    age outside 19–78, the equation's sample, adds a warning.
  - `missing`: `{input, flag, why}` for each input the rules still need,
    in order: `bodyweight`, then the one the basis needs next (`sex`,
    `height` or `goal_weight`), then `recent_intake`, then any the
    calorie estimate needs (`app`, or `sex`, `height`, `age`, `activity`,
    `phase`) not already named. Nothing is guessed.
  - `refs` are `rn:protein-energy-deficit` claims: 3 for a credible
    reading, 3/4/19 for a rough reading, 3/19 without a reading;
    17, 18 and 6 (fat-free mass) for target and stretch; 8 and 7 for
    the floor. The floor is a minimum commitment, the target a coaching
    aim, and the stretch an optional higher aim, not a universal benefit cap.
- Readers: R-25 reads C4 `phase` and may read C35 weights for
  `progress.md`'s bodyweight trend; R-40a reads `[nutrition] enabled` and
  writes the table at setup.

## C36. Check-in records, the card, catch-up mode (R-21a, R-21b; R-25, R-26, R-30a, R-31, R-33a, R-42a, R-43 read)

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
coach.checkin.prepare(root, today, until=None, tier=None, now=None) -> dict   # the card
coach.checkin.card_text(card) -> str                                         # the Sunday message
coach.checkin.misses(root, since, until, now=None) -> dict
coach.checkin.render_week_review(root, record_date) -> str                   # C11
coach.checkin.skeleton(root, date, tier=None, overlay_id=None, refresh=False, dry_run=False, now=None) -> dict
coach.checkin.mode_for(found, day) -> (mode, deep_reasons)                   # R-21b; due() and prepare() share it
coach.checkin.tag_gap(root, today, tag, now=None, dry_run=False) -> dict      # R-21b
coach.checkin_catchup.return_brief(root, config, now, proposal_id=None, overlay_id=None, reason="layoff") -> dict   # R-21b
coach.checkin.catch_up_after_days() -> int     # validity.RETURN_BANDS[0].upper (10)
coach.checkin.DEEP_AFTER_DAYS = 42             # rn:deloads.12
```

The message renderer is `card_text`, not `render_card`: the C11 sweep
takes any top-level `render_<kind>` as the renderer of that region kind,
and `render_card` would capture R-33b's `card` regions.

- **Window**: day after the last record's date to today (`--until` sets
  the end). No record: from the program's first overlay span start.
- **Mode**: `catch_up` when `days_since > catch_up_after_days()`, the
  first return band's upper edge (C22).
  Otherwise `deep` when there is no record, the last deep record is
  `DEEP_AFTER_DAYS` (42, rn:deloads.12) or more days old, a card part
  adds a reason, or `--tier deep`; else `weekly`. `--tier weekly` or `--tier deep` overrides a catch-up. A
  catch-up never runs deep; it sets `deep_deferred: true` (a record-based
  deep reason, or a part's tier reason), and its `tier_reasons` are the
  gap (`"28 days since the last check-in, over 10"`) plus `"deep review
  deferred (<reasons>)"`. When the newest records are catch-ups and a
  deep review was due at one of them (judged from the records before
  it), the next check-in's deep reasons start with "deferred from
  catch-up <date>", so a check-in that is not itself a catch-up runs
  deep. A part's tier reason is not recorded, so only record-based
  reasons carry over. `checkin due` uses the same rule.
- `due_date` = last record date + `[checkin] cadence_days`.

**Card document** (`checkin prepare` → `data.card`; `data.text` is the
markdown from `coach.checkin.card_text(card)`). It reads history with
`include_unsynced=True` (C17). The last record is the newest one dated
before the window end, so re-running `prepare` after writing today's
record gives the same card:

```json
{
  "schema_version": 2,
  "date": "2026-10-11",
  "window": {"start": "2026-10-05", "end": "2026-10-11"},
  "mode": "weekly", "tier_reasons": [], "deep_deferred": false,
  "days_since_last": 7, "unsynced": 0,
  "sessions": {
    "planned_core": 3, "trained_core": 2, "optional_trained": 0,
    "rows": [{"date": "2026-10-05", "session_id": "session-a", "title": "Session A", "tier": "core",
              "status": "trained", "moved": false, "unlogged": false, "tag": null,
              "workout_id": "…", "workout_date": "2026-10-05", "minutes": 58, "cap_minutes": 45}],
    "external": [{"date": "2026-10-06", "external_id": "pt-tue", "title": "PT", "done": null, "note": null}],
    "extra": []
  },
  "exercises": [{"date": "2026-10-05", "session_id": "session-a", "exercise_id": "bb_back_squat",
                 "name": "Back Squat (Barbell)", "prescribed": "3×5 @ 97.5 @ RPE 7.5",
                 "logged": "5, 5, 5 @ 97.5 @ RPE 7.5", "status": "hit", "rpe_delta": 0}],
  "e1rm": [{"exercise_id": "bb_back_squat", "name": "Back Squat (Barbell)", "load_mode": "total",
            "date": "2026-10-05", "e1rm": 121.88, "delta": 1.55, "method": "epley_rir"}],
  "hevy": [{"routine_id": "…0002", "title": "Session B", "session_id": "session-b",
            "overlay_id": "2026-10-05-weekly", "state": "edited_in_app",
            "changes": [{"class": "structural", "path": "…", "before": null, "after": "…"}],
            "summary": "Bench Press (Dumbbell) added"}],
  "flags": [],
  "fields": [{"id": "sessions", "n": 1, "label": "Sessions", "prefill": "…", "ask": "…"}],
  "facts": [],
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
- `e1rm`: exercises with a C18 point in the window; `delta` = C18 `delta`
  (latest minus previous rounded point, counting only points up to the
  window end). Compounds first (`coach.patterns.COMPOUND_PATTERNS` once
  R-23a exists; library order before), at most eight rows (a heuristic).
- `hevy`: per routine of an active session (`state.hevy.routines`),
  comparing the cache with the newest approved overlay whose span starts
  on or before the window end and whose session carries that routine,
  through R-14's `coach.routines.diff`, offline. (An approved overlay for
  next week is the programming pass's to write; the card judges the
  routines the athlete has been training from.) `state` is `current`,
  `not_written`, `edited_in_app`, `loads_edited` or `not_cached`;
  `summary` describes the listed changes in words. `edited_in_app`: a
  `structural` change and a cached `updated_at` after the routine's last
  C9 `verify` line; becomes a keep-or-replace question (R-03).
  `not_written`: no `verify: true` line for this routine, that overlay and
  its approval hash, whatever the cache holds; raises `stale_routine`.
  `not_cached`: written and verified, but missing from the cache. Load-only edits
  (`loads_edited`) are listed as a fact, not asked (R-03 overwrites
  them). Skipped when `[hevy] enabled` is false.
- `flags`: C20 objects for the window: `convention_slip` (open audit
  candidates), `duration_over_cap`, `stale_routine`, plus part flags.
  Presented through `coach.flags.for_mode` (C44).
- `misses` (deep tier only): `coach.checkin.misses(root, since=last deep
  record date, until=window end)` →
  `{"by_tag": {"time": 0, "sleep": 2, "ill": 0, "family": 0, "skipped": 0, "other": 0, "untagged": 1},
    "by_session": {"session-a": 2}, "sessions_missed": 3}`, plus `since`
  and `until`. Counts each missed planned session (C18 adherence over the
  span, by its tag or `untagged`) and each `miss` annotation in the span
  that no planned session's overlay span could match, so a tagged miss is
  counted once. A session the program marks `optional` is never counted.
- `facts` collects the parts' contributions; facts print above the fields.

**Fields.** Ids and order are R-01's Sunday message: `sessions`,
`coach_led`, `runs`, `sleep`, `niggles`, `nutrition`, `meal_plan`,
`next_week`, then `hevy_edits` (only when a routine is `edited_in_app`).
Each field is `{id, n, label, prefill, ask}`: `label` is the field's
name in the message, `prefill` states what the data shows for
confirmation, `ask` is the question. Fields that cannot apply are
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
# Field(prefill=None, ask=None, label=None)
# Contribution(fields: dict[str, Field | None] = {},   # None = omit that field
#              facts: list[str] = [], flags: list[dict] = [],
#              tier_reasons: list[str] = [])
```

- Two parts owning the same field id is an error at discovery (exit 1,
  both modules named), and so is a part setting a field it does not own.
  A part's `Field` replaces the builtin; returning `None` for a
  contribution falls back to the builtin. A field id outside R-01's list
  goes after `next_week`, before `hevy_edits`.
- Parts are pure reads and run in a fixed order (module name).
- R-21a ships one part itself, `nutrition`: when `coach.nutrition` exists
  and `nutrition status` says enabled, it replaces `nutrition` with
  `data.questions` (pre-fills included), labelled `Food`, and omits
  `meal_plan`. When the module is absent or reports `{"enabled": false}`,
  it returns None and R-01's builtin fields stay. A soft dependency on R-33a: nothing is computed
  from nutrition data here.
- Expected parts from later items: R-27 (`niggles` field from `niggles
  list`; due follow-ups as facts; `niggle_escalate`), R-30a and R-31
  (`tier_reasons`), R-43 (part `cardio`: `runs`, `sleep` stated from
  activity sources, and the week-flag providers' flags; C49).

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
  record date (no questions). It reads committed history only (no
  `include_unsynced`), leaves out the Hevy routine list and card parts,
  and takes its tier from the record's title, so a fresh render needs
  nothing gitignored. The skeleton warns when the window holds workouts
  not yet synced. The overlay region is R-13's `overlay render`.
- `--refresh` re-renders the week-review region only on the newest
  record (an older one is archive, C11), and every `overlay` region in
  the file; with `--overlay ID` it adds the collapsed prescription when
  the record has no region for it, and wraps a bare region for it (one
  `overlay render --into` appended) in the `<details>` block.
- Coach's read, Decisions and Next week are prose the coach writes. R-01's
  `Missed:` line lives in the region; R-02's adherence decision line and
  block status line are prose in Decisions until R-30a and R-31 script
  them.
- Deep records add `## Block planning` after Decisions, and `misses` in
  the region.
- Check `checkin_record_words` (warn): prose outside the title, rendered
  regions and `<details>` over 600 words (weekly, catch-up) or 1,000
  (deep), heuristics. It reads records in the skeleton format (holding a
  week-review region), so older hand-written records never warn. Check
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
  "missed": [{"date": "2026-09-17", "session_id": "session-b", "title": "Session B", "tag": "untagged"}],
  "return_week": {"proposal_id": "2026-10-12-weekly", "overlay_id": "2026-10-12-weekly", "week": "2026-W42",
                  "span": {"start": "2026-10-12", "end": "2026-10-18"}, "band": "22-42", "days_off": 28,
                  "load_factor": 0.9, "set_delta": -1, "rpe_cap": null,
                  "sessions": [{"date": "2026-10-12", "session_id": "session-a", "title": "Session A", "rpe_cap": null,
                                "lines": ["Back Squat (Barbell) 2×5 @ 90 RPE 7"]}],
                  "flags": [], "lines_digest": "sha256:…", "names": {"bb_back_squat": "Back Squat (Barbell)"}},
  "return_week_problem": null,
  "write_line": "Reply \"go\" to train this and write: Session A, Session B (Hevy)."
}
```

- `summary`: one row per week in the window (C7 weeks; `week` is the
  label, `start` the week's first day; the first and last rows may cover
  part of a week). Planned sessions come from the overlay in force (the
  card's C18 rows), else from `schedule plan` for those days, each
  matched to a workout of its session (its `session_id`, or the routine
  `state.hevy.routines` maps to it) in the same week, a
  `trained_unlogged` annotation, or a `miss` annotation for its tag.
  `planned_from` is `overlay` when an overlay is in force on every day of
  the row, `schedule` on none, else `mixed`. `external_done` counts
  coach-led sessions recorded done, null when none was recorded;
  `workouts` counts every logged workout in the row.
- `missed`: every missed planned core session in the window, with its
  tag or `untagged`; `checkin tag-gap` and the record's `Missed:` line
  read it.
- `return_week`: `propose week --dry-run` for the week holding tomorrow
  (R-23a's default span; `week` names it), which applies C22 decay.
  `days_off` = first session date − last lifting workout; `band` and its
  numbers from `band_for(days_off)`. Each session's `rpe_cap` is the
  band's cap, or `ILLNESS_RPE_CAP` on the first session when the
  proposal raised `return_after_illness`. `names` maps the week's
  exercise and session ids to names, for the flags line. `lines_digest` =
  C7 canonical hash of `data.lines`; `propose week` and `propose show`
  return the same `lines_digest`. After "ok", the real `propose week
  --week <week>` must give the same digest; if not, the coach presents
  again. When the proposal fails (an invalid program, no session
  planned), `return_week` and `write_line` are null,
  `return_week_problem` holds the message, `checkin prepare` warns, and
  the text ends "Answer 1–3." instead.
- The record of a catch-up check-in is titled `(catch-up)`; `checkin
  skeleton` picks that tier from the mode. Its week-review region holds
  the `Missed:` line and the summary table, never the return week (the
  region reads committed history only and runs no proposal).
- The rotation line (the `coach_led` field, else `next_week`; in
  catch-up mode question 3) states the position `schedule plan` infers
  for next week and whether it is confirmed; with no plannable program
  it falls back to `state.rotation`.
- The card ends with the write line (R-03's shape) and "Reply ok to accept
  all of this, or answer 1–3." "ok" alone means: misses stay untagged,
  nothing new to report, the return week as shown, written to Hevy.
- Parts contribute `facts` in catch-up mode; their
  fields are ignored.
- `checkin tag-gap --tag T [--dry-run]` writes one `miss` annotation per
  untagged missed planned core session in the window (`source` "checkin
  tag-gap <date>"), through `coach.history.add_annotations`, the same
  path as `history annotate`. A second run finds nothing left to tag.
- `checkin return-brief (--proposal ID | --overlay ID) --reason ill|travel|no_kit|layoff`
  returns `data.text`, the return template of the coach's brief: (1) one
  sentence on the gap (days off, reason); (2) what the return week does
  (band, load and set change, RPE cap); (3) per-session lines; (4) what
  happens after (normal progression from the logged loads, R-02); (5) the
  write line. `ill` adds R-02's safety lines (48 hours symptom-free first;
  first session at RPE 7 or below; fever, chest symptoms, other whole-body
  symptoms or a slow recovery mean checking with a qualified professional
  first; rn:detraining-return.4). `travel` and
  `no_kit` take a coach-built one-off overlay. Read-only; the coach may
  edit the words before presenting. Exactly one of `--proposal` and
  `--overlay` (exit 2 otherwise). Output: `text`, `days_off`, `band`,
  `sessions` (as `return_week.sessions`), `reason`, `source` and
  `warnings`. The brief claims only what the lines carry. A band's change
  is claimed when every line with an exposure to decay from is decayed to
  its own band (`provenance.decay.band`, C22); otherwise the brief states
  the band as the guideline and warns, naming the lines. A session's RPE
  cap, and `ill`'s "first session back at RPE 7", are claimed only when
  every working set in it is at or under the cap; `ill` on an uncapped
  first session warns. Each warning names the fix for its source: propose
  again (after `checkin tag-gap --tag ill` for illness) for `--proposal`,
  rebuild with `overlay build` for `--overlay`. The
  48 hours is `coach.validity.SYMPTOM_FREE_HOURS`, beside
  `ILLNESS_RPE_CAP` (C22), and a test keeps it equal to `CLAUDE.md`.

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
  never more than prescribed; rn:minimum-effective-dose.5) at the
  prescribed reps and load, and at the prescribed RPE or the item's
  optional `rpe` if lower. `into` is a session id, or `"next"` for the
  next planned session of any kind. No such later date in the span:
  unmatched.
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
  it after the program's rules, as a fallback, C40). Matching and
  application stay separate so callers can do this without copying either.
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

**Built with R-22** (details the text above leaves open):

- Rule shape (program v4): `when` is `{}` or `{"min_days_left": n}`;
  `action.kind` is one of the four kinds; `fold` takes `into` and
  `exercises` (each `{exercise_id, sets?, rpe?}`, `sets` ≥ 1, default 2;
  rn:minimum-effective-dose.5),
  `shift` takes `to_weekdays` (weekday ids), and `skip` and `manual` take
  neither. A `manual` rule needs its `text`. `program validate` reports a
  kind's missing or extra keys and an exercise listed twice in one rule;
  `missed_rules_valid` reports the references (a missing or non-active
  session, an `into` that is no session, an exercise its session lacks).
  The v2 → v3 migration writes each free-text rule's text as
  `<condition> → <action>`.
- `describe(rule, root=None, program_doc=None, library=None)`: the
  rule's `text` when set; otherwise written from the action with session
  titles from the program and exercise names from the library (ids when
  neither is given). `min_days_left` shows only above 1, since a fold or
  shift already needs a later day. `routine/program.md` lists each rule
  as `` `<id>`: <describe> ``, and the `missed` page part fills
  `brief.if_you_miss` the same way (nothing when there are no rules).
- `match(root, session_id, date, doc=None, program_doc=None)` takes the
  overlay in force when `doc` is None. `apply_rule(root, doc, session_id,
  date, rule, now=None, config=None, library=None)` returns the built,
  unwritten midweek overlay with its R-24 flags merged, None for `skip`,
  and raises `coach.missed.Unmatched` (its message is the reason) for
  `manual`, a fold with no later target or a line the missed session
  lacks, and a shift with no free day. The missed session must be dated
  `date` in `doc` (else exit 1).
- The midweek overlay holds `doc`'s sessions dated after the miss, plus
  a moved session. Its span starts at the earliest of them (a shift can
  land before the next planned date) and ends with `doc`'s; `focus` is
  `doc`'s. It carries `doc`'s non-R-24 flags on the sessions it holds,
  and a folded line's flags move with it to the target session.
- A folded line is a copy of the missed line with its first `sets`
  working sets (warm-ups dropped), `superset_id`, `override` and
  `change` cleared, provenance kept. A shift's candidate for a weekday is
  the first date with that weekday after the miss.
- A day before today (the athlete's time zone, C2 `COACH_NOW`) is never
  a fold target or a free shift day, so a miss planned once those days
  have passed is unmatched and falls back to the mid-week reprogram.
- `missed list` returns `data.missed`: `{date, session_id, title,
  overlay_id, recorded, tag}` per missed core session (optional sessions
  are never a miss), reading unsynced workouts too (C17); `recorded` is
  true when a `miss` annotation names that session and date.
- `missed plan` also returns `title`, `overlay_id`, `action`,
  `description`, `reason` (why unmatched), `floor_rule` (the priority
  floor applied alongside a program fold, C40, else null) and `flags`
  (the `missed_rule_unmatched` flag when unmatched). The summary is the miss
  and the rule, the change (loads in C12 Target form), the overlay and
  its span, and the prescription check's block and warn counts.
- Write lines: as R-03 with the draft's session titles; without Hevy
  `Reply "go" to train this. Nothing goes to Hevy (no Hevy).`; for
  `skip` `Reply "go" to train this. Nothing goes to Hevy (no change).`
- `missed apply` refuses (exit 3) before writing anything when a `miss`
  annotation already names that session and date, then re-plans, refuses
  (exit 3) an unmatched miss before writing anything, and writes the `miss` annotation with source
  `missed apply`. `skip` writes no overlay. Record lines for the other
  cases: `- Rule miss-a: Session A moved from Mon 12 Oct to Thu 15 Oct,
  this week only.`, `- Rule miss-c: nothing changes this week.`, `- No
  overlay; nothing goes to Hevy.`, and `- Overlay <id>; no Hevy.` without
  Hevy; an untagged miss reads `(untagged)`. A second apply adds its
  lines to the same `## Mid-week` section, which goes at the end of the
  record when absent. With no record it warns and writes the rest.
- `overlay_folds_expired` reads overlays whose span ends today or later
  (C13), and skips when there are none.

## C38. Standing pages and publishing (R-25; R-22, R-23b, R-26, R-27, R-30a, R-31, R-33a, R-40c read)

Three pages at the instance root, rendered whole, each with the C11 header
carrying its as-of time. Nothing writes them but `pages render`.

| Page | Source path in the header | Renderer |
|---|---|---|
| `this-week.md` (the brief) | the overlay in force | `render_brief(root, as_of)` |
| `README.md` (the dashboard) | `data/state.json` | `render_dashboard(root, as_of)` |
| `progress.md` | `data/history/` | `render_progress(root, as_of)` |

`coach.pages.header_facts(root, as_of) -> dict` computes the brief
header's facts once, for the brief, the dashboard and R-26b's `status`:

```json
{"week": "2026-W42", "week_start": "2026-10-12", "overlay_id": "2026-10-12-weekly",
 "rotation": {"position": "week-b", "confirmed": true},
 "phase": "recomp",
 "checkin": {"last": "2026-10-11", "due_date": "2026-10-18", "tier": "weekly",
             "days_since": 3, "mode": "weekly"}}
```

The brief's week is the coming week as C52 defines it: the week holding
the day after `as_of`'s local date, so on a week's last day the pages
show the week ahead. `week` is its C7 label and `week_start` its first
day. `overlay_id` is the latest created of the overlays in force (C10) on
the week's days, null when none is. `rotation` is `state.rotation`'s
position and confirmation, null with no `data/state.json`. `phase` comes
from R-33a's `nutrition status` when present (null when absent or
disabled). `checkin` comes from C36 `due()` on `as_of`'s date: `last`,
`due_date`, `days_since` and `mode` as `due()` gives them, and `tier`, the
next check-in's tier: `deep` when `deep_reasons` holds on the due date
(today when there is no record), else `weekly`.

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
| Mon 12 | Session A | core | Back Squat 3×5 @ 100 kg | ✔ |

## Changed
- Bench Press 22.5 → 25/hand (Hevy: 50): hit 3×10 at RPE 8.

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
- Sessions: every session of the overlay in force on each day of the
  week, by date (C18 adherence over the week's span, as of); Tier from
  the program (`core` for a session the program lacks); Key = first
  exercise's page name (below) and its working sets in C12 Target form
  without RPE (consecutive sets with equal reps and load collapse; a
  `total` load carries its unit: `Back Squat 3×5 @ 100 kg`); Done = ✔ trained, ✗
  missed, blank upcoming. A session dated `as_of`'s own day with no
  workout and no miss tag is blank, not ✗: the day is not over.
- Changed: lines whose `change` is set, by date then exercise order, at
  most five, then "and N more in the check-in". Each reads `<page name>
  <change>: <reason>`. Reason: `override.reason`, else
  `provenance.rationale` (C21), else `target_note`. A `per_hand_x2`
  change that ends on the bare per-hand load (`22.5 → 25/hand`) gets the
  Hevy value appended (`22.5 → 25/hand (Hevy: 50)`).
- Watch: at most three items by priority: unresolved `block` flags
  (priority 20), then unresolved `warn` flags (30) on the overlays behind
  the week's sessions, then part items (default 50). R-40a routes them
  through `coach.flags.for_mode` (C44).
- If you miss a day: R-22's `missed` part fills the slot with one line
  per `program.missed_day_rules` entry, in `describe`'s words; with no
  rules, one line saying so.
- Wins: at most three, by priority: a new best e1RM in the last seven
  days (20; `total`, `per_hand_x2` and `single_implement` lifts only, a
  point strictly above every earlier one); a core-complete streak of two
  weeks or more (30); every core session trained last week (40); part
  items.
- An empty Changed, Watch or Wins prints one line saying so.
- Over 60 lines: cut items from the end of Wins, then Watch, then
  Changed, until it fits; a section left with no items goes, heading
  included. Still over with those three gone: cut items from the end of
  If you miss a day, which then ends "and N more in
  routine/program.md" and keeps its heading. Sessions and Focus are
  never cut.
- Page name, wherever the brief or the dashboard names a lift (Key,
  Changed, Wins, the dashboard's e1RM bests): the library name without
  its trailing parenthesis (`Back Squat (Barbell)` → `Back Squat`),
  unless another exercise the pages can name (in the program, any
  overlay, or the C18 e1RM series) loses its parenthesis to the same
  name; then both keep their full names (`Bench Press (Barbell)`,
  `Bench Press (Dumbbell)`). `progress.md`'s table always uses the full
  name.

**Dashboard** (`README.md`): first, a status block of at most six lines
(the brief's header line; the block status line from
`coach.block.status_line` (C43); last check-in date, tier and link; open flag
count (unresolved `warn` and `block` flags on the week's overlays); the
page's as-of time as "Updated <day> <HH:MM> (<zone>)", then part lines up
to six), then the Sessions table, then a progress summary of at most
five lines (three e1RM bests, streak, latest bodyweight), then links
(`this-week.md`, `progress.md`, latest record, `routine/program.md`,
`check-ins/`, and the template's README on GitHub for "how this works").
The Sessions table header is within the first 12 lines. The three bests
are the program's exercises in session order, then any others by name.
"Last publish time" is the as-of time: `pages publish` renders the page
just before it commits, so the two match, while a time read from git
would make every publish stale its own dashboard.

**Progress** (`progress.md`): a table of every lift with a C18 series
(best e1RM and date, latest, change over 28 days: the latest point minus
the newest point dated at least 28 days before `as_of`); part sections
(ladder state, priority lifts); core-complete streak (current, longest,
and the last 12 weeks as ✔/✗, – for a week with no planned core
session); bodyweight (part, else the Hevy body-measurement cache dated by
`as_of` as weekly means labelled "scale (Hevy)"; the section says "no
bodyweight source" when neither exists).

**Core-complete week**: every planned core session of the overlay in force
trained (including `trained_unlogged`), and no external session with an
`external` annotation marked not done. External sessions with no annotation
neither count nor break the streak. Optional sessions never count. The
weeks run from the week of the first overlay's span start to the week
before the brief's week; a week with no planned core session is neither
complete nor missed, and it ends a streak.

**Page parts** (`coach/page_parts/<topic>.py`):

```python
SLOTS = ("brief.watch",)
def contribute(ctx: PageContext) -> dict[str, list[Item]] | None
# PageContext: root, as_of, today (as_of's local date), overlay (in force for the week), program, state
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

Two parts replacing the same slot, a part naming an unknown slot, and a
part filling a slot it does not declare in `SLOTS` are errors (exit 1,
naming the modules). Parts run in module-name order and read only.

R-25 ships one part itself, `nutrition`: when `coach.nutrition` exists and
`nutrition status` says enabled, it adds `data.brief_line` to
`brief.lines` (once) and the phase to `brief.header.phase`; absent or
disabled, it adds nothing. A soft dependency on R-33a, computing nothing.

R-25 prints every load through one call site, `_load`. R-40c gives it,
and the two helpers that call it (`sets_text`, `_change_text`), a
`show_hevy` argument the renderer fills from `config.hevy.enabled`.

**README ownership.** `pages render` refuses (exit 3) to overwrite a
`README.md` that does not start with the C11 header, unless
`--replace-readme` is given; that first replacement is reported. Checks
`pages_fresh` (fail: a page differs from a fresh render at its own as-of
time, or `this-week.md` or `progress.md` has no as-of header; a `README.md`
coach did not generate is not checked; skip when no page exists) and
`pages_line_ceiling` (fail: `this-week.md` over 60 lines; skip when
absent). The renderers are `coach.pages.render_brief(root, as_of)`,
`render_dashboard(root, as_of)` and `render_progress(root, as_of)`;
`render_all(root, now, kinds)` renders from one read of the instance.

**As-of reads** (C17, C18). `coach.history.workouts`, `annotations` and
`all_exposures`, and `coach.stats.e1rm_series` and `adherence`, take
`as_of` (an aware datetime, default None = no bound): workouts started at
or before it (a workout with no start time: dated on or before its local
date), annotations created at or before it, and body weights dated on or
before its local date. Withdrawals created later do not apply.

**Publishing** (roadmap decision 1). `pages publish --overlay ID [--record D]`:

1. Refuses (exit 3) unless the overlay is approved with a matching hash
   (C10).
2. Refuses (exit 3) outside a git work tree, on a branch with no upstream
   (or a detached HEAD), when the git index already holds staged changes
   to any other path (naming them), and when `README.md` is not coach's
   (README ownership). Every refusal comes before anything is written.
   The selected overlay must also be the brief's coming-week overlay;
   a mismatch refuses before writes, so an older approval cannot publish
   a different week's prescriptions. No record to publish (or no
   `check-ins/<D>.md`) exits 1; no git exits 5.
   Setup commits its explicit reviewed setup/adoption path list with
   athlete approval before week-one publishing; C45 adoption still never
   commits. A normal README clone has an upstream; a zip download or new
   git repository needs an agreed remote and `git push -u <remote>
   <branch>`. Setup and weekly close-out explain this prerequisite.
3. Renders all three pages and refreshes the record's regions
   (`checkin skeleton --refresh`). When Hevy is off, also renders
   `this-week-sheets.md` from the same approved overlay as the brief,
   refreshing missing or stale sheets. Hevy-enabled publication leaves
   existing sheets alone and does not require them.
4. Stages exactly `this-week.md`, `README.md`, `progress.md`,
   `data/overlays/<ID>.json` and `check-ins/<D>.md` (D defaults to the
   newest record), plus `this-week-sheets.md` when Hevy is off, commits
   with the message
   `coach: publish week of <span.start> (<ID>)`, and pushes `HEAD` to the
   current branch's upstream (never `--force`). A failed commit exits 1. A
   failed push exits 4 and keeps the commit; the message says to push by
   hand.
5. `--dry-run` reports the paths and message and changes nothing.

Metadata: `writes`, `git_write`. It is allowlisted (C2).

## C39. Removed: scheduled run, not built

R-45 was not built; see `.out-of-scope/scheduled-checkin-nudge.md`.

## C40. Dose targets, priority lifts and the minimum week (R-30a, R-30b; R-31, R-41b read)

**Dose targets** (R-30a). R-30a's program bump (C16 schema versions) adds
an optional top-level object; migration adds `{}`:

```json
"dose_targets": {"chest": 10, "lats": 10, "quadriceps": 8, "calves": 6}
```

- Keys are R-11 muscle names; values are fractional hard sets per week,
  0 to 40. A muscle with no key gets the default 10 (rn:volume-frequency.1)
  when it is a primary muscle of any exercise in an active core session,
  and no target otherwise.
- `coach.structure.targets(program, library=None) -> dict[muscle, float]`
  returns the effective targets (`library` None: the catalogue alone).
  Nothing else applies the default. A "core session" here is an active
  `lifting` session of tier `core`.
- `program.load` fills an absent `dose_targets` with `{}`. `program
  validate` reports a key that is not an R-11 muscle (`key not allowed
  here`) and a value outside 0 to 40, at `$.dose_targets.<key>`.
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
- `floor.sets` default 2 (rn:minimum-effective-dose.4); `floor.rpe` null
  = the current prescription's RPE. `program validate` rejects a
  priority `exercise_id` that no session holds.
- `coach.structure.priority_floor(root, missed_session_id, date) -> rule | None`
  builds a synthetic C37 fold rule for the priority lifts the missed
  session carried, or None when it carried none:
  `{"id": "priority:<exercise_id>", "session_id": "<missed>", "when": {},
  "action": {"kind": "fold", "into": "next", "exercises": [{"exercise_id": "<id>", "sets": <floor.sets>, "rpe": <floor.rpe>}]}}`.
  Loads and reps come from the approved prescription (no progression);
  `rpe` applies only when lower than the prescribed RPE.
- R-30b applies it through `coach.missed.apply_rule(root, overlay,
  session_id, date, rule)` after the program's own rules, as a fallback
  (see "Order in `missed plan`" below), in R-22's plan and apply path. Folded lines
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
  `propose week --plan`. The overlay stays kind `weekly`; the plan file
  makes the week kind `minimum` (C41), which adherence skips and the
  hard-week count neither counts nor resets (C43).

**Built with R-30b** (details the text above leaves open):

- Program v6 schema: `priority` items are `{exercise_id, kpi: {kind,
  target?, by?}, floor?: {sets?, rpe?}}`; `program.load` fills `target`
  and `by` with null and the floor with `{"sets": 2, "rpe": null}`.
  `minimum_week` is null or `{sessions, schedule: {rule, params}}`.
  `program validate` also reports a lift listed twice, a `rung` KPI on a
  lift no session ladders (`assistance_ladder`), a minimum-week session
  listed twice or unknown, and the minimum week's schedule rule and
  params as it does `$.schedule`, at `$.minimum_week.schedule`. The two
  limits `structure balance --variant minimum` checks (two sessions, a
  third of each target) are not schema rules, so a program can hold a
  minimum week that fails them and the check names why.
- **Synthetic rule id.** One rule covers every priority lift the missed
  session carried (alongside a program fold, only those the fold leaves
  out or carries short; see "Order in `missed plan`" below), in `priority` order: `priority:<id>`, or
  `priority:<id>+<id>` for two or more. The rule also carries
  `"text": null`, as program rules do. "Carried" means a line in the
  missed session of the overlay in force (the program session when no
  overlay holds it). R-22's overlay schema allowed only `^[a-z0-9-]+$`
  for `fold.rule_id`, so overlay v4 widens it to that or
  `^priority:[a-z0-9_]+(\+[a-z0-9_]+)*$`. The step changes no line, but
  the version is in the approval hash, so approved overlays lose their
  approval and the report lists them (as C21).
- **Order in `missed plan`** (and so `missed apply`): the program's rules
  are matched and applied first, as C37 reads. The floor rule is tried
  after them, as a fallback, only when:
  - no program rule matches the miss;
  - the matched rule is `skip` or `manual`;
  - the matched rule can't be applied (`apply_rule` raises `Unmatched`,
    for example a shift with no free day);
  - the matched rule is a fold that leaves out a priority lift the missed
    session carried, or carries it short.

  A shift that moves the whole session carries every lift with it, so
  the floor is not tried and no `priority_exposures_missed` is raised.
  In the first three cases the floor rule, when it applies, becomes the
  miss's rule (`data.rule`). In the fourth, the floor rule covers only
  the lifts the fold leaves out or carries short (its id names just
  those), it folds into the week the program's fold has already changed,
  a short lift's folded line is topped up to `floor.sets` working sets
  (never more than prescribed) at its prescribed load and `floor.rpe`,
  keeping the program rule's `fold.rule_id`, `data.rule` stays the
  program's rule, and
  `data.floor_rule` holds the floor rule (null in every other case).
  The summary's first line then ends `, with the priority floor <id>.`
  and the record line reads `- Rules <rule id> and <floor id>: …`. A
  fold covers a lift it gives `floor.sets` working sets or more, or
  every working set the missed line prescribes; with fewer, it carries
  the lift short. When the floor rule is tried and is unmatched, `data.flags` gets one
  `priority_exposures_missed` per lift and the program's rule stands
  alone (or the miss stays unmatched).
- `structure priority [--since D]` (default: 28 days before today)
  returns `since`, `until`, `flags` and per lift `exercise_id`, `name`,
  `sessions` (program sessions holding it), `floor`, `kpi` and `weeks`.
  `kpi` is `{kind, target, by, now, trend, met}`: `now` is the C18 best
  e1RM point in the window (`e1rm`), the heaviest working load or most
  reps at the newest valid exposure (`top_load`, `top_reps`), or the
  slot's `assistance_ladder` state `{value, name, date, session_id}`
  (`rung`, with no trend). `trend` is `{from, to, delta}` over the first
  and last point in the window, null with fewer than two. `met` is null
  without a target; for an `assisted` lift's `top_load`, lower is met.
- `weeks` rows, one per week from the week holding `since` to the week
  holding today: `planned` (core sessions holding the lift as their own
  line, not a fold and not a moved session), `trained` (workouts with a
  working set of it), `missed` (planned, dated before today, C18 status
  `missed`), `replaced` (a fold of the lift from that miss, or the
  session moved from it, was trained), `pending` (that make-up is still
  upcoming) and `unreplaced`. Each week with `unreplaced` raises one
  `priority_exposures_missed`, naming the misses.
- `structure balance --variant minimum` returns `variant`,
  `reference_week` (the week holding tomorrow), `sessions`, `schedule`,
  `targets`, `positions` (per position of the minimum week's schedule:
  `sessions` with `minutes`, `cap_minutes`, `within_cap`; `muscles` with
  `target`, `third`, `planned`, `met`; `priority` with `floor_sets`,
  `sets`, `session_id`, `met`), `passed`, `reasons` and `flags` (empty).
  Coach-led sessions are not counted: the minimum week stands on its own
  sessions. Session minutes are R-24's estimate
  (`coach.validity.estimate_minutes`). A floor is met by one session
  holding at least `floor.sets` hard working sets of the lift. On a
  failure it exits 1 with each reason as a detail at `$.minimum_week`
  and the report kept in `data` (C3).
- `structure minimum [--week W] [--write]` (default: the week holding
  tomorrow) returns `week`, `span`, `plan`, `path`, `written` and
  `balance` (`passed`, `reasons`); it plans the minimum week's schedule
  over its sessions only, refuses (exit 1) when the program has no
  minimum week or it plans no session that week, and writes only with
  `--write` (not with `--dry-run`). The plan is `{variant: "minimum",
  rule, week, span, sessions: [{date, session_id, title}], rotation:
  null, flags: []}`.
- `routine/program.md` gains `## Priority lifts` and `## Minimum week`
  sections only when the program has them, so existing pages stay fresh.
- A session dated today is not yet missed for `priority_exposures_missed`,
  though C18 adherence already counts it.

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
  adopted `light_week` decision covering it), not a `minimum` or
  `one_off` week, not inside a layoff gap of 11+ days. The window reaches
  back at most 12 weeks; with fewer than four ordinary weeks it reports
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
 "by_session": {"session-a": {"quadriceps": 3.0, "chest": 3.0}},
 "flags": []}
```

- `kind`: `ordinary`, `light`, `minimum`, `one_off`, `layoff`, the first
  that applies in the order `light`, `minimum` (a minimum plan file for
  the week, C40), `one_off`, `layoff`. Session `status` from C18
  adherence; external `status` `done`, `not_done`, `unconfirmed`.
- `planned` counts core and external sessions, `unconfirmed` excluded.
  `trained` counts core sessions with status `trained` and external
  sessions `done`. Optional sessions appear with `tier: optional` and count
  in neither.
- `muscles[m].planned`: core sessions and external estimates;
  `delivered`: logged core workouts plus `done` external estimates;
  `bonus`: logged optional and `extra` workouts.
- `by_session` and `session_volume_high` (info) use logged workouts;
  `session_volume_high` (warn) uses the sessions the overlay plans.

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
  one session, the per-session figure (rn:volume-frequency.3). Warn on a
  planned session: each active lifting program session in `structure
  balance`, and each lifting session an overlay plans in `structure
  week`. Info on a logged workout in `structure week`.
- `structure decide` appends the C25 `adherence_trigger` decision and
  prints R-02's line ("Adherence trigger: 58 % over 4 weeks: deferred to
  2026-11-02") for the check-in record.
- Check `program_balance` (warn) runs the static balance on
  `data/program.json`.
- R-30a's flags are registered in `coach/flags/structure.py` (C20).
  The `structure week`, `structure adherence` and `structure balance`
  commands route their flags through `coach.flags.for_mode` (C44); the
  `coach.structure` functions and the `program_balance` check keep the
  registered severities.

**Built with R-30a** (details the sections above leave open):

- Signatures: `week(root, week_start, *, today=None, now=None)` takes a
  date or a `Span` (the week holding it); `adherence`, `balance` and
  `ordinary_weeks` take the same keyword `today` and `now`.
  `coach.structure.session_dose(library, session)` is the planned dose of
  one session in either shape (a program session's set groups count
  `count` sets each; an overlay lists each set), and `planned_dose` sums
  it. Planned sets follow C18's hard-set rule: working sets not
  prescribed at RPE 5 or below.
- Session status comes from `coach.stats.adherence_of(root, planned,
  window, ...)`, the C18 matcher over given `(overlay, session)` pairs
  (`stats.adherence` calls it). A day no overlay covers takes the
  schedule rule's plan on the program, paired with a stand-in overlay
  whose `id` is null (the row's `overlay_id` is null).
- `structure week` rows: core and optional sessions carry `session_id`,
  `date`, `tier`, `status`, `moved`, `workout_id`, `overlay_id`, plus
  `tag` when missed and `unlogged: true` when trained unlogged. Coach-led
  rows carry `external_id`, `title`, `date`, `status` and
  `estimated_sets`. A coach-led session dated after today is `upcoming`.
  A coach-led session with `weekday` null is placed on the dates of its
  `external` annotations in the week. A placement takes the nearest
  annotation for that session in the week; of two on one date, the
  newest wins.
- `muscles[m].planned` adds coach-led estimates that are `done`,
  `not_done` or `upcoming` (an `unconfirmed` one is out of both sides).
  Muscles listed: every muscle with a target or any non-zero value;
  `target` null for a muscle without one. The output also carries
  `label` (`2026-W41`). `by_session` is keyed by session id, or
  `<session_id>@<date>` when a session is logged twice in the week.
- **Layoff week**: no workout, trained-unlogged session or coach-led
  session done in the week, and more than 10 days (the first C22 return
  band) from the last training before it to the first after it (or to
  the day after `until` when none follows yet). A week with no training
  before it at all is a layoff week. Weeks ending before the earliest
  overlay or workout are never scanned.
- A light week by decision: an adopted `light_week` decision, not
  withdrawn, whose `details.week` falls in the week.
- `structure adherence` returns `until`, `weeks` (`{week, label,
  planned, trained}` oldest first), `skipped` (`{week, label, kind}` for
  the non-ordinary weeks passed over), `planned`, `trained`, `pct`
  (rounded half up), `insufficient_weeks`, `flags` and `decision`. The
  70 % and 80 % lines compare the unrounded ratio. Its delivered
  `volume_undershoot` counts `delivered` plus `bonus` against the target.
- Decisions in effect, judged at `until` and ignoring decisions made
  after it: the newest `restructure` decision suppresses
  `restructure_required` as above, counting only ordinary weeks that
  start after the day it was made; an `add_session` decision is adopted
  only and holds for 28 days (`until` is set to `made_at` + 28).
  `withdrawn` decisions hold nothing.
- `structure decide` refuses (exit 1) when there are fewer than four
  ordinary weeks, `restructure` at 70 % or more, `add_session` at 80 % or
  more or with an outcome other than `adopted`, `declined` or
  `add_session` without `--reason`, `deferred` without a `--revisit`
  after today, and `--revisit` on any other outcome. Without `--reason`,
  `adopted` records "smaller schedule adopted" and `deferred` "deferred
  to <date>". Lines: `adopted`, `declined: <reason>`, `deferred to
  <date>`, and for an override `adopted (override: <reason>)`. Output:
  `decision`, `line`, `adherence` (`pct`, `planned`, `trained`, `weeks`),
  `written`.
- `structure balance` plans the week holding tomorrow once per position
  of the schedule rule (`positions(params)`, or one pass when it has
  none), with the rotation set to that position. Every coach-led session
  counts once per position. Output: `reference_week`, `positions`
  (`{position, sessions, external, muscles}`), `average`, `targets`,
  `muscles` (`{target, average, met}`; `met` null without a target),
  `by_session` (each active lifting session's planned dose, either tier,
  which `session_volume_high` judges), `added`, `adherence` (with FILE:
  `pct`, `planned`, `trained`, `insufficient_weeks`) and `flags`. FILE is
  validated like `program validate` (exit 1). `added` lists sessions
  active in FILE but not active in `data/program.json`, then new
  coach-led ids; `add_session_type_blocked` names each in `session_id`.
  It is not raised with fewer than four ordinary weeks.
- Check `program_balance` warns once per flag, as `<code>: <message>`;
  it skips with no program, or one the balance cannot be worked out for
  (`program_schema` reports why).

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
- `class`: `hard`, `partial`, `low`, `light`, `return`, `one_off`,
  `minimum`. Version 1 holds `minimum` too: widening the enum leaves every
  ledger valid, so it bumps no version.
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
  `ceiling`, `triggers`, `illness`, `coach`, or null.
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
- **Hard week**: not light, return, one-off or minimum; at least 75 % of
  planned core and coach-led sessions trained as prescribed. Under 50 %
  trained ends the block.
- **Ceiling**: `program.blocks.hard_weeks_ceiling`, default 6, allowed 4–8.
- **Triggers** (four): athlete-reported readiness, compound RPE drift two
  sessions running (`coach.patterns.rpe_drift`), an `aggravated` niggle
  (C27), poor sleep (the athlete's report, or `coach.cardio.sleep_debt`
  over the closed week; None means no source).
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
  since the last deep close (rn:deloads.12), a light week is being proposed, R-30a's
  structural flags are raised (coach mode only: in run mode, C44, no
  `adherence_trigger` decision is ever recorded to clear them), a
  catch-up check-in deferred a due deep review, or on the first close;
  never because of the light week itself.

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

**Built with R-31** (details C42 and C43 leave open):

- Signatures: `close(root, week_start, readiness=None, sleep=None,
  deep=False, dry_run=False, *, today=None, now=None)`, `status(root, *,
  today, now)`, `classify(root, week_start, *, today, now)`;
  `status_line_for(block_state, ceiling, ledger=None, decisions=None)` is
  the pure form `status_line(root)` and `program adopt` call.
  `coach.block.trained_as_prescribed(lines, workout)` is the C43 rule;
  `coach.block.outcome_for(class, count, fired, ceiling, ill)` the light
  week rules.
- **Which weeks a close covers**: every week after the newest closed one
  up to `--week`. With none closed yet: after the week
  `state.block.last_closed_week` names (`block init` sets it), else only
  `--week` when the open block carries a seed (`seed_reason` set: a
  migrated or state-seeded count already covers the weeks before), else
  from the block's `started` week. A week that has not started exits 1;
  re-closing the newest closed week replaces its entry (undoing the
  block end it caused); an older week exits 1. With no `data/blocks.json`
  the first close seeds one from `state.block`.
- A block that ends records `ended` as the last day of the week that
  ended it; the next block starts the day after, at zero. Every reset
  week ends a block, even one with no hard week.
- **Classes**, in order: `light`, `minimum` and `one_off` from
  `coach.structure.week` `kind` (`minimum` and `one_off` neither count
  nor reset); `return` when a session of the overlay in force carries a
  line decay past `0-10` and the last lifting workout before the first such
  session is more than 10 days back (R-02: a return week follows a
  layoff of 11+ days, so one stale lift rotated back in never ends a
  block); `low` when trained is under half of planned; `hard` when
  trained as prescribed is at least three quarters of planned; else
  `partial` (also with nothing planned). Trained as prescribed counts
  coach-led sessions `done` and core sessions logged against the overlay
  line (or the program session when no overlay covered the day),
  comparing `min(logged, prescribed)` working sets per line; a
  `trained_unlogged` session has no logged sets, so it is not.
- **Triggers**: readiness and sleep only for the week `--week` names
  (earlier weeks of a catch-up close read sleep from
  `coach.cardio.sleep_debt` only, else `unknown`). RPE drift: a compound
  or recovery-capped lift whose two newest non-excluded exposures up to
  the week's end, the newer inside the week, both drift (prescriptions
  from `coach.propose.Run.exposures`). Niggle: a row whose status on the
  week's last day (today for the week closed today or later) is
  `aggravated`. Sleep reads `coach.cardio.sleep_debt(root, span)`
  (C49): None, so `unknown`, without an activity source.
- **Illness**: a `low` week with an `ill` miss proposes a `return` week
  with reason `illness` (C42's reason enum gains `illness`), whatever
  the count.
- **Light-week state after a close**: an `agreed` week later than the
  closed week is kept; so is a `declined` state, with its
  `decision_id`, when the close re-closes the same week and still
  proposes the same type for the same week. Otherwise the closed week's
  outcome sets it
  (`due` → `proposed` for the next week, `watch`, `skipped`, `none` →
  `not_due`). The status line adds ", proposed again next check-in" to
  a decline only when the reason is `ceiling`; a declined trigger week
  is proposed again only if the triggers fire again.
- **Deep review** reasons: `first_close` and `six_weeks` come from
  `coach.checkin.deep_reasons` over the `check-ins/` records, with
  `state.block.last_deep_review` counted as one more deep record:
  `first_close` when no deep review is on record, `six_weeks` when
  `checkin.DEEP_AFTER_DAYS` (42, rn:deloads.12) or more have passed since the newest;
  `catch_up_deferred` when `coach.checkin.deferred_reason` finds a
  catch-up that put a due deep review off; `light_week_proposed`; and
  `restructure_required` (the adherence
  trigger from `coach.structure.adherence`). R-02's prose names the
  adherence trigger, not every structural flag, so `volume_undershoot`
  and `add_session_type_blocked` do not make a check-in deep. `--deep`
  marks the closed week `deep` and sets `last_deep_review` to today.
- `block decide`: `declined` needs a proposed (or declined) week and
  `--reason`; at the ceiling its `revisit_on` is the end of the proposed
  week. `adopted` takes the proposal's type and week by default; another
  type needs `--reason`, and with nothing proposed it needs `--reason`
  and records reason `coach`. An agreed week refuses a second decision
  until its decision is withdrawn. The output carries `command`, the
  `propose week --kind deload` run that builds the week (`--transform
  light` or `--transform return`; none for `deload`, which uses the
  program's `deload_rule`).
- `block init --hard-weeks N [--through W] [--started D]` replaces a
  ledger with no closed week (the migration's seed included): the block
  keeps the state's id, `--through` defaults to last week and becomes
  `last_closed_week`, and `--started` defaults to N weeks back from it.
- `program adopt` keeps the current `block` when a state exists, and
  starts `b-0001` today when it does not.
- `block_state` compares `id`, `started`, `hard_weeks_completed` and,
  once a week is closed, `last_closed_week` with the ledger; it skips
  without a ledger. `light_week_overlay` warns on an agreed week with no
  `deload` overlay covering it, and on a current `deload` overlay that
  no adopted `light_week` decision covers.
- The status provider `program` (C52) and the dashboard (C38) show the
  status line instead of the deload status.

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

**Built with R-40b** (details the sections above leave open):

- The table is declared in `coach/config_tables/coaching.py`, which also
  exports `mode(config)` and the constants `COACH`, `RUN` and `MODES`.
  Any other value exits 5 naming `[coaching]` and `mode`.
- `for_mode` returns new flag objects and never changes its input. In run
  mode a flag whose registered code is structural and whose severity is
  not `block` comes back at `info` with "run mode: " prefixed once (a
  message already starting with it is not prefixed again); every other
  flag, an unregistered code included, is returned as it is. A mode other
  than `coach` or `run` raises `ValueError`.
- Callers: `checkin prepare` and the record's Week in review region apply
  it to the card's flags, after the card parts and before the catch-up
  card is built; the brief and the dashboard apply it to the week's
  overlay flags before keeping `block` and `warn` (so a structural flag
  drops out of Watch and the open-flag count); the three `structure`
  report commands apply it to their `flags` (C41).
- The brief's and the dashboard's header line add `run mode` after the
  phase in run mode.
- In run mode `block close` and `block status` leave
  `restructure_required` out of `deep_review.reasons` (C43).
- `propose week`, the plugins, the validator and `block close`'s
  light-week rules do not read the mode.

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

**Built with R-40a** (details the text above leaves open):

- `--gym` defaults to `commercial`. `coach.onboarding.suggest(unit,
  gym)` holds the table; the command lives in
  `coach/commands/config_suggest.py`.
- `data` holds `unit`, `gym`, `values` and `notes`. `values` is
  `{"athlete": {"units", "bodyweight_units"}, "equipment": {...}}`, the
  equipment keys as in the table above; a home gym leaves
  `dumbbell_max` out, so an lb home config fails validation until the
  athlete's answer is written. `notes` is `[{key, message}]`, `key` a
  dotted config path such as `equipment.dumbbell_max`.
- `/setup` writes Hevy free as `[hevy] enabled = false`. It writes
  `[nutrition]` only as `enabled = false`, when the athlete declines
  nutrition coaching. On a yes it writes nothing and `/goals` sets the
  table after week one is approved, because `enabled = true` without
  R-33a's required keys fails validation. On "later" it writes nothing.
- The profile skeleton's sections are Goal, Training week, Equipment,
  Injuries / limitations and Coach's notes. The last-but-one keeps the
  heading `niggles import` reads (C27).

## C45. Program drafts, adoption, import and starters (R-41a, R-41b; R-40a, R-40c read)

A **program draft** is what `program adopt` takes. Every program source
(starter, import or a hand-written design) goes through it; no skill
writes `data/program.json` directly.

```json
{
  "schema_version": 2,
  "source": "hevy_import",
  "created_at": "2026-10-11T18:00:00Z",
  "program": { "...": "a complete program.json document (C16 / C23 v2 or later)" },
  "position": null,
  "hevy_routines": {"00000000-0000-4000-8000-000000000001": "session-a"},
  "hevy_folder": 1,
  "report": [
    {"kind": "converted_load", "session_id": "session-a", "exercise_id": "db_bench_press",
     "message": "Hevy 50 → 25/hand"},
    {"kind": "schedule_missing", "session_id": null, "exercise_id": null,
     "message": "Ask the athlete which days each session falls on."}
  ],
  "detected": {"percentage_based": false, "evidence": [], "suggested_schemes": []}
}
```

- `source`: `starter:<id>`, `hevy_import`, `manual_import`, `design`.
  `manual_import` means a supplied paper/manual program transcribed with its
  exercise/scheme structure preserved unless the athlete agreed edits. It
  uses no Hevy mapping or detection. Draft v2 adds this source. For an existing
  v1 draft, change only its top-level `schema_version` to 2, preserving its
  source, program and report, then rerun adoption's dry run. Drafts remain
  outside the migration runner; the nested program retains its own version.
- `hevy_folder` (R-41a): the Hevy folder id the imported routines share
  (`--folder`, else the one folder they all sit in), or null. Adopt
  writes it to `state.hevy.folders.program`; null keeps the old state's.
- `report[]`: `{kind, session_id, exercise_id, message}`, the ids null
  where they do not apply. `kind`: `converted_load`, `mixed_loads`,
  `cues_from_notes`, `schedule_missing`, `swapped_exercise`,
  `no_substitute`, `percentage_evidence`. The skill shows the report as
  one table.
- `detected` is filled by import only; for other sources it is
  `{"percentage_based": false, "evidence": [], "suggested_schemes": []}`.
  An evidence item is `{kind, exercise_id, message}` with `kind`
  `keyword`, `week_titles` or `top_loads`.
- Schema file `program_draft.schema.json`; the `program` member is
  validated with the program schema and the plugin `PARAMS` (C23).
  Drafts are gitignored and never migrated (C7).

`program adopt --input FILE [--replace] [--position P] [--dry-run]`:

1. Validate the draft and its program (`program validate` rules, library
   ids, `[caps]` for start loads, every `hevy_routines` session in the
   program). Exit 1 with JSONPaths from the draft's root
   (`$.program.sessions[0]...`) on failure. A schedule whose params name
   no program session (the import's placeholder) fails at
   `$.program.schedule.params`. A position the rule does not have, or a
   position for a rule without one, exits 1.
2. With an existing program: exit 3 without `--replace` (under
   `--dry-run` too); with it, copy both files to
   `data/archive/programs/<today>/` (`<today>-2`, `-3` when that exists).
3. Write `data/program.json` and `data/state.json` (block started
   today, zero hard weeks, deload not due; rotation position from
   `--position`, else the draft's `position`, else the schedule rule's
   first position, confirmed today for the week holding tomorrow, or
   null with `confirmed_at` and `week` null for a rule without positions;
   scheme state kept only for slots whose exercise and scheme are
   unchanged; `hevy.routines` from the draft; `one_off`,
   `folders.one_off` and `temporary_routines` carried over from the old
   state).
4. Render the pages (`program render`'s rules: changed pages written,
   pages of dropped sessions removed). Stage the written, archived and
   removed files; never commit. Outside a git work tree it writes and
   warns.
5. Return `data.unconfirmed` (`[{exercise_id, sessions}]`): program
   exercises with no confirmed load mode in the instance library. Adopt
   does not confirm on the athlete's behalf; the skill runs `library
   confirm` or `library set-mode`. Also `data.avoided`
   (`[{exercise_id, sessions, reason}]`, active sessions only, each with a
   warning), `data.without_routine` (sessions no `hevy_routines` entry
   names, empty when Hevy is off), `data.scheme_state` (`kept` and
   `dropped` slot keys), `archived`, `written`, `removed`, `staged`;
   under `--dry-run`, `would_archive`, `would_write` and `would_remove`.

Adopt reports an avoided exercise (C54) the way it reports an
unconfirmed load mode and leaves it in the program: swapping it is the
coach's call, made with the athlete (amended in R-41a's triage).
`starters draft` (R-41b) still substitutes and reports.

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
- Start load is the top working set's `weight_kg` (for an `assisted`
  line, the least assistance) through `units.from_hevy_kg` with the
  confirmed load mode; every conversion is
  a `converted_load` row (`Hevy 50 → 25/hand`). The value is rounded
  with `units.round_to_increment` to the exercise's increment
  (`stats.load_increment`) only when it does not convert back to the
  same `weight_kg` (a load set in the other unit), and the row says so
  (`Hevy 44.09 → 45, rounded to the 5 lb step`): a load the athlete
  actually set stays exactly as set. With no working load, a
  `bodyweight` line starts at 0 and other loaded lines at null.
  Working sets with different loads keep the top load and get a
  `mixed_loads` row. An exercise repeated in a routine becomes one entry
  whose set groups follow each other, with the first entry's rest and
  superset; its start load and `mixed_loads` check cover the working
  sets of every entry.
- Cues come from the note's `Cues:` line when present; otherwise the note
  text with `Target:`, `Focus:` and `Wk of` lines removed
  (`cues_from_notes`).
- Every imported exercise gets scheme `hold`. Schedule is a
  `fixed_weekdays` placeholder, `{"days": {}}`; adopt fails until the
  coach fills it (`schedule_missing`). Blocks default to a ceiling of 6
  and the `standard` deload rule; there are no external sessions or
  missed-day rules.
- Percentage detection only reports (`detected`, `percentage_evidence`):
  `%`, "TM", "training max", "1RM", "5/3/1" or "531" in titles and notes;
  two or more routines whose titles differ only by a week marker (`W1`,
  `Week 2`, `Wk3`); the same exercise in three or more routines with three
  or more distinct top loads. It suggests `wave_531` for week-marked
  titles or "TM", "training max", "5/3/1" or "531", and
  `fixed_reps_rpe` for `%` or "1RM", or for spread top loads without
  week-marked titles. It never assigns a scheme.
- Output: `draft`, `path`, `written`, and `problems`: what adopt would
  reject in the draft other than its schedule, as JSONPaths.

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
| `full-body-3` | 3 fixed | `linear` | `double_progression` | beginner; no required equipment, since every barbell lift has a dumbbell substitute |
| `upper-lower-4` | 4 fixed | `double_progression` | `double_progression` | beginner to intermediate |
| `push-pull-legs` | 3–6 rolling | `double_progression` | `double_progression` | intermediate |
| `wave-3wk` ("3-week wave (5/3/1-style)") | 4 fixed | `wave_531` | `double_progression` | intermediate, barbell |
| `rpe-full-body-3` | 3 fixed | `rpe_anchored` | `fixed_reps_rpe`; `double_progression` for 12- and 15-rep lines | intermediate to advanced |

- No starter raises a `program validate` warning. `rpe-full-body-3`'s
  12- and 15-rep accessories are too high-rep for an e1RM, so they use
  `double_progression` at 10–12 and 12–15 reps, RPE 8.
- Each starter declares its main lifts in `priority`, its weekly dose in
  `dose_targets` and a `minimum_week` (C40); `structure balance --variant
  minimum` must pass on it.
- Calibration lines (no data, no start load) carry `load: null` on a
  loaded mode with a `no_data` flag (C10).
- `starters list [--days N] [--equipment E,...] [--location NAME]`
  returns id, title, summary, level, days, minutes, required equipment
  and how the starter fits the kit.
- `starters show ID` returns the starter and its rendered session pages.
- `starters draft ID [--days mon,wed,fri] [--start-load EXERCISE=VALUE ...] [--location NAME] [--out FILE] [--dry-run]`
  remaps the schedule to the given days (default: `[athlete]
  available_days` when set, else the starter's defaults), applies any
  start loads (coaching numbers, athlete units), swaps exercises whose
  equipment is not in `available` (from `equipment_for`, C54), whose
  apparatus or ability is unconfirmed, or that are avoided for the first
  library substitute that fits, and writes a draft
  with `source: "starter:<id>"`. Exit 1 when the day count is outside
  `days` or `equipment_required` is not available.
- `cites` holds template research claim refs (C28); empty until the notes
  exist.

**Built with R-41b** (details the text above leaves open):

- Schema `starter.schema.json` v1: `level` items `beginner`,
  `intermediate`, `advanced`; `days.default` lists weekday ids;
  `equipment_required` items are R-11 equipment ids; `cites` items are
  `rn:<note>.<n>`. Every shipped starter cites current template claims.
- `coach.starters.load(id)` takes the starter's `program` through the
  program migration chain in memory, so a later program bump never
  leaves a starter behind; the files are updated when convenient.
- Major muscles, for the weekly-dose test: chest, upper_back, lats,
  front_delts, side_delts, quadriceps, hamstrings, glutes, biceps,
  triceps. Each full starter gives each 10 to 20 fractional sets a week
  (`structure balance` average at the default days) and every muscle at
  most 11 in one session. `dose_targets` sets 10 for each major muscle
  and, for any other primary muscle of an active exercise, the planned
  weekly sets capped at 6, so no muscle falls back to the default 10.
- Minimum-week sessions are `min-a` and `min-b`, standby, on scheme
  `maintenance`. Loaded lines start at null (a calibration line) except
  `bodyweight` lines, which start at 0 added load.
- `starters list` returns `starters` (rows: `id`, `title`, `summary`,
  `level`, `days`, `minutes`, `equipment_required`, `swaps`,
  `unmatched`, `recommended`), `days`, `equipment` (the filter used;
  empty means every piece), `location`, `experience` and
  `recommended_id`. Rows sort by default day count, then id. `swaps` and
  `unmatched` count the `swapped_exercise` and `no_substitute` rows a
  draft would report. `recommended` is true when `level` holds
  `[athlete] experience` and `unmatched` is 0; `recommended_id` is the
  first such row. `--days N` keeps starters with `min <= N <= max`;
  `--equipment` replaces the place's `available` and keeps starters
  whose `equipment_required` it covers (an unknown id is exit 2).
  `--location` judges the kit at `[equipment.locations.NAME]` (unknown:
  exit 5).
- `starters show ID` returns `starter` and `pages` (`program
  render`'s pages for the starter's program with its default days).
- `starters draft`:
  - Days sort into week order. A `fixed_weekdays` schedule gives its
    sessions, in default-day order, to the chosen days in order; a
    `next_in_sequence` schedule takes the days as `params.days`, and the
    draft's `position` is the sequence's last session, so week one opens
    on its first. The minimum week moves to the first chosen day and the
    one at index `(n + 1) div 2`. A day count outside `days` exits 1
    naming the allowed range and where the days came from.
  - The kit is the place's (`--location`, else the main table) from
    `equipment_for`; with `--location` every session's `location` is
    that place. Unknown is not confirmed (`coach.fit`): an exercise does
    not fit when its equipment is missing from a non-empty `available`,
    when an apparatus it `requires` is not in `apparatus` (unless both
    lists are empty: every piece assumed), or when its `ability` is
    `demonstrated` and `[athlete] demonstrated_exercises` does not list
    it, whatever the athlete's experience.
  - A line is swapped when its exercise is avoided (C54) or does not
    fit, in every session, standby ones included. The substitute is the
    first of the library entry's `substitutes` that is not avoided, that
    fits, that no niggle open on the draft's day (status not `resolved`)
    covers unless it also covers the replaced exercise (C27 `matches`),
    that the session does not already hold, and whose load mode the
    line's scheme accepts (`LOAD_MODES`). The line takes its load mode
    (confirmed, else the catalogue default), `cues` null, and a start
    load of 0 for `bodyweight`, else null (a calibration line). One
    `swapped_exercise` row per line names the reason and every
    substitute passed over with its reason. With none that fits, the
    line stays and gets one `no_substitute` row that names them too. A
    priority lift follows its first swap in an active session.
  - After a swap in an active session, `dose_targets` keeps each major
    muscle's target and re-derives the rest as the starter files do:
    each other primary muscle of an active exercise gets its planned
    weekly fractional sets at the draft's schedule, capped at 6, and a
    muscle no longer trained as a primary loses its target. A major
    muscle a swap leaves short keeps 10, so `structure balance` shows
    the gap.
  - `--start-load EXERCISE=VALUE` applies after the swaps to every line
    of that exercise. An exercise the draft lacks, a line that is not on
    a loaded mode, or a malformed pair exits 1.
  - Output: `draft`, `days`, `path`, `written` and `problems` (as
    `program import-hevy`). `program_drafts.report_row` and
    `program_drafts.timestamp` are public for it.
- Catalogue: `bb_back_squat` gains `goblet_squat` and `bb_deadlift`
  gains `db_romanian_deadlift` as last substitutes, so a dumbbell kit
  can run upper/lower.
- Catalogue regressions, so a bench-free dumbbell, band and bodyweight
  kit can run `full-body-3`: `split_squat`, `bw_squat`, `sit_to_stand`
  (`box`), `bw_step_up` (`box`), `incline_push_up` (`box`),
  `knee_push_up` and `db_floor_press`. Last substitutes added:
  `db_floor_press` for the flat presses; `db_bench_press`,
  `db_floor_press` and `push_up` for `db_incline_bench_press`; `db_row`
  for `lat_pulldown`; `db_romanian_deadlift` and
  `db_single_leg_romanian_deadlift` for the leg curls;
  `db_overhead_triceps_extension` for `cable_triceps_pushdown`; and the
  bodyweight regressions for their loaded forms.

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
- Schemas: `manual_workout_line` (`kind: "workout"`) and
  `manual_void_line` (`kind: "void"`), both claiming the file through
  `x-coach-paths` (C7).
- `log prefill --session S --date D` returns `data.draft`: a workout
  line without `id` and `logged_at`, built from the overlay in force on D
  (its session S nearest to D, so a moved session prefills too; no
  overlay, or none with S, exits 1).
  Fixed reps and loads are filled as prescribed; a `rep_range` leaves
  `reps` null; `rpe` and `duration_minutes` are null. Warm-up sets are
  left out.
- `log add --input FILE [--again] [--dry-run]` validates and appends one
  line. Exit 1 for: an input carrying `id` or `logged_at` (`log add`
  assigns both); a schema problem; an unknown exercise id; a load mode
  different from the slot's effective mode (the overlay line's
  `load_mode` when the workout's overlay session has the exercise, else
  the library's confirmed mode; an unconfirmed one accepts any); a null
  `reps` on a set of any mode but `duration` and `distance`; a date
  after today; a `value` on a null-load mode; a `unit` other than
  `[athlete] units`; a session id in neither the program nor any
  overlay; an overlay that does not exist or lacks the session. Exit 3
  when the date and session already have a live entry, unless `--again`
  (a workout with no session is never refused). Warning
  `looks_like_total` when a `per_hand_x2` `value` equals the `hevy_total`
  of a prescribed working set (and no prescribed per-hand load), so the
  athlete gave the pair as one number. Warnings in the envelope start
  with their code (`looks_like_total: ...`, `hevy_enabled: ...`).
  Returns `id`, `line`, and `summary`, one line printed with
  `units.format_load(..., show_hevy=False)`.
- `log void ID --reason TEXT [--dry-run]` appends a void line; an
  unknown or already void id, or an empty reason, exits 1. `log list
  [--since D]` returns live entries as `data.workouts`, oldest first.
- The `manual` history source reads the live entries; no log file means
  `None` (C17). Its `version(workout)` is the C7 canonical hash of the
  `SourceWorkout`. A workout's `title` is its overlay session's title,
  else its program session's, else the session id, else "Ad hoc
  workout"; each exercise's title is its library name.
- Check `manual_log_valid`: every line validates, ids are unique, every
  void names a live workout, exercise and session ids exist; one `fail`
  per problem naming its line. Skips with no log file.
- With `[hevy] enabled = true`, `log add` still works (for a workout the
  athlete forgot to log in Hevy) and warns `hevy_enabled`.
- With Hevy off (`[hevy] enabled = false`, which includes Hevy free),
  `overlay approve` is the last step of a programming pass; `routines
  push` exits 5 naming `[hevy] enabled`, and Hevy checks report `skip`.

`sheets render [--overlay ID] [--dry-run]` writes `this-week-sheets.md`
(C11 whole-file header, no as-of time: the sheets read no history) from
the brief's overlay (C38: the latest created of the overlays in force on
the days of the week holding tomorrow), else the next to start. So on a
Sunday after the programming pass the sheets show the coming week, as
the brief does. `coach.sheets.current(docs, today, week_starts)` picks
it. One section per session in date order, anchored by session id
(`<a id="session-a"></a>`; a session id seen again in the overlay gets
`-2`, `-3`; `coach.sheets.anchors(doc)`): title and date, the session
focus, then one row per run of equal sets
`| Exercise | Sets × reps | Load | RPE | Rest | Done |` with warm-ups on
their own row and the exercise name on its first row, then one bullet
per exercise with its focus and cues. Loads print with
`format_load(load, show_hevy=False)`; a null load on a loaded mode
prints "choose the load". An unapproved overlay renders with a "Not
approved yet" line and a warning. A footer says how to log ("reply to
the coach with what you did; differences only"). Check
`sheets_render_fresh`: skip when Hevy is enabled or there is neither a
file nor an overlay; warn when there is no file yet, or when the file
shows another overlay than the current one; fail when the file has no
C11 header or differs from a fresh render of the overlay its header
names. A page-part module
`coach/page_parts/sheets.py` (C38) contributes one `brief.sessions_footer`
item when Hevy is off and the brief has an overlay: "Session sheets:
[this-week-sheets.md](this-week-sheets.md)" followed by one link per
session to its anchor (`this-week-sheets.md#session-a`).

`pages publish` (C38) includes `this-week-sheets.md` when Hevy is off:
it regenerates the sheets from the approved overlay the brief names and
commits them with their links. Its dry run reports that additional path
without changing files, index or commits. With Hevy enabled there are no
sheet links, and publication neither requires nor stages old sheets.

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
weekly_quality = 2             # quality activities per week, runs and conditioning together; 0 = no cap
spike_ratio = 1.10             # run_volume_spike above this × the longest run in the lookback (rn:running-load.1)
spike_lookback_days = 30
spike_min_history_days = 14    # a run is judged only once the store's first activity is this far before it (rn:running-load.4)
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

- The combined figure is information only (rn:running-load.3). No flag
  reads it, and no ratio of it is ever computed (rn:running-load.2).
- `coach.cardio.CITES` holds `rn:running-load.1` to `.4`.
- Check `cardio_config` (fail, naming the key): caps 0 or more,
  `spike_ratio` above 1, `spike_lookback_days` at least 1,
  `spike_min_history_days` 0 to `spike_lookback_days`,
  `sleep_short_hours` above 0 and at most 24, `sleep_debt_nights` and
  `sleep_min_nights` 1 to 7, `reconcile_move_days` and
  `external_session_minutes` 0 or more, `quality_rpe_min` and
  `external_session_rpe` 0 to 10. Unknown keys and an unknown `tier` or
  `distance_unit` stay load errors (exit 5).
- `coach.cardio.week(root, week) -> dict`, mirrored by `cardio week`
  (`week` is a label, a date or any `Span`; a span that is not one week
  has `"week": null`; the card part passes its window):

```json
{"week": "2026-W41", "span": {"start": "2026-10-05", "end": "2026-10-11"}, "tier": "review",
 "distance_unit": "km", "activity_source": true,
 "lifting": {"workouts": 2, "hard_sets": 26, "minutes": 115},
 "external": {"done": 0},
 "run": {"count": 2, "distance": 18.5, "minutes": 110, "quality": 1},
 "conditioning": {"count": 1, "minutes": 20},
 "other": {"ride": {"count": 1, "minutes": 45}},
 "srpe": {"total": 1810, "by_method": {"athlete": 3, "lifting_sets": 2, "kind_default": 1}},
 "bouts": [{"ref": "manual:2026-10-06-run-1", "date": "2026-10-06", "kind": "run", "session_id": null,
            "minutes": 40, "distance": 7, "quality": true, "quality_basis": "rpe",
            "srpe": {"rpe": 8, "load": 320, "method": "athlete"}}]}
```

  `hard_sets` is the week's total of C18 hard sets (not a per-muscle sum)
  over exercises the library resolved, as C18 counts them. `minutes` for
  lifting come from C18 durations. Lifting and coach-led bouts have
  `quality: false` and `quality_basis: null`; workouts of a conditioning
  session (C17) are not lifting, they arrive as Activities. `srpe.rpe`
  for `lifting_sets` is the mean of the RPEs given, to 2 decimals;
  loads are rounded to 1 decimal.

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

coach.cardio.bouts(root, span, mode, overlay=None, today=None) -> list[Bout]
#   mode "logged":   C17 workouts, C30 activities, C17 `external` annotations marked done
#   mode "proposal": the overlay's sessions (kind "conditioning" for a conditioning session, else
#                    "lifting"; ref "<overlay id>/<session id>", minutes None), external sessions
#                    placed on their `weekday`, and at tier review|program the planned activities
#                    no logged Activity matched; with `today`, only dates from today on.
#                    No logged bouts: `evaluate` reads those itself (see Flags)
coach.cardio.match(planned, logged, move_days, today=None) -> list[dict]   # the reconcile matcher; R-44b reuses it
#   planned: C30 planned records; logged: resolved Activities. With today None every
#   unmatched plan is "missed".
coach.cardio.flag_bouts(root, config, span, today) -> list[Bout]   # what `cardio flags` judges
coach.cardio.evaluate(ctx) -> {"flags": [...], "skipped": [...]}  # every C49 rule; the provider returns "flags"
coach.cardio.evaluation_date(ctx) -> date   # the last night the `sleep_debt` flag judges
```

`Bout.to_json()` gives the dataclass as JSON (dates `YYYY-MM-DD`,
timestamps C7). A logged coach-led bout's `ref` is its annotation id
and its `session_id` the external id; a placed one uses the external id
for both.

**Reconcile** (`cardio reconcile --week W`, tiers `review` and
`program`; at `count` it returns `{"tier": "count", "items": []}`):

- Pass 1: same kind, same local date → `done`. Pass 2: same kind within
  `reconcile_move_days`, nearest first, ties to the earlier activity →
  `moved` (with `moved_days`). Unmatched planned before today → `missed`;
  today or later → `upcoming`. Unmatched activities → `extra`.
- Each item: `{status, planned_id, activity_id, date, activity_date,
  moved_days, kind, title, target: {...}, actual: {distance_meters,
  duration_seconds}, delta: {distance_meters, duration_seconds},
  quality}`. `date` is the plan's date (an `extra` item's own date);
  `activity_date` is the matched or extra Activity's; `moved_days` is
  the Activity's date minus the plan's, set only on `moved`; `delta` is
  actual minus target where both exist. An `extra` item's `quality` is
  the C48 rule's; a planned item's is the plan's. The output adds
  `summary`, counts by status.
- Planned activities from several sources are not merged (C30); each
  matches on its own, so a duplicate plan shows one `done` and one
  `missed`.

**Flags** (`cardio flags (--week W | --span A..B)`; also the `cardio`
week-flag provider in `propose week`; registered in
`coach/flags/cardio.py`, rows in C20):

| Code | Rule |
|---|---|
| `cap_breach` | Logged week, and planned week at `review`/`program`: run distance or minutes above the weekly cap; any single run above the single-run cap; quality activities above `weekly_quality`. One flag per cap broken, naming value, cap and unit. A planned record with only a duration target is checked on minutes only. |
| `run_volume_spike` | A run whose distance (else minutes) exceeds `spike_ratio` × the longest logged run in the `spike_lookback_days` before its date. Warn logged, info planned. No reference run, or store history shorter than the lookback (the store's first logged Activity, any kind, is fewer than `spike_min_history_days` before the run): listed in `data.skipped` with the reason, not flagged (rn:running-load.1, rn:running-load.4). |
| `quality_stack` | Two quality bouts on the same or consecutive local dates, logged or planned. Lifting is not part of it; lifting against runs is `collision` (C51). |
| `sleep_debt` | Over the 7 nights ending on the evaluation date (C30 wellness, resolved): at least `sleep_min_nights` with a value and at least `sleep_debt_nights` below `sleep_short_hours`. Evaluation date: the span's last day for `--week` and `--span`, or today when the span ends later; today for proposals. |
| `status_active` | A status day overlaps the span or today. Warn `ill`/`injured` (`injured` adds "check with a qualified professional"), info `travel`. |
| `niggle_link` | An active niggle's `applies_to.activity_kinds` holds the kind of a logged or planned activity in the span. The message gives the count and distance of those activities. |

In proposal mode, `evaluate` also reads the logged activities in the
span's C7 week dated before the span starts, so a midweek draft is judged
with the week's runs so far. They count toward that week's
`cap_breach` totals (run distance, run minutes, quality activities) and
as `quality_stack` neighbours. The single-run caps judge only the span's
bouts, and a pair of two earlier activities is not flagged again.

`coach.cardio.sleep_debt(root, span) -> bool | None` is the one reader of
the sleep rule for other items: it judges the 7 nights ending on
`span.end` of whatever span the caller passes (R-31 passes the configured
week from `coach.dates`), and returns None when `[activity]` is off or
fewer than `sleep_min_nights` nights have data. The `sleep_debt` flag
judges the nights ending on the evaluation date
(`coach.cardio.evaluation_date(ctx)`) instead. For a span ending on or
before today the two agree: the flag is raised exactly when
`sleep_debt(root, span)` returns True. For a span ending later they can
differ, because `sleep_debt` does not clamp to today. R-31 calls it for
its poor-sleep trigger.

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
later that no logged Activity matched. A provider that raises fails the
command (exit 9); it is never skipped silently. `cardio flags` returns
`{span, tier, today, sleep_judged_to, flags, skipped, bouts}`; `skipped`
lists the runs `run_volume_spike` could not judge (`{ref, date, source,
reason}`). With `[activity] enabled = false` only `status_active` can
fire. R-43's card part `cardio` (C36) owns the `runs` and `sleep`
fields: the window's runs from `week`, plans `reconcile` found missed,
the last seven nights when `sleep_min_nights` have data (else the
builtin ask), and every provider's flags over the window.

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
- `status-days add --kind K --from D [--to D] --note TEXT [--source TEXT]`
  (`--source` defaults to `coach`; a second ongoing row of one kind is
  refused, exit 1), `status-days end ID --date D`, `status-days withdraw
  ID --reason TEXT`, `status-days list [--active]` (`--active`: rows not
  withdrawn).
- `coach.statusdays.active(root, span) -> list[dict]` (rows not
  withdrawn whose days overlap the span; an ongoing row runs on) and
  `coach.statusdays.ill_in(root, span) -> bool` are the only readers
  other items call. The file is a migration-runner document (C16,
  `coach/migrations/status_days/`).
- Return rule: an `ill` status day overlapping the gap before a session
  counts exactly like an `ill` miss annotation for C22 and
  `return_after_illness`. Travel only explains the gap. Days off stay days
  off.
- Check `status_days_valid`: schema, unique ids, `start ≤ end`, at most one
  open-ended row per kind.

**Fixture instance `cardio/`** (R-43): a copy of `valid/` with its
activity, wellness and planned records and its sync map removed, plus
R-20's four logged workouts as `data/history/2026-09.json` and
`2026-10.json`, resolved by `history sync` from the synthetic set (no
Hevy cache), and:

- config: `[activity] enabled = true`; `[cardio] tier = "review"`,
  `weekly_run_distance = 18`, other caps default.
- activities (manual): 2026-09-21 run 10 km 60 min RPE 5; 2026-10-05 ride
  45 min; 2026-10-06 run "Intervals" 7 km 40 min RPE 8; 2026-10-07
  conditioning 20 min; 2026-10-09 run 11.5 km 70 min RPE 4.
- planned (manual): 2026-10-06 "Intervals" quality, 7 km; 2026-10-08
  "Long run" 11 km; 2026-10-10 "Easy 5 km" 5 km; 2026-10-14 "Easy 5 km"
  5 km; 2026-10-16 "Tempo" quality, 40 min.
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

**Built with R-44a** (details the text above leaves open):

- `InterferenceContext` also carries `titles` (`{ref: name}`: the session
  title, workout title, Activity name or planned title) for messages.
  Rules call the pure helpers in `coach.plugins.base`: `is_lift` (kind
  `lifting` or `external`), `quality_activities`, `timed`, `bout_end`
  (`end`, else `start` plus `minutes`), `hours_between`, `hours_text`,
  `bout_text` and `session_flag(code, message, session_id, severity)`.
- `bouts` also holds the quality activities of the days just before the
  span (`ceil(max hours / 24)` days, at least 1; logged ones to today and
  unmatched plans from today on, as `cardio flags` reads them), so a
  session on the span's first day is judged against the day before.
  Timestamps are in `[athlete] timezone`.
- A pair is judged on timestamps when both bouts have times, and at day
  level otherwise (a planned bout, a coach-led annotation), with the
  proposal-mode severities. At day level `quality_before_heavy_lower`
  looks 1 to `ceil(hours / 24)` days back. On timestamps it judges any
  quality activity ending under `hours` before the session starts, the
  same date included, so a quality run before a heavy squat session on
  one day raises both rules.
- Heavy lower reads a rep range by its start (the fewest reps asked). A
  rule without `heavy_rpe` or `heavy_max_reps` gets 7 and 6.
- `program validate` checks each rule's params against its plugin and
  fails a rule listed twice, at `$.interference[i]`. `program
  import-hevy` drafts list the two framework rules with their defaults
  (`coach.interference.default_rules()`).
- A framework rule that emits a code other than `collision`, or an
  instance rule a code outside its `FLAGS`, raises `PluginError` (exit
  9). `plugins validate` also fails an instance interference rule that
  passes a framework flag code to a call.
- `coach.interference.flags(root, config, span, mode, bouts, today,
  overlay=None)` is the one entry point; the provider and `interference
  check` call it. `interference list` returns `{rules, available}`:
  `rules` is the program's rules with params merged, `source`, `summary`
  and `cites` (null with no valid program), `available` every valid
  interference plugin with its defaults. `interference check` reads the
  bouts `cardio flags` reads and returns `{span, today, rules, flags}`.
  Those bouts hold lifting only once it is logged, so for an upcoming
  week it judges planned activities against logged lifting alone;
  `propose week` judges the week's planned sessions.
- Messages start with the rule name, e.g. `quality_before_heavy_lower:
  planned run "Tempo" (2026-10-11) is the day before planned Session A
  (2026-10-12), a heavy squat or hinge session. Keep quality activities
  at least 24 h before heavy lower-body lifting.`

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

**Built with R-44b** (details the text above leaves open):

- **Program v7.** Session `scheme` is optional and reads as null, like
  `location`; the migration step writes `scheme: null` on every session.
  `program validate` fails a session scheme on a `lifting` session
  (`$.sessions[i].scheme`), a non-`hold` exercise under one
  (`$.sessions[i].exercises[j].scheme.name`), an unknown density scheme,
  params that fail its `PARAMS`, and whatever its optional
  `problems(params, session) -> [(path, message)]` reports under
  `$.sessions[i].scheme.params` (reps for every exercise, caps at or
  above the start, at least one minute per exercise for an EMOM). The
  session page names the scheme and its params.
- **Plugin kind** `conditioning`: `propose` and `decay` required,
  `problems` optional, `STATE` required. `exercises` are
  `base.ExerciseInfo`. `last_prescription` is `{overlay_id, session_id,
  date, dates, span, lines}`: every date that overlay planned the
  session, and the newest date's sets per exercise. Helpers in
  `coach.plugins.base`: `work_set` (reps; seconds for `duration`, metres
  for `distance`), `density_verdict`, `stepped`, `stepped_back`,
  `density_decay`, `RPE_LOG_HINT`, `HEURISTIC`, `AT_CAP`.
- **State** `{"current": prescription | null, "previous": [...]}`. An
  EMOM prescription is `{minutes, reps, turn}` (`turn`: the exercise
  next in line for a rep), a circuit's `{rounds}`. A step up pushes the
  current prescription onto `previous`; a step back pops it, so it
  restores the previous prescription exactly, and at the start it holds.
  An exercise missing from `reps_cap` gains no reps. A stored
  prescription whose exercises no longer match the session restarts from
  the params. Every rationale that steps or holds on a bout says "a
  coaching heuristic".
- **Bouts and days off.** The newest approved overlay holding the session
  gives its dates; `coach.cardio.match` pairs them (kind `conditioning`,
  `reconcile_move_days`) with the conditioning Activities in that
  overlay's span. With `[activity] enabled = false` there are none and
  the scheme holds. Days off count from the newest logged conditioning
  Activity before the session date (0 with none); past 10 the session
  decays and raises `return_week` at session level.
- **Lines.** Each load is the slot's last approved top load, else its
  `start_load`; C26 constraints, caps and the illness RPE cap still apply,
  and nothing is rounded (the load is one the slot already knows).
  Provenance `scheme` is the density scheme, `derived_from` and `decay`
  are null, and every line carries the session's rationale; only the
  first exercise carries `focus`. The scheme's `no_data` is a session
  flag. A deload run, and the session's second date in one run, hold
  without judging, so one bout never moves the scheme twice.
- **Drop rule order.** Step 5b's decision is taken on the draft's
  sessions before step 5, so the step 5a flags judge the week without a
  dropped session; the `conditioning_dropped` flags follow 5a's. Triggers,
  first match wins, each reported by its flag code: `sleep_debt` (the 7
  nights ending today, `coach.cardio.sleep_judgement`), `status_active`
  (`coach.statusdays.active` on the session's date, any kind) and
  `quality_stack` (another quality bout within a day, from the bouts and
  tier filter R-43's flag judges, the week's earlier logged activities
  included; a session dropped earlier in date order no longer counts).
  The info flag's `session_id` is null, since the overlay no longer holds
  the session; its message names it. A draft is never emptied: when
  every session would go, none does and each gets the warn flag.
- **Restore.** `data.dropped` rows are `{session_id, date, trigger,
  reason, restored}`; the run facts (`.meta.json`) also keep each dropped
  session's draft and the scheme state it would have left pending, and
  `propose show` lists the rows. `propose restore` puts every dropped
  date of the session back into the draft and the `.proposed.json` copy
  (it is what the pipeline proposed, so finalize finds no unexplained
  change), resolves each flag with the reason, makes its scheme state
  pending again, re-runs the R-24 check and adds any new week flag. A
  session that was not dropped exits 1. Output `{id, session_id,
  restored, flags, lines, written}`.
- `state.problems` accepts `<session_id>/_session` for a `conditioning`
  session only; `program adopt` keeps that entry when the session keeps
  its density scheme. The flag registers in `coach/flags/conditioning.py`.

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
- `coach.status.collect(root, today, env=None, stderr=None,
  providers=None) -> list[Section]` runs them in `order` (ties by id);
  each provider's `ctx.today()` is `today`. R-26b's orders: `instance`
  10, `checks` 20, `overlay` 30, `program` 40, `checkin` 50, `hevy` 60.
- `lines` are plain sentences for a human, at most three per provider,
  loads only through `units.format_load`. `level` is `attention` when
  the coach should raise it in the first reply.
- A provider that raises is reported as one `attention` line
  ("<id>: unavailable (<error class>)") and the rest still run. A missing
  file or module drops its lines, not the command. A provider that raises
  `ConfigError` (no `config.toml`, or an invalid one) drops its section:
  `instance` and `checks` already report that.
- Output: `data.sections` (in `order`, each `{id, level, lines,
  data}`), `data.instance` (`template`, `uninitialised` or `instance`)
  and `data.today`. Both `profile.md` and `config.toml` mean `instance`;
  exactly one means `uninitialised`. With neither, template identity comes
  from local Git config `coach.workspace = template`, or (when the setting
  is absent) the canonical `joeuk89/claude-strength-coach` GitHub `origin`
  URL (HTTPS or SSH). `coach.workspace = athlete` overrides that origin.
  Only the requested root's own `.git` is consulted, never a parent repo
  or one an inherited `GIT_DIR`, `GIT_COMMON_DIR` or `GIT_WORK_TREE` names.
  Missing/unreadable Git identity and unknown settings default to
  `uninitialised`; bundled tests never establish identity. The README's
  clone/bootstrap step sets the local athlete identity before Claude starts;
  file copies can `git init` and set it explicitly. No network lookup runs.

Providers R-26b ships:

| id | Says |
|---|---|
| `instance` | uninitialised (no `config.toml` or no `profile.md`): "run /setup"; files behind their schema version: "run python3 -m coach migrate run" |
| `checks` | the `coach check` summary and the ids of any `fail` or `warn` |
| `hevy` | cache age against `[hevy] cache_max_age_hours`; skipped when Hevy is disabled |
| `overlay` | the overlay in force today (id, kind, span), else the next to start with its first session; whether it is approved, pushed and verified (a routine counts as verified when its latest `verify` line for the overlay's id and approval hash says so; Hevy off: approved only); the next one or two planned sessions; and the days of the coming week no overlay covers. The coming week is the week holding tomorrow (`[athlete] week_starts`), from today on: the rest of this week, or all of next week on its last day. Invalid overlays are skipped (`checks` names them) |
| `program` | rotation position and whether it is confirmed (R-25's `header_facts`), the confirmation date (`state.json`); the block status line (`coach.block.status_line`, C43) and `light_week` (`state.json`); `attention` when the position is unconfirmed or the light week is `proposed` or `agreed` |
| `checkin` | last check-in, days since, due date, tier and mode (`first`, `weekly`, `deep`, `catch_up`) from R-25's `header_facts` (its `data` is `header_facts`' `checkin`); `attention` when there is no record or the due date is today or past |

Later items add a provider when they own a fact the coach should see at
session start: R-21b (next check-in runs in catch-up mode), R-23a (an
unfinalised proposal draft), R-27 (follow-ups due, aggravated niggles),
R-31 (light week proposed), R-32a (expired research notes), R-33a
(nutrition override expiring), R-42a (source sync age).

The `checkin` and `program` providers read `coach.pages.header_facts`
(C38) and stop computing those facts themselves (R-25 made the switch;
R-26b merged first). `status` passes `as_of` = now.

## C53. Session hooks (R-26b; R-15 owns the `PreToolUse` hook)

`.claude/settings.json` gains two hook entries next to R-15's
`PreToolUse` gate. Both run `cd "$CLAUDE_PROJECT_DIR" && python3 -m coach
hooks <event>` (hooks start in Claude's current directory, which may not
be the instance root), read the hook JSON on stdin, print a hook
response JSON or nothing, and **always exit 0**. Neither needs an allow
rule (hooks run outside the permission layer); `status` gets one. R-15's
`PreToolUse` entry uses the same `cd` form.

- **`hooks sessionstart`** (all session sources: `startup`, `resume`,
  `clear`, `compact`, `fork`; the entry has no matcher). Prints
  `{"hookSpecificOutput": {"hookEventName": "SessionStart",
  "additionalContext": "<text>"}}`, where the text is the `status`
  lines, `attention` first, at most 12 lines and about 1,000
  characters, ending "Detail: python3 -m coach status". The first line
  is "Coach status for <today> (items needing attention first):"; when
  the lines do not fit, the last kept line says how many were dropped.
  It uses the same C52 identity as status; in the template repo it prints
  nothing. On any failure, including
  Python older than 3.11, it prints one line saying the coach scripts
  are unavailable and why. `coach/__main__.py` answers both hook
  commands under an old Python, or when the CLI fails before the hook
  runs (sessionstart: that line; posttooluse: nothing), and exits 0.
- **`hooks posttooluse`** (matcher `Write|Edit`; hand edits only, since
  `coach` commands validate their own output). Reads
  `tool_input.file_path`, makes it relative to the root (it may arrive
  absolute) and looks it up in the path map:

  | Path | Checks run (`check --only`) |
  |---|---|
  | `config.toml` | config, `nutrition_template` |
  | `data/exercises.json` | R-11's library checks, `overlay_library_consistency` |
  | `data/program.json`, `data/state.json` | R-17a's program and state checks |
  | `routine/*.md` | `routine_render_fresh` |
  | `data/overlays/*.json` | R-13's overlay checks, `load_caps`, `dangling_exercise_ids`, `dangling_routine_ids`, `overlay_library_consistency` |
  | `check-ins/*.md` | `overlay_render_fresh`, `bare_hevy_values`, `research_citations` |
  | `profile.md` | `bare_hevy_values`, `research_citations` |
  | `data/hevy/writes.jsonl` | `schema_versions` |
  | `data/activity/*.jsonl`, `data/activity/sync.json`, `.coach/activity/wellness.jsonl` | `activity_records_valid`, `activity_wellness_location` |
  | `data/nutrition/readings.json` | `nutrition_readings` |
  | `data/nutrition/plans/*.json` | `meal_plans`, `meal_plan_render_fresh` |
  | `nutrition/plans/*.md` | `meal_plan_render_fresh` |
  | `nutrition/menu/index.md` | `recipe_index_fresh` |
  | `nutrition/menu/*.md` | `recipe_cards`, `recipe_render_fresh`, `recipe_index_fresh`, `nutrition_template` |
  | `research/local/*.md` | `research_notes`, `research_render_fresh`, `research_citations` |
  | `research/*.md` | `research_notes`, `research_render_fresh` |
  | `this-week.md` | `pages_fresh`, `pages_line_ceiling` |
  | `README.md`, `progress.md` | `pages_fresh` |

  The first matching row wins; `*` matches within one path segment.
  R-26b added the rows after `profile.md`, and R-16's and R-33c's checks
  in the earlier rows, for the items that merged before the map existed.

  Any `fail`: `{"decision": "block", "reason": "<path> failed <id>:
  <message>. Fix the data file or re-render; don't leave it."}`, which
  reaches the coach next to the tool result (the edit has already
  happened; the hook cannot undo it). `warn` only: the same text with
  "has a warning from" for "failed", as
  `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
  "additionalContext": ...}}`. Up to five results are named, then "and N
  more". All pass, an unmapped path, or a hook error:
  nothing on stdout (errors get one `coach:` line on stderr). Only
  checks that read local files are mapped.
- The path map lives in `coach/hooks.py`, built on C13's `--only`, so no
  item edits the check registry. An item that adds a data path in C6 adds
  its row to the map in its own PR. A test asserts every mapped check id
  is registered, and that every C6 path has a row or a stated reason
  in `tests/test_hooks.py` `NOT_MAPPED`; an item that adds checks for an
  unmapped path moves it into the map.

## C54. Profile facts (R-10, R-11 own; R-17a, R-20, R-22, R-23a, R-24, R-30a, R-40a, R-41a, R-41b read)

Rule (ADR-0001): a profile fact that a script reads is config or data;
prose in `profile.md` is only what a human reads.

| Fact | Where | Owner |
|---|---|---|
| current experience, desired weekly sessions, available days, session length | `[athlete] experience`, `desired_sessions`, `available_days`, `session_minutes` (C4) | R-10 |
| optional birth year | `[athlete] birth_year`; `config show` reports explicitly approximate age, or null when unknown | R-10 |
| equipment at the main place and at other places | `[equipment]`, `[equipment.locations.<name>]` (C4) | R-10 |
| benches, bars and supports at each place | `apparatus` in those tables (C4, C5) | R-41b |
| skill exercises the athlete has shown they can do | `[athlete] demonstrated_exercises` (C4) | R-41b |
| which place a session or a one-off week uses | session `location` in `program.json` (C16) and the overlay (C10) | R-17a, R-13 |
| per-session time caps | `[sessions.cap_minutes]` (C19) | R-20 |
| coach-led sessions | `program.external_sessions` (C16) | R-17a |
| injuries and lasting limitations | niggles, `chronic` for a permanent one (C27) | R-27 |
| exercises the athlete cannot or will not do | `avoid` in the instance library (below) | R-11 |
| nutrition strategy | `[nutrition]` (C4, which also lists what stays prose) | R-33a |

Stays prose: the goal narrative, historical training and time off, height,
recovery habits, food preferences and the coach's notes. Setup confirms current
experience independently of lifetime years and records that confirmation in
notes. No automatic layoff-to-level conversion applies. `birth_year` is an
optional positive integer no later than the validation clock's year; absent
stays absent. Config loading accepts an optional `today` (date or timestamp) and checks the
future-year rule only against it, never the wall date; timestamps use the athlete timezone. Command
contexts pass their clock, and the starter, import and adoption paths reuse the command's config. `config show` adds `age`: null
when unknown, otherwise `{years, approximate: true, as_of, note}`. Calendar-year
subtraction is approximate, since actual age may be one less. Calculators
keep their own validated age bounds and require actual age when necessary.

`desired_sessions` is the total weekly target, including coach-led sessions;
setup settles the solo share, calls `starters list --days` with that count,
and passes agreed available weekdays explicitly to `starters draft`. Profile
corrections replace the corresponding config/data fact and prose paragraph
before completion; machine-owned values stay only in structured sources.

**Equipment resolver.** `coach.config.equipment_for(config, location=None)
-> dict` is the one resolver: the main `[equipment]` table with the named
location's keys laid over it. A location that sets `available` and no
`apparatus` gets `apparatus = []`: a bench or bar at the main place says
nothing about another. An unknown location is a config error naming
it. Every reader of equipment calls it: R-24 (caps and
representable loads, C22), R-23a (caps and rounding), R-41b (substitution
in `starters draft`), R-40a, `config suggest`.

**Readers of the other keys.**

- `session_minutes`: the default session cap; `[sessions.cap_minutes]`
  overrides it for a session id (C19). R-20's readers fall back to it.
- `available_days`: R-41b `starters draft` default days, R-30a's
  smaller-schedule proposal, R-22 `shift` rules (a shift never lands on a
  day outside `available_days` when it is non-empty, C37), R-40a.
- `experience`: R-41b starter recommendation, R-40a. It never confirms
  ability: `demonstrated_exercises` does.
- `apparatus`, `demonstrated_exercises`: R-41b substitution
  (`coach.fit`).

**Avoided exercises** (R-11). Instance library entries
(`data/exercises.json`) may carry `"avoid": null | {"reason": "non-empty
text"}`. Commands: `library set-avoid ID --reason TEXT`, `library
set-avoid ID --clear` (W, `--dry-run`), `library list --avoided`.

- R-41b `starters draft` treats an avoided exercise like missing
  equipment: substitute and report. R-41a `program adopt` reports it
  (`data.avoided`) and leaves it in the program (C45).
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
| R-23a (#19) | R-17a, R-20, R-24 | Plugins, proposal pipeline, decisions, load constraints (C23–C26); program v2 and the next state version. Merges after R-26a (it rewires skills R-26a also edits). |
| R-23b (#37) | R-23a | Remaining schemes and schedule rules. |
| R-27 (#23) | R-17a, R-23a | Follow-ups and niggles (C27). |
| R-21a (#17) | R-13, R-14, R-17a, R-20 | Card, records, skeleton (C36). |
| R-21b (#49) | R-21a, R-23a | Catch-up mode and the return brief (C36). |
| R-22 (#18) | R-13, R-14, R-17a, R-23a | Missed-day rules (C37); program and overlay bumps; builds the C23 `fold` filter. |
| R-25 (#21) | R-13, R-17a, R-20, R-21a | Pages and publishing (C38). Parallel with R-21b and R-24. |
| R-32a (#26) | R-10 | Research notes and commands (C28). Parallel with Phase 1. |
| R-32b1 (#44), R-32b2 (#45), R-32b3 (#46) | R-32a; b2 also R-02, b3 also R-06 | Seed notes. Parallel with each other. |
| R-32c (#47) | R-32b1, R-32b2, R-32b3, R-02, R-06 | Coaching principles rewritten against the notes. Before R-26. |
| R-26 (#22) | R-26a, R-20, R-21a, R-21b, R-22, R-23a, R-24, R-25, R-32c; R-27 either order | Skill merge and `CLAUDE.md` shrink; last in Phase 2. `program-week` absorbs the one-off week as modes (normal, midweek, light, minimum, constrained, reshuffle); each skill is a `SKILL.md` of at most 120 body lines plus step files of at most 150. |
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
| R-40b (#58) | R-23a, R-26a, R-30a, R-31 | Run mode (C44). |
| R-40c (#59) | R-13, R-20, R-25, R-26a | Training without Hevy (C46). Can land before Phase 3. |
| R-41a (#29) | R-11, R-12, R-14b, R-17a, R-23a, R-26a | Program drafts, adoption, Hevy import (C45). |
| R-41b (#57) | R-41a, R-23b, R-30b | Starter programs (C45). |
| R-40a (#28) | R-26a, R-41a, R-41b, R-33a, R-40b | Onboarding: config, six-question profile, program pick. Reads R-42a's `[activity]` when merged. |
| R-40d (#60) | R-40a, with R-40b, R-40c, R-41a, R-41b | Human: live onboarding trial. Last of R-40. |
| R-46 (#34) | R-42a, R-43, R-44a, R-32a, R-23a, and a maintainer go-ahead | needs-info. Program tier for running. |
