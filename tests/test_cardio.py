"""Cardio: tiers, weekly numbers, reconcile, flags, week-flag providers and the record region (contract C48, C49)."""

import json
import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import coach.weekflags
from coach import cardio, dates, flags, research
from coach.config_tables.cardio import CARDIO as CARDIO_TABLE
from tests.support import INSTANCES, REPO_ROOT, run_cli

CARDIO = INSTANCES / "cardio"
LAYOFF = INSTANCES / "layoff"
NOW = "2026-10-11T18:00:00Z"
CODES = ("cap_breach", "run_volume_spike", "quality_stack", "collision", "sleep_debt", "status_active", "niggle_link")
ACTIVITY_CODES = {"cap_breach", "run_volume_spike", "quality_stack", "sleep_debt", "niggle_link"}


class CardioCase(unittest.TestCase):
    base = CARDIO

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def data(self, *argv):
        return self.coach(*argv)["data"]

    def config(self, *lines):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        for line in lines:
            key = line.split("=")[0].strip()
            if re.search(rf"^{key} = .*$", text.split("[cardio]", 1)[1], flags=re.MULTILINE):
                head, tail = text.split("[cardio]", 1)
                text = head + "[cardio]" + re.sub(rf"^{key} = .*$", line, tail, count=1, flags=re.MULTILINE)
            else:
                text = text.replace("[cardio]\n", f"[cardio]\n{line}\n", 1)
        path.write_text(text, encoding="utf-8")

    def drop_lines(self, relative, predicate):
        path = self.root / relative
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if not predicate(json.loads(line))]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    def flags(self, *argv):
        return self.data("cardio", "flags", *argv)

    @staticmethod
    def codes(found):
        return [f["code"] for f in found]


class RegistryTest(unittest.TestCase):
    def test_the_seven_codes_are_registered_with_their_severities(self):
        registry = flags.registry()
        for code in CODES:
            with self.subTest(code=code):
                self.assertIn(code, registry)
                self.assertEqual(registry[code].owner, "R-43")
        self.assertEqual(registry["run_volume_spike"].severities, ("warn", "info"))
        self.assertEqual(registry["status_active"].severities, ("warn", "info"))


class ConfigTest(CardioCase):
    def test_defaults(self):
        settings = self.data("config", "show")["config"]["cardio"]
        self.assertEqual(settings["tier"], "review")
        self.assertEqual(settings["weekly_quality"], 2)
        self.assertEqual(settings["spike_ratio"], 1.10)
        self.assertEqual(settings["spike_lookback_days"], 30)

    def test_an_unknown_key_exits_5_naming_it(self):
        self.config("weekly_km = 10")
        envelope = self.coach("config", "validate", expect=5)
        self.assertIn("weekly_km", envelope["error"]["message"])

    def test_an_unknown_tier_exits_5_naming_the_key(self):
        self.config('tier = "plan"')
        envelope = self.coach("config", "validate", expect=5)
        self.assertIn("tier", envelope["error"]["message"])
        self.assertIn('"plan"', envelope["error"]["message"])

    def test_cardio_config_check_passes_on_the_fixture_and_fails_on_bad_ranges(self):
        result = self.data("check", "--only", "cardio_config")["results"]
        self.assertEqual([r["status"] for r in result], ["pass"])
        self.config("spike_ratio = 1.0", "weekly_run_distance = -1", "sleep_short_hours = 30")
        envelope = self.coach("check", "--only", "cardio_config", expect=1)
        messages = " ".join(r["message"] for r in envelope["data"]["results"])
        for key in ("spike_ratio", "weekly_run_distance", "sleep_short_hours"):
            self.assertIn(key, messages)

    def test_the_failing_fixture_fails_both_checks(self):
        code, envelope, _ = run_cli(["--root", str(INSTANCES / "cardio-invalid"), "check", "--only",
                                     "cardio_config,status_days_valid"], env={"COACH_NOW": NOW})
        self.assertEqual(code, 1)
        failed = {r["id"] for r in envelope["data"]["results"] if r["status"] == "fail"}
        self.assertEqual(failed, {"cardio_config", "status_days_valid"})


