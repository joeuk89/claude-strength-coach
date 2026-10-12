"""The rpe_anchored, assistance_ladder, maintenance and hold progression schemes (contract C23); wave_531 is in
test_wave_531."""

import unittest
from dataclasses import replace
from datetime import date, timedelta

from coach import plugins, render, stats
from coach.plugins import base
from tests.support import VALID, run_cli
from tests.test_propose import ProposeCase, coaching, find_line, working

SESSION_DATE = date(2026, 10, 12)
SQUAT = base.ExerciseInfo(id="bb_back_squat", name="Back squat", pattern="squat", muscles={}, equipment="barbell",
                          load_mode="total", increment=2.5, is_compound=True)
PULL_UP = base.ExerciseInfo(id="pull_up", name="Pull-up", pattern="vertical_pull", muscles={}, equipment="bodyweight",
                            load_mode="assisted", increment=5, is_compound=True, load_direction=-1)
THREE_FIVES = ({"count": 3, "type": "normal", "reps": 5, "rpe": 7},)
TOP_AND_BACK_OFFS = ({"count": 1, "type": "normal", "reps": 4, "rpe": 8},
                     {"count": 3, "type": "normal", "reps": 6, "rpe": 7})


def scheme(name):
    plugin = plugins.load().get("scheme", name)
    assert plugin is not None, f"no valid scheme {name}"
    return plugin


def context(name, params=None, state=None, exposures=(), e1rm=None, exercise=SQUAT, sets=THREE_FIVES,
            start_load=100, days_off=0, session_date=SESSION_DATE, week_kind="weekly"):
    plugin = scheme(name)
    merged, errors = plugins.merged_params(plugin, params or {})
    assert not errors, errors
    slot = base.SlotInfo(session_id="session-a", sets=tuple(sets), rest_seconds=180, cues=None, constraints=(),
                         start_load=start_load)
    return base.SchemeContext(
        today=session_date - timedelta(days=1), session_date=session_date, unit="kg", week_kind=week_kind,
        exercise=exercise, slot=slot, params=merged, state=dict(state if state is not None else plugin.module.STATE[
            "initial"]), exposures=tuple(exposures), e1rm=e1rm, last_prescription=None, last_override=None,
        days_off=days_off, constraints=(), scheme=name)


def exposure(day, sets, exercise=SQUAT, workout_id=None, week_kind=None):
    """`sets` as (load, reps, rpe) tuples, every one a normal working set."""
    logged = tuple(base.LoggedSet(index=i, type="normal", reps=reps, rpe=rpe, load=load)
                   for i, (load, reps, rpe) in enumerate(sets))
    return base.Exposure(date=day, workout_id=workout_id or f"w-{day.isoformat()}", session_id="session-a",
                         exercise_id=exercise.id, load_mode=exercise.load_mode, sets=logged, week_kind=week_kind)


def run(ctx):
    proposal = scheme(ctx.scheme).module.propose(ctx)
    assert not plugins.state_errors(scheme(ctx.scheme), proposal.state), proposal.state
    return proposal


def loads_and_reps(proposal):
    return [(s.load, s.reps) for s in proposal.sets if s.working]


