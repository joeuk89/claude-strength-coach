# Developing the template

This doc is for people changing the template itself: contributors, and
Claude working on the template in a session. It covers how a checkout
knows it is the template, the layout of the `coach` package, the rules
every command, check, plugin and migration follows, where the design
documents live, how skills relate to commands, and how to run the tests.
Athletes using a copy of the template want the [user guide](README.md)
instead.

## Two kinds of checkout

A clone is either the **template** (this repo, where the framework is
developed) or an **instance** (an athlete's private copy, holding their
data). The code is the same; the difference is identity, and it matters
because the session-start hook prints nothing in the template and the
`/setup` prompt in an uninitialised instance.

With neither `profile.md` nor `config.toml` present, `coach status` and
the hook decide from the checkout's own local git config, read by
`coach/workspace.py`:

- `coach.workspace = template` means the template;
- `coach.workspace = athlete` means an instance, whatever the origin;
- with no setting, an `origin` on the canonical
  `joeuk89/claude-strength-coach` GitHub repository (HTTPS or SSH) means
  the template; anything else is `uninitialised`.

Only the requested root's own `.git` is consulted, never a parent repo or
one named by an inherited `GIT_DIR`. There is no network lookup. A fork
or local development copy of the template therefore runs:

```bash
git config --local coach.workspace template
```

Git never commits or clones this setting, so set it in each new clone.
Contract C52 has the full rule. Both `profile.md` and `config.toml`
present means an instance regardless of git.

## Repo map for developers

`docs/design/coach-contract.md` section C1 is the authoritative layout,
with the roadmap item that owns each file. The parts a contributor
touches most:

| Path | What it is |
|---|---|
| `coach/__init__.py`, `coach/__main__.py` | `__version__`, and the Python floor check; both stay at Python 3.6 syntax so an old interpreter reaches the check |
| `coach/cli.py` | the argparse root, command discovery, the envelope and exit codes |
| `coach/errors.py` | `ExitCode` and the exception per code |
| `coach/context.py` | `Context`: root, env, lazy validated config, `now()`, `today()`, `warn()`, `log()` |
| `coach/paths.py` | every well-known path, defined once |
| `coach/commands/` | one module per CLI group; `__init__.py` holds the `@command` decorator and discovery |
| `coach/checks/` | one module per area; `__init__.py` holds the `@check` registry |
| `coach/plugins/` | `base.py` (contexts, proposals, default decay) and one subpackage per kind: `schemes/`, `schedules/`, `transforms/`, `interference/`, `conditioning/` |
| `coach/schemas/*.schema.json` | one file per JSON document type, including `envelope.schema.json` |
| `coach/migrations/<doc>/` | the migration runner's registry: `__init__.py` names the document's files, `NNNN_<slug>.py` are its steps |
| `coach/migrate.py` | the runner itself |
| `coach/starters/<id>.json` | the starter programs |
| `coach/catalogue/exercises.json` | the builtin exercise catalogue |
| `coach/status/` | status providers behind `coach status`; `__init__.py` holds the `@provider` registry |
| `coach/hooks.py` | the SessionStart and PostToolUse hooks and the path-to-checks map |
| `coach/gate.py` | the PreToolUse approval gate: reads a Bash command, dry-runs any Hevy write |
| `coach/units.py` | the only place that doubles, halves, converts kg and lb or rounds a load |
| `config.example.toml` | every config key, commented |
| `research/<id>.md` | template research notes |
| `tests/` | the suite, `support/` helpers and `fixtures/` |

Other registries follow the same pattern and are discovered with
`pkgutil.iter_modules`: `config_tables/`, `flags/`, `history_sources/`,
`checkin_parts/`, `page_parts/`, `weekflags/`, `activity/adapters/`. The
rule that lets parallel work land without conflicts: **add files, never
edit a shared registry**. No change edits `cli.py`, a registry's
`__init__.py` or another item's module.

The package runs on Python 3.11 with the standard library only. A test
parses every module with `ast.parse(..., feature_version=(3, 11))`, and
another rejects any third-party import in `coach/` or `tests/`. Stdlib
APIs newer than 3.11 are banned too.

