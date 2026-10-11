# The five ways to add or shape a recipe

Read this once the athlete has said which one they want. Every mode
follows the presentation rules in `SKILL.md` step 3, and every card
follows `reference/recipe-cards.md`.

**From an exact link.** Save the page and run `python3 -m coach recipes
import --html <file> --url <url>` (`reference/recipe-sources.md`),
resolve its flags, turn the draft into the card text with `recipes
draft --input <file>`, show the athlete the **full card**, adjust, then
write it on approval. Meal-kit
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
   house), ask the athlete what they have on hand and how much —
   quantities shape the design. Skip this for abstract briefs;
   `/meal-plan` handles shopping later.
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
derive the brief from the profile (phase, targets, dislikes,
allergies/intolerances, cooking appetite, slots that need depth), search per
`reference/recipe-sources.md`, and present a **shortlist table** of
~5–8 candidates: name, source, per-serving kcal/protein, prep effort,
and one line on why it fits the brief. The athlete picks; only picked
candidates become cards.
