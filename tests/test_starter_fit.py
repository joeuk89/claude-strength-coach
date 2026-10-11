"""Starters fitted to confirmed equipment, apparatus and ability, and the catalogue regressions they need (C45, C54)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import config as config_module
from coach.errors import ConfigError
from coach.library import APPARATUS, Library
from tests.support import INSTANCES, run_cli

EMPTY = INSTANCES / "empty"
NOW = "2026-10-11T18:00:00Z"
WEEK = "2026-W42"
MAJOR_MUSCLES = ("chest", "upper_back", "lats", "front_delts", "side_delts", "quadriceps", "hamstrings", "glutes",
                 "biceps", "triceps")
BEGINNER_KIT = ["dumbbell", "band", "bodyweight"]
NEEDS_KIT_OR_ABILITY = {"pull_up", "chin_up", "triceps_dip", "chest_dip", "nordic_curl", "db_incline_bench_press",
                        "bb_incline_bench_press"}
REGRESSIONS = {
    "split_squat": ("lunge", "bodyweight", "bodyweight", ["quadriceps", "glutes"], []),
    "bw_squat": ("squat", "bodyweight", "bodyweight", ["quadriceps", "glutes"], []),
    "sit_to_stand": ("squat", "bodyweight", "bodyweight", ["quadriceps", "glutes"], ["box"]),
    "bw_step_up": ("lunge", "bodyweight", "bodyweight", ["quadriceps", "glutes"], ["box"]),
    "incline_push_up": ("horizontal_push", "bodyweight", "bodyweight", ["chest"], ["box"]),
    "knee_push_up": ("horizontal_push", "bodyweight", "bodyweight", ["chest"], []),
    "db_floor_press": ("horizontal_push", "dumbbell", "per_hand_x2", ["chest"], []),
}


def instance(test, experience="beginner", available=None, apparatus=None, demonstrated=None, extra=""):
    """A copy of empty/ whose config states the athlete's level, kit, apparatus and demonstrated exercises."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name) / "instance"
    shutil.copytree(EMPTY, root)
    path = root / "config.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('experience = "intermediate"', f"experience = {json.dumps(experience)}"
                        + (f"\ndemonstrated_exercises = {json.dumps(demonstrated)}" if demonstrated else ""))
    text = text.replace("available = []", f"available = {json.dumps(available or [])}"
                        + (f"\napparatus = {json.dumps(apparatus)}" if apparatus is not None else ""))
    path.write_text(text + extra, encoding="utf-8")
    return root


def cli(root, *argv):
    return run_cli(["--root", str(root), *argv], env={"COACH_NOW": NOW})


def lines(doc, active_only=False):
    return [(session, line) for session in doc["sessions"] for line in session["exercises"]
            if not active_only or session["status"] == "active"]


def held(draft):
    return {line["exercise_id"] for _, line in lines(draft["program"])}


def rows(draft, kind, exercise_id=None):
    return [row for row in draft["report"] if row["kind"] == kind
            and (exercise_id is None or row["exercise_id"] == exercise_id)]


def swapped_to(draft, session_id, old_id):
    """The exercise the draft holds where the starter's session had `old_id`, by position."""
    from coach import starters

    original = next(s for s in starters.load(draft["source"].split(":", 1)[1])["program"]["sessions"]
                    if s["id"] == session_id)
    index = [line["exercise_id"] for line in original["exercises"]].index(old_id)
    session = next(s for s in draft["program"]["sessions"] if s["id"] == session_id)
    return session["exercises"][index]["exercise_id"]


class Case(unittest.TestCase):
    def ok(self, root, *argv):
        code, envelope, stderr = cli(root, *argv)
        self.assertEqual(code, 0, (argv, envelope, stderr))
        return envelope["data"]

    def fails(self, root, *argv, code=1):
        found, envelope, stderr = cli(root, *argv)
        self.assertEqual(found, code, (argv, envelope, stderr))
        return envelope["error"]

    def draft(self, root, *argv):
        return self.ok(root, "starters", "draft", *argv)["draft"]


