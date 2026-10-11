"""`routines create`, and diff and push finding routines through state.json (contract C9, C12, C16)."""

import copy
import json
import os
import subprocess
import sys
import unittest

from coach import gate, jsonio, routines, state
from coach.hevy.cache import HevyCache
from coach.validate import validate
from tests.support import REPO_ROOT
from tests.test_gate import hook_input, output
from tests.test_routines import (ENV, NOW, R1, R2, SYNTHETIC, WEEKLY, RoutinesCase, approved, audit_lines,
                                 nulls, read_overlay, write_overlay)

ONE_OFF = "2026-10-12-one-off"
T1 = "00000000-0000-4000-8000-0000000000a1"
T2 = "00000000-0000-4000-8000-0000000000a2"
CREATE = f"python3 -m coach routines create --overlay {WEEKLY}"


def read_state(root):
    return json.loads(state.path_for(root).read_text(encoding="utf-8"))


def write_state(root, doc):
    jsonio.write_doc(state.path_for(root), doc, dry_run=False)


class CreateCase(RoutinesCase):
    def forget_session_b(self, approve=True):
        """Session B has no routine in the overlay or in state.json."""
        self.edit_overlay(lambda doc: doc["sessions"][1].update(hevy_routine_id=None), approve=approve)
        doc = read_state(self.root)
        doc["hevy"]["routines"].pop(R2, None)
        write_state(self.root, doc)

    def create(self, *extra, overlay_id=WEEKLY, expect=0, env=None):
        if not extra and expect == 0:
            preview = self.cli("routines", "create", "--overlay", overlay_id, "--dry-run", env=env)["data"]
            if preview.get("plan_hash"):
                extra = ("--expect-plan", preview["plan_hash"])
        return self.cli("routines", "create", "--overlay", overlay_id, *extra, expect=expect, env=env)

    @property
    def posts(self):
        return [(path, body) for method, path, body in self.fake.writes if method == "POST"]


