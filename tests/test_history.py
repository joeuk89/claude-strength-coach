"""Resolving workouts into durable monthly history files (contract C17)."""

import importlib
import json
import sys
import tempfile
import textwrap
from pathlib import Path

from coach import history, history_sources
from coach.validate import validate
from coach import jsonio
from tests.support import run_cli
from tests.support.history import (DB_BENCH_LOAD, NOW, R_A, SYNTHETIC, W, HistoryCase, hevy_exercise, hevy_set,
                                   hevy_workout, write_json)

MONTH_SCHEMA = jsonio.load_schema("history_month")


def exercise(workout, exercise_id):
    return next(e for e in workout["exercises"] if e["exercise_id"] == exercise_id)


def workout_in(doc, workout_id):
    return next(w for w in doc["workouts"] if w["workout_id"] == workout_id)


class SyncFromHevyPullTest(HistoryCase):
    def test_pull_then_sync_writes_both_months_with_resolved_loads(self):
        env = {"COACH_HEVY_FIXTURES": str(SYNTHETIC)}
        self.coach("hevy", "pull", "--full", env=env)
        data = self.sync(env=env)
        self.assertEqual(sorted(data["added"]), [W[1], W[2], W[3], W[4]])
        self.assertEqual(sorted(data["months_written"]), ["2026-09", "2026-10"])

        september, october = self.month("2026-09"), self.month("2026-10")
        for doc in (september, october):
            self.assertEqual(validate(doc, MONTH_SCHEMA), [])
        self.assertEqual([w["workout_id"] for w in september["workouts"]], [W[1]])
        self.assertEqual([w["workout_id"] for w in october["workouts"]], [W[2], W[3], W[4]])
        for workout in september["workouts"] + october["workouts"]:
            self.assertEqual(workout["source"], "hevy")
            self.assertEqual(workout["resolved_at"], NOW)

        bench = exercise(workout_in(october, W[3]), "db_bench_press")
        self.assertEqual(bench["load_mode"], "per_hand_x2")
        self.assertEqual(bench["load_mode_source"], "library")
        for logged in bench["sets"]:
            self.assertEqual(logged["weight_kg"], 45)
            self.assertEqual(logged["load"], DB_BENCH_LOAD)

        squat = exercise(workout_in(october, W[3]), "bb_back_squat")
        self.assertEqual(squat["sets"][0]["load"],
                         {"mode": "total", "unit": "kg", "per_hand": None, "hevy_total": 97.5, "hevy_kg": 97.5})
        pull_up = exercise(workout_in(october, W[2]), "pull_up")
        self.assertEqual(pull_up["sets"][0]["load"]["hevy_total"], 0)
        workout_3 = workout_in(october, W[3])
        self.assertEqual(workout_3["duration_minutes"], 58)
        self.assertEqual(workout_3["date"], "2026-10-05")


