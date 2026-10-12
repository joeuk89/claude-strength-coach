# Protein: reference mass, floor, target, stretch, anchors

## Set the numbers

Run `python3 -m coach nutrition targets` and quote its output. From the
last 14 days it takes bodyweight from the newest weight on file (the
weigh-in kept in SKILL.md step 1 counts) and recent intake from the newest
reading; goal weight comes from `[nutrition]`. Pass what the athlete told you:

- `--body-fat <pct> --body-fat-source credible|rough` for a body-fat
  reading (`--help` says which methods count as credible);
- `--sex` when `missing` asks for it;
- `--height` for the BMI cue with a rough or absent reading (cm, or
  inches with lb);
- `--goal-weight` for the goal agreed in step 3, `--recent-intake` for
  a typical day's protein, and `--bodyweight` only for a what-if weight
  (a fresh weigh-in is kept with `bodyweight record` first, then read).

When `missing` names an input, ask the athlete for it and run again.

- `reference` gives the basis (the `reference_basis` value), the mass and
  the reason. Record the basis and the reason, with any reading's method
  and date (SKILL.md step 9).
- The **target** is the number to coach toward; the **stretch** is the
  optional higher aim, not a universal benefit cap; the **floor** is
  the minimum commitment this week. Actual intake can be higher. With
  fat-free mass the stretch is a range: agree a number from `g` to `g_high`.
- **MacroFactor users:** keep a comfortable app protein setting at or
  above the floor (SKILL.md step 6). A below-floor setting prompts review,
  respecting any active protein override. Record the actual app number;
  retain floor ≤ target ≤ stretch rather than raising the floor to match it.

**Explain the floor from the output.** Quote `floor.g`,
`from_intake_g`, `g_min` and `target.g` as printed and never recompute
them. `from_intake_g` is recent intake plus 15–20 g, the first 5 g step
at or above intake plus 15 g (rn:protein-energy-deficit.8). The floor
stays between two bounds, and `floor.clamped` says which one applied:

- `null`: neither; the floor is `from_intake_g`.
- `"min"`: `from_intake_g` falls short of the minimum, so the floor
  is `g_min`, set by `g_per_kg_min`: 1.2 g/kg for bodyweight or goal
  weight and 1.5 g/kg for fat-free mass, because muscle loss while
  losing weight is more likely below it (rn:protein-energy-deficit.7,
  low-confidence evidence). Say the floor asks for more than a 15–20 g
  step and let the anchors close the gap.
- `"target"`: `from_intake_g` passes the target, so the floor is
  `target.g`. Intake at or above the target stays compatible with the
  floor, so never tell the athlete to eat less protein
  (rn:protein-energy-deficit.8).

Reference selection uses the available rough body-fat, goal-gap and BMI
cues together; a positive cue selects goal weight. A credible reading
uses fat-free mass. Explain the reported reason as a coaching heuristic.
When the athlete asks why a number, `python3 -m coach research show <ref>`
prints the claim behind each of its `refs`.

**Habit progression.** The floor moves up as the habit sticks: when
the measured weekly average protein meets or beats the floor at **two
consecutive check-ins** since the floor last changed, the floor rises by
~10–15 g, **never above the target** (rn:protein-energy-deficit.9).
Missing the floor never lowers it; only `/goals` lowers it, with a
reason. `/check-in` applies the raise. For MacroFactor users the athlete
raises the app setting only if below the new floor, after reviewing any
active protein override. Whenever `/goals` changes `floor_g`, set `floor_since` to the day after the newest reading
on file (`python3 -m coach nutrition readings --last 1`), or today if
that is later: a reading already on file measured the old floor and must
not count toward the next raise.

Three unmeasured no-app check-ins since `floor_since` while below target
produce `protein_unmeasured`: offer optional calibration, explicit `/goals`
review or a deliberate hold (rn:protein-energy-deficit.20). Anchor adherence
cannot qualify a gram-based raise. Keep a typical-day estimate used at
setup in context notes; only an observed weekly average belongs in
`avg_protein_g`.

## Agree the protein anchors

Protein is coached through **2–3 standing protein anchors**, not a daily
meal plan. An anchor is a fixed daily item in a set slot that:

- carries **~25 g protein or more**;
- needs **no cooking** (a shake, a pot of high-protein yogurt, cottage
  cheese, a ready-to-eat protein snack, milk with a scoop); and
- together with the athlete's typical meals, gets them to the floor.

Propose candidates from what the athlete already eats and likes, check
the sum (anchors + a typical day's meals ≥ floor), and agree each
anchor's name, slot (breakfast, lunch, dinner, snack) and days (daily,
office days, named weekdays). Offer `recipe = "<slug>"` when an active
card describes that exact food and serving; confirm the card with the
athlete rather than matching its name alone. Use the link instead of
`kcal` and `protein_g`: the card supplies macros and shopping ingredients.
A bare anchor with known macros remains valid when no correct card is
available; its ingredients are unknown, so `/meal-plan` flags its missing
shopping coverage without guessing quantities. Record the agreed anchors
in `config.toml` (SKILL.md step 9). `/meal-plan` treats them as fixed
blocks; `/check-in` asks whether they happened most days.