## The envelope, exit codes and `--dry-run`

Every command prints exactly one JSON object on stdout:
`{"schema_version": 1, "ok": true, "command": "units format", "data":
{}, "warnings": []}`. On failure `ok` is `false`, `data` is absent
(except `coach check`, which keeps its report next to `error`) and
`error` carries `code`, one-sentence `message` and optional `details`
with JSONPaths. stderr carries diagnostics prefixed `coach: `; nothing
parses it. Exit codes: 0 success, 1 validation, 2 usage, 3 refused, 4
network, 5 config, 9 internal. The user guide's [cli.md](guide/cli.md)
has the athlete-facing version; contract C3 is the source.

**Every command that writes accepts `--dry-run`.** The decorator adds the
flag to any command declaring `writes`, `hevy_write` or `git_write`. A
dry run does every read and every check, writes nothing, and exits with
the code the real run would, so a push that would be refused exits 3
under `--dry-run` too. `tests/test_cli.py` asserts every writing command
has the flag; each command's own tests assert its dry run writes nothing.

## Commands

Commands are declared, not registered:

```python
from coach.commands import arg, command

@command("units format", help="...", args=(arg("--mode", required=True), ...),
         writes=False, hevy_write=False, network=False, git_write=False, envelope=True)
def units_format(args, ctx) -> dict:
    ...
```

The name is one or two lowercase words: `"<group> <command>"`, or one
word for a top-level command (`check`, `version`). The function takes
`(args, ctx)` and returns the envelope's `data`. The metadata flags are
what the permission layer reads:

| Flag | Meaning |
|---|---|
| `writes` | touches local files |
| `hevy_write` | sends a non-GET request to Hevy (requires `network=True`) |
| `network` | calls Hevy at all |
| `git_write` | commits or pushes |
| `envelope` | `False` for a Claude Code hook command, which prints the dict it returns as the hook response, or nothing for `None`, and exits 0 |

`discover()` imports every module under `coach/commands/` and collects
functions carrying the decorator; a name declared twice is an error.

### The allowlist

`.claude/settings.json` lists `permissions.allow` rules, one exact prefix
per command: `Bash(python3 -m coach <group> <command>:*)`, never a group
or broader prefix. `tests/test_gate.py` enforces it in both directions:
every rule names a registered command with `hevy_write` false and
`git_write` false (`pages publish` is the one exception, because it
refuses to run without an approved overlay), no rule matches a Hevy
write, and **every eligible registered command has its exact rule**, so
a new command cannot be forgotten. Hooks (`envelope=False`), `hevy
record-fixtures` and `plugins test` (it runs instance code) stay off the
list on purpose. Hevy writes stay behind the gate in `coach/gate.py`,
which dry-runs them and puts the summary on the permission prompt.

### Adding a command

1. Add the function to the group's module under `coach/commands/`, or a
   new module for a new group. Declare the flags honestly.
2. If it writes, make the dry run real: every read and check, nothing
   written, same exit code.
3. Add its allow rule to `.claude/settings.json` unless it writes to Hevy
   or git, and say so in the PR.
4. Add it to the command inventory in contract C2.
5. Test it with `run_cli` from `tests/support/` against a fixture
   instance copied to a temp directory.
