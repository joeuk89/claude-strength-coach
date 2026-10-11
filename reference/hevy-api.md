# Hevy API cheatsheet

The `coach` commands do every Hevy read and write: `hevy pull` fills the
local cache, and `routines diff`, `push`, `verify`, `create` and
`retire` write routines from an approved overlay, logging each write in
`data/hevy/writes.jsonl`. These notes describe the API under them, for
debugging and for the [Manual fallback](#manual-fallback). Full docs:
https://api.hevyapp.com/docs/ (spec is embedded in
`https://api.hevyapp.com/docs/swagger-ui-init.js` — the docs page itself is
JS-rendered, so fetch that file if you need schema detail).

## Auth

- Requires Hevy Pro. Key lives in `.env` at the repo root as
  `HEVY_API_KEY` — never print it, never commit it (`.gitignore` covers it).
- In a **Claude Code cloud session** there is no `.env` (it isn't in the
  clone). The key comes from the cloud environment's environment variables
  instead — see [Cloud sessions](#cloud-sessions) below.
- Every call: header `api-key: $HEVY_API_KEY`, base URL `https://api.hevyapp.com`.

```bash
# Loads .env when it exists (local); otherwise the var is already set (cloud).
[ -f .env ] && { set -a; . ./.env; set +a; }
curl -s -H "api-key: $HEVY_API_KEY" "https://api.hevyapp.com/v1/workouts/count"
```

### Cloud sessions

To use Hevy from Claude Code on the web, configure the cloud environment at
[claude.ai/code](https://claude.ai/code) — the cloud icon in the row above
the message box, then the settings gear on the environment:

- **Environment variables**: add `HEVY_API_KEY=<key>`. Values are readable by
  anyone using that environment, so keep it a personal environment.
- **Network access**: set to **Custom**, add `api.hevyapp.com`, and tick
  *"Also include default list of common package managers"*. The default
  **Trusted** level does not allow `api.hevyapp.com`, so every call fails
  without this.

Changes apply to sessions started afterwards, not ones already running.

Quote URLs with `?` in them — zsh globs them otherwise.

## Endpoints

| Endpoint | What it returns | Paging |
|---|---|---|
| `GET /v1/workouts?page=&pageSize=` | Logged workouts, newest first: workout-level `description` (the athlete's end-of-workout notes), exercises with `notes` (per-exercise notes typed mid-session) → sets with `weight_kg`, `reps`, `rpe`, `type` | max 10/page |
| `GET /v1/workouts/count` | Total workout count | — |
| `GET /v1/workouts/events?since=<ISO8601>&page=&pageSize=` | Workout updates/deletes since a date — use for "what's new since last check-in" | max 10/page |
| `GET /v1/workouts/{id}` · `PUT /v1/workouts/{id}` | One workout — GET, or replace it. PUT is how a mis-logged past session gets repaired; it replaces the whole workout, so GET first, edit the JSON, PUT it back. Confirm with the athlete before any write | — |
| `GET /v1/routines?page=&pageSize=` | Routine templates: `updated_at` (ISO 8601, UTC — what the STALE check compares), exercises with `rest_seconds`, `notes`, `supersets_id`, sets with `rep_range {start,end}` / `reps` / `weight_kg` | max 10/page |
| `POST /v1/routines` · `PUT /v1/routines/{id}` | Create / replace a routine (PUT replaces the whole exercise list) | — |
| `GET /v1/routine_folders` | Routine folders (id + title) | max 10/page |
| `POST /v1/routine_folders` | Create a routine folder (body `{"routine_folder": {"title": "…"}}`). `POST /v1/routines` takes a `folder_id` to file the new routine | — |
| `GET /v1/exercise_templates?page=&pageSize=` | Exercise catalogue — needed to get `exercise_template_id` when adding an exercise to a routine | max 100/page |
| `POST /v1/exercise_templates` | Create a custom exercise (`title`, `exercise_type` e.g. `duration`/`weight_reps`, `equipment_category`, `muscle_group`). Returns the new template ID as plain text | — |
| `GET /v1/exercise_history/{exerciseTemplateId}` | All logged sets of one exercise over time — good for progression analysis | — |
| `GET /v1/body_measurements` | Bodyweight etc. | max 10/page |
| `GET /v1/user/info` | Account sanity check | — |

## Dumbbell loads — two numbers, never one

Hevy stores a dumbbell set's weight as the **combined total lifted per rep**,
not the weight of one dumbbell. So there are always two numbers, and every
skill that writes or reads a load must keep them straight:

| | What it means | Example |
|---|---|---|
| **Per hand** | What the athlete physically sets each dumbbell to — the coaching number | `25/hand` |
| **Hevy value** | What goes in the app / the API's `weight_kg` | `50` |

**Two-arm exercises** (both dumbbells moving each rep — DB bench/incline press,
shoulder press, lateral raise, rear-delt fly, flye, simultaneous curls, DB
squats/lunges/split squats, DB RDL, seated calf raise): **Hevy value = 2 ×
per hand**.

**Single-implement exercises** (only one dumbbell moves per rep — single-arm
row, single-arm press, one-DB overhead triceps extension held in both hands,
single-arm/single-leg work loaded on one side, *and* any two-arm movement
performed **alternating** so one arm works per rep): **Hevy value = per hand**.

Rules that follow:

- **Never state a dumbbell load as a bare number** anywhere the athlete reads
  it — routine pages, overlays, `Target:` notes, check-in tables. Carry both: `25/hand (Hevy: 50)`. A bare `50` is ambiguous mid-set
  and that ambiguity is what corrupts the log.
- **Decide from how the lift is actually performed**, not from the exercise
  name. Hevy's catalogue mixes them — some one-arm variants are separate
  templates, some aren't. If the athlete alternates a curl, that set is
  single-implement. Ask when unclear rather than assuming.
- **Reading history: an exact-2× jump in one exercise at unchanged reps *and*
  unchanged RPE is a convention slip, not progress.** Check sibling exercises
  on the same dates before treating it as a strength change, and never let it
  set an e1RM, a PR, or a next-week load.
- **A doubled single-implement entry inflates prescriptions downstream.** If a
  starting load was derived from contaminated history, fix the load *and* say
  which sessions were misread.
- The athlete's own logging may be inconsistent across exercises and dates.
  When an audit turns up both conventions in one log, confirm the actual
  per-hand weights with the athlete before rewriting anything.

## Routine note format (standard)

Every routine exercise `notes` field this repo writes uses this format —
three lines, plus a week line on the first exercise only. A note nobody
reads between sets is wasted:

```
Wk of 12 Oct: heavier top sets, stop 1–2 reps short of failure
Target: 3×8 @ 80 kg @ RPE 8
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

- **Week line** — on the **first exercise of every routine a
  programming pass writes** (`/program-week`, `/one-off-week`), and only
  there: `Wk of <span start as D Mon>: <week focus>`, about 80
  characters at most. The focus is the coach's brief's week focus,
  shortened. Hevy drops routine-level notes on PUT, so this is the only
  place the week's intent can live, and the date lets the athlete spot a
  stale note mid-session. It is always the week focus — a session's own
  emphasis goes in its exercises' `Focus:` lines. This line is the only
  exception to the three-line cap.
- **Target** — always. The **absolute** prescription only, transcribed
  from the approved overlay in one fixed shape: sets × reps @ load @ RPE
  (`3×8–10 @ 80 kg @ RPE 8`). Leave warm-up sets out; consecutive
  working sets with the same reps, load and RPE collapse to `N×reps`, and
  groups join with ` + ` (`1×5 @ 100 kg @ RPE 8 + 3×5 @ 90 kg @ RPE 7`).
  **On a dumbbell exercise, give both numbers** — `3×8 @ 25/hand (Hevy:
  50) @ RPE 8` — since the athlete reads this note while entering the
  set. If the athlete picks the load, write the sets, reps and RPE, then
  `· choose the load`. **No relative or narrative wording** — "add 2.5 kg
  from last week", "same as last time", "+1 rep" go stale the moment the
  week ends, and a surviving note then tells the athlete the wrong thing.
  Changes and their reasons belong in the coach's brief and the check-in.
  Written by every programming pass, including the opening week's.
- **Focus** — only when there's a weekly emphasis. Omit the line
  otherwise.
- **Cues** — always. The canonical form cues, from the exercise's
  `cues` in `data/program.json` (the single source of truth — changing
  how a lift is performed edits it there first).

## Facts that bite

- **All weights are kg.** If the athlete programs in lb, convert (1 lb =
  0.45359237 kg) and round display values to the nearest 0.5 lb — raw values
  come back as long floats of exact lb amounts (e.g. `48.988…` kg = 108 lb).
- **Dumbbell weights are the COMBINED total across both arms**, per Hevy's own
  in-app guidance: *"When logging dumbbell exercises, you should log the total
  weight lifted per rep. For example, if each arm is lifting 10lbs, your weight
  logged should be 20lbs."* See "Dumbbell loads" below — this is the single
  easiest way to corrupt an athlete's log, and it is silent when it happens.
- **Routine templates cannot store an RPE target** (logged workout sets *do*
  carry `rpe`). RPE prescriptions live in the program and the
  overlay — and reach the athlete via each routine exercise's
  `notes` field in the standard format (see "Routine note format"
  above) whenever a routine is written to Hevy.
- **Set `type`** is one of `normal`, `warmup`, `dropset`, `failure`.
- **PUT replaces the entire routine** — to change one exercise, GET the routine,
  edit the JSON, PUT the whole thing back. Write only with the athlete's
  approval: "go" to a coach's brief whose closing line named the routine, a
  `/hevy-sync` decision, or `/new-program`'s confirmation before writing.
- **Routine-level `notes` are silently ignored on PUT** — the schema documents
  the field but writes don't persist it (verified 2026-07-18). The week focus
  lives in the first exercise's note instead: the week line above its Target
  line (see "Routine note format").
- **Omit `rep_range` when unused** — sending `"rep_range": null` in a set gets
  the whole PUT rejected with "Expected object, received null". Same for other
  null set fields: only send keys that have values.
- **Writes are rate-limited** — ~7 rapid PUTs trigger 429s. Space writes a few
  seconds apart and back off ~30 s on a 429.
- Routine ↔ plan mapping lives in **`data/state.json`** under `hevy`:
  `routines` maps each routine UUID (stable) to its program session. Trust
  IDs, not titles (titles can be renamed in the app). If the map and the
  live routine list disagree, heal the map with the athlete before doing
  anything else. `folders` holds the program and "One-off weeks" folder
  IDs, and `temporary_routines` the reusable one-off routines `routines
  create` writes — `/hevy-sync` ignores those routines entirely.

## Manual fallback

Only when a `coach` command keeps failing (not when a guard refuses a
write with exit 3 — fix the cause instead) and the athlete agrees to a
hand-built call. The approval gate's hook prompts on every raw write to
the API, with a warning; nothing the athlete hasn't approved goes out.

1. **Read** with `curl` and the auth block above; GET the routine before
   any write.
2. **Loads** still come from `coach` output: `python3 -m coach overlay
   notes <id>` gives each exercise's note, and `python3 -m coach units
   format --mode <load mode> --value <load>` gives each set's Hevy value
   (`hevy_kg` in its `load`). Never convert or double a load by hand.
3. **Write** the whole routine back with `PUT /v1/routines/{id}` (only
   keys with values, no routine-level `notes`), spacing writes a few
   seconds apart.
4. **Re-sync:** run `python3 -m coach hevy pull`, then `python3 -m coach
   routines verify --overlay <id>` to confirm the routine now matches
   the overlay. Raw calls skip the audit log, so say in the check-in
   record which routine was written by hand and why.