class MaintenanceTest(unittest.TestCase):
    def test_repeats_the_last_valid_exposure_at_the_program_set_count(self):
        newest = exposure(date(2026, 10, 5), [(102.5, 4, 8), (102.5, 4, 8)])
        older = exposure(date(2026, 9, 28), [(100, 5, 7)] * 3)
        proposal = run(context("maintenance", exposures=(newest, older)))
        self.assertEqual(loads_and_reps(proposal), [(102.5, 4)] * 3)
        self.assertIs(proposal.derived_from, newest)
        self.assertEqual([s.rpe for s in proposal.sets], [7, 7, 7])

    def test_skips_excluded_suspect_and_deload_exposures(self):
        deload = exposure(date(2026, 10, 5), [(80, 5, 6)] * 2, week_kind="deload")
        suspect = replace(exposure(date(2026, 10, 3), [(140, 5, 7)]), suspect=True)
        valid = exposure(date(2026, 9, 28), [(100, 5, 7)] * 3)
        proposal = run(context("maintenance", exposures=(deload, suspect, valid)))
        self.assertEqual(loads_and_reps(proposal), [(100, 5)] * 3)

    def test_never_proposes_a_higher_load_whatever_was_hit(self):
        easy = exposure(date(2026, 10, 5), [(100, 8, 5)] * 3)
        proposal = run(context("maintenance", exposures=(easy,)))
        self.assertTrue(all(load <= 100 for load, _ in loads_and_reps(proposal)))

    def test_with_no_exposure_it_starts_at_the_start_load(self):
        proposal = run(context("maintenance"))
        self.assertEqual(loads_and_reps(proposal), [(100, 5)] * 3)
        self.assertIsNone(proposal.derived_from)

    def test_the_default_return_band_applies(self):
        source = exposure(date(2026, 9, 14), [(100, 5, 7)] * 3)
        ctx = context("maintenance", exposures=(source,), days_off=28)
        decayed = scheme("maintenance").module.decay(ctx, run(ctx), 28)
        self.assertEqual(loads_and_reps(decayed), [(90, 5)] * 2)


class HoldAfterOnlyRecoveryWorkTest(unittest.TestCase):
    """The only approved line is return work: the program's sets come back, at the load the return week set."""

    def recovery_ctx(self, exposures=()):
        last = {"overlay_id": "o-0001", "session_id": "session-a", "date": "2026-10-05",
                "exercise_id": SQUAT.id, "load_mode": "total", "override": None, "recovery": "return",
                "sets": (base.SetSpec.from_dict({"type": "normal", "reps": 5, "rpe": 7}, load=90),) * 2}
        return replace(context("hold", exposures=exposures), last_prescription=last)

    def test_the_program_sets_at_the_load_the_return_week_logged(self):
        logged = exposure(date(2026, 10, 5), [(92.5, 5, 6)] * 2, week_kind="return")
        proposal = run(self.recovery_ctx((logged,)))
        self.assertEqual(loads_and_reps(proposal), [(92.5, 5)] * 3)
        self.assertIn("in o-0001, is return work", proposal.rationale)
        self.assertIn("the load logged on 2026-10-05", proposal.rationale)

    def test_with_nothing_logged_the_program_sets_at_the_approved_load(self):
        proposal = run(self.recovery_ctx())
        self.assertEqual(loads_and_reps(proposal), [(90, 5)] * 3)
        self.assertIn("at its load", proposal.rationale)


