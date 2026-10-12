"""Load cuts (resets, return bands, deloads, light weeks) take the nearest load the kit makes (C23, C24, R-24)."""

import math
import unittest

from coach import overlay, propose, stats, units
from coach.loads import AvailableLoads
from tests.support.history import read_json
from tests.test_propose import SQUAT, LayoffCase, ProposeCase, codes, coaching, edit_sets, find_line, working


def machine(step=5):
    return AvailableLoads("machine", "total", {}, step)


class SelectCutTest(unittest.TestCase):
    def test_the_nearest_load_wins_over_a_whole_step_down(self):
        bar = AvailableLoads("barbell", "total", {"bar_weight": 20.0, "plates": [25, 20, 15, 10, 5, 2.5, 1.25]}, 2.5)
        self.assertEqual(bar.select_cut(72, 80), 72.5)

    def test_a_cut_the_grid_cannot_make_holds_the_baseline(self):
        self.assertEqual(machine().select_cut(23.75, 25), 25)

    def test_a_tie_takes_the_lighter_load(self):
        self.assertEqual(machine().select_cut(22.5, 25), 20)
        rack = AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [20, 22.5, 25]}, 2.5)
        self.assertEqual(rack.select_cut(21.25, 25), 20)

    def test_neither_the_baseline_nor_a_cap_is_crossed(self):
        self.assertEqual(machine().select_cut(23.75, 25, cap=22), 20)
        rack = AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [20, 25]}, 2.5)
        self.assertEqual(rack.select_cut(23, 22), 20)

    def test_nothing_at_or_under_the_bounds_selects_nothing(self):
        rack = AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [22.5, 25]}, 2.5)
        self.assertIsNone(rack.select_cut(18, 20))


class CutWordsTest(unittest.TestCase):
    def test_a_cut_the_kit_can_only_make_heavier_says_the_load_rises(self):
        cut = {"baseline": 4, "target": 3.6, "actual": 5, "held": True, "rose": True, "other_cuts": True,
               "lighter": None}
        self.assertIn("the kit makes nothing at or under 4, so the load rises to 5, the nearest it makes",
                      propose._cut_words(cut, "total", "kg"))
        held = propose._held_cut_words(cut, "Curl", "total", "kg")
        self.assertIn("so the load rises to 5, the nearest it makes", held)
        self.assertNotIn("holds", held)


def squat_rationale(doc):
    return find_line(doc, "bb_back_squat")["provenance"]["rationale"]


def squat_loads(doc):
    return [coaching(s["load"]) for s in working(find_line(doc, "bb_back_squat"))]


class ResetCase(ProposeCase):
    LOAD = 80
    workouts = None

    def setUp(self):
        self.workouts = edit_sets(SQUAT, lambda wid, i, s: s.update(weight_kg=float(self.LOAD), reps=4))
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "linear")


class ResetOnAFineGridTest(ResetCase):
    def test_two_misses_reset_80_to_72_5_and_report_target_and_actual(self):
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual(set(squat_loads(doc)), {72.5})
        rationale = squat_rationale(doc)
        self.assertIn("the reset targets 90 % of 80", rationale)
        self.assertIn("a 10 % cut from 80 targets 72; the kit makes 72.5, an actual 9.4 % cut", rationale)
        self.assertNotIn("the kit makes 72.5, not 72", rationale)
        self.assertNotIn("load_cut_held", codes(doc, "bb_back_squat"))


class ResetOnACoarseGridTest(ResetCase):
    LOAD = 30

    def test_a_reset_the_kit_cannot_make_holds_and_asks_the_coach(self):
        self.set_config("barbell_increment = 2.5", "barbell_increment = 10")
        self.set_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [20, 10, 5]")
        data = self.propose()
        doc = data["overlay"]
        self.assertEqual(set(squat_loads(doc)), {30})
        rationale = squat_rationale(doc)
        self.assertIn("the reset targets 90 % of 30", rationale)
        self.assertIn("a 10 % cut from 30 targets 27; the nearest load the kit makes no heavier than 30 is 30 "
                      "itself, so the load holds (an actual 0 % cut) and no part of the cut applies", rationale)
        self.assertNotIn("resets to", rationale)
        [flag] = [f for f in doc["flags"] if f["code"] == "load_cut_held" and f["exercise_id"] == "bb_back_squat"]
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("no reset or cut is applied, so choose between holding it and 20, a 33.3 % cut",
                      flag["message"])
        meta = read_json(self.draft_path(data["id"]).with_suffix(".meta.json"))
        self.assertEqual(meta["scheme_state"]["session-a/bb_back_squat"]["data"]["misses"], 2)


