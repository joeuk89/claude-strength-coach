---
status: accepted
date: 2026-10-11
---

# Scripts propose and verify; the coach decides; a mechanical gate guards every Hevy write

Every weekly prescription used to be computed by the language model in
conversation: unit conversion, dumbbell doubling, progression arithmetic,
deload transforms, and the Hevy API payloads themselves. The failures that
reached the athlete were silent and expensive (a doubled load that sat in
Hevy for three weeks, a typo repaired through the API, stale targets
carried for seven weeks). We decided that a script computes the proposed
week from the history cache and each exercise's named progression scheme,
emits flags, and performs and verifies the write; the coach reviews the
proposal, overrides with a recorded reason, and writes the brief. No write
to Hevy happens without the athlete's approval, and that gate is enforced
by the tool permission layer and an approval hash on the overlay, not by
instructions the agent is asked to follow.

## Considered options

- **Full autopilot**, the script's output goes straight to Hevy.
  Rejected: the recorded coaching failures were judgement and dose
  problems a rules engine would have reproduced, and the athlete wants to
  read the week before training it.
- **Keep it all in the model, add more prose rules.** Rejected: eight
  copies of the dumbbell rule did not prevent the error.
- **Let the coach write a new progression scheme mid-session when a
  program needs one.** Rejected: untested code trusted because it is a
  script. New schemes are code changes with fixture tests; a `hold` scheme
  covers coach-managed work in the meantime.

## Consequences

- A scheduled or headless run can pull, compute and draft, but cannot
  write to Hevy, because the gate's prompt has no one to answer it.
- Overrides persist structurally so a scheme does not re-propose away a
  standing constraint every week.
- Plugins declare parameter and state schemas that are validated; a typo
  in a parameter name is an error, not a silent fallback.
