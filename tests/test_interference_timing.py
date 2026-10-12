"""Session and activity timing through every interference check: planned runs, proposed and logged lifting, and the
one-off weeks a coach builds (contract C10, C29, C30, C46, C51)."""

import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from coach import overlay, timing
from coach.activity.records import utc_text
from coach.cardio import Bout
from coach.dates import Span
from coach.plugins import base
from coach.plugins.interference import quality_before_heavy_lower, same_day
from tests.support import FIXTURES, INSTANCES, run_cli

INTERFERENCE = INSTANCES / "interference"
NOHEVY = INSTANCES / "nohevy"
DRAFT_KG = FIXTURES / "overlay" / "draft-kg.json"
NOW = "2026-10-11T18:00:00Z"
SAME_DAY = {"min_gap_hours": 6, "lift_first": True}
HEAVY = {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6}
UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")


def lift(start, minutes=60, day=None, ref="lift"):
    return Bout(day or start.date(), start, None, "lifting", "planned", ref, "session-a", minutes, None, False, None)


def run(start, minutes=40, day=None, ref="run"):
    return Bout(day or start.date(), start, None, "run", "planned", ref, None, minutes, None, True, "planned")


def judge(rule, params, *bouts, heavy=("lift",)):
    ctx = base.InterferenceContext("proposal", Span(date(2026, 1, 1), date(2026, 12, 31)), params, tuple(bouts),
                                   frozenset(heavy), {"lift": "Session A", "run": "Tempo"})
    return rule.evaluate(ctx)


class QualityBeforeHeavyLowerTimingTest(unittest.TestCase):
    def test_a_morning_run_and_the_next_evenings_squats_are_more_than_24_hours_apart(self):
        found = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 10, 11, 7, tzinfo=UTC)),
                      lift(datetime(2026, 10, 12, 18, tzinfo=UTC)))
        self.assertEqual(found, [])

    def test_an_evening_run_ending_21_hours_before_is_a_warn_with_the_measured_gap(self):
        [flag] = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 10, 11, 20, tzinfo=UTC)),
                       lift(datetime(2026, 10, 12, 18, tzinfo=UTC)))
        self.assertEqual((flag["code"], flag["severity"]), ("collision", "warn"))
        self.assertIn("ended 21.3 h before", flag["message"])
        self.assertIn("a cautious coaching heuristic", flag["message"])
        self.assertNotIn("unknown", flag["message"])

    def test_each_missing_start_or_duration_says_the_gap_is_unknown(self):
        cases = {
            "no start time for planned Session A": (run(datetime(2026, 10, 11, 20, tzinfo=UTC)),
                                                    lift(None, day=date(2026, 10, 12))),
            "no start time or duration for planned run": (run(None, None, day=date(2026, 10, 11)),
                                                          lift(datetime(2026, 10, 12, 18, tzinfo=UTC))),
            "no duration for planned run": (run(datetime(2026, 10, 11, 20, tzinfo=UTC), None),
                                            lift(datetime(2026, 10, 12, 18, tzinfo=UTC))),
        }
        for missing, bouts in cases.items():
            with self.subTest(missing=missing):
                [flag] = judge(quality_before_heavy_lower, HEAVY, *bouts)
                self.assertIn("The gap in hours is unknown", flag["message"])
                self.assertIn(missing, flag["message"])
                self.assertIn("may or may not be under 24 h", flag["message"])
                self.assertIn("Keep quality activities at least 24 h before heavy lower-body lifting",
                              flag["message"])
                self.assertNotIn("ended", flag["message"])

    def test_offsets_midnight_and_daylight_saving_use_elapsed_time(self):
        plus_two = timezone(timedelta(hours=2))
        [flag] = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 10, 11, 17, 30, tzinfo=UTC), 30),
                       lift(datetime(2026, 10, 12, 19, 30, tzinfo=plus_two)))
        self.assertIn("ended 23.5 h before", flag["message"])
        [flag] = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 10, 11, 18, 30, tzinfo=UTC), 30),
                       lift(datetime(2026, 10, 12, 20, 0, tzinfo=plus_two)))
        self.assertIn("ended 23 h before", flag["message"])
        [flag] = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 10, 11, 23, 10, tzinfo=UTC), 40),
                       lift(datetime(2026, 10, 12, 6, 0, tzinfo=UTC)))
        self.assertIn("ended 6.2 h before", flag["message"])
        # The clocks go forward on 2026-03-29: 18:30 GMT to 18:45 BST is 23.25 elapsed hours, not 24.25.
        [flag] = judge(quality_before_heavy_lower, HEAVY, run(datetime(2026, 3, 28, 17, 50, tzinfo=LONDON), 40),
                       lift(datetime(2026, 3, 29, 18, 45, tzinfo=LONDON)))
        self.assertIn("ended 23.2 h before", flag["message"])


