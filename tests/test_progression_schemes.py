"""The rpe_anchored, wave_531, assistance_ladder and maintenance progression schemes (contract C23)."""

import unittest
from dataclasses import replace
from datetime import date, timedelta

from coach import plugins, stats, units
from coach.plugins import base
from tests.support import VALID, run_cli
from tests.support.history import read_json
from tests.test_propose import FIRST_ID, LayoffCase, ProposeCase, codes, coaching, find_line, working

SESSION_DATE = date(2026, 10, 12)
SQUAT = base.ExerciseInfo(id="bb_back_squat", name="Back squat", pattern="squat", muscles={}, equipment="barbell",
                          load_mode="total", increment=2.5, is_compound=True)
PULL_UP = base.ExerciseInfo(id="pull_up", name="Pull-up", pattern="vertical_pull", muscles={}, equipment="bodyweight",
                            load_mode="assisted", increment=5, is_compound=True, load_direction=-1)
THREE_FIVES = ({"count": 3, "type": "normal", "reps": 5, "rpe": 7},)


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


class RpeAnchoredTest(unittest.TestCase):
    PARAMS = {"top_reps": 3, "top_rpe": 8, "backoff_sets": 3}

    def test_top_set_from_the_e1rm_inverse_then_back_offs_at_ninety_percent(self):
        proposal = run(context("rpe_anchored", self.PARAMS, e1rm=121.88))
        top, *backoffs = [s for s in proposal.sets if s.working]
        self.assertEqual((top.load, top.reps, top.rpe), (102.5, 3, 8))
        self.assertEqual([(s.load, s.reps) for s in backoffs], [(92.25, 3)] * 3)
        self.assertTrue(proposal.round_down)

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
        self.assertEqual([(s.load, s.reps, s.rpe) for s in backoffs], [(88, 4, None)] * 4)

    def test_with_no_e1rm_the_top_set_holds(self):
        proposal = run(context("rpe_anchored", self.PARAMS))
        self.assertEqual(proposal.sets[0].load, 100)
        self.assertIn("no e1RM", proposal.rationale)

    def test_programs_only_lines_with_an_e1rm(self):
        self.assertEqual(scheme("rpe_anchored").module.LOAD_MODES, base.E1RM_MODES)


class AssistanceLadderTest(unittest.TestCase):
    PARAMS = {"rungs": [{"name": "heavy band", "load": 40}, {"name": "medium band", "load": 30},
                        {"name": "light band", "load": 20}], "reps": 8, "sets": 3, "rpe": 8}
    SETS = ({"count": 3, "type": "normal", "reps": 8, "rpe": 8},)

    def ladder(self, state, exposures=(), days_off=0):
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

    def test_bodyweight_variations_carry_no_added_load(self):
        params = {"rungs": [{"name": "incline push-up"}, {"name": "push-up"}]}
        push_up = replace(SQUAT, id="push_up", load_mode="bodyweight", load_direction=1)
        proposal = run(context("assistance_ladder", params, exercise=push_up,
                               sets=({"count": 3, "type": "normal", "reps": 12, "rpe": 8},), start_load=0))
        self.assertEqual(loads_and_reps(proposal), [(0, 12)] * 3)
        self.assertIn("incline push-up", proposal.target_note)


