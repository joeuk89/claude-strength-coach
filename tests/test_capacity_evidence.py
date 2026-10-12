"""Capacity comparisons preserve unsupported and deliberately reduced observations."""

from datetime import datetime, timezone

from coach import history, overlay, stats
from tests.test_manual_log import NoHevyCase
from tests.support.history import read_json, write_json


class CapacityEvidenceTest(NoHevyCase):
    now = "2026-10-19T19:00:00Z"

    def setUp(self):
        super().setUp()
        (self.root / "data/log/workouts.jsonl").write_text("", encoding="utf-8")
        for path in (self.root / "data/history").glob("????-??.json"):
            path.unlink()

    def log_session(self, day, squat=100, bench=22.5, bench_reps=10, rpe=8, squat_rpe=7, overlay_id=None):
        draft = self.filled(day="2026-10-12")
        draft.update(date=day, overlay_id=overlay_id or (draft["overlay_id"] if day == "2026-10-12" else None))
        for exercise in draft["exercises"]:
            for logged in exercise["sets"]:
                if logged["type"] != "warmup":
                    logged.update(value=bench if exercise["exercise_id"] == "db_bench_press" else squat,
                                  reps=bench_reps if exercise["exercise_id"] == "db_bench_press" else 5,
                                  rpe=rpe if exercise["exercise_id"] == "db_bench_press" else squat_rpe)
        result = self.add(draft)
        self.coach("history", "sync")
        return result

    def test_over_cap_exposure_remains_an_observation_without_an_estimate(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=25, rpe=6)
        data = self.coach("stats", "e1rm", "--exercise", "db_bench_press")["data"]
        self.assertEqual(data["best"]["db_bench_press"], {"e1rm": 31.5, "date": "2026-10-05"})
        latest = data["observations"]["db_bench_press"][-1]
        self.assertFalse(latest["eligible"])
        self.assertEqual(latest["reason"], "over_rep_cap")
        self.assertIsNone(latest["e1rm"])
        self.assertEqual(latest["sets"][0]["reps_to_failure"], 14)
        self.assertEqual(latest["sets"][0]["load"], 25)

    def approve_context(self, kind="deload", decay=None, approved_at="2026-10-11T19:00:00Z"):
        path = next((self.root / "data/overlays").glob("2026-10-12-*.json"))
        doc = read_json(path)
        doc["kind"] = kind
        doc["id"] = "2026-10-12-" + kind.replace("_", "-")
        path.unlink()
        path = self.root / "data/overlays" / (doc["id"] + ".json")
        if decay:
            for line in doc["sessions"][0]["exercises"]:
                line["provenance"] = {"scheme": None, "derived_from": None, "inferred": False,
                                      "decay": decay, "rationale": "Return after a gap"}
        doc = overlay.approve(doc, datetime.fromisoformat(approved_at.replace("Z", "+00:00")))
        write_json(path, doc)
        return doc

    def test_approved_deload_is_inspectable_without_lowering_capacity(self):
        self.log_session("2026-10-05")
        self.approve_context()
        self.log_session("2026-10-12", squat=90, bench=18.5, bench_reps=8, rpe=6, squat_rpe=6)
        data = stats.e1rm_series(self.root)
        for exercise_id, normal, recovery in (("bb_back_squat", 126.67, 117),
                                               ("db_bench_press", 31.5, 25.9)):
            with self.subTest(exercise=exercise_id):
                self.assertEqual([p["e1rm"] for p in data["series"][exercise_id]], [normal])
                self.assertIsNone(data["delta"][exercise_id])
                observed = data["observations"][exercise_id][-1]
                self.assertEqual(observed["e1rm"], recovery)
                self.assertTrue(observed["eligible"])
                self.assertFalse(observed["comparable"])
                self.assertEqual(observed["context"]["kind"], "deload")
        exposures = history.exposures(self.root, "bb_back_squat")
        self.assertEqual(exposures[0]["date"], "2026-10-12")
        self.assertFalse(exposures[0]["excluded"])

    def test_new_easy_work_cannot_be_vetoed_by_an_older_estimate(self):
        from coach import units

        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=25, rpe=6)
        path = self.root / "data/overlays/2026-10-12-weekly.json"
        doc = read_json(path)
        doc["approval"] = None
        doc["span"] = {"start": "2026-10-19", "end": "2026-10-25"}
        doc["id"] = "2026-10-19-weekly"
        path = self.root / "data/overlays/2026-10-19-weekly.json"
        for session in doc["sessions"]:
            session["date"] = "2026-10-19"
            for line in session["exercises"]:
                if line["exercise_id"] == "db_bench_press":
                    line["sets"] = [{"type": "normal", "load": units.make_load(27, "per_hand_x2", "kg"),
                                     "reps": 8, "rpe": 7} for _ in range(3)]
        write_json(path, doc)
        result = self.coach("prescription", "check", "--overlay", doc["id"])["data"]
        bench_flags = [f["code"] for f in result["flags"] if f["exercise_id"] == "db_bench_press"]
        self.assertNotIn("unearned_load", bench_flags)
        row = next(r for r in result["lines"] if r["exercise_id"] == "db_bench_press")
        self.assertEqual(row["model_evidence"]["reason"], "over_rep_cap")
        self.assertIn("unavailable", row["model_evidence"]["message"])
        self.assertEqual(row["model_evidence"]["date"], "2026-10-12")
        bench = next(e for e in doc["sessions"][0]["exercises"] if e["exercise_id"] == "db_bench_press")
        for logged in bench["sets"]:
            logged["load"] = units.make_load(40, "per_hand_x2", "kg")
        write_json(path, doc)
        flags = self.coach("prescription", "check", "--overlay", doc["id"])["data"]["flags"]
        self.assertIn("unearned_load", [f["code"] for f in flags if f["exercise_id"] == "db_bench_press"])

    def test_priority_rep_range_without_eligible_sets_warns_for_that_lift(self):
        path = self.root / "data/program.json"
        doc = read_json(path)
        doc["priority"] = [{"exercise_id": "db_bench_press", "kpi": {"kind": "e1rm", "target": None, "by": None},
                            "floor": {"sets": 2, "rpe": None}}]
        line = next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == "db_bench_press")
        for group in line["sets"]:
            group.pop("reps", None)
            group.update(rep_range={"start": 10, "end": 15}, rpe=7)
        write_json(path, doc)
        warnings = self.coach("program", "validate")["warnings"]
        self.assertTrue(any("priority_no_e1rm" in w and "db_bench_press" in w for w in warnings), warnings)
        line["sets"][0].update(rep_range={"start": 8, "end": 10}, rpe=8)
        write_json(path, doc)
        self.assertFalse(any("priority_no_e1rm" in w for w in self.coach("program", "validate")["warnings"]))

    def test_one_off_name_alone_keeps_hard_work_comparable_but_return_decay_does_not(self):
        self.log_session("2026-10-05")
        self.approve_context(kind="one_off")
        self.log_session("2026-10-12", bench=25)
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 35)
        self.approve_context(kind="one_off", decay={"days_off": 14, "band": "11-21", "load_factor": 0.95,
                                                     "set_delta": -1, "rpe_cap": None})
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "return")
        self.assertEqual(data["series"]["db_bench_press"][-1]["date"], "2026-10-05")
        self.assertFalse(history.exposures(self.root, "db_bench_press")[0]["excluded"])

    def test_future_approval_does_not_change_an_as_of_capacity_series(self):
        self.log_session("2026-10-05")
        self.approve_context(approved_at="2026-10-14T19:00:00Z")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        then = datetime(2026, 10, 13, 23, tzinfo=timezone.utc)
        data = stats.e1rm_series(self.root, as_of=then)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 25.9)
        self.assertEqual(stats.e1rm_series(self.root)["series"]["db_bench_press"][-1]["e1rm"], 31.5)

    def decision(self, kind="light_week", **updates):
        from coach import decisions

        decision = {"id": "d-0001", "kind": kind, "made_at": "2026-10-11T19:00:00Z", "overlay_id": None,
                    "scope": {}, "outcome": "adopted", "reason": "Planned recovery", "standing": False,
                    "until": None, "revisit_on": None, "proposed_sets": None, "chosen_sets": None,
                    "details": {"type": "light", "week": "2026-10-12", "reason": "coach", "triggers": [],
                                "hard_weeks": 4}, "status": "active", "closed_at": None, "closed_reason": None}
        decision.update(updates)
        write_json(decisions.path_for(self.root), {"schema_version": 1, "decisions": [decision]})
        return decision

    def test_adopted_light_decision_is_bounded_by_as_of(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        self.decision(made_at="2026-10-14T19:00:00Z")
        then = datetime(2026, 10, 13, 23, tzinfo=timezone.utc)
        self.assertEqual(stats.e1rm_series(self.root, as_of=then)["series"]["db_bench_press"][-1]["e1rm"], 25.9)
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 31.5)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "light")

    def test_explicit_reduced_override_only_marks_its_own_one_off_lift(self):
        self.log_session("2026-10-05")
        doc = self.approve_context(kind="one_off")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        self.decision(kind="override", overlay_id=doc["id"],
                      scope={"session_id": "session-a", "exercise_id": "db_bench_press"}, details=None,
                      proposed_sets=[{"type": "normal", "load": 22.5, "reps": 10, "rpe": 8}] * 3,
                      chosen_sets=[{"type": "normal", "load": 18.5, "reps": 8, "rpe": 6}] * 2)
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 31.5)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "reduced")
        self.assertEqual(data["series"]["bb_back_squat"][-1]["date"], "2026-10-12")
        self.decision(kind="override", overlay_id=doc["id"],
                      scope={"session_id": "session-a", "exercise_id": "db_bench_press"}, details=None,
                      proposed_sets=[{"type": "normal", "load": 22.5, "reps": 10, "rpe": 8}],
                      chosen_sets=[{"type": "normal", "load": 25, "reps": 10, "rpe": 8}])
        self.assertEqual(stats.e1rm_series(self.root)["series"]["db_bench_press"][-1]["date"], "2026-10-12")

    def test_card_progress_and_priority_use_normal_capacity_and_explain_recovery(self):
        from coach import pages

        self.log_session("2026-10-05")
        self.approve_context()
        self.log_session("2026-10-12", squat=90, bench=18.5, bench_reps=8, rpe=6, squat_rpe=6)
        card = self.coach("checkin", "prepare", "--until", "2026-10-18")["data"]
        self.assertFalse(any(row["delta"] is not None and row["delta"] < 0 for row in card["card"]["e1rm"]))
        self.assertIn("deload (light week), kept in the log", card["text"])
        progress = pages.render_progress(self.root, datetime(2026, 10, 19, 19, tzinfo=timezone.utc))
        self.assertIn("31.5", progress)
        self.assertNotIn("25.9", progress)
        self.assertIn("deload (light week), kept in the log", progress)
        path = self.root / "data/program.json"
        doc = read_json(path)
        doc["priority"] = [{"exercise_id": "db_bench_press", "kpi": {"kind": "e1rm", "target": None, "by": None},
                            "floor": {"sets": 2, "rpe": None}}]
        write_json(path, doc)
        lift = self.coach("structure", "priority")["data"]["lifts"][0]
        self.assertEqual(lift["kpi"]["now"], {"value": 31.5, "date": "2026-10-05"})
        self.assertIsNone(lift["kpi"]["trend"])

    def test_lower_reps_with_a_heavier_override_is_not_recovery(self):
        self.approve_context(kind="one_off")
        self.log_session("2026-10-12", bench=27, bench_reps=8)
        self.decision(kind="override", overlay_id="2026-10-12-one-off",
                      scope={"session_id": "session-a", "exercise_id": "db_bench_press"}, details=None,
                      proposed_sets=[{"type": "normal", "load": 25, "reps": 10, "rpe": 8}] * 3,
                      chosen_sets=[{"type": "normal", "load": 27, "reps": 8, "rpe": 8}] * 3)
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 36)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "normal")

    def test_proposal_explains_missing_model_and_keeps_return_work_as_baseline(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=25, rpe=6)
        result = self.coach("propose", "week", "--week", "2026-10-19")["data"]
        bench = next(r for r in result["lines"] if r["exercise_id"] == "db_bench_press")
        self.assertIn("27/hand", bench["text"])
        self.assertIn("unavailable", bench["rationale"])
        self.assertNotIn("unearned_load", bench["flags"])
        self.approve_context(kind="weekly", decay={"days_off": 14, "band": "11-21", "load_factor": 0.95,
                                                    "set_delta": -1, "rpe_cap": None})
        result = self.coach("propose", "week", "--week", "2026-10-19")["data"]
        bench = next(r for r in result["lines"] if r["exercise_id"] == "db_bench_press")
        self.assertIn("2026-10-12", bench["rationale"])
        self.assertIn("27/hand", bench["text"])
        self.assertNotIn("unearned_load", bench["flags"])

    def test_later_overlay_does_not_reclassify_stored_exposure_provenance(self):
        self.log_session("2026-10-12", bench=25)
        path = self.root / "data/overlays/2026-10-12-weekly.json"
        doc = read_json(path)
        doc.update(id="2026-10-12-deload", kind="deload", created_at="2026-10-14T18:00:00Z")
        doc = overlay.approve(doc, datetime(2026, 10, 14, 19, tzinfo=timezone.utc))
        write_json(path.with_name("2026-10-12-deload.json"), doc)
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 35)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["overlay_id"],
                         "2026-10-12-weekly")

    def test_withdrawal_after_training_keeps_historic_light_context(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        self.decision(status="withdrawn", closed_at="2026-10-14T19:00:00Z", closed_reason="Resume normal work")
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 31.5)
        self.decision(status="withdrawn", closed_at="2026-10-11T20:00:00Z", closed_reason="Cancel recovery")
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 25.9)

    def test_new_eligible_normal_work_restores_model_evidence(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=25, rpe=6)
        self.log_session("2026-10-18", bench=27, bench_reps=8, rpe=8)
        data = stats.e1rm_series(self.root)
        evidence = stats.capacity_evidence(data, "db_bench_press", "2026-10-19", 42)
        self.assertEqual(evidence["estimate"]["e1rm"], 36)
        self.assertIsNone(evidence["reason"])

    def time_workout(self, day, start, end):
        path = self.root / "data/history/2026-10.json"
        doc = read_json(path)
        for workout in doc["workouts"]:
            if workout["date"] == day:
                workout.update(start_time=start, end_time=end)
        write_json(path, doc)

    def test_same_day_withdrawal_after_a_timed_workout_keeps_light_context(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        self.time_workout("2026-10-12", "2026-10-12T17:00:00Z", "2026-10-12T18:00:00Z")
        self.decision(status="withdrawn", closed_at="2026-10-12T21:00:00Z", closed_reason="Resume normal work")
        for as_of in (None, datetime(2026, 10, 12, 20, tzinfo=timezone.utc),
                      datetime(2026, 10, 13, 1, tzinfo=timezone.utc)):
            with self.subTest(as_of=as_of):
                data = stats.e1rm_series(self.root, as_of=as_of)
                self.assertEqual(data["series"]["db_bench_press"][-1]["date"], "2026-10-05")
                self.assertIsNone(data["delta"]["db_bench_press"])
                self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "light")
        self.decision(status="withdrawn", closed_at="2026-10-12T16:00:00Z", closed_reason="Cancel recovery")
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["e1rm"], 25.9)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "normal")

    def test_same_day_withdrawal_without_workout_timing_keeps_light_context(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=6)
        self.decision(status="withdrawn", closed_at="2026-10-12T06:00:00Z", closed_reason="Resume normal work")
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["series"]["db_bench_press"][-1]["date"], "2026-10-05")
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "light")

    def standing_week(self, carried=True, approved_at="2026-10-18T19:00:00Z"):
        from coach import units

        doc = read_json(self.root / "data/overlays/2026-10-12-weekly.json")
        doc.update(id="2026-10-19-weekly", span={"start": "2026-10-19", "end": "2026-10-25"},
                   created_at="2026-10-18T18:00:00Z")
        for session in doc["sessions"]:
            session["date"] = "2026-10-19"
            for line in session["exercises"]:
                if line["exercise_id"] == "db_bench_press":
                    line["sets"] = [{"type": "normal", "load": units.make_load(18.5, "per_hand_x2", "kg"),
                                     "reps": 8, "rpe": 6} for _ in range(2)]
                    line["override"] = {"reason": "Shoulder settles at lighter work", "proposed_sets": [
                        {"type": "normal", "load": units.make_load(23.5, "per_hand_x2", "kg"), "reps": 10, "rpe": 8}
                        for _ in range(3)]} if carried else None
        doc = overlay.approve(doc, datetime.fromisoformat(approved_at.replace("Z", "+00:00")))
        write_json(self.root / "data/overlays/2026-10-19-weekly.json", doc)
        return doc

    def standing_decision(self, made_at="2026-10-11T19:00:00Z"):
        return self.decision(kind="override", overlay_id="2026-10-12-weekly", made_at=made_at,
                             scope={"session_id": "session-a", "exercise_id": "db_bench_press"}, details=None,
                             reason="Shoulder settles at lighter work", standing=True, until="2026-11-08",
                             proposed_sets=[{"type": "normal", "load": 22.5, "reps": 10, "rpe": 8}] * 3,
                             chosen_sets=[{"type": "normal", "load": 18.5, "reps": 8, "rpe": 6}] * 2)

    def test_standing_reduction_keeps_its_provenance_in_a_later_approved_overlay(self):
        self.log_session("2026-10-05")
        doc = self.standing_week()
        self.log_session("2026-10-19", bench=18.5, bench_reps=8, rpe=6, overlay_id=doc["id"])
        decision = self.standing_decision()
        data = stats.e1rm_series(self.root)
        self.assertEqual(data["observations"]["db_bench_press"][-1]["context"],
                         {"kind": "reduced", "overlay_id": doc["id"], "decision_id": decision["id"]})
        self.assertEqual(data["series"]["db_bench_press"][-1]["date"], "2026-10-05")
        self.assertIsNone(data["delta"]["db_bench_press"])

    def test_standing_reduction_applies_only_to_overlays_that_carried_it(self):
        self.log_session("2026-10-05")
        for case, carried, made_at in (("not carried", False, "2026-10-11T19:00:00Z"),
                                       ("made after approval", True, "2026-10-19T08:00:00Z")):
            with self.subTest(case=case):
                doc = self.standing_week(carried=carried)
                if case == "not carried":
                    self.log_session("2026-10-19", bench=18.5, bench_reps=8, rpe=6, overlay_id=doc["id"])
                self.standing_decision(made_at=made_at)
                data = stats.e1rm_series(self.root)
                self.assertEqual(data["observations"]["db_bench_press"][-1]["context"]["kind"], "normal")
                self.assertEqual(data["series"]["db_bench_press"][-1]["date"], "2026-10-19")

    def next_week_bench(self, load, reps, rpe):
        from coach import units

        doc = read_json(next((self.root / "data/overlays").glob("2026-10-12-*.json")))
        doc.update(id="2026-10-19-weekly", kind="weekly", span={"start": "2026-10-19", "end": "2026-10-25"},
                   approval=None)
        for session in doc["sessions"]:
            session["date"] = "2026-10-19"
            for line in session["exercises"]:
                if line["exercise_id"] == "db_bench_press":
                    line["sets"] = [{"type": "normal", "load": units.make_load(load, "per_hand_x2", "kg"),
                                     "reps": reps, "rpe": rpe} for _ in range(3)]
        write_json(self.root / "data/overlays/2026-10-19-weekly.json", doc)
        result = self.coach("prescription", "check", "--overlay", doc["id"])["data"]
        flags = [f["code"] for f in result["flags"] if f["exercise_id"] == "db_bench_press"]
        return flags, next(r for r in result["lines"] if r["exercise_id"] == "db_bench_press")

    def test_over_cap_recovery_work_keeps_the_older_estimate_veto(self):
        self.log_session("2026-10-05")
        doc = self.approve_context()
        self.log_session("2026-10-12", bench=18.5, bench_reps=8, rpe=5, overlay_id=doc["id"])
        observed = stats.e1rm_series(self.root)["observations"]["db_bench_press"][-1]
        self.assertEqual((observed["reason"], observed["context"]["kind"]), ("recovery_context", "deload"))
        flags, row = self.next_week_bench(22.5, 12, 7)
        self.assertIn("rpe_infeasible", flags)
        self.assertIsNone(row["model_evidence"]["reason"])
        self.assertEqual(row["model_evidence"]["estimate"]["e1rm"], 31.5)
        result = self.coach("propose", "week", "--week", "2026-10-19")["data"]
        bench = next(r for r in result["lines"] if r["exercise_id"] == "db_bench_press")
        self.assertNotIn("unavailable", bench["rationale"])

    def test_every_prescription_check_line_carries_its_model_evidence(self):
        self.log_session("2026-10-05")
        flags, row = self.next_week_bench(22.5, 10, 8)
        self.assertEqual(row["model_evidence"]["estimate"]["e1rm"], 31.5)
        result = self.coach("prescription", "check", "--overlay", "2026-10-19-weekly")["data"]
        self.assertTrue(all("model_evidence" in line for line in result["lines"]))

    def assisted_context(self, chosen_load):
        from coach import capacity

        doc = self.approve_context(kind="one_off")
        self.decision(kind="override", overlay_id=doc["id"],
                      scope={"session_id": "session-a", "exercise_id": "db_bench_press"}, details=None,
                      proposed_sets=[{"type": "normal", "load": 20, "reps": 8, "rpe": 8}] * 3,
                      chosen_sets=[{"type": "normal", "load": chosen_load, "reps": 8, "rpe": 8}] * 3)
        exposure = {"date": "2026-10-12", "start_time": None, "session_id": "session-a",
                    "exercise_id": "db_bench_press", "load_mode": "assisted", "overlay_id": doc["id"]}
        return capacity.Context(self.root).for_exposure(exposure)["kind"]

    def test_more_assistance_is_a_reduction_and_less_assistance_is_not(self):
        self.assertEqual(self.assisted_context(30), "reduced")
        self.assertEqual(self.assisted_context(10), "normal")

    def card_and_progress(self):
        from coach import pages

        card = self.coach("checkin", "prepare", "--until", "2026-10-18")["data"]
        progress = pages.render_progress(self.root, datetime(2026, 10, 19, 19, tzinfo=timezone.utc))
        return card["card"]["e1rm_notes"], card["text"], progress

    def test_lifts_that_cannot_have_an_e1rm_get_no_notes(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12")
        path = self.root / "data/history/2026-10.json"
        original = read_json(path)
        for mode in ("band", "duration", "distance"):
            with self.subTest(mode=mode):
                doc = read_json(path)
                for workout in doc["workouts"]:
                    for exercise in workout["exercises"]:
                        if workout["date"] == "2026-10-12" and exercise["exercise_id"] == "db_bench_press":
                            exercise["load_mode"] = mode
                write_json(path, doc)
                notes, text, progress = self.card_and_progress()
                self.assertEqual(notes, [])
                self.assertNotIn("e1RM notes", text)
                self.assertNotIn("unsupported", progress)
        write_json(path, original)
        draft = self.prefill(session="session-b", day="2026-10-13")
        for exercise in draft["exercises"]:
            for logged in exercise["sets"]:
                logged.update(reps=8, rpe=8, value=logged["value"] if logged["value"] is not None else 0)
        self.add(draft)
        self.coach("history", "sync")
        observed = stats.e1rm_series(self.root)["observations"]["pull_up"][-1]
        self.assertEqual(observed["reason"], "no_bodyweight_reading")
        notes, text, progress = self.card_and_progress()
        self.assertEqual(notes, [])
        self.assertNotIn("Pull Up (", progress)

    def test_notes_name_cap_and_light_week_reasons_plainly(self):
        self.log_session("2026-10-05")
        self.log_session("2026-10-12", bench=25, rpe=6)
        notes, text, progress = self.card_and_progress()
        self.assertEqual(notes, ["Bench Press (Dumbbell) (2026-10-12): more than 12 reps from failure, "
                                 "too far for an e1RM"])
        self.assertIn("e1RM notes:", text)
        self.assertIn("more than 12 reps from failure", progress)
        self.decision(details={"type": "light", "week": "2026-10-12", "reason": "coach", "triggers": [],
                               "hard_weeks": 4})
        notes, _, _ = self.card_and_progress()
        self.assertEqual(notes, [f"{name} (2026-10-12): light week, kept in the log and left out of e1RM changes"
                                 for name in ("Back Squat (Barbell)", "Bench Press (Dumbbell)")])

    def test_progress_without_an_e1rm_says_where_one_comes_from(self):
        from coach import pages

        progress = pages.render_progress(self.root, datetime(2026, 10, 19, 19, tzinfo=timezone.utc))
        self.assertIn("No e1RM yet: it comes from logged working sets of barbell, dumbbell and machine lifts.",
                      progress)
