import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from coach import commands, jsonio
from coach.validate import validate
from tests.support import FIXTURES, INSTANCES, REPO_ROOT, VALID, run_cli, run_module

NOW = "2026-10-11T18:00:00Z"
ENV = {"COACH_NOW": NOW}
ENVELOPE = jsonio.load_schema("envelope")
HEVY_C1 = "hevy_conditioning:00000000-0000-4000-8000-0000000000c1"
ACTIVITIES = "data/activity/activities.jsonl"
LOCAL_WELLNESS = ".coach/activity/wellness.jsonl"
GIT_WELLNESS = "data/activity/wellness.jsonl"


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class ActivityCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(VALID, self.root, dirs_exist_ok=True)

    def set_config(self, extra, table="[activity]\n"):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace(table, table + extra, 1), encoding="utf-8")

    def cli(self, *argv, expect=0, root=None, env=None):
        code, envelope, stderr = run_cli(["--root", str(root or self.root), *argv], env=dict(ENV, **(env or {})))
        self.assertEqual(code, expect, (envelope, stderr))
        self.assertEqual(validate(envelope, ENVELOPE), [])
        return envelope

    def ok(self, *argv, **kwargs):
        return self.cli(*argv, **kwargs)["data"]

    def lines(self, relative):
        path = self.root / relative
        return [json.loads(text) for text in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


class ListTest(ActivityCase):
    def test_list_on_the_valid_fixture(self):
        code, envelope, stderr = run_module(["--root", str(VALID), "activity", "list", "--from", "2026-10-05",
                                             "--to", "2026-10-11"], env=ENV)
        self.assertEqual(code, 0, stderr)
        found = envelope["data"]["activities"]
        self.assertEqual([(a["local_date"], a["kind"]) for a in found],
                         [("2026-10-08", "run"), ("2026-10-10", "conditioning")])
        conditioning = found[1]
        self.assertEqual(conditioning["id"], "manual:2026-10-10-conditioning-1")
        self.assertEqual(conditioning["merged_from"], ["manual:2026-10-10-conditioning-1", HEVY_C1])

    def test_list_defaults_to_this_week(self):
        data = self.ok("activity", "list")
        self.assertEqual(data["span"], {"start": "2026-10-05", "end": "2026-10-11"})
        self.assertEqual(data["count"], 2)

    def test_show_finds_a_merged_record_by_either_id(self):
        data = self.ok("activity", "show", HEVY_C1)
        self.assertEqual(data["activity"]["id"], "manual:2026-10-10-conditioning-1")
        self.assertEqual(len(data["lines"]), 1)
        self.cli("activity", "show", "manual:nope", expect=1)


class AddTest(ActivityCase):
    ARGS = ("activity", "add", "--kind", "run", "--start", "2026-10-09T06:30:00+01:00", "--duration-min", "30",
            "--distance-km", "5", "--rpe", "6")

    def test_dry_run_returns_the_record_and_writes_nothing(self):
        before = snapshot(self.root)
        record = self.ok(*self.ARGS, "--dry-run")["record"]
        self.assertEqual(record["start"], "2026-10-09T05:30:00Z")
        self.assertEqual(record["local_date"], "2026-10-09")
        self.assertEqual(record["distance_meters"], 5000)
        self.assertEqual(record["utc_offset"], "+01:00")
        self.assertEqual(record["id"], "manual:2026-10-09-run-1")
        self.assertEqual(snapshot(self.root), before)

    def test_real_run_appends_exactly_one_line(self):
        before = self.lines(ACTIVITIES)
        data = self.ok(*self.ARGS)
        self.assertTrue(data["written"])
        after = self.lines(ACTIVITIES)
        self.assertEqual(after[:-1], before)
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(after[-1], data["record"])

    def test_a_second_run_that_day_takes_the_next_number(self):
        self.ok(*self.ARGS)
        self.assertEqual(self.ok(*self.ARGS)["record"]["id"], "manual:2026-10-09-run-2")

    def test_naive_start_is_athlete_local_time(self):
        self.set_config('timezone = "America/New_York"\n', table="[athlete]\n")
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('timezone = "UTC"\n', ""), encoding="utf-8")
        record = self.ok("activity", "add", "--kind", "walk", "--start", "2026-10-09T21:30:00",
                         "--duration-min", "45", "--distance-mi", "2", "--dry-run")["record"]
        self.assertEqual(record["start"], "2026-10-10T01:30:00Z")
        self.assertEqual(record["utc_offset"], "-04:00")
        self.assertEqual(record["local_date"], "2026-10-09")
        self.assertEqual(record["distance_meters"], 3218.688)

    def test_bad_values_exit_1(self):
        self.cli("activity", "add", "--kind", "run", "--start", "soon", "--duration-min", "30", expect=1)
        self.cli("activity", "add", "--kind", "run", "--start", NOW, "--duration-min", "30", "--rpe", "11", expect=1)
        self.cli("activity", "add", "--kind", "run", "--start", NOW, "--duration-min", "0", expect=1)
        self.cli("activity", "add", "--kind", "lifting", "--start", NOW, "--duration-min", "30", expect=2)


