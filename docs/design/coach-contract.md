# `coach` package contract

The interfaces every Phase 1 roadmap item (R-10 to R-17) builds against, so
items built separately fit together. Agreed in triage on 2026-10-11. See
`docs/roadmap/2026-10-11-system-review.md` for the items and `docs/adr/` for
the decisions behind them.

Anything not defined here is internal to the item that builds it. Changing
anything here is a change to this file, made in the PR that needs it and
called out in its description.

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
  config.py                  # config.toml loader and validator                          (R-10)
  dates.py                   # ISO dates, weeks, spans                                   (R-10)
  units.py                   # the ONLY place for x2, /2, kg<->lb, rounding, load formatting (R-10)
  checks/__init__.py         # check registry + auto-discovery                           (R-10)
  checks/<item>.py           # one module per item that adds checks
  commands/<group>.py        # one module per CLI group, auto-discovered
  schemas/<name>.schema.json # one file per JSON document type
  catalogue/exercises.json   # builtin exercise catalogue                                (R-11)
  library.py                                                                             (R-11)
  hevy/{client,transport,cache,ratelimit,anonymise,envfile}.py                           (R-12)
  overlay.py, render.py                                                                  (R-13)
  routines.py                # diff, push, verify, retire                                (R-14)
  gate.py                    # PreToolUse hook logic                                     (R-15)
  program.py, state.py, migrate.py, migrations/<doc>/NNNN_<slug>.py                      (R-17a)
config.example.toml          # framework: every Phase 1 key, commented                   (R-10)
tests/                       # template only, never synced
  test_<module>.py
  support/                   # shared test helpers (fake Hevy lives here, R-12)
  fixtures/instances/<name>/ # minimal instance trees
  fixtures/hevy/             # recorded or synthetic API responses
```

Rules that stop parallel agents colliding:

- **Add files; don't edit shared registries.** CLI groups and checks are
  discovered with `pkgutil.iter_modules` over `coach/commands/` and
  `coach/checks/`. No item edits `cli.py`, `checks/__init__.py` or another
  item's module.
- **R-10 owns these shared files and fills them for all of Phase 1 up
  front:** `paths.py` (all paths in C6), `config.example.toml` (all keys in
  C4), `.gitignore` (C6), `errors.py`. A later item that needs a new path or
  key adds it in its own PR and says so in the PR description; it never
  renames an existing one.
- Code runs on Python 3.11. Builders may run newer Pythons, so R-10 adds a test that parses every `coach/**/*.py` with
  `ast.parse(src, feature_version=(3, 11))`. Also banned: stdlib APIs added
  after 3.11 (`itertools.batched`, `pathlib.Path.walk`, `datetime` 3.12
  additions). No third-party imports anywhere, including tests.

## C2. CLI shape

- Invocation: `python3 -m coach [--root PATH] <group> <command> [options]`,
  run from the instance root. Root resolution: `--root`, then env
  `COACH_ROOT`, then the current directory.
- Two levels only: group, then command.
- Every command module declares, per command: `writes` (touches local
  files), `hevy_write` (sends a non-GET request to Hevy), `network` (calls
  Hevy at all). R-15's allowlist test reads this metadata.
- **Every command with `writes` or `hevy_write` accepts `--dry-run`.** Dry
  run does every read and every check, writes nothing, and returns what it
  would have done. It exits with the code the real run would have (so a
  push that would be refused exits 3 under `--dry-run` too). A test in R-10
  asserts every writing command accepts the flag; each item's tests assert
  their dry run writes nothing.
- Test-only environment overrides: `COACH_NOW` (ISO timestamp, fixes "now"
  and "today") and `COACH_HEVY_FIXTURES` (directory; makes the Hevy client
  replay fixtures instead of calling the network, R-12).

Phase 1 command inventory (owner in brackets). Read-only unless marked W
(writes local files) or H (writes to Hevy).

| Command | Owner | |
|---|---|---|
| `units format`, `units convert`, `units round` | R-10 | |
| `dates week`, `dates span` | R-10 | |
| `config show`, `config validate` | R-10 | |
| `check [--only ids] [--list]` | R-10 (framework), each item adds checks | |
| `version` | R-10 | |
| `library list`, `library show`, `library search`, `library validate` | R-11 | |
| `library seed`, `library confirm`, `library set-mode` | R-11 | W |
| `hevy status` | R-12 | |
| `hevy pull [--full]` | R-12 | W (gitignored cache only) |
| `hevy record-fixtures --out DIR` | R-12 | W (GET only, needs a real key) |
| `overlay list`, `overlay current`, `overlay validate`, `overlay notes` | R-13 | |
| `overlay build --input FILE`, `overlay render [--into FILE]`, `overlay approve ID` | R-13 | W |
| `routines diff --overlay ID`, `routines verify --overlay ID` | R-14 | |
| `routines push --overlay ID`, `routines retire --overlay ID` | R-14 | H |
| `gate pretooluse` | R-15 | |
| `program show`, `program validate`, `state show`, `migrate status` | R-17a | |
| `program render`, `migrate run` | R-17a | W |

## C3. Output envelope and exit codes

stdout carries exactly one JSON object per run, UTF-8, followed by a newline:

```json
{"schema_version": 1, "ok": true, "command": "units format",
 "data": {}, "warnings": []}
