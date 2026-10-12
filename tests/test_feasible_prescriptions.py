"""Proposals and the prescription check share one e1RM model verdict (contract C18, C22, C24)."""

import re
import unittest

from coach import units, validity
from tests.support import run_module
from tests.support.history import read_json, write_json
from tests.test_manual_log import NoHevyCase

RATED = {"e1rm": 31.5, "date": "2026-10-05", "method": "epley_rir"}
UNRATED = {"e1rm": 116.67, "date": "2026-10-12", "method": "epley"}
OFF_SCALE_RPE = re.compile(r"RPE (-\d|1\d\.|1[1-9]\b|[2-9]\d)")
MODEL_CODES = ("unearned_load", "rpe_infeasible")


class JudgeSetTest(unittest.TestCase):
    def test_a_range_passes_when_any_whole_rep_target_fits(self):
        verdict = validity.judge_set(RATED, 20, validity.rep_targets(None, (10, 15)), 8)
        self.assertEqual((verdict.unearned, verdict.off), (False, None))

    def test_a_range_no_target_of_which_fits_is_still_off(self):
        verdict = validity.judge_set(RATED, 20, validity.rep_targets(None, (10, 12)), 8)
        self.assertEqual((verdict.off, verdict.reps), ("easy", 12))

    def test_a_ceiling_is_never_too_easy(self):
        self.assertIsNone(validity.judge_set(RATED, 18.5, (8,), 6, ceiling=True).off)
        self.assertEqual(validity.judge_set(RATED, 18.5, (8,), 6).off, "easy")

    def test_a_ceiling_still_catches_work_too_hard_for_it(self):
        self.assertEqual(validity.judge_set(RATED, 25, (8,), 6, ceiling=True).off, "hard")
        self.assertTrue(validity.judge_set(RATED, 27.5, (8,), 6, ceiling=True).unearned)

    def test_an_estimate_from_unrated_sets_cannot_establish_failure(self):
        verdict = validity.judge_set(UNRATED, 102.5, (5,), 7)
        self.assertEqual((verdict.unearned, verdict.off), (False, None))
        self.assertTrue(validity.judge_set(dict(UNRATED, method="epley_rir"), 102.5, (5,), 7).unearned)

    def test_an_unrated_estimate_can_still_show_a_load_too_light(self):
        self.assertEqual(validity.judge_set(UNRATED, 60, (5,), 8).off, "easy")

    def test_off_scale_results_are_never_worded_as_ratings(self):
        self.assertEqual(validity.implied_words(7.75), "RPE 7.75")
        for value in (-3.08, 11.25):
            with self.subTest(value=value):
                words = validity.implied_words(value)
                self.assertNotIn("RPE -", words)
                self.assertIn("model result", words)


class LoadForCommandTest(unittest.TestCase):
    def run_load_for(self, *extra):
        code, envelope, _ = run_module(["units", "load-for", "--e1rm", "19.6", "--reps", "8", *extra])
        self.assertEqual(code, 0, envelope)
        return envelope["data"]

    def test_the_model_load_is_unrounded_to_any_kit(self):
        data = self.run_load_for("--rpe", "8")
        self.assertEqual(data["model"]["load"], 14.7)
        self.assertEqual(data["model"]["reps_to_failure"], 10)
        self.assertIsNone(data["equipment"])

    def test_a_grid_reports_the_achievable_load_separately(self):
        data = self.run_load_for("--rpe", "8", "--increment", "2")
        self.assertEqual(data["model"]["load"], 14.7)
        self.assertEqual(data["equipment"]["load"], 14)
        self.assertEqual(data["equipment"]["increment"], 2)
        self.assertIn("not rounded to any equipment", data["model"]["calculation"])

    def test_past_the_model_range_it_gives_no_load(self):
        data = self.run_load_for("--rpe", "4", "--increment", "2")
        self.assertIsNone(data["model"]["load"])
        self.assertIn("12", data["model"]["reason"])
        self.assertIsNone(data["equipment"])