class FreezingTest(HistoryCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()

    def test_a_second_sync_changes_no_byte(self):
        before = self.history_bytes()
        data = self.sync()
        self.assertEqual(self.history_bytes(), before)
        self.assertEqual((data["added"], data["updated"], data["removed"], data["months_written"]), ([], [], [], []))

    def test_a_changed_version_re_resolves_only_that_workout(self):
        def edit(workouts):
            workout = next(w for w in workouts if w["id"] == W[3])
            workout["updated_at"] = "2026-10-12T08:00:00Z"
            workout["exercises"][1]["sets"][2]["reps"] = 9

        before = self.month("2026-10")
        self.cache(edit=edit)
        data = self.sync(env={"COACH_NOW": "2026-10-12T09:00:00Z"})
        self.assertEqual(data["updated"], [W[3]])
        self.assertEqual(data["added"], [])
        after = self.month("2026-10")
        self.assertEqual(exercise(workout_in(after, W[3]), "db_bench_press")["sets"][2]["reps"], 9)
        self.assertEqual(workout_in(after, W[3])["resolved_at"], "2026-10-12T09:00:00Z")
        for workout_id in (W[2], W[4]):
            self.assertEqual(workout_in(after, workout_id), workout_in(before, workout_id))
        self.assertEqual(self.month("2026-09"), self.month("2026-09"))

    def test_a_library_mode_change_leaves_stored_sets_and_rebuild_dry_run_shows_the_difference(self):
        before = self.history_bytes()
        self.edit_json("data/exercises.json",
                       lambda doc: doc["exercises"]["db_bench_press"].update(load_mode="single_implement"))
        self.sync()
        self.assertEqual(self.history_bytes(), before)

        data = self.coach("history", "rebuild", "--month", "2026-10", "--dry-run")["data"]
        self.assertEqual(self.history_bytes(), before)
        self.assertFalse(data["written"])
        bench = [d for d in data["differences"] if d["exercise_id"] == "db_bench_press"]
        self.assertEqual(len(bench), 3)
        self.assertEqual({d["workout_id"] for d in bench}, {W[3]})
        self.assertEqual(bench[0]["before"]["load"], DB_BENCH_LOAD)
        self.assertEqual(bench[0]["after"]["load"],
                         {"mode": "single_implement", "unit": "kg", "per_hand": 45, "hevy_total": 45, "hevy_kg": 45})
        self.assertEqual(bench[0]["after"]["load_mode"], "single_implement")

    def test_rebuild_writes_the_reinterpretation(self):
        self.edit_json("data/exercises.json",
                       lambda doc: doc["exercises"]["db_bench_press"].update(load_mode="single_implement"))
        data = self.coach("history", "rebuild", "--month", "2026-10")["data"]
        self.assertTrue(data["written"])
        bench = exercise(workout_in(self.month("2026-10"), W[3]), "db_bench_press")
        self.assertEqual(bench["load_mode"], "single_implement")
        self.assertEqual(bench["sets"][0]["load"]["per_hand"], 45)

    def test_rebuild_of_a_month_with_no_file_exits_1(self):
        self.coach("history", "rebuild", "--month", "2026-07", expect=1)

    def test_a_workout_deleted_at_the_source_is_removed_and_reported(self):
        self.cache(edit=lambda workouts: workouts.remove(next(w for w in workouts if w["id"] == W[2])))
        data = self.sync()
        self.assertEqual(data["removed"], [W[2]])
        self.assertNotIn(W[2], [w["workout_id"] for w in self.month("2026-10")["workouts"]])

    def test_an_empty_hevy_cache_removes_nothing(self):
        import shutil

        before = self.history_bytes()
        shutil.rmtree(self.root / ".coach")
        data = self.sync()
        self.assertEqual(self.history_bytes(), before)
        self.assertEqual(data["removed"], [])

    def test_a_load_mode_annotation_re_resolves_the_workouts_it_covers(self):
        self.coach("history", "annotate", "--kind", "load_mode", "--exercise", "db_bench_press",
                   "--start", "2026-10-01", "--end", "2026-10-31", "--load-mode", "single_implement",
                   "--reason", "one dumbbell at a time all month")
        data = self.sync()
        self.assertEqual([r["workout_id"] for r in data["reinterpreted"]], [W[3]])
        bench = exercise(workout_in(self.month("2026-10"), W[3]), "db_bench_press")
        self.assertEqual((bench["load_mode"], bench["load_mode_source"]), ("single_implement", "annotation"))
        september_bench = exercise(self.month("2026-09")["workouts"][0], "db_bench_press")
        self.assertEqual(september_bench["load_mode_source"], "library")


class DryRunTest(HistoryCase):
    def setUp(self):
        super().setUp()
        self.cache()

    def test_sync_dry_run_writes_nothing(self):
        data = self.coach("history", "sync", "--dry-run")["data"]
        self.assertEqual(len(data["added"]), 4)
        self.assertFalse((self.root / "data" / "history").exists())

    def test_annotate_dry_run_writes_nothing(self):
        self.sync()
        before = self.history_bytes()
        data = self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-15", "--session", "session-b",
                          "--tag", "sleep", "--dry-run")["data"]
        self.assertEqual(data["annotation"]["id"], "a-0001")
        self.assertEqual(self.history_bytes(), before)

    def test_rebuild_dry_run_writes_nothing(self):
        self.sync()
        before = self.history_bytes()
        self.coach("history", "rebuild", "--month", "2026-10", "--dry-run")
        self.assertEqual(self.history_bytes(), before)


