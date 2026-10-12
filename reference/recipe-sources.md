# Sourcing recipes online

How `/recipes` finds and imports recipes without any paid API.

Research here is **compulsory whenever the agent invents or shapes a
recipe** (the design, improve, and sweep modes) — memory-drafted
recipes come out bland with sparse instructions. Only link imports,
transcriptions of meals the athlete already eats, and trivial
no-method cards skip it.

## The mechanism

1. **WebSearch**, scoped to reputable recipe sites (below), with a query
   built from the athlete's brief and goals — e.g.
   `site:bbcgoodfood.com high protein chicken traybake` or a plain query
   plus "recipe".
2. **Save the candidate page** to `.coach/drafts/` (gitignored), e.g.
   `mkdir -p .coach/drafts && curl -sL -A "Mozilla/5.0" "<url>" -o .coach/drafts/<slug>.html`.
   Some meal-kit sites (Gousto, for one) add their recipe data with
   JavaScript, so a plain download has none. For those, ask the athlete
   to open the page in a browser and save it ("Save Page As…"), then
   use that file.
3. **Import it:** `python3 -m coach recipes import --html <file> --url
   <url>`. It reads the page's embedded **schema.org/Recipe JSON-LD**
   (a `<script type="application/ld+json">` block on most major recipe
   sites) and returns a draft card in the format of
   `reference/recipe-cards.md`, the method as prose, and flags to
   resolve before the athlete sees the card:
   - `unparsed_ingredients`: lines it could not turn into an exact
     quantity, unit and item (ranges, "to taste", compound lines such as
     "2 red and 2 yellow peppers"). Enter each food with its own exact
     quantity, or drop the line.
   - `missing_nutrition`: the page has no per-serving macros. Estimate
     them from the ingredients and set `nutrition = "estimated"`.
   - `per_serving_doubt`: an ambiguous yield ("2 or 4 servings") or a
     figure too large for one serving. Check the numbers are per serving.
   - `macro_sum`: the published kcal disagrees with 4/4/9. Find out why
     rather than copying it.
   - `active_time_uncertain`: `time_min` is a proposal (prepTime, or 0),
     and `source_times` holds the page's raw times. Read the method and
     set the real active minutes; totalTime is elapsed time, not active.
   - `time_missing`: the page gives no time. Set active minutes from the
     method.
   - `incompatible_ingredient_units`: one food appears in units the
     importer does not add together, such as tbsp and ml, or tsp and tbsp
     (`items`, with source `lines`). Convert them into one exact unit per
     item; the card fails validation until you do.
   - `summed_ingredient_lines`: lines for the same food and unit were
     added into one quantity (`items`, with source `lines`). Check the
     lines buy the same product: "beef, diced" and "beef, minced" do not,
     so split them into two items.
   - `slot_guessed`, `servings_missing`, `aisle_guessed`: fields it had
     to guess. Check each one.
   `reference/recipe-cards.md` ("Reviewing an import") explains what the
   importer already normalised.
   Then normalise: metric quantities, per-serving amounts for `servings`,
   and `nutrition = "published"` only while the site's numbers still
   describe the food. Per `reference/recipe-cards.md`, an ingredient swap
   drops it to `estimated`; a pure unit or portion conversion keeps
   `published`.
4. **Draft the card:** save `{"slug": ..., "card": ..., "prose": ...}` to
   `.coach/drafts/` and run `python3 -m coach recipes draft --input
   <file>`. It returns the full card text, validated, to show the
   athlete.
5. If a page has **no structured data** (`recipes import` exits 1 saying
   so), read the page text instead, mark `nutrition = "estimated"`, and
   sanity-check the estimate against the ingredient list.

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
- **Food & eating** (`reference/record-formats.md`): use **Likes**;
  hard-filter **Dislikes** and **Allergies/intolerances** — never present
  a candidate that violates them. Match **Cooking appetite** and slot
  budgets (assemble-only means no hour-long cooks).
- **Training week**: portable/quick options for pre/post-session slots.

## Quality checks before drafting a card

- Nutrition is **per serving**, not per recipe — check `recipeYield`
  (`recipes import` flags a doubtful yield).
- Ingredient quantities are exact and shoppable after conversion.
- Published kcal agrees with the macros (4/4/9): `recipes import` and
  `recipes validate` flag a gap; explain weird numbers rather than
  copying them.