class AssistedReturnAndDeloadTest(unittest.TestCase):
    """More assistance is a lighter lift, so return bands and deloads keep the assistance and cut sets instead."""

    SOURCE = replace(exposure(date(2026, 9, 14), [(20, 5, 7)] * 3, exercise=PULL_UP),
                     prescribed=base.expand(THREE_FIVES))

    def assisted(self, name, days_off=0, week_kind="weekly", sets=THREE_FIVES):
        return context(name, exposures=(self.SOURCE,), exercise=PULL_UP, sets=sets, start_load=20,
                       days_off=days_off, week_kind=week_kind)

    def test_a_return_band_keeps_the_derived_from_assistance_and_cuts_a_set(self):
        for name in ("linear", "double_progression", "maintenance"):
            for days_off in (15, 28):
                with self.subTest(scheme=name, days_off=days_off):
                    ctx = self.assisted(name, days_off=days_off)
                    decayed = scheme(name).module.decay(ctx, run(ctx), days_off)
                    self.assertEqual({load for load, _ in loads_and_reps(decayed)}, {20})
                    self.assertEqual(len(loads_and_reps(decayed)), 2)

    def test_a_return_band_never_cuts_assistance_the_proposal_raised(self):
        ctx = self.assisted("linear", days_off=28)
        proposal = run(ctx)
        raised = replace(proposal, sets=base.with_load(proposal.sets, 30))
        decayed = scheme("linear").module.decay(ctx, raised, 28)
        self.assertEqual({load for load, _ in loads_and_reps(decayed)}, {30})

    def test_the_43_plus_band_caps_rpe_and_keeps_the_assistance(self):
        ctx = self.assisted("linear", days_off=60, sets=({"count": 3, "type": "normal", "reps": 5, "rpe": 9},))
        decayed = scheme("linear").module.decay(ctx, run(ctx), 60)
        self.assertEqual(loads_and_reps(decayed), [(20, 5)] * 2)
        self.assertEqual({s.rpe for s in decayed.sets if s.working}, {7})

    def test_the_standard_deload_of_an_assisted_linear_line_keeps_its_assistance(self):
        for name in ("standard", "scheme"):
            with self.subTest(transform=name):
                ctx = self.assisted("linear", week_kind="deload")
                proposal = run(ctx)
                self.assertEqual({load for load, _ in loads_and_reps(proposal)}, {15})
                transform = plugins.load().get("transform", name)
                params, _ = plugins.merged_params(transform, {})
                deloaded = transform.module.apply(replace(ctx, params=params), proposal)
                self.assertEqual(loads_and_reps(deloaded), [(20, 5)] * 2)
                self.assertEqual({s.rpe for s in deloaded.sets if s.working}, {6})

    def test_light_and_return_weeks_hold_the_derived_from_assistance(self):
        for name in ("light", "return"):
            with self.subTest(transform=name):
                ctx = self.assisted("linear")
                transform = plugins.load().get("transform", name)
                params, _ = plugins.merged_params(transform, {})
                lightened = transform.module.apply(replace(ctx, params=params), run(ctx))
                self.assertEqual(loads_and_reps(lightened), [(20, 5)] * 2)

    def test_other_load_modes_still_scale(self):
        source = exposure(date(2026, 9, 14), [(100, 5, 7)] * 3)
        ctx = context("linear", exposures=(source,), days_off=28)
        self.assertEqual(loads_and_reps(base.default_decay(ctx, run(ctx), 28)), [(90, 5)] * 2)
        self.assertEqual(loads_and_reps(base.standard_deload(run(ctx), **base.STANDARD_DELOAD)), [(90, 5)] * 2)


