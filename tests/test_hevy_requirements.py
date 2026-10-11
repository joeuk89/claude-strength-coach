"""Hevy mapping requirements and exact housekeeping writes, using only synthetic caches and clients."""

import copy
import json
import unittest
from unittest import mock

from coach import external, jsonio, library, program_drafts, state
from coach.hevy.cache import HevyCache
from coach.library import Library
from tests.test_library import CliMixin, Instance, read_library, write_library
from tests.test_library_seed import template
from tests.test_program_drafts import AdoptCase, SYNTHETIC, init_repo, snapshot
from tests.test_routines import ENV, R1, R2, WEEKLY, read_overlay, write_overlay
from tests.test_routines_create import (CREATE, ONE_OFF, T1, T2, CreateCase, GateMixin, OneOffCase, read_state,
                                        write_state)
from tests.test_starters import Case as StarterCase


class TemplateCacheTest(CliMixin, unittest.TestCase):
    def cache(self, root, items):
        HevyCache(root).write_collection("exercise_templates", items, "2026-10-11T18:00:00Z")

    def test_unique_full_cache_matches_without_any_routines(self):
        with Instance() as root:
            self.cache(root, [template("Butterfly (Pec Deck)", equipment="machine", tid="PEC"),
                              template("Bench Press (Dumbbell)", tid="BENCH")])
            self.assertEqual(Library.load(root).get("machine_pec_deck")["hevy_template_id"], "PEC")
            self.assertEqual(Library.load(root).get("db_bench_press")["hevy_template_id"], "BENCH")
            self.run_ok(root, "library", "seed")
            self.assertEqual(read_library(root)["exercises"]["machine_pec_deck"]["hevy_template_id"], "PEC")

    def test_ambiguous_requires_local_choice_and_choice_survives_seed_and_pull(self):
        with Instance() as root:
            items = [template("Butterfly (Pec Deck)", equipment="machine", tid=tid) for tid in ("P1", "P2")]
            self.cache(root, items)
            entry = Library.load(root).get("machine_pec_deck")
            self.assertIsNone(entry["hevy_template_id"])
            self.assertEqual(library.template_resolution(entry, items)["status"], "ambiguous")
            self.run_ok(root, "library", "set-template", "machine_pec_deck", "P2")
            self.cache(root, list(reversed(items)))
            self.run_ok(root, "library", "seed")
            self.assertEqual(Library.load(root).get("machine_pec_deck")["hevy_template_id"], "P2")
            before = (root / "data/exercises.json").read_bytes()
            self.run_fail(1, root, "library", "set-template", "machine_pec_deck", "UNKNOWN")
            self.assertEqual((root / "data/exercises.json").read_bytes(), before)

    def test_mapping_dry_run_is_local_and_read_only(self):
        with Instance() as root:
            self.cache(root, [template("Butterfly (Pec Deck)", equipment="machine", tid="P1")])
            before = snapshot(root)
            with mock.patch("coach.hevy.client.HevyClient.from_context", side_effect=AssertionError("network")):
                result = self.run_ok(root, "library", "set-template", "machine_pec_deck", "P1", "--dry-run")
            self.assertFalse(result["written"])
            self.assertEqual(snapshot(root), before)

    def test_no_match_is_explicit_and_custom_local_entry_survives(self):
        with Instance() as root:
            write_library(root, {"custom_local": {"name": "Local movement", "pattern": "carry",
                          "muscles": {"primary": ["full_body"], "secondary": []},
                          "equipment": "other", "load_mode_default": "total", "load_mode": "total"}})
            entry = Library.load(root).get("custom_local")
            self.assertEqual(library.template_resolution(entry, [])["status"], "missing")
            self.assertEqual(entry["load_mode"], "total")

    def test_explicit_identity_cannot_be_claimed_by_an_automatic_title_match(self):
        with Instance() as root:
            write_library(root, {"db_curl": {"hevy_template_id": "CHOSEN"}})
            self.cache(root, [template("Bench Press (Dumbbell)", tid="CHOSEN")])
            lib = Library.load(root)
            self.assertEqual(lib.by_hevy_template_id("CHOSEN")["id"], "db_curl")
            self.assertIsNone(lib.get("db_bench_press")["hevy_template_id"])
            self.run_ok(root, "library", "seed")
            self.assertIsNone(Library.load(root).get("db_bench_press")["hevy_template_id"])

    def test_set_template_refuses_an_id_another_exercise_owns_and_changes_nothing(self):
        with Instance() as root:
            write_library(root, {"db_curl": {"hevy_template_id": "CHOSEN"}})
            self.cache(root, [template("Bench Press (Dumbbell)", tid="CHOSEN")])
            before = snapshot(root)
            with mock.patch("coach.hevy.client.HevyClient.from_context", side_effect=AssertionError("network")):
                envelope = self.run_fail(1, root, "library", "set-template", "db_bench_press", "CHOSEN")
            self.assertIn("already belongs to db_curl", envelope["error"]["message"])
            self.assertEqual(snapshot(root), before)

    def test_multiple_verified_ids_without_primary_require_choice_even_with_one_cached(self):
        entry = Library({"schema_version": 1, "exercises": {
            "db_bench_press": {"hevy_template_ids": ["B1", "B2"]}}}).get("db_bench_press")
        result = library.template_resolution(entry, [template("Bench Press (Dumbbell)", tid="B1")])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["template_id"])


