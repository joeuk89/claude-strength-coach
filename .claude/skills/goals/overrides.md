# Nutrition overrides

A **nutrition override** is any period in which the athlete eats to a
number other than the app's (or, without an app, other than the
trend-driven calorie target on file): holding calories at expenditure
instead of the app's deficit, a manual calorie band, a protein figure
below the floor. An app setting at or above the floor is compatible.
If an override is agreed, record it as the
`[nutrition.override]` table in `config.toml` (SKILL.md step 9) with
every field:

- `start` date;
- `what` is overridden, with the number the athlete eats to;
- `reason`;
- `exit_condition` — what ends it early;
- `expires` — no later than **21 days** after the start (`config
  validate` refuses a later date);
- `renewal` — 0 for a first override, 1 once renewed, 2 for a second
  consecutive renewal.

Only **one override at a time**. `/check-in` expires it on or after its
expiry date (`nutrition status` flags `override_expired`) and returns the
athlete to the app's numbers. Renewing it needs this skill, a fresh
reason and a new expiry no later than 21 days from the renewal. A second
consecutive renewal is flagged to the athlete as a sign the plan itself
needs changing (usually the phase or the trend rate), and `/check-in`
keeps flagging it while it stands.