class WeekTest(CardioCase):
    def test_the_fixture_week(self):
        data = self.data("cardio", "week", "--week", "2026-W41")
        self.assertEqual((data["week"], data["span"]), ("2026-W41", {"start": "2026-10-05", "end": "2026-10-11"}))
        self.assertEqual(data["run"], {"count": 2, "distance": 18.5, "minutes": 110, "quality": 1})
        self.assertEqual(data["conditioning"], {"count": 1, "minutes": 20})
        self.assertEqual(data["other"], {"ride": {"count": 1, "minutes": 45}})
        self.assertEqual(data["lifting"], {"workouts": 2, "hard_sets": 12, "minutes": 118})
        self.assertEqual(data["external"], {"done": 0})
        by_ref = {b["ref"]: b for b in data["bouts"]}
        self.assertEqual((by_ref["manual:2026-10-06-run-1"]["quality"],
                          by_ref["manual:2026-10-06-run-1"]["quality_basis"]), (True, "rpe"))
        self.assertEqual((by_ref["manual:2026-10-09-run-1"]["quality"],
                          by_ref["manual:2026-10-09-run-1"]["quality_basis"]), (False, "rpe"))
        self.assertEqual((by_ref["manual:2026-10-07-conditioning-1"]["quality"],
                          by_ref["manual:2026-10-07-conditioning-1"]["quality_basis"]), (True, "kind"))
        self.assertTrue(all(b["srpe"]["method"] for b in data["bouts"]))

    def test_session_rpe_methods_and_loads(self):
        data = self.data("cardio", "week", "--week", "2026-W41")
        by_ref = {b["ref"]: b["srpe"] for b in data["bouts"]}
        self.assertEqual(by_ref["manual:2026-10-06-run-1"], {"rpe": 8, "load": 320, "method": "athlete"})
        self.assertEqual(by_ref["manual:2026-10-05-ride-1"], {"rpe": 4, "load": 180, "method": "kind_default"})
        self.assertEqual(by_ref["manual:2026-10-07-conditioning-1"], {"rpe": 7, "load": 140, "method": "kind_default"})
        squat_day = by_ref["10000000-0000-4000-8000-000000000003"]
        self.assertEqual((squat_day["rpe"], squat_day["method"]), (7.75, "lifting_sets"))
        self.assertEqual(data["srpe"]["by_method"], {"athlete": 2, "kind_default": 2, "lifting_sets": 2})
        self.assertEqual(data["srpe"]["total"], sum(b["srpe"]["load"] for b in data["bouts"]))
        self.assertNotIn("ratio", json.dumps(data["srpe"]))

    def test_a_matched_plan_gives_the_quality_and_the_rpe_when_the_athlete_gave_none(self):
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-10T07:00:00", "--duration-min", "30",
                   "--distance-km", "5")
        by_ref = {b["ref"]: b for b in self.data("cardio", "week", "--week", "2026-W41")["bouts"]}
        easy = by_ref["manual:2026-10-10-run-1"]
        self.assertEqual((easy["quality"], easy["quality_basis"]), (False, "planned"))
        self.assertEqual(easy["srpe"], {"rpe": 3, "load": 90, "method": "planned"})

    def test_the_name_rule_and_the_none_basis(self):
        self.config('tier = "count"')
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-10T07:00:00", "--duration-min", "30",
                   "--name", "Hill repeats")
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-11T07:00:00", "--duration-min", "30",
                   "--name", "Easy jog")
        by_ref = {b["ref"]: b for b in self.data("cardio", "week", "--week", "2026-W41")["bouts"]}
        self.assertEqual(by_ref["manual:2026-10-10-run-1"]["quality_basis"], "name")
        self.assertTrue(by_ref["manual:2026-10-10-run-1"]["quality"])
        self.assertEqual(by_ref["manual:2026-10-11-run-1"]["quality_basis"], "none")

    def test_a_coach_led_session_marked_done_counts_with_the_external_default(self):
        path = self.root / "data" / "history" / "annotations.json"
        path.write_text(json.dumps({"schema_version": 1, "annotations": [
            {"id": "a-0001", "kind": "external", "date": "2026-10-07", "external_id": "pt-tue", "done": True,
             "note": "upper body", "created_at": NOW, "source": "test", "reason": None}]}), encoding="utf-8")
        data = self.data("cardio", "week", "--week", "2026-W41")
        self.assertEqual(data["external"], {"done": 1})
        external = next(b for b in data["bouts"] if b["kind"] == "external")
        self.assertEqual(external["srpe"], {"rpe": 6, "load": 360, "method": "external_default"})

    def test_a_sunday_week_runs_sunday_to_saturday(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('week_starts = "monday"', 'week_starts = "sunday"'),
                        encoding="utf-8")
        data = self.data("cardio", "week", "--week", "2026-W41")
        self.assertEqual(data["span"], {"start": "2026-10-04", "end": "2026-10-10"})
        self.assertEqual(data["week"], "2026-W41")
        self.assertEqual([b["date"] for b in data["bouts"]][0], "2026-10-05")
        self.assertEqual(data["run"]["count"], 2)

    def test_without_an_activity_source_it_reports_lifting_and_warns(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("[activity]\nenabled = true",
                                                                 "[activity]\nenabled = false"), encoding="utf-8")
        envelope = self.coach("cardio", "week", "--week", "2026-W41")
        self.assertEqual(envelope["data"]["lifting"]["workouts"], 2)
        self.assertEqual(envelope["data"]["run"]["count"], 0)
        self.assertTrue(any("no activity source" in w for w in envelope["warnings"]))
        found = self.flags("--week", "2026-W41")["flags"]
        self.assertFalse(ACTIVITY_CODES & set(self.codes(found)))
        self.assertEqual(self.data("cardio", "reconcile", "--week", "2026-W41")["items"], [])


