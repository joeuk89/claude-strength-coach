"""The next-in-sequence and explicit-calendar schedule rules (contract C23)."""

import unittest
from datetime import date

from coach import plugins
from coach.plugins import base
from tests.support.history import HistoryCase

WEEK = "2026-W42"


def rule(name):
    return plugins.load().get("schedule", name)


def plan(name, params, start, end, rotation=None, today=date(2026, 10, 11)):
    plugin = rule(name)
    merged, errors = plugins.merged_params(plugin, params)
    assert not errors, errors
    ctx = base.ScheduleContext(today=today, span_start=start, span_end=end, week_starts="monday", params=merged,
                               rotation=dict(rotation or {}), sessions=(), external_sessions=())
    return plugin.module.plan(ctx)


def program(*session_ids):
    return {"sessions": [{"id": s} for s in session_ids], "external_sessions": []}


def unconfirmed(found):
    return [f["code"] for f in found.flags] == ["rotation_unconfirmed"]


class ExplicitCalendarTest(unittest.TestCase):
    PARAMS = {"dates": {"2026-10-11": "session-a", "2026-10-13": "session-b", "2026-10-16": "session-a",
                        "2026-10-19": "session-b"}}

    def test_plans_exactly_the_dates_in_the_span(self):
        found = plan("explicit_calendar", self.PARAMS, date(2026, 10, 12), date(2026, 10, 18))
        self.assertEqual(found.sessions, ((date(2026, 10, 13), "session-b"), (date(2026, 10, 16), "session-a")))
        self.assertIsNone(found.rotation)
        self.assertEqual(found.flags, ())

    def test_has_no_rotation_positions(self):
        self.assertEqual(rule("explicit_calendar").module.positions(self.PARAMS), ())

    def test_problems_name_unknown_sessions_and_bad_dates(self):
        params = {"dates": {"2026-10-13": "session-z", "2026-02-30": "session-a", "13/10/2026": "session-a"}}
        found = dict(rule("explicit_calendar").module.problems(params, program("session-a")))
        self.assertEqual(set(found), {"$.dates.2026-10-13", "$.dates.2026-02-30", "$.dates.13/10/2026"})
        self.assertIn("no program session session-z", found["$.dates.2026-10-13"])
        self.assertIn("not a date", found["$.dates.2026-02-30"])


class NextInSequenceTest(unittest.TestCase):
    ABC = {"sequence": ["session-a", "session-b", "session-c"], "days": ["mon", "wed", "fri"]}

    def test_continues_after_the_last_trained_session(self):
        rotation = {"position": "session-b", "confirmed": True, "week": "2026-10-12"}
        found = plan("next_in_sequence", self.ABC, date(2026, 10, 12), date(2026, 10, 18), rotation)
        self.assertEqual(found.sessions, ((date(2026, 10, 12), "session-c"), (date(2026, 10, 14), "session-a"),
                                          (date(2026, 10, 16), "session-b")))
        self.assertEqual(found.rotation, {"position": "session-b", "confirmed": True, "week": "2026-10-12"})
        self.assertEqual(found.flags, ())

    def test_a_later_week_assumes_the_planned_sessions_were_trained_and_asks_to_confirm(self):
        params = {"sequence": ["session-a", "session-b", "session-c"], "days": ["thu", "mon"]}
        rotation = {"position": "session-b", "confirmed": True, "week": "2026-10-12"}
        found = plan("next_in_sequence", params, date(2026, 10, 19), date(2026, 10, 25), rotation)
        self.assertEqual(found.sessions, ((date(2026, 10, 19), "session-b"), (date(2026, 10, 22), "session-c")))
        self.assertEqual(found.rotation, {"position": "session-a", "confirmed": False, "week": "2026-10-19"})
        self.assertTrue(unconfirmed(found))
        self.assertIn("schedule confirm --position", found.flags[0]["message"])

    def test_a_midweek_span_keeps_the_week_s_earlier_sessions(self):
        rotation = {"position": "session-b", "confirmed": True, "week": "2026-10-12"}
        found = plan("next_in_sequence", self.ABC, date(2026, 10, 15), date(2026, 10, 18), rotation)
        self.assertEqual(found.sessions, ((date(2026, 10, 16), "session-b"),))

    def test_no_position_starts_the_sequence_unconfirmed(self):
        found = plan("next_in_sequence", self.ABC, date(2026, 10, 12), date(2026, 10, 18),
                     {"position": None, "confirmed": True, "week": None})
        self.assertEqual([s for _, s in found.sessions], ["session-a", "session-b", "session-c"])
        self.assertEqual(found.rotation, {"position": "session-c", "confirmed": False, "week": "2026-10-12"})
        self.assertTrue(unconfirmed(found))

    def test_positions_are_the_sequence(self):
        self.assertEqual(rule("next_in_sequence").module.positions(self.ABC), ("session-a", "session-b", "session-c"))

    def test_problems_name_unknown_and_repeated_entries(self):
        params = {"sequence": ["session-a", "session-z", "session-a"], "days": ["mon", "mon"]}
        found = dict(rule("next_in_sequence").module.problems(params, program("session-a")))
        self.assertIn("no program session session-z", found["$.sequence[1]"])
        self.assertIn("twice", found["$.sequence"])
        self.assertIn("twice", found["$.days"])


class ScheduleCommandsTest(HistoryCase):
    def setUp(self):
        super().setUp()

        def change(doc):
            third = dict(doc["sessions"][0], id="session-c", title="Session C")
            doc["sessions"].append(third)
            doc["schedule"] = {"rule": "next_in_sequence", "params": {
                "sequence": ["session-a", "session-b", "session-c"], "days": ["mon", "wed", "fri"]}}
        self.edit_json("data/program.json", change)
        self.edit_json("data/state.json", lambda doc: doc.update(rotation={
            "position": "session-b", "confirmed": True, "confirmed_at": "2026-10-11", "week": "2026-10-12"}))

    def test_schedule_plan_after_session_b_plans_c_a_b(self):
        self.assertTrue(self.coach("program", "validate")["data"]["valid"])
        data = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual([(s["date"], s["session_id"]) for s in data["sessions"]],
                         [("2026-10-12", "session-c"), ("2026-10-14", "session-a"), ("2026-10-16", "session-b")])
        self.assertEqual(data["flags"], [])

    def test_schedule_confirm_records_the_last_trained_session(self):
        self.coach("schedule", "confirm", "--position", "session-a")
        data = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["session-b", "session-c", "session-a"])

    def test_explicit_calendar_through_schedule_plan(self):
        self.edit_json("data/program.json", lambda doc: doc.update(schedule={
            "rule": "explicit_calendar", "params": {"dates": {"2026-10-13": "session-c", "2026-10-20": "session-a"}}}))
        data = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual([(s["date"], s["session_id"]) for s in data["sessions"]], [("2026-10-13", "session-c")])

    def test_program_validate_reports_an_unknown_sequence_session(self):
        self.edit_json("data/program.json", lambda doc: doc["schedule"]["params"].update(
            sequence=["session-a", "session-q"]))
        details = self.coach("program", "validate", expect=1)["error"]["details"]
        self.assertIn("$.schedule.params.sequence[1]", [d["path"] for d in details])


if __name__ == "__main__":
    unittest.main()
