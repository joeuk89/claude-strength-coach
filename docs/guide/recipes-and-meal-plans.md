# Recipes and meal plans

This doc covers `/recipes`, which keeps your recipe bank, and
`/meal-plan`, which turns your standing eating week and a one-line list
of exceptions into a week's plan and a shopping list. Read it once
`/goals` has set your nutrition up (see [Nutrition](nutrition.md)) and
you want help with what to eat.

Both skills need nutrition enabled: if `nutrition status` says
`enabled: false`, the coach sends you to `/goals` first. The division of
labour is fixed. `/goals` owns the strategy and its numbers, `/recipes`
owns the bank, `/meal-plan` owns the standing template, and your
nutrition app, if you use one, owns the calorie target. Targets that
look wrong go back to `/goals`; a bank that needs work goes to
`/recipes`.

## The recipe bank

The bank (see [the glossary](../../CONTEXT.md)) is `nutrition/menu/`:
one card per recipe, named by its slug, plus `index.md`, which
`recipes render` writes and you never edit. `/meal-plan` selects from
the active cards. The full card format is in
[reference/recipe-cards.md](../../reference/recipe-cards.md); the
shopping-list arithmetic reads it, so the coach follows it exactly.

### What a card looks like

A card has three parts:

1. **A hidden data block** at the top: TOML inside an HTML comment, so
   GitHub hides it. The coach writes it after your approval; scripts
   never rewrite it.
2. **A rendered region** between `coach:begin card` and `coach:end card`
   markers: the title, the stats table, the ingredient list and the
   variations. `recipes render` writes it from the data block, and
   `coach check` fails a region that differs from a fresh render.
3. **Prose**: a numbered `## Method`, or `## What to order` on an eat-out
   card. Nothing parses it, and a trivial snack needs none.

The example card from the reference, shortened:

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

[[variations]]
name = "light"
label = "half the rice pouch"
changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]
delta = {kcal = -105, protein_g = 0, carbs_g = -22, fat_g = 0}
-->
<!-- coach:begin card chicken-rice-bowl -->
# Chicken + rice bowl

| | |
| --- | --- |
| **Per serving** | 610 kcal · 50 g P · 55 g C · 18 g F |
| **Slot** | lunch |
| **Prep** | assemble · 5 min · serves 1 |
...
<!-- coach:end card chicken-rice-bowl -->

