import json
import shutil
import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path

from coach import config as config_module
from coach.activity import records
from coach.activity.store import ActivityStore
from coach.dates import Span
from tests.support import VALID

WEEK = Span(date(2026, 10, 5), date(2026, 10, 11))
NOW = "2026-10-11T18:00:00Z"
HEVY_C1 = "hevy_conditioning:00000000-0000-4000-8000-0000000000c1"


def activity(record_id, kind, start, minutes=30, **fields):
    source = record_id.split(":")[0]
    record = {"id": record_id, "source": source, "source_id": None, "kind": kind, "name": None, "indoor": None,
              "start": start, "end": None, "utc_offset": None, "local_date": start[:10],
              "duration_seconds": minutes * 60, "distance_meters": None, "elevation_gain_meters": None,
              "avg_hr": None, "max_hr": None, "active_kcal": None, "rpe": None, "device": None, "notes": None}
    record.update(fields)
    return records.upsert_line(record, NOW, "activity")


def wellness(record_id, start, end=None, asleep=None, **fields):
    source = record_id.split(":")[0]
    record = {"id": record_id, "source": source, "span": {"start": start, "end": end or start},
              "sleep": None if asleep is None else {"asleep_hours": asleep, "in_bed_hours": None,
                                                    "start": None, "end": None},
              "resting_hr_bpm": None, "hrv_ms": None, "steps": None, "body_mass_kg": None,
              "body_fat_pct": None, "device": None}
    record.update(fields)
    return records.upsert_line(record, NOW, "wellness")


class StoreCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(VALID, self.root, dirs_exist_ok=True)
        self.config_text = (self.root / "config.toml").read_text(encoding="utf-8")

    def store(self, extra=""):
        text = self.config_text.replace("[activity]\n", "[activity]\n" + extra, 1)
        return ActivityStore(self.root, config_module.parse(tomllib.loads(text), self.root / "config.toml"))

    def write(self, name, lines):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


class ValidFixtureTest(StoreCase):
    def test_week_holds_the_run_and_one_merged_conditioning_activity(self):
        found = self.store().activities(WEEK)
        self.assertEqual([(a["local_date"], a["kind"]) for a in found],
                         [("2026-10-08", "run"), ("2026-10-10", "conditioning")])
        run, conditioning = found
        self.assertEqual(run["id"], "manual:2026-10-08-run-1")
        self.assertEqual(run["distance_meters"], 5000)
        self.assertEqual(conditioning["id"], "manual:2026-10-10-conditioning-1")
        self.assertEqual(conditioning["merged_from"], ["manual:2026-10-10-conditioning-1", HEVY_C1])
        self.assertEqual(conditioning["field_sources"]["rpe"], "manual")
        self.assertNotIn("content_hash", conditioning)

    def test_reversed_precedence_lets_hevy_win_and_manual_fill_rpe(self):
        store = self.store('precedence = ["hevy_conditioning", "manual"]\n')
        conditioning = store.activities(WEEK, kinds=["conditioning"])[0]
        self.assertEqual(conditioning["id"], HEVY_C1)
        self.assertEqual(conditioning["merged_from"], [HEVY_C1, "manual:2026-10-10-conditioning-1"])
        self.assertEqual(conditioning["source"], "hevy_conditioning")
        self.assertEqual(conditioning["start"], "2026-10-10T09:06:00Z")
        self.assertEqual(conditioning["field_sources"]["start"], "hevy_conditioning")
        self.assertEqual(conditioning["rpe"], 7)
        self.assertEqual(conditioning["field_sources"]["rpe"], "manual")

    def test_kinds_filter(self):
        self.assertEqual([a["kind"] for a in self.store().activities(WEEK, kinds=["run"])], ["run"])

    def test_planned_returns_both_fixture_records(self):
        planned = self.store().planned(Span(date(2026, 10, 12), date(2026, 10, 18)))
        self.assertEqual([(p["id"], p["quality"]) for p in planned],
                         [("manual:2026-10-14-run-1", False), ("manual:2026-10-16-run-1", True)])

    def test_wellness_daily_beats_span(self):
        days = self.store().wellness_days(WEEK)
        self.assertEqual(len(days), 7)
        by_date = {d["date"]: d for d in days}
        self.assertEqual(by_date["2026-10-11"]["sleep"]["asleep_hours"], 7.0)
        self.assertEqual(by_date["2026-10-11"]["field_sources"]["sleep"], "manual")
        self.assertEqual(by_date["2026-10-09"]["field_sources"]["sleep"], "apple_health")

    def test_sleep_summary(self):
        summary = self.store().sleep_summary(WEEK)
        self.assertEqual(summary["nights"], 6)
        self.assertEqual(summary["nights_in_span"], 7)
        self.assertEqual(summary["sources"], ["apple_health", "manual"])
        self.assertIsInstance(summary["avg_asleep_hours"], float)

    def test_sleep_summary_with_no_values(self):
        summary = self.store().sleep_summary(Span(date(2026, 9, 1), date(2026, 9, 3)))
        self.assertIsNone(summary["avg_asleep_hours"])
        self.assertEqual(summary["nights"], 0)
        self.assertEqual(summary["nights_in_span"], 3)
        self.assertEqual(summary["sources"], [])
        self.assertEqual(len(summary["missing_dates"]), 3)
        self.assertFalse(summary["complete"])


