"""Double progression: the program's range and effort target, the load-step gate and its load modes (contract C23)."""

import unittest
from dataclasses import replace
from datetime import date

from coach import patterns
from coach.plugins import base
from coach.plugins.schemes import double_progression
from tests.support.history import read_json
from tests.support.skills import flat, step_text
from tests.support.templates import cache_catalogue_templates
from tests.test_progression_schemes import PULL_UP, SQUAT, context, exposure, run
from tests.test_propose import FIRST_ID, NOW, ProposeCase, find_line, working

DAY = date(2026, 10, 5)
BENCH = base.ExerciseInfo(id="bb_bench_press", name="Bench press", pattern="horizontal_push", muscles={},
                          equipment="barbell", load_mode="total", increment=2.5, is_compound=True)
CURL = base.ExerciseInfo(id="db_curl", name="Dumbbell curl", pattern="elbow_flexion", muscles={},
                         equipment="dumbbell", load_mode="per_hand_x2", increment=1, is_compound=False,
                         is_isolation=True)
CRUNCH = base.ExerciseInfo(id="cable_crunch", name="Cable crunch", pattern="core", muscles={}, equipment="cable",
                           load_mode="total", increment=2.5, is_compound=False)
PULL_APART = base.ExerciseInfo(id="band_pull_apart", name="Band pull-apart", pattern="horizontal_pull", muscles={},
                               equipment="band", load_mode="band", increment=0, is_compound=True)
RPE_CAP = {"kind": "rpe_cap", "value": 8}


def program(count, start, end, rpe=8):
    return ({"count": count, "type": "normal", "rep_range": {"start": start, "end": end}, "rpe": rpe},)


def logged(sets, exercise, slot_sets):
    """`sets` as (load, reps, rpe), prescribed as the program's working sets."""
    return replace(exposure(DAY, sets, exercise=exercise), prescribed=tuple(base.working(base.expand(slot_sets))))


def propose(exercise, slot_sets, sets, constraints=()):
    ctx = context("double_progression", exposures=(logged(sets, exercise, slot_sets),), exercise=exercise,
                  sets=slot_sets)
    return run(replace(ctx, constraints=constraints))


def line(proposal):
    return [(s.load, s.reps, s.rep_range, s.rpe) for s in proposal.sets if s.working]


def flag_codes(proposal):
    return [f["code"] for f in proposal.flags]


