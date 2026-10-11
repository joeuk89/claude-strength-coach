---
name: meal-plan
description: Use when the athlete wants help planning what to eat — meals, snacks, and a shopping list for any window (the week ahead, a few days, one day). Triggers include "/meal-plan", "plan my meals", "what should I eat this week", "help me hit my protein", "what healthy snacks should I buy", "build me a shopping list".
---

# Meal planning & shopping list

A week's plan is the **standing template** (`[nutrition.template]` in
`config.toml`) plus that week's **plan exceptions**. The athlete's effort
per plan is **one exceptions line and one approval**: you draft the
exceptions and the picks for open slots, the `meals` commands do the
arithmetic (day totals, flags, the pool, the shopping list), and the
athlete says "go".

**Division of labour:** `/goals` owns the strategy and its numbers
(`[nutrition]`; `python3 -m coach nutrition status` returns them). This
skill owns the standing template (`[nutrition.template]`). The nutrition app, if the athlete uses one, owns the
calorie target; without one, `kcal_target` does. `/recipes` owns the
recipe bank. This skill picks food from the bank to those numbers and
never computes a calorie target. If the targets look wrong, send the
athlete to `/goals`; if the bank needs work, `/recipes`.

Requires nutrition to be set up: if `nutrition status` says `enabled:
false`, run `/setup` or `/goals` first. If `meals template` exits 5 for
want of `[nutrition.template]`, run **Set up the standing template**
below once before planning.

## The files

- **`nutrition/menu/`**: the recipe bank, owned by `/recipes`.
- **`data/nutrition/plans/<id>.json`**: the plan, written by `meals
  build`; the id is the first day of the window.
- **`nutrition/plans/<id>.md`**: the rendered plan, written by `meals
  render`. Never hand-edited: change the draft and build again.
- **`.coach/drafts/meal-plan-<id>.json`**: your draft (gitignored).

**No bank?** If `nutrition/menu/` doesn't exist, invoke the `/recipes`
skill now: run its interview and seeding flow, then come back here and
continue. Never plan from an empty bank.

## Set up the standing template (first run only)

1. Draft `[nutrition.template]` and its `[[nutrition.template.standing]]`
   rows from `profile.md` → Food & eating (written by `/recipes`'
   interview: staples, office days, who covers which meals, plan style)
   and the bank's card slugs, using the example in
   `config.example.toml` for the shape.
2. Show the athlete the exact TOML and what each standing row means in
   plain words. Write it to `config.toml` only on their approval.
3. Run `python3 -m coach config validate`, then `python3 -m coach check
   --only nutrition_template`. Fix anything either names, with the
   athlete, before planning.

This is the only time the skill asks more than the exceptions line and
the approval; later changes to the typical week are edits to this
table, made the same way.

## 1. Read the standing week

Run `python3 -m coach meals template` (the week ahead; `--week D` for
another) and `python3 -m coach nutrition status`. The template gives
every day's standing entries, the anchors, the open slots, the office
days, the staples, the plan style and the targets. Read
`routine/program.md` for training and rest days, and the index
`nutrition/menu/index.md` for the active cards (run `python3 -m coach
recipes render` first if `check --only recipe_index_fresh` fails).

## 2. Take the one exceptions line

If the check-in already asked the food-exceptions question (`/check-in`,
Food field c), use that answer. Otherwise ask it once, as the only
question before the plan:

> Anything different about food next week? Who cooks which nights,
> office-day changes, meals out, anything in the house to use up?

"Nothing" is a complete answer: the plan is the template plus your picks.
Everything else in this skill is yours to decide; anything you assume
(an estimate for a meal out, a pick for an open slot) is stated in the
presentation, where the athlete can correct it in their reply.

## 3. Draft

Write `.coach/drafts/meal-plan-<window start>.json` in the C34 draft
shape (`docs/design/coach-contract.md`):

- **`span`**: the window, `{"start", "end"}`; default the week the
  template showed.
