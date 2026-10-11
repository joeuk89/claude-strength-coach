---
name: meal-plan
description: Use when the athlete wants help planning what to eat — meals, snacks, and a shopping list for any window (the week ahead, a few days, one day). Triggers include "/meal-plan", "plan my meals", "what should I eat this week", "help me hit my protein", "what healthy snacks should I buy", "build me a shopping list".
---

# Meal planning & shopping list

Turn the nutrition targets on file into real food: plan the athlete's
meals and snacks for a chosen window (default: the week ahead) and build
a shopping list for **exactly** what the plan needs. Plan only the
**gaps** — meals already covered (meal kit, canteen, eating out, family
dinners) and the athlete's standing protein anchors are declared up
front and treated as fixed blocks.

**Division of labour:** `/goals` decides the strategy and records its
numbers in `config.toml` (`[nutrition]`; `python3 -m coach nutrition
status` returns them) and the reasoning in `profile.md` (Nutrition &
goals). MacroFactor, if the athlete uses it,
holds the live daily kcal/macro targets. `/recipes` owns the recipe
bank. This skill composes food to the targets from the bank — it never
computes TDEE, never revises targets, and never edits recipes beyond
status changes agreed in the opening review. If the targets look wrong,
send the athlete to `/goals`; if the bank needs work, `/recipes`.

Requires nutrition to be set up — if `nutrition status` says `enabled:
false`, run `/setup` or `/goals` first.

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
the output of `python3 -m coach nutrition status`, `routine/program.md` (training days, double days, rest days — count
cardio), `nutrition/menu/index.md`, and the newest dated plan in
`nutrition/`. If `python3 -m coach check --only
recipe_index_fresh,recipe_render_fresh` fails, run `python3 -m coach
recipes render` before reading the index.

## 2. Review the last plan (feedback loop)

Open with a quick review of the most recent dated plan: what got eaten,
skipped, swapped, disliked? Agree any card status changes (bench /
un-bench) and apply them: set `status` in each card's data block, then
run `python3 -m coach recipes render`.

Then a **bank-fit check** against the current phase: if `/goals` has
changed the phase since the bank was last touched and the bank skews
wrong for it (e.g. entering a deficit with a carb-heavy, low-satiety
bank), say so and offer a `/recipes` sweep before planning.

## 3. Current targets

- **MacroFactor users:** ask for today's kcal and protein targets off
  the dashboard, and whether calorie shifting is configured. If MF is
  still calibrating (a new account, or a fresh phase on-ramp) and shows
  no target yet, fall back to the numbers `nutrition status` returns
  and say you've done so.
- **Without MacroFactor:** use `kcal_target` and the protein numbers
  from `nutrition status`.
- **Protein:** plan every day to at least the **protein floor** and
  toward the **target** (both in `nutrition status` → `protein`). For
  MacroFactor users the app's protein target is the floor.
- Sanity-check either against those numbers. A big mismatch (wrong
  phase, stale targets) means the strategy needs attention — flag it
  and point at `/goals` before planning to a number you don't trust.

## 4. Coverage for the window

Confirm the window (default: the week ahead), then what's already
covered — which day × meal slots, and what with. Confirm which days are
training / double / rest days from the routine (don't assume — weeks
have one-off changes), and ask about anything unusual: travel, meals
out, guests.

**Protein anchors are fixed blocks.** Take the anchors from
`nutrition status` (`anchors`) and place each anchor in its slot on every day it
applies, before planning anything else. Like a covered meal, an anchor
is counted in the day's macros and never swapped or dropped;
unlike one, it is shopped for (step 6) unless it's on the staples list.
Don't re-ask about anchors — changing them is `/goals`' job.

**Ask once: "Anything in the house to use up?"** Leftovers, short-dated
meat, wilting veg, a half-finished pack. Note each item and the amount
the athlete gives. Ask it once per run and don't ask for a full stock
list: these named items are the only stock the plan accounts for.

**Covered meals with no card** (a family dinner, a canteen lunch):
estimate their per-serving macros with the athlete and record the
assumption in the plan — the day's totals lean on them. Ask which are
the **low-protein nights** (e.g. a veg-curry dinner) so any protein
top-up lands on the right day. Protein is the hard constraint; a covered
block's calories are an estimate, so treat the daily kcal as approximate
when much of the day is family-cooked.

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