def _sets(spec):
    """`18x10@6,20x9@10*2` as (load, reps, rpe) rows; `*N` repeats the group before it."""
    found = []
    for part in spec.split(","):
        part, _, times = part.partition("*")
        load, _, rest = part.partition("x")
        reps, _, rpe = rest.partition("@")
        found += [(float(load), int(reps), float(rpe) if rpe else None)] * int(times or 1)
    return found


class GeneratedLinesCase(NoHevyCase):
    """The no-Hevy instance with an empty log, a 2 kg dumbbell step and a linear squat."""

    now = "2026-10-18T19:00:00Z"

    def setUp(self):
        super().setUp()
        (self.root / "data/log/workouts.jsonl").write_text("", encoding="utf-8")
        for path in (self.root / "data/history").glob("????-??.json"):
            path.unlink()
        config = self.root / "config.toml"
        config.write_text(config.read_text(encoding="utf-8").replace("dumbbell_increment = 2.5",
                                                                     "dumbbell_increment = 2"), encoding="utf-8")
        self.edit_slot("bb_back_squat", lambda slot: slot.update(scheme={"name": "linear", "params": {}}))

    def edit_slot(self, exercise_id, change):
        path = self.root / "data/program.json"
        doc = read_json(path)
        change(next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == exercise_id))
        write_json(path, doc)

    def log(self, session, day, exercise_id, spec):
        draft = self.prefill(session=session, day=day)
        exercise = next(e for e in draft["exercises"] if e["exercise_id"] == exercise_id)
        exercise["sets"] = [{"type": "normal", "reps": reps, "rpe": rpe, "value": load, "duration_seconds": None,
                             "distance_meters": None} for load, reps, rpe in _sets(spec)]
        draft["exercises"] = [exercise]
        self.add(draft)
        self.coach("history", "sync")

    def proposed(self, exercise_id, *extra):
        data = self.coach("propose", "week", "--week", "2026-W43", "--dry-run", *extra)["data"]
        line = next(row for row in data["lines"] if row["exercise_id"] == exercise_id)
        overlay_line = next(e for s in data["overlay"]["sessions"] for e in s["exercises"]
                            if e["exercise_id"] == exercise_id)
        flags = [f for f in data["overlay"]["flags"] if f["exercise_id"] == exercise_id]
        loads = {s["load"]["per_hand"] if s["load"]["mode"] in units.PER_HAND_MODES else s["load"]["hevy_total"]
                 for s in overlay_line["sets"] if s["type"] == "normal"}
        return line, loads, flags