class DedupTest(StoreCase):
    def setUp(self):
        super().setUp()
        (self.root / "data" / "activity" / "activities.jsonl").unlink()

    def test_different_kinds_two_minutes_apart_stay_separate(self):
        self.write("data/activity/activities.jsonl", [
            activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z"),
            activity("hevy_conditioning:w1", "conditioning", "2026-10-06T07:02:00Z"),
        ])
        self.assertEqual(len(self.store().activities(WEEK)), 2)

    def test_same_kind_sixteen_minutes_apart_stay_separate(self):
        self.write("data/activity/activities.jsonl", [
            activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z"),
            activity("apple_health:a1", "run", "2026-10-06T07:16:00Z"),
        ])
        self.assertEqual(len(self.store().activities(WEEK)), 2)

    def test_same_kind_fifteen_minutes_apart_merge(self):
        self.write("data/activity/activities.jsonl", [
            activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z"),
            activity("apple_health:a1", "run", "2026-10-06T07:15:00Z", avg_hr=150),
        ])
        merged = self.store().activities(WEEK)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["avg_hr"], 150)
        self.assertEqual(merged[0]["field_sources"]["avg_hr"], "apple_health")

    def test_one_source_never_merges_with_itself(self):
        self.write("data/activity/activities.jsonl", [
            activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z"),
            activity("manual:2026-10-06-run-2", "run", "2026-10-06T07:05:00Z"),
        ])
        self.assertEqual(len(self.store().activities(WEEK)), 2)

    def test_last_line_wins_and_void_removes(self):
        first = activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z")
        second = activity("manual:2026-10-06-run-1", "run", "2026-10-06T07:00:00Z", rpe=5)
        void = records.void_line("manual:2026-10-06-run-2", "manual", "duplicate", "athlete", NOW)
        self.write("data/activity/activities.jsonl", [
            first, second, activity("manual:2026-10-06-run-2", "run", "2026-10-06T18:00:00Z"), void])
        store = self.store()
        self.assertEqual([a["rpe"] for a in store.activities(WEEK)], [5])
        self.assertEqual(len(store.records("activity")), 1)
        self.assertEqual([r["op"] for r in store.records("activity", include_void=True)], ["upsert", "void"])
        self.assertEqual(len(store.lines("activity")), 4)


class BodyMassTest(StoreCase):
    def body_masses(self, *lines):
        self.write(".coach/activity/wellness.jsonl", lines)
        return [(m["date"], m["body_mass_kg"], m["provenance"]["id"]) for m in self.store().body_masses()]

    def test_a_span_counts_once_on_its_end_date(self):
        self.assertEqual(self.body_masses(wellness("manual:week", "2026-09-28", "2026-10-04", body_mass_kg=70.0)),
                         [("2026-10-04", 70.0, "manual:week")])

    def test_a_days_own_record_outranks_a_span_ending_that_day_whatever_the_source(self):
        found = self.body_masses(
            wellness("manual:week", "2026-09-28", "2026-10-04", body_mass_kg=70.0),
            wellness("apple_health:day", "2026-10-04", body_mass_kg=71.0))
        self.assertEqual(found, [("2026-10-04", 71.0, "apple_health:day")])

    def test_records_without_a_body_mass_are_ignored(self):
        self.assertEqual(self.body_masses(wellness("manual:sleep", "2026-10-04", asleep=7.0)), [])


class WellnessLocationTest(StoreCase):
    def test_default_location_is_the_local_cache(self):
        self.assertEqual(self.store().path("wellness"), self.root / ".coach" / "activity" / "wellness.jsonl")

    def test_in_git_location(self):
        store = self.store("wellness_in_git = true\n")
        self.assertEqual(store.path("wellness"), self.root / "data" / "activity" / "wellness.jsonl")


if __name__ == "__main__":
    unittest.main()
