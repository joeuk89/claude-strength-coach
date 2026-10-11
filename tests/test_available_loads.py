"""Physical equipment facts constrain requested progression steps in athlete units."""

import unittest

from coach import config, loads, stats, units
from coach.library import Library
from tests.support import VALID
from tests.test_propose import ProposeCase, coaching, codes, find_line, working
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
        cfg = config.load(VALID)
        library = Library.load(VALID)
        cfg.equipment["dumbbell_increment"] = 2.5
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", None), 2.5)
        cfg.equipment.locations.home["dumbbell_increment"] = 5
        cfg.declared_equipment["locations"]["home"]["dumbbell_increment"] = 5
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", "home"), 5)
        cfg.declared_equipment.pop("dumbbell_increment")
        self.assertEqual(stats.load_increment(library, cfg, "db_bench_press", None), 2)

    def test_smith_base_is_optional_nonnegative_and_location_specific(self):
        raw = {"schema_version": 1, "athlete": {"units": "kg"},
               "equipment": {"smith_base_weight": 15, "locations": {"home": {"smith_base_weight": 7}}}}
        cfg = config.parse(raw, "config.toml")
        self.assertEqual(config.equipment_for(cfg)["smith_base_weight"], 15)
        self.assertEqual(config.equipment_for(cfg, "home")["smith_base_weight"], 7)
        raw["equipment"]["smith_base_weight"] = -1
        with self.assertRaises(config.ConfigError):
            config.parse(raw, "config.toml")

    def test_machine_cable_and_other_bar_grids_are_checked(self):
        for equipment in ("machine", "cable", "ez_bar", "trap_bar", "kettlebell"):
            with self.subTest(equipment=equipment):
                kit = loads.AvailableLoads(equipment, "total", {}, 5)
                self.assertIsNotNone(kit.problem(22.5))
                self.assertEqual(kit.select(22.5), 25)
                self.assertIsNone(kit.problem(25))

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
        from coach import validity
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

    def ladder(self, value):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["pull_up"].update(
            load_mode="assisted", load_mode_proposed="assisted", equipment="machine"))
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(load_mode="assisted"))
        self.set_scheme("session-b", "pull_up", "assistance_ladder", {"rungs": [{"name": "assisted", "load": value}]})
        self.edit_json("data/history/2026-10.json", lambda doc: [
            (e.update(load_mode="assisted"), [s.update(load=units.make_load(22.5, "assisted", "kg")) for s in e["sets"]])
            for w in doc["workouts"] for e in w["exercises"] if e["exercise_id"] == "pull_up"])
        return self.propose("--dry-run")["overlay"]

    def test_explicit_assistance_rung_stays_exact_after_off_grid_log(self):
        doc = self.ladder(25)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {25})
        self.assertNotIn("load_unrepresentable", codes(doc, "pull_up"))

    def test_incompatible_rung_is_flagged_without_snapping(self):
        doc = self.ladder(27.5)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {27.5})
        [flag] = [f for f in doc["flags"] if f["code"] == "load_unrepresentable" and f["exercise_id"] == "pull_up"]
        self.assertIn("explicit ladder rung", flag["message"])

    def test_no_available_rack_load_below_cap_remains_flagged(self):
        self.set_config("dumbbells = []", "dumbbells = [25, 30]")
        self.set_config("[caps]", "[caps]\ndb_bench_press = 20")
        doc = self.fixed("db_bench_press", 25)
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {20})
        self.assertIn("load_unrepresentable", codes(doc, "db_bench_press"))
        self.assertNotIn("load_cap", codes(doc, "db_bench_press"))

    def test_ladder_cap_conflict_refuses_instead_of_changing_the_rung(self):
        self.ladder(25)
        self.set_config("[caps]", "[caps]\npull_up = 20")
        result = self.propose("--dry-run", expect=1)
        self.assertIn("explicit ladder rung conflicts", result["error"]["message"])

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
