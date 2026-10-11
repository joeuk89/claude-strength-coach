import unittest

from tests.support import REPO_ROOT
from tests.test_nutrition import CliMixin, InstanceCopy, READINGS, edit_config


class MaintenanceTrendTest(CliMixin, unittest.TestCase):
    def test_maintenance_scenarios_preserve_rate_basis_and_app_ownership(self):
        for app in ("none", "macrofactor"):
            for intent in ("sleep-gated", "voluntary"):
                for end_weight, rate in ((79.1, -0.45), (80.9, 0.45)):
                    with self.subTest(app=app, intent=intent, rate=rate), InstanceCopy() as root:
                        if app == "none":
                            edit_config(root, 'app = "macrofactor"', 'app = "none"\nkcal_target = 2400')
                        (root / "profile.md").write_text(f"Maintenance recomp: {intent}. Target trend: zero.\n")
                        (root / READINGS).unlink()
                        weight_flag = "--scale-weight" if app == "none" else "--trend-weight"
                        self.run_ok(root, "nutrition", "record", "--date", "2026-09-27", weight_flag, "80")
                        self.run_ok(root, "nutrition", "record", "--date", "2026-10-04",
                                    weight_flag, str((80 + end_weight) / 2))
                        odd_week = self.run_ok(root, "nutrition", "status")
                        self.assertIsNone(odd_week["trend"]["rate_per_week"])
                        self.run_ok(root, "nutrition", "record", "--date", "2026-10-11", weight_flag, str(end_weight))
                        before = (root / "config.toml").read_bytes()
                        data = self.run_ok(root, "nutrition", "status")
                        self.assertEqual(data["phase"], "recomp")
                        self.assertEqual(data["trend"]["target_rate_per_week"], 0)
                        self.assertEqual(data["trend"]["rate_per_week"], rate)
                        self.assertEqual(data["trend"]["days"], 14)
                        self.assertEqual(data["trend"]["span"], {"start": "2026-09-27", "end": "2026-10-11"})
                        self.assertEqual(data["trend"]["basis"], weight_flag[2:].replace("-", "_"))
                        self.assertEqual(data["kcal_target"], 2400 if app == "none" else None)
                        self.assertEqual((root / "config.toml").read_bytes(), before)

    def test_coaching_workflow_covers_intent_symmetry_consent_and_app_ownership(self):
        text = (REPO_ROOT / ".claude/skills/check-in/nutrition.md").read_text()
        text = " ".join(text.split())
        for instruction in (
            "Read `data.trend.basis`, `span`, `days`",
            "Confirm the observation:",
            "One odd week does not automatically change calories",
            "**Maintenance recomp targets zero**",
            "whether chosen voluntarily or by the sleep gate",
            "-0.45 kg/week over 14 days is a review",
            "positive drift gets the converse review",
            "if so, route to `/goals`",
            "the app owns calorie adjustments",
            "Never supply a competing target or calorie adjustment",
            "upward for maintenance loss, downward for maintenance gain",
            "Obtain the athlete's yes before editing",
        ):
            self.assertIn(instruction, text)

    def test_goals_and_checkin_share_sleep_eligibility_contract(self):
        for path in (".claude/skills/goals/plan.md", ".claude/skills/check-in/nutrition.md"):
            self.assertIn("reference/nutrition-sleep.md", (REPO_ROOT / path).read_text())
        reference = " ".join((REPO_ROOT / "reference/nutrition-sleep.md").read_text().split())
        for instruction in ("low-confidence coaching heuristic", "trailing 14-day average",
                            "under 7 hours", "at or above 7 hours", "No hours source:",
                            "otherwise a deficit may proceed", "not evaluated",
                            "A period mean cannot establish that count"):
            self.assertIn(instruction, reference)


if __name__ == "__main__":
    unittest.main()
