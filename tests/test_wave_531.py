"""The 5/3/1 wave: state from trained work, rep-out sets, back-offs, deload, return weeks and the training max (C23)."""

import copy
import importlib
import unittest
from dataclasses import replace
from datetime import date

from coach import overlay, plugins, propose, render, sheets, stats, units
from coach.errors import UsageError
from coach.plugins import base
from tests.support.history import R_A, read_json
from tests.test_progression_schemes import SQUAT, context, run, scheme
from tests.test_propose import FIRST_ID, LayoffCase, ProposeCase, codes, coaching, find_line, working

SLOT = "session-a/bb_back_squat"
BACK_OFFS = {"count": 3, "type": "normal", "reps": 5, "rpe": 7}
WAVE_GROUP = {"count": 3, "type": "normal", "reps": 5}
THROUGH = {"date": "2026-10-01", "workout_id": None}
WAVE_SETS = 3


def state(completed=0, training_max=100, through=THROUGH):
    return {"completed_weeks": completed, "training_max": training_max, "through": through}


def wave_sets(week, training_max=100, rep_out=True):
    found = [base.SetSpec(reps=reps, load=round(training_max * pct, 4))
             for pct, reps in scheme("wave_531").module.WEEKS[week]]
    if rep_out:
        found[-1] = replace(found[-1], rep_out=True, rpe=base.REP_OUT_RPE_CAP)
    return tuple(found)


def trained(day, week, training_max=100, reps=None, rpes=None, loads=None, logged_sets=3, workout_id=None,
            **fields):
    """An exposure prescribed `week` of the wave at `training_max`, logged with `loads` (default: the prescribed
    loads), `reps` (default: the prescribed reps, two more on the rep-out set) and `rpes`."""
    prescribed = wave_sets(week, training_max)
    reps = reps or [s.reps + (2 if s.rep_out else 0) for s in prescribed]
    rpes = rpes or [None] * len(prescribed)
    loads = loads or [s.load for s in prescribed]
    logged = tuple(base.LoggedSet(index=i, type="normal", reps=r, rpe=rpe, load=load)
                   for i, (r, rpe, load) in enumerate(zip(reps, rpes, loads)))[:logged_sets]
    found = base.Exposure(date=day, workout_id=workout_id or f"w-{day.isoformat()}", session_id="session-a",
                          exercise_id=SQUAT.id, load_mode="total", sets=logged, prescribed=prescribed,
                          week_kind="weekly")
    return replace(found, **fields)


def wave(state_=None, exposures=(), sets=(WAVE_GROUP,), **kwargs):
    return context("wave_531", kwargs.pop("params", None), state=state_ if state_ is not None else state(),
                   exposures=tuple(sorted(exposures, key=lambda e: (e.date, e.workout_id), reverse=True)),
                   sets=sets, **kwargs)


def shape(proposal):
    return [(s.load, s.reps, s.rep_out, s.rpe) for s in proposal.sets if s.working]


def flag_codes(proposal):
    return [f["code"] for f in proposal.flags]


class WaveWeeksTest(unittest.TestCase):
    def test_each_week_s_percentages_end_in_a_rep_out_set_capped_at_rpe_9(self):
        weeks = {1: [(65, 5), (75, 5), (85, 5)], 2: [(70, 3), (80, 3), (90, 3)], 3: [(75, 5), (85, 3), (95, 1)]}
        for week, expected in weeks.items():
            with self.subTest(week=week):
                proposal = run(wave(state(week - 1)))
                self.assertEqual(shape(proposal), [(load, reps, False, None) for load, reps in expected[:2]]
                                 + [(expected[2][0], expected[2][1], True, 9)])
                self.assertEqual({s.type for s in proposal.sets if s.working}, {"normal"})
                self.assertIn(f"week {week} of 3", proposal.rationale)
                self.assertEqual(proposal.target_note, f"Wave week {week} of 3")

    def test_amrap_false_prescribes_no_rep_out_set(self):
        proposal = run(wave(params={"amrap": False}))
        self.assertFalse(any(s.rep_out for s in proposal.sets))

    def test_the_first_training_max_is_ninety_percent_of_the_e1rm_or_the_params(self):
        fresh = scheme("wave_531").module.STATE["initial"]
        self.assertEqual(run(wave(fresh, e1rm=120)).state["training_max"], 108)
        self.assertEqual(run(wave(fresh, params={"training_max": 90}, e1rm=120)).state["training_max"], 90)

    def test_history_before_the_training_max_starts_is_marked_judged(self):
        old = trained(date(2026, 10, 5), 1)
        proposal = run(wave(scheme("wave_531").module.STATE["initial"], exposures=(old,),
                            params={"training_max": 100}))
        self.assertEqual(proposal.state, state(0, 100, {"date": "2026-10-05", "workout_id": "w-2026-10-05"}))

    def test_with_no_training_max_and_no_e1rm_the_line_holds(self):
        fresh = scheme("wave_531").module.STATE["initial"]
        proposal = run(wave(fresh))
        self.assertEqual(proposal.state, fresh)
        self.assertEqual({s.load for s in proposal.sets if s.working}, {100})
        self.assertIn("no training max", proposal.rationale)


