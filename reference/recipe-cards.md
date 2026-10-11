# Recipe cards and the index: the bank format

The contract between `/recipes` (which writes the bank) and `/meal-plan`
(which plans from it). Shopping-list arithmetic reads the structured part
of every card, so follow it exactly.

## Layout

- **`nutrition/menu/<slug>.md`**: one card per recipe. The file name's
  slug (lowercase letters, digits and hyphens) is the recipe's identity.
- **`nutrition/menu/index.md`**: the selection index. `recipes render`
  writes it from the cards; never edit it by hand.

All commands below run from the workspace root as
`python3 -m coach recipes <command>`.

## A card has three parts

1. **The data block.** TOML inside an HTML comment at the very top, so
   GitHub hides it. The first line is exactly `<!-- coach:card` and the
   block ends at the first line that is exactly `-->`. The coach writes
   it with the Write or Edit tool; scripts never rewrite it. (The one
   exception is `recipes convert --apply`, which writes each old card's
   block once, with a backup.) The TOML must never contain `-->`.
2. **The rendered region**, between `<!-- coach:begin card <slug> -->`
   and `<!-- coach:end card <slug> -->`: the title, the stats table, the
   ingredient list and the variations. `recipes render` writes it from
   the data block. Never edit it by hand; `coach check` fails a region
   that differs from a fresh render.
3. **Prose**: `## Method` (numbered steps), or `## What to order` on an
   eat-out card, plus any notes. Nothing parses the prose. A trivial
   snack needs none.

## The data block

```toml
schema_version = 1
title = "Chicken + rice bowl"
slots = ["lunch"]
servings = 1
prep = "assemble"
time_min = 5
status = "active"
nutrition = "estimated"
tags = ["post-workout"]

[per_serving]
kcal = 610
protein_g = 50
carbs_g = 55
fat_g = 18

[[ingredients]]
qty = 170
unit = "g"
item = "chicken breast, cooked"
aisle = "meat-fish"

[[variations]]
name = "light"
label = "half the rice pouch"
changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]
delta = {kcal = -105, protein_g = 0, carbs_g = -22, fat_g = 0}
```

