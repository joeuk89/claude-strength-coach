"""Setup's structured facts and local command paths, using synthetic athlete answers."""

import copy
import json
import re
import shlex
import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from coach import config, program_drafts
from coach.errors import ConfigError
from tests.support import FIXTURES, MINIMAL_CONFIG, REPO_ROOT, run_cli
from tests.support.config_edit import apply
from tests.support.skills import flat, skill_text, step_text

ANSWERS = json.loads((FIXTURES / "onboarding/returning-athlete.json").read_text())


class BirthYearTest(unittest.TestCase):
    def config(self, value=None, today=date(2026, 10, 11)):
        raw = tomllib.loads(MINIMAL_CONFIG)
        if value is not None:
            raw["athlete"]["birth_year"] = value
        return config.parse(raw, "config.toml", today=today)

    def test_unknown_is_absent_and_has_no_derived_age(self):
        cfg = self.config()
        self.assertNotIn("birth_year", cfg.athlete)
        self.assertIsNone(config.approximate_age(cfg, date(2026, 10, 11)))

    def test_year_is_validated_without_a_new_calculator_age_policy(self):
        for value in (0, -1, True, "1968", 1968.5, 2027):
            with self.subTest(value=value), self.assertRaises(ConfigError) as caught:
                self.config(value)
            self.assertIn("birth_year", caught.exception.message)
        self.assertIn("future", caught.exception.message)
        self.assertEqual(self.config(2026).athlete.birth_year, 2026)
        self.assertEqual(self.config(1900).athlete.birth_year, 1900)

    def test_cli_uses_test_clock_for_validation_and_approximate_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(MINIMAL_CONFIG + "birth_year = 1968\n")
            for year, expected in ((2026, 58), (2030, 62)):
                code, out, stderr = run_cli(["--root", tmp, "config", "show"],
                                           env={"COACH_NOW": f"{year}-10-11T18:00:00Z"})
                self.assertEqual(code, 0, (out, stderr))
                self.assertEqual(out["data"]["age"]["years"], expected)
                self.assertTrue(out["data"]["age"]["approximate"])
                self.assertIn("birthday is unknown", out["data"]["age"]["note"])
            path.write_text(MINIMAL_CONFIG + "birth_year = 2030\n")
            code, out, _ = run_cli(["--root", tmp, "config", "validate"],
                                   env={"COACH_NOW": "2026-10-11T18:00:00Z"})
            self.assertEqual(code, 5)
            self.assertIn("2026", out["error"]["message"])

    def test_future_year_validation_and_age_share_the_athlete_timezone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(MINIMAL_CONFIG + 'birth_year = 2027\ntimezone = "America/Los_Angeles"\n')
            code, out, _ = run_cli(["--root", tmp, "config", "show"],
                                   env={"COACH_NOW": "2027-01-01T00:30:00Z"})
            self.assertEqual(code, 5)
            self.assertIn("after 2026", out["error"]["message"])
            path.write_text(MINIMAL_CONFIG + 'birth_year = 1968\ntimezone = "America/Los_Angeles"\n')
            code, out, stderr = run_cli(["--root", tmp, "config", "show"],
                                        env={"COACH_NOW": "2027-01-01T00:30:00Z"})
            self.assertEqual(code, 0, (out, stderr))
            self.assertEqual(out["data"]["age"]["as_of"], "2026-12-31")
            self.assertEqual(out["data"]["age"]["years"], 58)

    def test_desired_count_is_optional_bounded_and_separate_from_availability(self):
        raw = tomllib.loads(MINIMAL_CONFIG)
        self.assertNotIn("desired_sessions", config.parse(raw, "config.toml").athlete)
        for value in (0, 8, True, 4.5, "4"):
            raw["athlete"]["desired_sessions"] = value
            with self.subTest(value=value), self.assertRaises(ConfigError):
                config.parse(raw, "config.toml")


class LocalSetupTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "config.toml"
        self.path.write_text(apply((REPO_ROOT / "config.example.toml").read_text(), ANSWERS["config"]))
        blocked = patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("unexpected network call"))
        blocked.start()
        self.addCleanup(blocked.stop)

    def cli(self, *args):
        code, out, stderr = run_cli(["--root", str(self.root), *args], env={"COACH_NOW": ANSWERS["now"]})
        self.assertEqual(code, 0, (args, out, stderr))
        return out["data"]

    def test_filled_setup_suggestions_and_four_session_schedule_execute(self):
        main = flat(step_text("setup", "SKILL.md"))
        example = re.search(r"`(python3 -m coach config suggest[^`]+)`", main).group(1)
        self.cli(*shlex.split(example.replace("<kg|lb>", "kg"))[3:])
        self.cli("config", "suggest", "--unit", "kg", "--gym", "home")
        self.cli("config", "validate")
        selection = self.cli("starters", "list", "--days", "4")
        self.assertEqual(selection["recommended_id"], "upper-lower-4")
        self.assertEqual(self.cli("config", "show")["config"]["athlete"]["experience"], "beginner")
        draft = self.cli("starters", "draft", selection["recommended_id"],
                         "--days", "mon,tue,thu,fri", "--dry-run")
        self.assertEqual(draft["problems"], [])
        self.assertEqual(draft["days"], ["mon", "tue", "thu", "fri"])
        self.assertTrue(set(draft["days"]).issubset(ANSWERS["config"]["athlete"]["available_days"]))
        self.assertEqual(len(draft["draft"]["program"]["schedule"]["params"]["days"]), 4)
        self.assertFalse((self.root / ".coach/drafts/program.json").exists())

    def test_corrections_have_valid_structured_destinations_and_resume_reuses_niggle(self):
        profile = "# Synthetic athlete\n\n" + "\n\n".join(
            f"## {title}\n\n{body}" for title, body in ANSWERS["profile"].items())
        (self.root / "profile.md").write_text(profile)
        correction = ANSWERS["correction"]
        self.path.write_text(apply(self.path.read_text(), correction["config"]))
        for command in correction["commands"]:
            self.cli(*command)
        for title, body in correction["profile"].items():
            profile = profile.replace(ANSWERS["profile"][title], body)
        (self.root / "profile.md").write_text(profile)
        facts = self.cli("config", "show")["config"]
        self.assertEqual(facts["athlete"]["desired_sessions"], 2)
        self.assertEqual(facts["athlete"]["available_days"], ["mon", "thu"])
        self.assertIn("machine", facts["equipment"]["available"])
        rows = self.cli("niggles", "list")["niggles"]
        self.assertEqual(len(rows), 1)
        self.cli("niggles", "update", rows[0]["id"], "--notes", "Same limitation; confirmed on resume.")
        self.assertEqual(len(self.cli("niggles", "list")["niggles"]), 1)
        self.assertNotIn("None currently", profile)
        self.assertNotIn("Training at home", profile)
        for title in correction["profile"]:
            self.assertEqual(profile.count(f"## {title}\n"), 1)
        self.assertIn("20 years", profile)
        self.assertIn("12 years off", profile)

    def test_older_draft_requires_only_wrapper_upgrade_and_revalidation(self):
        draft = json.loads((FIXTURES / "program/draft.json").read_text())
        draft["schema_version"] = 1
        path = self.root / "older-draft.json"
        path.write_text(json.dumps(draft))
        before = path.read_bytes()
        code, out, _ = run_cli(["--root", str(self.root), "program", "adopt", "--input", str(path), "--dry-run"],
                               env={"COACH_NOW": ANSWERS["now"]})
        self.assertEqual(code, 1)
        self.assertIn("top-level schema_version to 2", out["error"]["details"][0]["message"])
        self.assertEqual(path.read_bytes(), before)
        upgraded = copy.deepcopy(draft)
        upgraded["schema_version"] = 2
        path.write_text(json.dumps(upgraded))
        preview = self.cli("program", "adopt", "--input", str(path), "--dry-run")
        self.assertEqual(preview["sessions"], ["session-a", "session-b"])
        self.assertEqual(upgraded["program"], draft["program"])
        self.assertEqual(upgraded["source"], draft["source"])
        self.assertEqual(upgraded["report"], draft["report"])
        self.assertFalse((self.root / "data/program.json").exists())

    def test_paper_run_draft_keeps_supplied_exercises_and_schemes_on_dry_run(self):
        draft = json.loads((FIXTURES / "program/draft.json").read_text())
        draft.update(source="manual_import", hevy_routines={}, hevy_folder=None, report=[],
                     detected=copy.deepcopy(program_drafts.NO_DETECTION))
        draft["program"]["name"] = "Supplied two-day paper program"
        draft["program"]["sessions"][0]["exercises"][1]["scheme"] = {
            "name": "double_progression", "params": {}}
        supplied = copy.deepcopy(draft["program"])
        self.path.write_text(apply(self.path.read_text(), {"coaching": {"mode": "run"},
                                                         "athlete": {"desired_sessions": 2}}))
        path = self.root / "paper-draft.json"
        path.write_text(json.dumps(draft))
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        preview = self.cli("program", "adopt", "--input", str(path), "--dry-run")
        self.assertEqual(preview["sessions"], ["session-a", "session-b"])
        self.assertEqual(preview["without_routine"], [])
        self.assertEqual(preview["written"], [])
        self.assertEqual(json.loads(path.read_text())["program"], supplied)
        self.assertEqual(self.cli("config", "show")["config"]["coaching"]["mode"], "run")
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class SetupWorkflowTest(unittest.TestCase):
    def test_current_level_corrections_and_resume_have_explicit_gates(self):
        main = flat(step_text("setup", "SKILL.md"))
        facts = flat(step_text("setup", "profile-facts.md"))
        self.assertNotIn("Skip when `profile.md` exists", main)
        for rule in ("recent consistency", "time off", "Confirm today's programming level", "only unresolved"):
            self.assertIn(rule, main)
        for rule in ("default is not confirmation", "beginner-style re-entry", "no years-off-to-level formula",
                     'incompatible "None currently"', "Replace the affected profile paragraph", "ask only what remains"):
            self.assertIn(rule, facts)
        self.assertIn("before proceeding or completing setup", main)

    def test_paper_route_and_age_reuse_are_reachable_without_design_or_hevy(self):
        path = flat(step_text("new-program", "import.md"))
        paper = path.split("## Paper/manual route", 1)[1].split("## Hevy route", 1)[0]
        for command in ("hevy pull", "library seed", "program import-hevy", "design.md"):
            self.assertNotIn(command, paper)
        for rule in ('"manual_import"', "supplied progression", "agrees an edit", "run it as written"):
            self.assertIn(rule, path)
        self.assertIn("source: \"manual_import\"", skill_text("setup"))
        self.assertIn("starters list --days 4", flat(step_text("setup", "program.md")))
        calories = flat(step_text("goals", "calories.md"))
        self.assertIn("confirm the actual current age", calories)
        self.assertIn("calculator's existing bounds", calories)


if __name__ == "__main__":
    unittest.main()
