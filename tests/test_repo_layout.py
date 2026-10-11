"""Template repo rules: instance namespaces, ignores and sync exclusions (contract C6)."""

import fnmatch
import subprocess
import unittest

from tests.support import REPO_ROOT

# Paths the template never tracks, so /framework-sync can never write them.
# An item that adds an instance namespace adds it here.
INSTANCE_NAMESPACES = [
    "config.toml",
    "data/**",
    "routine/**",
    "profile.md",
    "check-ins/**",
    "nutrition/**",
    "plugins/**",
    "research/local/**",
    "this-week.md",
    "progress.md",
    "this-week-sheets.md",
    ".coach/**",
    ".env",
]
NAMESPACE_EXCEPTIONS = ["check-ins/.gitkeep", "nutrition/.gitkeep"]


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)


def _in_git_checkout():
    try:
        return _git("rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except FileNotFoundError:
        return False


def in_namespace(path):
    if path in NAMESPACE_EXCEPTIONS:
        return False
    for pattern in INSTANCE_NAMESPACES:
        if pattern.endswith("/**"):
            if path.startswith(pattern[:-2]):
                return True
        elif fnmatch.fnmatchcase(path, pattern):
            return True
    return False


class NamespaceMatcherTest(unittest.TestCase):
    def test_matcher(self):
        self.assertTrue(in_namespace("config.toml"))
        self.assertTrue(in_namespace("data/overlays/2026-10-12-weekly.json"))
        self.assertTrue(in_namespace("check-ins/2026-10-11.md"))
        self.assertTrue(in_namespace(".coach/cache/hevy/meta.json"))
        self.assertFalse(in_namespace("check-ins/.gitkeep"))
        self.assertFalse(in_namespace("tests/fixtures/instances/valid/config.toml"))
        self.assertFalse(in_namespace("config.example.toml"))
        self.assertFalse(in_namespace("research/deloads.md"))


@unittest.skipUnless(_in_git_checkout(), "needs the template's git checkout")
class TemplateGitTest(unittest.TestCase):
    def test_no_instance_namespace_is_tracked(self):
        tracked = _git("ls-files").stdout.splitlines()
        self.assertTrue(tracked)
        self.assertEqual([path for path in tracked if in_namespace(path)], [])

    def test_gitignore_rules(self):
        for path in (".coach/cache/hevy/meta.json", "coach/__pycache__/cli.cpython-311.pyc", "coach/x.pyc"):
            with self.subTest(path=path):
                self.assertEqual(_git("check-ignore", "-q", "--no-index", path).returncode, 0, path)

    def test_fixture_coach_dirs_stay_tracked(self):
        result = _git("check-ignore", "-q", "--no-index", "tests/fixtures/instances/valid/.coach/x")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)


class FrameworkSyncTest(unittest.TestCase):
    def test_skill_excludes_tests(self):
        text = (REPO_ROOT / ".claude" / "skills" / "framework-sync" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`tests/**`", text)
        self.assertIn("`docs/**`", text)


if __name__ == "__main__":
    unittest.main()