class SameDayTimingTest(unittest.TestCase):
    def test_lift_then_run_with_a_sufficient_gap_passes(self):
        self.assertEqual(judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 7, tzinfo=UTC)),
                               run(datetime(2026, 10, 12, 14, tzinfo=UTC))), [])

    def test_lift_then_run_too_soon_is_a_warn_from_the_lifts_end(self):
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 7, tzinfo=UTC)),
                       run(datetime(2026, 10, 12, 12, tzinfo=UTC)))
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("started 4 h after", flag["message"])

    def test_run_first_is_a_warn_whatever_the_gap(self):
        [flag] = judge(same_day, SAME_DAY, run(datetime(2026, 10, 12, 6, tzinfo=UTC)),
                       lift(datetime(2026, 10, 12, 18, tzinfo=UTC)))
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("came before", flag["message"])
        self.assertIn("ending 11.3 h before it started", flag["message"])

    def test_a_late_lift_and_a_run_after_midnight_are_judged_on_elapsed_hours(self):
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 22, tzinfo=UTC), 60),
                       run(datetime(2026, 10, 13, 1, tzinfo=UTC)))
        self.assertIn("started 2 h after", flag["message"])
        self.assertEqual(judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 18, tzinfo=UTC), 60),
                               run(datetime(2026, 10, 13, 7, tzinfo=UTC))), [])

    def test_same_day_offsets_and_daylight_saving_are_elapsed(self):
        plus_one = timezone(timedelta(hours=1))
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 8, tzinfo=plus_one), 60),
                       run(datetime(2026, 10, 12, 12, tzinfo=UTC)))
        self.assertIn("started 4 h after", flag["message"])
        # 00:30 GMT plus 60 minutes ends at 02:30 BST, so a 08:00 BST run starts 5.5 h later, not 6.5 h.
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 3, 29, 0, 30, tzinfo=LONDON), 60),
                       run(datetime(2026, 3, 29, 8, 0, tzinfo=LONDON)))
        self.assertIn("started 5.5 h after", flag["message"])

    def test_missing_times_are_info_that_the_order_and_gap_are_unknown(self):
        [flag] = judge(same_day, SAME_DAY, lift(None, day=date(2026, 10, 12)),
                       run(datetime(2026, 10, 12, 18, tzinfo=UTC)))
        self.assertEqual(flag["severity"], "info")
        self.assertIn("order and gap are unknown (no start time for planned Session A (2026-10-12))", flag["message"])
        self.assertIn("lift first, keep at least 6 h between", flag["message"])

    def test_known_starts_without_a_duration_judge_what_they_can(self):
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 7, tzinfo=UTC), None),
                       run(datetime(2026, 10, 12, 10, tzinfo=UTC)))
        self.assertEqual(flag["severity"], "warn")
        [flag] = judge(same_day, SAME_DAY, lift(datetime(2026, 10, 12, 7, tzinfo=UTC), None),
                       run(datetime(2026, 10, 12, 17, tzinfo=UTC)))
        self.assertEqual(flag["severity"], "info")
        self.assertIn("unknown (no duration)", flag["message"])


