"""CLAUDE.md's coaching principles and research practice cite research-note claims (contract C28)."""

import re
import subprocess
import unittest

from coach import research
from tests.support import REPO_ROOT

DISCLAIMER = "This note does not replace assessment by a qualified professional."
INLINE_CITATION_MARKERS = ("et al.", "doi.org/", "ncbi.nlm.nih.gov")
CITATION_FREE_EXEMPT_DIRS = ("research/", "docs/", "tests/")


def _read(relative):
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def claude_section(heading):
    lines = _read("CLAUDE.md").splitlines()
    start = lines.index(f"## {heading}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start + 1:end]


def flat(lines):
    return " ".join(" ".join(lines).split())


def _tracked_files():
    try:
        result = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


class CoachingPrinciplesTest(unittest.TestCase):
    def setUp(self):
        self.lines = claude_section("Coaching principles")
        self.text = flat(self.lines)

    def test_every_line_with_a_number_cites_a_claim(self):
        uncited = [line for line in self.lines if re.search(r"[0-9]", line) and "rn:" not in line]
        self.assertEqual(uncited, [])

    def test_every_reference_in_the_section_resolves(self):
        notes = research.load_notes(REPO_ROOT)
        refs = research.REF.findall(self.text)
        self.assertTrue(refs)
        unresolved = [f"rn:{note}.{n}" for note, n in refs if research.resolve(f"rn:{note}.{n}", notes) is None]
        self.assertEqual(unresolved, [])

    def test_no_local_claim_is_cited(self):
        self.assertNotIn("rn:local-", self.text)

    def test_covers_the_principles_the_evidence_calls_for(self):
        for lead, phrase in (
            ("**Frequency**", "per-session"),
            ("**Fatigue management & deloads**", "triggered by fatigue"),
            ("**Minimum and maintenance dose**", "maintenance"),
            ("**Return after a layoff**", "return week"),
            ("**Concurrent training**", "lift first"),
            ("**Prescription validity**", "exposure"),
            ("**Reachable targets**", "delivered"),
        ):
            with self.subTest(principle=lead):
                self.assertIn(lead, self.text)
                bullet = self.text.split(lead, 1)[1].split(" - **", 1)[0]
                self.assertIn(phrase, bullet)


class ResearchPracticeTest(unittest.TestCase):
    def test_names_the_procedure_and_its_rules(self):
        text = flat(claude_section("Researching current best practice"))
        for needle in (
            "python3 -m coach research status",
            "research/local/",
            "research render",
            "rn:",
            "expired",
            "`updates`",
            "contradicts rn:<ref>: <reason>",
            DISCLAIMER,
            "qualified professional",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class SkillsPointAtTheProcedureTest(unittest.TestCase):
    def test_goals_and_new_program_use_the_research_procedure(self):
        for skill in ("goals", "new-program"):
            with self.subTest(skill=skill):
                text = flat(_read(f".claude/skills/{skill}/SKILL.md").splitlines())
                self.assertTrue('"Researching current best practice"' in text, skill)
                self.assertNotIn("cite sources", text)

    def test_deep_check_in_lists_expired_areas(self):
        text = flat(_read(".claude/skills/check-in/SKILL.md").splitlines())
        deep_tier = text.split("**Deep tier** — all of the above, plus:", 1)[1].split("**Both tiers", 1)[0]
        self.assertIn("python3 -m coach research status", deep_tier)
        self.assertIn("expired", deep_tier)
        self.assertIn("local note", deep_tier)


class NoInlineCitationsTest(unittest.TestCase):
    def test_framework_files_cite_claims_not_sources(self):
        tracked = _tracked_files()
        if tracked is None:
            self.skipTest("needs the template's git checkout")
        offending = []
        for path in tracked:
            if path.startswith(CITATION_FREE_EXEMPT_DIRS):
                continue
            try:
                text = (REPO_ROOT / path).read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            offending += [f"{path}: {m}" for m in INLINE_CITATION_MARKERS if m in text]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
