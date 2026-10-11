import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coach import overlay
from coach.checks import instance
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli, run_module

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
OVERLAY = "data/overlays/2026-10-12-weekly.json"
R16 = (
    "schema_versions", "dangling_exercise_ids", "dangling_routine_ids", "overlay_library_consistency",
    "load_caps", "env_untracked", "bare_hevy_values", "render_fresh_sweep",
)


def check(root, *only, env=NOW):
    argv = ["--root", str(root), "check"]
    for check_id in only:
        argv += ["--only", check_id]
    code, envelope, _ = run_cli(argv, env=env)
    data = envelope.get("data") or {}
    return code, data.get("results", []), envelope


def statuses(results, check_id):
    return [row["status"] for row in results if row["id"] == check_id]


def failures(results, check_id):
    return [row for row in results if row["id"] == check_id and row["status"] == "fail"]


class TempCopy:
    """A throwaway copy of a fixture instance (the valid one by default)."""

    def __init__(self, source=VALID):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(source, self.root)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def edit_overlay(self, change):
        path = self.root / OVERLAY
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        if doc.get("approval"):
            doc["approval"]["hash"] = overlay.approval_hash(doc)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def edit_json(self, rel, change):
        path = self.root / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append_config(self, text):
        with open(self.root / "config.toml", "a", encoding="utf-8") as handle:
            handle.write(text)


def db_bench(doc):
    return doc["sessions"][0]["exercises"][1]


class RegistrationTest(unittest.TestCase):
    def test_list_names_every_check_with_its_owner(self):
        code, envelope, _ = run_cli(["--root", str(VALID), "check", "--list"])
        self.assertEqual(code, 0)
        listed = {row["id"]: row["owner"] for row in envelope["data"]["checks"]}
        for check_id in R16:
            self.assertEqual(listed.get(check_id), "R-16", check_id)
        for check_id in ("python_floor", "config", "library_valid", "overlay_schema", "overlay_hevy_drift"):
            self.assertIn(check_id, listed)


class ValidInstanceTest(unittest.TestCase):
    def test_every_check_passes_or_skips(self):
        code, results, _ = check(VALID)
        self.assertEqual(code, 0)
        for row in results:
            if row["id"] in R16:
                self.assertIn(row["status"], ("pass", "skip"), row)
        self.assertEqual([row for row in results if row["status"] == "fail"], [])

    def test_the_module_entry_point_exits_0(self):
        code, envelope, _ = run_module(["--root", str(VALID), "check"], env=NOW)
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["summary"]["fail"], 0)

    def test_no_cache_skips_dangling_routine_ids(self):
        self.assertFalse((VALID / ".coach" / "cache").exists())
        code, results, _ = check(VALID, "dangling_routine_ids")
        self.assertEqual(code, 0)
        self.assertEqual(statuses(results, "dangling_routine_ids"), ["skip"])


class AloneFixtureTest(unittest.TestCase):
    """Each check has a fixture whose one fault fails it and no other R-16 check."""

    CASES = {
        "schema_versions": ("schema-version-log", ["data/hevy/writes.jsonl", "schema_version 2"]),
        "dangling_exercise_ids": ("dangling-exercise", [OVERLAY, "db_bench_pres"]),
        "dangling_routine_ids": ("dangling-routine", [OVERLAY, "00000000-0000-4000-8000-000000000009"]),
        "overlay_library_consistency": ("overlay-library-mismatch", [OVERLAY, "F0000003"]),
        "load_caps": ("load-over-cap", [OVERLAY, "45/hand (Hevy: 90)"]),
        "bare_hevy_values": ("bare-hevy-value", [OVERLAY, "50 kg"]),
        "render_fresh_sweep": ("render-stale-sweep", ["profile.md", "2026-10-12-weekly"]),
    }

    def test_only_exits_1_naming_the_file_and_value(self):
        for check_id, (fixture, needles) in self.CASES.items():
            with self.subTest(check_id):
                code, results, envelope = check(INSTANCES / fixture, check_id)
                self.assertEqual(code, 1)
                self.assertEqual(envelope["error"]["code"], "validation")
                failed = failures(results, check_id)
                self.assertTrue(failed, results)
                text = " ".join(f"{row['path']} {row['message']}" for row in failed)
                for needle in needles:
                    self.assertIn(needle, text)

    def test_no_other_r16_check_fails(self):
        for check_id, (fixture, _) in self.CASES.items():
            with self.subTest(check_id):
                _, results, _ = check(INSTANCES / fixture)
                failed = {row["id"] for row in results if row["status"] == "fail" and row["id"] in R16}
                self.assertEqual(failed, {check_id})


