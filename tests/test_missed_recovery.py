"""Recovering a missed session: the athlete's move or drop, destinations against available days, the
next-exposure route for a lift with no session left, and the status line for an unlogged session (contract C37)."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import overlay
from tests.support import INSTANCES, run_cli
from tests.support.skills import flat, step_text

NOHEVY = INSTANCES / "nohevy"
LOG = Path("data") / "log" / "workouts.jsonl"
WEEKLY = "2026-10-12-weekly"
TUESDAY = "2026-10-13T12:00:00Z"
WEDNESDAY = "2026-10-14T12:00:00Z"
SATURDAY = "2026-10-17T09:00:00Z"
B_TO_SAT = {"id": "b-to-sat", "session_id": "session-b", "text": None, "when": {},
            "action": {"kind": "shift", "to_weekdays": ["sat"]}}


def workout(day, session_id, exercises):
    """A manual-log workout line; `exercises` are (exercise_id, load_mode, [(value, reps, rpe)])."""
    return {"schema_version": 1, "kind": "workout", "id": f"manual:{day}-{session_id}-1",
            "logged_at": f"{day}T19:30:00Z", "date": day, "session_id": session_id, "overlay_id": WEEKLY,
            "duration_minutes": 55, "notes": "",
            "exercises": [{"exercise_id": exercise_id, "load_mode": load_mode, "unit": "kg", "notes": "",
                           "sets": [{"type": "normal", "reps": reps, "rpe": rpe, "value": value,
                                     "duration_seconds": None, "distance_meters": None}
                                    for value, reps, rpe in sets]}
                          for exercise_id, load_mode, sets in exercises]}


MONDAY_A = workout("2026-10-12", "session-a", [("bb_back_squat", "total", [(100, 5, 7)] * 3),
                                               ("db_bench_press", "per_hand_x2", [(25, 9, 8)] * 3)])
THURSDAY_B = workout("2026-10-15", "session-b", [("db_single_arm_row", "single_implement", [(30, 10, 8)] * 3),
                                                 ("pull_up", "bodyweight", [(0, 8, 8)] * 3)])


class RecoveryCase(unittest.TestCase):
    """The nohevy instance: Session A on Monday, Session B on Thursday, no missed-day rules, every day available."""

    now = TUESDAY

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "instance"
        shutil.copytree(NOHEVY, self.root)

    def coach(self, *argv, now=None, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now or self.now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"] if expect == 0 else envelope

    def log(self, *workouts):
        with (self.root / LOG).open("a", encoding="utf-8") as handle:
            for found in workouts:
                handle.write(json.dumps(found) + "\n")
        self.coach("history", "sync")

    def edit_json(self, relative, change):
        path = self.root / relative
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def set_available(self, days):
        path = self.root / "config.toml"
        text = re.sub(r"available_days = \[.*\]", f"available_days = {json.dumps(days)}",
                      path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8")

    def set_rules(self, rules):
        self.edit_json("data/program.json", lambda doc: doc.update(missed_day_rules=rules))

    def plan(self, *choice, session="session-a", day="2026-10-12", now=None):
        return self.coach("missed", "plan", "--session", session, "--date", day, *choice, now=now)

    def apply(self, *choice, session="session-a", day="2026-10-12", now=None, expect=0):
        return self.coach("missed", "apply", "--session", session, "--date", day, *choice, now=now, expect=expect)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def misses(self):
        path = self.root / "data" / "history" / "annotations.json"
        if not path.exists():
            return []
        doc = json.loads(path.read_text(encoding="utf-8"))
        return [a for a in doc["annotations"] if a["kind"] == "miss"]

    def statuses(self, data):
        return {row["date"]: row["status"] for row in data["destinations"]}


class NoRuleTest(RecoveryCase):
    def test_plan_offers_a_move_or_a_drop_and_marks_each_later_day(self):
        data = self.plan()
        self.assertFalse(data["matched"])
        self.assertIsNone(data["draft"])
        self.assertIn("--move-to", data["flags"][-1]["message"])
        self.assertIn("--drop", data["flags"][-1]["message"])
        self.assertNotIn("propose week", " ".join(data["summary"]))
        self.assertEqual(data["summary"][1], "Free days to move it to: Tue 13 Oct, Wed 14 Oct, Fri 16 Oct, "
                                             "Sat 17 Oct and Sun 18 Oct.")
        self.assertEqual(self.statuses(data), {"2026-10-13": "free", "2026-10-14": "free", "2026-10-15": "occupied",
                                               "2026-10-16": "free", "2026-10-17": "free", "2026-10-18": "free"})

    def test_elapsed_occupied_and_unavailable_days_are_told_apart(self):
        self.set_available(["mon", "thu", "sat"])
        data = self.plan(now=WEDNESDAY)
        self.assertEqual(self.statuses(data), {"2026-10-13": "elapsed", "2026-10-14": "unavailable",
                                               "2026-10-15": "occupied", "2026-10-16": "unavailable",
                                               "2026-10-17": "free", "2026-10-18": "unavailable"})
        reasons = {row["date"]: row["reason"] for row in data["destinations"]}
        self.assertEqual(reasons["2026-10-13"], "Tue 13 Oct has passed")
        self.assertEqual(reasons["2026-10-15"], "Thu 15 Oct already has Session B planned")
        self.assertEqual(reasons["2026-10-16"], "Fri is not one of the athlete's available days "
                                                "([athlete] available_days: Mon, Thu, Sat)")

    def test_drop_records_the_reason_and_leaves_the_rest_of_the_week(self):
        planned = self.plan("--drop")
        self.assertTrue(planned["matched"])
        self.assertEqual((planned["decision"], planned["draft"]), ("drop", None))
        data = self.apply("--drop", "--tag", "time")
        self.assertEqual(data["record_lines"], [
            "- Missed Mon 12 Oct Session A (time).",
            "- Dropped by choice: Session A is not trained this week.",
            "- No overlay; nothing goes to Hevy.",
        ])
        self.assertEqual([(a["session_id"], a["date"], a["tag"], a["reason"]) for a in self.misses()],
                         [("session-a", "2026-10-12", "time", "dropped this week by choice")])
        self.assertEqual(overlay.ids(self.root), [WEEKLY])
        week = overlay.load(self.root, WEEKLY)
        self.assertEqual([(s["date"], s["session_id"]) for s in week["sessions"]],
                         [("2026-10-12", "session-a"), ("2026-10-15", "session-b")])
        self.assertTrue(self.coach("missed", "list")["missed"][0]["recorded"])

    def test_move_writes_one_moved_session_and_a_second_apply_is_refused(self):
        planned = self.plan("--move-to", "2026-10-14")
        self.assertTrue(planned["matched"])
        draft = planned["draft"]
        self.assertEqual([(s["date"], s["session_id"], s["moved_from"]) for s in draft["sessions"]],
                         [("2026-10-14", "session-a", "2026-10-12"), ("2026-10-15", "session-b", None)])
        data = self.apply("--move-to", "2026-10-14", "--tag", "family")
        self.assertEqual(data["record_lines"][1],
                         "- Moved by choice: Session A moved from Mon 12 Oct to Wed 14 Oct, this week only.")
        self.assertEqual(self.misses()[0]["reason"], "moved to 2026-10-14 by choice")
        before = self.snapshot()
        for choice in (("--move-to", "2026-10-14"), ("--move-to", "2026-10-16"), ("--drop",)):
            with self.subTest(choice=choice):
                refused = self.apply(*choice, "--tag", "family", expect=3)
                self.assertIn("already recorded", refused["error"]["message"])
        self.assertEqual(self.snapshot(), before)
        moved = overlay.load(self.root, data["overlay_id"])
        self.assertEqual([s["session_id"] for s in moved["sessions"]].count("session-a"), 1)

    def test_a_move_to_a_day_that_cannot_take_it_is_refused_with_the_reason(self):
        self.set_available(["mon", "thu"])
        cases = (("2026-10-15", "Thu 15 Oct already has Session B planned"),
                 ("2026-10-13", "Tue 13 Oct has passed"),
                 ("2026-10-17", "Sat is not one of the athlete's available days"),
                 ("2026-10-19", "is not after the miss and within the overlay's span"))
        for day, reason in cases:
            with self.subTest(day=day):
                data = self.plan("--move-to", day, now=WEDNESDAY)
                self.assertFalse(data["matched"])
                self.assertIn(reason, data["reason"])
                self.assertIn(reason, data["summary"][0])
        before = self.snapshot()
        refused = self.apply("--move-to", "2026-10-17", now=WEDNESDAY, expect=3)
        self.assertIn("Sat is not one of the athlete's available days", refused["error"]["message"])
        self.assertEqual(self.snapshot(), before)

    def test_an_apply_with_no_choice_is_refused_and_names_both(self):
        refused = self.apply("--tag", "time", expect=3)
        self.assertIn("--move-to", refused["error"]["message"])
        self.assertIn("--drop", refused["error"]["message"])
        self.assertEqual(self.misses(), [])

    def test_move_and_drop_together_is_a_usage_error(self):
        refused = self.coach("missed", "plan", "--session", "session-a", "--date", "2026-10-12", "--move-to",
                             "2026-10-14", "--drop", expect=2)
        self.assertIn("--move-to", refused["error"]["message"])


class AvailabilityTest(RecoveryCase):
    def setUp(self):
        super().setUp()
        self.set_rules([B_TO_SAT])
        self.log(MONDAY_A)

    def check(self):
        code, envelope, stderr = run_cli(["--root", str(self.root), "check", "--only", "available_days_conflicts"],
                                         env={"COACH_NOW": self.now})
        self.assertEqual(code, 0, (envelope, stderr))
        return [r for r in envelope["data"]["results"] if r["id"] == "available_days_conflicts"]

    def test_a_shift_to_an_unavailable_day_warns_and_planning_says_why(self):
        self.set_available(["mon", "thu"])
        results = self.check()
        self.assertEqual([r["status"] for r in results], ["warn"])
        self.assertIn("rule b-to-sat moves Session B to Sat", results[0]["message"])
        self.assertIn("(Mon, Thu)", results[0]["message"])
        data = self.plan(session="session-b", day="2026-10-15", now="2026-10-16T09:00:00Z")
        self.assertFalse(data["matched"])
        self.assertIn("Sat is not one of the athlete's available days", data["reason"])
        self.assertEqual(self.statuses(data)["2026-10-17"], "unavailable")

    def test_adding_saturday_removes_the_conflict(self):
        self.set_available(["mon", "thu", "sat"])
        self.assertEqual([r["status"] for r in self.check()], ["pass"])
        data = self.plan(session="session-b", day="2026-10-15", now="2026-10-16T09:00:00Z")
        self.assertTrue(data["matched"])
        self.assertEqual([(s["date"], s["moved_from"]) for s in data["draft"]["sessions"]],
                         [("2026-10-17", "2026-10-15")])

    def test_a_scheduled_day_outside_available_days_is_reported(self):
        self.set_rules([])
        self.set_available(["mon", "tue"])
        results = self.check()
        self.assertEqual([r["status"] for r in results], ["warn"])
        self.assertIn("The schedule plans Session B on Thu", results[0]["message"])

    def test_an_empty_list_leaves_every_day_available(self):
        self.set_available([])
        results = self.check()
        self.assertEqual([r["status"] for r in results], ["pass"])
        self.assertIn("every day is available", results[0]["message"])
        self.assertTrue(self.plan(session="session-b", day="2026-10-15", now="2026-10-16T09:00:00Z")["matched"])


class StatusTest(RecoveryCase):
    now = SATURDAY

    def setUp(self):
        super().setUp()
        self.set_rules([B_TO_SAT])
        self.log(MONDAY_A)

    def missed_section(self):
        envelope = self.coach("status")
        return next((s for s in envelope["sections"] if s["id"] == "missed"), None)

    def test_saturday_status_names_thursday_and_the_shift_to_today_and_writes_nothing(self):
        before = self.snapshot()
        section = self.missed_section()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(section["level"], "attention")
        self.assertEqual(len(section["lines"]), 1)
        line = section["lines"][0]
        self.assertTrue(line.startswith("Thu 15 Oct Session B is not logged; rule b-to-sat moves it to today, "
                                        "Sat 17 Oct."), line)
        self.assertIn("missed plan --session session-b --date 2026-10-15", line)
        recovery = section["data"]["missed"][0]["recovery"]
        self.assertEqual((recovery["rule_id"], recovery["kind"], recovery["to"]), ("b-to-sat", "shift", "2026-10-17"))

    def test_logging_the_session_clears_the_line(self):
        self.log(THURSDAY_B)
        self.assertIsNone(self.missed_section())

    def test_recording_the_miss_clears_the_line(self):
        self.apply("--tag", "time", session="session-b", day="2026-10-15")
        self.assertIsNone(self.missed_section())

    def test_without_a_rule_status_offers_the_choice(self):
        self.set_rules([])
        line = self.missed_section()["lines"][0]
        self.assertIn("no missed-day rule applies", line)
        self.assertIn("move it, drop it or reshuffle the week", line)

    def test_an_unavailable_destination_is_named(self):
        self.set_available(["mon", "thu"])
        line = self.missed_section()["lines"][0]
        self.assertIn("Sat is not one of the athlete's available days", line)


class NextExposureTest(RecoveryCase):
    """Monday's squat, its only exposure this week, is logged; on Tuesday the athlete asks to bump it."""

    def setUp(self):
        super().setUp()
        self.log(MONDAY_A)

    def test_an_override_on_the_midweek_proposal_names_the_next_exposure_route(self):
        proposed = self.coach("propose", "week", "--kind", "midweek", "--week", "2026-W42")
        doc = json.loads((self.root / ".coach" / "proposals" / f"{proposed['id']}.json").read_text(encoding="utf-8"))
        self.assertEqual([s["session_id"] for s in doc["sessions"]], ["session-b"])
        before = self.snapshot()
        refused = self.coach("propose", "override", "--proposal", proposed["id"], "--session", "session-a",
                             "--exercise", "bb_back_squat", "--load", "105", "--reason", "bump my squat", expect=1)
        message = refused["error"]["message"]
        self.assertIn("next exposure is in a later week", message)
        self.assertIn("followups add", message)
        self.assertEqual(self.snapshot(), before)

    def test_the_mid_week_step_routes_a_lift_with_no_session_left_to_a_dated_follow_up(self):
        text = flat(step_text("program-week", "midweek.md"))
        route = text[text.index("**A lift with no session left"):]
        for words in ("stats e1rm --exercise", "followups add", "--review-at", "`followup_due`",
                      "that line's override (compute.md, step 5)"):
            self.assertIn(words, route)
        self.assertIn("next exposure is next week's own session", route)


class SkillTextTest(unittest.TestCase):
    def test_an_unmatched_miss_offers_move_reshuffle_or_drop_and_records_the_choice(self):
        text = flat(step_text("program-week", "midweek.md"))
        branch = text[text.index("**No rule applies.**"):text.index("**A lift with no session left")]
        for words in ("--move-to", "--drop", "one-off.md", "`destinations`", "--tag", "history annotate --kind miss",
                      "[athlete] available_days"):
            self.assertIn(words, branch)
        self.assertLess(branch.index("--move-to"), branch.index("missed apply"))

    def test_setup_and_redesign_explain_optional_missed_day_rules(self):
        for skill, step in (("setup", "program.md"), ("new-program", "design.md")):
            with self.subTest(skill=skill):
                text = flat(step_text(skill, step)).lower()
                self.assertIn("missed-day rules are optional", text)
                self.assertIn("each miss", text)
                self.assertIn("[athlete] available_days", text)


if __name__ == "__main__":
    unittest.main()