class ReconcileTest(CardioCase):
    def test_the_fixture_week(self):
        items = self.data("cardio", "reconcile", "--week", "2026-W41")["items"]
        by_date = {(i["date"], i["status"]): i for i in items}
        self.assertIn(("2026-10-06", "done"), by_date)
        moved = by_date[("2026-10-08", "moved")]
        self.assertEqual((moved["activity_date"], moved["moved_days"]), ("2026-10-09", 1))
        self.assertEqual(moved["delta"], {"distance_meters": 500, "duration_seconds": None})
        self.assertIn(("2026-10-10", "missed"), by_date)
        extra = [i for i in items if i["status"] == "extra"]
        self.assertIn(("ride", "manual:2026-10-05-ride-1"), [(i["kind"], i["activity_id"]) for i in extra])

    def test_the_count_tier_has_no_reconcile_and_plans_raise_nothing(self):
        self.config('tier = "count"')
        self.coach("planned", "add", "--date", "2026-10-17", "--kind", "run", "--title", "Long run",
                   "--distance-km", "15")
        data = self.data("cardio", "reconcile", "--week", "2026-W41")
        self.assertEqual((data["tier"], data["items"]), ("count", []))
        found = self.flags("--span", "2026-10-12..2026-10-18")
        self.assertEqual([b for b in found["bouts"] if b["source"] == "planned"], [])
        self.assertFalse({"cap_breach", "run_volume_spike", "quality_stack"} & set(self.codes(found["flags"])))

    def test_upcoming_plans_and_a_duplicate_plan(self):
        data = self.data("cardio", "reconcile", "--week", "2026-W42")
        self.assertEqual([i["status"] for i in data["items"]], ["upcoming", "upcoming"])
        planned = [{"id": "a:1", "date": "2026-10-06", "kind": "run", "title": "x", "quality": False, "target": None},
                   {"id": "b:1", "date": "2026-10-06", "kind": "run", "title": "x", "quality": False, "target": None}]
        logged = [{"id": "manual:r", "local_date": "2026-10-06", "kind": "run", "start": "2026-10-06T07:00:00Z",
                   "distance_meters": None, "duration_seconds": 1800}]
        statuses = sorted(i["status"] for i in cardio.match(planned, logged, 3, dates.parse_date("2026-10-11")))
        self.assertEqual(statuses, ["done", "missed"])

    def test_ties_go_to_the_earlier_activity(self):
        planned = [{"id": "p", "date": "2026-10-08", "kind": "run", "title": "x", "quality": False, "target": None}]
        logged = [{"id": f"manual:{d}", "local_date": d, "kind": "run", "start": f"{d}T07:00:00Z",
                   "distance_meters": None, "duration_seconds": 1800} for d in ("2026-10-09", "2026-10-07")]
        moved = [i for i in cardio.match(planned, logged, 3) if i["status"] == "moved"]
        self.assertEqual(moved[0]["activity_id"], "manual:2026-10-07")


