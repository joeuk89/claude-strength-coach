# Path A — Import (they already have a program)

For athletes arriving with routines in Hevy (or on paper).

1. **Fetch:** run `python3 -m coach hevy pull` — or take the paper
   plan, and write the draft as in Path B (design.md).
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
8. **Review with a coaching eye:** now assess it — weekly balance gaps,
   missing progression scheme, junk volume, recovery clashes between
   adjacent days. **Propose improvements; don't force them.** Small fixes
   can land now (with approval); big ones can wait for a `/check-in` or a
   redesign. In run mode, mention them as information only.
