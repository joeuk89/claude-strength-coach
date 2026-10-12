# Configuration

Every setting in your workspace: `config.toml` table by table, the `.env`
file that holds your Hevy key, the Claude Code settings that decide which
coach commands run without a prompt, and the git setting that marks a
clone as your workspace. Read this when `config validate` names a key, or
when you want to know what a setting does before changing it.

## `config.toml`: who writes it and how it is checked

You or the coach edit `config.toml` by hand. No script ever writes it:
the coach uses its Write tool, with your approval, and scripts only read
the result. The file lives at the workspace root. The template ships
[`config.example.toml`](../../config.example.toml) with every key and its
comment; copy it to `config.toml` and edit it. The template never tracks
`config.toml` itself.

Three rules hold for the whole file:

- **Unknown tables and keys are errors.** A typo stops the scripts
  instead of being ignored. The message names the file, the key and the
  type it expected. This holds inside `[equipment.locations.<name>]` too.
- **Only two keys are required:** `schema_version` and `[athlete] units`.
  Every other key takes the default shown below when left out, with the
  exceptions each table notes.
- **A command that needs config and finds none exits 5** and tells you to
  copy `config.example.toml` to `config.toml`. The `units` commands take
  `--unit` and work without a config.

Check the file with `python3 -m coach config validate`. It exits 5 and
names the file and key when something is wrong, and reports `"valid":
true` otherwise:

```json
{"schema_version": 1, "ok": true, "command": "config validate",
 "data": {"path": "config.toml", "valid": true}, "warnings": []}
```

`python3 -m coach config show` prints the validated config with every
default filled in, so you can see what a key left out resolves to. Add
`--location <name>` to print the equipment at one of your other training
places as well. `python3 -m coach config suggest --unit kg|lb [--gym
commercial|home]` reads no config at all: it proposes `[athlete]` and
`[equipment]` values for a new file and lists what to confirm, such as
the heaviest dumbbell the gym has. `/setup` runs it for you.

The file starts with `schema_version = 1`.

## `[athlete]`

Who trains and when. These are the facts scripts read; everything in your
own words stays in `profile.md`.

| Key | Values | Default | What it does |
|---|---|---|---|
| `units` | `"kg"` or `"lb"` | required | The units for every load. With `"lb"`, set every `[equipment]` weight in lb. |
| `bodyweight_units` | `"kg"` or `"lb"` | same as `units` | Units for weigh-ins and goal weight. |
| `week_starts` | `"monday"` or `"sunday"` | `"monday"` | The first day of your week. |
| `timezone` | IANA name such as `"Europe/London"` | `""` | `""` means this computer's local time. |
| `experience` | `"beginner"`, `"intermediate"`, `"advanced"` | `"intermediate"` | Your current level, confirmed with you. |
| `birth_year` | a whole year | omitted | Omitted means unknown, so a derived age is approximate. |
| `desired_sessions` | 1 to 7 | omitted | Sessions you want each week, separate from the days you are free. |
| `demonstrated_exercises` | list of `"pull_up"`, `"chin_up"`, `"chest_dip"`, `"triceps_dip"`, `"nordic_curl"`, `"hanging_leg_raise"` | `[]` | Skill exercises you have shown you can do for working sets. A swap picks one only once it is listed here. |
| `available_days` | list of `"mon"` to `"sun"` | `[]` | Days you can train. `[]` means not stated. |
| `session_minutes` | minutes | `60` | The default time cap per session. `0` means no cap. |

## `[hevy]`

| Key | Values | Default | What it does |
|---|---|---|---|
| `enabled` | `true` or `false` | `true` | `false` if you do not log in Hevy. See [Training without Hevy](training-without-hevy.md). |
| `cache_max_age_hours` | hours | `24` | `coach check` warns when the Hevy cache is older than this. |

## `[equipment]` and `[equipment.locations.<name>]`

The main place you train. Every weight is in `[athlete] units`. With
`units = "kg"`, each weight left out takes the default shown. With
`units = "lb"`, the increments, `dumbbell_max`, `bar_weight` and
`plates` have no default: set every one in lb, or validation stops.

