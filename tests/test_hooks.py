"""The SessionStart and PostToolUse hooks, and their settings entries (contract C53)."""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import checks, hooks
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli
from tests.support.git import git

NOW = "2026-10-11T18:00:00Z"
ENV = {"COACH_NOW": NOW}
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
CONTRACT = REPO_ROOT / "docs" / "design" / "coach-contract.md"
STALE = INSTANCES / "program-stale-render"
SESSIONSTART = 'cd "$CLAUDE_PROJECT_DIR" && python3 -m coach hooks sessionstart'
POSTTOOLUSE = 'cd "$CLAUDE_PROJECT_DIR" && python3 -m coach hooks posttooluse'

# C6 paths with no PATH_MAP row, and why. An item that adds checks for one of
# these moves it into PATH_MAP.
NOT_MAPPED = {
    "data/archive/programs/<YYYY-MM-DD>/": "archived copies; nothing reads them",
    "data/history/<YYYY-MM>.json": "R-20 adds its checks",
    "data/history/annotations.json": "R-20 adds its checks",
    "data/decisions.json": "R-23a adds its checks",
    "data/followups.json": "R-27 adds its checks",
    "data/niggles.json": "R-27 adds its checks",
    "data/blocks.json": "R-31 adds its checks",
    "data/status-days.json": "R-43 adds its checks",
    "data/log/workouts.jsonl": "R-40c adds its checks",
    "nutrition/archive/": "frozen pre-R-33 plans",
    "this-week-sheets.md": "R-40c adds its checks",
    "plugins/<kind>/<name>.py": "code, tested by plugins test (R-23a)",
    "plugins/tests/test_<name>.py": "code, tested by plugins test (R-23a)",
    ".coach/cache/hevy/": "gitignored cache only hevy pull writes",
    ".coach/backups/<UTC timestamp>/": "gitignored backups",
    ".coach/proposals/<id>.json": "gitignored drafts a command checks when it reads them",
    ".coach/proposals/<id>.proposed.json": "gitignored drafts a command checks when it reads them",
    ".coach/proposals/<id>.meta.json": "gitignored drafts a command checks when it reads them",
    ".coach/plans/<week start>-<name>.json": "gitignored drafts a command checks when it reads them",
    ".coach/drafts/": "gitignored drafts a command checks when it reads them",
}


def session_input(source="startup"):
    return {"session_id": "s-1", "transcript_path": "/dev/null", "cwd": "/somewhere", "hook_event_name": "SessionStart",
            "source": source, "model": "claude"}


def edit_input(file_path, tool="Edit", cwd="/somewhere"):
    return {"session_id": "s-1", "transcript_path": "/dev/null", "cwd": cwd, "permission_mode": "default",
            "hook_event_name": "PostToolUse", "tool_name": tool,
            "tool_input": {"file_path": str(file_path), "old_string": "a", "new_string": "b"},
            "tool_response": {"filePath": str(file_path), "success": True}, "tool_use_id": "toolu_1"}


def copy_of(test, source):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name) / "instance"
    shutil.copytree(source, root)
    return root


def run_hook(event, root, payload):
    stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
    with mock.patch("sys.stdin", stdin):
        return run_cli(["--root", str(root), "hooks", event], env=ENV)


def run_entry(argv, payload=None):
    """`coach.__main__.run`, the entry point the hook commands go through, with its stdout and stderr."""
    from coach import __main__ as entry

    stdin = io.StringIO(json.dumps(payload if payload is not None else session_input()))
    stdout, stderr = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", stdin), mock.patch.dict(os.environ, ENV), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = entry.run(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def context_of(response):
    return response["hookSpecificOutput"]["additionalContext"]


def c6_paths():
    text = CONTRACT.read_text(encoding="utf-8")
    section = text[text.index("## C6."):text.index("## C7.")]
    found = []
    for row in section.splitlines():
        if not row.startswith("| `"):
            continue
        first_cell = row.split("|")[1]
        names = re.findall(r"`([^`]+)`", first_cell)
        base = names[0].rsplit("/", 1)[0] + "/" if "/" in names[0] else ""
        for name in names:
            found.append(name if "/" in name or not base else base + name)
    return found


def as_example(path):
    """A concrete instance path for a C6 path with placeholders."""
    example = re.sub(r"<[^>]+>", "x", path)
    return example + "x.json" if example.endswith("/") else example