class OverlaySessionTest(HistoryCase):
    def test_a_workout_takes_the_session_and_overlay_whose_routine_it_carries(self):
        self.cache(workouts=[hevy_workout(W[5], R_A, "Session A", "2026-10-13", [
            hevy_exercise(0, "Squat (Barbell)", "F0000001", [hevy_set(0, 100.0, 5, 7)])])])
        self.sync(env={"COACH_NOW": "2026-10-19T18:00:00Z"})
        workout = self.month("2026-10")["workouts"][0]
        self.assertEqual((workout["session_id"], workout["overlay_id"]), ("session-a", "2026-10-12-weekly"))
        self.assertEqual(workout["exercises"][0]["load_mode_source"], "overlay")

    def test_a_workout_with_no_overlay_in_force_has_neither(self):
        self.cache()
        self.sync()
        workout = self.month("2026-09")["workouts"][0]
        self.assertEqual((workout["session_id"], workout["overlay_id"]), (None, None))

    def test_an_exercise_the_library_does_not_know_stays_unresolved(self):
        self.cache(workouts=[hevy_workout(W[5], None, "Odd day", "2026-10-06", [
            hevy_exercise(0, "Mystery Lift", "Z9999999", [hevy_set(0, 40.0, 8, 8)])])])
        data = self.sync()
        stored = self.month("2026-10")["workouts"][0]["exercises"][0]
        self.assertEqual((stored["exercise_id"], stored["load_mode"], stored["sets"][0]["load"]), (None, None, None))
        self.assertEqual(stored["title"], "Mystery Lift")
        self.assertEqual(data["unresolved"], [{"workout_id": W[5], "date": "2026-10-06", "title": "Mystery Lift",
                                               "exercise_id": None}])


MANUAL_SOURCE = textwrap.dedent('''
    from coach.history_sources import SourceWorkout

    VERSION = "v1"

    def workouts(root):
        return [SourceWorkout(
            source="manual", workout_id="manual:2026-10-12-session-a-1", date="2026-10-12",
            start_time=None, end_time=None, duration_minutes=55, title="Session A", description="",
            routine_id=None, session_id="session-a", overlay_id="2026-10-12-weekly", hevy_updated_at=None,
            exercises=[{"exercise_id": "db_bench_press", "title": "DB bench", "hevy_template_id": None,
                        "load_mode": "per_hand_x2", "unit": "kg", "notes": "",
                        "sets": [{"index": i, "type": "normal", "reps": 10, "rpe": 8, "value": 22.5,
                                  "weight_kg": None, "duration_seconds": None, "distance_meters": None}
                                 for i in range(3)]}])]

    def version(workout):
        return VERSION
''')


class ManualSourceTest(HistoryCase):
    """A source module dropped into coach/history_sources/ is found without editing any registry.

    The stub is named `stub_manual` because the real `manual` source would shadow a module of that name.
    """

    def setUp(self):
        super().setUp()
        self.cache()
        package_dir = self.tmp / "sources"
        package_dir.mkdir()
        (package_dir / "stub_manual.py").write_text(MANUAL_SOURCE, encoding="utf-8")
        history_sources.__path__.append(str(package_dir))
        self.addCleanup(history_sources.__path__.remove, str(package_dir))
        self.addCleanup(sys.modules.pop, "coach.history_sources.stub_manual", None)
        self.env = {"COACH_NOW": "2026-10-19T18:00:00Z"}

    def manual_workout(self):
        doc = self.month("2026-10")
        return workout_in(doc, "manual:2026-10-12-session-a-1")

    def test_its_workout_resolves_with_source_manual(self):
        data = self.sync()
        self.assertIn("manual:2026-10-12-session-a-1", data["added"])
        workout = self.manual_workout()
        self.assertEqual((workout["source"], workout["routine_id"], workout["hevy_updated_at"]),
                         ("manual", None, None))
        self.assertEqual(workout["session_id"], "session-a")
        bench = exercise(workout, "db_bench_press")
        self.assertEqual(bench["load_mode_source"], "log")
        for logged in bench["sets"]:
            self.assertIsNone(logged["weight_kg"])
            self.assertEqual(logged["load"], DB_BENCH_LOAD)
        for other in self.month("2026-10")["workouts"]:
            if other["workout_id"].startswith("1000"):
                self.assertEqual(other["source"], "hevy")

    def test_adherence_counts_session_a_trained_from_it(self):
        self.sync()
        data = self.coach("stats", "adherence", "--overlay", "2026-10-12-weekly")["data"]
        session_a = next(s for s in data["sessions"] if s["session_id"] == "session-a")
        self.assertEqual(session_a["status"], "trained")
        self.assertEqual(session_a["workout_id"], "manual:2026-10-12-session-a-1")

    def test_a_changed_version_re_resolves_only_that_workout(self):
        self.sync()
        module = importlib.import_module("coach.history_sources.stub_manual")
        module.VERSION = "v2"
        data = self.sync(env={"COACH_NOW": "2026-10-20T08:00:00Z"})
        self.assertEqual(data["updated"], ["manual:2026-10-12-session-a-1"])
        self.assertEqual(self.manual_workout()["resolved_at"], "2026-10-20T08:00:00Z")


