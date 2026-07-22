# Recipe cards & index — the bank format

The contract between `/recipes` (which writes the bank) and `/meal-plan`
(which plans from it). Follow it exactly — shopping-list arithmetic
depends on it.

## Layout

- **`nutrition/menu/<slug>.md`** — one card per recipe. The filename slug
  is the recipe's identity; there are no meal codes.
- **`nutrition/menu/index.md`** — the selection index (see below).

## Card frontmatter

```yaml
---
name: chicken-rice-bowl   # must equal the filename slug
slot: [lunch]             # list — a meal may fit several slots:
                          # breakfast | lunch | dinner | snack
kcal: 610                 # per serving
protein: 50               # grams per serving
carbs: 55                 # grams per serving
fat: 18                   # grams per serving
nutrition: estimated      # estimated | published (source site's numbers)
prep: assemble            # assemble | quick-cook | cook
time: 5                   # active minutes
servings: 1               # portions the ingredient quantities make
source: null              # URL when sourced online; null if not
tags: []                  # freeform, e.g. [post-workout, portable, batch]
status: active            # active | benched
---
```

All four macro fields are **required**. Use the source's published
per-serving numbers when available (`nutrition: published`); otherwise
estimate from the ingredients (`nutrition: estimated`). Rough is fine —
the athlete's food log is ground truth — but fields are never blank.

## Card body

### Ingredients

Exact quantities for the stated `servings`. **No ranges** — "½–1 pouch"
is banned; a quantity choice is a named variation instead. Every line
must be shoppable: quantity + unit + item.

### Method

Numbered steps. **Optional for trivial items** — a two-ingredient snack
needs no method section.

### Variations

**Named exact deltas** on the base recipe. Each variation states its
ingredient changes and macro deltas:

```markdown
## Variations
- **light** — ½ rice pouch instead of full · −105 kcal · −22 g carbs
- **+egg** — add 1 boiled egg · +70 kcal · +6 g protein · +5 g fat
```

Plans reference `recipe (variation)`; shopping-list maths applies the
ingredient delta. A variation with no exact delta is not a variation —
it's a new card.

## Special cards

Everything the plan can slot is a card, however small:

- **Tiny snacks** — ingredients + macros, no method.
- **Eating-out fallbacks** — a **"What to order"** section instead of
  ingredients, tag `eat-out`. With no ingredient lines they are
  naturally excluded from shopping lists.
- **Meal-kit recipes** (Gousto and similar) — imported like any other
  card, tagged `meal-kit` plus a provider tag (e.g. `gousto`), with the
  ingredient list included when the provider publishes it. Exclusion
  from shopping lists is decided by the **plan** (a pool entry marked
  covered by the box), not by the tag — a meal-kit recipe cooked
  outside a box shops normally.

## The index — `nutrition/menu/index.md`

The planner reads the index to *select* recipes, then reads only the
chosen cards. Format:

- One section per slot (Breakfasts / Lunches / Dinners / Snacks) with a
  table, one row per card:

```markdown
| Recipe | kcal | Protein | Prep | Status |
| --- | --- | --- | --- | --- |
| [Chicken + rice bowl](chicken-rice-bowl.md) | 610 | 50 g | assemble | active |
```

  (A card with several slots gets a row in each section.)
- **Slot notes** under each section heading for things that aren't
  recipes: standing coverage ("dinners covered by family — top up
  protein on low-protein nights"), per-slot priorities ("breakfast must
  be fast or it gets skipped"), eat-out context.

### Same-write rule (hard)

Any operation that creates, edits, or benches a card **updates
`index.md` in the same operation**. Any skill that reads the index
spot-checks it against the card filenames and flags drift to the
athlete instead of silently trusting either side.

## Example card

`nutrition/menu/chicken-rice-bowl.md`:

```markdown
---
name: chicken-rice-bowl
slot: [lunch]
kcal: 610
protein: 50
carbs: 55
fat: 18
nutrition: estimated
prep: assemble
time: 5
servings: 1
source: null
tags: [post-workout]
status: active
---

# Chicken + rice bowl

## Ingredients
- 170 g pre-cooked chicken breast
- 1 pouch (250 g) microwave basmati rice
- 80 g mixed salad leaves
- 6 cherry tomatoes

## Method
1. Heat the rice pouch (90 sec).
2. Bowl everything; season.

## Variations
- **light** — ½ rice pouch instead of full · −105 kcal · −22 g carbs
- **+egg** — add 1 boiled egg · +70 kcal · +6 g protein · +5 g fat
```

Minimal snack card, `nutrition/menu/yoghurt-honey-nuts.md`:

```markdown
---
name: yoghurt-honey-nuts
slot: [snack]
kcal: 250
protein: 20
carbs: 22
fat: 9
nutrition: estimated
prep: assemble
time: 2
servings: 1
source: null
tags: []
status: active
---

# Greek yoghurt + honey + nuts

## Ingredients
- 200 g 0% Greek yoghurt
- 1 tsp (7 g) honey
- 15 g almonds
```
