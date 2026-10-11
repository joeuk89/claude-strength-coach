"""Starter programs: the library, `starters list|show|draft`, and each starter adopted and proposed (contract C45)."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import jsonio, program, research, render, routines, starters, units, validity
from coach.hevy.cache import HevyCache
from coach.library import Library
from tests.support import INSTANCES, REPO_ROOT, run_cli
from tests.support.skills import flat, step_text

EMPTY = INSTANCES / "empty"
NOW = "2026-10-11T18:00:00Z"
WEEK = "2026-W42"
STARTER_IDS = ("full-body-3", "push-pull-legs", "rpe-full-body-3", "upper-lower-4", "wave-3wk")
MAJOR_MUSCLES = ("chest", "upper_back", "lats", "front_delts", "side_delts", "quadriceps", "hamstrings", "glutes",
                 "biceps", "triceps")
MAIN_SCHEMES = {"full-body-3": "linear", "upper-lower-4": "double_progression", "push-pull-legs": "double_progression",
                "wave-3wk": "wave_531", "rpe-full-body-3": "rpe_anchored"}
ACCESSORY_SCHEMES = {"double_progression", "fixed_reps_rpe"}


def instance(test, source=EMPTY):
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name) / "instance"
    shutil.copytree(source, root)
    return root


def cli(root, *argv):
    return run_cli(["--root", str(root), *argv], env={"COACH_NOW": NOW})


def set_athlete(root, **values):
    path = Path(root) / "config.toml"
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        old = next(line for line in text.splitlines() if line.startswith(f"{key} ="))
        text = text.replace(old, f"{key} = {json.dumps(value)}")
    path.write_text(text, encoding="utf-8")


def rows(draft, kind):
    return [row for row in draft["report"] if row["kind"] == kind]


def lines(doc):
    return [(session, line) for session in doc["sessions"] for line in session["exercises"]]


def planned(session):
    """A program session in the overlay shape the time estimate reads: one entry per set."""
    exercises = [dict(line, sets=[group for group in line["sets"] for _ in range(group["count"])])
                 for line in session["exercises"]]
    return dict(session, session_id=session["id"], date="2026-10-12", exercises=exercises)


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

    def adopted(self, starter_id):
        """The starter adopted, load modes confirmed, onto a copy of empty/ whose Hevy cache holds a template per catalogue title."""
        root = instance(self)
        templates = [{"id": f"STARTER-{index}", "title": entry["hevy_titles"][0]}
                     for index, entry in enumerate(Library().entries()) if entry["hevy_titles"]]
        HevyCache(root).write_collection("exercise_templates", templates, NOW)
        found = self.ok(root, "starters", "draft", starter_id)
        self.assertEqual(found["problems"], [])
        adopted = self.ok(root, "program", "adopt", "--input", str(root / found["path"]))
        modes = {line["exercise_id"]: line["load_mode"] for _, line in lines(found["draft"]["program"])}
        for entry in adopted["unconfirmed"]:
            self.ok(root, "library", "set-mode", entry["exercise_id"], modes[entry["exercise_id"]])
        return root, found["draft"]


class StarterFilesTest(Case):
    """Every shipped starter is a complete, valid, cited program."""

    @classmethod
    def setUpClass(cls):
        cls.starters = {doc["id"]: doc for doc in starters.load_all()}
        cls.library = Library()

    def test_the_five_starters_ship(self):
        self.assertEqual(tuple(sorted(self.starters)), STARTER_IDS)

    def test_each_program_is_valid_with_its_default_days(self):
        for starter_id, doc in self.starters.items():
            with self.subTest(starter=starter_id):
                self.assertEqual(program.validate(doc["program"], None, self.library), [])
                days = doc["days"]
                self.assertTrue(days["min"] <= len(days["default"]) <= days["max"])

    def test_cites_are_current_template_claims(self):
        notes, _, _ = research.load_all(REPO_ROOT)
        templates = [note for note in notes if note.kind == "template"]
        for starter_id, doc in self.starters.items():
            with self.subTest(starter=starter_id):
                self.assertTrue(doc["cites"])
                for ref in doc["cites"]:
                    self.assertIsNotNone(research.resolve(ref, templates), ref)

    def test_main_lifts_and_accessories_use_the_agreed_schemes(self):
        for starter_id, doc in self.starters.items():
            prog = doc["program"]
            main = {lift["exercise_id"] for lift in prog["priority"]}
            for session, line in lines(prog):
                if session["status"] != "active":
                    continue
                with self.subTest(starter=starter_id, session=session["id"], exercise=line["exercise_id"]):
                    self.assertIn(line["scheme"]["name"], ACCESSORY_SCHEMES | {MAIN_SCHEMES[starter_id]})
                    if line["exercise_id"] in main:
                        self.assertEqual(line["scheme"]["name"], MAIN_SCHEMES[starter_id])
        self.assertEqual(self.starters["push-pull-legs"]["program"]["schedule"]["rule"], "next_in_sequence")
        self.assertEqual(self.starters["wave-3wk"]["program"]["blocks"]["deload_rule"]["name"], "scheme")

    def test_no_starter_line_is_too_high_rep_for_its_scheme_to_progress(self):
        for starter_id, doc in self.starters.items():
            with self.subTest(starter=starter_id):
                self.assertEqual(program.warnings(doc["program"]), [])

    def test_each_declares_priority_lifts_and_a_target_for_each_major_muscle_it_trains(self):
        for starter_id, doc in self.starters.items():
            prog = doc["program"]
            with self.subTest(starter=starter_id):
                self.assertTrue(prog["priority"])
                trained = set()
                for session, line in lines(prog):
                    entry = self.library.get(line["exercise_id"])
                    trained |= set(entry["muscles"]["primary"]) | set(entry["muscles"]["secondary"])
                for muscle in trained & set(MAJOR_MUSCLES):
                    self.assertIn(muscle, prog["dose_targets"], muscle)

    def test_every_session_fits_the_stated_minutes(self):
        for starter_id, doc in self.starters.items():
            for session in doc["program"]["sessions"]:
                with self.subTest(starter=starter_id, session=session["id"]):
                    minutes = validity.estimate_minutes(EMPTY, planned(session))
                    self.assertLessEqual(minutes, doc["minutes_per_session"])

    def test_the_minimum_week_sits_on_the_days_a_draft_would_give_it(self):
        for starter_id, doc in self.starters.items():
            with self.subTest(starter=starter_id):
                days = doc["program"]["minimum_week"]["schedule"]["params"]["days"]
                self.assertEqual(list(days), starters.minimum_week_days(doc["days"]["default"]))

    def test_a_starter_behind_the_program_schema_is_migrated_on_load(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        doc = json.loads((starters.STARTERS_DIR / "full-body-3.json").read_text(encoding="utf-8"))
        old = doc["program"]
        old["schema_version"] = 5
        del old["priority"], old["minimum_week"]
        for session in old["sessions"]:
            session["status"] = "active"
        (Path(tmp.name) / "full-body-3.json").write_text(json.dumps(doc), encoding="utf-8")
        loaded = starters.load("full-body-3", tmp.name)
        current = jsonio.current_version(jsonio.load_schema(program.SCHEMA))
        self.assertEqual(loaded["program"]["schema_version"], current)
        self.assertEqual((loaded["program"]["priority"], loaded["program"]["minimum_week"]), ([], None))

    def test_an_unknown_starter_names_the_known_ones(self):
        error = self.fails(EMPTY, "starters", "show", "no-such-starter")
        self.assertIn("full-body-3", error["message"])


class AdoptedStarterTest(Case):
    """Each starter drafted with its default days onto a copy of empty/, adopted, rendered and proposed."""

    def test_an_adopted_starter_blocks_its_first_week_until_the_load_modes_are_confirmed(self):
        root = instance(self)
        found = self.ok(root, "starters", "draft", "full-body-3")
        adopted = self.ok(root, "program", "adopt", "--input", str(root / found["path"]))
        self.assertTrue(adopted["unconfirmed"])
        proposed = self.ok(root, "propose", "week", "--week", WEEK, "--dry-run")
        codes = {f["code"] for f in proposed["overlay"]["flags"] if f["severity"] == "block"}
        self.assertEqual(codes, {"load_mode_unconfirmed"})

    def test_every_starter_adopts_validates_renders_and_proposes_week_one(self):
        for starter_id in STARTER_IDS:
            with self.subTest(starter=starter_id):
                root, draft = self.adopted(starter_id)
                self.ok(root, "program", "validate")
                rendered = self.ok(root, "program", "render")
                for session in draft["program"]["sessions"]:
                    page = f"routine/{session['id']}.md"
                    self.assertIn(page, rendered["pages"])
                    self.assertTrue((root / page).is_file())

                proposed = self.ok(root, "propose", "week", "--week", WEEK, "--dry-run")
                self.assertNotIn("block", {f.get("severity") for f in proposed["overlay"]["flags"]})
                self.assert_calibration_lines(draft["program"], proposed["overlay"])

                minimum = self.ok(root, "structure", "balance", "--variant", "minimum")
                self.assertTrue(minimum["passed"], minimum["reasons"])
                plan = self.ok(root, "structure", "minimum", "--week", WEEK, "--write")
                planned = self.ok(root, "propose", "week", "--plan", str(root / plan["path"]), "--dry-run")
                self.assertNotIn("block", {f.get("severity") for f in planned["overlay"]["flags"]})

    def assert_calibration_lines(self, prog, overlay):
        start_loads = {(s["id"], line["exercise_id"]): line["start_load"] for s, line in lines(prog)}
        no_data = {(f["session_id"], f["exercise_id"]) for f in overlay["flags"] if f["code"] == "no_data"}
        for session in overlay["sessions"]:
            for line in session["exercises"]:
                if line["load_mode"] not in units.LOADED_MODES:
                    continue
                key = (session["session_id"], line["exercise_id"])
                working = [s for s in line["sets"] if s["type"] != "warmup"]
                if start_loads[key] is None:
                    self.assertIn(key, no_data)
                    self.assertTrue(all(s["load"] is None for s in working), key)
                else:
                    self.assertNotIn(key, no_data)

    def test_weekly_and_per_session_dose_stay_in_range(self):
        for starter_id in STARTER_IDS:
            with self.subTest(starter=starter_id):
                root, _ = self.adopted(starter_id)
                balance = self.ok(root, "structure", "balance")
                self.assertEqual(balance["flags"], [])
                for muscle in MAJOR_MUSCLES:
                    average = balance["muscles"].get(muscle, {}).get("average", 0)
                    self.assertTrue(10 <= average <= 20, f"{muscle}: {average}")
                for session_id, dose in balance["by_session"].items():
                    self.assertTrue(all(value <= 11 for value in dose.values()), (session_id, dose))

    def test_a_calibration_line_asks_the_athlete_to_choose_the_load_in_hevy(self):
        root, _ = self.adopted("full-body-3")
        overlay = self.ok(root, "propose", "week", "--week", WEEK, "--dry-run")["overlay"]
        session = next(s for s in overlay["sessions"] if s["session_id"] == "full-body-a")
        line = next(e for e in session["exercises"] if e["exercise_id"] == "db_romanian_deadlift")
        note = render.render_hevy_note(overlay, session, line, False)
        self.assertIn("Target: 3×8–10 @ RPE 7 · choose the load", note.splitlines())
        line["hevy_template_id"] = "F00000AA"
        body = routines.intended_body(overlay, dict(session, exercises=[line]), {})
        self.assertTrue(all("weight_kg" not in s for s in body["routine"]["exercises"][0]["sets"]))


class ListTest(Case):
    def test_three_days_lists_the_three_day_starters(self):
        found = self.ok(EMPTY, "starters", "list", "--days", "3")
        self.assertEqual({row["id"] for row in found["starters"]}, {"full-body-3", "push-pull-legs", "rpe-full-body-3"})

    def test_a_row_carries_what_the_athlete_chooses_on(self):
        row = self.ok(EMPTY, "starters", "list")["starters"][0]
        self.assertEqual(set(row), {"id", "title", "summary", "level", "days", "minutes", "equipment_required",
                                    "swaps", "unmatched", "recommended"})

    def test_equipment_filters_out_starters_that_need_more(self):
        found = self.ok(EMPTY, "starters", "list", "--equipment", "dumbbell,bodyweight")
        self.assertEqual({row["id"] for row in found["starters"]}, {"full-body-3", "push-pull-legs", "upper-lower-4"})

    def test_equipment_defaults_to_config(self):
        root = instance(self)
        path = root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('available = []',
                                                                  'available = ["dumbbell", "bodyweight"]'),
                        encoding="utf-8")
        self.assertNotIn("wave-3wk", {row["id"] for row in self.ok(root, "starters", "list")["starters"]})

    def test_experience_marks_a_recommendation_without_filtering(self):
        root = instance(self)
        set_athlete(root, experience="beginner")
        found = self.ok(root, "starters", "list")
        self.assertEqual(found["recommended_id"], "full-body-3")
        self.assertEqual(len(found["starters"]), len(STARTER_IDS))

    def test_an_unknown_equipment_id_is_a_usage_error(self):
        self.fails(EMPTY, "starters", "list", "--equipment", "anvil", code=2)


class ShowTest(Case):
    def test_show_returns_the_starter_and_its_session_pages(self):
        found = self.ok(EMPTY, "starters", "show", "full-body-3")
        self.assertEqual(found["starter"]["id"], "full-body-3")
        self.assertEqual(set(found["pages"]), {"routine/program.md"} | {
            f"routine/{s['id']}.md" for s in found["starter"]["program"]["sessions"]})


class DraftTest(Case):
    def test_days_and_a_start_load_are_applied(self):
        root = instance(self)
        draft = self.draft(root, "full-body-3", "--days", "tue,thu,sat", "--start-load", "bb_back_squat=60")
        self.assertEqual(draft["source"], "starter:full-body-3")
        self.assertEqual(draft["program"]["schedule"]["params"]["days"],
                         {"tue": "full-body-a", "thu": "full-body-b", "sat": "full-body-c"})
        squats = [line for _, line in lines(draft["program"]) if line["exercise_id"] == "bb_back_squat"]
        self.assertTrue(squats)
        self.assertTrue(all(line["start_load"] == 60 for line in squats))
        self.assertEqual(json.loads((root / ".coach/drafts/program.json").read_text(encoding="utf-8")), draft)

    def test_available_days_are_the_default_and_days_override_them(self):
        root = instance(self)
        set_athlete(root, available_days=["mon", "wed", "fri"])
        self.assertEqual(set(self.draft(root, "full-body-3")["program"]["schedule"]["params"]["days"]),
                         {"mon", "wed", "fri"})
        set_athlete(root, available_days=["tue", "thu", "sat"])
        self.assertEqual(set(self.draft(root, "full-body-3")["program"]["schedule"]["params"]["days"]),
                         {"tue", "thu", "sat"})
        overridden = self.draft(root, "full-body-3", "--days", "mon,wed,fri")
        self.assertEqual(set(overridden["program"]["schedule"]["params"]["days"]), {"mon", "wed", "fri"})

    def test_the_minimum_week_follows_the_athletes_days(self):
        draft = self.draft(instance(self), "full-body-3", "--days", "tue,thu,sat")
        self.assertEqual(draft["program"]["minimum_week"]["schedule"]["params"]["days"],
                         {"tue": "min-a", "sat": "min-b"})

    def test_a_sequence_takes_the_days_and_opens_on_its_first_session(self):
        draft = self.draft(instance(self), "push-pull-legs", "--days", "fri,mon,wed")
        self.assertEqual(draft["program"]["schedule"]["params"]["days"], ["mon", "wed", "fri"])
        self.assertEqual(draft["position"], "legs")

    def test_a_dumbbell_and_bodyweight_kit_swaps_every_barbell_exercise(self):
        root = instance(self)
        path = root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace(
            'available = []', 'available = ["dumbbell", "bodyweight"]\napparatus = ["flat_bench", "incline_bench"]'),
            encoding="utf-8")
        library = Library()
        before = starters.load("upper-lower-4")["program"]
        draft = self.draft(root, "upper-lower-4")
        swapped = rows(draft, "swapped_exercise")
        missing = rows(draft, "no_substitute")
        after = {(s["id"], line["exercise_id"]) for s, line in lines(draft["program"])}
        for session, line in lines(before):
            key = (session["id"], line["exercise_id"])
            equipment = library.get(line["exercise_id"])["equipment"]
            found = [row for row in swapped if (row["session_id"], row["exercise_id"]) == key]
            if equipment == "barbell":
                with self.subTest(line=key):
                    self.assertEqual(len(found), 1)
                    self.assertNotIn(key, after)
            if equipment not in ("dumbbell", "bodyweight"):
                self.assertEqual(len(found) + len([r for r in missing if (r["session_id"], r["exercise_id"]) == key]),
                                 1, key)
        for session, line in lines(draft["program"]):
            equipment = library.get(line["exercise_id"])["equipment"]
            if equipment not in ("dumbbell", "bodyweight"):
                self.assertIn((session["id"], line["exercise_id"]),
                              {(r["session_id"], r["exercise_id"]) for r in missing})
        self.assertTrue(missing)
        self.assertEqual({lift["exercise_id"] for lift in draft["program"]["priority"]},
                         {"db_bench_press", "goblet_squat", "db_romanian_deadlift"})
        self.ok(root, "program", "adopt", "--input", str(root / ".coach/drafts/program.json"), "--dry-run")

    def test_start_loads_take_the_swapped_ids_a_dry_run_lists_as_priority(self):
        root = instance(self)
        path = root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace(
            'available = []', 'available = ["dumbbell", "bodyweight"]\napparatus = ["flat_bench"]'), encoding="utf-8")
        preview = self.ok(root, "starters", "draft", "upper-lower-4", "--dry-run")
        self.assertFalse(preview["written"])
        self.assertFalse((root / ".coach/drafts/program.json").exists())
        priority = [lift["exercise_id"] for lift in preview["draft"]["program"]["priority"]]
        self.assertIn("db_bench_press", priority)
        error = self.fails(root, "starters", "draft", "upper-lower-4", "--start-load", "bb_bench_press=60")
        self.assertIn("db_bench_press", error["message"])
        draft = self.draft(root, "upper-lower-4", "--start-load", "db_bench_press=20")
        loads = {line["start_load"] for _, line in lines(draft["program"]) if line["exercise_id"] == "db_bench_press"}
        self.assertEqual(loads, {20})

    def test_a_barbell_starter_refuses_a_kit_without_a_barbell(self):
        root = instance(self)
        path = root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('available = []',
                                                                  'available = ["dumbbell", "bodyweight"]'),
                        encoding="utf-8")
        error = self.fails(root, "starters", "draft", "wave-3wk")
        self.assertIn("barbell", error["message"])
        self.assertFalse((root / ".coach/drafts/program.json").exists())

    def test_a_day_count_outside_the_range_names_the_range(self):
        error = self.fails(instance(self), "starters", "draft", "push-pull-legs", "--days", "mon")
        self.assertIn("3 to 6", error["message"])

    def test_an_avoided_exercise_is_swapped_for_its_first_substitute_that_is_not_avoided(self):
        root = instance(self)
        self.ok(root, "library", "set-avoid", "bb_back_squat", "--reason", "knee pain under load")
        draft = self.draft(root, "full-body-3")
        swapped = [row for row in rows(draft, "swapped_exercise") if row["exercise_id"] == "bb_back_squat"]
        self.assertEqual({row["session_id"] for row in swapped}, {"full-body-a", "full-body-c", "min-a"})
        self.assertTrue(all("avoid" in row["message"] and "knee pain" in row["message"] for row in swapped))
        held = {line["exercise_id"] for _, line in lines(draft["program"])}
        self.assertNotIn("bb_back_squat", held)
        self.assertIn("bb_front_squat", held)
        self.assertIn("bb_front_squat", {lift["exercise_id"] for lift in draft["program"]["priority"]})

    def test_an_avoided_exercise_with_no_fitting_substitute_is_reported(self):
        root = instance(self)
        for exercise_id in ("lat_pulldown", "pull_up", "close_grip_lat_pulldown", "assisted_pull_up", "db_row"):
            self.ok(root, "library", "set-avoid", exercise_id, "--reason", "shoulder")
        draft = self.draft(root, "full-body-3")
        missing = [row for row in rows(draft, "no_substitute") if row["exercise_id"] == "lat_pulldown"]
        self.assertEqual({row["session_id"] for row in missing}, {"full-body-a", "min-a"})
        self.assertIn("lat_pulldown", {line["exercise_id"] for _, line in lines(draft["program"])})

    def test_a_start_load_for_an_exercise_the_draft_lacks_exits_1(self):
        error = self.fails(instance(self), "starters", "draft", "full-body-3", "--start-load", "leg_press=100")
        self.assertIn("leg_press", error["message"])

    def test_a_malformed_start_load_exits_1(self):
        self.fails(instance(self), "starters", "draft", "full-body-3", "--start-load", "bb_back_squat")

    def test_dry_run_writes_nothing(self):
        root = instance(self)
        found = self.ok(root, "starters", "draft", "full-body-3", "--dry-run")
        self.assertFalse(found["written"])
        self.assertFalse((root / ".coach").exists())

    def test_the_rpe_starters_high_rep_accessories_progress_by_double_progression(self):
        draft = self.draft(instance(self), "rpe-full-body-3")
        found = {(session["id"], line["exercise_id"]): line for session, line in lines(draft["program"])
                 if session["status"] == "active"}
        expected = {("rpe-a", "db_lateral_raise"): (12, 15), ("rpe-a", "db_curl"): (10, 12),
                    ("rpe-b", "db_lateral_raise"): (12, 15), ("rpe-b", "cable_triceps_pushdown"): (10, 12),
                    ("rpe-c", "machine_seated_leg_curl"): (10, 12), ("rpe-c", "db_curl"): (10, 12),
                    ("rpe-c", "face_pull"): (12, 15)}
        for key, (start, end) in expected.items():
            with self.subTest(line=key):
                self.assertEqual(found[key]["scheme"]["name"], "double_progression")
                self.assertEqual([(group["rep_range"], group["rpe"]) for group in found[key]["sets"]],
                                 [({"start": start, "end": end}, 8)])
                self.assertNotIn("reps", found[key]["sets"][0])

    def test_the_draft_leaves_the_starter_file_alone(self):
        before = copy.deepcopy(starters.load("full-body-3"))
        self.draft(instance(self), "full-body-3", "--days", "tue,thu,sat", "--start-load", "bb_back_squat=60")
        self.assertEqual(starters.load("full-body-3"), before)


class WiringTest(unittest.TestCase):
    def test_the_three_commands_are_allowlisted(self):
        allow = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
        for name in ("starters list", "starters show", "starters draft"):
            self.assertIn(f"Bash(python3 -m coach {name}:*)", allow)

    def test_the_glossary_defines_a_starter(self):
        self.assertIn("**Starter**:", (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8"))

    def test_new_program_offers_the_starter_path_before_adopting(self):
        path = flat(step_text("new-program", "starter.md"))
        order = [path.index(name) for name in ("python3 -m coach starters list", "python3 -m coach starters draft",
                                               "python3 -m coach program adopt")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
