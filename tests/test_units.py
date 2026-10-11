import unittest

from coach import units
from coach.units import (
    LOAD_MODES,
    check_load,
    format_load,
    from_hevy_kg,
    make_load,
    plate_breakdown,
    round_to_increment,
    to_hevy_kg,
)


class LoadModesTest(unittest.TestCase):
    def test_enum_matches_contract(self):
        self.assertEqual(
            LOAD_MODES,
            ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band", "duration", "distance"),
        )


class MakeLoadTest(unittest.TestCase):
    CASES = [
        # mode, value, unit, per_hand, hevy_total, hevy_kg, text
        ("total", 80, "kg", None, 80, 80, "80"),
        ("total", 135, "lb", None, 135, 61.235, "135"),
        ("per_hand_x2", 25, "kg", 25, 50, 50, "25/hand (Hevy: 50)"),
        ("per_hand_x2", 25, "lb", 25, 50, 22.6796, "25/hand (Hevy: 50)"),
        ("per_hand_x2", 22.5, "kg", 22.5, 45, 45, "22.5/hand (Hevy: 45)"),
        ("single_implement", 25, "kg", 25, 25, 25, "25 (Hevy: 25)"),
        ("single_implement", 30, "lb", 30, 30, 13.6078, "30 (Hevy: 30)"),
        ("bodyweight", 0, "kg", None, 0, 0, "BW"),
        ("bodyweight", 10, "kg", None, 10, 10, "BW+10"),
        ("bodyweight", 0, "lb", None, 0, 0, "BW"),
        ("bodyweight", 25, "lb", None, 25, 11.3398, "BW+25"),
        ("assisted", 20, "kg", None, 20, 20, "BW-20 assist (Hevy: 20)"),
        ("assisted", 40, "lb", None, 40, 18.1437, "BW-40 assist (Hevy: 40)"),
    ]

    def test_every_loaded_mode_in_both_units(self):
        for mode, value, unit, per_hand, hevy_total, hevy_kg, text in self.CASES:
            with self.subTest(mode=mode, unit=unit, value=value):
                load = make_load(value, mode, unit)
                self.assertEqual(
                    load,
                    {"mode": mode, "unit": unit, "per_hand": per_hand, "hevy_total": hevy_total, "hevy_kg": hevy_kg},
                )
                self.assertEqual(check_load(load), [])
                self.assertEqual(format_load(load), text)

    def test_loaded_modes_cover_both_units(self):
        covered = {(mode, unit) for mode, _, unit, *_ in self.CASES}
        for mode in ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted"):
            for unit in ("kg", "lb"):
                self.assertIn((mode, unit), covered)

    def test_unloaded_modes_return_none(self):
        for mode in ("band", "duration", "distance"):
            for unit in ("kg", "lb"):
                with self.subTest(mode=mode, unit=unit):
                    self.assertIsNone(make_load(10, mode, unit))

    def test_integral_values_are_ints(self):
        load = make_load(25.0, "per_hand_x2", "kg")
        self.assertIsInstance(load["per_hand"], int)
        self.assertIsInstance(load["hevy_total"], int)
        self.assertIsInstance(load["hevy_kg"], int)

    def test_rejects_bad_input(self):
        for args in [(-5, "total", "kg"), (10, "kettlebell", "kg"), (10, "total", "stone"), (True, "total", "kg"),
                     ("10", "total", "kg"), (float("nan"), "total", "kg")]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    make_load(*args)


class CheckLoadTest(unittest.TestCase):
    def test_rejects_hevy_total_not_twice_per_hand(self):
        load = {"mode": "per_hand_x2", "unit": "kg", "per_hand": 25, "hevy_total": 25, "hevy_kg": 25}
        errors = check_load(load)
        self.assertTrue(any("hevy_total" in e and "expected 50" in e for e in errors), errors)

    def test_rejects_wrong_hevy_kg(self):
        load = {"mode": "per_hand_x2", "unit": "lb", "per_hand": 25, "hevy_total": 50, "hevy_kg": 45.3592}
        self.assertEqual(check_load(load), ["hevy_kg: expected 22.6796, found 45.3592"])

    def test_rejects_single_implement_mismatch(self):
        load = {"mode": "single_implement", "unit": "kg", "per_hand": 25, "hevy_total": 50, "hevy_kg": 50}
        self.assertTrue(check_load(load))

    def test_rejects_per_hand_on_total(self):
        load = {"mode": "total", "unit": "kg", "per_hand": 40, "hevy_total": 80, "hevy_kg": 80}
        self.assertTrue(check_load(load))

    def test_rejects_unknown_mode_unit_and_keys(self):
        self.assertTrue(check_load({"mode": "x", "unit": "kg", "per_hand": None, "hevy_total": 1, "hevy_kg": 1}))
        self.assertTrue(check_load({"mode": "total", "unit": "st", "per_hand": None, "hevy_total": 1, "hevy_kg": 1}))
        self.assertTrue(check_load({"mode": "total", "unit": "kg", "hevy_total": 1, "hevy_kg": 1}))
        self.assertTrue(check_load({"mode": "band", "unit": "kg", "per_hand": None, "hevy_total": 1, "hevy_kg": 1}))
        self.assertTrue(check_load("80"))


