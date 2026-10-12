"""Training without Hevy: the manual log, its history source and the Hevy-off rules (contract C46, C5, C17, C18)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import units
from tests.support import INSTANCES, VALID, run_cli, run_module
from tests.support.history import read_json, write_json

NOHEVY = INSTANCES / "nohevy"
LOG = Path("data") / "log" / "workouts.jsonl"
MONDAY = "2026-10-12T19:00:00Z"
WEEKLY = "2026-10-12-weekly"
DB_BENCH_LOAD = {"mode": "per_hand_x2", "unit": "kg", "per_hand": 22.5, "hevy_total": 45, "hevy_kg": 45.0}


class FormatLoadWithoutHevyTest(unittest.TestCase):
    def test_show_hevy_false_prints_the_athletes_number_only(self):
        cases = [
            (units.make_load(25, "per_hand_x2", "kg"), "25/hand"),
            (units.make_load(25, "single_implement", "kg"), "25"),
            (units.make_load(20, "assisted", "kg"), "BW-20 assist"),
            (units.make_load(100, "total", "kg"), "100"),
            (units.make_load(10, "bodyweight", "kg"), "BW+10"),
            (units.make_load(0, "bodyweight", "kg"), "BW"),
        ]
        for load, text in cases:
            with self.subTest(text=text):
                self.assertEqual(units.format_load(load, show_hevy=False), text)

    def test_the_default_still_shows_the_hevy_value(self):
        self.assertEqual(units.format_load(units.make_load(25, "per_hand_x2", "kg")), "25/hand (Hevy: 50)")

    def test_units_format_no_hevy(self):
        argv = ["units", "format", "--mode", "per_hand_x2", "--value", "25", "--unit", "kg"]
        code, envelope, _ = run_module(argv + ["--no-hevy"])
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["text"], "25/hand")
        code, envelope, _ = run_module(argv)
        self.assertEqual(envelope["data"]["text"], "25/hand (Hevy: 50)")


class NoHevyCase(unittest.TestCase):
    """A temp copy of an instance (default `nohevy/`), with COACH_NOW on Monday evening."""

    base = NOHEVY
    now = MONDAY

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0, now=None):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now or self.now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def prefill(self, session="session-a", day="2026-10-12"):
        return self.coach("log", "prefill", "--session", session, "--date", day)["data"]["draft"]

    def write_input(self, draft, name="draft.json"):
        path = self.tmp / name
        path.write_text(json.dumps(draft), encoding="utf-8")
        return str(path)

    def filled(self, edit=None, day="2026-10-12"):
        """The Session A prefill with every rep range filled at its top and an RPE the athlete gave, optionally edited."""
        draft = self.prefill(day=day)
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                if set_["reps"] is None:
                    set_["reps"] = 10
                if set_["rpe"] is None:
                    set_["rpe"] = 8
        if edit:
            edit(draft)
        return draft

    def add(self, draft, *extra, expect=0):
        return self.coach("log", "add", "--input", self.write_input(draft), *extra, expect=expect)

    def log_lines(self):
        path = self.root / LOG
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def bench(self, draft):
        return next(e for e in draft["exercises"] if e["exercise_id"] == "db_bench_press")


class PrefillTest(NoHevyCase):
    def test_db_bench_comes_back_in_the_athletes_number(self):
        draft = self.prefill()
        bench = self.bench(draft)
        self.assertEqual(bench["load_mode"], "per_hand_x2")
        self.assertEqual(bench["unit"], "kg")
        self.assertEqual(len(bench["sets"]), 3)
        for set_ in bench["sets"]:
            self.assertEqual(set_["value"], 25)
            self.assertIsNone(set_["reps"])
            self.assertIsNone(set_["rpe"])
            self.assertEqual(set_["type"], "normal")

    def test_fixed_reps_and_loads_are_filled_and_warm_ups_left_out(self):
        draft = self.prefill()
        squat = next(e for e in draft["exercises"] if e["exercise_id"] == "bb_back_squat")
        self.assertEqual([(s["reps"], s["value"]) for s in squat["sets"]], [(5, 100)] * 3)

    def test_the_draft_is_a_line_without_id_and_logged_at(self):
        draft = self.prefill()
        self.assertNotIn("id", draft)
        self.assertNotIn("logged_at", draft)
        self.assertEqual((draft["kind"], draft["date"], draft["session_id"], draft["overlay_id"]),
                         ("workout", "2026-10-12", "session-a", WEEKLY))

    def test_a_session_moved_to_another_day_still_prefills(self):
        draft = self.prefill(day="2026-10-13")
        self.assertEqual((draft["date"], draft["session_id"]), ("2026-10-13", "session-a"))

    def test_no_overlay_or_unknown_session_exits_1(self):
        self.coach("log", "prefill", "--session", "session-a", "--date", "2026-11-30", expect=1)
        self.coach("log", "prefill", "--session", "session-z", "--date", "2026-10-12", expect=1)

    def test_prefill_writes_nothing(self):
        before = (self.root / LOG).read_bytes()
        self.prefill()
        self.assertEqual((self.root / LOG).read_bytes(), before)


class AddTest(NoHevyCase):
    def test_appends_exactly_one_line_and_returns_the_id_and_a_summary(self):
        before = self.log_lines()
        data = self.add(self.filled())["data"]
        after = self.log_lines()
        self.assertEqual(after[:-1], before)
        self.assertEqual(len(after), len(before) + 1)
        line = after[-1]
        self.assertEqual(data["id"], "manual:2026-10-12-session-a-1")
        self.assertEqual(line["id"], data["id"])
        self.assertEqual(line["logged_at"], MONDAY)
        self.assertIn("25/hand", data["summary"])
        self.assertNotIn("Hevy", data["summary"])
        self.assertNotIn("\n", data["summary"])

    def test_dry_run_leaves_the_file_byte_identical(self):
        before = (self.root / LOG).read_bytes()
        data = self.add(self.filled(), "--dry-run")["data"]
        self.assertEqual((self.root / LOG).read_bytes(), before)
        self.assertEqual(data["id"], "manual:2026-10-12-session-a-1")
        self.assertFalse(data["written"])

    def test_a_second_add_for_the_same_date_and_session_is_refused_unless_again(self):
        self.add(self.filled())
        before = (self.root / LOG).read_bytes()
        envelope = self.add(self.filled(), expect=3)
        self.assertIn("--again", envelope["error"]["message"])
        self.assertEqual((self.root / LOG).read_bytes(), before)
        data = self.add(self.filled(), "--again")["data"]
        self.assertEqual(data["id"], "manual:2026-10-12-session-a-2")

    def test_a_voided_entry_no_longer_blocks_and_its_number_is_not_reused(self):
        self.add(self.filled())
        self.coach("log", "void", "manual:2026-10-12-session-a-1", "--reason", "logged the wrong bench")
        data = self.add(self.filled())["data"]
        self.assertEqual(data["id"], "manual:2026-10-12-session-a-2")

    def test_a_per_hand_value_equal_to_the_hevy_total_warns_looks_like_total(self):
        def doubled(draft):
            for set_ in self.bench(draft)["sets"]:
                set_["value"] = 50

        envelope = self.add(self.filled(doubled))
        self.assertTrue(any(w.startswith("looks_like_total") for w in envelope["warnings"]), envelope["warnings"])

    def test_an_ordinary_add_has_no_warning(self):
        self.assertEqual(self.add(self.filled())["warnings"], [])

    def test_with_hevy_on_add_still_works_and_warns_hevy_enabled(self):
        config = self.root / "config.toml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            "[hevy]\nenabled = false", "[hevy]\nenabled = true"), encoding="utf-8")
        envelope = self.add(self.filled())
        self.assertTrue(any(w.startswith("hevy_enabled") for w in envelope["warnings"]), envelope["warnings"])

    def test_validation_failures_exit_1_and_write_nothing(self):
        def unknown_exercise(draft):
            self.bench(draft)["exercise_id"] = "db_bench_pres"

        def other_mode(draft):
            self.bench(draft)["load_mode"] = "single_implement"

        def null_reps(draft):
            self.bench(draft)["sets"][0]["reps"] = None

        def future(draft):
            draft["date"] = "2026-10-15"

        def value_on_a_null_load_mode(draft):
            draft["exercises"].append({"exercise_id": "plank", "load_mode": "duration", "unit": "kg", "notes": "",
                                       "sets": [{"type": "normal", "reps": None, "rpe": None, "value": 10,
                                                 "duration_seconds": 60, "distance_meters": None}]})

        def other_unit(draft):
            self.bench(draft)["unit"] = "lb"

        def given_id(draft):
            draft["id"] = "manual:2026-10-12-session-a-9"

        def impossible_date(draft):
            draft["date"] = "2026-10-32"

        before = (self.root / LOG).read_bytes()
        for edit in (unknown_exercise, other_mode, null_reps, future, value_on_a_null_load_mode, other_unit,
                     given_id, impossible_date):
            with self.subTest(edit=edit.__name__):
                envelope = self.add(self.filled(edit), expect=1)
                self.assertEqual(envelope["error"]["code"], "validation")
        self.assertEqual((self.root / LOG).read_bytes(), before)

    def test_a_duration_set_needs_no_reps(self):
        def plank(draft):
            draft["exercises"].append({"exercise_id": "plank", "load_mode": "duration", "unit": "kg", "notes": "",
                                       "sets": [{"type": "normal", "reps": None, "rpe": None, "value": None,
                                                 "duration_seconds": 60, "distance_meters": None}]})

        self.add(self.filled(plank))

    def test_an_unplanned_workout_gets_an_adhoc_id(self):
        def adhoc(draft):
            draft["session_id"] = None
            draft["overlay_id"] = None

        data = self.add(self.filled(adhoc))["data"]
        self.assertEqual(data["id"], "manual:2026-10-12-adhoc-1")
        self.assertEqual(self.add(self.filled(adhoc))["data"]["id"], "manual:2026-10-12-adhoc-2")

    def test_the_first_add_creates_the_log(self):
        (self.root / LOG).unlink()
        self.add(self.filled())
        self.assertEqual(len(self.log_lines()), 1)


class VoidAndListTest(NoHevyCase):
    def test_list_returns_live_entries_and_since_filters_them(self):
        found = self.coach("log", "list")["data"]["workouts"]
        self.assertEqual([w["id"] for w in found],
                         ["manual:2026-09-28-session-a-1", "manual:2026-10-05-session-a-1"])
        found = self.coach("log", "list", "--since", "2026-10-01")["data"]["workouts"]
        self.assertEqual([w["id"] for w in found], ["manual:2026-10-05-session-a-1"])

    def test_void_appends_a_void_line_and_list_drops_the_entry(self):
        data = self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", "logged twice")["data"]
        self.assertTrue(data["written"])
        line = self.log_lines()[-1]
        self.assertEqual((line["kind"], line["id"], line["reason"], line["logged_at"]),
                         ("void", "manual:2026-09-28-session-a-1", "logged twice", MONDAY))
        found = self.coach("log", "list")["data"]["workouts"]
        self.assertEqual([w["id"] for w in found], ["manual:2026-10-05-session-a-1"])

    def test_void_dry_run_writes_nothing(self):
        before = (self.root / LOG).read_bytes()
        self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", "x", "--dry-run")
        self.assertEqual((self.root / LOG).read_bytes(), before)

    def test_void_of_an_unknown_or_voided_id_or_without_a_reason_exits_1(self):
        self.coach("log", "void", "manual:2026-09-29-session-a-1", "--reason", "x", expect=1)
        self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", " ", expect=1)
        self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", "x")
        self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", "x", expect=1)


class HistoryFromTheLogTest(NoHevyCase):
    def test_sync_writes_manual_workouts_into_the_month_files(self):
        data = self.coach("history", "sync")["data"]
        self.assertEqual(sorted(data["added"]), ["manual:2026-09-28-session-a-1", "manual:2026-10-05-session-a-1"])
        for month, workout_id in (("2026-09", "manual:2026-09-28-session-a-1"),
                                  ("2026-10", "manual:2026-10-05-session-a-1")):
            doc = read_json(self.root / "data" / "history" / f"{month}.json")
            record = next(w for w in doc["workouts"] if w["workout_id"] == workout_id)
            self.assertEqual(record["source"], "manual")
            self.assertIsNone(record["routine_id"])
            self.assertIsNone(record["hevy_updated_at"])
            self.assertEqual(record["session_id"], "session-a")
            bench = next(e for e in record["exercises"] if e["exercise_id"] == "db_bench_press")
            self.assertEqual(bench["load_mode_source"], "log")
            for set_ in bench["sets"]:
                self.assertEqual(set_["load"], DB_BENCH_LOAD)
                self.assertIsNone(set_["weight_kg"])

    def test_a_workout_without_an_overlay_takes_its_program_session_title(self):
        self.coach("history", "sync")
        doc = read_json(self.root / "data" / "history" / "2026-09.json")
        record = next(w for w in doc["workouts"] if w["workout_id"] == "manual:2026-09-28-session-a-1")
        self.assertIsNone(record["overlay_id"])
        self.assertEqual(record["title"], "Session A")

    def test_a_second_sync_changes_nothing(self):
        self.coach("history", "sync")
        directory = self.root / "data" / "history"
        before = {p.name: p.read_bytes() for p in directory.glob("*.json")}
        data = self.coach("history", "sync")["data"]
        self.assertEqual((data["added"], data["updated"], data["removed"]), ([], [], []))
        self.assertEqual({p.name: p.read_bytes() for p in directory.glob("*.json")}, before)

    def test_a_void_removes_the_entry_from_history(self):
        self.coach("history", "sync")
        data = self.coach("log", "void", "manual:2026-09-28-session-a-1", "--reason", "never happened")["data"]
        self.assertEqual(data["history"]["removed"], ["manual:2026-09-28-session-a-1"])
        doc = read_json(self.root / "data" / "history" / "2026-09.json")
        self.assertEqual(doc["workouts"], [])
        self.assertEqual(self.coach("history", "sync")["data"]["removed"], [])

    def test_e1rm_reads_the_manual_history(self):
        self.coach("history", "sync")
        series = self.coach("stats", "e1rm", "--exercise", "db_bench_press")["data"]["series"]["db_bench_press"]
        self.assertEqual([p["load"] for p in series], [22.5, 22.5])

    def test_adherence_counts_a_manual_session_a_as_trained(self):
        self.add_monday()
        self.coach("history", "sync")
        data = self.coach("stats", "adherence", "--overlay", WEEKLY)["data"]
        row = next(s for s in data["sessions"] if s["session_id"] == "session-a")
        self.assertEqual(row["status"], "trained")
        self.assertEqual(row["workout_id"], "manual:2026-10-12-session-a-1")
        self.assertEqual({e["exercise_id"]: e["status"] for e in row["exercises"]},
                         {"bb_back_squat": "hit", "db_bench_press": "hit"})

    def test_adherence_reads_an_unsynced_manual_workout(self):
        self.append_monday_without_sync()
        stored = self.coach("stats", "adherence", "--overlay", WEEKLY)["data"]
        self.assertNotEqual(next(s for s in stored["sessions"] if s["session_id"] == "session-a")["status"], "trained")
        data = self.coach("stats", "adherence", "--overlay", WEEKLY, "--include-unsynced")["data"]
        row = next(s for s in data["sessions"] if s["session_id"] == "session-a")
        self.assertEqual(row["status"], "trained")

    def append_monday_without_sync(self):
        line = dict(self.log_lines()[1], id="manual:2026-10-12-session-a-1", date="2026-10-12", overlay_id=WEEKLY)
        with open(self.root / LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")

    def add_monday(self):
        draft = self.coach("log", "prefill", "--session", "session-a", "--date", "2026-10-12")["data"]["draft"]
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                set_["reps"] = set_["reps"] or 10
                set_["rpe"] = 8
        path = self.tmp / "monday.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        self.coach("log", "add", "--input", str(path))

    def test_no_log_means_the_manual_source_holds_no_data(self):
        self.coach("history", "sync")
        (self.root / LOG).unlink()
        data = self.coach("history", "sync")["data"]
        self.assertEqual(data["removed"], [])


class ObservedNotPrescribedTest(NoHevyCase):
    """Squat is fixed 3×5 @ 100 RPE 7; DB bench is 3×8–10 @ 25/hand RPE 8."""

    def prefill_data(self):
        return self.coach("log", "prefill", "--session", "session-a", "--date", "2026-10-12")["data"]

    def squat(self, draft):
        return next(e for e in draft["exercises"] if e["exercise_id"] == "bb_back_squat")

    def asks(self, data, exercise_id, field):
        return [a for a in data["ask"] if a["exercise_id"] == exercise_id and a["field"] == field]

    def test_prefill_keeps_the_prescription_beside_a_draft_that_invents_nothing(self):
        data = self.prefill_data()
        draft = data["draft"]
        self.assertEqual([(s["reps"], s["rpe"]) for s in self.bench(draft)["sets"]], [(None, None)] * 3)
        self.assertEqual([(s["reps"], s["value"], s["rpe"]) for s in self.squat(draft)["sets"]], [(5, 100, None)] * 3)
        [reps] = self.asks(data, "db_bench_press", "reps")
        self.assertEqual((reps["sets"], reps["prescribed"]), ([1, 2, 3], {"start": 8, "end": 10}))
        self.assertIn("8–10", reps["message"])
        [effort] = self.asks(data, "db_bench_press", "rpe")
        self.assertEqual((effort["sets"], effort["prescribed"]), ([1, 2, 3], 8))
        [squat_effort] = self.asks(data, "bb_back_squat", "rpe")
        self.assertEqual(squat_effort["prescribed"], 7)
        self.assertIn("never the target", squat_effort["message"])
        [as_written] = self.asks(data, "bb_back_squat", "as_written")
        self.assertEqual((as_written["sets"], as_written["prescribed"]), ([1, 2, 3], ["reps", "load"]))
        [bench_load] = self.asks(data, "db_bench_press", "as_written")
        self.assertEqual((bench_load["sets"], bench_load["prescribed"]), ([1, 2, 3], ["load"]))
        self.assertEqual(self.asks(data, "bb_back_squat", "reps"), [])
        self.assertEqual([a for a in data["ask"] if a["field"] == "value"], [])

    def choose_the_squat_load(self):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(path)
        session = next(s for s in doc["sessions"] if s["session_id"] == "session-a")
        squat = next(e for e in session["exercises"] if e["exercise_id"] == "bb_back_squat")
        for set_ in squat["sets"]:
            if set_["type"] != "warmup":
                set_["load"] = None
        write_json(path, doc)

    def test_a_choose_the_load_set_asks_for_the_load_instead_of_claiming_it_is_prefilled(self):
        self.choose_the_squat_load()
        data = self.prefill_data()
        self.assertEqual([(s["reps"], s["value"]) for s in self.squat(data["draft"])["sets"]], [(5, None)] * 3)
        [load] = self.asks(data, "bb_back_squat", "value")
        self.assertEqual((load["sets"], load["prescribed"]), ([1, 2, 3], None))
        self.assertIn("choose the load", load["message"])
        [as_written] = self.asks(data, "bb_back_squat", "as_written")
        self.assertEqual(as_written["prescribed"], ["reps"])
        self.assertNotIn("load", as_written["message"])

    def test_a_bodyweight_choose_the_load_set_asks_for_the_added_load(self):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(path)
        session = next(s for s in doc["sessions"] if s["session_id"] == "session-b")
        pull_up = next(e for e in session["exercises"] if e["exercise_id"] == "pull_up")
        for set_ in pull_up["sets"]:
            set_["load"] = None
        write_json(path, doc)
        data = self.coach("log", "prefill", "--session", "session-b", "--date", "2026-10-12")["data"]
        [load] = self.asks(data, "pull_up", "value")
        self.assertIn("added load", load["message"])

    def test_a_loaded_set_logged_without_a_load_is_accepted_with_a_warning(self):
        self.choose_the_squat_load()
        envelope = self.add(self.filled())
        self.assertTrue(envelope["data"]["written"])
        [warning] = [w for w in envelope["warnings"] if w.startswith("load_unknown")]
        self.assertIn("Back Squat", warning)
        self.assertIn("sets 1–3", warning)
        filled = self.filled()
        for set_ in self.squat(filled)["sets"]:
            set_["value"] = 90
        envelope = self.add(filled, "--again")
        self.assertEqual([w for w in envelope["warnings"] if w.startswith("load_unknown")], [])

    def make_the_last_squat_set_a_rep_out(self):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(path)
        session = next(s for s in doc["sessions"] if s["session_id"] == "session-a")
        squat = next(e for e in session["exercises"] if e["exercise_id"] == "bb_back_squat")
        squat["sets"][-1].update(rep_out=True, rpe=9)
        write_json(path, doc)

    def test_a_rep_out_set_asks_for_the_reps_done_instead_of_prefilling_its_minimum(self):
        self.make_the_last_squat_set_a_rep_out()
        data = self.prefill_data()
        self.assertEqual([(s["reps"], s["value"]) for s in self.squat(data["draft"])["sets"]],
                         [(5, 100), (5, 100), (None, 100)])
        [reps] = self.asks(data, "bb_back_squat", "reps")
        self.assertEqual((reps["sets"], reps["prescribed"]), ([3], {"at_least": 5}))
        self.assertIn("at least 5", reps["message"])
        as_written = {tuple(a["sets"]): a["prescribed"] for a in self.asks(data, "bb_back_squat", "as_written")}
        self.assertEqual(as_written, {(1, 2): ["reps", "load"], (3,): ["load"]})
        stop = next(a for a in self.asks(data, "bb_back_squat", "rpe") if a["sets"] == [3])
        self.assertEqual(stop["prescribed"], 9)
        self.assertIn("stop at 9", stop["message"])
        self.assertNotIn("target", stop["message"])

        envelope = self.add(data["draft"], expect=1)
        self.assertIn("at least 5", envelope["error"]["message"])
        filled = self.filled()
        self.squat(filled)["sets"][2]["reps"] = 7
        self.add(filled)
        self.assertEqual([s["reps"] for s in self.squat(self.log_lines()[-1])["sets"]], [5, 5, 7])

    def test_an_unchanged_ranged_draft_cannot_be_recorded(self):
        before = (self.root / LOG).read_bytes()
        envelope = self.add(self.prefill(), expect=1)
        self.assertIn("8–10", envelope["error"]["message"])
        self.assertEqual((self.root / LOG).read_bytes(), before)
        self.assertFalse((self.root / "data" / "history").exists())

    def test_squat_as_written_with_unknown_effort_stays_null_and_warns(self):
        def bench_reported(draft):
            for set_, reps, rpe in zip(self.bench(draft)["sets"], (10, 9, 8), (8, 8.5, 9)):
                set_.update(reps=reps, rpe=rpe)

        draft = self.prefill()
        bench_reported(draft)
        envelope = self.add(draft)
        line = self.log_lines()[-1]
        squat, bench = self.squat(line), self.bench(line)
        self.assertEqual([(s["reps"], s["value"], s["rpe"]) for s in squat["sets"]], [(5, 100, None)] * 3)
        self.assertEqual([(s["reps"], s["value"], s["rpe"]) for s in bench["sets"]],
                         [(10, 25, 8), (9, 25, 8.5), (8, 25, 9)])
        [warning] = [w for w in envelope["warnings"] if w.startswith("rpe_unknown")]
        self.assertIn("Back Squat", warning)
        self.assertIn("sets 1–3", warning)
        self.assertNotIn("Bench", warning)

    def test_valid_reps_and_loads_without_any_effort_are_accepted_with_a_warning(self):
        draft = self.prefill()
        for set_, reps in zip(self.bench(draft)["sets"], (10, 9, 8)):
            set_["reps"] = reps
        envelope = self.add(draft)
        self.assertTrue(envelope["data"]["written"])
        warnings = [w for w in envelope["warnings"] if w.startswith("rpe_unknown")]
        self.assertEqual(len(warnings), 2, warnings)
        self.assertTrue(all(s["rpe"] is None for e in self.log_lines()[-1]["exercises"] for s in e["sets"]))


TUESDAY = "2026-10-13T18:00:00Z"
SUNDAY = "2026-10-18T18:00:00Z"
MONDAY_A = "manual:2026-10-12-session-a-1"


class ImmediateStatusTest(NoHevyCase):
    """A fresh nohevy copy: no data/history yet, and the log holds two earlier weeks."""

    now = TUESDAY

    def log_monday(self, *extra, now=None, expect=0):
        draft = self.filled()
        return self.coach("log", "add", "--input", self.write_input(draft), *extra, now=now, expect=expect)

    def dashboard_row(self):
        self.coach("pages", "render")
        text = (self.root / "README.md").read_text(encoding="utf-8")
        return next(line for line in text.splitlines() if line.startswith("| Mon 12 | Session A"))

    def block_week(self):
        data = self.coach("block", "close", "--week", "2026-W42", "--dry-run", now=SUNDAY)["data"]
        return data["weeks"][0], data["deep_review"]

    def history_files(self):
        directory = self.root / "data" / "history"
        return {p.name: p.read_bytes() for p in directory.glob("*.json")} if directory.exists() else {}

    def test_a_logged_session_shows_as_completed_without_a_separate_sync(self):
        self.assertTrue(self.dashboard_row().endswith("| ✗ |"))
        data = self.log_monday()["data"]
        self.assertTrue(data["history"]["synced"])
        self.assertIn(MONDAY_A, data["history"]["added"])
        self.assertTrue(self.dashboard_row().endswith("| ✔ |"))
        week, _ = self.block_week()
        self.assertEqual((week["planned"], week["trained"]), (2, 1))

    def test_the_sunday_review_reads_the_logged_session_without_a_separate_sync(self):
        def sunday_card():
            envelope = self.coach("checkin", "prepare", now=SUNDAY)
            card = envelope["data"]["card"]
            return card["sessions"]["trained_core"], card["unsynced"], envelope["warnings"]

        trained, _, _ = sunday_card()
        self.log_monday()
        trained_after, unsynced, warnings = sunday_card()
        self.assertEqual((trained_after, unsynced), (trained + 1, 0))
        self.assertFalse(any("history sync" in w for w in warnings), warnings)
        week, _ = self.block_week()
        self.assertEqual(week["trained"], 1)

    def test_the_live_check_in_read_agrees_with_the_stored_read(self):
        self.log_monday()
        stored = self.coach("stats", "adherence", "--overlay", WEEKLY)["data"]["sessions"]
        live = self.coach("stats", "adherence", "--overlay", WEEKLY, "--include-unsynced")["data"]["sessions"]
        self.assertEqual([(s["session_id"], s["status"], s["workout_id"]) for s in stored],
                         [(s["session_id"], s["status"], s["workout_id"]) for s in live])

    def test_a_later_sync_and_rerender_credit_the_workout_once(self):
        self.log_monday()
        self.dashboard_row()
        pages = {name: (self.root / name).read_bytes() for name in ("README.md", "this-week.md")}
        data = self.coach("history", "sync")["data"]
        self.assertEqual((data["added"], data["updated"], data["removed"]), ([], [], []))
        report = self.coach("pages", "render")["data"]["pages"]
        self.assertFalse(any(p["changed"] for p in report), report)
        self.assertEqual({name: (self.root / name).read_bytes() for name in pages}, pages)
        rows = self.coach("stats", "adherence", "--overlay", WEEKLY, "--include-unsynced")["data"]
        self.assertEqual([w["workout_id"] for w in rows["extra"]], [])
        week, _ = self.block_week()
        self.assertEqual(week["trained"], 1)

    def test_a_void_shows_the_session_missed_again(self):
        self.log_monday()
        data = self.coach("log", "void", MONDAY_A, "--reason", "wrong day")["data"]
        self.assertEqual(data["history"]["removed"], [MONDAY_A])
        self.assertTrue(self.dashboard_row().endswith("| ✗ |"))
        week, _ = self.block_week()
        self.assertEqual(week["trained"], 0)

    def test_a_correction_replaces_the_credit(self):
        self.log_monday()
        self.coach("log", "void", MONDAY_A, "--reason", "bench reps were wrong")
        self.log_monday()
        workouts = self.coach("history", "show", "--since", "2026-10-12")["data"]["workouts"]
        self.assertEqual([w["workout_id"] for w in workouts], ["manual:2026-10-12-session-a-2"])
        self.assertTrue(self.dashboard_row().endswith("| ✔ |"))

    def test_a_stale_stored_copy_does_not_resurrect_a_voided_workout(self):
        self.log_monday()
        void = {"schema_version": 1, "kind": "void", "id": MONDAY_A, "logged_at": TUESDAY, "reason": "stale copy"}
        with open(self.root / LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(void) + "\n")
        live = self.coach("history", "show", "--since", "2026-10-12", "--include-unsynced")["data"]["workouts"]
        self.assertEqual(live, [])
        rows = self.coach("stats", "adherence", "--overlay", WEEKLY, "--include-unsynced")["data"]["sessions"]
        self.assertNotEqual(next(s for s in rows if s["session_id"] == "session-a")["status"], "trained")

    def test_dry_run_and_invalid_input_write_no_log_history_or_pages(self):
        log_before, history_before = (self.root / LOG).read_bytes(), self.history_files()
        data = self.log_monday("--dry-run")["data"]
        self.assertIsNone(data["history"])

        def null_reps(draft):
            self.bench(draft)["sets"][0]["reps"] = None

        self.add(self.filled(null_reps), expect=1)
        self.assertEqual((self.root / LOG).read_bytes(), log_before)
        self.assertEqual(self.history_files(), history_before)
        self.assertFalse((self.root / "README.md").exists())

    def test_a_failed_sync_reports_the_incomplete_state_and_the_next_step(self):
        history_dir = self.root / "data" / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "2026-09.json").write_text("{not json", encoding="utf-8")
        envelope = self.log_monday()
        data = envelope["data"]
        self.assertTrue(data["written"])
        self.assertEqual(self.log_lines()[-1]["id"], MONDAY_A)
        self.assertFalse(data["history"]["synced"])
        self.assertIn("history sync", data["history"]["next_step"])
        [warning] = [w for w in envelope["warnings"] if w.startswith("history_not_synced")]
        self.assertIn(MONDAY_A, warning)
        self.assertIn("python3 -m coach history sync", warning)
        self.assertIn("do not repeat", warning)

    def test_an_as_of_read_keeps_its_cutoff(self):
        self.log_monday()
        from coach import history, stats
        from datetime import datetime, timezone

        sunday_before = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)
        for unsynced in (False, True):
            with self.subTest(include_unsynced=unsynced):
                found = history.workouts(self.root, include_unsynced=unsynced, as_of=sunday_before)
                self.assertNotIn(MONDAY_A, [w["workout_id"] for w in found])
                rows = stats.adherence(self.root, span=("2026-10-12", "2026-10-18"), include_unsynced=unsynced,
                                       as_of=sunday_before)["sessions"]
                self.assertTrue(all(r["status"] != "trained" for r in rows), rows)


class ManualLogCheckTest(NoHevyCase):
    def check(self, root=None, expect=0):
        code, envelope, stderr = run_cli(["--root", str(root or self.root), "check", "--only", "manual_log_valid"],
                                         env={"COACH_NOW": self.now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"]["results"]

    def test_the_nohevy_log_passes(self):
        self.assertEqual([r["status"] for r in self.check()], ["pass"])

    def test_no_log_skips(self):
        self.assertEqual([r["status"] for r in self.check(VALID)], ["skip"])

    def test_the_invalid_fixture_fails_once_per_problem(self):
        results = self.check(INSTANCES / "manual-log-invalid", expect=1)
        self.assertTrue(all(r["status"] == "fail" for r in results))
        messages = " ".join(r["message"] for r in results)
        for expected in ("no_such_lift", "manual:2026-09-21-session-a-1", "line 3", "session-z", "twice"):
            self.assertIn(expected, messages)
        self.assertTrue(all(r["path"] == "data/log/workouts.jsonl" for r in results))

    def test_a_line_with_an_impossible_date_fails(self):
        line = dict(self.log_lines()[0], id="manual:2026-10-32-session-a-1", date="2026-10-32", overlay_id=WEEKLY)
        with open(self.root / LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
        results = self.check(expect=1)
        self.assertEqual([r["status"] for r in results], ["fail"])
        self.assertIn("line 3: $.date: '2026-10-32' is not a real date", results[0]["message"])

    def test_a_line_that_is_not_json_fails(self):
        with open(self.root / LOG, "a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        results = self.check(expect=1)
        self.assertIn("line 3", results[0]["message"])


class HevyOffTest(NoHevyCase):
    now = "2026-10-11T18:00:00Z"

    def test_routines_push_exits_5_naming_hevy_enabled(self):
        envelope = self.coach("routines", "push", "--overlay", WEEKLY, "--dry-run", expect=5)
        self.assertIn("[hevy] enabled", envelope["error"]["message"])

    def test_check_on_the_nohevy_fixture_has_no_fail(self):
        code, envelope, stderr = run_cli(["--root", str(NOHEVY), "check"], env={"COACH_NOW": self.now})
        failed = [r for r in envelope["data"]["results"] if r["status"] == "fail"]
        self.assertEqual(failed, [], stderr)
        self.assertEqual(code, 0)

    def test_hevy_checks_skip(self):
        ids = "hevy_cache_age,overlay_hevy_drift,dangling_routine_ids"
        code, envelope, _ = run_cli(["--root", str(self.root), "check", "--only", ids], env={"COACH_NOW": self.now})
        self.assertEqual({r["id"]: r["status"] for r in envelope["data"]["results"]},
                         {"hevy_cache_age": "skip", "overlay_hevy_drift": "skip", "dangling_routine_ids": "skip"})


if __name__ == "__main__":
    unittest.main()
