"""Seeding the instance library from the Hevy cache: matching, the heuristic rows, the command."""

import json
import unittest

from coach import library
from coach.library import Library
from tests.support import INSTANCES, run_cli
from tests.test_library import CliMixin, Instance, read_library, write_library

SEED = INSTANCES / "library-seed"


def template(title, type_="weight_reps", equipment="dumbbell", primary="chest", secondary=(), custom=False, tid="T1"):
    return {"id": tid, "title": title, "type": type_, "equipment": equipment, "primary_muscle_group": primary,
            "secondary_muscle_groups": list(secondary), "is_custom": custom}


def propose(title, lib=None, tid="T1", **kwargs):
    lib = lib or Library()
    return library.propose(lib, tid, title, template(title, tid=tid, **kwargs))


class MatchOrderTest(unittest.TestCase):
    def test_template_id_beats_title(self):
        lib = Library({"schema_version": 1, "exercises": {"db_curl": {"hevy_template_id": "T1"}}})
        proposal = propose("Bench Press (Dumbbell)", lib)
        self.assertEqual((proposal["matched_id"], proposal["matched_by"]), ("db_curl", "template_id"))

    def test_hevy_title_beats_alias(self):
        proposal = propose("Bench Press (Dumbbell)")
        self.assertEqual((proposal["matched_id"], proposal["matched_by"]), ("db_bench_press", "hevy_title"))

    def test_alias(self):
        proposal = propose("Flat Dumbbell Press")
        self.assertEqual((proposal["matched_id"], proposal["matched_by"]), ("db_bench_press", "alias"))

    def test_no_match(self):
        proposal = propose("Tyre Flip", equipment="other")
        self.assertEqual((proposal["matched_id"], proposal["matched_by"]), (None, None))


class HeuristicRowTest(unittest.TestCase):
    """One test per row of the seed heuristic table (contract C5)."""

    def assert_proposal(self, proposal, mode, confidence, rule):
        self.assertEqual(
            (proposal["load_mode_proposed"], proposal["confidence"], proposal["rule"]), (mode, confidence, rule)
        )

    def test_hevy_type_fixes_the_mode(self):
        cases = [
            ("Plank", "duration", "none", "duration"),
            ("Running", "distance_duration", "none", "distance"),
            ("Pull Up (Assisted)", "bodyweight_assisted_reps", "machine", "assisted"),
            ("Pull Up", "bodyweight_reps", "none", "bodyweight"),
            ("Band Pull Apart", "reps_only", "resistance_band", "band"),
            ("Dead Bug", "reps_only", "none", "bodyweight"),
        ]
        for title, type_, equipment, mode in cases:
            with self.subTest(title=title):
                self.assert_proposal(propose(title, type_=type_, equipment=equipment), mode, "high", "hevy_type")

    def test_hevy_type_disagreeing_with_the_entry_is_low(self):
        proposal = propose("Bench Press (Dumbbell)", type_="duration")
        self.assert_proposal(proposal, "duration", "low", "hevy_type")

    def test_alternating_title(self):
        self.assert_proposal(propose("Alternating Bicep Curl (Dumbbell)"), "single_implement", "high", "alternating")

    def test_one_arm_title(self):
        for title in ("Single Arm Lateral Raise (Dumbbell)", "One-Arm Overhead Press (Dumbbell)"):
            with self.subTest(title=title):
                self.assert_proposal(propose(title), "single_implement", "high", "one_arm")

    def test_one_arm_cable_work_stays_with_the_stack(self):
        proposal = propose("Single Arm Lateral Raise (Cable)", equipment="machine")
        self.assert_proposal(proposal, "total", "high", "matched")

    def test_matched_entry_consistent_with_hevy_equipment(self):
        self.assert_proposal(propose("Bench Press (Dumbbell)"), "per_hand_x2", "high", "matched")
        self.assert_proposal(propose("Squat (Barbell)", equipment="barbell"), "total", "high", "matched")
        self.assert_proposal(propose("Dumbbell Row"), "single_implement", "high", "matched")

    def test_matched_entry_inconsistent_with_hevy_equipment_is_low(self):
        self.assert_proposal(propose("Bench Press (Dumbbell)", equipment="barbell"), "per_hand_x2", "low", "matched")

    def test_alias_match_is_low(self):
        self.assert_proposal(propose("Flat Dumbbell Press"), "per_hand_x2", "low", "alias")

    def test_custom_entry_match_stays_low(self):
        lib = Library({"schema_version": 1, "exercises": {"custom_tyre_flip": library.custom_entry(
            "C0000001", "Tyre Flip", template("Tyre Flip", equipment="other"), "total")}})
        proposal = library.propose(lib, "C0000001", "Tyre Flip", template("Tyre Flip", equipment="other"))
        self.assertEqual(proposal["matched_by"], "template_id")
        self.assert_proposal(proposal, "total", "low", "custom")

    def test_no_match_falls_back_to_hevy_equipment(self):
        cases = [
            ("dumbbell", "per_hand_x2"), ("kettlebell", "single_implement"), ("barbell", "total"),
            ("machine", "total"), ("plate", "total"), ("other", "total"), ("resistance_band", "band"),
            ("none", "bodyweight"), ("suspension", "bodyweight"),
        ]
        for equipment, mode in cases:
            with self.subTest(equipment=equipment):
                self.assert_proposal(propose("Mystery Lift", equipment=equipment), mode, "low", "equipment")

    def test_no_template_and_no_match(self):
        proposal = library.propose(Library(), "T9", "Mystery Lift", None)
        self.assert_proposal(proposal, "total", "low", "equipment")


