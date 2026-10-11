"""`nutrition targets`: the protein reference mass, floor, target and stretch (contract C35)."""

import json
import unittest

from coach import calories, protein, research
from coach.errors import ValidationError
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli
from tests.test_nutrition import InstanceCopy, edit_config

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
REF = "rn:protein-energy-deficit."


def targets(**inputs):
    inputs.setdefault("unit", "kg")
    return protein.targets(**inputs)


def missing(result):
    return [item["input"] for item in result["missing"]]


class BasisTest(unittest.TestCase):
    def test_credible_reading_uses_fat_free_mass(self):
        result = targets(bodyweight=80, body_fat_pct=20, body_fat_source="credible", goal_weight=70,
                         recent_intake_g=100)
        reference = result["reference"]
        self.assertEqual((reference["basis"], reference["mass"], reference["mass_kg"]), ("fat_free_mass", 64, 64))
        self.assertIn("credible", reference["reason"])
        self.assertEqual(reference["refs"], [REF + "3"])
        numbers = result["protein"]
        self.assertEqual((numbers["target"]["g"], numbers["target"]["g_per_kg"]), (130, 2.0))
        self.assertEqual((numbers["stretch"]["g"], numbers["stretch"]["g_high"]), (165, 180))
        self.assertEqual((numbers["stretch"]["g_per_kg"], numbers["stretch"]["g_per_kg_high"]), (2.6, 2.8))
        self.assertEqual((numbers["floor"]["g"], numbers["floor"]["g_min"], numbers["floor"]["g_per_kg_min"]),
                         (115, 100, 1.5))
        self.assertEqual(numbers["target"]["refs"], [REF + "1", REF + "6"])
        self.assertEqual(numbers["stretch"]["refs"], [REF + "2", REF + "6"])
        self.assertEqual(result["missing"], [])

    def test_high_rough_reading_for_a_man_uses_goal_weight(self):
        result = targets(bodyweight=100, body_fat_pct=28, body_fat_source="rough", sex="male", goal_weight=85,
                         recent_intake_g=120)
        reference = result["reference"]
        self.assertEqual((reference["basis"], reference["mass"]), ("goal_weight", 85))
        self.assertEqual(reference["refs"], [REF + "3", REF + "4"])
        numbers = result["protein"]
        self.assertEqual((numbers["target"]["g"], numbers["stretch"]["g"], numbers["stretch"]["g_high"]),
                         (135, 185, 185))
        self.assertEqual((numbers["floor"]["g"], numbers["floor"]["g_min"]), (135, 105))
        self.assertEqual(numbers["target"]["refs"], [REF + "1"])

    def test_high_rough_reading_for_a_woman_uses_goal_weight(self):
        result = targets(bodyweight=90, body_fat_pct=38, body_fat_source="rough", sex="female", goal_weight=70)
        self.assertEqual((result["reference"]["basis"], result["reference"]["mass"]), ("goal_weight", 70))
        self.assertEqual((result["protein"]["target"]["g"], result["protein"]["stretch"]["g"]), (110, 155))
        self.assertEqual(result["protein"]["floor"]["g_min"], 85)

    def test_womens_line_is_35_not_25(self):
        result = targets(bodyweight=70, body_fat_pct=30, body_fat_source="rough", sex="female", goal_weight=62)
        self.assertEqual(result["reference"]["basis"], "bodyweight")

    def test_the_lines_are_strictly_above(self):
        result = targets(bodyweight=80, body_fat_pct=25, body_fat_source="rough", sex="male", goal_weight=75)
        self.assertEqual(result["reference"]["basis"], "bodyweight")

    def test_a_rough_reading_needs_sex_only_between_the_lines(self):
        above = targets(bodyweight=100, body_fat_pct=36, body_fat_source="rough", goal_weight=80)
        self.assertEqual(above["reference"]["basis"], "goal_weight")
        self.assertIn("~25 % line for men and the ~35 % line for women", above["reference"]["reason"])
        below = targets(bodyweight=80, body_fat_pct=25, body_fat_source="rough")
        self.assertEqual(below["reference"]["basis"], "bodyweight")
        between = targets(bodyweight=80, body_fat_pct=25.5, body_fat_source="rough")
        self.assertIsNone(between["reference"])

    def test_bmi_just_under_30_is_not_high(self):
        result = targets(bodyweight=97.1, height_m=1.8, goal_weight=95)
        self.assertEqual((result["reference"]["basis"], result["reference"]["bmi"]), ("bodyweight", 29.9))

    def test_no_reading_and_bmi_30_uses_goal_weight(self):
        result = targets(bodyweight=97.2, height_m=1.8, goal_weight=95)
        reference = result["reference"]
        self.assertEqual((reference["basis"], reference["mass"], reference["bmi"]), ("goal_weight", 95, 30.0))
        self.assertEqual(reference["refs"], [REF + "3", REF + "5"])
        self.assertIn("BMI", reference["reason"])

    def test_no_reading_and_a_goal_10_percent_below_uses_goal_weight(self):
        result = targets(bodyweight=90, height_m=1.85, goal_weight=81)
        reference = result["reference"]
        self.assertEqual((reference["basis"], reference["mass"]), ("goal_weight", 81))
        self.assertIn("10 %", reference["reason"])

    def test_a_goal_10_percent_below_needs_no_height(self):
        result = targets(bodyweight=100, goal_weight=90, recent_intake_g=100)
        self.assertEqual(result["reference"]["basis"], "goal_weight")
        self.assertEqual(result["missing"], [])

    def test_bodyweight_by_default(self):
        result = targets(bodyweight=80, height_m=1.8, goal_weight=78, recent_intake_g=104)
        reference = result["reference"]
        self.assertEqual((reference["basis"], reference["mass"], reference["bmi"]), ("bodyweight", 80, 24.6))
        self.assertEqual(reference["refs"], [REF + "3", REF + "5"])
        numbers = result["protein"]
        self.assertEqual((numbers["target"]["g"], numbers["target"]["g_per_kg"]), (130, 1.6))
        self.assertEqual((numbers["stretch"]["g"], numbers["stretch"]["g_high"]), (175, 175))
        self.assertEqual((numbers["floor"]["g"], numbers["floor"]["g_min"], numbers["floor"]["g_per_kg_min"]),
                         (120, 100, 1.2))
        self.assertEqual(numbers["floor"]["refs"], [REF + "8", REF + "7"])

    def test_bodyweight_without_a_goal_weight(self):
        result = targets(bodyweight=80, height_m=1.8)
        self.assertEqual(result["reference"]["basis"], "bodyweight")

    def test_pounds_report_both_units(self):
        result = targets(unit="lb", bodyweight=180, height_m=1.8)
        reference = result["reference"]
        self.assertEqual((reference["mass"], reference["unit"], reference["mass_kg"]), (180, "lb", 81.6))
        self.assertEqual(result["protein"]["target"]["g"], 130)


