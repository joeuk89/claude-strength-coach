"""Program drafts: `program import-hevy` and `program adopt` (contract C45, C5, C6, C16)."""

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import jsonio, program_drafts, units
from coach.errors import ConfigError, RefusedError, ValidationError
from coach.hevy.cache import HevyCache
from coach.validate import validate
from tests.support import FIXTURES, INSTANCES, REPO_ROOT, VALID, run_cli
from tests.support.fake_hevy import FakeHevy
from tests.support.skills import flat, skill_text, step_text

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
PUSHED = FIXTURES / "hevy" / "pushed"
WAVE = FIXTURES / "hevy" / "wave"
EMPTY = INSTANCES / "empty"
DRAFT = FIXTURES / "program" / "draft.json"
NOW = "2026-10-11T18:00:00Z"
ROUTINE_A = "00000000-0000-4000-8000-000000000001"
ROUTINE_B = "00000000-0000-4000-8000-000000000002"


def fixtures(*sets):
    return os.pathsep.join(str(path) for path in sets)


def env(*sets):
    found = {"COACH_NOW": NOW}
    if sets:
        found["COACH_HEVY_FIXTURES"] = fixtures(*sets)
    return found


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in Path(root).rglob("*")
            if path.is_file() and ".git" not in path.relative_to(root).parts}


def read(root, relative):
    return json.loads((Path(root) / relative).read_text(encoding="utf-8"))


def write(root, relative, doc):
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def exercise(draft, session_id, exercise_id):
    session = next(s for s in draft["program"]["sessions"] if s["id"] == session_id)
    return next(e for e in session["exercises"] if e["exercise_id"] == exercise_id)


def rows(draft, kind, exercise_id=None):
    return [row for row in draft["report"]
            if row["kind"] == kind and (exercise_id is None or row["exercise_id"] == exercise_id)]


def git(root, *argv):
    return subprocess.run(["git", "-C", str(root), *argv], capture_output=True, text=True)


def init_repo(root):
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")


class Case(unittest.TestCase):
    def instance(self, source=VALID):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "instance"
        shutil.copytree(source, root)
        return root

    def cli(self, root, *argv, sets=()):
        return run_cli(["--root", str(root), *argv], env=env(*sets))

    def pull(self, root, *sets):
        code, envelope, stderr = self.cli(root, "hevy", "pull", "--full", sets=sets)
        self.assertEqual(code, 0, (envelope, stderr))

    def set_library(self, root, exercise_id, **fields):
        doc = read(root, "data/exercises.json")
        doc["exercises"][exercise_id].update(fields)
        write(root, "data/exercises.json", doc)


def routine(title, exercises, routine_id=ROUTINE_A, folder_id=1):
    return {"id": routine_id, "title": title, "folder_id": folder_id, "updated_at": NOW, "created_at": NOW,
            "exercises": exercises}


def hevy_exercise(template_id, title, sets, notes="", rest=120, superset=None):
    return {"index": 0, "title": title, "rest_seconds": rest, "notes": notes, "exercise_template_id": template_id,
            "superset_id": superset, "sets": sets}


def hevy_set(weight_kg, reps=None, rep_range=None, kind="normal", duration=None):
    return {"index": 0, "type": kind, "weight_kg": weight_kg, "reps": reps, "distance_meters": None,
            "duration_seconds": duration, "custom_metric": None, "rep_range": rep_range}


class ImportCase(Case):
    """Imports from a cache written straight into a copy of the valid instance."""

    def cached(self, routines, root=None, folders=None):
        root = root or self.instance()
        cache = HevyCache(root)
        cache.write_collection("routines", routines, NOW)
        cache.write_collection("routine_folders", folders if folders is not None else
                               [{"id": 1, "index": 0, "title": "Program", "updated_at": NOW, "created_at": NOW}], NOW)
        return root

    def draft_of(self, routines, root=None, folders=None, **kwargs):
        return program_drafts.import_hevy(self.cached(routines, root, folders), now=NOW, **kwargs)


