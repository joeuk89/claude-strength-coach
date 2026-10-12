"""`coach status` and its providers (contract C52)."""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from coach import overlay, status
from coach.status import Provider, Section
from tests.support import INSTANCES, VALID, run_cli
from tests.support.git import git

NOW = "2026-10-11T18:00:00Z"
ENV = {"COACH_NOW": NOW}
WEEKLY = "2026-10-12-weekly"


def sections(envelope):
    return {section["id"]: section for section in envelope["data"]["sections"]}


def text(section):
    return " ".join(section["lines"])


class TempCopy:
    """A temp copy of a fixture instance, for tests that change files."""

    def __init__(self, test, source=VALID):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "instance"
        shutil.copytree(source, self.root)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def status(self, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(self.root), "status"], env={"COACH_NOW": now})
        assert code == 0, (envelope, stderr)
        return sections(envelope)


def verify_lines(doc, routine_ids, verified=True):
    return "".join(json.dumps({
        "schema_version": 1, "at": "2026-10-11T19:05:00Z", "kind": "verify", "routine_id": routine_id,
        "overlay_id": doc["id"], "overlay_hash": doc["approval"]["hash"], "verified": verified, "diff": [],
    }) + "\n" for routine_id in routine_ids)


ROUTINES = ("00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000002")


