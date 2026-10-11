"""Derived stats: e1RM, adherence, dose, durations and the convention-jump audit (contract C18)."""

import copy
import unittest

from coach import history, research, stats
from coach.library import Library
from tests.support import INSTANCES, REPO_ROOT, VALID
from tests.support.history import (R_A, W, HistoryCase, fixture_workouts, hevy_exercise, hevy_set, hevy_workout,
                                   read_json, write_json)

LATER = {"COACH_NOW": "2026-10-19T18:00:00Z"}
CONDITIONING_ROUTINE = "00000000-0000-4000-8000-000000000003"


class E1rmFormulaTest(unittest.TestCase):
    def test_epley_with_reps_in_reserve_when_rpe_is_logged(self):
        self.assertAlmostEqual(stats.e1rm(97.5, 5, 7.5), 121.875)
        self.assertAlmostEqual(stats.e1rm(100, 5), 100 * (1 + 5 / 30))

    def test_a_single_at_rpe_10_is_the_load(self):
        self.assertEqual(stats.e1rm(140, 1, 10), 140)

    def test_no_e1rm_past_12_reps_to_failure(self):
        self.assertIsNone(stats.e1rm(60, 12, 9))
        self.assertIsNotNone(stats.e1rm(60, 12, 10))
        self.assertIsNone(stats.e1rm(60, 15))

    def test_load_for_and_implied_rpe_invert_it(self):
        e1rm = stats.e1rm(100, 5, 8)
        self.assertAlmostEqual(stats.load_for(e1rm, 5, 8), 100)
        self.assertAlmostEqual(stats.implied_rpe(e1rm, 100, 5), 8)
        self.assertAlmostEqual(stats.implied_rpe(150, 150, 1), 10)
        self.assertGreater(stats.implied_rpe(100, 110, 5), 10)


class SetWeightsTest(unittest.TestCase):
    def test_primary_counts_one_secondary_half(self):
        entry = Library.load(VALID).get("db_bench_press")
        self.assertEqual(stats.set_weights(entry), {"chest": 1.0, "triceps": 0.5, "front_delts": 0.5})


class CitedThresholdsTest(unittest.TestCase):
    def test_the_e1rm_cap_and_the_hard_set_cut_off_keep_their_values(self):
        self.assertEqual((stats.MAX_REPS_TO_FAILURE, stats.EASY_RPE), (12, 5))

    def test_each_cites_a_heuristic_claim_with_its_sources(self):
        notes = research.load_notes(REPO_ROOT)
        cited = {ref: research.resolve(ref, notes) for ref in stats.CITES}
        self.assertEqual({ref: (claim.basis, claim.sources) for ref, claim in cited.items()}, {
            "rn:autoregulation.5": ("heuristic", ("reynolds-2006", "halperin-2022")),
            "rn:proximity-to-failure.5": ("heuristic", ("robinson-2024", "refalo-2023")),
        })