class CreateTest(CreateCase):
    def test_creates_the_missing_routine_records_it_in_state_and_leaves_the_overlay_alone(self):
        self.forget_session_b()
        overlay_bytes = (self.root / "data" / "overlays" / f"{WEEKLY}.json").read_bytes()
        data = self.create()["data"]

        self.assertEqual([path for path, _ in self.posts], ["/v1/routines"])
        body = self.posts[0][1]["routine"]
        self.assertEqual(body["title"], "Session B")
        self.assertEqual(body["folder_id"], 1)
        self.assertEqual(nulls(body), [])
        self.assertNotIn("notes", body)
        new_id = self.fake.collection("routines")[-1]["id"]

        recorded = read_state(self.root)["hevy"]["routines"]
        self.assertEqual(recorded[new_id], {"session_id": "session-b"})
        self.assertEqual((self.root / "data" / "overlays" / f"{WEEKLY}.json").read_bytes(), overlay_bytes)

        lines = audit_lines(self.root)
        self.assertEqual([(l["kind"], l["routine_id"]) for l in lines], [("write", new_id), ("verify", new_id)])
        self.assertEqual(lines[0]["method"], "POST")
        for line in lines:
            schema = {"write": "hevy_write_line", "verify": "hevy_verify_line"}[line["kind"]]
            self.assertEqual(validate(line, jsonio.load_schema(schema)), [], line)
        self.assertTrue(lines[1]["verified"])
        self.assertEqual([(r["session_id"], r["routine_id"], r["status"]) for r in data["routines"]],
                         [("session-b", new_id, "created")])
        self.assertEqual(data["writes"], 1)

        again = self.create()["data"]
        self.assertEqual(len(self.fake.writes), 1)
        self.assertEqual((again["routines"], again["writes"]), ([], 0))

        pushed = self.routines_cmd("push")["data"]
        self.assertEqual([r["routine_id"] for r in pushed["routines"]], [R1, new_id])
        self.assertEqual(pushed["routines"][1]["status"], "unchanged")
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}"])
        self.assertEqual(self.routines_cmd("diff")["data"]["routines"][1]["routine_id"], new_id)

    def test_unapproved_exits_3_with_no_writes(self):
        self.forget_session_b(approve=False)
        state_before = state.path_for(self.root).read_bytes()
        envelope = self.create(expect=3)
        self.assertEqual(envelope["error"]["code"], "refused")
        self.assertIn("not approved", envelope["error"]["message"])
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(audit_lines(self.root), [])
        self.assertEqual(state.path_for(self.root).read_bytes(), state_before)

    def test_ended_overlay_is_refused(self):
        self.forget_session_b()
        self.create(expect=3, env=dict(ENV, COACH_NOW="2026-10-19T08:00:00Z"))
        self.assertEqual(self.fake.writes, [])

    def test_dry_run_writes_nothing_and_says_what_it_would_create(self):
        self.forget_session_b()
        state_before = state.path_for(self.root).read_bytes()
        data = self.create("--dry-run")["data"]
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(audit_lines(self.root), [])
        self.assertEqual(state.path_for(self.root).read_bytes(), state_before)
        self.assertEqual([(r["session_id"], r["routine_id"], r["status"]) for r in data["routines"]],
                         [("session-b", None, "would_create")])
        self.assertIn("Session B", data["summary"])
        self.assertIn("Target:", data["summary"])

    def test_a_routine_state_already_records_is_found_and_nothing_is_created(self):
        self.edit_overlay(lambda doc: doc["sessions"][1].update(hevy_routine_id=None))
        data = self.create()["data"]
        self.assertEqual((data["routines"], self.fake.writes), ([], []))
        pushed = self.routines_cmd("push")["data"]
        self.assertEqual([r["routine_id"] for r in pushed["routines"]], [R1, R2])

    def test_a_session_neither_names_still_stops_push_and_points_at_create(self):
        self.forget_session_b()
        envelope = self.routines_cmd("push", expect=1)
        self.assertIn("routines create", envelope["error"]["message"])
        self.assertEqual(self.fake.writes, [])

    def test_a_non_temporary_session_the_program_lacks_exits_1(self):
        def rename(doc):
            doc["sessions"][1].update(hevy_routine_id=None, session_id="session-z")
        self.edit_overlay(rename)
        envelope = self.create(expect=1)
        self.assertIn("session-z", envelope["error"]["message"])
        self.assertEqual(self.fake.writes, [])

    def test_without_state_exits_1(self):
        self.forget_session_b()
        state.path_for(self.root).unlink()
        self.assertIn("state.json", self.create(expect=1)["error"]["message"])
        self.assertEqual(self.fake.writes, [])

    def test_a_failed_read_back_exits_1_and_keeps_the_new_id(self):
        self.forget_session_b()
        original = self.fake._stored_routine

        def drop_a_set(request, existing):
            stored = original(request, existing)
            stored["exercises"][0]["sets"].pop()
            return stored
        self.fake._stored_routine = drop_a_set
        preview = self.create("--dry-run")["data"]
        envelope = self.create("--expect-plan", preview["plan_hash"], expect=1)
        new_id = self.fake.collection("routines")[-1]["id"]
        self.assertEqual(read_state(self.root)["hevy"]["routines"][new_id], {"session_id": "session-b"})
        self.assertFalse(audit_lines(self.root)[-1]["verified"])
        self.assertEqual(envelope["data"]["routines"][0]["status"], "failed")


class OneOffCase(CreateCase):
    """A one-off overlay of three temporary travel sessions, with spare temporary routines T1 and T2."""

    def setUp(self):
        super().setUp()
        doc = read_overlay(self.root)
        doc.update(id=ONE_OFF, kind="one_off", approval=None, focus="Travel week: hotel gym.")
        friday = copy.deepcopy(doc["sessions"][0])
        friday.update(session_id="travel-c", date="2026-10-16", title="Travel C")
        doc["sessions"].append(friday)
        for session, name in zip(doc["sessions"], ("travel-a", "travel-b", "travel-c")):
            session.update(session_id=name, title=f"Travel {name[-1].upper()}", hevy_routine_id=None,
                           temporary=True, location=None)
        write_overlay(self.root, approved(doc))
        (self.root / "data" / "overlays" / f"{WEEKLY}.json").unlink()
        for routine_id, title in ((T1, "(unused)"), (T2, "(unused)")):
            spare = copy.deepcopy(self.fake.collection("routines")[0])
            spare.update(id=routine_id, title=title, folder_id=None)
            self.fake.collection("routines").append(spare)
            HevyCache(self.root).upsert_routine(spare)
        doc = read_state(self.root)
        doc["hevy"]["temporary_routines"] = [
            {"routine_id": T1, "overlay_id": None, "session_id": None},
            {"routine_id": T2, "overlay_id": "2026-09-28-one-off", "session_id": "old-a"},
        ]
        write_state(self.root, doc)


