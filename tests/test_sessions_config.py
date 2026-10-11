"""`[sessions]` config: per-session time caps (contract C19)."""

import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from coach import config
from coach.errors import ConfigError
from tests.support import MINIMAL_CONFIG, REPO_ROOT, VALID, run_cli


def load_text(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        path.write_text(text, encoding="utf-8")
        return config.parse_file(path)


class SessionsTableTest(unittest.TestCase):
    def test_absent_table_means_no_session_caps(self):
        self.assertEqual(load_text(MINIMAL_CONFIG).sessions.cap_minutes, {})

    def test_cap_minutes_takes_session_ids(self):
        cfg = load_text(MINIMAL_CONFIG + "\n[sessions.cap_minutes]\nsession-a = 45\nsession-b = 0\n")
        self.assertEqual(cfg.sessions.cap_minutes, {"session-a": 45, "session-b": 0})

    def test_bad_values_and_ids_are_config_errors(self):
        for body, needle in (("session-a = -5", "at least 0"), ("session-a = 45.5", "whole number"),
                             ("Session_A = 45", "Session_A")):
            with self.subTest(body=body):
                with self.assertRaises(ConfigError) as caught:
                    load_text(MINIMAL_CONFIG + f"\n[sessions.cap_minutes]\n{body}\n")
                self.assertIn(needle, caught.exception.message)

    def test_an_unknown_key_under_sessions_exits_5_naming_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.toml").write_text(
                MINIMAL_CONFIG + "\n[sessions]\ncap_minute = 45\n", encoding="utf-8")
            code, envelope, _ = run_cli(["--root", tmp, "config", "validate"])
        self.assertEqual(code, 5, envelope)
        self.assertIn("cap_minute", envelope["error"]["message"])
        self.assertIn("[sessions]", envelope["error"]["message"])

    def test_the_example_carries_a_commented_cap(self):
        text = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        self.assertIn("[sessions.cap_minutes]", text)
        self.assertNotIn("sessions", tomllib.loads(text))


class SessionCapIdsCheckTest(unittest.TestCase):
    def run_check(self, extra):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(VALID, root)
            with (root / "config.toml").open("a", encoding="utf-8") as handle:
                handle.write(extra)
            return run_cli(["--root", str(root), "check", "--only", "session_cap_ids"])

    def test_warns_on_an_id_the_program_lacks(self):
        code, envelope, _ = self.run_check("\n[sessions.cap_minutes]\nsession-a = 45\nsession-z = 30\n")
        self.assertEqual(code, 0, envelope)
        results = envelope["data"]["results"]
        self.assertEqual([r["status"] for r in results], ["warn"])
        self.assertIn("session-z", results[0]["message"])

    def test_passes_when_every_id_is_a_program_session(self):
        code, envelope, _ = self.run_check("\n[sessions.cap_minutes]\nsession-a = 45\n")
        self.assertEqual([r["status"] for r in envelope["data"]["results"]], ["pass"])

    def test_skips_without_caps(self):
        code, envelope, _ = self.run_check("")
        self.assertEqual([r["status"] for r in envelope["data"]["results"]], ["skip"])


if __name__ == "__main__":
    unittest.main()