class RpeAnchoredTest(unittest.TestCase):
    PARAMS = {"top_reps": 3, "top_rpe": 8, "backoff_sets": 3}
    STARTER_SETS = ({"count": 1, "type": "normal", "reps": 5, "rpe": 8},
                    {"count": 3, "type": "normal", "reps": 5, "rpe": 7})

    def test_top_set_from_the_e1rm_inverse_then_back_offs_from_it_one_rpe_lower(self):
        proposal = run(context("rpe_anchored", self.PARAMS, e1rm=121.88))
        top, *backoffs = [s for s in proposal.sets if s.working]
        self.assertEqual((top.load, top.reps, top.rpe), (102.5, 3, 8))
        self.assertEqual([(s.load, s.reps, s.rpe) for s in backoffs], [(100, 3, 7)] * 3)
        self.assertTrue(proposal.round_down)

    def test_starter_back_offs_come_from_the_e1rm_at_their_rpe_floored_to_the_increment(self):
        proposal = run(context("rpe_anchored", {}, e1rm=121.88, sets=self.STARTER_SETS))
        top, *backoffs = [s for s in proposal.sets if s.working]
        self.assertEqual((top.load, top.reps, top.rpe), (97.5, 5, 8))
        self.assertEqual([(s.load, s.reps, s.rpe) for s in backoffs], [(95, 5, 7)] * 3)
        self.assertLessEqual(95, stats.load_for(121.88, 5, 7))
        self.assertAlmostEqual(stats.load_for(121.88, 5, 7) / stats.load_for(121.88, 5, 8), 0.97, delta=0.005)
        self.assertIn("RPE 7", proposal.rationale)

    def test_an_explicit_backoff_pct_overrides_the_e1rm_rule_and_keeps_the_back_off_rpe(self):
        proposal = run(context("rpe_anchored", {"backoff_pct": 0.9}, e1rm=121.88, sets=self.STARTER_SETS))
        top, *backoffs = [s for s in proposal.sets if s.working]
        self.assertEqual(top.load, 97.5)
        self.assertEqual([(s.load, s.reps, s.rpe) for s in backoffs], [(87.75, 5, 7)] * 3)
        self.assertIn("backoff_pct", proposal.rationale)

    def test_backoff_rpe_comes_from_the_param_else_the_second_group_else_one_below_the_top(self):
        def backoff_rpes(params, sets):
            proposal = run(context("rpe_anchored", params, e1rm=121.88, sets=sets))
            return {s.rpe for s in proposal.sets[1:] if s.working}

        self.assertEqual(backoff_rpes({"backoff_rpe": 6.5}, self.STARTER_SETS), {6.5})
        self.assertEqual(backoff_rpes({}, self.STARTER_SETS), {7})
        no_rpe = (self.STARTER_SETS[0], {"count": 3, "type": "normal", "reps": 5})
        self.assertEqual(backoff_rpes({}, no_rpe), {7})
        self.assertEqual(backoff_rpes({"top_rpe": 9}, no_rpe), {8})

    def test_a_back_off_never_exceeds_the_top_set(self):
        for params in ({"backoff_rpe": 9}, {"backoff_rpe": 8, "backoff_reps": 3}, {"backoff_pct": 1}):
            with self.subTest(params=params):
                proposal = run(context("rpe_anchored", params, e1rm=121.88, sets=self.STARTER_SETS))
                top, *backoffs = [s for s in proposal.sets if s.working]
                self.assertTrue(all(s.load <= top.load for s in backoffs), proposal.sets)
        proposal = run(context("rpe_anchored", {"backoff_rpe": 9}, e1rm=121.88, sets=self.STARTER_SETS))
        self.assertEqual({s.load for s in proposal.sets if s.working}, {97.5})
        self.assertIn("capped at the top set", proposal.rationale)

    def test_the_logged_top_set_recalibrates_the_next_week(self):
        heavier = exposure(date(2026, 10, 5), [(110, 3, 9), (99, 3, None), (99, 3, None)])
        proposal = run(context("rpe_anchored", self.PARAMS, exposures=(heavier,), e1rm=121.88))
        self.assertEqual(proposal.sets[0].load, 105)
        self.assertIn("2026-10-05", proposal.rationale)
        slower = exposure(date(2026, 10, 5), [(100, 3, 9.5)])
        proposal = run(context("rpe_anchored", self.PARAMS, exposures=(slower,), e1rm=121.88))
        self.assertEqual(proposal.sets[0].load, 95)

    def test_null_params_read_the_program_s_top_set_and_back_offs(self):
        sets = ({"count": 1, "type": "warmup", "reps": 5}, {"count": 1, "type": "normal", "reps": 2, "rpe": 9},
                {"count": 4, "type": "normal", "reps": 4})
        proposal = run(context("rpe_anchored", {"backoff_pct": 0.8}, e1rm=121.88, sets=sets))
        self.assertEqual(proposal.sets[0].type, "warmup")
        top, *backoffs = [s for s in proposal.sets if s.working]
        self.assertEqual((top.load, top.reps, top.rpe), (110, 2, 9))
        self.assertEqual([(s.load, s.reps, s.rpe) for s in backoffs], [(88, 4, 8)] * 4)

    def test_with_no_e1rm_the_top_set_holds(self):
        proposal = run(context("rpe_anchored", self.PARAMS))
        self.assertEqual(proposal.sets[0].load, 100)
        self.assertIn("no e1RM", proposal.rationale)

    def test_with_no_e1rm_the_back_offs_sit_at_ninety_percent_and_keep_the_programmed_rpe(self):
        proposal = run(context("rpe_anchored", {}, sets=TOP_AND_BACK_OFFS))
        self.assertEqual([(s.load, s.reps, s.rpe) for s in proposal.sets if s.working],
                         [(100, 4, 8)] + [(90, 6, 7)] * 3)
        self.assertFalse(proposal.round_down)
        self.assertIn("provisional", proposal.rationale)
        self.assertIn("RPE 7", proposal.rationale)

    def test_with_no_e1rm_a_backoff_rpe_param_wins_over_the_program(self):
        proposal = run(context("rpe_anchored", {"backoff_rpe": 6.5}, sets=self.STARTER_SETS))
        self.assertEqual({s.rpe for s in proposal.sets[1:] if s.working}, {6.5})

    def test_a_programmed_back_off_rpe_is_the_same_with_or_without_an_e1rm(self):
        one_group = ({"count": 4, "type": "normal", "reps": 5, "rpe": 8},)
        for params, sets, expected in (({}, TOP_AND_BACK_OFFS, 7), ({}, one_group, 7), (self.PARAMS, THREE_FIVES, 7),
                                       ({"backoff_rpe": 6.5}, one_group, 6.5)):
            with self.subTest(params=params, sets=sets):
                for e1rm in (121.88, None):
                    proposal = run(context("rpe_anchored", params, e1rm=e1rm, sets=sets))
                    self.assertEqual({s.rpe for s in proposal.sets[1:] if s.working}, {expected}, e1rm)

    def test_with_no_e1rm_an_unprogrammed_back_off_rpe_stays_absent(self):
        no_rpe = (self.STARTER_SETS[0], {"count": 3, "type": "normal", "reps": 5})
        single_top = ({"count": 1, "type": "normal", "reps": 5, "rpe": 8},)
        for params, sets in (({}, no_rpe), ({"backoff_sets": 3}, single_top)):
            with self.subTest(params=params, sets=sets):
                proposal = run(context("rpe_anchored", params, sets=sets))
                self.assertEqual([s.rpe for s in proposal.sets[1:] if s.working], [None] * 3)
                self.assertNotIn("at RPE", proposal.rationale)

    def test_with_an_e1rm_but_no_top_set_rpe_the_back_offs_hold_and_keep_their_rpe(self):
        sets = ({"count": 1, "type": "normal", "reps": 4}, {"count": 3, "type": "normal", "reps": 6, "rpe": 7})
        proposal = run(context("rpe_anchored", {}, e1rm=120, sets=sets))
        self.assertEqual([(s.load, s.reps, s.rpe) for s in proposal.sets if s.working],
                         [(100, 4, None)] + [(90, 6, 7)] * 3)
        self.assertIn("no top-set reps or RPE", proposal.rationale)
        self.assertIn("RPE 7", proposal.rationale)
        self.assertNotIn("provisional", proposal.rationale)

    def test_the_hold_rationale_names_no_missing_rep_target(self):
        proposal = run(context("rpe_anchored", {}, sets=({"count": 4, "type": "normal", "rpe": 8},)))
        self.assertNotIn("None", proposal.rationale)
        self.assertIn("3 back-off sets at 90 % of it at RPE 7", proposal.rationale)

    def test_with_no_load_to_hold_the_rationale_leaves_the_first_loads_to_the_coach(self):
        proposal = run(context("rpe_anchored", {}, sets=TOP_AND_BACK_OFFS, start_load=None))
        self.assertEqual([(s.load, s.rpe) for s in proposal.sets if s.working], [(None, 8)] + [(None, 7)] * 3)
        self.assertIn("coach picks the first loads", proposal.rationale)
        self.assertIn("3×6 at RPE 7", proposal.rationale)
        for absent in ("no load", "% of it", "provisional"):
            self.assertNotIn(absent, proposal.rationale)

    def test_programs_only_lines_with_an_e1rm(self):
        self.assertEqual(scheme("rpe_anchored").module.LOAD_MODES, base.E1RM_MODES)

    def test_cites_the_back_off_claim(self):
        self.assertIn("rn:progression-training-age.8", scheme("rpe_anchored").module.CITES)


