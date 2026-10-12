"""Physical equipment facts constrain requested progression steps in athlete units."""

import unittest

from coach import config, library, loads, onboarding, stats, units, validity
from coach.library import Library
from tests.support import VALID
from tests.test_propose import SQUAT, ProposeCase, coaching, codes, edit_sets, find_line, working
from tests.test_plugins import fixed_load_plugin


class AvailableLoadsTest(unittest.TestCase):
    def test_plate_selection_uses_combinations_not_only_a_common_divisor(self):
        kit = loads.AvailableLoads("barbell", "total", {"bar_weight": 20, "plates": [6, 10]}, 2.5)
        self.assertEqual(kit.select(22), 20)
        self.assertEqual(kit.select(30, "up"), 32)
        self.assertEqual(kit.select(31, "down"), 20)
        self.assertIsNotNone(kit.problem(24))
        self.assertIsNone(kit.problem(52))

    def test_rack_takes_precedence_over_grid_and_respects_caps(self):
        kit = loads.AvailableLoads("dumbbell", "per_hand_x2", {"dumbbells": [7, 12, 17]}, 2.5)
        self.assertEqual(kit.select(15), 17)
        self.assertEqual(kit.select(15, cap=16), 12)
        self.assertIsNone(kit.select(5, "down"))
        self.assertIsNone(kit.select(17, cap=6))
        self.assertIsNone(kit.problem(17))
        self.assertIsNotNone(kit.problem(15))

    def test_declared_location_then_main_increment_precedes_catalogue(self):
        library = Library.load(VALID)
        raw = {"schema_version": 1, "athlete": {"units": "kg"},
               "equipment": {"dumbbell_increment": 2.5, "locations": {"home": {"dumbbell_increment": 5}}}}
        cfg = config.parse(raw, "config.toml")
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", None), 2.5)
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", "home"), 5)
        raw["equipment"].pop("dumbbell_increment")
        cfg = config.parse(raw, "config.toml")
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", None), 2)

    def test_a_location_config_does_not_name_uses_the_main_step(self):
        cfg = config.load(VALID)
        self.assertEqual(stats.load_increment(Library.load(VALID), cfg, "db_bench_press", "hotel"), 2.5)

    def test_a_declared_dumbbell_step_does_not_define_the_kettlebell_grid(self):
        cfg = config.load(VALID)
        library = Library.load(VALID)
        self.assertEqual(cfg.declared_equipment["dumbbell_increment"], 2.5)
        step = stats.load_increment(library, cfg, "kb_swing", None)
        self.assertEqual(step, 4)
        self.assertIsNone(loads.AvailableLoads("kettlebell", "single_implement", {}, step).problem(24))

    def test_default_plates_do_not_override_a_declared_barbell_step(self):
        raw = {"schema_version": 1, "athlete": {"units": "kg"}, "equipment": {"barbell_increment": 5}}
        cfg = config.parse(raw, "config.toml")
        kit = loads.available_loads(Library.load(VALID), cfg, "bb_back_squat", "total", None)
        self.assertIsNotNone(kit.problem(102.5))
        self.assertEqual(kit.select(102.5, "down"), 100)

    def test_base_masses_are_optional_nonnegative_and_location_specific(self):
        for key in ("smith_base_weight", "ez_bar_weight", "trap_bar_weight"):
            with self.subTest(key=key):
                raw = {"schema_version": 1, "athlete": {"units": "kg"},
                       "equipment": {key: 15, "locations": {"home": {key: 7}}}}
                cfg = config.parse(raw, "config.toml")
                self.assertEqual(config.equipment_for(cfg)[key], 15)
                self.assertEqual(config.equipment_for(cfg, "home")[key], 7)
                self.assertNotIn(key, config.equipment_for(config.parse(
                    {"schema_version": 1, "athlete": {"units": "kg"}}, "config.toml")))
                raw["equipment"][key] = -1
                with self.assertRaises(config.ConfigError):
                    config.parse(raw, "config.toml")

    def test_ez_and_trap_bar_totals_build_on_their_declared_mass(self):
        plates = [25, 20, 15, 10, 5, 2.5, 1.25]
        trap = loads.AvailableLoads("trap_bar", "total", {"trap_bar_weight": 27, "plates": plates}, 2.5)
        self.assertIsNone(trap.geometry_warning)
        self.assertIsNone(trap.problem(29.5))
        self.assertIsNone(trap.problem(87))
        self.assertIn("base mass 27", trap.problem(87.5))
        self.assertEqual(trap.select(87.5, "down"), 87)
        ez = loads.AvailableLoads("ez_bar", "total", {"ez_bar_weight": 8, "plates": plates}, 2.5)
        self.assertIsNone(ez.problem(13))
        self.assertEqual(ez.select(13, "down"), 13)
        self.assertEqual(ez.select(12.5, "down"), 10.5)

    def test_a_declared_bar_step_without_plates_counts_from_the_bar_mass(self):
        trap = loads.AvailableLoads("trap_bar", "total", {"trap_bar_weight": 27, "plates": [20]}, 2.5,
                                    plates_win=False)
        self.assertIsNone(trap.problem(29.5))
        self.assertEqual(trap.select(88), 87)
        self.assertIsNotNone(trap.problem(87.5))

    def test_an_unknown_ez_or_trap_bar_mass_is_disclosed_not_assumed_zero(self):
        for equipment, key in (("ez_bar", "ez_bar_weight"), ("trap_bar", "trap_bar_weight")):
            with self.subTest(equipment=equipment):
                kit = loads.AvailableLoads(equipment, "total", {"bar_weight": 20, "plates": [5]}, 2.5)
                self.assertIn(f"equipment.{key}", kit.geometry_warning)
                self.assertIsNone(kit.problem(29.5))
                self.assertEqual(kit.select(13, "down"), 13)

    def test_machine_and_cable_grids_count_from_zero(self):
        for equipment in ("machine", "cable"):
            with self.subTest(equipment=equipment):
                kit = loads.AvailableLoads(equipment, "total", {}, 5)
                self.assertIsNotNone(kit.problem(22.5))
                self.assertEqual(kit.select(22.5), 25)
                self.assertIsNone(kit.problem(25))

    def test_undeclared_kettlebell_sizes_are_neither_snapped_nor_flagged(self):
        for unit, bells in (("kg", (14, 18)), ("lb", (35, 44, 53, 62))):
            raw = dict(onboarding.suggest(unit)["values"], schema_version=1)
            kit = loads.available_loads(Library.load(VALID), config.parse(raw, "config.toml"), "kb_swing",
                                        "single_implement", None)
            for bell in bells:
                with self.subTest(unit=unit, bell=bell):
                    self.assertIsNone(kit.problem(bell))
                    self.assertEqual(kit.select(bell, "down"), bell)

    def test_declared_kettlebells_are_the_bells_at_their_location(self):
        raw = {"schema_version": 1, "athlete": {"units": "kg"},
               "equipment": {"kettlebells": [12, 14, 16, 18, 20], "locations": {"home": {"kettlebells": [8, 12]}}}}
        cfg = config.parse(raw, "config.toml")
        gym = loads.available_loads(Library.load(VALID), cfg, "kb_swing", "single_implement", None)
        self.assertEqual(gym.select(17, "down"), 16)
        self.assertIsNone(gym.problem(18))
        self.assertIn("kettlebell", gym.problem(15))
        home = loads.available_loads(Library.load(VALID), cfg, "kb_swing", "single_implement", "home")
        self.assertEqual(home.select(16, "down"), 12)
        self.assertIsNotNone(home.problem(16))

    def test_zero_smith_base_is_known_geometry(self):
        kit = loads.AvailableLoads("smith_machine", "total", {"smith_base_weight": 0, "plates": [5]}, 2.5)
        self.assertIsNone(kit.geometry_warning)
        self.assertEqual(kit.select(12.5), 10)

    def test_lb_plate_geometry_stays_in_athlete_units(self):
        kit = loads.AvailableLoads("smith_machine", "total", {"smith_base_weight": 15, "plates": [10, 5]}, 2.5)
        value = kit.select(42.5)
        self.assertEqual(value, 45)
        load = units.make_load(value, "total", "lb")
        self.assertEqual(load["hevy_total"], 45)
        self.assertEqual(load["hevy_kg"], 20.4117)
        self.assertEqual(units.plate_breakdown(value, 15, [10, 5]), [10, 5])


