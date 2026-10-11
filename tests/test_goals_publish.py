"""/goals' close-out: approved nutrition edits leave current published pages, or an honest unfinished close-out."""

import re
import shutil
import unittest

from tests.support.config_edit import apply
from tests.support.skills import flat, skill_text, step_text
from tests.test_pages import WEEKLY, PublishCase, SetupCase, git

COMMAND = re.compile(r"`python3 -m coach ([a-z]+ [a-z]+)[^`]*`")
CLOSE_OUT = ["config validate", "pages render", "pages publish", "check --only"]
NUTRITION = """
[nutrition]
enabled = true
app = "none"
phase = "cut"
target_rate_per_week = -0.5
goal_weight = 72.0

[nutrition.protein]
reference_basis = "bodyweight"
reference_mass = 80.0
floor_g = 120
target_g = 130
stretch_g = 175
floor_since = 2026-10-12
floor_step_g = 10
"""


def close_out_commands():
    """The coach commands goals/publish.md runs, in the order it first names them."""
    found = []
    for name in COMMAND.findall(flat(step_text("goals", "publish.md"))):
        if name not in found:
            found.append(name)
    return found


def goals_edit(config_text):
    """The approved step-9 edit: recomp at 110 g becomes a cut at 120 g."""
    text = apply(config_text, {"nutrition": {"phase": "cut", "target_rate_per_week": -0.5}})
    for old, new in (("floor_g = 110", "floor_g = 120"), ("floor_since = 2026-09-28", "floor_since = 2026-10-15")):
        assert old in text, old
        text = text.replace(old, new)
    return text


class CloseOutDocsTest(unittest.TestCase):
    def test_goals_validates_renders_publishes_then_checks_freshness(self):
        self.assertEqual(close_out_commands()[:2], ["config validate", "pages render"])
        self.assertIn("pages publish", close_out_commands())
        doc = flat(step_text("goals", "publish.md"))
        self.assertIn("python3 -m coach check --only pages_fresh", doc)
        self.assertLess(doc.index("pages publish"), doc.rindex("check --only pages_fresh"))
        for needle in ("brief_overlay", "approved", "exits 3", "exits 4", "not done", "never `git add -A`"):
            self.assertIn(needle, doc)

    def test_goals_and_setup_send_their_close_out_through_the_publish_step(self):
        goals = flat(skill_text("goals").split("[publish.md]")[0])
        self.assertIn("## 10. Publish the pages", goals)
        setup = flat(skill_text("setup"))
        self.assertIn("goals/publish.md", setup)
        close_out = setup[setup.index("## 7. Close out"):]
        self.assertIn("check --only pages_fresh", close_out)
        self.assertIn("not done", close_out)


