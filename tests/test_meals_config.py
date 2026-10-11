"""The [nutrition.template] keys and recipe anchors R-33c adds (contract C4)."""

import re
import tomllib
import unittest

from coach.config import parse
from coach.errors import ConfigError
from tests.support import INSTANCES, MINIMAL_CONFIG, REPO_ROOT, VALID, run_cli, run_module

VALID_TEXT = (VALID / "config.toml").read_text(encoding="utf-8")
OVERLAP = INSTANCES / "meals-template-overlap"


def parse_text(text):
    return parse(tomllib.loads(text), "config.toml")


def error_for(text):
    try:
        parse_text(text)
    except ConfigError as exc:
        return exc
    raise AssertionError("expected a ConfigError")


def messages(exc):
    return " ".join(detail["message"] for detail in exc.details)


def paths_of(exc):
    return [detail["path"] for detail in exc.details]


def with_standing(*rows, office_days='["tue", "thu"]'):
    body = "\n".join(f"[[nutrition.template.standing]]\n{row}\n" for row in rows)
    return VALID_TEXT.split("[nutrition.template]")[0] + (
        f"[nutrition.template]\noffice_days = {office_days}\n\n{body}")


class ValidTemplateTest(unittest.TestCase):
    def test_valid_fixture_reads_the_template(self):
        template = parse_text(VALID_TEXT).nutrition.template
        self.assertEqual(template.slots, ["breakfast", "lunch", "dinner", "snack"])
        self.assertEqual(template.office_days, ["tue", "thu"])
        self.assertEqual(template.staples, ["eggs", "rolled oats", "olive oil"])
        self.assertEqual(template.kcal_tolerance_pct, 15)
        self.assertIs(template.shopping_issue, False)
        self.assertNotIn("plan_style", template)
        self.assertEqual([row.slot for row in template.standing], ["breakfast", "lunch", "dinner"])

    def test_defaults(self):
        template = parse_text(MINIMAL_CONFIG + "[nutrition.template]\n").nutrition.template
        self.assertEqual(template.slots, ["breakfast", "lunch", "dinner", "snack"])
        self.assertEqual((template.office_days, template.staples, template.standing), ([], [], []))
        self.assertEqual((template.kcal_tolerance_pct, template.shopping_issue), (15, False))

    def test_config_validate_as_a_subprocess(self):
        code, envelope, stderr = run_module(["--root", "tests/fixtures/instances/valid", "config", "validate"])
        self.assertEqual(code, 0, stderr)


class StandingRowTest(unittest.TestCase):
    def test_exactly_one_of_recipe_pool_cover(self):
        for row in ('days = ["mon"]\nslot = "lunch"',
                    'days = ["mon"]\nslot = "lunch"\nrecipe = "a"\npool = ["b"]'):
            with self.subTest(row=row):
                exc = error_for(with_standing(row))
                self.assertIn("exactly one of recipe, pool or cover", messages(exc))
                self.assertIn("nutrition.template.standing[0]", paths_of(exc))

    def test_cover_needs_its_estimate_and_others_carry_none(self):
        exc = error_for(with_standing('days = ["mon"]\nslot = "dinner"\ncover = "family"\nkcal = 700'))
        self.assertIn("protein_g", messages(exc))
        exc = error_for(with_standing('days = ["mon"]\nslot = "dinner"\nrecipe = "a"\nkcal = 700'))
        self.assertIn("only on a cover row", messages(exc))

    def test_slot_must_be_configured(self):
        exc = error_for(with_standing('days = ["mon"]\nslot = "elevenses"\nrecipe = "a"'))
        self.assertIn("elevenses", messages(exc))

    def test_unknown_key(self):
        exc = error_for(with_standing('days = ["mon"]\nslot = "lunch"\nrecipe = "a"\nservings = 2'))
        self.assertIn('"servings"', messages(exc))

    def test_two_rows_for_the_same_day_and_slot_name_both(self):
        exc = error_for(with_standing('days = ["daily"]\nslot = "breakfast"\nrecipe = "a"',
                                      'days = ["mon", "tue"]\nslot = "dinner"\ncover = "family"\nkcal = 700\n'
                                      'protein_g = 35',
                                      'days = ["mon"]\nslot = "dinner"\nrecipe = "b"'))
        text = messages(exc)
        self.assertIn("nutrition.template.standing[1]", text)
        self.assertIn("nutrition.template.standing[2]", text)
        self.assertIn("mon", text)

    def test_office_and_home_rows_do_not_overlap(self):
        cfg = parse_text(with_standing('days = ["office"]\nslot = "lunch"\npool = ["a"]',
                                       'days = ["home"]\nslot = "lunch"\nrecipe = "b"'))
        self.assertEqual(len(cfg.nutrition.template.standing), 2)

    def test_daily_overlaps_an_office_row(self):
        exc = error_for(with_standing('days = ["daily"]\nslot = "lunch"\nrecipe = "a"',
                                      'days = ["office"]\nslot = "lunch"\npool = ["b"]'))
        self.assertIn("tue", messages(exc))

    def test_overlap_fixture_exits_5_naming_both_rows(self):
        code, envelope, _ = run_cli(["--root", str(OVERLAP), "config", "validate"])
        self.assertEqual(code, 5, envelope)
        self.assertIn("nutrition.template.standing[2]", envelope["error"]["message"])
        self.assertIn("nutrition.template.standing[3]", envelope["error"]["message"])


class AnchorRecipeTest(unittest.TestCase):
    def test_anchor_may_name_a_card(self):
        text = VALID_TEXT.replace("kcal = 150\nprotein_g = 30\n", 'recipe = "whey-shake"\n', 1)
        anchor = parse_text(text).nutrition.anchors[0]
        self.assertEqual(anchor.recipe, "whey-shake")
        self.assertNotIn("kcal", anchor)

    def test_anchor_needs_macros_or_a_card_not_both(self):
        exc = error_for(VALID_TEXT.replace("kcal = 150\nprotein_g = 30\n", "", 1))
        self.assertIn("nutrition.anchors[0]", paths_of(exc))
        exc = error_for(VALID_TEXT.replace("kcal = 150\n", 'kcal = 150\nrecipe = "whey-shake"\n', 1))
        self.assertIn("nutrition.anchors[0]", paths_of(exc))

    def test_anchor_slot_must_be_a_template_slot(self):
        exc = error_for(VALID_TEXT.replace('slot = "snack"', 'slot = "supper"', 1))
        self.assertIn("supper", messages(exc))


class ExampleTest(unittest.TestCase):
    def test_commented_template_example_validates(self):
        text = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        block = re.search(r"^# \[nutrition\.template\]\n(?:#.*\n)+", text, re.M)
        self.assertIsNotNone(block, "config.example.toml needs a commented [nutrition.template] example")
        lines = [line[2:] for line in block.group(0).splitlines() if line.startswith("# ")]
        cfg = parse_text(MINIMAL_CONFIG + "\n".join(lines) + "\n")
        self.assertEqual([row.slot for row in cfg.nutrition.template.standing], ["breakfast", "lunch", "dinner"])


if __name__ == "__main__":
    unittest.main()