class E1rmSeriesTest(HistoryCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()

    def test_back_squat_has_two_points(self):
        data = self.coach("stats", "e1rm", "--exercise", "bb_back_squat")["data"]
        series = data["series"]["bb_back_squat"]
        self.assertEqual([p["date"] for p in series], ["2026-09-28", "2026-10-05"])
        latest = series[1]
        self.assertEqual((latest["e1rm"], latest["method"]), (121.88, "epley_rir"))
        self.assertEqual((latest["load"], latest["reps"], latest["rpe"], latest["workout_id"]), (97.5, 5, 7.5, W[3]))
        self.assertEqual(data["best"]["bb_back_squat"], {"e1rm": 121.88, "date": "2026-10-05"})
        self.assertEqual(data["delta"]["bb_back_squat"], 1.55)

    def test_per_hand_lifts_use_the_per_hand_number(self):
        series = self.coach("stats", "e1rm")["data"]["series"]
        self.assertEqual(series["db_bench_press"][0]["load"], 22.5)

    def test_bodyweight_lifts_need_a_weigh_in_within_14_days(self):
        from coach.hevy.cache import HevyCache

        cache = HevyCache(self.root)
        cache.write_collection("body_measurements", [], "2026-10-11T12:00:00Z")
        self.assertNotIn("pull_up", self.coach("stats", "e1rm")["data"]["series"])
        cache.write_collection("body_measurements", [{"date": "2026-10-01", "weight_kg": 80.0, "lean_mass_kg": None,
                                                     "fat_percent": None}], "2026-10-11T12:00:00Z")
        series = self.coach("stats", "e1rm", "--exercise", "pull_up")["data"]["series"]["pull_up"]
        self.assertEqual((series[0]["date"], series[0]["method"], series[0]["load"]), ("2026-10-01", "epley", 80))


class RepairTest(HistoryCase):
    def test_a_repair_changes_e1rm_and_leaves_the_month_file_alone(self):
        def typo(workouts):
            squat = next(w for w in workouts if w["id"] == W[3])["exercises"][0]
            squat["sets"][2].update(weight_kg=105.0, reps=55)

        self.cache(edit=typo)
        self.sync()
        before = self.coach("stats", "e1rm", "--exercise", "bb_back_squat")["data"]["series"]["bb_back_squat"]
        self.assertEqual(before[1]["e1rm"], 121.88)
        self.coach("history", "annotate", "--kind", "repair", "--workout", W[3], "--exercise", "bb_back_squat",
                   "--set", "2", "--field", "reps", "--value", "5", "--reason", "typo: 55")
        after = self.coach("stats", "e1rm", "--exercise", "bb_back_squat")["data"]["series"]["bb_back_squat"]
        self.assertEqual((after[1]["e1rm"], after[1]["set_index"]), (131.25, 2))
        stored = next(w for w in self.month("2026-10")["workouts"] if w["workout_id"] == W[3])
        self.assertEqual(stored["exercises"][0]["sets"][2]["reps"], 55)


    def test_withdrawing_a_repair_with_flags_alone_restores_the_logged_value(self):
        def typo(workouts):
            squat = next(w for w in workouts if w["id"] == W[3])["exercises"][0]
            squat["sets"][2].update(weight_kg=105.0, reps=55)

        self.cache(edit=typo)
        self.sync()
        repair = self.coach("history", "annotate", "--kind", "repair", "--workout", W[3], "--exercise",
                            "bb_back_squat", "--set", "2", "--field", "reps", "--value", "5",
                            "--reason", "typo: 55")["data"]["annotation"]
        withdrawal = self.coach("history", "annotate", "--kind", "repair", "--withdraws", repair["id"],
                                "--reason", "the 55 was real")["data"]["annotation"]
        self.assertNotIn("set_index", withdrawal)
        after = self.coach("stats", "e1rm", "--exercise", "bb_back_squat")["data"]["series"]["bb_back_squat"]
        self.assertEqual(after[1]["e1rm"], 121.88)


def session_a_workout(day="2026-10-12", squat_sets=3):
    return hevy_workout(W[5], R_A, "Session A", day, [
        hevy_exercise(0, "Squat (Barbell)", "F0000001",
                      [hevy_set(0, 60.0, 5, None, "warmup")]
                      + [hevy_set(i + 1, 100.0, 5, 7) for i in range(squat_sets)]),
        hevy_exercise(1, "Bench Press (Dumbbell)", "F0000002", [hevy_set(i, 50.0, 10, 8) for i in range(3)]),
    ])


class AdherenceTest(HistoryCase):
    def setUp(self):
        super().setUp()
        self.env = dict(LATER)

    def adherence(self):
        return self.coach("stats", "adherence", "--overlay", "2026-10-12-weekly")["data"]

    def session(self, data, session_id):
        return next(s for s in data["sessions"] if s["session_id"] == session_id)

    def exercise(self, session, exercise_id):
        return next(e for e in session["exercises"] if e["exercise_id"] == exercise_id)

    def test_a_workout_at_the_prescription_hits(self):
        self.cache(workouts=[session_a_workout()])
        self.sync()
        data = self.adherence()
        session_a = self.session(data, "session-a")
        self.assertEqual((session_a["status"], session_a["workout_id"], session_a["moved"]), ("trained", W[5], False))
        squat = self.exercise(session_a, "bb_back_squat")
        self.assertEqual((squat["status"], squat["sets_prescribed"], squat["sets_logged"], squat["rpe_delta"]),
                         ("hit", 3, 3, 0))
        self.assertEqual(self.exercise(session_a, "db_bench_press")["status"], "hit")
        self.assertEqual(data["summary"]["trained"], 1)

    def test_two_of_three_squat_sets_is_under(self):
        self.cache(workouts=[session_a_workout(squat_sets=2)])
        self.sync()
        self.assertEqual(self.exercise(self.session(self.adherence(), "session-a"), "bb_back_squat")["status"], "under")

    def test_a_heavier_load_is_over_and_a_moved_session_says_so(self):
        workout = session_a_workout(day="2026-10-13")
        for logged in workout["exercises"][0]["sets"][1:]:
            logged["weight_kg"] = 105.0
        self.cache(workouts=[workout])
        self.sync()
        session_a = self.session(self.adherence(), "session-a")
        self.assertEqual((session_a["status"], session_a["moved"]), ("trained", True))
        self.assertEqual(self.exercise(session_a, "bb_back_squat")["status"], "over")

    def test_a_missed_session_carries_its_miss_tag_or_untagged(self):
        self.cache(workouts=[session_a_workout()])
        self.sync()
        session_b = self.session(self.adherence(), "session-b")
        self.assertEqual((session_b["status"], session_b["tag"]), ("missed", "untagged"))
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-15", "--session", "session-b",
                   "--tag", "sleep", "--source", "check-in 2026-10-19")
        data = self.adherence()
        self.assertEqual((self.session(data, "session-b")["status"], self.session(data, "session-b")["tag"]),
                         ("missed", "sleep"))
        self.assertEqual(data["summary"]["missed"], {"sleep": 1})

    def test_one_miss_annotation_tags_one_missed_session(self):
        def second_session_a(doc):
            doc["sessions"].append(dict(copy.deepcopy(doc["sessions"][0]), date="2026-10-17"))

        self.edit_json("data/overlays/2026-10-12-weekly.json", second_session_a)
        self.cache(workouts=[])
        self.sync()
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-17", "--session", "session-a",
                   "--tag", "sleep")
        data = self.adherence()
        tags = {s["date"]: (s["status"], s["tag"]) for s in data["sessions"] if s["session_id"] == "session-a"}
        self.assertEqual(tags, {"2026-10-12": ("missed", "untagged"), "2026-10-17": ("missed", "sleep")})
        self.assertEqual(data["summary"]["missed"]["sleep"], 1)

    def test_trained_unlogged_counts_trained_with_unknown_exercises_and_no_dose_or_e1rm(self):
        self.cache(workouts=[session_a_workout()])
        self.sync()
        dose = self.coach("stats", "dose", "--week", "2026-W42")["data"]
        e1rm = self.coach("stats", "e1rm")["data"]
        self.coach("history", "annotate", "--kind", "trained_unlogged", "--session", "session-b",
                   "--date", "2026-10-15", "--note", "hotel gym, phone dead")
        session_b = self.session(self.adherence(), "session-b")
        self.assertEqual((session_b["status"], session_b["unlogged"]), ("trained", True))
        self.assertEqual({e["status"] for e in session_b["exercises"]}, {"unknown"})
        self.assertEqual(self.coach("stats", "dose", "--week", "2026-W42")["data"], dose)
        self.assertEqual(self.coach("stats", "e1rm")["data"], e1rm)

    def test_sessions_after_today_are_upcoming(self):
        self.env = {"COACH_NOW": "2026-10-13T18:00:00Z"}
        self.cache(workouts=[session_a_workout()])
        self.sync()
        self.assertEqual(self.session(self.adherence(), "session-b")["status"], "upcoming")

    def test_a_span_reads_the_overlay_in_force_each_day(self):
        self.cache(workouts=[session_a_workout()])
        self.sync()
        data = self.coach("stats", "adherence", "--span", "2026-10-12..2026-10-13")["data"]
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["session-a"])


