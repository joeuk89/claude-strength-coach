"""A one-off week's exercises need a confirmed load mode before approval, and the repair it names works (C10, C22)."""

import unittest

from coach import flags, validity
from tests.support import run_cli
from tests.support.history import HistoryCase, read_json, write_json
from tests.support.skills import step_text

ONE_OFF = "2026-10-13-one-off"
LIBRARY = "data/exercises.json"


def one_off_draft():
    return {
        "kind": "one_off",
        "span": {"start": "2026-10-13", "end": "2026-10-14"},
        "focus": "Travel: keep pressing and hinging alive at home.",
        "sessions": [{
            "session_id": "travel-a",
            "date": "2026-10-14",
            "title": "Travel A — Full body",
            "temporary": True,
            "location": "home",
            "exercises": [
                {"exercise_id": "push_up", "load_mode": "bodyweight",
                 "sets": [{"type": "normal", "reps": 12, "rpe": 8, "load": 0} for _ in range(2)]},
                {"exercise_id": "db_romanian_deadlift", "load_mode": "per_hand_x2",
                 "sets": [{"type": "normal", "reps": 10, "rpe": 8, "load": 20} for _ in range(2)]},
                {"exercise_id": "db_bench_press", "load_mode": "per_hand_x2",
                 "sets": [{"type": "normal", "reps": 10, "rpe": 8, "load": 20} for _ in range(2)]},
            ],
        }],
    }


def unconfirmed(found):
    return {f["exercise_id"]: f for f in found if f["code"] == "load_mode_unconfirmed"}


def blocks(found, exercise_id):
    return sorted(f["code"] for f in found if f["severity"] == "block" and f["exercise_id"] == exercise_id)


