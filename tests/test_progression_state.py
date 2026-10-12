"""Scheme state that follows approved prescriptions, incomplete exposures and all-or-nothing finalize (C23, C24)."""

import copy
import json
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from coach import jsonio, propose, units
from coach.errors import ValidationError
from coach.plugins import base
from tests.support.history import W, R_B, read_json
from tests.support.skills import flat, step_text
from tests.test_progression_schemes import PULL_UP, context, exposure, loads_and_reps, run, scheme
from tests.test_propose import FIRST_ID, SQUAT, ProposeCase, codes, coaching, edit_sets, working

THREE_EIGHTS = ({"count": 3, "type": "normal", "reps": 8, "rpe": 8},)
RUNGS = [{"name": "30 kg assist", "load": 30}, {"name": "25 kg assist", "load": 25},
         {"name": "20 kg assist", "load": 20}]
BODYWEIGHT_RUNGS = {"rungs": [{"name": "Bodyweight", "load": None}, {"name": "+5 kg", "load": 5},
                              {"name": "+10 kg", "load": 10}]}


def prescribed(day, reps, sets=THREE_EIGHTS, load=100, workout_id=None, logged=None):
    """An exposure logging one working set per entry of `reps` at `logged` (default `load`), against the
    prescription `sets` at `load`."""
    found = exposure(day, [(load if logged is None else logged, r, 8) for r in reps], workout_id=workout_id)
    return replace(found, prescribed=base.with_load(base.expand(sets), load))


def linear(exposures, state=None, limit=1, sets=THREE_EIGHTS):
    return run(context("linear", {"misses_before_reset": limit, "increment": 2.5}, state=state,
                       exposures=tuple(exposures), sets=sets))


class IncompleteExposureTest(unittest.TestCase):
    def test_two_hit_sets_and_a_missing_third_hold_without_counting_a_miss(self):
        short = prescribed(date(2026, 10, 5), (8, 8))
        self.assertIsNone(base.missed(short))
        self.assertTrue(base.incomplete(short))
        proposal = linear([short])
        self.assertEqual(loads_and_reps(proposal), [(100, 8)] * 3)
        self.assertEqual(proposal.state, {"misses": 0, "through": "2026-10-05"})
        self.assertIn("2 of 3 prescribed working sets", proposal.rationale)
        [flag] = proposal.flags
        self.assertEqual((flag["code"], flag["severity"]), ("incomplete_exposure", "warn"))
        self.assertIn("skipped or failed", flag["message"])

    def test_a_missing_set_keeps_an_earlier_miss_without_adding_one(self):
        miss = prescribed(date(2026, 9, 28), (8, 8, 6))
        short = prescribed(date(2026, 10, 5), (8, 8))
        proposal = linear([short, miss], limit=2)
        self.assertEqual(loads_and_reps(proposal), [(100, 8)] * 3)
        self.assertEqual(proposal.state["misses"], 1)
        self.assertIn("incomplete_exposure", [f["code"] for f in proposal.flags])

    def test_an_attempted_short_set_still_counts_as_a_miss(self):
        for reps in ((8, 8, 5), (8, 5)):
            with self.subTest(reps=reps):
                attempt = prescribed(date(2026, 10, 5), reps)
                self.assertIs(base.missed(attempt), True)
                proposal = linear([attempt])
                self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {90})
                self.assertIn("reset targets", proposal.rationale)
                self.assertNotIn("incomplete_exposure", [f["code"] for f in proposal.flags])

    def test_every_set_logged_at_its_reps_is_neither_missed_nor_incomplete(self):
        full = prescribed(date(2026, 10, 5), (8, 8, 8))
        self.assertIs(base.missed(full), False)
        self.assertFalse(base.incomplete(full))
        self.assertEqual({load for load, _ in loads_and_reps(linear([full]))}, {102.5})

    def test_an_unknown_prescription_is_not_called_incomplete(self):
        unknown = exposure(date(2026, 10, 5), [(100, 8, 8)] * 2)
        self.assertIsNone(base.missed(unknown))
        self.assertFalse(base.incomplete(unknown))