class FloorTest(unittest.TestCase):
    def floor(self, intake):
        return targets(bodyweight=80, height_m=1.8, recent_intake_g=intake)["protein"]["floor"]

    def test_first_5_g_step_15_to_20_g_above_intake(self):
        for intake, expected in ((100, 115), (101, 120), (104, 120), (105, 120), (106, 125)):
            with self.subTest(intake=intake):
                floor = self.floor(intake)
                self.assertEqual(floor["g"], expected)
                self.assertTrue(15 <= floor["g"] - intake <= 20)
                self.assertIsNone(floor["clamped"])

    def test_clamped_up_to_the_minimum(self):
        floor = self.floor(60)
        self.assertEqual((floor["g"], floor["from_intake_g"], floor["clamped"]), (100, 75, "min"))

    def test_clamped_down_to_the_target(self):
        floor = self.floor(125)
        self.assertEqual((floor["g"], floor["from_intake_g"], floor["clamped"]), (130, 140, "target"))

    def test_the_minimum_rounds_up(self):
        floor = targets(bodyweight=81, height_m=1.8, recent_intake_g=50)["protein"]["floor"]
        self.assertEqual(floor["g_min"], 100)

    def test_no_intake_leaves_the_floor_open(self):
        result = targets(bodyweight=80, height_m=1.8)
        floor = result["protein"]["floor"]
        self.assertIsNone(floor["g"])
        self.assertEqual(floor["g_min"], 100)
        self.assertEqual(missing(result), ["recent_intake"])
        self.assertEqual(result["protein"]["target"]["g"], 130)


