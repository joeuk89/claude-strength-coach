# Sourcing recipes online

How `/recipes` finds and imports recipes without any paid API.

## The mechanism

1. **WebSearch**, scoped to reputable recipe sites (below), with a query
   built from the athlete's brief and goals — e.g.
   `site:bbcgoodfood.com high protein chicken traybake` or a plain query
   plus "recipe".
2. **WebFetch** the candidate page and extract the embedded
   **schema.org/Recipe JSON-LD** (a `<script type="application/ld+json">`
   block on most major recipe sites). It carries name, ingredient lines,
   instructions, servings (`recipeYield`), and usually per-serving
   nutrition (`nutrition` → calories, proteinContent, …).
3. **Normalise** into a draft card per `reference/recipe-cards.md`:
   convert to metric quantities, per-serving amounts, record the URL in
   `source`, and set `nutrition: published` if the site's numbers were
   used — but per that doc's rule, an ingredient swap drops it back to
   `estimated` (a pure unit/portion conversion keeps `published`).
4. If a page has **no structured data**, fall back to reading the page
   text; mark `nutrition: estimated` and sanity-check the estimate
   against the ingredient list.

## Reliable sources

Sites that consistently ship structured recipe data and credible
per-serving nutrition (not exhaustive — any site with schema.org/Recipe
works):

- **BBC Good Food** — broad, tested, good nutrition data, metric.
- **EatingWell** — nutrition-forward, dietitian-reviewed.
- **Budget Bytes** — cheap, simple, per-serving costs and macros.
- **Serious Eats** — technique-heavy; nutrition sometimes missing.
- **RecipeTin Eats** — reliable data, weeknight-friendly.
- **Skinnytaste** — macro-labelled, lighter recipes.

Prefer sites the athlete's region/units match; convert otherwise.

## Fit the athlete, always

Before searching, derive the brief from `profile.md`:

- **Phase & targets** (Nutrition & goals): a cut wants high-satiety,
  protein-dense, lower-kcal meals; a bulk wants easy extra calories;
  maintenance wants balance. Respect the protein floor.
- **Food & eating**: hard-filter dislikes and allergies — never present
  a candidate that violates them; match cooking appetite (don't offer
  hour-long cooks to an assemble-only athlete) and slot budgets.
- **Training week**: portable/quick options for pre/post-session slots.

## Quality checks before drafting a card

- Nutrition is **per serving**, not per recipe — check `recipeYield`.
- Ingredient quantities are exact and shoppable after conversion.
- Sanity-check published kcal against the macros (4/4/9); flag weird
  numbers rather than copying them.
