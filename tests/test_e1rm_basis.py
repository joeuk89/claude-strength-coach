"""e1RM eligibility and load basis: unsupported movements and total-system estimates (contract C18, C40)."""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coach import library, program, stats, units
from coach.plugins import base
from tests.support import INSTANCES, run_cli
from tests.support.history import read_json, write_json
from tests.test_progression_schemes import context, exposure, loads_and_reps, run

NOHEVY = INSTANCES / "nohevy"
LOG = Path("data") / "log" / "workouts.jsonl"
READINGS = Path("data") / "nutrition" / "readings.json"
OVERLAY = Path("data") / "overlays" / "2026-10-12-weekly.json"
SUNDAY = "2026-10-11T20:00:00Z"
CHECKIN_RECORD = INSTANCES / "checkin" / "check-ins" / "2026-10-04.md"
TOTAL_SYSTEM_TEXT = "total system mass"
BODY_MASS_REASON = "body mass dominates this movement"
SPLIT_SQUAT = base.ExerciseInfo(id="db_bulgarian_split_squat", name="Bulgarian split squat", pattern="lunge",
                                muscles={}, equipment="dumbbell", load_mode="per_hand_x2", increment=2,
                                is_compound=True, e1rm_supported=False)
TEN_AT_EIGHT = ({"count": 3, "type": "normal", "reps": 10, "rpe": 8},)


SESSION_DAY = datetime(2026, 10, 8).date()


def manual_workout(day, session_id, exercise_id, load_mode, sets):
    """A manual-log workout line; `sets` are (value, reps, rpe)."""
    return {"schema_version": 1, "kind": "workout", "id": f"manual:{day}-{session_id}-1",
            "logged_at": f"{day}T19:05:00Z", "date": day, "session_id": session_id, "overlay_id": None,
            "duration_minutes": 50, "notes": "",
            "exercises": [{"exercise_id": exercise_id, "load_mode": load_mode, "unit": "kg", "notes": "",
                           "sets": [{"type": "normal", "reps": reps, "rpe": rpe, "value": value,
                                     "duration_seconds": None, "distance_meters": None}
                                    for value, reps, rpe in sets]}]}


def reading(day, weight, unit="kg"):
    return {"date": day, "source": "app", "weight_unit": unit, "trend_weight": weight, "scale_weight": None,
            "expenditure_kcal": None, "target_kcal": None, "target_protein_g": None, "avg_kcal": None,
            "avg_protein_g": None, "days_logged": None, "anchors_most_days": None, "note": None}


def working(reps, rpe, per_hand, count=3):
    load = units.make_load(per_hand, "per_hand_x2", "kg")
    return [{"type": "normal", "reps": reps, "rpe": rpe, "load": load} for _ in range(count)]