class SchemaVersionsTest(unittest.TestCase):
    def test_newer_overlay_says_framework_sync(self):
        code, results, _ = check(INSTANCES / "schema-newer", "schema_versions")
        self.assertEqual(code, 1)
        [row] = failures(results, "schema_versions")
        self.assertEqual(row["path"], OVERLAY)
        self.assertIn(f"schema_version {overlay.current_version() + 1}", row["message"])
        self.assertIn("run /framework-sync", row["message"])

    def test_older_overlay_says_migrate_run(self):
        code, results, _ = check(INSTANCES / "schema-older", "schema_versions")
        self.assertEqual(code, 1)
        [row] = failures(results, "schema_versions")
        self.assertIn("schema_version 0", row["message"])
        self.assertIn("run python3 -m coach migrate run", row["message"])

    def test_older_jsonl_lines_are_fine_and_newer_ones_fail(self):
        with TempCopy() as tmp:
            line = {"schema_version": 1, "at": "2026-10-11T19:00:00Z", "kind": "verify", "routine_id": "r",
                    "overlay_id": "2026-10-12-weekly", "overlay_hash": "sha256:00", "verified": True, "diff": []}
            lines = (dict(line, schema_version=0), dict(line, schema_version=2), line)
            tmp.write("data/hevy/writes.jsonl", "\n".join(json.dumps(x) for x in lines) + "\n")
            code, results, _ = check(tmp.root, "schema_versions")
        self.assertEqual(code, 1)
        [row] = failures(results, "schema_versions")
        self.assertIn("line 2", row["message"])
        self.assertIn("/framework-sync", row["message"])

    def test_lines_go_to_the_schema_whose_constants_match(self):
        with TempCopy() as tmp:
            void = {"schema_version": 3, "op": "void", "id": "manual:x", "source": "manual",
                    "recorded_at": "2026-10-11T19:00:00Z", "reason": "typo", "by": "athlete"}
            tmp.write("data/activity/planned.jsonl", json.dumps(void) + "\n")
            _, results, _ = check(tmp.root, "schema_versions")
        [row] = failures(results, "schema_versions")
        self.assertEqual(row["path"], "data/activity/planned.jsonl")
        self.assertIn("schema_version 3", row["message"])

    def test_migrated_documents_come_from_the_migration_registry(self):
        with TempCopy() as tmp:
            tmp.edit_json("data/program.json", lambda doc: doc.update(schema_version=doc["schema_version"] + 1))
            _, results, _ = check(tmp.root, "schema_versions")
        [row] = failures(results, "schema_versions")
        self.assertEqual(row["path"], "data/program.json")
        self.assertIn("/framework-sync", row["message"])

    def test_cache_files_and_missing_versions(self):
        with TempCopy(INSTANCES / "dangling-routine") as tmp:
            tmp.edit_json(".coach/cache/hevy/meta.json", lambda doc: doc.update(schema_version=0))
            tmp.edit_json(".coach/cache/hevy/routines.json", lambda doc: doc.pop("schema_version"))
            code, results, _ = check(tmp.root, "schema_versions")
        self.assertEqual(code, 1)
        failed = {row["path"]: row["message"] for row in failures(results, "schema_versions")}
        self.assertIn("hevy pull --full", failed[".coach/cache/hevy/meta.json"])
        self.assertIn("no integer schema_version", failed[".coach/cache/hevy/routines.json"])

    def test_schemas_the_runner_does_not_own_name_their_paths(self):
        from coach import migrate

        claimed = instance.claimed_documents()
        for name in ("hevy_write_line", "hevy_verify_line", "hevy_retire_line", "hevy_cache_meta", "hevy_cache_file",
                     "nutrition_readings", "activity_sync", "activity_record", "activity_void", "planned_record",
                     "wellness_record"):
            self.assertIn(name, claimed)
        for name in migrate.registry().documents:
            self.assertNotIn(name, claimed, "the migration registry already says where it lives")

    def test_empty_instance_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.toml").write_text((VALID / "config.toml").read_text(encoding="utf-8"),
                                                encoding="utf-8")
            _, results, _ = check(tmp, "schema_versions")
        self.assertEqual(statuses(results, "schema_versions"), ["skip"])


