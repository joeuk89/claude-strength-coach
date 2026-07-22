# Meal-Plan Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-file menu bank with per-recipe cards + index, add a `/recipes` bank-management skill with online sourcing, and make `/meal-plan` produce exact meal pools and arithmetic shopping lists.

**Architecture:** Two repos. Framework work (Tasks 1–6) happens in **`~/personal/workout-template`** (the public template); instance chores (Tasks 7–9) happen in **`~/personal/workout`** (Joe's private instance) after merging. The card/index format lives in one canonical reference doc; both skills point at it. Spec: `docs/superpowers/specs/2026-07-22-meal-plan-redesign-design.md` (template repo) — read it first.

**Tech Stack:** Markdown skills + reference docs only. No code. Verification is grep checks and read-throughs.

**Hard rules for every task:**
- **Never commit without human approval.** Each task ends: stage, show the diff, STOP. Commit only after Joe approves, then move to the next task.
- **Framework files stay generic** — no athlete-specific content (no supermarket names, family arrangements, specific staples, "Joe"). Athlete data lives in instance files only.
- The prose style to match is the existing skills' voice (see `.claude/skills/meal-plan/SKILL.md` before rewriting it): second-person coach addressing an agent, tight, wrapped ~76 cols, bold key rules.
- Content blocks below are complete drafts. You may tighten wording, but every **normative rule** in them (schemas, formats, MUST/never statements) must survive verbatim in meaning.

---

### Task 1: `reference/recipe-cards.md` — the canonical bank format

**Repo:** `~/personal/workout-template`
**Files:**
- Create: `reference/recipe-cards.md`

- [ ] **Step 1: Write the file** with this content:

````markdown
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
````

- [ ] **Step 2: Verify format self-consistency**

Run: `cd ~/personal/workout-template && grep -c "same operation" reference/recipe-cards.md`
Expected: `1` (same-write rule present). Read the file once through: the two example cards must use every frontmatter field and demonstrate a variation delta and a no-method snack.

- [ ] **Step 3: Stage and stop for human review**

```bash
cd ~/personal/workout-template
git add reference/recipe-cards.md
git diff --staged   # show to Joe; commit only after approval
# After approval: git commit -m "Add reference/recipe-cards.md: canonical card + index format"
```

---

### Task 2: `reference/recipe-sources.md` — sourcing guidance

**Repo:** `~/personal/workout-template`
**Files:**
- Create: `reference/recipe-sources.md`

- [ ] **Step 1: Write the file** with this content:

````markdown
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
   `source`, set `nutrition: published` if the site's numbers were used.
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
````

- [ ] **Step 2: Verify genericity**

Run: `cd ~/personal/workout-template && grep -in "joe\|tesco\|m&s\|mum\|huel\|gazpacho" reference/recipe-sources.md`
Expected: no output.

- [ ] **Step 3: Stage and stop for human review**

```bash
cd ~/personal/workout-template
git add reference/recipe-sources.md
git diff --staged   # show to Joe; commit only after approval
# After approval: git commit -m "Add reference/recipe-sources.md: no-API online sourcing guidance"
```

---

### Task 3: New `/recipes` skill

**Repo:** `~/personal/workout-template`
**Files:**
- Create: `.claude/skills/recipes/SKILL.md`

- [ ] **Step 1: Write the file** with this content:

````markdown
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
````

- [ ] **Step 2: Verify cross-references and genericity**

Run: `cd ~/personal/workout-template && grep -c "recipe-cards.md" .claude/skills/recipes/SKILL.md && grep -c "recipe-sources.md" .claude/skills/recipes/SKILL.md && grep -in "joe\|tesco\|m&s\|mum\|huel\|gazpacho" .claude/skills/recipes/SKILL.md`
Expected: two counts ≥ 1, then no grep matches.

- [ ] **Step 3: Stage and stop for human review**

```bash
cd ~/personal/workout-template
git add .claude/skills/recipes/SKILL.md
git diff --staged   # show to Joe; commit only after approval
# After approval: git commit -m "Add /recipes skill: recipe-bank lifecycle with online sourcing"
```

---

### Task 4: Rewrite `/meal-plan` skill

**Repo:** `~/personal/workout-template`
**Files:**
- Modify: `.claude/skills/meal-plan/SKILL.md` (full rewrite; keep the frontmatter `description` as is)

- [ ] **Step 1: Rewrite the body** with this content (frontmatter unchanged):

````markdown
# Meal planning & shopping list

Turn the nutrition targets on file into real food: plan the athlete's
meals and snacks for a chosen window (default: the week ahead) and build
a shopping list for **exactly** what the plan needs. Plan only the
**gaps** — meals already covered (meal kit, canteen, eating out, family
dinners) are declared up front and treated as fixed blocks.

**Division of labour:** `/goals` decides the strategy and records it in
`profile.md` (Nutrition & goals). MacroFactor, if the athlete uses it,
holds the live daily kcal/macro targets. `/recipes` owns the recipe
bank. This skill composes food to the targets from the bank — it never
computes TDEE, never revises targets, and never edits recipes beyond
status changes agreed in the opening review. If the targets look wrong,
send the athlete to `/goals`; if the bank needs work, `/recipes`.

Requires `profile.md` with a real Nutrition & goals section — if it's
missing or still TBD, run `/setup` or `/goals` first.

## The files

- **`nutrition/menu/`** — the recipe bank: one card per recipe plus
  `index.md`. Format: `reference/recipe-cards.md`. Owned by `/recipes`.
- **`nutrition/YYYY-MM-DD.md`** — one dated plan per run: exact meal
  pool, day-by-day table, and the shopping list.
- **`profile.md` → "Food & eating"** — what this skill never re-asks:
  preferences, staples, shopping style, standing coverage, and the
  plan-style preference (loose ↔ strict).

**No bank?** If `nutrition/menu/` doesn't exist, invoke the `/recipes`
skill now — run its interview and seeding flow, then come back here and
continue. Never plan from an empty bank, and never dead-end the athlete.

## 1. Read the context

Read `profile.md` (Nutrition & goals, Food & eating, the training week),
`routine/program.md` (training days, double days, rest days — count
cardio), `nutrition/menu/index.md`, and the newest dated plan in
`nutrition/`. Spot-check the index against the card filenames; flag
drift.

## 2. Review the last plan (feedback loop)

Open with a quick review of the most recent dated plan: what got eaten,
skipped, swapped, disliked? Agree any card status changes (bench /
un-bench) and apply them — card + index in the same operation. Then a
**bank-fit check** against the current phase: if `/goals` has changed
the phase since the bank was last touched and the bank skews wrong for
it (e.g. entering a deficit with a carb-heavy, low-satiety bank), say
so and offer a `/recipes` sweep before planning.

## 3. Current targets

- **MacroFactor users:** ask for today's kcal and protein targets off
  the dashboard, and whether calorie shifting is configured.
- **Without MacroFactor:** use the calorie/protein targets in
  `profile.md`.
- Sanity-check either against Nutrition & goals. A big mismatch (wrong
  phase, stale targets) means the strategy needs attention — flag it
  and point at `/goals` before planning to a number you don't trust.

## 4. Coverage for the window

Confirm the window (default: the week ahead), then what's already
covered — which day × meal slots, and what with. Confirm which days are
training / double / rest days from the routine (don't assume — weeks
have one-off changes), and ask about anything unusual: travel, meals
out, guests.

**Meal-kit boxes:** if any coverage is a recipe box (Gousto etc.), ask
the athlete to link the provider's recipe pages for the meals in this
window's box, and import any that aren't in the bank yet — same flow as
`/recipes`' exact-link add, tagged `meal-kit` + provider. No shareable
pages? Ask for name + per-serving macros off the app instead. Box meals
then appear in the pool and day table like any other recipe — linked
and counted in the day's macros — but marked **covered**, which
excludes them from the shopping list (their ingredients arrive in the
box).

## 5. Compose the plan

Select from **active** cards via the index (read only the chosen cards
in full). Compose each day to land close to the targets.

**The exact-pool rule — both plan styles.** Every plan fixes the
window's exact meal pool: each recipe — or named variation — with its
count, e.g. `chicken-rice-bowl ×2 · cod-traybake ×2 · omelette (+egg)
×1`. The pool is the plan's contract; its **non-covered** entries are
the sole input to the shopping list (covered entries — meal-kit box
meals — count toward macros but aren't shopped). Never leave a slot as
an unresolved either/or.

- **Strict style:** every pool item is pinned to a day × slot in the
  day table.
- **Loose style:** the day table is a **suggested** assignment from the
  pool; the athlete swaps freely within a slot — **except day-locked
  entries** (a post-run lunch that must be quick, a pre-session snack),
  which are marked 🔒 with the reason. The pool table is the contract;
  the day table is advice.

Also:

- **Protein is the anchor.** Spread it across the day (~4 feeds is a
  good default; ~0.4 g/kg per meal is a heuristic, not dogma).
- **Train-day awareness:** bigger fuelling on double days, leaner rest
  days; calorie cycling if the profile opts in (carbs/kcal toward
  higher-output days, protein flat). Timing notes only where they
  matter — around training slots.
- **Batch cooking:** a card with `servings` > 1 covers multiple slots —
  schedule the cook day and the leftover day explicitly, and count the
  recipe once per serving in the pool.
- Favour variety and meals the athlete wants to eat. Close-enough
  daily, corrected weekly, beats gram-perfect and abandoned.

## 6. Shopping list — arithmetic, never assumption

Derive from the pool's **non-covered** entries: per-serving ingredient
quantities × counts, with variation deltas applied, aggregated across
the window. Two sections, both exact:

1. **Buy** — non-staple ingredients with exact quantities (and pack
   sizes where they help).
2. **Staples — confirm you have enough** — every staple the pool
   needs, each with the required amount (e.g. "eggs: 14"). Ask which
   are running short and promote those to Buy.

Nothing the pool needs may be missing from both sections. Shape the
list to the athlete's shopping style (one basket for a weekly online
shop; grouped by category in person; staples-vs-extras for ad hoc).
If a grocery integration is connected, offer to push the list.

## 7. Write and close out

Write `nutrition/YYYY-MM-DD.md`:

```markdown
# Meal plan — <window start> → <window end>

**Targets used:** ~X kcal · ~Y g protein (source: MacroFactor dashboard /
profile) · plan style: loose/strict

## This week's pool
| Meal | Count | Per serving |
| --- | --- | --- |
| [Chicken + rice bowl](menu/chicken-rice-bowl.md) | 2 | 610 kcal · 50 g P |
| [Cod traybake](menu/cod-traybake.md) (light) | 2 | 420 kcal · 38 g P |
| [Chorizo rice](menu/chorizo-rice.md) | 2 | 650 kcal · 32 g P · **covered — Gousto box** |
(The contract. Counts are exact; variations named; covered entries are
in the plan and the macros but not the shopping list.)

## The week
| Day | Type | Covered | Breakfast | Lunch | Snacks |
| --- | --- | --- | --- | --- | --- |
| Mon | training | D: family | [Overnight oats](menu/overnight-oats.md) | [Chicken + rice bowl](menu/chicken-rice-bowl.md) 🔒 post-run — quick | … |
(Strict: assignments are fixed. Loose: suggested — swap within a slot
except 🔒 day-locked entries. Recipes always linked by full name.)

## Notes
Timing cues, batch-cook schedule, anything decided this run.

## Shopping list
### Buy
| Item | Quantity | Covers |
| --- | --- | --- |

### Staples — confirm you have enough
| Staple | Needed this week |
| --- | --- |
```

Then close out: apply any remaining card/index status changes agreed
this run; update Food & eating for any preference the athlete confirmed
changed; remind the athlete that logging (MacroFactor, if used) stays
the ground truth — the next `/check-in` reviews how the plan went.
````

- [ ] **Step 2: Verify the rewrite**

Run: `cd ~/personal/workout-template && grep -c "menu.md" .claude/skills/meal-plan/SKILL.md; grep -c "exact" .claude/skills/meal-plan/SKILL.md; grep -in "interview" .claude/skills/meal-plan/SKILL.md`
Expected: `0` for `menu.md` (the old path is gone — note `index.md` doesn't match this grep); `exact` count ≥ 4; `interview` appears at most once, only in the missing-bank pointer to `/recipes` (the interview itself must not live here).

- [ ] **Step 3: Stage and stop for human review**

```bash
cd ~/personal/workout-template
git add .claude/skills/meal-plan/SKILL.md
git diff --staged   # show to Joe; commit only after approval
# After approval: git commit -m "Rewrite /meal-plan: consume recipe bank, exact pools, arithmetic lists"
```

---

### Task 5: Cross-reference updates (CLAUDE.md, setup, check-in, README)

**Repo:** `~/personal/workout-template`
**Files:**
- Modify: `CLAUDE.md` (lines ~54, ~91, ~126–128)
- Modify: `.claude/skills/setup/SKILL.md` (line ~108)
- Modify: `.claude/skills/check-in/SKILL.md` (line ~104)
- Modify: `README.md` (line ~53)

- [ ] **Step 1: CLAUDE.md files table** — replace the `nutrition/` row:

Old:
```
| `nutrition/` | Meal planning: `menu.md` (the athlete's menu bank) and dated meal plans (`YYYY-MM-DD.md`). Created by `/meal-plan`. |
```
New:
```
| `nutrition/` | Meal planning: `menu/` (the recipe bank — one card per recipe plus `index.md`; format in `reference/recipe-cards.md`) and dated meal plans (`YYYY-MM-DD.md`). Bank managed by `/recipes`, plans by `/meal-plan`. |
```

- [ ] **Step 2: CLAUDE.md commands list** — after the `/meal-plan` bullet (line ~91), insert:

```
- **`/recipes`** — manage the recipe bank: add recipes (from a link, a
  description, or sourced online against the athlete's goals), edit or
  bench them, and run the first-time food interview.
```

- [ ] **Step 3: CLAUDE.md nutrition section** — replace (lines ~126–128):

Old:
```
- **`/meal-plan`** turns the targets into actual meals and a shopping
  list — planning *to* the numbers, never recomputing them. Plans and the
  athlete's menu bank live in `nutrition/`.
```
New:
```
- **`/meal-plan`** turns the targets into actual meals and a shopping
  list — planning *to* the numbers, never recomputing them. The recipe
  bank (managed by `/recipes`) and the plans live in `nutrition/`.
```

- [ ] **Step 4: setup/SKILL.md** — replace (line ~108):

Old:
```
(Filled by /meal-plan — food preferences and allergies, staples, cooking
appetite, shopping style, standing meal coverage, plan-style preference.)
```
New:
```
(Filled by /recipes — food preferences and allergies, staples, cooking
appetite, shopping style, standing meal coverage, plan-style preference.)
```

- [ ] **Step 5: check-in/SKILL.md** — replace (line ~104):

Old:
```
for the next `/meal-plan` run (menu-bank changes belong there, not here).
```
New:
```
for the next `/meal-plan` run (recipe-bank changes belong in `/recipes`,
not here).
```

- [ ] **Step 6: README.md** — after the `/meal-plan` bullet (line ~53–55), insert:

```
- **`/recipes`** — manage your recipe bank: add a recipe from a link or
  an idea, have the coach source new ones online that fit your goals,
  or bench the ones you're bored of.
```

- [ ] **Step 7: Verify no stale references**

Run: `cd ~/personal/workout-template && grep -rn "menu.md" CLAUDE.md README.md .claude/skills/`
Expected: no output (only `index.md` and `menu/` remain; note this grep's dot matches `menu/md` never — if it prints `recipe-cards.md` context lines referencing `index.md`, those are fine, but literal `menu.md` must be gone).

- [ ] **Step 8: Stage and stop for human review**

```bash
cd ~/personal/workout-template
git add CLAUDE.md README.md .claude/skills/setup/SKILL.md .claude/skills/check-in/SKILL.md
git diff --staged   # show to Joe; commit only after approval
# After approval: git commit -m "Wire /recipes and the card bank into framework docs"
```

---

### Task 6: Template-wide verification pass

**Repo:** `~/personal/workout-template`
**Files:** none (checks only; fix anything found, re-stage with the relevant task's commit)

- [ ] **Step 1: Genericity sweep over everything this plan touched**

Run: `cd ~/personal/workout-template && grep -rin "joe\b\|tesco\|m&s\|mum\|huel\|gazpacho\|charing" reference/recipe-cards.md reference/recipe-sources.md .claude/skills/recipes/SKILL.md .claude/skills/meal-plan/SKILL.md CLAUDE.md README.md`
Expected: no output.

- [ ] **Step 2: Meal-code sweep**

Run: `cd ~/personal/workout-template && grep -rn "B1\|L1\|S1\b" .claude/skills/ reference/recipe-cards.md`
Expected: no output — codes are dead everywhere.

- [ ] **Step 3: Cross-reference resolution**

Run: `cd ~/personal/workout-template && grep -l "recipe-cards.md" .claude/skills/recipes/SKILL.md .claude/skills/meal-plan/SKILL.md CLAUDE.md`
Expected: all three files listed.

- [ ] **Step 4: Read-through** — read `recipes/SKILL.md` and `meal-plan/SKILL.md` end to end once. Check: no contradiction with `reference/recipe-cards.md`; the interview lives only in `/recipes`; the exact-pool rule and two-section shopping list are stated in `/meal-plan`; both mention the same-write rule or point to the doc that does.

- [ ] **Step 5: Report findings to Joe** — nothing to stage if clean; if fixes were needed, present them as amendments to the relevant task's file and re-run that task's stage/review step.

---

### Task 7: Instance fresh start (Joe's repo)

**Repo:** `~/personal/workout`
**Files:**
- Delete: `nutrition/menu.md`, `nutrition/2026-07-21.md` (both untracked)
- Modify: `profile.md` (line ~170, Food & eating → Plan style)

**Note:** `profile.md` already has unrelated uncommitted modifications — show Joe the full diff and let him decide what gets committed together.

- [ ] **Step 1: Delete the old nutrition outputs**

```bash
cd ~/personal/workout
rm nutrition/menu.md nutrition/2026-07-21.md
ls nutrition/   # expected: empty (or only files Joe added since)
```

- [ ] **Step 2: Flip the plan style in profile.md**

Old:
```
- **Plan style:** **loose** — 2–3 macro-equivalent options per slot, not a
  strict named meal.
```
New:
```
- **Plan style:** **strict** — one named meal pinned to each day × slot;
  the weekly pool and shopping list are exact.
```

- [ ] **Step 3: Stage and stop for human review**

```bash
cd ~/personal/workout
git add profile.md
git status --short && git diff --staged   # deletions were untracked — nothing to stage for them
# After approval: git commit -m "Flip meal-plan style to strict; fresh-start the recipe bank"
```

---

### Task 8: Merge template into the instance

**Repo:** `~/personal/workout`

- [ ] **Step 1: Merge**

```bash
cd ~/personal/workout
git fetch template
git merge template/main -m "Merge template: /recipes skill, card bank, meal-plan rewrite"
```
Expected: clean merge (instance copies of the framework files are byte-identical to the template's pre-change state). If conflicts appear, STOP and show Joe — something drifted and needs eyes, don't resolve silently.

- [ ] **Step 2: Verify the instance matches**

```bash
cd ~/personal/workout
ls .claude/skills/recipes/ reference/recipe-cards.md reference/recipe-sources.md
diff .claude/skills/meal-plan/SKILL.md ~/personal/workout-template/.claude/skills/meal-plan/SKILL.md
```
Expected: files exist; diff is empty.

- [ ] **Step 3: Stop for human review** — a merge is already a commit; show Joe `git log --oneline -3` and the merged file list. (If he wants it unpicked: `git reset --hard ORIG_HEAD`.)

---

### Task 9: Update the auto-memory framework list

**Files:**
- Modify: `/Users/joeabousselam/.claude/projects/-Users-joeabousselam-personal-workout/memory/template-instance-split.md`

- [ ] **Step 1: Update the framework-file list** in the "How to apply" section:

Old:
```
- Framework files = CLAUDE.md, README.md, `.claude/settings.json`,
  `.claude/skills/{setup,new-program,check-in,goals,hevy-sync}/SKILL.md`,
  `reference/hevy-api.md`, `.env.example`. Edit them **in the template
```
New:
```
- Framework files = CLAUDE.md, README.md, `.claude/settings.json`,
  `.claude/skills/{setup,new-program,check-in,goals,hevy-sync,meal-plan,recipes}/SKILL.md`,
  `reference/hevy-api.md`, `reference/recipe-cards.md`,
  `reference/recipe-sources.md`, `.env.example`. Edit them **in the template
```

- [ ] **Step 2: Confirm with Joe** — memory files aren't in either repo; no staging. State plainly that the memory was updated and what changed.

---

## Acceptance (after all tasks)

From the spec's testing section — Joe runs these live, not the implementing agent:

1. `/recipes` on the fresh instance: interview skips everything already in Food & eating; bank seeded with cards + index; at least one link-sourced and one sweep-sourced recipe added with provenance.
2. `/meal-plan` for a window: linked names (no codes), exact pool with counts, strict day-pinning honoured, shopping-list quantities reproducible by hand from the cards, staples section lists required amounts.
3. Genericity: Task 6's greps stay clean in the template.