class MachineSquatCase(ProposeCase):
    """The squat on a 5-step machine, last logged at 25."""

    workouts = staticmethod(edit_sets(SQUAT, lambda wid, i, s: s.update(weight_kg=25.0)))

    def setUp(self):
        super().setUp()
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["bb_back_squat"].update(
            equipment="machine"))

    def deload(self, rule, **params):
        self.edit_program(lambda doc: doc["blocks"].update(deload_rule={"name": rule, "params": params}))
        return self.propose("--kind", "deload", "--dry-run")["overlay"]


class DeloadCutTest(MachineSquatCase):
    def test_a_standard_deload_tie_takes_the_lighter_load(self):
        doc = self.deload("standard")
        self.assertEqual(set(squat_loads(doc)), {20})
        self.assertIn("a 10 % cut from 25 targets 22.5; the kit makes 20, an actual 20 % cut", squat_rationale(doc))
        self.assertNotIn("load_cut_held", codes(doc, "bb_back_squat"))

    def test_a_light_week_cut_the_kit_cannot_make_keeps_its_set_and_effort_cuts(self):
        doc = self.deload("light", load_factor=0.95)
        line = find_line(doc, "bb_back_squat")
        self.assertEqual(set(squat_loads(doc)), {25})
        self.assertEqual(len(working(line)), 2)
        self.assertTrue(all(s["rpe"] <= 8 for s in working(line)))
        self.assertIn("so the load holds (an actual 0 % cut) and the set and effort cuts still apply",
                      squat_rationale(doc))
        [flag] = [f for f in doc["flags"] if f["code"] == "load_cut_held" and f["exercise_id"] == "bb_back_squat"]
        self.assertEqual(flag["severity"], "info")

    def test_a_cap_below_the_nearest_load_wins(self):
        self.set_config("[caps]", "[caps]\nbb_back_squat = 22")
        doc = self.deload("light", load_factor=0.95)
        self.assertEqual(set(squat_loads(doc)), {20})
        self.assertNotIn("load_cut_held", codes(doc, "bb_back_squat"))


class EffortCeilingCutTest(ProposeCase):
    """A fixed_reps_rpe squat: its e1RM load sits below the derived-from 97.5 and is an effort ceiling."""

    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "fixed_reps_rpe")
        best = max(p["e1rm"] for p in stats.e1rm_series(self.root)["series"]["bb_back_squat"])
        self.scheme_load = stats.load_for(best, 5, 7)

    def test_a_deload_measures_its_cut_from_the_scheme_load_and_rounds_down(self):
        target = self.scheme_load * 0.9
        below = 2.5 * math.floor(target / 2.5)
        self.assertLess(self.scheme_load, 97.5)
        self.assertGreater(target - below, 1.25, "the nearest load would be heavier than the round-down one")
        doc = self.propose("--kind", "deload", "--dry-run")["overlay"]
        self.assertEqual(set(squat_loads(doc)), {below})
        actual = units.format_number(round((self.scheme_load - below) / self.scheme_load * 100, 1))
        self.assertIn(f"a 10 % cut from {units.format_number(self.scheme_load)} targets "
                      f"{units.format_number(target)}; the kit makes {units.format_number(below)}, an actual "
                      f"{actual} % cut", squat_rationale(doc))


