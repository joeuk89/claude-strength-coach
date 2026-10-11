"""`nutrition targets`: the protein reference mass, floor, target and stretch (contract C35)."""

import json
import unittest

from coach import protein, research
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
        self.assertEqual((reference["basis"], reference["mass"], reference["bmi"]), ("bodyweight", 80, 24.7))
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
        self.assertEqual(protein.PER_KG["other"], (1.6, 2.2, 2.2, 1.2))
        self.assertEqual(protein.PER_KG["fat_free_mass"], (2.0, 2.6, 2.8, 1.5))
        for n, needle in ((1, "1.6 g/kg"), (2, "2.2 g/kg"), (6, "~2.0 g/kg"), (6, "~2.6–2.8 g/kg"),
                          (7, "1.2 g/kg"), (7, "~1.5 g/kg"), (4, "~25 % for men or ~35 % for women"),
                          (5, "BMI is 30 or more"), (5, "10 % or more below"), (8, "~15–20 g")):
            with self.subTest(claim=n, needle=needle):
                self.assertIn(needle, self.claim(n))
        self.assertEqual((protein.HIGH_BMI, protein.GOAL_GAP_PCT, protein.FLOOR_ABOVE_INTAKE_G), (30, 10, 15))


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

    def test_output_is_json_serialisable(self):
        json.dumps(self.ok(VALID, "--height", "180"))


if __name__ == "__main__":
    unittest.main()
