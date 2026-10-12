"""Activity identity regressions across reconciliation, persisted corrections and rendered records."""

import json
from datetime import timedelta

from coach import cardio, dates, jsonio, paths
from coach.activity import records
from tests.test_cardio import CardioCase, NOW


def plan(record_id, day, meters, quality=False, title="Run", seconds=None):
    return {"id": record_id, "source": "manual", "date": day, "kind": "run", "title": title,
            "quality": quality, "target": {"distance_meters": meters, "duration_seconds": seconds}}


def activity(record_id, day, meters, seconds=1800, name=None, rpe=None):
    return {"id": record_id, "source": "manual", "local_date": day, "kind": "run",
            "start": day + "T07:00:00Z", "duration_seconds": seconds, "distance_meters": meters,
            "name": name, "rpe": rpe}


class IdentityTest(CardioCase):
    def set_records(self, plans, activities):
        for kind, items in (("planned", plans), ("activities", activities)):
            path = self.root / "data" / "activity" / (kind + ".jsonl")
            path.write_text("".join(json.dumps(records.upsert_line(item, NOW)) + "\n" for item in items))

    def swapped(self):
        plans = [plan("manual:quality", "2026-10-06", 10000, True),
                 plan("manual:easy", "2026-10-07", 6000)]
        acts = [activity("manual:short", "2026-10-06", 6000),
                activity("manual:long", "2026-10-07", 10000, 3000)]
        self.set_records(plans, acts)
        return plans, acts

    def reconcile(self):
        return self.data("cardio", "reconcile", "--week", "2026-W41")["items"]

    def test_swapped_distances_drive_quality_effort_totals_and_bout_timeline(self):
        self.swapped()
        rows = {i["planned_id"]: i for i in self.reconcile()}
        self.assertEqual(rows["manual:quality"]["activity_id"], "manual:long")
        self.assertEqual(rows["manual:easy"]["activity_id"], "manual:short")
        self.assertTrue(all(i["status"] == "moved" for i in rows.values()))
        self.assertTrue(all("distance_meters" in i["match_basis"] for i in rows.values()))
        week = self.data("cardio", "week", "--week", "2026-W41")
        bouts = {b["ref"]: b for b in week["bouts"]}
        self.assertEqual(week["run"]["quality"], 1)
        self.assertEqual(bouts["manual:long"]["planned_id"], "manual:quality")
        self.assertIn("distance_meters", bouts["manual:long"]["match_basis"])
        self.assertEqual(bouts["manual:short"]["srpe"], {"rpe": 3, "load": 90, "method": "planned"})
        self.assertEqual(bouts["manual:long"]["srpe"], {"rpe": 7, "load": 350, "method": "planned"})
        span = dates.parse_week("2026-W41", "monday")
        actual = {b.ref: b.quality for b in cardio.bouts(self.root, span, "logged") if b.kind == "run"}
        self.assertEqual(actual, {"manual:short": False, "manual:long": True})
        flags = self.data("cardio", "flags", "--week", "2026-W41")
        self.assertEqual({b["ref"]: b["quality"] for b in flags["bouts"] if b["kind"] == "run"}, actual)

    def test_logged_rpe_overrides_inherited_quality_and_effort_everywhere(self):
        plans, acts = self.swapped()
        acts[1]["rpe"] = 2
        self.set_records(plans, acts)
        direct = next(i for i in cardio.match(plans, acts, 3) if i["activity_id"] == "manual:long")
        self.assertEqual((direct["quality"], direct["quality_basis"]), (False, "rpe"))
        row = next(i for i in self.reconcile() if i["activity_id"] == "manual:long")
        self.assertEqual((row["quality"], row["quality_basis"]), (False, "rpe"))
        week = self.data("cardio", "week", "--week", "2026-W41")
        bout = next(b for b in week["bouts"] if b["ref"] == "manual:long")
        self.assertEqual((week["run"]["quality"], bout["srpe"]),
                         (0, {"rpe": 2, "load": 100, "method": "athlete"}))

    def test_ambiguous_plans_need_explicit_ids_and_clearing_recomputes_quality(self):
        plans = [plan("manual:p1", "2026-10-06", 10000, True),
                 plan("manual:p2", "2026-10-07", 10000)]
        acts = [activity("manual:a1", "2026-10-06", 10000),
                activity("manual:a2", "2026-10-07", 10000)]
        self.set_records(plans, acts)
        self.assertEqual({i["status"] for i in self.reconcile()}, {"ambiguous"})
        self.assertEqual(self.data("cardio", "week", "--week", "2026-W41")["run"]["quality"], 0)
        dry = self.data("cardio", "associate", "manual:a2", "--planned-id", "manual:p1", "--dry-run")
        self.assertFalse(dry["written"])
        self.assertFalse((self.root / paths.ACTIVITY_ASSOCIATIONS).exists())
        self.data("cardio", "associate", "manual:a2", "--planned-id", "manual:p1")
        first = self.reconcile()
        self.assertEqual(first, self.reconcile())
        self.assertEqual(len({i["activity_id"] for i in first}), 2)
        quality = next(i for i in first if i["planned_id"] == "manual:p1")
        self.assertEqual((quality["activity_id"], quality["match_basis"]),
                         ("manual:a2", ["explicit_association"]))
        self.data("cardio", "associate", "manual:a2", "--clear")
        self.assertEqual({i["status"] for i in self.reconcile()}, {"ambiguous"})
        self.assertEqual(self.data("cardio", "week", "--week", "2026-W41")["run"]["quality"], 0)

    def test_same_id_correction_and_reimport_keep_association_and_recompute_effort(self):
        plans, acts = self.swapped()
        self.data("cardio", "associate", "manual:short", "--planned-id", "manual:quality")
        changed = dict(acts[0], rpe=1, distance_meters=12000)
        path = self.root / paths.ACTIVITIES
        line = records.upsert_line(changed, NOW)
        records.append_lines(path, [line, line])
        item = next(i for i in self.reconcile() if i["planned_id"] == "manual:quality")
        self.assertEqual((item["activity_id"], item["delta"]["distance_meters"], item["quality"]),
                         ("manual:short", 2000, False))
        self.assertEqual(item["match_basis"], ["explicit_association"])
        self.data("cardio", "associate", "manual:short", "--clear")
        self.assertEqual(next(i for i in self.reconcile() if i["planned_id"] == "manual:quality")["activity_id"],
                         "manual:long")

    def test_conflicting_hand_edited_links_and_dedup_aliases_are_reviewable(self):
        plans, acts = self.swapped()
        duplicate = dict(acts[0], id="apple_health:alias", source="apple_health")
        self.set_records(plans, acts + [duplicate])
        self.data("cardio", "associate", "apple_health:alias", "--planned-id", "manual:quality")
        self.assertEqual(next(i for i in self.reconcile() if i["planned_id"] == "manual:quality")["activity_id"],
                         "manual:short")
        self.coach("cardio", "associate", "manual:long", "--planned-id", "manual:quality", expect=1)
        jsonio.write_doc(self.root / paths.ACTIVITY_ASSOCIATIONS,
                        {"schema_version": 1, "associations": {"manual:short": "manual:quality",
                                                               "manual:long": "manual:quality"}}, False)
        rows = self.reconcile()
        self.assertFalse(any(i["planned_id"] and i["activity_id"] for i in rows))
        self.assertTrue(any(i["review_reason"] == "conflicting explicit associations" for i in rows))

    def test_distances_render_signed_in_km_and_miles_and_preserve_prose(self):
        for unit, factor in (("km", 1000), ("mi", 1609.344)):
            with self.subTest(unit=unit):
                self.config(f'distance_unit = "{unit}"')
                plans = [plan(f"manual:p{i}", f"2026-10-{6+i:02}", target * factor)
                         for i, target in enumerate((10, 20, 30, 40))]
                acts = [activity(f"manual:a{i}", p["date"], actual * factor if actual is not None else None)
                        for i, (p, actual) in enumerate(zip(plans, (6, 20, 32, None)))]
                self.set_records(plans, acts)
                for p, a in zip(plans, acts):
                    self.data("cardio", "associate", a["id"], "--planned-id", p["id"])
                path = self.root / "check-ins" / "signed.md"
                path.write_text("# Record\n\nAthlete prose before.\n")
                self.data("cardio", "render", "--week", "2026-W41", "--into", str(path))
                path.write_text(path.read_text() + "\nAthlete prose after.\n")
                before = path.read_bytes()
                result = self.data("cardio", "render", "--week", "2026-W41", "--into", str(path))
                self.assertFalse(result["changed"])
                self.assertEqual(path.read_bytes(), before)
                self.assertIn(f"Distance Δ ({unit})", result["text"])
                for delta in ("| -4 |", "| 0 |", "| +2 |", "|  |  |"):
                    self.assertIn(delta, result["text"])
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-11T07:00:00Z",
                   "--duration-min", "30", "--distance-km", "-1", expect=1)

    def test_unique_short_completion_still_matches(self):
        self.set_records([plan("manual:p", "2026-10-06", 10000)],
                         [activity("manual:a", "2026-10-06", 6000)])
        [row] = self.reconcile()
        self.assertEqual((row["status"], row["delta"]["distance_meters"]), ("done", -4000))
        self.assertIn("| -4 |", self.data("cardio", "render", "--week", "2026-W41")["text"])

    def test_duration_and_independent_name_can_identify_moved_runs_but_conflicts_cannot(self):
        plans = [plan("manual:p1", "2026-10-06", None, True, "Tempo", 3600),
                 plan("manual:p2", "2026-10-07", None, False, "Easy", 1800)]
        acts = [activity("manual:a1", "2026-10-06", None, 1800, "Easy"),
                activity("manual:a2", "2026-10-07", None, 3600, "Tempo")]
        self.set_records(plans, acts)
        self.assertTrue(all(i["status"] == "moved" for i in self.reconcile()))
        acts[0]["name"], acts[1]["name"] = "Tempo", "Easy"
        self.set_records(plans, acts)
        self.assertEqual({i["status"] for i in self.reconcile()}, {"ambiguous"})

    def test_cross_week_move_window_and_stale_associations(self):
        self.set_records([plan("manual:p", "2026-10-11", 10000, True)],
                         [activity("manual:a", "2026-10-12", 10000)])
        [row] = self.reconcile()
        self.assertEqual((row["status"], row["activity_date"]), ("moved", "2026-10-12"))
        self.assertEqual(self.data("cardio", "week", "--week", "2026-W42")["run"]["quality"], 1)
        self.data("cardio", "associate", "manual:a", "--planned-id", "manual:p")
        self.config("reconcile_move_days = 0")
        [row] = self.reconcile()
        self.assertEqual(row["status"], "ambiguous")
        self.assertEqual(self.data("cardio", "week", "--week", "2026-W42")["run"]["quality"], 0)
        self.data("cardio", "associate", "manual:a", "--clear")
        self.assertEqual(self.reconcile()[0]["status"], "upcoming")

    def test_voided_plan_does_not_leave_stale_quality_and_link_can_be_cleared(self):
        self.set_records([plan("manual:p", "2026-10-06", 10000, True)],
                         [activity("manual:a", "2026-10-06", 10000)])
        self.data("cardio", "associate", "manual:a", "--planned-id", "manual:p")
        self.data("planned", "void", "manual:p", "--reason", "cancelled")
        [row] = self.reconcile()
        self.assertEqual((row["status"], row["quality"]), ("ambiguous", False))
        self.data("cardio", "associate", "manual:a", "--clear")
        self.assertEqual(self.reconcile()[0]["status"], "extra")

    def test_invalid_association_schema_is_reported_by_activity_check(self):
        path = self.root / paths.ACTIVITY_ASSOCIATIONS
        path.write_text('{"schema_version": 1, "associations": {"manual:a": 7}}')
        result = self.coach("check", "--only", "activity_records_valid", expect=1)
        where = paths.ACTIVITY_ASSOCIATIONS.as_posix()
        failures = [r for r in result["data"]["results"] if r["status"] == "fail" and r["path"] == where]
        self.assertEqual(len(failures), 1, failures)
        self.assertIn(f"{where}: $.associations", failures[0]["message"])

    def test_source_sync_correction_and_repeat_keep_the_explicit_plan(self):
        from tests.support import FIXTURES
        from tests.support.activity import write_hevy_cache

        cache = write_hevy_cache(self.root, FIXTURES / "hevy" / "conditioning")
        self.data("activity", "sync", "--source", "hevy_conditioning")
        record_id = "hevy_conditioning:00000000-0000-4000-8000-0000000000c6"
        activity_row = self.data("activity", "show", record_id)["activity"]
        planned = self.data("planned", "add", "--date", activity_row["local_date"], "--kind", "run",
                            "--title", "Quality", "--quality", "--distance-km", "10")
        self.data("cardio", "associate", record_id, "--planned-id", planned["record"]["id"])
        workout = cache.workout(record_id.split(":", 1)[1])
        workout["description"] = "Corrected effort, RPE 2"
        cache.write_workout(workout, NOW)
        self.data("activity", "sync", "--source", "hevy_conditioning")
        self.data("activity", "sync", "--source", "hevy_conditioning")
        row = next(i for i in self.data("cardio", "reconcile", "--week", activity_row["local_date"])["items"]
                   if i["activity_id"] == record_id)
        self.assertEqual((row["planned_id"], row["match_basis"], row["quality"]),
                         (planned["record"]["id"], ["explicit_association"], False))

    def test_unique_date_fallback_and_input_order_are_deterministic(self):
        plans = [plan("manual:p", "2026-10-06", None)]
        acts = [activity("manual:a1", "2026-10-06", None), activity("manual:a2", "2026-10-07", None)]
        rows = cardio.match(plans, acts, 3)
        matched = next(i for i in rows if i["planned_id"])
        self.assertEqual((matched["activity_id"], matched["status"]), ("manual:a1", "done"))
        self.assertIn("date_proximity", matched["match_basis"])
        self.assertEqual(rows, cardio.match(plans, list(reversed(acts)), 3))
        plans, acts = self.swapped()
        self.assertEqual(cardio.match(plans, acts, 3), cardio.match(list(reversed(plans)), list(reversed(acts)), 3))

    def test_link_survives_a_change_of_dedup_winner(self):
        plans, acts = self.swapped()
        duplicate = dict(acts[0], id="apple_health:alias", source="apple_health")
        self.set_records(plans, acts + [duplicate])
        self.data("cardio", "associate", "apple_health:alias", "--planned-id", "manual:quality")
        self.data("activity", "void", "manual:short", "--reason", "duplicate")
        row = next(i for i in self.reconcile() if i["planned_id"] == "manual:quality")
        self.assertEqual((row["activity_id"], row["match_basis"]),
                         ("apple_health:alias", ["explicit_association"]))

    def test_an_explicit_correction_recomputes_quality_without_reusing_the_activity(self):
        self.swapped()
        self.data("cardio", "associate", "manual:long", "--planned-id", "manual:quality")
        self.data("cardio", "associate", "manual:long", "--planned-id", "manual:easy")
        rows = self.reconcile()
        row = next(i for i in rows if i["activity_id"] == "manual:long")
        self.assertEqual((row["planned_id"], row["quality"]), ("manual:easy", False))
        self.assertEqual(sum(i["activity_id"] == "manual:long" for i in rows), 1)

    def test_interference_observes_the_resolved_quality_on_the_logged_date(self):
        from coach import flags
        from tests.test_interference import PLUGIN_TEST, custom_rule

        saved = dict(flags.registry())
        self.addCleanup(lambda: (flags._REGISTRY.clear(), flags._REGISTRY.update(saved)))
        self.swapped()
        directory = self.root / "plugins" / "interference"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "custom_quality_seen.py").write_text(custom_rule("custom_quality_seen"))
        test_path = self.root / "plugins" / "tests" / "test_custom_quality_seen.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(PLUGIN_TEST)
        path = self.root / paths.PROGRAM
        program = json.loads(path.read_text())
        program["interference"] = [{"name": "custom_quality_seen", "params": {}}]
        path.write_text(json.dumps(program))
        result = self.data("cardio", "flags", "--week", "2026-W41")
        messages = [f["message"] for f in result["flags"] if f["code"] == "custom_quality_seen"]
        self.assertEqual(messages, ["quality activity on 2026-10-07"])

    def test_conditioning_kind_precedes_easy_name_rpe_and_planned_quality(self):
        for intended_quality in (False, True):
            with self.subTest(planned_quality=intended_quality):
                planned = dict(plan("manual:p", "2026-10-06", None, intended_quality), kind="conditioning")
                completed = dict(activity("manual:a", "2026-10-07", None, name="Easy circuit", rpe=6),
                                 kind="conditioning")
                self.set_records([planned], [completed])
                [row] = self.reconcile()
                self.assertEqual((row["status"], row["activity_id"], row["quality"], row["quality_basis"]),
                                 ("moved", "manual:a", True, "kind"))

    def test_identical_plans_done_on_their_days_match_by_date(self):
        days = ("2026-10-05", "2026-10-07", "2026-10-09")
        for actuals in ((5000, 5000, 5000), (5100, 4900, 5200)):
            with self.subTest(actuals=actuals):
                self.set_records([plan(f"manual:p{i}", day, 5000) for i, day in enumerate(days)],
                                 [activity(f"manual:a{i}", day, meters) for i, (day, meters)
                                  in enumerate(zip(days, actuals))])
                rows = self.reconcile()
                self.assertEqual([(i["status"], i["planned_id"][-1], i["activity_id"][-1]) for i in rows],
                                 [("done", "0", "0"), ("done", "1", "1"), ("done", "2", "2")])
                self.assertTrue(all("date_proximity" in i["match_basis"] for i in rows))
                week = self.data("cardio", "week", "--week", "2026-W41")
                self.assertEqual({b["planned_id"] for b in week["bouts"] if b["kind"] == "run"},
                                 {"manual:p0", "manual:p1", "manual:p2"})
                self.assertEqual({b["srpe"]["method"] for b in week["bouts"] if b["kind"] == "run"}, {"planned"})

    def test_an_identical_easy_run_moved_a_day_still_matches(self):
        days = ("2026-10-05", "2026-10-07", "2026-10-09")
        self.set_records([plan(f"manual:p{i}", day, 5000) for i, day in enumerate(days)],
                         [activity("manual:a0", "2026-10-05", 5100), activity("manual:a1", "2026-10-08", 4900),
                          activity("manual:a2", "2026-10-09", 5200)])
        rows = {i["planned_id"]: (i["status"], i["activity_id"]) for i in self.reconcile()}
        self.assertEqual(rows, {"manual:p0": ("done", "manual:a0"), "manual:p1": ("moved", "manual:a1"),
                                "manual:p2": ("done", "manual:a2")})

    def test_a_training_plan_week_run_on_schedule_is_done_across_weeks(self):
        shape = ((1, 8000, True, 8150), (3, 6000, False, 6180), (4, 6000, False, 5820), (6, 16000, False, 15800))
        plans, acts = [], []
        for start in (dates.parse_date("2026-09-28"), dates.parse_date("2026-10-05")):
            for offset, target, quality, actual in shape:
                day = (start + timedelta(days=offset)).isoformat()
                plans.append(plan(f"manual:p-{day}", day, target, quality))
                acts.append(activity(f"manual:a-{day}", day, actual))
        self.set_records(plans, acts)
        for week in ("2026-W40", "2026-W41"):
            rows = self.data("cardio", "reconcile", "--week", week)["items"]
            self.assertEqual({i["status"] for i in rows}, {"done"})
            self.assertTrue(all(i["planned_id"][10:] == i["activity_id"][10:] for i in rows))

    def test_identical_plans_mid_week_leave_the_later_plan_upcoming(self):
        self.set_records([plan("manual:tue", "2026-10-06", 5000), plan("manual:thu", "2026-10-08", 5000)],
                         [activity("manual:a", "2026-10-06", 5100)])
        rows = self.coach("cardio", "reconcile", "--week", "2026-W41", now="2026-10-06T18:00:00Z")["data"]["items"]
        self.assertEqual([(i["status"], i["planned_id"], i["activity_id"]) for i in rows],
                         [("done", "manual:tue", "manual:a"), ("upcoming", "manual:thu", None)])

    def test_a_lone_moved_run_with_contradicting_effort_still_matches(self):
        cases = ((True, 10000, 6000, 5, -4000, False), (True, 10000, 10040, 6, 40, False),
                 (False, 6000, 6100, 8, 100, True))
        for quality, target, actual, rpe, delta, delivered in cases:
            with self.subTest(quality=quality, rpe=rpe):
                self.set_records([plan("manual:p", "2026-10-06", target, quality)],
                                 [activity("manual:a", "2026-10-07", actual, rpe=rpe)])
                [row] = self.reconcile()
                self.assertEqual((row["status"], row["delta"]["distance_meters"], row["quality"],
                                  row["quality_basis"]), ("moved", delta, delivered, "rpe"))

    def test_logged_effort_breaks_a_tie_between_plans_of_different_quality(self):
        self.set_records([plan("manual:p1", "2026-10-06", 10000, True), plan("manual:p2", "2026-10-07", 10000)],
                         [activity("manual:a1", "2026-10-06", 10000, rpe=8),
                          activity("manual:a2", "2026-10-07", 10000)])
        rows = {i["planned_id"]: (i["status"], i["activity_id"]) for i in self.reconcile()}
        self.assertEqual(rows, {"manual:p1": ("done", "manual:a1"), "manual:p2": ("done", "manual:a2")})
        p1 = next(i for i in self.reconcile() if i["planned_id"] == "manual:p1")
        self.assertIn("effort", p1["match_basis"])

    def test_ambiguous_plans_are_not_counted_beside_their_logged_candidate(self):
        from coach import config as config_module

        self.set_records([plan("manual:p1", "2026-10-06", 10000, True), plan("manual:p2", "2026-10-07", 10000)],
                         [activity("manual:a1", "2026-10-06", 10000), activity("manual:a2", "2026-10-07", 10000)])
        span = dates.parse_week("2026-W41", "monday")
        found = cardio.flag_bouts(self.root, config_module.load(self.root), span, dates.parse_date("2026-10-06"))
        self.assertEqual([(b.date.isoformat(), b.source, b.ref) for b in found if b.kind == "run"],
                         [("2026-10-06", "logged", "manual:a1")])

    def test_a_later_ambiguous_plan_still_counts_as_upcoming(self):
        from coach import config as config_module

        def runs(found):
            return [(b.date.isoformat(), b.source, b.ref, b.quality) for b in found if b.kind == "run"]

        self.set_records([plan("manual:easy", "2026-10-07", None, title="Easy", seconds=2400),
                          plan("manual:tempo", "2026-10-08", None, True, title="Tempo", seconds=2400)],
                         [activity("manual:a", "2026-10-07", None, 2460, name="Outdoor Run")])
        now = "2026-10-07T18:00:00Z"
        rows = self.coach("cardio", "reconcile", "--week", "2026-W41", now=now)["data"]["items"]
        self.assertEqual({i["status"] for i in rows}, {"ambiguous"})
        expected = [("2026-10-07", "logged", "manual:a", False), ("2026-10-08", "planned", "manual:tempo", True)]
        flags = self.coach("cardio", "flags", "--week", "2026-W41", now=now)["data"]
        self.assertEqual([(b["date"], b["source"], b["ref"], b["quality"]) for b in flags["bouts"]
                          if b["kind"] == "run"], expected)
        span, today = dates.parse_week("2026-W41", "monday"), dates.parse_date("2026-10-07")
        self.assertEqual(runs(cardio.flag_bouts(self.root, config_module.load(self.root), span, today)), expected)
        self.assertEqual(runs(cardio.bouts(self.root, span, "proposal", today=today)), expected[1:])

    def test_a_sunday_run_on_schedule_leaves_monday_quality_upcoming_next_week(self):
        from coach import config as config_module

        self.set_records([plan("manual:sun", "2026-10-11", 6000), plan("manual:mon", "2026-10-12", 6000, True)],
                         [activity("manual:a", "2026-10-11", 6000)])
        span, today = dates.parse_week("2026-W42", "monday"), dates.parse_date("2026-10-11")
        found = cardio.flag_bouts(self.root, config_module.load(self.root), span, today)
        self.assertEqual([(b.date.isoformat(), b.source, b.ref, b.quality) for b in found if b.kind == "run"],
                         [("2026-10-12", "planned", "manual:mon", True)])

    def test_a_tempo_planned_by_two_sources_and_run_on_the_day_counts_once_as_quality(self):
        from coach import config as config_module

        tempo = [dict(plan(f"{source}:t1", "2026-10-06", 8000, True, title="Tempo"), source=source)
                 for source in ("manual", "runna")]
        self.set_records(tempo, [activity("manual:r", "2026-10-06", 8050, name="Outdoor Run")])
        expected = [("done", "manual:t1", "manual:r", True, "planned"), ("duplicate", "runna:t1", None, True, None)]
        span = dates.parse_week("2026-W41", "monday")
        for now in (NOW, "2026-10-06T18:00:00Z"):
            with self.subTest(now=now):
                rows = self.coach("cardio", "reconcile", "--week", "2026-W41", now=now)["data"]["items"]
                self.assertEqual([(i["status"], i["planned_id"], i["activity_id"], i["quality"], i["quality_basis"])
                                  for i in rows], expected)
                self.assertIn("manual:t1", rows[1]["review_reason"])
                today = dates.parse_date(now[:10])
                found = cardio.flag_bouts(self.root, config_module.load(self.root), span, today)
                self.assertEqual([(b.source, b.ref, b.quality) for b in found if b.kind == "run"],
                                 [("logged", "manual:r", True)])
        week = self.data("cardio", "week", "--week", "2026-W41")
        bout = next(b for b in week["bouts"] if b["ref"] == "manual:r")
        self.assertEqual((week["run"]["quality"], bout["planned_id"], bout["srpe"]),
                         (1, "manual:t1", {"rpe": 7, "load": 210, "method": "planned"}))
        text = self.data("cardio", "render", "--week", "2026-W41")["text"]
        self.assertIn("runna:t1 duplicates manual:t1, planned by another source and matched.", text)
        self.assertNotIn("Review runna:t1", text)
        self.assertEqual(cardio.match(tempo, [activity("manual:r", "2026-10-06", 8050)], 3),
                         cardio.match(list(reversed(tempo)), [activity("manual:r", "2026-10-06", 8050)], 3))

    def test_a_tempo_planned_by_two_sources_with_titles_differing_only_in_case_counts_once(self):
        tempo = [dict(plan(f"{source}:t1", "2026-10-06", 8000, True, title=title), source=source)
                 for source, title in (("manual", "Tempo"), ("runna", " tempo"))]
        rows = cardio.match(tempo, [activity("manual:r", "2026-10-06", 8050)], 3)
        self.assertEqual([(i["status"], i["planned_id"]) for i in rows],
                         [("done", "manual:t1"), ("duplicate", "runna:t1")])

    def test_a_double_day_from_one_source_with_one_run_leaves_the_other_missed(self):
        plans = [plan("manual:am", "2026-10-06", 5000), plan("manual:pm", "2026-10-06", 5000)]
        rows = cardio.match(plans, [activity("manual:r", "2026-10-06", 5000)], 3)
        self.assertEqual([(i["status"], i["planned_id"], i["activity_id"]) for i in rows],
                         [("done", "manual:am", "manual:r"), ("missed", "manual:pm", None)])

    def flagged_runs(self, today="2026-10-11"):
        from coach import config as config_module

        span = dates.parse_week("2026-W41", "monday")
        found = cardio.flag_bouts(self.root, config_module.load(self.root), span, dates.parse_date(today))
        return [(b.ref, b.quality) for b in found if b.kind == "run"]

    def test_runs_an_equal_gap_from_two_plans_of_one_quality_take_the_earlier_plan(self):
        plans = [plan(f"manual:p{day}", f"2026-10-0{day}", 8000, True, "Intervals") for day in (5, 7)]
        cases = ((("6", "8"), {"manual:p5": ("moved", "manual:6"), "manual:p7": ("moved", "manual:8")}, 2),
                 (("6",), {"manual:p5": ("moved", "manual:6"), "manual:p7": ("missed", None)}, 1))
        for days, expected, quality in cases:
            with self.subTest(days=days):
                self.set_records(plans, [activity(f"manual:{d}", f"2026-10-0{d}", 8000, name="Outdoor Run")
                                         for d in days])
                rows = self.reconcile()
                self.assertEqual({i["planned_id"]: (i["status"], i["activity_id"]) for i in rows}, expected)
                self.assertEqual({i["quality_basis"] for i in rows if i["activity_id"]}, {"planned"})
                self.assertIn("order", rows[0]["match_basis"])
                self.assertEqual(self.data("cardio", "week", "--week", "2026-W41")["run"]["quality"], quality)
                self.assertEqual(self.flagged_runs(), [(f"manual:{d}", True) for d in days])

    def test_conditioning_an_equal_gap_from_two_planned_days_still_counts_the_bout(self):
        from coach import conditioning, config as config_module

        last = {"overlay_id": "o", "session_id": "circuit", "dates": ["2026-10-05", "2026-10-07"],
                "span": {"start": "2026-10-05", "end": "2026-10-11"}}
        for days in (("6",), ("6", "8")):
            with self.subTest(days=days):
                self.set_records([], [dict(activity(f"manual:{d}", f"2026-10-0{d}", None, 720, "Circuit", 6),
                                           kind="conditioning") for d in days])
                found = conditioning.bouts(self.root, config_module.load(self.root), last,
                                           dates.parse_date("2026-10-11"))
                self.assertEqual([b["activity_id"] for b in found], [f"manual:{d}" for d in reversed(days)])

    def test_a_double_day_of_identical_plans_pairs_in_start_order(self):
        cases = ((5000, False, "Easy"), (6000, True, "Threshold"))
        for meters, quality, title in cases:
            with self.subTest(title=title):
                self.set_records([plan(f"manual:{t}", "2026-10-06", meters, quality, title) for t in ("am", "pm")],
                                 [dict(activity(f"manual:{t}", "2026-10-06", meters), start=f"2026-10-06T{h}:00:00Z")
                                  for t, h in (("pm", "18"), ("am", "07"))])
                rows = self.reconcile()
                self.assertEqual([(i["status"], i["planned_id"], i["activity_id"], i["quality"], i["quality_basis"])
                                  for i in rows],
                                 [("done", "manual:am", "manual:am", quality, "planned"),
                                  ("done", "manual:pm", "manual:pm", quality, "planned")])
                self.assertEqual(rows[0]["match_basis"], ["order"])
                week = self.data("cardio", "week", "--week", "2026-W41")
                self.assertEqual(week["run"]["quality"], 2 if quality else 0)
                self.assertEqual({b["srpe"]["method"] for b in week["bouts"] if b["kind"] == "run"}, {"planned"})
                self.assertEqual(self.flagged_runs(), [("manual:am", quality), ("manual:pm", quality)])

    def test_a_shakeout_beside_a_tempo_planned_by_two_sources_stays_extra(self):
        tempo = [dict(plan(f"{source}:t1", "2026-10-06", 8000, True, title="Tempo"), source=source)
                 for source in ("manual", "runna")]
        self.set_records(tempo, [activity("manual:r", "2026-10-06", 8050),
                                 dict(activity("manual:s", "2026-10-06", 3000, 1200), start="2026-10-06T18:00:00Z")])
        rows = self.reconcile()
        self.assertEqual([(i["status"], i["planned_id"], i["activity_id"], i["quality"], i["quality_basis"])
                          for i in rows],
                         [("extra", None, "manual:s", False, "none"),
                          ("done", "manual:t1", "manual:r", True, "planned"),
                          ("duplicate", "runna:t1", None, True, None)])
        week = self.data("cardio", "week", "--week", "2026-W41")
        self.assertEqual(week["run"]["quality"], 1)
        self.assertEqual(self.flagged_runs(), [("manual:r", True), ("manual:s", False)])

    def test_a_conditioning_session_planned_by_two_sources_counts_once(self):
        plans = [dict(plan(f"{source}:c", "2026-10-06", None, quality, "Circuit"), source=source, kind="conditioning")
                 for source, quality in (("manual", False), ("runna", True))]
        rows = cardio.match(plans, [dict(activity("manual:a", "2026-10-06", None, 720), kind="conditioning")], 3)
        self.assertEqual([(i["status"], i["planned_id"]) for i in rows],
                         [("done", "manual:c"), ("duplicate", "runna:c")])

    def test_a_different_session_from_another_source_on_the_day_is_not_a_duplicate(self):
        easy = plan("manual:easy", "2026-10-06", 5000, title="Easy 5k")
        long_run = dict(plan("runna:long", "2026-10-06", 20000, title="Long Run"), source="runna")
        self.set_records([easy, long_run], [activity("manual:a", "2026-10-06", 5000)])
        rows = self.reconcile()
        self.assertEqual([(i["status"], i["planned_id"], i["activity_id"]) for i in rows],
                         [("done", "manual:easy", "manual:a"), ("missed", "runna:long", None)])
        self.assertCountEqual(self.flagged_runs(today="2026-10-06"), [("manual:a", False), ("runna:long", False)])
        for other in (dict(easy, target={"distance_meters": 5000, "duration_seconds": 1800}),
                      dict(easy, target={"distance_meters": 8000, "duration_seconds": None})):
            with self.subTest(target=other["target"]):
                rows = cardio.match([easy, dict(other, id="runna:easy", source="runna")],
                                    [activity("manual:a", "2026-10-06", 5000)], 3)
                self.assertEqual([i["status"] for i in rows], ["done", "missed"])

    def test_a_run_tied_between_different_quality_plans_stays_ambiguous_beside_another_source(self):
        tempo = dict(plan("runna:tempo", "2026-10-07", 20000, True, title="Tempo"), source="runna")
        long_run = dict(plan("runna:long", "2026-10-06", 20000, title="Long Run"), source="runna")
        self.set_records([plan("manual:easy", "2026-10-06", 5000, title="Easy 5k"), long_run, tempo],
                         [activity("manual:a", "2026-10-06", 5000),
                          activity("manual:b", "2026-10-07", 20000, 6000, name="Outdoor Run")])
        rows = self.reconcile()
        self.assertEqual([(i["status"], i["planned_id"], i["activity_id"], i["quality"]) for i in rows],
                         [("done", "manual:easy", "manual:a", False), ("ambiguous", "runna:long", None, False),
                          ("ambiguous", None, "manual:b", False), ("ambiguous", "runna:tempo", None, True)])

    def test_every_reconcile_row_has_one_shape(self):
        self.set_records([plan("manual:p", "2026-10-06", 5000), plan("manual:q", "2026-10-10", 5000, True)],
                         [activity("manual:a", "2026-10-06", 5000)])
        rows = self.reconcile()
        self.assertEqual(len({tuple(sorted(i)) for i in rows}), 1)
        self.assertEqual([(i["status"], i["quality_basis"]) for i in rows], [("done", "planned"), ("missed", None)])

    def test_associate_rejections_write_nothing(self):
        self.set_records([plan("manual:p", "2026-10-06", 10000), plan("manual:far", "2026-10-11", 10000),
                          dict(plan("manual:ride", "2026-10-06", None), kind="ride"),
                          plan("manual:taken", "2026-10-07", 10000)],
                         [activity("manual:a", "2026-10-06", 10000), activity("manual:b", "2026-10-07", 10000)])
        self.data("cardio", "associate", "manual:b", "--planned-id", "manual:taken")
        path = self.root / paths.ACTIVITY_ASSOCIATIONS
        before = path.read_bytes()
        cases = ((("manual:a", "--planned-id", "manual:ride"), 1, "same kind within reconcile_move_days"),
                 (("manual:a", "--planned-id", "manual:far"), 1, "same kind within reconcile_move_days"),
                 (("manual:missing", "--planned-id", "manual:p"), 1, "live activity ID and a live planned ID"),
                 (("manual:a", "--planned-id", "manual:missing"), 1, "live activity ID and a live planned ID"),
                 (("manual:a", "--planned-id", "manual:taken"), 1, "planned ID already associated"),
                 (("manual:a", "--clear"), 1, "no association for activity 'manual:a'"),
                 (("manual:a",), 2, "give --planned-id or --clear"),
                 (("manual:a", "--planned-id", "manual:p", "--clear"), 2, "give --planned-id or --clear"))
        for argv, code, message in cases:
            with self.subTest(argv=argv):
                envelope = self.coach("cardio", "associate", *argv, expect=code)
                self.assertIn(message, json.dumps(envelope))
                self.assertEqual(path.read_bytes(), before)
