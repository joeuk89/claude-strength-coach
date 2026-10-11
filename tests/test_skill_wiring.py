"""The skills call the Phase 1 commands instead of the Hevy API (contract preamble, C2, C3, C10, C12, C16)."""

import re
import tempfile
import unittest
from pathlib import Path

from coach.commands import discover
from tests.support import REPO_ROOT, run_module

SKILLS = REPO_ROOT / ".claude" / "skills"
WIRED = ("check-in", "hevy-sync", "new-program", "one-off-week", "program-week", "setup")
PROGRAM_CHANGERS = ("check-in", "hevy-sync", "new-program", "program-week")
PROGRAMMING_PASSES = ("one-off-week", "program-week")
APPROVAL_SENTENCE = 'Reply "go" to train this'
WAIT = "stop and wait for the athlete's reply"
PASS_ORDER = ("overlay build", "overlay validate", "overlay render", "routines diff", APPROVAL_SENTENCE,
              "overlay approve", "routines push", "routines verify")

FULL_COMMAND = re.compile(r"python3\s+-m\s+coach\s+(?:--root\s+\S+\s+)?([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*))?")
CODE_SPAN = re.compile(r"`([^`\n]+)`")


def skill_text(name):
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def all_skills():
    return {path.parent.name: path.read_text(encoding="utf-8") for path in sorted(SKILLS.glob("*/SKILL.md"))}


def flat(text):
    return " ".join(text.split())


class NoHandBuiltHevyCallsTest(unittest.TestCase):
    def test_no_skill_names_the_api_or_the_old_map(self):
        pattern = re.compile(r"api\.hevyapp\.com|/v1/|weight_kg|hevy-map")
        found = [f"{name}: {line.strip()}" for name, text in all_skills().items()
                 for line in text.splitlines() if pattern.search(line)]
        self.assertEqual(found, [])

    def test_no_skill_converts_dumbbell_loads_in_prose(self):
        pattern = re.compile(r"double the|halve the", re.IGNORECASE)
        found = [f"{name}: {line.strip()}" for name, text in all_skills().items()
                 for line in text.splitlines() if pattern.search(line)]
        self.assertEqual(found, [])