class OneOffCreateTest(OneOffCase):
    def test_creates_the_folder_once_reuses_two_and_creates_one(self):
        data = self.create(overlay_id=ONE_OFF)["data"]
        self.assertEqual([path for path, _ in self.posts], ["/v1/routine_folders", "/v1/routines"])
        self.assertEqual(self.posts[0][1], {"routine_folder": {"title": "One-off weeks"}})
        folder_id = self.fake.collection("routine_folders")[-1]["id"]
        self.assertEqual(self.posts[1][1]["routine"]["folder_id"], folder_id)
        self.assertEqual(self.posts[1][1]["routine"]["title"], "Travel C")
        self.assertEqual(self.put_paths, [f"/v1/routines/{T1}", f"/v1/routines/{T2}"])
        self.assertEqual([b["routine"]["title"] for b in self.fake.put_bodies], ["Travel A", "Travel B"])
        new_id = self.fake.collection("routines")[-1]["id"]

        hevy = read_state(self.root)["hevy"]
        self.assertEqual(hevy["folders"], {"program": 1, "one_off": folder_id})
        self.assertEqual(hevy["temporary_routines"], [
            {"routine_id": T1, "overlay_id": ONE_OFF, "session_id": "travel-a"},
            {"routine_id": T2, "overlay_id": ONE_OFF, "session_id": "travel-b"},
            {"routine_id": new_id, "overlay_id": ONE_OFF, "session_id": "travel-c"},
        ])
        self.assertEqual(state.problems(state.load(self.root)), [])
        self.assertEqual([r["status"] for r in data["routines"]], ["reused", "reused", "created"])
        self.assertEqual(data["folder"]["status"], "created")
        self.assertEqual([l["kind"] for l in audit_lines(self.root)],
                         ["write", "write", "verify", "write", "verify", "write", "verify"])

        again = self.create(overlay_id=ONE_OFF)["data"]
        self.assertEqual((again["routines"], again["writes"]), ([], 0))
        self.assertEqual(len(self.fake.writes), 4)
        pushed = self.cli("routines", "push", "--overlay", ONE_OFF, "--refresh")["data"]
        self.assertEqual([r["status"] for r in pushed["routines"]], ["unchanged"] * 3)
        self.assertEqual(len(self.fake.writes), 4)

    def test_a_recorded_folder_is_used_and_not_created(self):
        doc = read_state(self.root)
        doc["hevy"]["folders"]["one_off"] = 7
        write_state(self.root, doc)
        self.create(overlay_id=ONE_OFF)
        self.assertEqual([path for path, _ in self.posts], ["/v1/routines"])
        self.assertEqual(self.posts[0][1]["routine"]["folder_id"], 7)

    def test_a_routine_a_live_overlay_carries_is_not_reused(self):
        doc = read_state(self.root)
        doc["hevy"]["temporary_routines"][1].update(overlay_id="2026-10-05-one-off", session_id="other")
        write_state(self.root, doc)
        live = read_overlay(self.root, ONE_OFF)
        live.update(id="2026-10-05-one-off", span={"start": "2026-10-05", "end": "2026-10-13"},
                    created_at="2026-10-04T08:00:00Z", approval=None)
        live["sessions"] = [dict(live["sessions"][0], session_id="other", date="2026-10-13")]
        write_overlay(self.root, live)
        data = self.create(overlay_id=ONE_OFF)["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{T1}"])
        self.assertEqual([r["status"] for r in data["routines"]], ["reused", "created", "created"])

    def test_a_spare_hevy_no_longer_has_is_skipped_and_dropped_from_state(self):
        self.fake.collection("routines")[:] = [r for r in self.fake.collection("routines") if r["id"] != T1]
        self.cli("hevy", "pull", "--full")
        dry = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        self.assertEqual(dry["stale"], [T1])
        self.assertIn(f"Hevy no longer has temporary routine(s) {T1}", dry["summary"])
        self.assertEqual(len(read_state(self.root)["hevy"]["temporary_routines"]), 2)

        data = self.create(overlay_id=ONE_OFF)["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{T2}"])
        self.assertEqual([r["status"] for r in data["routines"]], ["reused", "created", "created"])
        carriers = read_state(self.root)["hevy"]["temporary_routines"]
        self.assertNotIn(T1, [entry["routine_id"] for entry in carriers])
        self.assertEqual([entry["session_id"] for entry in carriers], ["travel-a", "travel-b", "travel-c"])

    def test_dry_run_names_the_folder_and_the_reuse(self):
        data = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(data["folder"]["status"], "would_create")
        self.assertEqual([r["status"] for r in data["routines"]], ["would_reuse", "would_reuse", "would_create"])
        self.assertIn("One-off weeks", data["summary"])
        self.assertIn("(unused)", data["summary"])

    def test_retire_finds_the_routines_through_state(self):
        self.create(overlay_id=ONE_OFF)
        preview = self.cli("routines", "retire", "--overlay", ONE_OFF, "--dry-run",
                           env=dict(ENV, COACH_NOW="2026-10-19T08:00:00Z"))["data"]
        data = self.cli("routines", "retire", "--overlay", ONE_OFF, "--expect-plan", preview["plan_hash"],
                        env=dict(ENV, COACH_NOW="2026-10-19T08:00:00Z"))["data"]
        self.assertEqual([r["status"] for r in data["routines"]], ["retired"] * 3)


