# The Sunday message

Send **one** message that pre-fills what the log shows and asks only what
it can't, then wait for the athlete's single reply. They answer by
number. This replaces an interview: no question-by-question turns.

Run `python3 -m coach checkin prepare` and send its `data.text` as the
Sunday message. You may tighten the wording, and drop a field that
cannot apply or that the athlete's opening message already answers,
renumbering the rest. Never change the card's figures or the order of
the fields. `data.card` holds the same week as data: the window (the day
after the newest review to today; before the first review, from the
program's start), each planned session trained, missed (with any tag on
file) or trained but not logged, with durations against the session cap;
each exercise's result against the prescription; e1RM changes; flags
(`convention_slip`, `duration_over_cap`, `stale_routine`); and each Hevy
routine's state (`edited_in_app` routines end the card with a
keep-or-replace field, settled in program-week). The card picks the tier
(`mode`, with `tier_reasons`: no review yet, or the last deep review 42
or more days old, rn:deloads.12). When the block preview requires deep,
pass one `--deep-reason <code>` for each `deep_review.reasons` code and
no `--tier`: the card runs deep, or a catch-up card defers the deep
review. Pass `--tier deep` only when the athlete asks for a deep review;
`--tier weekly` overrides a due deep review. Mode `catch_up` means more
than 10 days since the last check-in: send the catch-up card instead
([catch-up.md](catch-up.md)).

The first line names the window and the tier with its reason. Then the
fields, always in this order:

1. **Sessions** — logged vs. planned for the window, day by day. List
   each planned session with no logged workout and ask for one tag per
   miss: `time / sleep / ill / family / skipped / other`. Optional
   sessions need no tag. Ask for anything trained but not logged.
2. **Coach-led** — ask what each coach-led session in the window
   covered. State what its log shows and the inferred rotation position
   for confirmation.
3. **Runs** — with an activity source, the card states the window's runs
   from `python3 -m coach cardio week` (count, distance, quality runs)
   and any planned activity `cardio reconcile` found missed, and asks
   only for runs no source logged. With no source on, it states the runs
   the activity files record or plan in the window and asks the same;
   with no run recorded or planned in the window, there is no Runs
   field. Lifting alone never implies running.
4. **Sleep** — with enough dated nightly observations, the card
   states the last seven nights (average and short nights) and asks how
   it felt. Otherwise ask, in one line, for hours asleep each night (diary
   or tracker), else the average with its dates and source, and how it
   felt: only nightly hours feed the fatigue check (analyze.md).
5. **Niggles** — anything new? Name each open niggle-log row (`watching`
   or `easing`) and ask whether it is quiet or still there. The card
   quotes the window's workout and exercise notes once, under "Notes
   logged" (`data.card.notes`, with date, session and exercise), and
   this field asks whether anything in them is a niggle to track. A note
   is the athlete's report, not a diagnosis: the card never records a
   niggle from a note alone. Add one with `niggles add` (act.md) only
   once the reply confirms it.
6. **Food** — the food questions, worded as `python3 -m coach nutrition
   status` gives them in `data.questions`, one line each:
   1. Readings: the app's numbers (trend weight · expenditure · targets
      (kcal/protein) · 7-day average (kcal/protein) · days logged), or,
      without an app, this week's morning weigh-ins and average daily
      protein if they track it. A dashboard screenshot is accepted.
   2. Habits: anchors most days (y/n)? Anything in the plan that didn't
      work? The anchors ask is left out when no anchors are on file, the
      plan ask unless a meal plan is in force, which the card names.
   3. Next week: food exceptions — who cooks which nights, office-day
      changes, meals out. Asked **only when a standing weekly template
      exists** (`[nutrition.template]` in `config.toml`); `data.questions`
      leaves it out otherwise.

   Nutrition not enabled (`data.enabled` is false): the field is
   **Bodyweight**, one morning scale weight, and nothing else.
7. **Next week** — anything different: travel, schedule, kit, illness?

**Leave out a field that cannot apply** and renumber the rest from 1:
no coach-led sessions in the window, no Coach-led field; no cardio in
the athlete's week, no Runs field; no meal plan, no plan question. **A fact the log already answers is
stated for confirmation, not asked.** If the athlete's opening message
already covers the fields, don't send the template; leave out any single
field it already answers.

**Deep tier:** the same message. Any deep-only asks follow the last
field, numbered on.

**Body composition** (waist, body fat, progress photos) is a deep-only
ask, never a weekly one. Ask it only when both hold:

- the goals or a phase trigger in `profile.md` use waist, body fat or
  photos, or the phase is a cut or recomp; and
- no deep record has a reading yet, or the last reading is 4 or more
  weeks old (the newest deep record's **Body composition** line says).

Ask for waist, a body-fat reading if they have one, and their own
one-line read of their progress photos. **Photos stay with the athlete
and never go into the repo**: record only their read. A reading the
reply leaves out is recorded once as "not supplied" and not asked again
before the next deep check-in.

**Rotation position.** If the program rotates, infer where the coming
week lands and state it for confirmation: never ask it as its own
question. Sources, in order: the coach-led session's log,
`rotation.position` in `state show`, the newest check-in. State it in
the Coach-led field, or in the Next week field when there is no
Coach-led field. If the sources disagree, state the first one and name
the disagreement.

**Missed sessions** get the one-word tag, with no follow-up on the
reason. A miss the reply leaves untagged is recorded as `untagged`.

## Record the reply

Record the reply in one batch before analysing it. Write the facts it
gives as a JSON list to `.coach/drafts/checkin-<date>-reply.json` and
run `python3 -m coach history annotate --input <that file>`, with
`"source": "check-in <date>"` on each:

- `{"kind": "miss", "date": D, "session_id": S, "tag": T}` for each
  tagged miss (no annotation for one left untagged);
- `{"kind": "trained_unlogged", "date": D, "session_id": S, "note": N}`
  for a planned session trained but not logged: it counts as trained,
  with no results and no e1RM;
- `{"kind": "external", "date": D, "external_id": E, "done": true|false,
  "note": N}` for each coach-led session, the note one line on what it
  covered.

Exit 1 names each annotation that doesn't fit; fix the file and run it
again. Days the reply says the athlete was ill, injured or away go in as
status days: `python3 -m coach status-days add --kind ill|injured|travel
--from D --to D --note "<one line>" --source "check-in <date>"` (leave
out `--to` while it is still going on; `status-days end <id> --date D`
closes it later, `status-days withdraw <id> --reason <text>` takes back
a wrong one). An ill status day in the gap brings in the illness return
rule, exactly as an `ill` miss tag does, and no session is planned on its
days. Add `--no-training` when the athlete agrees not to train on those
days: a planned break, whose sessions need no tag and whose weeks neither
count nor reset. Leave it off when they will train while away. Add a goal event the reply names
with `python3 -m coach events add --id <slug> --title <name> --date D
--priority A|B|C` (plus `--activity`, `--distance-km`, `--planned-id`
for a planned activity). For each pending decision the Events field
asks, record the agreed window with `events window <id> --from D --to D
--rationale <why>` (or `--none`), and a result with `python3 -m coach
events complete <id> --result <text>`. An event's window is always one
the athlete agreed, with its reason. Then run `checkin prepare` again:
the card now carries the reply.

**At most one follow-up turn**, and only for a gap that blocks
programming: an unresolved rotation position, a new niggle's severity,
or nutrition numbers you can't read. Ask every such gap in that one
turn. Record any other gap once as "not supplied" and move on.
