"""The approval gate: the PreToolUse hook decision and the template's allowlist (contract C2, C12, C53)."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import commands, gate, jsonio, overlay
from tests.support import FIXTURES, REPO_ROOT, VALID, run_cli
from tests.support.fake_hevy import FakeHevy

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
WEEKLY = "2026-10-12-weekly"
NOW = "2026-10-11T18:00:00Z"
ENV = {"COACH_NOW": NOW, "COACH_HEVY_FIXTURES": str(SYNTHETIC)}
PUSH = f"python3 -m coach routines push --overlay {WEEKLY}"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
HOOK_COMMAND = 'cd "$CLAUDE_PROJECT_DIR" && python3 -m coach gate pretooluse'
GIT_WRITES_ALLOWED = {"pages publish"}
SUBSTITUTED_PUSHES = (
    f'out="$({PUSH})"',
    f'echo "$({PUSH})"',
    f"echo `{PUSH}`",
    f'git commit -m "$({PUSH})"',
    f'echo "$(echo "$({PUSH})")"',
    f'echo x > "$({PUSH})"',
)


def hook_input(command, cwd, mode="default", tool="Bash"):
    return {
        "session_id": "s-1", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": mode,
        "hook_event_name": "PreToolUse", "tool_name": tool,
        "tool_input": {"command": command, "description": "x"},
    }


def output(decision):
    return decision["hookSpecificOutput"]


class GateCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(VALID, self.root)
        self.fake = FakeHevy(SYNTHETIC)
        for patcher in (mock.patch("coach.hevy.transport.from_env", return_value=self.fake),
                        mock.patch("coach.hevy.client.time.sleep")):
            patcher.start()
            self.addCleanup(patcher.stop)
        code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", "pull", "--full"], env=ENV)
        self.assertEqual(code, 0, (envelope, stderr))
        self.fake.requests.clear()

    def decide(self, command, mode="default", cwd=None, tool="Bash"):
        return gate.decide(hook_input(command, cwd or self.root, mode, tool), env=ENV)

    def snapshot(self):
        return {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def unapprove(self):
        path = overlay.path_for(self.root, WEEKLY)
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["approval"] = None
        jsonio.write_doc(path, doc, dry_run=False)


class PushDecisionTest(GateCase):
    def test_an_approved_push_asks_with_the_dry_run_summary(self):
        decision = output(self.decide(PUSH))
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "ask")
        reason = decision["permissionDecisionReason"]
        for text in ("Session A", "Session B", "25/hand (Hevy: 50)", WEEKLY):
            self.assertIn(text, reason)

    def test_the_dry_run_writes_nothing(self):
        before = self.snapshot()
        self.decide(PUSH)
        self.assertEqual(self.fake.writes, [])
        self.assertEqual({r["method"] for r in self.fake.requests}, {"GET"})
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "data" / "hevy" / "writes.jsonl").exists())

    def test_an_unapproved_push_is_denied_with_the_refusal(self):
        self.unapprove()
        decision = output(self.decide(PUSH))
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn(f"overlay {WEEKLY} is not approved", decision["permissionDecisionReason"])

    def test_bypass_permissions_is_denied_without_calling_hevy(self):
        decision = output(self.decide(PUSH, mode="bypassPermissions"))
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("bypass", decision["permissionDecisionReason"])
        self.assertEqual(self.fake.requests, [])

    def test_a_failure_inside_summary_building_asks(self):
        with mock.patch("coach.routines.summary", side_effect=RuntimeError("boom")):
            decision = output(self.decide(PUSH))
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("summary unavailable", decision["permissionDecisionReason"])

    def test_a_push_that_cannot_be_dry_run_asks(self):
        decision = output(self.decide("python3 -m coach routines push --overlay 2099-01-05-weekly"))
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("summary unavailable", decision["permissionDecisionReason"])

    def test_the_root_follows_cd_and_root_options(self):
        for command in (f"cd instance && {PUSH}",
                        f"python3 -m coach --root instance routines push --overlay {WEEKLY}",
                        f"COACH_ROOT=instance python3 -m coach routines push --overlay {WEEKLY}",
                        f'cd instance && echo "$({PUSH})"'):
            with self.subTest(command=command):
                decision = output(self.decide(command, cwd=self.root.parent))
                self.assertEqual(decision["permissionDecision"], "ask")
                self.assertIn("25/hand (Hevy: 50)", decision["permissionDecisionReason"])


class CommandShapeTest(GateCase):
    def assert_decision(self, command):
        decision = self.decide(command)
        self.assertIsNotNone(decision, command)
        self.assertIn(output(decision)["permissionDecision"], ("ask", "deny"), command)
        return output(decision)

    def assert_no_opinion(self, command):
        self.assertIsNone(self.decide(command), command)

    def test_brief_examples(self):
        self.assert_decision("cd x && python3 -m coach routines push --overlay y")
        self.assert_decision("python3 -m coach --root . routines retire --overlay y")
        self.assert_decision("curl -X PUT https://api.hevyapp.com/v1/routines/z")
        self.assert_no_opinion("python3 -m coach routines push --overlay y --dry-run")
        self.assert_no_opinion("python3 -m coach check")
        self.assert_no_opinion("ls")

    def test_wrapped_and_chained_pushes(self):
        for command in (
            f"bash -c '{PUSH}'",
            f"echo start; {PUSH} 2>&1 | tail -5",
            f"out=$({PUSH})",
            f"echo start\n{PUSH}",
            f"env COACH_NOW={NOW} {PUSH}",
            f"/usr/bin/python3.11 -m coach routines push --overlay {WEEKLY}",
            f"python3 -X utf8 -I -m coach routines push --overlay {WEEKLY}",
            f"python3 -mcoach routines push --overlay {WEEKLY}",
            f"{PUSH} --refresh",
            f"cat <({PUSH})",
            f"cat <<EOF\n$({PUSH})\nEOF",
            f"bash <<'EOF'\n{PUSH}\nEOF",
            *SUBSTITUTED_PUSHES,
        ):
            with self.subTest(command=command):
                self.assert_decision(command)

    def test_substituted_pushes_are_denied_in_bypass_mode(self):
        for command in SUBSTITUTED_PUSHES:
            with self.subTest(command=command):
                decision = output(self.decide(command, mode="bypassPermissions"))
                self.assertEqual(decision["permissionDecision"], "deny")

    def test_reads_and_dry_runs_have_no_opinion(self):
        for command in (
            f"{PUSH} --dry-run 2>&1",
            f"{PUSH} --help",
            f"python3 -m coach routines diff --overlay {WEEKLY}",
            "python3 -m coach overlay approve 2026-10-12-weekly",
            'git commit -m "routines push now asks first"',
            "grep -rn 'routines push' .claude/skills",
            "curl https://api.hevyapp.com/v1/routines/z",
            "curl -X GET https://api.hevyapp.com/v1/routines/z",
            "python3 -m unittest discover -s tests -t .",
            f"grep -rn '$({PUSH})' .",
            f"git commit -m \"$(cat <<'EOF'\nMake the gate's check stricter\n\nRun `{PUSH}` after (it asks).\nEOF\n)\"",
            f"git commit -F - <<'EOF'\nThe gate's check\n{PUSH}\nEOF",
        ):
            with self.subTest(command=command):
                self.assert_no_opinion(command)

    def test_raw_hevy_writes_ask_with_a_warning(self):
        for command in (
            "curl -X PUT https://api.hevyapp.com/v1/routines/z -d @body.json",
            "curl --request=POST https://api.hevyapp.com/v1/routines",
            "curl -XDELETE https://api.hevyapp.com/v1/routines/z",
            "curl https://api.hevyapp.com/v1/routines/z --json '{}'",
            "wget --method=PUT https://api.hevyapp.com/v1/routines/z",
            "http PUT https://api.hevyapp.com/v1/routines/z title=x",
        ):
            with self.subTest(command=command):
                decision = self.assert_decision(command)
                self.assertEqual(decision["permissionDecision"], "ask")
                self.assertIn("Hevy API directly", decision["permissionDecisionReason"])

    def test_raw_hevy_writes_are_denied_in_bypass_mode(self):
        decision = output(self.decide("curl -X PUT https://api.hevyapp.com/v1/routines/z", mode="bypassPermissions"))
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_an_unreadable_command_that_mentions_a_push_asks(self):
        decision = self.assert_decision(f"{PUSH} 'unclosed")
        self.assertEqual(decision["permissionDecision"], "ask")

    def test_other_tools_and_malformed_input(self):
        self.assertIsNone(self.decide(PUSH, tool="Read"))
        decision = gate.decide({"tool_name": "Bash", "tool_input": "not a dict"}, env=ENV)
        self.assertEqual(output(decision)["permissionDecision"], "ask")


class PretooluseCommandTest(GateCase):
    def run_gate(self, payload):
        stdin = io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
        with mock.patch("sys.stdin", stdin):
            return run_cli(["gate", "pretooluse"], env=ENV)

    def test_prints_the_hook_response_and_exits_0(self):
        code, printed, _ = self.run_gate(hook_input(PUSH, self.root))
        self.assertEqual(code, 0)
        self.assertEqual(output(printed)["permissionDecision"], "ask")
        self.assertNotIn("ok", printed)

    def test_prints_nothing_without_an_opinion(self):
        code, printed, _ = self.run_gate(hook_input("ls", self.root))
        self.assertEqual((code, printed), (0, None))

    def test_a_summary_exception_asks_and_exits_0(self):
        with mock.patch("coach.routines.summary", side_effect=RuntimeError("boom")):
            code, printed, _ = self.run_gate(hook_input(PUSH, self.root))
        self.assertEqual(code, 0)
        self.assertEqual(output(printed)["permissionDecision"], "ask")
        self.assertIn("summary unavailable", output(printed)["permissionDecisionReason"])

    def test_unreadable_hook_input_asks_and_exits_0(self):
        code, printed, _ = self.run_gate("{not json")
        self.assertEqual(code, 0)
        self.assertEqual(output(printed)["permissionDecision"], "ask")


class SubprocessTest(unittest.TestCase):
    """The hook as Claude Code runs it: JSON on stdin of `python3 -m coach gate pretooluse`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(VALID, self.root, dirs_exist_ok=True)
        code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", "pull", "--full"], env=ENV)
        self.assertEqual(code, 0, (envelope, stderr))

    def pipe(self, command, mode="default"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("COACH_") and k != "HEVY_API_KEY"}
        env.update(ENV)
        proc = subprocess.run(
            [sys.executable, "-m", "coach", "gate", "pretooluse"],
            input=json.dumps(hook_input(command, self.root, mode)), cwd=str(REPO_ROOT), env=env,
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_approved_push_asks_naming_each_routine_and_both_dumbbell_numbers(self):
        decision = output(self.pipe(PUSH))
        self.assertEqual(decision["permissionDecision"], "ask")
        for text in ("Session A", "Session B", "25/hand (Hevy: 50)"):
            self.assertIn(text, decision["permissionDecisionReason"])

    def test_unapproved_push_is_denied(self):
        path = overlay.path_for(self.root, WEEKLY)
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["approval"] = None
        jsonio.write_doc(path, doc, dry_run=False)
        decision = output(self.pipe(PUSH))
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("not approved", decision["permissionDecisionReason"])

    def test_bypass_mode_is_denied(self):
        self.assertEqual(output(self.pipe(PUSH, mode="bypassPermissions"))["permissionDecision"], "deny")

    def test_no_output_for_reads(self):
        self.assertIsNone(self.pipe("python3 -m coach check"))
        self.assertIsNone(self.pipe("ls"))


def allow_rules():
    return json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["allow"]


def bash_rules():
    found = []
    for rule in allow_rules():
        if rule.startswith("Bash(") and rule.endswith(")"):
            body = rule[len("Bash("):-1]
            found.append((body[:-2], True) if body.endswith(":*") else (body, False))
    return found


def rule_matches(rule, command):
    text, is_prefix = rule
    return command.startswith(text) if is_prefix else command == text


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        self.registered = {cmd.name: cmd for cmd in commands.discover()}

    def test_keeps_the_hevy_webfetch_rule(self):
        self.assertIn("WebFetch(domain:api.hevyapp.com)", allow_rules())

    def test_no_allow_rule_matches_a_hevy_write(self):
        for name, cmd in self.registered.items():
            if not cmd.hevy_write:
                continue
            for command in (f"python3 -m coach {name} --overlay x", f"python3 -m coach {name}"):
                for rule in bash_rules():
                    with self.subTest(rule=rule, command=command):
                        self.assertFalse(rule_matches(rule, command))
        for command in ("python3 -m coach routines push --overlay x", "python3 -m coach routines retire --overlay x"):
            self.assertFalse(any(rule_matches(rule, command) for rule in bash_rules()), command)

    def test_every_allowlisted_coach_command_exists_and_never_writes_to_hevy(self):
        coach_rules = [rule for rule in bash_rules() if rule[0].startswith("python3 -m coach")]
        self.assertTrue(coach_rules)
        for text, is_prefix in coach_rules:
            with self.subTest(rule=text):
                self.assertTrue(is_prefix)
                name = text[len("python3 -m coach "):]
                self.assertIn(name, self.registered)
                metadata = self.registered[name].metadata()
                self.assertFalse(metadata["hevy_write"])
                if name not in GIT_WRITES_ALLOWED:
                    self.assertFalse(metadata["git_write"])

    def test_commands_that_stay_behind_a_prompt(self):
        names = {text[len("python3 -m coach "):] for text, _ in bash_rules() if text.startswith("python3 -m coach")}
        for name in ("routines push", "routines retire", "migrate run", "hevy record-fixtures", "plugins test",
                     "gate pretooluse"):
            self.assertNotIn(name, names)
        for text, _ in bash_rules():
            self.assertNotIn(text.strip(), ("python3 -m coach", "python3", "python3 -m"))

    def test_the_pretooluse_hook_runs_the_gate_on_every_bash_command(self):
        entries = self.settings["hooks"]["PreToolUse"]
        gates = [hook for entry in entries if entry.get("matcher") == "Bash" for hook in entry["hooks"]]
        self.assertEqual([hook["command"] for hook in gates], [HOOK_COMMAND])
        self.assertEqual(gates[0]["type"], "command")


if __name__ == "__main__":
    unittest.main()
