"""CLAUDE.md's coaching principles and research practice cite research-note claims (contract C28)."""

import json
import re
import subprocess
import unittest

from coach import checkin, research
from tests.support import REPO_ROOT
from tests.support.skills import skill_text, step_text

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


class HeuristicLabelsTest(unittest.TestCase):
    def setUp(self):
        self.notes = research.load_notes(REPO_ROOT)

    def claim(self, ref):
        return research.resolve(ref, self.notes)

    def test_return_bands_and_illness_rule_are_labelled_heuristics(self):
        bullet = text_of_bullet(flat(claude_section("Coaching principles")), "**Return after a layoff**")
        bands, illness = bullet.split("**Illness adds:**", 1)
        for part, ref in ((bands, "rn:detraining-return.3"), (illness, "rn:detraining-return.4")):
            with self.subTest(ref=ref):
                self.assertIn("coaching heuristic", part)
                self.assertIn(ref, part)
                self.assertEqual(self.claim(ref).basis, "heuristic")

    def test_return_bands_cite_the_long_layoff_source(self):
        self.assertIn("mujika-padilla-2000", self.claim("rn:detraining-return.3").sources)

    def test_illness_rule_is_for_mild_illness(self):
        claim = self.claim("rn:detraining-return.4")
        self.assertIn("mild", claim.text)
        self.assertIn("snyders-2022", claim.sources)

    def test_deep_review_threshold_cites_its_claim(self):
        claim = self.claim("rn:deloads.12")
        self.assertEqual(claim.basis, "heuristic")
        self.assertIn("42 days", claim.text)
        check_in = text_of_bullet(flat(_read("CLAUDE.md").splitlines()), "**`/check-in`**")
        self.assertIn("rn:deloads.12", check_in)
        self.assertIn("rn:deloads.12", skill_text("check-in"))
        self.assertEqual(checkin.DEEP_AFTER_DAYS, 42)
        self.assertIn("`DEEP_AFTER_DAYS` after the last one, a coaching heuristic (rn:deloads.12)",
                      flat(checkin.__doc__.splitlines()))

    def test_deload_timing_claim_accepts_planned_or_fatigue_triggered_deloads(self):
        claim = self.claim("rn:deloads.1")
        self.assertEqual(claim.basis, "consensus")
        self.assertIn("pre-planned or triggered by fatigue", claim.text)
        self.assertIn("ceiling", claim.text)

    def test_ceiling_is_a_heuristic_counted_in_completed_hard_weeks(self):
        claim = self.claim("rn:deloads.3")
        self.assertEqual(claim.basis, "heuristic")
        self.assertEqual(set(claim.sources), {"bell-2023", "rogerson-2024"})
        for phrase in ("default 6 completed hard weeks", "4 to 8", "calendar weeks"):
            self.assertIn(phrase, claim.text)

    def test_deload_rules_are_labelled_heuristics(self):
        text = flat(claude_section("Coaching principles"))
        bullet = text.split("**Fatigue management & deloads**", 1)[1].split("**Minimum and maintenance dose**", 1)[0]
        labels = bullet.split("These rules are coaching heuristics, not research cut-offs.", 1)[1]
        for rule, refs in (
            ("the 75 % and 50 % lines", ("rn:deloads.2",)),
            ("the hard-week session gate", ("rn:deloads.11",)),
            ("the ceiling counted in completed hard weeks", ("rn:deloads.3",)),
            ("the four fatigue triggers with the two-trigger rule", ("rn:autoregulation.4", "rn:deloads.5")),
            ("the three-week skip rule", ("rn:deloads.4",)),
        ):
            with self.subTest(rule=rule):
                self.assertIn(f"{rule} ({', '.join(refs)})", labels)
                for ref in refs:
                    self.assertEqual(self.claim(ref).basis, "heuristic")

    def test_standard_deload_cites_its_claim_as_a_heuristic(self):
        text = flat(step_text("program-week", "compute.md").splitlines())
        sentence = next(s for s in text.split(". ") if "(rn:deloads.9)" in s)
        self.assertIn("RPE 6", sentence)
        self.assertIn("coaching heuristic", sentence)
        self.assertEqual(self.claim("rn:deloads.9").basis, "heuristic")

    def test_rpe_accuracy_claim_no_longer_rests_on_training_experience(self):
        retired = research.find_claim("rn:autoregulation.3", self.notes)
        self.assertEqual(retired.status, "retired")
        self.assertEqual(retired.superseded_by, "rn:autoregulation.7")
        claim = self.claim("rn:autoregulation.7")
        self.assertEqual((claim.basis, claim.confidence), ("heuristic", "low"))
        self.assertEqual(set(claim.sources), {"halperin-2022", "zourdos-2016", "helms-2016"})
        self.assertIn("near failure", claim.text)
        cites = json.loads(_read("coach/starters/rpe-full-body-3.json"))["cites"]
        self.assertIn("rn:autoregulation.7", cites)
        citing_retired = [f"{c.path}:{c.line}" for c in research.scan_citations(REPO_ROOT, self.notes)
                          if c.ref == "rn:autoregulation.3"]
        self.assertEqual(citing_retired, [])


def text_of_bullet(text, lead):
    return text.split(lead, 1)[1].split(" - **", 1)[0]


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
                text = flat(skill_text(skill).splitlines())
                self.assertTrue('"Researching current best practice"' in text, skill)
                self.assertNotIn("cite sources", text)

    def test_deep_check_in_lists_expired_areas(self):
        text = flat(skill_text("check-in").splitlines())
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
