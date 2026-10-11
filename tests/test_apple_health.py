import json
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from coach import units
from coach.activity import health_auto_export
from coach.activity.adapters import apple_health
from tests.support import FIXTURES
from tests.support.activity import write_hevy_cache
from tests.test_activity_commands import ACTIVITIES, LOCAL_WELLNESS, ActivityCase, snapshot

HAE = FIXTURES / "apple_health"
WEEK = HAE / "v2-week.json"
NO_SOURCE = HAE / "v2-no-source.json"
V1 = HAE / "v1.json"
TO_ANONYMISE = HAE / "export-to-anonymise.json"
SYNC = "data/activity/sync.json"
RUN_ID = "apple_health:5A1C0001-0000-4000-8000-000000000001"
WEEK_SPAN = ("--from", "2026-09-21", "--to", "2026-09-27")


class AppleHealthCase(ActivityCase):
    def import_file(self, path, *extra, expect=0, **kwargs):
        envelope = self.cli("activity", "import", "--source", "apple_health", "--file", str(path), *extra,
                            expect=expect, **kwargs)
        return envelope

    def apple_lines(self, relative):
        return [line for line in self.lines(relative) if line["source"] == "apple_health"]

    def write_export(self, name, doc):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path


class ImportTest(AppleHealthCase):
    def test_dry_run_reports_records_and_drops_and_writes_nothing(self):
        before = snapshot(self.root)
        envelope = self.import_file(WEEK, "--dry-run")
        data = envelope["data"]
        self.assertEqual(data["records"], {"activity": 1, "wellness": 7})
        self.assertEqual(data["dropped"], {
            "lifting workout; Hevy is the lifting logbook": 1,
            "written to Apple Health by Hevy, which is in drop_source_names": 1,
        })
        self.assertFalse(data["already_seen"])
        self.assertTrue(data["dry_run"])
        self.assertIn("apple_health: dropped 1 item(s): lifting workout; Hevy is the lifting logbook",
                      envelope["warnings"])
        self.assertEqual(snapshot(self.root), before)

    def test_import_writes_records_in_metres_and_kilograms(self):
        self.import_file(WEEK)
        runs = self.apple_lines(ACTIVITIES)
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertEqual(run["id"], RUN_ID)
        self.assertEqual(run["distance_meters"], units.to_meters(3.1, "mi"))
        self.assertEqual(run["kind"], "run")
        self.assertEqual(run["start"], "2026-09-23T06:00:00Z")
        self.assertEqual(run["utc_offset"], "+01:00")
        self.assertEqual(run["local_date"], "2026-09-23")
        self.assertEqual(run["duration_seconds"], 1920)
        self.assertEqual((run["avg_hr"], run["max_hr"], run["active_kcal"]), (148, 171, 352))
        self.assertEqual(run["elevation_gain_meters"], units.to_meters(98, "ft"))
        self.assertIs(run["indoor"], False)

        days = self.ok("wellness", "list", *WEEK_SPAN)["days"]
        self.assertEqual(len(days), 7)
        first = days[0]
        self.assertEqual(first["date"], "2026-09-21")
        self.assertEqual(first["body_mass_kg"], units.mass_kg(176.4, "lb"))
        self.assertEqual(first["sleep"], {"asleep_hours": 7.1, "in_bed_hours": 7.6,
                                          "start": "2026-09-20T22:10:00Z", "end": "2026-09-21T05:40:00Z"})
        self.assertEqual((first["resting_hr_bpm"], first["steps"]), (54, 8120))
        self.assertIsNone(days[1]["body_mass_kg"])
        self.assertEqual(first["field_sources"]["sleep"], "apple_health")
        september = [line for line in self.apple_lines(LOCAL_WELLNESS) if line["span"]["start"] < "2026-10-01"]
        self.assertEqual(len(september), 7)

    def test_second_import_appends_nothing_and_reports_the_file_seen(self):
        self.import_file(WEEK)
        before = snapshot(self.root)
        data = self.import_file(WEEK)["data"]
        self.assertTrue(data["already_seen"])
        self.assertEqual(data["appended"], 0)
        self.assertEqual(snapshot(self.root), before)
        sync_map = json.loads((self.root / SYNC).read_text(encoding="utf-8"))
        files = sync_map["sources"]["apple_health"]["state"]["files"]
        self.assertEqual(list(files), ["v2-week.json"])
        self.assertRegex(files["v2-week.json"], r"^sha256:[0-9a-f]{64}$")

    def test_import_does_not_need_the_folder_source_enabled(self):
        self.assertFalse(self.root.joinpath("config.toml").read_text(encoding="utf-8").count("[sources.apple_health]"))
        self.import_file(WEEK)

    def test_version_1_is_refused_naming_the_setting(self):
        envelope = self.import_file(V1, expect=1)
        self.assertIn("Export Version 2", envelope["error"]["message"])

    def test_csv_is_refused_naming_the_setting(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "HealthAutoExport.csv"
        path.write_text("Date,Step Count (count)\n2026-09-21,8120\n", encoding="utf-8")
        envelope = self.import_file(path, expect=1)
        self.assertIn("Export Format", envelope["error"]["message"])
        self.assertIn("JSON", envelope["error"]["message"])

    def test_unknown_metrics_are_ignored_with_one_summary_warning(self):
        doc = json.loads(WEEK.read_text(encoding="utf-8"))
        doc["data"]["metrics"] += [
            {"name": "dietary_water", "units": "mL", "data": [{"date": "2026-09-21 00:00:00 +0100", "qty": 2000}]},
            {"name": "mindful_minutes", "units": "min", "data": [{"date": "2026-09-21 00:00:00 +0100", "qty": 10}]},
        ]
        envelope = self.import_file(self.write_export("extra.json", doc))
        unknown = [w for w in envelope["warnings"] if "metric" in w and "ignored" in w]
        self.assertEqual(len(unknown), 1, envelope["warnings"])
        self.assertIn("dietary_water", unknown[0])
        self.assertIn("mindful_minutes", unknown[0])
        self.assertEqual(envelope["data"]["records"]["wellness"], 7)

    def test_a_later_file_with_fewer_metrics_keeps_the_other_readings(self):
        self.import_file(WEEK)
        doc = {"data": {"metrics": [{"name": "step_count", "units": "count",
                                     "data": [{"date": "2026-09-21 00:00:00 +0100", "qty": 9999}]}]}}
        self.import_file(self.write_export("steps-only.json", doc))
        day = self.ok("wellness", "list", "--from", "2026-09-21", "--to", "2026-09-21")["days"][0]
        self.assertEqual(day["steps"], 9999)
        self.assertEqual(day["sleep"]["asleep_hours"], 7.1)
        self.assertEqual(day["resting_hr_bpm"], 54)

    def test_dedup_with_a_manual_run(self):
        self.ok("activity", "add", "--kind", "run", "--start", "2026-09-23T07:04:00+01:00", "--duration-min", "30",
                "--distance-km", "5", "--rpe", "6")
        self.import_file(WEEK)
        found = self.ok("activity", "list", "--from", "2026-09-23", "--to", "2026-09-23")["activities"]
        self.assertEqual(len(found), 1)
        activity = found[0]
        self.assertEqual(sorted(activity["merged_from"]), sorted(["manual:2026-09-23-run-1", RUN_ID]))
        self.assertEqual((activity["avg_hr"], activity["field_sources"]["avg_hr"]), (148, "apple_health"))
        self.assertEqual((activity["rpe"], activity["field_sources"]["rpe"]), (6, "manual"))

    def test_unknown_or_unsupported_source(self):
        self.cli("activity", "import", "--source", "strava", "--file", str(WEEK), expect=2)
        self.cli("activity", "import", "--source", "hevy_conditioning", "--file", str(WEEK), expect=2)


class HevyOverlapTest(AppleHealthCase):
    def test_a_sourceless_workout_near_a_hevy_workout_is_dropped(self):
        write_hevy_cache(self.root, FIXTURES / "hevy" / "conditioning")
        data = self.import_file(NO_SOURCE)["data"]
        self.assertEqual(data["dropped"], {"no source, and it starts within 15 minutes of a Hevy workout": 1})
        ids = [line["id"] for line in self.apple_lines(ACTIVITIES)]
        self.assertEqual(ids, ["apple_health:5A1C0002-0000-4000-8000-000000000002"])

    def test_the_window_follows_dedup_window_minutes(self):
        write_hevy_cache(self.root, FIXTURES / "hevy" / "conditioning")
        self.set_config("dedup_window_minutes = 4\n")
        data = self.import_file(NO_SOURCE)["data"]
        self.assertEqual(data["dropped"], {})
        self.assertEqual(data["records"], {"activity": 2})

    def test_without_hevy_in_drop_source_names_nothing_is_dropped_by_time(self):
        write_hevy_cache(self.root, FIXTURES / "hevy" / "conditioning")
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + "\n[sources.apple_health]\ndrop_source_names = []\n",
                        encoding="utf-8")
        data = self.import_file(NO_SOURCE)["data"]
        self.assertEqual(data["dropped"], {})