class TrainedWorkTest(unittest.TestCase):
    def test_runs_with_no_logged_work_repeat_week_one_and_keep_the_training_max(self):
        current = state()
        for _ in range(4):
            proposal = run(wave(current))
            current = proposal.state
            self.assertEqual(shape(proposal)[0][:2], (65, 5))
        self.assertEqual(current, state())

    def test_a_completed_week_moves_the_wave_on_once(self):
        week_one = trained(date(2026, 10, 5), 1)
        proposal = run(wave(exposures=(week_one,)))
        self.assertEqual(shape(proposal)[0][:2], (70, 3))
        self.assertIn("week 1 was completed on 2026-10-05", proposal.rationale)
        again = run(wave(proposal.state, exposures=(week_one,)))
        self.assertEqual(again.state, proposal.state)
        self.assertIn("week 2 again", again.rationale)

    def test_a_second_session_of_the_same_week_does_not_earn_the_next(self):
        first = trained(date(2026, 10, 5), 1)
        repeat = trained(date(2026, 10, 8), 1)
        proposal = run(wave(exposures=(first, repeat)))
        self.assertEqual(proposal.state["completed_weeks"], 1)
        self.assertEqual(proposal.state["through"], {"date": "2026-10-08", "workout_id": "w-2026-10-08"})

    def test_unrelated_or_unknown_prescriptions_earn_nothing(self):
        unknown = replace(trained(date(2026, 10, 5), 1), prescribed=())
        other = replace(trained(date(2026, 10, 6), 1), prescribed=base.with_load(wave_sets(1), 100))
        lighter = trained(date(2026, 10, 7), 1, training_max=90)
        for exposure in (unknown, other, lighter):
            with self.subTest(exposure=exposure.date):
                proposal = run(wave(exposures=(exposure,)))
                self.assertEqual(proposal.state["completed_weeks"], 0)
                self.assertIn("week 1 again", proposal.rationale)

    def test_a_deload_or_return_week_session_earns_nothing(self):
        for fields in ({"week_kind": "deload"}, {"decayed": True}):
            with self.subTest(fields=fields):
                proposal = run(wave(exposures=(trained(date(2026, 10, 5), 1, **fields),)))
                self.assertEqual(proposal.state["completed_weeks"], 0)
                self.assertEqual(proposal.state["training_max"], 100)

    def test_a_rep_out_set_short_of_its_reps_repeats_the_week_for_review(self):
        short = trained(date(2026, 10, 5), 1, reps=[5, 5, 4])
        proposal = run(wave(exposures=(short,)))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertEqual(flag_codes(proposal), ["wave_review"])
        self.assertIn("wave set 3 (5+) logged 4 reps", proposal.flags[0]["message"])
        self.assertIn("training max holds for review", proposal.rationale)

    def test_a_rep_out_set_past_its_cap_repeats_the_week_for_review(self):
        hard = trained(date(2026, 10, 5), 1, rpes=[None, None, 10])
        proposal = run(wave(exposures=(hard,)))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertIn("logged RPE 10, past its cap of 9", proposal.flags[0]["message"])

    def test_missing_wave_sets_repeat_the_week_as_incomplete(self):
        partial = trained(date(2026, 10, 5), 1, logged_sets=2)
        proposal = run(wave(exposures=(partial,)))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertEqual(flag_codes(proposal), ["incomplete_exposure"])

    def test_a_short_set_among_missing_ones_holds_for_review(self):
        partial = trained(date(2026, 10, 5), 1, reps=[5, 3, 5], logged_sets=2)
        proposal = run(wave(exposures=(partial,)))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertEqual(flag_codes(proposal), ["wave_review"])
        message = proposal.flags[0]["message"]
        self.assertIn("wave set 2 (5) logged 3 reps", message)
        self.assertIn("2 of its 3 wave sets logged", message)

    def test_a_lighter_logged_load_repeats_the_week_for_review(self):
        lighter = trained(date(2026, 10, 19), 3, training_max=100, loads=[75, 85, 85])
        proposal = run(wave(state(2), exposures=(lighter,)))
        self.assertEqual((proposal.state["completed_weeks"], proposal.state["training_max"]), (2, 100))
        self.assertEqual(flag_codes(proposal), ["wave_review"])
        self.assertIn("wave set 3 (1+) logged at 85, under its prescribed 95", proposal.flags[0]["message"])
        self.assertIn("training max holds for review", proposal.rationale)

    def test_a_wave_logged_far_lighter_throughout_never_moves_or_raises(self):
        logs = tuple(trained(date(2026, 10, 5 + 7 * (week - 1)), week, loads=[40, 40, 40]) for week in (1, 2, 3))
        proposal = run(wave(exposures=logs))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertEqual(proposal.state["training_max"], 100)
        self.assertEqual(set(flag_codes(proposal)), {"wave_review"})

    def test_a_heavier_unknown_or_within_tolerance_load_still_completes_the_week(self):
        for loads in ([70, 80, 90], [None, None, None], [62.5, 72.5, 82.5]):
            with self.subTest(loads=loads):
                proposal = run(wave(exposures=(trained(date(2026, 10, 5), 1, loads=loads),)))
                self.assertEqual(proposal.state["completed_weeks"], 1)
                self.assertEqual(flag_codes(proposal), [])

    def test_completing_the_wave_at_its_reps_and_caps_raises_the_increment_once(self):
        logs = (trained(date(2026, 10, 5), 1), trained(date(2026, 10, 12), 2), trained(date(2026, 10, 19), 3))
        proposal = run(wave(exposures=logs))
        self.assertEqual(proposal.state["completed_weeks"], 0)
        self.assertEqual(proposal.state["training_max"], 105)
        self.assertEqual(shape(proposal)[0][:2], (68.25, 5))
        self.assertIn("lower-body increment of 5", proposal.rationale)
        again = run(wave(proposal.state, exposures=logs))
        self.assertEqual(again.state["training_max"], 105)

    def test_the_increment_follows_the_region_and_unit(self):
        bench = replace(SQUAT, id="bb_bench_press", pattern="horizontal_push")
        for exercise, params, unit, raised in ((SQUAT, None, "kg", 105), (bench, None, "kg", 102.5),
                                               (SQUAT, None, "lb", 110), (bench, None, "lb", 105),
                                               (SQUAT, {"increment_lower": 7.5}, "kg", 107.5)):
            with self.subTest(exercise=exercise.id, params=params, unit=unit):
                logs = tuple(replace(trained(date(2026, 10, 5 + 7 * (week - 1)), week), exercise_id=exercise.id)
                             for week in (1, 2, 3))
                ctx = replace(wave(state(), exposures=logs, params=params, exercise=exercise), unit=unit)
                self.assertEqual(run(ctx).state["training_max"], raised)

    def test_a_failed_week_never_raises_the_training_max(self):
        logs = (trained(date(2026, 10, 5), 1), trained(date(2026, 10, 12), 2),
                trained(date(2026, 10, 19), 3, reps=[5, 3, 0]))
        proposal = run(wave(exposures=logs))
        self.assertEqual((proposal.state["completed_weeks"], proposal.state["training_max"]), (2, 100))
        self.assertEqual(flag_codes(proposal), ["wave_review"])