| Key | Values | Default (kg) | What it does |
|---|---|---|---|
| `available` | list of `"barbell"`, `"ez_bar"`, `"trap_bar"`, `"dumbbell"`, `"kettlebell"`, `"machine"`, `"smith_machine"`, `"cable"`, `"plate"`, `"band"`, `"suspension"`, `"bodyweight"`, `"cardio_machine"`, `"other"` | `[]` | The equipment you have. `[]` assumes every piece. |
| `apparatus` | list of `"flat_bench"`, `"incline_bench"`, `"pull_up_bar"`, `"dip_station"`, `"nordic_anchor"`, `"box"` | `[]` | Benches, bars and supports. `[]` with `available = []` assumes every piece; otherwise an unlisted one is missing. A bench serves as a box. |
| `dumbbells` | list of per-hand weights | `[]` | Your rack. `[]` uses the increment grid instead. |
| `kettlebells` | list of bells | `[]` | `[]` means kettlebell loads are not matched or checked. |
| `dumbbell_increment` | weight | `2.0` | Smallest per-hand dumbbell jump. |
| `dumbbell_max` | weight | `40.0` | Heaviest per-hand dumbbell; prescriptions are capped here. |
| `barbell_increment` | weight | `2.5` | Smallest jump in total bar load. |
| `bar_weight` | weight | `20.0` | The bar's own mass. |
| `smith_base_weight` | weight | none | The Smith machine's known effective unloaded mass. Never inferred. |
| `ez_bar_weight` | weight | none | Your EZ bar's own mass. Without it EZ-bar loads are not checked. |
| `trap_bar_weight` | weight | none | Your trap bar's own mass. Without it trap-bar loads are not checked. |
| `plates` | list of plate sizes | `[25, 20, 15, 10, 5, 2.5, 1.25]` | Plate sizes you have in pairs, one per side, any number of each. A dip belt takes them singly. |
| `machine_increment` | weight | `5.0` | The jump between plates on machine stacks. |
| `cable_increment` | weight | `2.5` | The jump between plates on cable stacks. |

**Other places you train** get one table each, named with lowercase
letters, digits and hyphens: `[equipment.locations.home]`, for example.
Any `[equipment]` key may appear. At that place it replaces the main
table's value, and keys left out keep the main table's value, with one
exception: a place that lists its own `available` and no `apparatus`
has no apparatus.

```toml
[equipment.locations.home]
available = ["dumbbell", "band", "bodyweight"]
dumbbells = [5, 10, 15, 20]
dumbbell_max = 20.0
```

## `[caps]`

Optional load caps by exercise id, in your units: per hand for dumbbell
exercises, total otherwise. For example, `db_bench_press = 30.0`. An
absent table means no caps.

## `[sessions.cap_minutes]`

Optional time caps in minutes by session id, such as `session-a = 45`.
A session left out uses `[athlete] session_minutes`. `0` means no cap.

## `[checkin]`

| Key | Values | Default | What it does |
|---|---|---|---|
| `cadence_days` | days | `7` | A check-in falls due this many days after the last record in `check-ins/`. `python3 -m coach checkin due` reports it. |

## `[coaching]`

| Key | Values | Default | What it does |
|---|---|---|---|
| `mode` | `"coach"` or `"run"` | `"coach"` | In `coach` mode the coach reviews the program's structure and proposes changes. In `run` mode your own program is run as written: loads still progress and every safety check still runs, but structural flags are shown as information and the coach never proposes a restructure or a redesign. |

## `[nutrition]`

The nutrition strategy `/goals` sets with your approval. Leave the table
out, or set `enabled = false`, and nutrition is off: the check-in asks
for one morning weigh-in and `/goals` sets things up. See
[Nutrition](nutrition.md).

| Key | Values | Default | What it does |
|---|---|---|---|
| `enabled` | `true` or `false` | off | Must be stated whenever any other nutrition key is set, so numbers are never silently ignored. |
| `app` | `"macrofactor"` or `"none"` | required when enabled | The nutrition app you log in. |
| `phase` | `"bulk"`, `"cut"`, `"maintain"`, `"recomp"` | required when enabled | The current phase. |
| `target_rate_per_week` | number | required when enabled | Bodyweight units a week; negative means loss. |
| `goal_weight` | weight | omitted | In `[athlete] bodyweight_units`. |
| `kcal_target` | kcal | omitted | Only with `app = "none"`. An error otherwise: no key holds a calorie figure the app owns. |

A table holding only `[nutrition.bank]` leaves nutrition off.

