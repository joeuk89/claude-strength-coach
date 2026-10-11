"""The check-in skill calls the history and stats commands in the steps they replace (contract preamble, C17, C18)."""

import re
import unittest

from tests.support import REPO_ROOT

SKILL = REPO_ROOT / ".claude" / "skills" / "check-in" / "SKILL.md"


def section(text, start, end):
    return text[text.index(start):text.index(end)]


class CheckInSkillTest(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_names_each_command_in_its_step(self):
        flat = " ".join(self.text.split())
        pull = section(flat, "## 2. Pull the data", "## 3.")
        analyse = section(flat, "## 4. Analyze", "## 5.")
        self.assertIn("python3 -m coach history sync", pull)
        for command in ("stats e1rm", "stats adherence", "stats audit", "history annotate"):
            with self.subTest(command=command):
                self.assertIn(f"python3 -m coach {command}", analyse)

    def test_carries_no_e1rm_formula(self):
        self.assertIsNone(re.search(r"Epley|reps\s*/\s*30|1 \+ reps", self.text))


if __name__ == "__main__":
    unittest.main()
