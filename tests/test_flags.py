"""The flag registry: one vocabulary of overlay flag codes (contract C20)."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import flags
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli

CONTRACT = REPO_ROOT / "docs" / "design" / "coach-contract.md"
CODE_CELL = re.compile(r"^`([a-z][a-z0-9_]*)`$")


def reserved_codes():
    """{code: (severities, owner, structural)} from the C20 reserved-codes table."""
    text = CONTRACT.read_text(encoding="utf-8")
    section = text.split("## C20.", 1)[1].split("\n## C21.", 1)[0]
    table = section.split("Reserved codes:", 1)[1]
    found = {}
    for line in table.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = CODE_CELL.match(cells[0]) if len(cells) == 5 else None
        if match:
            code, (severities, owner, structural) = match.group(1), cells[1:4]
            owner_id = re.match(r"R-[0-9]+[a-z0-9]*", owner).group(0)
            found[code] = (tuple(s.strip() for s in severities.split(",")), owner_id, structural == "yes")
    return found


class MakeTest(unittest.TestCase):
    def test_an_unknown_code_raises(self):
        with self.assertRaises(ValueError):
            flags.make("no_such_code", message="x")

    def test_a_severity_outside_the_codes_list_raises(self):
        with self.assertRaises(ValueError):
            flags.make("convention_slip", "block", message="x")

    def test_builds_the_c10_flag_with_the_first_listed_severity(self):
        flag = flags.make("duration_over_cap", session_id="session-a", message="58 min against a 45 min cap")
        self.assertEqual(flag, {"code": "duration_over_cap", "severity": "info", "session_id": "session-a",
                                "exercise_id": None, "message": "58 min against a 45 min cap",
                                "resolved": False, "resolution": None})


class RegisterTest(unittest.TestCase):
    def setUp(self):
        self.saved = dict(flags.registry())
        self.addCleanup(self.restore)

    def restore(self):
        flags._REGISTRY.clear()
        flags._REGISTRY.update(self.saved)

    def test_structural_defaults_to_false(self):
        flags.register("custom_demo", owner="test", severities=("info",), summary="A demo code.")
        self.assertFalse(flags.registry()["custom_demo"].structural)
        flags.register("custom_shape", owner="test", severities=("warn",), summary="Shape.", structural=True)
        self.assertTrue(flags.registry()["custom_shape"].structural)

    def test_a_duplicate_code_raises_even_with_another_structural_value(self):
        flags.register("custom_demo", owner="test", severities=("info",), summary="A demo code.")
        with self.assertRaises(ValueError):
            flags.register("custom_demo", owner="test", severities=("info",), summary="A demo code.",
                           structural=True)

    def test_codes_are_snake_case_with_known_severities(self):
        with self.assertRaises(ValueError):
            flags.register("Bad-Code", owner="test", severities=("info",), summary="x")
        with self.assertRaises(ValueError):
            flags.register("custom_bad", owner="test", severities=("loud",), summary="x")


class ContractTableTest(unittest.TestCase):
    def test_every_registered_code_is_in_the_contract_table(self):
        table = reserved_codes()
        self.assertIn("convention_slip", table)
        for code, entry in flags.registry().items():
            with self.subTest(code=code):
                self.assertIn(code, table)
                severities, owner, structural = table[code]
                self.assertEqual(entry.severities, severities)
                self.assertEqual(entry.owner, owner)
                self.assertEqual(entry.structural, structural)

    def test_r20_codes_are_registered(self):
        registry = flags.registry()
        self.assertEqual(registry["convention_slip"].severities, ("warn",))
        self.assertEqual(registry["duration_over_cap"].severities, ("info",))
        self.assertEqual({registry[c].owner for c in ("convention_slip", "duration_over_cap")}, {"R-20"})


class FlagCodesKnownCheckTest(unittest.TestCase):
    def run_check(self, root):
        return run_cli(["--root", str(root), "check", "--only", "flag_codes_known"])

    def test_fails_on_an_overlay_flag_with_an_unregistered_code(self):
        code, envelope, _ = self.run_check(INSTANCES / "flag-unknown")
        self.assertEqual(code, 1, envelope)
        results = envelope["data"]["results"]
        self.assertEqual([r["status"] for r in results], ["fail"])
        self.assertIn("no_such_code", results[0]["message"])
        self.assertEqual(results[0]["path"], "data/overlays/2026-10-12-weekly.json")

    def test_passes_when_every_code_is_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "flag-unknown", root)
            path = root / "data" / "overlays" / "2026-10-12-weekly.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["flags"][0]["code"] = "convention_slip"
            doc["flags"][0]["severity"] = "warn"
            path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            code, envelope, _ = self.run_check(root)
        self.assertEqual(code, 0, envelope)
        self.assertEqual([r["status"] for r in envelope["data"]["results"]], ["pass"])

    def test_skips_without_overlays(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(VALID / "config.toml", Path(tmp) / "config.toml")
            code, envelope, _ = self.run_check(tmp)
        self.assertEqual(code, 0, envelope)
        self.assertEqual([r["status"] for r in envelope["data"]["results"]], ["skip"])


if __name__ == "__main__":
    unittest.main()