class ImportHevyCommandTest(Case):
    def setUp(self):
        self.root = self.instance()
        self.pull(self.root, SYNTHETIC, PUSHED)

    def test_the_dry_run_returns_the_draft_and_writes_nothing(self):
        before = snapshot(self.root)
        code, envelope, stderr = self.cli(self.root, "program", "import-hevy", "--dry-run", sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 0, (envelope, stderr))
        self.assertEqual(snapshot(self.root), before)
        data = envelope["data"]
        self.assertFalse(data["written"])
        draft = data["draft"]
        self.assertEqual(validate(draft, jsonio.load_schema("program_draft")), [])
        self.assertEqual([s["id"] for s in draft["program"]["sessions"]], ["session-a", "session-b"])
        self.assertEqual(draft["source"], "hevy_import")
        self.assertEqual(draft["hevy_routines"], {ROUTINE_A: "session-a", ROUTINE_B: "session-b"})
        self.assertEqual(draft["hevy_folder"], 1)

        bench = exercise(draft, "session-a", "db_bench_press")
        self.assertEqual((bench["load_mode"], bench["start_load"]), ("per_hand_x2", 25))
        self.assertEqual([r["message"] for r in rows(draft, "converted_load", "db_bench_press")],
                         ["Hevy 50 → 25/hand"])
        row = exercise(draft, "session-b", "db_single_arm_row")
        self.assertEqual((row["load_mode"], row["start_load"]), ("single_implement", 30))
        self.assertEqual(exercise(draft, "session-b", "pull_up")["start_load"], 0)

        schemes = {e["scheme"]["name"] for s in draft["program"]["sessions"] for e in s["exercises"]}
        self.assertEqual(schemes, {"hold"})
        self.assertEqual(len(rows(draft, "schedule_missing")), 1)
        self.assertEqual(draft["program"]["schedule"], {"rule": "fixed_weekdays", "params": {"days": {}}})
        self.assertFalse(draft["detected"]["percentage_based"])

    def test_set_groups_rest_and_cues_come_from_the_routine(self):
        code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--dry-run", sets=(SYNTHETIC, PUSHED))
        draft = envelope["data"]["draft"]
        squat = exercise(draft, "session-a", "bb_back_squat")
        self.assertEqual(squat["sets"], [{"count": 1, "type": "warmup", "reps": 5},
                                         {"count": 3, "type": "normal", "reps": 5}])
        self.assertEqual((squat["start_load"], squat["rest_seconds"], squat["superset_id"]), (100, 180, None))
        self.assertEqual(squat["cues"], "brace · knees out")
        bench = exercise(draft, "session-a", "db_bench_press")
        self.assertEqual(bench["sets"][1], {"count": 3, "type": "normal", "rep_range": {"start": 8, "end": 10}})
        self.assertEqual(bench["cues"], "elbows tucked · feet planted")
        self.assertEqual(len(rows(draft, "cues_from_notes")), 4)

    def test_without_dry_run_the_draft_lands_in_coach_drafts(self):
        code, envelope, stderr = self.cli(self.root, "program", "import-hevy", sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 0, (envelope, stderr))
        self.assertTrue(envelope["data"]["written"])
        self.assertEqual(envelope["data"]["path"], ".coach/drafts/program.json")
        self.assertEqual(read(self.root, ".coach/drafts/program.json"), envelope["data"]["draft"])

    def test_out_names_the_file(self):
        target = self.root / "my-draft.json"
        code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--out", str(target),
                                     sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 0, envelope)
        self.assertEqual(read(self.root, "my-draft.json")["source"], "hevy_import")

    def test_an_unconfirmed_load_mode_refuses_the_import(self):
        self.set_library(self.root, "db_bench_press", load_mode=None)
        code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--dry-run", sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 1, envelope)
        message = envelope["error"]["message"]
        for needle in ("db_bench_press", "library seed", "library confirm"):
            self.assertIn(needle, message)

    def test_one_routine_with_routine(self):
        code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--dry-run", "--routine", ROUTINE_B,
                                     sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 0, envelope)
        self.assertEqual([s["id"] for s in envelope["data"]["draft"]["program"]["sessions"]], ["session-b"])

    def test_an_unknown_routine_id_exits_1(self):
        code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--dry-run", "--routine", "nope",
                                     sets=(SYNTHETIC, PUSHED))
        self.assertEqual(code, 1, envelope)
        self.assertIn("nope", envelope["error"]["message"])

    def test_the_command_never_calls_hevy(self):
        fake = FakeHevy(SYNTHETIC)
        with mock.patch("coach.hevy.transport.from_env", return_value=fake):
            code, envelope, _ = self.cli(self.root, "program", "import-hevy", "--dry-run")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(fake.requests, [])


class ImportWithoutCacheTest(Case):
    def test_no_cached_routines_names_hevy_pull(self):
        root = self.instance()
        code, envelope, _ = self.cli(root, "program", "import-hevy", "--dry-run")
        self.assertEqual(code, 5, envelope)
        self.assertIn("hevy pull", envelope["error"]["message"])