class Wave531Test(unittest.TestCase):
    def wave(self, state, params=None, e1rm=None, exercise=SQUAT, days_off=0, exposures=(), session_date=SESSION_DATE,
             unit="kg"):
        ctx = context("wave_531", params, state=state, e1rm=e1rm, exercise=exercise, days_off=days_off,
                      exposures=exposures, session_date=session_date)
        return replace(ctx, unit=unit)

    @staticmethod
    def shape(proposal):
        return [(s.load, s.reps, s.type) for s in proposal.sets if s.working]

    def test_the_three_wave_weeks(self):
        weeks = {
            1: [(65, 5, "normal"), (75, 5, "normal"), (85, 5, "failure")],
            2: [(70, 3, "normal"), (80, 3, "normal"), (90, 3, "failure")],
            3: [(75, 5, "normal"), (85, 3, "normal"), (95, 1, "failure")],
        }
        for week, expected in weeks.items():
            with self.subTest(week=week):
                state = {"wave_week": week - 1, "training_max": 100, "proposed_for": "2026-10-05"}
                proposal = run(self.wave(state))
                self.assertEqual(self.shape(proposal), expected)
                self.assertEqual(proposal.state, {"wave_week": week, "training_max": 100,
                                                  "proposed_for": "2026-10-12"})
                self.assertIn(f"week {week} of 3", proposal.rationale)

    def test_the_next_wave_raises_the_training_max_by_the_lower_or_upper_increment(self):
        done = {"wave_week": 3, "training_max": 100, "proposed_for": "2026-10-05"}
        bench = replace(SQUAT, id="bb_bench_press", pattern="horizontal_push")
        for exercise, params, unit, raised in ((SQUAT, None, "kg", 105), (bench, None, "kg", 102.5),
                                               (SQUAT, None, "lb", 110), (bench, None, "lb", 105),
                                               (SQUAT, {"increment_lower": 7.5}, "kg", 107.5)):
            with self.subTest(exercise=exercise.id, params=params, unit=unit):
                proposal = run(self.wave(done, params, exercise=exercise, unit=unit))
                self.assertEqual(proposal.state["training_max"], raised)
                self.assertEqual(proposal.state["wave_week"], 1)
                self.assertAlmostEqual(proposal.sets[0].load, raised * 0.65)

    def test_a_second_run_in_the_same_week_reproposes_that_week(self):
        state = {"wave_week": 2, "training_max": 100, "proposed_for": "2026-10-12"}
        proposal = run(self.wave(state, session_date=date(2026, 10, 15)))
        self.assertEqual(proposal.state, state)
        self.assertEqual(proposal.sets[0].load, 70)

    def test_the_first_training_max_is_ninety_percent_of_the_e1rm_or_the_params(self):
        fresh = {"wave_week": 0, "training_max": None, "proposed_for": None}
        self.assertEqual(run(self.wave(fresh, e1rm=120)).state["training_max"], 108)
        self.assertEqual(run(self.wave(fresh, {"training_max": 90}, e1rm=120)).state["training_max"], 90)

    def test_with_no_training_max_and_no_e1rm_the_line_holds(self):
        fresh = {"wave_week": 0, "training_max": None, "proposed_for": None}
        proposal = run(self.wave(fresh))
        self.assertEqual(proposal.state, fresh)
        self.assertEqual({s.load for s in proposal.sets if s.working}, {100})
        self.assertIn("no training max", proposal.rationale)

    def test_the_deload_is_40_50_60_of_the_finished_wave_s_training_max(self):
        ctx = self.wave({"wave_week": 3, "training_max": 100, "proposed_for": "2026-10-05"})
        deloaded = scheme("wave_531").module.deload(ctx, run(ctx))
        self.assertEqual(self.shape(deloaded), [(40, 5, "normal"), (50, 5, "normal"), (60, 5, "normal")])
        self.assertTrue(deloaded.round_down)

    def test_a_return_band_lowers_the_training_max(self):
        source = exposure(date(2026, 9, 14), [(65, 5, None), (75, 5, None), (85, 8, None)])
        state = {"wave_week": 1, "training_max": 100, "proposed_for": "2026-09-14"}
        ctx = self.wave(state, days_off=28, exposures=(source,))
        decayed = scheme("wave_531").module.decay(ctx, run(ctx), 28)
        self.assertEqual(decayed.state["training_max"], 90)
        self.assertEqual(self.shape(decayed), [(63, 3, "normal"), (72, 3, "normal")])
        self.assertTrue(decayed.round_down)

    def test_a_retest_band_caps_rpe_and_the_derived_from_load(self):
        source = exposure(date(2026, 8, 1), [(60, 5, None)] * 2)
        state = {"wave_week": 2, "training_max": 100, "proposed_for": "2026-08-01"}
        ctx = self.wave(state, days_off=60, exposures=(source,))
        decayed = scheme("wave_531").module.decay(ctx, run(ctx), 60)
        self.assertEqual(decayed.state["training_max"], 85)
        self.assertEqual([(s.load, s.rpe) for s in decayed.sets if s.working], [(51, 7)])

    def test_programs_only_lines_with_an_e1rm(self):
        self.assertEqual(scheme("wave_531").module.LOAD_MODES, base.E1RM_MODES)


