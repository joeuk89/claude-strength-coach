"""The Food & eating record format and the skills that write and read it (C4, ADR-0001)."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support import REPO_ROOT, VALID, run_cli
from tests.support.skills import flat, skill_text

FORMATS = (REPO_ROOT / "reference" / "record-formats.md").read_text(encoding="utf-8")
SECTION = re.split(r"(?m)^## (?!Food & eating$)", FORMATS.split("## profile.md: Food & eating", 1)[1], maxsplit=1)[0]
PLANNING_FIELDS = {"Household staples", "Office-day pattern", "Meal responsibility/standing coverage", "Plan style"}


def blocks(language):
    return re.findall(rf"```{language}\n(.*?)```", SECTION, re.S)


def labels(block):
    return re.findall(r"(?m)^- \*\*(.+?):\*\*", block)


def mapping_rows():
    """{field: consumer} from the consumers table; a row may name several fields, split on '; '."""
    rows = {}
    for fields, consumer in re.findall(r"(?m)^\| (?!Food & eating field|---)(.+?) \| (.+?) \|$", SECTION):
        for field in fields.split("; "):
            rows[field] = consumer
    return rows


class FoodProfileFormatTest(unittest.TestCase):
    def test_skeleton_example_and_mapping_name_the_same_fields(self):
        skeleton, example = blocks("markdown")[:2]
        self.assertEqual(len(labels(skeleton)), 9)
        self.assertEqual(labels(skeleton), labels(example))
        self.assertEqual(set(labels(skeleton)), set(mapping_rows()))

    def test_the_pointer_line_replaces_exactly_the_fields_config_holds(self):
        in_template = {field for field, consumer in mapping_rows().items() if "[nutrition.template" in consumer}
        self.assertEqual(in_template, PLANNING_FIELDS)
        pointer = blocks("markdown")[2]
        self.assertIn("`config.toml` → `[nutrition.template]`", pointer)
        after = flat(SECTION.split("### After the standing template exists", 1)[1].split("###", 1)[0])
        for field in PLANNING_FIELDS:
            self.assertIn(field, after)

    def test_no_preference_leaves_plan_style_unset(self):
        self.assertIn("no preference leaves it unset", mapping_rows()["Plan style"])


class ExampleMappingTest(unittest.TestCase):
    def test_example_toml_drives_the_standing_template(self):
        proposal = blocks("toml")[0]
        example = blocks("markdown")[1]
        self.assertIn("Tuesday and Thursday", example)
        self.assertIn("Partner decides dinner Monday to Thursday", example)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "instance"
            shutil.copytree(VALID, root)
            config = root / "config.toml"
            text = config.read_text(encoding="utf-8")
            self.assertIn("\n[nutrition.template]\n", text)
            config.write_text(text.split("\n[nutrition.template]\n", 1)[0] + "\n" + proposal, encoding="utf-8")

            for args in (["config", "validate"], ["check", "--only", "nutrition_template"]):
                code, envelope, stderr = run_cli(["--root", str(root), *args])
                self.assertEqual(code, 0, (args, envelope, stderr))
            code, envelope, stderr = run_cli(["--root", str(root), "meals", "template", "--week", "2026-10-12"])
            self.assertEqual(code, 0, (envelope, stderr))
            data = envelope["data"]
            self.assertEqual(data["office_days"], ["tue", "thu"])
            self.assertEqual(data["staples"], ["eggs", "rice", "olive oil"])
            self.assertEqual(data["style"], "loose")
            covered = [(day["weekday"], slot["entries"][0]["cover"]) for day in data["days"]
                       for slot in day["slots"] if slot["slot"] == "dinner" and slot["entries"]]
            self.assertEqual(covered, [("mon", "partner"), ("tue", "partner"), ("wed", "partner"), ("thu", "partner")])

            notes = dict(re.findall(r'(?m)^(\w+) = "(.*)"$', proposal.split("[nutrition.bank.slot_notes]", 1)[1]))
            self.assertTrue(notes)
            self.assertLessEqual(set(notes), set(data["slots"]))
            code, envelope, stderr = run_cli(["--root", str(root), "recipes", "render"])
            self.assertEqual(code, 0, (envelope, stderr))
            index = (root / "nutrition" / "menu" / "index.md").read_text(encoding="utf-8")
            for note in notes.values():
                self.assertIn(note, index)


class SkillWorkflowTest(unittest.TestCase):
    def test_recipes_asks_missing_fields_together_and_defers_planning_fields(self):
        text = flat(skill_text("recipes"))
        interview = text[text.index("## 2. First run"):text.index("## 3.")]
        for needle in ('"profile.md: Food & eating"', "all missing fields together in one message",
                       "only the necessary follow-up", "go straight to seeding", "only after the athlete confirms",
                       "a change to them is a `/meal-plan` template edit"):
            with self.subTest(needle=needle):
                self.assertIn(needle, interview)
        self.assertNotIn("one question at a time", text)

    def test_recipes_sweep_filters_allergies(self):
        text = flat(skill_text("recipes"))
        sweep = text[text.index("**Sourcing sweep.**"):]
        self.assertIn("allergies/intolerances", sweep[:300])

    def test_meal_plan_setup_reads_the_section_and_writes_the_pointer(self):
        text = flat(skill_text("meal-plan"))
        setup = text[text.index("## Set up the standing template"):text.index("## 1. Read the standing week")]
        for needle in ('"profile.md: Food & eating"', "ask only unresolved planning details",
                       "config pointer line", "only on the athlete's approval", "slot_notes]` note that names the changed fact"):
            with self.subTest(needle=needle):
                self.assertIn(needle, setup)

    def test_contract_records_where_the_planning_fields_live(self):
        contract = flat((REPO_ROOT / "docs" / "design" / "coach-contract.md").read_text(encoding="utf-8"))
        self.assertIn("| staples, office days, standing coverage, plan style (R-33c) |", contract)
        self.assertIn("replaces them with a pointer line, so those facts are never in both places", contract)


if __name__ == "__main__":
    unittest.main()