class PercentageDetectionTest(Case):
    def test_a_wave_program_is_detected_but_not_assigned(self):
        root = self.instance()
        self.pull(root, SYNTHETIC, WAVE)
        code, envelope, stderr = self.cli(root, "program", "import-hevy", "--dry-run", sets=(SYNTHETIC, WAVE))
        self.assertEqual(code, 0, (envelope, stderr))
        draft = envelope["data"]["draft"]
        detected = draft["detected"]
        self.assertTrue(detected["percentage_based"])
        self.assertIn("wave_531", detected["suggested_schemes"])
        by_kind = {}
        for item in detected["evidence"]:
            by_kind.setdefault(item["kind"], []).append(item["message"])
        self.assertTrue(any('"TM"' in message for message in by_kind["keyword"]), by_kind)
        self.assertTrue(all(title in by_kind["week_titles"][0]
                            for title in ("W1 Squat Day", "W2 Squat Day", "W3 Squat Day")), by_kind)
        self.assertTrue(all(load in by_kind["top_loads"][0] for load in ("85", "90", "95")), by_kind)
        self.assertEqual(len(rows(draft, "percentage_evidence")), len(detected["evidence"]))
        for session in draft["program"]["sessions"]:
            for line in session["exercises"]:
                self.assertEqual(line["scheme"]["name"], "hold")
        squat_ids = [s["id"] for s in draft["program"]["sessions"] if s["exercises"][0]["exercise_id"] == "bb_back_squat"]
        self.assertEqual(squat_ids, ["w1-squat-day", "w2-squat-day", "w3-squat-day"])