def conditioning_instance(case, kind="conditioning"):
    """Program and overlay with a session of `kind` carried by the cached Conditioning routine."""
    def add_session(doc):
        session = copy.deepcopy(doc["sessions"][1])
        session.update(id="circuit", title="Circuit", kind=kind)
        session["exercises"] = [dict(session["exercises"][0], exercise_id="kb_swing", load_mode="single_implement",
                                     start_load=24)]
        doc["sessions"].append(session)

    case.edit_json("data/program.json", add_session)
    case.edit_json("data/exercises.json", lambda doc: doc["exercises"].update(kb_swing={
        "hevy_template_id": "F00000A3", "load_mode": "single_implement", "load_mode_proposed": "single_implement",
        "confidence": "high", "avoid": None}))
    overlay = read_json(VALID / "data" / "overlays" / "2026-10-12-weekly.json")
    overlay.update(id="2026-10-05-weekly", span={"start": "2026-10-05", "end": "2026-10-11"}, approval=None,
                   created_at="2026-10-04T18:00:00Z")
    line = copy.deepcopy(overlay["sessions"][1]["exercises"][0])
    line.update(exercise_id="kb_swing", hevy_template_id="F00000A3", load_mode="single_implement")
    for logged in line["sets"]:
        logged["load"] = {"mode": "single_implement", "unit": "kg", "per_hand": 24, "hevy_total": 24, "hevy_kg": 24}
    overlay["sessions"] = [dict(overlay["sessions"][1], session_id="circuit", date="2026-10-09", title="Circuit",
                                hevy_routine_id=CONDITIONING_ROUTINE, exercises=[line])]
    write_json(case.root / "data" / "overlays" / "2026-10-05-weekly.json", overlay)
    swings = next(w for w in fixture_workouts(VALID.parents[1] / "hevy" / "conditioning")
                  if w["id"].endswith("0c3"))
    case.cache(workouts=[swings])
    case.sync()


