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
   - `dose_targets` and `dose_intent`, agreed with the athlete; the
     goal comes from that conversation, never from the nutrition phase.
     Keep three numbers apart: the **target** (weekly fractional hard sets
     balance judges), the **ordinary baseline** (what the athlete trains
     in an ordinary week now) and the **minimum week** (the short-week
     variant in `minimum_week`, checked against the ordinary program,
     never a target). For example:

     ```json
     "dose_targets": {"chest": 4, "lats": 4, "quadriceps": 4, "hamstrings": 0},
     "dose_intent": {"goal": "maintenance", "baseline": {"chest": 12, "lats": 12, "quadriceps": 10},
                     "reasons": {"chest": "a third of their own 12 sets while the new job settles",
                                 "hamstrings": "trained by their weekly hill sprints for now"}}
     ```

     Hypertrophy: a muscle without a target falls back to 10
     (rn:volume-frequency.1). Strength: set targets from the agreed
     priority emphasis. Maintenance: record `baseline` and agree each
     target from it; for an athlete about 60 or older keep it nearer the
     baseline (rn:minimum-effective-dose.2). Running counts no sets: say
     in `reasons` how it shaped a target. A 0 with a reason records a
     deliberate omission.
   - Before showing the draft, run `python3 -m coach structure balance
     --program .coach/drafts/program.json`. It only reads, and needs no
     adopted program. Settle each `dose_coverage_gap` (a target, or a 0
     with its reason) and `dose_target_pending` (an agreed target), and
     weigh each `volume_undershoot` with the athlete.
   - `hevy_routines` `{}` for a first program. For a redesign, adopt
     builds `hevy.routines` only from the draft, so carry the mapping
     over: take each `hevy.routines` entry from `python3 -m coach state
     show` whose `session_id` the new program keeps, and write it as
     `"<routine id>": "<session id>"`. Leave sessions that are new out;
     step 5 gives them routines.
5. **Hevy:** adopt lists `without_routine` and `orphan_routines`.
   Show the managed routines now unmapped and offer leave, explicit
   reuse, or retirement. Adoption changes the local program only;
   external housekeeping belongs in the opening `/program-week` brief.
   Its build.md preflight resolves templates from the complete cache,
   including a starter's first exercise, and previews the exact new or
   reused routines (`python3 -m coach routines create --overlay <id>
   --dry-run`) and retirements before asking for approval. Without
   Hevy (`[hevy] enabled = false`) skip this step.