class ParseStartTest(unittest.TestCase):
    def test_a_clock_time_is_local_in_the_zone_and_must_stay_on_the_date(self):
        start = timing.parse_start("07:00", "2026-10-11", LONDON)
        self.assertEqual(utc_text(start), "2026-10-11T06:00:00Z")
        self.assertEqual(utc_text(timing.parse_start("2026-10-11T07:00+02:00", "2026-10-11", LONDON)),
                         "2026-10-11T05:00:00Z")
        self.assertEqual(utc_text(timing.parse_start("2026-10-11T23:30:00Z", "2026-10-12", LONDON)),
                         "2026-10-11T23:30:00Z")
        for text, day in (("2026-10-12T07:00", "2026-10-11"), ("25:00", "2026-10-11"), ("soon", "2026-10-11")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                timing.parse_start(text, day, LONDON)


class Case(unittest.TestCase):
    base = INTERFERENCE
    now = NOW

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": self.now})
        self.assertEqual(code, expect, (argv, envelope, stderr))
        return envelope

    def data(self, *argv):
        return self.coach(*argv)["data"]

    @staticmethod
    def collisions(found):
        return [f for f in found if f["code"] == "collision"]


class PlannedStartTest(Case):
    def test_a_planned_run_keeps_its_start_and_legacy_plans_read_as_untimed(self):
        record = self.data("planned", "add", "--date", "2026-10-13", "--kind", "run", "--title", "Hills",
                           "--quality", "--duration-min", "40", "--start", "07:15")["record"]
        self.assertEqual((record["schema_version"], record["start"]), (2, "2026-10-13T07:15:00Z"))
        listed = {p["id"]: p["start"] for p in self.data("planned", "list", "--from", "2026-10-11", "--to",
                                                           "2026-10-14")["planned"]}
        self.assertEqual(listed, {"manual:2026-10-11-run-1": None, "manual:2026-10-13-run-1": "2026-10-13T07:15:00Z",
                                  "manual:2026-10-14-run-1": None})
        self.assertEqual(self.data("check", "--only", "schema_versions")["results"][0]["status"], "pass")

    def test_a_start_on_another_day_is_refused(self):
        envelope = self.coach("planned", "add", "--date", "2026-10-13", "--kind", "run", "--title", "Hills",
                              "--start", "2026-10-14T07:00", expect=1)
        self.assertIn("falls on 2026-10-14", envelope["error"]["message"])

    def test_the_same_session_is_not_planned_twice(self):
        argv = ("planned", "add", "--date", "2026-10-14", "--kind", "run", "--title", "Easy 5 km", "--distance-km",
                "5", "--description", "Zone 2")
        envelope = self.coach(*argv, expect=3)
        self.assertIn("manual:2026-10-14-run-1 already plans this session", envelope["error"]["message"])
        self.assertIn("planned void manual:2026-10-14-run-1", envelope["error"]["message"])
        self.assertTrue(self.data(*argv, "--again")["written"])


class ProposalTimingTest(Case):
    def setUp(self):
        super().setUp()
        # Unplanned, Thursday's run would reconcile as Sunday's tempo done early.
        self.data("planned", "add", "--date", "2026-10-08", "--kind", "run", "--title", "Easy 5 km",
                  "--duration-min", "40")

    def retime_tempo(self, start):
        current = [p for p in self.data("planned", "list", "--from", "2026-10-11", "--to", "2026-10-11")["planned"]]
        for plan in current:
            self.data("planned", "void", plan["id"], "--reason", "the athlete moved the tempo")
        self.data("planned", "add", "--date", "2026-10-11", "--kind", "run", "--title", "Tempo", "--quality",
                  "--duration-min", "40", "--start", start)

    def propose(self):
        return self.data("propose", "week", "--week", "2026-W42")["overlay"]["id"]

    def heavy_collisions(self, flags):
        return [f for f in self.collisions(flags) if "quality_before_heavy_lower" in f["message"]]

    def test_morning_run_and_next_evening_squats_clear_an_evening_run_collides(self):
        self.retime_tempo("07:00")
        proposal = self.propose()
        timed = self.data("propose", "time", "--proposal", proposal, "--session", "session-a", "--start", "18:00",
                          "--duration-min", "60")
        self.assertEqual((timed["start"], timed["duration_minutes"]), ("2026-10-12T18:00:00Z", 60))
        self.assertEqual(self.heavy_collisions(timed["interference"]), [])
        self.retime_tempo("20:00")
        again = self.data("propose", "time", "--proposal", proposal, "--session", "session-a", "--start", "18:00",
                          "--duration-min", "60")
        [flag] = self.heavy_collisions(again["interference"])
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("ended 21.3 h before planned Session A (2026-10-12 18:00)", flag["message"])

    def test_the_proposed_start_survives_finalize_rebuild_and_kinds(self):
        proposal = self.propose()
        self.data("propose", "time", "--proposal", proposal, "--session", "session-a", "--start", "18:00",
                  "--duration-min", "60")
        rebuilt = self.data("propose", "rebuild", "--proposal", proposal)
        session = next(s for s in rebuilt["overlay"]["sessions"] if s["session_id"] == "session-a")
        self.assertEqual((session["start"], session["duration_minutes"]), ("2026-10-12T18:00:00Z", 60))
        finalized = self.data("propose", "finalize", "--proposal", proposal)
        written = json.loads((self.root / finalized["path"]).read_text(encoding="utf-8"))
        session = next(s for s in written["sessions"] if s["session_id"] == "session-a")
        self.assertEqual((written["schema_version"], session["start"], session["duration_minutes"]),
                         (6, "2026-10-12T18:00:00Z", 60))
        for kind in ("midweek", "deload"):
            with self.subTest(kind=kind):
                draft = self.data("propose", "week", "--week", "2026-W42", "--kind", kind)["overlay"]
                self.data("propose", "time", "--proposal", draft["id"], "--session", "session-b", "--start",
                          "2026-10-15T19:00+01:00")
                shown = self.data("propose", "show", draft["id"])["overlay"]
                session = next(s for s in shown["sessions"] if s["session_id"] == "session-b")
                self.assertEqual(session["start"], "2026-10-15T18:00:00Z")

    def test_clearing_a_start_goes_back_to_the_untimed_warning(self):
        self.retime_tempo("07:00")
        proposal = self.propose()
        self.data("propose", "time", "--proposal", proposal, "--session", "session-a", "--start", "18:00")
        cleared = self.data("propose", "time", "--proposal", proposal, "--session", "session-a", "--clear")
        [flag] = self.heavy_collisions(cleared["interference"])
        self.assertIn("no start time for planned Session A", flag["message"])


class OneOffInterferenceTest(Case):
    def setUp(self):
        super().setUp()
        self.data("planned", "add", "--date", "2026-10-08", "--kind", "run", "--title", "Easy 5 km",
                  "--duration-min", "40")

    def draft(self, squat_day="2026-10-12"):
        draft = json.loads(DRAFT_KG.read_text(encoding="utf-8"))
        draft.update(kind="one_off", focus="Reshuffle: the same sessions on new days.")
        draft["sessions"][0]["date"] = squat_day
        path = self.tmp / "draft.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        return path

    def build(self, path):
        return self.data("overlay", "build", "--input", str(path))

    def test_a_reshuffle_raises_the_same_collision_as_the_ordinary_proposal_before_approval(self):
        ordinary = self.collisions(self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]["flags"])
        built = self.build(self.draft())
        found = self.collisions(built["overlay"]["flags"])
        self.assertEqual([(f["severity"], f["session_id"], f["message"]) for f in found],
                         [(f["severity"], f["session_id"], f["message"]) for f in ordinary])
        self.assertEqual(len(found), 1)
        self.assertIsNone(built["overlay"]["approval"])

    def test_rebuilding_does_not_duplicate_and_moving_the_session_clears_the_collision(self):
        first = self.build(self.draft())
        overlay_id = first["id"]
        again = json.loads(self.draft().read_text(encoding="utf-8"))
        again.update(id=overlay_id, flags=first["overlay"]["flags"])
        path = self.tmp / "again.json"
        path.write_text(json.dumps(again), encoding="utf-8")
        self.assertEqual(len(self.collisions(self.build(path)["overlay"]["flags"])), 1)
        moved = json.loads(self.draft("2026-10-13").read_text(encoding="utf-8"))
        moved.update(id=overlay_id, flags=first["overlay"]["flags"])
        path.write_text(json.dumps(moved), encoding="utf-8")
        self.assertEqual(self.collisions(self.build(path)["overlay"]["flags"]), [])

    def test_a_one_off_draft_start_is_kept_and_judged(self):
        draft = json.loads(self.draft().read_text(encoding="utf-8"))
        draft["sessions"][0].update(start="2026-10-12T18:00", duration_minutes=60)
        path = self.tmp / "timed.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        built = self.build(path)["overlay"]
        self.assertEqual(built["sessions"][0]["start"], "2026-10-12T18:00:00Z")
        [flag] = self.collisions(built["flags"])
        self.assertIn("unknown (no start time for planned run \"Tempo\" (2026-10-11))", flag["message"])