class CatalogueRegressionTest(Case):
    def test_searches_find_the_new_regressions(self):
        expected = {"split squat": "split_squat", "bodyweight squat": "bw_squat", "air squat": "bw_squat",
                    "sit to stand": "sit_to_stand", "step up": "bw_step_up", "push up": "knee_push_up",
                    "incline push up": "incline_push_up", "floor press": "db_floor_press"}
        for query, exercise_id in expected.items():
            with self.subTest(query=query):
                matches = [m["id"] for m in self.ok(EMPTY, "library", "search", query)["matches"]]
                self.assertIn(exercise_id, matches)
        split = [m["id"] for m in self.ok(EMPTY, "library", "search", "split squat")["matches"]]
        self.assertIn("db_bulgarian_split_squat", split)
        self.assertEqual(split[0], "split_squat")

    def test_each_regression_has_truthful_metadata_and_declares_its_supports(self):
        library = Library()
        for exercise_id, (pattern, equipment, mode, primary, requires) in REGRESSIONS.items():
            with self.subTest(exercise=exercise_id):
                entry = self.ok(EMPTY, "library", "show", exercise_id)["exercise"]
                self.assertEqual((entry["pattern"], entry["equipment"], entry["load_mode_default"]),
                                 (pattern, equipment, mode))
                self.assertEqual(entry["muscles"]["primary"], primary)
                self.assertEqual(entry["requires"], requires)
                self.assertIsNone(entry["ability"])
                self.assertIsNotNone(entry["increment"])
                self.assertTrue(entry["substitutes"])
                self.assertTrue(all(library.get(sub) for sub in entry["substitutes"]))
        self.ok(EMPTY, "library", "validate")

    def test_apparatus_and_ability_are_declared_where_an_exercise_needs_them(self):
        library = Library()
        needs = {"pull_up": (["pull_up_bar"], "demonstrated"), "chin_up": (["pull_up_bar"], "demonstrated"),
                 "triceps_dip": (["dip_station"], "demonstrated"), "chest_dip": (["dip_station"], "demonstrated"),
                 "nordic_curl": (["nordic_anchor"], "demonstrated"),
                 "db_incline_bench_press": (["incline_bench"], None), "db_bench_press": (["flat_bench"], None), "db_step_up": (["box"], None), "push_up": ([], None),
                 "db_row": ([], None)}
        for exercise_id, (requires, ability) in needs.items():
            with self.subTest(exercise=exercise_id):
                entry = library.get(exercise_id)
                self.assertEqual((entry["requires"], entry["ability"]), (requires, ability))
        self.assertTrue({piece for entry in library.entries() for piece in entry["requires"]} <= set(APPARATUS))


