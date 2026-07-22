# Hevy API cheatsheet

How this repo reads and writes the athlete's Hevy data. Full docs:
https://api.hevyapp.com/docs/ (spec is embedded in
`https://api.hevyapp.com/docs/swagger-ui-init.js` — the docs page itself is
JS-rendered, so fetch that file if you need schema detail).

## Auth

- Requires Hevy Pro. Key lives in `.env` at the repo root as
  `HEVY_API_KEY` — never print it, never commit it (`.gitignore` covers it).
- Every call: header `api-key: $HEVY_API_KEY`, base URL `https://api.hevyapp.com`.

```bash
set -a && source .env && set +a
curl -s -H "api-key: $HEVY_API_KEY" "https://api.hevyapp.com/v1/workouts/count"
```

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

## Facts that bite

- **All weights are kg.** If the athlete programs in lb, convert (1 lb =
  0.45359237 kg) and round display values to the nearest 0.5 lb — raw values
  come back as long floats of exact lb amounts (e.g. `48.988…` kg = 108 lb).
- **Routine templates cannot store an RPE target** (logged workout sets *do*
  carry `rpe`). RPE prescriptions live in the `routine/` files — and, as a
  standing rule, go into each routine exercise's `notes` field (with the key
  form cue) whenever a routine is written to Hevy, so the athlete sees them
  mid-session.
- **Set `type`** is one of `normal`, `warmup`, `dropset`, `failure`.
- **PUT replaces the entire routine** — to change one exercise, GET the routine,
  edit the JSON, PUT the whole thing back. Confirm with the athlete before any
  write.
- **Routine-level `notes` are silently ignored on PUT** — the schema documents
  the field but writes don't persist it (verified 2026-07-18). Day-level intent
  has to live in the first exercise's note instead.
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