class OverlayMigrationTest(Case):
    def test_v5_overlays_gain_null_timing_and_say_they_lose_their_approval(self):
        path = self.root / "data" / "overlays" / "2026-10-12-weekly.json"
        before = json.loads(path.read_text(encoding="utf-8"))
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["schema_version"] = 5
        for session in doc["sessions"]:
            del session["start"], session["duration_minutes"]
        doc["approval"]["hash"] = overlay.approval_hash(doc)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        data = self.data("migrate", "run")
        self.assertIn("overlay/0005_session_timing", [s for row in data["files"] for s in row["steps"]])
        self.assertTrue(any("2026-10-12-weekly loses its approval" in n for n in data["notes"]), data["notes"])
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(after["sessions"], before["sessions"])
        self.assertEqual({(s["start"], s["duration_minutes"]) for s in after["sessions"]}, {(None, None)})
        self.assertTrue(self.data("overlay", "validate", "2026-10-12-weekly")["results"][0]["valid"])


class ManualWorkoutStartTest(Case):
    base = NOHEVY
    now = "2026-10-12T19:00:00Z"

    def log_session_a(self, start_time):
        draft = self.data("log", "prefill", "--session", "session-a", "--date", "2026-10-12")["draft"]
        self.assertIsNone(draft["start_time"])
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                set_["reps"] = set_["reps"] or 10
        draft.update(start_time=start_time, duration_minutes=60)
        path = self.tmp / "workout.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        return self.data("log", "add", "--input", str(path))["line"]

    def test_the_start_survives_history_sync_and_logged_interference(self):
        line = self.log_session_a("16:00")
        self.assertEqual((line["schema_version"], line["start_time"]), (2, "2026-10-12T16:00:00Z"))
        self.data("activity", "add", "--kind", "run", "--start", "2026-10-12T14:00", "--duration-min", "40",
                  "--rpe", "8", "--name", "Tempo")
        self.data("history", "sync")
        month = json.loads((self.root / "data" / "history" / "2026-10.json").read_text(encoding="utf-8"))
        workout = next(w for w in month["workouts"] if w["workout_id"] == line["id"])
        self.assertEqual((workout["start_time"], workout["end_time"]), ("2026-10-12T16:00:00Z", "2026-10-12T17:00:00Z"))
        found = self.collisions(self.data("interference", "check", "--week", "2026-W42")["flags"])
        messages = " | ".join(f["message"] for f in found)
        self.assertIn("ended 1.3 h before", messages)
        self.assertIn("came before", messages)
        self.assertNotIn("unknown", messages)

    def test_a_legacy_line_without_a_start_still_reads(self):
        legacy = "manual:2026-09-28-session-a-1"
        self.data("history", "sync")
        listed = self.data("log", "list", "--since", "2026-09-01")["workouts"]
        self.assertIn(legacy, [w["id"] for w in listed])
        month = json.loads((self.root / "data" / "history" / "2026-09.json").read_text(encoding="utf-8"))
        workout = next(w for w in month["workouts"] if w["workout_id"] == legacy)
        self.assertEqual((workout["start_time"], workout["end_time"]), (None, None))


if __name__ == "__main__":
    unittest.main()
