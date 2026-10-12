import importlib
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from coach.activity import adapters, sync
from coach.activity.adapters import hevy_conditioning
from tests.support import FIXTURES
from tests.support.activity import map_routines, write_hevy_cache
from tests.test_activity_commands import ACTIVITIES, ActivityCase

CONDITIONING = FIXTURES / "hevy" / "conditioning"
SYNC = "data/activity/sync.json"


def workout_id(n):
    return f"00000000-0000-4000-8000-0000000000{n}"


def hevy_id(n):
    return f"hevy_conditioning:{workout_id(n)}"


class SyncCase(ActivityCase):
    def setUp(self):
        super().setUp()
        self.cache = write_hevy_cache(self.root, CONDITIONING)

    def sync(self, *extra, **kwargs):
        envelope = self.cli("activity", "sync", *extra, **kwargs)
        return envelope["data"]["sources"], envelope["warnings"]

    def hevy_lines(self):
        return [line for line in self.lines(ACTIVITIES) if line["source"] == "hevy_conditioning"]


class HevySyncTest(SyncCase):
    def test_second_sync_appends_nothing_then_edits_and_deletes_append_one_line_each(self):
        self.sync()
        first = self.lines(ACTIVITIES)
        report, _ = self.sync()
        self.assertEqual(self.lines(ACTIVITIES), first)
        self.assertEqual((report[0]["appended"], report[0]["voided"]), (0, 0))

        workout = self.cache.workout(workout_id("c1"))
        workout["end_time"] = "2026-10-10T09:40:00Z"
        self.cache.write_workout(workout, "2026-10-11T12:00:00Z")
        self.sync()
        after_edit = self.lines(ACTIVITIES)
        self.assertEqual(len(after_edit), len(first) + 1)
        self.assertEqual(after_edit[-1]["id"], hevy_id("c1"))
        self.assertEqual(after_edit[-1]["duration_seconds"], 2040)

        self.cache.remove_workout(workout_id("c1"))
        self.sync()
        after_delete = self.lines(ACTIVITIES)
        self.assertEqual(len(after_delete), len(after_edit) + 1)
        self.assertEqual(after_delete[-1]["op"], "void")
        self.assertEqual(after_delete[-1]["id"], hevy_id("c1"))
        self.assertEqual(after_delete[-1]["reason"], "deleted in Hevy")
        self.assertEqual(after_delete[-1]["by"], "sync")
        self.sync()
        self.assertEqual(self.lines(ACTIVITIES), after_delete)

    def test_the_fixture_record_matches_a_fresh_sync(self):
        self.sync()
        self.assertEqual(sorted(line["id"] for line in self.hevy_lines()),
                         [hevy_id("c1"), hevy_id("c5"), hevy_id("c6")])

    def test_mixed_lifting_and_conditioning_is_no_activity(self):
        _, warnings = self.sync()
        self.assertNotIn(hevy_id("c2"), [line["id"] for line in self.hevy_lines()])
        self.assertIn("hevy_conditioning: dropped 3 item(s): lifting workout; Hevy is the lifting logbook", warnings)

    def test_kinds_from_the_library_table_and_cardio_templates(self):
        self.sync()
        by_id = {line["id"]: line for line in self.hevy_lines()}
        self.assertEqual(by_id[hevy_id("c6")]["kind"], "run")
        self.assertEqual(by_id[hevy_id("c6")]["distance_meters"], 5000)
        self.assertEqual(by_id[hevy_id("c6")]["rpe"], 5)
        self.assertEqual(by_id[hevy_id("c5")]["kind"], "conditioning")
        self.assertEqual(by_id[hevy_id("c1")]["kind"], "conditioning")
        self.assertEqual(by_id[hevy_id("c1")]["distance_meters"], 2000)

    def test_routine_mapped_to_a_conditioning_session_is_an_activity(self):
        map_routines(self.root, {"00000000-0000-4000-8000-000000000003": "conditioning",
                                 "00000000-0000-4000-8000-000000000001": "lifting"})
        self.sync()
        by_id = {line["id"]: line for line in self.hevy_lines()}
        self.assertEqual(by_id[hevy_id("c3")]["kind"], "conditioning")
        self.assertEqual(by_id[hevy_id("c3")]["rpe"], 7)
        self.assertNotIn(hevy_id("c4"), by_id)

    def test_without_state_the_hinge_workout_is_no_activity(self):
        (self.root / "data" / "state.json").unlink()
        report, _ = self.sync()
        self.assertTrue(report[0]["ok"], report)
        self.assertNotIn(hevy_id("c3"), [line["id"] for line in self.hevy_lines()])

    def test_a_malformed_state_fails_the_source_and_voids_nothing(self):
        map_routines(self.root, {"00000000-0000-4000-8000-000000000003": "conditioning"})
        self.sync()
        before = self.lines(ACTIVITIES)
        state_path = self.root / "data" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["hevy"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        report, _ = self.sync()
        self.assertFalse(report[0]["ok"])
        self.assertIn("data/state.json is not a valid state document", report[0]["error"])
        self.assertEqual(self.lines(ACTIVITIES), before)

    def test_sync_map_records_state_and_holds_no_health_values(self):
        self.sync()
        doc = json.loads((self.root / SYNC).read_text(encoding="utf-8"))
        state = doc["sources"]["hevy_conditioning"]
        self.assertEqual(state["last_sync_at"], "2026-10-11T18:00:00Z")
        self.assertEqual(state["state"], {"seen_workout_ids": [workout_id("c1"), workout_id("c5"), workout_id("c6")]})

    def test_an_athlete_void_survives_a_sync_but_a_changed_workout_returns(self):
        self.sync()
        self.ok("activity", "void", hevy_id("c6"), "--reason", "logged twice")
        voided = self.lines(ACTIVITIES)
        self.sync()
        self.assertEqual(self.lines(ACTIVITIES), voided)
        workout = self.cache.workout(workout_id("c6"))
        workout["description"] = "easy, RPE 4"
        self.cache.write_workout(workout, "2026-10-11T12:00:00Z")
        self.sync()
        self.assertEqual(self.lines(ACTIVITIES)[-1]["rpe"], 4)

    def test_a_workout_back_in_the_cache_after_a_sync_void_returns(self):
        self.sync()
        saved = self.cache.workout(workout_id("c6"))
        self.cache.remove_workout(workout_id("c6"))
        self.sync()
        self.cache.write_workout(saved, "2026-10-11T12:00:00Z")
        self.sync()
        self.assertEqual(self.lines(ACTIVITIES)[-1]["op"], "upsert")
        self.assertEqual(self.lines(ACTIVITIES)[-1]["id"], hevy_id("c6"))

    def test_stale_cache_warns_and_no_cache_voids_nothing(self):
        _, warnings = self.sync(env={"COACH_NOW": "2026-10-13T18:00:00Z"})
        self.assertTrue(any("54 hours old" in w for w in warnings), warnings)
        shutil.rmtree(self.root / ".coach" / "cache")
        before = self.lines(ACTIVITIES)
        _, warnings = self.sync()
        self.assertEqual(self.lines(ACTIVITIES), before)
        self.assertTrue(any("no Hevy cache" in w for w in warnings), warnings)

    def test_unknown_or_disabled_source(self):
        self.cli("activity", "sync", "--source", "strava", expect=2)
        self.cli("activity", "sync", "--source", "manual", expect=2)
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + "\n[sources.hevy_conditioning]\nenabled = false\n",
                        encoding="utf-8")
        self.cli("activity", "sync", "--source", "hevy_conditioning", expect=5)

    def test_never_calls_the_network(self):
        self.assertFalse(hevy_conditioning.NETWORK)
        self.sync(env={"COACH_HEVY_FIXTURES": "/nonexistent"})


