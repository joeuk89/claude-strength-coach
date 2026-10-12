"""Proposal flags are addressed by a stable reference, never by list position (contract C24)."""

import unittest

from coach import config, flags, overlay, validity
from tests.support.history import read_json, write_json
from tests.support.skills import flat, step_text
from tests.test_propose import FIRST_ID, ProposeCase

TRAVEL = ("status-days", "add", "--kind", "travel", "--from", "2026-10-17", "--to", "2026-10-18", "--note", "away")
REASON = "synthetic: accepted for the test"


class RefTest(unittest.TestCase):
    def flag(self, **changes):
        return dict(flags.make("unearned_load", session_id="session-a", exercise_id="bb_back_squat",
                               message="bb_back_squat in session-a on 2026-10-12: 140 implies RPE 11"), **changes)

    def test_a_ref_names_the_condition_whatever_its_resolution(self):
        ref = flags.ref(self.flag())
        self.assertRegex(ref, r"^unearned_load:[0-9a-f]{6}$")
        self.assertEqual(flags.ref(self.flag(resolved=True, resolution="tested last week")), ref)

    def test_a_different_condition_gets_a_different_ref(self):
        ref = flags.ref(self.flag())
        for changes in ({"message": "bb_back_squat in session-a on 2026-10-15: 140 implies RPE 11"},
                        {"session_id": "session-b"}, {"severity": "warn"}):
            with self.subTest(changes=changes):
                self.assertNotEqual(flags.ref(self.flag(**changes)), ref)


class ProposalRefCase(ProposeCase):
    def data(self, *argv, expect=0):
        envelope = self.coach(*argv, expect=expect)
        return envelope["data"] if expect == 0 else envelope

    def shown(self, proposal_id=FIRST_ID):
        return self.data("propose", "show", proposal_id)["flags"]

    def override(self, exercise_id, *extra, session_id="session-a"):
        return self.data("propose", "override", "--proposal", FIRST_ID, "--session", session_id, "--exercise",
                         exercise_id, *extra, "--reason", "synthetic test")

    def resolve(self, ref, *extra, expect=0, proposal_id=FIRST_ID):
        return self.data("propose", "resolve", "--proposal", proposal_id, "--flag", ref, "--resolution", REASON,
                         *extra, expect=expect)

    def draft_bytes(self, proposal_id=FIRST_ID):
        return self.draft_path(proposal_id).read_bytes()


class ReorderTest(ProposalRefCase):
    def put_mismatch_in_proposed_order(self):
        """Store the draft's flags as propose week orders them, line flags, then R-24 flags, then week flags,
        with a load_mode_mismatch among the R-24 flags. The program cannot hold a mismatch when the week is
        proposed, so the library changes after it."""
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["db_single_arm_row"].update(
            load_mode="total"))
        draft = read_json(self.draft_path())
        owned = validity.owned_codes()
        found = validity.check_overlay(self.root, overlay.build(draft, config.load(self.root), root=self.root))
        week = [f for f in draft["flags"] if f["code"] == "status_active"]
        line = [f for f in draft["flags"] if f["code"] not in owned and f not in week]
        draft["flags"] = line + found + week
        write_json(self.draft_path(), draft)

    def test_an_override_that_reorders_the_flags_leaves_the_mismatch_ref_on_the_mismatch(self):
        self.coach(*TRAVEL)
        self.propose()
        self.put_mismatch_in_proposed_order()
        before = self.shown()
        codes = [f["code"] for f in before]
        mismatch = next(f for f in before if f["code"] == "load_mode_mismatch")
        self.assertLess(codes.index("load_mode_mismatch"), codes.index("status_active"))

        after = self.override("bb_back_squat", "--load", "60")["flags"]
        codes_after = [f["code"] for f in after]
        self.assertGreater(codes_after.index("load_mode_mismatch"), codes_after.index("status_active"))
        self.assertEqual(next(f["ref"] for f in after if f["code"] == "load_mode_mismatch"), mismatch["ref"])

        resolved = self.resolve(mismatch["ref"])["flag"]
        self.assertEqual((resolved["code"], resolved["ref"], resolved["resolution"]),
                         ("load_mode_mismatch", mismatch["ref"], REASON))
        status = [f for f in self.shown() if f["code"] == "status_active"]
        self.assertTrue(status and not any(f["resolved"] for f in status))

    def test_a_list_position_is_refused_and_changes_nothing(self):
        self.coach(*TRAVEL)
        self.propose()
        before = self.draft_bytes()
        envelope = self.resolve("0", expect=2)
        self.assertIn("ref", envelope["error"]["message"])
        self.assertEqual(self.draft_bytes(), before)


