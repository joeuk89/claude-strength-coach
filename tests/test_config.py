import re
import tomllib
import unittest

from coach import config
from coach.config import equipment_for
from coach.errors import ConfigError
from tests.support import MINIMAL_CONFIG, REPO_ROOT, VALID, TempInstance

EXAMPLE = REPO_ROOT / "config.example.toml"


def load_text(text):
    with TempInstance(text) as root:
        return config.load(root)


def config_error(text):
    with TempInstance(text) as root:
        try:
            config.load(root)
        except ConfigError as exc:
            return exc
    raise AssertionError("expected a ConfigError")


class LoadTest(unittest.TestCase):
    def test_valid_fixture(self):
        cfg = config.load(VALID)
        self.assertEqual(cfg.athlete.units, "kg")
        self.assertEqual(cfg.athlete.week_starts, "monday")
        self.assertIs(cfg.hevy.enabled, True)
        self.assertEqual(cfg["equipment"]["bar_weight"], 20.0)
        self.assertEqual(cfg.path, VALID / "config.toml")

    def test_missing_file_names_the_example(self):
        with TempInstance() as root:
            with self.assertRaises(ConfigError) as caught:
                config.load(root)
        self.assertIn("config.example.toml", caught.exception.message)
        self.assertEqual(caught.exception.exit_code, 5)

    def test_bad_toml(self):
        exc = config_error("schema_version = \n")
        self.assertIn("not valid TOML", exc.message)

    def test_minimal_config_takes_defaults(self):
        cfg = load_text(MINIMAL_CONFIG)
        self.assertEqual(cfg.athlete.bodyweight_units, "kg")
        self.assertEqual(cfg.athlete.experience, "intermediate")
        self.assertEqual(cfg.athlete.available_days, [])
        self.assertEqual(cfg.athlete.session_minutes, 60)
        self.assertEqual(cfg.equipment.plates, [25, 20, 15, 10, 5, 2.5, 1.25])
        self.assertEqual(cfg.equipment.locations, {})
        self.assertEqual(cfg.caps, {})

    def test_lb_needs_its_equipment_numbers(self):
        exc = config_error('schema_version = 1\n[athlete]\nunits = "lb"\n')
        self.assertIn("bar_weight", " ".join(d["message"] for d in exc.details))
        self.assertIn('units = "lb"', exc.message)

    def test_units_required(self):
        exc = config_error("schema_version = 1\n")
        self.assertIn("[athlete] units is required", exc.message)

    def test_newer_schema_version(self):
        exc = config_error('schema_version = 2\n[athlete]\nunits = "kg"\n')
        self.assertIn("/framework-sync", exc.message)


class StrictnessTest(unittest.TestCase):
    def assert_names(self, text, *fragments):
        exc = config_error(text)
        for fragment in ("config.toml",) + fragments:
            self.assertIn(fragment, exc.message)
        return exc

    def test_unknown_key(self):
        self.assert_names(MINIMAL_CONFIG + 'week_start = "monday"\n', '"week_start"', "[athlete]")

    def test_unknown_table_and_top_level_key(self):
        self.assert_names(MINIMAL_CONFIG + "[sessions]\n", "[sessions]")
        self.assert_names("colour = 1\n" + MINIMAL_CONFIG, '"colour"')

    def test_type_errors_name_the_expected_type(self):
        self.assert_names(MINIMAL_CONFIG + "[equipment]\ndumbbell_max = \"40\"\n", "dumbbell_max", "a number")
        self.assert_names(MINIMAL_CONFIG + "session_minutes = 45.5\n", "session_minutes", "whole number")
        self.assert_names(MINIMAL_CONFIG + "[hevy]\nenabled = \"yes\"\n", "enabled", "true or false")

    def test_experience_enum(self):
        self.assert_names(MINIMAL_CONFIG + 'experience = "expert"\n', "experience", '"expert"')

    def test_available_days_ids(self):
        self.assert_names(MINIMAL_CONFIG + 'available_days = ["monday"]\n', "available_days", '"monday"')
        self.assert_names(MINIMAL_CONFIG + 'available_days = ["mon", "mon"]\n', "available_days", "repeat")

    def test_session_minutes_not_negative(self):
        self.assert_names(MINIMAL_CONFIG + "session_minutes = -5\n", "session_minutes")

    def test_available_is_distinct_strings(self):
        self.assert_names(MINIMAL_CONFIG + '[equipment]\navailable = ["bench", "bench"]\n', "available", "repeat")
        self.assert_names(MINIMAL_CONFIG + "[equipment]\navailable = [1]\n", "available", "string")

    def test_timezone(self):
        self.assert_names(MINIMAL_CONFIG + 'timezone = "Mars/Olympus"\n', "timezone", "Mars/Olympus")
        self.assertEqual(load_text(MINIMAL_CONFIG + 'timezone = "Europe/London"\n').athlete.timezone, "Europe/London")

    def test_caps_keys_are_exercise_ids(self):
        cfg = load_text(MINIMAL_CONFIG + "[caps]\ndb_bench_press = 30.0\n")
        self.assertEqual(cfg.caps, {"db_bench_press": 30.0})
        self.assert_names(MINIMAL_CONFIG + '[caps]\n"DB Bench" = 30.0\n', "DB Bench")
        self.assert_names(MINIMAL_CONFIG + "[caps]\ndb_bench_press = 0\n", "db_bench_press")

    def test_location_unknown_key_names_table_and_key(self):
        text = MINIMAL_CONFIG + "[equipment.locations.home]\ndumbells = [5, 10]\n"
        self.assert_names(text, "[equipment.locations.home]", '"dumbells"')

    def test_location_name_pattern(self):
        text = MINIMAL_CONFIG + '[equipment.locations."Home Gym"]\ndumbbell_max = 20.0\n'
        self.assert_names(text, '"Home Gym"')

    def test_location_values_checked(self):
        text = MINIMAL_CONFIG + '[equipment.locations.home]\ndumbbell_max = "heavy"\n'
        self.assert_names(text, "dumbbell_max", "[equipment.locations.home]")

    def test_every_problem_is_in_details(self):
        exc = config_error(MINIMAL_CONFIG + 'experience = "expert"\nweek_start = "monday"\n')
        self.assertEqual(len(exc.details), 2)
        self.assertIn("1 more", exc.message)