class ImportRulesTest(ImportCase):
    def test_mixed_working_loads_keep_the_top_and_are_reported(self):
        sets = [hevy_set(60, 5, kind="warmup"), hevy_set(100, 5), hevy_set(90, 5), hevy_set(90, 5)]
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)", sets)])])
        squat = exercise(draft, "session-a", "bb_back_squat")
        self.assertEqual(squat["start_load"], 100)
        self.assertEqual(squat["sets"], [{"count": 1, "type": "warmup", "reps": 5},
                                         {"count": 3, "type": "normal", "reps": 5}])
        mixed = rows(draft, "mixed_loads", "bb_back_squat")
        self.assertEqual(len(mixed), 1)
        self.assertIn("100, 90, 90", mixed[0]["message"])

    def test_sets_with_different_reps_make_separate_groups(self):
        sets = [hevy_set(100, 3), hevy_set(90, 5), hevy_set(90, 5)]
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)", sets)])])
        self.assertEqual(exercise(draft, "session-a", "bb_back_squat")["sets"],
                         [{"count": 1, "type": "normal", "reps": 3}, {"count": 2, "type": "normal", "reps": 5}])

    def test_retired_routines_are_skipped_and_folder_limits(self):
        squat = hevy_exercise("F0000001", "Squat (Barbell)", [hevy_set(100, 5)])
        row = hevy_exercise("F0000003", "Single Arm Row (Dumbbell)", [hevy_set(30, 10)])
        routines = [routine("Session A", [squat]), routine("(unused)", [row], routine_id="r-unused"),
                    routine("Travel", [row], routine_id="r-travel", folder_id=2)]
        folders = [{"id": 1, "title": "Program"}, {"id": 2, "title": "One-off"}]
        draft = self.draft_of(routines, folders=folders)
        self.assertEqual([s["id"] for s in draft["program"]["sessions"]], ["session-a", "travel"])
        self.assertIsNone(draft["hevy_folder"])
        draft = self.draft_of(routines, folders=folders, folder_id=2)
        self.assertEqual([s["id"] for s in draft["program"]["sessions"]], ["travel"])
        self.assertEqual(draft["hevy_folder"], 2)

    def test_titles_that_slug_the_same_get_a_suffix(self):
        squat = hevy_exercise("F0000001", "Squat (Barbell)", [hevy_set(100, 5)])
        routines = [routine("Session A", [squat]), routine("Session  A!", [squat], routine_id="r-2"),
                    routine("Program", [squat], routine_id="r-3")]
        draft = self.draft_of(routines)
        self.assertEqual([s["id"] for s in draft["program"]["sessions"]], ["session-a", "session-a-2", "program-2"])

    def test_notes_without_a_cues_line_become_cues_without_the_prescription_lines(self):
        notes = "Wk of 12 Oct: heavy week\nTarget: 3×5 @ 100 kg @ RPE 7\nFocus: speed\nchest up\nknees out"
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)",
                                                                    [hevy_set(100, 5)], notes=notes)])])
        self.assertEqual(exercise(draft, "session-a", "bb_back_squat")["cues"], "chest up · knees out")
        self.assertEqual(len(rows(draft, "cues_from_notes", "bb_back_squat")), 1)

    def test_an_empty_note_gives_no_cues(self):
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)",
                                                                    [hevy_set(100, 5)])])])
        self.assertIsNone(exercise(draft, "session-a", "bb_back_squat")["cues"])
        self.assertEqual(rows(draft, "cues_from_notes"), [])

    def test_a_missing_working_load_leaves_the_start_load_to_the_coach(self):
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)",
                                                                    [hevy_set(None, 5)])])])
        self.assertIsNone(exercise(draft, "session-a", "bb_back_squat")["start_load"])
        self.assertEqual(rows(draft, "converted_load"), [])

    def test_supersets_and_a_repeated_exercise(self):
        bench = hevy_exercise("F0000002", "Bench Press (Dumbbell)", [hevy_set(50, 8)], superset=0)
        row = hevy_exercise("F0000003", "Single Arm Row (Dumbbell)", [hevy_set(30, 10)], superset=0)
        again = hevy_exercise("F0000002", "Bench Press (Dumbbell)", [hevy_set(40, 12)])
        draft = self.draft_of([routine("Session A", [bench, row, again])])
        session = draft["program"]["sessions"][0]
        self.assertEqual([e["exercise_id"] for e in session["exercises"]], ["db_bench_press", "db_single_arm_row"])
        self.assertEqual(session["exercises"][0]["superset_id"], 0)
        self.assertEqual(session["exercises"][0]["sets"], [{"count": 1, "type": "normal", "reps": 8},
                                                           {"count": 1, "type": "normal", "reps": 12}])
        self.assertEqual(session["exercises"][0]["start_load"], 25)
        self.assertEqual(len(rows(draft, "mixed_loads", "db_bench_press")), 1)

    def test_a_repeated_exercise_takes_its_top_set_from_every_entry(self):
        top_set = hevy_exercise("F0000001", "Squat (Barbell)", [hevy_set(90, 5)])
        back_off = hevy_exercise("F0000001", "Squat (Barbell)", [hevy_set(100, 3), hevy_set(100, 3)],
                                 notes="Cues: brace hard")
        draft = self.draft_of([routine("Session A", [top_set, back_off])])
        squat = exercise(draft, "session-a", "bb_back_squat")
        self.assertEqual(squat["start_load"], 100)
        self.assertEqual(squat["cues"], "brace hard")
        self.assertEqual(squat["sets"], [{"count": 1, "type": "normal", "reps": 5},
                                         {"count": 2, "type": "normal", "reps": 3}])
        mixed = rows(draft, "mixed_loads", "bb_back_squat")
        self.assertEqual(len(mixed), 1)
        self.assertIn("90, 100, 100", mixed[0]["message"])
        self.assertEqual([row["message"] for row in rows(draft, "converted_load", "bb_back_squat")],
                         ["Hevy 100 → 100"])

    def test_an_assisted_line_starts_from_its_least_assistance(self):
        root = self.instance()
        self.set_library(root, "pull_up", load_mode="assisted")
        sets = [hevy_set(30, 6), hevy_set(20, 6), hevy_set(20, 6)]
        draft = self.draft_of([routine("Session B", [hevy_exercise("F0000004", "Pull Up", sets)])], root=root)
        self.assertEqual(exercise(draft, "session-b", "pull_up")["start_load"], 20)
        self.assertIn("BW-20 assist", rows(draft, "converted_load", "pull_up")[0]["message"])

    def test_an_all_conditioning_routine_is_a_conditioning_session(self):
        root = self.instance()
        lib = read(root, "data/exercises.json")
        lib["exercises"]["custom_bike_sprints"] = {
            "name": "Bike Sprints", "muscles": {"primary": ["cardio"], "secondary": []}, "pattern": "conditioning",
            "equipment": "cardio_machine", "load_mode_default": "duration", "hevy_template_id": "C00000A1",
            "load_mode": "duration", "avoid": None}
        write(root, "data/exercises.json", lib)
        sprint = hevy_exercise("C00000A1", "Bike Erg Sprints", [hevy_set(None, duration=30)] * 6)
        draft = self.draft_of([routine("Finisher", [sprint])], root=root)
        session = draft["program"]["sessions"][0]
        self.assertEqual(session["kind"], "conditioning")
        self.assertEqual(session["exercises"][0]["sets"], [{"count": 6, "type": "normal", "duration_seconds": 30}])
        self.assertIsNone(session["exercises"][0]["start_load"])

    def test_an_exercise_no_library_entry_holds_names_library_seed(self):
        routines = [routine("Session A", [hevy_exercise("ZZZZ", "Mystery Lift", [hevy_set(50, 5)])])]
        with self.assertRaises(ValidationError) as caught:
            self.draft_of(routines)
        self.assertIn("Mystery Lift", caught.exception.message)
        self.assertIn("library seed", caught.exception.message)

    def test_an_lb_athlete_keeps_a_load_set_in_lb_and_rounds_one_set_in_kg(self):
        root = self.instance()
        config = (root / "config.toml").read_text(encoding="utf-8").replace('units = "kg"', 'units = "lb"', 1)
        (root / "config.toml").write_text(config, encoding="utf-8")
        bench = hevy_exercise("F0000002", "Bench Press (Dumbbell)", [hevy_set(units.to_hevy_kg(25, "per_hand_x2", "lb"), 8)])
        squat = hevy_exercise("F0000001", "Squat (Barbell)", [hevy_set(20, 5)])
        draft = self.draft_of([routine("Session A", [bench, squat])], root=root)
        self.assertEqual(exercise(draft, "session-a", "db_bench_press")["start_load"], 25)
        self.assertEqual(exercise(draft, "session-a", "bb_back_squat")["start_load"], 45)
        message = rows(draft, "converted_load", "bb_back_squat")[0]["message"]
        self.assertEqual(message, "Hevy 44.09 → 45, rounded to the 5 lb step")

    def test_the_draft_validates_and_its_program_has_only_the_schedule_to_fill(self):
        draft = self.draft_of([routine("Session A", [hevy_exercise("F0000001", "Squat (Barbell)",
                                                                    [hevy_set(100, 5)])])])
        self.assertEqual(validate(draft, jsonio.load_schema("program_draft")), [])
        root = self.instance(EMPTY)
        with self.assertRaises(ValidationError) as caught:
            program_drafts.adopt(root, draft, today="2026-10-11")
        self.assertEqual([d["path"] for d in caught.exception.details], ["$.program.schedule.params"])