class CustomEntryTest(unittest.TestCase):
    def test_fields_come_from_the_template(self):
        tpl = template("Tyre Flip", equipment="other", primary="full_body", secondary=["quadriceps", "shoulders"],
                       custom=True, tid="C0000001")
        entry = library.custom_entry("C0000001", "Tyre Flip", tpl, "total")
        self.assertEqual(entry["name"], "Tyre Flip")
        self.assertEqual(entry["hevy_titles"], ["Tyre Flip"])
        self.assertEqual(entry["muscles"], {"primary": ["full_body"], "secondary": ["quadriceps", "front_delts"]})
        self.assertEqual(entry["equipment"], "other")
        self.assertEqual(entry["pattern"], "conditioning")
        self.assertEqual(entry["load_mode_default"], "total")
        self.assertEqual(entry["hevy_template_id"], "C0000001")

    def test_shoulders_split_by_title(self):
        tpl = template("Leaning Lateral Raise", primary="shoulders")
        self.assertEqual(library.custom_entry("T1", tpl["title"], tpl, "per_hand_x2")["muscles"]["primary"], ["side_delts"])
        tpl = template("Bent Over Rear Raise", primary="shoulders")
        self.assertEqual(library.custom_entry("T1", tpl["title"], tpl, "per_hand_x2")["muscles"]["primary"], ["rear_delts"])

    def test_cardio_machine(self):
        tpl = template("Assault Bike", type_="duration", equipment="machine", primary="cardio")
        entry = library.custom_entry("T1", tpl["title"], tpl, "duration")
        self.assertEqual((entry["equipment"], entry["pattern"]), ("cardio_machine", "conditioning"))

    def test_slug(self):
        self.assertEqual(library.custom_id("Tyre Flip (Heavy!)", set()), "custom_tyre_flip_heavy")
        self.assertEqual(library.custom_id("Tyre Flip", {"custom_tyre_flip"}), "custom_tyre_flip_2")