class RangeAndEffortTargetTest(unittest.TestCase):
    def test_over_target_effort_holds_the_load_at_the_range_and_target_rpe_and_flags_the_mismatch(self):
        slot = program(3, 8, 12)
        proposal = propose(BENCH, slot, [(80, 12, 10), (80, 11, 10), (80, 10, 10)])
        self.assertEqual(line(proposal), [(80, None, (8, 12), 8)] * 3)
        self.assertEqual(flag_codes(proposal), ["range_effort_mismatch"])
        message = proposal.flags[0]["message"]
        for words in ("RPE 10", "target RPE 8", "load"):
            self.assertIn(words, message)
        self.assertNotIn("11 reps", proposal.rationale)
        self.assertIn("8–12 reps at RPE 8", proposal.rationale)

    def test_reps_below_the_range_flag_a_load_review_without_claiming_the_range_is_reachable(self):
        slot = program(4, 12, 15)
        proposal = propose(BENCH, slot, [(60, 8, 9)] * 4)
        self.assertEqual(line(proposal), [(60, None, (12, 15), 8)] * 4)
        self.assertEqual(flag_codes(proposal), ["range_effort_mismatch"])
        message = proposal.flags[0]["message"]
        self.assertIn("8, 8, 8, 8 reps", message)
        self.assertIn("below the program's 12–15", message)
        self.assertIn("does not make it reachable", message)
        self.assertNotIn("9 reps", proposal.rationale)

    def test_far_under_target_work_names_both_the_load_and_the_rep_range_options(self):
        proposal = propose(BENCH, program(3, 8, 12), [(100, 5, 9), (100, 4, 9.5), (100, 4, 10)])
        message = proposal.flags[0]["message"]
        self.assertIn("a lighter load", message)
        self.assertIn("a different rep range", message)
        self.assertEqual({s.load for s in proposal.sets}, {100})

    def test_a_near_target_exposure_keeps_the_range_and_target_effort_with_no_flag(self):
        proposal = propose(BENCH, program(3, 8, 12), [(80, 10, 8), (80, 9, 8.5), (80, 9, 9)])
        self.assertEqual(line(proposal), [(80, None, (8, 12), 8)] * 3)
        self.assertEqual(proposal.flags, ())

    def test_effort_one_over_target_is_not_a_mismatch(self):
        proposal = propose(BENCH, program(3, 8, 12), [(80, 10, 9)] * 3)
        self.assertEqual(proposal.flags, ())

    def test_unknown_rpe_makes_no_effort_claim(self):
        proposal = propose(BENCH, program(3, 8, 12), [(80, 10, None)] * 3)
        self.assertEqual(proposal.flags, ())

    def test_every_set_at_the_top_adds_the_increment_and_keeps_the_range_and_target(self):
        proposal = propose(BENCH, program(3, 8, 12), [(80, 12, 8)] * 3)
        self.assertEqual(line(proposal), [(82.5, None, (8, 12), 8)] * 3)
        self.assertIn("every working set reached 12 reps at or under the target RPE", proposal.rationale)
        self.assertEqual(proposal.flags, ())

    def test_an_extra_set_past_the_prescription_neither_holds_nor_flags(self):
        proposal = propose(BENCH, program(3, 8, 12), [(80, 12, 8)] * 3 + [(80, 6, 10)])
        self.assertEqual({s.load for s in proposal.sets}, {82.5})
        self.assertEqual(proposal.flags, ())

    def test_a_fixed_rep_line_keeps_its_reps(self):
        slot = ({"count": 3, "type": "normal", "reps": 5, "rpe": 7},)
        proposal = propose(BENCH, slot, [(100, 5, 7), (100, 5, 7), (100, 4, 8)])
        self.assertEqual(line(proposal), [(100, 5, None, 7)] * 3)


    def test_a_top_set_without_a_logged_load_holds_and_says_so(self):
        proposal = propose(BENCH, program(3, 8, 12), [(None, 12, 8)] * 3)
        self.assertIn("logged without a load", proposal.rationale)
        self.assertNotIn("None", proposal.rationale)
        self.assertEqual(proposal.flags, ())

    def test_a_slot_with_no_working_sets_is_left_as_programmed(self):
        slot = ({"count": 2, "type": "warmup", "reps": 10},)
        proposal = propose(BENCH, slot, [(80, 12, 8)])
        self.assertEqual(proposal.sets, base.expand(slot))
        self.assertIn("no working sets", proposal.rationale)


class SetGroupsTest(unittest.TestCase):
    """A top set plus back-offs: each set group keeps its own reps and RPE, in the line and in the words."""

    SLOT = ({"count": 1, "type": "normal", "reps": 3, "rpe": 8}, {"count": 3, "type": "normal", "reps": 5, "rpe": 7})

    def test_a_short_back_off_is_judged_against_its_own_group(self):
        proposal = propose(SQUAT, self.SLOT, [(140, 3, 8), (120, 3, 7), (120, 3, 7), (120, 3, 7)])
        [message] = [f["message"] for f in proposal.flags if f["code"] == "range_effort_mismatch"]
        self.assertNotIn("below the program's 3", message)
        self.assertIn("logged 3, 3, 3 reps on sets 2–4 at 120, below the program's 5;", message)
        self.assertIn("140 holds and the target is 3 reps at RPE 8, then 5 reps at RPE 7", proposal.rationale)
        self.assertEqual([(s.reps, s.rpe) for s in proposal.sets], [(3, 8), (5, 7), (5, 7), (5, 7)])

    def test_effort_over_target_names_the_set_it_was_on(self):
        proposal = propose(SQUAT, self.SLOT, [(140, 3, 8), (120, 5, 9), (120, 5, 7), (120, 5, 7)])
        [message] = [f["message"] for f in proposal.flags if f["code"] == "range_effort_mismatch"]
        self.assertIn("logged RPE 9 on set 2 at 120 against the target RPE 7;", message)

    def test_every_group_at_its_top_adds_the_increment_and_keeps_each_group(self):
        proposal = propose(SQUAT, self.SLOT, [(140, 3, 8), (120, 5, 7), (120, 5, 7), (120, 5, 7)])
        self.assertIn("every working set reached the top of its range", proposal.rationale)
        self.assertIn("the target is 3 reps at RPE 8, then 5 reps at RPE 7", proposal.rationale)
        self.assertEqual([(s.reps, s.rpe) for s in proposal.sets], [(3, 8), (5, 7), (5, 7), (5, 7)])