class DanglingIdsTest(unittest.TestCase):
    def test_routine_ids_skip_when_hevy_is_off(self):
        with TempCopy(INSTANCES / "dangling-routine") as tmp:
            text = (tmp.root / "config.toml").read_text(encoding="utf-8").replace("enabled = true",
                                                                                   "enabled = false")
            tmp.write("config.toml", text)
            _, results, _ = check(tmp.root, "dangling_routine_ids")
        self.assertEqual(statuses(results, "dangling_routine_ids"), ["skip"])

    def test_routine_ids_ignore_overlays_whose_span_has_ended(self):
        _, results, _ = check(INSTANCES / "dangling-routine", "dangling_routine_ids",
                              env={"COACH_NOW": "2026-10-19T09:00:00Z"})
        self.assertEqual(statuses(results, "dangling_routine_ids"), ["skip"])

    def test_routine_ids_pass_when_every_routine_is_cached(self):
        with TempCopy(INSTANCES / "dangling-routine") as tmp:
            tmp.edit_overlay(lambda doc: doc["sessions"][1].update(
                hevy_routine_id="00000000-0000-4000-8000-000000000002"))
            code, results, _ = check(tmp.root, "dangling_routine_ids")
        self.assertEqual(code, 0)
        self.assertEqual(statuses(results, "dangling_routine_ids"), ["pass"])

    def test_exercise_ids_check_every_overlay(self):
        _, results, _ = check(INSTANCES / "dangling-exercise", "dangling_exercise_ids",
                              env={"COACH_NOW": "2026-12-01T09:00:00Z"})
        self.assertEqual(statuses(results, "dangling_exercise_ids"), ["fail"])


class OverlayLibraryConsistencyTest(unittest.TestCase):
    def test_template_mismatch_names_the_owner(self):
        _, results, _ = check(INSTANCES / "overlay-library-mismatch", "overlay_library_consistency")
        [row] = failures(results, "overlay_library_consistency")
        self.assertIn("db_single_arm_row", row["message"])

    def test_load_mode_mismatch(self):
        with TempCopy() as tmp:
            tmp.edit_json("data/exercises.json",
                          lambda doc: doc["exercises"]["db_bench_press"].update(load_mode="single_implement"))
            code, results, _ = check(tmp.root, "overlay_library_consistency")
        self.assertEqual(code, 1)
        [row] = failures(results, "overlay_library_consistency")
        self.assertIn("per_hand_x2", row["message"])
        self.assertIn("single_implement", row["message"])

    def test_unconfirmed_mode_is_left_to_load_modes_confirmed(self):
        with TempCopy() as tmp:
            tmp.edit_json("data/exercises.json",
                          lambda doc: doc["exercises"]["db_bench_press"].update(load_mode=None))
            _, results, _ = check(tmp.root, "overlay_library_consistency")
        self.assertEqual(statuses(results, "overlay_library_consistency"), ["pass"])


class LoadCapsTest(unittest.TestCase):
    def test_caps_table_wins_over_dumbbell_max(self):
        with TempCopy(INSTANCES / "load-over-cap") as tmp:
            tmp.append_config("db_bench_press = 50\nbb_back_squat = 90\n")
            _, results, _ = check(tmp.root, "load_caps")
        [row] = failures(results, "load_caps")
        self.assertIn("bb_back_squat", row["message"])
        self.assertIn("[caps] bb_back_squat", row["message"])

    def test_location_dumbbell_max(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: doc["sessions"][0].update(location="home"))
            _, results, _ = check(tmp.root, "load_caps")
        [row] = failures(results, "load_caps")
        self.assertIn("25/hand (Hevy: 50)", row["message"])
        self.assertIn("[equipment.locations.home] dumbbell_max", row["message"])

    def test_single_implement_uses_dumbbell_max(self):
        with TempCopy() as tmp:
            text = (tmp.root / "config.toml").read_text(encoding="utf-8").replace("dumbbell_max = 40.0",
                                                                                   "dumbbell_max = 27.5")
            tmp.write("config.toml", text)
            _, results, _ = check(tmp.root, "load_caps")
        [row] = failures(results, "load_caps")
        self.assertIn("db_single_arm_row", row["message"])

    def test_loads_with_broken_arithmetic_are_left_to_overlay_arithmetic(self):
        with TempCopy(INSTANCES / "overlay-bad-arithmetic") as tmp:
            text = (tmp.root / "config.toml").read_text(encoding="utf-8").replace("dumbbell_max = 40.0",
                                                                                   "dumbbell_max = 10.0")
            tmp.write("config.toml", text)
            tmp.edit_overlay(lambda doc: db_bench(doc)["sets"][1]["load"].update(per_hand=None))
            _, results, _ = check(tmp.root, "load_caps")
        messages = " ".join(row["message"] for row in failures(results, "load_caps"))
        self.assertNotIn("crashed", messages)
        self.assertIn("db_single_arm_row", messages)

    def test_ended_overlays_are_not_checked(self):
        _, results, _ = check(INSTANCES / "load-over-cap", "load_caps", env={"COACH_NOW": "2026-10-19T09:00:00Z"})
        self.assertEqual(statuses(results, "load_caps"), ["skip"])


