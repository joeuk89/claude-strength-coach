"""The meal-plan skill and the glossary follow the meals commands (contract preamble, C34)."""

import json
import re
import unittest

from tests.support import REPO_ROOT


class SkillWiringTest(unittest.TestCase):
    TEXT = (REPO_ROOT / ".claude" / "skills" / "meal-plan" / "SKILL.md").read_text(encoding="utf-8")

    def test_skill_uses_the_commands(self):
        for needle in ("meals template", "nutrition status", "meals build", "--dry-run", "meals approve",
                       "meals render", "meals shopping", "--format issue", "gh issue create", "shopping_issue"):
            self.assertTrue(needle in self.TEXT, needle)

    def test_skill_asks_one_line_and_posts_only_after_go(self):
        for needle in ("one exceptions line", '"go"', "only when `shopping_issue = true`"):
            self.assertTrue(needle in self.TEXT, needle)
        for gone in ("Ask once:", "ask for today's kcal and protein targets", "## 4. Coverage for the window"):
            self.assertFalse(gone in self.TEXT, gone)


class GlossaryTest(unittest.TestCase):
    def test_terms_are_defined_with_avoid_lines(self):
        text = (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8")
        for term in ("Standing template", "Plan exception"):
            match = re.search(rf"^\*\*{term}\*\*:\n(.*?)(?=\n\n|\Z)", text, re.M | re.S)
            self.assertIsNotNone(match, term)
            self.assertIn("_Avoid_:", match.group(1))


class AllowlistTest(unittest.TestCase):
    def test_every_meals_command_is_allowlisted(self):
        from coach import commands

        rules = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
        for cmd in commands.discover():
            if cmd.name.startswith("meals "):
                self.assertIn(f"Bash(python3 -m coach {cmd.name}:*)", rules)


if __name__ == "__main__":
    unittest.main()