class AssistanceLadderTest(unittest.TestCase):
    PARAMS = {"rungs": [{"name": "heavy band", "load": 40}, {"name": "medium band", "load": 30},
                        {"name": "light band", "load": 20}], "reps": 8, "sets": 3, "rpe": 8}
    SETS = ({"count": 3, "type": "normal", "reps": 8, "rpe": 8},)

    def ladder(self, state, exposures=(), days_off=0):
        exposures = tuple(replace(e, prescribed=base.expand(self.SETS)) for e in exposures)
        return context("assistance_ladder", self.PARAMS, state=state, exposures=exposures, exercise=PULL_UP,
                       sets=self.SETS, start_load=None, days_off=days_off)

    def test_every_set_at_target_reps_moves_up_one_rung(self):
        hit = exposure(date(2026, 10, 5), [(30, 8, 8)] * 3, exercise=PULL_UP)
        proposal = run(self.ladder({"rung": 1, "through": "2026-09-28"}, (hit,)))
        self.assertEqual(loads_and_reps(proposal), [(20, 8)] * 3)
        self.assertEqual(proposal.state, {"rung": 2, "through": "2026-10-05"})
        self.assertIn("light band", proposal.target_note)

    def test_a_short_set_or_a_set_over_the_target_rpe_holds(self):
        for sets in ([(30, 8, 8), (30, 8, 8), (30, 7, 8)], [(30, 8, 8), (30, 8, 9), (30, 8, 8)],
                     [(30, 8, 8), (30, 8, 8)]):
            with self.subTest(sets=sets):
                short = exposure(date(2026, 10, 5), sets, exercise=PULL_UP)
                proposal = run(self.ladder({"rung": 1, "through": "2026-09-28"}, (short,)))
                self.assertEqual(loads_and_reps(proposal), [(30, 8)] * 3)
                self.assertEqual(proposal.state["rung"], 1)

    def test_two_hits_in_one_week_climb_one_rung(self):
        hits = tuple(exposure(date(2026, 10, d), [(40, 8, 8)] * 3, exercise=PULL_UP) for d in (8, 5))
        proposal = run(self.ladder({"rung": 0, "through": "2026-10-01"}, hits))
        self.assertEqual(proposal.state, {"rung": 1, "through": "2026-10-08"})
        self.assertEqual(loads_and_reps(proposal), [(30, 8)] * 3)

    def test_the_newest_exposure_decides(self):
        hit = exposure(date(2026, 10, 5), [(40, 8, 8)] * 3, exercise=PULL_UP)
        short = exposure(date(2026, 10, 8), [(40, 8, 8), (40, 8, 8), (40, 6, 8)], exercise=PULL_UP)
        proposal = run(self.ladder({"rung": 0, "through": "2026-10-01"}, (short, hit)))
        self.assertEqual(proposal.state["rung"], 0)

    def test_an_exposure_is_counted_once(self):
        hit = exposure(date(2026, 10, 5), [(30, 8, 8)] * 3, exercise=PULL_UP)
        proposal = run(self.ladder({"rung": 1, "through": "2026-10-05"}, (hit,)))
        self.assertEqual(proposal.state["rung"], 1)

    def test_a_new_ladder_judges_only_the_newest_exposure(self):
        hits = tuple(exposure(date(2026, 10, d), [(40, 8, 8)] * 3, exercise=PULL_UP) for d in (5, 1))
        proposal = run(self.ladder({"rung": 0, "through": None}, hits))
        self.assertEqual(proposal.state, {"rung": 1, "through": "2026-10-05"})

    def test_the_top_rung_holds(self):
        hit = exposure(date(2026, 10, 5), [(20, 8, 8)] * 3, exercise=PULL_UP)
        proposal = run(self.ladder({"rung": 2, "through": "2026-09-28"}, (hit,)))
        self.assertEqual((loads_and_reps(proposal)[0], proposal.state["rung"]), ((20, 8), 2))

    def test_a_return_band_steps_back_rungs_instead_of_cutting_load(self):
        source = exposure(date(2026, 9, 21), [(20, 8, 8)] * 3, exercise=PULL_UP)
        for days_off, rung, load in ((15, 1, 30), (28, 0, 40)):
            with self.subTest(days_off=days_off):
                ctx = self.ladder({"rung": 2, "through": "2026-09-21"}, (source,), days_off=days_off)
                decayed = scheme("assistance_ladder").module.decay(ctx, run(ctx), days_off)
                self.assertEqual(loads_and_reps(decayed), [(load, 8)] * 2)
                self.assertEqual(decayed.state["rung"], rung)
                self.assertIn(self.PARAMS["rungs"][rung]["name"], decayed.target_note)

    def test_a_hit_before_the_layoff_still_steps_back_from_the_rung_trained(self):
        hit = exposure(date(2026, 9, 27), [(30, 8, 8)] * 3, exercise=PULL_UP)
        ctx = self.ladder({"rung": 1, "through": "2026-09-20"}, (hit,), days_off=15)
        decayed = scheme("assistance_ladder").module.decay(ctx, run(ctx), 15)
        self.assertEqual(decayed.state["rung"], 0)
        self.assertEqual(loads_and_reps(decayed), [(40, 8)] * 2)

    def test_bodyweight_variations_carry_no_added_load(self):
        params = {"rungs": [{"name": "incline push-up"}, {"name": "push-up"}]}
        push_up = replace(SQUAT, id="push_up", load_mode="bodyweight", load_direction=1)
        proposal = run(context("assistance_ladder", params, exercise=push_up,
                               sets=({"count": 3, "type": "normal", "reps": 12, "rpe": 8},), start_load=0))
        self.assertEqual(loads_and_reps(proposal), [(0, 12)] * 3)
        self.assertIn("incline push-up", proposal.target_note)

    def final_note(self, loads, week_kind="weekly", params=None):
        ctx = replace(self.ladder({"rung": 0, "through": "2026-09-28"}), week_kind=week_kind,
                      params=dict(self.PARAMS, **(params or {})))
        proposal = base.Proposal(sets=(), rationale="x", derived_from=None, state={"rung": 1, "through": None},
                                 flags=(), target_note="Rung 2 of 3: medium band")
        sets = tuple(base.SetSpec(reps=8, rpe=6, load=load) for load in loads)
        return scheme("assistance_ladder").module.final_note(ctx, proposal, sets)

    def test_the_final_note_names_the_rung_the_sets_deliver(self):
        self.assertEqual(self.final_note((30, 30)), "Rung 2 of 3: medium band")
        self.assertEqual(self.final_note((20, 20)), "Rung 3 of 3: light band")
        self.assertEqual(self.final_note((40, 40), "deload"),
                         "Rung 1 of 3: heavy band; rung 2 waits for an ordinary week")

    def test_a_final_note_off_the_rungs_names_the_load_or_nothing(self):
        self.assertEqual(self.final_note((35, 35)), "Between rungs this week: 35 kg of assistance")
        self.assertIsNone(self.final_note((40, 30)))
        self.assertEqual(self.final_note((None, None), params={"rungs": [{"name": "a", "load": None}] * 3}),
                         "Rung 2 of 3: medium band")

    def variation_note(self, proposed, load, week_kind="weekly", last_override=None):
        params = {"rungs": [{"name": "negative"}, {"name": "pull-up"}, {"name": "weighted", "load": 10}]}
        bodyweight = replace(PULL_UP, load_mode="bodyweight", load_direction=1)
        ctx = replace(context("assistance_ladder", params, exercise=bodyweight, sets=self.SETS, start_load=0,
                              week_kind=week_kind), last_override=last_override)
        proposal = base.Proposal(sets=(), rationale="x", derived_from=None, state={"rung": proposed, "through": None},
                                 flags=(), target_note=f"Rung {proposed + 1} of 3: proposed")
        sets = (base.SetSpec(reps=8, rpe=6, load=load),) * 3
        return scheme("assistance_ladder").module.final_note(ctx, proposal, sets)

    def test_a_variation_rung_sharing_its_load_keeps_its_name(self):
        for week_kind in ("weekly", "deload"):
            with self.subTest(week_kind=week_kind):
                self.assertEqual(self.variation_note(1, 0, week_kind), "Rung 2 of 3: pull-up")
                self.assertEqual(self.variation_note(0, 0, week_kind), "Rung 1 of 3: negative")

    def test_a_load_moved_onto_shared_rungs_names_the_nearest_one_below(self):
        self.assertEqual(self.variation_note(2, 0), "Rung 2 of 3: pull-up")
        self.assertEqual(self.variation_note(2, 0, "deload"),
                         "Rung 2 of 3: pull-up; rung 3 waits for an ordinary week")

    def test_a_deload_under_a_standing_override_promises_no_climb(self):
        standing = {"standing": True, "id": "d1", "until": "2026-11-15"}
        self.assertEqual(self.variation_note(2, 0, "deload", standing), "Rung 2 of 3: pull-up")
        self.assertEqual(self.variation_note(2, 0, "deload", dict(standing, standing=False)),
                         "Rung 2 of 3: pull-up; rung 3 waits for an ordinary week")


