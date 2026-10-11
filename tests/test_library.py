"""The exercise library: merge rules, lookups, and the read-only commands."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import jsonio
from coach.errors import ValidationError
from coach.library import Library
from coach.validate import validate
from tests.support import INSTANCES, MINIMAL_CONFIG, VALID, run_cli

ENVELOPE = jsonio.load_schema("envelope")


def write_library(root, exercises):
    path = Path(root) / "data" / "exercises.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "exercises": exercises}), encoding="utf-8")
    return path


def read_library(root):
    return json.loads((Path(root) / "data" / "exercises.json").read_text(encoding="utf-8"))


class Instance:
    """A temporary instance: a copy of a fixture instance, or just a minimal config."""

    def __init__(self, fixture=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "instance"
        if fixture is None:
            self.root.mkdir()
            (self.root / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
        else:
            shutil.copytree(fixture, self.root)

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


class CliMixin:
    def run_ok(self, root, *argv):
        code, envelope, stderr = run_cli(["--root", str(root), *argv])
        self.assertEqual(code, 0, (envelope, stderr))
        self.assertEqual(validate(envelope, ENVELOPE), [])
        return envelope["data"]

    def run_fail(self, code, root, *argv):
        actual, envelope, stderr = run_cli(["--root", str(root), *argv])
        self.assertEqual(actual, code, (envelope, stderr))
        self.assertEqual(validate(envelope, ENVELOPE), [])
        self.assertFalse(envelope["ok"])
        return envelope


class MergeTest(unittest.TestCase):
    def test_catalogue_only_without_an_instance_file(self):
        with Instance() as root:
            lib = Library.load(root)
            entry = lib.get("db_bench_press")
        self.assertEqual(entry["load_mode_default"], "per_hand_x2")
        self.assertEqual(entry["source"], "catalogue")
        self.assertIsNone(entry["load_mode"])
        self.assertIsNone(lib.effective_load_mode("db_bench_press"))

    def test_instance_fields_override_the_catalogue(self):
        with Instance() as root:
            write_library(root, {"db_curl": {
                "load_mode_default": "single_implement",
                "aliases": ["alternating curl"],
                "load_mode": "single_implement",
            }})
            entry = Library.load(root).get("db_curl")
        self.assertEqual(entry["load_mode_default"], "single_implement")
        self.assertEqual(entry["aliases"], ["alternating curl"])
        self.assertEqual(entry["name"], "Bicep Curl (Dumbbell)")
        self.assertEqual(entry["overridden"], ["aliases", "load_mode_default"])

    def test_effective_load_mode_is_the_confirmed_mode_only(self):
        with Instance() as root:
            write_library(root, {
                "db_curl": {"load_mode_proposed": "per_hand_x2", "confidence": "high"},
                "db_lateral_raise": {"load_mode": "single_implement"},
            })
            lib = Library.load(root)
        self.assertIsNone(lib.effective_load_mode("db_curl"))
        self.assertEqual(lib.effective_load_mode("db_lateral_raise"), "single_implement")
        self.assertIsNone(lib.effective_load_mode("no_such_exercise"))

    def test_custom_entry_needs_its_core_fields_and_gets_defaults(self):
        custom = {
            "name": "Tyre Flip", "muscles": {"primary": ["full_body"], "secondary": []},
            "pattern": "conditioning", "equipment": "other", "load_mode_default": "total",
            "hevy_template_id": "C0000001",
        }
        with Instance() as root:
            write_library(root, {"custom_tyre_flip": custom})
            lib = Library.load(root)
            entry = lib.get("custom_tyre_flip")
        self.assertEqual(entry["source"], "custom")
        self.assertEqual(entry["aliases"], [])
        self.assertEqual(entry["substitutes"], [])
        self.assertIsNone(entry["increment"])
        self.assertEqual(lib.by_hevy_template_id("C0000001")["id"], "custom_tyre_flip")

    def test_hevy_template_id_is_found_from_the_instance_and_the_catalogue(self):
        with Instance() as root:
            write_library(root, {"db_bench_press": {"hevy_template_id": "F0000002"}})
            lib = Library.load(root)
        self.assertEqual(lib.by_hevy_template_id("F0000002")["id"], "db_bench_press")
        self.assertEqual(lib.get("db_bench_press")["hevy_template_ids"], ["F0000002"])
        self.assertIsNone(lib.by_hevy_template_id("NOPE"))

    def test_increment_and_avoided(self):
        with Instance() as root:
            write_library(root, {"db_bench_press": {"avoid": {"reason": "shoulder"}, "increment": {"kg": 1, "lb": 2.5}}})
            lib = Library.load(root)
        self.assertEqual(lib.increment("db_bench_press", "kg"), 1)
        self.assertEqual(lib.increment("db_bench_press", "lb"), 2.5)
        self.assertEqual(lib.increment("bb_back_squat", "lb"), 5)
        self.assertIsNone(lib.increment("plank", "kg"))
        self.assertEqual(lib.avoided("db_bench_press"), {"reason": "shoulder"})
        self.assertIsNone(lib.avoided("bb_back_squat"))

    def test_search_ranks_exact_names_first(self):
        with Instance() as root:
            lib = Library.load(root)
        found = [hit["id"] for hit in lib.search("db bench")]
        self.assertEqual(found[0], "db_bench_press")
        self.assertIn("db_incline_bench_press", found)
        self.assertEqual(lib.search("Bench Press (Dumbbell)")[0]["id"], "db_bench_press")
        self.assertEqual(lib.search("zzz"), [])


class InvalidInstanceTest(unittest.TestCase):
    def assert_invalid(self, exercises, path):
        with Instance() as root:
            write_library(root, exercises)
            with self.assertRaises(ValidationError) as caught:
                Library.load(root)
        paths = [detail["path"] for detail in caught.exception.details]
        self.assertIn(path, paths, caught.exception.details)

    def test_unknown_field(self):
        self.assert_invalid({"db_bench_press": {"colour": "blue"}}, "$.exercises.db_bench_press.colour")

    def test_avoid_without_reason(self):
        self.assert_invalid({"db_bench_press": {"avoid": {}}}, "$.exercises.db_bench_press.avoid")

    def test_empty_avoid_reason(self):
        self.assert_invalid({"db_bench_press": {"avoid": {"reason": " "}}}, "$.exercises.db_bench_press.avoid.reason")

    def test_unknown_id_without_the_custom_prefix(self):
        self.assert_invalid({"tyre_flip": {"name": "Tyre Flip"}}, "$.exercises.tyre_flip")

    def test_bad_id(self):
        self.assert_invalid({"Bench Press": {}}, "$.exercises['Bench Press']")
        self.assert_invalid({"Bench": {}}, "$.exercises.Bench")

    def test_custom_entry_missing_fields(self):
        self.assert_invalid({"custom_tyre_flip": {"name": "Tyre Flip"}}, "$.exercises.custom_tyre_flip")

    def test_unknown_substitute(self):
        self.assert_invalid({"db_bench_press": {"substitutes": ["nope"]}}, "$.exercises.db_bench_press.substitutes[0]")

    def test_alias_clash_with_another_entry(self):
        self.assert_invalid({"db_curl": {"aliases": ["hammer curl"]}}, "$.exercises.db_curl.aliases[0]")

    def test_hevy_template_id_on_two_entries(self):
        self.assert_invalid(
            {"db_curl": {"hevy_template_id": "X1"}, "db_hammer_curl": {"hevy_template_id": "X1"}},
            "$.exercises.db_hammer_curl.hevy_template_id",
        )

    def test_newer_schema_version(self):
        with Instance() as root:
            path = write_library(root, {})
            path.write_text(json.dumps({"schema_version": 99, "exercises": {}}), encoding="utf-8")
            with self.assertRaises(ValidationError) as caught:
                Library.load(root)
        self.assertIn("/framework-sync", caught.exception.message)


class ReadCommandsTest(CliMixin, unittest.TestCase):
    def test_show_valid_db_bench_press(self):
        data = self.run_ok(VALID, "library", "show", "db_bench_press")
        entry = data["exercise"]
        self.assertEqual(entry["id"], "db_bench_press")
        self.assertEqual(entry["effective_load_mode"], "per_hand_x2")
        self.assertEqual(entry["hevy_template_id"], "F0000002")
        self.assertEqual(entry["pattern"], "horizontal_push")

    def test_show_unknown_id_suggests(self):
        envelope = self.run_fail(1, VALID, "library", "show", "db_bench")
        self.assertIn("db_bench", envelope["error"]["message"])
        self.assertIn("db_bench_press", envelope["error"]["message"])

    def test_list(self):
        data = self.run_ok(VALID, "library", "list")
        rows = {row["id"]: row for row in data["exercises"]}
        self.assertEqual(rows["pull_up"]["effective_load_mode"], "bodyweight")
        self.assertIsNone(rows["db_curl"]["effective_load_mode"])
        self.assertEqual(data["count"], len(data["exercises"]))

    def test_search(self):
        data = self.run_ok(VALID, "library", "search", "romanian deadlift")
        ids = [hit["id"] for hit in data["matches"]]
        self.assertIn("bb_romanian_deadlift", ids)
        self.assertIn("db_romanian_deadlift", ids)

    def test_validate_valid(self):
        data = self.run_ok(VALID, "library", "validate")
        self.assertTrue(data["valid"])
        self.assertEqual(data["instance_entries"], 4)

    def test_validate_names_the_unknown_field(self):
        envelope = self.run_fail(1, INSTANCES / "library-invalid", "library", "validate")
        paths = [detail["path"] for detail in envelope["error"]["details"]]
        self.assertIn("$.exercises.db_bench_press.colour", paths)
        self.assertEqual(envelope["error"]["code"], "validation")


if __name__ == "__main__":
    unittest.main()