class FlagsTest(CardioCase):
    def test_the_fixture_week(self):
        found = self.flags("--week", "2026-W41")["flags"]
        codes = self.codes(found)
        self.assertEqual(codes, ["cap_breach", "run_volume_spike", "quality_stack", "sleep_debt", "niggle_link"])
        by_code = {f["code"]: f for f in found}
        self.assertIn("18.5 km", by_code["cap_breach"]["message"])
        self.assertIn("18 km", by_code["cap_breach"]["message"])
        spike = by_code["run_volume_spike"]
        self.assertEqual(spike["severity"], "warn")
        self.assertIn("2026-10-09", spike["message"])
        self.assertIn("10 km", spike["message"])
        self.assertIn("2026-10-06", by_code["quality_stack"]["message"])
        self.assertIn("2026-10-07", by_code["quality_stack"]["message"])
        self.assertIn("4 of the 7 nights", by_code["sleep_debt"]["message"])
        self.assertIn("left knee", by_code["niggle_link"]["message"])
        self.assertIn("2 runs", by_code["niggle_link"]["message"])
        self.assertTrue(all(f["session_id"] is None and f["exercise_id"] is None for f in found))

    def test_a_short_store_history_is_skipped_not_flagged(self):
        self.drop_lines("data/activity/activities.jsonl", lambda line: line["id"] == "manual:2026-09-21-run-1")
        data = self.flags("--week", "2026-W41")
        self.assertNotIn("run_volume_spike", self.codes(data["flags"]))
        skipped = {s["ref"]: s["reason"] for s in data["skipped"]}
        self.assertIn("store history shorter than the 30-day lookback", skipped["manual:2026-10-09-run-1"])
        self.assertIn(" 1 day before this run", skipped["manual:2026-10-06-run-1"])
        self.assertIn(" 4 days before this run", skipped["manual:2026-10-09-run-1"])

    def test_no_reference_run_is_skipped(self):
        self.drop_lines("data/activity/activities.jsonl", lambda line: line["id"] == "manual:2026-09-21-run-1")
        self.config("spike_min_history_days = 0")
        skipped = {s["ref"]: s["reason"] for s in self.flags("--week", "2026-W41")["skipped"]}
        self.assertIn("no logged run", skipped["manual:2026-10-06-run-1"])

    def test_next_week(self):
        found = self.flags("--span", "2026-10-12..2026-10-18")["flags"]
        status = [f for f in found if f["code"] == "status_active"]
        self.assertEqual([(f["severity"], "2026-10-15" in f["message"]) for f in status], [("info", True)])
        self.assertNotIn("cap_breach", self.codes(found))

    def test_a_planned_spike_is_info(self):
        self.coach("planned", "add", "--date", "2026-10-17", "--kind", "run", "--title", "Long run",
                   "--distance-km", "15")
        found = self.flags("--span", "2026-10-12..2026-10-18")["flags"]
        spikes = [f for f in found if f["code"] == "run_volume_spike"]
        self.assertEqual(len(spikes), 1)
        self.assertEqual(spikes[0]["severity"], "info")
        self.assertIn("Planned activity (run) on 2026-10-17", spikes[0]["message"])

    def test_ill_and_injured_status_days_warn(self):
        self.coach("status-days", "add", "--kind", "injured", "--from", "2026-10-10", "--note", "calf")
        found = [f for f in self.flags("--week", "2026-W41")["flags"] if f["code"] == "status_active"]
        self.assertEqual(found[0]["severity"], "warn")
        self.assertIn("qualified professional", found[0]["message"])

    def test_single_run_and_quality_caps(self):
        self.config("single_run_distance = 10", "single_run_minutes = 65", "weekly_quality = 1",
                    "weekly_run_minutes = 100")
        messages = [f["message"] for f in self.flags("--week", "2026-W41")["flags"] if f["code"] == "cap_breach"]
        self.assertEqual(len(messages), 5)
        self.assertTrue(any("single-run cap" in m and "11.5 km" in m for m in messages))
        self.assertTrue(any("70 min" in m for m in messages))
        self.assertTrue(any("2 quality activities" in m for m in messages))
        self.assertTrue(any("110 min" in m for m in messages))

    def test_sleep_debt_reader(self):
        span = dates.Span(dates.parse_date("2026-10-05"), dates.parse_date("2026-10-11"))
        self.assertTrue(cardio.sleep_debt(self.root, span))
        earlier = dates.Span(dates.parse_date("2026-09-28"), dates.parse_date("2026-10-04"))
        self.assertIsNone(cardio.sleep_debt(self.root, earlier))
        self.config("sleep_debt_nights = 5")
        self.assertFalse(cardio.sleep_debt(self.root, span))


