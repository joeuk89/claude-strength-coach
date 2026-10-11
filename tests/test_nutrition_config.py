"""The [nutrition] keys R-33a owns (contract C4)."""

import re
import tomllib
import unittest
from datetime import date

from coach import config
from coach import nutrition
from coach.config import parse
from coach.errors import ConfigError
from tests.support import MINIMAL_CONFIG, REPO_ROOT, VALID, TempInstance, run_cli, run_module

VALID_TEXT = (VALID / "config.toml").read_text(encoding="utf-8")


def parse_text(text):
    return parse(tomllib.loads(text), "config.toml")


def error_for(text):
    try:
        parse_text(text)
    except ConfigError as exc:
        return exc
    raise AssertionError("expected a ConfigError")


def replaced(old, new, text=VALID_TEXT):
    assert old in text, old
    return text.replace(old, new, 1)


def detail_paths(exc):
    return [detail["path"] for detail in exc.details]


OVERRIDE = """
[nutrition.override]
start = 2026-10-11
expires = 2026-11-01
what = "app protein target held at 120"
reason = "travel week"
exit_condition = "back home"
renewal = 0
"""


class ValidFixtureTest(unittest.TestCase):
    def test_valid_fixture_reads_the_c14_table(self):
        cfg = config.load(VALID)
        self.assertIs(cfg.nutrition.enabled, True)
        self.assertEqual(cfg.nutrition.app, "macrofactor")
        self.assertEqual(cfg.nutrition.phase, "recomp")
        protein = cfg.nutrition.protein
        self.assertEqual((protein.reference_mass, protein.floor_g, protein.target_g, protein.stretch_g),
                         (80.0, 110, 128, 176))
        self.assertEqual(protein.floor_since, date(2026, 9, 28))
        self.assertEqual(cfg.nutrition.anchors[0].name, "Whey shake")
        self.assertEqual(cfg.nutrition.anchors[0].protein_g, 30)
        self.assertNotIn("override", cfg.nutrition)

    def test_config_validate_on_the_valid_fixture_as_a_subprocess(self):
        code, envelope, stderr = run_module(["--root", "tests/fixtures/instances/valid", "config", "validate"])
        self.assertEqual(code, 0, stderr)
        self.assertIs(envelope["data"]["valid"], True)

    def test_floor_step_defaults_to_ten(self):
        cfg = parse_text(replaced("floor_step_g = 10\n", ""))
        self.assertEqual(cfg.nutrition.protein.floor_step_g, 10)


