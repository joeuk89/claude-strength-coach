"""The `overlay` commands and the overlay checks, end to end through the CLI (contract C2, C3, C13)."""

import json
import unittest

from coach import jsonio
from tests.support import FIXTURES, INSTANCES, MINIMAL_CONFIG, REPO_ROOT, VALID, run_module
from tests.test_cli import EnvelopeMixin
from tests.test_overlay import Instance, lb_config, valid_overlay

WEEKLY = "2026-10-12-weekly"
DRAFT_KG = FIXTURES / "overlay" / "draft-kg.json"
NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}


def files_under(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class BuildCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_dry_run_returns_the_overlay_and_writes_nothing(self):
        with Instance() as root:
            before = files_under(root)
            data = self.run_ok("--root", str(root), "overlay", "build", "--input", str(DRAFT_KG), "--dry-run",
                               env=NOW)
            self.assertEqual(files_under(root), before)
        bench = data["overlay"]["sessions"][0]["exercises"][1]
        self.assertEqual(
            bench["sets"][1]["load"],
            {"mode": "per_hand_x2", "unit": "kg", "per_hand": 25, "hevy_total": 50, "hevy_kg": 50.0},
        )
        self.assertFalse(data["written"])

    def test_acceptance_command_from_the_repo_root(self):
        code, envelope, _ = run_module(["--root", "tests/fixtures/instances/valid", "overlay", "build", "--input",
                                        "tests/fixtures/overlay/draft-kg.json", "--dry-run"], cwd=REPO_ROOT)
        self.assertEqual(code, 0, envelope)
        load = envelope["data"]["overlay"]["sessions"][0]["exercises"][1]["sets"][1]["load"]
        self.assertEqual(load, {"mode": "per_hand_x2", "unit": "kg", "per_hand": 25, "hevy_total": 50,
                                "hevy_kg": 50.0})

    def test_lb_draft(self):
        with Instance(lb_config(), copy_valid=False) as root:
            data = self.run_ok("--root", str(root), "overlay", "build", "--input", str(DRAFT_KG), "--dry-run",
                               env=NOW)
        self.assertEqual(data["overlay"]["sessions"][0]["exercises"][1]["sets"][1]["load"]["hevy_kg"], 22.6796)

    def test_build_writes_the_file(self):
        with Instance(MINIMAL_CONFIG, copy_valid=False) as root:
            data = self.run_ok("--root", str(root), "overlay", "build", "--input", str(DRAFT_KG), env=NOW)
            self.assertEqual(data["id"], WEEKLY)
            self.assertEqual(data["path"], f"data/overlays/{WEEKLY}.json")
            written = jsonio.read_doc(root / "data" / "overlays" / f"{WEEKLY}.json", "overlay")
            self.assertEqual(written, data["overlay"])

    def test_rebuilding_an_approved_overlay_is_refused(self):
        draft = json.loads(DRAFT_KG.read_text(encoding="utf-8"))
        draft["id"] = WEEKLY
        with Instance() as root:
            path = root / "draft.json"
            path.write_text(json.dumps(draft), encoding="utf-8")
            envelope, _ = self.run_fail(3, "--root", str(root), "overlay", "build", "--input", str(path), env=NOW)
            self.assertEqual(envelope["error"]["code"], "refused")

    def test_unflagged_null_load_exits_1_with_the_set_path(self):
        draft = json.loads(DRAFT_KG.read_text(encoding="utf-8"))
        draft["sessions"][0]["exercises"][1]["sets"][1]["load"] = None
        with Instance() as root:
            path = root / "draft.json"
            path.write_text(json.dumps(draft), encoding="utf-8")
            envelope, _ = self.run_fail(1, "--root", str(root), "overlay", "build", "--input", str(path), env=NOW)
        self.assertIn("$.sessions[0].exercises[1].sets[1].load", [d["path"] for d in envelope["error"]["details"]])

    def test_missing_input(self):
        self.run_fail(1, "--root", str(VALID), "overlay", "build", "--input", "nope.json", env=NOW)


class ValidateCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_valid(self):
        data = self.run_ok("--root", str(VALID), "overlay", "validate", WEEKLY)
        self.assertEqual(data["results"], [{"id": WEEKLY, "path": f"data/overlays/{WEEKLY}.json", "valid": True,
                                            "approved": True}])
        self.assertEqual(len(self.run_ok("--root", str(VALID), "overlay", "validate")["results"]), 1)

    def test_bad_hevy_total_exits_1_with_the_load_path(self):
        envelope, _ = self.run_fail(1, "--root", str(INSTANCES / "overlay-bad-arithmetic"), "overlay", "validate",
                                    WEEKLY)
        details = envelope["error"]["details"]
        self.assertTrue(all(d["path"].startswith("$.sessions[0].exercises[1].sets[") for d in details), details)
        self.assertIn("$.sessions[0].exercises[1].sets[1].load.hevy_total", [d["path"] for d in details])

    def test_file_option(self):
        doc = valid_overlay()
        doc["sessions"][0]["exercises"][1]["sets"][1]["load"]["hevy_total"] = 25
        with Instance() as root:
            path = root / "candidate.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            envelope, _ = self.run_fail(1, "--root", str(root), "overlay", "validate", "--file", str(path))
        self.assertEqual(envelope["error"]["details"][0]["path"], "$.sessions[0].exercises[1].sets[1].load.hevy_total")

    def test_unflagged_null_load(self):
        doc = valid_overlay()
        doc["sessions"][0]["exercises"][1]["sets"][1]["load"] = None
        with Instance() as root:
            path = root / "candidate.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            envelope, _ = self.run_fail(1, "--root", str(root), "overlay", "validate", "--file", str(path))
            self.assertIn("$.sessions[0].exercises[1].sets[1].load",
                          [d["path"] for d in envelope["error"]["details"]])
            doc["flags"] = [{"code": "no_data", "severity": "warn", "session_id": "session-a",
                             "exercise_id": "db_bench_press", "message": "No exposure.", "resolved": False,
                             "resolution": None}]
            path.write_text(json.dumps(doc), encoding="utf-8")
            data = self.run_ok("--root", str(root), "overlay", "validate", "--file", str(path))
        self.assertTrue(data["results"][0]["valid"])
        self.assertFalse(data["results"][0]["approved"])

    def test_location_needs_its_config_table(self):
        doc = valid_overlay()
        doc["sessions"][0]["location"] = "home"
        with Instance() as root:
            path = root / "candidate.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.run_ok("--root", str(root), "overlay", "validate", "--file", str(path))
            (root / "config.toml").write_text(MINIMAL_CONFIG, encoding="utf-8")
            envelope, _ = self.run_fail(1, "--root", str(root), "overlay", "validate", "--file", str(path))
        self.assertIn("home", json.dumps(envelope["error"]))

    def test_id_and_file_together_is_usage(self):
        self.run_fail(2, "--root", str(VALID), "overlay", "validate", WEEKLY, "--file", "x.json")


class ListAndCurrentTest(EnvelopeMixin, unittest.TestCase):
    def test_list(self):
        data = self.run_ok("--root", str(VALID), "overlay", "list")
        self.assertEqual([row["id"] for row in data["overlays"]], [WEEKLY])
        self.assertTrue(data["overlays"][0]["approved"])

    def test_current_weekly_then_midweek(self):
        midweek = valid_overlay()
        midweek.update(id="2026-10-14-midweek", kind="midweek", created_at="2026-10-14T07:00:00Z",
                       supersedes=WEEKLY, span={"start": "2026-10-14", "end": "2026-10-18"}, approval=None)
        midweek["sessions"] = [midweek["sessions"][1]]
        with Instance() as root:
            jsonio.write_doc(root / "data" / "overlays" / "2026-10-14-midweek.json", midweek, False)
            data = self.run_ok("--root", str(root), "overlay", "current", "--date", "2026-10-13")
            self.assertEqual(data["overlay_id"], WEEKLY)
            data = self.run_ok("--root", str(root), "overlay", "current", "--date", "2026-10-15")
            self.assertEqual(data["overlay_id"], "2026-10-14-midweek")
            self.assertEqual([s["session_id"] for s in data["sessions"]], ["session-b"])
            data = self.run_ok("--root", str(root), "overlay", "current", "--date", "2026-10-20")
            self.assertIsNone(data["overlay_id"])

    def test_current_defaults_to_today(self):
        data = self.run_ok("--root", str(VALID), "overlay", "current", env={"COACH_NOW": "2026-10-12T09:00:00Z"})
        self.assertEqual(data["date"], "2026-10-12")
        self.assertEqual(data["overlay_id"], WEEKLY)


class NotesCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_session_a(self):
        data = self.run_ok("--root", str(VALID), "overlay", "notes", WEEKLY, "--session", "session-a")
        [session] = data["sessions"]
        first, bench = session["exercises"]
        lines = first["note"].splitlines()
        overlay_focus = valid_overlay()["focus"]
        self.assertEqual(lines[0], f"Wk of 12 Oct: {overlay_focus}")
        self.assertTrue(lines[1].startswith("Target: "))
        self.assertTrue(lines[2].startswith("Cues: "))
        self.assertIn("25/hand (Hevy: 50)", bench["note"])
        self.assertNotIn("50", bench["note"].replace("(Hevy: 50)", ""))
        self.assertNotIn("12.5", bench["note"])
        self.assertNotIn("add 2.5 from last week", first["note"])

    def test_all_sessions_and_unknown_session(self):
        data = self.run_ok("--root", str(VALID), "overlay", "notes", WEEKLY)
        self.assertEqual([s["session_id"] for s in data["sessions"]], ["session-a", "session-b"])
        self.run_fail(1, "--root", str(VALID), "overlay", "notes", WEEKLY, "--session", "session-z")

    def test_target_note_is_in_the_render_not_the_notes(self):
        notes = json.dumps(self.run_ok("--root", str(VALID), "overlay", "notes", WEEKLY))
        rendered = self.run_ok("--root", str(VALID), "overlay", "render", WEEKLY)["text"]
        self.assertNotIn("add 2.5 from last week", notes)
        self.assertIn("add 2.5 from last week", rendered)

    def test_choose_the_load(self):
        doc = valid_overlay()
        doc["approval"] = None
        doc["sessions"][0]["exercises"][1]["sets"] = [
            {"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7, "load": None}] * 3
        doc["flags"] = [{"code": "no_data", "severity": "warn", "session_id": "session-a",
                         "exercise_id": "db_bench_press", "message": "No exposure.", "resolved": False,
                         "resolution": None}]
        with Instance() as root:
            jsonio.write_doc(root / "data" / "overlays" / f"{WEEKLY}.json", doc, False)
            data = self.run_ok("--root", str(root), "overlay", "notes", WEEKLY, "--session", "session-a")
            rendered = self.run_ok("--root", str(root), "overlay", "render", WEEKLY)["text"]
        self.assertEqual(data["sessions"][0]["exercises"][1]["note"].splitlines()[0],
                         "Target: 3×8–10 @ RPE 7 · choose the load")
        self.assertIn("| choose the load |", rendered)


class RenderCommandTest(EnvelopeMixin, unittest.TestCase):
    PROSE_BEFORE = (
        "# Check-in — 2026-10-11 (weekly)\n\n## Decisions\n\nStay the course.\n\n## The week ahead — 12–18 Oct\n\n"
    )
    PROSE_AFTER = "\n\nFocus: heavier top sets.\n"

    def test_into_writes_the_region_and_is_idempotent(self):
        with Instance() as root:
            checkin = root / "check-ins" / "2026-10-18.md"
            original = self.PROSE_BEFORE + "Plan below.\n\n## Coach's read\n\nSteady week.\n"
            checkin.write_text(original, encoding="utf-8")
            data = self.run_ok("--root", str(root), "overlay", "render", WEEKLY, "--into", str(checkin))
            self.assertTrue(data["changed"])
            first = checkin.read_bytes()
            text = first.decode("utf-8")
            begin = f"<!-- coach:begin overlay {WEEKLY} -->"
            end = f"<!-- coach:end overlay {WEEKLY} -->"
            self.assertTrue(text.startswith(self.PROSE_BEFORE + "Plan below.\n\n" + begin + "\n"))
            self.assertTrue(text.endswith(end + "\n\n## Coach's read\n\nSteady week.\n"))
            self.assertEqual(text[:text.index(begin)] + text[text.index(end) + len(end) + 2:], original)
            data = self.run_ok("--root", str(root), "overlay", "render", WEEKLY, "--into", str(checkin))
            self.assertFalse(data["changed"])
            self.assertEqual(checkin.read_bytes(), first)

    def test_into_replaces_a_stale_region_only(self):
        stale = f"<!-- coach:begin overlay {WEEKLY} -->\nold table\n<!-- coach:end overlay {WEEKLY} -->"
        with Instance() as root:
            checkin = root / "check-ins" / "2026-10-18.md"
            checkin.write_bytes((self.PROSE_BEFORE + stale + self.PROSE_AFTER).encode("utf-8"))
            self.run_ok("--root", str(root), "overlay", "render", WEEKLY, "--into", str(checkin))
            text = checkin.read_bytes().decode("utf-8")
        self.assertTrue(text.startswith(self.PROSE_BEFORE + f"<!-- coach:begin overlay {WEEKLY} -->\n"))
        self.assertTrue(text.endswith(f"<!-- coach:end overlay {WEEKLY} -->" + self.PROSE_AFTER))
        self.assertNotIn("old table", text)

    def test_dry_run_writes_nothing(self):
        with Instance() as root:
            checkin = root / "check-ins" / "2026-10-18.md"
            checkin.write_text(self.PROSE_BEFORE, encoding="utf-8")
            data = self.run_ok("--root", str(root), "overlay", "render", WEEKLY, "--into", str(checkin), "--dry-run")
            self.assertEqual(checkin.read_text(encoding="utf-8"), self.PROSE_BEFORE)
        self.assertTrue(data["changed"])
        self.assertIn(f"<!-- coach:begin overlay {WEEKLY} -->", data["text"])

    def test_into_needs_an_existing_file(self):
        with Instance() as root:
            self.run_fail(1, "--root", str(root), "overlay", "render", WEEKLY, "--into", str(root / "nope.md"))


class ApproveCommandTest(EnvelopeMixin, unittest.TestCase):
    def unapproved_instance(self):
        instance = Instance()
        root = instance.__enter__()
        path = root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["approval"] = None
        jsonio.write_doc(path, doc, False)
        self.addCleanup(instance.__exit__)
        return root, path

    def test_approve_then_edit(self):
        from coach import overlay

        root, path = self.unapproved_instance()
        data = self.run_ok("--root", str(root), "overlay", "approve", WEEKLY, env=NOW)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["approval"]["hash"], data["hash"])
        self.assertEqual(doc["approval"]["approved_at"], "2026-10-11T18:00:00Z")
        self.assertTrue(overlay.is_approved(doc))
        doc["sessions"][0]["exercises"][0]["sets"][1]["reps"] = 6
        self.assertFalse(overlay.is_approved(doc))

    def test_dry_run_writes_nothing(self):
        root, path = self.unapproved_instance()
        before = files_under(root)
        data = self.run_ok("--root", str(root), "overlay", "approve", WEEKLY, "--dry-run", env=NOW)
        self.assertEqual(files_under(root), before)
        self.assertTrue(data["hash"].startswith("sha256:"))
        self.assertFalse(data["written"])

    def test_already_approved_is_left_alone(self):
        with Instance() as root:
            before = files_under(root)
            data = self.run_ok("--root", str(root), "overlay", "approve", WEEKLY, env=NOW)
            self.assertEqual(files_under(root), before)
        self.assertTrue(data["already_approved"])

    def test_unresolved_block_is_refused(self):
        root, path = self.unapproved_instance()
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["flags"] = [{"code": "stale_prescription", "severity": "block", "session_id": "session-a",
                         "exercise_id": "db_bench_press", "message": "Old exposure.", "resolved": False,
                         "resolution": None}]
        jsonio.write_doc(path, doc, False)
        envelope, _ = self.run_fail(3, "--root", str(root), "overlay", "approve", WEEKLY, env=NOW)
        self.assertIn("stale_prescription", envelope["error"]["details"][0]["message"])
        self.run_fail(3, "--root", str(root), "overlay", "approve", WEEKLY, "--dry-run", env=NOW)

    def test_invalid_overlay_is_not_approved(self):
        root, path = self.unapproved_instance()
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["sessions"][0]["exercises"][1]["sets"][1]["load"]["hevy_total"] = 25
        jsonio.write_doc(path, doc, False)
        self.run_fail(1, "--root", str(root), "overlay", "approve", WEEKLY, env=NOW)


class OverlayChecksTest(EnvelopeMixin, unittest.TestCase):
    CHECKS = ("overlay_schema", "overlay_arithmetic", "overlay_render_fresh")

    def statuses(self, root, check_id, ok=True):
        argv = ("--root", str(root), "check", "--only", check_id)
        if ok:
            data = self.run_ok(*argv)
        else:
            envelope, _ = self.run_fail(1, *argv)
            data = envelope["data"]
        return {row["status"] for row in data["results"]}, data["results"]

    def test_valid_fixture_passes_every_check(self):
        for check_id in self.CHECKS:
            with self.subTest(check=check_id):
                self.assertEqual(self.statuses(VALID, check_id)[0], {"pass"})

    def test_failing_fixtures(self):
        cases = [
            ("overlay-bad-schema", "overlay_schema", "$.sessions[1].date"),
            ("overlay-bad-arithmetic", "overlay_arithmetic", "hevy_total"),
            ("overlay-stale-render", "overlay_render_fresh", "2026-10-11.md"),
        ]
        for instance, check_id, expected in cases:
            with self.subTest(check=check_id):
                found, results = self.statuses(INSTANCES / instance, check_id, ok=False)
                self.assertIn("fail", found)
                self.assertIn(expected, json.dumps(results))

    def test_each_failing_fixture_fails_only_its_own_check(self):
        self.assertEqual(self.statuses(INSTANCES / "overlay-bad-arithmetic", "overlay_schema")[0], {"pass"})
        self.assertEqual(self.statuses(INSTANCES / "overlay-stale-render", "overlay_arithmetic")[0], {"pass"})

    def test_no_overlays_or_check_ins_skips(self):
        with Instance(MINIMAL_CONFIG, copy_valid=False) as root:
            for check_id in self.CHECKS:
                with self.subTest(check=check_id):
                    self.assertEqual(self.statuses(root, check_id)[0], {"skip"})

    def test_render_fresh_fails_on_a_missing_overlay(self):
        with Instance() as root:
            (root / "data" / "overlays" / f"{WEEKLY}.json").unlink()
            found, _ = self.statuses(root, "overlay_render_fresh", ok=False)
        self.assertIn("fail", found)


if __name__ == "__main__":
    unittest.main()
