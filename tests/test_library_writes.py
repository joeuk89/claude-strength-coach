"""Commands that write the instance library: confirm, set-mode, set-avoid; and the library checks."""

import json
import unittest

from tests.support import INSTANCES, VALID
from tests.test_library import CliMixin, Instance, read_library, write_library

UNCONFIRMED = INSTANCES / "library-unconfirmed"
INVALID = INSTANCES / "library-invalid"
REASON = "shoulder: no pressing from the bottom position"


class ConfirmTest(CliMixin, unittest.TestCase):
    def test_confirm_named_ids(self):
        with Instance(UNCONFIRMED) as root:
            data = self.run_ok(root, "library", "confirm", "db_bench_press")
            entry = read_library(root)["exercises"]["db_bench_press"]
        self.assertEqual(entry["load_mode"], "per_hand_x2")
        self.assertEqual(data["confirmed"], [{"id": "db_bench_press", "load_mode": "per_hand_x2", "previous": None}])
        self.assertEqual(data["still_unconfirmed"], [])

    def test_confirm_dry_run_writes_nothing(self):
        with Instance(UNCONFIRMED) as root:
            before = read_library(root)
            data = self.run_ok(root, "library", "confirm", "--all", "--dry-run")
            self.assertEqual(read_library(root), before)
        self.assertEqual([row["id"] for row in data["confirmed"]], ["db_bench_press"])
        self.assertFalse(data["written"])

    def test_confirm_without_a_proposal(self):
        with Instance(UNCONFIRMED) as root:
            envelope = self.run_fail(1, root, "library", "confirm", "db_curl")
        self.assertIn("db_curl", envelope["error"]["message"])
        self.assertIn("set-mode", envelope["error"]["message"])

    def test_confirm_unknown_id(self):
        with Instance(UNCONFIRMED) as root:
            envelope = self.run_fail(1, root, "library", "confirm", "no_such_exercise")
        self.assertIn("no_such_exercise", envelope["error"]["message"])

    def test_confirm_needs_ids_or_all(self):
        with Instance(UNCONFIRMED) as root:
            self.run_fail(2, root, "library", "confirm")
            self.run_fail(2, root, "library", "confirm", "--all", "db_bench_press")


class SetModeTest(CliMixin, unittest.TestCase):
    def test_set_mode(self):
        with Instance(UNCONFIRMED) as root:
            data = self.run_ok(root, "library", "set-mode", "db_bench_press", "single_implement")
            self.assertEqual(read_library(root)["exercises"]["db_bench_press"]["load_mode"], "single_implement")
        self.assertTrue(data["written"])

    def test_set_mode_creates_the_entry_and_the_file(self):
        with Instance() as root:
            self.run_ok(root, "library", "set-mode", "db_curl", "single_implement")
            doc = read_library(root)
        self.assertEqual(doc, {"schema_version": 1, "exercises": {"db_curl": {"load_mode": "single_implement"}}})

    def test_set_mode_dry_run_writes_nothing(self):
        with Instance() as root:
            self.run_ok(root, "library", "set-mode", "db_curl", "single_implement", "--dry-run")
            self.assertFalse((root / "data" / "exercises.json").exists())

    def test_invalid_mode_exits_1_listing_the_modes(self):
        with Instance(VALID) as root:
            envelope = self.run_fail(1, root, "library", "set-mode", "db_bench_press", "nonsense")
        message = envelope["error"]["message"]
        self.assertEqual(envelope["error"]["code"], "validation")
        for mode in ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band", "duration", "distance"):
            self.assertIn(mode, message)

    def test_unknown_id(self):
        with Instance(VALID) as root:
            envelope = self.run_fail(1, root, "library", "set-mode", "no_such_exercise", "total")
        self.assertIn("no_such_exercise", envelope["error"]["message"])