class RequirementsTest(CreateCase):
    def test_all_missing_templates_and_missing_session_are_reported_together(self):
        self.forget_session_b(approve=False)
        self.edit_overlay(lambda doc: [e.update(hevy_template_id=None) for s in doc["sessions"]
                                       for e in s["exercises"]], approve=False)
        before = snapshot(self.root)
        result = self.cli("routines", "preflight", "--overlay", WEEKLY)["data"]
        doc = read_overlay(self.root)
        self.assertEqual(len(result["templates"]), sum(len(s["exercises"]) for s in doc["sessions"]))
        self.assertEqual(result["sessions"][0]["session_id"], "session-b")
        self.assertTrue(all("set-template" in row["repair"] for row in result["templates"]))
        self.assertFalse(any("hevy pull" in row["repair"] for row in result["templates"]))
        self.cli("overlay", "approve", WEEKLY, expect=3)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.fake.writes, [])

    def test_disabled_hevy_does_not_block_local_approval(self):
        self.edit_overlay(lambda doc: [e.update(hevy_template_id=None) for s in doc["sessions"]
                                       for e in s["exercises"]], approve=False)
        config = self.root / "config.toml"
        config.write_text(config.read_text().replace("[hevy]\nenabled = true", "[hevy]\nenabled = false"))
        result = self.cli("routines", "preflight", "--overlay", WEEKLY)["data"]
        self.assertTrue(result["ready"])
        self.cli("overlay", "approve", WEEKLY)

    def test_preapproval_create_preview_needs_no_key_or_network_and_changes_no_file(self):
        self.forget_session_b(approve=False)
        before = snapshot(self.root)
        with mock.patch("coach.hevy.client.HevyClient.from_context", side_effect=AssertionError("network")):
            result = self.create("--dry-run", env={"COACH_NOW": ENV["COACH_NOW"]})["data"]
        self.assertEqual(result["routines"][0]["status"], "would_create")
        self.assertEqual(snapshot(self.root), before)

    def test_create_needs_the_exact_reviewed_plan(self):
        self.forget_session_b()
        before = snapshot(self.root)
        self.cli("routines", "create", "--overlay", WEEKLY, expect=3)
        preview = self.create("--dry-run")["data"]
        self.cli("routines", "create", "--overlay", WEEKLY, "--expect-plan", "wrong", expect=3)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.fake.writes, [])
        result = self.create("--expect-plan", preview["plan_hash"])["data"]
        self.assertEqual([r["session_id"] for r in result["routines"]], ["session-b"])
        self.assertEqual(len(self.fake.writes), 1)


class RedesignCase(CreateCase):
    def redesign(self):
        """Session A/B lose their mappings; the archive keeps them, and an unrelated routine sits in folder 9."""
        old = read_state(self.root)
        archive = self.root / "data/archive/programs/2026-10-10/state.json"
        jsonio.write_doc(archive, old, False)
        old["hevy"]["routines"] = {}
        write_state(self.root, old)
        self.edit_overlay(lambda doc: [s.update(hevy_routine_id=None) for s in doc["sessions"]])
        unrelated = copy.deepcopy(self.fake.collection("routines")[0])
        unrelated.update(id="unrelated", folder_id=9, title="Unrelated")
        self.fake.collection("routines").append(unrelated)
        HevyCache(self.root).upsert_routine(unrelated)