class LinearResetStateTest(unittest.TestCase):
    def test_a_reset_is_proposed_again_until_new_training_is_logged(self):
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        first = linear([miss])
        self.assertEqual({load for load, _ in loads_and_reps(first)}, {94.5})
        self.assertEqual(first.state, {"misses": 1, "through": "2026-10-05"})
        again = linear([miss], state=first.state)
        self.assertEqual(loads_and_reps(again), loads_and_reps(first))
        self.assertEqual((again.rationale, again.state), (first.rationale, first.state))

    def test_the_next_exposure_after_a_reset_starts_a_new_count(self):
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        after_reset = linear([miss], limit=2, state={"misses": 2, "through": "2026-10-05"})
        hit = prescribed(date(2026, 10, 12), (8, 8, 8), load=94.5)
        climbed = linear([hit, miss], limit=2, state=after_reset.state)
        self.assertEqual({load for load, _ in loads_and_reps(climbed)}, {97})
        self.assertEqual(climbed.state, {"misses": 0, "through": "2026-10-12"})
        missed_again = prescribed(date(2026, 10, 12), (8, 8, 6), load=94.5)
        held = linear([missed_again, miss], limit=2, state=after_reset.state)
        self.assertEqual({load for load, _ in loads_and_reps(held)}, {94.5})
        self.assertEqual(held.state, {"misses": 1, "through": "2026-10-12"})
        short = prescribed(date(2026, 10, 12), (8, 8), load=94.5)
        incomplete = linear([short, miss], limit=2, state=after_reset.state)
        self.assertEqual({load for load, _ in loads_and_reps(incomplete)}, {94.5})
        self.assertEqual(incomplete.state, {"misses": 0, "through": "2026-10-12"})

    def test_a_reset_approved_before_resets_were_kept_is_proposed_again(self):
        miss = prescribed(date(2026, 10, 5), (5, 5, 4), load=105)
        for limit in (1, 2):
            with self.subTest(limit=limit):
                legacy = linear([miss], limit=limit, state={"misses": 0, "through": "2026-10-05"})
                self.assertEqual({load for load, _ in loads_and_reps(legacy)}, {94.5})
                self.assertIn("reset targets", legacy.rationale)
                self.assertEqual(legacy.state, {"misses": limit, "through": "2026-10-05"})
        hit = prescribed(date(2026, 10, 5), (8, 8, 8), load=105)
        climbed = linear([hit], state={"misses": 0, "through": "2026-10-05"})
        self.assertEqual({load for load, _ in loads_and_reps(climbed)}, {107.5})

    def test_a_lowered_limit_resets_a_running_count_that_reaches_it(self):
        two_running = {"misses": 2, "through": "2026-10-05"}
        old_miss = prescribed(date(2026, 10, 5), (8, 8, 6))
        before_training = linear([old_miss], limit=2, state=two_running)
        self.assertEqual({load for load, _ in loads_and_reps(before_training)}, {90})
        third_miss = prescribed(date(2026, 10, 12), (8, 8, 6))
        for limit in (2, 3):
            with self.subTest(limit=limit):
                proposal = linear([third_miss, old_miss], limit=limit, state=two_running)
                self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {90})
                self.assertEqual(proposal.state, {"misses": 3, "through": "2026-10-12"})

    def test_a_trained_reset_starts_a_new_count_after_the_limit_is_raised(self):
        kept_reset = {"misses": 2, "through": "2026-10-05"}
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        missed_at_reset = prescribed(date(2026, 10, 12), (8, 8, 6), load=94.5)
        held = linear([missed_at_reset, miss], limit=3, state=kept_reset)
        self.assertEqual({load for load, _ in loads_and_reps(held)}, {94.5})
        self.assertEqual(held.state, {"misses": 1, "through": "2026-10-12"})

    def test_a_limit_raised_before_new_training_rereads_a_kept_reset_as_a_hold(self):
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        reread = linear([miss], limit=3, state={"misses": 2, "through": "2026-10-05"})
        self.assertEqual({load for load, _ in loads_and_reps(reread)}, {105})
        self.assertIn("miss 2 of 3", reread.rationale)

    def test_a_reset_ignored_for_the_old_load_keeps_counting(self):
        kept_reset = {"misses": 2, "through": "2026-10-05"}
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        missed_again = prescribed(date(2026, 10, 12), (5, 5, 4), load=94.5, logged=105)
        reset = linear([missed_again, miss], limit=2, state=kept_reset)
        self.assertEqual({load for load, _ in loads_and_reps(reset)}, {94.5})
        self.assertIn("reset targets", reset.rationale)
        self.assertEqual(reset.state, {"misses": 3, "through": "2026-10-12"})
        hit = prescribed(date(2026, 10, 12), (8, 8, 8), load=94.5, logged=105)
        climbed = linear([hit, miss], limit=2, state=kept_reset)
        self.assertEqual({load for load, _ in loads_and_reps(climbed)}, {107.5})
        self.assertEqual(climbed.state, {"misses": 0, "through": "2026-10-12"})

    def test_an_incomplete_exposure_under_a_kept_reset_still_resets_and_raises_the_flag(self):
        kept_reset = {"misses": 2, "through": "2026-10-05"}
        miss = prescribed(date(2026, 10, 5), (5, 5, 5), load=105)
        ignored_and_short = prescribed(date(2026, 10, 12), (8, 8), load=94.5, logged=105)
        first = linear([ignored_and_short, miss], limit=2, state=kept_reset)
        again = linear([ignored_and_short, miss], limit=2, state=first.state)
        for proposal in (first, again):
            self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {94.5})
            self.assertEqual(proposal.state, {"misses": 2, "through": "2026-10-12"})
            self.assertIn("2 of 3 prescribed working sets logged on 2026-10-12", proposal.rationale)
            self.assertIn("no miss is counted", proposal.rationale)
            self.assertIn("2 misses already counted", proposal.rationale)
            self.assertNotIn("missed 2 exposures running", proposal.rationale)
            [flag] = [f for f in proposal.flags if f["code"] == "incomplete_exposure"]
            self.assertIn("still reset the load", flag["message"])

    def test_misses_then_an_incomplete_exposure_judged_together_still_reset_with_the_flag(self):
        misses = [prescribed(date(2026, 10, day), (8, 8, 6)) for day in (8, 5)]
        short = prescribed(date(2026, 10, 12), (8, 8))
        proposal = linear([short, *misses], limit=2)
        self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {90})
        self.assertEqual(proposal.state["misses"], 2)
        self.assertIn("incomplete_exposure", [f["code"] for f in proposal.flags])

    def test_any_lower_load_trained_after_a_running_count_starts_a_new_count(self):
        running = {"misses": 1, "through": "2026-10-05"}
        miss = prescribed(date(2026, 10, 5), (8, 8, 6))
        return_week_miss = prescribed(date(2026, 10, 12), (8, 8, 6), load=95)
        held = linear([return_week_miss, miss], limit=2, state=running)
        self.assertEqual({load for load, _ in loads_and_reps(held)}, {95})
        self.assertEqual(held.state, {"misses": 1, "through": "2026-10-12"})
        lowered_but_trained_heavy = prescribed(date(2026, 10, 12), (8, 8, 6), load=95, logged=100)
        reset = linear([lowered_but_trained_heavy, miss], limit=2, state=running)
        self.assertEqual({load for load, _ in loads_and_reps(reset)}, {90})
        self.assertEqual(reset.state, {"misses": 2, "through": "2026-10-12"})

    def test_a_kept_reset_without_the_through_exposure_starts_a_new_count(self):
        missed_at_reset = prescribed(date(2026, 10, 12), (8, 8, 6), load=94.5)
        held = linear([missed_at_reset], limit=2, state={"misses": 2, "through": "2026-10-05"})
        self.assertEqual({load for load, _ in loads_and_reps(held)}, {94.5})
        self.assertEqual(held.state, {"misses": 1, "through": "2026-10-12"})

    def test_a_running_count_with_an_unknown_load_runs_on(self):
        running = {"misses": 1, "through": "2026-10-05"}
        miss = prescribed(date(2026, 10, 12), (8, 8, 6))
        without_through = linear([miss], limit=2, state=running)
        self.assertEqual({load for load, _ in loads_and_reps(without_through)}, {90})
        self.assertEqual(without_through.state, {"misses": 2, "through": "2026-10-12"})
        unloaded = replace(miss, sets=tuple(replace(s, load=None) for s in miss.sets))
        no_load = linear([unloaded, prescribed(date(2026, 10, 5), (8, 8, 6))], limit=2, state=running)
        self.assertEqual(no_load.state, {"misses": 2, "through": "2026-10-12"})

    def test_misses_judged_together_with_no_reset_between_them_still_reset(self):
        misses = [prescribed(date(2026, 10, day), (8, 8, 6)) for day in (12, 8, 5)]
        proposal = linear(misses, limit=2)
        self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {90})
        self.assertEqual(proposal.state["misses"], 3)