## `[nutrition.protein]`

Required when nutrition is enabled. Grams a day.

| Key | Values | What it does |
|---|---|---|
| `reference_basis` | `"bodyweight"`, `"goal_weight"`, `"fat_free_mass"` | What the per-kg numbers are based on. |
| `reference_mass` | weight | The mass the basis gives. |
| `floor_g` | grams | The minimum commitment now: the number entered in the app. |
| `target_g` | grams | What the coach steers toward. |
| `stretch_g` | grams | An optional higher aim. |
| `floor_since` | date | Readings dated on or after this count toward a raise. |
| `floor_step_g` | grams | How far the floor rises once average protein meets it at two check-ins running, never above the target. |

Rule: `floor_g <= target_g <= stretch_g`.

## `[[nutrition.anchors]]`

The two or three standing protein anchors, one `[[nutrition.anchors]]`
row each.

| Key | Values | What it does |
|---|---|---|
| `name` | text | The anchor's name, such as `"Whey shake"`. |
| `slot` | a meal slot | One of the template's `slots` when a template exists. |
| `days` | list of `"daily"`, `"office"`, `"home"` or `"mon"` to `"sun"` | At least one day. |
| `kcal`, `protein_g` | numbers | The anchor's macros. |
| `recipe` | a card slug | A card in `nutrition/menu/` instead of `kcal` and `protein_g`, never both. |

## `[nutrition.override]`

A dated departure from the app's numbers. At most one, and it must expire
no more than 21 days after it starts.

| Key | Values | What it does |
|---|---|---|
| `start` | date | When it starts. |
| `expires` | date | After `start`, at most 21 days later. |
| `what` | text | What is held, such as `"app protein target held at 120"`. |
| `reason` | text | Why. |
| `exit_condition` | text | What ends it. |
| `renewal` | `0`, `1` or `2` | `0` for a first override, `1` once renewed, `2` renewed twice (flagged). |

## `[nutrition.bank]` and `[nutrition.bank.slot_notes]`

Recipe bank checks for `/recipes`. The defaults apply while the table
stays commented out. The bank works with nutrition disabled.

| Key | Default | What it does |
|---|---|---|
| `aisles` | `["produce", "bakery", "meat-fish", "dairy-eggs", "chilled", "frozen", "tins-jars-dry", "snacks", "drinks", "household"]` | The shopping walk order. Every ingredient names one. |
| `min_protein_per_100kcal` | `{breakfast = 5.0, lunch = 5.0, dinner = 5.0, snack = 0.0}` | Warn when a card for that slot has less protein per 100 kcal. `0` means not checked. A heuristic, not an evidence-based cut-off. A slot left out keeps its default. |
| `macro_sum_warn_pct` | `10` | How far a card's kcal may sit from 4 × protein + 4 × carbs + 9 × fat (grams) before `recipes validate` warns. |
| `macro_sum_fail_pct` | `20` | The same distance before it fails. Both catch typos; they are not coaching numbers. |

`[nutrition.bank.slot_notes]` holds one line per slot, printed under
that slot in `nutrition/menu/index.md`: `breakfast = "must be fast or it
gets skipped"`, for example.

## `[nutrition.template]` and `[[nutrition.template.standing]]`

The standing week `/meal-plan` starts from; each week's plan is only the
exceptions to it. Optional: without it `/meal-plan` has nothing to start
from. `python3 -m coach meals template` prints it.

| Key | Default | What it does |
|---|---|---|
| `slots` | `["breakfast", "lunch", "dinner", "snack"]` | The meal slots in day order. Anchors and cards use these names. |
| `office_days` | `[]` | Weekday ids. `"office"` and `"home"` in a `days` list mean these days and the rest. |
| `staples` | `[]` | Ingredient items, as cards name them, kept in by default. The shopping list moves them to "check you have". |
| `plan_style` | none | `"loose"` (the pool is fixed, the week table is a suggestion) or `"strict"`. Left out, the plan picks loose when a standing row covers dinner. |
| `kcal_tolerance_pct` | `15` | How far a day may sit from the calorie target before the plan flags it. |
| `shopping_issue` | `false` | `true` offers the approved shopping list as a GitHub issue with tick boxes. |