class CutBelowTheDerivedLoadTest(MachineSquatCase):
    """A hold squat on a 5-step machine whose newest exposure (25) sits above the line's own load (20)."""

    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "hold")

    def test_a_cut_the_kit_rounds_back_to_the_week_s_load_holds(self):
        self.edit_json("data/overlays/2026-10-12-weekly.json", self.approved_at(20))
        doc = self.deload("light", load_factor=0.95)
        self.assertEqual(set(squat_loads(doc)), {20})
        self.assertIn("a 5 % cut from 20 targets 19; the nearest load the kit makes no heavier than 20 is 20 itself",
                      squat_rationale(doc))
        self.assertIn("load_cut_held", codes(doc, "bb_back_squat"))

    @staticmethod
    def approved_at(load):
        def edit(doc):
            line = find_line(doc, "bb_back_squat")
            for s in working(line):
                s["load"] = units.make_load(load, line["load_mode"], "kg")
            doc["approval"]["hash"] = overlay.approval_hash(doc)
        return edit


class ReturnBandCutTest(LayoffCase):
    """The layoff instance with the squat on a 5-step machine at 25, last trained 18 days before session A."""

    def setUp(self):
        super().setUp()
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["bb_back_squat"].update(
            equipment="machine"))

        def machine_squat(doc):
            for workout in doc["workouts"]:
                for exercise in workout["exercises"]:
                    if exercise["exercise_id"] == "bb_back_squat":
                        for set_ in exercise["sets"]:
                            set_.update(weight_kg=25.0, load=dict(set_["load"], hevy_total=25, hevy_kg=25))
                if workout["date"] == "2026-09-14":
                    workout.update(date="2026-09-24", start_time="2026-09-24T18:00:00Z",
                                   end_time="2026-09-24T19:00:00Z")
        for month in ("2026-08", "2026-09"):
            self.edit_json(f"data/history/{month}.json", machine_squat)

    def check(self, data):
        checked = self.coach("prescription", "check", "--file", str(self.draft_path(data["id"])))["data"]
        return [f for f in checked["flags"] if f["exercise_id"] == "bb_back_squat"]

    def test_the_11_21_band_holds_25_with_one_set_fewer_and_passes_the_check(self):
        data = self.propose()
        line = find_line(data["overlay"], "bb_back_squat")
        self.assertEqual(line["provenance"]["decay"]["band"], "11-21")
        self.assertEqual(squat_loads(data["overlay"]), [25, 25])
        self.assertIn("a 5 % cut from 25 targets 23.75; the nearest load the kit makes no heavier than 25 is 25 "
                      "itself, so the load holds (an actual 0 % cut) and the set and effort cuts still apply",
                      line["provenance"]["rationale"])
        self.assertNotIn("stale_prescription", [f["code"] for f in self.check(data)])

    def test_a_hand_built_load_above_the_kit_s_cut_is_stale(self):
        data = self.propose()

        def heavier(doc):
            line = find_line(doc, "bb_back_squat")
            for s in working(line):
                s["load"] = 30
        self.edit_json(f".coach/proposals/{data['id']}.json", heavier)
        [flag] = [f for f in self.check(data) if f["code"] == "stale_prescription"]
        self.assertIn("load 30 is above 25, the kit's nearest load to 25 × 0.95 (23.75) no heavier than 25",
                      flag["message"])


class BarbellReturnCheckTest(LayoffCase):
    def test_one_increment_over_the_kit_s_cut_is_stale(self):
        data = self.propose()
        self.assertEqual(set(squat_loads(data["overlay"])), {90})

        def heavier(doc):
            for s in working(find_line(doc, "bb_back_squat")):
                s["load"] = 92.5
        self.edit_json(f".coach/proposals/{data['id']}.json", heavier)
        checked = self.coach("prescription", "check", "--file", str(self.draft_path(data["id"])))["data"]
        [flag] = [f for f in checked["flags"] if f["code"] == "stale_prescription"
                  and f["exercise_id"] == "bb_back_squat"]
        self.assertIn("load 92.5 is above 90, the kit's nearest load to 100 × 0.9 (90) no heavier than 100",
                      flag["message"])


if __name__ == "__main__":
    unittest.main()
