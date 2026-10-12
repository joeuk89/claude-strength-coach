"""Disrupted weeks: illness and reshuffles in schedule adherence, and logged effort and reps against the
prescription beside the hard-week gate (contract C41, C43)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import block
from tests.support import INSTANCES, run_cli
from tests.support.history import read_json, write_json

NOHEVY = INSTANCES / "nohevy"
WEEKLY = Path("data") / "overlays" / "2026-10-12-weekly.json"
SUNDAY = "2026-10-18T19:00:00Z"
W42 = "2026-10-12"


class NoHevyWeekCase(unittest.TestCase):
    """A temp copy of `nohevy/`: Session A on Mondays and Session B on Thursdays, W42 planned by an overlay."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(NOHEVY, self.root)

    def coach(self, *argv, now=SUNDAY, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"]

    def train(self, session_id, day, rpe=None, reps=None):
        """Log a session from its prefill: rep ranges at their top and targets as RPE, unless overridden.

        `rpe` sets every working set's RPE (None leaves the target); `reps` maps an exercise id to its sets' reps.
        """
        now = f"{day}T20:00:00Z"
        draft = self.coach("log", "prefill", "--session", session_id, "--date", day, now=now)["draft"]
        for exercise in draft["exercises"]:
            logged = iter((reps or {}).get(exercise["exercise_id"]) or ())
            for set_ in exercise["sets"]:
                working = set_["type"] != "warmup"
                set_["reps"] = next(logged, None) if working and reps and exercise["exercise_id"] in reps \
                    else set_["reps"] or 10
                set_["rpe"] = rpe if rpe is not None and working else set_["rpe"]
        path = self.tmp / f"{session_id}-{day}.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        self.coach("log", "add", "--input", str(path), now=now)
        self.coach("history", "sync", now=now)

    def miss(self, session_id, day, tag):
        self.coach("history", "annotate", "--kind", "miss", "--date", day, "--session", session_id, "--tag", tag)

    def status_day(self, kind, start, end, *extra):
        return self.coach("status-days", "add", "--kind", kind, "--from", start, "--to", end, "--note", "test",
                          *extra)["day"]

    def week(self):
        return self.coach("structure", "week", "--week", W42)

    def adherence(self):
        return self.coach("structure", "adherence")

    def close(self, *extra):
        return self.coach("block", "close", "--week", W42, *extra)

    def skipped(self, label="2026-W42"):
        return next((s for s in self.adherence()["skipped"] if s["label"] == label), None)

    def counted(self, label="2026-W42"):
        return next((w for w in self.adherence()["weeks"] if w["label"] == label), None)


class IllnessTest(NoHevyWeekCase):
    def ill_week(self):
        self.train("session-a", W42)
        self.status_day("ill", "2026-10-13", "2026-10-17")
        self.miss("session-b", "2026-10-15", "ill")

    def test_the_ill_week_is_skipped_for_illness_with_its_trained_session_kept(self):
        self.ill_week()
        skipped = self.skipped()
        self.assertEqual((skipped["kind"], skipped["planned"], skipped["trained"]), ("illness", 2, 1))
        self.assertEqual(skipped["reason"], "illness: planned training missed while ill, session-b on 2026-10-15 "
                                            "(tagged ill, status day s-0001)")
        self.assertIsNone(self.counted())
        week = self.week()
        self.assertEqual((week["kind"], week["planned"], week["trained"]), ("illness", 2, 1))
        self.assertEqual(week["kind_reason"], skipped["reason"])

    def test_the_block_keeps_the_ill_weeks_training_and_fatigue_facts(self):
        self.ill_week()
        closed = self.close()
        entry = closed["weeks"][-1]
        self.assertEqual((entry["class"], entry["planned"], entry["trained"], entry["as_prescribed"]),
                         ("partial", 2, 1, 1))
        self.assertEqual(closed["block"]["hard_weeks_completed"], 2)
        review = closed["reviews"][-1]
        self.assertEqual((review["kind"], review["hard_gate"]), ("illness", 1))
        self.assertEqual([s["session_id"] for s in review["sessions"]], ["session-a"])
        self.assertIn("Adherence leaves this week out (illness: planned training missed while ill", review["summary"])

    def test_closing_the_ill_week_again_gives_the_same_result(self):
        self.ill_week()
        first = self.close()
        again = self.close()
        self.assertTrue(again["replaced"])
        for key in ("weeks", "block", "reviews", "flags", "deep_review", "status_line"):
            with self.subTest(key=key):
                self.assertEqual(again[key], first[key])

    def test_an_ill_tag_alone_is_enough(self):
        self.train("session-a", W42)
        self.miss("session-b", "2026-10-15", "ill")
        self.assertEqual(self.skipped()["reason"], "illness: planned training missed while ill, session-b on "
                                                   "2026-10-15 (tagged ill)")

    def test_an_ill_status_day_alone_is_enough(self):
        self.train("session-a", W42)
        self.status_day("ill", "2026-10-15", "2026-10-15")
        self.assertEqual(self.skipped()["reason"], "illness: planned training missed while ill, session-b on "
                                                   "2026-10-15 (status day s-0001)")

    def test_a_coach_led_session_not_done_on_an_ill_day_is_enough(self):
        program = self.root / "data" / "program.json"
        doc = read_json(program)
        doc["external_sessions"] = [{"id": "pt-wed", "title": "PT", "weekday": "wed", "estimated_sets": {"chest": 3}}]
        write_json(program, doc)
        self.train("session-a", W42)
        self.train("session-b", "2026-10-15")
        self.coach("history", "annotate", "--kind", "external", "--date", "2026-10-14", "--external", "pt-wed",
                   "--not-done")
        self.status_day("ill", "2026-10-14", "2026-10-14")
        skipped = self.skipped()
        self.assertEqual((skipped["kind"], skipped["planned"], skipped["trained"]), ("illness", 3, 2))
        self.assertEqual(skipped["reason"], "illness: planned training missed while ill, pt-wed on 2026-10-14 "
                                            "(status day s-0001)")

    def test_illness_on_days_with_no_planned_work_leaves_the_week_ordinary(self):
        self.train("session-a", W42)
        self.status_day("ill", "2026-10-13", "2026-10-14")
        self.miss("session-b", "2026-10-15", "time")
        self.assertIsNone(self.skipped())
        self.assertEqual(self.counted(), {"week": W42, "label": "2026-W42", "planned": 2, "trained": 1})
        self.assertEqual(self.week()["kind"], "ordinary")

    def test_an_ill_week_trained_in_full_stays_ordinary(self):
        self.train("session-a", W42)
        self.train("session-b", "2026-10-15")
        self.status_day("ill", "2026-10-13", "2026-10-17")
        self.assertEqual(self.counted()["trained"], 2)

    def test_travel_without_the_break_intent_is_not_illness(self):
        self.train("session-a", W42)
        self.status_day("travel", "2026-10-14", "2026-10-16")
        self.assertIsNone(self.skipped())
        self.assertEqual(self.counted()["trained"], 1)

    def test_a_partial_planned_break_keeps_its_partial_accounting(self):
        self.train("session-a", W42)
        self.status_day("travel", "2026-10-15", "2026-10-16", "--no-training")
        self.assertIsNone(self.skipped())
        self.assertEqual(self.counted(), {"week": W42, "label": "2026-W42", "planned": 1, "trained": 1})


class ReshuffleTest(NoHevyWeekCase):
    def write_one_off(self, temporary=False):
        """A one-off over W42 that keeps Session A on Monday and moves Session B to Friday, or, with `temporary`,
        replaces Session B with a hotel session."""
        doc = read_json(self.root / WEEKLY)
        doc.update(id="2026-10-12-one-off", kind="one_off", created_at="2026-10-12T21:00:00Z", approval=None,
                   supersedes="2026-10-12-weekly", flags=[])
        b = next(s for s in doc["sessions"] if s["session_id"] == "session-b")
        if temporary:
            b.update(session_id="travel-b", title="Travel B", temporary=True, date="2026-10-16")
        else:
            b.update(date="2026-10-16", moved_from="2026-10-15")
        write_json(self.root / "data" / "overlays" / f"{doc['id']}.json", doc)

    def test_a_reshuffled_week_stays_in_adherence_with_its_genuine_miss(self):
        self.write_one_off()
        self.miss("session-a", W42, "time")
        self.train("session-b", "2026-10-16")
        self.assertIsNone(self.skipped())
        self.assertEqual(self.counted(), {"week": W42, "label": "2026-W42", "planned": 2, "trained": 1})
        week = self.week()
        self.assertEqual(week["kind"], "ordinary")
        self.assertEqual([(s["session_id"], s["date"], s["status"]) for s in week["sessions"]],
                         [("session-a", W42, "missed"), ("session-b", "2026-10-16", "trained")])
        self.assertEqual(self.close()["weeks"][-1]["class"], "partial")

    def test_a_constrained_week_is_skipped_with_its_reason(self):
        self.write_one_off(temporary=True)
        self.train("session-a", W42)
        skipped = self.skipped()
        self.assertEqual((skipped["kind"], skipped["reason"]),
                         ("one_off", "constrained one-off week: temporary sessions travel-b"))
        self.assertEqual(self.close()["weeks"][-1]["class"], "one_off")


class PrescriptionTest(NoHevyWeekCase):
    def codes(self, closed):
        return [f["code"] for f in closed["flags"]]

    def flag(self, closed, code, session_id):
        return next(f for f in closed["flags"] if f["code"] == code and f["session_id"] == session_id)

    def test_every_set_well_under_its_target_rpe_asks_for_a_load_review(self):
        self.train("session-a", W42, rpe=5)
        self.train("session-b", "2026-10-15", rpe=5)
        closed = self.close()
        self.assertEqual(closed["weeks"][-1]["class"], "partial")
        self.assertEqual(self.codes(closed).count("effort_below_target"), 2)
        self.assertEqual(self.flag(closed, "effort_below_target", "session-a")["message"],
                         "2026-10-12 session-a: logged RPE averaged under target (Back Squat (Barbell) by 2 across 3 "
                         "sets; Bench Press (Dumbbell) by 3 across 3 sets); the loads look light, so review them "
                         "with the athlete")
        self.assertNotIn("reps_missed", self.codes(closed))
        self.assertNotIn("effort_above_target", self.codes(closed))
        summary = closed["reviews"][-1]["summary"]
        self.assertIn("0 of 2 planned sessions passed the hard-week gate", summary)
        self.assertIn("2 sessions logged effort under target", summary)

    def test_failed_reps_at_rpe_10_still_count_hard_and_are_named(self):
        self.train("session-a", W42, reps={"bb_back_squat": [5, 2, 1]})
        for exercise_id in ("bb_back_squat",):
            self.set_rpe(W42, exercise_id, 10)
        self.train("session-b", "2026-10-15", rpe=10,
                   reps={"db_single_arm_row": [10, 7, 4], "pull_up": [8, 5, 2]})
        closed = self.close()
        entry = closed["weeks"][-1]
        self.assertEqual((entry["class"], entry["as_prescribed"]), ("hard", 2))
        self.assertEqual(self.codes(closed).count("reps_missed"), 2)
        self.assertEqual(self.codes(closed).count("effort_above_target"), 2)
        self.assertNotIn("effort_below_target", self.codes(closed))
        missed = self.flag(closed, "reps_missed", "session-b")["message"]
        self.assertIn("reps under the prescription", missed)
        self.assertIn("5/2/1 against 5", self.flag(closed, "reps_missed", "session-a")["message"])
        self.assertIn("10/7/4 against 10", missed)
        self.assertIn("8/5/2 against 8", missed)
        self.assertIn("the prescription was not met", missed)
        above = self.flag(closed, "effort_above_target", "session-a")["message"]
        self.assertIn("Back Squat (Barbell) by 3 across 3 sets", above)
        self.assertNotIn("Bench", above)
        summary = closed["reviews"][-1]["summary"]
        self.assertIn("2 of 2 planned sessions passed the hard-week gate (rn:deloads.11), which counts training "
                      "stress for the block, not completed prescriptions.", summary)
        self.assertIn("2 sessions missed reps, 2 sessions logged effort over target", summary)
        for flag in closed["flags"]:
            self.assertNotIn("as prescribed", flag["message"])

    def test_missing_rpe_is_not_measured_effort(self):
        self.train("session-a", W42)
        self.clear_rpe(W42)
        closed = self.close()
        session = closed["reviews"][-1]["sessions"][0]
        self.assertEqual((session["rpe_sets"], session["rpe_missing"], session["mean_rpe_delta"]), (0, 6, None))
        self.assertEqual(session["signals"], [])
        self.assertIn("No RPE logged on 6 sets with a target: the gate counts them on target, but their effort was "
                      "not measured.", closed["reviews"][-1]["summary"])

    def edit_log(self, day, change):
        path = self.root / "data" / "log" / "workouts.jsonl"
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in lines:
            if line.get("date") == day:
                change(line)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        self.coach("history", "sync")

    def set_rpe(self, day, exercise_id, rpe):
        def change(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == exercise_id:
                    for set_ in exercise["sets"]:
                        set_["rpe"] = rpe
        self.edit_log(day, change)

    def clear_rpe(self, day):
        def change(workout):
            for exercise in workout["exercises"]:
                for set_ in exercise["sets"]:
                    set_["rpe"] = None
        self.edit_log(day, change)


class CompareTest(unittest.TestCase):
    LINE = {"exercise_id": "x", "sets": [{"type": "normal", "reps": 5, "rpe": 8}] * 3}

    @staticmethod
    def logged(*sets):
        return {"exercises": [{"exercise_id": "x", "sets": [{"type": "normal", "reps": r, "rpe": e} for r, e in sets]}]}

    def test_the_gate_and_the_prescription_are_reported_apart(self):
        found = block.compare([self.LINE], self.logged((5, 10), (2, 10), (1, 10)))
        self.assertTrue(found["hard_gate"])
        self.assertEqual(found["signals"], ["effort_above_target", "reps_missed"])
        self.assertEqual(found["reps_missed"], [{"exercise_id": "x", "target": "5", "logged": [5, 2, 1]}])
        self.assertEqual(found["effort_above"], [{"exercise_id": "x", "mean_rpe_delta": 2.0, "sets": 3}])

    def test_a_rep_range_is_judged_at_its_bottom(self):
        line = {"exercise_id": "x", "sets": [{"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 8}] * 2}
        self.assertEqual(block.compare([line], self.logged((8, 8), (8, 8)))["signals"], [])
        found = block.compare([line], self.logged((8, 8), (7, 8)))
        self.assertEqual(found["reps_missed"], [{"exercise_id": "x", "target": "8–10", "logged": [8, 7]}])

    def test_effort_within_the_tolerance_raises_nothing(self):
        found = block.compare([self.LINE], self.logged((5, 9.5), (5, 9.5), (5, 9.5)))
        self.assertEqual((found["signals"], found["hard_gate"]), ([], True))
        found = block.compare([self.LINE], self.logged((5, 6), (5, 6), (5, 6)))
        self.assertEqual((found["signals"], found["hard_gate"]), (["effort_below_target"], False))


if __name__ == "__main__":
    unittest.main()
