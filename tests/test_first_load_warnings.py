"""First-load warnings: a `no_data` flag retires once its own line has its loads, and opens again without them
(contract C24)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import first_loads
from tests.support import INSTANCES, run_cli
from tests.support.skills import flat, step_text

SUNDAY = "2026-10-18T19:00:00Z"
TUESDAY = "2026-10-20T07:00:00Z"
WEEKLY = "2026-10-19-weekly"
MONDAY, WEDNESDAY = "2026-10-19", "2026-10-21"
SQUAT = ("--session", "session-a", "--exercise", "bb_back_squat")
LEFT_FOR_THE_COACH = "left for the coach to set"


class FirstLoadCase(unittest.TestCase):
    """The nohevy instance with no history, no overlays and no start load for the squat."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "instance"
        shutil.copytree(INSTANCES / "nohevy", self.root)
        for found in (self.root / "data" / "overlays").glob("*.json"):
            found.unlink()
        (self.root / "data" / "log" / "workouts.jsonl").write_text("", encoding="utf-8")
        program = self.root / "data" / "program.json"
        doc = json.loads(program.read_text(encoding="utf-8"))
        doc["sessions"][0]["exercises"][0]["start_load"] = None
        program.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def run_coach(self, *argv, now=SUNDAY, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"] if expect == 0 else envelope

    def propose(self, *dates_, now=SUNDAY, kind=()):
        if not dates_:
            return self.run_coach("propose", "week", "--week", "2026-W43", *kind, now=now)
        plan = self.root / ".coach" / "plans" / "plan.json"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(json.dumps({"sessions": [{"date": d, "session_id": "session-a"} for d in dates_]}),
                        encoding="utf-8")
        return self.run_coach("propose", "week", "--week", "2026-W43", *kind, "--plan", str(plan), now=now)

    def override(self, *change, proposal=WEEKLY, now=SUNDAY, expect=0, exercise=SQUAT):
        return self.run_coach("propose", "override", "--proposal", proposal, *exercise, *change,
                              "--reason", "first load agreed with the athlete", now=now, expect=expect)

    def first_loads(self, found):
        return [f for f in found if f["code"] == "no_data" and f["exercise_id"] == "bb_back_squat"]

    def draft(self, proposal=WEEKLY):
        return json.loads((self.root / ".coach" / "proposals" / f"{proposal}.json").read_text(encoding="utf-8"))


class RetireTest(FirstLoadCase):
    def test_an_override_with_the_load_retires_the_warning_and_the_record_and_watch_drop_it(self):
        proposed = self.propose()
        [flag] = self.first_loads(proposed["overlay"]["flags"])
        self.assertEqual(flag["message"], f"Back Squat (Barbell) on {MONDAY}: no usable exposure and no start load, "
                                          f"so the load is {LEFT_FOR_THE_COACH}")
        self.assertFalse(flag["resolved"])
        squat = next(r for r in proposed["lines"] if r["exercise_id"] == "bb_back_squat")
        self.assertIn("no_data", squat["flags"])
        note = self.draft()["sessions"][0]["exercises"][0]["target_note"]

        [flag] = self.first_loads(self.override("--load", "60")["flags"])
        self.assertEqual((flag["resolved"], flag["resolution"]),
                         (True, f"first load set: 60 on {MONDAY}, not yet trained"))
        self.assertEqual(self.draft()["sessions"][0]["exercises"][0]["target_note"], note)
        squat = next(r for r in self.run_coach("propose", "show", WEEKLY)["lines"]
                     if r["exercise_id"] == "bb_back_squat")
        self.assertNotIn("no_data", squat["flags"])

        doc = self.run_coach("propose", "finalize", "--proposal", WEEKLY)["overlay"]
        self.assertTrue(self.first_loads(doc["flags"])[0]["resolved"])
        self.run_coach("overlay", "approve", WEEKLY)
        region = self.run_coach("overlay", "render", WEEKLY)["text"]
        self.assertNotIn(LEFT_FOR_THE_COACH, region)
        self.assertIn(f"first load set: 60 on {MONDAY}, not yet trained", region)
        brief = self.run_coach("pages", "show", "brief")["text"]
        self.assertNotIn(LEFT_FOR_THE_COACH, brief)
        dashboard = self.run_coach("pages", "show", "dashboard")["text"]
        self.assertIn("Open flags: none", dashboard)

    def test_a_retired_line_is_checked_like_any_other(self):
        self.propose()
        found = self.override("--load", "61")["flags"]
        self.assertTrue(self.first_loads(found)[0]["resolved"])
        self.assertIn("load_unrepresentable", [f["code"] for f in found if f["exercise_id"] == "bb_back_squat"])


class OccurrenceTest(FirstLoadCase):
    def test_each_date_has_its_own_warning_and_a_dated_override_retires_only_its_own(self):
        proposed = self.propose(MONDAY, WEDNESDAY)
        messages = [f["message"] for f in self.first_loads(proposed["overlay"]["flags"])]
        self.assertEqual([m.split(":")[0] for m in messages],
                         [f"Back Squat (Barbell) on {MONDAY}", f"Back Squat (Barbell) on {WEDNESDAY}"])

        found = self.first_loads(self.override("--load", "60", "--date", MONDAY)["flags"])
        self.assertEqual([(f["message"].split(":")[0][-10:], f["resolved"]) for f in found],
                         [(MONDAY, True), (WEDNESDAY, False)])
        rows = {r["date"]: r["flags"] for r in self.run_coach("propose", "show", WEEKLY)["lines"]
                if r["exercise_id"] == "bb_back_squat"}
        self.assertEqual(("no_data" in rows[MONDAY], "no_data" in rows[WEDNESDAY]), (False, True))

        found = self.first_loads(self.override("--load", "60")["flags"])
        self.assertEqual([f["resolved"] for f in found], [True, True])
        self.assertEqual(found[1]["resolution"], f"first load set: 60 on {WEDNESDAY}, not yet trained")

    def test_a_date_the_slot_does_not_have_is_refused(self):
        self.propose(MONDAY, WEDNESDAY)
        self.override("--load", "60", "--date", "2026-10-20", expect=1)
        self.override("--load", "60", "--date", MONDAY, "--standing", expect=2)


class StillOpenTest(FirstLoadCase):
    def setUp(self):
        super().setUp()
        self.propose()

    def open_squat(self, found):
        [flag] = self.first_loads(found)
        return not flag["resolved"] and flag["resolution"] is None

    def test_an_override_of_another_exercise_leaves_it_open(self):
        bench = ("--session", "session-a", "--exercise", "db_bench_press")
        self.assertTrue(self.open_squat(self.override("--load", "20", exercise=bench)["flags"]))

    def test_a_refused_override_changes_nothing(self):
        before = self.draft()
        self.override("--sets", "3x35s rpe7", expect=1)
        self.assertEqual(self.draft(), before)
        self.assertTrue(self.open_squat(before["flags"]))

    def test_a_partly_loaded_line_stays_open(self):
        self.assertTrue(self.open_squat(self.override("--sets", "1x8@60 rpe7, 2x8 rpe7")["flags"]))
        doc = self.run_coach("propose", "finalize", "--proposal", WEEKLY)["overlay"]
        self.assertTrue(self.open_squat(doc["flags"]))

    def test_removing_the_load_opens_it_again(self):
        self.override("--load", "60")
        self.assertTrue(self.open_squat(self.override("--sets", "3x8 rpe7")["flags"]))

    def test_a_resolution_the_coach_wrote_stays(self):
        [index] = [i for i, f in enumerate(self.draft()["flags"]) if f["code"] == "no_data"]
        self.run_coach("propose", "resolve", "--proposal", WEEKLY, "--flag", str(index), "--resolution",
                       "the athlete works up to a top set on the day")
        found = self.first_loads(self.override("--load", "20", exercise=("--session", "session-a", "--exercise",
                                                                          "db_bench_press"))["flags"])
        self.assertEqual(found[0]["resolution"], "the athlete works up to a top set on the day")


class RebuildTest(FirstLoadCase):
    def test_a_rebuild_keeps_the_retirement_and_reopens_a_stale_one(self):
        self.propose()
        self.override("--load", "60")
        rebuilt = self.run_coach("propose", "rebuild", "--proposal", WEEKLY)
        self.assertEqual(rebuilt["resolutions_kept"], 0)
        [flag] = self.first_loads(self.draft()["flags"])
        self.assertTrue(first_loads.is_automatic(flag))

        draft_path = self.root / ".coach" / "proposals" / f"{WEEKLY}.json"
        self.run_coach("propose", "discard", "--proposal", WEEKLY)
        self.propose()
        draft = self.draft()
        for found in self.first_loads(draft["flags"]):
            found.update(resolved=True, resolution=flag["resolution"])
        draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        self.run_coach("propose", "rebuild", "--proposal", WEEKLY)
        [flag] = self.first_loads(self.draft()["flags"])
        self.assertEqual((flag["resolved"], flag["resolution"]), (False, None))

    def test_a_midweek_run_keeping_the_agreed_first_load_raises_no_new_warning(self):
        self.propose()
        self.override("--load", "60")
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)
        self.run_coach("overlay", "approve", WEEKLY)
        midweek = self.propose("2026-10-22", now=TUESDAY, kind=("--kind", "midweek"))
        self.assertEqual(self.first_loads(midweek["overlay"]["flags"]), [])
        self.assertIn("override_kept", [f["code"] for f in midweek["overlay"]["flags"]
                                        if f["exercise_id"] == "bb_back_squat"])