class GeneratedLinesTest(GeneratedLinesCase):
    def test_a_linear_step_from_sets_without_rpe_is_not_judged_beyond_failure(self):
        self.log("session-a", "2026-10-12", "bb_back_squat", "100x5*3")
        line, loads, flags = self.proposed("bb_back_squat")
        self.assertEqual(loads, {102.5})
        self.assertNotIn("unearned_load", line["flags"])

    def test_an_earned_dumbbell_step_the_model_rejects_holds_the_logged_load(self):
        self.log("session-a", "2026-10-12", "db_bench_press", "14x10@8*3")
        line, loads, _ = self.proposed("db_bench_press")
        self.assertEqual(loads, {14})
        self.assertNotIn("unearned_load", line["flags"])
        self.assertIn("16/hand × 8 (the closest rep target in 8–10) implies a model result of 11.25",
                      line["rationale"])
        self.assertIn("the e1RM of 19.6 from 2026-10-12, so 14/hand, the heaviest load logged", line["rationale"])
        self.assertNotIn("(Hevy:", line["rationale"])
        self.assertIn("3×8–10 @ 14/hand", line["text"])

    def test_a_fixed_rep_step_the_model_rejects_holds_the_logged_load(self):
        self.log("session-b", "2026-10-15", "db_single_arm_row", "30x10@8*3")
        line, loads, _ = self.proposed("db_single_arm_row")
        self.assertEqual(loads, {30})
        self.assertNotIn("unearned_load", line["flags"])
        self.assertIn("implies a model result of 10.62", line["rationale"])

    def test_mixed_loads_hold_a_range_line_the_model_accepts(self):
        self.log("session-a", "2026-10-12", "db_bench_press", "18x10@6,20x9@10*2")
        line, loads, _ = self.proposed("db_bench_press")
        self.assertEqual(loads, {20})
        self.assertNotIn("unearned_load", line["flags"])

    def test_mixed_loads_never_earn_the_failed_load_for_fixed_reps(self):
        self.edit_slot("db_bench_press", lambda slot: slot.update(
            sets=[{"count": 3, "type": "normal", "reps": 10, "rpe": 8}]))
        self.log("session-a", "2026-10-12", "db_bench_press", "18x10@6,20x9@10*2")
        line, loads, _ = self.proposed("db_bench_press")
        self.assertEqual(loads, {18})
        self.assertNotIn("unearned_load", line["flags"])
        self.assertIn("20/hand × 10 implies a model result of 11", line["rationale"])

    def test_a_step_with_no_e1rm_says_the_model_did_not_check_it(self):
        self.log("session-a", "2026-10-12", "db_bench_press", "4x12@6*3")
        line, loads, _ = self.proposed("db_bench_press")
        self.assertEqual(loads, {6})
        self.assertNotIn("unearned_load", line["flags"])
        self.assertIn("e1RM unavailable", line["rationale"])
        self.assertNotIn("model accepts", line["rationale"])

    def test_a_deload_line_is_not_held_by_the_model(self):
        path = self.root / "data/program.json"
        doc = read_json(path)
        doc["blocks"]["deload_rule"]["params"] = {"load_factor": 1}
        write_json(path, doc)
        self.edit_slot("db_bench_press", lambda slot: slot.update(
            sets=[{"count": 3, "type": "normal", "reps": 10, "rpe": 8}]))
        self.log("session-a", "2026-10-12", "db_bench_press", "18x10@6,20x9@10*2")
        line, loads, _ = self.proposed("db_bench_press", "--kind", "deload")
        self.assertEqual(loads, {18})
        self.assertIn("the standard deload", line["rationale"])
        self.assertNotIn("model accepts", line["rationale"])
        self.assertIn("the e1RM model reaches at most 8 reps at RPE 6, so 8 reps", line["rationale"])
        self.assertNotIn("unearned_load", line["flags"])
        self.assertNotIn("rpe_infeasible", line["flags"])

    def test_with_no_logged_load_the_model_accepts_the_scheme_load_stays_flagged(self):
        self.edit_slot("db_bench_press", lambda slot: slot.update(
            sets=[{"count": 3, "type": "normal", "reps": 15, "rpe": 8}]))
        self.log("session-a", "2026-10-12", "db_bench_press", "20x5@10*3")
        line, loads, _ = self.proposed("db_bench_press")
        self.assertEqual(loads, {20})
        self.assertIn("unearned_load", line["flags"])
        self.assertNotIn("model accepts", line["rationale"])


