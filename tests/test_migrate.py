"""The migration runner: step discovery, status, plan, run with backup, validation and staging (contract C7, C16)."""

import json
import subprocess
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from coach import jsonio, migrate, overlay
from tests.support import REPO_ROOT, VALID, run_cli
from tests.test_cli import EnvelopeMixin
from tests.test_program import Instance

OVERLAY = "data/overlays/2026-10-12-weekly.json"
NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
BACKUP = ".coach/backups/20261011T180000Z"
CURRENT = overlay.current_version()
NEXT = CURRENT + 1
ADD_NOTE = f"""
    DOC = "overlay"
    FROM = {CURRENT}
    TO = {NEXT}


    def migrate(doc):
        doc["note"] = None
        return doc


    def notes(before, after):
        return [f"{{before['id']}}: note added"]
"""
BREAK_KIND = f"""
    DOC = "overlay"
    FROM = {CURRENT}
    TO = {NEXT}


    def migrate(doc):
        doc["kind"] = "bogus"
        return doc
"""


class TempRegistry:
    """A migrations package and schema directory in a temp dir, with overlay one version past the current."""

    def __init__(self, steps=None, target=NEXT, files=("data/overlays/*.json",)):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.package = base / "migrations"
        self.schemas = base / "schemas"
        doc_dir = self.package / "overlay"
        doc_dir.mkdir(parents=True)
        (self.package / "__init__.py").write_text("", encoding="utf-8")
        (doc_dir / "__init__.py").write_text(f"FILES = {tuple(files)!r}\n", encoding="utf-8")
        for name, source in (steps if steps is not None else {"0001_add_note.py": ADD_NOTE}).items():
            (doc_dir / name).write_text(textwrap.dedent(source), encoding="utf-8")
        self.schemas.mkdir()
        schema = jsonio.load_schema("overlay")
        schema["properties"]["schema_version"] = {"const": target}
        schema["properties"]["note"] = {"type": ["string", "null"]}
        (self.schemas / "overlay.schema.json").write_text(json.dumps(schema), encoding="utf-8")

    def __enter__(self):
        return migrate.Registry.discover(self.package, self.schemas)

    def __exit__(self, *exc):
        self._tmp.cleanup()


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True,
    ).stdout


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts}


class DiscoveryTest(unittest.TestCase):
    def test_framework_registry_owns_the_json_documents(self):
        reg = migrate.registry()
        self.assertEqual(sorted(reg.documents), ["annotations", "decisions", "exercise_library", "followups",
                                               "history_month", "niggles", "overlay", "program", "state"])
        self.assertEqual(reg.documents["program"].files, ("data/program.json",))
        for document in reg.documents.values():
            with self.subTest(document=document.name):
                self.assertEqual(document.target, 1 + len(document.steps))

    def test_steps_load_from_a_package(self):
        with TempRegistry() as reg:
            steps = reg.documents["overlay"].steps
        self.assertEqual([(s.name, s.from_version, s.to_version) for s in steps], [("overlay/0001_add_note", CURRENT, NEXT)])

    def assert_discovery_fails(self, steps, text, target=NEXT):
        with self.assertRaises(migrate.RegistryError) as caught:
            with TempRegistry(steps, target=target):
                pass
        self.assertIn(text, str(caught.exception))

    def test_a_step_must_add_one_version(self):
        self.assert_discovery_fails({"0001_jump.py": ADD_NOTE.replace(f"TO = {NEXT}", f"TO = {NEXT + 1}")}, "FROM + 1", target=NEXT + 1)

    def test_doc_must_match_its_directory(self):
        self.assert_discovery_fails({"0001_x.py": ADD_NOTE.replace('DOC = "overlay"', 'DOC = "program"')},
                                    "overlay")

    def test_two_steps_from_one_version(self):
        self.assert_discovery_fails({"0001_a.py": ADD_NOTE, "0002_b.py": ADD_NOTE}, "two steps")

    def test_step_past_the_schema_version(self):
        self.assert_discovery_fails({"0001_a.py": ADD_NOTE}, "schema", target=CURRENT)

    def test_step_file_name(self):
        self.assert_discovery_fails({"add_note.py": ADD_NOTE}, "NNNN_")


