"""Planned sessions: the schedule rule only from the program's adoption on, and a moved session planned once (C40, C41)."""

import json
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from coach import dates, overlay
from tests.support import INSTANCES, run_cli
from tests.support.history import read_json, write_json

NOHEVY = INSTANCES / "nohevy"
WEEKLY = "2026-10-12-weekly"
SQUAT, ROW = "bb_back_squat", "db_single_arm_row"
SHIFT_TO_SAT = {"id": "a-to-sat", "session_id": "session-a", "text": None, "when": {},
                "action": {"kind": "shift", "to_weekdays": ["sat"]}}


def priority_entry(exercise_id):
    return {"exercise_id": exercise_id, "kpi": {"kind": "e1rm", "target": None, "by": None},
            "floor": {"sets": 2, "rpe": None}}


def codes(found):
    return [f["code"] for f in found]


class PlannedSessionCase(unittest.TestCase):
    """nohevy/: Session A on Mondays, B on Thursdays, Session A logged on 28 Sep and 5 Oct, adopted 11 Oct."""

    adopted = "2026-10-11"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(NOHEVY, self.root)
        self.edit("data/state.json", lambda doc: doc.update(program_adopted=self.adopted))
        self.edit("data/program.json", lambda doc: doc.update(priority=[priority_entry(SQUAT), priority_entry(ROW)]))

    def edit(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)

    def remake(self, overlay_id, created_at):
        """Rewrite an overlay as made at `created_at`, approved again."""
        path = self.root / "data" / "overlays" / f"{overlay_id}.json"
        doc = dict(read_json(path), created_at=created_at, approval=None)
        write_json(path, overlay.approve(doc, dates.parse_timestamp(created_at)))

    def drop_overlays(self):
        for path in (self.root / "data" / "overlays").glob("*.json"):
            path.unlink()

    def coach(self, *argv, now, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"]

    def plan_week(self, start):
        """A weekly overlay for the week starting `start`, copied from W42's with its dates moved."""
        doc = read_json(self.root / "data" / "overlays" / f"{WEEKLY}.json")
        shift = (dates.parse_date(start) - dates.parse_date(doc["span"]["start"])).days
        moved = lambda day: (dates.parse_date(day) + timedelta(days=shift)).isoformat()
        doc.pop("approval", None)
        doc.update(id=f"{start}-weekly", span={"start": start, "end": moved(doc["span"]["end"])},
                   created_at=f"{moved(doc['created_at'][:10])}T18:00:00Z")
        for session in doc["sessions"]:
            session["date"] = moved(session["date"])
        doc = overlay.approve(doc, dates.parse_timestamp(doc["created_at"]))
        write_json(self.root / "data" / "overlays" / f"{doc['id']}.json", doc)

    def train(self, session_id, day):
        """Log the session on `day` as prescribed: every rep range at its top, every set at its target RPE."""
        now = f"{day}T20:00:00Z"
        draft = self.coach("log", "prefill", "--session", session_id, "--date", day, now=now)["draft"]
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                set_["reps"] = set_["reps"] or 10
                set_["rpe"] = set_["rpe"] or 8
        path = self.tmp / f"{session_id}-{day}.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        self.coach("log", "add", "--input", str(path), now=now)
        self.coach("history", "sync", now=now)

    def week(self, start, now):
        return self.coach("structure", "week", "--week", start, now=now)

    def rows(self, report):
        return [(s["date"], s["session_id"], s["status"]) for s in report["sessions"]]

    def lift_weeks(self, data, exercise_id):
        lift = next(lift for lift in data["lifts"] if lift["exercise_id"] == exercise_id)
        return [(w["label"], w["planned"], w["missed"], w["unreplaced"]) for w in lift["weeks"]]


class AdoptionTest(PlannedSessionCase):
    def setUp(self):
        super().setUp()
        self.train("session-a", "2026-10-12")
        self.train("session-b", "2026-10-15")

    def test_priority_reports_only_the_weeks_since_adoption(self):
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 1, 0, 0)])
        self.assertEqual(self.lift_weeks(data, ROW), [("2026-W42", 1, 0, 0)])
        self.assertEqual(data["flags"], [])

    def test_older_workouts_stay_strength_evidence(self):
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        squat = next(lift for lift in data["lifts"] if lift["exercise_id"] == SQUAT)
        self.assertEqual(squat["kpi"]["trend"]["from"]["date"], "2026-09-28")

    def test_adherence_never_judges_weeks_before_adoption(self):
        self.plan_week("2026-10-19")
        self.train("session-a", "2026-10-19")
        self.train("session-b", "2026-10-22")
        data = self.coach("structure", "adherence", now="2026-10-25T19:00:00Z")
        self.assertEqual([(w["label"], w["planned"], w["trained"]) for w in data["weeks"]],
                         [("2026-W42", 2, 2), ("2026-W43", 2, 2)])
        self.assertEqual((data["planned"], data["trained"], data["pct"], data["insufficient_weeks"]),
                         (4, 4, 100, True))
        self.assertEqual(data["flags"], [])

    def test_a_week_before_adoption_plans_nothing(self):
        report = self.week("2026-10-05", now="2026-10-18T19:00:00Z")
        self.assertEqual((report["sessions"], report["planned"], report["trained"]), ([], 0, 0))

    def test_a_new_block_keeps_the_adoption_and_the_weeks_before_it(self):
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", "--week", "2026-10-19",
                   "--reason", "travel", now="2026-10-18T19:00:00Z")
        closed = self.coach("block", "close", "--week", "2026-W43", now="2026-10-25T19:00:00Z")
        self.assertEqual(closed["ended"], ["b-0001"])
        self.assertEqual(closed["block"]["started"], "2026-10-26")
        self.plan_week("2026-10-26")
        self.train("session-a", "2026-10-26")
        self.train("session-b", "2026-10-29")
        self.assertEqual(read_json(self.root / "data/state.json")["program_adopted"], self.adopted)
        data = self.coach("structure", "adherence", now="2026-11-01T19:00:00Z")
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W42", "2026-W44"])
        self.assertEqual([w["label"] for w in data["skipped"]], ["2026-W43"])