class VoidTest(ActivityCase):
    def test_void_hides_the_record_and_keeps_history(self):
        before = self.lines(ACTIVITIES)
        data = self.ok("activity", "void", "manual:2026-10-08-run-1", "--reason", "duplicate")
        after = self.lines(ACTIVITIES)
        self.assertEqual(after[:-1], before)
        self.assertEqual(after[-1]["op"], "void")
        self.assertEqual(after[-1]["reason"], "duplicate")
        self.assertEqual(after[-1]["by"], "athlete")
        self.assertEqual(data["void"], after[-1])
        found = self.ok("activity", "list", "--from", "2026-10-05", "--to", "2026-10-11")["activities"]
        self.assertNotIn("manual:2026-10-08-run-1", [a["id"] for a in found])
        self.assertEqual(self.ok("activity", "show", "manual:2026-10-08-run-1")["voided"], True)

    def test_void_of_an_unknown_or_void_record_exits_1(self):
        self.cli("activity", "void", "manual:nope", "--reason", "x", expect=1)
        self.ok("activity", "void", "manual:2026-10-08-run-1", "--reason", "duplicate")
        self.cli("activity", "void", "manual:2026-10-08-run-1", "--reason", "again", expect=1)
        self.cli("activity", "void", "manual:2026-10-10-conditioning-1", "--reason", " ", expect=1)


class WellnessTest(ActivityCase):
    def test_daily_beats_span_in_the_summary(self):
        self.ok("wellness", "add", "--date", "2026-10-10", "--sleep-hours", "6.5")
        self.ok("wellness", "add", "--from", "2026-10-05", "--to", "2026-10-11", "--sleep-hours", "7")
        data = self.ok("wellness", "summary", "--from", "2026-10-05", "--to", "2026-10-11")
        nights = {night["date"]: (night["asleep_hours"], night["source"]) for night in data["nights"]}
        self.assertEqual(nights["2026-10-10"], (6.5, "manual"))
        fixture = {"2026-10-05": 6.9, "2026-10-06": 7.2, "2026-10-07": 6.4, "2026-10-08": 7.5, "2026-10-09": 6.8}
        for day, hours in fixture.items():
            self.assertEqual(nights[day], (hours, "apple_health"), day)
        self.assertNotIn("2026-10-11", nights)
        self.assertEqual(data["sleep"]["missing_dates"], ["2026-10-11"])
        self.assertEqual(data["sleep"]["nights"], 6)
        self.assertEqual(data["sleep"]["nights_in_span"], 7)
        self.assertEqual(data["sleep"]["avg_asleep_hours"], 6.88)

    def test_adding_again_updates_the_same_record_and_keeps_other_fields(self):
        self.ok("wellness", "add", "--date", "2026-10-12", "--sleep-hours", "6.5")
        record = self.ok("wellness", "add", "--date", "2026-10-12", "--resting-hr", "51")["record"]
        self.assertEqual(record["id"], "manual:2026-10-12-wellness")
        self.assertEqual(record["sleep"]["asleep_hours"], 6.5)
        self.assertEqual(record["resting_hr_bpm"], 51)

    def test_body_mass_is_stored_in_kg(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('bodyweight_units = "kg"', 'bodyweight_units = "lb"'),
                        encoding="utf-8")
        record = self.ok("wellness", "add", "--date", "2026-10-12", "--body-mass", "180", "--dry-run")["record"]
        self.assertEqual(record["body_mass_kg"], 81.6466)

    def test_default_location_is_gitignored(self):
        self.ok("wellness", "add", "--date", "2026-10-12", "--sleep-hours", "7")
        self.assertEqual(self.lines(LOCAL_WELLNESS)[-1]["id"], "manual:2026-10-12-wellness")
        self.assertFalse((self.root / GIT_WELLNESS).exists())
        with tempfile.TemporaryDirectory() as repo:
            repo = Path(repo)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            shutil.copy(REPO_ROOT / ".gitignore", repo / ".gitignore")
            (repo / LOCAL_WELLNESS).parent.mkdir(parents=True)
            shutil.copy(self.root / LOCAL_WELLNESS, repo / LOCAL_WELLNESS)
            ignored = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", LOCAL_WELLNESS])
            self.assertEqual(ignored.returncode, 0)

    def test_in_git_location(self):
        self.set_config("wellness_in_git = true\n")
        (self.root / LOCAL_WELLNESS).unlink()
        self.ok("wellness", "add", "--date", "2026-10-12", "--sleep-hours", "7")
        self.assertEqual(len(self.lines(GIT_WELLNESS)), 1)
        self.assertFalse((self.root / LOCAL_WELLNESS).exists())

    def test_void(self):
        self.ok("wellness", "void", "manual:2026-10-05..2026-10-11-wellness", "--reason", "wrong week")
        days = self.ok("wellness", "list", "--from", "2026-10-11", "--to", "2026-10-11")["days"]
        self.assertEqual(days, [])

    def test_needs_a_day_and_a_reading(self):
        self.cli("wellness", "add", "--sleep-hours", "7", expect=1)
        self.cli("wellness", "add", "--date", "2026-10-12", expect=1)
        self.cli("wellness", "add", "--date", "2026-10-12", "--from", "2026-10-12", "--sleep-hours", "7", expect=1)