class FolderSyncTest(AppleHealthCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name) / "AutoExport"
        shutil.copytree(HAE / "folder", self.folder)
        self.enable(self.folder)

    def enable(self, folder):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8")
                        + f'\n[sources.apple_health]\nenabled = true\npath = "{folder.as_posix()}"\n',
                        encoding="utf-8")

    def sync(self, **kwargs):
        envelope = self.cli("activity", "sync", "--source", "apple_health", **kwargs)
        return envelope["data"]["sources"][0], envelope["warnings"]

    def test_reads_the_downloaded_file_and_warns_about_the_placeholder(self):
        row, warnings = self.sync()
        self.assertTrue(row["ok"], row)
        self.assertEqual(row["files_read"], ["HealthAutoExport-2026-09-28.json"])
        self.assertEqual(row["records"], {"wellness": 1})
        placeholder = [w for w in warnings if "brctl download" in w]
        self.assertEqual(len(placeholder), 1, warnings)
        self.assertIn("HealthAutoExport-2026-09-29.json", placeholder[0])
        files = json.loads((self.root / SYNC).read_text(encoding="utf-8"))["sources"]["apple_health"]["state"]["files"]
        self.assertEqual(list(files), ["HealthAutoExport-2026-09-28.json"])
        day = self.ok("wellness", "list", "--from", "2026-09-28", "--to", "2026-09-28")["days"][0]
        self.assertEqual(day["sleep"]["asleep_hours"], 7.4)

    def test_a_second_sync_skips_files_already_read_and_never_copies_them(self):
        self.sync()
        before = snapshot(self.root)
        row, _ = self.sync()
        self.assertEqual(row["files_read"], [])
        self.assertEqual(row["appended"], 0)
        after = snapshot(self.root)
        after.pop(SYNC)
        before.pop(SYNC)
        self.assertEqual(after, before)
        self.assertFalse([p for p in self.root.rglob("HealthAutoExport*")])

    def test_a_changed_file_is_read_again(self):
        self.sync()
        path = self.folder / "HealthAutoExport-2026-09-28.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["data"]["metrics"][2]["data"][0]["qty"] = 12000
        path.write_text(json.dumps(doc), encoding="utf-8")
        row, _ = self.sync()
        self.assertEqual(row["appended"], 1)
        day = self.ok("wellness", "list", "--from", "2026-09-28", "--to", "2026-09-28")["days"][0]
        self.assertEqual(day["steps"], 12000)

    def test_version_1_and_csv_files_in_the_folder_are_skipped_with_warnings(self):
        shutil.copy(V1, self.folder / "HealthAutoExport-old.json")
        (self.folder / "HealthAutoExport.csv").write_text("Date,Step Count (count)\n", encoding="utf-8")
        row, warnings = self.sync()
        self.assertTrue(row["ok"])
        self.assertEqual(row["files_read"], ["HealthAutoExport-2026-09-28.json"])
        self.assertTrue(any("Export Version 2" in w for w in warnings), warnings)
        self.assertTrue(any("Export Format" in w and "HealthAutoExport.csv" in w for w in warnings), warnings)

    def test_a_missing_folder_fails_the_source(self):
        shutil.rmtree(self.folder)
        row, warnings = self.sync()
        self.assertFalse(row["ok"])
        self.assertIn("[sources.apple_health] path", row["error"])

    def test_precedence_must_list_apple_health_once_enabled(self):
        self.set_config('precedence = ["manual", "hevy_conditioning"]\n')
        self.cli("config", "validate", expect=5)

    def test_never_calls_the_network(self):
        self.assertFalse(apple_health.NETWORK)
        self.assertEqual(apple_health.KINDS, ("activity", "wellness"))


