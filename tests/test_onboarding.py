"""Onboarding: `config suggest`, the config /setup writes, and the setup skill's shape (contract C44, C54)."""

import json
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from coach.commands import discover
from tests.support import FIXTURES, REPO_ROOT, run_cli, run_module
from tests.support.config_edit import apply
from tests.support.skills import skill_text, step_text

EXAMPLE = REPO_ROOT / "config.example.toml"
TRANSCRIPT = FIXTURES / "onboarding" / "starter-path.json"


def flat(text):
    return " ".join(text.split())


def sections(text):
    """{heading line: body} for each `## ` section; headings inside code fences belong to the body."""
    found, heading, fenced = {}, None, False
    for line in text.splitlines(keepends=True):
        if line.startswith("```"):
            fenced = not fenced
        if line.startswith("## ") and not fenced:
            heading = line.strip()
            found[heading] = ""
        elif heading is not None:
            found[heading] += line
    return found


def section(text, prefix):
    found = [body for heading, body in sections(text).items() if heading.startswith(prefix)]
    if len(found) != 1:
        raise AssertionError(f"expected one section starting {prefix!r}, found {len(found)}")
    return found[0]


def files_under(root):
    return sorted(str(path.relative_to(root)) for path in Path(root).rglob("*"))


class SuggestTest(unittest.TestCase):
    def suggest(self, *argv):
        with tempfile.TemporaryDirectory() as tmp:
            code, envelope, stderr = run_cli(["--root", tmp, "config", "suggest", *argv])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(files_under(tmp), [])
        return envelope["data"]

    def test_lb_commercial_suggests_a_45_lb_bar_and_lb_plates(self):
        equipment = self.suggest("--unit", "lb", "--gym", "commercial")["values"]["equipment"]
        self.assertEqual(equipment["bar_weight"], 45)
        self.assertEqual(equipment["barbell_increment"], 5)
        self.assertEqual(equipment["plates"], [45, 35, 25, 10, 5, 2.5])

    def test_the_kg_and_lb_tables(self):
        self.assertEqual(self.suggest("--unit", "kg")["values"]["equipment"], {
            "bar_weight": 20, "plates": [25, 20, 15, 10, 5, 2.5, 1.25], "barbell_increment": 2.5,
            "dumbbell_increment": 2, "dumbbell_max": 50, "machine_increment": 5, "cable_increment": 2.5})
        self.assertEqual(self.suggest("--unit", "lb")["values"]["equipment"], {
            "bar_weight": 45, "plates": [45, 35, 25, 10, 5, 2.5], "barbell_increment": 5,
            "dumbbell_increment": 5, "dumbbell_max": 120, "machine_increment": 10, "cable_increment": 5})

    def test_athlete_units_follow_the_unit(self):
        self.assertEqual(self.suggest("--unit", "lb")["values"]["athlete"], {"units": "lb", "bodyweight_units": "lb"})

    def test_the_gym_defaults_to_commercial(self):
        self.assertEqual(self.suggest("--unit", "kg")["gym"], "commercial")

    def test_a_home_gym_asks_for_the_heaviest_dumbbell(self):
        data = self.suggest("--unit", "kg", "--gym", "home")
        self.assertNotIn("dumbbell_max", data["values"]["equipment"])
        self.assertEqual(data["values"]["equipment"]["dumbbell_increment"], 2.5)
        self.assertIn("equipment.dumbbell_max", [note["key"] for note in data["notes"]])

    def test_every_note_names_a_key_and_says_what_to_confirm(self):
        for unit in ("kg", "lb"):
            for gym in ("commercial", "home"):
                for note in self.suggest("--unit", unit, "--gym", gym)["notes"]:
                    with self.subTest(unit=unit, gym=gym, key=note["key"]):
                        self.assertRegex(note["key"], r"^(athlete|equipment)\.[a-z_]+$")
                        self.assertTrue(note["message"].strip())

    def test_a_unit_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, _ = run_cli(["--root", tmp, "config", "suggest"])
        self.assertEqual(code, 2)

    def test_it_is_read_only_and_allowlisted(self):
        found = {cmd.name: cmd for cmd in discover()}["config suggest"]
        self.assertFalse(any(found.metadata()[flag] for flag in ("writes", "hevy_write", "network", "git_write")))
        allow = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
        self.assertIn("Bash(python3 -m coach config suggest:*)", allow)

    def test_the_cli_prints_the_envelope(self):
        code, envelope, stderr = run_module(["config", "suggest", "--unit", "lb", "--gym", "commercial"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(envelope["data"]["values"]["equipment"]["bar_weight"], 45)


def suggested(unit, gym="commercial"):
    code, envelope, stderr = run_cli(["config", "suggest", "--unit", unit, "--gym", gym])
    assert code == 0, stderr
    return envelope["data"]["values"]


class SuggestedConfigValidatesTest(unittest.TestCase):
    def validate(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config.toml").write_text(text, encoding="utf-8")
            return run_cli(["--root", tmp, "config", "validate"])

    def test_the_example_with_the_lb_suggestions_validates(self):
        text = apply(EXAMPLE.read_text(encoding="utf-8"), suggested("lb"))
        code, envelope, stderr = self.validate(text)
        self.assertEqual(code, 0, (envelope, stderr))
        self.assertEqual(tomllib.loads(text)["equipment"]["bar_weight"], 45)

    def test_the_example_with_the_kg_suggestions_validates(self):
        for gym in ("commercial", "home"):
            with self.subTest(gym=gym):
                code, envelope, stderr = self.validate(apply(EXAMPLE.read_text(encoding="utf-8"), suggested("kg", gym)))
                self.assertEqual(code, 0, (envelope, stderr))

    def test_an_lb_home_gym_needs_the_heaviest_dumbbell_it_asks_for(self):
        text = apply(EXAMPLE.read_text(encoding="utf-8"), suggested("lb", "home"))
        code, envelope, _ = self.validate(text)
        self.assertEqual(code, 5)
        self.assertIn("dumbbell_max", envelope["error"]["message"])
        code, envelope, stderr = self.validate(apply(text, {"equipment": {"dumbbell_max": 50}}))
        self.assertEqual(code, 0, (envelope, stderr))


class WorkedExampleTest(unittest.TestCase):
    """The fixture transcript: a new athlete from /setup to week one on the starter path."""

    @classmethod
    def setUpClass(cls):
        cls.transcript = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))

    def run_transcript(self, root):
        transcript = self.transcript
        env = {"COACH_NOW": transcript["now"]}
        text = apply(EXAMPLE.read_text(encoding="utf-8"),
                     suggested(transcript["suggest"]["unit"], transcript["suggest"]["gym"]))
        outputs = {}
        for reply in transcript["replies"]:
            text = apply(text, reply["config"])
            (root / "config.toml").write_text(text, encoding="utf-8")
            for argv in reply["commands"]:
                if argv == "confirm load modes":
                    self.confirm_load_modes(root, env, outputs["program adopt"])
                    continue
                argv = [part.replace("{root}", str(root)).replace("{week}", transcript["week"]) for part in argv]
                code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
                self.assertEqual(code, 0, (argv, envelope, stderr))
                outputs[" ".join(argv[:2])] = envelope["data"]
        return tomllib.loads(text), outputs

    def confirm_load_modes(self, root, env, adopted):
        self.assertTrue(adopted["unconfirmed"])
        program = json.loads((root / "data" / "program.json").read_text(encoding="utf-8"))
        modes = {line["exercise_id"]: line["load_mode"] for s in program["sessions"] for line in s["exercises"]}
        for row in adopted["unconfirmed"]:
            exercise_id = row["exercise_id"]
            code, envelope, stderr = run_cli(
                ["--root", str(root), "library", "set-mode", exercise_id, modes[exercise_id]], env=env)
            self.assertEqual(code, 0, (exercise_id, envelope, stderr))

    def test_ten_or_fewer_replies_reach_week_one(self):
        replies = self.transcript["replies"]
        self.assertLessEqual(len(replies), 10)
        self.assertIn('Reply "go" to train this', replies[-1]["asked"])
        self.assertEqual(replies[-1]["athlete"], "go")

    def test_the_config_holds_the_profile_facts_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, outputs = self.run_transcript(root)
            code, envelope, stderr = run_cli(["--root", tmp, "config", "validate"])
            self.assertEqual(code, 0, (envelope, stderr))

        athlete = config["athlete"]
        self.assertEqual(athlete["experience"], "beginner")
        self.assertEqual(athlete["available_days"], ["mon", "wed", "fri"])
        self.assertEqual(athlete["session_minutes"], 75)
        self.assertIn("barbell", config["equipment"]["available"])
        self.assertEqual(config["equipment"]["dumbbell_max"], 50)
        self.assertEqual(config["equipment"]["locations"]["home"]["dumbbell_max"], 22.5)
        self.assertNotIn("bar_weight", config["equipment"]["locations"]["home"])
        self.assertEqual(config["nutrition"], {"enabled": False})
        self.assertTrue(config["activity"]["enabled"])

    def test_the_starter_path_adopts_and_proposes_week_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, outputs = self.run_transcript(root)
            self.assertEqual(outputs["starters list"]["recommended_id"], "full-body-3")
            draft = json.loads((root / ".coach" / "drafts" / "program.json").read_text(encoding="utf-8"))
            exercises = {line["exercise_id"] for s in draft["program"]["sessions"] for line in s["exercises"]}
            self.assertNotIn("bb_deadlift", exercises)
            self.assertIn("swapped_exercise", {row["kind"] for row in draft["report"]})
            self.assertTrue((root / "data" / "program.json").is_file())
            overlay = outputs["propose week"]["overlay"]
            self.assertNotIn("block", {flag.get("severity") for flag in overlay["flags"]})


class SetupSkillTest(unittest.TestCase):
    COMMANDS = ("config suggest", "config validate", "starters list", "starters draft", "program import-hevy",
                "program adopt", "propose week")

    @classmethod
    def setUpClass(cls):
        cls.text = skill_text("setup")
        cls.flat = flat(cls.text)

    def test_setup_commit_precedes_week_one_and_uses_athlete_reviewed_paths(self):
        body = flat(section(self.text, "## 5."))
        self.assertLess(body.index("[commit.md]"), body.index("**program-week**"))
        commit = flat(step_text("setup", "commit.md"))
        for required in ("written", "removed", "archived", "staged", "athlete to approve", "git add --",
                         "git diff --cached", "upstream", "zip", "normal clone"):
            self.assertIn(required, commit)
        self.assertNotIn("git add -A", self.text)

    def test_names_the_onboarding_commands(self):
        for name in self.COMMANDS:
            with self.subTest(command=name):
                self.assertIn(f"python3 -m coach {name}", self.flat)

    def test_asks_six_profile_questions_in_one_list_and_at_most_two_messages(self):
        body = section(self.text, "## 3.")
        questions = re.findall(r"(?m)^\d+\. ", body)
        self.assertEqual(len(questions), 6)
        self.assertIn("at most two messages", flat(body))

    def test_does_no_plate_increment_or_load_arithmetic(self):
        arithmetic = re.compile(r"\d\s*(kg|lb)\b|[×x*/]\s*2\b|\bper side\b|\b(bar_weight|barbell_increment|"
                                r"dumbbell_increment|machine_increment|cable_increment|plates)\s*=", re.IGNORECASE)
        self.assertEqual([m.group(0) for m in arithmetic.finditer(self.text)], [])

    def test_nutrition_lives_in_the_config_question_and_one_yes_branch(self):
        config_step = section(self.text, "## 1.")
        branch_heading, branch = next((h, b) for h, b in sections(self.text).items() if "Nutrition" in h)
        self.assertIn("only when", branch_heading.lower() + flat(branch).lower()[:200])
        self.assertIn("/goals", branch)
        self.assertIn("Invoke the **goals** skill", flat(branch))
        outside = self.text.replace(config_step, "").replace(branch, "").replace(branch_heading, "")
        self.assertEqual(re.findall(r"(?i)nutrition|/goals|goals skill|macrofactor", outside), [])

    def test_the_goals_call_comes_after_week_one_is_approved(self):
        self.assertLess(self.flat.index("python3 -m coach propose week"), self.flat.index("Invoke the **goals** skill"))

    def test_asks_run_or_coach_only_on_the_import_path(self):
        self.assertEqual(self.flat.count("run it as written"), 1)
        import_path = self.flat[self.flat.index("**Import path**"):self.flat.index("**Design path**")]
        self.assertIn("run it as written", import_path)
        self.assertIn("`[coaching] mode`", import_path)

    def test_no_notion_or_pantry(self):
        self.assertEqual(re.findall(r"(?i)notion|pantry", self.text), [])

    def test_the_profile_skeleton_has_five_sections_and_no_nutrition(self):
        self.assertIn("reference/record-formats.md", flat(step_text("setup", "profile-facts.md")))
        formats = (REPO_ROOT / "reference" / "record-formats.md").read_text(encoding="utf-8")
        body = formats.split("## profile.md: the first version", 1)[1].split("## profile.md: Nutrition", 1)[0]
        skeleton = re.search(r"```markdown\n(.*?)```", body, re.S).group(1)
        headings = re.findall(r"(?m)^## (.*)$", skeleton)
        self.assertEqual(headings, ["Goal", "Training week", "Equipment", "Injuries / limitations",
                                    "Coach's notes"])


class NewProgramOfferTest(unittest.TestCase):
    def test_new_program_opens_with_the_three_paths_and_a_recommendation(self):
        text = flat(skill_text("new-program"))
        offer = text[text.index("## 1. Offer the three paths"):text.index("## 2.")]
        for needle in ("Path A", "Path B", "Path C", "one message", "recommend"):
            with self.subTest(needle=needle):
                self.assertIn(needle, offer)


if __name__ == "__main__":
    unittest.main()