class MidweekAdoptionTest(PlannedSessionCase):
    """A first program adopted on Wed 14 Oct, its opening week's overlay written that day."""

    adopted = "2026-10-14"

    def setUp(self):
        super().setUp()
        self.remake(WEEKLY, f"{self.adopted}T09:00:00Z")

    def test_the_adoption_week_plans_only_the_days_from_adoption(self):
        self.train("session-b", "2026-10-15")
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained")])
        self.assertEqual((report["planned"], report["trained"]), (1, 1))
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 0, 0, 0)])
        self.assertEqual(data["flags"], [])
        card = self.coach("checkin", "prepare", "--until", "2026-10-18", now="2026-10-18T19:00:00Z")["card"]
        self.assertEqual((card["sessions"]["planned_core"], card["sessions"]["trained_core"]), (1, 1))

    def test_the_schedule_rule_plans_only_the_days_from_adoption(self):
        self.train("session-b", "2026-10-15")
        self.drop_overlays()
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained")])
        self.assertEqual((report["planned"], report["trained"]), (1, 1))

    def test_an_adoption_week_with_no_session_left_is_not_judged(self):
        self.edit("data/state.json", lambda doc: doc.update(program_adopted="2026-10-16"))
        self.remake(WEEKLY, "2026-10-16T09:00:00Z")
        self.plan_week("2026-10-19")
        self.train("session-a", "2026-10-19")
        self.train("session-b", "2026-10-22")
        data = self.coach("structure", "adherence", now="2026-10-25T19:00:00Z")
        self.assertEqual([(w["label"], w["planned"]) for w in data["weeks"]], [("2026-W43", 2)])
        priority = self.coach("structure", "priority", now="2026-10-25T19:00:00Z")
        self.assertEqual([row[0] for row in self.lift_weeks(priority, SQUAT)], ["2026-W43"])

    def test_coach_led_sessions_start_at_adoption(self):
        self.edit("data/program.json", lambda doc: doc.update(external_sessions=[
            {"id": "pt-mon", "title": "PT", "weekday": "mon", "estimated_sets": {}}]))
        self.plan_week("2026-10-19")
        adoption_week = self.week("2026-10-12", now="2026-10-25T19:00:00Z")
        next_week = self.week("2026-10-19", now="2026-10-25T19:00:00Z")
        self.assertEqual([s.get("external_id") for s in adoption_week["sessions"]], [None])
        self.assertEqual([(s["date"], s["external_id"]) for s in next_week["sessions"] if s.get("external_id")],
                         [("2026-10-19", "pt-mon")])