class OrphanTest(RedesignCase):
    def test_preview_identifies_orphans_and_new_routines_but_never_unrelated_folder(self):
        self.redesign()
        before = snapshot(self.root)
        preview = self.create("--dry-run")["data"]
        self.assertEqual({r["routine_id"] for r in preview["orphan_routines"]}, {R1, R2})
        self.assertEqual([r["status"] for r in preview["routines"]], ["would_create"] * 2)
        self.assertIn("leave, reuse, or retire", preview["summary"])
        self.assertEqual(snapshot(self.root), before)
        self.cli("routines", "retire", "--overlay", WEEKLY, "--routine", "unrelated", "--dry-run", expect=3)

    def test_reuse_updates_mapping_only_after_success_and_uses_the_reviewed_id(self):
        self.redesign()
        args = ("--reuse", f"session-a={R1}")
        preview = self.create(*args, "--dry-run")["data"]
        self.assertEqual(preview["routines"][0]["routine_id"], R1)
        self.assertIn(R1, preview["summary"])
        before = state.path_for(self.root).read_bytes()
        self.create("--reuse", f"session-a={R2}", "--expect-plan", preview["plan_hash"], expect=3)
        self.assertEqual(state.path_for(self.root).read_bytes(), before)
        self.assertEqual(self.fake.writes, [])
        with mock.patch("coach.hevy.client.HevyClient.put", side_effect=RuntimeError("synthetic failure")):
            self.create(*args, "--expect-plan", preview["plan_hash"], expect=9)
        self.assertEqual(state.path_for(self.root).read_bytes(), before)
        self.create(*args, "--expect-plan", preview["plan_hash"])
        self.assertEqual(read_state(self.root)["hevy"]["routines"][R1], {"session_id": "session-a"})
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}"])

    def test_retirement_only_writes_the_named_approved_orphan(self):
        self.redesign()
        args = ("routines", "retire", "--overlay", WEEKLY, "--routine", R1)
        preview = self.cli(*args, "--dry-run")["data"]
        self.assertIn(R1, preview["summary"])
        self.cli(*args, expect=3)
        self.cli("routines", "retire", "--overlay", WEEKLY, "--routine", R2,
                 "--expect-plan", preview["plan_hash"], expect=3)
        self.assertEqual(self.fake.writes, [])
        self.cli(*args, "--expect-plan", preview["plan_hash"])
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}"])
        self.assertEqual(external.orphan_routines(self.root)[0]["routine_id"], R2)


class AdoptionOrphanTest(AdoptCase):
    def test_replacing_imported_sessions_reports_old_managed_routines(self):
        root = self.instance()
        self.pull(root, SYNTHETIC)
        init_repo(root)
        draft = self.draft()
        draft = json.loads(json.dumps(draft).replace("session-a", "upper").replace("session-b", "lower"))
        draft["hevy_routines"] = {}
        before = snapshot(root)
        report = program_drafts.adopt(root, draft, replace=True, dry_run=True, today="2026-10-11")
        self.assertEqual({row["routine_id"] for row in report["orphan_routines"]}, {R1, R2})
        self.assertEqual(report["without_routine"], ["upper", "lower"])
        self.assertEqual(snapshot(root), before)
        program_drafts.adopt(root, draft, replace=True, today="2026-10-11")
        self.assertEqual({row["routine_id"] for row in external.orphan_routines(root)}, {R1, R2})