class UnitsForTheReportTest(unittest.TestCase):
    def test_format_number(self):
        self.assertEqual(units.format_number(50), "50")
        self.assertEqual(units.format_number(44.092), "44.09")
        self.assertEqual(units.format_number(22.5), "22.5")

    def test_format_load_without_the_hevy_value(self):
        load = units.make_load(25, "per_hand_x2", "kg")
        self.assertEqual(units.format_load(load, show_hevy=False), "25/hand")
        self.assertEqual(units.format_load(load), "25/hand (Hevy: 50)")


def scheduled(draft, days=None):
    draft = copy.deepcopy(draft)
    draft["program"]["schedule"]["params"]["days"] = days or {"mon": "session-a", "thu": "session-b"}
    return draft


class AdoptCase(Case):
    def draft(self):
        return read(DRAFT.parent, DRAFT.name)

    def adopt(self, root, draft, *argv):
        path = Path(tempfile.mkdtemp()) / "draft.json"
        self.addCleanup(shutil.rmtree, path.parent)
        write(path.parent, path.name, draft)
        return self.cli(root, "program", "adopt", "--input", str(path), *argv)


class DraftFixtureTest(AdoptCase):
    def test_the_fixture_is_the_pushed_import_with_its_schedule_filled(self):
        root = self.instance()
        self.pull(root, SYNTHETIC, PUSHED)
        _, envelope, _ = self.cli(root, "program", "import-hevy", "--dry-run", sets=(SYNTHETIC, PUSHED))
        self.assertEqual(scheduled(envelope["data"]["draft"]), self.draft())


