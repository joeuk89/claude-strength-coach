"""Slot-specific progression evidence and the three-exposure coaching heuristic."""

import copy
import unittest
from dataclasses import replace
from datetime import date
from unittest import mock

from coach import config, dates, flags, propose, units
from coach.plugins import base
from tests.test_progression_schemes import context, exposure, run, PULL_UP, THREE_FIVES
from tests.test_propose import ProposeCase
from tests.support.history import read_json


class EvidencePipelineTest(ProposeCase):
    def make_run(self):
        return propose.Run(self.root, config.load(self.root), date(2026, 10, 11),
                           dates.parse_timestamp("2026-10-11T18:00:00Z"))

    def two_slots(self, mode="total", scheme="double_progression"):
        current = read_json(self.root / "data/program.json")
        slot = copy.deepcopy(current["sessions"][0]["exercises"][0])
        slot.update(exercise_id="lat_pulldown", load_mode=mode, start_load=70,
                    sets=[{"count": 3, "type": "normal", "reps": 8, "rpe": 8}],
                    scheme={"name": scheme, "params": {"increment": 2.5}})
        runner = self.make_run()
        for session in runner.program["sessions"]:
            session["exercises"] = [copy.deepcopy(slot)]
        return runner

    def propose_slot(self, runner, session_id):
        session = runner.sessions[session_id]
        return propose.propose_line(runner, session, date(2026, 10, 12), session["exercises"][0],
                                    {"states": {}, "kind": "weekly", "transform": None,
                                     "illness": None, "first_day": date(2026, 10, 12)})

    def test_heavy_and_light_pulldown_slots_use_their_own_most_recent_usable_exposure(self):
        runner = self.two_slots()
        prescribed = (base.SetSpec(reps=8, rpe=8),) * 3
        heavy = replace(exposure(date(2026, 10, 5), [(70, 8, 8)] * 3), exercise_id="lat_pulldown",
                        prescribed=prescribed)
        light = replace(exposure(date(2026, 10, 8), [(60, 8, 8)] * 3), exercise_id="lat_pulldown",
                        session_id="session-b", prescribed=prescribed)
        suspect = replace(heavy, date=date(2026, 10, 9), suspect=True,
                          sets=(base.LoggedSet(0, "normal", 8, 8, 140),) * 3)
        runner._exposures = [suspect, light, heavy]
        with mock.patch.object(runner, "increment", return_value=2.5):
            a, b = (self.propose_slot(runner, session) for session in ("session-a", "session-b"))
        self.assertEqual({s["load"] for s in a.draft_line["sets"]}, {72.5})
        self.assertEqual({s["load"] for s in b.draft_line["sets"]}, {62.5})
        self.assertEqual(a.draft_line["provenance"]["derived_from"], heavy.ref())
        self.assertEqual(b.draft_line["provenance"]["derived_from"], light.ref())

    def test_session_and_load_mode_filters_leave_exercise_wide_evidence_available(self):
        runner = self.make_run()
        a = exposure(date(2026, 10, 5), [(70, 5, 7)] * 3)
        b = replace(a, session_id="session-b", date=date(2026, 10, 8))
        assisted = replace(a, load_mode="assisted")
        unmatched = replace(a, session_id=None)
        runner._exposures = [b, a, assisted, unmatched]
        before = date(2026, 10, 12)
        self.assertEqual(runner.exposures_of(a.exercise_id, before, "session-a", "total"), (a,))
        self.assertEqual(len(runner.exposures_of(a.exercise_id, before)), 4)
        runner._series = {"series": {a.exercise_id: [{"date": "2026-10-05", "e1rm": 90},
                                                   {"date": "2026-10-08", "e1rm": 110}]},
                          "observations": {}}
        self.assertEqual(runner.e1rm(a.exercise_id, before), 110)

    def test_unknown_three_set_history_is_not_judged_as_missing_a_redesigned_fourth_set(self):
        runner = self.two_slots()
        runner.sessions["session-a"]["exercises"][0]["sets"][0]["count"] = 4
        raw = {"date": "2026-10-05", "workout_id": "historical", "session_id": "session-a",
               "exercise_id": "lat_pulldown", "load_mode": "total", "suspect": False, "excluded": False,
               "sets": [{"index": i, "type": "normal", "reps": 8, "rpe": 8,
                         "load": units.make_load(70, "total", "kg")} for i in range(3)]}
        historical = runner._exposure(raw, None)
        self.assertEqual(historical.prescribed, ())
        runner._exposures = [historical]
        result = self.propose_slot(runner, "session-a")
        rationale = result.draft_line["provenance"]["rationale"]
        self.assertIn("historical prescription unknown", rationale)
        self.assertNotIn("fewer working sets", rationale)
        self.assertNotIn("every working set reached", rationale)
        self.assertEqual({s["load"] for s in result.draft_line["sets"]}, {70})
        self.assertEqual(len(result.draft_line["sets"]), 4)
        self.assertIn("prescription_unknown", [f["code"] for f in result.flags])
        self.assertNotIn("no_data", [f["code"] for f in result.flags])

    def test_distinct_ladder_slots_use_their_own_historical_targets(self):
        runner = self.two_slots("assisted", "assistance_ladder")
        for sid, reps in (("session-a", 8), ("session-b", 12)):
            slot = runner.sessions[sid]["exercises"][0]
            slot["sets"][0]["reps"] = reps
            slot["scheme"]["params"] = {"rungs": [{"name": "first", "load": 30},
                                                    {"name": "second", "load": 25}], "reps": reps}
        a = replace(exposure(date(2026, 10, 5), [(30, 8, 8)] * 3, exercise=PULL_UP),
                    exercise_id="lat_pulldown", prescribed=(base.SetSpec(reps=8, rpe=8),) * 3)
        b = replace(a, session_id="session-b", date=date(2026, 10, 8),
                    prescribed=(base.SetSpec(reps=12, rpe=8),) * 3)
        runner._exposures = [b, a]
        self.assertEqual(self.propose_slot(runner, "session-a").state["rung"], 1)
        self.assertEqual(self.propose_slot(runner, "session-b").state["rung"], 0)

    def test_duration_and_distance_survive_history_projection(self):
        runner = self.make_run()
        for mode, field in (("duration", "duration_seconds"), ("distance", "distance_meters")):
            with self.subTest(mode=mode):
                raw = {"date": "2026-10-05", "workout_id": "timed", "session_id": "session-a",
                       "exercise_id": "plank", "load_mode": mode, "suspect": False, "excluded": False,
                       "sets": [{"index": 0, "type": "normal", "reps": None, "rpe": 7,
                                 "load": None, field: 30}]}
                projected = runner._exposure(raw, None)
                self.assertEqual(getattr(projected.sets[0], field), 30)