class SeedCommandTest(CliMixin, unittest.TestCase):
    def test_dry_run_lists_one_proposal_per_distinct_exercise_and_writes_nothing(self):
        with Instance(SEED) as root:
            data = self.run_ok(root, "library", "seed", "--dry-run")
            self.assertFalse((root / "data" / "exercises.json").exists())
        proposals = {p["hevy_template_id"]: p for p in data["proposals"]}
        self.assertEqual(list(proposals), ["F0000001", "F0000002", "F0000003", "F0000004", "C0000001"])
        expected = {
            "F0000001": ("bb_back_squat", "total", "high"),
            "F0000002": ("db_bench_press", "per_hand_x2", "high"),
            "F0000003": ("db_single_arm_row", "single_implement", "high"),
            "F0000004": ("pull_up", "bodyweight", "high"),
            "C0000001": ("custom_tyre_flip", "total", "low"),
        }
        for tid, (matched_id, mode, confidence) in expected.items():
            with self.subTest(tid=tid):
                p = proposals[tid]
                self.assertEqual((p["matched_id"], p["load_mode_proposed"], p["confidence"]), (matched_id, mode, confidence))
        self.assertEqual(proposals["F0000002"]["routines"], ["Session A", "Session B"])
        self.assertEqual(proposals["C0000001"]["matched_by"], "custom")
        self.assertFalse(data["written"])

    def test_seed_writes_the_instance_file_then_confirm_all(self):
        with Instance(SEED) as root:
            data = self.run_ok(root, "library", "seed")
            self.assertTrue(data["written"])
            doc = read_library(root)
            self.assertEqual(doc["schema_version"], 1)
            self.assertEqual(set(doc["exercises"]),
                             {"bb_back_squat", "db_bench_press", "db_single_arm_row", "pull_up", "custom_tyre_flip"})
            bench = doc["exercises"]["db_bench_press"]
            self.assertEqual(bench["hevy_template_id"], "F0000002")
            self.assertEqual(bench["load_mode_proposed"], "per_hand_x2")
            self.assertIsNone(bench["load_mode"])
            custom = doc["exercises"]["custom_tyre_flip"]
            self.assertEqual(custom["name"], "Tyre Flip")
            self.assertEqual(custom["hevy_template_id"], "C0000001")
            self.assertEqual(custom["equipment"], "other")
            self.assertEqual(custom["muscles"]["primary"], ["full_body"])

            self.run_ok(root, "library", "confirm", "--all")
            doc = read_library(root)
            modes = {i: e["load_mode"] for i, e in doc["exercises"].items()}
            self.assertEqual(modes, {
                "bb_back_squat": "total", "db_bench_press": "per_hand_x2", "db_single_arm_row": "single_implement",
                "pull_up": "bodyweight", "custom_tyre_flip": "total",
            })
            self.run_ok(root, "check", "--only", "load_modes_confirmed,library_valid")

    def test_seed_twice_changes_nothing(self):
        with Instance(SEED) as root:
            self.run_ok(root, "library", "seed")
            first = read_library(root)
            data = self.run_ok(root, "library", "seed")
            self.assertEqual(read_library(root), first)
        self.assertEqual({p["action"] for p in data["proposals"]}, {"unchanged"})

    def test_seed_keeps_a_confirmed_mode(self):
        with Instance(SEED) as root:
            write_library(root, {"db_bench_press": {"load_mode": "single_implement"}})
            data = self.run_ok(root, "library", "seed")
            bench = read_library(root)["exercises"]["db_bench_press"]
        self.assertEqual(bench["load_mode"], "single_implement")
        self.assertEqual(bench["hevy_template_id"], "F0000002")
        action = {p["matched_id"]: p["action"] for p in data["proposals"]}["db_bench_press"]
        self.assertEqual(action, "confirmed")

    def test_seed_without_a_cache_is_exit_5(self):
        with Instance() as root:
            envelope = self.run_fail(5, root, "library", "seed", "--dry-run")
        self.assertIn("hevy pull", envelope["error"]["message"])

    def test_seed_without_cached_templates_matches_by_routine_title(self):
        with Instance(SEED) as root:
            (root / ".coach" / "cache" / "hevy" / "exercise_templates.json").unlink()
            code, envelope, _ = run_cli(["--root", str(root), "library", "seed", "--dry-run"])
        self.assertEqual(code, 0)
        matched = {p["hevy_title"]: p["matched_id"] for p in envelope["data"]["proposals"]}
        self.assertEqual(matched["Bench Press (Dumbbell)"], "db_bench_press")
        self.assertTrue(any("exercise templates" in warning for warning in envelope["warnings"]))

    def test_seed_reports_guessed_custom_fields(self):
        with Instance(SEED) as root:
            code_data = self.run_ok(root, "library", "seed", "--dry-run")
        self.assertTrue(any("custom_tyre_flip" in warning for warning in code_data["guessed"]))

    def test_two_custom_templates_with_one_title_share_an_entry(self):
        with Instance(SEED) as root:
            path = root / ".coach" / "cache" / "hevy"
            templates = json.loads((path / "exercise_templates.json").read_text())
            routines = json.loads((path / "routines.json").read_text())
            twin = dict(templates["data"][-1], id="C0000002")
            templates["data"].append(twin)
            exercise = dict(routines["data"][1]["exercises"][-1], exercise_template_id="C0000002", index=4)
            routines["data"][1]["exercises"].append(exercise)
            (path / "exercise_templates.json").write_text(json.dumps(templates))
            (path / "routines.json").write_text(json.dumps(routines))
            data = self.run_ok(root, "library", "seed")
            lib = Library.load(root)
        twin_proposal = [p for p in data["proposals"] if p["hevy_template_id"] == "C0000002"][0]
        self.assertEqual(twin_proposal["matched_id"], "custom_tyre_flip")
        self.assertEqual(lib.by_hevy_template_id("C0000002")["id"], "custom_tyre_flip")


if __name__ == "__main__":
    unittest.main()
