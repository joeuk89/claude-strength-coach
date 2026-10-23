"""A return cut is measured once, from the pre-layoff working load, and the proposal and `prescription check`
agree on that base (contract C22, C23, C24)."""

import unittest
from dataclasses import replace

from coach import units
from coach.plugins import base
from tests.support.history import read_json
from tests.test_progression_schemes import context
from tests.test_propose import coaching, find_line
from tests.test_return_to_training import ReturnCase, working

SUNDAY_29 = "2026-11-29T18:00:00Z"
MONDAY_30 = "2026-11-30T08:00:00Z"
PRESS_SLOT = {"exercise_id": "bb_overhead_press", "load_mode": "total",
              "sets": [{"count": 3, "type": "normal", "reps": 5, "rpe": 7}],
              "rest_seconds": 150, "superset_id": None, "cues": None, "constraints": [],
              "scheme": {"name": "double_progression", "params": {}}, "start_load": 75}


class ReturnCutCase(ReturnCase):
    """The block fixture trained through Thu 15 Oct and proposed for the week of Mon 30 Nov: 46 days off, band 43+."""

    def add_slot(self, session_index, slot):
        self.edit("data/program.json", lambda doc: doc["sessions"][session_index]["exercises"].append(slot))

    def loads(self, doc, exercise_id, session_id=None):
        return [coaching(s["load"]) for s in working(find_line(doc, exercise_id, session_id))]

    def check(self, proposal_id, now):
        draft = self.root / ".coach" / "proposals" / f"{proposal_id}.json"
        return self.data("prescription", "check", "--file", str(draft), now=now)

    def logged_top(self, day, exercise_id):
        return max(s["weight_kg"] for w in self.workouts() if w["date"] == day
                   for e in w["exercises"] if e["exercise_id"] == exercise_id for s in e["sets"])


class ReProposedReturnWeekTest(ReturnCutCase):
    """The overhead press is new to the program: no exposure anywhere, a start load of 75."""

    def setUp(self):
        super().setUp()
        self.add_slot(0, PRESS_SLOT)
        self.edit("data/exercises.json", lambda doc: doc["exercises"].update(bb_overhead_press={
            "hevy_template_id": "F0000009", "load_mode": "total", "load_mode_proposed": "total",
            "confidence": "high", "avoid": None}))

    def test_a_midweek_re_proposal_and_a_rebuild_keep_the_approved_cut(self):
        weekly = self.propose("--week", "2026-W49", now=SUNDAY_29)
        press = find_line(weekly["overlay"], "bb_overhead_press")
        self.assertEqual(press["provenance"]["decay"]["band"], "43+")
        self.assertIsNone(press["provenance"]["derived_from"])
        self.assertIn("a 15 % cut from 75", press["provenance"]["rationale"])
        loads = self.loads(weekly["overlay"], "bb_overhead_press")
        squat = self.loads(weekly["overlay"], "bb_back_squat")
        self.assertEqual(len(loads), 2)
        self.assertLess(loads[0], 75)
        self.approve(weekly, SUNDAY_29)

        midweek = self.propose("--kind", "midweek", now=MONDAY_30)
        self.assertEqual([s["date"] for s in midweek["overlay"]["sessions"]], ["2026-11-30", "2026-12-03"])
        again = find_line(midweek["overlay"], "bb_overhead_press")
        self.assertEqual(self.loads(midweek["overlay"], "bb_overhead_press"), loads)
        self.assertEqual(len(working(again)), 2)
        self.assertIn("a 15 % cut from 75", again["provenance"]["rationale"])
        self.assertEqual(self.loads(midweek["overlay"], "bb_back_squat"), squat)

        self.data("propose", "finalize", "--proposal", midweek["id"], now=MONDAY_30)
        rebuilt = self.data("propose", "rebuild", "--proposal", midweek["id"], now=MONDAY_30)
        self.assertEqual(self.loads(rebuilt["overlay"], "bb_overhead_press"), loads)
        self.assertEqual(self.loads(rebuilt["overlay"], "bb_back_squat"), squat)
        self.assertIn("a 15 % cut from 75", find_line(rebuilt["overlay"], "bb_overhead_press")["provenance"]["rationale"])