Each `[[nutrition.template.standing]]` row covers one slot on a set of
days with exactly one of `recipe` (a card), `pool` (cards to pick from
each week) or `cover` (someone else decides). A `cover` row also gives
its estimated `kcal` and `protein_g`, and no other row does. Two rows
whose days meet may not fill the same slot on the same day: `daily` is
every day, `office` the office days, `home` the rest. Every standing
row's and anchor's `slot` must be one of `slots`.

```toml
[[nutrition.template.standing]]
days = ["mon", "tue", "wed", "thu"]
slot = "dinner"
cover = "family"
kcal = 700
protein_g = 35
```

## `[activity]`

Runs, rides, conditioning and wellness logged outside the lifting log.
Manual entry is always available; each `[sources.<name>]` table turns on
one source. See [Cardio and activity](cardio-and-activity.md).

| Key | Default | What it does |
|---|---|---|
| `enabled` | `false` | `true` to use the activity, wellness and planned commands. |
| `wellness_in_git` | `false` | `false` keeps wellness in `.coach/activity/` (gitignored); `true` puts it in `data/activity/` (committed). |
| `dedup_window_minutes` | `15` | Records of one kind starting this close are one activity. |
| `precedence` | `["manual", "apple_health", "hevy_conditioning"]` | Which source wins each field. List `"manual"` and every enabled source once. |
| `gap_warn_days` | `3` | `coach check` warns when an enabled source's newest day is older than this. |

## `[sources.hevy_conditioning]`

| Key | Default | What it does |
|---|---|---|
| `enabled` | `true` | Reads Hevy conditioning workouts from the Hevy cache, never the API. Also needs `[hevy] enabled = true`. |

## `[sources.apple_health]`

Apple Health through the Health Auto Export app: JSON, Export Version 2,
Summarize Data on. Files are read in place, never copied.

| Key | Default | What it does |
|---|---|---|
| `enabled` | `false` | `true` reads the folder on every `activity sync`. |
| `path` | `""` | iCloud Drive's AutoExport folder, or any folder holding both automation folders (one exports Health Metrics, one Workouts). On a Mac: `"~/Library/Mobile Documents/com~apple~CloudDocs/AutoExport"`. |
| `drop_source_names` | `["Hevy"]` | Workouts these apps wrote to Apple Health are dropped. With `"Hevy"` listed, a workout with no source that starts within `dedup_window_minutes` of a Hevy workout is dropped too. |

## `[cardio]`

Who owns the run plan, the caps, and the thresholds behind the cardio
flags. Distances are in `distance_unit`; every week is the one
`week_starts` defines. Values marked "a heuristic" are coaching
judgement, not research cut-offs.

| Key | Default | What it does |
|---|---|---|
| `tier` | `"count"` | `"count"`: no plan, planned activities ignored. `"review"`: an outside plan or yours, reconciled against what was logged. `"program"`: the coach writes the plan. |
| `distance_unit` | `"km"` | `"km"` or `"mi"`. |
| `weekly_run_distance` | `0` | Cap; `0` means none. |
| `weekly_run_minutes` | `0` | Cap; `0` means none. |
| `single_run_distance` | `0` | Cap; `0` means none. |
| `single_run_minutes` | `0` | Cap; `0` means none. |
| `weekly_quality` | `2` | Quality activities a week, runs and conditioning together; `0` means no cap. A heuristic. |
| `spike_ratio` | `1.10` | A run longer than this × the longest run in the lookback is a spike. |
| `spike_lookback_days` | `30` | The lookback for spikes. |
| `spike_min_history_days` | `14` | A run is judged only once the logs reach back this far before it. A heuristic. |
| `sleep_short_hours` | `7.0` | A night below this is short. |
| `sleep_debt_nights` | `4` | Short nights of the last 7 that raise sleep debt. A heuristic. |
| `sleep_min_nights` | `4` | Nights with data needed to judge. A heuristic. |
| `reconcile_move_days` | `3` | A logged activity this many days from its plan still matches that planned activity, as moved. A heuristic. |
| `quality_rpe_min` | `7` | A session RPE at or above this makes an activity a quality one. A heuristic. |
| `external_session_minutes` | `60` | A coach-led session counts as this long when you recorded no duration. |
| `external_session_rpe` | `6` | A coach-led session counts at this session RPE when you recorded none. Each recorded value replaces its default. |

## `.env` and the Hevy key

