# Meal-planning redesign — recipe cards, /recipes skill, exact plans

**Date:** 2026-07-22 · **Status:** approved design, pre-implementation

## Context and problem

The current `/meal-plan` skill keeps the whole menu in one `nutrition/menu.md`
file with code-named meals (B1, L2 …) carrying only rough kcal/protein. Three
problems surfaced in real use:

1. **Plans are painful to read** — day tables reference codes, forcing
   cross-referencing against menu.md.
2. **Shopping lists can be wrong** — the plan's meal pool was ambiguous
   ("maybe L1 twice?"), so list quantities rested on unstated assumptions.
3. **The menu can't grow well** — one file with rough numbers has no room for
   ingredients, methods, variations, provenance, or sourcing new recipes
   against the athlete's goals.

## What changes (summary)

- `nutrition/menu.md` is replaced by a **`nutrition/menu/` directory of recipe
  cards** (one file per recipe) plus a slim **`index.md`**.
- A new **`/recipes` skill** owns the bank's lifecycle: the food interview,
  adding (by link, by description, or by goal-aligned online sourcing),
  editing, benching, and feedback.
- **`/meal-plan`** becomes a pure consumer of the bank. Every plan fixes the
  week's **exact meal pool with counts**, in both loose and strict modes, so
  the **shopping list is arithmetic**, never assumption.
- Plans reference recipes by **full linked name** — codes are gone.

## Non-goals

- No calorie/TDEE computation — MacroFactor (or `/goals` numbers) stays the
  target authority. Unchanged division of labour.
- No paid recipe APIs, no API keys, no new integrations.
- No logging/tracking features — apps remain the logbooks.

## Recipe cards — `nutrition/menu/*.md`

One card per recipe, slug filename (e.g. `chicken-rice-bowl.md`). The card
format is canonically defined in **`reference/recipe-cards.md`** (a framework
file both skills point at — the format lives in exactly one place). Schema:

```yaml
---
name: chicken-rice-bowl   # must equal the filename slug
slot: [lunch]             # list; a meal may fit several slots
kcal: 610
protein: 50               # grams; all four macro fields are required
carbs: 55
fat: 18
nutrition: estimated      # estimated | published (from the source site)
prep: assemble            # assemble | quick-cook | cook
time: 5                   # active minutes
servings: 1               # portions the ingredient quantities below make
source: null              # URL when sourced online — provenance is kept
tags: [post-workout, portable]
status: active            # active | benched
---
```

Body sections:

- **Ingredients** — exact per-serving quantities. **No ranges** ("½–1 pouch"
  is banned); a quantity choice is a named variation instead.
- **Method** — optional for trivial items (a two-ingredient snack needs none).
- **Variations** — **named exact deltas** on the base: each variation states
  its ingredient changes and macro deltas, e.g.
  `**light** — ½ rice pouch instead of full · −105 kcal · −22 g carbs`.
  Plans reference `recipe (variation)` and list maths applies the delta.

**Everything plannable is a card**, however small: tiny snacks get
ingredients + macros and no method; eating-out fallbacks get a "what to
order" section instead of ingredients, a `eat-out` tag, and are naturally
excluded from shopping-list maths (no ingredient lines to sum). One format,
one lookup path.

All four macro fields are required. When the source publishes per-serving
nutrition, use it (`nutrition: published`); otherwise the agent estimates
from ingredients (`nutrition: estimated`). Rough is fine — the food log is
ground truth — but the fields are never blank.

## The index — `nutrition/menu/index.md`

A slim, human-browsable table the planner reads to *select* recipes (it then
reads only the chosen cards for ingredients):

- One row per card: linked name · slot · kcal · protein · prep effort ·
  status.
- Plus **slot-level notes** that aren't recipes: standing coverage (e.g.
  "dinners covered by family most nights — top up protein on low-protein
  nights"), eat-out fallbacks context, per-slot priorities (e.g. "breakfast
  must be fast or it gets skipped").