class RpeAnchoredProposeTest(ProposeCase):
    def test_top_set_and_back_offs_from_the_e1rm_rounded_down(self):
        self.set_scheme("session-a", "bb_back_squat", "rpe_anchored", {"top_reps": 3, "top_rpe": 8, "backoff_sets": 3})
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual([(coaching(s["load"]), s["reps"], s["rpe"]) for s in working(find_line(doc, "bb_back_squat"))],
                         [(102.5, 3, 8), (100, 3, 7), (100, 3, 7), (100, 3, 7)])
        self.assertLessEqual(102.5, stats.load_for(121.88, 3, 8))
        self.assertLessEqual(100, stats.load_for(121.88, 3, 7))
        self.assertEqual([f for f in doc["flags"] if f["severity"] == "block"], [])


class RpeAnchoredNoLogProposeTest(ProposeCase):
    synced = False

    def test_the_overlay_and_its_target_keep_the_programmed_back_off_rpe(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            scheme={"name": "rpe_anchored", "params": {}}, sets=list(TOP_AND_BACK_OFFS)))
        doc = self.propose("--dry-run")["overlay"]
        line = find_line(doc, "bb_back_squat")
        self.assertEqual([(s["reps"], s["rpe"]) for s in working(line)], [(4, 8)] + [(6, 7)] * 3)
        self.assertIn("no e1RM", line["provenance"]["rationale"])
        self.assertRegex(render.target_line(line), r"^Target: 1×4 @ .+ @ RPE 8 \+ 3×6 @ .+ @ RPE 7$")
        self.assertEqual([f for f in doc["flags"] if f["severity"] == "block"], [])