class ConditioningTest(HistoryCase):
    def test_a_conditioning_session_adds_no_dose_exposure_or_e1rm(self):
        conditioning_instance(self)
        workout = self.month("2026-10")["workouts"][0]
        self.assertEqual(workout["session_id"], "circuit")
        self.assertEqual(self.coach("stats", "dose", "--week", "2026-W41")["data"]["muscles"], {})
        self.assertEqual(history.exposures(self.root, "kb_swing"), [])
        self.assertNotIn("kb_swing", self.coach("stats", "e1rm")["data"]["series"])
        circuit = self.coach("stats", "adherence", "--overlay", "2026-10-05-weekly")["data"]["sessions"][0]
        self.assertEqual((circuit["status"], circuit["exercises"]), ("trained", []))

    def test_the_same_workout_in_a_lifting_session_counts(self):
        conditioning_instance(self, kind="lifting")
        self.assertEqual(self.coach("stats", "dose", "--week", "2026-W41")["data"]["muscles"]["glutes"]["direct"], 3)
        self.assertEqual(len(history.exposures(self.root, "kb_swing")), 1)


class DoseTest(HistoryCase):
    def test_week_41_counts_direct_and_fractional_sets(self):
        self.cache()
        self.sync()
        data = self.coach("stats", "dose", "--week", "2026-W41")["data"]
        self.assertEqual(data["week"], "2026-W41")
        self.assertEqual(data["muscles"]["chest"], {"direct": 3, "fractional": 3})
        self.assertEqual(data["muscles"]["triceps"], {"direct": 0, "fractional": 1.5})
        self.assertEqual(sorted(data["by_workout"]), [W[3], W[4]])
        self.assertEqual(data["by_workout"][W[3]]["muscles"]["chest"], {"direct": 3, "fractional": 3})

    def test_fractional_totals_match_set_weights(self):
        self.cache()
        self.sync()
        data = self.coach("stats", "dose", "--week", "2026-W41")["data"]
        library = Library.load(self.root)
        expected = {}
        for exercise_id, sets in (("bb_back_squat", 3), ("db_bench_press", 3), ("db_single_arm_row", 3),
                                  ("pull_up", 3)):
            for muscle, weight in stats.set_weights(library.get(exercise_id)).items():
                expected[muscle] = expected.get(muscle, 0) + sets * weight
        self.assertEqual({m: v["fractional"] for m, v in data["muscles"].items()}, expected)

    def test_a_set_at_rpe_5_is_not_a_hard_set(self):
        def easy_set(workouts):
            bench = next(w for w in workouts if w["id"] == W[3])["exercises"][1]
            bench["sets"].append(hevy_set(3, 45.0, 10, 5))

        self.cache(edit=easy_set)
        self.sync()
        self.assertEqual(self.coach("stats", "dose", "--week", "2026-W41")["data"]["muscles"]["chest"]["direct"], 3)

    def test_a_sunday_week_takes_its_own_span(self):
        self.cache()
        self.sync()
        with (self.root / "config.toml").open("r+", encoding="utf-8") as handle:
            text = handle.read().replace('week_starts = "monday"', 'week_starts = "sunday"')
            handle.seek(0)
            handle.write(text)
            handle.truncate()
        data = self.coach("stats", "dose", "--week", "2026-10-04")["data"]
        self.assertEqual(data["span"], {"start": "2026-10-04", "end": "2026-10-10"})
        self.assertEqual(data["muscles"]["chest"]["direct"], 3)


