import re
import unittest

from coach import research
from tests.support import INSTANCES, REPO_ROOT, run_cli
from tests.support.history import HistoryCase


class RunnerResearchTest(unittest.TestCase):
    def test_notes_are_discoverable_with_current_sourced_claims(self):
        code, envelope, stderr = run_cli(
            ["--root", str(REPO_ROOT), "research", "status", "--kind", "template"],
            env={"COACH_NOW": "2026-10-11T18:00:00Z"})
        self.assertEqual(code, 0, stderr)
        rows = {row["id"]: row for row in envelope["data"]["notes"]}
        notes = research.load_notes(REPO_ROOT)
        for note_id in ("strength-for-running", "endurance-fuelling"):
            with self.subTest(note=note_id):
                self.assertEqual(rows[note_id]["status"], "current")
                self.assertEqual(rows[note_id]["claims"], 3)
                for n in range(1, 4):
                    claim = research.resolve(f"rn:{note_id}.{n}", notes)
                    self.assertIsNotNone(claim)
                    if claim.basis != "heuristic":
                        self.assertTrue(claim.sources)

    def test_workflows_reach_shared_review_only_under_running_condition(self):
        for rel in ("goals/plan.md", "setup/program.md", "check-in/analyze.md"):
            path = REPO_ROOT / ".claude/skills" / rel
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(step=rel):
                self.assertRegex(text, re.compile(
                    r"When an outside running plan or endurance event is relevant, consult "
                    r"\[runner review\]\(([^)]+)\).*?Otherwise skip runner-specific "
                    r"research and fuelling questions\."))
                target = re.search(r"\[runner review\]\(([^)]+)\)", text).group(1)
                self.assertTrue((path.parent / target).is_file())
        citations = research.scan_citations(REPO_ROOT)
        reached = {c.ref for c in citations if c.path == "reference/runner-review.md" and c.resolved}
        self.assertEqual(reached, {f"rn:{note}.{n}"
                                  for note in ("strength-for-running", "endurance-fuelling")
                                  for n in range(1, 4)})


class NonRunnerCheckinTest(HistoryCase):
    base = INSTANCES / "checkin"

    def test_non_runner_card_has_no_fuelling_interview_or_target_write(self):
        config = self.root / "config.toml"
        text = config.read_text(encoding="utf-8")
        self.assertIn("[activity]\nenabled = true", text)
        config.write_text(text.replace("[activity]\nenabled = true", "[activity]\nenabled = false"),
                          encoding="utf-8")
        (self.root / "profile.md").write_text(
            "# Synthetic strength athlete\n\nStrength training only; no running plan or event.\n",
            encoding="utf-8")
        before = config.read_bytes()
        card = self.coach("checkin", "prepare")["data"]
        self.assertNotIn("fuelling", card["text"].lower())
        self.assertNotIn("carbohydrate", card["text"].lower())
        self.assertEqual(config.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