class LadderAndMaintenanceProposeTest(ProposeCase):
    def test_pull_up_ladder_moves_up_from_the_newest_exposure(self):
        self.set_scheme("session-b", "pull_up", "assistance_ladder", {"rungs": [
            {"name": "pull-up", "load": 0}, {"name": "weighted pull-up", "load": 2.5},
            {"name": "heavier weighted pull-up", "load": 5}]})
        doc = self.propose("--dry-run")["overlay"]
        line = find_line(doc, "pull_up")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {2.5})
        self.assertEqual(line["target_note"], "Rung 2 of 3: weighted pull-up")

    def test_maintenance_repeats_the_squat(self):
        self.set_scheme("session-a", "bb_back_squat", "maintenance")
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({(coaching(s["load"]), s["reps"]) for s in working(find_line(doc, "bb_back_squat"))},
                         {(97.5, 5)})


class PluginListingTest(unittest.TestCase):
    NAMES = ("rpe_anchored", "wave_531", "assistance_ladder", "maintenance", "next_in_sequence", "explicit_calendar")

    def test_each_new_plugin_validates_and_is_listed_with_its_summary(self):
        code, envelope, _ = run_cli(["--root", str(VALID), "plugins", "validate"])
        self.assertEqual(code, 0, envelope)
        code, envelope, _ = run_cli(["--root", str(VALID), "plugins", "list"])
        listed = {p["name"]: p for p in envelope["data"]["plugins"]}
        registry = plugins.load()
        for name in self.NAMES:
            with self.subTest(name=name):
                self.assertTrue(listed[name]["valid"])
                self.assertEqual(listed[name]["summary"], registry.find(name)[0].module.SUMMARY)
                self.assertTrue(listed[name]["summary"].endswith("."))


if __name__ == "__main__":
    unittest.main()