class AdoptOnEmptyTest(AdoptCase):
    def setUp(self):
        self.root = self.instance(EMPTY)
        init_repo(self.root)

    def test_adopt_writes_renders_and_stages_without_committing(self):
        code, envelope, stderr = self.adopt(self.root, self.draft())
        self.assertEqual(code, 0, (envelope, stderr))
        data = envelope["data"]
        expected = ["data/program.json", "data/state.json", "routine/program.md", "routine/session-a.md",
                    "routine/session-b.md"]
        self.assertEqual(sorted(data["written"]), expected)
        self.assertEqual(sorted(data["staged"]), expected)
        staged = git(self.root, "diff", "--cached", "--name-only").stdout.split()
        self.assertEqual(sorted(staged), expected)
        self.assertNotEqual(git(self.root, "rev-parse", "--verify", "HEAD").returncode, 0)
        self.assertEqual(read(self.root, "data/program.json"), self.draft()["program"])
        code, envelope, _ = self.cli(self.root, "check", "--only", "program_schema,state_schema,routine_render_fresh")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(data["unconfirmed"], [{"exercise_id": "db_bench_press", "sessions": ["session-a"]}])
        self.assertEqual(data["avoided"], [])
        self.assertEqual(data["without_routine"], [])

    def test_the_new_state(self):
        code, envelope, _ = self.adopt(self.root, self.draft())
        self.assertEqual(code, 0, envelope)
        state = read(self.root, "data/state.json")
        self.assertEqual(state["block"], {"id": "b-0001", "started": "2026-10-11", "hard_weeks_completed": 0,
                                          "last_closed_week": None, "last_deep_review": None,
                                          "light_week": {"status": "not_due", "type": None, "reason": None,
                                                         "week": None, "decision_id": None}})
        self.assertEqual(state["rotation"], {"position": None, "confirmed": True, "confirmed_at": None, "week": None})
        self.assertEqual(state["scheme_state"], {})
        self.assertEqual(state["hevy"], {"routines": {ROUTINE_A: {"session_id": "session-a"},
                                                      ROUTINE_B: {"session_id": "session-b"}},
                                         "folders": {"program": 1, "one_off": None}, "temporary_routines": []})
        self.assertIsNone(state["one_off"])

    def test_the_dry_run_writes_nothing_and_says_what_it_would(self):
        before = snapshot(self.root)
        code, envelope, _ = self.adopt(self.root, self.draft(), "--dry-run")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(envelope["data"]["written"], [])
        self.assertIn("routine/session-a.md", envelope["data"]["would_write"])

    def test_an_avoided_exercise_is_reported_and_kept(self):
        self.set_library(self.root, "db_bench_press", avoid={"reason": "shoulder"})
        code, envelope, _ = self.adopt(self.root, self.draft(), "--dry-run")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["avoided"],
                         [{"exercise_id": "db_bench_press", "sessions": ["session-a"], "reason": "shoulder"}])
        self.assertTrue(any("db_bench_press" in warning for warning in envelope["warnings"]))
        code, envelope, _ = self.adopt(self.root, self.draft())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(exercise({"program": read(self.root, "data/program.json")}, "session-a",
                                  "db_bench_press")["exercise_id"], "db_bench_press")

    def test_an_empty_schedule_exits_1_at_schedule_params(self):
        draft = self.draft()
        draft["program"]["schedule"]["params"]["days"] = {}
        before = snapshot(self.root)
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 1, envelope)
        self.assertEqual([d["path"] for d in envelope["error"]["details"]], ["$.program.schedule.params"])
        self.assertEqual(snapshot(self.root), before)

    def test_a_program_problem_is_reported_under_program(self):
        draft = self.draft()
        draft["program"]["sessions"][0]["exercises"][0]["exercise_id"] = "no_such_exercise"
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 1, envelope)
        self.assertIn("$.program.sessions[0].exercises[0].exercise_id",
                      [d["path"] for d in envelope["error"]["details"]])

    def test_a_start_load_over_its_cap_exits_1(self):
        draft = self.draft()
        exercise(draft, "session-a", "db_bench_press")["start_load"] = 45
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 1, envelope)
        self.assertEqual([d["path"] for d in envelope["error"]["details"]],
                         ["$.program.sessions[0].exercises[1].start_load"])
        self.assertIn("dumbbell_max", envelope["error"]["details"][0]["message"])

    def test_a_routine_mapped_to_no_session_exits_1(self):
        draft = self.draft()
        draft["hevy_routines"]["r-extra"] = "session-z"
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 1, envelope)
        self.assertEqual([d["path"] for d in envelope["error"]["details"]], ["$.hevy_routines['r-extra']"])

    def test_a_malformed_draft_exits_1(self):
        draft = self.draft()
        draft["source"] = "somewhere"
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 1, envelope)
        self.assertIn("$.source", [d["path"] for d in envelope["error"]["details"]])

    def test_a_missing_input_exits_1(self):
        code, envelope, _ = self.cli(self.root, "program", "adopt", "--input", str(self.root / "nope.json"))
        self.assertEqual(code, 1, envelope)

    def test_sessions_without_a_routine_are_listed(self):
        draft = self.draft()
        draft["hevy_routines"] = {ROUTINE_A: "session-a"}
        code, envelope, _ = self.adopt(self.root, draft, "--dry-run")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["without_routine"], ["session-b"])

    def test_adopt_makes_no_network_call(self):
        fake = FakeHevy(SYNTHETIC)
        with mock.patch("coach.hevy.transport.from_env", return_value=fake):
            code, envelope, _ = self.adopt(self.root, self.draft())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(fake.requests, [])

    def test_outside_git_it_writes_and_warns(self):
        shutil.rmtree(self.root / ".git")
        code, envelope, _ = self.adopt(self.root, self.draft())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["staged"], [])
        self.assertTrue(any("not staged" in warning for warning in envelope["warnings"]))