class OccurrenceTest(ProposalRefCase):
    def test_the_same_condition_on_two_dates_is_addressed_per_date(self):
        self.propose()
        self.override("bb_back_squat", "--load", "95", "--standing")
        plan = self.root / "plan.json"
        write_json(plan, {"sessions": [{"date": "2026-10-12", "session_id": "session-a"},
                                       {"date": "2026-10-14", "session_id": "session-a"}]})
        data = self.propose("--plan", str(plan))
        kept = [f for f in data["flags"] if f["code"] == "override_standing"]
        self.assertEqual(len(kept), 2)
        self.assertEqual(len({f["ref"] for f in kept}), 2)
        self.assertTrue(kept[0]["message"].startswith("session-a on 2026-10-12: "))
        self.assertTrue(kept[1]["message"].startswith("session-a on 2026-10-14: "))

        resolved = self.resolve(kept[1]["ref"], proposal_id=data["id"])["flag"]
        self.assertIn("2026-10-14", resolved["message"])
        after = {f["ref"]: f for f in self.shown(data["id"])}
        self.assertFalse(after[kept[0]["ref"]]["resolved"])
        self.assertTrue(after[kept[1]["ref"]]["resolved"])


class LifecycleTest(ProposalRefCase):
    def setUp(self):
        super().setUp()
        self.propose()

    def unearned(self, found):
        return [f for f in found if f["code"] == "unearned_load"]

    def bench_rpe(self, found):
        [flag] = [f for f in found if f["code"] == "rpe_infeasible" and f["exercise_id"] == "db_bench_press"]
        return flag

    def test_a_gone_condition_is_refused_and_a_new_one_gets_its_own_ref(self):
        [heavy] = self.unearned(self.override("bb_back_squat", "--sets", "3x5@140 rpe7")["flags"])
        self.assertEqual(self.unearned(self.override("bb_back_squat", "--load", "100")["flags"]), [])
        before = self.draft_bytes()
        envelope = self.resolve(heavy["ref"], expect=1)
        self.assertIn("gone or has changed", envelope["error"]["message"])
        self.assertIn(f"propose show {FIRST_ID}", envelope["error"]["message"])
        self.assertEqual(self.draft_bytes(), before)

        [heavier] = self.unearned(self.override("bb_back_squat", "--sets", "3x5@150 rpe7")["flags"])
        self.assertNotEqual(heavier["ref"], heavy["ref"])

    def test_a_resolution_stays_with_its_condition_through_saves_and_revalidation(self):
        bench = self.bench_rpe(self.shown())
        self.resolve(bench["ref"])
        for step in ("show", "override", "override again"):
            with self.subTest(step=step):
                if step == "show":
                    found = self.shown()
                else:
                    found = self.override("bb_back_squat", "--load", "95" if step == "override" else "97.5")["flags"]
                kept = self.bench_rpe(found)
                self.assertEqual((kept["ref"], kept["resolved"], kept["resolution"]), (bench["ref"], True, REASON))

    def test_a_fresh_condition_never_inherits_a_resolution(self):
        [heavy] = self.unearned(self.override("bb_back_squat", "--sets", "3x5@140 rpe7")["flags"])
        self.resolve(heavy["ref"])
        [heavier] = self.unearned(self.override("bb_back_squat", "--sets", "3x5@150 rpe7")["flags"])
        self.assertFalse(heavier["resolved"])
        envelope = self.coach("propose", "finalize", "--proposal", FIRST_ID, expect=3)
        self.assertIn(heavier["ref"], str(envelope["error"]["details"]))

    def test_a_dry_run_resolution_writes_nothing(self):
        bench = self.bench_rpe(self.shown())
        before = self.snapshot()
        self.assertFalse(self.resolve(bench["ref"], "--dry-run")["written"])
        self.assertEqual(self.snapshot(), before)

    def test_an_unknown_ref_lists_the_open_flags_and_changes_nothing(self):
        before = self.snapshot()
        envelope = self.resolve("unearned_load:000000", expect=1)
        self.assertIn(self.bench_rpe(self.shown())["ref"], str(envelope["error"]["details"]))
        self.assertEqual(self.snapshot(), before)

    def test_a_hand_added_flag_with_only_the_required_fields_resolves_by_its_ref(self):
        draft = read_json(self.draft_path())
        draft["flags"].append({"code": "unearned_load", "severity": "warn", "message": "hand added"})
        write_json(self.draft_path(), draft)
        [hand] = [f for f in self.shown() if f["message"] == "hand added"]

        envelope = self.resolve("unearned_load:000000", expect=1)
        self.assertIn(hand["ref"], str(envelope["error"]["details"]))

        resolved = self.resolve(hand["ref"])["flag"]
        self.assertEqual((resolved["ref"], resolved["resolved"], resolved["resolution"]), (hand["ref"], True, REASON))
        [after] = [f for f in self.shown() if f["message"] == "hand added"]
        self.assertTrue(after["resolved"])


class SkillTest(unittest.TestCase):
    def test_program_week_resolves_a_flag_by_its_ref(self):
        compute = flat(step_text("program-week", "compute.md"))
        self.assertIn("--flag <ref>", compute)
        self.assertNotIn("--flag <index>", compute)


if __name__ == "__main__":
    unittest.main()