class ProgressMetricTest(unittest.TestCase):
    def exposures(self, mode="total", loads=(70, 70, 70), reps=(8, 8, 8), rpes=(8, 8, 8), metrics=None):
        entries = []
        for i, (load, count, effort) in enumerate(zip(loads, reps, rpes)):
            e = replace(exposure(date(2026, 10, 1 + i * 3), [(load, count, effort)] * 3), load_mode=mode)
            if metrics:
                field = "duration_seconds" if mode == "duration" else "distance_meters"
                e = replace(e, sets=tuple(replace(s, **{field: metrics[i]}) for s in e.sets))
            entries.append(e)
        return tuple(reversed(entries))

    def test_band_rep_gains_and_reduced_assistance_are_progress(self):
        self.assertIsNone(propose._stalled(self.exposures("band", (None,) * 3, (15, 15, 16))))
        self.assertIsNone(propose._stalled(self.exposures("assisted", (30, 25, 20))))
        self.assertIsNone(propose._stalled(self.exposures("bodyweight", (0,) * 3, (8, 8, 9))))

    def test_duration_and_distance_progress_and_constant_work(self):
        for mode in ("duration", "distance"):
            with self.subTest(mode=mode):
                self.assertIsNone(propose._stalled(self.exposures(mode, (None,) * 3, (None,) * 3,
                                                                  metrics=(30, 30, 35))))
                self.assertEqual(len(propose._stalled(self.exposures(mode, (None,) * 3, (None,) * 3,
                                                                     metrics=(30, 30, 30)))), 3)
                self.assertIsNone(propose._stalled(self.exposures(mode, (None,) * 3, (None,) * 3)))

    def test_effort_improves_only_at_matched_work(self):
        self.assertIsNone(propose._stalled(self.exposures(rpes=(8, 8, 7))))
        self.assertIsNotNone(propose._stalled(self.exposures(reps=(8, 8, 7), rpes=(8, 8, 7))))
        self.assertIsNotNone(propose._stalled(self.exposures(rpes=(8, 8, None))))

    def test_incomparable_sets_cannot_establish_a_stall(self):
        newest, middle, oldest = self.exposures()
        self.assertIsNone(propose._stalled((replace(newest, sets=newest.sets[:2]), middle, oldest)))
        self.assertIsNone(propose._stalled((replace(newest, load_mode="assisted"), middle, oldest)))
        self.assertIsNone(propose._stalled((replace(newest, excluded=True), middle, oldest)))
        self.assertIsNone(propose._stalled((replace(newest, suspect=True), middle, oldest)))
        self.assertIsNone(propose._stalled((replace(newest, week_kind="deload"), middle, oldest)))

    def test_final_load_increase_suppresses_stall_but_unchanged_work_warns(self):
        exposures = self.exposures()
        ctx = context("linear", exposures=exposures)
        def line_flag(code, message, severity=None):
            return flags.make(code, severity, message=message)
        for load, stalled in ((72.5, False), (70, True)):
            found = propose._core_flags(ctx, {}, {"sets": THREE_FIVES},
                                        (base.SetSpec(reps=8, load=load),) * 3,
                                        exposures, (), line_flag, "total", date(2026, 10, 12))
            self.assertEqual("stalled" in [f["code"] for f in found], stalled)
            if stalled:
                warning = next(f for f in found if f["code"] == "stalled")
                self.assertIn("coaching heuristic, not a diagnosis", warning["message"])

    def test_linear_unknown_targets_do_not_invent_hits_or_misses(self):
        unknown = exposure(date(2026, 10, 5), [(70, 5, 7)] * 3)
        result = run(context("linear", exposures=(unknown,), sets=({"count": 4, "reps": 5},)))
        self.assertEqual({s.load for s in result.sets}, {70})
        self.assertIn("historical prescription unknown", result.rationale)
        self.assertIsNone(base.missed(unknown))
        self.assertEqual(result.state["misses"], 0)

    def test_ladder_unknown_targets_hold_without_claiming_a_miss(self):
        unknown = exposure(date(2026, 10, 5), [(30, 8, 8)] * 3, exercise=PULL_UP)
        result = run(context("assistance_ladder", {"rungs": [{"name": "first", "load": 30},
                                                             {"name": "next", "load": 25}]},
                             exposures=(unknown,), exercise=PULL_UP))
        self.assertEqual(result.state["rung"], 0)
        self.assertIn("historical prescription unknown", result.rationale)

    def test_linear_reset_below_start_is_information_without_an_extra_adjustment(self):
        missed = tuple(replace(e, prescribed=base.expand(THREE_FIVES))
                       for e in self.exposures(loads=(70,) * 3, reps=(4,) * 3))
        result = run(context("linear", exposures=missed, start_load=70))
        self.assertEqual({s.load for s in result.sets}, {63})
        self.assertEqual([(f["code"], f["severity"]) for f in result.flags], [("linear_below_start", "info")])
        self.assertEqual(result.state["misses"], 3)
