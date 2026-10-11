"""The state document and `state show` (contract C16)."""

import json
import tempfile
import unittest
from datetime import datetime, timezone

from coach import jsonio, migrate, program, state
from coach.errors import ValidationError
from tests.support import INSTANCES, VALID
from tests.test_cli import EnvelopeMixin
from tests.test_program import Instance


def valid_state():
    return json.loads((VALID / "data" / "state.json").read_text(encoding="utf-8"))


def problem_paths(doc):
    return [error.path for error in state.problems(doc, program.load(VALID))]


class StateTest(unittest.TestCase):
    def test_valid_state_loads(self):
        doc = state.load(VALID)
        self.assertEqual(doc["hevy"]["routines"]["00000000-0000-4000-8000-000000000001"], {"session_id": "session-a"})
        self.assertEqual(problem_paths(doc), [])

    def test_missing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValidationError) as caught:
                state.load(tmp)
        self.assertIn("data/state.json", caught.exception.message)

    def test_misspelt_key(self):
        doc = valid_state()
        doc["rotation"]["confirmd"] = True
        self.assertIn("$.rotation.confirmd", problem_paths(doc))

    def test_routine_for_an_unknown_session(self):
        doc = valid_state()
        doc["hevy"]["routines"]["r-3"] = {"session_id": "session-c"}
        self.assertIn("$.hevy.routines['r-3'].session_id", problem_paths(doc))

    def test_scheme_state_key_names_a_program_slot(self):
        doc = valid_state()
        doc["scheme_state"]["session-b/bb_back_squat"] = {}
        doc["scheme_state"]["squat"] = {}
        paths = problem_paths(doc)
        self.assertIn("$.scheme_state['session-b/bb_back_squat']", paths)
        self.assertIn("$.scheme_state.squat", paths)

    def test_one_off_span_order(self):
        doc = valid_state()
        doc["one_off"] = {"overlay_id": "2026-10-12-one-off", "span": {"start": "2026-10-18", "end": "2026-10-12"}}
        self.assertIn("$.one_off.span", problem_paths(doc))

    def test_impossible_date(self):
        doc = valid_state()
        doc["block"]["started"] = "2026-02-30"
        self.assertIn("$.block.started", problem_paths(doc))


class TemporaryRoutineMigrationTest(unittest.TestCase):
    def test_v1_routine_ids_become_entries_that_carry_nothing(self):
        doc = valid_state()
        doc["schema_version"] = 1
        doc["rotation"].pop("week")
        doc["scheme_state"] = {slot: entry["data"] for slot, entry in doc["scheme_state"].items()}
        doc["hevy"]["temporary_routines"] = ["t-1", "t-2"]
        doc["block"] = {"started": "2026-09-28", "hard_weeks_completed": 2,
                        "deload": {"status": "not_due", "since": None}}
        with Instance() as root:
            (root / "data" / "state.json").write_text(json.dumps(doc), encoding="utf-8")
            migrate.run(root, dry_run=False, now=datetime(2026, 10, 11, 18, tzinfo=timezone.utc))
            upgraded = state.load(root)
        self.assertEqual(upgraded["schema_version"], jsonio.current_version(jsonio.load_schema("state")))
        self.assertEqual(upgraded["hevy"]["temporary_routines"],
                         [{"routine_id": "t-1", "overlay_id": None, "session_id": None},
                          {"routine_id": "t-2", "overlay_id": None, "session_id": None}])


class StateShowTest(EnvelopeMixin, unittest.TestCase):
    def test_show(self):
        data = self.run_ok("--root", str(VALID), "state", "show")
        self.assertEqual(data["path"], "data/state.json")
        self.assertEqual(data["state"]["block"]["light_week"]["status"], "not_due")

    def test_invalid_state_exits_1(self):
        envelope, _ = self.run_fail(1, "--root", str(INSTANCES / "state-bad-schema"), "state", "show")
        self.assertIn("$.block.light_week.status", [d["path"] for d in envelope["error"]["details"]])

    def test_cross_reference_problem_exits_1(self):
        doc = valid_state()
        doc["hevy"]["routines"]["r-3"] = {"session_id": "session-c"}
        with Instance() as root:
            (root / "data" / "state.json").write_text(json.dumps(doc), encoding="utf-8")
            envelope, _ = self.run_fail(1, "--root", str(root), "state", "show")
        self.assertIn("session-c", " ".join(d["message"] for d in envelope["error"]["details"]))


if __name__ == "__main__":
    unittest.main()