class LadderOverrideStateTest(unittest.TestCase):
    PARAMS = {"rungs": RUNGS}

    def override_state(self, state, loads, params=PARAMS, load_mode="assisted"):
        sets = tuple(base.SetSpec(reps=8, rpe=8, load=load) for load in loads)
        return scheme("assistance_ladder").module.override_state(params, state, sets, load_mode)

    def test_an_override_onto_a_rung_moves_the_ladder_there(self):
        self.assertEqual(self.override_state({"rung": 0, "through": "2026-10-08"}, (25, 25, 25)),
                         {"rung": 1, "through": "2026-10-08"})

    def test_an_override_off_the_rungs_or_with_mixed_loads_leaves_the_state(self):
        for loads in ((22.5,) * 3, (25, 25, 30), (None,) * 3):
            with self.subTest(loads=loads):
                self.assertEqual(self.override_state({"rung": 0, "through": None}, loads),
                                 {"rung": 0, "through": None})

    def test_an_override_to_bodyweight_moves_a_bodyweight_ladder_to_its_null_rung(self):
        self.assertEqual(self.override_state({"rung": 2, "through": "2026-10-08"}, (0, 0, 0), BODYWEIGHT_RUNGS,
                                             "bodyweight"), {"rung": 0, "through": "2026-10-08"})

    def test_a_null_rung_matches_no_load_on_an_assisted_ladder(self):
        rungs = {"rungs": [{"name": "Band", "load": None}, *RUNGS]}
        self.assertEqual(self.override_state({"rung": 1, "through": None}, (0, 0, 0), rungs),
                         {"rung": 1, "through": None})

    def test_an_override_state_that_fails_the_state_schema_is_refused(self):
        plugin = scheme("assistance_ladder")
        program_doc = {"sessions": [{"id": "session-a", "exercises": [
            {"exercise_id": "pull_up", "load_mode": "assisted",
             "scheme": {"name": "assistance_ladder", "params": self.PARAMS}}]}]}
        line = {"override": {"reason": "synthetic"}, "sets": [{"type": "normal", "reps": 8, "rpe": 8, "load": 25}]}
        with mock.patch.object(plugin.module, "override_state", return_value={"rung": -1, "through": None}):
            with self.assertRaises(ValidationError) as caught:
                propose._override_state(program_doc, plugin, "session-a/pull_up", {"rung": 0, "through": None}, line)
        self.assertIn("fails its STATE schema", str(caught.exception))

    def test_override_params_that_fail_the_params_schema_are_refused(self):
        plugin = scheme("assistance_ladder")
        program_doc = {"sessions": [{"id": "session-a", "exercises": [
            {"exercise_id": "pull_up", "load_mode": "assisted",
             "scheme": {"name": "assistance_ladder", "params": {"rungs": "none"}}}]}]}
        line = {"override": {"reason": "synthetic"}, "sets": [{"type": "normal", "reps": 8, "rpe": 8, "load": 25}]}
        with self.assertRaises(ValidationError) as caught:
            propose._override_state(program_doc, plugin, "session-a/pull_up", {"rung": 0, "through": None}, line)
        self.assertIn("fail its PARAMS schema", str(caught.exception))

    def test_only_the_ladder_defines_an_override_state(self):
        for name in ("linear", "double_progression", "wave_531", "hold"):
            with self.subTest(name=name):
                self.assertIsNone(getattr(scheme(name).module, "override_state", None))