## Method
1. Heat the rice pouch (90 seconds).
2. Bowl everything and season.
```

The rules the coach keeps on every card:

| Field | Rule |
| --- | --- |
| slug | the file name, lowercase letters, digits and hyphens; the recipe's identity |
| `slots` | one or more of your configured slots: `breakfast`, `lunch`, `dinner`, `snack` |
| `status` | `active` or `benched` |
| `prep`, `time_min` | `assemble`, `quick-cook`, `cook` or `eat-out`; active minutes, not elapsed time |
| `[per_serving]` | all four macros, always; `nutrition` says `published` (the source's numbers) or `estimated` |
| `[[ingredients]]` | exact quantities in `g`, `ml`, `each`, `tsp` or `tbsp`, a lowercase item spelt the same on every card, and an aisle |
| `[[variations]]` | a named, exact change with its macro delta; a range such as "half to one pouch" becomes a variation, never a range |
| `source` | the URL on every sourced card |

Rough macros are fine, since your food log is the ground truth, but no
macro is ever left out. An ingredient swap drops `published` to
`estimated`; a unit or portion conversion keeps it. Eat-out cards have no
ingredients and never reach a shopping list. Meal-kit recipes are tagged
`meal-kit` plus the provider; the plan decides whether a box covers a
meal, not the tag.

### First run: the food interview and seeding

With no bank yet, `/recipes` collects a **Food & eating** section for
`profile.md`: likes, dislikes, allergies and intolerances, household
staples, cooking appetite, shopping pattern, office-day pattern, who
decides each meal, and plan style. The coach reuses what your profile and
config already say and asks every missing field together in one message.
It shows the proposed section, and any slot notes for
`[nutrition.bank.slot_notes]`, before writing either.

Then it seeds the bank: cards for what you already eat and like, slot by
slot, snacks included, and offers a sourcing sweep to fill thin slots.
Every card is presented for approval before it is written.

### Five ways to add or shape a recipe

| Mode | You say | What the coach does |
| --- | --- | --- |
| From a link | "add this recipe", a URL | saves the page, imports its structured recipe data, resolves the import flags, shows the full card |
| Transcribe | "card my usual porridge" | captures the meal as you describe it and estimates macros; no research |
| Design | "something for all these bananas" | checks the index for near-duplicates (benched ones too), asks what you have on hand if the brief is ingredient-driven, brings 2–3 real published starting points, iterates with you |
| Improve | "make my chilli better" | researches published versions, shows a before/after of the changed lines, records the primary source |
| Sourcing sweep | "find me better lunches", "build me a bank" | derives a brief from your profile and phase, searches reputable sites, shows a shortlist of about 5–8 candidates; only the ones you pick become cards |

Research is compulsory whenever the coach invents or shapes a recipe
(design, improve, sweep). Recipes drafted from memory come out bland with
sparse instructions. Link imports, transcriptions and trivial assemble-only
cards are exempt. The sourcing procedure and the sites that ship reliable
structured data are in
[reference/recipe-sources.md](../../reference/recipe-sources.md). Before
searching, the coach filters hard on your dislikes and allergies and
matches your cooking appetite and the current phase.

An import runs `python3 -m coach recipes import --html <file> --url <url>`
on a saved page, which writes nothing and returns a draft card with flags
to resolve: ingredient lines it could not read exactly, missing
nutrition, a doubtful per-serving yield, a kcal figure that disagrees
with the macros, a guessed slot or aisle, and uncertain active time. On
the `jsonld-plain.html` fixture it returns, for example:

```json
[{"code": "slot_guessed", "message": "the page names no meal slot; dinner is a guess"},
 {"code": "time_missing", "message": "the page gives no time; set active minutes before accepting time_min = 0"},
 {"code": "per_serving_doubt", "message": "check the nutrition is per serving (yield '2 or 4 servings', 580 kcal)"}]