| Key | Required | Values |
| --- | --- | --- |
| `schema_version` | yes | `1` |
| `title` | yes | the name shown on the card and in the index |
| `slots` | yes | one or more of the configured slots: `breakfast`, `lunch`, `dinner`, `snack` |
| `servings` | yes | portions the ingredient quantities make, a whole number |
| `prep` | yes | `assemble`, `quick-cook`, `cook` or `eat-out` |
| `time_min` | yes | active minutes |
| `status` | yes | `active` or `benched` |
| `nutrition` | yes | `published` (the source's numbers) or `estimated` |
| `source` | no | the URL when the recipe came from a page |
| `tags` | no | free-form, lowercase with hyphens: `post-workout`, `batch`, `meal-kit` |
| `[per_serving]` | yes | `kcal`, `protein_g`, `carbs_g`, `fat_g` for one serving |
| `[[ingredients]]` | yes, except on `eat-out` cards | `qty`, `unit`, `item`, `aisle` |
| `[[variations]]` | no | `name`, `label`, `changes`, `delta` |

### Macros

All four macros are required. Use the source's per-serving numbers when it
publishes them (`nutrition = "published"`); otherwise estimate from the
ingredients (`nutrition = "estimated"`). Keep `published` through unit or
portion conversions, since the numbers still describe the food. Drop to
`estimated` the moment you swap, add or remove an ingredient. Rough is
fine (the athlete's food log is the ground truth), but no field is ever
left out.

`recipes validate` checks that `kcal` agrees with the macros, using the
Atwater general factors: 4 kcal per gram of protein and of carbohydrate,
9 per gram of fat (FAO 2003, *Food energy: methods of analysis and
conversion factors*). It warns when `kcal` is more than 10 % away from
that sum and fails above 20 % (`macro_sum_warn_pct` and
`macro_sum_fail_pct` in `[nutrition.bank]`). Small gaps are normal:

- UK and EU labels count fibre at 2 kcal per gram on top of carbohydrate,
  which excludes fibre (Regulation (EU) 1169/2011, Annex XIV). A card
  copied from such a label sits about 2 kcal per gram of fibre above the
  sum: 8 g of fibre adds 16 kcal, under 3 % of a 600 kcal meal.
- US labels count fibre inside total carbohydrate, so the sum can run a
  little above the label's kcal.

A card outside the bands is nearly always a typo or a per-recipe figure
copied as per-serving.

### Protein density

`recipes validate` warns when a card has less protein per 100 kcal than
`min_protein_per_100kcal` sets for any of its slots. The default is 5 g
for breakfast, lunch and dinner, and 0 (not checked) for snacks. It is a
heuristic to catch protein-light meals, not an evidence-based cut-off.
Set a slot to `0.0` to switch it off.

### Ingredients

- **Exact quantities, no ranges.** "½ to 1 pouch" is banned; a quantity
  choice is a named variation instead.
- `unit` is `g`, `ml`, `each`, `tsp` or `tbsp`. Count packaged things as
  `each` and put the package in the item: `1 each "microwave basmati rice
  pouch"`.
- `item` is lowercase. Together with `unit` it is the shopping-list key,
  so spell an ingredient the same way on every card ("eggs", not "egg"
  on one card and "large eggs" on another).
- `aisle` is one of `[nutrition.bank] aisles` (default: `produce`,
  `bakery`, `meat-fish`, `dairy-eggs`, `chilled`, `frozen`,
  `tins-jars-dry`, `snacks`, `drinks`, `household`). The shopping list
  walks the aisles in that order.

### Variations

A variation is a named, exact change to the base recipe.

- `name`: short, lowercase (`light`, `+egg`). Plans refer to it as
  `recipe (variation)`.
- `label`: what the athlete reads: "half the rice pouch".
- `changes`: the ingredient changes. A negative `qty` reduces or removes
  an ingredient the card already has, in that ingredient's unit. A
  positive `qty` adds to one, or adds a new item, which must carry its
  `aisle`.
- `delta`: the change to the per-serving macros. `recipes validate`
  checks it against 4/4/9 like the card, but never flags a gap under
  20 kcal, since small deltas round badly.

A plan may stack variations that change different ingredients
(`recipe (+banana, +PB)`), and the deltas add. Two variations that change
the same ingredient never stack. A change with no exact delta is not a
variation: it is a new card.

## Special cards

Everything a plan can slot is a card, however small:

- **Tiny snacks**: ingredients and macros, no method.
- **Eat-out fallbacks**: `prep = "eat-out"`, no ingredients, and a
  `## What to order` section in the prose. With no ingredients they never
  reach a shopping list.
- **Meal-kit recipes** (Gousto, HelloFresh and similar): imported like any
  other card, tagged `meal-kit` plus a provider tag (`gousto`), with the
  ingredients the provider publishes. The **plan** decides whether a meal
  is covered by the box, not the tag: a meal-kit recipe cooked outside a
  box shops normally.

## The index

`recipes render` writes `nutrition/menu/index.md` whole: one section per
configured slot, in config order, each a table of the cards that fit it
(a card with several slots appears in each). Active cards come first,
then benched ones. The planner reads the index to choose recipes, then
reads only the chosen cards.

Notes that are not recipes (standing coverage such as "dinners covered by
family, top up protein on light nights", or a slot's priority such as
"breakfast must be fast or it gets skipped") go in
`[nutrition.bank.slot_notes]` in `config.toml`. The index prints each one
under its slot.

## Commands

| Command | Use it to |
| --- | --- |
| `recipes list [--slot S] [--status S]` | list the cards |
| `recipes show SLUG` | read one card's data |
| `recipes validate [SLUG]` | check the schema, the macro sum, protein density, variations and aisles; exit 1 on a fail |
| `recipes render [SLUG] [--dry-run]` | rewrite the cards' rendered regions and the index from the data blocks |
| `recipes import --html FILE [--url URL]` | read a saved recipe page's schema.org JSON-LD into a draft card, with flags to resolve |
| `recipes draft --input FILE` | turn a draft (`{"slug", "card", "prose"}`) into the full card text, validated, for the athlete to approve |
| `recipes convert --parse` / `--apply --input FILE` | convert old YAML cards (below) |

`recipes import` and `recipes draft` write nothing: the coach shows the
athlete the card and writes the file only after approval. After any card
is written or edited, run `recipes render`, then `recipes validate`.
`python3 -m coach check` runs the same checks as `recipe_cards`,
`recipe_render_fresh` and `recipe_index_fresh`.

## Converting old cards

Cards written before this format open with YAML front matter (`---`) and
fail `recipes validate`. To convert a bank:

1. `recipes convert --parse` reads every old card and returns a draft per
   card plus a review table: title, macros, ingredient count, ingredient
   lines it could not read, the aisle it guessed for each ingredient, the
   variations whose `changes` need filling in, and notes (front matter it
   could not read, for one). It also reads the old index's slot notes
   (the prose under each slot heading) and returns them as
   `slot_notes_toml`, listed under the card table. It writes nothing.
2. Walk the table with the athlete: add the unread ingredients exactly,
   correct the aisles, and give each variation its `changes`. Save the
   corrected drafts as `{"cards": [{"slug": ..., "card": {...}}]}`.
3. Add the slot notes to `config.toml` under
   `[nutrition.bank.slot_notes]` (`slot_notes_toml` is the text to add),
   with any the athlete wants changed. The rendered index takes its slot
   notes from there, so a note left out is dropped; `--apply` warns about
   each one config lacks.
4. `recipes convert --apply --input FILE` copies the old cards and the
   old index to `.coach/backups/<UTC timestamp>/`, writes each card as a
   data block plus a rendered region plus its original prose (the Method
   and What to order sections keep their exact text), then re-renders the
   index once no old cards remain. Try it first with `--dry-run`.

## Example card

`nutrition/menu/chicken-rice-bowl.md`:

```markdown
<!-- coach:card
schema_version = 1
title = "Chicken + rice bowl"
slots = ["lunch"]
servings = 1
prep = "assemble"
time_min = 5
status = "active"
nutrition = "estimated"
tags = ["post-workout"]

[per_serving]
kcal = 610
protein_g = 50
carbs_g = 55
fat_g = 18

[[ingredients]]
qty = 170
unit = "g"
item = "chicken breast, cooked"
aisle = "meat-fish"

[[ingredients]]
qty = 1
unit = "each"
item = "microwave basmati rice pouch"
aisle = "tins-jars-dry"

[[ingredients]]
qty = 80
unit = "g"
item = "mixed salad leaves"
aisle = "produce"

[[ingredients]]
qty = 6
unit = "each"
item = "cherry tomatoes"
aisle = "produce"

[[variations]]
name = "light"
label = "half the rice pouch"
changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]
delta = {kcal = -105, protein_g = 0, carbs_g = -22, fat_g = 0}

[[variations]]
name = "+egg"
label = "add a boiled egg"
changes = [{item = "eggs", qty = 1, unit = "each", aisle = "dairy-eggs"}]
delta = {kcal = 70, protein_g = 6, carbs_g = 0, fat_g = 5}
-->
<!-- coach:begin card chicken-rice-bowl -->
# Chicken + rice bowl

| | |
| --- | --- |
| **Per serving** | 610 kcal · 50 g P · 55 g C · 18 g F |
| **Slot** | lunch |
| **Prep** | assemble · 5 min · serves 1 |
| **Nutrition** | estimated |
| **Tags** | post-workout |
| **Status** | active |

## Ingredients
- 170 g chicken breast, cooked
- 1 microwave basmati rice pouch
- 80 g mixed salad leaves
- 6 cherry tomatoes

## Variations
- **light** — half the rice pouch · −105 kcal · −22 g C
- **+egg** — add a boiled egg · +70 kcal · +6 g P · +5 g F
<!-- coach:end card chicken-rice-bowl -->

## Method
1. Heat the rice pouch (90 seconds).
2. Bowl everything and season.
```
