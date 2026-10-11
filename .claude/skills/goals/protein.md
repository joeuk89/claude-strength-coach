# Protein: reference mass, floor, target, stretch, anchors

## Set the numbers

Run `python3 -m coach nutrition targets` and quote its output. It takes
bodyweight and recent intake from the newest reading of the last 14 days
and goal weight from `[nutrition]`. Pass what the athlete told you:

- `--body-fat <pct> --body-fat-source credible|rough` for a body-fat
  reading (`--help` says which methods count as credible), with `--sex`
  for a rough one;
- `--height` when there is no reading (cm, or inches with lb);
- `--bodyweight` for a fresh weigh-in, `--goal-weight` for the goal
  agreed in step 3, and `--recent-intake` for a typical day's protein.

When `missing` names an input, ask the athlete for it and run again.

- `reference` gives the basis (the `reference_basis` value), the mass and
  the reason: record the basis and its reason (SKILL.md step 9).
- The **target** is the number to coach toward; the **stretch** is the
  most that still adds anything (useful on a hard cut); the **floor** is
  the reachable number the athlete is held to this week. With fat-free
  mass the stretch is a range: agree a number from `g` to `g_high`.
- **MacroFactor users:** the floor is the protein number set in the app
  (SKILL.md step 6). The app's protein figure and the floor on file are
  the same number unless an active nutrition override covers protein.

Per kg of bodyweight, protein overshoots for an athlete carrying a lot of
fat; goal weight or fat-free mass keeps it reachable. When the athlete
asks why a number, `python3 -m coach research show <ref>` prints the
claim behind each of its `refs`.

**Habit progression.** The floor moves up as the habit sticks: when
the weekly average protein meets or beats the floor at **two
consecutive check-ins** since the floor last changed, the floor rises by
~10–15 g, **never above the target** (rn:protein-energy-deficit.9).
Missing the floor never lowers it; only `/goals` lowers it, with a
reason. `/check-in` applies the raise. For MacroFactor users the athlete
sets the app's protein to the new floor the same day. Whenever `/goals`
changes `floor_g`, set `floor_since` to the day after the newest reading
on file (`python3 -m coach nutrition readings --last 1`), or today if
that is later: a reading already on file measured the old floor and must
not count toward the next raise.

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
office days, named weekdays). Record them in `config.toml` (SKILL.md
step 9). `/meal-plan` treats them as fixed blocks; `/check-in` asks
whether they happened most days.
