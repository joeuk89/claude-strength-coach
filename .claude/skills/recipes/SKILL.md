---
name: recipes
description: Use when the athlete wants to manage their recipe bank — add a recipe (from a link, by transcribing what they already eat, or by sourcing candidates online against their goals), design a new one collaboratively, improve an existing one, edit or bench one, review the bank, or run the first-time food interview. Triggers include "/recipes", "add this recipe", "save this to my menu", "find me some high-protein lunches", "build me a recipe bank", "improve this recipe", "make my chilli better", "what can I do with all these bananas", "invent me a recipe", "I'm bored of my meals", "bench/remove that recipe".
---

# Recipe bank

Own the athlete's recipe bank: `nutrition/menu/`, one card per recipe
plus `index.md`. This skill adds, edits, benches and sources recipes;
`/meal-plan` consumes them. Cards follow **`reference/recipe-cards.md`**
exactly (`/meal-plan`'s shopping list depends on it); online sourcing
follows **`reference/recipe-sources.md`**.

## 1. Read the context

Read `profile.md` (Nutrition & goals, Food & eating, the training week),
the output of `python3 -m coach nutrition status` (phase and protein
numbers) and `nutrition/menu/index.md` if it exists. Everything here
is **goal-aware**: adds and sweeps serve the current phase and targets.
If `nutrition status` says `enabled: false`, send the athlete to
`/goals` first.

Then run `python3 -m coach recipes validate`. If it reports old YAML
cards, convert the bank first (`reference/recipe-cards.md`, "Converting
old cards"): run `recipes convert --parse`, walk the review table with
the athlete, write its slot notes to `config.toml` under
`[nutrition.bank.slot_notes]` (the output's `slot_notes_toml`), then run
`recipes convert --apply --input <file>`. If
`python3 -m coach check --only recipe_index_fresh,recipe_render_fresh`
fails, run `python3 -m coach recipes render` before reading the index.

## 2. First run — the food interview

If `profile.md` has no Food & eating section or `nutrition/menu/`
doesn't exist, interview first — one question at a time, and **skip
anything already on file; only ask what's missing**: likes, dislikes,
allergies/intolerances; staples always in the house; cooking appetite
(assemble-only ↔ batch-cook ↔ cook most days); how they shop (weekly
online order, weekly in person, ad hoc top-ups); standing coverage
(meal kit, canteen, family dinners, regular meals out); and plan style
(loose ↔ strict — see `/meal-plan`). **If Food & eating is already
complete, don't open an interview at all — confirm it's current and go
straight to seeding.**

Write/refresh the Food & eating section with the athlete's confirmation.

Then **seed the bank**: draft cards for what the athlete already eats
and likes (macros estimated per the card format), slot by slot, snacks
included; offer a sourcing sweep (below) to fill thin slots.
Record the slot notes that came out of the interview (coverage,
per-slot priorities) in `config.toml` under
`[nutrition.bank.slot_notes]`, then run `python3 -m coach recipes
render`, which writes `index.md` with them.

## 3. Adding and shaping recipes — five modes

Pick the mode from what the athlete asks for, then read
[modes.md](modes.md) for its steps:

- **From an exact link** — import a published page or a meal-kit recipe.
- **Transcribe** — card a meal they already eat, as described.
- **Design** — build a new recipe together from a rough brief.
- **Improve** — make an existing card better, shown as a before/after.
- **Sourcing sweep** — a shortlist of candidates for thin slots.

Whatever the mode, **no card is ever written unseen** (presentation
rules below), every card follows `reference/recipe-cards.md`, and every
card write is followed by `python3 -m coach recipes render`, then
`recipes validate`.

**The research mandate.** Whenever you are inventing or shaping a
recipe — design, improve, sweep — online research per
`reference/recipe-sources.md` is **compulsory**, not optional. Recipes
drafted purely from memory come out bland, with sparse instructions;
real published recipes bring flavour, technique, and sensible
variations. Exempt: link imports (the link *is* the research),
transcriptions of meals the athlete already eats, and trivial
assemble-only cards with no method. Rule of thumb: if you'd be writing
a Method section from your own head, research first.

**Presenting for approval.** A single new card is shown **in full** —
the rendered part of `recipes draft`'s text — since the athlete is
approving exact quantities and macros. Drafts that `recipes draft`
fails never reach the athlete; fix them first. An edit or
improve shows a **before/after of the changed lines**, not the whole
card. A batch of 2+ cards gets a **summary table first** — name, core
ingredients, prep type, active time, per-serving kcal/protein — with
any card shown in full on request before the batch is written. Nothing
is written until the athlete approves.

## 4. Editing and benching

- **Edit**: adjust any part of a card's data block (quantities, macros,
  variations, tags) with the athlete, then run `recipes render`. The
  file name is the slug; never edit the rendered region or `index.md`. Making a recipe *better* (not just
  correcting it) is the **Improve** mode above — research included.
- **Bench**: set `status = "benched"` in the data block and run
  `recipes render` — never delete. Benched recipes keep
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

- **Render after every write:** any card create, edit or bench is
  followed by `recipes render`; `index.md` and each card's rendered
  region are never hand-edited.
- **Exact quantities, no ranges** — ranges become named variations.
- **Provenance:** sourced cards record the URL in `source`.
- **All four macros on every card**, `estimated` or `published`.
- Sustainable food only — no extreme-restriction recipes.
