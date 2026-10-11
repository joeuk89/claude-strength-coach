"""Structure accounting: dose targets, the week table, trailing adherence, static balance and decisions (contract C40, C41)."""

import copy
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from coach import decisions, flags, jsonio, migrate, program, stats, structure
from coach.library import MUSCLES, Library
from tests.support import INSTANCES, VALID, run_cli
from tests.support.history import read_json, write_json

DOSE = INSTANCES / "dose"
NOW = "2026-10-11T18:00:00Z"
R_C = "00000000-0000-4000-8000-0000000000c9"
CODES = {
    "adherence_low": (("warn",), False),
    "add_session_type_blocked": (("warn",), True),
    "restructure_required": (("warn",), True),
    "volume_undershoot": (("warn",), True),
    "session_volume_high": (("warn", "info"), True),
}


def codes(found):
    return [f["code"] for f in found]


class StructureCase(unittest.TestCase):
    """A temp copy of a fixture instance (dose/ by default) and the coach CLI against it."""

    base = DOSE

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def data(self, *argv, now=NOW):
        return self.coach(*argv, now=now)["data"]

    def edit(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)

    def annotate(self, **fields):
        def add(doc):
            number = max(int(a["id"][2:]) for a in doc["annotations"]) + 1
            doc["annotations"].append(dict({"id": f"a-{number:04d}", "created_at": NOW, "source": "test",
                                            "reason": None}, **fields))
        self.edit("data/history/annotations.json", add)

    def annotation_id(self, **match):
        doc = read_json(self.root / "data/history/annotations.json")
        return next(a["id"] for a in doc["annotations"] if all(a.get(k) == v for k, v in match.items()))

    def make_kind(self, week_start, kind):
        """Turn the weekly overlay starting `week_start` into one of `kind`."""
        old = self.root / "data" / "overlays" / f"{week_start}-weekly.json"
        doc = read_json(old)
        doc["kind"] = kind
        doc["id"] = f"{week_start}-{kind.replace('_', '-')}"
        old.unlink()
        write_json(self.root / "data" / "overlays" / f"{doc['id']}.json", doc)

    def write_minimum_plan(self, week_start):
        write_json(self.root / structure.minimum_plan_path(week_start), {"variant": "minimum"})

    def drop_workouts(self, start, end):
        for path in (self.root / "data" / "history").glob("2026-*.json"):
            doc = read_json(path)
            doc["workouts"] = [w for w in doc["workouts"] if not start <= w["date"] <= end]
            write_json(path, doc)

    def adherence(self, *argv, now=NOW):
        return self.data("structure", "adherence", *argv, now=now)

    def write_decisions(self, *entries):
        doc = decisions.empty()
        for index, entry in enumerate(entries, start=1):
            doc["decisions"].append(dict({
                "id": f"d-{index:04d}", "kind": "adherence_trigger", "overlay_id": None, "scope": {},
                "standing": False, "until": None, "revisit_on": None, "proposed_sets": None, "chosen_sets": None,
                "status": "active", "closed_at": None, "closed_reason": None,
                "details": {"rule": "restructure", "adherence_pct": 58, "weeks": ["2026-09-14"]}}, **entry))
        write_json(self.root / "data" / "decisions.json", doc)


class TargetsTest(unittest.TestCase):
    def setUp(self):
        self.doc = program.load(VALID)
        self.library = Library.load(VALID)

    def test_primary_muscles_of_core_exercises_default_to_10(self):
        self.assertEqual(structure.targets(self.doc, self.library),
                         {"chest": 10, "glutes": 10, "lats": 10, "quadriceps": 10, "upper_back": 10})

    def test_a_declared_target_wins_and_adds_a_muscle(self):
        self.doc["dose_targets"] = {"chest": 14, "calves": 6}
        found = structure.targets(self.doc, self.library)
        self.assertEqual((found["chest"], found["calves"], found["lats"]), (14, 6, 10))

    def test_optional_and_parked_sessions_give_no_default(self):
        self.doc["sessions"][1]["tier"] = "optional"
        self.doc["sessions"][0]["status"] = "parked"
        self.assertEqual(structure.targets(self.doc, self.library), {})