class GitRepo:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(VALID, self.root)
        self.git("init", "-q")
        self.git("config", "core.excludesFile", os.devnull)
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *argv):
        subprocess.run(["git", "-C", str(self.root), *argv], check=True, capture_output=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


@unittest.skipUnless(shutil.which("git"), "needs git")
class EnvUntrackedTest(unittest.TestCase):
    def run_check(self, root):
        _, results, _ = check(root, "env_untracked")
        return [row for row in results if row["id"] == "env_untracked"]

    def test_committed_env_fails(self):
        with GitRepo() as repo:
            (repo.root / ".env").write_text("HEVY_API_KEY=not-a-real-key\n", encoding="utf-8")
            repo.git("add", "-f", ".env")
            repo.git("commit", "-q", "-m", "add env")
            [row] = self.run_check(repo.root)
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["path"], ".env")
        self.assertIn("tracked", row["message"])
        self.assertNotIn("not-a-real-key", row["message"])

    def test_untracked_and_ignored_env_passes(self):
        with GitRepo() as repo:
            (repo.root / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo.root / ".env").write_text("HEVY_API_KEY=not-a-real-key\n", encoding="utf-8")
            [row] = self.run_check(repo.root)
        self.assertEqual(row["status"], "pass")

    def test_untracked_but_not_ignored_env_fails(self):
        with GitRepo() as repo:
            (repo.root / ".env").write_text("HEVY_API_KEY=not-a-real-key\n", encoding="utf-8")
            [row] = self.run_check(repo.root)
        self.assertEqual(row["status"], "fail")
        self.assertIn(".gitignore", row["message"])

    def test_no_env_and_no_ignore_rule_warns(self):
        with GitRepo() as repo:
            [row] = self.run_check(repo.root)
        self.assertEqual(row["status"], "warn")

    def test_outside_git_skips(self):
        with TempCopy() as tmp:
            env = dict(NOW, GIT_CEILING_DIRECTORIES=str(tmp.root.parent))
            _, results, _ = check(tmp.root, "env_untracked", env=env)
        self.assertEqual(statuses(results, "env_untracked"), ["skip"])