class ParseRpeTest(unittest.TestCase):
    def test_first_match_halves_and_range(self):
        cases = {"EMOM 12 min, RPE 7": 7, "rpe 6.5 then RPE 9": 6.5, "RPE7": 7, "RPE 10": 10, "RPE 11": None,
                 "RPE 7.3": None, "": None, None: None, "no effort noted": None}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(hevy_conditioning.parse_rpe(text), expected)


TEST_ADAPTER = '''
from coach.activity.adapters import Drop, FetchResult
from coach.config import Key

NAME = "test_source"
KINDS = ("activity", "wellness")
NETWORK = False
CONFIG = {"enabled": Key("boolean", default=False)}


def fetch(ctx, sync_state):
    if ctx.env.get("TEST_SOURCE_FAIL"):
        raise RuntimeError("export folder missing")
    return FetchResult(items=[{"day": "2026-10-11"}, {"bad": True}], sync_state={"cursor": 1})


def normalise(item, ctx):
    if "bad" in item:
        raise Drop("not a test record")
    return [{"id": "test_source:" + item["day"], "source": NAME, "span": {"start": item["day"], "end": item["day"]},
             "sleep": {"asleep_hours": 8.0, "in_bed_hours": None, "start": None, "end": None},
             "resting_hr_bpm": None, "hrv_ms": None, "steps": None, "body_mass_kg": None, "body_fat_pct": None,
             "device": None}]
'''