class BeginnerKitTest(Case):
    """Dumbbells, bands and bodyweight; no bench, step, bar, dip station or anchor confirmed."""

    def setUp(self):
        self.root = instance(self, available=BEGINNER_KIT)

    def test_a_three_day_full_body_starter_is_recommended(self):
        found = self.ok(self.root, "starters", "list", "--days", "3")
        row = next(r for r in found["starters"] if r["id"] == "full-body-3")
        self.assertTrue(row["recommended"])
        self.assertEqual(row["unmatched"], 0)
        self.assertGreater(row["swaps"], 0)
        self.assertEqual(found["recommended_id"], "full-body-3")

    def test_a_dumbbell_and_machine_gym_is_recommended_one_too(self):
        root = instance(self, available=["machine", "cable", "dumbbell", "bodyweight"])
        found = self.ok(root, "starters", "list", "--days", "3")
        self.assertEqual(found["recommended_id"], "full-body-3")
        result = self.ok(root, "starters", "draft", "full-body-3")
        self.assertEqual(result["problems"], [])
        self.assertEqual(rows(result["draft"], "no_substitute"), [])

    def test_its_draft_holds_no_barbell_and_adopts(self):
        result = self.ok(self.root, "starters", "draft", "full-body-3")
        draft = result["draft"]
        self.assertEqual(result["problems"], [])
        self.assertEqual(rows(draft, "no_substitute"), [])
        library = Library()
        for session, line in lines(draft["program"]):
            with self.subTest(session=session["id"], exercise=line["exercise_id"]):
                entry = library.get(line["exercise_id"])
                self.assertIn(entry["equipment"], BEGINNER_KIT)
                self.assertEqual(entry["requires"], [])
        self.ok(self.root, "program", "adopt", "--input", str(self.root / result["path"]))
        self.ok(self.root, "program", "validate")

    def test_each_major_muscle_is_trained_on_at_least_two_days(self):
        draft = self.draft(self.root, "full-body-3")
        library = Library()
        days = {muscle: set() for muscle in MAJOR_MUSCLES}
        for session, line in lines(draft["program"], active_only=True):
            muscles = library.get(line["exercise_id"])["muscles"]
            for muscle in set(muscles["primary"]) | set(muscles["secondary"]):
                days.setdefault(muscle, set()).add(session["id"])
        for muscle in MAJOR_MUSCLES:
            self.assertGreaterEqual(len(days[muscle]), 2, muscle)

    def test_no_line_needs_kit_or_ability_the_athlete_has_not_confirmed(self):
        for starter_id in ("full-body-3", "push-pull-legs", "upper-lower-4"):
            with self.subTest(starter=starter_id):
                draft = self.draft(self.root, starter_id)
                self.assertEqual(held(draft) & NEEDS_KIT_OR_ABILITY, set())

    def test_a_passed_over_substitute_names_the_constraint(self):
        draft = self.draft(self.root, "full-body-3")
        pulldown = rows(draft, "swapped_exercise", "lat_pulldown")[0]["message"]
        self.assertIn("Pull Up", pulldown)
        self.assertIn("pull_up_bar", pulldown)
        self.assertIn("[equipment] apparatus", pulldown)
        pushdown = rows(draft, "swapped_exercise", "cable_triceps_pushdown")[0]["message"]
        self.assertIn("Triceps Dip", pushdown)
        self.assertIn("dip_station", pushdown)
        curl = rows(draft, "swapped_exercise", "machine_seated_leg_curl")[0]["message"]
        self.assertIn("Nordic", curl)
        self.assertIn("nordic_anchor", curl)
        incline = rows(draft, "swapped_exercise", "db_incline_bench_press")[0]["message"]
        self.assertIn("incline_bench", incline)

    def test_dose_targets_stay_coherent_after_the_swaps(self):
        result = self.ok(self.root, "starters", "draft", "full-body-3")
        prog = result["draft"]["program"]
        targets = prog["dose_targets"]
        for muscle in MAJOR_MUSCLES:
            self.assertEqual(targets[muscle], 10, muscle)
        library = Library()
        primary = {muscle for session, line in lines(prog, active_only=True)
                   for muscle in library.get(line["exercise_id"])["muscles"]["primary"]}
        others = {muscle: value for muscle, value in targets.items() if muscle not in MAJOR_MUSCLES}
        self.assertEqual(set(others), primary - set(MAJOR_MUSCLES))
        self.assertNotIn("lower_back", others)
        self.assertTrue(all(0 < value <= 6 for value in others.values()), others)
        self.ok(self.root, "program", "adopt", "--input", str(self.root / result["path"]))
        balance = self.ok(self.root, "structure", "balance")
        self.assertEqual({flag["code"] for flag in balance["flags"]} - {"volume_undershoot"}, set())
        for muscle in others:
            self.assertTrue(balance["muscles"][muscle]["met"], muscle)
        for muscle in MAJOR_MUSCLES:
            self.assertTrue(8 <= balance["muscles"][muscle]["average"] <= 20, (muscle, balance["muscles"][muscle]))
        minimum = self.ok(self.root, "structure", "balance", "--variant", "minimum")
        self.assertTrue(minimum["passed"], minimum["reasons"])
        schedule = result["draft"]["program"]["schedule"]["params"]["days"]
        ids = {s["id"] for s in result["draft"]["program"]["sessions"]}
        self.assertTrue(set(schedule.values()) <= ids)

    def test_swapped_loaded_lines_keep_the_calibration_week(self):
        result = self.ok(self.root, "starters", "draft", "full-body-3")
        self.ok(self.root, "program", "adopt", "--input", str(self.root / result["path"]))
        overlay = self.ok(self.root, "propose", "week", "--week", WEEK, "--dry-run")["overlay"]
        no_data = {(f["session_id"], f["exercise_id"]) for f in overlay["flags"] if f["code"] == "no_data"}
        goblet = [s for s in overlay["sessions"] for line in s["exercises"] if line["exercise_id"] == "goblet_squat"]
        self.assertTrue(goblet)
        for session in goblet:
            self.assertIn((session["session_id"], "goblet_squat"), no_data)
            line = next(e for e in session["exercises"] if e["exercise_id"] == "goblet_squat")
            self.assertTrue(all(s["load"] is None for s in line["sets"] if s["type"] != "warmup"))

    def test_a_kit_without_dumbbells_still_finds_apparatus_free_work(self):
        root = instance(self, available=["band", "bodyweight"])
        draft = self.draft(root, "full-body-3")
        self.assertEqual(swapped_to(draft, "full-body-b", "db_bulgarian_split_squat"), "split_squat")
        self.assertIn("push_up", held(draft))
        self.assertEqual(held(draft) & {"sit_to_stand", "bw_step_up", "incline_push_up"}, set())
        unmatched = rows(draft, "no_substitute")
        self.assertTrue(unmatched)
        for row in unmatched:
            self.assertIn(row["exercise_id"], held(draft))