class LoadStepGateTest(unittest.TestCase):
    TOP = [(20, 15, 8), (20, 15, 9), (20, 15, 9.5)]

    def test_an_isolation_lift_at_the_top_adds_the_increment_whatever_its_rpe(self):
        proposal = propose(CURL, program(3, 12, 15), self.TOP)
        self.assertEqual(line(proposal), [(21, None, (12, 15), 8)] * 3)
        self.assertEqual(proposal.flags, ())
        self.assertIn("every working set reached 15 reps", proposal.rationale)
        self.assertIn("RPE 9.5 over the target RPE 8 does not hold isolation work", proposal.rationale)
        self.assertNotIn("at or under the target RPE", proposal.rationale)

    def test_a_compound_lift_keeps_its_effort_gate(self):
        proposal = propose(replace(BENCH, increment=1), program(3, 12, 15), self.TOP)
        self.assertEqual({s.load for s in proposal.sets}, {20})
        self.assertIn("over the target RPE 8", proposal.rationale)

    def test_a_recovery_cap_keeps_the_effort_gate_on_isolation_work(self):
        proposal = propose(CURL, program(3, 12, 15), self.TOP, constraints=(RPE_CAP,))
        self.assertEqual({s.load for s in proposal.sets}, {20})
        self.assertIn("recovery cap", proposal.rationale)

    def test_work_not_classified_as_isolation_keeps_the_effort_gate(self):
        proposal = propose(CRUNCH, program(3, 12, 15), self.TOP)
        self.assertEqual({s.load for s in proposal.sets}, {20})

    def test_an_isolation_lift_short_of_the_top_holds(self):
        proposal = propose(CURL, program(3, 12, 15), [(20, 15, 8), (20, 14, 8), (20, 13, 8)])
        self.assertEqual({s.load for s in proposal.sets}, {20})


class IsolationClassificationTest(unittest.TestCase):
    def test_only_single_joint_patterns_are_isolation(self):
        for pattern in ("elbow_flexion", "elbow_extension", "shoulder_raise", "knee_flexion", "knee_extension",
                        "hip_abduction", "hip_adduction", "calf_raise"):
            with self.subTest(pattern=pattern):
                self.assertTrue(patterns.is_isolation({"pattern": pattern}))
        for entry in ({"pattern": "squat"}, {"pattern": "core"}, {"pattern": "carry"}, {"pattern": None}, {}, None):
            with self.subTest(entry=entry):
                self.assertFalse(patterns.is_isolation(entry))


class BandAndModesTest(unittest.TestCase):
    def test_band_rationale_names_the_band_not_none(self):
        slot = program(3, 12, 15)
        top = propose(PULL_APART, slot, [(None, 15, 7)] * 3)
        held = propose(PULL_APART, slot, [(None, 13, 7)] * 3)
        for proposal in (top, held):
            self.assertNotIn("None", proposal.rationale)
            self.assertEqual({s.load for s in proposal.sets}, {None})
        self.assertIn("a harder band", top.rationale)
        self.assertIn("the band holds", held.rationale)

    def test_a_band_mismatch_asks_for_an_easier_band(self):
        held = propose(PULL_APART, program(3, 12, 15), [(None, 10, 7)] * 3)
        [message] = [f["message"] for f in held.flags if f["code"] == "range_effort_mismatch"]
        self.assertIn("on the band; holding the band at the program's range does not make it reachable", message)
        self.assertIn("review an easier band or a different rep range", message)
        self.assertNotIn("load", message)

    def test_an_assisted_mismatch_asks_for_more_assistance(self):
        held = propose(PULL_UP, program(3, 8, 12), [(30, 5, 8)] * 3)
        [message] = [f["message"] for f in held.flags if f["code"] == "range_effort_mismatch"]
        self.assertIn("review more assistance or a different rep range", message)
        self.assertNotIn("lighter", message)

    def test_a_bodyweight_mismatch_at_bodyweight_asks_for_an_easier_variation(self):
        dip = replace(BENCH, id="dip", name="Dip", load_mode="bodyweight")
        at_bw = propose(dip, program(3, 8, 12), [(0, 5, 8)] * 3)
        loaded = propose(dip, program(3, 8, 12), [(10, 5, 8)] * 3)
        self.assertIn("at BW; ", at_bw.flags[0]["message"])
        self.assertIn("review an easier variation or a different rep range", at_bw.flags[0]["message"])
        self.assertIn("review a lighter load or a different rep range", loaded.flags[0]["message"])

    def test_programs_every_load_mode_but_duration_and_distance(self):
        self.assertEqual(set(double_progression.LOAD_MODES),
                         {"total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band"})


PLANK = {"exercise_id": "plank", "load_mode": "duration",
         "sets": [{"count": 2, "type": "normal", "duration_seconds": 30, "rpe": 7}], "rest_seconds": 60,
         "superset_id": None, "cues": None, "constraints": [], "scheme": {"name": "hold", "params": {}},
         "start_load": None}


