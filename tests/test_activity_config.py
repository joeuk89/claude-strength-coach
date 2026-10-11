import tomllib
import unittest

from coach import config
from coach.errors import ConfigError
from tests.support import MINIMAL_CONFIG, REPO_ROOT

ENABLED = MINIMAL_CONFIG + "\n[activity]\nenabled = true\n"


def load_text(text):
    return config.parse(tomllib.loads(text), "config.toml")


def config_error(text):
    try:
        load_text(text)
    except ConfigError as exc:
        return exc
    raise AssertionError("expected a ConfigError")


class ActivityConfigTest(unittest.TestCase):
    def test_defaults(self):
        cfg = load_text(MINIMAL_CONFIG)
        self.assertFalse(cfg.activity.enabled)
        self.assertFalse(cfg.activity.wellness_in_git)
        self.assertEqual(cfg.activity.dedup_window_minutes, 15)
        self.assertEqual(cfg.activity.precedence, ["manual", "apple_health", "hevy_conditioning"])
        self.assertEqual(cfg.activity.gap_warn_days, 3)
        self.assertTrue(cfg.sources.hevy_conditioning.enabled)

    def test_precedence_must_list_every_enabled_source(self):
        exc = config_error(ENABLED + 'precedence = ["manual"]\n')
        self.assertEqual(exc.exit_code, 5)
        self.assertIn("[activity] precedence", exc.message)
        self.assertIn("hevy_conditioning", exc.message)

    def test_precedence_must_list_manual(self):
        exc = config_error(ENABLED + 'precedence = ["hevy_conditioning"]\n')
        self.assertIn("manual", exc.message)

    def test_precedence_must_not_repeat(self):
        exc = config_error(ENABLED + 'precedence = ["manual", "hevy_conditioning", "manual"]\n')
        self.assertIn("[activity] precedence", exc.message)
        self.assertIn("repeat", exc.message)

    def test_disabled_source_may_be_left_out(self):
        cfg = load_text(ENABLED + 'precedence = ["manual"]\n\n[sources.hevy_conditioning]\nenabled = false\n')
        self.assertEqual(cfg.activity.precedence, ["manual"])

    def test_hevy_off_turns_the_hevy_source_off(self):
        text = MINIMAL_CONFIG + '\n[hevy]\nenabled = false\n\n[activity]\nenabled = true\nprecedence = ["manual"]\n'
        self.assertEqual(load_text(text).activity.precedence, ["manual"])

    def test_precedence_is_not_checked_while_activity_is_off(self):
        cfg = load_text(MINIMAL_CONFIG + '\n[activity]\nprecedence = ["manual"]\n')
        self.assertFalse(cfg.activity.enabled)

    def test_unknown_source_key_is_named(self):
        exc = config_error(ENABLED + "\n[sources.hevy_conditioning]\nenabled = true\nfolder = 3\n")
        self.assertIn("folder", exc.message)
        self.assertIn("sources.hevy_conditioning", exc.message)

    def test_unknown_source_table_is_named(self):
        exc = config_error(ENABLED + "\n[sources.strava]\nenabled = true\n")
        self.assertIn("sources.strava", exc.message)

    def test_window_and_gap_must_be_sensible(self):
        self.assertIn("dedup_window_minutes", config_error(ENABLED + "dedup_window_minutes = -1\n").message)
        self.assertIn("gap_warn_days", config_error(ENABLED + "gap_warn_days = 0\n").message)


class ExampleTest(unittest.TestCase):
    def test_example_has_every_activity_key(self):
        raw = tomllib.loads((REPO_ROOT / "config.example.toml").read_text(encoding="utf-8"))
        tables = config.registered_tables()
        self.assertEqual(set(raw["activity"]), set(tables["activity"].keys))
        self.assertEqual(set(raw["sources"]), set(tables["sources"].tables))
        for name, table in tables["sources"].tables.items():
            with self.subTest(source=name):
                self.assertEqual(set(raw["sources"][name]), set(table.keys))
        self.assertFalse(raw["activity"]["enabled"])
        self.assertFalse(raw["sources"]["apple_health"]["enabled"])


if __name__ == "__main__":
    unittest.main()