class OneOffCase(HistoryCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()
        self.draft = self.tmp / "overlay-2026-10-13.json"
        write_json(self.draft, one_off_draft())

    def build(self):
        return self.coach("overlay", "build", "--input", str(self.draft))

    def check_file(self):
        return self.coach("prescription", "check", "--file", str(self.draft))["data"]["flags"]

    def check_overlay(self, *extra):
        return self.coach("prescription", "check", "--overlay", ONE_OFF, *extra)["data"]["flags"]

    def readiness(self):
        _, envelope, _ = run_cli(["--root", str(self.root), "check", "--only", "load_modes_confirmed"], env=self.env)
        return [r for r in envelope["data"]["results"] if r["status"] == "fail"]

    def set_mode(self, exercise_id, mode):
        return self.coach("library", "set-mode", exercise_id, mode)

    def propose(self, exercise_id, mode):
        self.edit_json(LIBRARY, lambda doc: doc["exercises"].setdefault(exercise_id, {}).update(
            load_mode=None, load_mode_proposed=mode, confidence="low"))


class BeforeApprovalTest(OneOffCase):
    def test_the_draft_check_reports_both_new_exercises_and_passes_the_confirmed_one(self):
        found = unconfirmed(self.check_file())
        self.assertEqual(sorted(found), ["db_romanian_deadlift", "push_up"])
        self.assertEqual({f["severity"] for f in found.values()}, {"block"})
        self.assertEqual(blocks(self.check_file(), "db_bench_press"), [])

    def test_with_no_proposal_the_repair_is_set_mode_with_the_lines_mode(self):
        found = unconfirmed(self.check_file())
        self.assertIn("python3 -m coach library set-mode push_up bodyweight", found["push_up"]["message"])
        self.assertIn("python3 -m coach library set-mode db_romanian_deadlift per_hand_x2",
                      found["db_romanian_deadlift"]["message"])
        for flag in found.values():
            self.assertNotIn("library confirm", flag["message"])
            self.assertNotIn("library seed", flag["message"])

    def test_build_warns_about_each_unconfirmed_mode(self):
        warnings = " ".join(self.build().get("warnings", []))
        self.assertIn("push_up", warnings)
        self.assertIn("db_romanian_deadlift", warnings)
        self.assertNotIn("db_bench_press", warnings)

    def test_approve_refuses_while_the_readiness_check_fails(self):
        self.build()
        self.assertEqual(len(self.readiness()), 2)
        envelope = self.coach("overlay", "approve", ONE_OFF, expect=3)
        messages = " ".join(d["message"] for d in envelope["error"]["details"])
        self.assertIn("library set-mode push_up bodyweight", messages)
        self.assertIn("library set-mode db_romanian_deadlift per_hand_x2", messages)
        self.assertIsNone(read_json(self.root / "data/overlays" / f"{ONE_OFF}.json")["approval"])

    def test_a_hand_resolved_flag_does_not_let_approval_through(self):
        self.build()
        self.check_overlay("--write")

        def resolve_all(doc):
            for flag in doc["flags"]:
                flag.update(resolved=True, resolution="the athlete knows these")
        self.edit_json(f"data/overlays/{ONE_OFF}.json", resolve_all)
        self.coach("overlay", "approve", ONE_OFF, expect=3)
        self.check_overlay("--write")
        stored = unconfirmed(read_json(self.root / "data/overlays" / f"{ONE_OFF}.json")["flags"])
        self.assertEqual({f["resolved"] for f in stored.values()}, {False})
        envelope = self.coach("check", "--only", "prescription_valid", expect=1)
        self.assertIn("load_mode_unconfirmed", " ".join(r["message"] for r in envelope["data"]["results"]))


class RepairTest(OneOffCase):
    def test_set_mode_resolves_it_and_the_checks_agree_before_and_after_approval(self):
        self.build()
        self.set_mode("push_up", "bodyweight")
        self.set_mode("db_romanian_deadlift", "per_hand_x2")
        self.assertEqual(unconfirmed(self.check_overlay("--write")), {})
        self.assertEqual(self.readiness(), [])
        self.coach("overlay", "approve", ONE_OFF)
        self.assertEqual(self.readiness(), [])
        self.assertEqual(unconfirmed(self.check_overlay()), {})
        self.coach("check", "--only", "prescription_valid,load_modes_confirmed,overlay_library_consistency")

    def test_a_genuine_proposal_offers_confirm_and_confirming_leaves_the_loads_alone(self):
        self.propose("db_romanian_deadlift", "per_hand_x2")
        found = unconfirmed(self.check_file())
        message = found["db_romanian_deadlift"]["message"]
        self.assertIn("python3 -m coach library confirm db_romanian_deadlift", message)
        self.assertIn("library set-mode db_romanian_deadlift", message)
        self.assertNotIn("library confirm", found["push_up"]["message"])
        self.build()
        path = self.root / "data/overlays" / f"{ONE_OFF}.json"
        before = path.read_bytes()
        self.coach("library", "confirm", "db_romanian_deadlift")
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("db_romanian_deadlift", unconfirmed(self.check_overlay()))

    def test_a_confirmed_proposal_that_disagrees_with_the_line_blocks_as_a_mismatch(self):
        self.propose("db_romanian_deadlift", "single_implement")
        self.build()
        self.coach("library", "confirm", "db_romanian_deadlift")
        self.assertEqual(blocks(self.check_overlay(), "db_romanian_deadlift"), ["load_mode_mismatch"])

    def test_a_confirmed_mismatch_still_blocks(self):
        self.set_mode("db_romanian_deadlift", "single_implement")
        self.assertEqual(blocks(self.check_file(), "db_romanian_deadlift"), ["load_mode_mismatch"])

    def test_removing_a_confirmation_brings_the_flag_back_unresolved(self):
        self.build()
        self.set_mode("push_up", "bodyweight")
        self.set_mode("db_romanian_deadlift", "per_hand_x2")
        self.check_overlay("--write")
        self.edit_json(LIBRARY, lambda doc: doc["exercises"]["push_up"].update(load_mode=None))
        self.check_overlay("--write")
        stored = unconfirmed(read_json(self.root / "data/overlays" / f"{ONE_OFF}.json")["flags"])
        self.assertEqual(sorted(stored), ["push_up"])
        self.assertFalse(stored["push_up"]["resolved"])
        self.coach("overlay", "approve", ONE_OFF, expect=3)


class MergeTest(unittest.TestCase):
    def test_merge_never_carries_a_resolution_onto_a_missing_mode_flag(self):
        flag = flags.make("load_mode_unconfirmed", session_id="travel-a", exercise_id="push_up", message="m")
        doc = {"flags": [dict(flag, resolved=True, resolution="waved through")]}
        [merged] = validity.merge_flags(doc, [flag])
        self.assertEqual((merged["resolved"], merged["resolution"]), (False, None))
        self.assertEqual(validity.unresolved_blocks(doc, [flag]), [flag])


class OneOffSkillTest(unittest.TestCase):
    def test_the_one_off_flow_confirms_new_exercises_before_the_draft(self):
        text = " ".join(step_text("program-week", "one-off.md").split())
        self.assertIn("python3 -m coach library set-mode", text)
        self.assertIn("python3 -m coach library confirm", text)
        self.assertIn("load_mode_proposed", text)
        self.assertLess(text.index("library set-mode"), text.index("## Write the draft"))

    def test_write_step_says_approve_refuses_an_unconfirmed_mode(self):
        text = " ".join(step_text("program-week", "write.md").split())
        self.assertIn("load_mode_unconfirmed", text)


if __name__ == "__main__":
    unittest.main()