class UnsyncedTest(HistoryCase):
    def test_include_unsynced_reads_cached_workouts_without_writing(self):
        self.cache(edit=lambda workouts: workouts.remove(next(w for w in workouts if w["id"] == W[4])))
        self.sync()
        self.cache()
        before = self.history_bytes()
        cache_before = {p: p.read_bytes() for p in sorted((self.root / ".coach").rglob("*.json"))}

        default = history.workouts(self.root)
        fresh = history.workouts(self.root, include_unsynced=True)
        self.assertNotIn(W[4], [w["workout_id"] for w in default])
        unsynced = [w for w in fresh if w["unsynced"]]
        self.assertEqual([w["workout_id"] for w in unsynced], [W[4]])
        self.assertTrue(all(not w["unsynced"] for w in fresh if w["workout_id"] != W[4]))

        from coach import stats
        report = stats.adherence(self.root, span=("2026-10-05", "2026-10-11"), include_unsynced=True)
        self.assertIn((W[4], True), [(w["workout_id"], w["unsynced"]) for w in report["extra"]])
        default_report = stats.adherence(self.root, span=("2026-10-05", "2026-10-11"))
        self.assertNotIn(W[4], [w["workout_id"] for w in default_report["extra"]])
        self.assertEqual(self.history_bytes(), before)
        self.assertEqual({p: p.read_bytes() for p in sorted((self.root / ".coach").rglob("*.json"))}, cache_before)


class ShowTest(HistoryCase):
    def test_show_filters_by_date(self):
        self.cache()
        self.sync()
        data = self.coach("history", "show", "--since", "2026-10-02", "--until", "2026-10-06")["data"]
        self.assertEqual([w["workout_id"] for w in data["workouts"]], [W[3]])


class ReadingApiTest(HistoryCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()

    def test_exposures_are_newest_first_with_working_sets_only(self):
        found = history.exposures(self.root, "bb_back_squat")
        self.assertEqual([e["date"] for e in found], ["2026-10-05", "2026-09-28"])
        self.assertEqual(len(found[0]["sets"]), 3)
        self.assertEqual((found[0]["suspect"], found[0]["excluded"]), (False, False))
        self.assertEqual([e["date"] for e in history.exposures(self.root, "bb_back_squat", before="2026-10-05")],
                         ["2026-09-28"])

    def test_last_lifting_date(self):
        self.assertEqual(str(history.last_lifting_date(self.root, "2026-10-12")), "2026-10-08")
        self.assertEqual(str(history.last_lifting_date(self.root, "2026-10-08")), "2026-10-05")
        self.assertIsNone(history.last_lifting_date(self.root, "2026-09-28"))

    def test_a_withdrawn_annotation_stops_applying(self):
        self.coach("history", "annotate", "--kind", "discount", "--workout", W[3], "--exercise", "bb_back_squat",
                   "--reason", "wrong bar")
        self.assertTrue(history.exposures(self.root, "bb_back_squat")[0]["excluded"])
        self.coach("history", "annotate", "--kind", "discount", "--withdraws", "a-0001", "--reason", "it was right")
        self.assertFalse(history.exposures(self.root, "bb_back_squat")[0]["excluded"])
        self.assertEqual(history.annotations(self.root), [])
        listed = self.coach("history", "annotations", "--all")["data"]["annotations"]
        self.assertEqual([(a["id"], a["in_force"]) for a in listed], [("a-0001", False), ("a-0002", False)])