def squat_lines(doc):
    return [line for session in doc["sessions"] for line in session["exercises"]
            if line["exercise_id"] == "bb_back_squat"]


class LinearResetPipelineTest(ProposeCase):
    workouts = staticmethod(edit_sets(SQUAT, lambda wid, i, s: s.update(reps=4), workout_ids=(W[3],)))

    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "linear", {"misses_before_reset": 1})

    def assert_reset(self, doc, load=87.5):
        lines = squat_lines(doc)
        self.assertTrue(lines)
        for line in lines:
            rationale = line["provenance"]["rationale"]
            self.assertIn("reset targets 90 % of 97.5", rationale)
            self.assertNotIn("every prescribed rep was hit", rationale)
            self.assertTrue(all(coaching(s["load"]) <= load for s in working(line)), line["sets"])
        return lines

    def test_an_approved_reset_is_retained_until_new_training(self):
        [line] = self.assert_reset(self.propose()["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {87.5})
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        self.coach("overlay", "approve", FIRST_ID)
        self.assert_reset(self.propose("--dry-run")["overlay"])
        self.assert_reset(self.propose("--dry-run", env={"COACH_NOW": "2026-10-12T06:00:00Z"})["overlay"])
        next_week = self.propose("--dry-run", env={"COACH_NOW": "2026-10-18T18:00:00Z"}, week="2026-W43")
        self.assert_reset(next_week["overlay"])

    def test_a_reset_approved_before_resets_were_kept_is_retained(self):
        self.propose()
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        slot = "session-a/bb_back_squat"
        through = read_json(self.root / "data" / "state.json")["scheme_state"][slot]["pending"]["data"]["through"]
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({slot: {
            "scheme": "linear", "data": {"misses": 0, "through": through}, "pending": None}}))
        self.assert_reset(self.propose("--dry-run")["overlay"])

    def test_a_slot_trained_twice_in_one_pass_keeps_its_reset_in_both_sessions(self):
        self.edit_program(lambda doc: doc["schedule"]["params"].update(days={"mon": "session-a", "thu": "session-a"}))
        doc = self.propose("--dry-run")["overlay"]
        lines = self.assert_reset(doc)
        self.assertEqual(len(lines), 2)
        self.assertEqual([{coaching(s["load"]) for s in working(line)} for line in lines], [{87.5}, {87.5}])
        self.assertNotIn("unearned_load", codes(doc, "bb_back_squat"))


class LadderPipelineCase(ProposeCase):
    """The pull-up as an assisted ladder at its first rung, 30 kg of assistance, every logged exposure consumed."""

    def setUp(self):
        super().setUp()
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["pull_up"].update(
            load_mode="assisted", load_mode_proposed="assisted"))
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(
            load_mode="assisted", start_load=30, scheme={"name": "assistance_ladder", "params": {"rungs": RUNGS}}))
        for path in (self.root / "data" / "history").glob("????-??.json"):
            self.edit_json(path.relative_to(self.root).as_posix(), lambda doc: [
                self.assist(exercise, 30, 8) for workout in doc["workouts"] for exercise in workout["exercises"]
                if exercise["exercise_id"] == "pull_up"])
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({"session-b/pull_up": {
            "scheme": "assistance_ladder", "data": {"rung": 0, "through": "2026-10-08"}, "pending": None}}))

    @staticmethod
    def assist(exercise, load, rpe):
        exercise["load_mode"] = "assisted"
        for s in exercise["sets"]:
            s.update(weight_kg=float(load), load=units.make_load(load, "assisted", "kg"), reps=8, rpe=rpe)

    def pull_up(self, doc):
        return next(line for session in doc["sessions"] for line in session["exercises"]
                    if line["exercise_id"] == "pull_up")

    def log_pull_ups(self, day, load, rpe, overlay_id=FIRST_ID):
        """A session-b workout on `day` trained against an approved overlay, holding only the pull-up."""
        def edit(doc):
            source = next(w for w in doc["workouts"] if any(e["exercise_id"] == "pull_up" for e in w["exercises"]))
            logged = copy.deepcopy(source)
            logged.update(workout_id="10000000-0000-4000-8000-000000000099", date=day, routine_id=R_B,
                          session_id="session-b", overlay_id=overlay_id, start_time=f"{day}T18:00:00Z",
                          end_time=f"{day}T19:00:00Z",
                          exercises=[e for e in logged["exercises"] if e["exercise_id"] == "pull_up"])
            self.assist(logged["exercises"][0], load, rpe)
            doc["workouts"].append(logged)
        self.edit_json("data/history/2026-10.json", edit)

    def next_week(self):
        return self.pull_up(self.propose("--dry-run", env={"COACH_NOW": "2026-10-18T18:00:00Z"},
                                         week="2026-W43")["overlay"])