class DurationsTest(HistoryCase):
    def set_config(self, old, new):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def add_overlay_for_workout_3(self):
        overlay = read_json(VALID / "data" / "overlays" / "2026-10-12-weekly.json")
        overlay.update(id="2026-10-05-weekly", span={"start": "2026-10-05", "end": "2026-10-11"}, approval=None,
                       created_at="2026-10-04T18:00:00Z")
        overlay["sessions"][0]["date"] = "2026-10-05"
        overlay["sessions"][1]["date"] = "2026-10-08"
        write_json(self.root / "data" / "overlays" / "2026-10-05-weekly.json", overlay)

    def workout_3(self):
        data = self.coach("stats", "durations")["data"]
        return data, next(d for d in data["workouts"] if d["workout_id"] == W[3])

    def test_a_session_cap_puts_workout_3_over(self):
        self.add_overlay_for_workout_3()
        self.set_config("[caps]", "[caps]\n\n[sessions.cap_minutes]\nsession-a = 45\n")
        self.cache()
        self.sync()
        data, row = self.workout_3()
        self.assertEqual((row["minutes"], row["session_id"], row["cap_minutes"], row["over_cap"]),
                         (58, "session-a", 45, True))
        self.assertEqual([(f["code"], f["severity"], f["session_id"]) for f in data["flags"]],
                         [("duration_over_cap", "info", "session-a")])

    def test_the_athlete_default_applies_without_a_session_entry(self):
        self.set_config("session_minutes = 60", "session_minutes = 45")
        self.cache()
        self.sync()
        _, row = self.workout_3()
        self.assertEqual((row["cap_minutes"], row["over_cap"]), (45, True))
        self.set_config("session_minutes = 45", "session_minutes = 60")
        _, row = self.workout_3()
        self.assertEqual((row["cap_minutes"], row["over_cap"]), (60, False))

    def test_a_zero_cap_means_no_cap(self):
        self.set_config("session_minutes = 60", "session_minutes = 0")
        self.cache()
        self.sync()
        _, row = self.workout_3()
        self.assertEqual((row["cap_minutes"], row["over_cap"]), (None, False))


class AuditTest(HistoryCase):
    base = INSTANCES / "slip"

    def candidates(self):
        return self.coach("stats", "audit")["data"]["candidates"]

    def bench_points(self):
        series = self.coach("stats", "e1rm", "--exercise", "db_bench_press")["data"]["series"]
        return [p["date"] for p in series.get("db_bench_press", [])]

    def test_one_open_candidate_with_its_sibling_and_out_of_e1rm(self):
        found = [c for c in self.candidates() if c["exercise_id"] == "db_bench_press"]
        self.assertEqual(len(found), 1)
        candidate = found[0]
        self.assertEqual((candidate["date"], candidate["ratio"], candidate["status"]), ("2026-10-05", 2.0, "open"))
        self.assertEqual(candidate["siblings"], ["db_shoulder_press"])
        self.assertEqual(candidate["previous"]["date"], "2026-09-28")
        flags = self.coach("stats", "audit")["data"]["flags"]
        self.assertIn(("convention_slip", "warn", "db_bench_press"),
                      [(f["code"], f["severity"], f["exercise_id"]) for f in flags])
        self.assertEqual(self.bench_points(), ["2026-09-28"])
        self.assertTrue(history.exposures(self.root, "db_bench_press")[0]["suspect"])

    def test_a_discount_closes_it_and_keeps_it_out(self):
        self.coach("history", "annotate", "--kind", "discount", "--workout", W[3], "--exercise", "db_bench_press",
                   "--reason", "logged Hevy 90 for 22.5/hand")
        candidate = next(c for c in self.candidates() if c["exercise_id"] == "db_bench_press")
        self.assertEqual(candidate["status"], "discounted")
        self.assertEqual(self.bench_points(), ["2026-09-28"])

    def test_a_confirm_closes_it_and_lets_it_in(self):
        self.coach("history", "annotate", "--kind", "confirm", "--workout", W[3], "--exercise", "db_bench_press",
                   "--reason", "moved to heavier dumbbells")
        candidate = next(c for c in self.candidates() if c["exercise_id"] == "db_bench_press")
        self.assertEqual(candidate["status"], "confirmed")
        self.assertEqual(self.bench_points(), ["2026-09-28", "2026-10-05"])

    def test_the_window_is_the_last_n_weeks(self):
        self.env = {"COACH_NOW": "2026-12-20T18:00:00Z"}
        self.assertEqual(self.candidates(), [])


class MissTagTest(HistoryCase):
    def test_an_unknown_tag_exits_1_listing_the_six(self):
        envelope = self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-15", "--session",
                              "session-b", "--tag", "lazy", expect=1)
        message = envelope["error"]["message"]
        for tag in ("time", "sleep", "ill", "family", "skipped", "other"):
            self.assertIn(tag, message)
        self.assertFalse((self.root / "data" / "history" / "annotations.json").exists())


if __name__ == "__main__":
    unittest.main()