class NamedCommandsExistTest(unittest.TestCase):
    """Every command a skill or CLAUDE.md names is registered (C2)."""

    @classmethod
    def setUpClass(cls):
        cls.names = {command.name for command in discover()}
        cls.groups = {name.split()[0] for name in cls.names if " " in name}

    def unknown(self, text):
        missing = set()
        for match in FULL_COMMAND.finditer(text):
            first, second = match.group(1), match.group(2)
            if first in self.names:
                continue
            if f"{first} {second}" not in self.names:
                missing.add(f"{first} {second}")
        for span in CODE_SPAN.findall(text):
            words = span.split()
            if len(words) >= 2 and words[0] in self.groups and re.fullmatch(r"[a-z][a-z0-9-]*", words[1]):
                if f"{words[0]} {words[1]}" not in self.names:
                    missing.add(f"{words[0]} {words[1]}")
        return sorted(missing)

    def test_skills_name_only_registered_commands(self):
        for name, text in all_skills().items():
            with self.subTest(skill=name):
                self.assertEqual(self.unknown(text), [])

    def test_claude_md_names_only_registered_commands(self):
        self.assertEqual(self.unknown((REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")), [])

    def test_the_resolver_catches_an_unknown_command(self):
        self.assertEqual(self.unknown("Run `python3 -m coach routines publish --overlay X`."), ["routines publish"])
        self.assertEqual(self.unknown("then `overlay publish ID`"), ["overlay publish"])


class ProgrammingPassTest(unittest.TestCase):
    def test_the_pass_names_its_commands_in_order(self):
        for name in PROGRAMMING_PASSES:
            text = flat(skill_text(name))
            position = 0
            for needle in PASS_ORDER:
                with self.subTest(skill=name, needle=needle):
                    found = text.find(needle, position)
                    self.assertNotEqual(found, -1, f"{needle!r} missing after position {position}")
                    position = found + len(needle)

    def test_no_skill_pushes_before_it_waits_for_the_reply(self):
        for name, text in all_skills().items():
            text = flat(text)
            push = text.find("routines push")
            if push == -1:
                continue
            with self.subTest(skill=name):
                wait = text.find(WAIT)
                self.assertNotEqual(wait, -1, "names routines push but never waits for the reply")
                self.assertLess(wait, push)

    def test_a_refused_push_is_reported_not_retried(self):
        for name in PROGRAMMING_PASSES:
            with self.subTest(skill=name):
                text = flat(skill_text(name))
                self.assertIn("exits 3", text)
                self.assertIn("Manual fallback", text)


class ProgramChangesGoThroughTheDataTest(unittest.TestCase):
    HAND_EDIT = re.compile(
        r"\b(edit|edits|editing|update|updates|write|writes|add|adds|move)\b[^.\n]{0,60}`routine/", re.IGNORECASE)

    def test_structural_changes_edit_the_data_then_validate_and_render(self):
        for name in PROGRAM_CHANGERS:
            with self.subTest(skill=name):
                text = flat(skill_text(name))
                data = min(i for i in (text.find("data/program.json"), text.find("data/state.json")) if i != -1)
                validate = text.find("program validate", data)
                self.assertNotEqual(validate, -1)
                self.assertNotEqual(text.find("program render", validate), -1)

    def test_no_skill_edits_the_rendered_pages(self):
        found = [f"{name}: {match.group(0)}" for name, text in all_skills().items()
                 for match in self.HAND_EDIT.finditer(flat(text))]
        self.assertEqual(found, [])


class ProgramWeekSkillTest(unittest.TestCase):
    def test_program_week_close_out_renders_then_publishes_after_a_verified_push(self):
        text = skill_text("program-week")
        start = text.index("## 7. Close out")
        close_out, rest = " ".join(text[start:].split()), text[:start]
        verify = close_out.index("routines verify")
        render = close_out.index("python3 -m coach pages render")
        publish = close_out.index("python3 -m coach pages publish --overlay")
        self.assertLess(verify, render)
        self.assertLess(render, publish)
        self.assertNotIn("pages render", rest)
        self.assertNotIn("pages publish", rest)


class SkillsStartWithCheckTest(unittest.TestCase):
    def test_wired_skills_run_check_first_and_stop_before_the_bootstrap(self):
        for name in WIRED:
            with self.subTest(skill=name):
                text = flat(skill_text(name))
                self.assertEqual(text.find("python3 -m coach"), text.find("python3 -m coach check"))
                self.assertIn("`fail`", text)
                self.assertIn("bootstrap migration", text)

    def test_wired_skills_quote_loads_from_coach_output(self):
        for name in WIRED:
            if name == "setup":
                continue
            with self.subTest(skill=name):
                self.assertIn("loads come from `coach` output; quote them", flat(skill_text(name)).lower())


class ManualFallbackTest(unittest.TestCase):
    def test_reference_has_the_fallback_section(self):
        text = (REPO_ROOT / "reference" / "hevy-api.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^## Manual fallback$")
        self.assertNotIn("hevy-map", text)

    def test_skills_link_the_reference_only_as_the_failure_path(self):
        for name, text in all_skills().items():
            for paragraph in re.split(r"\n\s*\n", text):
                if "hevy-api.md" in paragraph:
                    with self.subTest(skill=name, paragraph=paragraph[:60]):
                        self.assertIn("Manual fallback", paragraph)


class SetupWritesConfigTest(unittest.TestCase):
    """`setup` copies config.example.toml to config.toml, edits the answers in, and validates it."""

    KEYS = ("units", "bodyweight_units", "week_starts", "timezone", "enabled", "available", "dumbbells")

    def test_setup_names_the_steps(self):
        text = flat(skill_text("setup"))
        for needle in ("config.example.toml", "config.toml", "python3 -m coach config validate",
                       "python3 -m coach hevy status", "python3 -m coach hevy pull"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        for key in self.KEYS:
            with self.subTest(key=key):
                self.assertIn(f"`{key}`", text)

    def make_config(self, root, replacements):
        text = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        for old, new in replacements:
            self.assertIn(old, text)
            text = text.replace(old, new, 1)
        (root / "config.toml").write_text(text, encoding="utf-8")

    def validate(self, root):
        return run_module(["--root", str(root), "config", "validate"])

    def test_a_kg_athlete_with_hevy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_config(root, [
                ('week_starts = "monday"', 'week_starts = "sunday"'),
                ('timezone = ""', 'timezone = "Europe/London"'),
                ("available = []", 'available = ["barbell", "dumbbell", "cable"]'),
                ("dumbbells = []", "dumbbells = [5, 7.5, 10, 12.5, 15, 17.5, 20]"),
                ("# dumbbell_max = 40.0", "dumbbell_max = 20.0"),
            ])
            code, envelope, stderr = self.validate(root)
            self.assertEqual(code, 0, stderr)
            self.assertTrue(envelope["data"]["valid"])

    def test_an_lb_athlete_without_hevy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_config(root, [
                ('units = "kg"  ', 'units = "lb"  '),
                ('bodyweight_units = "kg"', 'bodyweight_units = "lb"'),
                ('timezone = ""', 'timezone = "America/New_York"'),
                ("enabled = true                # false if", "enabled = false               # false if"),
                ("# dumbbell_increment = 2.0", "dumbbell_increment = 5.0"),
                ("# dumbbell_max = 40.0", "dumbbell_max = 50.0"),
                ("# barbell_increment = 2.5", "barbell_increment = 5.0"),
                ("# bar_weight = 20.0", "bar_weight = 45.0"),
                ("# plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [45, 35, 25, 10, 5, 2.5]"),
                ("# machine_increment = 5.0", "machine_increment = 10.0"),
                ("# cable_increment = 2.5", "cable_increment = 5.0"),
            ])
            code, envelope, stderr = self.validate(root)
            self.assertEqual(code, 0, stderr)
            self.assertTrue(envelope["data"]["valid"])

    def test_an_lb_config_with_kg_equipment_left_commented_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_config(root, [('units = "kg"  ', 'units = "lb"  ')])
            code, envelope, _ = self.validate(root)
            self.assertEqual(code, 5)


if __name__ == "__main__":
    unittest.main()