class MessageTest(unittest.TestCase):
    def test_an_undated_flag_stands_for_every_line_of_its_slot(self):
        line = {"exercise_id": "bb_back_squat", "load_mode": "total", "sets": [{"type": "normal", "load": None}]}
        sessions = [{"session_id": "session-a", "date": day, "exercises": [line]} for day in (MONDAY, WEDNESDAY)]
        flag = {"code": "no_data", "severity": "warn", "session_id": "session-a", "exercise_id": "bb_back_squat",
                "message": "Back Squat: no usable exposure", "resolved": False, "resolution": None}
        self.assertEqual([s["date"] for s, _ in first_loads.occurrences(flag, sessions)], [MONDAY, WEDNESDAY])
        dated = dict(flag, message=first_loads.message("Back Squat", WEDNESDAY, "no usable exposure"))
        self.assertEqual([s["date"] for s, _ in first_loads.occurrences(dated, sessions)], [WEDNESDAY])


class GuidanceTest(unittest.TestCase):
    def test_program_week_sets_a_first_load_per_day_and_lets_the_warning_retire(self):
        compute = flat(step_text("program-week", "compute.md"))
        for phrase in ("`no_data` (set the first load with the athlete in step 3; it retires once that day's line "
                       "has loads)", "`--date <day>` changes only that day's line"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, compute)


if __name__ == "__main__":
    unittest.main()