class BackOffTest(unittest.TestCase):
    def test_a_back_off_group_with_an_rpe_is_loaded_from_the_e1rm_at_its_reps_and_rpe(self):
        """5 at RPE 7 is 8 reps to failure: 121.88 / (1 + 8/30) = 96.2, floored to the 2.5 increment."""
        warm_up = {"count": 1, "type": "warmup", "reps": 5}
        proposal = run(wave(sets=(warm_up, WAVE_GROUP, BACK_OFFS), e1rm=121.88))
        self.assertEqual(proposal.sets[0].type, "warmup")
        self.assertEqual(shape(proposal), [(65, 5, False, None), (75, 5, False, None), (85, 5, True, 9)]
                         + [(95, 5, False, 7)] * 3)
        self.assertIn("3 back-off sets loaded from the e1RM of 121.88 at their reps and RPE", proposal.rationale)
        self.assertAlmostEqual(stats.implied_rpe(121.88, 95, 5), 7, delta=1)

    def test_back_offs_without_an_rpe_or_an_e1rm_take_the_first_wave_set_s_load(self):
        cases = (((WAVE_GROUP, BACK_OFFS), None, 7), ((WAVE_GROUP, dict(BACK_OFFS, rpe=None)), 121.88, None))
        for sets, e1rm, rpe in cases:
            with self.subTest(e1rm=e1rm, rpe=rpe):
                proposal = run(wave(sets=sets, e1rm=e1rm))
                self.assertEqual(shape(proposal)[WAVE_SETS:], [(65, 5, False, rpe)] * 3)
                self.assertIn("3 back-off sets at the first wave set's load", proposal.rationale)

    def test_a_wave_group_that_is_not_three_sets_is_refused(self):
        module = scheme("wave_531").module
        self.assertEqual(module.problems({}, [WAVE_GROUP, BACK_OFFS]), [])
        found = module.problems({}, [{"count": 1, "type": "warmup", "reps": 5}, dict(WAVE_GROUP, count=4)])
        self.assertEqual([path for path, _ in found], ["$.sets[1].count"])
        self.assertEqual([path for path, _ in module.problems({}, [{"count": 2, "type": "warmup", "reps": 5}])],
                         ["$.sets"])