class ExtraSlotCase(ProposeCase):
    """The valid instance with `extra_slot` added to session-b as its third exercise."""

    extra_slot = None

    def setUp(self):
        super().setUp()
        self.edit_program(lambda doc: doc["sessions"][1]["exercises"].append(dict(self.extra_slot)))
        self.coach("library", "set-mode", self.extra_slot["exercise_id"], self.extra_slot["load_mode"])
        cache_catalogue_templates(self.root, NOW)

    def override(self, exercise, spec, expect=0):
        envelope = self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-b",
                              "--exercise", exercise, "--sets", spec, "--reason", "synthetic: longer hold",
                              expect=expect)
        return envelope["data"] if expect == 0 else envelope

    def refusal(self, exercise_id):
        """The validate message for setting `exercise_id` on double progression."""
        self.set_scheme("session-b", exercise_id, "double_progression")
        envelope = self.coach("program", "validate", expect=1)
        details = {d["path"]: d["message"] for d in envelope["error"]["details"]}
        return details["$.sessions[1].exercises[2].scheme.name"]


class DurationSlotTest(ExtraSlotCase):
    extra_slot = PLANK

    def test_double_progression_on_a_duration_slot_fails_validate_and_names_a_supported_path(self):
        message = self.refusal("plank")
        self.assertIn("this slot is duration", message)
        self.assertIn("hold", message)
        self.assertIn('propose override --sets "2x35s rpe7"', message)

    def test_a_duration_override_survives_finalize_and_the_sheets(self):
        self.propose()
        data = self.override("plank", "2x35s rpe7")
        self.assertEqual(data["lines"][0]["text"], "2×35 s RPE 7")
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        stored = find_line(read_json(self.root / "data" / "overlays" / f"{FIRST_ID}.json"), "plank")
        self.assertEqual([(s["duration_seconds"], s["rpe"], s.get("reps"), s["load"]) for s in working(stored)],
                         [(35, 7, None, None)] * 2)
        self.coach("sheets", "render", "--overlay", FIRST_ID)
        sheets = (self.root / "this-week-sheets.md").read_text(encoding="utf-8")
        self.assertIn("35 s", sheets)
        self.assertNotIn("30 s", sheets)

    def test_mixed_or_mismatched_metrics_refuse_without_writes(self):
        self.propose()
        before = self.snapshot()
        for exercise, spec, code in (("plank", "2x35s, 1x10", 2), ("plank", "2x30-40s", 2), ("plank", "2x35s@10", 2),
                                     ("plank", "3x10 rpe7", 1), ("db_single_arm_row", "2x35s rpe7", 1)):
            with self.subTest(spec=spec):
                envelope = self.override(exercise, spec, expect=code)
                self.assertIn(spec.split(",")[0].strip() if code == 2 else exercise, envelope["error"]["message"])
        self.assertEqual(self.snapshot(), before)


ROW = {"exercise_id": "rowing_machine", "load_mode": "distance",
       "sets": [{"count": 1, "type": "normal", "distance_meters": 2000, "rpe": 6}], "rest_seconds": 60,
       "superset_id": None, "cues": None, "constraints": [], "scheme": {"name": "hold", "params": {}},
       "start_load": None}


class DistanceSlotTest(ExtraSlotCase):
    extra_slot = ROW

    def test_double_progression_on_a_distance_slot_names_hold_alone(self):
        message = self.refusal("rowing_machine")
        self.assertIn("this slot is distance; use hold, which repeats the program's distance", message)
        self.assertNotIn("linear", message)

    def test_sets_on_a_distance_line_refuse_without_writes(self):
        self.propose()
        before = self.snapshot()
        for spec in ("1x10 rpe6", "1x600s rpe6"):
            with self.subTest(spec=spec):
                envelope = self.override("rowing_machine", spec, expect=1)
                self.assertIn("rowing_machine is a distance line, and --sets takes reps or seconds, not a distance",
                              envelope["error"]["message"])
        self.assertEqual(self.snapshot(), before)


class ComputeGuidanceTest(unittest.TestCase):
    def test_compute_settles_the_mismatch_flag_and_shows_the_timed_override(self):
        text = flat(step_text("program-week", "compute.md"))
        self.assertIn("`range_effort_mismatch`", text)
        self.assertIn("agree a lighter load or a different rep range", text)
        self.assertIn('`--sets "2x35s rpe7"`', text)


if __name__ == "__main__":
    unittest.main()