```

### Approval

No card is ever written unseen:

- **One new card** is shown in full, as `recipes draft` renders it, since
  you are approving exact quantities and macros. A draft that fails
  `recipes draft` never reaches you.
- **An edit or improvement** shows a before/after of the changed lines.
- **A batch of two or more** gets a summary table first (name, core
  ingredients, prep type, active time, per-serving kcal and protein),
  with any card shown in full on request.

After every write the coach runs `recipes render`, then
`recipes validate`.

### Editing, benching and reviewing the bank

To edit, the coach adjusts the data block with you and renders. Making a
recipe better rather than correcting it is the improve mode, research
included. A change that makes a different dish is a new card.

To bench, the coach sets `status = "benched"` and renders; it never
deletes a card. Benched recipes keep their history, `/meal-plan` ignores
them, and flipping the status back un-benches one.

Ask "is my bank any good?" for a bank review, and the coach suggests one
after `/goals` changes your phase. It checks the active cards against the
current targets: enough protein-dense options per slot, kcal budgets
realistic for the phase, slots with fewer than 3 active options. Then it
offers benches and a sweep to fill the gaps. `/meal-plan` runs a light
version at the start of each planning run.

### Commands and checks

| Command | Use it to |
| --- | --- |
| `recipes list [--slot S] [--status S]` | list the cards |
| `recipes show SLUG` | read one card's data |
| `recipes validate [SLUG]` | check schema, macro sum, protein density, variations and aisles; exit 1 on a fail |
| `recipes render [SLUG] [--dry-run]` | rewrite the rendered regions and the index from the data blocks |
| `recipes import --html FILE [--url URL]` | read a saved page into a draft card; writes nothing |
| `recipes draft --input FILE` | turn a draft into the full card text, validated; writes nothing |
| `recipes convert --parse` / `--apply --input FILE` | convert old YAML cards |

`recipes validate` applies the bank checks in `[nutrition.bank]` of
`config.toml`. Left commented, the defaults apply:

- `aisles`: the shopping walk order; every ingredient names one. The
  default runs produce, bakery, meat-fish, dairy-eggs, chilled, frozen,
  tins-jars-dry, snacks, drinks, household.
- `min_protein_per_100kcal`: warns when a card has less protein per
  100 kcal for one of its slots. The default is 5 g for breakfast, lunch
  and dinner and 0 (not checked) for snacks. A heuristic, not an
  evidence-based cut-off.
- `macro_sum_warn_pct` (10) and `macro_sum_fail_pct` (20): how far `kcal`
  may sit from 4 × protein + 4 × carbs + 9 × fat before validation warns
  or fails. Data-entry checks that catch typos, not coaching numbers.
- `[nutrition.bank.slot_notes]`: one line printed under each slot in the
  index, such as a breakfast that must be fast or it gets skipped. Notes
  explain the standing week but never create coverage in a plan.

`python3 -m coach check` runs the same checks as `recipe_cards`,
`recipe_render_fresh` and `recipe_index_fresh`. On the `recipes-stale`
fixture, a card whose kcal is 27 % off its macro sum fails validation,
and the check reports:

```text
chicken-rice-bowl: the rendered region differs from its data block; run python3 -m coach recipes render
```

### Converting old YAML cards

Cards written in the older format open with YAML front matter and fail
`recipes validate` with a message naming `recipes convert`. The coach
runs `recipes convert --parse`, which writes nothing and returns a draft
per card plus a review table: title, macros, ingredient count, lines it
could not read, the aisle it guessed for each ingredient, variations
whose changes need filling in, and notes. It also reads the old index's
slot notes and returns them as TOML for `[nutrition.bank.slot_notes]`.

The coach walks the table with you, saves the corrected drafts, adds the
slot notes to `config.toml` (a note left out is dropped), then runs
`recipes convert --apply --input <file>`, trying `--dry-run` first. The
apply backs up the old cards and index to `.coach/backups/`, writes each
card as a data block plus a rendered region plus its original prose, and
re-renders the index once no old cards remain.

## Meal plans

A week's plan is your **standing template** plus that week's **plan
exceptions** (see [the glossary](../../CONTEXT.md)). Your effort per plan
is one exceptions line and one approval. The coach drafts the exceptions
and its picks for open slots, the `meals` commands do the arithmetic, and
you say "go".

### The standing template

Your typical eating week lives once in `config.toml` as
`[nutrition.template]`. From
[config.example.toml](../../config.example.toml):

```toml
[nutrition.template]
slots = ["breakfast", "lunch", "dinner", "snack"]
office_days = ["tue", "thu"]
staples = ["eggs", "rolled oats", "olive oil"]
# plan_style = "loose"
kcal_tolerance_pct = 15
shopping_issue = false

[[nutrition.template.standing]]
days = ["daily"]
slot = "breakfast"
recipe = "overnight-oats"

[[nutrition.template.standing]]
days = ["office"]
slot = "lunch"
pool = ["chicken-rice-bowl"]