`.env` holds one line, `HEVY_API_KEY=<your key>`, generated in Hevy under
Settings, Developer (Hevy Pro). Copy [`.env.example`](../../.env.example)
to `.env` and paste the key. The file is gitignored and never committed;
the coach never prints it. The `env_untracked` check fails if `.env` is
tracked or exists without being ignored. A missing or rejected key makes
a Hevy command exit 5. See [Hevy](hevy.md).

## `.claude/settings.json`: the allowlist and the hooks

Claude Code reads `.claude/settings.json` from the workspace. It is a
framework file, so `/framework-sync` updates it. Your own local overrides
go in `.claude/settings.local.json`, which is gitignored.

**The permission allowlist** (`permissions.allow`) names every coach
command that may run without a prompt: one rule per command, such as
`Bash(python3 -m coach overlay approve:*)`, plus
`WebFetch(domain:api.hevyapp.com)`. Every read-only command and every
command that writes local files is listed. Three kinds of command are
deliberately left off, so Claude Code asks you first:

- **Hevy writes:** `routines push`, `routines create` and `routines
  retire`. These are the only commands that write to Hevy, and each
  waits for your approval of the coach's brief.
- `hevy record-fixtures` and `plugins test`, which are development
  commands (the latter runs instance code).
- The hook commands, which run outside the permission layer.

`pages publish` is the one command that commits and pushes, and it is
allowlisted because it refuses to run without an approved overlay; see
[Pages and publishing](pages-and-publishing.md).

**The three hooks** run `cd "$CLAUDE_PROJECT_DIR" && python3 -m coach
...` so they find the workspace whatever directory Claude is in:

| Hook | Command | What it does |
|---|---|---|
| `PreToolUse` on `Bash` | `gate pretooluse` | The approval gate. A coach command that writes to Hevy gets a dry run first, and the permission prompt shows what it would write; a push the dry run refuses is denied with the reason. A raw HTTP write to the Hevy API prompts with a warning. In bypass-permissions mode every Hevy write is denied, because nobody would see a prompt. Commands whose effects cannot be read ask for review. Other commands get no opinion, so the allowlist decides. |
| `SessionStart` | `hooks sessionstart` | Puts the session-start status (see [the glossary](../../CONTEXT.md)) in the coach's context: the `coach status` lines, items needing attention first, at most 12 lines, ending "Detail: python3 -m coach status". In the template repo it prints nothing. |
| `PostToolUse` on `Write` or `Edit` | `hooks posttooluse` | After a hand edit of a data file, runs the checks mapped to that path (`config.toml` gets `config` and `nutrition_template`, `data/program.json` the program checks, `this-week.md` the page checks, and so on). A failing check blocks with "Fix the data file or re-render; don't leave it."; a warning is passed on as context; a pass or an unmapped path prints nothing. |

Both `hooks` commands always exit 0 and never write.

## The `coach.workspace` git setting

A clone of the template looks like the template until you tell git
otherwise. Run this in each new clone, before opening Claude:

```bash
git config --local coach.workspace athlete
```

The coach scripts decide whether a folder is the template, an
uninitialised copy or an instance from `config.toml` and `profile.md`
(both present means an instance; one means uninitialised). With neither,
they read this local git setting: `template` marks the template repo, and
`athlete` overrides the template's own GitHub `origin` URL, which would
otherwise mark your clone as the template. In the template, the
session-start hook prints nothing and `/setup` has nothing to set up, so
a clone without the setting starts the wrong way. Git never copies or
commits the setting, so set it in every clone. A copy that is not a
clone needs `git init` first, then the same command. Keep the `tests/`
folder; nothing needs deleting.

## The framework-sync marker

`.claude/framework-sync.json` records the template commit this workspace
last synced to, as `{"template_commit": "<full sha>", "synced_at":
"YYYY-MM-DD"}`. `/framework-sync` writes it and your workspace commits
it; the template never contains one. See [Updating](updating.md).

## Environment variables

`COACH_ROOT` sets the workspace root when you run a command from another
directory; `--root PATH` overrides it. `COACH_NOW` (an ISO timestamp)
fixes "now" and "today", and `COACH_HEVY_FIXTURES` makes the Hevy client
replay recorded fixtures instead of calling the network. The last two
exist for the test suite and for producing example output from the
fixture instances; leave them unset in normal use.