class AnonymiseTest(AppleHealthCase):
    def anonymise(self, *extra, expect=0):
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        envelope = self.cli("activity", "anonymise", "--source", "apple_health", "--file", str(TO_ANONYMISE),
                            "--out", out.name, *extra, expect=expect)
        return envelope, Path(out.name)

    def test_output_hides_ids_timestamps_and_device_names_and_still_imports(self):
        envelope, out = self.anonymise()
        written = Path(envelope["data"]["path"])
        self.assertEqual(written.parent, out)
        text = written.read_text(encoding="utf-8")
        original = TO_ANONYMISE.read_text(encoding="utf-8")
        source = json.loads(original)

        for workout_id in [w["id"] for w in source["data"]["workouts"]]:
            self.assertNotIn(workout_id, text)
        for stamp in set(re.findall(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2} [+-]\d{4})?", original)):
            self.assertNotIn(stamp, text)
        self.assertNotIn("Sample Person", text)
        self.assertNotIn("Sample Town", text)
        self.assertIn('"Hevy"', text)
        self.assertIn("Device 1", text)

        doc = json.loads(text)
        self.assertIs(doc["x-anonymised"], True)
        self.assertEqual(sorted(doc["data"]), ["metrics", "workouts"])
        run = doc["data"]["workouts"][0]
        self.assertNotIn("route", run)
        self.assertNotIn("metadata", run)
        self.assertEqual(run["distance"]["units"], "km")
        self.assertNotEqual(run["distance"]["qty"], 5.0)
        self.assertAlmostEqual(run["distance"]["qty"], 5.0, delta=0.25)

        before = datetime.strptime(source["data"]["workouts"][0]["start"], "%Y-%m-%d %H:%M:%S %z")
        after = datetime.strptime(run["start"], "%Y-%m-%d %H:%M:%S %z")
        self.assertEqual(after.weekday(), before.weekday())
        self.assertEqual((before - after).days % 7, 0)
        self.assertEqual(after.utcoffset(), before.utcoffset())
        sleep_day = date.fromisoformat(doc["data"]["metrics"][0]["data"][0]["date"])
        self.assertEqual(sleep_day.weekday(), date(2026, 9, 21).weekday())

        data = self.import_file(written)["data"]
        self.assertEqual(data["records"], {"activity": 1, "wellness": 7})
        self.assertEqual(data["dropped"], {"written to Apple Health by Hevy, which is in drop_source_names": 1})

    def test_ids_are_deterministic_within_a_run(self):
        doc = json.loads(TO_ANONYMISE.read_text(encoding="utf-8"))
        doc["data"]["workouts"].append(dict(doc["data"]["workouts"][0]))
        path = self.write_export("twice.json", doc)
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        report = health_auto_export.anonymise(path, Path(out.name))
        written = json.loads(Path(report["path"]).read_text(encoding="utf-8"))["data"]["workouts"]
        self.assertEqual(written[0]["id"], written[2]["id"])
        self.assertNotEqual(written[0]["id"], written[1]["id"])

    def test_dry_run_writes_nothing(self):
        _, out = self.anonymise("--dry-run")
        self.assertEqual(list(out.iterdir()), [])

    def test_refuses_version_1_and_unsupported_sources(self):
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        self.cli("activity", "anonymise", "--source", "apple_health", "--file", str(V1), "--out", out.name, expect=1)
        self.cli("activity", "anonymise", "--source", "manual", "--file", str(V1), "--out", out.name, expect=2)