[[nutrition.template.standing]]
days = ["mon", "tue", "wed", "thu"]
slot = "dinner"
cover = "family"
kcal = 700
protein_g = 35
```

| Key | Meaning |
| --- | --- |
| `slots` | the meal slots in day order; anchors and cards use these names |
| `office_days` | weekday ids; `"office"` and `"home"` in a days list mean these days and the rest |
| `staples` | ingredients kept in by default, spelt as the cards spell them; the shopping list moves them to "check you have" |
| `plan_style` | `loose` (the pool is fixed, the week table is a suggestion) or `strict` (a dated menu); left out, loose when a standing row covers dinner |
| `kcal_tolerance_pct` | how far a day may sit from the calorie target before the plan flags it |
| `shopping_issue` | `true` offers the approved shopping list as a GitHub issue with tick boxes |
| `[[nutrition.template.standing]]` | one row per slot and set of days with exactly one of `recipe` (a card), `pool` (cards to pick from each week) or `cover` (someone else decides, with its estimated `kcal` and `protein_g`); two rows may not fill the same slot on the same day |

Slots the template leaves empty are open: the coach picks a card for
each from the bank. Your protein anchors from `/goals` fill their slots
as fixed blocks.

### First-run template setup

The first `/meal-plan` run, when `meals template` exits 5 for want of the
table, maps your profile's Food & eating section to TOML and asks only
the unresolved planning details, together. The coach also offers each
anchor an optional recipe link, using only an active card you confirm
describes that food and serving. It shows the exact TOML, what each
standing row means in plain words, and the profile edit that swaps the
four planning fields (staples, office days, standing coverage, plan
style) for one pointer line to the config. It writes both only on your
approval, then runs `config validate` and
`check --only nutrition_template`.

This is the only time the skill asks more than the exceptions line and
the approval. Later changes to your typical week are edits to this
table, made the same way. If `nutrition/menu/` does not exist, the coach
runs the `/recipes` interview and seeding first; it never plans from an
empty bank.

### The one exceptions line

If the last check-in's Food field already asked about next week's food,
the coach uses that answer. Otherwise it asks once:

> Anything different about food next week? Who cooks which nights,
> office-day changes, meals out, anything in the house to use up?

"Nothing" is a complete answer: the plan is the template plus the coach's
picks. An exception replaces everything the template puts in that slot
that day, anchors included. Anything the coach assumes, such as an
estimate for a meal out or a pick for an open slot, is stated in the
presentation, where you can correct it.

### The draft and the dry run

The coach writes `.coach/drafts/meal-plan-<window start>.json`
(gitignored): the span, the exceptions you named, a pick for every open
and pool slot, the items to use up, and notes such as batch-cook days.
It picks protein first (the anchors cover part of the floor, the rest is
spread over the day's meals), then calories toward the target, then
variety and what you like. A card with `servings` above 1 fills that many
slots from one batch.

Then it runs `python3 -m coach meals build --input <draft> --dry-run`,
which writes nothing and returns the plan and its rendered page, and
fixes the draft until no blocking flag remains:

| Flag | Severity | What it means |
| --- | --- | --- |
| `recipe_unknown`, `variation_unknown` | block | a slug or variation name that is not in the bank |
| `variation_conflict` | block | two variations that change the same ingredient |
| `anchor_shopping_unknown` | warn | an anchor with no recipe link; its macros count but its ingredients are missing from shopping |
| `slot_open` | warn | a slot with no item, or a pool slot with no pick; left open only on purpose |
| `protein_below_floor` | warn | a day under the protein floor |
| `kcal_off_target` | warn | a day further from the calorie target than `kcal_tolerance_pct` |
| `recipe_benched` | warn | a benched card, used only if you asked for it |
| `use_up_unmatched`, `units_mixed` | warn | a use-up item spelt or measured differently from the cards |
| `no_target` | warn | no calorie target on file: days are checked against protein only |

The calorie target is the newest reading's app target with an app, or
`kcal_target` without one. The protein floor is `floor_g` from
`[nutrition.protein]`. The skill never computes a calorie target.

### What you see

The coach presents, in one message: the week table (and, in loose style,
the pool table above it, where the pool is the contract), the flags that
remain, the shopping summary with the buy count by aisle and the staples
to check, every assumption it made, and one closing line naming what
"go" does. From the valid fixture's plan page:

```markdown
## Pool