class NoHevyCase(unittest.TestCase):
    """A temp copy of the Hevy-off `nohevy/` instance, with helpers to log workouts and nutrition readings."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(NOHEVY, self.root)
        self.confirm("db_bulgarian_split_squat", "per_hand_x2")
        self.confirm("assisted_pull_up", "assisted")

    def coach(self, *argv, expect=0, now=SUNDAY):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def confirm(self, exercise_id, load_mode):
        doc = read_json(self.root / "data" / "exercises.json")
        doc["exercises"][exercise_id] = {"hevy_template_id": None, "load_mode": load_mode,
                                         "load_mode_proposed": load_mode, "confidence": "high", "avoid": None}
        write_json(self.root / "data" / "exercises.json", doc)

    def log(self, *workouts):
        with (self.root / LOG).open("a", encoding="utf-8") as handle:
            for workout in workouts:
                handle.write(json.dumps(workout) + "\n")
        self.coach("history", "sync")

    def nutrition_readings(self, *readings):
        if readings:
            write_json(self.root / READINGS, {"schema_version": 1, "readings": list(readings)})
        else:
            (self.root / READINGS).unlink()

    def e1rm(self):
        return self.coach("stats", "e1rm")["data"]


class SplitSquatTest(NoHevyCase):
    """Split squat 2.5/hand × 10 @ 9, then 5/hand × 8 prescribed: the dumbbells are a small share of the mass moved."""

    def setUp(self):
        super().setUp()
        self.log(manual_workout("2026-10-08", "session-b", "db_bulgarian_split_squat", "per_hand_x2",
                                [(2.5, 10, 9)] * 3))

    def prescribe(self, per_hand):
        doc = read_json(self.root / OVERLAY)
        doc["approval"] = None
        line = next(e for e in doc["sessions"][0]["exercises"] if e["exercise_id"] == "db_bench_press")
        line.update(exercise_id="db_bulgarian_split_squat", hevy_template_id=None, change=None,
                    sets=working(8, 8, per_hand))
        write_json(self.root / OVERLAY, doc)
        flags = self.coach("prescription", "check", "--overlay", "2026-10-12-weekly")["data"]["flags"]
        return [f for f in flags if f["exercise_id"] == "db_bulgarian_split_squat"]

    def test_the_next_step_gets_no_model_block(self):
        found = self.prescribe(5)
        self.assertEqual(found, [])

    def test_the_estimate_is_unavailable_and_the_observation_is_kept(self):
        data = self.e1rm()
        self.assertNotIn("db_bulgarian_split_squat", data["series"])
        self.assertNotIn("db_bulgarian_split_squat", data["best"])
        gone = data["unavailable"]["db_bulgarian_split_squat"]
        self.assertEqual((gone["reason"], gone["date"]), ("unsupported_exercise", "2026-10-08"))
        self.assertIn("body mass", gone["message"])
        self.assertEqual([(s["load"], s["reps"], s["rpe"]) for s in gone["sets"]], [(2.5, 10, 9)] * 3)
        observed = data["observations"]["db_bulgarian_split_squat"][-1]
        self.assertEqual(observed["reason"], "unsupported_exercise")
        self.assertEqual({s["reason"] for s in observed["sets"]}, {"unsupported_exercise"})
        self.assertEqual([(s["load"], s["e1rm"]) for s in observed["sets"]], [(2.5, None)] * 3)

    def test_the_load_step_guard_still_applies(self):
        found = self.prescribe(10)
        self.assertEqual([f["code"] for f in found], ["unearned_load"])
        self.assertIn("no e1RM to judge it by (body mass dominates this movement)", found[0]["message"])
        self.assertNotIn("implies RPE", found[0]["message"])

    def test_the_catalogue_marks_single_leg_dumbbell_squats_unsupported(self):
        unsupported = {e["id"] for e in library.catalogue() if not library.e1rm_supported(e["id"])}
        self.assertEqual(unsupported, {"db_bulgarian_split_squat", "db_lunge", "db_walking_lunge", "db_step_up"})
        self.assertTrue(library.e1rm_supported("bb_back_squat"))
        self.assertTrue(library.e1rm_supported("custom_anything"))

    def test_only_dumbbell_variants_lose_the_e1rm(self):
        unsupported = [e for e in library.catalogue() if not library.e1rm_supported(e["id"])]
        self.assertEqual({e["equipment"] for e in unsupported}, {"dumbbell"})
        self.assertTrue(library.e1rm_supported("split_squat"))
        self.assertTrue(library.e1rm_supported("bw_step_up"))

    def test_a_bodyweight_split_squat_keeps_a_total_system_e1rm(self):
        self.confirm("split_squat", "bodyweight")
        self.nutrition_readings(reading("2026-10-07", 80))
        self.log(manual_workout("2026-10-08", "session-b", "split_squat", "bodyweight", [(0, 10, 8)]))
        data = self.e1rm()
        point = data["series"]["split_squat"][0]
        self.assertEqual((point["load"], point["basis"]), (80, "total_system"))
        self.assertNotIn("split_squat", data["unavailable"])


class TotalSystemTest(NoHevyCase):
    """Pull-up 0 × 8 @ 8 with an 80 kg nutrition reading, Hevy off."""

    def setUp(self):
        super().setUp()
        self.log(manual_workout("2026-10-08", "session-b", "pull_up", "bodyweight", [(0, 8, 8)]))

    def pull_up(self, data=None):
        return (data or self.e1rm())["series"]["pull_up"][0]

    def test_a_manual_nutrition_reading_gives_the_total_system_estimate(self):
        self.nutrition_readings(reading("2026-10-08", 80))
        point = self.pull_up()
        self.assertEqual((point["e1rm"], point["load"], point["basis"]), (106.67, 80, "total_system"))
        self.assertEqual(point["bodyweight"], {"value": 80, "date": "2026-10-08", "source": "nutrition"})

    def test_a_lb_nutrition_reading_is_converted_to_load_units(self):
        self.nutrition_readings(reading("2026-10-08", 176.3698, unit="lb"))
        self.assertEqual(self.pull_up()["e1rm"], 106.67)

    def test_a_scale_weight_stands_in_for_a_missing_trend_weight(self):
        scale = dict(reading("2026-10-08", None), source="scale", scale_weight=80)
        self.nutrition_readings(scale)
        self.assertEqual(self.pull_up()["e1rm"], 106.67)

    def test_a_recorded_weigh_in_wins_over_a_same_day_nutrition_reading(self):
        self.nutrition_readings(reading("2026-10-08", 82))
        self.coach("bodyweight", "record", "--date", "2026-10-08", "--weight", "80")
        point = self.pull_up()
        self.assertEqual(point["e1rm"], 106.67)
        self.assertEqual(point["bodyweight"], {"value": 80, "date": "2026-10-08", "source": "wellness"})

    def test_load_lifts_keep_the_load_basis(self):
        self.nutrition_readings(reading("2026-10-08", 80))
        squat = self.e1rm()["series"]["bb_back_squat"][-1]
        self.assertEqual((squat["basis"], squat["bodyweight"]), ("load", None))

    def test_no_nutrition_reading_within_14_days_gives_a_reason_not_a_number(self):
        for readings in ([reading("2026-09-23", 80)], []):
            with self.subTest(readings=readings):
                self.nutrition_readings(*readings)
                data = self.e1rm()
                self.assertNotIn("pull_up", data["series"])
                gone = data["unavailable"]["pull_up"]
                self.assertEqual((gone["reason"], gone["date"]), ("no_bodyweight_reading", "2026-10-08"))
                self.assertIn("14 days", gone["message"])
                self.assertIn("a total-system e1RM counts body mass", gone["message"])
                self.assertEqual([(s["load"], s["reps"], s["rpe"]) for s in gone["sets"]], [(0, 8, 8)])
                self.assertEqual(data["observations"]["pull_up"][-1]["reason"], gone["reason"])

    def test_a_nutrition_reading_after_as_of_is_not_used(self):
        self.nutrition_readings(reading("2026-10-10", 80))
        before = stats.e1rm_series(self.root, as_of=datetime(2026, 10, 9, 20, tzinfo=timezone.utc))
        self.assertNotIn("pull_up", before["series"])
        self.assertEqual(before["unavailable"]["pull_up"]["reason"], "no_bodyweight_reading")
        after = stats.e1rm_series(self.root, as_of=datetime(2026, 10, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(self.pull_up(after)["bodyweight"]["date"], "2026-10-10")

    def test_an_assisted_estimate_names_its_basis(self):
        self.nutrition_readings(reading("2026-10-08", 80))
        self.log(manual_workout("2026-10-09", "session-a", "assisted_pull_up", "assisted", [(20, 8, 8)]))
        point = self.e1rm()["series"]["assisted_pull_up"][0]
        self.assertEqual((point["e1rm"], point["load"], point["basis"]), (80, 60, "total_system"))
        progress = self.coach("pages", "show", "progress")["data"]["text"]
        row = next(line for line in progress.splitlines() if line.startswith("| Assisted Pull Up"))
        self.assertIn(f"80 {TOTAL_SYSTEM_TEXT}", row)

    def test_an_assisted_estimate_without_a_reading_says_why_in_glossary_words(self):
        self.nutrition_readings()
        self.log(manual_workout("2026-10-09", "session-a", "assisted_pull_up", "assisted", [(20, 8, 8)]))
        gone = self.e1rm()["unavailable"]["assisted_pull_up"]
        self.assertEqual(gone["reason"], "no_bodyweight_reading")
        self.assertIn("no e1RM on 2026-10-09: a total-system e1RM counts body mass", gone["message"])
        self.assertNotIn("assisted e1RM", gone["message"])

    def test_every_human_display_labels_the_total_system_estimate(self):
        self.nutrition_readings(reading("2026-10-08", 80))
        progress = self.coach("pages", "show", "progress")["data"]["text"]
        row = next(line for line in progress.splitlines() if line.startswith("| Pull Up"))
        self.assertIn(f"106.67 {TOTAL_SYSTEM_TEXT}", row)
        dashboard = self.coach("pages", "show", "dashboard")["data"]["text"]
        self.assertIn(f"Pull Up 106.67 kg {TOTAL_SYSTEM_TEXT}", dashboard)
        shutil.copy(CHECKIN_RECORD, self.root / "check-ins" / CHECKIN_RECORD.name)
        prepared = self.coach("checkin", "prepare")["data"]
        row = next(r for r in prepared["card"]["e1rm"] if r["exercise_id"] == "pull_up")
        self.assertEqual(row["basis"], "total_system")
        self.assertIn(f"Pull Up 106.67 {TOTAL_SYSTEM_TEXT}", prepared["text"])
        self.assertNotIn(f"Back Squat (Barbell) 121.88 {TOTAL_SYSTEM_TEXT}", prepared["text"])


class PriorityKpiTest(NoHevyCase):
    def set_priority(self, exercise_id, swap=None):
        def change(doc):
            if swap:
                line = next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == swap)
                line["exercise_id"] = exercise_id
            doc["priority"] = [{"exercise_id": exercise_id, "kpi": {"kind": "e1rm", "target": 110, "by": None},
                                "floor": {"sets": 2, "rpe": None}}]
        doc = read_json(self.root / "data" / "program.json")
        change(doc)
        write_json(self.root / "data" / "program.json", doc)

    def kpi(self, exercise_id):
        lifts = self.coach("structure", "priority", "--since", "2026-09-28")["data"]["lifts"]
        return next(lift["kpi"] for lift in lifts if lift["exercise_id"] == exercise_id)

    def test_an_unsupported_e1rm_kpi_gets_an_actionable_warning(self):
        self.set_priority("db_bulgarian_split_squat", swap="db_bench_press")
        warnings = self.coach("program", "validate")["warnings"]
        found = [w for w in warnings if w.startswith(f"{program.PRIORITY_E1RM_UNSUPPORTED}: ")]
        self.assertEqual(len(found), 1, warnings)
        for text in ("db_bulgarian_split_squat", "top_load", "top_reps"):
            self.assertIn(text, found[0])

    def test_the_unsupported_warning_replaces_the_rep_cap_one(self):
        self.set_priority("db_bulgarian_split_squat", swap="db_bench_press")
        doc = read_json(self.root / "data" / "program.json")
        line = next(e for s in doc["sessions"] for e in s["exercises"]
                    if e["exercise_id"] == "db_bulgarian_split_squat")
        line["sets"] = [{"count": 3, "type": "normal", "rep_range": {"start": 20, "end": 25}, "rpe": 7}]
        write_json(self.root / "data" / "program.json", doc)
        codes = [w.split(":")[0] for w in self.coach("program", "validate")["warnings"]]
        self.assertIn(program.PRIORITY_E1RM_UNSUPPORTED, codes)
        self.assertNotIn(program.PRIORITY_NO_E1RM_WARNING, codes)

    def test_a_supported_e1rm_kpi_gets_no_warning(self):
        self.set_priority("pull_up")
        warnings = self.coach("program", "validate").get("warnings", [])
        self.assertEqual([w for w in warnings if w.startswith(program.PRIORITY_E1RM_UNSUPPORTED)], [])

    def test_the_program_page_names_the_kpi_basis(self):
        page = program.PROGRAM_PAGE
        self.set_priority("pull_up")
        self.assertIn(f"Pull Up: KPI e1RM ({TOTAL_SYSTEM_TEXT})", program.render_all(self.root)[page])
        self.set_priority("db_bulgarian_split_squat", swap="db_bench_press")
        self.assertIn("Bulgarian Split Squat (Dumbbell): KPI e1RM (unavailable: body mass dominates this movement)",
                      program.render_all(self.root)[page])

    def test_an_unsupported_kpi_says_why_it_has_no_value(self):
        self.set_priority("db_bulgarian_split_squat", swap="db_bench_press")
        self.log(manual_workout("2026-10-08", "session-a", "db_bulgarian_split_squat", "per_hand_x2",
                                [(2, 10, 9)]))
        kpi = self.kpi("db_bulgarian_split_squat")
        self.assertIsNone(kpi["now"])
        self.assertEqual(kpi["unavailable"]["reason"], "unsupported_exercise")

    def test_a_missing_nutrition_reading_kpi_says_why_and_a_present_one_names_its_basis(self):
        self.set_priority("pull_up")
        self.log(manual_workout("2026-10-08", "session-b", "pull_up", "bodyweight", [(0, 8, 8)]))
        self.nutrition_readings()
        kpi = self.kpi("pull_up")
        self.assertIsNone(kpi["now"])
        self.assertEqual(kpi["unavailable"]["reason"], "no_bodyweight_reading")
        self.nutrition_readings(reading("2026-10-08", 80))
        kpi = self.kpi("pull_up")
        self.assertEqual((kpi["now"]["value"], kpi["now"]["basis"]), (106.67, "total_system"))
        self.assertIsNone(kpi["unavailable"])


class E1rmSchemeTest(unittest.TestCase):
    """A scheme that loads from an e1RM holds an unsupported lift and names body mass as the reason."""

    def test_rpe_anchored_makes_no_estimate_from_the_logged_top_set(self):
        logged = exposure(SESSION_DAY, [(10, 10, 9)] * 3, exercise=SPLIT_SQUAT)
        proposal = run(context("rpe_anchored", exposures=[logged], exercise=SPLIT_SQUAT, sets=TEN_AT_EIGHT))
        self.assertEqual(loads_and_reps(proposal)[0], (10, 10))
        self.assertIn(BODY_MASS_REASON, proposal.rationale)
        self.assertNotIn("e1RM of", proposal.rationale)
        self.assertNotIn("provisional", proposal.rationale)

    def test_fixed_reps_rpe_says_why_the_load_holds(self):
        logged = exposure(SESSION_DAY, [(10, 10, 6)] * 3, exercise=SPLIT_SQUAT)
        proposal = run(context("fixed_reps_rpe", exposures=[logged], exercise=SPLIT_SQUAT, sets=TEN_AT_EIGHT))
        self.assertEqual(loads_and_reps(proposal), [(10, 10)] * 3)
        self.assertIn(BODY_MASS_REASON, proposal.rationale)
        self.assertNotIn("42 days", proposal.rationale)

    def test_wave_531_without_a_training_max_says_why_it_holds(self):
        proposal = run(context("wave_531", exercise=SPLIT_SQUAT, sets=TEN_AT_EIGHT, start_load=10))
        self.assertIn(BODY_MASS_REASON, proposal.rationale)


class E1rmSchemeProgramTest(NoHevyCase):
    """Split squat on an e1RM scheme in session A, logged 10/hand × 10."""

    def use_scheme(self, name):
        doc = read_json(self.root / "data" / "program.json")
        line = next(e for s in doc["sessions"] for e in s["exercises"]
                    if e["exercise_id"] in ("db_bench_press", "db_bulgarian_split_squat"))
        line.update(exercise_id="db_bulgarian_split_squat", scheme={"name": name, "params": {}},
                    sets=[{"count": 3, "type": "normal", "reps": 10, "rpe": 8}])
        write_json(self.root / "data" / "program.json", doc)

    def test_each_e1rm_scheme_holds_the_load_and_validate_warns(self):
        self.log(manual_workout("2026-10-08", "session-a", "db_bulgarian_split_squat", "per_hand_x2",
                                [(10, 10, 9)] * 3))
        for name in ("fixed_reps_rpe", "rpe_anchored"):
            with self.subTest(scheme=name):
                self.use_scheme(name)
                warnings = self.coach("program", "validate")["warnings"]
                found = [w for w in warnings if w.startswith(f"{program.E1RM_SCHEME_UNSUPPORTED}: ")]
                self.assertEqual(len(found), 1, warnings)
                for text in ("db_bulgarian_split_squat", "session-a", name, "double_progression"):
                    self.assertIn(text, found[0])
                overlay = self.coach("propose", "week", "--week", "2026-W42", "--dry-run")["data"]["overlay"]
                line = next(e for s in overlay["sessions"] for e in s["exercises"]
                            if e["exercise_id"] == "db_bulgarian_split_squat")
                top = [s["load"]["per_hand"] for s in line["sets"] if s["type"] == "normal"]
                self.assertEqual(top[0], 10)
                self.assertIn(BODY_MASS_REASON, line["provenance"]["rationale"])

    def test_double_progression_on_an_unsupported_lift_gets_no_warning(self):
        self.use_scheme("double_progression")
        warnings = self.coach("program", "validate").get("warnings", [])
        self.assertEqual([w for w in warnings if w.startswith(program.E1RM_SCHEME_UNSUPPORTED)], [])

    def test_a_wave_with_its_own_training_max_gets_no_warning(self):
        doc = read_json(self.root / "data" / "program.json")
        line = next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == "db_bench_press")
        line.update(exercise_id="db_bulgarian_split_squat", scheme={"name": "wave_531", "params": {"training_max": 20}})
        self.assertEqual([w for w in program.warnings(doc) if w.startswith(program.E1RM_SCHEME_UNSUPPORTED)], [])
        line["scheme"]["params"] = {}
        self.assertEqual(len([w for w in program.warnings(doc) if w.startswith(program.E1RM_SCHEME_UNSUPPORTED)]), 1)


if __name__ == "__main__":
    unittest.main()