class StarterRequirementsTest(StarterCase):
    def test_first_starter_bench_and_create_preview_use_full_cache_without_old_routines(self):
        root, _ = self.adopted("full-body-3")
        proposal = self.ok(root, "propose", "week", "--week", "2026-W42")
        doc = proposal["overlay"]
        bench = next(e for s in doc["sessions"] for e in s["exercises"] if "bench_press" in e["exercise_id"])
        self.assertTrue(bench["hevy_template_id"].startswith("STARTER-"))
        self.assertEqual(HevyCache(root).routines(), [])
        self.ok(root, "propose", "finalize", "--proposal", doc["id"])
        before = snapshot(root)
        with mock.patch("coach.hevy.client.HevyClient.from_context", side_effect=AssertionError("network")):
            report = self.ok(root, "routines", "preflight", "--overlay", doc["id"])
            preview = self.ok(root, "routines", "create", "--overlay", doc["id"], "--dry-run")
        self.assertTrue(report["ready"])
        self.assertTrue(report["sessions"])
        self.assertTrue(all(r["status"] == "would_create" for r in preview["routines"]))
        self.assertEqual(snapshot(root), before)

    def test_proposal_flags_every_missing_template_even_without_a_routine(self):
        root, _ = self.adopted("full-body-3")
        HevyCache(root).path("exercise_templates.json").unlink()
        own = read_library(root)["exercises"]
        for entry in own.values():
            entry.pop("hevy_template_id", None)
            entry.pop("hevy_template_ids", None)
        write_library(root, own)
        result = self.ok(root, "propose", "week", "--week", "2026-W42", "--dry-run")
        doc = result["overlay"]
        expected = {(s["session_id"], e["exercise_id"]) for s in doc["sessions"] for e in s["exercises"]}
        unresolved = [f for f in doc["flags"] if f["code"] == "hevy_template_unresolved"]
        self.assertEqual({(f["session_id"], f["exercise_id"]) for f in unresolved}, expected)
        self.assertTrue(all("hevy pull" in f["message"] for f in unresolved))
        self.assertIn("hevy_routine_unmapped", {f["code"] for f in doc["flags"]})