class MissingInputTest(unittest.TestCase):
    def test_rough_reading_without_sex(self):
        result = targets(bodyweight=90, body_fat_pct=30, body_fat_source="rough", recent_intake_g=100)
        self.assertEqual(missing(result), ["sex"])
        self.assertIsNone(result["reference"])
        self.assertIsNone(result["protein"])
        self.assertEqual(result["missing"][0]["flag"], "--sex")

    def test_no_reading_without_height(self):
        result = targets(bodyweight=90, goal_weight=88, recent_intake_g=100)
        self.assertEqual(missing(result), ["height"])
        self.assertIsNone(result["reference"])

    def test_high_body_fat_without_a_goal_weight(self):
        result = targets(bodyweight=100, height_m=1.75, recent_intake_g=100)
        self.assertEqual(missing(result), ["goal_weight"])
        self.assertIsNone(result["reference"])

    def test_no_bodyweight(self):
        result = targets(bodyweight=None, recent_intake_g=100)
        self.assertEqual(missing(result), ["bodyweight"])
        self.assertIsNone(result["protein"])

    def test_each_missing_input_names_its_flag(self):
        result = targets(bodyweight=None)
        self.assertEqual(missing(result), ["bodyweight", "recent_intake"])
        self.assertEqual([item["flag"] for item in result["missing"]], ["--bodyweight", "--recent-intake"])
        for item in result["missing"]:
            self.assertTrue(item["why"])


class ClaimTest(unittest.TestCase):
    def claim(self, n):
        return " ".join(research.find_claim(f"{REF}{n}", research.load_notes(REPO_ROOT)).text.split())

    def test_each_number_is_the_one_its_claim_states(self):
        self.assertEqual(protein.PER_KG["other"], {"target": 1.6, "stretch": 2.2, "stretch_high": 2.2,
                                                   "floor_min": 1.2})
        self.assertEqual(protein.PER_KG["fat_free_mass"], {"target": 2.0, "stretch": 2.6, "stretch_high": 2.8,
                                                           "floor_min": 1.5})
        for n, needle in ((1, "1.6 g/kg"), (2, "2.2 g/kg"), (6, "~2.0 g/kg"), (6, "~2.6–2.8 g/kg"),
                          (7, "1.2 g/kg"), (7, "~1.5 g/kg"), (4, "~25 % for men or ~35 % for women"),
                          (5, "BMI is 30 or more"), (5, "10 % or more below"), (8, "~15–20 g")):
            with self.subTest(claim=n, needle=needle):
                self.assertIn(needle, self.claim(n))
        self.assertEqual((protein.HIGH_BMI, protein.GOAL_GAP_PCT, protein.FLOOR_ABOVE_INTAKE_G), (30, 10, 15))

    def test_each_calorie_number_is_the_one_its_claim_states(self):
        for n, needle in ((14, "10 × weight in kg + 6.25 × height in cm − 5 × age in years, + 5 for men or − 161 "
                                "for women"), (15, "1.53"), (15, "1.76"), (15, "2.25"), (16, "7700 kcal"),
                          (16, "nearest 50 kcal")):
            with self.subTest(claim=n, needle=needle):
                self.assertIn(needle, self.claim(n))


def estimate(**inputs):
    inputs.setdefault("unit", "kg")
    return calories.estimates(**inputs)