class SetAvoidTest(CliMixin, unittest.TestCase):
    def test_dry_run_then_set_then_list_then_clear(self):
        with Instance(VALID) as root:
            before = read_library(root)
            self.run_ok(root, "library", "set-avoid", "db_bench_press", "--reason", REASON, "--dry-run")
            self.assertEqual(read_library(root), before)

            self.run_ok(root, "library", "set-avoid", "db_bench_press", "--reason", REASON)
            self.assertEqual(read_library(root)["exercises"]["db_bench_press"]["avoid"], {"reason": REASON})

            data = self.run_ok(root, "library", "list", "--avoided")
            self.assertEqual([(row["id"], row["avoid"]) for row in data["exercises"]],
                             [("db_bench_press", {"reason": REASON})])

            self.run_ok(root, "library", "set-avoid", "db_bench_press", "--clear")
            self.assertIsNone(read_library(root)["exercises"]["db_bench_press"]["avoid"])
            self.assertEqual(self.run_ok(root, "library", "list", "--avoided")["exercises"], [])

    def test_creates_the_instance_entry(self):
        with Instance() as root:
            self.run_ok(root, "library", "set-avoid", "db_bench_press", "--reason", REASON)
            doc = read_library(root)
        self.assertEqual(doc["exercises"], {"db_bench_press": {"avoid": {"reason": REASON}}})

    def test_empty_reason_exits_1(self):
        with Instance(VALID) as root:
            before = read_library(root)
            self.run_fail(1, root, "library", "set-avoid", "db_bench_press", "--reason", "")
            self.run_fail(1, root, "library", "set-avoid", "db_bench_press", "--reason", "   ")
            self.assertEqual(read_library(root), before)

    def test_unknown_id_exits_1_naming_it(self):
        with Instance(VALID) as root:
            envelope = self.run_fail(1, root, "library", "set-avoid", "no_such_exercise", "--reason", "x")
        self.assertIn("no_such_exercise", envelope["error"]["message"])

    def test_needs_reason_or_clear(self):
        with Instance(VALID) as root:
            self.run_fail(2, root, "library", "set-avoid", "db_bench_press")
            self.run_fail(2, root, "library", "set-avoid", "db_bench_press", "--reason", "x", "--clear")

    def test_validate_names_an_avoid_without_reason(self):
        with Instance(VALID) as root:
            write_library(root, {"db_bench_press": {"avoid": {}}})
            envelope = self.run_fail(1, root, "library", "validate")
        paths = [detail["path"] for detail in envelope["error"]["details"]]
        self.assertIn("$.exercises.db_bench_press.avoid", paths)


class LoadModesConfirmedCheckTest(CliMixin, unittest.TestCase):
    def results(self, envelope_or_data):
        data = envelope_or_data.get("data", envelope_or_data)
        return data["results"]

    def test_unconfirmed_exercise_fails_naming_it(self):
        envelope = self.run_fail(1, UNCONFIRMED, "check", "--only", "load_modes_confirmed")
        failures = [r for r in self.results(envelope) if r["status"] == "fail"]
        self.assertEqual(len(failures), 1)
        self.assertIn("db_bench_press", failures[0]["message"])
        self.assertIn("Session A", failures[0]["message"])

    def test_valid_fixture_passes(self):
        data = self.run_ok(VALID, "check", "--only", "load_modes_confirmed")
        self.assertEqual([r["status"] for r in self.results(data)], ["pass"])

    def test_routine_exercise_with_no_library_entry_fails(self):
        with Instance(INSTANCES / "library-seed") as root:
            envelope = self.run_fail(1, root, "check", "--only", "load_modes_confirmed")
        messages = " ".join(r["message"] for r in self.results(envelope))
        self.assertIn("Tyre Flip", messages)
        self.assertIn("library seed", messages)

    def test_overlay_exercise_without_a_confirmed_mode_fails(self):
        with Instance(VALID) as root:
            overlay = {"schema_version": 1, "id": "2026-10-12-weekly", "sessions": [
                {"session_id": "session-a", "exercises": [{"exercise_id": "db_bench_press"}, {"exercise_id": "db_curl"}]},
            ]}
            path = root / "data" / "overlays" / "2026-10-12-weekly.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(overlay), encoding="utf-8")
            envelope = self.run_fail(1, root, "check", "--only", "load_modes_confirmed")
        failures = [r for r in self.results(envelope) if r["status"] == "fail"]
        self.assertEqual(len(failures), 1)
        self.assertIn("db_curl", failures[0]["message"])
        self.assertIn("2026-10-12-weekly", failures[0]["message"])

    def test_invalid_library_fails(self):
        envelope = self.run_fail(1, INVALID, "check", "--only", "load_modes_confirmed")
        self.assertIn("library_valid", self.results(envelope)[0]["message"])


class LibraryValidCheckTest(CliMixin, unittest.TestCase):
    def test_valid_fixture_passes(self):
        data = self.run_ok(VALID, "check", "--only", "library_valid")
        self.assertEqual([r["status"] for r in data["results"]], ["pass"])

    def test_invalid_fixture_fails_with_the_jsonpath(self):
        envelope = self.run_fail(1, INVALID, "check", "--only", "library_valid")
        failures = envelope["data"]["results"]
        self.assertEqual({r["status"] for r in failures}, {"fail"})
        self.assertTrue(any("$.exercises.db_bench_press.colour" in r["message"] for r in failures))
        self.assertEqual(failures[0]["path"], "data/exercises.json")

    def test_no_instance_file_passes(self):
        with Instance() as root:
            data = self.run_ok(root, "check", "--only", "library_valid")
        self.assertEqual(data["results"][0]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