- **`exceptions`**: one per change the athlete named. A slot change is
  `{"date", "slot", "entry", "note"}` and replaces everything the
  template puts in that slot that day, anchors included; an office-day
  change is `{"date", "office": true|false}`. An entry is
  `{"recipe", "variations", "covered_by", "lock"}`, or
  `{"cover", "kcal", "protein_g"}` for a meal someone else decides (your
  estimate, stated in the presentation), or `{"skip": true}`.
- **`assignments`**: a pick for every open slot and every pool slot,
  from active cards. An assignment adds to its slot, so a protein
  top-up on a low-protein covered night is an assignment beside the
  cover. Use `lock` with a reason for a day-locked entry (a post-run
  lunch that must be quick). A meal-kit box meal is a recipe with
  `covered_by` set to the provider: counted, not shopped. A box meal
  with no card is a cover entry with the box's numbers.
- **`use_up`**: each item the athlete named, `{"item", "qty", "unit"}`
  with the item spelt as the cards spell it. Plan those items into
  meals early in the window.
- **`notes`**: batch-cook days, timing cues.

How to pick: protein first (the anchors cover part of the floor; spread
the rest over the day's meals), then calories toward the target, then
variety and what the athlete likes to eat. A card with `servings` above
1 fills that many slots from one batch; schedule the cook day in
`notes`. Variations stack only when they change different ingredients.

## 4. Dry run and fix the flags

Run `python3 -m coach meals build --input .coach/drafts/meal-plan-<id>.json
--dry-run`. It writes nothing and returns the plan (`data.plan`) and its
rendered page (`data.rendered`). Fix the draft and re-run until no
`block` flag remains:

| Flag | Severity | What to do |
| --- | --- | --- |
| `recipe_unknown`, `variation_unknown` | block | Correct the slug or variation name, or pick another card. |
| `variation_conflict` | block | Keep one of the two variations. |
| `slot_open` | warn | Add an assignment; leave it open only on purpose (say so). |
| `protein_below_floor` | warn | Add a top-up or swap a meal; present any that remain. |
| `kcal_off_target` | warn | Adjust portions or picks; present any that remain, with the reason. |
| `recipe_benched` | warn | Pick an active card, unless the athlete asked for it. |
| `use_up_unmatched`, `units_mixed` | warn | Match the item's spelling and unit to the card's. |
| `no_target` | warn | Say the days are checked against protein only; `/goals` or the next reading fixes it. |

## 5. Present

Show, in one message:

1. The week: the "## The week" table from the dry run's
   `data.rendered` (one column per slot, day totals; covered entries
   marked *(covered)*, anchors *(anchor)*, locked entries 🔒 with the
   reason), and the pool table above it in loose style, where the pool
   is the contract.
2. The flags that remain, one line each.
3. The shopping summary: the Buy count by aisle, and the "check you
   have" staples with the amounts needed.
4. Every assumption you made (cover estimates, picks you chose).
5. One closing line naming what "go" does: build, approve and render
   the plan, and, only when `shopping_issue = true` in
   `[nutrition.template]`, post the shopping list as a GitHub issue.

Presenting and writing never happen in the same turn. A tweak in the
reply means a revised draft, a new dry run and a new presentation.

## 6. On "go"

1. `python3 -m coach meals build --input .coach/drafts/meal-plan-<id>.json`
2. `python3 -m coach meals approve <id>`
3. `python3 -m coach meals render <id>`
4. Only when `shopping_issue = true`: `python3 -m coach meals shopping
   <id> --format issue`. Write the returned `body` to
   `.coach/shopping-<id>.md` with the Write tool, then run
   `gh issue create --title "<title>" --body-file .coach/shopping-<id>.md`,
   so the shell never expands the body's text. Otherwise give the
   athlete `meals shopping <id>` (markdown) inline if they want the
   list in the chat.

Then close out: remind the athlete that logging (in the nutrition app, if
used) stays the ground truth, and that the next `/check-in` asks what in
the plan didn't work.