| Meal | Count | Per serving | Make |
| --- | --- | --- | --- |
| [Chicken + rice bowl](../menu/chicken-rice-bowl.md) (light) | 2 | 505 kcal · 50 g P | 2 |
| [Overnight oats](../menu/overnight-oats.md) | 7 | 440 kcal · 30 g P | 7 |
| [Turkey chilli](../menu/turkey-chilli.md) | 4 | 620 kcal · 48 g P | 1 × batch of 4 |

## The week

| Day | Breakfast | Lunch | Dinner | Snack | Total |
| --- | --- | --- | --- | --- | --- |
| Mon 12 Oct | [Overnight oats](../menu/overnight-oats.md) | [Turkey chilli](../menu/turkey-chilli.md) | family *(covered)* | Whey shake *(anchor)* | 2110 kcal · 148 g P |
| Tue 13 Oct · office | [Overnight oats](../menu/overnight-oats.md) | [Chicken + rice bowl](../menu/chicken-rice-bowl.md) (light) 🔒 post-run, must be quick | family *(covered)* | Whey shake *(anchor)* | 1995 kcal · 150 g P ⚠ |
| Wed 14 Oct | [Overnight oats](../menu/overnight-oats.md) | [Turkey chilli](../menu/turkey-chilli.md) | out *(covered)* — birthday | Whey shake *(anchor)* | 2310 kcal · 153 g P |
```

Covered entries are marked *(covered)*, anchors *(anchor)*, and locked
entries carry a padlock and the reason. A day with a flag carries a
warning mark on its total, and the flags are listed in full:

```markdown
- warn · `kcal_off_target`: Tue 13 Oct: 1995 kcal is 17% under the 2400 kcal target (tolerance 15%).
```

Presenting and writing never happen in the same turn. A tweak in your
reply means a revised draft, a new dry run and a new presentation.

### What "go" does

1. `meals build --input <draft>` writes `data/nutrition/plans/<id>.json`,
   the id being the window's first day.
2. `meals approve <id>` stamps your approval and a hash that any later
   edit breaks; it refuses a plan with unresolved blocking flags.
3. `meals render <id>` writes `nutrition/plans/<id>.md`.
4. Only when `shopping_issue = true`: `meals shopping <id> --format issue`
   returns a title and a body with tick boxes under aisle headings and a
   "Check you have" section, and the coach opens it as a GitHub issue
   with `gh issue create`. Otherwise `meals shopping <id>` gives the list
   as markdown in the chat if you want it. An unapproved plan is refused
   (exit 3).

The shopping list covers items with a recipe and no `covered_by`, batches
by each card's servings, takes use-up items off the matching line, lists
staples under "Check you have", and walks the aisles in config order. A
card edited after the build changes nothing in the plan or the list.

### The plan files

| File | What it is |
| --- | --- |
| `.coach/drafts/meal-plan-<id>.json` | the coach's draft, gitignored |
| `data/nutrition/plans/<id>.json` | the plan: days, items with snapshotted macros, pool, shopping, flags, approval |
| `nutrition/plans/<id>.md` | the rendered page |

Neither plan file is hand-edited: to change a plan, the coach changes the
draft and builds again. `meals show <id>` tells you whether the approval
still holds, `meals validate <id>` checks the arithmetic, and
`coach check` reports a page out of date with its data:

```text
nutrition/plans/2026-10-12.md was edited by hand or is out of date; it is never hand-edited. Run python3 -m coach meals render 2026-10-12
```

### After the week

The next `/check-in`'s Food field asks whether anything in the plan did
not work, and, since a template exists, next week's food exceptions. The
coach notes the learnings for the next `/meal-plan` run and feeds the
exceptions straight into it. Recipe-bank changes belong in `/recipes`,
not the check-in.

The nutrition app, if you use one, stays the ground truth: the plan says
what to cook and buy, the log says what you ate, and the app's numbers
are what the check-in records.