class SessionStartTest(unittest.TestCase):
    def test_valid_instance_prints_the_status_lines(self):
        code, response, _ = run_hook("sessionstart", VALID, session_input())
        self.assertEqual(code, 0)
        self.assertEqual(response["hookSpecificOutput"]["hookEventName"], "SessionStart")
        text = context_of(response)
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 12)
        self.assertLessEqual(len(text), hooks.MAX_CHARS)
        self.assertEqual(lines[-1], "Detail: python3 -m coach status")
        self.assertIn("2026-10-12-weekly", text)

    def test_attention_lines_come_first(self):
        _, response, _ = run_hook("sessionstart", VALID, session_input())
        lines = context_of(response).splitlines()
        self.assertIn("No overlay is in force today", lines[1])
        self.assertLess(lines.index(next(l for l in lines if "no Hevy cache" in l)),
                        lines.index(next(l for l in lines if l.startswith("coach check:"))))

    def test_every_session_source(self):
        for source in ("startup", "resume", "clear", "compact", "fork"):
            with self.subTest(source=source):
                code, response, _ = run_hook("sessionstart", VALID, session_input(source))
                self.assertEqual(code, 0)
                self.assertTrue(context_of(response).endswith("Detail: python3 -m coach status"))

    def test_template_repo_prints_nothing(self):
        root = copy_of(self, VALID)
        (root / "profile.md").unlink()
        (root / "config.toml").unlink()
        git(root, "init", "-q")
        git(root, "config", "--local", "coach.workspace", "template")
        code, response, _ = run_hook("sessionstart", root, session_input())
        self.assertEqual((code, response), (0, None))

    def test_uninitialised_copy_says_run_setup(self):
        root = copy_of(self, VALID)
        (root / "profile.md").unlink()
        (root / "config.toml").unlink()
        code, response, _ = run_hook("sessionstart", root, session_input())
        self.assertEqual(code, 0)
        self.assertIn("run /setup", context_of(response))

    def test_unreadable_input_still_reports(self):
        code, response, _ = run_hook("sessionstart", VALID, "{not json")
        self.assertEqual(code, 0)
        self.assertIn("Detail: python3 -m coach status", context_of(response))

    def test_long_output_is_cut_to_twelve_lines_and_the_character_budget(self):
        from coach.status import Section

        many = [Section(f"s{n}", [f"line {n}.{k} " + "x" * 60 for k in range(3)]) for n in range(6)]
        text = hooks.context_text(many, __import__("datetime").date(2026, 10, 11))
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 12)
        self.assertLessEqual(len(text), hooks.MAX_CHARS)
        self.assertRegex(lines[-2], r"^\.\.\.and \d+ more lines\.$")
        self.assertEqual(lines[-1], hooks.DETAIL)

    def test_a_forced_exception_prints_one_unavailable_line(self):
        with mock.patch("coach.status.collect", side_effect=RuntimeError("boom")):
            code, response, _ = run_hook("sessionstart", VALID, session_input())
        self.assertEqual(code, 0)
        text = context_of(response)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn("unavailable", text)
        self.assertIn("RuntimeError", text)

    def test_python_3_10_exits_0_with_one_line(self):
        from coach import __main__ as entry

        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entry.run(["--root", str(VALID), "hooks", "sessionstart"], version_info=(3, 10, 14, "final", 0))
        self.assertEqual(code, 0)
        text = context_of(json.loads(stdout.getvalue()))
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn("3.11", text)
        self.assertIn("3.10.14", text)

    def test_a_failure_before_the_hook_runs_still_exits_0_with_one_line(self):
        for failure in (mock.patch("coach.commands.discover", side_effect=RuntimeError("broken command")),
                        mock.patch("coach.cli.main", return_value=9)):
            with self.subTest(failure=failure.attribute), failure:
                code, stdout, _ = run_entry(["--root", str(VALID), "hooks", "sessionstart"])
                self.assertEqual(code, 0)
                text = context_of(json.loads(stdout))
                self.assertEqual(len(text.splitlines()), 1)
                self.assertIn("unavailable", text)

    def test_the_entry_point_unavailable_line_matches_the_hook_module(self):
        from coach import __main__ as entry

        self.assertEqual(entry.unavailable_response("X: y"), hooks.session_response(hooks.unavailable_text("X: y")))

    def test_python_3_10_posttooluse_prints_nothing(self):
        from coach import __main__ as entry

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = entry.run(["hooks", "posttooluse"], version_info=(3, 10, 14, "final", 0))
        self.assertEqual((code, stdout.getvalue()), (0, ""))