class PlannedTest(ActivityCase):
    def test_add_then_list(self):
        self.ok("planned", "void", "manual:2026-10-16-run-1", "--reason", "replaced")
        record = self.ok("planned", "add", "--date", "2026-10-16", "--kind", "run", "--title", "Intervals",
                         "--quality")["record"]
        self.assertEqual(record["id"], "manual:2026-10-16-run-2")
        found = self.ok("planned", "list", "--from", "2026-10-12", "--to", "2026-10-18")["planned"]
        self.assertEqual([(p["id"], p["title"], p["quality"]) for p in found],
                         [("manual:2026-10-14-run-1", "Easy 5 km", False),
                          ("manual:2026-10-16-run-2", "Intervals", True)])
        self.assertNotIn("content_hash", found[0])


class DryRunTest(ActivityCase):
    WRITING = {
        "activity add": ("activity", "add", "--kind", "run", "--start", NOW, "--duration-min", "20"),
        "activity void": ("activity", "void", "manual:2026-10-08-run-1", "--reason", "duplicate"),
        "activity sync": ("activity", "sync"),
        "activity import": ("activity", "import", "--source", "apple_health",
                            "--file", str(FIXTURES / "apple_health" / "v2-week.json")),
        "activity anonymise": ("activity", "anonymise", "--source", "apple_health",
                               "--file", str(FIXTURES / "apple_health" / "v2-week.json"),
                               "--out", "/nonexistent/coach-anonymise-dry-run"),
        "wellness add": ("wellness", "add", "--date", "2026-10-12", "--sleep-hours", "7"),
        "wellness void": ("wellness", "void", "manual:2026-10-05..2026-10-11-wellness", "--reason", "x"),
        "planned add": ("planned", "add", "--date", "2026-10-20", "--kind", "run", "--title", "Long run"),
        "planned void": ("planned", "void", "manual:2026-10-14-run-1", "--reason", "x"),
    }

    def test_every_writing_command_is_covered(self):
        writing = {c.name for c in commands.discover()
                   if c.accepts_dry_run and c.name.split()[0] in ("activity", "wellness", "planned")}
        self.assertEqual(writing, set(self.WRITING))

    def test_dry_run_writes_nothing(self):
        before = snapshot(self.root)
        for name, argv in self.WRITING.items():
            with self.subTest(command=name):
                self.ok(*argv, "--dry-run")
                self.assertEqual(snapshot(self.root), before)


class DisabledTest(ActivityCase):
    def test_commands_exit_5_naming_the_key(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("[activity]\nenabled = true", "[activity]\nenabled = false"),
                        encoding="utf-8")
        for argv in (("activity", "list"), ("activity", "status"), ("activity", "sync"), ("wellness", "summary"),
                     ("activity", "import", "--source", "apple_health", "--file", "export.json"),
                     ("activity", "anonymise", "--source", "apple_health", "--file", "export.json", "--out", "out"),
                     ("planned", "list"), ("planned", "add", "--date", "2026-10-20", "--kind", "run", "--title", "x")):
            with self.subTest(argv=argv):
                envelope = self.cli(*argv, expect=5)
                self.assertIn("[activity] enabled", envelope["error"]["message"])
        results = self.ok("check", "--only", "activity_records_valid,activity_wellness_location,activity_source_fresh")
        self.assertEqual({row["status"] for row in results["results"]}, {"skip"})


