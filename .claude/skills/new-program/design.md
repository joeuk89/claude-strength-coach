# Path B — Design (from scratch, and every redesign)

A full coaching conversation, grounded in `profile.md` (goal, experience,
equipment, training week, time per session, injuries, recovery, cardio)
and `config.toml` (units, equipment and its increments).

1. **Confirm the constraints** from the profile; ask only what's missing.
2. **Propose 2–3 structure options** that fit the constraints, with
   trade-offs (e.g. for 4 days: upper/lower vs. full-body vs. PPL+1).
   Recommend one and say why. Where the choice depends on evidence,
   follow `CLAUDE.md` "Researching current best practice": read the notes
   for the area first, research and save a local note when none answers
   it, and cite claim ids.
3. **Draft the program:** the rules first (progression scheme — double
   progression is a sensible default; RPE targets; the light-week
   policy — a hard-week ceiling and the fatigue triggers from
   `CLAUDE.md` "Coaching principles", the ceiling set for this athlete
   within the allowed range; warm-up protocol), then each session, every
   exercise picked from the exercise library (`python3 -m coach library
   search <name>`). If no entry fits, follow
   [custom exercise creation](../../../reference/custom-exercises.md)
   to agree, preview and create one before using it. Respect every profile
   constraint (equipment load caps, session time limits, recovery windows around coach-led
   sessions and cardio). The program's interference rules flag quality
   cardio placed too close to lifting: `python3 -m coach interference
   list` shows the rules available and their defaults.
4. **Walk the athlete through it** — the reasoning, not just the tables.
   Iterate until they'd actually train it. Confirm before writing files,
   then write the draft to `.coach/drafts/program.json` and adopt it as
   SKILL.md step 2 sets out (a redesign adds `--replace`, step 3). The
   schema lists every key; set these as follows:
   - `source` `design`, `hevy_folder` null (adopt then keeps the
     current program folder), `report` `[]`, and `detected`
     `{"percentage_based": false, "evidence": [], "suggested_schemes": []}`.
   - The program's `interference`, as `{"name", "params"}` entries,
     unless the athlete agreed otherwise; `[]` turns the rules off. For
     a first program, take each rule from `interference list`
     `available` with its defaults. For a redesign, carry over
     `interference list` `rules` (each rule's name and params), so a
     tuned param or a rule the athlete left off survives.
   - `hevy_routines` `{}` for a first program. For a redesign, adopt
     builds `hevy.routines` only from the draft, so carry the mapping
     over: take each `hevy.routines` entry from `python3 -m coach state
     show` whose `session_id` the new program keeps, and write it as
     `"<routine id>": "<session id>"`. Leave sessions that are new out;
     step 5 gives them routines. A kept session left out gets a second
     routine and its old one goes stale.
5. **Hevy:** adopt lists the sessions without a routine in
   `without_routine`; the opening week's programming pass creates them.
   `/program-week` names each new routine in its write line, and after
   the athlete's "go" runs `python3 -m coach routines create --overlay
   <id>` behind the approval gate, which makes each routine in the
   program folder and records its id in `data/state.json`. Without Hevy
   (`[hevy] enabled = false`) skip this step.