class DeloadAndReturnTest(unittest.TestCase):
    def test_the_deload_is_40_50_60_with_no_rep_out_set_and_no_advance(self):
        ctx = wave(state(2), exposures=(trained(date(2026, 10, 5), 3),), sets=(WAVE_GROUP, BACK_OFFS))
        proposal = run(ctx)
        deloaded = scheme("wave_531").module.deload(ctx, proposal)
        self.assertEqual(shape(deloaded), [(40, 5, False, None), (50, 5, False, None), (60, 5, False, None)]
                         + [(40, 5, False, None)] * 3)
        self.assertEqual(deloaded.state, ctx.state)
        self.assertIn("40/50/60 % of the training max of 100", deloaded.rationale)
        self.assertIn("training max raised to 105", deloaded.rationale)
        self.assertNotIn("same week", deloaded.rationale)
        self.assertTrue(deloaded.load_cut)

    def test_a_return_week_lowers_only_the_temporary_prescription(self):
        source = trained(date(2026, 9, 14), 1)
        ctx = wave(state(0, 100, {"date": "2026-09-14", "workout_id": "w-2026-09-14"}), exposures=(source,),
                   days_off=28)
        proposal = run(ctx)
        decayed = scheme("wave_531").module.decay(ctx, proposal, 28)
        self.assertEqual(shape(decayed), [(58.5, 5, False, None), (67.5, 5, False, None)])
        self.assertEqual(decayed.state, proposal.state)
        self.assertEqual(decayed.state["training_max"], 100)
        self.assertIn("no + set", decayed.target_note)
        self.assertTrue(decayed.load_cut)
        self.assertIn("week 1 of 3 at 65/75/85 % of the training max of 100", decayed.rationale)
        self.assertIn("taken as a return week at 90 % of the training max of 100 with no + set, and the next "
                      "ordinary week resumes the training max of 100", decayed.rationale)

        logged = trained(date(2026, 10, 12), 1, training_max=90, decayed=True)
        after = run(wave(decayed.state, exposures=(source, logged)))
        self.assertEqual(shape(after), [(65, 5, False, None), (75, 5, False, None), (85, 5, True, 9)])
        self.assertEqual(after.state["training_max"], 100)
        self.assertIn("week 1 again after the return week on 2026-10-12", after.rationale)

    def test_a_return_week_cuts_back_offs_loaded_from_the_e1rm_by_the_band(self):
        """22-42 days off: 90 % of the e1RM-loaded 96.2 is 86.6, floored to 85, under the 95 × 0.9 ceiling."""
        logged = tuple(base.LoggedSet(index=i, type="normal", reps=5, rpe=None, load=load)
                       for i, load in enumerate((65, 75, 85, 95, 95, 95)))
        source = base.Exposure(date=date(2026, 9, 14), workout_id="w", session_id="session-a",
                               exercise_id=SQUAT.id, load_mode="total", sets=logged)
        ctx = wave(state(0, 100, None), exposures=(source,), days_off=28, sets=(WAVE_GROUP, BACK_OFFS), e1rm=121.88)
        decayed = scheme("wave_531").module.decay(ctx, run(ctx), 28)
        self.assertEqual(shape(decayed), [(58.5, 5, False, None), (67.5, 5, False, None), (76.5, 5, False, None)]
                         + [(85, 5, False, 7)] * 2)

    def test_a_return_week_of_a_kept_override_takes_the_standard_return_band(self):
        ctx = wave(state(0, 100, None), exposures=(trained(date(2026, 9, 14), 1),), days_off=28)
        kept = base.Proposal(sets=(base.SetSpec(reps=5, load=60),) * 3, rationale="kept", derived_from=None, state={})
        decayed = scheme("wave_531").module.decay(ctx, kept, 28)
        self.assertEqual(shape(decayed), [(54, 5, False, None)] * 2)

    def test_a_retest_band_caps_rpe_and_the_derived_from_load(self):
        source = base.Exposure(date=date(2026, 8, 1), workout_id="w", session_id="session-a", exercise_id=SQUAT.id,
                               load_mode="total", sets=(base.LoggedSet(0, "normal", 5, None, 60),) * 2)
        ctx = wave(state(1, 100, None), exposures=(source,), days_off=60)
        decayed = scheme("wave_531").module.decay(ctx, run(ctx), 60)
        self.assertEqual(decayed.state["training_max"], 100)
        self.assertEqual([(s.load, s.rpe, s.rep_out) for s in decayed.sets if s.working], [(51, 7, False)])

    def test_programs_only_lines_with_an_e1rm_and_cites_the_wave_numbers(self):
        module = scheme("wave_531").module
        self.assertEqual(module.LOAD_MODES, base.E1RM_MODES)
        self.assertIn("rn:progression-training-age.9", module.CITES)


class RepOutSetTest(unittest.TestCase):
    def test_a_plus_set_parses_as_a_rep_out_set_capped_at_rpe_9(self):
        [set_] = propose.parse_sets("1x5+@145")
        self.assertEqual((set_.type, set_.reps, set_.load, set_.rpe, set_.rep_out), ("normal", 5, 145, 9, True))
        self.assertEqual(base.SetSpec.from_dict(set_.to_dict()), set_)
        [lower] = propose.parse_sets("1x5+ @145 rpe8")
        self.assertEqual((lower.rpe, lower.rep_out), (8, True))
        plain = propose.parse_sets("3x5@100")[0]
        self.assertNotIn("rep_out", plain.to_dict())

    def test_a_plus_on_a_range_or_a_timed_set_is_refused(self):
        for spec in ("3x8-10+@25", "2x35+s"):
            with self.subTest(spec=spec), self.assertRaises(UsageError):
                propose.parse_sets(spec)

    def test_rep_out_and_failure_sets_render_apart(self):
        load = units.make_load(85, "total", "kg")
        line = {"load_mode": "total", "exercise_id": "bb_back_squat", "rest_seconds": 180, "sets": [
            {"type": "normal", "reps": 5, "rpe": 9, "rep_out": True, "load": load},
            {"type": "failure", "reps": 8, "rpe": None, "load": load}]}
        self.assertEqual(render.target_line(line), "Target: 1×5+ @ 85 kg (stop at RPE 9) + 1×8 @ 85 kg")
        rows = render._exercise_rows(line)
        self.assertIn("| 1×5+ | 85 | stop at 9 |", rows[0])
        self.assertIn("1×8 to failure", rows[1])
        self.assertEqual(propose.sets_text(tuple(base.SetSpec.from_dict(s, load=85) for s in line["sets"]), "total",
                                           "kg"), "1×5+ @ 85 stop at RPE 9, 1×8 @ 85")

    def test_an_overlay_rep_out_set_needs_fixed_reps_on_a_normal_set(self):
        for set_ in ({"type": "normal", "rep_range": {"start": 5, "end": 8}, "rep_out": True},
                     {"type": "failure", "reps": 5, "rep_out": True}):
            with self.subTest(set_=set_):
                errors = overlay._set_errors(set_, "$.s", "total", True)
                self.assertIn("$.s.rep_out", [e.path for e in errors])
        self.assertEqual(overlay._set_errors({"type": "normal", "reps": 5, "rep_out": True}, "$.s", "total", True),
                         [])

    def test_a_standard_deload_drops_the_rep_out(self):
        proposal = run(wave())
        deloaded = base.standard_deload(proposal, **base.STANDARD_DELOAD)
        self.assertFalse(any(s.rep_out for s in deloaded.sets))