class StrictTest(unittest.TestCase):
    def assert_config_exit(self, text, fragment, path=None):
        with TempInstance(text) as root:
            code, envelope, stderr = run_cli(["--root", str(root), "config", "validate"])
        self.assertEqual(code, 5, envelope)
        self.assertIn(fragment, envelope["error"]["message"])
        if path:
            self.assertIn(path, [d["path"] for d in envelope["error"]["details"]])

    def test_kcal_target_with_an_app_is_an_error(self):
        text = replaced("target_rate_per_week = 0.0\n", "target_rate_per_week = 0.0\nkcal_target = 2400\n")
        self.assert_config_exit(text, "kcal_target", "nutrition.kcal_target")

    def test_kcal_target_without_an_app_is_fine(self):
        text = replaced('app = "macrofactor"', 'app = "none"')
        text = replaced("target_rate_per_week = 0.0\n", "target_rate_per_week = 0.0\nkcal_target = 2400\n", text)
        self.assertEqual(parse_text(text).nutrition.kcal_target, 2400)

    def test_misspelt_protein_key(self):
        self.assert_config_exit(replaced("floor_g = 110", "flor_g = 110"), "flor_g", "nutrition.protein.flor_g")

    def test_override_longer_than_21_days(self):
        text = VALID_TEXT + OVERRIDE.replace("expires = 2026-11-01", "expires = 2026-11-02")
        self.assert_config_exit(text, "21 days", "nutrition.override.expires")

    def test_override_of_21_days_is_fine(self):
        cfg = parse_text(VALID_TEXT + OVERRIDE)
        self.assertEqual(cfg.nutrition.override.expires, date(2026, 11, 1))
        self.assertEqual(cfg.nutrition.override.renewal, 0)

    def test_override_must_end_after_it_starts(self):
        exc = error_for(VALID_TEXT + OVERRIDE.replace("expires = 2026-11-01", "expires = 2026-10-11"))
        self.assertIn("nutrition.override.expires", detail_paths(exc))

    def test_protein_numbers_must_be_in_order(self):
        for old, new in (("floor_g = 110", "floor_g = 130"), ("stretch_g = 176", "stretch_g = 120")):
            with self.subTest(change=new):
                exc = error_for(replaced(old, new))
                self.assertIn("floor_g", exc.message)
                self.assertIn("stretch_g", exc.message)

    def test_enums(self):
        for old, new, fragment in (('app = "macrofactor"', 'app = "cronometer"', "app"),
                                   ('phase = "recomp"', 'phase = "shred"', "phase"),
                                   ('reference_basis = "bodyweight"', 'reference_basis = "lean"', "reference_basis"),
                                   ('days = ["daily"]', 'days = ["weekends"]', "days")):
            with self.subTest(key=fragment):
                self.assertIn(fragment, error_for(replaced(old, new)).message)

    def test_anchor_unknown_key_and_missing_key(self):
        exc = error_for(replaced('name = "Whey shake"', 'nmae = "Whey shake"'))
        self.assertIn('"nmae"', " ".join(d["message"] for d in exc.details))
        self.assertIn("nutrition.anchors[0].name", detail_paths(exc))

    def test_anchors_must_be_tables(self):
        exc = error_for(MINIMAL_CONFIG + '[nutrition]\nenabled = false\nanchors = ["Whey shake"]\n')
        self.assertIn("nutrition.anchors", detail_paths(exc))

    def test_renewal_is_zero_one_or_two(self):
        exc = error_for(VALID_TEXT + OVERRIDE.replace("renewal = 0", "renewal = 3"))
        self.assertIn("renewal", exc.message)

    def test_enabled_needs_the_strategy_keys(self):
        exc = error_for(MINIMAL_CONFIG + "[nutrition]\nenabled = true\n")
        paths = detail_paths(exc)
        for key in ("nutrition.app", "nutrition.phase", "nutrition.target_rate_per_week", "nutrition.protein"):
            self.assertIn(key, paths)

    def test_strategy_keys_without_enabled_is_an_error(self):
        exc = error_for(replaced("[nutrition]\nenabled = true\n", "[nutrition]\n"))
        self.assertIn("nutrition.enabled", detail_paths(exc))


class DisabledTest(unittest.TestCase):
    def test_absent_table_is_disabled(self):
        self.assertFalse(nutrition.enabled(parse_text(MINIMAL_CONFIG)))

    def test_bank_only_table_is_disabled_and_valid(self):
        cfg = parse_text(MINIMAL_CONFIG + "[nutrition.bank]\nmacro_sum_warn_pct = 12\n")
        self.assertFalse(nutrition.enabled(cfg))

    def test_enabled_false_keeps_the_numbers_but_switches_off(self):
        cfg = parse_text(replaced("[nutrition]\nenabled = true", "[nutrition]\nenabled = false"))
        self.assertFalse(nutrition.enabled(cfg))
        self.assertEqual(cfg.nutrition.protein.floor_g, 110)

    def test_enabled_false_alone_is_valid(self):
        self.assertFalse(nutrition.enabled(parse_text(MINIMAL_CONFIG + "[nutrition]\nenabled = false\n")))


class ExampleTest(unittest.TestCase):
    def test_commented_nutrition_example_validates_and_matches_c14(self):
        text = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        block = re.search(r"^# \[nutrition\]\n(?:#.*\n)+", text, re.M)
        self.assertIsNotNone(block, "config.example.toml needs a commented [nutrition] example")
        lines = [line[2:] for line in block.group(0).splitlines() if line.startswith("# ")]
        cfg = parse_text(MINIMAL_CONFIG + "\n".join(lines) + "\n")
        self.assertTrue(nutrition.enabled(cfg))
        self.assertEqual(cfg.nutrition.protein.floor_g, 110)
        self.assertEqual([anchor.name for anchor in cfg.nutrition.anchors], ["Whey shake"])


if __name__ == "__main__":
    unittest.main()
