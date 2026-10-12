"""Each skill is a short SKILL.md plus step files read on demand, and CLAUDE.md stays short."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.support import REPO_ROOT
from tests.support.skills import SKILLS, all_skills, body_lines, flat, skill_files, skill_names, skill_text, step_text

NINE = ("check-in", "framework-sync", "goals", "hevy-sync", "meal-plan", "new-program", "program-week", "recipes",
        "setup")
SKILL_MD_CAP = 120
STEP_FILE_CAP = 150
MODES = ("normal", "midweek", "light", "minimum", "constrained", "reshuffle")
APPROVAL_TEMPLATE = 'Reply "go" to train this and write: <routines> (Hevy) · <structural files>.'
NO_HEVY_VARIANT = 'Reply "go" to train this and write: <structural files>. Nothing goes to Hevy (no Hevy).'
NOTHING_TO_WRITE_VARIANT = 'Reply "go" to train this. Nothing goes to Hevy (<reason>).'
COMMIT_CLAUSES = (" Commit: <each path in full>.", " Commit: no training records.")
SCRIPT_RULE = ("Never compute, convert or call Hevy by hand: run `python3 -m coach` and quote its output. "
               "If a command fails, say so and quote the error.")
OLD_SKILL = "one-off" + "-week"


def over_cap(folder):
    """Each file in a skill folder longer than its cap, as `name: lines`."""
    found = []
    for path in sorted(Path(folder).glob("*.md")):
        cap = SKILL_MD_CAP if path.name == "SKILL.md" else STEP_FILE_CAP
        if len(body_lines(path)) > cap:
            found.append(f"{path.name}: {len(body_lines(path))}")
    return found


def claude_md_lines():
    return (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").rstrip("\n").splitlines()


def without_sections(lines, headings):
    kept, skipping = [], False
    for line in lines:
        if line.startswith("## "):
            skipping = line[3:] in headings
        if not skipping:
            kept.append(line)
    return kept


class SkillFolderTest(unittest.TestCase):
    def test_the_nine_skills(self):
        self.assertEqual(sorted(path.name for path in SKILLS.iterdir() if path.is_dir()), list(NINE))
        self.assertEqual(skill_names(), list(NINE))

    def test_every_file_fits_its_cap(self):
        for name in NINE:
            with self.subTest(skill=name):
                self.assertEqual(over_cap(SKILLS / name), [])

    def test_the_cap_catches_a_long_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "SKILL.md").write_text("---\nname: x\n---\n" + "line\n" * 121, encoding="utf-8")
            Path(tmp, "step.md").write_text("line\n" * 150, encoding="utf-8")
            self.assertEqual(over_cap(tmp), ["SKILL.md: 121"])
            Path(tmp, "step.md").write_text("line\n" * 151, encoding="utf-8")
            self.assertEqual(over_cap(tmp), ["SKILL.md: 121", "step.md: 151"])

    def test_skill_md_points_at_every_step_file(self):
        for name in NINE:
            main = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            for path in skill_files(name)[1:]:
                with self.subTest(skill=name, step=path.name):
                    self.assertIn(f"]({path.name})", main)


class SkillContentTest(unittest.TestCase):
    def test_no_skill_carries_an_e1rm_formula(self):
        pattern = re.compile(r"Epley|reps\s*/\s*30|1 \+ reps")
        for name, text in all_skills().items():
            with self.subTest(skill=name):
                self.assertIsNone(pattern.search(text))

    def test_check_in_and_program_week_hold_no_record_template(self):
        for name in ("check-in", "program-week"):
            with self.subTest(skill=name):
                self.assertNotIn("```markdown", skill_text(name))

    def test_no_skill_holds_a_record_template(self):
        for name, text in all_skills().items():
            with self.subTest(skill=name):
                self.assertNotIn("```markdown", text)


class ProgramWeekModesTest(unittest.TestCase):
    def setUp(self):
        self.main = (SKILLS / "program-week" / "SKILL.md").read_text(encoding="utf-8")
        self.text = skill_text("program-week")

    def mode_rows(self):
        return {row.split("|")[1].strip(): row for row in self.main.splitlines()
                if row.startswith("| ") and row.split("|")[1].strip() in MODES}

    def test_skill_md_names_the_six_modes_and_how_each_runs(self):
        rows = self.mode_rows()
        self.assertEqual(sorted(rows), sorted(MODES))
        for mode, row in rows.items():
            with self.subTest(mode=mode):
                self.assertRegex(row, r"\]\([a-z-]+\.md\)|`[a-z]+ [a-z-]+")

    def test_each_mode_names_its_overlay_kind(self):
        kinds = {"normal": "`weekly`", "midweek": "`midweek`", "light": "`deload`", "minimum": "`weekly`",
                 "constrained": "`one_off`", "reshuffle": "`one_off`"}
        rows = self.mode_rows()
        for mode, kind in kinds.items():
            with self.subTest(mode=mode):
                self.assertIn(kind, rows[mode])

    def test_the_approval_sentence_appears_once_with_its_variants(self):
        for sentence in (APPROVAL_TEMPLATE, NO_HEVY_VARIANT, NOTHING_TO_WRITE_VARIANT):
            with self.subTest(sentence=sentence):
                self.assertEqual(self.text.count(sentence), 1)

    def test_every_write_line_ends_with_the_commit_plan_from_pages_plan(self):
        brief = flat(step_text("program-week", "brief.md"))
        plan = brief[brief.index("**The commit plan**"):]
        self.assertIn("`missed plan`'s too", plan)
        self.assertIn("python3 -m coach pages plan", plan)
        for flag in ("`--structural`", "`--session <id>`", "`--light-week`", "`--one-off`", "`--create-routines`",
                     "`--missed`"):
            with self.subTest(flag=flag):
                self.assertIn(flag, plan)
        self.assertIn("changed now or `planned`", plan)
        for clause in COMMIT_CLAUSES:
            with self.subTest(clause=clause):
                self.assertIn(f"`{clause}`", plan)
        stop = brief[brief.index("## Then stop"):]
        self.assertIn("every write the line names and its commit plan", stop)
        self.assertIn("don't ask again before writing to Hevy or committing those records", stop)
        self.assertIn("drop the commit plan", stop)
        midweek = flat(step_text("program-week", "midweek.md"))
        self.assertIn("`write_line` and the commit plan (brief.md, step 7, with `--missed`)", midweek)

    def test_a_skip_rule_has_no_commit_plan_and_says_the_miss_stays_local(self):
        brief = flat(step_text("program-week", "brief.md"))
        self.assertIn("not a `skip` rule's (midweek.md)", brief)
        midweek = flat(step_text("program-week", "midweek.md"))
        skip = midweek[midweek.index("A `skip` rule"):midweek.index("When it reports `matched: false`")]
        self.assertIn("its write line has no commit plan", skip)
        self.assertIn("stays only on this computer (uncommitted)", skip)
        self.assertIn("`data/history/annotations.json`", skip)

    def test_close_out_commits_the_approved_plan_and_names_what_stays_local(self):
        write = flat(step_text("program-week", "write.md"))
        close = write[write.index("## Close out"):]
        publish = close.index("pages publish --overlay <id>` with `--include <path>`")
        self.assertLess(publish, close.index("`--dry-run` first"))
        self.assertIn("include them only after the athlete's yes", close)
        self.assertIn("The approved plan itself needs no second question", close)
        self.assertIn("no `--include` when the athlete kept the records local", close)
        self.assertIn("`records.local`", close[close.index("Recap"):])

    def test_the_description_carries_the_one_off_triggers(self):
        description = self.main.split("description:", 1)[1].split("\n", 1)[0]
        for phrase in ("deload week", "I'm traveling next week", "plan me a fallback week"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, description)

    def test_an_active_one_off_continues_in_its_mode(self):
        text = flat(self.text)
        self.assertNotIn("stand down", text.lower())
        self.assertIn("`state.one_off`", text)

    def test_run_mode_and_no_hevy_apply_in_every_mode(self):
        text = flat(self.main)
        self.assertIn("**Run mode", text)
        self.assertIn("**No Hevy", text)
        self.assertIn("python3 -m coach sheets render", text)

    def test_constrained_mode_builds_checks_and_writes_temporary_routines(self):
        text = flat(step_text("program-week", "one-off.md"))
        for needle in ("python3 -m coach units round", "`[equipment.locations.*]`", "`one_off`", '`"temporary": true`',
                       "`dumbbells`", "`kettlebells`", "`load_unrepresentable`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        write = flat(step_text("program-week", "write.md"))
        order = [write.index(word) for word in ("overlay approve", "routines retire", "routines create",
                                                "routines push", "routines verify")]
        self.assertEqual(order, sorted(order))

    def test_a_reshuffle_writes_nothing_to_hevy(self):
        text = flat(step_text("program-week", "one-off.md"))
        reshuffle = text[text.index("**Reshuffle"):]
        self.assertIn("routines diff", reshuffle)
        self.assertIn("nothing goes to Hevy", reshuffle)

    def test_a_one_off_week_is_recorded_in_state_and_retired_after_it_ends(self):
        text = flat(self.text)
        self.assertIn('{"overlay_id": "<id>", "span": {"start": "<start>", "end": "<end>"}}', text)
        self.assertIn("python3 -m coach routines retire --overlay", text)
        self.assertIn("python3 -m coach block decide --outcome adopted", text)


class CheckInHandOverTest(unittest.TestCase):
    def test_check_in_hands_an_agreed_light_week_to_program_week_light_mode(self):
        text = flat(skill_text("check-in"))
        self.assertIn("**program-week** skill in light mode", text)
        self.assertNotIn(OLD_SKILL, text)


class ClaudeMdTest(unittest.TestCase):
    def setUp(self):
        self.lines = claude_md_lines()
        self.text = "\n".join(self.lines)

    def test_states_the_script_rule_next_to_the_exit_codes(self):
        text = flat(self.text)
        self.assertIn(SCRIPT_RULE, text)
        self.assertLess(text.index(SCRIPT_RULE), text.index("- **3** —"))

    def test_line_caps(self):
        self.assertLessEqual(len(self.lines), 230)
        rest = without_sections(self.lines, ("Coaching principles", "Researching current best practice"))
        self.assertLessEqual(len(rest), 105)

    def test_names_the_nine_skills(self):
        for name in NINE:
            with self.subTest(skill=name):
                self.assertIn(f"`/{name}`", self.text)

    def test_the_agent_skills_stub_points_at_the_moved_section(self):
        start = self.lines.index("## Agent skills")
        stub = [line for line in self.lines[start + 1:] if line.strip()]
        self.assertLessEqual(len(stub), 3)
        self.assertIn("docs/agents/README.md", " ".join(stub))
        self.assertNotIn("### Issue tracker", self.text)

    def test_docs_agents_readme_holds_the_former_section(self):
        text = (REPO_ROOT / "docs" / "agents" / "README.md").read_text(encoding="utf-8")
        for needle in ("### Issue tracker", "`joeuk89/claude-strength-coach`", "docs/agents/issue-tracker.md",
                       "### Triage labels", "docs/agents/triage-labels.md", "### Domain docs",
                       "docs/agents/domain.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class GlossaryTest(unittest.TestCase):
    def test_defines_a_programming_pass(self):
        text = (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8")
        match = re.search(r"^\*\*Programming pass\*\*:\n(.*?)(?=\n\n)", text, re.M | re.S)
        self.assertIsNotNone(match)
        self.assertIn("one approval", match.group(1))
        self.assertIn("_Avoid_:", match.group(1))


class OldSkillGoneTest(unittest.TestCase):
    def test_no_framework_file_names_the_old_skill(self):
        try:
            result = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others",
                                     "--exclude-standard"], capture_output=True, text=True)
        except FileNotFoundError:
            self.skipTest("needs the template's git checkout")
        if result.returncode != 0:
            self.skipTest("needs the template's git checkout")
        found = []
        for path in result.stdout.splitlines():
            if path.startswith(("docs/", ".agent/")) or not (REPO_ROOT / path).is_file():
                continue
            try:
                text = (REPO_ROOT / path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if OLD_SKILL in text:
                found.append(path)
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