class BareHevyValuesTest(unittest.TestCase):
    def test_equipment_and_other_exercises_are_not_dumbbell_prescriptions(self):
        examples = (
            "Home only: adjustable dumbbells, 2–20 kg per hand in 2 kg steps.",
            "dumbbells 5–40 kg per hand in 2.5 kg steps. Plates down to 1.25 kg",
            "cables and dumbbells to 30 kg.",
            "Next block: the 20 kg dumbbell is the heaviest she has. Goal plan current: 1.9 kg to 73 kg.",
            "dumbbell Romanian deadlift 20/hand × 10–12, leg curl 25 kg × 15, "
            "assisted pull-up 6s at 50 kg assistance.",
            "Dumbbells go up in 2.5 kg at the gym.",
            "Lateral raise at 15 lb fell short: the 5 lb cable step is a third of the load.",
            "Lateral raise on the cable machine: 10 kg.",
            "dumbbells up to 30 kg per hand.",
            "DB bench 20 kg per hand, leg curl 25 kg.",
        )
        for text in examples:
            with self.subTest(text=text), TempCopy() as tmp:
                config = (tmp.root / "config.toml").read_text()
                tmp.write("config.toml", config.replace("enabled = true", "enabled = false", 1))
                tmp.write("profile.md", text)
                code, results, _ = check(tmp.root, "bare_hevy_values")
                self.assertEqual(code, 0, failures(results, "bare_hevy_values"))

    def test_explicit_dumbbell_loads_still_fail_in_separate_clauses(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "DB bench 20 kg, leg curl 25 kg; dumbbell RDL 30 kg.")
            _, results, _ = check(tmp.root, "bare_hevy_values")
            failed = failures(results, "bare_hevy_values")
            self.assertEqual(len(failed), 2, failed)
            self.assertIn("20 kg", failed[0]["message"])
            self.assertIn("30 kg", failed[1]["message"])
            self.assertTrue(all("'25 kg'" not in r["message"] for r in failed))

    def test_bodyweight_context_does_not_change_an_exercises_equipment(self):
        examples = (
            "Arnold press 20 kg at bodyweight 73 kg",
            "Arnold press 20 kg with bodyweight down 2 kg",
            "Arnold press 20 kg with bodyweight stable",
            "Arnold press 20 kg: the cable step is 5 kg",
            "Arnold press 20 kg; bodyweight 73 kg",
            "At bodyweight 73 kg, Arnold press 20 kg",
            "Arnold press 20 kg and bodyweight fell 2 kg",
        )
        for text in examples:
            with self.subTest(text=text), TempCopy() as tmp:
                tmp.write("profile.md", text)
                code, results, _ = check(tmp.root, "bare_hevy_values")
                self.assertEqual(code, 1, results)
                [failed] = failures(results, "bare_hevy_values")
                self.assertIn(": '20 kg' for db_arnold_press", failed["message"])

    def test_conjunctions_separate_exercises_and_preserve_load_instructions(self):
        for conjunction in ("and", "and then", "but", "but then", "then", "plus", "while"):
            for following, expected in (("leg curl 25 kg", 0),
                                        ("3 sets of leg curl at 25 kg", 0),
                                        ("move to 25 kg", 1),
                                        ("dumbbell RDL 25 kg", 1)):
                text = f"DB bench 20/hand {conjunction} {following}."
                with self.subTest(text=text), TempCopy() as tmp:
                    tmp.write("profile.md", text)
                    code, results, _ = check(tmp.root, "bare_hevy_values")
                    self.assertEqual(code, expected, results)

    def test_comma_preserves_load_instructions_but_not_a_new_numbered_exercise(self):
        for text, expected in (("DB bench, move to 20 kg.", 1),
                               ("DB bench 20/hand, 3 sets of leg curl at 25 kg.", 0),
                               ("DB bench, 20 kg, leg curl at 25 kg.", 1)):
            with self.subTest(text=text), TempCopy() as tmp:
                tmp.write("profile.md", text)
                code, results, _ = check(tmp.root, "bare_hevy_values")
                self.assertEqual(code, expected, results)
                self.assertTrue(all("'25 kg'" not in r["message"] for r in failures(results, "bare_hevy_values")))

    def test_measurement_exemption_does_not_hide_a_later_prescription(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: db_bench(doc).update(target_note="bodyweight 73 kg and move to 8 kg"))
            code, results, _ = check(tmp.root, "bare_hevy_values")
            self.assertEqual(code, 1)
            [failed] = failures(results, "bare_hevy_values")
            self.assertIn(": '8 kg' for db_bench_press", failed["message"])

    def test_a_comma_before_a_load_does_not_detach_it_from_the_exercise(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "DB bench, 20 kg")
            code, results, _ = check(tmp.root, "bare_hevy_values")
            self.assertEqual(code, 1, results)
            self.assertIn("'20 kg'", failures(results, "bare_hevy_values")[0]["message"])

    def test_confirmed_per_hand_goblet_load_fails_without_hevy_requirement(self):
        with TempCopy() as tmp:
            tmp.edit_json("data/exercises.json", lambda d: d["exercises"].update(
                goblet_squat={"load_mode": "per_hand_x2"}))
            config = (tmp.root / "config.toml").read_text()
            tmp.write("config.toml", config.replace("enabled = true", "enabled = false", 1))
            tmp.write("profile.md", "goblet squat 20 kg")
            code, results, _ = check(tmp.root, "bare_hevy_values")
            self.assertEqual(code, 1)
            [failed] = failures(results, "bare_hevy_values")
            self.assertIn("per-hand", failed["message"])
            self.assertNotIn("Hevy", failed["message"])

    def test_equipment_context_resolves_lateral_raise_variants(self):
        for text, expected in (("dumbbell lateral raise 10 kg", 1),
                               ("cable lateral raise 10 kg", 0),
                               ("lateral raise (cable) 10 kg", 0),
                               ("cable-based lateral raise 10 kg", 0),
                               ("lateral raise 10 kg on the cable machine", 0),
                               ("lateral raise with 10 kg dumbbells", 1),
                               ("lateral raise 10 kg using dumbbells", 1),
                               ("dumbbells for lateral raise 10 kg", 1),
                               ("lateral raise 10 kg", 0)):
            with self.subTest(text=text), TempCopy() as tmp:
                tmp.write("profile.md", text)
                code, results, _ = check(tmp.root, "bare_hevy_values")
                self.assertEqual(code, expected, failures(results, "bare_hevy_values"))

    def test_overlay_ignores_measurements_but_still_checks_its_load(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: db_bench(doc).update(
                target_note="bodyweight 73 kg; dumbbells up to 30 kg; move to 8 kg"))
            _, results, _ = check(tmp.root, "bare_hevy_values")
            [failed] = failures(results, "bare_hevy_values")
            self.assertIn(": '8 kg' for db_bench_press", failed["message"])

    def test_per_hand_only_passes_with_hevy_enabled(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "DB bench 20 kg per hand.")
            tmp.edit_overlay(lambda doc: db_bench(doc).update(target_note="move to 20 kg per hand"))
            code, results, _ = check(tmp.root, "bare_hevy_values")
            self.assertEqual(code, 0, failures(results, "bare_hevy_values"))

    def test_two_number_form_passes(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: db_bench(doc).update(target_note="go to 25/hand (Hevy: 50)"))
            code, results, _ = check(tmp.root, "bare_hevy_values")
        self.assertEqual(code, 0)
        self.assertEqual(statuses(results, "bare_hevy_values"), ["pass"])

    def test_other_load_modes_are_not_checked(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: doc["sessions"][0]["exercises"][0].update(target_note="go to 100 kg"))
            code, _, _ = check(tmp.root, "bare_hevy_values")
        self.assertEqual(code, 0)

    def test_arrow_without_per_hand_fails(self):
        with TempCopy() as tmp:
            tmp.edit_overlay(lambda doc: db_bench(doc).update(change="45 → 50"))
            _, results, _ = check(tmp.root, "bare_hevy_values")
        [row] = failures(results, "bare_hevy_values")
        self.assertIn("$.sessions[0].exercises[1].change", row["message"])

    def test_profile_prose_names_the_line(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "# Profile\n\nSquat 100 kg for 5.\nDB bench: work up to 50 kg by December.\n")
            _, results, _ = check(tmp.root, "bare_hevy_values")
        [row] = failures(results, "bare_hevy_values")
        self.assertEqual(row["path"], "profile.md")
        self.assertIn("line 4", row["message"])
        self.assertIn("50 kg", row["message"])

    def test_check_in_load_column(self):
        record = (
            "# Check-in\n\n| Exercise | Sets × reps | Load (kg) | RPE |\n| --- | --- | --- | --- |\n"
            "| Back squat | 3×5 | 100 | 7 |\n| DB bench | 3×10 | 45 | 8 |\n|  | 1×12 | 40 | 9 |\n"
            "| Dumbbell row | 3×10 | 30 | 8 |\n| Incline DB press | 3×10 | 22.5/hand (Hevy: 45) | 8 |\n"
        )
        with TempCopy() as tmp:
            tmp.write("check-ins/2026-10-04.md", record)
            _, results, _ = check(tmp.root, "bare_hevy_values")
        failed = failures(results, "bare_hevy_values")
        self.assertEqual(len(failed), 2, failed)
        self.assertTrue(all(row["path"] == "check-ins/2026-10-04.md" for row in failed))
        self.assertIn("line 6", failed[0]["message"])
        self.assertIn("line 7", failed[1]["message"])

    def test_figures_belong_only_to_an_exercise_named_before_them(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "# Profile\n\nSquat up to 100 kg; DB bench stays 25/hand (Hevy: 50).\n"
                                    "Aim for 50 kg on the DB bench.\n")
            code, results, _ = check(tmp.root, "bare_hevy_values")
        self.assertEqual(code, 0, failures(results, "bare_hevy_values"))

    def test_table_rows_carry_an_exercise_only_into_empty_exercise_cells(self):
        record = (
            "# Check-in\n\n| Exercise | Load |\n| --- | --- |\n| DB bench press | 25/hand (Hevy: 50) |\n"
            "| Squat | 100 kg |\n|  | 90 kg |\n| DB bench | 45 kg |\n|  | 40 kg |\n"
        )
        with TempCopy() as tmp:
            tmp.write("check-ins/2026-10-04.md", record)
            _, results, _ = check(tmp.root, "bare_hevy_values")
        failed = failures(results, "bare_hevy_values")
        self.assertEqual([row["message"].split(":")[0] for row in failed],
                         ["check-ins/2026-10-04.md line 8", "check-ins/2026-10-04.md line 9"])

    def test_tables_that_give_both_numbers_in_their_columns_pass(self):
        tables = (
            "| Exercise | Per hand (kg) | Hevy (kg) |\n| --- | --- | --- |\n| DB bench press | 25 | 50 |\n",
            "| Exercise | Load/hand (kg) |\n| --- | --- |\n| DB bench press | 25 |\n",
            "| Exercise | Load (kg) | Hevy |\n| --- | --- | --- |\n| DB bench press | 22.5 → 25 | 45 → 50 |\n",
        )
        for table in tables:
            with self.subTest(table), TempCopy() as tmp:
                tmp.write("check-ins/2026-10-04.md", "# Check-in\n\n" + table)
                code, results, _ = check(tmp.root, "bare_hevy_values")
                self.assertEqual(code, 0, failures(results, "bare_hevy_values"))

    def test_a_load_column_without_its_hevy_value_fails(self):
        table = "| Exercise | Load (kg) | Hevy |\n| --- | --- | --- |\n| DB bench press | 25 |  |\n"
        with TempCopy() as tmp:
            tmp.write("check-ins/2026-10-04.md", "# Check-in\n\n" + table)
            _, results, _ = check(tmp.root, "bare_hevy_values")
        [row] = failures(results, "bare_hevy_values")
        self.assertIn("'25'", row["message"])

    def test_rendered_regions_are_not_scanned(self):
        with TempCopy() as tmp:
            record = (tmp.root / "check-ins/2026-10-11.md").read_text(encoding="utf-8")
            tmp.write("check-ins/2026-10-11.md", record.replace("25/hand (Hevy: 50)", "50 kg"))
            _, results, _ = check(tmp.root, "bare_hevy_values")
        self.assertEqual(statuses(results, "bare_hevy_values"), ["pass"])