class StatusCommandTest(unittest.TestCase):
    def run_status(self, root=VALID, env=ENV):
        code, envelope, stderr = run_cli(["--root", str(root), "status"], env=env)
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope

    def test_valid_instance_reports_every_section_in_order(self):
        envelope = self.run_status()
        data = envelope["data"]
        self.assertEqual(data["instance"], "instance")
        self.assertEqual(data["today"], "2026-10-11")
        self.assertEqual([s["id"] for s in data["sections"]],
                         ["instance", "checks", "overlay", "program", "checkin", "hevy"])
        for section in data["sections"]:
            self.assertLessEqual(len(section["lines"]), 3, section["id"])
            self.assertIn(section["level"], ("info", "attention"))

    def test_overlay_names_the_next_one_and_its_first_session(self):
        overlay_section = sections(self.run_status())["overlay"]
        line = overlay_section["lines"][0]
        self.assertIn("No overlay is in force today", line)
        self.assertIn(WEEKLY, line)
        self.assertIn("first session Session A on Mon 2026-10-12", line)
        self.assertIn("not pushed", line)
        self.assertEqual(overlay_section["level"], "attention")
        data = overlay_section["data"]
        self.assertIsNone(data["in_force"])
        self.assertEqual(data["next"]["id"], WEEKLY)
        self.assertEqual(data["next"]["first_session"]["title"], "Session A")
        self.assertEqual([s["title"] for s in data["next_sessions"]], ["Session A", "Session B"])
        self.assertEqual(data["uncovered"], [])

    def test_overlay_in_force_pushed_and_verified(self):
        copy = TempCopy(self)
        doc = overlay.load(copy.root, WEEKLY)
        copy.write("data/hevy/writes.jsonl", verify_lines(doc, ROUTINES))
        found = copy.status(now="2026-10-13T08:00:00Z")["overlay"]
        self.assertIn(f"Overlay in force today: {WEEKLY}", found["lines"][0])
        self.assertIn("pushed and verified", found["lines"][0])
        self.assertEqual(found["data"]["in_force"]["state"], "verified")
        self.assertEqual([s["title"] for s in found["data"]["next_sessions"]], ["Session B"])
        self.assertEqual(found["level"], "info")

    def test_one_routine_verified_of_two(self):
        copy = TempCopy(self)
        doc = overlay.load(copy.root, WEEKLY)
        copy.write("data/hevy/writes.jsonl", verify_lines(doc, ROUTINES[:1]))
        found = copy.status(now="2026-10-13T08:00:00Z")["overlay"]
        self.assertIn("1 of 2 Hevy routines verified", found["lines"][0])
        self.assertEqual(found["level"], "attention")

    def test_a_verify_line_for_an_older_hash_does_not_count(self):
        copy = TempCopy(self)
        doc = dict(overlay.load(copy.root, WEEKLY))
        doc["approval"] = {"approved_at": "2026-10-10T00:00:00Z", "hash": "sha256:" + "0" * 64}
        copy.write("data/hevy/writes.jsonl", verify_lines(doc, ROUTINES))
        found = copy.status(now="2026-10-13T08:00:00Z")["overlay"]
        self.assertEqual(found["data"]["in_force"]["state"], "not_pushed")

    def test_a_write_with_no_verify_line_is_unverified(self):
        copy = TempCopy(self)
        copy.write("data/hevy/writes.jsonl", json.dumps({
            "schema_version": 1, "at": "2026-10-11T19:05:00Z", "kind": "write", "method": "PUT",
            "path": f"/v1/routines/{ROUTINES[0]}", "status": None, "routine_id": ROUTINES[0], "overlay_id": WEEKLY,
            "overlay_hash": None, "request_body": {}, "request_sha256": "sha256:" + "0" * 64}) + "\n")
        found = copy.status(now="2026-10-13T08:00:00Z")["overlay"]
        self.assertIn("pushed but not verified", found["lines"][0])
        self.assertEqual(found["level"], "attention")

    def test_uncovered_days_in_the_coming_week(self):
        copy = TempCopy(self)
        found = copy.status(now="2026-10-18T18:00:00Z")["overlay"]
        self.assertIn("No overlay covers 2026-10-19 to 2026-10-25", text(found))
        self.assertEqual(found["level"], "attention")
        midweek = copy.status(now="2026-10-14T08:00:00Z")["overlay"]
        self.assertEqual(midweek["data"]["uncovered"], [])
        self.assertEqual(midweek["data"]["coming_week"], {"start": "2026-10-12", "end": "2026-10-18"})

    def test_coming_week_follows_week_starts_sunday(self):
        copy = TempCopy(self)
        config = (copy.root / "config.toml").read_text(encoding="utf-8")
        copy.write("config.toml", config.replace('week_starts = "monday"', 'week_starts = "sunday"'))
        found = copy.status(now="2026-10-17T18:00:00Z")["overlay"]
        self.assertEqual(found["data"]["coming_week"], {"start": "2026-10-18", "end": "2026-10-24"})
        self.assertEqual(found["data"]["uncovered"], [f"2026-10-{day}" for day in range(19, 25)])

    def test_an_unapproved_overlay_needs_attention(self):
        copy = TempCopy(self)
        path = overlay.path_for(copy.root, WEEKLY)
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["approval"] = None
        copy.write(f"data/overlays/{WEEKLY}.json", json.dumps(doc, indent=2) + "\n")
        found = copy.status()["overlay"]
        self.assertIn("not approved", found["lines"][0])
        self.assertEqual(found["level"], "attention")

    def test_an_invalid_overlay_is_skipped_not_fatal(self):
        copy = TempCopy(self)
        copy.write("data/overlays/2026-10-19-weekly.json", "{not json")
        found = copy.status()["overlay"]
        self.assertEqual(found["data"]["skipped"], ["2026-10-19-weekly"])
        self.assertEqual(found["data"]["next"]["id"], WEEKLY)

    def test_hevy_off_drops_the_hevy_section(self):
        copy = TempCopy(self)
        config = (copy.root / "config.toml").read_text(encoding="utf-8")
        copy.write("config.toml", config.replace("[hevy]\nenabled = true", "[hevy]\nenabled = false"))
        found = copy.status()
        self.assertNotIn("hevy", found)
        self.assertIn("approved", found["overlay"]["lines"][0])
        self.assertNotIn("pushed", found["overlay"]["lines"][0])

    def test_hevy_cache_age(self):
        for name, phrase, level in (("hevy-fresh", "6 hours old (limit 24)", "info"),
                                    ("hevy-stale", "54 hours old, past the 24-hour limit", "attention")):
            with self.subTest(fixture=name):
                found = sections(self.run_status(INSTANCES / name))["hevy"]
                self.assertIn(phrase, text(found))
                self.assertEqual(found["level"], level)

    def test_checks_summary_names_fail_and_warn_ids(self):
        envelope = self.run_status(INSTANCES / "program-stale-render")
        found = sections(envelope)["checks"]
        self.assertIn("routine_render_fresh", found["data"]["fail"])
        self.assertIn("Failing: ", text(found))
        self.assertIn("routine_render_fresh", text(found))
        self.assertEqual(found["level"], "attention")
        self.assertIn("hevy_cache_age", sections(self.run_status())["checks"]["data"]["warn"])

    def test_program_reports_block_and_rotation(self):
        found = sections(self.run_status())["program"]
        self.assertIn("Block 1 · 2 of 6 hard weeks · triggers 0 of 4 · light week: not due", text(found))
        copy = TempCopy(self)
        state = json.loads((copy.root / "data/state.json").read_text(encoding="utf-8"))
        state["rotation"] = {"position": "week-b", "confirmed": False, "confirmed_at": None, "week": None}
        state["block"]["light_week"] = {"status": "proposed", "type": "deload", "reason": "ceiling",
                                        "week": "2026-10-12", "decision_id": None}
        copy.write("data/state.json", json.dumps(state, indent=2) + "\n")
        found = copy.status()["program"]
        self.assertIn("Rotation: week-b, not confirmed", text(found))
        self.assertIn("light week: proposed for wk of 12 Oct (deload, ceiling)", text(found))
        self.assertEqual(found["level"], "attention")

    def test_checkin_due_after_seven_days(self):
        found = sections(self.run_status())["checkin"]
        self.assertIn("next is due 2026-10-18", text(found))
        self.assertEqual(found["level"], "info")
        copy = TempCopy(self)
        late = copy.status(now="2026-10-19T09:00:00Z")["checkin"]
        self.assertIn("Check-in due", text(late))
        self.assertEqual(late["data"]["days_since"], 8)
        self.assertEqual(late["level"], "attention")
        for path in (copy.root / "check-ins").glob("*.md"):
            path.unlink()
        first = copy.status()["checkin"]
        self.assertEqual(first["data"]["mode"], "first")

    def test_uninitialised_copy_says_run_setup_and_drops_config_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            envelope = self.run_status(Path(tmp))
        self.assertEqual(envelope["data"]["instance"], "uninitialised")
        found = sections(envelope)
        self.assertIn("run /setup", text(found["instance"]))
        self.assertEqual(found["instance"]["level"], "attention")
        self.assertNotIn("hevy", found)
        self.assertNotIn("overlay", found)

    def test_template_repo_is_recognised(self):
        with tempfile.TemporaryDirectory() as tmp:
            git(tmp, "init", "-q")
            git(tmp, "config", "--local", "coach.workspace", "template")
            envelope = self.run_status(Path(tmp))
        self.assertEqual(envelope["data"]["instance"], "template")

    def test_files_behind_their_schema_version_say_migrate(self):
        copy = TempCopy(self)
        state = json.loads((copy.root / "data/state.json").read_text(encoding="utf-8"))
        state["schema_version"] = 1
        copy.write("data/state.json", json.dumps(state, indent=2) + "\n")
        found = copy.status()["instance"]
        self.assertIn("data/state.json", text(found))
        self.assertIn("run python3 -m coach migrate run", text(found))
        self.assertEqual(found["level"], "attention")

    def test_status_writes_nothing_and_makes_no_hevy_call(self):
        copy = TempCopy(self)
        before = {p: p.read_bytes() for p in copy.root.rglob("*") if p.is_file()}
        with mock.patch("coach.hevy.transport.from_env", side_effect=AssertionError("network")) as from_env, \
                mock.patch("coach.hevy.transport.UrllibTransport.request",
                           side_effect=AssertionError("network")) as request:
            copy.status()
        from_env.assert_not_called()
        request.assert_not_called()
        after = {p: p.read_bytes() for p in copy.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)