class MappingTest(unittest.TestCase):
    def test_workout_names_to_kinds(self):
        cases = {"Outdoor Run": "run", "Running": "run", "Indoor Cycling": "ride", "Pool Swim": "swim",
                 "Rowing": "row", "Outdoor Walk": "walk", "Hiking": "hike",
                 "High Intensity Interval Training": "conditioning", "Yoga": "mobility", "Soccer": "sport",
                 "Traditional Strength Training": "lifting", "Functional Strength Training": "lifting",
                 "Dance": "other"}
        for name, kind in cases.items():
            with self.subTest(name=name):
                self.assertEqual(apple_health.workout_kind(name), kind)

    def test_sleep_belongs_to_the_day_the_athlete_woke(self):
        self.assertEqual(apple_health.sleep_day({"date": "2026-09-21", "sleepEnd": "2026-09-22 06:30:00 +0100"}),
                         "2026-09-22")
        self.assertEqual(apple_health.sleep_day({"date": "2026-09-21 00:00:00 +0100"}), "2026-09-21")

    def test_one_table_holds_every_uncertain_mapping(self):
        self.assertEqual(sorted(apple_health.MAPPING), ["indoor_locations", "metrics", "sleep", "workout_kinds"])


if __name__ == "__main__":
    unittest.main()