ALTERNATING = {"rule": "alternating_external_anchor", "params": {"weeks": [
    {"name": "week-a", "days": {"mon": "session-a"}}, {"name": "week-b", "days": {"thu": "session-b"}}]}}


class AdoptPositionTest(AdoptCase):
    def setUp(self):
        self.root = self.instance(EMPTY)

    def alternating(self):
        draft = self.draft()
        draft["program"]["schedule"] = copy.deepcopy(ALTERNATING)
        return draft

    def test_a_rotation_starts_at_its_first_position_for_the_coming_week(self):
        code, envelope, _ = self.adopt(self.root, self.alternating())
        self.assertEqual(code, 0, envelope)
        self.assertEqual(read(self.root, "data/state.json")["rotation"],
                         {"position": "week-a", "confirmed": True, "confirmed_at": "2026-10-11", "week": "2026-10-12"})

    def test_position_picks_another(self):
        code, envelope, _ = self.adopt(self.root, self.alternating(), "--position", "week-b")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(read(self.root, "data/state.json")["rotation"]["position"], "week-b")

    def test_the_draft_can_carry_the_position(self):
        draft = self.alternating()
        draft["position"] = "week-b"
        code, envelope, _ = self.adopt(self.root, draft)
        self.assertEqual(code, 0, envelope)
        self.assertEqual(read(self.root, "data/state.json")["rotation"]["position"], "week-b")

    def test_an_unknown_position_exits_1(self):
        code, envelope, _ = self.adopt(self.root, self.alternating(), "--position", "week-z")
        self.assertEqual(code, 1, envelope)
        self.assertIn("week-a, week-b", envelope["error"]["message"])

    def test_a_position_on_a_rule_without_rotation_exits_1(self):
        code, envelope, _ = self.adopt(self.root, self.draft(), "--position", "week-a")
        self.assertEqual(code, 1, envelope)
        self.assertIn("fixed_weekdays", envelope["error"]["message"])