class CheckCase(NoHevyCase):
    """The no-Hevy instance with an empty log, checking a bench line of the next week against the model's flags."""

    now = "2026-10-19T19:00:00Z"

    def setUp(self):
        super().setUp()
        (self.root / "data/log/workouts.jsonl").write_text("", encoding="utf-8")
        for path in (self.root / "data/history").glob("????-??.json"):
            path.unlink()

    def log_bench(self, day, load, reps, rpe):
        draft = self.filled(day="2026-10-12")
        draft.update(date=day, overlay_id=None)
        for exercise in draft["exercises"]:
            for logged in exercise["sets"]:
                if logged["type"] != "warmup":
                    if exercise["exercise_id"] == "db_bench_press":
                        logged.update(value=load, reps=reps, rpe=rpe)
                    else:
                        logged.update(value=100, reps=5, rpe=7)
        self.add(draft)
        self.coach("history", "sync")

    def check(self, sets, kind="weekly", provenance=None):
        source = self.root / "data/overlays/2026-10-12-weekly.json"
        doc = read_json(source)
        doc.update(approval=None, kind=kind, id=f"2026-10-19-{kind}", span={"start": "2026-10-19", "end": "2026-10-25"})
        for session in doc["sessions"]:
            session["date"] = "2026-10-19" if session["session_id"] == "session-a" else "2026-10-22"
            for line in session["exercises"]:
                if line["exercise_id"] == "db_bench_press":
                    line["sets"] = sets
                    line["provenance"] = provenance
        write_json(self.root / f"data/overlays/{doc['id']}.json", doc)
        data = self.coach("prescription", "check", "--overlay", doc["id"])["data"]
        flags = [f for f in data["flags"] if f["exercise_id"] == "db_bench_press" and f["code"] in MODEL_CODES]
        row = next(r for r in data["lines"] if r["exercise_id"] == "db_bench_press")
        return flags, row

    def bench_sets(self, count, load, rpe, reps=None, rep_range=None):
        return [{"type": "normal", "load": units.make_load(load, "per_hand_x2", "kg"), "reps": reps,
                 "rep_range": rep_range, "rpe": rpe} for _ in range(count)]


