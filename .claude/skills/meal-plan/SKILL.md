---
name: meal-plan
description: Use when the athlete wants help planning what to eat — meals, snacks, and a shopping list for any window (the week ahead, a few days, one day). Triggers include "/meal-plan", "plan my meals", "what should I eat this week", "help me hit my protein", "what healthy snacks should I buy", "build me a shopping list".
---

# Meal planning & shopping list

Turn the nutrition targets on file into real food: plan the athlete's
meals and snacks for a chosen window (default: the week ahead) and build a
shopping list for exactly what the plan needs. Plan only the **gaps** —
meals already covered (meal kit, canteen, eating out, family dinners) are
declared up front and treated as fixed blocks.

**Division of labour:** `/goals` decides the strategy and records it in
`profile.md` (Nutrition & goals). MacroFactor, if the athlete uses it,
holds the live daily kcal/macro targets. This skill composes food to those
targets — it never computes TDEE, never revises targets, and never builds
a competing calorie calculator. If the targets themselves look wrong, send
the athlete to `/goals`.

Requires `profile.md` with a real Nutrition & goals section — if it's
missing or still TBD, run `/setup` or `/goals` first.

## The files

- **`nutrition/menu.md`** — the persistent **menu bank**: one section per
  slot (Breakfasts / Lunches / Dinners / Snacks), each meal with rough
  kcal + protein and prep effort. Built on the first run, evolved on every
  later run. Variety lives here — keep 3–5 real options per slot the
  athlete needs.
- **`nutrition/YYYY-MM-DD.md`** — one dated plan per run: the window's
  day-by-day skeleton plus the shopping list.
- **`profile.md` → "Food & eating"** — what the skill should never
  re-ask: likes/dislikes/allergies, staples always in stock, cooking
  appetite, shopping style, standing coverage (e.g. "meal kit ×3
  dinners/week"), and plan-style preference (loose rotation ↔ strict
  day-by-day).

## 1. Read the context

Read `profile.md` (Nutrition & goals, Food & eating, the training week),
`routine/program.md` (which days are training days, double days, rest days
— count cardio), `nutrition/menu.md`, and the newest dated plan in
`nutrition/` (what worked and what didn't feeds this run).

## 2. First run — the food interview

If there's no Food & eating section in `profile.md` or no
`nutrition/menu.md`, run a short interview first — one question at a time:
likes, dislikes, allergies/intolerances; staples always in the house;
cooking appetite (assemble-only ↔ batch-cook ↔ cook most days); how they
shop (one weekly online order, weekly in person, ad hoc top-ups); standing
coverage (meal-kit subscription, canteen, regular meals out); and how
prescriptive they want plans (loose menu-of-options ↔ strict named meal
per slot). Then draft `nutrition/menu.md` (macro-tagged options for every
slot the athlete actually needs to fill — snacks included, healthy and
specific) and the Food & eating section together, and confirm both with
the athlete before writing. Later runs never re-interview — they evolve
the menu: retire what the athlete didn't enjoy, add new ideas on request.

## 3. Current targets

- **MacroFactor users:** ask for today's **kcal target** and **protein
  target** off the dashboard, and whether calorie shifting (more on
  higher-output days) is configured.
- **Without MacroFactor:** use the calorie/protein targets in
  `profile.md`.
- Sanity-check either against the profile's Nutrition & goals section. A
  big mismatch (wrong phase, stale targets) means the strategy needs
  attention — flag it and point at `/goals` before planning to a number
  you don't trust.

## 4. Coverage for the window

Confirm the window (default: the week ahead), then ask what's already
covered — which day × meal slots, and what with. Meal-kit recipes usually
publish per-serving nutrition; use those numbers when the athlete has
them, otherwise estimate together and say so. Confirm which days are
training / double / rest days from the routine (don't assume — the
schedule can have one-off changes), and ask about anything unusual in the
window: travel, meals out, guests.

## 5. Compose the plan

Build a day-by-day skeleton. For each day: the day type (training, double,
rest), the covered meals as fixed blocks, and the gap slots filled from
the menu bank so the day lands close to the targets.

- **Plan style follows the profile preference.** Loose: each gap slot
  lists 2–3 menu options that are roughly macro-equivalent, so swapping
  never breaks the plan. Strict: one named meal per slot.
- **Protein is the anchor.** Spread it across the day (~4 feeds is a good
  default; ~0.4 g/kg per meal is a reasonable heuristic, not dogma). If
  breakfast tends to get skipped, that's the first structural fix — make
  it fast to assemble, or move the protein elsewhere deliberately.
- **Calorie cycling:** if the profile opts in, shift carbs/kcal toward the
  higher-output days and keep protein flat.
- **Timing notes only where they matter** — around training slots (e.g.
  something quick before a morning session, protein after), not a
  schedule for its own sake.
- Favour variety across the week and meals the athlete actually wants to
  eat. Close-enough daily, corrected weekly, beats gram-perfect and
  abandoned. No extreme restriction — sustainable food only.

## 6. Shopping list

Derive the list from the gap meals: ingredients needed minus staples on
hand (ask which staples need restocking rather than assuming). Shape it to
the athlete's shopping style — a complete basket with quantities for a
weekly online shop; grouped by category for in-person; staples-to-restock
vs this-week-extras for ad hoc shoppers. If a grocery MCP or similar
integration is connected in this environment, offer to push the list to
it; otherwise the list itself is the deliverable.

## 7. Write and close out

Write `nutrition/YYYY-MM-DD.md`:

```markdown
# Meal plan — <window start> → <window end>

**Targets used:** ~X kcal · ~Y g protein (source: MacroFactor dashboard /
profile) · plan style: loose/strict

## The week
| Day | Type | Covered | Plan |
| --- | --- | --- | --- |
| Mon | training | — | B: … · L: … · S: … · D: … |
(One row per day. Gap slots reference menu-bank meals; covered slots name
what's covering them.)

## Notes
Timing cues, batch-cook steps, anything decided this run.

## Shopping list
(Shaped to the athlete's shopping style.)
```

Then: update `nutrition/menu.md` with anything added or retired this run;
update the Food & eating section for any preference the athlete confirmed
changed; remind the athlete that logging (MacroFactor, if used) stays the
ground truth — the next `/check-in` reviews how the plan actually went.