class PreLayoffBaseTest(ReturnCutCase):
    """The squat added to session-b with session-a's start load: no exposure of its own, the lift logged elsewhere."""

    def setUp(self):
        super().setUp()
        self.squat = dict(read_json(self.root / "data" / "program.json")["sessions"][0]["exercises"][0])
        self.add_slot(1, self.squat)
        self.top = self.logged_top("2026-10-12", "bb_back_squat")

    def test_the_lifts_newest_exposure_is_the_base_for_the_proposal_and_the_check(self):
        data = self.propose("--week", "2026-W49", now=SUNDAY_29)
        own = find_line(data["overlay"], "bb_back_squat", "session-a")
        fresh = find_line(data["overlay"], "bb_back_squat", "session-b")
        self.assertEqual(own["provenance"]["derived_from"]["date"], "2026-10-12")
        self.assertEqual(fresh["provenance"]["derived_from"], own["provenance"]["derived_from"])
        self.assertEqual(self.loads(data["overlay"], "bb_back_squat", "session-b"),
                         self.loads(data["overlay"], "bb_back_squat", "session-a"))
        self.assertLess(self.loads(data["overlay"], "bb_back_squat", "session-b")[0], self.top)
        self.assertIn(f"the slot has no exposure of its own, so the return band cuts from the lower of its 100 and "
                      f"the lift's newest, {units.format_number(self.top)} logged on 2026-10-12 in session-a: "
                      f"{units.format_number(min(100, self.top))}, keeping the slot's own set count",
                      fresh["provenance"]["rationale"])
        checked = self.check(data["id"], SUNDAY_29)
        self.assertEqual(checked["summary"]["block"], 0, checked["flags"])
        row = next(r for r in checked["lines"] if r["date"] == "2026-12-03" and r["exercise_id"] == "bb_back_squat")
        self.assertEqual((row["band"], row["derived_from"]), ("43+", own["provenance"]["derived_from"]))

    def test_a_workout_matched_to_no_session_is_still_the_base(self):
        def unmap(workout):
            workout.update(session_id=None, overlay_id=None)
        for day in [w["date"] for w in self.workouts() if w["session_id"] == "session-a"]:
            self.edit_workout(day, unmap)
        data = self.propose("--week", "2026-W49", now=SUNDAY_29)
        for session_id in ("session-a", "session-b"):
            with self.subTest(session=session_id):
                line = find_line(data["overlay"], "bb_back_squat", session_id)
                self.assertEqual(line["provenance"]["derived_from"]["date"], "2026-10-12")
                self.assertIn("logged on 2026-10-12 in a workout matched to no session", line["provenance"]["rationale"])
                self.assertLess(self.loads(data["overlay"], "bb_back_squat", session_id)[0], self.top)
        self.assertEqual(self.check(data["id"], SUNDAY_29)["summary"]["block"], 0)

    def test_a_borrowed_exposure_sets_the_load_but_never_the_set_count(self):
        def one_set(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == "bb_back_squat":
                    exercise["sets"] = exercise["sets"][:1]
        self.edit_workout("2026-10-12", one_set)
        weekly = self.propose("--week", "2026-W49", now=SUNDAY_29)
        own = working(find_line(weekly["overlay"], "bb_back_squat", "session-a"))
        borrowed = working(find_line(weekly["overlay"], "bb_back_squat", "session-b"))
        self.assertEqual((len(own), len(borrowed)), (1, 2))
        self.assertEqual([coaching(s["load"]) for s in borrowed], [coaching(own[0]["load"])] * 2)
        self.assertEqual(self.check(weekly["id"], SUNDAY_29)["summary"]["block"], 0)
        self.approve(weekly, SUNDAY_29)
        midweek = self.propose("--kind", "midweek", now=MONDAY_30)
        again = working(find_line(midweek["overlay"], "bb_back_squat", "session-b"))
        self.assertEqual([(s["reps"], coaching(s["load"])) for s in again],
                         [(s["reps"], coaching(s["load"])) for s in borrowed])

    def test_after_mondays_return_session_the_approved_thursday_line_stands(self):
        """Monday trained as prescribed; Tuesday re-plans the same week and the rest of it: session-b's squat, with no
        exposure of its own, keeps the approved return line (never cut again from Monday's load, never the start load)."""
        weekly = self.propose("--week", "2026-W49", now=SUNDAY_29)
        doc = self.approve(weekly, SUNDAY_29)
        approved = [(s["reps"], coaching(s["load"])) for s in working(find_line(doc, "bb_back_squat", "session-b"))]
        self.log_as_prescribed(doc, "2026-11-30")
        tuesday = "2026-12-01T08:00:00Z"
        for argv in (("--week", "2026-W49"), ("--kind", "midweek")):
            with self.subTest(argv=argv):
                data = self.propose(*argv, now=tuesday)
                line = find_line(data["overlay"], "bb_back_squat", "session-b")
                self.assertEqual([(s["reps"], coaching(s["load"])) for s in working(line)], approved)
                self.assertNotIn("logged on 2026-11-30", line["provenance"]["rationale"])
                self.assertEqual(self.check(data["id"], tuesday)["summary"]["block"], 0)

    def test_a_start_load_below_the_pre_layoff_load_is_cut_from_itself(self):
        lower = round(self.top - 20)
        self.edit("data/program.json", lambda doc: doc["sessions"][1]["exercises"][-1].update(start_load=lower))
        data = self.propose("--week", "2026-W49", now=SUNDAY_29)
        fresh = find_line(data["overlay"], "bb_back_squat", "session-b")
        self.assertEqual(fresh["provenance"]["derived_from"]["date"], "2026-10-12")
        self.assertIn(f"a 15 % cut from {lower}", fresh["provenance"]["rationale"])
        self.assertLess(self.loads(data["overlay"], "bb_back_squat", "session-b")[0], lower)
        self.assertEqual(self.check(data["id"], SUNDAY_29)["summary"]["block"], 0)

    def test_an_agreed_return_week_after_a_layoff_passes_the_check(self):
        data = self.propose("--week", "2026-W49", "--kind", "deload", "--transform", "return", now=SUNDAY_29)
        fresh = find_line(data["overlay"], "bb_back_squat", "session-b")
        self.assertEqual(fresh["provenance"]["derived_from"]["date"], "2026-10-12")
        self.assertEqual(self.check(data["id"], SUNDAY_29)["summary"]["block"], 0)


class StartLoadTest(unittest.TestCase):
    def test_a_recovery_line_is_never_the_base_of_a_cut(self):
        returned = {"sets": (base.SetSpec(reps=5, rpe=7, load=63.75),), "recovery": "return"}
        ordinary = {"sets": (base.SetSpec(reps=5, rpe=7, load=72.5),), "recovery": None}
        ctx = replace(context("double_progression", start_load=75, days_off=46), last_prescription=returned)
        self.assertEqual(base.start_load(ctx), 75)
        self.assertEqual(base.start_load(replace(ctx, last_ordinary_prescription=ordinary)), 72.5)
        self.assertIsNone(base.start_load(replace(ctx, slot=replace(ctx.slot, start_load=None))))

    def test_with_no_cut_to_apply_the_last_approved_line_holds(self):
        returned = {"sets": (base.SetSpec(reps=5, rpe=7, load=63.75),), "recovery": "return"}
        ctx = replace(context("double_progression", start_load=75, days_off=3), last_prescription=returned)
        self.assertEqual(base.start_load(ctx), 63.75)


if __name__ == "__main__":
    unittest.main()