class ProviderRegistryTest(unittest.TestCase):
    def test_a_provider_that_raises_is_one_unavailable_line(self):
        def boom(ctx):
            raise RuntimeError("boom")

        providers = [Provider("boom", "test", 5, boom)] + status.discover()
        found = status.collect(VALID, date(2026, 10, 11), env=ENV, providers=providers)
        self.assertEqual(found[0].id, "boom")
        self.assertEqual(found[0].lines, ["boom: unavailable (RuntimeError)"])
        self.assertEqual(found[0].level, "attention")
        self.assertEqual([s.id for s in found[1:]], ["instance", "checks", "overlay", "program", "checkin", "hevy"])

    def test_a_raising_provider_through_the_command(self):
        with mock.patch("coach.status.checkin.checkin_status.coach_status_provider",
                        Provider("checkin", "R-26b", 50, mock.Mock(side_effect=KeyError("x")))):
            code, envelope, _ = run_cli(["--root", str(VALID), "status"], env=ENV)
        self.assertEqual(code, 0)
        found = sections(envelope)
        self.assertEqual(found["checkin"]["lines"], ["checkin: unavailable (KeyError)"])
        self.assertIn("overlay", found)

    def test_discovery_finds_the_shipped_providers(self):
        found = {item.id: item for item in status.discover()}
        self.assertEqual(set(found), {"instance", "checks", "hevy", "overlay", "program", "checkin", "proposal",
                                      "followups", "niggles", "events"})
        self.assertEqual({item.id for item in found.values() if item.owner != "R-26b"},
                         {"proposal", "followups", "niggles", "events"})
        self.assertEqual(found["proposal"].owner, "R-23a")
        self.assertEqual((found["followups"].owner, found["niggles"].owner), ("R-27", "R-27"))

    def test_section_rules(self):
        with self.assertRaises(ValueError):
            Section("x", ["a", "b", "c", "d"])
        with self.assertRaises(ValueError):
            Section("x", [], level="loud")


if __name__ == "__main__":
    unittest.main()