class MigrationTest(unittest.TestCase):
    def step(self, name):
        return importlib.import_module(f"coach.migrations.{name}")

    def test_state_keeps_the_training_max_and_rejudges_the_last_approved_week(self):
        step = self.step("state.0005_wave_evidence")
        old = {"wave_week": 2, "training_max": 170, "proposed_for": "2026-10-15", "proposed_on": "2026-10-11"}
        doc = {"schema_version": 5, "scheme_state": {
            SLOT: {"scheme": "wave_531", "data": dict(old), "pending": {"overlay_id": "x", "data": dict(old)}},
            "session-a/db_bench_press": {"scheme": "linear", "data": {"misses": 0, "through": None},
                                         "pending": None}}}
        before = copy.deepcopy(doc)
        after = step.migrate(doc)
        expected = {"completed_weeks": 1, "training_max": 170, "through": {"date": "2026-10-11", "workout_id": None}}
        self.assertEqual(after["scheme_state"][SLOT]["data"], expected)
        self.assertEqual(after["scheme_state"][SLOT]["pending"]["data"], expected)
        self.assertEqual(after["scheme_state"]["session-a/db_bench_press"]["data"], {"misses": 0, "through": None})
        self.assertFalse(plugins.state_errors(scheme("wave_531"), expected))
        self.assertIn("2026-10-11", step.notes(before, after)[0])

    def test_state_notes_name_the_pending_week_the_approval_will_settle(self):
        step = self.step("state.0005_wave_evidence")
        stored = {"wave_week": 3, "training_max": 80, "proposed_for": "2026-10-01", "proposed_on": "2026-09-27"}
        pending = {"wave_week": 1, "training_max": 82.5, "proposed_for": "2026-10-08", "proposed_on": "2026-10-04"}
        doc = {"schema_version": 5, "scheme_state": {
            SLOT: {"scheme": "wave_531", "data": stored, "pending": {"overlay_id": "2026-10-05-weekly",
                                                                     "data": pending}}}}
        before = copy.deepcopy(doc)
        notes = step.notes(before, step.migrate(doc))
        self.assertEqual(len(notes), 1)
        self.assertIn("pending wave week 1 (overlay 2026-10-05-weekly)", notes[0])
        self.assertIn("after 2026-10-04", notes[0])
        self.assertNotIn("week 3", notes[0])

    def test_overlay_turns_an_unoverridden_wave_failure_set_into_a_rep_out_set(self):
        step = self.step("overlay.0004_rep_out_sets")
        line = {"provenance": {"scheme": "wave_531"}, "override": None,
                "sets": [{"type": "normal", "reps": 5}, {"type": "failure", "reps": 5}]}
        other = {"provenance": {"scheme": "linear"}, "override": None, "sets": [{"type": "failure", "reps": 8}]}
        overridden = dict(copy.deepcopy(line), override={"reason": "x", "proposed_sets": []})
        doc = {"id": "2026-10-12-weekly", "approval": None, "sessions": [{"exercises": [line, other, overridden]}]}
        after = step.migrate(copy.deepcopy(doc))
        wave_line, linear_line, overridden = after["sessions"][0]["exercises"]
        self.assertEqual(wave_line["sets"][1], {"type": "normal", "reps": 5, "rep_out": True,
                                                "rpe": base.REP_OUT_RPE_CAP})
        self.assertEqual(linear_line["sets"][0]["type"], "failure")
        self.assertEqual(overridden["sets"][1]["type"], "failure")
        self.assertIn("stop at RPE 9", step.notes(doc, after)[0])

    def test_overlay_keeps_a_wave_failure_set_s_own_rpe(self):
        step = self.step("overlay.0004_rep_out_sets")
        line = {"provenance": {"scheme": "wave_531"}, "override": None,
                "sets": [{"type": "failure", "reps": 1, "rpe": 8}]}
        doc = {"id": "2026-10-12-weekly", "approval": None, "sessions": [{"exercises": [line]}]}
        after = step.migrate(copy.deepcopy(doc))
        self.assertEqual(after["sessions"][0]["exercises"][0]["sets"][0]["rpe"], 8)


