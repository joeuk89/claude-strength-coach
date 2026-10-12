"""Fatigue trigger evidence: comparable drift, dated niggle flares, measured sleep and recovery ceilings (C43)."""

import json
import unittest

from coach import checkin, dates, overlay, patterns
from coach.activity import records
from coach.plugins.base import LoggedSet, SetSpec
from tests.support import INSTANCES
from tests.support.history import log_at_prescription, prescribe_fixture_history, read_json, write_json
from tests.support.skills import step_text
from tests.test_activity_store import wellness
from tests.test_block import NOW, BlockCase, codes

SQUAT, BENCH = "bb_back_squat", "db_bench_press"
DRIFT_DAYS = ("2026-09-28", "2026-10-05")
EARLIER_SQUATS = ("2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21")
WELLNESS = ".coach/activity/wellness.jsonl"


def total(kg):
    return {"mode": "total", "unit": "kg", "per_hand": None, "hevy_total": kg, "hevy_kg": kg}


def logged(rpe, load=95, reps=5, kind="normal"):
    return LoggedSet(index=0, type=kind, reps=reps, rpe=rpe, load=load)


def target(rpe=7, load=95, reps=5, rep_range=None):
    return SetSpec(reps=reps, rep_range=rep_range, rpe=rpe, load=load)


class DriftReadingTest(unittest.TestCase):
    def test_sets_at_the_prescription_drift_on_two_over_target(self):
        reading = patterns.drift_reading([logged(8), logged(8), logged(7)], [target()] * 3, load_mode="total")
        self.assertEqual((reading.compared, reading.over, reading.set_aside), (3, (1, 2), ()))
        self.assertTrue(reading.drifted)

    def test_heavier_extra_and_longer_sets_are_set_aside(self):
        sets = [logged(8.5), logged(8.5, load=105), logged(8.5, reps=8), logged(9), logged(9)]
        reading = patterns.drift_reading(sets, [target()] * 3, load_mode="total")
        self.assertEqual(reading.over, (1,))
        self.assertEqual(reading.set_aside, ((2, "heavier"), (3, "more_reps"), (4, "extra"), (5, "extra")))
        self.assertFalse(reading.drifted)
        self.assertFalse(reading.steady)

    def test_a_missing_target_load_or_rpe_proves_nothing(self):
        prescribed = [target(rpe=None), target(load=None), target()]
        reading = patterns.drift_reading([logged(9), logged(9), logged(None)], prescribed, load_mode="total")
        self.assertEqual(reading.set_aside, ((1, "no_target"), (2, "no_load"), (3, "no_rpe")))
        self.assertEqual(reading.compared, 0)

    def test_less_assistance_is_harder_and_a_range_top_bounds_the_reps(self):
        assisted = [target(load=20)] * 2
        reading = patterns.drift_reading([logged(8, load=10), logged(8, load=25)], assisted, load_mode="assisted")
        self.assertEqual(reading.set_aside, ((1, "heavier"),))
        ranged = [target(rpe=8, reps=None, rep_range=(8, 10), load=25)] * 2
        reading = patterns.drift_reading([logged(9, load=25, reps=10), logged(9, load=25, reps=11)], ranged,
                                         load_mode="per_hand_x2")
        self.assertEqual((reading.over, reading.set_aside), ((1,), ((2, "more_reps"),)))

    def test_lighter_or_short_sets_can_show_drift_but_never_steadiness(self):
        lighter = patterns.drift_reading([logged(7, load=40)] * 3, [target()] * 3, load_mode="total")
        self.assertEqual((lighter.compared, lighter.below), (3, ((1, "lighter"), (2, "lighter"), (3, "lighter"))))
        self.assertFalse(lighter.steady)
        short = patterns.drift_reading([logged(7, reps=3)] * 3, [target()] * 3, load_mode="total")
        self.assertEqual(short.below, ((1, "fewer_reps"), (2, "fewer_reps"), (3, "fewer_reps")))
        self.assertFalse(short.steady)
        self.assertTrue(patterns.drift_reading([logged(8.5, load=40)] * 2, [target()] * 2, load_mode="total").drifted)
        mixed = patterns.drift_reading([logged(7), logged(7), logged(7, load=90)], [target()] * 3, load_mode="total")
        self.assertEqual(mixed.below, ((3, "lighter"),))
        self.assertTrue(mixed.steady)

    def test_more_assistance_or_a_range_bottom_missed_is_below_the_prescription(self):
        assisted = patterns.drift_reading([logged(7, load=30)] * 2, [target(load=20)] * 2, load_mode="assisted")
        self.assertEqual(assisted.below, ((1, "lighter"), (2, "lighter")))
        ranged = [target(reps=None, rep_range=(8, 10), load=25)] * 2
        reading = patterns.drift_reading([logged(7, load=25, reps=8), logged(7, load=25, reps=7)], ranged,
                                         load_mode="per_hand_x2")
        self.assertEqual(reading.below, ((2, "fewer_reps"),))

    def test_a_recovery_cap_lowers_the_target(self):
        self.assertTrue(patterns.rpe_drift([logged(7)] * 2, [target(rpe=8)] * 2, capped=6, load_mode="total"))