class ConvertTest(unittest.TestCase):
    def test_to_hevy_kg(self):
        self.assertEqual(to_hevy_kg(25, "per_hand_x2", "kg"), 50)
        self.assertEqual(to_hevy_kg(25, "per_hand_x2", "lb"), 22.6796)
        self.assertEqual(to_hevy_kg(25, "single_implement", "lb"), 11.3398)
        self.assertEqual(to_hevy_kg(100, "total", "kg"), 100)

    def test_from_hevy_kg(self):
        self.assertEqual(from_hevy_kg(50, "per_hand_x2", "kg"), 25)
        self.assertEqual(from_hevy_kg(22.6796, "per_hand_x2", "lb"), 25)
        self.assertEqual(from_hevy_kg(11.3398, "single_implement", "lb"), 25)
        self.assertEqual(from_hevy_kg(45, "per_hand_x2", "kg"), 22.5)
        self.assertEqual(from_hevy_kg(61.235, "total", "lb"), 135)

    def test_round_trip(self):
        for mode in ("total", "per_hand_x2", "single_implement", "bodyweight", "assisted"):
            for unit in ("kg", "lb"):
                for value in (0, 1.25, 2.5, 12.5, 22.5, 25, 47.5, 100, 142.5):
                    with self.subTest(mode=mode, unit=unit, value=value):
                        self.assertEqual(from_hevy_kg(to_hevy_kg(value, mode, unit), mode, unit), value)

    def test_unloaded_modes_raise(self):
        with self.assertRaises(ValueError):
            to_hevy_kg(10, "band", "kg")
        with self.assertRaises(ValueError):
            from_hevy_kg(10, "duration", "kg")


class FormatTest(unittest.TestCase):
    def test_two_decimals_and_trailing_zeros(self):
        self.assertEqual(format_load(make_load(22.5, "total", "kg")), "22.5")
        self.assertEqual(format_load(make_load(1.25, "total", "kg")), "1.25")
        self.assertEqual(format_load(make_load(25.0, "total", "kg")), "25")
        self.assertEqual(format_load(make_load(1.125, "single_implement", "kg")), "1.13 (Hevy: 1.13)")

    def test_none_raises(self):
        with self.assertRaises(ValueError):
            format_load(None)


class RoundTest(unittest.TestCase):
    def test_directions(self):
        self.assertEqual(round_to_increment(23.7, 2.5), 22.5)
        self.assertEqual(round_to_increment(23.75, 2.5), 25)
        self.assertEqual(round_to_increment(23.7, 2.5, "up"), 25)
        self.assertEqual(round_to_increment(24.9, 2.5, "down"), 22.5)
        self.assertEqual(round_to_increment(25, 2.5, "down"), 25)
        self.assertEqual(round_to_increment(25, 2.5, "up"), 25)
        self.assertEqual(round_to_increment(0.3, 0.1, "up"), 0.3)

    def test_rejects_bad_increment_and_direction(self):
        with self.assertRaises(ValueError):
            round_to_increment(10, 0)
        with self.assertRaises(ValueError):
            round_to_increment(10, 2.5, "sideways")


class PlateTest(unittest.TestCase):
    KG = [25, 20, 15, 10, 5, 2.5, 1.25]

    def test_breakdown(self):
        self.assertEqual(plate_breakdown(100, 20, self.KG), [25, 15])
        self.assertEqual(plate_breakdown(20, 20, self.KG), [])
        self.assertEqual(plate_breakdown(102.5, 20, self.KG), [25, 15, 1.25])
        self.assertEqual(plate_breakdown(180, 20, self.KG), [25, 25, 25, 5])

    def test_unrepresentable(self):
        self.assertIsNone(plate_breakdown(101, 20, self.KG))
        self.assertIsNone(plate_breakdown(15, 20, self.KG))
        self.assertIsNone(plate_breakdown(100, 20, []))

    def test_fewest_plates_not_greedy(self):
        self.assertEqual(plate_breakdown(60, 20, [15, 10]), [10, 10])


class DistanceTest(unittest.TestCase):
    def test_to_meters(self):
        self.assertEqual(units.to_meters(5, "km"), 5000)
        self.assertEqual(units.to_meters(1, "mi"), 1609.344)
        self.assertEqual(units.to_meters(100, "ft"), 30.48)
        self.assertEqual(units.to_meters(400, "m"), 400)

    def test_from_meters(self):
        self.assertEqual(units.from_meters(5000, "km"), 5)
        self.assertEqual(units.from_meters(1609.344, "mi"), 1)
        self.assertEqual(units.from_meters(30.48, "ft"), 100)

    def test_rejects_bad_input(self):
        for value, unit in ((5, "yd"), (-1, "km"), (True, "km"), ("5", "km")):
            with self.subTest(value=value, unit=unit), self.assertRaises(ValueError):
                units.to_meters(value, unit)


class JsonNumberTest(unittest.TestCase):
    def test_normalises(self):
        self.assertIsInstance(units.json_number(25.0), int)
        self.assertEqual(units.json_number(22.5), 22.5)
        self.assertEqual(units.json_number(-0.0), 0)


if __name__ == "__main__":
    unittest.main()