- **Use it up.** Items the athlete named to use up get planned into
  meals **early in the window**, and the pool rationale says so ("cod
  traybake Monday — the cod needs eating"). Partial packs steer
  selection toward recipes that finish them. A tiebreaker with teeth,
  not a straitjacket: macro fit and what the athlete wants to eat still
  win.
- **Protein comes first.** The anchors cover part of the floor; spread
  the rest across the day's meals (~4 feeds including the anchors is a
  good default; ~0.4 g/kg of the reference mass in `nutrition status` per
  meal is a heuristic, not dogma).
- **Train-day awareness:** bigger fuelling on double days, leaner rest
  days; calorie cycling if the profile opts in (carbs/kcal toward
  higher-output days, protein flat). Timing notes only where they
  matter — around training slots.
- **Stacking variations:** a pool entry may carry more than one variation
  when they hit different ingredients (`oats (+banana, +PB)`) — the deltas
  add. See `reference/recipe-cards.md`.
- **Batch cooking:** a card with `servings` > 1 covers multiple slots —
  schedule the cook day and the leftover day explicitly, and count the
  recipe once per serving in the pool.
- Favour variety and meals the athlete wants to eat. Close-enough
  daily, corrected weekly, beats gram-perfect and abandoned.

## 6. Shopping list — arithmetic, never assumption

Derive from the pool's **non-covered** entries and the anchors (each
anchor × the days it applies): per-serving ingredient
quantities × counts, with variation deltas applied, aggregated across
the window. **Then subtract the use-up items:** the amounts the athlete
named in step 4 come off the totals before anything lands in Buy.

A **staple** is anything on the athlete's staples list in `profile.md`
(Food & eating) — what they keep in by default; everything else is a
Buy item, even cupboard basics not on that list. Two sections, both
exact:

1. **Buy** — non-staple ingredients with exact quantities (and pack
   sizes where they help), net of the use-up amounts — plus any staple
   the athlete says they're short of.
2. **Staples — confirm you have enough** — every staple the pool
   needs, each with the required amount (e.g. "eggs: 14"). Ask the
   athlete about every one of them and promote any shortfall to Buy.

Nothing the pool needs may be missing from both sections. Shape the
list to the athlete's shopping style (one basket for a weekly online
shop; grouped by category in person; staples-vs-extras for ad hoc).
If a grocery integration is connected, offer to push the list.

## 7. Write and close out

Write `nutrition/YYYY-MM-DD.md`:

```markdown
# Meal plan — <window start> → <window end>

**Targets used:** ~X kcal · protein floor Y g, target Z g (source: MacroFactor dashboard /
profile) · plan style: loose/strict
**Anchors:** <anchor> (<slot>, <days>) · …

## This week's pool
| Meal | Count | Per serving |
| --- | --- | --- |
| [Chicken + rice bowl](menu/chicken-rice-bowl.md) | 2 | 610 kcal · 50 g P |
| [Cod traybake](menu/cod-traybake.md) (light) | 2 | 420 kcal · 38 g P |
| [Chorizo rice](menu/chorizo-rice.md) | 2 | 650 kcal · 32 g P · **covered — Gousto box** |
(The contract. Counts are exact; variations named; covered entries are
in the plan and the macros but not the shopping list.)

## The week
| Day | Type | Breakfast | Lunch | Dinner | Snacks |
| --- | --- | --- | --- | --- | --- |
| Mon | training | [Overnight oats](menu/overnight-oats.md) | [Chicken + rice bowl](menu/chicken-rice-bowl.md) 🔒 post-run — quick | family: chicken + pasta *(covered)* | … |
(Every slot the plan touches gets a column, dinner included. Covered
entries — family dinners, meal-kit boxes, eat-out — sit in their slot's
cell marked *(covered)*: counted in the day's macros, absent from the
shopping list. Anchors sit in their slot's cell marked *(anchor)*. A
linked top-up recipe on a low-protein night goes in the
Dinner cell alongside the covered block. Strict: assignments are fixed.
Loose: suggested — swap within a slot except 🔒 day-locked entries.
Recipes always linked by full name.)

## Notes
Used up this week: what the athlete named to use up, and where it went.
Timing cues, batch-cook schedule, anything decided this run.

## Shopping list
### Buy
| Item | Quantity | Covers |
| --- | --- | --- |

### Staples — confirm you have enough
| Staple | Needed this week |
| --- | --- |
```

Then close out: apply any remaining card status changes agreed this
run (then `recipes render`); update Food & eating for any preference the athlete confirmed
changed; remind the athlete that logging (MacroFactor, if used) stays
the ground truth — the next `/check-in` reviews how the plan went.
