---
name: recipes
description: Use when the athlete wants to manage their recipe bank — add a recipe (from a link, by transcribing what they already eat, or by sourcing candidates online against their goals), design a new one collaboratively, improve an existing one, edit or bench one, review the bank, or run the first-time food interview. Triggers include "/recipes", "add this recipe", "save this to my menu", "find me some high-protein lunches", "build me a recipe bank", "improve this recipe", "make my chilli better", "what can I do with all these bananas", "invent me a recipe", "I'm bored of my meals", "bench/remove that recipe".
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
(loose ↔ strict — see `/meal-plan`). **If Food & eating is already
complete, don't open an interview at all — confirm it's current and go
straight to seeding.**

Write/refresh the Food & eating section with the athlete's confirmation.

Then **seed the bank**: draft cards for what the athlete already eats
and likes (macros estimated per the card format), slot by slot, snacks
included; offer a sourcing sweep (below) to fill thin slots.
Create `index.md` with the slot notes that came out of the interview
(coverage, per-slot priorities).

## 3. Adding and shaping recipes — five modes

Whatever the mode, **no card is ever written unseen** (presentation
rules below), every card follows `reference/recipe-cards.md`, and every
write updates `index.md` in the same operation.

**The research mandate.** Whenever you are inventing or shaping a
recipe — design, improve, sweep — online research per
`reference/recipe-sources.md` is **compulsory**, not optional. Recipes
drafted purely from memory come out bland, with sparse instructions;
real published recipes bring flavour, technique, and sensible
variations. Exempt: link imports (the link *is* the research),
transcriptions of meals the athlete already eats, and trivial
assemble-only cards with no method. Rule of thumb: if you'd be writing
a Method section from your own head, research first.

**From an exact link.** Fetch the URL, extract the structured recipe
data (`reference/recipe-sources.md`), normalise into a draft card, show
the athlete the **full card**, adjust, then write on approval. Meal-kit
recipe pages (Gousto etc.) import the same way — tag `meal-kit` plus
the provider. If the provider doesn't publish shareable pages, ask the
athlete for the essentials off the app instead (name, per-serving
macros, servings) and card it from those.

**Transcribe.** The athlete describes a meal they already eat — "card
my usual porridge" — capture it as described, estimate macros, no
research needed. If they want it made *better*, that's an improve.

**Design.** The athlete has a rough brief — "something for all these
bananas", "I need a new bagel recipe" — and you build the recipe
together:

1. Check `index.md` for near-duplicates first and surface them —
   including **benched** ones, where un-bench-and-improve may be the
   cheaper path. Don't build what the bank already has.
2. If the brief is **ingredient-driven** (using up what's in the
   house), read `nutrition/pantry.md` — quantities on hand shape the
   design. Skip the pantry for abstract briefs; `/meal-plan` handles
   shopping later.
3. Research: bring back **2–3 real published starting points** that
   fit the brief and the profile.
4. Iterate with the athlete — pick a base, adapt it to their macros,
   equipment, and cooking appetite; name the variations.
5. Land the result through the normal presentation rules.

**Improve.** The athlete points at an existing card and wants it
better — tastier, fuller instructions, variations. Research published
versions of the dish, then present the improvement as a
**before/after** against the current card. Record the primary research
URL in `source`. An ingredient change re-estimates macros (`published`
drops to `estimated`, per the card format). If the improvement changes
the dish's identity, that's a new card — bench the old one.

**Sourcing sweep.** "Build me a bank" / "find me better lunches" —
derive the brief from the profile (phase, targets, dislikes, cooking
appetite, slots that need depth), search per
`reference/recipe-sources.md`, and present a **shortlist table** of
~5–8 candidates: name, source, per-serving kcal/protein, prep effort,
and one line on why it fits the brief. The athlete picks; only picked
candidates become cards.

**Presenting for approval.** A single new card is shown **in full** —
the athlete is approving exact quantities and macros. An edit or
improve shows a **before/after of the changed lines**, not the whole
card. A batch of 2+ cards gets a **summary table first** — name, core
ingredients, prep type, active time, per-serving kcal/protein — with
any card shown in full on request before the batch is written. Nothing
is written until the athlete approves.

## 4. Editing and benching

- **Edit**: adjust any part of a card (quantities, macros, variations,
  tags) with the athlete; keep `name` = filename; update the index row
  if a listed field changed. Making a recipe *better* (not just
  correcting it) is the **Improve** mode above — research included.
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
- **Notion mirror:** if `notion-map.json` exists and covers recipes,
  card writes (create/edit/bench) mirror to Notion per
  `reference/notion-sync.md`; if no Notion MCP is connected this
  session, the sync is pending — `/notion-sync` catches it up.
- **Exact quantities, no ranges** — ranges become named variations.
- **Provenance:** sourced cards record the URL in `source`.
- **All four macros on every card**, `estimated` or `published`.
- Sustainable food only — no extreme-restriction recipes.
