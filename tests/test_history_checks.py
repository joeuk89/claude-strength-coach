"""History checks: history_schema, history_unresolved and annotations_valid (contract C13, C17)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support import INSTANCES, VALID, run_cli
from tests.support.history import W


def run_check(root, check_id):
    code, envelope, _ = run_cli(["--root", str(root), "check", "--only", check_id])
    return code, [(r["status"], r["message"], r["path"]) for r in envelope["data"]["results"]]


class HistorySchemaTest(unittest.TestCase):
    def test_passes_on_the_slip_history(self):
        self.assertEqual(run_check(INSTANCES / "slip", "history_schema")[1][0][0], "pass")

    def test_fails_naming_the_file_and_path(self):
        code, results = run_check(INSTANCES / "history-bad-schema", "history_schema")
        self.assertEqual(code, 1)
        self.assertEqual([r[0] for r in results], ["fail"])
        self.assertIn("weight", results[0][1])
        self.assertEqual(results[0][2], "data/history/2026-10.json")

    def test_skips_without_history(self):
        self.assertEqual(run_check(VALID, "history_schema")[1][0][0], "skip")


class HistoryUnresolvedTest(unittest.TestCase):
    def test_warns_on_an_exercise_with_no_library_match(self):
        code, results = run_check(INSTANCES / "history-unresolved", "history_unresolved")
        self.assertEqual(code, 0)
        self.assertEqual([r[0] for r in results], ["warn"])
        self.assertIn("Mystery Lift", results[0][1])
        self.assertIn("2026-10-05", results[0][1])

    def test_passes_when_every_exercise_resolved(self):
        self.assertEqual(run_check(INSTANCES / "slip", "history_unresolved")[1][0][0], "pass")


class AnnotationsValidTest(unittest.TestCase):
    def test_fails_on_a_workout_the_history_lacks(self):
        code, results = run_check(INSTANCES / "annotations-invalid", "annotations_valid")
        self.assertEqual(code, 1)
        self.assertEqual([r[0] for r in results], ["fail"])
        self.assertIn("a-0001", results[0][1])
        self.assertIn("10000000-0000-4000-8000-000000000099", results[0][1])

    def test_passes_on_annotations_the_command_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "slip", root)
            code, envelope, _ = run_cli(["--root", str(root), "history", "annotate", "--kind", "discount",
                                         "--workout", W[3], "--exercise", "db_bench_press", "--reason", "slip"],
                                        env={"COACH_NOW": "2026-10-11T18:00:00Z"})
            self.assertEqual(code, 0, envelope)
            self.assertEqual(run_check(root, "annotations_valid")[1][0][0], "pass")

    def test_skips_without_annotations(self):
        self.assertEqual(run_check(INSTANCES / "slip", "annotations_valid")[1][0][0], "skip")


if __name__ == "__main__":
    unittest.main()