class FatigueCase(BlockCase):
    def set_sets(self, day, exercise_id, change):
        def edit(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == exercise_id:
                    for position, set_ in enumerate(exercise["sets"], start=1):
                        change(position, set_)
        self.edit_workout(day, edit)

    def add_sets(self, day, exercise_id, rpe, count=2):
        def edit(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == exercise_id:
                    last = exercise["sets"][-1]
                    for _ in range(count):
                        exercise["sets"].append(dict(last, index=len(exercise["sets"]), rpe=rpe))
        self.edit_workout(day, edit)

    def drop_squats(self, days):
        for day in days:
            self.edit_workout(day, lambda w: w.update(
                exercises=[e for e in w["exercises"] if e["exercise_id"] != SQUAT]))

    def drift_squat(self, days=DRIFT_DAYS, rpe=8.5):
        for day in days:
            self.set_rpe(day, SQUAT, rpe)

    def lift(self, data, exercise_id=SQUAT, week=-1):
        return next((lift for lift in data["reviews"][week]["fatigue"]["rpe_drift"]
                     if lift["exercise_id"] == exercise_id), None)


class ComparableDriftTest(FatigueCase):
    def setUp(self):
        super().setUp()
        prescribe_fixture_history(self.root)
        log_at_prescription(self.root, (SQUAT, BENCH))

    def test_two_first_ever_over_target_exposures_are_calibration_not_drift(self):
        self.drop_squats(EARLIER_SQUATS)
        self.drift_squat()
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        lift = self.lift(data)
        self.assertEqual((lift["status"], lift["baseline"]), ("calibration", None))
        self.assertEqual([e["date"] for e in lift["exposures"]], ["2026-10-05", "2026-09-28"])
        calibration = [f for f in data["flags"] if f["code"] == "drift_calibration"]
        self.assertEqual(len(calibration), 1)
        self.assertIn("28 Sep and 5 Oct", calibration[0]["message"])
        self.assertIn("calibration, not fatigue drift", calibration[0]["message"])

    def test_three_over_target_exposures_still_have_no_baseline(self):
        self.drop_squats(EARLIER_SQUATS[:-1])
        self.drift_squat(("2026-09-21",) + DRIFT_DAYS)
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        self.assertEqual(self.lift(data)["status"], "calibration")

    def test_an_earlier_steady_exposure_then_two_drifting_ones_trigger(self):
        self.drift_squat()
        data = self.close()
        self.assertIn("rpe_drift", data["weeks"][-1]["triggers"])
        lift = self.lift(data)
        self.assertEqual(lift["status"], "drift")
        self.assertEqual(lift["baseline"]["date"], "2026-09-21")
        self.assertEqual([(e["date"], e["verdict"], e["over_sets"]) for e in lift["exposures"]],
                         [("2026-10-05", "drift", [1, 2, 3]), ("2026-09-28", "drift", [1, 2, 3])])
        self.assertNotIn("drift_calibration", codes(data))

    def test_an_earlier_exposure_below_the_prescription_is_no_baseline(self):
        self.drop_squats(EARLIER_SQUATS[:-1])
        self.drift_squat()
        for change in (lambda n, s: s.update(rpe=7, load=total(40)), lambda n, s: s.update(rpe=7, reps=3)):
            with self.subTest(change=change):
                self.set_sets("2026-09-21", SQUAT, change)
                data = self.close()
                self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
                lift = self.lift(data)
                self.assertEqual((lift["status"], lift["baseline"]), ("calibration", None))
                self.set_sets("2026-09-21", SQUAT, lambda n, s: s.update(load=total(100), reps=5))

    def test_sets_logged_heavier_than_prescribed_do_not_prove_drift(self):
        for day in DRIFT_DAYS:
            self.set_sets(day, SQUAT, lambda n, s: s.update(rpe=8.5, load=total(105)) if n > 1 else None)
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        lift = self.lift(data)
        self.assertEqual(lift["status"], "not_counted")
        self.assertEqual(lift["exposures"][0]["set_aside"],
                         [{"set": 2, "reason": "heavier"}, {"set": 3, "reason": "heavier"}])

    def test_extra_sets_and_extra_reps_do_not_prove_drift(self):
        for day in DRIFT_DAYS:
            self.add_sets(day, SQUAT, 9)
        self.assertNotIn("rpe_drift", self.close()["weeks"][-1]["triggers"])
        for day in DRIFT_DAYS:
            self.set_sets(day, SQUAT, lambda n, s: s.update(rpe=8.5, reps=8))
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        self.assertEqual({a["reason"] for a in self.lift(data)["exposures"][0]["set_aside"]}, {"more_reps", "extra"})

    def test_an_unmatched_session_does_not_prove_drift_even_under_a_cap(self):
        self.edit("data/program.json", lambda doc: doc["sessions"][0]["exercises"][0].update(
            constraints=[{"kind": "rpe_cap", "value": 8, "reason": "left knee"}]))
        self.drift_squat(rpe=9)
        for day in DRIFT_DAYS:
            self.edit_workout(day, lambda w: w.update(overlay_id=None))
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        lift = self.lift(data)
        self.assertEqual(lift["status"], "not_counted")
        self.assertEqual([e["why"] for e in lift["exposures"]], ["no_prescription", "no_prescription"])

    def test_matched_drift_on_another_lift_still_counts(self):
        for day in DRIFT_DAYS:
            self.set_sets(day, SQUAT, lambda n, s: s.update(rpe=8.5, load=total(105)))
            self.set_rpe(day, BENCH, 9.5)
        data = self.close()
        self.assertIn("rpe_drift", data["weeks"][-1]["triggers"])
        self.assertEqual(self.lift(data, BENCH)["status"], "drift")
        self.assertEqual(self.lift(data)["status"], "not_counted")

    def test_repeated_close_is_idempotent_and_names_its_evidence(self):
        self.init(3)
        self.drift_squat()
        first = self.close("2026-W41", "--readiness", "poor")
        second = self.close("2026-W41", "--readiness", "poor")
        self.assertEqual(first["weeks"], second["weeks"])
        self.assertEqual(first["reviews"][-1]["fatigue"], second["reviews"][-1]["fatigue"])
        evidence = second["reviews"][-1]["fatigue"]
        self.assertEqual(evidence["readiness"], {"value": "poor", "source": "athlete"})
        self.assertEqual(evidence["sleep"]["source"], "none")
        self.assertEqual(self.lift(second)["exposures"][0]["workout_id"], "20000000-0000-4000-8000-000000000151")


class RecoveryWorkTest(FatigueCase):
    def setUp(self):
        super().setUp()
        prescribe_fixture_history(self.root)

    def deload(self, overlay_id):
        path = self.root / "data/overlays" / f"{overlay_id}.json"
        doc = read_json(path)
        doc.pop("approval")
        doc["kind"] = "deload"
        write_json(path, overlay.approve(doc, dates.parse_timestamp(doc["created_at"])))

    def test_deload_work_is_left_out_of_drift_but_its_ceiling_breach_is_raised(self):
        self.deload("2026-10-05-weekly")
        self.drift_squat()
        data = self.close()
        self.assertNotIn("rpe_drift", data["weeks"][-1]["triggers"])
        newest = self.lift(data)["exposures"][0]
        self.assertEqual((newest["intent"], newest["why"]), ("deload", "deload"))
        breach = [b for b in data["reviews"][-1]["recovery_ceilings"] if b["exercise_id"] == SQUAT]
        self.assertEqual(breach[0]["sets"][0], {"set": 1, "rpe": 8.5, "ceiling": 7})
        flag = next(f for f in data["flags"] if f["code"] == "recovery_ceiling_exceeded")
        self.assertEqual((flag["severity"], flag["exercise_id"]), ("warn", SQUAT))
        self.assertIn("deload work", flag["message"])
        self.assertIn("not a fatigue trigger", flag["message"])

    def test_an_rpe_cap_breach_is_raised_on_an_ordinary_week(self):
        def cap(doc):
            for session in doc["sessions"]:
                for line in session["exercises"]:
                    if line["exercise_id"] == SQUAT:
                        line["constraints"] = [{"kind": "rpe_cap", "value": 6, "reason": "left knee"}]
        self.edit("data/program.json", cap)
        data = self.close()
        flag = next(f for f in data["flags"] if f["code"] == "recovery_ceiling_exceeded"
                    and f["message"].startswith("2026-10-05 session-a"))
        self.assertIn("RPE cap 6 (left knee)", flag["message"])
        self.assertIn("set 1 at RPE 7 (ceiling 6)", flag["message"])


class NiggleHistoryTest(FatigueCase):
    def niggle(self, *steps):
        """(date, status) steps: the first adds the niggle, the rest update it, each on its own day."""
        (day, status), rest = steps[0], steps[1:]
        self.data("niggles", "add", "--area", "left knee", "--status", status, "--pattern", "squat",
                  now=f"{day}T09:00:00Z")
        for day, status in rest:
            self.data("niggles", "update", "n-0001", "--status", status, now=f"{day}T09:00:00Z")

    def test_a_flare_that_settled_before_sunday_still_fires(self):
        self.init(1)
        self.niggle(("2026-10-01", "watching"), ("2026-10-06", "aggravated"), ("2026-10-09", "watching"))
        data = self.close()
        self.assertIn("niggle", data["weeks"][-1]["triggers"])
        flare, = data["reviews"][-1]["fatigue"]["niggle"]
        self.assertEqual((flare["aggravated_on"], flare["aggravated_since"], flare["status_now"]),
                         (["2026-10-06"], None, "watching"))
        self.assertIn("left knee (aggravated 6 Oct)", next(f["message"] for f in data["flags"]
                                                           if f["code"] == "fatigue_watch"))

    def test_reclosing_after_resolution_keeps_the_trigger_and_the_agreed_light_week(self):
        self.init(3)
        self.niggle(("2026-10-01", "watching"), ("2026-10-06", "aggravated"), ("2026-10-09", "watching"))
        data = self.close("2026-W41", "--readiness", "poor")
        self.assertEqual(data["weeks"][-1]["triggers"], ["readiness", "niggle"])
        self.data("block", "decide", "--outcome", "adopted")
        self.data("niggles", "resolve", "n-0001")
        data = self.close("2026-W41", "--readiness", "poor")
        self.assertEqual(data["weeks"][-1]["triggers"], ["readiness", "niggle"])
        self.assertEqual(data["block"]["light_week"]["status"], "agreed")

    def test_a_flare_wholly_before_the_week_does_not_count(self):
        self.niggle(("2026-09-29", "aggravated"), ("2026-10-02", "watching"))
        data = self.close()
        self.assertNotIn("niggle", data["weeks"][-1]["triggers"])
        self.assertIn("niggle", data["weeks"][-2]["triggers"])

    def test_a_flare_after_the_week_does_not_fire_it(self):
        self.niggle(("2026-10-01", "watching"), ("2026-10-13", "aggravated"))
        data = self.close("2026-W41", now="2026-10-14T09:00:00Z")
        self.assertNotIn("niggle", data["weeks"][-1]["triggers"])
        self.assertEqual(data["reviews"][-1]["fatigue"]["niggle"], [])

    def test_a_late_check_in_dates_an_in_week_flare_to_when_it_happened(self):
        self.niggle(("2026-10-01", "watching"))
        monday = "2026-10-12T09:00:00Z"
        self.data("niggles", "update", "n-0001", "--status", "aggravated", "--date", "2026-10-08", now=monday)
        self.data("niggles", "update", "n-0001", "--status", "watching", "--mention", now=monday)
        data = self.close("2026-W41", now=monday)
        self.assertIn("niggle", data["weeks"][-1]["triggers"])
        flare, = data["reviews"][-1]["fatigue"]["niggle"]
        self.assertEqual((flare["aggravated_on"], flare["status_now"]), (["2026-10-08"], "watching"))

    def test_a_report_date_is_not_in_the_future_or_before_the_newest_entry(self):
        self.niggle(("2026-10-05", "watching"))
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--date", "2026-10-12", expect=1)
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--date", "2026-10-04", expect=1)
        self.coach("niggles", "add", "--area", "elbow", "--date", "2026-10-12", expect=1)
        row = self.data("niggles", "add", "--area", "elbow", "--status", "aggravated", "--date", "2026-10-07")["niggle"]
        self.assertEqual((row["first_noted"], row["history"][0]["date"]), ("2026-10-07", "2026-10-07"))

    def test_the_check_in_dates_a_report_of_an_earlier_flare(self):
        act = " ".join(step_text("check-in", "act.md").split())
        self.assertIn("--date <that day>", act)
        self.assertIn("only when dated inside that week", act)

    def test_a_flare_persisting_into_the_week_counts(self):
        self.niggle(("2026-10-02", "aggravated"))
        flare, = self.close()["reviews"][-1]["fatigue"]["niggle"]
        self.assertEqual((flare["aggravated_on"], flare["aggravated_since"]), ([], "2026-10-02"))


class MeasuredSleepTest(FatigueCase):
    base = INSTANCES / "cardio"

    def nights(self, hours, source, days=None):
        (self.root / WELLNESS).unlink(missing_ok=True)
        for day in (days or [f"2026-10-{d:02d}" for d in range(5, 12)]):
            if source == "manual":
                self.data("wellness", "add", "--date", day, "--sleep-hours", str(hours))
            else:
                records.append_lines(self.root / WELLNESS, [wellness(f"{source}:{day}", day, asleep=hours)])

    def sleep(self, *extra):
        week = self.close("2026-W41", *extra)
        return week["weeks"][-1]["signals"], week["reviews"][-1]["fatigue"]["sleep"]

    def test_a_diary_and_a_tracker_give_the_same_poor_sleep(self):
        for source in ("manual", "apple_health"):
            with self.subTest(source=source):
                self.nights(6.4, source)
                signals, evidence = self.sleep()
                self.assertEqual((signals["sleep"], signals["sleep_source"]), ("poor", "sleep_debt"))
                self.assertEqual(evidence["measured"]["short_nights"], 7)
                self.assertEqual({n["source"] for n in evidence["measured"]["nightly"]}, {source})

    def test_feeling_fine_is_readiness_and_does_not_clear_measured_sleep(self):
        self.nights(6.4, "manual")
        signals, _ = self.sleep("--readiness", "ok")
        self.assertEqual((signals["readiness"], signals["sleep"]), ("ok", "poor"))
        envelope = self.coach("block", "close", "--week", "2026-W41", "--sleep", "ok", expect=1)
        self.assertIn("--sleep-reason", json.dumps(envelope))

    def test_an_override_keeps_its_reason_and_the_measured_nights(self):
        self.nights(6.4, "manual")
        signals, evidence = self.sleep("--sleep", "ok", "--sleep-reason", "diary hours were time in bed")
        self.assertEqual((signals["sleep"], signals["sleep_source"], signals["sleep_reason"]),
                         ("ok", "override", "diary hours were time in bed"))
        self.assertEqual((evidence["reason"], evidence["measured"]["value"]),
                         ("diary hours were time in bed", "poor"))

    def test_the_check_in_asks_for_and_enters_nightly_hours(self):
        self.assertIn("hours asleep each night", checkin.SLEEP_ASK)
        analyze = " ".join(step_text("check-in", "analyze.md").split())
        self.assertIn("wellness add --date <night> --sleep-hours <h>", analyze)
        self.assertIn("`[activity]` off: `reference/nutrition-sleep.md`", analyze)

    def test_too_few_nights_or_a_period_mean_stay_unknown(self):
        self.nights(6.4, "manual", days=["2026-10-09", "2026-10-10", "2026-10-11"])
        signals, evidence = self.sleep()
        self.assertEqual((signals["sleep"], signals["sleep_source"]), ("unknown", "none"))
        self.assertIn("3 nights", evidence["measured"]["why"])
        (self.root / WELLNESS).unlink()
        self.data("wellness", "add", "--from", "2026-10-05", "--to", "2026-10-11", "--sleep-hours", "6.4")
        signals, evidence = self.sleep()
        self.assertEqual(signals["sleep"], "unknown")
        self.assertEqual(evidence["measured"]["period_means"], ["manual:2026-10-05..2026-10-11-wellness"])


class RunSpikeTest(FatigueCase):
    base = INSTANCES / "cardio"

    def test_a_spike_asks_for_a_review_and_adds_no_trigger(self):
        spike = next(f for f in self.data("cardio", "flags", "--week", "2026-W41")["flags"]
                      if f["code"] == "run_volume_spike")
        self.assertIn("symptoms", spike["message"])
        self.assertIn("follow-up", spike["message"])
        self.assertIn("not a fatigue trigger", spike["message"])
        week = self.close()["weeks"][-1]
        self.assertEqual(set(week["triggers"]) - {"sleep"}, set())

    def test_the_check_in_reviews_a_spike_and_records_the_action(self):
        act = " ".join(step_text("check-in", "act.md").split())
        self.assertIn("run_volume_spike", act)
        self.assertIn("followups add", act)


class LedgerMigrationTest(BlockCase):
    def test_v2_weeks_gain_a_null_sleep_reason(self):
        closed = {"week": "2026-10-05", "class": "hard", "planned": 3, "trained": 3, "as_prescribed": 3,
                  "on_break": 0, "signals": {"readiness": "ok", "sleep": "ok", "sleep_source": "athlete",
                                             "rpe_drift": False, "niggle": False},
                  "triggers": [], "count_after": 1, "outcome": "none", "deep": False, "closed_at": NOW}
        doc = read_json(self.root / "data/blocks.json")
        doc["schema_version"] = 2
        doc["blocks"][0]["weeks"] = [closed]
        write_json(self.root / "data/blocks.json", doc)
        self.data("migrate", "run")
        migrated = self.ledger()
        self.assertEqual(migrated["schema_version"], 3)
        self.assertEqual(migrated["blocks"][0]["weeks"][0]["signals"]["sleep_source"], "athlete")
        self.assertIsNone(migrated["blocks"][0]["weeks"][0]["signals"]["sleep_reason"])


if __name__ == "__main__":
    unittest.main()