class CheckTest(CheckCase):
    def test_a_range_any_target_of_which_is_feasible_passes(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        flags, row = self.check(self.bench_sets(3, 20, 8, rep_range={"start": 10, "end": 15}))
        self.assertEqual(flags, [])
        self.assertEqual((row["feasibility"]["status"], row["feasibility"]["rpe"]), ("checked", "target"))

    def test_a_range_no_target_of_which_is_feasible_still_warns(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        flags, _ = self.check(self.bench_sets(3, 20, 8, rep_range={"start": 10, "end": 12}))
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])
        self.assertIn("× 12 (the closest rep target in 10–12) implies RPE 4.75", flags[0]["message"])

    def test_a_recovery_ceiling_is_not_flagged_as_too_easy(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        flags, row = self.check(self.bench_sets(2, 18.5, 6, reps=8), kind="deload")
        self.assertEqual(flags, [])
        self.assertEqual(row["feasibility"]["rpe"], "ceiling")
        self.assertIn("ceiling", row["feasibility"]["message"])

    def test_a_return_band_line_is_not_flagged_as_too_easy(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        decay = {"days_off": 14, "band": "11-21", "load_factor": 0.95, "set_delta": -1, "rpe_cap": None}
        provenance = {"scheme": "double_progression", "derived_from": None, "inferred": False, "decay": decay,
                      "rationale": None}
        flags, row = self.check(self.bench_sets(2, 18.5, 8, reps=8), provenance=provenance)
        self.assertEqual(flags, [])
        self.assertEqual(row["feasibility"]["rpe"], "ceiling")
        self.assertIn("a return-band line", row["feasibility"]["message"])
        flags, _ = self.check(self.bench_sets(2, 18.5, 8, reps=8))
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])

    def test_the_first_session_after_illness_is_not_flagged_as_too_easy(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-15", "--session", "session-b",
                   "--tag", "ill")
        flags, row = self.check(self.bench_sets(2, 18.5, 7, reps=8))
        self.assertEqual(flags, [])
        self.assertEqual(row["feasibility"]["rpe"], "ceiling")
        self.assertIn("the first session after illness", row["feasibility"]["message"])
        flags, row = self.check(self.bench_sets(2, 18.5, 6, reps=8))
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])
        self.assertIn("target RPE 6", flags[0]["message"])
        self.assertEqual(row["feasibility"]["rpe"], "target")

    def test_an_rpe_cap_constraint_makes_the_rpe_a_ceiling(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        path = self.root / "data/program.json"
        doc = read_json(path)
        slot = next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == "db_bench_press")
        slot["constraints"] = [{"kind": "rpe_cap", "value": 6, "reason": "synthetic elbow"}]
        write_json(path, doc)
        flags, row = self.check(self.bench_sets(2, 18.5, 6, reps=8))
        self.assertEqual(flags, [])
        self.assertEqual(row["feasibility"]["rpe"], "ceiling")

    def cap_bench(self, value):
        path = self.root / "data/program.json"
        doc = read_json(path)
        slot = next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == "db_bench_press")
        slot["constraints"] = [{"kind": "rpe_cap", "value": value, "reason": "synthetic elbow"}]
        write_json(path, doc)

    def test_a_set_under_an_rpe_cap_keeps_its_rpe_a_target(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        self.cap_bench(7)
        flags, row = self.check(self.bench_sets(2, 18.5, 6, reps=8))
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])
        self.assertIn("target RPE 6, but", flags[0]["message"])
        self.assertEqual(row["feasibility"]["rpe"], "target")
        self.assertNotIn("ceiling", row["feasibility"]["message"])

    def test_a_line_part_under_an_rpe_cap_judges_each_set_by_its_own_reading(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        self.cap_bench(7)
        flags, row = self.check(self.bench_sets(1, 18.5, 7, reps=8) + self.bench_sets(1, 18.5, 6, reps=8))
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])
        self.assertIn("target RPE 6, but", flags[0]["message"])
        self.assertEqual(row["feasibility"]["rpe"], "ceiling")
        self.assertIn("ceiling on 1 of 2 working sets (an RPE cap constraint)", row["feasibility"]["message"])

    def test_work_over_a_recovery_ceiling_is_still_flagged(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        flags, _ = self.check(self.bench_sets(2, 25, 6, reps=8), kind="deload")
        self.assertEqual([f["code"] for f in flags], ["rpe_infeasible"])
        self.assertIn("RPE ceiling 6, but", flags[0]["message"])
        flags, _ = self.check(self.bench_sets(2, 27.5, 6, reps=8), kind="deload")
        self.assertEqual([f["code"] for f in flags], ["unearned_load"])

    def test_no_message_prints_an_off_scale_result_as_an_rpe(self):
        self.log_bench("2026-10-12", 22.5, 10, 8)
        for sets in (self.bench_sets(2, 18.5, 8, reps=8), self.bench_sets(3, 27.5, 8, reps=8)):
            flags, _ = self.check(sets)
            with self.subTest(load=sets[0]["load"]["per_hand"]):
                self.assertTrue(flags)
                for flag in flags:
                    self.assertIsNone(OFF_SCALE_RPE.search(flag["message"]), flag["message"])
                    self.assertIn("model result", flag["message"])

    def test_an_over_cap_exposure_reports_no_model_check(self):
        self.log_bench("2026-10-12", 4, 12, 6)
        flags, row = self.check(self.bench_sets(3, 6, 8, rep_range={"start": 8, "end": 10}))
        self.assertEqual(flags, [])
        self.assertEqual(row["feasibility"]["status"], "unavailable")
        self.assertIn("No e1RM model check ran", row["feasibility"]["message"])
        self.assertIn("more than 12 reps from failure", row["feasibility"]["message"])

    def test_the_load_step_guard_still_judges_an_over_cap_jump(self):
        self.log_bench("2026-10-12", 4, 12, 6)
        flags, _ = self.check(self.bench_sets(3, 10, 8, rep_range={"start": 8, "end": 10}))
        self.assertEqual([f["code"] for f in flags], ["unearned_load"])
        self.assertIn("more than 2 increments", flags[0]["message"])

    def test_an_unrated_estimate_is_a_lower_bound_under_the_step_guard(self):
        self.log_bench("2026-10-12", 20, 10, None)
        flags, row = self.check(self.bench_sets(3, 22.5, 8, rep_range={"start": 8, "end": 10}))
        self.assertNotIn("unearned_load", [f["code"] for f in flags])
        self.assertEqual(row["feasibility"]["status"], "lower_bound")
        flags, _ = self.check(self.bench_sets(3, 27.5, 8, rep_range={"start": 8, "end": 10}))
        self.assertEqual([f["code"] for f in flags], ["unearned_load"])
        self.assertIn("comes from sets logged without RPE", flags[0]["message"])


if __name__ == "__main__":
    unittest.main()
