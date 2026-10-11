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
(`[nutrition]`; `python3 -m coach nutrition status` returns them), and
`/recipes` owns the recipe bank. This skill owns the standing template
(`[nutrition.template]`). The nutrition app, if the athlete uses one,
owns the calorie target; without one, `kcal_target` does. This skill
picks food from the bank to those numbers and never computes a calorie
target. Targets look wrong → `/goals`; the bank needs work → `/recipes`.

Requires nutrition to be set up: if `nutrition status` says `enabled:
false`, run `/setup` or `/goals` first. If `meals template` exits 5 for
want of `[nutrition.template]`, run **Set up the standing template**
below once before planning. If `nutrition/menu/` doesn't exist, invoke
the `/recipes` skill now for its interview and seeding flow, then come
back: never plan from an empty bank.

**The files:** the plan is `data/nutrition/plans/<id>.json` (written by
`meals build`; the id is the window's first day), rendered to
`nutrition/plans/<id>.md` by `meals render` — never hand-edited: change
the draft and build again. Your draft is
`.coach/drafts/meal-plan-<id>.json` (gitignored).

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

If `/check-in`'s Food field already asked about next week's food, use
that answer. Otherwise ask once, as the only question before the plan:

> Anything different about food next week? Who cooks which nights,
> office-day changes, meals out, anything in the house to use up?

"Nothing" is a complete answer: the plan is the template plus your picks.
Everything else in this skill is yours to decide; anything you assume
(an estimate for a meal out, a pick for an open slot) is stated in the
presentation, where the athlete can correct it in their reply.

## 3. Draft, dry run, fix the flags

Write `.coach/drafts/meal-plan-<window start>.json` in the C34 draft
shape: the span, the exceptions the athlete named, a pick for every open
and pool slot, the items to use up, and notes. Then run `python3 -m
coach meals build --input .coach/drafts/meal-plan-<id>.json --dry-run`:
it writes nothing and returns the plan (`data.plan`) and its rendered
page (`data.rendered`). Fix the draft and re-run until no `block` flag
remains. Read [draft.md](draft.md) for each draft field, how to pick,
and what to do with each flag.

## 4. Present

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

## 5. On "go"

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