class LoadFigureTest(unittest.TestCase):
    def bare(self, text, load_column=False):
        return [figure.text for figure in instance.bare_figures(text, load_column=load_column)]

    def test_figures(self):
        cases = {
            "go to 50 kg": ["50 kg"],
            "dumbbells go up in 2.5 kg": [],
            "move dumbbells to 8 kg": ["8 kg"],
            "dumbbells up to 30 kg; move to 8 kg": ["8 kg"],
            "equipment has 2.5 kg steps; add 2.5 kg": ["2.5 kg"],
            "the cable step is 5 kg and move to 8 kg": ["8 kg"],
            "bodyweight 73 kg; move to 8 kg": ["8 kg"],
            "bodyweight 73 kg and move to 8 kg": ["8 kg"],
            "bodyweight fell 2 kg; move to 8 kg per hand": [],
            "bodyweight dropped by 2 kg and move to 8 kg": ["8 kg"],
            "bodyweight went from 75 kg to 73 kg and move to 8 kg": ["8 kg"],
            "bodyweight was 75 kg and now 73 kg; move to 8 kg per hand": [],
            "bodyweight 75 → 73 and move to 8 kg": ["8 kg"],
            "bodyweight stable and move to 8 kg": ["8 kg"],
            "Goal plan current: 1.9 kg to 73 kg and move to 8 kg": ["8 kg"],
            "cables and dumbbells to 30 kg.": [],
            "move cables and dumbbells to 8 kg": ["8 kg"],
            "Next block: the 20 kg dumbbell is the heaviest she has.": [],
            "plates down to 1.25 kg": [],
            "go to 25/hand (Hevy: 50)": [],
            "22.5 → 25/hand": [],
            "45 → 50": ["45", "50"],
            "45 -> 50 kg": ["45", "50 kg"],
            "pause 1 s on the chest": [],
            "3×8–10 @ RPE 8": [],
            "RPE 7 → 8": [],
            "add 2.5 kg": ["2.5 kg"],
            "25 kg each": [],
            "25 lb per hand": [],
            "25 (Hevy: 50)": [],
            "Hevy: 50": [],
            "on 2026-10-11": [],
            "8 reps → 10 reps": [],
        }
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(self.bare(text), expected)

    def test_load_column_cells(self):
        self.assertEqual(self.bare("45", load_column=True), ["45"])
        self.assertEqual(self.bare("22.5/hand (Hevy: 45)", load_column=True), [])
        self.assertEqual(self.bare("BW", load_column=True), [])