class SessionDoseTest(unittest.TestCase):
    def test_set_groups_and_overlay_sets_count_hard_working_sets_only(self):
        library = Library.load(VALID)
        groups = {"exercises": [{"exercise_id": "db_bench_press", "sets": [
            {"count": 1, "type": "warmup", "reps": 10}, {"count": 3, "type": "normal", "reps": 8, "rpe": 8},
            {"count": 2, "type": "normal", "reps": 15, "rpe": 5}]}]}
        listed = {"exercises": [{"exercise_id": "db_bench_press", "sets": [
            {"type": "warmup", "reps": 10}] + [{"type": "normal", "reps": 8, "rpe": 8}] * 3}]}
        expected = {"chest": 3.0, "triceps": 1.5, "front_delts": 1.5}
        self.assertEqual(structure.session_dose(library, groups), expected)
        self.assertEqual(structure.session_dose(library, listed), expected)


class AdherenceTest(StructureCase):
    def test_the_dose_fixture_is_58_percent_over_w38_to_w41(self):
        data = self.adherence()
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W38", "2026-W39", "2026-W40", "2026-W41"])
        self.assertEqual((data["planned"], data["trained"], data["pct"]), (12, 7, 58))
        self.assertFalse(data["insufficient_weeks"])
        for code in ("adherence_low", "add_session_type_blocked", "restructure_required"):
            self.assertIn(code, codes(data["flags"]))
        self.assertIsNone(data["decision"])

    def test_each_weeks_count_matches_the_fixture_table(self):
        data = self.adherence("--until", "2026-09-27")
        self.assertEqual([(w["label"], w["trained"]) for w in data["weeks"]],
                         [("2026-W36", 3), ("2026-W37", 3), ("2026-W38", 1), ("2026-W39", 2)])

    def test_training_w38s_missed_sessions_lifts_it_past_the_70_percent_line(self):
        self.annotate(kind="trained_unlogged", date="2026-09-17", session_id="session-b", note="hotel gym")
        data = self.adherence()
        self.assertEqual((data["trained"], data["planned"], data["pct"]), (8, 12, 67))
        self.assertIn("restructure_required", codes(data["flags"]))
        self.annotate(kind="external", date="2026-09-15", external_id="pt-tue", done=True, note="moved, not missed")
        data = self.adherence()
        self.assertEqual((data["trained"], data["planned"], data["pct"]), (9, 12, 75))
        self.assertNotIn("adherence_low", codes(data["flags"]))
        self.assertNotIn("restructure_required", codes(data["flags"]))
        self.assertIn("add_session_type_blocked", codes(data["flags"]))

    def test_a_deload_week_is_skipped_and_the_window_reaches_back(self):
        self.make_kind("2026-09-28", "deload")
        data = self.adherence()
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W37", "2026-W38", "2026-W39", "2026-W41"])
        self.assertEqual(data["skipped"], [{"week": "2026-09-28", "label": "2026-W40", "kind": "light"}])
        self.assertEqual((data["trained"], data["planned"]), (8, 12))

    def test_a_one_off_week_and_an_adopted_light_week_are_skipped(self):
        self.make_kind("2026-09-28", "one_off")
        self.write_decisions({"kind": "light_week", "made_at": "2026-09-13T18:00:00Z", "outcome": "adopted",
                              "reason": "ceiling", "details": {"type": "light", "week": "2026-09-21",
                                                              "reason": "ceiling", "triggers": [], "hard_weeks": 6}})
        data = self.adherence()
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W36", "2026-W37", "2026-W38", "2026-W41"])
        self.assertEqual({s["label"]: s["kind"] for s in data["skipped"]}, {"2026-W39": "light", "2026-W40": "one_off"})

    def test_a_minimum_week_is_skipped(self):
        self.write_minimum_plan("2026-09-28")
        data = self.adherence()
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W37", "2026-W38", "2026-W39", "2026-W41"])
        self.assertEqual(data["skipped"], [{"week": "2026-09-28", "label": "2026-W40", "kind": "minimum"}])
        self.assertEqual(structure.ordinary_weeks(self.root, date(2026, 10, 11), today=date(2026, 10, 11)),
                         ["2026-09-07", "2026-09-14", "2026-09-21", "2026-10-05"])

    def test_two_weeks_without_training_are_a_layoff(self):
        self.drop_workouts("2026-09-21", "2026-10-04")
        self.annotate(kind="external", date="2026-09-22", external_id="pt-tue", done=False, note="away")
        data = self.adherence()
        self.assertEqual([w["label"] for w in data["weeks"]], ["2026-W36", "2026-W37", "2026-W38", "2026-W41"])
        self.assertEqual({s["label"]: s["kind"] for s in data["skipped"]}, {"2026-W39": "layoff", "2026-W40": "layoff"})
        self.assertEqual((data["trained"], data["planned"]), (9, 12))

    def test_a_missed_week_inside_a_shorter_gap_still_counts(self):
        activity = [date(2026, 9, 27), date(2026, 10, 6)]
        week = structure.dates.Span(date(2026, 9, 28), date(2026, 10, 4))
        self.assertFalse(structure._in_layoff(week, activity, date(2026, 10, 11)))
        self.assertTrue(structure._in_layoff(week, [date(2026, 9, 26), date(2026, 10, 7)], date(2026, 10, 11)))

    def test_three_ordinary_weeks_raise_no_adherence_flag(self):
        for start in ("2026-08-31", "2026-09-07", "2026-09-14"):
            self.make_kind(start, "deload")
        data = self.adherence()
        self.assertTrue(data["insufficient_weeks"])
        self.assertEqual(len(data["weeks"]), 3)
        self.assertEqual(data["flags"], [])

    def test_ordinary_weeks_lists_start_dates_oldest_first(self):
        found = structure.ordinary_weeks(self.root, date(2026, 10, 11), today=date(2026, 10, 11))
        self.assertEqual(found, ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"])
        self.assertEqual(structure.ordinary_weeks(self.root, date(2026, 10, 10), n=2, today=date(2026, 10, 11)),
                         ["2026-09-21", "2026-09-28"])

    def test_a_week_still_running_is_not_counted(self):
        data = self.adherence(now="2026-10-08T12:00:00Z")
        self.assertEqual(data["weeks"][-1]["label"], "2026-W40")

    def test_delivered_undershoot_names_the_muscles_short_in_three_of_four_weeks(self):
        found = [f for f in self.adherence()["flags"] if f["code"] == "volume_undershoot"]
        self.assertTrue(found)
        chest = next(f for f in found if f["message"].startswith("chest:"))
        self.assertIn("delivered", chest["message"])
        self.assertIn("4 of the last 4 ordinary weeks", chest["message"])


class OptionalSessionTest(StructureCase):
    def setUp(self):
        super().setUp()

        def add_session(doc):
            extra = copy.deepcopy(doc["sessions"][1])
            extra.update(id="session-c", title="Session C", tier="optional")
            doc["sessions"].append(extra)
        self.edit("data/program.json", add_session)
        self.edit("data/state.json", lambda doc: doc["hevy"]["routines"].update({R_C: {"session_id": "session-c"}}))

        def plan_it(doc):
            extra = copy.deepcopy(doc["sessions"][1])
            extra.update(session_id="session-c", date="2026-10-10", title="Session C", hevy_routine_id=R_C)
            doc["sessions"].append(extra)
        self.edit("data/overlays/2026-10-05-weekly.json", plan_it)

    def log_session_c(self):
        def add(doc):
            workout = copy.deepcopy(next(w for w in doc["workouts"] if w["title"] == "Session B"))
            workout.update(workout_id="10000000-0000-4000-8000-0000000003c1", date="2026-10-10", routine_id=R_C,
                           title="Session C", session_id="session-c", start_time="2026-10-10T18:00:00Z",
                           end_time="2026-10-10T19:00:00Z")
            doc["workouts"].append(workout)
        self.edit("data/history/2026-10.json", add)

    def test_an_untrained_optional_session_changes_neither_count(self):
        data = self.adherence()
        self.assertEqual((data["planned"], data["trained"]), (12, 7))
        week = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual((week["planned"], week["trained"]), (3, 2))
        row = next(s for s in week["sessions"] if s.get("session_id") == "session-c")
        self.assertEqual(row["tier"], "optional")

    def test_training_it_adds_its_sets_to_bonus_only(self):
        before = self.data("structure", "week", "--week", "2026-W41")
        self.log_session_c()
        after = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual((after["planned"], after["trained"]), (3, 2))
        self.assertEqual((self.adherence()["planned"], self.adherence()["trained"]), (12, 7))
        self.assertEqual(after["muscles"]["lats"]["bonus"], 6)
        self.assertEqual(after["muscles"]["upper_back"]["bonus"], 4.5)
        for muscle, row in after["muscles"].items():
            with self.subTest(muscle=muscle):
                self.assertEqual(row["delivered"], before["muscles"][muscle]["delivered"])
                self.assertEqual(row["planned"], before["muscles"][muscle]["planned"])
        self.assertIn("session-c", after["by_session"])


class WeekTest(StructureCase):
    def test_w41_lists_pt_done_with_its_estimate_in_delivered(self):
        data = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual((data["week"], data["kind"], data["planned"], data["trained"]),
                         ("2026-10-05", "ordinary", 3, 2))
        pt = next(s for s in data["sessions"] if s.get("external_id") == "pt-tue")
        self.assertEqual((pt["date"], pt["status"]), ("2026-10-06", "done"))
        self.assertEqual(pt["estimated_sets"], {"chest": 3.0, "lats": 3.0})
        self.assertEqual(data["muscles"]["chest"], {"target": 10, "planned": 6, "delivered": 6, "bonus": 0})
        self.assertEqual(data["muscles"]["lats"]["delivered"], 3)
        missed = next(s for s in data["sessions"] if s.get("session_id") == "session-b")
        self.assertEqual((missed["status"], missed["tag"]), ("missed", "sleep"))

    def test_without_its_annotation_pt_is_unconfirmed_and_counts_nowhere(self):
        self.annotate(kind="external", withdraws=self.annotation_id(kind="external", date="2026-10-06"))
        data = self.data("structure", "week", "--week", "2026-W41")
        pt = next(s for s in data["sessions"] if s.get("external_id") == "pt-tue")
        self.assertEqual(pt["status"], "unconfirmed")
        self.assertEqual((data["planned"], data["trained"]), (2, 1))
        self.assertEqual(data["muscles"]["chest"]["planned"], 3)
        self.assertEqual(data["muscles"]["chest"]["delivered"], 3)
        self.assertEqual(data["muscles"]["lats"]["delivered"], 0)

    def test_a_week_with_a_minimum_plan_is_a_minimum_week(self):
        self.write_minimum_plan("2026-10-05")
        self.assertEqual(self.data("structure", "week", "--week", "2026-W41")["kind"], "minimum")
        self.assertEqual(self.data("structure", "week", "--week", "2026-W40")["kind"], "ordinary")

    def test_light_wins_over_a_minimum_plan_and_a_minimum_plan_over_one_off(self):
        self.make_kind("2026-09-21", "deload")
        self.make_kind("2026-09-28", "one_off")
        for start in ("2026-09-21", "2026-09-28"):
            self.write_minimum_plan(start)
        self.assertEqual(self.data("structure", "week", "--week", "2026-W39")["kind"], "light")
        self.assertEqual(self.data("structure", "week", "--week", "2026-W40")["kind"], "minimum")

    def test_by_session_holds_each_logged_session(self):
        data = self.data("structure", "week", "--week", "2026-W40")
        self.assertEqual(data["by_session"]["session-a"]["chest"], 3)
        self.assertEqual(data["by_session"]["session-b"]["lats"], 6)
        self.assertEqual(data["flags"], [])

    def test_a_week_with_no_overlay_is_planned_from_the_schedule_rule(self):
        (self.root / "data" / "overlays" / "2026-09-28-weekly.json").unlink()
        data = self.data("structure", "week", "--week", "2026-W40")
        self.assertEqual([(s.get("session_id"), s["date"], s["status"]) for s in data["sessions"]],
                         [("session-a", "2026-09-28", "trained"), (None, "2026-09-29", "not_done"),
                          ("session-b", "2026-10-01", "trained")])
        self.assertIsNone(data["sessions"][0]["overlay_id"])
        self.assertEqual((data["planned"], data["trained"]), (3, 2))

    def test_a_logged_session_over_11_sets_for_a_muscle_is_flagged_info(self):
        def heavy(doc):
            workout = next(w for w in doc["workouts"] if w["date"] == "2026-10-05")
            bench = next(e for e in workout["exercises"] if e["exercise_id"] == "db_bench_press")
            first = bench["sets"][0]
            bench["sets"] = [dict(first, index=i) for i in range(12)]
        self.edit("data/history/2026-10.json", heavy)
        data = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual([(f["code"], f["severity"], f["session_id"]) for f in data["flags"]],
                         [("session_volume_high", "info", "session-a")])


    def test_a_planned_overlay_session_over_11_sets_for_a_muscle_is_flagged_warn(self):
        def bench_sets(count):
            def change(doc):
                session = next(s for s in doc["sessions"] if s["session_id"] == "session-a")
                bench = next(e for e in session["exercises"] if e["exercise_id"] == "db_bench_press")
                working = next(s for s in bench["sets"] if s["type"] == "normal")
                bench["sets"] = [dict(working) for _ in range(count)]
            return change

        self.edit("data/overlays/2026-10-05-weekly.json", bench_sets(12))
        data = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual([(f["code"], f["severity"], f["session_id"]) for f in data["flags"]],
                         [("session_volume_high", "warn", "session-a")])
        self.edit("data/overlays/2026-10-05-weekly.json", bench_sets(11))
        self.assertEqual(self.data("structure", "week", "--week", "2026-W41")["flags"], [])

class PlannedEqualsDeliveredTest(StructureCase):
    def test_the_same_sets_give_the_same_dose_through_set_weights(self):
        overlay_doc = read_json(self.root / "data" / "overlays" / "2026-10-05-weekly.json")
        planned_session = next(s for s in overlay_doc["sessions"] if s["session_id"] == "session-a")

        def match_overlay(doc):
            workout = next(w for w in doc["workouts"] if w["date"] == "2026-10-05")
            for exercise in workout["exercises"]:
                line = next(e for e in planned_session["exercises"] if e["exercise_id"] == exercise["exercise_id"])
                template = exercise["sets"][0]
                exercise["sets"] = [dict(template, index=i, type=s["type"], rpe=s.get("rpe"))
                                    for i, s in enumerate(line["sets"])]
        self.edit("data/history/2026-10.json", match_overlay)
        calls = []
        real = stats.set_weights

        def counting(entry):
            calls.append(entry["id"])
            return real(entry)

        with mock.patch.object(stats, "set_weights", side_effect=counting):
            planned = structure.planned_dose(self.root, [planned_session])
            planned_calls = list(calls)
            delivered = structure.week(self.root, date(2026, 10, 5), now=structure.dates.parse_timestamp(NOW))
        self.assertEqual(delivered["by_session"]["session-a"], planned)
        self.assertEqual(sorted(planned_calls), ["bb_back_squat", "db_bench_press"])
        self.assertGreater(len(calls), len(planned_calls))


class DecideTest(StructureCase):
    def test_declined_appends_one_decision_and_prints_the_line(self):
        data = self.data("structure", "decide", "--rule", "restructure", "--outcome", "declined",
                         "--reason", "busy month")
        self.assertEqual(data["line"], "Adherence trigger: 58 % over 4 weeks: declined: busy month")
        stored = read_json(self.root / "data" / "decisions.json")["decisions"]
        self.assertEqual(len(stored), 1)
        self.assertEqual((stored[0]["kind"], stored[0]["outcome"], stored[0]["details"]["adherence_pct"],
                          stored[0]["details"]["rule"]), ("adherence_trigger", "declined", 58, "restructure"))
        self.assertEqual(stored[0]["details"]["weeks"], ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"])
        self.assertEqual(self.coach("check", "--only", "decisions_schema")["data"]["summary"]["fail"], 0)
        after = self.adherence()
        self.assertNotIn("restructure_required", codes(after["flags"]))
        self.assertIn("adherence_low", codes(after["flags"]))
        self.assertEqual(after["decision"]["id"], stored[0]["id"])

    def test_made_at_is_stored_in_utc_when_the_clock_has_an_offset(self):
        self.data("structure", "decide", "--rule", "restructure", "--outcome", "adopted",
                  now="2026-10-11T20:00:00+02:00")
        stored = read_json(self.root / "data" / "decisions.json")["decisions"]
        self.assertEqual(stored[0]["made_at"], "2026-10-11T18:00:00Z")

    def test_declined_holds_until_four_ordinary_weeks_close_after_it(self):
        self.write_decisions({"made_at": "2026-09-20T18:00:00Z", "outcome": "declined", "reason": "busy month"})
        self.assertNotIn("restructure_required", codes(self.adherence()["flags"]))
        self.write_decisions({"made_at": "2026-09-13T18:00:00Z", "outcome": "declined", "reason": "busy month"})
        self.assertIn("restructure_required", codes(self.adherence()["flags"]))

    def test_a_skipped_week_does_not_count_toward_the_four(self):
        self.write_decisions({"made_at": "2026-09-13T18:00:00Z", "outcome": "declined", "reason": "busy month"})
        self.make_kind("2026-09-28", "deload")
        self.assertNotIn("restructure_required", codes(self.adherence()["flags"]))

    def test_deferred_holds_until_its_revisit_date(self):
        data = self.data("structure", "decide", "--rule", "restructure", "--outcome", "deferred",
                         "--revisit", "2026-11-02")
        self.assertEqual(data["line"], "Adherence trigger: 58 % over 4 weeks: deferred to 2026-11-02")
        self.assertEqual(data["decision"]["revisit_on"], "2026-11-02")
        self.assertNotIn("restructure_required", codes(self.adherence()["flags"]))
        self.assertNotIn("restructure_required", codes(self.adherence("--until", "2026-11-01")["flags"]))
        self.assertIn("restructure_required", codes(self.adherence("--until", "2026-11-02")["flags"]))

    def test_adopted_holds_for_four_ordinary_weeks(self):
        self.write_decisions({"made_at": "2026-09-20T18:00:00Z", "outcome": "adopted", "reason": "fewer days"})
        self.assertNotIn("restructure_required", codes(self.adherence()["flags"]))
        self.write_decisions({"made_at": "2026-09-13T18:00:00Z", "outcome": "adopted", "reason": "fewer days"})
        self.assertIn("restructure_required", codes(self.adherence()["flags"]))

    def test_a_withdrawn_decision_suppresses_nothing(self):
        self.write_decisions({"made_at": "2026-10-11T18:00:00Z", "outcome": "declined", "reason": "busy month",
                              "status": "withdrawn", "closed_at": "2026-10-11T19:00:00Z", "closed_reason": "x"})
        self.assertIn("restructure_required", codes(self.adherence()["flags"]))

    def test_dry_run_writes_nothing(self):
        data = self.data("structure", "decide", "--rule", "restructure", "--outcome", "adopted", "--dry-run")
        self.assertEqual(data["line"], "Adherence trigger: 58 % over 4 weeks: adopted")
        self.assertFalse(data["written"])
        self.assertFalse((self.root / "data" / "decisions.json").exists())

    def test_refusals(self):
        cases = [
            (("--rule", "restructure", "--outcome", "declined"), "why"),
            (("--rule", "restructure", "--outcome", "deferred"), "--revisit"),
            (("--rule", "restructure", "--outcome", "deferred", "--revisit", "2026-10-11"), "after today"),
            (("--rule", "restructure", "--outcome", "adopted", "--revisit", "2026-11-02"), "deferred"),
            (("--rule", "add_session", "--outcome", "declined", "--reason", "x"), "adopted"),
            (("--rule", "add_session", "--outcome", "adopted"), "name the session"),
        ]
        for argv, text in cases:
            with self.subTest(argv=argv):
                envelope = self.coach("structure", "decide", *argv, expect=1)
                self.assertIn(text, envelope["error"]["message"])
        self.assertFalse((self.root / "data" / "decisions.json").exists())

    def test_no_restructure_decision_above_70_percent(self):
        self.annotate(kind="trained_unlogged", date="2026-09-17", session_id="session-b", note="hotel gym")
        self.annotate(kind="external", date="2026-09-15", external_id="pt-tue", done=True, note="moved")
        envelope = self.coach("structure", "decide", "--rule", "restructure", "--outcome", "adopted", expect=1)
        self.assertIn("75 %", envelope["error"]["message"])

    def test_no_decision_without_four_ordinary_weeks(self):
        for start in ("2026-08-31", "2026-09-07", "2026-09-14"):
            self.make_kind(start, "deload")
        envelope = self.coach("structure", "decide", "--rule", "restructure", "--outcome", "adopted", expect=1)
        self.assertIn("no adherence figure", envelope["error"]["message"])

    def test_the_line_shape_for_each_outcome(self):
        line = structure.decision_line
        self.assertEqual(line(76, 4, "add_session", "adopted", "adds Sat conditioning", None),
                         "Adherence trigger: 76 % over 4 weeks: adopted (override: adds Sat conditioning)")
        self.assertEqual(line(58, 4, "restructure", "adopted", "fewer days", None),
                         "Adherence trigger: 58 % over 4 weeks: adopted")


def conditioning_session():
    return {"id": "conditioning-sat", "title": "Conditioning", "kind": "conditioning", "tier": "optional",
            "status": "active", "location": None, "focus": None, "exercises": [{
                "exercise_id": "kb_swing", "load_mode": "single_implement",
                "sets": [{"count": 3, "type": "normal", "reps": 15, "rpe": 7}], "rest_seconds": 60,
                "superset_id": None, "cues": None, "constraints": [], "scheme": {"name": "hold", "params": {}},
                "start_load": 16}]}


class BalanceTest(StructureCase):
    base = VALID

    def add_pt(self, chest):
        def change(doc):
            doc["dose_targets"] = {"chest": 10}
            doc["external_sessions"] = [{"id": "pt-tue", "title": "PT", "weekday": "tue",
                                         "estimated_sets": {"chest": chest}}]
        self.edit("data/program.json", change)

    def test_chest_undershoots_on_bench_plus_pt_and_passes_when_pt_carries_more(self):
        self.add_pt(3)
        data = self.data("structure", "balance")
        self.assertEqual(data["muscles"]["chest"], {"target": 10, "average": 6, "met": False})
        chest = [f for f in data["flags"] if f["code"] == "volume_undershoot" and f["message"].startswith("chest:")]
        self.assertEqual(len(chest), 1)
        self.assertIn("planned 6", chest[0]["message"])
        self.add_pt(7)
        data = self.data("structure", "balance")
        self.assertEqual(data["muscles"]["chest"], {"target": 10, "average": 10, "met": True})
        self.assertFalse([f for f in data["flags"] if f["message"].startswith("chest:")])

    def test_a_target_set_at_what_is_planned_passes(self):
        self.edit("data/program.json", lambda doc: doc.update(dose_targets={
            "chest": 3, "quadriceps": 3, "glutes": 3, "lats": 6, "upper_back": 4.5}))
        data = self.data("structure", "balance")
        self.assertEqual(data["flags"], [])
        self.assertEqual(self.coach("check", "--only", "program_balance")["data"]["results"][0]["status"], "pass")

    def test_the_check_warns_on_each_undershoot(self):
        rows = self.coach("check", "--only", "program_balance")["data"]["results"]
        self.assertEqual({r["status"] for r in rows}, {"warn"})
        self.assertTrue(any(r["message"].startswith("volume_undershoot: chest:") for r in rows))

    def set_chest_sets(self, count):
        def change(doc):
            doc["sessions"][0]["exercises"].append({
                "exercise_id": "machine_chest_press", "load_mode": "total",
                "sets": [{"count": count, "type": "normal", "reps": 10, "rpe": 8}], "rest_seconds": 90,
                "superset_id": None, "cues": None, "constraints": [], "scheme": {"name": "hold", "params": {}},
                "start_load": 40})
        self.edit("data/program.json", change)

    def test_a_session_over_11_fractional_sets_for_a_muscle_warns(self):
        self.set_chest_sets(9)
        found = [f for f in self.data("structure", "balance")["flags"] if f["code"] == "session_volume_high"]
        self.assertEqual([(f["severity"], f["session_id"]) for f in found], [("warn", "session-a")])
        self.assertIn("chest 12", found[0]["message"])

    def test_exactly_11_fractional_sets_does_not(self):
        self.set_chest_sets(8)
        data = self.data("structure", "balance")
        self.assertEqual(data["by_session"]["session-a"]["chest"], 11)
        self.assertNotIn("session_volume_high", codes(data["flags"]))

    def test_an_alternating_rule_averages_its_positions(self):
        def change(doc):
            doc["schedule"] = {"rule": "alternating_external_anchor", "params": {"weeks": [
                {"name": "week-a", "days": {"mon": "session-a", "thu": "session-b"}},
                {"name": "week-b", "days": {"mon": "session-a", "wed": "session-b", "fri": "session-a"}}]}}
        self.edit("data/program.json", change)
        data = self.data("structure", "balance")
        self.assertEqual([p["position"] for p in data["positions"]], ["week-a", "week-b"])
        self.assertEqual([p["muscles"]["chest"] for p in data["positions"]], [3, 6])
        self.assertEqual(data["average"]["chest"], 4.5)


class CandidateBalanceTest(StructureCase):
    def candidate(self, change):
        doc = read_json(self.root / "data" / "program.json")
        change(doc)
        path = self.root / "candidate.json"
        write_json(path, doc)
        return str(path)

    def test_a_new_session_under_80_percent_is_blocked_until_an_override(self):
        path = self.candidate(lambda doc: doc["sessions"].append(conditioning_session()))
        data = self.data("structure", "balance", "--program", path)
        self.assertEqual(data["added"], ["conditioning-sat"])
        self.assertEqual(data["adherence"]["pct"], 58)
        blocked = [f for f in data["flags"] if f["code"] == "add_session_type_blocked"]
        self.assertEqual([f["session_id"] for f in blocked], ["conditioning-sat"])
        decided = self.data("structure", "decide", "--rule", "add_session", "--outcome", "adopted",
                            "--reason", "athlete wants it")
        self.assertEqual(decided["line"], "Adherence trigger: 58 % over 4 weeks: adopted (override: athlete wants it)")
        data = self.data("structure", "balance", "--program", path)
        self.assertNotIn("add_session_type_blocked", codes(data["flags"]))

    def test_the_override_lapses_after_28_days(self):
        self.data("structure", "decide", "--rule", "add_session", "--outcome", "adopted", "--reason", "Sat conditioning")
        path = self.candidate(lambda doc: doc["sessions"].append(conditioning_session()))
        later = self.data("structure", "balance", "--program", path, now="2026-11-09T18:00:00Z")
        self.assertIn("add_session_type_blocked", codes(later["flags"]))

    def test_a_new_coach_led_session_counts_and_a_swap_does_not(self):
        path = self.candidate(lambda doc: doc["external_sessions"].append(
            {"id": "class-sat", "title": "Class", "weekday": "sat", "estimated_sets": {"quadriceps": 3}}))
        self.assertIn("add_session_type_blocked", codes(self.data("structure", "balance", "--program", path)["flags"]))

        def swap(doc):
            doc["sessions"][0]["exercises"][1]["exercise_id"] = "bb_bench_press"
            doc["sessions"][0]["exercises"][1]["load_mode"] = "total"
        path = self.candidate(swap)
        data = self.data("structure", "balance", "--program", path)
        self.assertEqual(data["added"], [])
        self.assertNotIn("add_session_type_blocked", codes(data["flags"]))

    def test_an_invalid_candidate_exits_1(self):
        path = self.candidate(lambda doc: doc.update(dose_targets={"pecs": 10}))
        envelope = self.coach("structure", "balance", "--program", path, expect=1)
        self.assertTrue(any("pecs" in d["path"] + d["message"] for d in envelope["error"]["details"]))


class ProgramDoseTargetsTest(StructureCase):
    base = VALID

    def validate(self, targets):
        self.edit("data/program.json", lambda doc: doc.update(dose_targets=targets))
        return run_cli(["--root", str(self.root), "program", "validate"])

    def test_a_key_that_is_not_a_muscle_and_a_value_over_40_are_rejected(self):
        for targets, path in (({"pecs": 10}, "$.dose_targets.pecs"), ({"chest": 41}, "$.dose_targets.chest")):
            with self.subTest(targets=targets):
                code, envelope, _ = self.validate(targets)
                self.assertEqual(code, 1, envelope)
                self.assertIn(path, [d["path"] for d in envelope["error"]["details"]])
        code, envelope, _ = self.validate({"chest": 40, "calves": 0, "lats": 12.5})
        self.assertEqual(code, 0, envelope)

    def test_the_schema_lists_every_library_muscle(self):
        schema = jsonio.load_schema("program")
        self.assertEqual(tuple(schema["$defs"]["dose_targets"]["properties"]), MUSCLES)

    def test_migrate_run_adds_empty_targets_to_the_version_before_them(self):
        current = jsonio.current_version(jsonio.load_schema("program"))
        [step] = [s for s in migrate.registry().documents["program"].steps if s.name.endswith("_dose_targets")]

        def older(doc):
            doc["schema_version"] = step.from_version
            doc.pop("dose_targets", None)
        self.edit("data/program.json", older)
        data = self.data("migrate", "run")
        self.assertEqual([(f["path"], f["from"], f["to"]) for f in data["files"]],
                         [("data/program.json", step.from_version, current)])
        migrated = read_json(self.root / "data" / "program.json")
        self.assertEqual(migrated["dose_targets"], {})
        self.assertEqual(program.load(self.root)["dose_targets"], {})

    def test_a_program_without_targets_loads_with_none_declared(self):
        self.assertNotIn("dose_targets", read_json(VALID / "data" / "program.json"))
        self.assertEqual(program.load(VALID)["dose_targets"], {})


class RegistryTest(unittest.TestCase):
    def test_the_five_codes_are_registered_with_their_severities(self):
        registry = flags.registry()
        for code, (severities, structural) in CODES.items():
            with self.subTest(code=code):
                self.assertEqual(registry[code].owner, "R-30a")
                self.assertEqual(registry[code].severities, severities)
                self.assertEqual(registry[code].structural, structural)


class CheckTest(StructureCase):
    def test_no_program_skips(self):
        (self.root / "data" / "program.json").unlink()
        rows = self.coach("check", "--only", "program_balance")["data"]["results"]
        self.assertEqual([r["status"] for r in rows], ["skip"])

    def test_an_unreadable_program_skips(self):
        (self.root / "data" / "program.json").write_text("{", encoding="utf-8")
        rows = self.coach("check", "--only", "program_balance")["data"]["results"]
        self.assertEqual([r["status"] for r in rows], ["skip"])


if __name__ == "__main__":
    unittest.main()