class StatusAndPlanTest(unittest.TestCase):
    def test_status_on_the_valid_instance(self):
        rows = migrate.status(VALID)
        paths = {row["path"]: row for row in rows}
        expected = {"data/program.json": 2, "data/state.json": 3, "data/exercises.json": 1, OVERLAY: 2}
        for path, version in expected.items():
            with self.subTest(path=path):
                self.assertEqual(paths[path]["version"], version)
                self.assertEqual(paths[path]["target"], version)
                self.assertEqual(paths[path]["state"], "current")

    def test_plan_lists_the_step(self):
        with TempRegistry() as reg:
            entries, problems = migrate.plan(VALID, reg)
        self.assertEqual(problems, [])
        self.assertEqual(entries, [{"path": OVERLAY, "doc": "overlay", "from": CURRENT, "to": NEXT,
                                    "steps": ["overlay/0001_add_note"]}])

    def test_a_missing_step_is_a_problem(self):
        step = ADD_NOTE.replace(f"FROM = {CURRENT}", f"FROM = {NEXT}").replace(f"TO = {NEXT}", f"TO = {NEXT + 1}")
        with TempRegistry({"0002_later.py": step}, target=NEXT + 1) as reg:
            entries, problems = migrate.plan(VALID, reg)
        self.assertEqual(entries, [])
        self.assertEqual(problems[0]["path"], OVERLAY)
        self.assertIn(f"no step from version {CURRENT}", problems[0]["message"])

    def test_a_newer_file_is_a_problem(self):
        with Instance() as root:
            doc = json.loads((root / OVERLAY).read_text(encoding="utf-8"))
            doc["schema_version"] = 5
            (root / OVERLAY).write_text(json.dumps(doc), encoding="utf-8")
            rows = {row["path"]: row for row in migrate.status(root)}
            _, problems = migrate.plan(root)
        self.assertEqual(rows[OVERLAY]["state"], "ahead")
        self.assertIn("/framework-sync", problems[0]["message"])


class RunTest(unittest.TestCase):
    def test_run_backs_up_writes_and_reports(self):
        with Instance() as root, TempRegistry() as reg:
            original = (root / OVERLAY).read_bytes()
            report = migrate.run(root, dry_run=False, now=datetime(2026, 10, 11, 18, tzinfo=timezone.utc), reg=reg)
            self.assertEqual((root / BACKUP / OVERLAY).read_bytes(), original)
            upgraded = json.loads((root / OVERLAY).read_text(encoding="utf-8"))
        self.assertEqual(upgraded["schema_version"], NEXT)
        self.assertIsNone(upgraded["note"])
        self.assertEqual(report["backup"], BACKUP)
        self.assertEqual(report["notes"], ["2026-10-12-weekly: note added"])

    def test_nothing_to_do(self):
        report = migrate.run(VALID, dry_run=False, now=datetime(2026, 10, 11, tzinfo=timezone.utc))
        self.assertEqual(report["files"], [])
        self.assertIsNone(report["backup"])


