---
name: recipes
description: Use when the athlete wants to manage their recipe bank — add a recipe (from a link, from a description, or by sourcing candidates online against their goals), edit or bench one, review the bank, or run the first-time food interview. Triggers include "/recipes", "add this recipe", "save this to my menu", "find me some high-protein lunches", "build me a recipe bank", "I'm bored of my meals", "bench/remove that recipe".
---

# Recipe bank

Own the athlete's recipe bank: `nutrition/menu/` — one card per recipe
plus `index.md`. This skill adds, edits, benches, and sources recipes;
`/meal-plan` consumes them. The card and index format is defined in
**`reference/recipe-cards.md`** — follow it exactly; shopping-list
arithmetic in `/meal-plan` depends on it. Online sourcing follows
**`reference/recipe-sources.md`**.

## 1. Read the context

Read `profile.md` (Nutrition & goals, Food & eating, the training week)
and `nutrition/menu/index.md` if it exists. Everything this skill does
is **goal-aware**: adds and sweeps serve the athlete's current phase and
targets. If Nutrition & goals is missing or TBD, send the athlete to
`/goals` before building a bank around numbers that don't exist.

When reading the index, spot-check it against the card filenames in
`nutrition/menu/` — flag drift to the athlete rather than trusting
either side (see the same-write rule below).

## 2. First run — the food interview

If `profile.md` has no Food & eating section or `nutrition/menu/`
doesn't exist, interview first — one question at a time, and **skip
anything already on file; only ask what's missing**: likes, dislikes,
allergies/intolerances; staples always in the house; cooking appetite
(assemble-only ↔ batch-cook ↔ cook most days); how they shop (weekly
online order, weekly in person, ad hoc top-ups); standing coverage
(meal kit, canteen, family dinners, regular meals out); and plan style
(loose ↔ strict — see `/meal-plan`).

Write/refresh the Food & eating section with the athlete's confirmation.

Then **seed the bank**: draft cards for what the athlete already eats
and likes (macros estimated per the card format), slot by slot, snacks
included; offer a sourcing sweep (mode 3 below) to fill thin slots.
Create `index.md` with the slot notes that came out of the interview
(coverage, per-slot priorities).

## 3. Adding recipes — three modes

Whatever the mode, **no card is ever written unseen** (approval rules
below), every card follows `reference/recipe-cards.md`, and every write
updates `index.md` in the same operation.

**From an exact link.** Fetch the URL, extract the structured recipe
data (`reference/recipe-sources.md`), normalise into a draft card, show
the athlete the **full card**, adjust, then write on approval. Meal-kit
recipe pages (Gousto etc.) import the same way — tag `meal-kit` plus
the provider. If the provider doesn't publish shareable pages, ask the
athlete for the essentials off the app instead (name, per-serving
macros, servings) and card it from those.

**From a description.** "A high-protein traybake I can batch" — draft
the card yourself, or source candidates online if the athlete wants
real published recipes. Show the full card; write on approval.

**Sourcing sweep.** "Build me a bank" / "find me better lunches" —
derive the brief from the profile (phase, targets, dislikes, cooking
appetite, slots that need depth), search per
`reference/recipe-sources.md`, and present a **shortlist table** of
~5–8 candidates: name, source, per-serving kcal/protein, prep effort,
and one line on why it fits the brief. The athlete picks; only picked
candidates become cards (each still shown before writing, batched is
fine).

## 4. Editing and benching

- **Edit**: adjust any part of a card (quantities, macros, variations,
  tags) with the athlete; keep `name` = filename; update the index row
  if a listed field changed.
- **Bench**: set `status: benched` — never delete. Benched recipes keep
  their history and can come back; `/meal-plan` ignores them. Un-bench
  by flipping status back.
- If a change makes a recipe into a genuinely different dish, that's a
  new card, not an edit.

## 5. Bank review

On demand ("is my bank any good?") — and suggest one after `/goals`
changes the phase: check the active cards against the current targets
(enough protein-dense options per slot? kcal budgets realistic for the
phase? slots with fewer than 3 active options?), then offer benches and
a sweep to fill gaps. `/meal-plan` also runs a light version of this at
the start of each planning run.

## Rules that always apply

- **Same-write rule:** any card create/edit/bench updates `index.md`
  in the same operation.
- **Exact quantities, no ranges** — ranges become named variations.
- **Provenance:** sourced cards record the URL in `source`.
- **All four macros on every card**, `estimated` or `published`.
- Sustainable food only — no extreme-restriction recipes.