def squat(doc):
    return find_line(doc, "bb_back_squat", "session-a")


class WavePipelineCase(ProposeCase):
    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "wave_531", {"training_max": 100})
        self.serial = 50

    def state(self):
        return read_json(self.root / "data" / "state.json")["scheme_state"].get(SLOT)

    def approve(self, week, now):
        data = self.propose(week=week, env={"COACH_NOW": now})
        self.coach("propose", "finalize", "--proposal", data["id"], env={"COACH_NOW": now})
        self.coach("overlay", "approve", data["id"], env={"COACH_NOW": now})
        return data

    def log_squat(self, day, overlay_id, sets):
        """A session-a workout on `day` against `overlay_id`, holding only the squat's (load, reps, rpe) sets."""
        self.serial += 1
        workout_id = f"10000000-0000-4000-8000-0000000000{self.serial}"

        def edit(doc):
            source = next(w for w in doc["workouts"] if w.get("session_id") == "session-a")
            logged = copy.deepcopy(source)
            logged.update(workout_id=workout_id, date=day, routine_id=R_A, session_id="session-a",
                          overlay_id=overlay_id, start_time=f"{day}T18:00:00Z", end_time=f"{day}T19:00:00Z",
                          exercises=[e for e in logged["exercises"] if e["exercise_id"] == "bb_back_squat"])
            exercise = logged["exercises"][0]
            template = next(s for s in exercise["sets"] if s["type"] == "normal")
            exercise["sets"] = [dict(template, index=i, type="normal", reps=reps, rpe=rpe, weight_kg=float(load),
                                     load=units.make_load(load, "total", "kg"))
                                for i, (load, reps, rpe) in enumerate(sets)]
            doc["workouts"].append(logged)
        month = day[:7]
        self.edit_json(f"data/history/{month}.json", edit)


