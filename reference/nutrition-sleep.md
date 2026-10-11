# Nutrition sleep gate

Read this before agreeing a deficit in `/goals`, when checking an active
deficit, or when a sleep gate is `pending measurement` at `/check-in`.
This is a low-confidence coaching heuristic: a trailing 14-day average
under 7 hours leads to recomp at maintenance; at or above 7 hours passes
this gate (rn:sleep-dieting.3). Seven hours is not a medically proven
permission boundary for dieting. Keep the no-source fallback below.

## Record the evidence

Use hours asleep, not time in bed or a subjective answer such as "sleep
felt fine". Accept dated manual nightly hours, tracker nightly hours, or
an explicitly reported period average with its start and end dates.
Manual hours require no watch. Ask whether an average represents the
whole stated period, and identify manual period means as self-report.

`wellness` requires `[activity] enabled = true`. If disabled, explain
`/setup`'s supported activity setup: show that config change, obtain the
athlete's approval and run `python3 -m coach config validate`. Manual
entry needs no device adapter or external connection. Preserve the
existing wellness storage/privacy choice.

After confirming the supplied hours and dates, record nightly values
with `python3 -m coach wellness add --date YYYY-MM-DD --sleep-hours H`.
Record a period mean once with `wellness add --from START --to END
--sleep-hours H`; never expand it into invented nightly entries.
Run `python3 -m coach wellness summary --from START --to END` for the
14 calendar dates ending on the assessment date. Read `nutrition_gate`
and `sleep.evidence`, `covered_dates`, `missing_dates` and `nights`.

A complete diary or complete non-overlapping period means can settle
the average gate. `nights` counts actual nightly observations only;
period means retain their original span. A clipped period mean, or one
partly replaced by daily observations, cannot supply the missing
nightly hours: the summary excludes it from the average and shows its
original span and resolved dates. Ask for the matching period average
or missing nightly hours rather than estimating them.

## Resolve and record

- Complete supported coverage: replace `pending measurement` with the
  actual result, `recomp` or `passed`. At 6.4 h, agree maintenance;
  at 7.2 h, offer `/goals` to reconsider a deficit if desired.
- Incomplete coverage: keep `pending measurement`, state which dates
  are missing and which source spans are unusable. An incomplete diary
  does not become a complete measured period.
- No hours source: ask how they sleep. Reported short sleep or a sleep
  limiter in Recovery defaults to maintenance, `pending measurement`;
  otherwise a deficit may proceed, `not evaluated` (rn:sleep-dieting.4).

In `profile.md`, record status, average if supported, assessment date,
covered dates, source, nightly versus period-mean basis, and missing
coverage. A self-reported mean stays labelled self-report after the
pending status resolves. During a deficit, a failed gate routes to
`/goals` to agree maintenance; propose phase/config/profile changes and
obtain athlete approval. Passing this gate does not change the phase.

The separate seven-day fatigue decision counts individual short nights.
A period mean cannot establish that count, even when it settles this
fourteen-day nutrition gate. Do not copy this gate's status into fatigue.