class BoutsTest(CardioCase):
    def test_logged_bouts(self):
        span = dates.Span(dates.parse_date("2026-10-05"), dates.parse_date("2026-10-11"))
        found = cardio.bouts(self.root, span, "logged")
        self.assertEqual([b.kind for b in found], ["ride", "lifting", "run", "conditioning", "lifting", "run"])
        self.assertTrue(all(isinstance(b, cardio.Bout) and b.source == "logged" for b in found))

    def test_proposal_bouts(self):
        envelope = self.coach("propose", "week", "--week", "2026-W42", "--dry-run")
        doc = envelope["data"]["overlay"]
        span = dates.Span(dates.parse_date("2026-10-12"), dates.parse_date("2026-10-18"))
        found = cardio.bouts(self.root, span, "proposal", overlay=doc, today=dates.parse_date("2026-10-11"))
        refs = [b.ref for b in found]
        self.assertIn(f"{doc['id']}/session-a", refs)
        self.assertIn("manual:2026-10-14-run-1", refs)
        self.assertIsNone(next(b for b in found if b.kind == "lifting").start)


class ProposeTest(CardioCase):
    def test_the_providers_flags_join_the_overlay(self):
        overlay = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        week_flags = [f for f in overlay["flags"] if f["code"] in CODES]
        self.assertIn("status_active", self.codes(week_flags))
        self.assertTrue(all(f["session_id"] is None for f in week_flags))

    def test_a_midweek_draft_counts_the_activities_logged_earlier_that_week(self):
        self.config("weekly_run_distance = 12")
        midweek = "2026-10-08T06:00:00Z"
        self.coach("planned", "add", "--date", "2026-10-08", "--kind", "run", "--title", "Tempo", "--quality",
                   "--distance-km", "6", now=midweek)
        envelope = self.coach("propose", "week", "--kind", "midweek", "--dry-run", now=midweek)
        self.assertEqual(envelope["data"]["span"]["start"], "2026-10-08")
        found = [f for f in envelope["data"]["overlay"]["flags"] if f["code"] in CODES]
        caps = [f["message"] for f in found if f["code"] == "cap_breach"]
        self.assertEqual(len(caps), 2)
        self.assertIn("Run distance 18 km in 2026-W41", caps[0])
        self.assertIn("3 quality activities in 2026-W41", caps[1])
        stacks = [f["message"] for f in found if f["code"] == "quality_stack"]
        self.assertEqual(len(stacks), 1)
        self.assertIn("2026-10-07", stacks[0])
        self.assertIn("2026-10-08", stacks[0])

    def test_a_provider_is_discovered_without_a_registry(self):
        directory = Path(tempfile.mkdtemp(dir=self.tmp))
        name = f"probe_{id(self)}"
        (directory / f"{name}.py").write_text(textwrap.dedent("""
            from coach import flags as registry
            NAME = "probe"
            def flags(ctx):
                return [registry.make("collision", "info", message=f"probe saw {len(ctx.bouts)} bouts")]
        """), encoding="utf-8")
        self.addCleanup(sys.modules.pop, f"coach.weekflags.{name}", None)
        with mock.patch.object(coach.weekflags, "__path__", list(coach.weekflags.__path__) + [str(directory)]):
            self.assertIn("probe", [p.name for p in coach.weekflags.discover()])
            overlay = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        self.assertIn("probe saw", " ".join(f["message"] for f in overlay["flags"] if f["code"] == "collision"))

    def test_a_provider_that_raises_fails_the_command(self):
        directory = Path(tempfile.mkdtemp(dir=self.tmp))
        name = f"broken_{id(self)}"
        (directory / f"{name}.py").write_text("NAME = 'broken'\ndef flags(ctx):\n    raise RuntimeError('boom')\n",
                                              encoding="utf-8")
        self.addCleanup(sys.modules.pop, f"coach.weekflags.{name}", None)
        with mock.patch.object(coach.weekflags, "__path__", list(coach.weekflags.__path__) + [str(directory)]):
            self.coach("propose", "week", "--week", "2026-W42", "--dry-run", expect=9)


