"""A load mode corrected after a program line was written: validation names the slot, reconcile-mode settles it."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import units
from tests.support import INSTANCES, VALID, run_cli
from tests.support.skills import flat, step_text

EMPTY = INSTANCES / "empty"
NOW = "2026-10-11T18:00:00Z"
WEEK = "2026-W42"
DRAFT = ".coach/drafts/program.json"


def instance(test, source):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name) / "instance"
    shutil.copytree(source, root)
    return root


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, doc):
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def cable_fly_lines(doc):
    return [(session["id"], line) for session in doc["sessions"] for line in session["exercises"]
            if line["exercise_id"] == "cable_fly"]


class Case(unittest.TestCase):
    def cli(self, root, *argv):
        return run_cli(["--root", str(root), *argv], env={"COACH_NOW": NOW})

    def ok(self, root, *argv):
        code, envelope, stderr = self.cli(root, *argv)
        self.assertEqual(code, 0, (argv, envelope, stderr))
        return envelope

    def fails(self, root, *argv, code=1):
        found, envelope, stderr = self.cli(root, *argv)
        self.assertEqual(found, code, (argv, envelope, stderr))
        return envelope

    def adopted_ppl(self):
        """The push/pull/legs starter adopted with cable fly at 20, before its load mode was confirmed."""
        root = instance(self, EMPTY)
        self.ok(root, "starters", "draft", "push-pull-legs", "--start-load", "cable_fly=20")
        self.ok(root, "program", "adopt", "--input", str(root / DRAFT))
        return root


class PostAdoptionCorrectionTest(Case):
    """Setup adopted cable fly as total 20; the athlete then says it is loaded per hand."""

    def setUp(self):
        self.root = self.adopted_ppl()
        self.program = self.root / "data" / "program.json"
        envelope = self.ok(self.root, "library", "set-mode", "cable_fly", "per_hand_x2")
        self.set_mode = envelope

    def test_set_mode_reports_the_program_slot_it_leaves_behind(self):
        slots = self.set_mode["data"]["program_slots"]
        self.assertEqual([(s["session_id"], s["load_mode"], s["start_load"]) for s in slots], [("push", "total", 20)])
        self.assertTrue(any("reconcile-mode cable_fly" in w for w in self.set_mode["warnings"]))

    def test_program_validate_names_the_slot_before_any_proposal(self):
        error = self.fails(self.root, "program", "validate")["error"]
        mismatches = [d for d in error["details"] if d["path"].endswith(".load_mode")]
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["path"], "$.sessions[0].exercises[4].load_mode")
        message = mismatches[0]["message"]
        for needle in ("cable_fly", "push", "total", "per_hand_x2", "20", "reconcile-mode cable_fly --basis"):
            self.assertIn(needle, message)

    def test_schema_validity_does_not_clear_the_mismatch(self):
        checks = self.fails(self.root, "check", "--only", "program_schema,program_exercise_ids")["data"]["results"]
        by_id = {}
        for result in checks:
            by_id.setdefault(result["id"], []).append(result)
        self.assertEqual({r["status"] for r in by_id["program_schema"]}, {"pass"})
        failed = [r for r in by_id["program_exercise_ids"] if r["status"] == "fail"]
        self.assertEqual(len(failed), 1)
        self.assertIn("cable_fly", failed[0]["message"])

    def test_the_basis_is_required(self):
        before = self.program.read_bytes()
        self.fails(self.root, "program", "reconcile-mode", "cable_fly", code=2)
        self.assertEqual(self.program.read_bytes(), before)

    def test_old_basis_converts_20_total_to_10_per_hand_and_reaches_a_valid_proposal(self):
        preview = self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old", "--dry-run")["data"]
        self.assertFalse(preview["written"])
        self.assertEqual([(c["from"]["start_load"], c["to"]["start_load"]) for c in preview["changed"]], [(20, 10)])
        self.assertEqual(cable_fly_lines(read(self.program))[0][1]["load_mode"], "total")

        data = self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old")["data"]
        self.assertTrue(data["written"])
        [(session_id, line)] = cable_fly_lines(read(self.program))
        self.assertEqual((session_id, line["load_mode"], line["start_load"]), ("push", "per_hand_x2", 10))
        self.ok(self.root, "program", "validate")
        self.ok(self.root, "check", "--only", "routine_render_fresh,program_exercise_ids")
        self.assertIn("10/hand (Hevy: 20)", (self.root / "routine" / "push.md").read_text(encoding="utf-8"))

        overlay = self.ok(self.root, "propose", "week", "--week", WEEK, "--dry-run")["data"]["overlay"]
        self.assertNotIn("block", {flag.get("severity") for flag in overlay["flags"]})
        self.assertNotIn("load_mode_mismatch", {flag["code"] for flag in overlay["flags"]})
        modes = {line["load_mode"] for session in overlay["sessions"] for line in session["exercises"]
                 if line["exercise_id"] == "cable_fly"}
        self.assertEqual(modes, {"per_hand_x2"})

    def test_confirmed_basis_keeps_20_as_20_per_hand(self):
        self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "confirmed")
        [(_, line)] = cable_fly_lines(read(self.program))
        self.assertEqual((line["load_mode"], line["start_load"]), ("per_hand_x2", 20))
        self.ok(self.root, "program", "validate")

    def test_reconciling_twice_and_setting_the_same_mode_change_nothing(self):
        self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old")
        before = snapshot(self.root)
        again = self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old")["data"]
        self.assertEqual((again["changed"], again["written"]), ([], False))
        same = self.ok(self.root, "library", "set-mode", "cable_fly", "per_hand_x2")["data"]
        self.assertEqual((same["written"], same["program_slots"]), (False, []))
        self.assertEqual(snapshot(self.root), before)

    def test_an_unchanged_mode_still_reports_a_slot_left_unreconciled(self):
        same = self.ok(self.root, "library", "set-mode", "cable_fly", "per_hand_x2")["data"]
        self.assertFalse(same["written"])
        self.assertEqual([s["session_id"] for s in same["program_slots"]], ["push"])


class TwoSessionsTest(Case):
    """Cable fly at total 20 in both sessions of the valid fixture, with the library confirming per hand."""

    def setUp(self):
        self.root = instance(self, VALID)
        self.program = self.root / "data" / "program.json"
        doc = read(self.program)
        template = dict(doc["sessions"][0]["exercises"][0], exercise_id="cable_fly", load_mode="total", start_load=20,
                        cues=None)
        for session in doc["sessions"]:
            session["exercises"].append(dict(template))
        write(self.program, doc)
        self.ok(self.root, "program", "validate")
        self.ok(self.root, "program", "render")
        self.ok(self.root, "library", "set-mode", "cable_fly", "per_hand_x2")

    def test_both_sessions_are_reported_and_reconciled(self):
        error = self.fails(self.root, "program", "validate")["error"]
        paths = sorted(d["path"] for d in error["details"])
        self.assertEqual(paths, ["$.sessions[0].exercises[2].load_mode", "$.sessions[1].exercises[2].load_mode"])

        before_doc = read(self.program)
        before = snapshot(self.root)
        data = self.ok(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old")["data"]
        self.assertEqual(sorted(c["session_id"] for c in data["changed"]), ["session-a", "session-b"])

        after_doc = read(self.program)
        for session_before, session_after in zip(before_doc["sessions"], after_doc["sessions"]):
            for line_before, line_after in zip(session_before["exercises"], session_after["exercises"]):
                if line_before["exercise_id"] == "cable_fly":
                    self.assertEqual((line_after["load_mode"], line_after["start_load"]), ("per_hand_x2", 10))
                    self.assertEqual(dict(line_after, load_mode="total", start_load=20), line_before)
                else:
                    self.assertEqual(line_after, line_before)
        after = snapshot(self.root)
        changed = sorted(path for path in after if after[path] != before.get(path))
        self.assertEqual(changed, ["data/program.json", "routine/session-a.md", "routine/session-b.md"])
        self.ok(self.root, "program", "validate")

    def test_an_invalid_reconciliation_leaves_the_program_intact(self):
        self.ok(self.root, "library", "set-mode", "cable_fly", "duration")
        before = snapshot(self.root)
        error = self.fails(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "confirmed")["error"]
        self.assertTrue(any("duration_seconds" in d["message"] for d in error["details"]), error)
        self.assertEqual(snapshot(self.root), before)

    def test_an_unconfirmed_exercise_cannot_be_reconciled(self):
        library = read(self.root / "data" / "exercises.json")
        library["exercises"]["cable_fly"]["load_mode"] = None
        write(self.root / "data" / "exercises.json", library)
        error = self.fails(self.root, "program", "reconcile-mode", "cable_fly", "--basis", "old")["error"]
        self.assertIn("library set-mode cable_fly", error["message"])


class BeforeAdoptionTest(Case):
    """The setup path: the load-mode table confirmed, and a corrected row reconciled, before adopt."""

    def test_a_corrected_row_is_reconciled_in_the_draft_and_then_adopts(self):
        root = instance(self, EMPTY)
        self.ok(root, "starters", "draft", "push-pull-legs", "--start-load", "cable_fly=20")
        self.ok(root, "library", "set-mode", "cable_fly", "per_hand_x2")

        error = self.fails(root, "program", "adopt", "--input", str(root / DRAFT), "--dry-run")["error"]
        self.assertEqual([d["path"] for d in error["details"]], ["$.program.sessions[0].exercises[4].load_mode"])
        self.assertFalse((root / "data" / "program.json").exists())

        data = self.ok(root, "program", "reconcile-mode", "cable_fly", "--basis", "confirmed",
                       "--input", str(root / DRAFT))["data"]
        self.assertEqual(data["path"], str(root / DRAFT))
        self.ok(root, "program", "adopt", "--input", str(root / DRAFT))
        [(_, line)] = cable_fly_lines(read(root / "data" / "program.json"))
        self.assertEqual((line["load_mode"], line["start_load"]), ("per_hand_x2", 20))
        overlay = self.ok(root, "propose", "week", "--week", WEEK, "--dry-run")["data"]["overlay"]
        self.assertNotIn("block", {flag.get("severity") for flag in overlay["flags"]})


class ConvertModeTest(unittest.TestCase):
    def test_the_hevy_round_trip_between_modes(self):
        self.assertEqual(units.convert_mode(20, "total", "per_hand_x2", "kg"), 10)
        self.assertEqual(units.convert_mode(10, "per_hand_x2", "total", "lb"), 20)
        self.assertEqual(units.convert_mode(20, "total", "single_implement", "kg"), 20)


class ConfirmReportsSlotsTest(Case):
    def test_confirming_a_proposal_that_differs_from_the_line_reports_the_slot(self):
        root = self.adopted_ppl()
        library = read(root / "data" / "exercises.json")
        library["exercises"]["cable_fly"] = {"load_mode": None, "load_mode_proposed": "per_hand_x2"}
        write(root / "data" / "exercises.json", library)
        data = self.ok(root, "library", "confirm", "cable_fly")["data"]
        self.assertEqual([(s["session_id"], s["confirmed"]) for s in data["program_slots"]], [("push", "per_hand_x2")])


class SkillTextTest(unittest.TestCase):
    def test_setup_records_the_table_before_adopt_and_asks_the_basis_of_a_corrected_row(self):
        text = flat(step_text("setup", "program.md"))
        adopt = text[text.index("On every path"):]
        self.assertLess(adopt.index("settle the load modes as below first"), adopt.index("without `--dry-run`"))
        self.assertIn("**Confirm the load-mode table once, before adopting.**", adopt)
        self.assertIn("program reconcile-mode <id> --input .coach/drafts/program.json", adopt)
        for needle in ("--basis old", "--basis confirmed", "The athlete's answer picks the basis", "program_slots"):
            self.assertIn(needle, adopt)

if __name__ == "__main__":
    unittest.main()