class MigrateCommandTest(EnvelopeMixin, unittest.TestCase):
    def run_with(self, reg, code, *argv):
        with mock.patch.object(migrate, "registry", return_value=reg):
            if code == 0:
                return self.run_ok(*argv, env=NOW)
            return self.run_fail(code, *argv, env=NOW)[0]

    def test_status_lists_each_owned_file(self):
        data = self.run_ok("--root", str(VALID), "migrate", "status")
        listed = {row["path"]: (row["version"], row["target"]) for row in data["files"]}
        self.assertEqual(listed["data/program.json"], (2, 2))
        self.assertEqual(listed[OVERLAY], (CURRENT, CURRENT))
        self.assertEqual(data["behind"], 0)

    def test_status_with_a_pending_step(self):
        with TempRegistry() as reg:
            data = self.run_with(reg, 0, "--root", str(VALID), "migrate", "status")
        row = next(r for r in data["files"] if r["path"] == OVERLAY)
        self.assertEqual((row["version"], row["target"], row["state"]), (CURRENT, NEXT, "behind"))
        self.assertEqual(data["behind"], 1)

    def test_dry_run_lists_the_step_and_changes_nothing(self):
        with Instance() as root, TempRegistry() as reg:
            before = snapshot(root)
            data = self.run_with(reg, 0, "--root", str(root), "migrate", "run", "--dry-run")
            self.assertEqual(snapshot(root), before)
        self.assertEqual(data["files"][0]["steps"], ["overlay/0001_add_note"])
        self.assertFalse(data["written"])
        self.assertIsNone(data["backup"])

    def test_run_stages_without_committing(self):
        with Instance() as root, TempRegistry() as reg:
            git(root, "init", "-q")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "baseline")
            original = (root / OVERLAY).read_bytes()
            data = self.run_with(reg, 0, "--root", str(root), "migrate", "run")
            staged = git(root, "diff", "--cached", "--name-only").split()
            commits = git(root, "rev-list", "--count", "HEAD").strip()
            self.assertEqual((root / BACKUP / OVERLAY).read_bytes(), original)
            self.assertEqual(json.loads((root / OVERLAY).read_text(encoding="utf-8"))["schema_version"], NEXT)
        self.assertEqual(staged, [OVERLAY])
        self.assertEqual(commits, "1")
        self.assertEqual(data["staged"], [OVERLAY])
        self.assertTrue(data["written"])

    def test_outside_git_it_writes_and_warns(self):
        with Instance() as root, TempRegistry() as reg:
            with mock.patch.object(migrate, "registry", return_value=reg):
                code, envelope, _ = run_cli(["--root", str(root), "migrate", "run"], env=NOW)
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["staged"], [])
        self.assertTrue(any("git" in w for w in envelope["warnings"]))

    def test_invalid_result_exits_1_and_leaves_files_as_the_backup(self):
        with Instance() as root, TempRegistry({"0001_break.py": BREAK_KIND}) as reg:
            before = snapshot(root)
            envelope = self.run_with(reg, 1, "--root", str(root), "migrate", "run")
            after = {k: v for k, v in snapshot(root).items() if not k.startswith(".coach/backups/")}
            backup = (root / BACKUP / OVERLAY).read_bytes()
            self.assertEqual(after, before)
            self.assertEqual((root / OVERLAY).read_bytes(), backup)
        self.assertEqual(envelope["error"]["code"], "validation")
        self.assertIn(f"{OVERLAY}: $.kind", [d["path"] for d in envelope["error"]["details"]])

    def test_invalid_result_under_dry_run_exits_1_too(self):
        with Instance() as root, TempRegistry({"0001_break.py": BREAK_KIND}) as reg:
            before = snapshot(root)
            self.run_with(reg, 1, "--root", str(root), "migrate", "run", "--dry-run")
            self.assertEqual(snapshot(root), before)

    def test_a_write_failure_restores_from_the_backup(self):
        with Instance() as root, TempRegistry() as reg:
            before = snapshot(root)
            def half_write(path, doc, dry_run):
                Path(path).write_text("{", encoding="utf-8")
                raise OSError("disk full")

            with mock.patch.object(jsonio, "write_doc", side_effect=half_write):
                with self.assertRaises(OSError):
                    migrate.run(root, dry_run=False, now=datetime(2026, 10, 11, 18, tzinfo=timezone.utc), reg=reg)
            after = {k: v for k, v in snapshot(root).items() if not k.startswith(".coach/backups/")}
        self.assertEqual(after, before)


class FrameworkSyncSkillTest(unittest.TestCase):
    def test_skill_runs_the_migration_and_stages(self):
        text = (REPO_ROOT / ".claude" / "skills" / "framework-sync" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("python3 -m coach migrate run --dry-run", text)
        self.assertIn("python3 -m coach migrate run", text)
        self.assertIn("stages", text)
        self.assertIn("never commits", text)


if __name__ == "__main__":
    unittest.main()