class TemporaryPlanTest(OneOffCase):
    def test_a_changed_spare_cannot_replace_the_reviewed_action(self):
        preview = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        before = state.path_for(self.root).read_bytes()
        spare = next(r for r in self.fake.collection("routines") if r["id"] == T1)
        spare.update(title="Changed after preview", updated_at="2026-10-11T19:00:00Z")
        self.create("--expect-plan", preview["plan_hash"], overlay_id=ONE_OFF, expect=3)
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(state.path_for(self.root).read_bytes(), before)

    def test_explicit_later_reuse_is_reserved_before_automatic_selection(self):
        args = ("--reuse", f"travel-c={T1}")
        preview = self.create(*args, "--dry-run", overlay_id=ONE_OFF)["data"]
        self.assertEqual([r["routine_id"] for r in preview["routines"]], [T2, None, T1])
        self.create(*args, "--expect-plan", preview["plan_hash"], overlay_id=ONE_OFF)
        self.assertEqual(self.put_paths, [f"/v1/routines/{T2}", f"/v1/routines/{T1}"])

    def test_the_plan_hash_is_the_canonical_hash(self):
        preview = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        self.assertRegex(preview["plan_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_a_by_id_read_with_extra_fields_still_matches_the_reviewed_plan(self):
        preview = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        for routine in self.fake.collection("routines"):
            routine["only_on_get"] = "field the list endpoint leaves out"
        self.create("--expect-plan", preview["plan_hash"], overlay_id=ONE_OFF)
        self.assertEqual(self.put_paths, [f"/v1/routines/{T1}", f"/v1/routines/{T2}"])

    def test_an_orphan_reused_for_a_temporary_session_is_no_longer_reported_unmapped(self):
        old = read_state(self.root)
        jsonio.write_doc(self.root / "data/archive/programs/2026-10-10/state.json", old, False)
        old["hevy"]["routines"].pop(R1)
        write_state(self.root, old)
        self.assertIn(R1, {r["routine_id"] for r in external.orphan_routines(self.root)})
        args = ("--reuse", f"travel-a={R1}")
        preview = self.create(*args, "--dry-run", overlay_id=ONE_OFF)["data"]
        self.create(*args, "--expect-plan", preview["plan_hash"], overlay_id=ONE_OFF)
        self.assertNotIn(R1, {r["routine_id"] for r in external.orphan_routines(self.root)})
        again = self.create("--dry-run", overlay_id=ONE_OFF)["data"]
        self.assertEqual(again["orphan_routines"], [])
        self.assertNotIn("now unmapped", again["summary"])


class ReuseRefusalTest(OneOffCase):
    """Every malformed, unrelated, busy or duplicate --reuse refuses before any file or Hevy change."""

    def setUp(self):
        super().setUp()
        old = read_state(self.root)
        jsonio.write_doc(self.root / "data/archive/programs/2026-10-10/state.json", old, False)
        old["hevy"]["routines"].pop(R2)
        old["hevy"]["temporary_routines"][1].update(overlay_id="2026-10-05-one-off", session_id="other")
        write_state(self.root, old)
        live = read_overlay(self.root, ONE_OFF)
        live.update(id="2026-10-05-one-off", span={"start": "2026-10-05", "end": "2026-10-13"},
                    created_at="2026-10-04T08:00:00Z", approval=None)
        live["sessions"] = [dict(live["sessions"][0], session_id="other", date="2026-10-13")]
        write_overlay(self.root, live)
        unrelated = copy.deepcopy(self.fake.collection("routines")[0])
        unrelated.update(id="unrelated", folder_id=9, title="Unrelated")
        self.fake.collection("routines").append(unrelated)
        HevyCache(self.root).upsert_routine(unrelated)

    def test_each_bad_choice_refuses_with_no_change(self):
        cases = {
            "malformed": (["travel-a"], "Cannot reuse"),
            "unknown session": ([f"travel-z={T1}"], "Cannot reuse"),
            "unrelated routine": (["travel-a=unrelated"], "Cannot reuse"),
            "actively mapped routine": ([f"travel-a={R1}"], "Cannot reuse"),
            "busy in another live overlay": ([f"travel-a={T2}"], "Cannot reuse"),
            "duplicate routine": ([f"travel-a={T1}", f"travel-b={T1}"], "distinct"),
            "duplicate session": ([f"travel-a={T1}", f"travel-a={R2}"], "distinct"),
        }
        self.assertEqual({r["routine_id"] for r in external.orphan_routines(self.root)}, {R2})
        before = snapshot(self.root)
        for name, (choices, message) in cases.items():
            args = [arg for choice in choices for arg in ("--reuse", choice)]
            with self.subTest(name):
                for extra in (("--dry-run",), ("--expect-plan", "sha256:any")):
                    envelope = self.create(*args, *extra, overlay_id=ONE_OFF, expect=3)
                    self.assertIn(message, envelope["error"]["message"])
                self.assertEqual(snapshot(self.root), before)
                self.assertEqual(self.fake.writes, [])


class PlanGateTest(GateMixin, RedesignCase):
    """The gate denies an approved create or retire unless --expect-plan names the reviewed plan."""

    def assert_denied(self, decision):
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("--expect-plan", decision["permissionDecisionReason"])

    def test_an_approved_create_without_or_with_a_wrong_hash_is_denied(self):
        self.forget_session_b()
        for command in (CREATE, CREATE + " --expect-plan sha256:wrong"):
            with self.subTest(command=command):
                self.assert_denied(self.decide(command))
                self.assert_denied(self.pipe(command))
        self.assertEqual(self.fake.writes, [])

    def test_an_orphan_retire_without_or_with_a_wrong_hash_is_denied(self):
        self.redesign()
        retire = f"python3 -m coach routines retire --overlay {WEEKLY} --routine {R1}"
        for command in (retire, retire + " --expect-plan sha256:wrong"):
            with self.subTest(command=command):
                self.assert_denied(self.decide(command))
                self.assert_denied(self.pipe(command))
        preview = self.cli("routines", "retire", "--overlay", WEEKLY, "--routine", R1, "--dry-run")["data"]
        self.assertEqual(self.decide(f"{retire} --expect-plan {preview['plan_hash']}")["permissionDecision"], "ask")
        self.assertEqual(self.fake.writes, [])

    def test_a_retire_with_nothing_to_retire_needs_no_hash_in_the_cli_or_the_gate(self):
        ended = dict(ENV, COACH_NOW="2026-10-19T08:00:00Z")
        envelope = self.cli("routines", "retire", "--overlay", WEEKLY, env=ended)
        self.assertEqual(envelope["data"]["routines"], [])
        self.assertNotIn("plan_hash", envelope["data"])
        decision = self.decide(f"python3 -m coach routines retire --overlay {WEEKLY}", env=ended)
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertEqual(self.fake.writes, [])
