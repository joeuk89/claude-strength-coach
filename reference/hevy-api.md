# Hevy API cheatsheet

How this repo reads and writes the athlete's Hevy data. Full docs:
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
| `GET /v1/workouts?page=&pageSize=` | Logged workouts, newest first: exercises → sets with `weight_kg`, `reps`, `rpe`, `type` | max 10/page |
| `GET /v1/workouts/count` | Total workout count | — |
| `GET /v1/workouts/events?since=<ISO8601>&page=&pageSize=` | Workout updates/deletes since a date — use for "what's new since last check-in" | max 10/page |
| `GET /v1/workouts/{id}` | One workout | — |
| `GET /v1/routines?page=&pageSize=` | Routine templates: exercises with `rest_seconds`, `notes`, `supersets_id`, sets with `rep_range {start,end}` / `reps` / `weight_kg` | max 10/page |
| `POST /v1/routines` · `PUT /v1/routines/{id}` | Create / replace a routine (PUT replaces the whole exercise list) | — |
| `GET /v1/routine_folders` | Routine folders (id + title) | max 10/page |
| `POST /v1/routine_folders` | Create a routine folder (body `{"routine_folder": {"title": "…"}}`). `POST /v1/routines` takes a `folder_id` to file the new routine | — |
| `GET /v1/exercise_templates?page=&pageSize=` | Exercise catalogue — needed to get `exercise_template_id` when adding an exercise to a routine | max 100/page |
| `POST /v1/exercise_templates` | Create a custom exercise (`title`, `exercise_type` e.g. `duration`/`weight_reps`, `equipment_category`, `muscle_group`). Returns the new template ID as plain text | — |
| `GET /v1/exercise_history/{exerciseTemplateId}` | All logged sets of one exercise over time — good for progression analysis | — |
| `GET /v1/body_measurements` | Bodyweight etc. | max 10/page |
| `GET /v1/user/info` | Account sanity check | — |

## Routine note format (standard)

Every routine exercise `notes` field this repo writes uses this
three-line format — hard cap three lines; a note nobody reads between
sets is wasted:

```
Target: 3×8 @ RPE 8 — add 2.5 kg from last week
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

- **Target** — always. This week's sets × reps @ RPE plus the load
  instruction. Written weekly by `/program-week`; `/new-program` and
  `/one-off-week` write their own targets at creation time.
- **Focus** — only when there's a weekly emphasis. Omit the line
  otherwise.
- **Cues** — always. The canonical form cues, copied from the
  exercise's `Cues:` line in `routine/*.md` (that line is the single
  source of truth — changing how a lift is performed edits it there
  first).

## Facts that bite

- **All weights are kg.** If the athlete programs in lb, convert (1 lb =
  0.45359237 kg) and round display values to the nearest 0.5 lb — raw values
  come back as long floats of exact lb amounts (e.g. `48.988…` kg = 108 lb).
- **Routine templates cannot store an RPE target** (logged workout sets *do*
  carry `rpe`). RPE prescriptions live in the `routine/` files and the
  weekly overlay — and reach the athlete via each routine exercise's
  `notes` field in the standard three-line format (see "Routine note
  format" above) whenever a routine is written to Hevy.
- **Set `type`** is one of `normal`, `warmup`, `dropset`, `failure`.
- **PUT replaces the entire routine** — to change one exercise, GET the routine,
  edit the JSON, PUT the whole thing back. Confirm with the athlete before any
  write.
- **Routine-level `notes` are silently ignored on PUT** — the schema documents
  the field but writes don't persist it (verified 2026-07-18). Day-level intent
  has to live in the first exercise's note instead: one extra line above its
  Target line — the only exception to the three-line cap.
- **Omit `rep_range` when unused** — sending `"rep_range": null` in a set gets
  the whole PUT rejected with "Expected object, received null". Same for other
  null set fields: only send keys that have values.
- **Writes are rate-limited** — ~7 rapid PUTs trigger 429s. Space writes a few
  seconds apart and back off ~30 s on a 429.
- Routine ↔ plan mapping lives in **`routine/hevy-map.json`** — routine UUIDs
  (stable) mapped to repo file + heading. Trust IDs, not titles (titles can be
  renamed in the app). If the map and the live routine list disagree, heal the
  map with the athlete before doing anything else.
  A `temporary` section holds the "One-off weeks" folder ID and its
  reusable routine IDs (written by `/one-off-week`) — `/hevy-sync`
  ignores those routines entirely.
