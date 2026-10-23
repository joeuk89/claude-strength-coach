"""Warm-up loads: the ramp into the first working set, its pins, and where the loads land (contract C24, C46)."""

import unittest
from unittest import mock

from coach import program, render, sheets, warmups
from coach.loads import AvailableLoads
from coach.plugins import base
from tests.support.fake_hevy import FakeHevy
from tests.support.history import SYNTHETIC, read_json
from tests.test_program import valid_doc
from tests.test_propose import FIRST_ID, LayoffCase, ProposeCase, coaching, find_line, working

PLATES = [25, 20, 15, 10, 5, 2.5, 1.25]
BAR = AvailableLoads("barbell", "total", {"bar_weight": 20.0, "plates": PLATES}, 2.5)
RACK = AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [5, 10, 15, 20]}, 2.5)
GRID = AvailableLoads("dumbbell", "per_hand_x2", {}, 2.5)


def sets(warmup_count, load, reps=5, mode_type="normal"):
    return (base.SetSpec(type="warmup", reps=reps),) * warmup_count + (
        base.SetSpec(type=mode_type, reps=reps, rpe=7, load=load),) * 3


def warmup_loads(found):
    return [s.load for s in found if s.type == "warmup"]


class RampTest(unittest.TestCase):
    def test_the_ramp_by_warm_up_count(self):
        self.assertEqual(warmups.percents(1), (60,))
        self.assertEqual(warmups.percents(2), (50, 75))
        self.assertEqual(warmups.percents(3), (40, 60, 80))
        self.assertEqual([round(p, 2) for p in warmups.percents(4)], [40, 53.33, 66.67, 80])

    def test_two_warm_ups_on_a_barbell_take_50_and_75_percent_on_the_plates(self):
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 100), "total", BAR)), [50, 75])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 102.5), "total", BAR)), [50, 75])

    def test_three_warm_ups_take_40_60_and_80_percent_rounded_down(self):
        self.assertEqual(warmup_loads(warmups.with_loads(sets(3, 102.5), "total", BAR)), [40, 60, 80])

    def test_a_barbell_warm_up_never_drops_below_the_bar_and_a_repeat_of_it_is_dropped(self):
        self.assertEqual(warmup_loads(warmups.with_loads(sets(3, 30), "total", BAR)), [20, None, 22.5])

    def test_a_coarse_kit_never_prescribes_the_same_warm_up_twice(self):
        bells = AvailableLoads("kettlebell", "single_implement", {"kettlebells": [12, 16, 20, 24, 28]}, 4)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 16), "single_implement", bells)), [12, None])
        lb_rack = AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [10, 15, 20]}, 5)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 15), "per_hand_x2", lb_rack)), [10, None])
        lb_bar = AvailableLoads("barbell", "total", {"bar_weight": 45, "plates": [45, 35, 25, 10, 5, 2.5]}, 5)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 55), "total", lb_bar)), [45, None])
        self.assertEqual(warmups.words(warmups.with_loads(sets(2, 55), "total", lb_bar), "total", lb_bar, [], str),
                         "warm-ups 45 (50 %) and none (a repeat of 45), percents of the first working set")

    def test_a_kit_that_cannot_be_enumerated_rounds_to_its_step_or_gives_no_load(self):
        no_step = AvailableLoads("machine", "total", {}, 0)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 97.5), "total", no_step)), [None, None])
        self.assertEqual(warmups.words(warmups.with_loads(sets(1, 97.5), "total", no_step), "total", no_step, [], str),
                         "warm-ups none (no load step is set for this kit)")
        stepped = AvailableLoads("machine", "total", {}, 5)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 97.5), "total", stepped)), [45, 70])
        smith = AvailableLoads("smith_machine", "total", {"plates": PLATES}, 2.5)
        self.assertIsNotNone(smith.geometry_warning)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 97.5), "total", smith)), [47.5, 72.5])
        ez = AvailableLoads("ez_bar", "total", {"plates": PLATES}, 2.5)
        self.assertEqual(warmup_loads(warmups.with_loads(sets(1, 27.5), "total", ez)), [15])

    def test_nothing_lighter_than_the_first_working_load_leaves_the_warm_up_open(self):
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 20), "total", BAR)), [None, None])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(1, 5), "per_hand_x2", RACK)), [None])

    def test_per_hand_warm_ups_land_on_the_rack_or_the_dumbbell_grid(self):
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 20), "per_hand_x2", RACK)), [10, 15])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 17.5), "per_hand_x2", RACK)), [5, 10])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(1, 22.5), "per_hand_x2", GRID)), [12.5])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 25), "single_implement", RACK)), [10, 15])

    def test_bodyweight_assisted_banded_and_unloaded_lines_keep_their_warm_ups(self):
        belt = AvailableLoads("other", "bodyweight", {"plates": PLATES}, 0)
        for mode, available, load in (("bodyweight", belt, 10), ("assisted", GRID, 20), ("band", None, None),
                                      ("total", BAR, None)):
            with self.subTest(mode=mode):
                found = sets(2, load)
                self.assertEqual(warmups.with_loads(found, mode, available), found)

    def test_a_pinned_load_or_percent_replaces_the_ramp_for_its_position(self):
        pins = warmups.pins([{"count": 1, "type": "warmup", "reps": 5, "warmup_load": 60},
                             {"count": 1, "type": "warmup", "reps": 3, "warmup_percent": 85},
                             {"count": 3, "type": "normal", "reps": 5}])
        self.assertEqual(pins, [{"load": 60}, {"percent": 85}])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 100), "total", BAR, pins)), [60, 85])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 101), "total", BAR, pins)), [60, 85])

    def test_a_pin_at_or_above_a_cut_working_load_gives_way_to_the_ramp(self):
        pins = [{"load": 60}, None]
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 60), "total", BAR, pins)), [30, 45])
        self.assertEqual(warmup_loads(warmups.with_loads(sets(2, 50), "total", BAR, pins)), [25, 37.5])

    def test_the_words_name_each_load_and_its_percent_or_pin(self):
        text = lambda v: str(v)  # noqa: E731
        found = warmups.with_loads(sets(2, 100), "total", BAR)
        self.assertEqual(warmups.words(found, "total", BAR, [], text),
                         "warm-ups 50 (50 %) and 75 (75 %), percents of the first working set")
        pins = [{"load": 60}, None]
        found = warmups.with_loads(sets(2, 100), "total", BAR, pins)
        self.assertEqual(warmups.words(found, "total", BAR, pins, text),
                         "warm-ups 60 (pinned) and 75 (75 %), percents of the first working set")
        found = warmups.with_loads(sets(1, 20), "total", BAR)
        self.assertEqual(warmups.words(found, "total", BAR, [], text),
                         "warm-ups none lighter than the first working set")
        self.assertIsNone(warmups.words(sets(1, None), "total", BAR, [], text))


