import copy
import json
import unittest
from unittest import mock

from coach import commands, jsonio, program_drafts
from coach.library import Library
from tests.support import FIXTURES, REPO_ROOT
from tests.test_library import CliMixin, Instance, read_library, write_library


ENTRY = {
    "name": "Paused Squat",
    "muscles": {"primary": ["quadriceps", "glutes"], "secondary": ["lower_back"]},
    "pattern": "squat",
    "equipment": "barbell",
    "load_mode_default": "total",
    "load_mode": "total",
    "aliases": ["Two second paused squat"],
    "hevy_titles": [],
    "increment": {"kg": 2.5, "lb": 5},
    "substitutes": ["bb_back_squat"],
}
EXERCISE_ID = "custom_paused_squat"


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class CreateTest(CliMixin, unittest.TestCase):
    def setUp(self):
        self.instance = Instance()
        self.root = self.instance.__enter__()
        self.addCleanup(self.instance.__exit__, None, None, None)
        with (self.root / "config.toml").open("a", encoding="utf-8") as handle:
            handle.write("\n[hevy]\nenabled = false\n")
        self.source = self.root / "entry.json"
        self.input(ENTRY)

    def input(self, entry):
        self.source.write_text(jsonio.dumps(entry), encoding="utf-8")

    def create(self, *extra, exercise_id=EXERCISE_ID):
        return self.run_ok(self.root, "library", "create", exercise_id, "--input", str(self.source), *extra)

    def fails_without_writing(self, *extra, exercise_id=EXERCISE_ID):
        before = snapshot(self.root)
        envelope = self.run_fail(1, self.root, "library", "create", exercise_id,
                                 "--input", str(self.source), *extra)
        self.assertEqual(snapshot(self.root), before)
        return envelope["error"]

    def test_no_hevy_create_validates_searches_shows_metadata_and_confirms_mode(self):
        data = self.create()
        self.assertTrue(data["written"])
        self.assertFalse(data["unchanged"])
        self.assertEqual(read_library(self.root)["exercises"], {EXERCISE_ID: ENTRY})
        self.assertTrue(self.run_ok(self.root, "library", "validate")["valid"])
        shown = self.run_ok(self.root, "library", "show", EXERCISE_ID)["exercise"]
        self.assertEqual(shown, data["exercise"])
        for key, value in ENTRY.items():
            self.assertEqual(shown[key], value)
        self.assertEqual(shown["effective_load_mode"], "total")
        self.assertIsNone(shown["hevy_template_id"])
        self.assertEqual(shown["hevy_template_ids"], [])
        for query in ("paused squat", "two second"):
            matches = self.run_ok(self.root, "library", "search", query)["matches"]
            self.assertIn(EXERCISE_ID, [entry["id"] for entry in matches])

    def test_created_entry_is_usable_in_a_program_draft(self):
        self.create()
        draft = json.loads((FIXTURES / "program" / "draft.json").read_text(encoding="utf-8"))
        draft.update(source="design", hevy_routines={}, hevy_folder=None, report=[])
        session = draft["program"]["sessions"][0]
        session["exercises"] = [session["exercises"][0]]
        session["exercises"][0]["exercise_id"] = EXERCISE_ID
        draft["program"]["sessions"] = [session]
        draft["program"]["schedule"]["params"]["days"] = {"mon": "session-a"}
        self.assertEqual(program_drafts.draft_problems(draft, self.root), [])

    def test_dry_run_proposes_complete_entry_without_creating_any_files(self):
        before = snapshot(self.root)
        data = self.create("--dry-run")
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(data["written"])
        self.assertFalse(data["unchanged"])
        self.assertEqual(data["exercise"]["id"], EXERCISE_ID)
        self.assertEqual(data["exercise"]["muscles"], ENTRY["muscles"])
        self.assertFalse((self.root / "data").exists())

    def test_dry_run_preserves_existing_library_and_real_create_preserves_other_entries(self):
        write_library(self.root, {"db_curl": {"load_mode": "single_implement"}})
        before = snapshot(self.root)
        self.create("--dry-run")
        self.assertEqual(snapshot(self.root), before)
        self.create()
        self.assertEqual(read_library(self.root)["exercises"]["db_curl"], {"load_mode": "single_implement"})

    def test_identical_retry_is_explicitly_unchanged_without_rewriting(self):
        self.create()
        before = snapshot(self.root)
        with mock.patch("coach.jsonio.write_doc", side_effect=AssertionError("must not rewrite")):
            for args in ((), ("--dry-run",)):
                data = self.create(*args)
                self.assertTrue(data["unchanged"])
                self.assertFalse(data["written"])
        self.assertEqual(snapshot(self.root), before)

    def test_creation_never_updates_an_existing_custom_id(self):
        self.create()
        changed = copy.deepcopy(ENTRY)
        changed["increment"]["kg"] = 5
        self.input(changed)
        for args in ((), ("--dry-run",)):
            error = self.fails_without_writing(*args)
            self.assertIn("already exists", error["message"])
            self.assertIn("cannot update", error["message"])

    def test_catalogue_collision_and_invalid_ids_are_rejected(self):
        for exercise_id in ("bb_back_squat", "paused_squat", "custom_bad-id", "custom_Bad"):
            with self.subTest(exercise_id=exercise_id):
                error = self.fails_without_writing(exercise_id=exercise_id)
                self.assertIn("custom_", error["message"])

    def test_invalid_values_are_actionable_and_preserve_existing_document(self):
        write_library(self.root, {"db_curl": {"load_mode": "single_implement"}})
        invalid = {
            "muscles": {"primary": ["legs"], "secondary": []},
            "load_mode": "per_dumbbell",
            "load_mode_default": "unknown",
            "pattern": "unknown",
            "equipment": "unknown",
            "name": " ",
            "increment": {"kg": 0, "lb": 5},
            "substitutes": ["custom_missing"],
            "aliases": ["Bicep Curl (Dumbbell)"],
            "extra_field": True,
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                entry = copy.deepcopy(ENTRY)
                entry[field] = value
                self.input(entry)
                error = self.fails_without_writing()
                self.assertTrue(any(field in detail["path"] for detail in error["details"]), error)

    def test_required_facts_are_never_guessed_from_the_name(self):
        for field in ("name", "muscles", "pattern", "equipment", "load_mode_default", "load_mode"):
            with self.subTest(field=field):
                entry = copy.deepcopy(ENTRY)
                del entry[field]
                self.input(entry)
                self.assertIn(field, self.fails_without_writing()["message"])
        for field in ("primary", "secondary"):
            entry = copy.deepcopy(ENTRY)
            del entry["muscles"][field]
            self.input(entry)
            self.assertIn(field, str(self.fails_without_writing()["details"]))
        self.input(dict(ENTRY, load_mode=None))
        self.assertIn("confirmed", self.fails_without_writing()["message"])

    def test_bad_input_files_are_validation_errors(self):
        for content in ("[", "[]", "null", "42"):
            with self.subTest(content=content):
                self.source.write_text(content, encoding="utf-8")
                error = self.fails_without_writing()
                self.assertEqual(error["code"], "validation")
                self.assertIn("entry.json", error["message"])
        self.source.unlink()
        self.assertIn("cannot read", self.fails_without_writing()["message"])

    def test_failed_atomic_replace_preserves_document_and_cleans_temporary_file(self):
        write_library(self.root, {"db_curl": {"load_mode": "single_implement"}})
        before = snapshot(self.root)
        with mock.patch("coach.jsonio.os.replace", side_effect=OSError("disk failure")):
            self.run_fail(9, self.root, "library", "create", EXERCISE_ID, "--input", str(self.source))
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(Library.load(self.root).effective_load_mode("db_curl"), "single_implement")

    def test_command_metadata_and_exact_permission_are_local_only(self):
        command = next(item for item in commands.discover() if item.name == "library create")
        self.assertEqual(command.metadata(), {"writes": True, "network": False,
                                               "hevy_write": False, "git_write": False})
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Bash(python3 -m coach library create:*)", settings["permissions"]["allow"])

    def test_documented_entry_and_workflow_are_usable(self):
        reference = REPO_ROOT / "reference" / "custom-exercises.md"
        text = reference.read_text(encoding="utf-8")
        entry = json.loads(text.split("```json\n", 1)[1].split("```", 1)[0])
        self.input(entry)
        self.assertFalse(self.create("--dry-run")["written"])
        self.assertTrue(self.create()["written"])
        for skill, filename in (("new-program", "design.md"), ("goals", "SKILL.md")):
            path = REPO_ROOT / ".claude" / "skills" / skill / filename
            self.assertIn("../../../reference/custom-exercises.md", path.read_text(encoding="utf-8"))
            self.assertEqual((path.parent / "../../../reference/custom-exercises.md").resolve(), reference)


if __name__ == "__main__":
    unittest.main()