class WavePipelineTest(WavePipelineCase):
    def test_the_rep_out_cap_is_a_stop_not_an_rpe_target(self):
        """At a training max of 100 the + set is 85 × 5, far below RPE 9 at the squat's e1RM of 121.88."""
        doc = self.propose("--dry-run")["overlay"]
        last = squat(doc)["sets"][-1]
        self.assertEqual((coaching(last["load"]), last["reps"], last.get("rep_out"), last["rpe"]), (85, 5, True, 9))
        self.assertNotIn("rpe_infeasible", codes(doc, "bb_back_squat"))

    def test_four_approved_weeks_with_no_logs_repeat_week_one_and_keep_the_training_max(self):
        """Weeks without training also bring a return band, which lowers only that week's loads."""
        for week, now in (("2026-W42", "2026-10-11T18:00:00Z"), ("2026-W43", "2026-10-18T18:00:00Z"),
                          ("2026-W44", "2026-10-25T18:00:00Z"), ("2026-W45", "2026-11-01T18:00:00Z")):
            with self.subTest(week=week):
                line = squat(self.approve(week, now)["overlay"])
                self.assertIn("week 1 of 3 at 65/75/85 % of the training max of 100", line["provenance"]["rationale"])
                self.assertEqual([s["reps"] for s in working(line)][:2], [5, 5])
                self.assertEqual(self.state()["pending"]["data"]["training_max"], 100)
        data = self.propose("--dry-run", week="2026-W46", env={"COACH_NOW": "2026-11-08T18:00:00Z"})
        self.assertIn("week 1 of 3", squat(data["overlay"])["provenance"]["rationale"])
        stored = self.state()["pending"]["data"]
        self.assertEqual((stored["completed_weeks"], stored["training_max"]), (0, 100))

    def test_a_trained_wave_moves_on_weekly_and_raises_the_training_max_once(self):
        first = self.approve("2026-W42", "2026-10-11T18:00:00Z")
        line = squat(first["overlay"])
        self.assertEqual([(s["type"], s.get("rep_out", False), s["rpe"]) for s in working(line)],
                         [("normal", False, None)] * 2 + [("normal", True, 9)])
        self.log_squat("2026-10-12", first["id"], [(65, 5, None), (75, 5, None), (85, 8, 8.5)])
        second = self.approve("2026-W43", "2026-10-18T18:00:00Z")
        self.assertEqual([coaching(s["load"]) for s in working(squat(second["overlay"]))], [70, 80, 90])
        self.log_squat("2026-10-19", second["id"], [(70, 3, None), (80, 3, None), (90, 5, 9)])
        third = self.approve("2026-W44", "2026-10-25T18:00:00Z")
        self.assertEqual([(coaching(s["load"]), s["reps"]) for s in working(squat(third["overlay"]))],
                         [(75, 5), (85, 3), (95, 1)])
        self.log_squat("2026-10-26", third["id"], [(75, 5, None), (85, 3, None), (95, 4, 9)])
        fourth = self.approve("2026-W45", "2026-11-01T18:00:00Z")
        self.assertEqual([coaching(s["load"]) for s in working(squat(fourth["overlay"]))], [67.5, 77.5, 87.5])
        again = self.propose("--dry-run", week="2026-W45", env={"COACH_NOW": "2026-11-01T19:00:00Z"})
        self.assertEqual([coaching(s["load"]) for s in working(squat(again["overlay"]))], [67.5, 77.5, 87.5])
        self.assertEqual(self.state()["pending"]["data"]["training_max"], 105)

    def test_a_short_rep_out_set_repeats_the_week_with_wave_review(self):
        first = self.approve("2026-W42", "2026-10-11T18:00:00Z")
        self.log_squat("2026-10-12", first["id"], [(65, 5, None), (75, 5, None), (85, 3, 10)])
        data = self.propose("--dry-run", week="2026-W43", env={"COACH_NOW": "2026-10-18T18:00:00Z"})
        self.assertEqual([coaching(s["load"]) for s in working(squat(data["overlay"]))], [65, 75, 85])
        self.assertIn("wave_review", codes(data["overlay"], "bb_back_squat"))

    def test_the_rationale_names_the_rep_out_set_and_its_cap(self):
        rationale = squat(self.propose("--dry-run")["overlay"])["provenance"]["rationale"]
        self.assertIn("the 5+ set takes as many reps as the athlete can before RPE 9 (a coaching heuristic)",
                      rationale)

    def test_a_light_week_that_drops_the_rep_out_set_stops_promising_it(self):
        line = squat(self.propose("--kind", "deload", "--transform", "light")["overlay"])
        self.assertEqual(len(working(line)), 2)
        self.assertFalse(any(s.get("rep_out") for s in line["sets"]))
        rationale = line["provenance"]["rationale"]
        self.assertNotIn("as many reps", rationale)
        self.assertIn("no + set this week", rationale)

    def test_a_light_week_that_keeps_the_rep_out_set_names_its_lower_cap(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            sets=[WAVE_GROUP, BACK_OFFS]))
        line = squat(self.propose("--kind", "deload", "--transform", "light")["overlay"])
        self.assertEqual([(s.get("rep_out", False), s["rpe"]) for s in working(line)],
                         [(False, 8), (False, 8), (True, 8), (False, 7)])
        rationale = line["provenance"]["rationale"]
        self.assertIn("the 5+ set takes as many reps as the athlete can before RPE 8", rationale)
        self.assertNotIn("RPE 9", rationale)

    def test_a_scheme_deload_names_its_percentages_and_moves_nothing_on(self):
        self.edit_program(lambda doc: doc["blocks"].update(deload_rule={"name": "scheme", "params": {}}))
        data = self.propose("--kind", "deload")
        line = squat(data["overlay"])
        self.assertEqual([coaching(s["load"]) for s in working(line)], [40, 50, 60])
        self.assertFalse(any(s.get("rep_out") for s in line["sets"]))
        rationale = line["provenance"]["rationale"]
        self.assertIn("40/50/60 % of the training max of 100", rationale)
        self.assertNotIn("again", rationale)
        meta = read_json(self.root / ".coach" / "proposals" / f"{data['id']}.meta.json")
        self.assertEqual(meta["scheme_state"], {})

    def test_programmed_back_offs_reach_the_overlay_at_a_load_their_rpe_can_reach(self):
        """At the squat's e1RM of 121.88, with the program's training max of 100 or the default 90 % of the e1RM."""
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            sets=[WAVE_GROUP, BACK_OFFS]))
        for params in ({"training_max": 100}, {}):
            with self.subTest(params=params):
                self.set_scheme("session-a", "bb_back_squat", "wave_531", params)
                doc = self.propose("--dry-run")["overlay"]
                line = squat(doc)
                self.assertEqual([(coaching(s["load"]), s["reps"], s["rpe"]) for s in working(line)][WAVE_SETS:],
                                 [(95, 5, 7)] * 3)
                self.assertNotIn("rpe_infeasible", codes(doc, "bb_back_squat"))

    def test_program_validate_refuses_a_wave_group_that_would_lose_sets(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            sets=[dict(WAVE_GROUP, count=5)]))
        envelope = self.coach("program", "validate", expect=1)
        paths = [d["path"] for d in envelope["error"]["details"]]
        self.assertIn("$.sessions[0].exercises[0].sets[0].count", paths)


