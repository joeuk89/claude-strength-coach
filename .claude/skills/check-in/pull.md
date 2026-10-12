# Pull the data

The window runs from the day after the newest review (a Check-in
record) to today, so it leaves out workouts that review already covered:
normally about a week. Before the first review it starts at the earliest
overlay, else the program start. **Deep tier:** for the trend
analysis, extend the lookback to the last deep check-in (about six
weeks): one week can't show a trend. **Adherence and the
hard-week count** need more history: read the check-in records and logs
back as far as analyze.md needs.

**Gap check.** Count the days from the last lifting workout of any
kind — solo, or coach-led as the log or the reply shows it — to the
first session of the coming week, the same count program-week makes.
Over 10 days means the coming week is a **return week** under the
return rule in `CLAUDE.md` "Coaching principles": say so in the Sunday
message's first line ("… — 16 days off by Tuesday's session, so next
week is a return week"). An `ill` miss tag or reported illness in the
gap brings in that rule's illness conditions too. Program-week applies
the rule.

**With Hevy:** run `python3 -m coach hevy pull`, then `python3 -m coach
history sync` to resolve the new workouts into `data/history/` (it lists
any exercise it could not match in `data.unresolved`), then `python3 -m
coach hevy status` for the cache's age and counts. Read the window's
workouts from the cache (`.coach/cache/hevy/workouts/`). **Read every
workout's `description` and each exercise's `notes`**: the athlete's
own words on how the session went (fatigue, sleep, a target that was too
high, a niggle, why sets were dropped). They're the readiness signal
the numbers can't show, so quote them in the analysis and let them
shape the decisions. The cached body measurements are a fallback weight
source only.

**STALE check (Hevy).** Run `python3 -m coach overlay current` and, with
an overlay in force, `python3 -m coach routines verify --overlay <its
id>`. A routine it reports with `verified: false` and a `prescription`
change to an exercise's notes is **STALE**: it doesn't carry the overlay
in force, so it still holds older notes. A `structural` change is an
in-app edit, which program-week settles. No overlay yet: skip the check.
On a normal week the list appears in program-week's coach's brief (on a
hold-steady week, its close-out), which reuses this verify; the pass
rewrites every routine in the span either way. Skip the check when the
coming week is a light or other one-off week: program-week writes fresh
temporary routines for it.

**Without Hevy:** the workouts are in the manual log, one `log add` per
workout the athlete reported. Log any they report now the same way
(`CLAUDE.md` "Hevy" → "No Hevy?"), then run `python3 -m coach history
sync` so `checkin prepare` pre-fills the Sunday message from them. Read
each logged workout's `notes` as you would a Hevy description.

**Coach-led sessions (PT, classes) are often logged worse than solo
sessions**: the Coach-led field of the Sunday message confirms which
ones happened. Never compute adherence from the API alone. Check
Coach's notes for this athlete's known logging habits.