6. If it replaces a step a skill does by hand, rewrite that step (see
   [Skills](#skills)).

## Checks

A check is a function on a `Context` returning a list of `Result`:

```python
from coach.checks import Result, check

@check(id="overlay_arithmetic", owner="R-13")
def overlay_arithmetic(ctx) -> list[Result]:
    ...   # Result(status="pass"|"warn"|"fail"|"skip", message=str, path=str|None)
```

The registry runs each check and shapes the outcome: a `ConfigError`
becomes one `skip` (the check needed `ctx.config` and there is none, or
it is invalid), any other exception one `fail` with the traceback on
stderr, an empty list one `pass`. Every failing result names the file,
the JSONPath or line, and the offending value. `coach check` exits 1 on
any `fail`; `--only` runs a subset; `--list` prints the ids.

`python3 -m coach --root tests/fixtures/instances/valid check --list`
prints the registered checks (63 at the time of writing). Each ships
with a passing and a failing fixture instance under
`tests/fixtures/instances/`.

To add a check: add the function to the right module under
`coach/checks/` (or a new module), add the fixtures, and if it reads a
file a hand edit could break, add the file's row to `PATH_MAP` in
`coach/hooks.py` so the PostToolUse hook runs it. `tests/test_hooks.py`
asserts every mapped id is registered and every instance path in
contract C6 is either mapped or listed in `NOT_MAPPED` with a reason.

## Plugins

A plugin is one pure Python module. The kinds are subpackages of
`coach/plugins/`, each declaring in its `__init__.py` the `KIND`, the
functions its plugins must define (`REQUIRED`), the optional ones and
whether it is `STATEFUL`:

| Kind | Must define | Purpose |
|---|---|---|
| `schemes` | `propose`, `decay` | turn a slot's exposures into its next prescription (stateful) |
| `schedules` | `plan`, `positions` | put sessions on dates and track the rotation |
| `transforms` | `apply` | reshape a proposed week: light, return, standard deload, a scheme's own deload |
| `interference` | `evaluate` | judge the week's bouts against lifting and return flags; never move anything |
| `conditioning` | `propose`, `decay` | progress a conditioning session on its session RPE (stateful) |

Every module carries `API = 1`, `KIND`, `NAME` (equal to the file stem),
`SUMMARY` (one sentence), `PARAMS = {"schema", "defaults"}`, `FLAGS`
(instance plugins only) and `CITES` (template research claim refs).
Stateful kinds add `STATE = {"schema", "initial"}`. `coach/plugins/base.py`
defines what a plugin works with: `SchemeContext`, `ScheduleContext`,
`Proposal`, `SetSpec`, `SchedulePlan` and `default_decay`.

Two rules shape every plugin. **Purity:** no I/O, no imports beyond
`coach.plugins.base`, the pure e1RM functions `coach.stats.e1rm`,
`load_for` and `implied_rpe`, and `math`, `dataclasses`, `typing`,
`datetime`. **Units:** every load a plugin sees or returns is the coaching
number in athlete units; the core applies decay, the transform,
constraints, caps, rounding and only then builds the load object. A
plugin therefore cannot double a load, and an AST scan rejects any
module that multiplies or divides by 2 or 0.5 or holds a kg/lb factor.

`python3 -m coach plugins validate` enforces the contract on framework
and instance plugins alike:

- **shape:** the module keys above, `API` matching, `KIND` matching its
  package, `NAME` matching the file, the required functions present;
- **schemas:** `PARAMS` and `STATE` schemas in the supported JSON Schema
  subset, with `initial` validating against its schema;
- **purity:** the AST scan for I/O, forbidden imports, private access,
  `getattr` and friends;
- **no x2:** the doubling and unit-factor scan;
- **instance names:** an instance plugin's name starts `custom_` and does
  not collide with a framework plugin; its flag codes start `custom_`;
- **tests:** every instance plugin ships `plugins/tests/test_<name>.py`.

An instance plugin that fails the scan is never imported. The
`plugins_valid` check runs the same validation inside `coach check`.

To add a framework plugin: add the module under its kind, cite template
claims in `CITES`, write its tests, and run `plugins validate`. The
purity scan runs over `coach/plugins/**` in `tests/test_plugins.py` as
well.

## Migrations

Every JSON document the package owns carries an integer
`schema_version`, and validators are strict (`additionalProperties:
false`), so any change to a document's shape bumps its version. The
runner in `coach/migrate.py` finds the documents it owns through
`coach/migrations/<doc>/`:

```python
# coach/migrations/blocks/__init__.py
FILES = ("data/blocks.json",)

# coach/migrations/blocks/0002_sleep_override.py
DOC = "blocks"
FROM = 2
TO = 3          # always FROM + 1

def migrate(doc):
    ...
    return doc
```

A step may also define `notes(before, after)` for the run's report and
`creates(before, after)` for documents it brings into being. The target
version is the `schema_version` const in the document's schema file; a
step past it, two steps from one version, or a badly named step file is
a `RegistryError`, a framework bug. `migrate run` backs every file up
under `.coach/backups/<UTC timestamp>/`, migrates, validates, writes only
when everything validates, restores from the backup on a failed write,
and stages with `git add` without committing.

To add a migration: bump the const in `coach/schemas/<doc>.schema.json`,
add `NNNN_<slug>.py` with `FROM` at the old version, and update the
fixtures that carry the document. The `schema-newer` and `schema-older`
fixtures show the two messages a reader prints. A document the runner
does not own (append-only logs, caches) declares its paths with
`x-coach-paths` in its schema instead; see contract C7.

## Starters

`coach/starters/<id>.json` holds the starter programs an athlete can
draft from. Each has `schema_version`, `id`, `title`, `summary`, `level`,
`days`, `minutes_per_session`, `equipment_required`, `cites` and the
`program` itself, validated against `starter.schema.json`. `starters
list`, `starters show` and `starters draft` read them. A new starter is a
new file, and `tests/test_starters.py` already runs every starter
through adopt, validate, render and a first proposed week, checks its
claims are current template claims and that each session fits its
stated minutes; update the count it expects.

## Design documents

| Document | Role |
|---|---|
| `CONTEXT.md` | the glossary: the vocabulary every file uses, each term with the synonyms to avoid |
| `docs/adr/` | the decisions behind the design: structured data rendered to markdown (0001), scripts propose and the coach decides with a mechanical gate (0002), no unofficial Garmin or Strava access (0003) |
| `docs/design/coach-contract.md` | the interface contract, sections C1 to C55 |
| `docs/roadmap/2026-10-11-system-review.md` | the review that produced the plan: what was found, the decisions, the items by phase. History, not a to-do list |

The contract is the interface every item builds against, so items built
separately fit together. Anything not defined in it is internal to the
item that builds it. **Changing anything in it is a change to that file,
made in the PR that needs it and called out in the PR description.**
Section numbers are fixed because issue briefs cite them; C47 is unused
and stays so. The "Build order and ownership" table at its end records
which item owns what and what each depends on.

`docs/agents/` configures the dev-tooling skills: the issue tracker is
GitHub issues on `joeuk89/claude-strength-coach`, worked with the `gh`
CLI (`docs/agents/issue-tracker.md`); the triage labels are
`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human` and
`wontfix` (`docs/agents/triage-labels.md`); and the domain docs rule is
one `CONTEXT.md` and one `docs/adr/` at the root
(`docs/agents/domain.md`). Instances ignore this folder.

## Skills

The coaching flows are Claude Code skills: `.claude/skills/<name>/SKILL.md`
plus sibling step files read on demand. `SKILL.md` is capped at 120 body
lines and each step file at 150; `tests/test_skill_rules.py` checks the
caps, the nine skill names, that `SKILL.md` points at every step file,
the approval sentence and its variants, that no skill carries an e1RM
formula or a record template, and that `CLAUDE.md` states the script
rule next to the exit codes.

**Skills follow the commands.** A change whose command replaces a step a
skill does by hand rewrites that step in the same PR: the skill names
the command and says what to do with its output, and changes nothing
else. `tests/support/skills.py` reads a skill folder in reading order
(`skill_text`, `step_text`, `all_skills`, `body_lines`), and many tests
assert skill text directly: that a step names a command, that a
threshold matches `CLAUDE.md`, that the framework-sync skill excludes
`tests/**` and `README.md`. Expect a skill edit to fail a test until the
test is updated with it, and vice versa.

## Tests

The suite is plain `unittest`, stdlib only. Run everything from the repo
root:

```bash
python3 -m unittest discover -s tests -t .
```

One module, verbose:

```bash
python3 -m unittest tests.test_units -v
```

That module runs 32 tests in well under a second. The whole suite takes
about 11 to 12 minutes.

### Fixtures

- `tests/fixtures/instances/<name>/` are whole workspaces. `valid/` is
  the shared one; contract C14 fixes its ids, loads and dates so fixtures
  from parallel items line up, and lists every other instance with what
  it holds. Tests copy an instance to a temp directory before writing,
  and never write to the fixture itself.
- `tests/fixtures/hevy/<set>/` are Hevy fixture sets: one file per
  collection (`workouts.json`, `routines.json`, ...), each marked
  `"x-synthetic": true` or `"x-anonymised": true`. Several sets layer:
  for each file, the last directory wins.
- `COACH_NOW` fixes "now" and "today" to an ISO timestamp; the valid
  instance expects `2026-10-11T18:00:00Z`.
- `COACH_HEVY_FIXTURES` makes the Hevy client replay fixture sets
  (directories joined with `os.pathsep`) instead of calling the network.
- `hevy record-fixtures --out DIR` records anonymised fixtures from a real
  account (GET only, needs a real key); `activity anonymise --source NAME
  --file PATH --out DIR` turns a real activity export into a committable
  fixture. Both shift dates by whole weeks and replace ids and names;
  contract C15 lists the anonymiser's rules.

### Helpers in `tests/support/`

| Helper | Use |
|---|---|
| `run_cli(argv, env)` | runs `coach.cli.main` in-process, returns `(code, envelope, stderr)` |
| `run_module(argv)` | runs `python -m coach` in a subprocess |
| `TempInstance`, `MINIMAL_CONFIG` | a temp root with an optional `config.toml` |
| `fake_hevy.FakeHevy`, `FakeClock` | a stateful fake Hevy seeded from a fixture set; patch `coach.hevy.transport.from_env` to use it |
| `history.HistoryCase` | a temp copy of an instance with a Hevy cache written from a fixture set |
| `activity.write_hevy_cache`, `map_routines` | a cache from a fixture set; routine-to-session mappings |
| `config_edit.set_key`, `apply` | edit `config.toml` text the way `/setup` does |
| `skills.skill_text` and friends | read a skill folder |
| `git.git` | run git in a fixture repo with a clean config |
| `templates.cache_catalogue_templates` | a template cache resolving every catalogue exercise |

### Rules the suite enforces on the repo

- **Instance namespaces** (`tests/test_repo_layout.py`): the template
  never tracks `config.toml`, `data/**`, `routine/**`, `profile.md`,
  `check-ins/**`, `nutrition/**`, `plugins/**`, `research/local/**`,
  `this-week.md`, `progress.md`, `this-week-sheets.md`, `.coach/**` or
  `.env` (the two `.gitkeep` files excepted), so `/framework-sync` can
  never write an athlete's files. An item that adds a namespace extends
  the list.
- **Package rules** (`tests/test_package_rules.py`): Python 3.11 syntax,
  stdlib only, and no doubling, halving or unit conversion outside
  `coach/units.py`.
- **The gate and allowlist** (`tests/test_gate.py`): see above.
- **Hooks** (`tests/test_hooks.py`): every mapped check exists; every
  instance path is mapped or excused.

## Writing conventions

Plain words, active voice, one idea per sentence. Prose wraps at about
78 columns. Use the vocabulary in `CONTEXT.md` exactly and avoid the
synonyms it lists; a term that is not there is either a sign you are
inventing language or a gap to add. Framework files cite research claims
by id (`rn:<note>.<n>`) and never cite sources directly.

## What never goes in the template

- `.env`, or any Hevy key.
- Instance data: anything in the namespaces above. Test fixtures live
  under `tests/fixtures/` and never contain a file named `.env`.
- A `.claude/framework-sync.json` marker. Instances commit one; the
  template never has one.

## How instances get updates, and where docs live

An instance pulls the framework with `/framework-sync`: every file the
template tracks except `docs/**`, `tests/**`, `README.md` and
`.gitkeep`, in one commit, with data migrations run first. The user
guide's [updating.md](guide/updating.md) describes the flow from the
athlete's side.

User docs live in `docs/guide/` and, like everything under `docs/`, are
not synced. Athletes read them on GitHub in the template repo, so a doc
change ships the moment it merges, and a doc must describe the current
`main`.