class CalorieTest(unittest.TestCase):
    MAN = {"sex": "male", "bodyweight": 80, "height_m": 1.8, "age": 30, "activity": "active"}

    def test_one_estimate_per_phase_with_the_method_shown(self):
        result = estimate(**self.MAN, phases=[("cut", -0.5), ("maintain", 0), ("bulk", 0.25)])
        self.assertEqual((result["resting_kcal"], result["activity_level"], result["maintenance_kcal"]),
                         (1780, 1.76, 3150))
        rows = [(e["phase"], e["rate_per_week"], e["adjustment_kcal"], e["kcal"]) for e in result["estimates"]]
        self.assertEqual(rows, [("cut", -0.5, -550, 2600), ("maintain", 0, 0, 3150), ("bulk", 0.25, 275, 3450)])
        self.assertEqual([e["below_resting"] for e in result["estimates"]], [False, False, False])
        self.assertIn("Mifflin", result["method"])
        self.assertEqual(result["refs"], [REF + "14", REF + "15", REF + "16"])
        self.assertEqual(result["missing"], [])

    def test_a_sedentary_woman(self):
        result = estimate(sex="female", bodyweight=60, height_m=1.65, age=40, activity="sedentary",
                          phases=[("cut", -0.4)])
        self.assertEqual((result["resting_kcal"], result["maintenance_kcal"]), (1270, 1950))
        self.assertEqual(result["estimates"][0]["kcal"], 1500)

    def test_pounds(self):
        result = estimate(unit="lb", sex="male", bodyweight=176.4, height_m=1.8, age=30, activity="active",
                          phases=[("cut", -1)])
        self.assertEqual(result["estimates"][0]["adjustment_kcal"], -499)
        self.assertEqual(result["estimates"][0]["unit"], "lb")

    def test_missing_inputs_are_named(self):
        result = estimate(sex=None, bodyweight=80, height_m=None, age=None, activity=None, phases=[])
        self.assertEqual([m["input"] for m in result["missing"]], ["sex", "height", "age", "activity", "phase"])
        self.assertIsNone(result["maintenance_kcal"])
        self.assertEqual(result["estimates"], [])

    def test_the_activity_levels_are_the_fao_reference_lifestyles(self):
        self.assertEqual(calories.ACTIVITY_LEVEL, {"sedentary": 1.53, "active": 1.76, "vigorous": 2.25})
        self.assertEqual(calories.KCAL_PER_KG, 7700)

    def test_method_names_the_numbers_it_uses(self):
        for needle in ("Mifflin–St Jeor", str(calories.KCAL_PER_KG), str(calories.ROUND_KCAL)):
            self.assertIn(needle, calories.METHOD)

    def test_kcal_is_the_shown_maintenance_plus_the_shown_adjustment(self):
        result = estimate(**self.MAN, phases=[("cut", -0.6)])
        row = result["estimates"][0]
        self.assertEqual(row["adjustment_kcal"], -660)
        self.assertEqual(row["kcal"], 2500)

    def test_an_estimate_under_the_resting_rate_is_flagged(self):
        result = estimate(sex="female", bodyweight=55, height_m=1.6, age=60, activity="sedentary",
                          phases=[("cut", -0.55)])
        row = result["estimates"][0]
        self.assertLess(row["kcal"], result["resting_kcal"])
        self.assertIs(row["below_resting"], True)

    def test_a_rate_outside_the_claims_is_refused(self):
        for phase in (("cut", -0.9), ("bulk", 0.45)):
            with self.subTest(phase=phase), self.assertRaises(ValidationError):
                estimate(**self.MAN, phases=[phase])
        self.assertEqual(estimate(**self.MAN, phases=[("cut", -0.8), ("bulk", 0.4)])["missing"], [])

    def test_a_rate_against_its_phase_is_refused(self):
        for phase in (("cut", 0.2), ("bulk", -0.2), ("maintain", 0.1), ("recomp", -0.1)):
            with self.subTest(phase=phase), self.assertRaises(ValidationError):
                estimate(**self.MAN, phases=[phase])


def run(root, *argv, env=NOW):
    code, envelope, stderr = run_cli(["--root", str(root), "nutrition", "targets", *argv], env=env)
    return code, envelope