@unittest.skipIf(shutil.which("git") is None, "needs git")
class GoalsCloseOutTest(PublishCase):
    """The valid instance's week, published, then a /goals pass changes its phase, rate and floor."""

    def setUp(self):
        super().setUp()
        self.approve()
        self.publish()
        self.assertIn("Recomp", self.remote_page("this-week.md"))
        self.published_head = git(self.root, "rev-parse", "HEAD", env=self.git_env).strip()
        config = self.root / "config.toml"
        config.write_text(goals_edit(config.read_text(encoding="utf-8")), encoding="utf-8")
        with open(self.root / "profile.md", "a", encoding="utf-8") as handle:
            handle.write("\n## Nutrition & goals\n\nCut to 75 kg at 0.5 kg a week.\n")

    def fresh(self, expect=0):
        return [row["status"] for row in self.check("pages_fresh", expect=expect)]

    def run_close_out(self, expect_publish=0):
        """goals/publish.md's commands, in its order; the publish envelope."""
        results = {}
        for name in close_out_commands():
            if name == "config validate":
                self.coach("config", "validate")
            elif name == "pages render":
                results["render"] = self.coach("pages", "render")["data"]
            elif name == "pages publish":
                overlay_id = results["render"]["brief_overlay"]["id"]
                results["publish"] = self.coach("pages", "publish", "--overlay", overlay_id, expect=expect_publish)
        return results

    def test_the_edit_leaves_the_pages_stale_until_the_close_out_republishes_them(self):
        self.assertIn("fail", self.fresh(expect=1))
        results = self.run_close_out()
        self.assertEqual(results["render"]["brief_overlay"], {"id": WEEKLY, "approved": True})
        self.assertTrue(results["publish"]["data"]["pushed"])
        self.assertEqual(set(self.fresh()), {"pass"})
        brief = self.remote_page("this-week.md")
        self.assertIn(" · Cut · ", brief.splitlines()[1])
        self.assertIn("Food: protein floor 120 g", brief)
        self.assertNotIn("Recomp", brief)
        self.assertIn(" · Cut · ", self.remote_page("README.md"))

    def test_the_republish_commits_only_the_published_files(self):
        self.run_close_out()
        files = git(self.root, "diff", "--name-only", self.published_head, "HEAD", env=self.git_env).split()
        self.assertTrue(set(files) <= set(self.PUBLISHED), files)
        self.assertIn("this-week.md", files)
        changed = git(self.root, "status", "--porcelain", env=self.git_env)
        self.assertIn(" M config.toml", changed)
        self.assertIn(" M profile.md", changed)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only", env=self.git_env), "")
        self.assertIn('phase = "recomp"', git(self.remote, "show", "main:config.toml", env=self.git_env))

    def test_without_a_remote_the_publish_refuses_with_its_fix_and_commits_nothing(self):
        git(self.root, "remote", "remove", "origin", env=self.git_env)
        results = self.run_close_out(expect_publish=3)
        message = results["publish"]["error"]["message"]
        self.assertIn("no upstream", message)
        self.assertIn("git push -u", message)
        self.assertEqual(git(self.root, "rev-parse", "HEAD", env=self.git_env).strip(), self.published_head)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only", env=self.git_env), "")
        self.assertEqual(set(self.fresh()), {"pass"})

    def test_render_names_an_unapproved_brief_overlay_so_publishing_waits(self):
        self.edit_json(f"data/overlays/{WEEKLY}.json", lambda doc: doc.update(focus="Edited after approval"))
        data = self.coach("pages", "render")["data"]
        self.assertEqual(data["brief_overlay"], {"id": WEEKLY, "approved": False})
        self.assertIn("edited after approval", self.publish(expect=3)["error"]["message"])
        self.assertEqual(git(self.root, "rev-parse", "HEAD", env=self.git_env).strip(), self.published_head)

    def test_render_reports_no_brief_overlay_when_none_covers_the_week(self):
        (self.root / "data" / "overlays" / f"{WEEKLY}.json").unlink()
        self.assertIsNone(self.coach("pages", "render")["data"]["brief_overlay"])


@unittest.skipIf(shutil.which("git") is None, "needs git")
class SetupGoalsCloseOutTest(SetupCase):
    def test_setup_does_not_finish_on_pages_from_before_goals(self):
        overlay_id = self.first_publish({"hevy": {"enabled": False},
                                         "athlete": {"available_days": ["mon", "wed", "fri"]}})
        self.assertNotIn("Food:", self.remote_page("this-week.md"))
        with open(self.root / "config.toml", "a", encoding="utf-8") as handle:
            handle.write(NUTRITION)
        self.coach("config", "validate")
        render = self.coach("pages", "render")
        self.assertEqual(render["brief_overlay"], {"id": overlay_id, "approved": True})
        self.assertTrue(self.coach("pages", "publish", "--overlay", overlay_id)["pushed"])
        results = self.coach("check", "--only", "pages_fresh")["results"]
        self.assertEqual({row["status"] for row in results}, {"pass"})
        brief = self.remote_page("this-week.md")
        self.assertIn(" · Cut · ", brief.splitlines()[1])
        self.assertIn("Food: protein floor 120 g", brief)
        self.assertIn(overlay_id, self.remote_page("this-week-sheets.md"))
        self.assertIn("config.toml", self.local_git("diff", "--name-only"))


if __name__ == "__main__":
    unittest.main()
