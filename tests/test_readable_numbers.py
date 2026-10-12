"""Athlete-facing numbers: whole-unit e1RMs, RPE gaps in words, labelled set groups and the cardio line."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import cardio, checkin, stats, units
from tests.support import INSTANCES, run_cli

NOHEVY = INSTANCES / "nohevy"
LOG = Path("data") / "log" / "workouts.jsonl"
SUNDAY = "2026-10-18T18:00:00Z"
SQUAT_SETS = [(100, 5, 6), (100, 5, 6), (100, 5, 6.5)]
BENCH_SETS = [(25, 9, 9.5), (25, 7, 8.5), (25, 6, 8.5)]


def workout(day, session_id, exercises, minutes=57):
    """A manual-log workout line; `exercises` are (exercise_id, load_mode, [(value, reps, rpe)])."""
    return {"schema_version": 1, "kind": "workout", "id": f"manual:{day}-{session_id}-1",
            "logged_at": f"{day}T19:05:00Z", "date": day, "session_id": session_id, "overlay_id": None,
            "duration_minutes": minutes, "notes": "",
            "exercises": [{"exercise_id": exercise_id, "load_mode": load_mode, "unit": "kg", "notes": "",
                           "sets": [{"type": "normal", "reps": reps, "rpe": rpe, "value": value,
                                     "duration_seconds": None, "distance_meters": None}
                                    for value, reps, rpe in sets]}
                          for exercise_id, load_mode, sets in exercises]}


class NoHevyWeek(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(NOHEVY, self.root)

    def coach(self, *argv, now=SUNDAY):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope["data"]

    def log(self, *workouts):
        with (self.root / LOG).open("a", encoding="utf-8") as handle:
            for line in workouts:
                handle.write(json.dumps(line) + "\n")
        self.coach("history", "sync")


class CheckInNumbersTest(NoHevyWeek):
    def setUp(self):
        super().setUp()
        self.log(workout("2026-10-12", "session-a", [("bb_back_squat", "total", SQUAT_SETS),
                                                      ("db_bench_press", "per_hand_x2", BENCH_SETS)]))
        self.prepared = self.coach("checkin", "prepare")
        self.card, self.text = self.prepared["card"], self.prepared["text"]

    def exercise(self, exercise_id):
        return next(r for r in self.card["exercises"] if r["exercise_id"] == exercise_id)

    def e1rm(self, exercise_id):
        return next(r for r in self.card["e1rm"] if r["exercise_id"] == exercise_id)

    def region(self):
        return self.coach("checkin", "skeleton", "--date", "2026-10-18", "--dry-run")["text"]

    def test_an_rpe_gap_reads_as_words_against_the_target(self):
        self.assertEqual(self.exercise("bb_back_squat")["rpe_delta"], -0.83)
        self.assertIn("Back Squat (Barbell) hit (RPE 0.8 below target)", self.text)
        self.assertIn("| hit, RPE 0.8 below target |", self.region())
        for text in (self.text, self.region()):
            self.assertNotIn("RPE -", text)

    def test_logged_set_groups_name_their_sets(self):
        logged = self.exercise("db_bench_press")["logged"]
        self.assertEqual(logged, "set 1: 9 @ 25/hand @ RPE 9.5; sets 2–3: 7, 6 @ 25/hand @ RPE 8.5")
        self.assertIn(f"under: {logged} against", self.text)
        self.assertNotIn(" + ", logged)

    def test_one_group_needs_no_set_labels(self):
        self.log(workout("2026-10-15", "session-b", [("db_single_arm_row", "single_implement", [(30, 10, 8)] * 3)]))
        card = self.coach("checkin", "prepare")["card"]
        row = next(r for r in card["exercises"] if r["exercise_id"] == "db_single_arm_row")
        self.assertTrue(row["logged"].startswith("10, 10, 10 @ 30"), row["logged"])

    def row_week(self, rpes):
        self.log(workout("2026-10-15", "session-b",
                         [("db_single_arm_row", "single_implement", [(30, 10, rpe) for rpe in rpes])]))
        prepared = self.coach("checkin", "prepare")
        row = next(r for r in prepared["card"]["exercises"] if r["exercise_id"] == "db_single_arm_row")
        return prepared, row

    def test_an_rpe_above_target_reads_as_above(self):
        prepared, row = self.row_week([8.5, 8.5, 8.5])
        self.assertEqual((row["status"], row["rpe_delta"]), ("hit", 0.5))
        self.assertIn(f"{row['name']} hit (RPE 0.5 above target)", prepared["text"])
        self.assertIn("| hit, RPE 0.5 above target |", self.region())

    def test_an_rpe_gap_that_rounds_to_nothing_is_not_shown(self):
        prepared, row = self.row_week([8, 8, 8.1])
        self.assertEqual(row["status"], "hit")
        self.assertAlmostEqual(row["rpe_delta"], 0.03, places=2)
        self.assertIn(f"{row['name']} hit", prepared["text"])
        self.assertNotIn(f"{row['name']} hit (", prepared["text"])
        region_row = next(line for line in self.region().splitlines() if f"| {row['name']} |" in line)
        self.assertTrue(region_row.endswith("| hit |"), region_row)

    def test_a_lift_with_no_earlier_estimate_reads_as_a_first_estimate(self):
        prepared, row = self.row_week([8, 8, 8])
        estimate = next(r for r in prepared["card"]["e1rm"] if r["exercise_id"] == "db_single_arm_row")
        self.assertIsNone(estimate["delta"])
        line = next(line for line in prepared["text"].splitlines() if line.startswith("e1RM"))
        self.assertRegex(line, re.escape(row["name"]) + r" \d+ kg \(first estimate\)")
        self.assertNotIn("(—)", line)

    def test_estimates_show_whole_units_with_their_basis_and_keep_precision_in_data(self):
        bench = self.e1rm("db_bench_press")
        self.assertEqual((bench["e1rm"], bench["delta"]), (32.92, 1.42))
        line = next(line for line in self.text.splitlines() if line.startswith("e1RM"))
        self.assertIn("estimated one-rep max", line)
        self.assertIn("Bench Press (Dumbbell) 33 kg/hand (+1)", line)
        self.assertIn("Back Squat (Barbell) 130 kg (+7)", line)
        self.assertNotIn("32.92", self.text)
        region = self.region()
        self.assertIn("| Bench Press (Dumbbell) | 33/hand | +1 |", region)
        self.assertIn("estimated one-rep max", region)
        self.assertNotIn("32.92", region)

    def test_progress_shows_whole_estimates_and_says_what_an_e1rm_is(self):
        progress = self.coach("pages", "show", "progress")["text"]
        row = next(line for line in progress.splitlines() if line.startswith("| Bench Press (Dumbbell) |"))
        self.assertIn("| 33/hand |", row)
        self.assertNotIn("32.92", progress)
        self.assertIn("estimated one-rep max", progress.split("| Lift |")[0])

    def test_dashboard_bests_say_what_an_e1rm_is_on_their_first_line(self):
        dashboard = self.coach("pages", "show", "dashboard")["text"]
        bests = [line for line in dashboard.splitlines() if "Best e1RM" in line]
        self.assertGreaterEqual(len(bests), 2, dashboard)
        self.assertTrue(bests[0].startswith("- Best e1RM (estimated one-rep max): "), bests[0])
        self.assertEqual(sum("estimated one-rep max" in line for line in bests), 1)
        self.assertNotIn("32.92", dashboard)

    def test_brief_wins_say_what_an_e1rm_is_on_their_first_e1rm_line(self):
        brief = self.coach("pages", "show", "brief", now="2026-10-13T08:00:00Z")["text"]
        wins = [line for line in brief.split("## Wins")[1].splitlines() if "e1RM" in line]
        self.assertGreaterEqual(len(wins), 2, brief)
        self.assertTrue(wins[0].startswith("- New best e1RM (estimated one-rep max): "), wins[0])
        self.assertEqual(sum("estimated one-rep max" in line for line in wins), 1)
        self.assertIn("33 kg/hand", brief)


class CardioLineTest(NoHevyWeek):
    def setUp(self):
        super().setUp()
        self.log(workout("2026-10-12", "session-a", [("bb_back_squat", "total", [(60, 5, 5)] * 3),
                                                      ("db_bench_press", "per_hand_x2", [(12, 10, 5)] * 3)]))

    def test_one_easy_workout_reads_in_the_singular_and_explains_zero_hard_sets(self):
        lifting = self.coach("cardio", "week", "--week", "2026-W42")["lifting"]
        self.assertEqual((lifting["workouts"], lifting["hard_sets"], lifting["working_sets"]), (1, 0, 6))
        text = self.coach("cardio", "render", "--week", "2026-W42")["text"]
        line = next(line for line in text.splitlines() if line.startswith("Lifting:"))
        self.assertIn("1 workout,", line)
        self.assertNotIn("1 workouts", line)
        self.assertIn("0 hard sets of 6 working sets", line)
        self.assertIn(f"RPE {stats.EASY_RPE} or below", line)

    def test_session_rpe_load_names_its_inputs_and_sets_no_threshold(self):
        text = self.coach("cardio", "render", "--week", "2026-W42")["text"]
        line = next(line for line in text.splitlines() if line.startswith("Session-RPE load"))
        self.assertIn("minutes × session RPE", line)
        self.assertIn("a lifting session's is the mean RPE of its working sets, "
                      f"or {cardio.KIND_RPE['lifting']} when most have none", line)
        self.assertIn("arbitrary units", line)
        self.assertIn("information only", line)
        for word in ("target", "threshold", "too high", "risk"):
            self.assertNotIn(word, line.split("information only")[0])


class RpeGapTextTest(unittest.TestCase):
    def test_a_gap_reads_as_its_size_and_direction_against_the_target(self):
        self.assertEqual(checkin.rpe_gap_text(-0.83), "RPE 0.8 below target")
        self.assertEqual(checkin.rpe_gap_text(0.5), "RPE 0.5 above target")
        self.assertEqual(checkin.rpe_gap_text(0.05), "RPE 0.1 above target")

    def test_no_gap_or_one_that_rounds_to_nothing_gives_no_text(self):
        for delta in (None, 0, 0.04, -0.04):
            self.assertIsNone(checkin.rpe_gap_text(delta), delta)


class WholeNumberTest(unittest.TestCase):
    def test_whole_rounds_half_up_and_signs_changes(self):
        self.assertEqual([units.whole(v) for v in (32.92, 32.5, 0.4, -0.4, -1.5)], ["33", "33", "0", "0", "-2"])
        self.assertEqual([units.signed_whole(v) for v in (1.42, -1.42, 0.3, 0, None)],
                         ["+1", "-1", "±0", "±0", "—"])


if __name__ == "__main__":
    unittest.main()
