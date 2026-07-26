---
name: pantry
description: Use when the athlete's food stock changes or needs checking between meal plans — they bought something ad hoc, used something up, binned something, or want the pantry record brought back in line with reality. Triggers include "/pantry", "I bought…", "we're out of…", "I binned the…", "update the pantry", "what's in the fridge", "reconcile the pantry".
---

# Pantry

Own `nutrition/pantry.md` — the record of what's actually in the house:
perishables, opened partial packs, cooked leftovers, and the coarse
state of each staple. Format and estimation rules live in
**`reference/pantry.md`** — follow it exactly; `/meal-plan`'s
shopping-list subtraction and use-it-up bias depend on it.

This skill is deliberately small. `/meal-plan` runs the weekly
reconcile itself during its plan review; this command exists for
everything **between** plans — and for the first run.

## Quick update

"Bought extra mince", "used the last of the oats", "binned the
spinach": edit the relevant rows and stop. New perishables and partials
get a row; staples flip state; gone perishables come off the table.
Don't audit the rest of the file, don't re-ask anything, and don't
touch **Last reconciled** — a quick update is a row edit, not a
reconcile.

## Reconcile

Predict the current state per `reference/pantry.md` (last reconciled
file + newest plan's Buy list assumed bought − what the plan consumed,
perishables aged realistically). Present the predicted table **once**
and ask what's wrong or missing — plus anything bought ad hoc or binned
since. Write the corrected file and refresh **Last reconciled**
(via /pantry).

If `/meal-plan` reconciled recently and nothing has changed since, say
so and don't make the athlete re-confirm a table they just confirmed.

## First run

No `nutrition/pantry.md`? Create it:

- Seed the Staples table from the staples list in `profile.md` (Food &
  eating), asking for the states (in / low / out) in one pass — not one
  question per staple.
- One open question for perishables & partials: "what's in the fridge
  that needs eating, and any opened packs?" Rough amounts are fine.
- Write the file with today as **Last reconciled** (via /pantry).

No staples list in the profile either? Send the athlete through
`/recipes`' food interview first — the pantry mirrors a staples list
that has to exist.