**Same-write rule (hard):** any operation that creates, edits, or benches a
card updates `index.md` in the same operation. Any skill that reads the index
spot-checks it against the card filenames and flags drift instead of
trusting it blindly.

## `/recipes` — new skill (bank lifecycle)

Owns everything about the bank:

- **First-run food interview** (moves here from `/meal-plan`): likes /
  dislikes / allergies, staples, cooking appetite, shopping style, standing
  coverage, plan-style preference. Writes profile.md's **Food & eating** and
  seeds the initial bank. The interview **skips anything already on file** —
  it only asks what's missing.
- **Add — three modes:**
  1. **Exact link:** athlete pastes a URL → fetch → extract → draft card.
  2. **Rough description:** "a high-protein traybake I can batch" → agent
     drafts or sources candidates.
  3. **Bulk goal-aligned sweep:** "build me a good bank" → the sourcing
     brief is derived from profile.md (current phase, kcal/protein targets,
     slot budgets, dislikes, cooking appetite, training schedule) before
     searching.
- **Approval gates:** single adds show the **full draft card** for
  confirmation before writing. Bulk sweeps present a **shortlist table**
  (~5–8 candidates: name, source, macros, effort, why it fits the goals);
  only picked candidates become cards. **No card is ever written unseen.**
- **Edit** and **bench** (set `status: benched`, never delete — benched
  recipes can come back). Feedback/pruning available on demand here too.

### Online sourcing (no APIs)

- WebSearch scoped to reputable recipe sites → WebFetch the page → extract
  the embedded **schema.org/Recipe JSON-LD** (ingredients, quantities,
  per-serving nutrition) → normalise into a draft card. `source` records the
  URL; published nutrition is preferred over estimates.
- **`reference/recipe-sources.md`** (new framework file) curates sources:
  sites with reliable structured data and trustworthy nutrition first, and
  guidance on scoping searches to the athlete's goals.
- Paid APIs (Spoonacular, Edamam) are deliberately out of scope; the design
  leaves room to add one later without changing the card format.

## `/meal-plan` — revised skill (plan consumer)

Keeps its current spine (read context → targets → coverage → compose →
shopping list → write dated plan) with these changes:

- **Opens with the feedback loop:** review the most recent dated plan — what
  got eaten, skipped, disliked — and update card statuses (bench/promote)
  before planning. Also check **bank-fit against the current phase** (see
  Training-system connection).
- **Selection reads `index.md`;** only the chosen cards are read in full.
- **The exact-pool rule (both modes):** every plan fixes the week's exact
  meal pool — each recipe (or named variation) with its count, e.g.
  "chicken-rice-bowl ×2 · cod-and-potatoes ×2 · omelette (+egg) ×1". This is
  the plan's contract and the sole input to the shopping list.
  - **Strict mode:** each pool item is additionally pinned to a day × slot.
  - **Loose mode:** the day table shows a **suggested assignment** from the
    pool; the athlete swaps freely within a slot **except day-locked
    entries** (e.g. a post-run lunch that must be quick, a pre-session
    snack), which are explicitly marked. The pool table is the contract; the
    day table is advice.
- **Recipes appear by full linked name** — `[Chicken + rice bowl](menu/chicken-rice-bowl.md)` —
  never by code.
- **Batch-cooking awareness:** `servings` > 1 lets plans schedule "cook
  Wednesday, second portion Thursday"; counts and quantities aggregate
  accordingly.
- **Shopping list — arithmetic, two exact sections:**
  1. **Buy** — non-staple ingredients: per-serving quantity × count, with
     variation deltas applied, aggregated across the pool.
  2. **Staples — confirm you have enough** — each staple the pool needs,
     with the exact required quantity (e.g. "eggs: 14 needed"). During
     planning the skill asks which staples are short and promotes those to
     Buy. Nothing the pool needs is silently assumed.