class PhysicalKitProposalTest(ProposeCase):
    def fixed(self, exercise_id, value, session="session-a"):
        self.write_plugin("custom_kit_fixed", fixed_load_plugin("custom_kit_fixed"))
        self.set_scheme(session, exercise_id, "custom_kit_fixed", {"load": value})
        return self.propose("--dry-run")["overlay"]

    def test_nohevy_bench_requests_25_on_declared_two_point_five_grid(self):
        self.set_config("enabled = true", "enabled = false")
        data = self.propose("--dry-run")
        bench = find_line(data["overlay"], "db_bench_press")
        self.assertEqual({coaching(s["load"]) for s in working(bench)}, {25})
        self.assertIn("25/hand", next(row["text"] for row in data["lines"] if row["exercise_id"] == "db_bench_press"))
        self.assertNotIn("load_unrepresentable", codes(data["overlay"], "db_bench_press"))

    def test_explicit_scheme_increment_requests_a_step_without_defining_the_grid(self):
        self.set_scheme("session-a", "db_bench_press", "double_progression", {"increment": 2})
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {25})

    def test_historical_off_grid_load_is_not_an_anchor(self):
        self.set_config("dumbbell_increment = 2.5", "dumbbell_increment = 2.0")
        doc = self.fixed("db_bench_press", 22.5)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {22})
        self.assertNotIn("load_unrepresentable", codes(doc, "db_bench_press"))

    def test_barbell_generation_and_independent_manual_validation_share_plates(self):
        self.set_config("barbell_increment = 2.5", "barbell_increment = 10")
        self.set_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [20, 10, 5]")
        doc = self.fixed("bb_back_squat", 102.5)
        line = find_line(doc, "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {100})
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))
        for s in line["sets"]:
            s["load"] = units.make_load(102.5, "total", "kg")
        checked = validity.report(self.root, doc)
        self.assertIn("load_unrepresentable", [f["code"] for f in checked["flags"]])

    def smith(self):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["bb_back_squat"].update(
            equipment="smith_machine"))
        self.set_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [20, 10, 5]")

    def test_known_smith_base_uses_its_own_plate_geometry(self):
        self.smith()
        self.set_config("bar_weight = 20.0", "bar_weight = 20.0\nsmith_base_weight = 15")
        doc = self.fixed("bb_back_squat", 102.5)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "bb_back_squat"))}, {105})
        self.assertNotIn("load_geometry_unknown", codes(doc, "bb_back_squat"))
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))

    def test_unknown_smith_base_discloses_capability_instead_of_using_bar_weight(self):
        self.smith()
        doc = self.fixed("bb_back_squat", 102.5)
        [flag] = [f for f in doc["flags"] if f["code"] == "load_geometry_unknown"]
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("smith_base_weight", flag["message"])
        self.assertIn("ordinary bar_weight", flag["message"])

    def ladder(self, *values, extra=()):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["pull_up"].update(
            load_mode="assisted", load_mode_proposed="assisted", equipment="machine"))
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(load_mode="assisted"))
        self.set_scheme("session-b", "pull_up", "assistance_ladder",
                        {"rungs": [{"name": f"assisted {v}", "load": v} for v in values]})
        self.edit_json("data/history/2026-10.json", lambda doc: [
            (e.update(load_mode="assisted"), [s.update(load=units.make_load(22.5, "assisted", "kg")) for s in e["sets"]])
            for w in doc["workouts"] for e in w["exercises"] if e["exercise_id"] == "pull_up"])
        return self.propose("--dry-run", *extra)["overlay"]

    def test_explicit_assistance_rung_stays_exact_after_off_grid_log(self):
        doc = self.ladder(25)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {25})
        self.assertNotIn("load_unrepresentable", codes(doc, "pull_up"))

    def test_incompatible_rung_is_flagged_without_snapping(self):
        doc = self.ladder(27.5)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {27.5})
        [flag] = [f for f in doc["flags"] if f["code"] == "load_unrepresentable" and f["exercise_id"] == "pull_up"]
        self.assertIn("explicit ladder rung", flag["message"])

    def test_a_deload_below_the_lightest_rack_dumbbell_takes_the_lightest_not_the_heaviest(self):
        self.set_config("dumbbells = []", "dumbbells = [22.5, 25, 27.5]")
        doc = self.propose("--kind", "deload", "--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {22.5})
        self.assertNotIn("unearned_load", codes(doc, "db_bench_press"))

    def test_a_deload_below_the_bar_takes_the_bar_under_a_cap(self):
        self.set_config("[caps]", "[caps]\nbb_back_squat = 120")
        doc = self.fixed("bb_back_squat", 15)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "bb_back_squat"))}, {20})

    def test_no_available_rack_load_below_cap_remains_flagged(self):
        self.set_config("dumbbells = []", "dumbbells = [25, 30]")
        self.set_config("[caps]", "[caps]\ndb_bench_press = 20")
        doc = self.fixed("db_bench_press", 25)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {20})
        self.assertIn("load_unrepresentable", codes(doc, "db_bench_press"))
        self.assertNotIn("load_cap", codes(doc, "db_bench_press"))

    def test_a_cap_no_rung_fits_under_flags_the_line_and_proposes_the_rest_of_the_week(self):
        self.ladder(25)
        self.set_config("[caps]", "[caps]\npull_up = 20")
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {20})
        [flag] = [f for f in doc["flags"] if f["code"] == "constraint_applied" and f["exercise_id"] == "pull_up"]
        self.assertIn("no ladder rung", flag["message"])
        self.assertTrue(find_line(doc, "bb_back_squat")["sets"])

    def test_a_line_leaving_the_ladder_names_the_load_the_kit_makes(self):
        self.ladder(25)
        self.set_config("[caps]", "[caps]\npull_up = 22")
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {20})
        [flag] = [f for f in doc["flags"] if f["code"] == "constraint_applied" and f["exercise_id"] == "pull_up"]
        self.assertIn("leaves the ladder at BW-20 assist", flag["message"])

    def test_no_added_load_holds_the_nearest_rung_that_keeps_the_assistance(self):
        def constrained(doc):
            self.slot(doc, "session-b", "pull_up")["constraints"] = [
                {"kind": "no_added_load", "value": None, "reason": "elbow niggle"}]
        self.edit_program(constrained)
        doc = self.ladder(25, 15)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {25})
        self.assertIn("constraint_applied", codes(doc, "pull_up"))
        self.assertNotIn("load_unrepresentable", codes(doc, "pull_up"))

    def test_a_ladder_deload_rounds_its_off_rung_assistance_up_to_the_kit(self):
        doc = self.ladder(25, 15, extra=("--kind", "deload"))
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {25})
        self.assertNotIn("load_unrepresentable", codes(doc, "pull_up"))

    def test_rationale_names_the_load_the_kit_makes(self):
        self.set_scheme("session-a", "db_bench_press", "double_progression", {"increment": 2})
        data = self.propose("--dry-run")
        rationale = find_line(data["overlay"], "db_bench_press")["provenance"]["rationale"]
        self.assertIn("24.5/hand", rationale)
        self.assertIn("the kit makes 25/hand", rationale)

    def test_custom_kettlebell_takes_the_kettlebell_step_not_the_declared_dumbbell_step(self):
        entry = library.custom_entry("F00000KB", "Bottoms-Up Press (Kettlebell)",
                                     {"equipment": "kettlebell", "primary_muscle_group": "shoulders"},
                                     "single_implement")
        entry.update(load_mode="single_implement", load_mode_proposed="single_implement", confidence="high",
                     avoid=None)
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"].update(custom_bottoms_up_press=entry))
        step = stats.load_increment(Library.load(self.root), config.load(self.root), "custom_bottoms_up_press", None)
        self.assertEqual(step, 4)
        kit = loads.AvailableLoads("kettlebell", "single_implement", {}, step)
        self.assertIsNone(kit.problem(16))
        self.assertIsNone(kit.problem(24))

    def test_trap_bar_generation_and_validation_use_the_declared_bar_mass(self):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["bb_back_squat"].update(
            equipment="trap_bar"))
        self.set_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [20, 10, 5]")
        self.set_config("bar_weight = 20.0", "bar_weight = 20.0\ntrap_bar_weight = 27")
        doc = self.fixed("bb_back_squat", 87)
        line = find_line(doc, "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {87})
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))
        self.assertNotIn("load_geometry_unknown", codes(doc, "bb_back_squat"))
        for s in line["sets"]:
            s["load"] = units.make_load(87.5, "total", "kg")
        checked = validity.report(self.root, doc)
        self.assertIn("load_unrepresentable", [f["code"] for f in checked["flags"]])

    def test_unknown_trap_bar_mass_discloses_capability_and_leaves_the_load(self):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["bb_back_squat"].update(
            equipment="trap_bar"))
        doc = self.fixed("bb_back_squat", 87)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "bb_back_squat"))}, {87})
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))
        [flag] = [f for f in doc["flags"] if f["code"] == "load_geometry_unknown"]
        self.assertIn("trap_bar_weight", flag["message"])

    def test_location_smith_base_overrides_main_geometry(self):
        self.smith()
        self.set_config("bar_weight = 20.0", "bar_weight = 20.0\nsmith_base_weight = 15")
        self.set_config("[equipment.locations.home]", "[equipment.locations.home]\nsmith_base_weight = 10")
        self.edit_program(lambda doc: doc["sessions"][0].update(location="home"))
        doc = self.fixed("bb_back_squat", 102.5)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "bb_back_squat"))}, {100})
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))

    def test_no_added_load_rounds_assistance_up_to_the_physical_grid(self):
        self.ladder(25)
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(
            constraints=[{"kind": "no_added_load", "value": None, "reason": "hold effort"}]))
        doc = self.fixed("pull_up", 20, session="session-b")
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {25})
        self.assertNotIn("load_unrepresentable", codes(doc, "pull_up"))


class HeldLoadOnCoarseKitTest(ProposeCase):
    workouts = staticmethod(edit_sets(SQUAT, lambda wid, i, s: s.update(weight_kg=97.5, rpe=9)))

    def test_a_held_load_off_the_kit_rounds_to_the_lighter_lift_and_says_so(self):
        self.set_config("barbell_increment = 2.5", "barbell_increment = 10")
        self.set_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [20, 10, 5]")
        doc = self.propose("--dry-run")["overlay"]
        squat = find_line(doc, "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(squat)}, {90})
        self.assertIn("97.5 holds", squat["provenance"]["rationale"])
        self.assertIn("the kit makes 90", squat["provenance"]["rationale"])
        self.assertNotIn("load_unrepresentable", codes(doc, "bb_back_squat"))
