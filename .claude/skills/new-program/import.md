# Path A — Import (they already have a program)

For athletes arriving with routines in Hevy (or on paper).

First reuse an explicit run/coach choice, or ask once: **run it as written,
or coach it?** Record `[coaching] mode` as `"run"` or `"coach"`; a default
value alone is not confirmation. Both routes preserve supplied structure
until the athlete agrees an edit. Run mode still applies every safety check.

## Paper/manual route (no Hevy required)

1. Read the supplied program. Transcribe its sessions, exercise order,
   working and warm-up set groups, rep targets, rest, supersets, cues and
   progression rules into a draft. Use `python3 -m coach library search
   "<exercise name>"` to resolve ids and confirm uncertain load modes.
2. Ask only for missing or ambiguous details: available days and desired
   count, rotation, loads, progression or light-week policy. Map the supplied
   progression to a supported scheme; if no scheme represents it, explain
   the gap and agree a representation before adoption. A missing load can
   use agreed calibration; retain an explicit supplied load once confirmed.
3. Write `.coach/drafts/program.json` using `coach/schemas/program_draft.schema.json`:
   `source` is `"manual_import"`, `hevy_routines` is `{}`, `hevy_folder` is null,
   `report` is `[]`, and `detected` is
   `{"percentage_based": false, "evidence": [], "suggested_schemes": []}`.
   Fill `created_at`, `schema_version`, `position` and the complete `program`
   according to the schema. Show the transcription beside the supplied
   exercise/scheme structure, and identify all agreed additions or changes.
4. Run `python3 -m coach program adopt --input .coach/drafts/program.json
   --dry-run`; settle errors and load-mode questions before the adoption
   approval. Then use step 7 below. Resume from this draft, reusing settled
   answers. With Hevy disabled, use training sheets for the first week.

## Hevy route

1. **Fetch:** run `python3 -m coach hevy pull`.
2. **Interview:** which routines are active? How do they rotate across a
   week (or longer cycle)? Any coach-/PT-led sessions alongside them?
   Rest days? What progression rule do they follow, if any?
3. **Load modes:** run `python3 -m coach library seed`. It matches
   every exercise in the routines to the exercise library and proposes
   how each is loaded. Put each `low`-confidence proposal and each
   `guessed` custom entry to the athlete — decide from how the lift is
   actually performed, not its name (an alternating curl is one
   implement) — and record the answers with `python3 -m coach library
   set-mode <id> <mode>`; confirm the rest with `python3 -m coach
   library confirm <ids>` (or `--all` once every one is right).
4. **Import:** run `python3 -m coach program import-hevy` (`--routine
   <id>` for each active routine, or `--folder <id>`). It writes the
   draft with one session per routine, mirroring the athlete's *actual*
   structure (don't reshape it during import): set groups, rest,
   supersets, a start load from each routine's top working set, cues
   from the exercise notes, and `hevy_routines` mapping each routine to
   its session. It exits 1 naming any exercise still without a
   confirmed load mode; settle it as in step 3 and run it again.
5. **Show the draft's report as one table** (kind, session, exercise,
   message): every converted load (check each dumbbell number against
   the athlete's actual dumbbells), working sets at mixed loads, cues
   taken from notes, and the missing schedule. When
   `detected.percentage_based` is true, show its evidence too.
6. **Finish the draft with the athlete:** the schedule rule and its
   days (adopt refuses an empty schedule), coach-led sessions, the
   light-week policy, and a progression scheme per exercise. Import sets
   every scheme to `hold`; a percentage-based program's
   `suggested_schemes` are a starting point for that conversation, never
   applied for you. Agree `cues` per exercise as you go.
7. **Adopt:** run `python3 -m coach program adopt --input
   .coach/drafts/program.json --dry-run`, then without `--dry-run`, as
   SKILL.md step 2 sets out.
8. **Review with a coaching eye:** run `python3 -m coach structure balance
   --program .coach/drafts/program.json` (the draft, before or after
   adopting) and agree `dose_targets` and `dose_intent` as design.md step
   4 sets out, keeping the athlete's own numbers as the ordinary baseline.
   Then assess it — weekly balance gaps, missing progression scheme, junk
   volume, recovery clashes between adjacent days. **Propose improvements; don't force them.** Small fixes
   can land now (with approval); big ones can wait for a `/check-in` or a
   redesign. In run mode, mention them as information only.