class RenderTest(CardioCase):
    def record(self):
        path = self.root / "check-ins" / "2026-10-11.md"
        return path, path.read_text(encoding="utf-8")

    def test_into_adds_one_region_and_a_second_run_changes_nothing(self):
        path, before = self.record()
        first = self.data("cardio", "render", "--week", "2026-W41", "--into", str(path))
        self.assertTrue(first["written"])
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(before))
        self.assertEqual(text.count("<!-- coach:begin cardio 2026-W41 -->"), 1)
        self.assertEqual(text.count("<!-- coach:end cardio 2026-W41 -->"), 1)
        self.assertIn("| Runs | 2 | 18.5 | 110 | 1 |", text)
        self.assertIn("moved", text)
        self.assertIn("`cap_breach`", text)
        snapshot = path.read_bytes()
        second = self.data("cardio", "render", "--week", "2026-W41", "--into", str(path))
        self.assertFalse(second["changed"])
        self.assertEqual(path.read_bytes(), snapshot)

    def test_dry_run_writes_nothing(self):
        path, before = self.record()
        data = self.data("cardio", "render", "--week", "2026-W41", "--into", str(path), "--dry-run")
        self.assertTrue(data["changed"])
        self.assertFalse(data["written"])
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_the_sweep_leaves_the_snapshot_alone(self):
        path, _ = self.record()
        self.data("cardio", "render", "--week", "2026-W41", "--into", str(path))
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-10T07:00:00", "--duration-min", "30")
        results = self.data("check", "--only", "render_fresh_sweep")["results"]
        self.assertEqual([r["status"] for r in results], ["pass"])


class CardPartTest(CardioCase):
    def test_runs_and_sleep_are_stated(self):
        card = self.data("checkin", "prepare", "--tier", "weekly")["card"]
        fields = {f["id"]: f for f in card["fields"]}
        self.assertIn("Logged: 3 runs, 28.5 km (1 quality).", fields["runs"]["prefill"])
        self.assertIn("Easy 5 km", fields["runs"]["prefill"])
        self.assertIn("4 under 7 h", fields["sleep"]["prefill"])
        self.assertIn("sleep_debt", self.codes(card["flags"]))

    def test_a_period_mean_leaves_the_stated_nightly_average_and_count_alone(self):
        self.drop_lines(".coach/activity/wellness.jsonl", lambda r: r["span"]["start"] in ("2026-10-10", "2026-10-11"))
        self.coach("wellness", "add", "--from", "2026-10-10", "--to", "2026-10-11", "--sleep-hours", "6")
        card = self.data("checkin", "prepare", "--tier", "weekly")["card"]
        fields = {f["id"]: f for f in card["fields"]}
        self.assertIn("Recorded: 6.68 h a night over 5 nights, 4 under 7 h.", fields["sleep"]["prefill"])


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.notes = research.load_notes(REPO_ROOT)

    def claim(self, ref):
        found = research.resolve(ref, self.notes)
        self.assertIsNotNone(found, ref)
        return found

    def test_the_module_cites_the_running_load_claims(self):
        self.assertEqual(cardio.CITES, tuple(f"rn:running-load.{n}" for n in range(1, 5)))
        for ref in cardio.CITES:
            self.claim(ref)

    def test_the_claims_state_the_defaults_the_code_uses(self):
        defaults = {name: key.default for name, key in CARDIO_TABLE.keys.items()}
        self.assertEqual((defaults["spike_ratio"], defaults["spike_lookback_days"], defaults["spike_min_history_days"]),
                         (1.10, 30, 14))
        spike = self.claim("rn:running-load.1")
        self.assertIn("1.10", spike.text)
        self.assertIn("30 days", spike.text)
        note = next(n for n in self.notes if n.id == "running-load")
        self.assertEqual((spike.basis, spike.confidence or note.confidence), ("evidence", "low"))
        guard = self.claim("rn:running-load.4")
        self.assertEqual((guard.basis, "14 days" in guard.text), ("heuristic", True))

    def test_the_sources_behind_each_claim(self):
        expected = {1: ("evidence", {"frandsen-2025"}),
                    2: ("evidence", {"frandsen-2025", "impellizzeri-2020", "lolli-2019"}),
                    3: ("evidence", {"foster-2001", "haddad-2017"}),
                    4: ("heuristic", set())}
        for n, (basis, sources) in expected.items():
            with self.subTest(claim=n):
                found = self.claim(f"rn:running-load.{n}")
                self.assertEqual((found.basis, set(found.sources)), (basis, sources))

    def test_the_config_example_cites_the_running_load_claims(self):
        lines = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8").splitlines()
        start = lines.index("[cardio]")
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
        section = "\n".join(lines[start:end])
        self.assertNotIn("no research note", section)
        for ref in ("rn:running-load.1", "rn:running-load.4", "rn:running-load.5", "rn:running-load.6",
                    "rn:running-load.7"):
            self.assertIn(ref, section)


if __name__ == "__main__":
    unittest.main()