class FlatBenchTest(Case):
    def test_a_flat_bench_allows_flat_pressing_but_not_an_incline(self):
        root = instance(self, available=["dumbbell", "bodyweight"], apparatus=["flat_bench"])
        draft = self.draft(root, "full-body-3")
        self.assertNotIn("db_incline_bench_press", held(draft))
        self.assertEqual(swapped_to(draft, "min-b", "db_incline_bench_press"), "db_bench_press")
        self.assertEqual(swapped_to(draft, "full-body-a", "bb_bench_press"), "db_bench_press")
        message = rows(draft, "swapped_exercise", "db_incline_bench_press")[0]["message"]
        self.assertIn("needs incline_bench, which [equipment] apparatus does not list", message)

    def test_a_bench_serves_as_a_box(self):
        root = instance(self, available=["dumbbell", "bodyweight"], apparatus=["flat_bench"])
        self.assertIn("db_bulgarian_split_squat", held(self.draft(root, "full-body-3")))


class ConfirmedAbilityTest(Case):
    def test_confirmed_apparatus_and_ability_keep_a_pull_up_and_a_dip(self):
        root = instance(self, available=["dumbbell", "bodyweight"], apparatus=["pull_up_bar", "dip_station"],
                        demonstrated=["pull_up", "triceps_dip"])
        draft = self.draft(root, "full-body-3")
        self.assertEqual(swapped_to(draft, "full-body-a", "lat_pulldown"), "pull_up")
        self.assertEqual(swapped_to(draft, "full-body-b", "cable_triceps_pushdown"), "triceps_dip")

    def test_apparatus_without_demonstrated_ability_is_not_enough(self):
        root = instance(self, available=["dumbbell", "bodyweight"], apparatus=["pull_up_bar", "dip_station"])
        draft = self.draft(root, "full-body-3")
        self.assertNotIn("pull_up", held(draft))
        message = rows(draft, "swapped_exercise", "lat_pulldown")[0]["message"]
        self.assertIn("needs demonstrated ability, which [athlete] demonstrated_exercises does not list", message)

    def test_an_intermediate_is_held_to_the_same_rule(self):
        root = instance(self, experience="intermediate", available=["dumbbell", "bodyweight"],
                        apparatus=["pull_up_bar"])
        self.assertNotIn("pull_up", held(self.draft(root, "full-body-3")))

    def test_demonstrated_exercises_must_be_ones_that_need_it(self):
        for value in (["pullup"], ["push_up"]):
            with self.subTest(value=value):
                root = instance(self, demonstrated=value)
                with self.assertRaises(ConfigError) as caught:
                    config_module.load(root)
                self.assertIn("demonstrated_exercises", str(caught.exception))