class AdoptReplaceTest(AdoptCase):
    def setUp(self):
        self.root = self.instance()
        init_repo(self.root)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "fixture")

    def replacement(self):
        """The valid program as a draft, with DB bench moved to linear."""
        program = read(self.root, "data/program.json")
        program["sessions"][0]["exercises"][1]["scheme"] = {"name": "linear", "params": {}}
        draft = self.draft()
        draft.update(program=program)
        return draft

    def test_without_replace_an_existing_program_refuses(self):
        before = snapshot(self.root)
        for argv in ((), ("--dry-run",)):
            code, envelope, _ = self.adopt(self.root, self.replacement(), *argv)
            self.assertEqual(code, 3, envelope)
            self.assertIn("--replace", envelope["error"]["message"])
        self.assertEqual(snapshot(self.root), before)

    def test_replace_archives_the_old_files_and_keeps_unchanged_scheme_state(self):
        old_program, old_state = read(self.root, "data/program.json"), read(self.root, "data/state.json")
        code, envelope, stderr = self.adopt(self.root, self.replacement(), "--replace")
        self.assertEqual(code, 0, (envelope, stderr))
        archive = "data/archive/programs/2026-10-11"
        self.assertEqual(read(self.root, f"{archive}/program.json"), old_program)
        self.assertEqual(read(self.root, f"{archive}/state.json"), old_state)
        self.assertEqual(sorted(envelope["data"]["archived"]), [f"{archive}/program.json", f"{archive}/state.json"])
        staged = git(self.root, "diff", "--cached", "--name-only").stdout.split()
        self.assertIn(f"{archive}/program.json", staged)
        state = read(self.root, "data/state.json")
        self.assertEqual(sorted(state["scheme_state"]), ["session-a/bb_back_squat"])
        self.assertEqual(state["scheme_state"]["session-a/bb_back_squat"],
                         old_state["scheme_state"]["session-a/bb_back_squat"])
        self.assertEqual(envelope["data"]["scheme_state"], {"kept": ["session-a/bb_back_squat"],
                                                            "dropped": ["session-a/db_bench_press"]})
        self.assertEqual(state["block"], old_state["block"])

    def test_a_second_adoption_the_same_day_archives_beside_the_first(self):
        for _ in range(2):
            code, envelope, _ = self.adopt(self.root, self.replacement(), "--replace")
            self.assertEqual(code, 0, envelope)
        self.assertTrue((self.root / "data/archive/programs/2026-10-11-2/program.json").is_file())

    def test_replace_removes_pages_for_dropped_sessions(self):
        draft = self.replacement()
        draft["program"]["sessions"] = draft["program"]["sessions"][:1]
        draft["program"]["schedule"]["params"]["days"] = {"mon": "session-a"}
        draft["hevy_routines"] = {ROUTINE_A: "session-a"}
        code, envelope, _ = self.adopt(self.root, draft, "--replace")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["removed"], ["routine/session-b.md"])
        self.assertFalse((self.root / "routine/session-b.md").exists())
        self.assertIn("routine/session-b.md", git(self.root, "diff", "--cached", "--name-only").stdout.split())

    def test_an_invalid_old_state_is_archived_as_it_is_and_carries_nothing(self):
        state = read(self.root, "data/state.json")
        del state["block"]
        write(self.root, "data/state.json", state)
        code, envelope, _ = self.adopt(self.root, self.replacement(), "--replace")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(read(self.root, "data/archive/programs/2026-10-11/state.json"), state)
        self.assertEqual(read(self.root, "data/state.json")["scheme_state"], {})
        self.assertTrue(any("archived as it is" in warning for warning in envelope["warnings"]))

    def test_one_off_and_temporary_routines_carry_over(self):
        state = read(self.root, "data/state.json")
        state["hevy"]["folders"]["one_off"] = 2
        state["hevy"]["temporary_routines"] = [{"routine_id": "t-1", "overlay_id": None, "session_id": None}]
        write(self.root, "data/state.json", state)
        draft = self.replacement()
        draft["hevy_folder"] = None
        code, envelope, _ = self.adopt(self.root, draft, "--replace")
        self.assertEqual(code, 0, envelope)
        hevy = read(self.root, "data/state.json")["hevy"]
        self.assertEqual(hevy["folders"], {"program": 1, "one_off": 2})
        self.assertEqual(hevy["temporary_routines"], state["hevy"]["temporary_routines"])


class AdoptFunctionTest(AdoptCase):
    def test_refusal_and_config_errors_are_the_contract_exceptions(self):
        root = self.instance()
        with self.assertRaises(RefusedError):
            program_drafts.adopt(root, self.draft(), today="2026-10-11", dry_run=True)
        bare = self.instance(EMPTY)
        (bare / "config.toml").unlink()
        with self.assertRaises(ConfigError):
            program_drafts.adopt(bare, self.draft(), today="2026-10-11", dry_run=True)


class AllowlistTest(unittest.TestCase):
    def test_both_commands_are_allowlisted(self):
        allow = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
        for name in ("program import-hevy", "program adopt"):
            self.assertIn(f"Bash(python3 -m coach {name}:*)", allow)


class NewProgramSkillTest(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(skill_text("new-program").split())

    def test_it_names_the_commands(self):
        for name in ("python3 -m coach program import-hevy", "python3 -m coach program adopt",
                     "python3 -m coach routines create", "python3 -m coach library seed",
                     "python3 -m coach library confirm"):
            self.assertTrue(name in self.text, name)

    def test_the_import_path_runs_its_commands_in_order(self):
        path = flat(step_text("new-program", "import.md").split("## Hevy route", 1)[1])
        order = [path.index(name) for name in ("library seed", "library confirm", "program import-hevy",
                                               "one table", "program adopt")]
        self.assertEqual(order, sorted(order))

    def test_a_designed_draft_spells_out_detected_and_keeps_routines_on_a_redesign(self):
        path = flat(step_text("new-program", "design.md"))
        self.assertIn('`{"percentage_based": false, "evidence": [], "suggested_schemes": []}`', path)
        self.assertIn("python3 -m coach state show", path)

    def test_it_does_no_load_arithmetic_and_no_hand_work_on_hevy_or_the_archive(self):
        for needle in ("units convert", "from-hevy-kg", "×2", "/2", "halve", "halving", "double the", "doubling",
                       "routines.json", "copy the current", "page through", "paging"):
            self.assertFalse(needle in self.text.lower(), needle)
        self.assertNotRegex(self.text, r"(?i)\barchive\b[^.]*\bby hand\b")


if __name__ == "__main__":
    unittest.main()