class LadderOverridePipelineTest(LadderPipelineCase):
    def approve_override_to_the_second_rung(self):
        line = self.pull_up(self.propose()["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {30})
        self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-b", "--exercise", "pull_up",
                   "--load", "25", "--reason", "synthetic: 30 kg of assistance is too easy")
        data = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]
        self.assertIn("session-b/pull_up", data["pending"])
        state = read_json(self.root / "data" / "state.json")["scheme_state"]["session-b/pull_up"]
        self.assertEqual(state["pending"], {"overlay_id": FIRST_ID, "data": {"rung": 1, "through": "2026-10-08"}})
        self.coach("overlay", "approve", FIRST_ID)

    def test_the_matching_log_at_the_approved_rung_is_its_baseline(self):
        self.approve_override_to_the_second_rung()
        self.log_pull_ups("2026-10-15", 25, 8.5)
        line = self.next_week()
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {25})
        self.assertEqual(line["target_note"], "Rung 2 of 3: 25 kg assist")
        self.assertEqual(line["provenance"]["derived_from"]["date"], "2026-10-15")

    def test_a_hit_at_the_approved_rung_climbs_from_it(self):
        self.approve_override_to_the_second_rung()
        self.log_pull_ups("2026-10-15", 25, 8)
        self.assertEqual({coaching(s["load"]) for s in working(self.next_week())}, {20})

    def test_proposing_the_week_again_keeps_the_approved_rung(self):
        self.approve_override_to_the_second_rung()
        line = self.pull_up(self.propose("--dry-run")["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {25})


class LadderDeloadPipelineTest(LadderPipelineCase):
    """The pull-up ladder with its 30 kg hit of 2026-10-08 not yet judged, so the week earns the 25 kg rung."""

    DELOAD_ID = "2026-10-12-deload"

    def setUp(self):
        super().setUp()
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"]["session-b/pull_up"]["data"].update(
            through="2026-10-01"))

    def test_an_ordinary_week_climbs_to_the_earned_rung(self):
        line = self.pull_up(self.propose("--dry-run")["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {25})
        self.assertEqual(line["target_note"], "Rung 2 of 3: 25 kg assist")

    def test_a_deload_names_the_assistance_it_delivers_and_leaves_the_climb_for_later(self):
        data = self.propose("--kind", "deload")
        self.assertEqual(data["id"], self.DELOAD_ID)
        line = self.pull_up(data["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {30})
        self.assertEqual(line["target_note"], "Rung 1 of 3: 30 kg assist; rung 2 waits for an ordinary week")
        self.assertNotIn("25", line["target_note"])

        finalized = self.coach("propose", "finalize", "--proposal", self.DELOAD_ID)["data"]
        self.assertNotIn("session-b/pull_up", finalized["pending"])
        state = read_json(self.root / "data" / "state.json")["scheme_state"]["session-b/pull_up"]
        self.assertEqual((state["data"], state["pending"]), ({"rung": 0, "through": "2026-10-01"}, None))
        self.coach("overlay", "approve", self.DELOAD_ID)
        self.log_pull_ups("2026-10-15", 30, 6, overlay_id=self.DELOAD_ID)
        line = self.next_week()
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {25})
        self.assertEqual(line["target_note"], "Rung 2 of 3: 25 kg assist")


class BodyweightLadderOverridePipelineTest(ProposeCase):
    """The pull-up as a bodyweight ladder stored at its top rung, +10 kg, every logged exposure consumed."""

    def setUp(self):
        super().setUp()
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["pull_up"].update(
            load_mode="bodyweight", load_mode_proposed="bodyweight"))
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(
            load_mode="bodyweight", start_load=10, scheme={"name": "assistance_ladder", "params": BODYWEIGHT_RUNGS}))
        for path in (self.root / "data" / "history").glob("????-??.json"):
            self.edit_json(path.relative_to(self.root).as_posix(), lambda doc: [
                self.weighted(exercise) for workout in doc["workouts"] for exercise in workout["exercises"]
                if exercise["exercise_id"] == "pull_up"])
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({"session-b/pull_up": {
            "scheme": "assistance_ladder", "data": {"rung": 2, "through": "2026-10-08"}, "pending": None}}))

    @staticmethod
    def weighted(exercise):
        exercise["load_mode"] = "bodyweight"
        for s in exercise["sets"]:
            s.update(weight_kg=10.0, load=units.make_load(10, "bodyweight", "kg"), reps=8, rpe=9)

    def pull_up(self, doc):
        return next(line for session in doc["sessions"] for line in session["exercises"]
                    if line["exercise_id"] == "pull_up")

    def test_an_approved_override_back_to_bodyweight_holds_the_ladder_on_its_first_rung(self):
        line = self.pull_up(self.propose()["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {10})
        self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-b", "--exercise", "pull_up",
                   "--load", "0", "--reason", "synthetic: elbow niggle, back to bodyweight")
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        state = read_json(self.root / "data" / "state.json")["scheme_state"]["session-b/pull_up"]
        self.assertEqual(state["pending"], {"overlay_id": FIRST_ID, "data": {"rung": 0, "through": "2026-10-08"}})
        self.coach("overlay", "approve", FIRST_ID)
        again = self.pull_up(self.propose("--dry-run")["overlay"])
        self.assertEqual({coaching(s["load"]) for s in working(again)}, {0})
        self.assertEqual(again["target_note"], "Rung 1 of 3: Bodyweight")


class FinalizeAtomicTest(ProposeCase):
    def setUp(self):
        super().setUp()
        self.propose()
        self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                   "bb_back_squat", "--load", "95", "--reason", "synthetic: bar speed was slow")
        self.overlay_path = self.root / "data" / "overlays" / f"{FIRST_ID}.json"

    def test_a_stale_routine_reference_fails_before_anything_is_written(self):
        self.edit_json("data/state.json", lambda doc: doc["hevy"]["routines"].update({
            "00000000-0000-4000-8000-000000000099": {"session_id": "session-gone"}}))
        before = self.snapshot()
        for extra in (("--dry-run",), ()):
            with self.subTest(extra=extra):
                envelope = self.coach("propose", "finalize", "--proposal", FIRST_ID, *extra, expect=1)
                self.assertIn("no program session session-gone", json.dumps(envelope["error"]))
                self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.overlay_path.exists())
        refused = self.coach("overlay", "approve", FIRST_ID, expect=1)
        self.assertFalse(refused["ok"])
        self.assertFalse(self.overlay_path.exists())

    def test_a_write_failing_before_the_overlay_leaves_none_to_approve_and_a_retry_repairs_it(self):
        write_doc = jsonio.write_doc
        for failed in ("data/state.json", "data/decisions.json"):
            def failing(path, doc, dry_run, failed=failed):
                if Path(path) == self.root / failed:
                    raise OSError("synthetic: disk full")
                return write_doc(path, doc, dry_run)

            with self.subTest(failed=failed):
                with mock.patch.object(jsonio, "write_doc", side_effect=failing):
                    self.coach("propose", "finalize", "--proposal", FIRST_ID, expect=9)
                self.assertFalse(self.overlay_path.exists())
                self.assertFalse(self.coach("overlay", "approve", FIRST_ID, expect=1)["ok"])
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        self.coach("overlay", "approve", FIRST_ID)
        decisions = read_json(self.root / "data" / "decisions.json")["decisions"]
        self.assertEqual([d["overlay_id"] for d in decisions], [FIRST_ID])

    def test_a_normal_finalize_writes_coherent_records_and_is_safe_to_retry(self):
        first = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]
        written = {path: read_json(self.root / path) for path in
                   (first["path"], "data/decisions.json", "data/state.json")}
        self.assertEqual([d["overlay_id"] for d in written["data/decisions.json"]["decisions"]], [FIRST_ID])
        pending = {slot: entry["pending"]["overlay_id"]
                   for slot, entry in written["data/state.json"]["scheme_state"].items() if entry["pending"]}
        self.assertEqual(set(pending), set(first["pending"]))
        self.assertEqual(set(pending.values()), {FIRST_ID})
        again = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]
        self.assertEqual(again["decisions"], [])
        self.assertEqual({path: read_json(self.root / path) for path in written}, written)
        self.coach("overlay", "approve", FIRST_ID)
        settled = self.propose("--dry-run", env={"COACH_NOW": "2026-10-18T18:00:00Z"}, week="2026-W43")["settled"]
        self.assertEqual({row["action"] for row in settled}, {"promoted"})


class ComputeGuidanceTest(unittest.TestCase):
    def test_program_week_settles_incomplete_exposures_ladder_overrides_and_refused_finalizes(self):
        compute = flat(step_text("program-week", "compute.md"))
        for phrase in ("`incomplete_exposure`", "skipped or failed", "`misses_before_reset`",
                       "resets anyway and needs no question", "moves the ladder to that rung",
                       "A refused finalize writes nothing", "a deload or light week still cuts it"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, compute)


if __name__ == "__main__":
    unittest.main()