class CliTest(unittest.TestCase):
    def ok(self, root, *argv, env=NOW):
        code, envelope = run(root, *argv, env=env)
        self.assertEqual(code, 0, envelope)
        return envelope["data"]

    def test_reads_bodyweight_and_intake_from_the_newest_reading(self):
        data = self.ok(VALID, "--height", "180")
        self.assertEqual(data["inputs"]["bodyweight"], {"value": 82.4, "unit": "kg", "from": "reading 2026-10-11"})
        self.assertEqual(data["inputs"]["recent_intake_g"], {"value": 115, "from": "reading 2026-10-11"})
        self.assertEqual(data["reference"]["basis"], "bodyweight")
        self.assertEqual(data["protein"]["floor"]["g"], 130)
        self.assertEqual(data["protein"]["target"]["g"], 130)

    def test_a_newer_scale_weight_beats_an_older_trend_weight(self):
        with InstanceCopy() as root:
            later = {"COACH_NOW": "2026-10-13T08:00:00Z"}
            code, envelope, stderr = run_cli(["--root", str(root), "nutrition", "record", "--date", "2026-10-13",
                                              "--scale-weight", "81.5"], env=later)
            self.assertEqual(code, 0, envelope)
            data = self.ok(root, "--height", "180", env=later)
            self.assertEqual(data["inputs"]["bodyweight"], {"value": 81.5, "unit": "kg", "from": "reading 2026-10-13"})

    def test_a_height_in_the_wrong_unit_exits_1(self):
        code, envelope = run(VALID, "--height", "1.8")
        self.assertEqual(code, 1, envelope)
        self.assertIn("cm", envelope["error"]["message"])

    def test_flags_override_the_files(self):
        data = self.ok(VALID, "--bodyweight", "80", "--recent-intake", "104", "--height", "180")
        self.assertEqual(data["inputs"]["bodyweight"]["from"], "flag")
        self.assertEqual(data["protein"]["floor"]["g"], 120)

    def test_goal_weight_from_config(self):
        with InstanceCopy() as root:
            edit_config(root, "target_rate_per_week = 0.0", "target_rate_per_week = -0.5\ngoal_weight = 74.0")
            data = self.ok(root)
            self.assertEqual(data["inputs"]["goal_weight"], {"value": 74.0, "unit": "kg", "from": "config"})
            self.assertEqual((data["reference"]["basis"], data["reference"]["mass"]), ("goal_weight", 74))

    def test_a_credible_reading_from_flags(self):
        data = self.ok(VALID, "--body-fat", "20", "--body-fat-source", "credible")
        self.assertEqual(data["reference"]["basis"], "fat_free_mass")
        self.assertEqual(data["inputs"]["body_fat"], {"pct": 20, "source": "credible"})

    def test_missing_height_is_named(self):
        data = self.ok(VALID)
        self.assertEqual(missing(data), ["height"])
        self.assertIsNone(data["protein"])

    def test_a_stale_reading_is_not_used(self):
        data = self.ok(VALID, "--height", "180", env={"COACH_NOW": "2026-11-11T18:00:00Z"})
        self.assertEqual(missing(data), ["bodyweight", "recent_intake"])
        self.assertIsNone(data["inputs"]["bodyweight"])

    def test_height_in_inches_for_a_pound_athlete(self):
        with InstanceCopy() as root:
            edit_config(root, 'bodyweight_units = "kg"', 'bodyweight_units = "lb"')
            data = self.ok(root, "--bodyweight", "180", "--height", "71", "--height-unit", "in",
                           "--recent-intake", "110")
            self.assertEqual(data["inputs"]["height_m"], 1.803)
            self.assertEqual(data["reference"]["basis"], "bodyweight")

    def test_works_without_nutrition_enabled(self):
        root = INSTANCES / "empty"
        data = self.ok(root, "--bodyweight", "80", "--height", "180", "--recent-intake", "100")
        self.assertEqual(data["protein"]["target"]["g"], 130)

    def test_body_fat_needs_its_source(self):
        code, envelope = run(VALID, "--body-fat", "20")
        self.assertEqual(code, 1, envelope)
        self.assertIn("--body-fat-source", envelope["error"]["message"])
        code, envelope = run(VALID, "--body-fat-source", "rough")
        self.assertEqual(code, 1, envelope)

    def test_out_of_range_inputs_exit_1(self):
        for argv in (("--body-fat", "0", "--body-fat-source", "rough"), ("--body-fat", "100", "--body-fat-source",
                     "rough"), ("--bodyweight", "-1"), ("--height", "0"), ("--recent-intake", "-5")):
            with self.subTest(argv=argv):
                code, envelope = run(VALID, *argv)
                self.assertEqual(code, 1, envelope)

    def test_an_app_athlete_gets_no_calorie_figure(self):
        data = self.ok(VALID, "--height", "180", "--age", "30", "--sex", "male", "--activity", "active")
        self.assertEqual(data["calories"]["by"], "app")
        self.assertNotIn("kcal", json.dumps(data["calories"]))

    def test_a_no_app_athlete_gets_an_estimate_for_the_phase_on_file(self):
        with InstanceCopy() as root:
            edit_config(root, 'app = "macrofactor"', 'app = "none"')
            edit_config(root, "target_rate_per_week = 0.0", "target_rate_per_week = -0.5")
            edit_config(root, 'phase = "recomp"', 'phase = "cut"')
            data = self.ok(root, "--height", "180", "--age", "30", "--sex", "male", "--activity", "active")
            self.assertEqual(data["calories"]["by"], "estimate")
            self.assertEqual([(e["phase"], e["rate_per_week"]) for e in data["calories"]["estimates"]],
                             [("cut", -0.5)])
            self.assertEqual(data["inputs"]["phases"], {"value": [["cut", -0.5]], "from": "config"})

    def test_phases_from_flags(self):
        data = self.ok(INSTANCES / "empty", "--app", "none", "--bodyweight", "80", "--height", "180", "--age", "30",
                       "--sex", "male", "--activity", "active", "--recent-intake", "100",
                       "--phase", "cut:-0.5", "--phase", "maintain:0")
        self.assertEqual([e["kcal"] for e in data["calories"]["estimates"]], [2600, 3150])
        self.assertEqual(missing(data), [])

    def test_no_app_on_file_or_in_flags_is_named(self):
        data = self.ok(INSTANCES / "empty", "--bodyweight", "80", "--height", "180", "--recent-intake", "100")
        self.assertIsNone(data["calories"])
        self.assertEqual(missing(data), ["app"])

    def test_calorie_inputs_are_named_once(self):
        data = self.ok(INSTANCES / "empty", "--app", "none", "--bodyweight", "80", "--recent-intake", "100",
                       "--phase", "cut:-0.5")
        self.assertEqual(missing(data), ["height", "sex", "age", "activity"])

    def test_a_bad_phase_exits_1(self):
        for value in ("cut", "shred:-0.5", "cut:fast", "cut:nan", "cut:inf", "cut:0.5", "bulk:-0.2",
                      "maintain:0.1"):
            with self.subTest(value=value):
                code, envelope = run(VALID, "--phase", value)
                self.assertEqual(code, 1, envelope)

    def test_a_rate_outside_the_claims_exits_1(self):
        code, envelope = run(INSTANCES / "empty", "--app", "none", "--bodyweight", "80", "--height", "180",
                             "--age", "30", "--sex", "male", "--activity", "active", "--phase", "cut:-1.5")
        self.assertEqual(code, 1, envelope)
        self.assertIn("1 %", envelope["error"]["message"])

    def test_age(self):
        base = ("--app", "none", "--bodyweight", "80", "--height", "180", "--sex", "male", "--activity", "active",
                "--recent-intake", "100", "--phase", "maintain:0")
        for age in ("0", "5", "150"):
            with self.subTest(age=age):
                code, envelope = run(INSTANCES / "empty", *base, "--age", age)
                self.assertEqual(code, 1, envelope)
        code, envelope = run(INSTANCES / "empty", *base, "--age", "82")
        self.assertEqual(code, 0, envelope)
        self.assertTrue(any("19–78" in warning for warning in envelope["warnings"]), envelope["warnings"])
        code, envelope = run(INSTANCES / "empty", *base, "--age", "40")
        self.assertEqual(envelope["warnings"], [])

    def test_an_estimate_under_the_resting_rate_warns(self):
        code, envelope = run(INSTANCES / "empty", "--app", "none", "--bodyweight", "55", "--height", "160",
                             "--age", "60", "--sex", "female", "--activity", "sedentary", "--recent-intake", "80",
                             "--phase", "cut:-0.55")
        self.assertEqual(code, 0, envelope)
        self.assertTrue(any("resting" in warning for warning in envelope["warnings"]), envelope["warnings"])

    def test_output_is_json_serialisable(self):
        json.dumps(self.ok(VALID, "--height", "180"))


if __name__ == "__main__":
    unittest.main()