class RenderFreshSweepTest(unittest.TestCase):
    def test_stale_card_region_anywhere(self):
        with TempCopy() as tmp:
            card = (tmp.root / "nutrition/menu/whey-shake.md").read_text(encoding="utf-8")
            start = card.index("<!-- coach:begin card whey-shake -->")
            end = card.index("<!-- coach:end card whey-shake -->") + len("<!-- coach:end card whey-shake -->")
            tmp.write("notes/snacks.md", "# Snacks\n\n" + card[start:end].replace("kcal", "calories") + "\n")
            _, results, _ = check(tmp.root, "render_fresh_sweep")
        [row] = failures(results, "render_fresh_sweep")
        self.assertEqual(row["path"], "notes/snacks.md")

    def test_regions_their_owners_check_are_left_to_them(self):
        with TempCopy() as tmp:
            record = (tmp.root / "check-ins/2026-10-11.md").read_text(encoding="utf-8")
            tmp.write("check-ins/2026-10-11.md", record.replace("25/hand (Hevy: 50)", "27.5/hand (Hevy: 55)"))
            _, results, _ = check(tmp.root, "render_fresh_sweep", "overlay_render_fresh")
        self.assertEqual(statuses(results, "overlay_render_fresh"), ["fail"])
        self.assertEqual(statuses(results, "render_fresh_sweep"), ["pass"])

    def test_region_that_cannot_render_warns(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "<!-- coach:begin overlay 2026-01-05-weekly -->\nold\n"
                                    "<!-- coach:end overlay 2026-01-05-weekly -->\n")
            code, results, _ = check(tmp.root, "render_fresh_sweep")
        self.assertEqual(code, 0)
        self.assertEqual(statuses(results, "render_fresh_sweep"), ["warn"])

    def test_unbalanced_markers_fail(self):
        with TempCopy() as tmp:
            tmp.write("profile.md", "# Profile\n\n<!-- coach:begin overlay 2026-10-12-weekly -->\nhalf\n")
            _, results, _ = check(tmp.root, "render_fresh_sweep")
        [row] = failures(results, "render_fresh_sweep")
        self.assertEqual(row["path"], "profile.md")

    def test_snapshot_kinds_and_unknown_kinds(self):
        with TempCopy() as tmp:
            tmp.write("check-ins/2026-10-04.md",
                      "# Check-in\n\n<!-- coach:begin cardio 2026-W40 -->\nold numbers\n"
                      "<!-- coach:end cardio 2026-W40 -->\n\n<!-- coach:begin mystery x -->\n?\n"
                      "<!-- coach:end mystery x -->\n")
            code, results, _ = check(tmp.root, "render_fresh_sweep")
        self.assertEqual(code, 0)
        self.assertEqual(statuses(results, "render_fresh_sweep"), ["warn"])

    def test_markers_shown_as_examples_are_not_regions(self):
        with TempCopy() as tmp:
            card = tmp.root / "nutrition/menu/chicken-rice-bowl.md"
            card.write_text(card.read_text(encoding="utf-8").replace("servings = 1", "servings = 2", 1),
                            encoding="utf-8")
            for name in ("recipe-cards.md", "research-notes.md"):
                shutil.copy(REPO_ROOT / "reference" / name, tmp.root / "reference" / name)
            tmp.write("notes/inline.md", "Write regions as text <!-- coach:begin card whey-shake --> mid-line.\n")
            _, results, _ = check(tmp.root, "render_fresh_sweep")
        self.assertEqual(statuses(results, "render_fresh_sweep"), ["pass"])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_framework_files_are_left_out(self):
        stale = "<!-- coach:begin card whey-shake -->\nstale\n<!-- coach:end card whey-shake -->\n"
        with GitRepo() as repo:
            (repo.root / "reference" / "guide.md").write_text(stale, encoding="utf-8")
            repo.git("add", "reference/guide.md")
            repo.git("commit", "-q", "-m", "template")
            commit = subprocess.run(["git", "-C", str(repo.root), "rev-parse", "HEAD"], check=True,
                                    capture_output=True, text=True).stdout.strip()
            (repo.root / "notes").mkdir()
            (repo.root / "notes" / "mine.md").write_text(stale, encoding="utf-8")
            _, before, _ = check(repo.root, "render_fresh_sweep")
            (repo.root / ".claude").mkdir()
            (repo.root / ".claude" / "framework-sync.json").write_text(
                json.dumps({"template_commit": commit, "synced_at": "2026-10-11"}), encoding="utf-8")
            _, after, _ = check(repo.root, "render_fresh_sweep")
        self.assertEqual(sorted(row["path"] for row in failures(before, "render_fresh_sweep")),
                         ["notes/mine.md", "reference/guide.md"])
        self.assertEqual([row["path"] for row in failures(after, "render_fresh_sweep")], ["notes/mine.md"])

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_bundled_tests_are_excluded_independently_of_framework_sync(self):
        stale = "<!-- coach:begin overlay 2026-10-12-weekly -->\nstale\n" \
                "<!-- coach:end overlay 2026-10-12-weekly -->\n"
        bundled = stale + "<!-- coach:begin week-review 2026-10-11 -->\nstale\n" \
                  "<!-- coach:end week-review 2026-10-11 -->\n" \
                  "<!-- coach:begin overlay 2026-01-05-weekly -->\nunavailable\n" \
                  "<!-- coach:end overlay 2026-01-05-weekly -->\n"
        athlete_paths = ["profile.md", "notes/tests/custom.md", "tests-notes/custom.md"]
        for metadata in ("absent", "malformed", "unreadable", "unknown-commit", "valid"):
            with self.subTest(metadata=metadata), GitRepo() as repo:
                guide = repo.root / "reference/guide.md"
                guide.write_text(stale, encoding="utf-8")
                repo.git("add", "reference/guide.md")
                repo.git("commit", "-q", "-m", "template")
                commit = subprocess.run(["git", "-C", str(repo.root), "rev-parse", "HEAD"], check=True,
                                        capture_output=True, text=True).stdout.strip()
                marker = repo.root / ".claude/framework-sync.json"
                if metadata != "absent":
                    marker.parent.mkdir()
                    if metadata == "unreadable":
                        marker.mkdir()
                    elif metadata == "malformed":
                        marker.write_text("{", encoding="utf-8")
                    else:
                        marker.write_text(json.dumps({"template_commit": commit if metadata == "valid"
                                                      else "unknown-commit"}), encoding="utf-8")
                fixture = repo.root / "tests/fixtures/instance/profile.md"
                fixture.parent.mkdir(parents=True)
                fixture.write_text(bundled, encoding="utf-8")
                for rel in athlete_paths:
                    path = repo.root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(stale, encoding="utf-8")
                code, results, _ = check(repo.root, "render_fresh_sweep")
                expected = athlete_paths + ([] if metadata == "valid" else ["reference/guide.md"])
                self.assertEqual(code, 1)
                self.assertEqual(sorted(row["path"] for row in results), sorted(expected), results)
                self.assertEqual(statuses(results, "render_fresh_sweep"), ["fail"] * len(expected))

    def test_valid_regions_are_fresh(self):
        _, results, _ = check(VALID, "render_fresh_sweep")
        [row] = [r for r in results if r["id"] == "render_fresh_sweep"]
        self.assertEqual(row["status"], "pass")


if __name__ == "__main__":
    unittest.main()
