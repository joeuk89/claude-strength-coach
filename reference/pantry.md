# Pantry — the stock format

The contract between `/pantry` (which owns `nutrition/pantry.md`) and
`/meal-plan` (which reads it at plan time and reconciles it during the
plan review). Follow it exactly — `/meal-plan`'s shopping-list
subtraction and use-it-up bias depend on it.

## What the pantry is — and isn't

`nutrition/pantry.md` records what's **actually in the house right
now**. It is deliberately not a full inventory — tracking every gram of
everything is bookkeeping the athlete will abandon within weeks. The
file tracks only what earns its keep:

- **Perishables & partials** — anything that can be wasted: fresh food,
  opened packs (½ rice pouch), ingredients left over from a skipped
  meal, and **cooked leftover portions** from batch cooks (a
  `servings: 3` card cooked against 2 planned slots leaves a portion —
  that's stock).
- **Staples** — coarse state only (`in` / `low` / `out`) for each item
  on the staples list in `profile.md` (Food & eating).

**Division of truth:** `profile.md` owns the staples *list* — identity,
what the athlete keeps in by default. The pantry owns the *state* —
what's actually there today. Add or remove staples in the profile; flip
their state here.

Quantities are rough by design ("~200 g", "½ bag"). Close enough to
plan from beats precise and abandoned.

## File layout — `nutrition/pantry.md`

```markdown
# Pantry

**Last reconciled:** 2026-07-27 (via /meal-plan)

## Perishables & partials
| Item | Approx. amount | Pressure | Note |
| --- | --- | --- | --- |
| Chicken breast (cooked) | ~200 g | eat in ~2 days | leftover portion — chicken-rice-bowl |
| Basmati rice pouch | ½ pouch (~125 g) | open, keeps | |
| Spinach | ~½ bag | wilting | est. |

## Staples
| Staple | State |
| --- | --- |
| Eggs | in |
| Oats | low |
```

- **Last reconciled** — date plus which skill wrote it. Estimation
  (below) measures from this point.
- **Pressure** — plain words, not dates: "eat in ~2 days", "wilting",
  "open, keeps", "frozen". Enough to order the use-it-up bias, no more.
- **`est.` in Note** — the entry is system-inferred and the athlete
  hasn't confirmed it. Reconciliation clears the marker (confirm or
  correct); skills treat `est.` amounts as guesses, not facts.
- Staples state is three values only: `in` | `low` | `out`. No
  quantities in the staples table.

## Estimation — predicting the current state

Both `/pantry` (reconcile mode) and `/meal-plan` (its plan review)
predict the state before asking, so the athlete corrects a table
instead of answering an inventory quiz. The prediction:

1. Start from the pantry file as last reconciled.
2. Add the newest dated plan's **Buy** list — assume it was purchased.
3. Subtract what that plan consumed: the pool's ingredients plus
   whatever the plan noted as **assumed used** from the pantry —
   corrected by the plan review's eaten/skipped/swapped answers (a
   skipped meal's ingredients are probably still in; a swap consumed
   something else).
4. Ignore covered entries (meal-kit boxes, family dinners, eat-out) —
   their ingredients were never the athlete's stock.
5. Mark everything inferred `est.`, and age perishables realistically
   (bought Monday, reconciling Friday — probably wilting).

Present the predicted table **once** and ask what's wrong or missing —
never walk it item by item. The athlete's corrections, plus anything
bought ad hoc or binned since, become the new file.

## Rules

- **Same-write rule:** any conversation that changes stock — a
  reconcile or a quick "bought / used up / binned" update — writes
  `pantry.md` in that same operation. Only a full reconcile refreshes
  **Last reconciled**; a quick update edits rows without claiming one
  happened.
- **No pantry file is a normal state, not an error** — `/meal-plan`
  plans the old way (live staples check) and offers `/pantry` at
  close-out. Never block planning on it.
- Perishables that are gone come **off the table** — the pantry is
  current state, not a log.