class EquipmentForTest(unittest.TestCase):
    TEXT = MINIMAL_CONFIG + (
        "[equipment]\ndumbbell_max = 40.0\ndumbbells = [10, 20, 30, 40]\n"
        "[equipment.locations.home]\ndumbbells = [5, 10]\ndumbbell_max = 20.0\n"
    )

    def test_main_table_unchanged(self):
        cfg = load_text(self.TEXT)
        main = equipment_for(cfg)
        self.assertEqual(main["dumbbells"], [10, 20, 30, 40])
        self.assertEqual(main["dumbbell_max"], 40.0)
        self.assertNotIn("locations", main)
        self.assertEqual(main, {k: v for k, v in cfg.equipment.items() if k != "locations"})

    def test_location_laid_over_main(self):
        cfg = load_text(self.TEXT)
        main = equipment_for(cfg)
        home = equipment_for(cfg, "home")
        self.assertEqual(home["dumbbells"], [5, 10])
        self.assertEqual(home["dumbbell_max"], 20.0)
        for key in main:
            if key not in ("dumbbells", "dumbbell_max"):
                self.assertEqual(home[key], main[key], key)
        self.assertEqual(set(home), set(main))

    def test_does_not_mutate_config(self):
        cfg = load_text(self.TEXT)
        equipment_for(cfg, "home")
        self.assertEqual(cfg.equipment.dumbbells, [10, 20, 30, 40])

    def test_unknown_location(self):
        cfg = load_text(self.TEXT)
        with self.assertRaises(ConfigError) as caught:
            equipment_for(cfg, "hotel")
        self.assertIn("hotel", caught.exception.message)
        self.assertEqual(caught.exception.exit_code, 5)


class ExampleTest(unittest.TestCase):
    def test_example_validates(self):
        config.parse_file(EXAMPLE)

    def test_example_has_every_key(self):
        raw = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
        tables = config.registered_tables()
        for name in ("athlete", "hevy", "equipment"):
            for key in tables[name].keys:
                with self.subTest(table=name, key=key):
                    self.assertIn(key, raw[name])
        for key in ("experience", "available_days", "session_minutes"):
            self.assertIn(key, raw["athlete"])
        for key in ("available", "dumbbells"):
            self.assertIn(key, raw["equipment"])

    def test_commented_location_example_validates(self):
        text = EXAMPLE.read_text(encoding="utf-8")
        block = re.search(r"^# \[equipment\.locations\.[a-z0-9-]+\]\n(?:# .*\n)+", text, re.M)
        self.assertIsNotNone(block, "config.example.toml needs a commented [equipment.locations.<name>] example")
        uncommented = "\n".join(line[2:] for line in block.group(0).splitlines())
        cfg = load_text(MINIMAL_CONFIG + uncommented + "\n")
        self.assertEqual(len(cfg.equipment.locations), 1)


if __name__ == "__main__":
    unittest.main()
