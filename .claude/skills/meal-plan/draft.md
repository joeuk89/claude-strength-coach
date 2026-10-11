# The meal-plan draft and its flags

Read this when writing `.coach/drafts/meal-plan-<window start>.json`
and when its dry run returns flags (both in SKILL.md step 3).

## The draft

The C34 draft shape (`docs/design/coach-contract.md`):

- **`span`**: the window, `{"start", "end"}`; default the week the
  template showed.
- **`exceptions`**: one per change the athlete named. A slot change is
  `{"date", "slot", "entry", "note"}` and replaces everything the
  template puts in that slot that day, anchors included; an office-day
  change is `{"date", "office": true|false}`. An entry is
  `{"recipe", "variations", "covered_by", "lock"}`, or
  `{"cover", "kcal", "protein_g"}` for a meal someone else decides (your
  estimate, stated in the presentation), or `{"skip": true}`.
- **`assignments`**: a pick for every open slot and every pool slot,
  from active cards. An assignment adds to its slot, so a protein
  top-up on a low-protein covered night is an assignment beside the
  cover. Use `lock` with a reason for a day-locked entry (a post-run
  lunch that must be quick). A meal-kit box meal is a recipe with
  `covered_by` set to the provider: counted, not shopped. A box meal
  with no card is a cover entry with the box's numbers.
- **`use_up`**: each item the athlete named, `{"item", "qty", "unit"}`
  with the item spelt as the cards spell it. Plan those items into
  meals early in the window.
- **`notes`**: batch-cook days, timing cues.

How to pick: protein first (the anchors cover part of the floor; spread
the rest over the day's meals), then calories toward the target, then
variety and what the athlete likes to eat. A card with `servings` above
1 fills that many slots from one batch; schedule the cook day in
`notes`. Variations stack only when they change different ingredients.

## Anchor shopping coverage

During setup, offer each anchor's optional `recipe = "<slug>"` link in
`[[nutrition.anchors]]`, replacing its inline `kcal` and `protein_g`.
Use only an active card the athlete confirms describes the food and
serving; a similar name is not a match. When no correct card exists,
keep the valid bare anchor and its known macros; `/recipes` can add a
card once the athlete supplies ingredients and amounts.

Anchors already fill their scheduled slots; assign additional food only
when needed, keeping the anchor out of open-slot picks. Linked anchors
shop their scheduled servings using the card's batch size. For a supplied
meal, a slot exception with `recipe` and `covered_by` replaces the anchor;
a `cover` exception records supplied food without a card. Pantry items
belong in `staples` or `use_up` and retain their normal shopping treatment.

Present every remaining `anchor_shopping_unknown` warning before approval:
name the anchor and explain that its macros count but its ingredients are
missing from shopping. Keep the bare anchor if that is the agreed choice;
state that the athlete must arrange it separately. Quantities come from
confirmed ingredients, never from macros.

## The dry run's flags

Fix the draft and re-run the dry run until no `block` flag remains:

| Flag | Severity | What to do |
| --- | --- | --- |
| `recipe_unknown`, `variation_unknown` | block | Correct the slug or variation name, or pick another card. |
| `variation_conflict` | block | Keep one of the two variations. |
| `anchor_shopping_unknown` | warn | Follow Anchor shopping coverage above; show any gap before approval. |
| `slot_open` | warn | Add an assignment; leave it open only on purpose (say so). |
| `protein_below_floor` | warn | Add a top-up or swap a meal; present any that remain. |
| `kcal_off_target` | warn | Adjust portions or picks; present any that remain, with the reason. |
| `recipe_benched` | warn | Pick an active card, unless the athlete asked for it. |
| `use_up_unmatched`, `units_mixed` | warn | Match the item's spelling and unit to the card's. |
| `no_target` | warn | Say the days are checked against protein only; `/goals` or the next reading fixes it. |