class SundayWeekAdoptionTest(PlannedSessionCase):
    """The midweek adoption with weeks starting on Sunday."""

    adopted = "2026-10-14"

    def setUp(self):
        super().setUp()
        self.remake(WEEKLY, f"{self.adopted}T09:00:00Z")
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('week_starts = "monday"', 'week_starts = "sunday"'),
                        encoding="utf-8")

    def test_the_adoption_week_plans_only_the_days_from_adoption(self):
        self.train("session-b", "2026-10-15")
        report = self.week("2026-10-11", now="2026-10-18T19:00:00Z")
        self.assertEqual((report["week"], report["span"]["end"]), ("2026-10-11", "2026-10-17"))
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained")])
        self.assertEqual((report["planned"], report["trained"]), (1, 1))
        data = self.coach("structure", "adherence", now="2026-10-18T19:00:00Z")
        self.assertEqual([(w["week"], w["planned"], w["trained"]) for w in data["weeks"]], [("2026-10-11", 1, 1)])


class ReplacedProgramTest(PlannedSessionCase):
    """The program was replaced on Mon 19 Oct, after W42 was trained under the old program's overlay."""

    def setUp(self):
        super().setUp()
        self.train("session-a", "2026-10-12")
        self.train("session-b", "2026-10-15")
        self.edit("data/state.json", lambda doc: doc.update(program_adopted="2026-10-19"))
        self.plan_week("2026-10-19")
        self.train("session-a", "2026-10-19")
        self.train("session-b", "2026-10-22")

    def test_the_old_programs_overlay_weeks_still_count(self):
        data = self.coach("structure", "adherence", now="2026-10-25T19:00:00Z")
        self.assertEqual([(w["label"], w["planned"], w["trained"]) for w in data["weeks"]],
                         [("2026-W42", 2, 2), ("2026-W43", 2, 2)])
        report = self.week("2026-10-12", now="2026-10-25T19:00:00Z")
        self.assertEqual((report["planned"], report["trained"]), (2, 2))

    def test_the_new_schedule_rule_never_reaches_back_before_the_replace(self):
        self.drop_overlays()
        report = self.week("2026-10-12", now="2026-10-25T19:00:00Z")
        self.assertEqual((report["sessions"], report["planned"]), ([], 0))


class UnrecordedAdoptionTest(PlannedSessionCase):
    """A state migrated from v4: `program_adopted` is null."""

    adopted = None

    def setUp(self):
        super().setUp()
        self.train("session-a", "2026-10-12")
        self.train("session-b", "2026-10-15")

    def block_started(self, day):
        self.edit("data/state.json", lambda doc: doc["block"].update(started=day))

    def test_the_block_start_dates_it_when_no_overlay_exists(self):
        self.drop_overlays()
        self.block_started("2026-10-12")
        self.assertEqual((self.week("2026-10-12", now="2026-10-18T19:00:00Z")["planned"],
                          self.week("2026-10-05", now="2026-10-18T19:00:00Z")["planned"]), (2, 0))
        closed = self.coach("block", "close", "--week", "2026-W42", "--dry-run", now="2026-10-18T19:00:00Z")
        self.assertEqual(closed["weeks"][-1]["class"], "hard")

    def test_the_first_overlay_dates_it_without_a_block_start(self):
        self.block_started(None)
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 1, 0, 0)])
        self.assertEqual(data["flags"], [])

    def test_the_newest_program_archive_dates_a_replaced_program(self):
        self.drop_overlays()
        for name in ("2026-09-01", "2026-10-14"):
            (self.root / "data" / "archive" / "programs" / name).mkdir(parents=True)
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained")])


