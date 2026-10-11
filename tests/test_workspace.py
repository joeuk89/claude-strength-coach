"""Fresh-copy identity through the documented local Git bootstrap."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import status, workspace
from tests.support import VALID, run_cli
from tests.support.git import git
from tests.test_hooks import context_of, run_hook, session_input
from tests.test_status import sections, text


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def git(self, root, *args):
        git(root, *args)

    def test_template_clone_bootstrap(self):
        source = self.root / "framework"
        source.mkdir()
        self.git(source, "init", "-q")
        (source / "tests").mkdir()
        (source / "tests" / "example.md").write_text("Bundled fixture\n")
        self.git(source, "add", "tests")
        self.git(source, "commit", "-qm", "Framework fixture")
        self.git(source, "remote", "add", "origin", "https://github.com/joeuk89/claude-strength-coach.git")
        self.assertEqual(status.instance_kind(source), status.TEMPLATE)
        self.assertIsNone(run_hook("sessionstart", source, session_input())[1])

        athlete = self.root / "athlete"
        self.git(self.root, "clone", "-q", str(source), str(athlete))
        self.assertTrue((athlete / "tests").is_dir())
        self.assertEqual(status.instance_kind(athlete), status.UNINITIALISED)
        self.git(athlete, "remote", "set-url", "origin", "git@github.com:fixture/my-training.git")
        self.assertEqual(status.instance_kind(athlete), status.UNINITIALISED)
        self.assertIn("run /setup", context_of(run_hook("sessionstart", athlete, session_input())[1]))

        self.git(athlete, "remote", "set-url", "origin", "git@github.com:joeuk89/claude-strength-coach.git")
        self.assertEqual(status.instance_kind(athlete), status.TEMPLATE)
        for unknown in ("", "unknown"):
            self.git(athlete, "config", "--local", "coach.workspace", unknown)
            self.assertEqual(status.instance_kind(athlete), status.UNINITIALISED)
            self.assertIn("run /setup", context_of(run_hook("sessionstart", athlete, session_input())[1]))
        self.git(athlete, "config", "--local", "coach.workspace", "athlete")
        self.assertEqual(status.instance_kind(athlete), status.UNINITIALISED)
        self.assertIn("run /setup", context_of(run_hook("sessionstart", athlete, session_input())[1]))

    def test_local_file_copy_bootstrap(self):
        copy = self.root / "copy"
        (copy / "tests").mkdir(parents=True)
        self.git(copy, "init", "-q")
        self.git(copy, "config", "--local", "coach.workspace", "athlete")
        self.assertEqual(status.instance_kind(copy), status.UNINITIALISED)
        self.assertIn("run /setup", context_of(run_hook("sessionstart", copy, session_input())[1]))

    def test_setup_files_take_precedence_and_missing_artifact_is_named(self):
        self.git(self.root, "init", "-q")
        self.git(self.root, "config", "--local", "coach.workspace", "template")
        (self.root / "tests").mkdir()
        for present, missing in (("config.toml", "profile.md"), ("profile.md", "config.toml")):
            with self.subTest(present=present):
                shutil.copyfile(VALID / present, self.root / present)
                code, envelope, _ = run_cli(["--root", str(self.root), "status"])
                self.assertEqual(code, 0)
                self.assertEqual(envelope["data"]["instance"], status.UNINITIALISED)
                self.assertIn(missing, text(sections(envelope)["instance"]))
                (self.root / present).unlink()
        for name in ("config.toml", "profile.md"):
            shutil.copyfile(VALID / name, self.root / name)
        self.assertEqual(status.instance_kind(self.root), status.INSTANCE)

    def test_unknown_copy_does_not_depend_on_tests_or_parent_git(self):
        self.git(self.root, "init", "-q")
        self.git(self.root, "config", "--local", "coach.workspace", "template")
        child = self.root / "copy"
        (child / "tests").mkdir(parents=True)
        self.assertEqual(status.instance_kind(child), status.UNINITIALISED)
        (child / ".git").mkdir()
        self.assertFalse(workspace.is_template(child))
        (child / ".git" / "objects").mkdir()
        self.assertFalse(workspace.is_template(child))
        self.assertEqual(status.instance_kind(child), status.UNINITIALISED)
        with mock.patch("coach.workspace.subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(workspace.is_template(self.root))
        with mock.patch("coach.workspace.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 2)):
            self.assertFalse(workspace.is_template(self.root))

    def test_inherited_git_environment_cannot_redirect_identity(self):
        template = self.root / "template"
        copy = self.root / "copy"
        for repo in (template, copy):
            repo.mkdir()
            self.git(repo, "init", "-q")
        self.git(template, "config", "--local", "coach.workspace", "template")
        redirect = {"GIT_DIR": str(template / ".git"), "GIT_COMMON_DIR": str(template / ".git"),
                    "GIT_WORK_TREE": str(template)}
        for name, value in redirect.items():
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: value}):
                self.assertFalse(workspace.is_template(copy))
        with mock.patch.dict(os.environ, redirect):
            self.assertFalse(workspace.is_template(copy))

    def test_origin_identity_uses_exact_repository(self):
        self.git(self.root, "init", "-q")
        self.git(self.root, "remote", "add", "origin", "unused")
        for origin, expected in (
            ("ssh://git@github.com/joeuk89/claude-strength-coach.git", True),
            ("https://github.com/joeuk89/claude-strength-coach/", True),
            ("https://github.com/fixture/claude-strength-coach.git", False),
            ("https://github.com/joeuk89/claude-strength-coach-copy.git", False),
            ("https://github.com.example/joeuk89/claude-strength-coach.git", False),
        ):
            with self.subTest(origin=origin):
                self.git(self.root, "remote", "set-url", "origin", origin)
                self.assertEqual(workspace.is_template(self.root), expected)