class PostToolUseTest(unittest.TestCase):
    def test_equipment_profile_write_does_not_block(self):
        root = copy_of(self, VALID)
        profile = root / "profile.md"
        profile.write_text("Home only: adjustable dumbbells, 2–20 kg per hand in 2 kg steps.\n"
                           "dumbbells 5–40 kg per hand in 2.5 kg steps. Plates down to 1.25 kg\n"
                           "cables and dumbbells to 30 kg.\n", encoding="utf-8")
        code, response, _ = run_hook("posttooluse", root, edit_input(profile))
        self.assertEqual((code, response), (0, None))

    def test_hand_edited_routine_page_blocks_naming_the_check(self):
        root = copy_of(self, STALE)
        code, response, _ = run_hook("posttooluse", root, edit_input(root / "routine" / "session-a.md"))
        self.assertEqual(code, 0)
        self.assertEqual(response["decision"], "block")
        self.assertIn("routine/session-a.md failed routine_render_fresh", response["reason"])
        self.assertTrue(response["reason"].endswith("Fix the data file or re-render; don't leave it."))

    def test_overlay_template_id_the_library_gives_another_exercise_blocks(self):
        root = copy_of(self, VALID)
        overlay = root / "data" / "overlays" / "2026-10-12-weekly.json"
        text = overlay.read_text(encoding="utf-8")
        self.assertEqual(text.count('"F0000001"'), 1)
        overlay.write_text(text.replace('"F0000001"', '"F0000002"'), encoding="utf-8")
        code, response, _ = run_hook("posttooluse", root, edit_input(overlay))
        self.assertEqual(code, 0)
        self.assertEqual(response["decision"], "block")
        self.assertIn("failed overlay_library_consistency", response["reason"])

    def test_a_failure_before_the_hook_runs_prints_nothing(self):
        root = copy_of(self, STALE)
        with mock.patch("coach.commands.discover", side_effect=RuntimeError("broken command")):
            code, stdout, stderr = run_entry(["--root", str(root), "hooks", "posttooluse"],
                                             edit_input(root / "routine" / "session-a.md"))
        self.assertEqual((code, stdout), (0, ""))
        self.assertIn("broken command", stderr)

    def test_valid_instance_prints_nothing(self):
        for relative in ("routine/session-a.md", "data/program.json", "data/overlays/2026-10-12-weekly.json",
                         "check-ins/2026-10-11.md", "config.toml", "profile.md", "data/exercises.json"):
            with self.subTest(path=relative):
                code, response, _ = run_hook("posttooluse", VALID, edit_input(VALID / relative, tool="Write"))
                self.assertEqual((code, response), (0, None))

    def test_unmapped_and_outside_paths_print_nothing(self):
        for path in (VALID / "notes.txt", REPO_ROOT / "README.md", "/etc/hosts"):
            with self.subTest(path=path):
                code, response, _ = run_hook("posttooluse", VALID, edit_input(path))
                self.assertEqual((code, response), (0, None))

    def test_relative_path_resolves_against_the_hook_cwd(self):
        root = copy_of(self, STALE)
        code, response, _ = run_hook("posttooluse", root, edit_input("routine/session-a.md", cwd=str(root)))
        self.assertEqual(response["decision"], "block")

    def test_warning_only_becomes_additional_context(self):
        root = copy_of(self, VALID)
        (root / "check-ins" / "2026-10-04.md").write_text("# Check-in\n\nCap (rn:fixture-dose.9).\n",
                                                         encoding="utf-8")
        code, response, _ = run_hook("posttooluse", root, edit_input(root / "check-ins" / "2026-10-04.md"))
        self.assertEqual(code, 0)
        self.assertNotIn("decision", response)
        self.assertEqual(response["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("research_citations", context_of(response))

    def test_a_forced_exception_prints_nothing(self):
        root = copy_of(self, STALE)
        with mock.patch("coach.checks.run", side_effect=RuntimeError("boom")):
            code, response, stderr = run_hook("posttooluse", root, edit_input(root / "routine" / "session-a.md"))
        self.assertEqual((code, response), (0, None))
        self.assertEqual(len([l for l in stderr.splitlines() if "boom" in l]), 1)

    def test_unreadable_input_prints_nothing(self):
        code, response, _ = run_hook("posttooluse", VALID, "{not json")
        self.assertEqual((code, response), (0, None))

    def test_hooks_write_nothing_and_make_no_hevy_call(self):
        root = copy_of(self, STALE)
        before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        with mock.patch("coach.hevy.transport.from_env", side_effect=AssertionError("network")) as from_env, \
                mock.patch("coach.hevy.transport.UrllibTransport.request",
                           side_effect=AssertionError("network")) as request:
            run_hook("sessionstart", root, session_input())
            run_hook("posttooluse", root, edit_input(root / "routine" / "session-a.md"))
            run_hook("posttooluse", root, edit_input(root / "data" / "program.json"))
        from_env.assert_not_called()
        request.assert_not_called()
        self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)


class PathMapTest(unittest.TestCase):
    def test_every_mapped_check_is_registered(self):
        registered = {item.id for item in checks.discover()}
        for pattern, ids in hooks.PATH_MAP:
            with self.subTest(pattern=pattern):
                self.assertTrue(ids)
                self.assertEqual([i for i in ids if i not in registered], [])

    def test_every_c6_path_has_a_row_or_a_reason(self):
        found = c6_paths()
        self.assertIn("data/program.json", found)
        self.assertIn("data/state.json", found)
        for path in found:
            with self.subTest(path=path):
                mapped = bool(hooks.checks_for(as_example(path)))
                self.assertNotEqual(mapped, path in NOT_MAPPED,
                                    "mapped and exempt" if mapped else "neither mapped nor exempt")
        self.assertEqual([p for p in NOT_MAPPED if p not in found], [])

    def test_contract_table_rows(self):
        self.assertEqual(hooks.checks_for("routine/session-a.md"), ("routine_render_fresh",))
        self.assertIn("load_caps", hooks.checks_for("data/overlays/2026-10-12-weekly.json"))
        self.assertIn("bare_hevy_values", hooks.checks_for("profile.md"))
        self.assertEqual(hooks.checks_for("routine/sub/page.md"), ())
        self.assertEqual(hooks.checks_for("notes.txt"), ())
        self.assertEqual(hooks.checks_for("nutrition/menu/index.md"), ("recipe_index_fresh",))
        self.assertIn("nutrition_template", hooks.checks_for("config.toml"))
        self.assertIn("nutrition_template", hooks.checks_for("nutrition/menu/oats.md"))
        self.assertIn("overlay_library_consistency", hooks.checks_for("data/exercises.json"))
        self.assertIn("program_exercise_ids", hooks.checks_for("data/exercises.json"))
        for check_id in ("overlay_library_consistency", "dangling_routine_ids"):
            self.assertIn(check_id, hooks.checks_for("data/overlays/2026-10-12-weekly.json"))


class SubprocessTest(unittest.TestCase):
    """The hooks as Claude Code runs them: JSON on stdin of `python3 -m coach hooks <event>`."""

    def pipe(self, event, root, payload):
        env = {k: v for k, v in os.environ.items() if not k.startswith("COACH_") and k != "HEVY_API_KEY"}
        env.update(ENV)
        proc = subprocess.run([sys.executable, "-m", "coach", "--root", str(root), "hooks", event],
                              input=json.dumps(payload), cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_sessionstart(self):
        text = context_of(self.pipe("sessionstart", VALID, session_input()))
        self.assertTrue(text.endswith("Detail: python3 -m coach status"))

    def test_posttooluse(self):
        root = copy_of(self, STALE)
        self.assertEqual(self.pipe("posttooluse", root, edit_input(root / "routine/session-a.md"))["decision"],
                         "block")
        self.assertIsNone(self.pipe("posttooluse", VALID, edit_input(VALID / "routine/session-a.md")))

    def test_status_command(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("COACH_") and k != "HEVY_API_KEY"}
        env.update(ENV)
        proc = subprocess.run([sys.executable, "-m", "coach", "--root", "tests/fixtures/instances/valid", "status"],
                              cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    def commands_for(self, event, matcher=None):
        return [hook["command"] for entry in self.settings["hooks"][event]
                if matcher is None or entry.get("matcher") == matcher for hook in entry["hooks"]]

    def test_sessionstart_hook_runs_for_every_source(self):
        entries = self.settings["hooks"]["SessionStart"]
        self.assertEqual([entry.get("matcher") for entry in entries], [None])
        self.assertEqual(self.commands_for("SessionStart"), [SESSIONSTART])

    def test_posttooluse_hook_matches_write_and_edit(self):
        self.assertEqual(self.commands_for("PostToolUse", "Write|Edit"), [POSTTOOLUSE])

    def test_hook_commands_are_not_allowlisted_and_status_is(self):
        allow = self.settings["permissions"]["allow"]
        self.assertIn("Bash(python3 -m coach status:*)", allow)
        for rule in allow:
            self.assertNotIn("coach hooks", rule)
            self.assertNotIn("coach gate", rule)

    def test_claude_md_puts_the_session_start_status_first(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        start = text.index("**Start every session")
        paragraph = " ".join(text[start:text.index("\n\n", start)].split())
        self.assertIn("session-start status", paragraph)
        self.assertLess(paragraph.index("session-start status"), paragraph.index("profile.md"))


if __name__ == "__main__":
    unittest.main()