class GateMixin:
    """The permission gate in process (`decide`) and as Claude Code runs it (`pipe`)."""

    def decide(self, command, mode="default", env=None):
        return output(gate.decide(hook_input(command, self.root, mode), env=env or ENV))

    def pipe(self, command):
        env = {k: v for k, v in os.environ.items() if not k.startswith("COACH_") and k != "HEVY_API_KEY"}
        env.update(COACH_NOW=NOW, COACH_HEVY_FIXTURES=str(SYNTHETIC))
        proc = subprocess.run([sys.executable, "-m", "coach", "gate", "pretooluse"],
                              input=json.dumps(hook_input(command, self.root)), cwd=str(REPO_ROOT), env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return output(json.loads(proc.stdout))


class CreateGateTest(GateMixin, CreateCase):

    def test_an_approved_create_asks_with_the_summary(self):
        self.forget_session_b()
        preview = self.create("--dry-run")["data"]
        decision = self.decide(CREATE + " --expect-plan " + preview["plan_hash"])
        self.assertEqual(decision["permissionDecision"], "ask")
        reason = decision["permissionDecisionReason"]
        for text in ("routines create", "Session B", WEEKLY, "new routine"):
            self.assertIn(text, reason)
        self.assertEqual(self.fake.writes, [])

    def test_an_unapproved_create_is_denied(self):
        self.forget_session_b(approve=False)
        decision = self.decide(CREATE)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("not approved", decision["permissionDecisionReason"])

    def test_bypass_mode_is_denied(self):
        self.forget_session_b()
        self.assertEqual(self.decide(CREATE, mode="bypassPermissions")["permissionDecision"], "deny")


class CreateHookProcessTest(GateMixin, CreateCase):
    """`python3 -m coach gate pretooluse` as Claude Code runs it, replaying the synthetic fixtures."""

    def test_ask_with_the_summary_when_approved_and_deny_when_not(self):
        self.forget_session_b()
        preview = self.create("--dry-run")["data"]
        decision = self.pipe(CREATE + " --expect-plan " + preview["plan_hash"])
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("Session B (Thu 15 Oct): new routine in folder 1", decision["permissionDecisionReason"])
        self.forget_session_b(approve=False)
        decision = self.pipe(CREATE)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("not approved", decision["permissionDecisionReason"])


class CreateSummaryTest(CreateCase):
    def test_both_dumbbell_numbers_reach_the_summary(self):
        self.edit_overlay(lambda doc: doc["sessions"][0].update(hevy_routine_id=None))
        doc = read_state(self.root)
        del doc["hevy"]["routines"][R1]
        write_state(self.root, doc)
        summary = self.create("--dry-run")["data"]["summary"]
        self.assertIn("25/hand (Hevy: 50)", summary)
        self.assertIn("Session A", summary)


class DriftCheckAfterCreateTest(CreateCase):
    def drift(self):
        envelope = self.cli("check", "--only", "overlay_hevy_drift", expect=0)
        return [r["message"] for r in envelope["data"]["results"]]

    def test_the_check_finds_a_created_routine_through_state(self):
        self.forget_session_b()
        missing = [m for m in self.drift() if "has no Hevy routine" in m]
        self.assertEqual(len(missing), 1)
        self.assertIn("routines create", missing[0])
        self.create()
        self.assertFalse([m for m in self.drift() if "has no Hevy routine" in m or "Session B" in m])


class ResolutionTest(CreateCase):
    def test_two_routines_for_one_session_is_a_validation_error(self):
        self.edit_overlay(lambda doc: doc["sessions"][1].update(hevy_routine_id=None))
        doc = read_state(self.root)
        doc["hevy"]["routines"][T1] = {"session_id": "session-b"}
        write_state(self.root, doc)
        envelope = self.routines_cmd("diff", expect=1)
        self.assertIn("session-b", envelope["error"]["message"])

    def test_the_overlay_id_wins_over_state(self):
        doc = read_state(self.root)
        doc["hevy"]["routines"] = {T1: {"session_id": "session-a"}}
        write_state(self.root, doc)
        overlay_doc = read_overlay(self.root)
        self.assertEqual(routines.session_routines(self.root, overlay_doc), [R1, R2])


if __name__ == "__main__":
    unittest.main()