class MovedSessionTest(PlannedSessionCase):
    """Session A missed on Mon 12 Oct and shifted to Sat 17 Oct by the program's rule."""

    approve = False

    def setUp(self):
        super().setUp()
        self.edit("data/program.json", lambda doc: doc.update(missed_day_rules=[SHIFT_TO_SAT]))
        applied = self.coach("missed", "apply", "--session", "session-a", "--date", "2026-10-12", "--tag", "family",
                             now="2026-10-13T08:00:00Z")
        self.moved_id = applied["overlay_id"]
        if self.approve:
            path = self.root / "data" / "overlays" / f"{self.moved_id}.json"
            write_json(path, overlay.approve(read_json(path), dates.parse_timestamp("2026-10-13T08:05:00Z")))
        self.train("session-b", "2026-10-15")

    def test_the_move_wrote_a_moved_copy(self):
        doc = read_json(self.root / "data" / "overlays" / f"{self.moved_id}.json")
        self.assertIn(("2026-10-17", "session-a", "2026-10-12"),
                      [(s["date"], s["session_id"], s.get("moved_from")) for s in doc["sessions"]])
        self.assertEqual(overlay.is_approved(doc), self.approve)

    def test_a_moved_session_trained_on_its_new_day_counts_once(self):
        self.train("session-a", "2026-10-17")
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained"),
                                             ("2026-10-17", "session-a", "trained")])
        self.assertEqual(report["sessions"][1]["moved_from"], "2026-10-12")
        self.assertEqual((report["planned"], report["trained"]), (2, 2))
        closed = self.coach("block", "close", "--week", "2026-W42", "--dry-run", now="2026-10-18T19:00:00Z")
        week = closed["weeks"][-1]
        self.assertEqual((week["class"], week["planned"], week["trained"], week["as_prescribed"]), ("hard", 2, 2, 2))

    def test_the_check_in_card_counts_a_trained_move_once(self):
        self.train("session-a", "2026-10-17")
        span = self.coach("stats", "adherence", "--span", "2026-10-12..2026-10-18", now="2026-10-18T19:00:00Z")
        self.assertEqual([(s["date"], s["session_id"], s["status"]) for s in span["sessions"]],
                         [("2026-10-15", "session-b", "trained"), ("2026-10-17", "session-a", "trained")])
        card = self.coach("checkin", "prepare", "--until", "2026-10-18", now="2026-10-18T19:00:00Z")["card"]
        self.assertEqual((card["sessions"]["planned_core"], card["sessions"]["trained_core"]), (2, 2))
        self.assertNotIn("2026-10-12", [row["date"] for row in card["sessions"]["rows"]])
        missed = self.coach("checkin", "misses", "--since", "2026-10-12", "--until", "2026-10-18",
                            now="2026-10-18T19:00:00Z")
        self.assertEqual(missed["sessions_missed"], 0)

    def test_priority_and_overlay_adherence_agree_on_a_trained_move(self):
        self.train("session-a", "2026-10-17")
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 1, 0, 0)])
        self.assertEqual(data["flags"], [])
        weekly = self.coach("stats", "adherence", "--overlay", WEEKLY, now="2026-10-18T19:00:00Z")
        row = next(s for s in weekly["sessions"] if s["session_id"] == "session-a")
        self.assertEqual((row["status"], row["moved"]), ("trained", True))

    def test_an_untrained_moved_session_is_one_miss_on_its_new_day(self):
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained"),
                                             ("2026-10-17", "session-a", "missed")])
        self.assertEqual((report["planned"], report["trained"]), (2, 1))
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 1, 1, 1)])
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"])
        self.assertIn("session-a on 2026-10-17", data["flags"][0]["message"])
        moved = self.coach("stats", "adherence", "--overlay", self.moved_id, now="2026-10-18T19:00:00Z")
        self.assertEqual([(s["session_id"], s["status"]) for s in moved["sessions"]
                          if s["session_id"] == "session-a"], [("session-a", "missed")])

    def test_a_pending_move_leaves_no_miss_on_the_original_day(self):
        report = self.week("2026-10-12", now="2026-10-16T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-15", "session-b", "trained"),
                                             ("2026-10-17", "session-a", "upcoming")])
        self.assertEqual((report["planned"], report["trained"]), (1, 1))


class ApprovedMovedSessionTest(MovedSessionTest):
    approve = True


class ExtraSessionTest(PlannedSessionCase):
    def test_an_extra_session_that_moves_nothing_is_a_second_planned_session(self):
        def add_saturday_a(doc):
            monday = next(s for s in doc["sessions"] if s["session_id"] == "session-a")
            doc["sessions"].append(dict(json.loads(json.dumps(monday)), date="2026-10-17"))
            doc["approval"] = None
        self.edit(f"data/overlays/{WEEKLY}.json", add_saturday_a)
        self.train("session-b", "2026-10-15")
        self.train("session-a", "2026-10-17")
        report = self.week("2026-10-12", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.rows(report), [("2026-10-12", "session-a", "missed"),
                                             ("2026-10-15", "session-b", "trained"),
                                             ("2026-10-17", "session-a", "trained")])
        self.assertEqual((report["planned"], report["trained"]), (3, 2))
        data = self.coach("structure", "priority", now="2026-10-18T19:00:00Z")
        self.assertEqual(self.lift_weeks(data, SQUAT), [("2026-W42", 2, 1, 1)])


if __name__ == "__main__":
    unittest.main()