```

On failure `ok` is false, `data` is absent, and:

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
| 4 | `network` | Hevy unreachable or erroring after retries | timeout, 5xx, 429 after back-off |
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
  expected type.
- Commands that need config and find none exit 5 with "copy
  config.example.toml to config.toml". `units` commands take `--unit` and
  work without config.

Phase 1 keys (R-10 defines all of them; later items read them):

```toml
schema_version = 1

[athlete]
units = "kg"              # "kg" | "lb" — loads
bodyweight_units = "kg"   # "kg" | "lb"
week_starts = "monday"    # "monday" | "sunday"
timezone = ""             # IANA name; empty = system local time

[hevy]
enabled = true
cache_max_age_hours = 24  # coach check warns past this

[equipment]               # all in athlete units
dumbbell_increment = 2.0  # per hand
dumbbell_max = 40.0       # per hand; a cap
barbell_increment = 2.5   # smallest total jump
bar_weight = 20.0
plates = [25, 20, 15, 10, 5, 2.5, 1.25]   # per side, pairs available
machine_increment = 5.0
cable_increment = 2.5

[caps]                    # optional: library exercise id = max load, athlete units
                          # (per hand for per-hand modes, total otherwise)
```

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
- `format_load` never prints a unit; table headers and surrounding text
  carry it. It prints at most two decimals and strips trailing zeros
  (`22.5`, `1.25`, `25`).
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
| `data/exercises.json` | instance library: overrides, custom entries, confirmed load modes | committed | R-11 |
| `data/overlays/<id>.json` | one overlay per programming pass | committed | R-13 |
| `data/hevy/writes.jsonl` | append-only audit of every Hevy write and verification | committed | R-12 (writes), R-14 (verify, retire) |
| `data/program.json`, `data/state.json` | program and state | committed | R-17a |
| `routine/*.md` | rendered session pages | committed, never hand-edited | R-17a |
| `.coach/cache/hevy/` | raw Hevy cache, rebuildable with `hevy pull --full` | **gitignored** | R-12 |
| `.coach/backups/<UTC timestamp>/` | pre-migration copies | gitignored | R-17a |

- `.gitignore` gains `/.coach/`, `__pycache__/` and `*.pyc` (R-10). The
  `.coach` pattern is **root-anchored** so test fixtures under
  `tests/fixtures/instances/*/.coach/` stay tracked. Fixtures never contain
  a file named `.env` (the existing pattern ignores it at any depth); tests
  that need one create it in a temp directory.
- **Instance namespaces** that the template never tracks, so
  `/framework-sync` can never write them: `config.toml`, `data/**`,
  `routine/**`, `profile.md`, `check-ins/**` (except `.gitkeep`),
  `nutrition/**` (except `.gitkeep`), `plugins/**`, `.coach/**`, `.env`.
  R-10 adds a test that fails if `git ls-files` in the template lists any of
  them.
- **Sync exclusions**: R-10 edits `.claude/skills/framework-sync/SKILL.md`
  so the framework set excludes `tests/**` as well as `docs/**` and
  `.gitkeep`. Its tests check the skill text names `tests/**`.

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
- Identifier patterns: library exercise ids `^[a-z0-9_]+$` (custom ones
  start `custom_`); session ids `^[a-z0-9-]+$`; overlay ids
  `^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`.

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

## C9. Audit log line (`data/hevy/writes.jsonl`)

```json
{"schema_version":1,"at":ts,"kind":"write","method":"PUT","path":"/v1/routines/<id>",
 "status":200,"routine_id":"<id>","overlay_id":"<id>|null","overlay_hash":"sha256:..|null",
 "request_body":{...},"request_sha256":"sha256:.."}
{"schema_version":1,"at":ts,"kind":"verify","routine_id":"<id>","overlay_id":"<id>",
 "overlay_hash":"sha256:..","verified":true,"diff":[]}
```

`kind` is `write`, `verify` or `retire`. The client appends a `write` line
for every non-GET request, success or failure. The API key never appears.

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
    {"code": "stale_prescription", "severity": "warn", "session_id": "mon-lower",
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
  them (Hevy rejects nulls).
- `override`: null or `{"reason": "non-empty", "proposed_sets": [...]}`.
- `approval`: null or `{"approved_at": ts, "hash": "sha256:..."}`. The hash
  is the canonical hash (C7) of the whole document with `approval`
  removed. Any edit after approval, including resolving a flag, breaks it.
- Flag `severity`: `info`, `warn`, `block`. Push refuses any `block` flag
  with `resolved: false`.
- **Overlay in force** for a date D: of the overlays whose span contains D
  and which have a session dated D, the one with the latest `created_at`.
  `supersedes` is an audit link; resolution does not depend on it.
- File name is `data/overlays/<id>.json`; id is `<span.start>-<kind>`,
  with `-2`, `-3` on collision.

## C11. Rendered markdown markers (R-13, R-16, R-17a)

- A whole rendered file starts with
  `<!-- generated by coach from <source path>; edit the data, then run: python3 -m coach <command> -->`.
- A rendered region inside a prose file (the check-in's "The week ahead")
  sits between `<!-- coach:begin <kind> <id> -->` and
  `<!-- coach:end <kind> <id> -->`.
- Freshness means the bytes equal a fresh render. Each renderer exposes
  `render_<kind>(id) -> str` so `coach check` can compare.

## C12. Hevy routine note (R-13 renders, R-14 writes)

```
Wk of 12 Oct: <week focus>        (first exercise of each routine only)
Target: 3×8–10 @ 25/hand (Hevy: 50) @ RPE 8
Focus: <exercise focus, only when set>
Cues: <cues>
```

- Warm-up sets are left out of the Target line. Consecutive working sets
  with equal reps or range, load and RPE collapse to `N×reps`; groups join
  with ` + `.
- The Target line is absolute. It never carries `target_note` or `change`:
  relative wording ("add 2.5 from last week") goes stale in the app. Those
  fields appear in the brief and the check-in only.
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
| overlay | `2026-10-12-weekly`, span 2026-10-12 to 2026-10-18; squat 100, DB bench 25/hand (Hevy: 50), row 30 (Hevy: 30), pull-up BW |
| `COACH_NOW` | `2026-10-11T18:00:00Z` |

## C15. Hevy fixtures and anonymisation (R-12)

- Synthetic fixtures (hand-written from the documented API shape) are
  marked `"x-synthetic": true` at the top of the fixture file and are what
  every agent uses. The API shape comes from
  `https://api.hevyapp.com/docs/swagger-ui-init.js`, which needs no key.
- Recorded fixtures come from `hevy record-fixtures`, run by a human with a
  real key, GET requests only. The anonymiser:
  - replaces routine, workout, folder and custom-template ids with
    deterministic fake UUIDs (salted hash, so joins survive);
  - keeps built-in exercise template ids and titles (public catalogue);
  - replaces workout titles, routine titles and custom exercise titles
    with `Workout N`, `Routine N`, `Custom exercise N`;
  - replaces every `description` and `notes` with `note N` (non-empty
    stays non-empty, empty stays empty);
  - shifts every timestamp by a whole number of weeks (keeps weekdays and
    gaps);
  - keeps sets, reps, weights and RPE; replaces body-measurement values
    with synthetic ones; drops `/v1/user/info` entirely;
  - asserts the output contains none of: the API key, any original id, any
    original title or note text.

## C16. Program and state documents (R-17a owns; R-22, R-23, R-31 read)

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
- `sets` is a list of set groups. Each group has `count`, `type` (as in
  C10), exactly one of `reps` or `rep_range`, and optional `rpe`,
  `duration_seconds`, `distance_meters`. A plain 3×5 is one group.
- `start_load` is in athlete units and per hand for per-hand modes, like
  every load a human writes; code builds load objects from it (C5).
- `schedule.rule`: `fixed_weekdays`, `alternating_external_anchor`,
  `next_in_sequence`, `explicit_calendar`.
- Scheme, schedule and deload names are checked against a fixed list; their
  `params` are free-form objects in v1. R-23 adds a schema per plugin and
  bumps the version.
- Missed-day rules are free text in v1; R-22 makes them executable.

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
- `one_off`: null or `{"overlay_id": id, "span": span}`.
- `hevy.routines` replaces `routine/hevy-map.json`.

---

## Build order and ownership

| Item | Depends on | Notes |
|---|---|---|
| R-10 | nothing | Owns the shared files in C1, the check registry (C13) and the Python and config checks. |
| R-11, R-12, R-13 | R-10 | Can be built in parallel. R-13 owns `overlay approve` and the approval hash (C10). |
| R-14 | R-12, R-13 | Enforces approval; does not build it. |
| R-17a | R-11 | Program and state schemas, renderer, migration runner. |
| R-15 | R-14 | The permission layer only: allowlist and `PreToolUse` hook. |
| R-16 | R-11, R-12, R-13, R-14 | Cross-cutting checks only; each item registers its own checks. |
| R-17b | R-17a, R-14 | Bootstrap migration of a real instance, run with the athlete. |