class PinValidationTest(unittest.TestCase):
    def errors(self, change):
        doc = valid_doc()
        change(doc["sessions"][0]["exercises"], doc["sessions"][1]["exercises"])
        return [(e.path, e.message) for e in program.validate(doc)]

    def test_a_pinned_warm_up_on_a_ramping_line_is_valid(self):
        def pin(session_a, _):
            session_a[0]["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 5, "warmup_percent": 55})
            session_a[1]["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 10, "warmup_load": 10})
        self.assertEqual(self.errors(pin), [])

    def test_a_pin_on_a_working_group_both_pins_or_a_bodyweight_line_are_errors(self):
        def wrong(session_a, session_b):
            session_a[0]["sets"][0]["warmup_percent"] = 55
            session_a[1]["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 10, "warmup_load": 10,
                                            "warmup_percent": 50})
            session_b[1]["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 5, "warmup_load": 5})
        found = self.errors(wrong)
        self.assertEqual([path for path, _ in found],
                         ["$.sessions[0].exercises[0].sets[0].warmup_percent",
                          "$.sessions[0].exercises[1].sets[0].warmup_percent",
                          "$.sessions[1].exercises[1].sets[0].warmup_load"])
        self.assertIn("warmup set group, not a normal one", found[0][1])
        self.assertIn("not both", found[1][1])
        self.assertIn("keeps load-less warm-ups", found[2][1])

    def test_the_schema_bounds_a_percent_pin(self):
        def over(session_a, _):
            session_a[0]["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 5, "warmup_percent": 100})
        self.assertTrue(any("warmup_percent" in path for path, _ in self.errors(over)))

    def test_the_session_page_shows_a_pin_on_its_warm_up_row(self):
        doc = valid_doc()
        squat = doc["sessions"][0]["exercises"][0]
        squat["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 5, "warmup_percent": 55})
        squat["sets"].insert(0, {"count": 1, "type": "warmup", "reps": 8, "warmup_load": 40})
        text = program.render_session_page(doc["sessions"][0], program_library(), "kg")
        self.assertIn("| 1×8 warm-up |  | 40 pinned |", text)
        self.assertIn("| 1×5 warm-up |  | 55 % pinned |", text)


def program_library():
    from coach.library import Library
    from tests.support import VALID
    return Library.load(VALID)


def add_warmups(doc, squat=2, bench=1):
    session_a = doc["sessions"][0]["exercises"]
    session_a[0]["sets"] = [{"count": squat, "type": "warmup", "reps": 5}] + session_a[0]["sets"]
    session_a[1]["sets"] = [{"count": bench, "type": "warmup", "reps": 10}] + session_a[1]["sets"]


class WarmupCase(ProposeCase):
    def setUp(self):
        super().setUp()
        self.edit_program(add_warmups)

    def squat_and_bench(self, doc):
        return find_line(doc, "bb_back_squat"), find_line(doc, "db_bench_press")


class ProposedWeekTest(WarmupCase):
    def test_warm_ups_ramp_from_each_line_s_first_working_load(self):
        doc = self.propose("--dry-run")["overlay"]
        squat, bench = self.squat_and_bench(doc)
        first = coaching(working(squat)[0]["load"])
        self.assertEqual([coaching(s["load"]) for s in squat["sets"] if s["type"] == "warmup"],
                         [BAR.select(first * 50 / 100, "down"), BAR.select(first * 75 / 100, "down")])
        self.assertEqual(first, 97.5)
        self.assertEqual([coaching(s["load"]) for s in squat["sets"] if s["type"] == "warmup"], [47.5, 72.5])
        self.assertEqual([coaching(s["load"]) for s in bench["sets"] if s["type"] == "warmup"], [15])
        self.assertIn("warm-ups 47.5 (50 %) and 72.5 (75 %), percents of the first working set",
                      squat["provenance"]["rationale"])
        self.assertIn("warm-ups 15/hand (Hevy: 30) (60 %)", bench["provenance"]["rationale"])
        self.assertEqual(render.target_line(squat).split(" @ ")[0], "Target: 3×5")

    def test_a_deload_recomputes_the_ramp_from_the_cut_working_load(self):
        doc = self.propose("--kind", "deload", "--dry-run")["overlay"]
        squat, _ = self.squat_and_bench(doc)
        first = coaching(working(squat)[0]["load"])
        self.assertEqual(first, 87.5)
        self.assertEqual([coaching(s["load"]) for s in squat["sets"] if s["type"] == "warmup"], [42.5, 65])

    def test_a_pin_in_the_program_holds_its_position(self):
        def pin(doc):
            groups = doc["sessions"][0]["exercises"][0]["sets"]
            groups[0] = {"count": 1, "type": "warmup", "reps": 8, "warmup_load": 40}
            groups.insert(1, {"count": 1, "type": "warmup", "reps": 3, "warmup_percent": 80})
        self.edit_program(pin)
        doc = self.propose("--dry-run")["overlay"]
        squat, _ = self.squat_and_bench(doc)
        self.assertEqual([coaching(s["load"]) for s in squat["sets"] if s["type"] == "warmup"], [40, 77.5])
        self.assertIn("warm-ups 40 (pinned) and 77.5 (80 %)", squat["provenance"]["rationale"])

    def test_an_override_ramps_the_warm_ups_again_from_the_new_first_working_load(self):
        self.propose()
        data = self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                          "bb_back_squat", "--sets", "3x5@80 rpe7", "--reason", "sore hip")["data"]
        self.assertEqual(data["lines"][0]["text"], "3×5 @ 80 RPE 7")
        draft = read_json(self.draft_path())
        squat = find_line(draft, "bb_back_squat")
        self.assertEqual([s["load"] for s in squat["sets"] if s["type"] == "warmup"], [40, 60])
        self.assertEqual([s["load"] for s in squat["override"]["proposed_sets"] if s["type"] == "warmup"],
                         [47.5, 72.5])

    def test_the_hevy_push_sheets_and_week_ahead_carry_the_warm_up_loads(self):
        self.propose()
        doc = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]["overlay"]
        self.coach("overlay", "approve", doc["id"])
        fake = FakeHevy(SYNTHETIC)
        with mock.patch("coach.hevy.transport.from_env", return_value=fake), \
                mock.patch("coach.hevy.client.time.sleep"):
            data = self.coach("routines", "push", "--overlay", doc["id"],
                              env={"HEVY_API_KEY": "k-0000-0000"})["data"]
        self.assertEqual([r["status"] for r in data["routines"]], ["written", "written"])
        session_a = fake.put_bodies[0]["routine"]
        self.assertEqual([(s["type"], s.get("weight_kg")) for s in session_a["exercises"][0]["sets"]],
                         [("warmup", 47.5), ("warmup", 72.5), ("normal", 97.5), ("normal", 97.5), ("normal", 97.5)])
        self.assertEqual(session_a["exercises"][1]["sets"][0], {"type": "warmup", "weight_kg": 30, "reps": 10})
        text = sheets.render_sheets(self.root, doc["id"])
        self.assertIn("| Back Squat (Barbell) | 1×5 warm-up | 47.5 |  |  |  |", text)
        self.assertIn("|  | 1×5 warm-up | 72.5 |  |  |  |", text)
        self.assertIn("| Bench Press (Dumbbell) | 1×10 warm-up | 15/hand |  |  |  |", text)
        self.assertNotIn(f"| {render.CHOOSE_THE_LOAD} |", text)
        region = render.render_overlay_doc(self.root, doc)
        self.assertIn("| 1×5 warm-up | 72.5 |", region)
        self.assertIn("| 1×10 warm-up | 15/hand (Hevy: 30) |", region)


class ReturnWeekTest(LayoffCase):
    def test_a_return_band_cut_ramps_the_warm_ups_from_the_cut_load(self):
        self.set_scheme("session-a", "bb_back_squat", "hold")
        self.edit_program(add_warmups)
        doc = self.propose("--dry-run")["overlay"]
        squat = find_line(doc, "bb_back_squat")
        self.assertEqual([coaching(s["load"]) for s in working(squat)], [90, 90])
        self.assertEqual(squat["provenance"]["decay"]["band"], "22-42")
        # Hold repeats the last prescription, whose one warm-up now ramps at 60 % of the cut load, not of 100.
        self.assertEqual([coaching(s["load"]) for s in squat["sets"] if s["type"] == "warmup"], [52.5])


if __name__ == "__main__":
    unittest.main()
