"""Minimum weeks compare scheduled dose with the corresponding ordinary week."""

import copy

from coach import jsonio, program, structure
from coach.library import Library
from tests.support import INSTANCES
from tests.support.history import read_json, write_json
from tests.test_priority import MinimumCase, minimum_sessions


class MinimumReferenceTest(MinimumCase):
    base = INSTANCES / "nohevy"

    def report(self):
        return structure.balance(self.root, variant="minimum", today="2026-10-11")

    def ordinary_bench(self, count):
        self.edit_json("data/program.json", lambda doc: doc["sessions"][0]["exercises"][1]["sets"][0].update(count=count))

    def external(self, retained=False, weekday="wed"):
        def change(doc):
            doc["external_sessions"] = [{"id": "pt", "title": "Coach-led", "weekday": weekday,
                                         "estimated_sets": {"calves": 6}}]
            doc["minimum_week"]["external_sessions"] = ["pt"] if retained else []
        self.edit_json("data/program.json", change)

    def test_identical_standby_copies_pass_without_hevy(self):
        def change(doc):
            active = [s for s in doc["sessions"] if s["status"] == "active"]
            standby = copy.deepcopy(active)
            for session in standby:
                session.update(id="min-" + session["id"], status="standby")
            doc["sessions"] = active + standby
            doc["minimum_week"] = {"sessions": [s["id"] for s in standby], "schedule": {
                "rule": "fixed_weekdays", "params": {"days": {"mon": standby[0]["id"], "thu": standby[1]["id"]}}}}
        self.edit_json("data/program.json", change)
        report = self.report()
        self.assertTrue(report["passed"], report["reasons"])
        self.assertEqual(report["positions"][0]["muscles"]["chest"]["ordinary"], 3)

    def test_six_ordinary_sets_need_two_even_when_hypertrophy_target_is_ten(self):
        self.ordinary_bench(6)
        self.edit_json("data/program.json", lambda doc: doc.update(dose_targets={"chest": 10}))
        for delivered, passed in ((1, False), (2, True)):
            with self.subTest(delivered=delivered):
                self.set_minimum(sessions=minimum_sessions(bench_sets=delivered))
                report = self.report()
                chest = report["positions"][0]["muscles"]["chest"]
                self.assertEqual(chest, {"ordinary": 6, "third": 2, "planned": delivered, "met": passed})
                self.assertEqual(report["passed"], passed, report["reasons"])
                self.assertEqual(report["targets"]["chest"], 10)

    def test_scheduled_coach_dose_is_only_delivered_when_retained(self):
        for retained in (False, True):
            with self.subTest(retained=retained):
                self.external(retained=retained)
                report = self.report()
                position = report["positions"][0]
                self.assertEqual(position["muscles"]["calves"], {
                    "ordinary": 6, "third": 2, "planned": 6 if retained else 0, "met": retained})
                self.assertEqual(report["passed"], retained, report["reasons"])
                self.assertEqual([s["external_id"] for s in position["reference_external"]], ["pt"])
                self.assertEqual([s["external_id"] for s in position["external"]], ["pt"] if retained else [])

    def test_unscheduled_external_estimate_does_not_inflate_the_reference(self):
        self.external(weekday=None)
        report = self.report()
        self.assertNotIn("calves", report["positions"][0]["muscles"])
        self.assertTrue(report["passed"], report["reasons"])

    def rotation(self, minimum_names=None):
        def change(doc):
            doc["schedule"] = {"rule": "alternating_external_anchor", "params": {"weeks": [
                {"name": "a", "days": {"mon": "session-a"}},
                {"name": "b", "days": {"mon": "session-a", "thu": "session-b"}}]}}
            if minimum_names:
                doc["minimum_week"]["schedule"] = {"rule": "alternating_external_anchor", "params": {"weeks": [
                    {"name": minimum_names[0], "days": {"tue": "min-a"}},
                    {"name": minimum_names[1], "days": {"tue": "min-a", "fri": "min-b"}}]}}
        self.edit_json("data/program.json", change)

    def test_fixed_minimum_reports_each_rotating_ordinary_reference(self):
        self.rotation()
        positions = self.report()["positions"]
        self.assertEqual([r["reference_position"] for r in positions], ["a", "b"])
        self.assertEqual([r["position"] for r in positions], [None, None])
        self.assertEqual(positions[0]["muscles"]["lats"]["ordinary"], 0)
        self.assertEqual(positions[1]["muscles"]["lats"]["ordinary"], 6)
        self.assertEqual([s["session_id"] for s in positions[1]["reference_sessions"]], ["session-a", "session-b"])

    def test_matching_rotations_compare_like_positions_and_keep_other_failures(self):
        self.rotation(("a", "b"))
        self.edit_json("data/program.json", lambda doc: doc["priority"][0]["floor"].update(sets=5))
        with (self.root / "config.toml").open("a") as handle:
            handle.write("\n[sessions.cap_minutes]\nmin-a = 5\n")
        report = self.report()
        self.assertEqual([(r["position"], r["reference_position"]) for r in report["positions"]], [("a", "a"), ("b", "b")])
        for position in ("a", "b"):
            self.assertTrue(any(reason.startswith(position + ":") and "priority floor" in reason for reason in report["reasons"]))
            self.assertTrue(any(reason.startswith(position + ":") and "min cap" in reason for reason in report["reasons"]))

    def test_disjoint_rotating_labels_require_an_explicit_matching_schedule(self):
        self.rotation(("x", "y"))
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertTrue(any("position names" in r for r in report["reasons"]))

    def test_retained_coach_session_is_in_the_written_plan(self):
        self.external(retained=True)
        report = structure.minimum(self.root, "2026-10-12", write=True, today="2026-10-11")
        plan = read_json(self.root / report["path"])
        self.assertEqual(plan["external_sessions"][0]["external_id"], "pt")
        self.assertEqual(plan["external_sessions"][0]["date"], "2026-10-14")

    def test_retained_external_ids_must_be_unique_known_and_scheduled(self):
        self.external(retained=True)
        for ids, weekday, fragment in ((["pt", "pt"], "wed", "listed twice"),
                                       (["missing"], "wed", "no external session"),
                                       (["pt"], None, "weekday")):
            with self.subTest(ids=ids, weekday=weekday):
                doc = read_json(self.root / "data/program.json")
                doc["minimum_week"]["external_sessions"] = ids
                doc["external_sessions"][0]["weekday"] = weekday
                problems = program.validate(doc, None, Library.load(self.root), self.root)
                self.assertTrue(any(fragment in e.message for e in problems), problems)

    def test_v7_migration_preserves_minimum_and_does_not_invent_coach_work(self):
        doc = read_json(self.root / "data/program.json")
        doc["schema_version"] = 7
        before = copy.deepcopy(doc)
        write_json(self.root / "data/program.json", doc)
        self.data("migrate", "run")
        migrated = read_json(self.root / "data/program.json")
        expected = dict(before, schema_version=jsonio.current_version(jsonio.load_schema("program")))
        expected["minimum_week"]["external_sessions"] = []
        self.assertEqual(migrated, expected)

    def test_minimum_plan_checks_the_requested_calendar_week(self):
        self.ordinary_bench(6)
        self.set_minimum(sessions=minimum_sessions(bench_sets=2))
        self.edit_json("data/program.json", lambda doc: doc.update(schedule={
            "rule": "explicit_calendar", "params": {"dates": {
                "2026-10-12": "session-a", "2026-10-19": "session-a", "2026-10-22": "session-a"}}}))
        self.assertTrue(self.report()["passed"])
        later = structure.minimum(self.root, "2026-10-19", today="2026-10-11")
        self.assertFalse(later["balance"]["passed"])
        self.assertTrue(any("ordinary dose of 12 (4)" in r for r in later["balance"]["reasons"]))

    def test_migration_preserves_a_null_minimum(self):
        doc = read_json(self.root / "data/program.json")
        doc.update(schema_version=7, minimum_week=None)
        write_json(self.root / "data/program.json", doc)
        self.data("migrate", "run")
        expected = dict(doc, schema_version=jsonio.current_version(jsonio.load_schema("program")))
        self.assertEqual(read_json(self.root / "data/program.json"), expected)

    def test_program_render_identifies_retained_coach_work(self):
        self.external(retained=True)
        self.assertIn("Retained coach-led sessions: pt.", program.render_all(self.root)["routine/program.md"])
