"""Activity identity regressions across reconciliation, persisted corrections and rendered records."""

import json

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
        self.assertTrue(any(r["status"] == "fail" and r["path"] == paths.ACTIVITY_ASSOCIATIONS.as_posix()
                            for r in result["data"]["results"]))

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
        from tests.test_interference import PLUGIN_TEST, custom_rule

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