class ChecksTest(ActivityCase):
    def check(self, check_id, root=None, expect=0):
        envelope = self.cli("check", "--only", check_id, root=root, expect=expect)
        return envelope["data"]["results"]

    def test_valid_fixture_passes_every_activity_check(self):
        for check_id in ("activity_records_valid", "activity_wellness_location", "activity_source_fresh"):
            with self.subTest(check=check_id):
                self.assertEqual({r["status"] for r in self.check(check_id, root=VALID)}, {"pass"})

    def test_misplaced_wellness_file_fails_and_names_the_move(self):
        results = self.check("activity_wellness_location", root=INSTANCES / "activity-wellness-misplaced", expect=1)
        self.assertEqual(results[0]["status"], "fail")
        message = results[0]["message"]
        self.assertIn("git rm --cached --quiet --ignore-unmatch data/activity/wellness.jsonl", message)
        self.assertIn("mv data/activity/wellness.jsonl .coach/activity/wellness.jsonl", message)

    def test_moving_into_git_names_a_plain_move(self):
        self.set_config("wellness_in_git = true\n")
        results = self.check("activity_wellness_location", expect=1)
        self.assertIn("mkdir -p data/activity && mv .coach/activity/wellness.jsonl data/activity/wellness.jsonl",
                      results[0]["message"])
        self.assertNotIn("git rm", results[0]["message"])

    def test_unknown_field_names_file_line_and_jsonpath(self):
        results = self.check("activity_records_valid", root=INSTANCES / "activity-bad-record", expect=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "fail")
        self.assertEqual(results[0]["path"], ACTIVITIES)
        self.assertIn("data/activity/activities.jsonl line 2", results[0]["message"])
        self.assertIn("$.heart_zone", results[0]["message"])

    def test_source_freshness_warns_past_gap_warn_days(self):
        later = {"COACH_NOW": "2026-10-15T18:00:00Z"}
        results = self.cli("check", "--only", "activity_source_fresh", env=later)["data"]["results"]
        self.assertEqual(results[0]["status"], "warn")
        self.assertIn("hevy_conditioning", results[0]["message"])
        self.assertIn("4 days ago", results[0]["message"])


class StatusTest(ActivityCase):
    def test_lists_each_enabled_source(self):
        rows = {row["source"]: row for row in self.ok("activity", "status")["sources"]}
        self.assertEqual(sorted(rows), ["hevy_conditioning", "manual"])
        hevy = rows["hevy_conditioning"]
        self.assertEqual(hevy["last_sync_at"], "2026-10-11T12:00:00Z")
        self.assertEqual(hevy["counts"], {"activity": 1})
        self.assertEqual(hevy["newest_date"], "2026-10-10")
        self.assertIsNone(hevy["missing_days"])
        manual = rows["manual"]
        self.assertIsNone(manual["last_sync_at"])
        self.assertEqual(manual["counts"], {"activity": 2, "wellness": 1, "planned": 2})
        self.assertEqual(manual["newest_date"], "2026-10-11")
        self.assertEqual(len(manual["missing_days"]), 7)
        self.assertEqual(manual["missing_days"][0], "2026-09-28")


class ConfigValidateTest(ActivityCase):
    def test_exits_5_naming_the_key(self):
        cases = {
            'precedence = ["manual"]\n': "hevy_conditioning",
            'precedence = ["manual", "hevy_conditioning", "manual"]\n': "[activity] precedence",
        }
        original = (self.root / "config.toml").read_text(encoding="utf-8")
        for extra, named in cases.items():
            with self.subTest(extra=extra):
                (self.root / "config.toml").write_text(original, encoding="utf-8")
                self.set_config(extra)
                envelope = self.cli("config", "validate", expect=5)
                self.assertIn(named, envelope["error"]["message"])
        (self.root / "config.toml").write_text(original + "\n[sources.hevy_conditioning]\nfolder = 1\n",
                                               encoding="utf-8")
        envelope = self.cli("config", "validate", expect=5)
        self.assertIn('unknown key "folder" in [sources.hevy_conditioning]', envelope["error"]["message"])


if __name__ == "__main__":
    unittest.main()