class AvoidAndNiggleTest(Case):
    def test_an_avoided_substitute_is_passed_over_and_said_so(self):
        root = instance(self, available=BEGINNER_KIT)
        self.ok(root, "library", "set-avoid", "db_row", "--reason", "lower back")
        draft = self.draft(root, "full-body-3")
        self.assertNotIn("db_row", held(draft))
        row = rows(draft, "no_substitute", "lat_pulldown")[0]
        self.assertIn("Bent Over Row (Dumbbell): marked avoid", row["message"])
        self.assertIn("lat_pulldown", held(draft))

    def test_an_active_niggle_is_not_brought_in_by_a_swap(self):
        root = instance(self, available=BEGINNER_KIT)
        self.ok(root, "niggles", "add", "--area", "low back", "--pattern", "hinge", "--constraint", "rpe_cap=7")
        draft = self.draft(root, "full-body-3")
        replaced = swapped_to(draft, "full-body-c", "machine_seated_leg_curl")
        self.assertEqual(replaced, "machine_seated_leg_curl")
        row = rows(draft, "no_substitute", "machine_seated_leg_curl")[0]
        self.assertIn("niggle n-0001 (low back) covers it", row["message"])
        self.assertIn("db_romanian_deadlift", held(draft))

    def test_a_resolved_niggle_no_longer_blocks_the_swap(self):
        root = instance(self, available=BEGINNER_KIT)
        self.ok(root, "niggles", "add", "--area", "low back", "--pattern", "hinge")
        self.ok(root, "niggles", "resolve", "n-0001")
        draft = self.draft(root, "full-body-3")
        self.assertEqual(swapped_to(draft, "full-body-c", "machine_seated_leg_curl"), "db_romanian_deadlift")


class LocationTest(Case):
    HOME = '\n[equipment.locations.home]\navailable = ["dumbbell", "band", "bodyweight"]\n'

    def test_a_location_s_kit_replaces_the_main_gym_s(self):
        root = instance(self, available=[], extra=self.HOME)
        self.assertIn("bb_back_squat", held(self.draft(root, "full-body-3")))
        result = self.ok(root, "starters", "draft", "full-body-3", "--location", "home")
        draft = result["draft"]
        self.assertEqual(result["problems"], [])
        self.assertNotIn("bb_back_squat", held(draft))
        self.assertEqual({s["location"] for s in draft["program"]["sessions"]}, {"home"})
        listed = self.ok(root, "starters", "list", "--days", "3", "--location", "home")
        self.assertEqual(listed["equipment"], BEGINNER_KIT)
        self.assertEqual(listed["location"], "home")

    def test_a_location_listing_its_own_kit_does_not_inherit_the_main_gym_s_apparatus(self):
        root = instance(self, available=["dumbbell", "bodyweight", "cable"], apparatus=["pull_up_bar", "flat_bench"],
                        demonstrated=["pull_up"], extra=self.HOME)
        self.assertEqual(config_module.equipment_for(config_module.load(root), "home")["apparatus"], [])
        draft = self.draft(root, "full-body-3", "--location", "home")
        self.assertNotIn("pull_up", held(draft))
        self.assertNotIn("db_bench_press", held(draft))
        message = rows(draft, "swapped_exercise", "lat_pulldown")[0]["message"]
        self.assertIn("[equipment.locations.home] available", message)

    def test_an_unknown_location_is_a_config_error(self):
        self.fails(instance(self), "starters", "draft", "full-body-3", "--location", "beach", code=5)


class ConfigTest(Case):
    def test_an_unknown_apparatus_is_rejected(self):
        root = instance(self, available=["dumbbell"], apparatus=["trampoline"])
        with self.assertRaises(ConfigError) as caught:
            config_module.load(root)
        self.assertIn("apparatus", str(caught.exception))

    def test_apparatus_defaults_to_none_listed(self):
        config = config_module.load(instance(self))
        self.assertEqual(config_module.equipment_for(config)["apparatus"], [])
        self.assertEqual(config.athlete.demonstrated_exercises, [])


if __name__ == "__main__":
    unittest.main()