- **Missing bank:** if `nutrition/menu/` doesn't exist, `/meal-plan` invokes
  the `/recipes` skill inline (interview + seeding), then continues planning
  in the same session — no dead end for a first-time "plan my meals".

The dated-plan template in the skill is updated to match: pool table with
counts, day table (pinned or suggested+locks), linked names, two-section
shopping list.

## Training-system connection

Meal planning is part of the coaching system, not a standalone tool. Three
strands, to be stated explicitly in both skills:

1. **Targets flow one way.** `/goals` decides the strategy (phase, trend
   rate, protein floor) and records it in profile.md; MacroFactor (if used)
   holds the live daily numbers. `/meal-plan` composes food to those targets
   and never recomputes them. The existing sanity check stays: targets that
   look stale or contradict the phase stop the run and point at `/goals`.
2. **The routine shapes the week.** Day types (training / double / rest,
   runs, PT sessions) come from profile.md and `routine/program.md`, and
   drive composition (bigger fuelling on double days, leaner rest days),
   timing cues, day-locks in loose mode, and calorie cycling when the
   profile opts in.
3. **The bank stays phase-aware (new).** `/recipes` sourcing briefs are
   derived from the current phase and targets — a cut sweep hunts
   high-satiety, protein-dense, lower-kcal recipes; a bulk sweep hunts easy
   surplus calories. `/meal-plan`'s opening review includes a bank-fit
   check: after a phase change, flag mismatch ("entering the deficit and the
   bank skews carb-heavy — want a `/recipes` sweep?").

## Framework / instance split

All skill and reference work happens in the **template repo**
(`joeuk89/claude-strength-coach`, local `~/personal/workout-template`) first,
then merges into instances. Framework touch list:

| File | Change |
| --- | --- |
| `.claude/skills/recipes/SKILL.md` | **New** — bank lifecycle skill. |
| `.claude/skills/meal-plan/SKILL.md` | Rewrite — consumer of the bank, exact pools, arithmetic lists, feedback loop, inline `/recipes` handoff. |
| `reference/recipe-cards.md` | **New** — canonical card + index format, with a full example card. |
| `reference/recipe-sources.md` | **New** — curated sourcing guidance. |
| `CLAUDE.md` | Files table (`nutrition/menu/` + index), commands list (add `/recipes`), nutrition section wording. |
| `.claude/skills/setup/SKILL.md` | Line ~109: "Filled by /meal-plan" → `/recipes`. |
| `.claude/skills/check-in/SKILL.md` | Line ~104: menu-bank changes pointed at `/recipes`, not `/meal-plan`. |
| `README.md` | Command list — add `/recipes`, adjust `/meal-plan` blurb. |

Skills must stay **generic** — no athlete-specific content (no named
supermarkets, family arrangements, or specific staples in framework files;
those live in the instance's profile.md / cards).

## Instance-side work (Joe's repo, `~/personal/workout`)

- **Fresh start:** delete `nutrition/menu.md` and `nutrition/2026-07-21.md`
  (both untracked). No migration of old menu items — the bank is rebuilt
  through the new `/recipes` skill for real.
- **profile.md:** keep the Food & eating section as-is except **plan style:
  loose → strict**.
- Merge the template changes (`git fetch template && git merge
  template/main`).
- Update the auto-memory `template-instance-split.md` so the framework-file
  list includes the meal-plan and recipes skills and the two new reference
  docs.

## Testing / acceptance

- **Format check:** example card in `reference/recipe-cards.md` parses
  cleanly and demonstrates every field, a variation delta, and a no-method
  snack.
- **End-to-end (Joe's instance):** run `/recipes` to seed a fresh bank
  (interview should skip what's on file), including at least one
  link-sourced and one sweep-sourced recipe; then run `/meal-plan` for a
  window and verify: names linked (no codes), exact pool with counts, strict
  day-pinning honoured, shopping list quantities reproducible by hand from
  the cards, staples section lists required amounts.
- **Genericity check:** grep framework files for athlete-specific strings.