def squat_loads(doc):
    return [(coaching(s["load"]), s["reps"], s["type"]) for s in working(find_line(doc, "bb_back_squat"))]


class Wave531ProposeTest(ProposeCase):
    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "wave_531", {"training_max": 100})

    def meta_state(self):
        meta = read_json(self.root / ".coach" / "proposals" / f"{FIRST_ID}.meta.json")
        return meta["scheme_state"]["session-a/bb_back_squat"]["data"]

    def test_week_one_at_65_75_85_on_the_barbell_s_plates(self):
        doc = self.propose()["overlay"]
        self.assertEqual(squat_loads(doc), [(65, 5, "normal"), (75, 5, "normal"), (85, 5, "failure")])
        for set_ in working(find_line(doc, "bb_back_squat")):
            self.assertIsNotNone(units.plate_breakdown(coaching(set_["load"]), 20.0, [25, 20, 15, 10, 5, 2.5, 1.25]))
        self.assertEqual(self.meta_state(), {"wave_week": 1, "training_max": 100, "proposed_for": "2026-10-12"})
        self.assertEqual([f for f in doc["flags"] if f["severity"] == "block"], [])

    def test_week_four_is_the_40_50_60_deload_then_the_next_wave_raises_the_training_max(self):
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({"session-a/bb_back_squat": {
            "scheme": "wave_531", "data": {"wave_week": 3, "training_max": 100, "proposed_for": "2026-10-05"},
            "pending": None}}))
        self.edit_program(lambda doc: doc["blocks"].update(deload_rule={"name": "scheme", "params": {}}))
        deload = self.propose("--kind", "deload", "--dry-run")["overlay"]
        self.assertEqual(squat_loads(deload), [(40, 5, "normal"), (50, 5, "normal"), (60, 5, "normal")])

        doc = self.propose()["overlay"]
        self.assertEqual(self.meta_state(), {"wave_week": 1, "training_max": 105, "proposed_for": "2026-10-12"})
        self.assertEqual(squat_loads(doc), [(67.5, 5, "normal"), (77.5, 5, "normal"), (87.5, 5, "failure")])


class Wave531LayoffTest(LayoffCase):
    def test_the_22_42_band_lowers_the_training_max_by_ten_percent_and_passes_the_check(self):
        self.set_scheme("session-a", "bb_back_squat", "wave_531")
        best = max(p["e1rm"] for p in stats.e1rm_series(self.root)["series"]["bb_back_squat"])
        data = self.propose()
        line = find_line(data["overlay"], "bb_back_squat")
        self.assertEqual(line["provenance"]["decay"]["band"], "22-42")
        meta = read_json(self.root / ".coach" / "proposals" / f"{data['id']}.meta.json")
        state = meta["scheme_state"]["session-a/bb_back_squat"]["data"]
        self.assertAlmostEqual(state["training_max"], best * 0.9 * 0.9, delta=0.02)
        self.assertEqual(len(working(line)), 2)
        checked = self.coach("prescription", "check", "--file", str(self.draft_path(data["id"])))["data"]
        self.assertEqual(checked["summary"]["block"], 0, checked["flags"])
        self.assertNotIn("stale_prescription", codes(data["overlay"], "bb_back_squat"))


class RpeAnchoredProposeTest(ProposeCase):
    def test_top_set_from_the_e1rm_rounded_down_then_back_offs_at_ninety_percent(self):
        self.set_scheme("session-a", "bb_back_squat", "rpe_anchored", {"top_reps": 3, "top_rpe": 8, "backoff_sets": 3})
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual([(coaching(s["load"]), s["reps"], s["rpe"]) for s in working(find_line(doc, "bb_back_squat"))],
                         [(102.5, 3, 8), (90, 3, None), (90, 3, None), (90, 3, None)])
        self.assertLessEqual(102.5, stats.load_for(121.88, 3, 8))
        self.assertLessEqual(90, 0.9 * 102.5)
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
