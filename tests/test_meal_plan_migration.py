"""Migration preserves saved meal choices without carrying approval across a changed hash."""

import json
import unittest

from coach import meals
from tests.test_meals import CliMixin, InstanceCopy, NOW_DT, PLAN_ID, PLAN_JSON, PLAN_MD, build
from tests.test_migrate import git, snapshot


def write_v1(root, approval):
    doc = build(root=root)
    doc["schema_version"] = 1
    doc["flags"] = [flag for flag in doc["flags"] if flag["code"] != "anchor_shopping_unknown"]
    if approval != "none":
        doc = meals.approve(doc, NOW_DT)
    if approval == "stale":
        doc["input"]["notes"] = "Changed after approval"
    (root / PLAN_JSON).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


class MealPlanMigrationTest(CliMixin, unittest.TestCase):
    def test_old_and_newer_versions_name_the_supported_next_action(self):
        with InstanceCopy() as root:
            doc = write_v1(root, "none")
            old = self.run_code(1, root, "meals", "show", PLAN_ID)
            self.assertIn("python3 -m coach migrate run", old["error"]["message"])
            status = self.run_ok(root, "migrate", "status")
            row = next(row for row in status["files"] if row["path"] == PLAN_JSON.as_posix())
            self.assertEqual((row["version"], row["target"], row["state"]), (1, 2, "behind"))
            doc["schema_version"] = 3
            (root / PLAN_JSON).write_text(json.dumps(doc), encoding="utf-8")
            newer = self.run_code(1, root, "meals", "show", PLAN_ID)
            self.assertIn("/framework-sync", newer["error"]["message"])

    def test_dry_run_preserves_every_file_and_reports_approval_loss(self):
        with InstanceCopy() as root:
            write_v1(root, "approved")
            before = snapshot(root)
            report = self.run_ok(root, "migrate", "run", "--dry-run")
            self.assertEqual(snapshot(root), before)
        self.assertFalse(report["written"])
        self.assertIsNone(report["backup"])
        self.assertEqual(report["staged"], [])
        self.assertEqual(report["files"], [{"path": PLAN_JSON.as_posix(), "doc": "meal_plan", "from": 1, "to": 2,
                                          "steps": ["meal_plan/0001_anchor_shopping_coverage"]}])
        self.assertTrue(any("loses its approval" in note for note in report["notes"]))
        self.assertTrue(any(f"meals render {PLAN_ID}" in note for note in report["notes"]))

    def test_migration_backs_up_stages_and_requires_fresh_approval(self):
        for approval in ("none", "approved", "stale"):
            with self.subTest(approval=approval), InstanceCopy() as root:
                old = write_v1(root, approval)
                original = (root / PLAN_JSON).read_bytes()
                old_render = (root / PLAN_MD).read_bytes()
                git(root, "init", "-q")
                git(root, "add", "-A")
                git(root, "commit", "-q", "-m", "baseline")
                report = self.run_ok(root, "migrate", "run")
                self.assertTrue(report["written"])
                self.assertEqual((root / report["backup"] / PLAN_JSON).read_bytes(), original)
                self.assertEqual(report["staged"], [PLAN_JSON.as_posix()])
                self.assertEqual(git(root, "diff", "--cached", "--name-only").split(), [PLAN_JSON.as_posix()])
                self.assertEqual(git(root, "rev-list", "--count", "HEAD").strip(), "1")
                migrated = meals.load(root, PLAN_ID)
                self.assertEqual(migrated, dict(old, schema_version=2))
                self.assertFalse(meals.is_approved(migrated))
                self.assertEqual((root / PLAN_MD).read_bytes(), old_render)
                self.assertEqual(meals.validate(migrated), [])
                rendered = self.run_ok(root, "meals", "render", PLAN_ID)
                self.assertIn("not yet approved", rendered["text"])
                self.assertNotIn("anchor_shopping_unknown", rendered["text"])
                self.run_code(3, root, "meals", "shopping", PLAN_ID, "--format", "issue")
                self.run_ok(root, "meals", "approve", PLAN_ID)
                self.run_ok(root, "meals", "shopping", PLAN_ID, "--format", "issue")
                before_repeat = snapshot(root)
                repeated = self.run_ok(root, "migrate", "run")
                self.assertFalse(repeated["written"])
                self.assertEqual(snapshot(root), before_repeat)
                self.assertTrue(meals.is_approved(meals.load(root, PLAN_ID)))


if __name__ == "__main__":
    unittest.main()