class WaveOverrideTest(WavePipelineCase):
    def override(self, spec, reason="synthetic override"):
        return self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                          "bb_back_squat", "--sets", spec, "--reason", reason)["data"]

    def test_appended_back_offs_keep_the_rep_out_set_and_its_cap(self):
        self.propose()
        self.override("1x5@65, 1x5@75, 1x5+@85, 3x5@65 rpe7")
        draft = read_json(self.draft_path())
        line = squat(draft)
        self.assertEqual([(s["reps"], s.get("rep_out", False), s["rpe"]) for s in working(line)],
                         [(5, False, None), (5, False, None), (5, True, 9)] + [(5, False, 7)] * 3)
        self.assertNotIn("last set", line["target_note"])
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        self.coach("overlay", "approve", FIRST_ID)
        doc = overlay.load(self.root, FIRST_ID)
        stored = squat(doc)
        self.assertEqual([s.get("rep_out", False) for s in working(stored)], [False, False, True] + [False] * 3)
        self.assertIn("1×5+ @ 85 kg (stop at RPE 9) + 3×5 @ 65 kg @ RPE 7", render.target_line(stored))
        self.coach("sheets", "render", "--overlay", FIRST_ID)
        text = (self.root / "this-week-sheets.md").read_text(encoding="utf-8")
        self.assertIn("| 1×5+ | 85 | stop at 9 |", text)
        self.assertIn(sheets.REP_OUT, text)

    def test_an_rpe_cap_constraint_lowers_the_rep_out_cap(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            constraints=[{"kind": "rpe_cap", "value": 8, "reason": "synthetic knee"}]))
        line = squat(self.propose()["overlay"])
        self.assertEqual(working(line)[-1]["rpe"], 8)
        self.assertIn("the 5+ set takes as many reps as the athlete can before RPE 8",
                      line["provenance"]["rationale"])
        self.override("1x5@65, 1x5@75, 1x5+@85")
        self.assertEqual(working(squat(read_json(self.draft_path())))[-1]["rpe"], 8)

    def test_an_ordinary_override_does_not_change_the_training_max(self):
        self.propose()
        self.override("3x5@60", reason="synthetic: lighter while the knee settles")
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        self.coach("overlay", "approve", FIRST_ID)
        self.assertEqual(self.state()["pending"]["data"]["training_max"], 100)
        line = squat(self.propose("--dry-run", week="2026-W43", env={"COACH_NOW": "2026-10-18T18:00:00Z"})["overlay"])
        self.assertIn("training max of 100", line["provenance"]["rationale"])


class TrainingMaxCommandTest(WavePipelineCase):
    def set_max(self, *extra, expect=0):
        return self.coach("state", "set-training-max", "--session", "session-a", "--exercise", "bb_back_squat",
                          "--value", "95", "--reason", "synthetic: grinding the 85 % sets", *extra, expect=expect)

    def test_the_dry_run_previews_and_writes_nothing(self):
        self.approve("2026-W42", "2026-10-11T18:00:00Z")
        before = self.snapshot()
        data = self.set_max("--dry-run")["data"]
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((data["from"], data["to"], data["written"]), (100, 95, False))

    def test_a_pending_state_still_waiting_for_approval_takes_the_change(self):
        self.propose()
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        data = self.set_max()["data"]
        self.assertEqual(self.state()["pending"]["data"]["training_max"], 95)
        self.assertEqual(data["pending_overlay"], FIRST_ID)
        self.assertIn(f"propose that week again before approving {FIRST_ID}", data["note"])
        self.coach("overlay", "approve", FIRST_ID)
        line = squat(self.propose("--dry-run", week="2026-W43", env={"COACH_NOW": "2026-10-18T18:00:00Z"})["overlay"])
        self.assertIn("training max of 95", line["provenance"]["rationale"])

    def test_the_change_is_stored_recorded_and_proposed(self):
        self.approve("2026-W42", "2026-10-11T18:00:00Z")
        data = self.set_max()["data"]
        stored = self.state()
        self.assertEqual(stored["data"]["training_max"], 95)
        self.assertIsNone(stored["pending"])
        self.assertEqual((data["pending_overlay"], data["note"]), (None, None))
        decision = data["decision"]
        self.assertEqual((decision["kind"], decision["details"], decision["scope"]),
                         ("training_max", {"scheme": "wave_531", "from": 100, "to": 95},
                          {"session_id": "session-a", "exercise_id": "bb_back_squat"}))
        line = squat(self.propose("--dry-run", week="2026-W43", env={"COACH_NOW": "2026-10-18T18:00:00Z"})["overlay"])
        self.assertIn("training max of 95", line["provenance"]["rationale"])

    def test_a_slot_without_a_training_max_is_refused(self):
        self.set_scheme("session-a", "bb_back_squat", "linear")
        envelope = self.set_max(expect=1)
        self.assertIn("keeps no training max", envelope["error"]["message"])


class WaveReturnWeekTest(LayoffCase):
    def test_the_return_week_keeps_the_stored_training_max(self):
        self.set_scheme("session-a", "bb_back_squat", "wave_531")
        best = max(p["e1rm"] for p in stats.e1rm_series(self.root)["series"]["bb_back_squat"])
        data = self.propose()
        line = find_line(data["overlay"], "bb_back_squat")
        self.assertEqual(line["provenance"]["decay"]["band"], "22-42")
        self.assertEqual(len(working(line)), 2)
        self.assertFalse(any(s.get("rep_out") for s in line["sets"]))
        rationale = line["provenance"]["rationale"]
        self.assertIn("taken as a return week at 90 % of the training max", rationale)
        self.assertIn("with no + set", rationale)
        self.assertNotIn("as many reps", rationale)
        meta = read_json(self.root / ".coach" / "proposals" / f"{data['id']}.meta.json")
        stored = meta["scheme_state"][SLOT]["data"]
        self.assertAlmostEqual(stored["training_max"], best * 0.9, delta=0.02)
        self.assertLess(max(coaching(s["load"]) for s in working(line)), stored["training_max"] * 0.75)
        checked = self.coach("prescription", "check", "--file", str(self.draft_path(data["id"])))["data"]
        self.assertEqual(checked["summary"]["block"], 0, checked["flags"])


if __name__ == "__main__":
    unittest.main()