class DiscoveredAdapterTest(SyncCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        (Path(folder.name) / "test_source.py").write_text(textwrap.dedent(TEST_ADAPTER), encoding="utf-8")
        adapters.__path__.append(folder.name)
        self.addCleanup(self._forget, folder.name)
        self._reload_tables()
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + "\n[sources.test_source]\nenabled = true\n", encoding="utf-8")
        self.set_config('precedence = ["manual", "test_source", "hevy_conditioning"]\n')

    def _forget(self, folder):
        adapters.__path__.remove(folder)
        sys.modules.pop("coach.activity.adapters.test_source", None)
        self._reload_tables()

    @staticmethod
    def _reload_tables():
        import coach.config_tables.activity as tables
        importlib.reload(tables)

    def test_is_discovered_and_synced(self):
        report, warnings = self.sync()
        by_source = {row["source"]: row for row in report}
        self.assertEqual(by_source["test_source"]["appended"], 1)
        self.assertEqual(by_source["test_source"]["dropped"], {"not a test record": 1})
        self.assertIn("test_source: dropped 1 item(s): not a test record", warnings)
        days = self.ok("wellness", "list", "--from", "2026-10-11", "--to", "2026-10-11")["days"]
        self.assertEqual(days[0]["sleep"]["asleep_hours"], 8.0)
        self.assertEqual(days[0]["field_sources"]["sleep"], "test_source")
        sync_map = json.loads((self.root / SYNC).read_text(encoding="utf-8"))
        self.assertEqual(sync_map["sources"]["test_source"]["state"], {"cursor": 1})

    def test_a_failing_adapter_leaves_the_others_and_its_own_state(self):
        self.sync()
        before_map = json.loads((self.root / SYNC).read_text(encoding="utf-8"))
        workout = self.cache.workout(workout_id("c1"))
        workout["end_time"] = "2026-10-10T09:40:00Z"
        self.cache.write_workout(workout, "2026-10-11T12:00:00Z")
        report, warnings = self.sync(env={"TEST_SOURCE_FAIL": "1", "COACH_NOW": "2026-10-11T19:00:00Z"})
        by_source = {row["source"]: row for row in report}
        self.assertFalse(by_source["test_source"]["ok"])
        self.assertEqual(by_source["hevy_conditioning"]["appended"], 1)
        self.assertTrue(any("test_source: sync failed" in w for w in warnings), warnings)
        after_map = json.loads((self.root / SYNC).read_text(encoding="utf-8"))
        self.assertEqual(after_map["sources"]["test_source"], before_map["sources"]["test_source"])

    def test_freshness_by_newest_record(self):
        self.sync()
        results = self.cli("check", "--only", "activity_source_fresh",
                           env={"COACH_NOW": "2026-10-15T18:00:00Z"})["data"]["results"]
        by_message = {r["message"].split("'")[0]: r["status"] for r in results}
        self.assertEqual(by_message["test_source"], "warn")

    def test_status_reports_missing_wellness_days(self):
        self.sync()
        rows = {row["source"]: row for row in self.ok("activity", "status")["sources"]}
        self.assertEqual(rows["test_source"]["counts"], {"activity": 0, "wellness": 1})
        self.assertEqual(len(rows["test_source"]["missing_days"]), 13)
        self.assertNotIn("2026-10-11", rows["test_source"]["missing_days"])


class PlannedAdapterLineTest(unittest.TestCase):
    """A synced plan feed writes planned records with or without a start (C30, C31)."""

    PLAN = {"id": "runna:20261014-easy", "source": "runna", "date": "2026-10-14", "kind": "run",
            "title": "Easy 5 km", "quality": False, "target": None, "notes": None}
    FEED = SimpleNamespace(NAME="runna", KINDS=("planned",))

    def line(self, record):
        return sync._line(None, self.FEED, record, "2026-10-11T18:00:00Z")

    def test_a_plan_without_a_start_is_planned_and_untimed(self):
        kind, line = self.line(dict(self.PLAN))
        self.assertEqual(kind, "planned")
        self.assertEqual(line["schema_version"], 2)
        self.assertIsNone(line["start"])

    def test_a_plan_with_a_start_or_a_null_start_is_planned(self):
        for start in ("2026-10-14T06:30:00Z", None):
            with self.subTest(start=start):
                kind, line = self.line({**self.PLAN, "start": start})
                self.assertEqual(kind, "planned")
                self.assertEqual(line["start"], start)

    def test_activity_and_wellness_shapes_keep_their_files(self):
        self.assertEqual(sync.file_kind({"start": "2026-10-14T06:30:00Z", "local_date": "2026-10-14"}), "activity")
        self.assertEqual(sync.file_kind({"span": {"from": "2026-10-14", "to": "2026-10-14"}}), "wellness")


if __name__ == "__main__":
    unittest.main()
