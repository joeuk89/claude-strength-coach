# Protein: reference mass, floor, target, stretch, anchors

## Pick the reference mass

The mass every protein figure is multiplied by. Take the first rule that
applies:

1. **Fat-free mass** when a credible body-fat reading exists (DEXA, a
   BodPod or underwater weighing, or skinfolds by an experienced tester,
   from the last ~3 months): bodyweight × (1 − body-fat fraction).
2. **Goal weight** when body fat is high: above ~25 % for men or ~35 %
   for women on a rougher reading (a smart scale, a tape method). With
   no reading at all, treat body fat as high when BMI is 30 or more, or
   when the goal weight is 10 % or more below current bodyweight.
3. **Current bodyweight** otherwise.

Per kg of bodyweight, protein overshoots for an athlete carrying a lot of
fat; goal weight or fat-free mass keeps the number reachable. Record the
basis and why (the reading and its source).

## Record three numbers from that mass

| Number | Bodyweight or goal weight | Fat-free mass |
| --- | --- | --- |
| **Target** | 1.6 g/kg | ~2.0 g/kg |
| **Stretch** | 2.2 g/kg | ~2.6–2.8 g/kg |
| **Floor** | recent average intake + ~15–20 g, no lower than 1.2 g/kg and no higher than the target | same rule, no lower than ~1.5 g/kg |

The fat-free-mass column is the first column converted at ~15–20 % body
fat.

- The **target** is the number to coach toward; the **stretch** is the
  most that still adds anything (useful on a hard cut); the **floor** is
  the reachable number the athlete is held to this week.
- **MacroFactor users:** the floor is the protein number set in the app
  (SKILL.md step 6). The app's protein figure and the floor on file are
  the same number unless an active nutrition override covers protein.
- Round to the nearest 5 g.

Why these numbers: gains in fat-free mass stop rising at ~1.6 g/kg/day,
which sets the target (rn:protein-energy-deficit.1), and the top of the
95 % confidence interval around that plateau, 2.2 g/kg, sets the stretch
(rn:protein-energy-deficit.2). The fat-free-mass stretch sits inside the
2.3–3.1 g/kg of fat-free mass that lean lifters likely need in a deficit
(rn:protein-energy-deficit.6). The floor never drops under 1.2 g/kg
because muscle loss during weight loss is more likely at lower intakes
(rn:protein-energy-deficit.7), and starts from recent intake so it is
reachable this week (rn:protein-energy-deficit.8). The reference mass
keeps every figure reachable for an athlete carrying a lot of fat
(rn:protein-energy-deficit.3). The ~25 %/~35 % body-fat lines are the
WHO obesity lines that research uses (rn:protein-energy-deficit.4),
and BMI ≥ 30 alone misses over half of people with excess fat — hence
the goal-weight fallback (rn:protein-energy-deficit.5).

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
