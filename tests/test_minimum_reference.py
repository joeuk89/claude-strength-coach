"""Minimum weeks compare scheduled dose with the corresponding ordinary week."""

import copy

from coach import cli, commands, jsonio, program, structure
from coach.library import Library
from tests.support import INSTANCES
from tests.support.history import read_json, write_json
from tests.test_priority import MinimumCase, minimum_sessions


class MinimumReferenceTest(MinimumCase):
    base = INSTANCES / "nohevy"

    def report(self):
        return structure.balance(self.root, variant="minimum", today="2026-10-11")

    def ordinary_bench(self, count):
        self.edit_json("data/program.json",
                       lambda doc: doc["sessions"][0]["exercises"][1]["sets"][0].update(count=count))

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
        for planned, passed in ((1, False), (2, True)):
            with self.subTest(planned=planned):
                self.set_minimum(sessions=minimum_sessions(bench_sets=planned))
                report = self.report()
                chest = report["positions"][0]["muscles"]["chest"]
                self.assertEqual(chest, {"ordinary": 6, "third": 2, "planned": planned, "met": passed})
                self.assertEqual(report["passed"], passed, report["reasons"])
                self.assertEqual(report["targets"]["chest"], 10)

    def test_scheduled_coach_dose_is_only_planned_when_retained(self):
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

    def test_coach_work_without_a_weekday_counts_in_the_reference_as_in_ordinary_balance(self):
        for retained in (False, True):
            with self.subTest(retained=retained):
                self.external(retained=retained, weekday=None)
                ordinary = structure.balance(self.root, today="2026-10-11")["muscles"]["calves"]["average"]
                report = self.report()
                position = report["positions"][0]
                self.assertEqual(position["muscles"]["calves"], {
                    "ordinary": ordinary, "third": 2, "planned": 6 if retained else 0, "met": retained})
                self.assertEqual(report["passed"], retained, report["reasons"])
                self.assertEqual([(s["external_id"], s["date"]) for s in position["reference_external"]],
                                 [("pt", None)])
                self.assertEqual([s["external_id"] for s in position["external"]], ["pt"] if retained else [])

    def rotation(self, minimum_names=None, ordinary=True):
        def change(doc):
            if ordinary:
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

    def test_rotating_minimum_compares_each_position_with_a_fixed_ordinary_week(self):
        self.ordinary_bench(30)
        self.rotation(("a", "b"), ordinary=False)
        report = self.report()
        self.assertEqual([r["position"] for r in report["positions"]], ["a", "b"])
        for row in report["positions"]:
            with self.subTest(position=row["position"]):
                self.assertIsNone(row["reference_position"])
                self.assertEqual([s["session_id"] for s in row["reference_sessions"]], ["session-a", "session-b"])
                self.assertEqual(row["reference_external"], [])
                self.assertEqual(row["muscles"]["chest"], {"ordinary": 30, "third": 10, "planned": 4, "met": False})
                self.assertIn(f"{row['position']}: chest: 4 fractional sets planned, below a third of its ordinary "
                              "dose of 30 (10)", report["reasons"])
        self.assertFalse(report["passed"])

    def test_matching_rotations_compare_like_positions_and_keep_other_failures(self):
        self.rotation(("a", "b"))
        self.edit_json("data/program.json", lambda doc: doc["priority"][0]["floor"].update(sets=5))
        with (self.root / "config.toml").open("a") as handle:
            handle.write("\n[sessions.cap_minutes]\nmin-a = 5\n")
        report = self.report()
        self.assertEqual([(r["position"], r["reference_position"]) for r in report["positions"]],
                         [("a", "a"), ("b", "b")])
        for position in ("a", "b"):
            for failure in ("priority floor", "min cap"):
                self.assertTrue(any(reason.startswith(position + ":") and failure in reason
                                    for reason in report["reasons"]), report["reasons"])

    def test_disjoint_rotating_labels_require_an_explicit_matching_schedule(self):
        self.rotation(("x", "y"))
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertTrue(any("position names" in r for r in report["reasons"]))

    def test_rotation_mismatch_keeps_session_count_duration_and_priority_failures(self):
        self.edit_json("data/program.json", lambda doc: doc["priority"][0]["floor"].update(sets=5))
        with (self.root / "config.toml").open("a") as handle:
            handle.write("\n[sessions.cap_minutes]\nmin-a = 5\n")
        for names in (("x", "y"), ("a", "y")):
            with self.subTest(names=names):
                self.rotation(names)
                def overbook(doc):
                    for week in doc["minimum_week"]["schedule"]["params"]["weeks"]:
                        week["days"] = {"mon": "min-a", "wed": "min-a", "fri": "min-a"}
                self.edit_json("data/program.json", overbook)
                report = self.balance(expect=1)["data"]
                self.assertFalse(report["passed"])
                self.assertTrue(any("position names" in reason for reason in report["reasons"]))
                self.assertEqual([row["position"] for row in report["positions"]], list(names))
                for row in report["positions"]:
                    position = row["position"]
                    for failure in ("schedule plans 3 sessions", "priority floor", "over its 5 min cap"):
                        self.assertTrue(any(reason.startswith(position + ":") and failure in reason
                                            for reason in report["reasons"]), report["reasons"])
                    self.assertTrue(all(not session["within_cap"] for session in row["sessions"]))
                    self.assertFalse(row["priority"][0]["met"])
                    if position == "a":
                        self.assertEqual(row["reference_position"], "a")
                        self.assertEqual(row["muscles"]["chest"]["ordinary"], 3)
                    else:
                        self.assertIsNone(row["reference_position"])
                        self.assertIsNone(row["reference_sessions"])
                        self.assertIsNone(row["reference_external"])
                        self.assertEqual(row["muscles"]["chest"], {
                            "ordinary": None, "third": None, "planned": 12, "met": None})

    def test_retained_coach_session_is_in_the_written_plan(self):
        for weekday, date in (("wed", "2026-10-14"), (None, None)):
            with self.subTest(weekday=weekday):
                self.external(retained=True, weekday=weekday)
                report = structure.minimum(self.root, "2026-10-12", write=True, today="2026-10-11")
                plan = read_json(self.root / report["path"])
                self.assertEqual([(s["external_id"], s["date"]) for s in plan["external_sessions"]], [("pt", date)])

    def test_retained_external_ids_must_be_unique_and_known(self):
        self.external(retained=True)
        for ids, fragment in ((["pt", "pt"], "listed twice"), (["missing"], "no external session")):
            with self.subTest(ids=ids):
                doc = read_json(self.root / "data/program.json")
                doc["minimum_week"]["external_sessions"] = ids
                problems = program.validate(doc, None, Library.load(self.root), self.root)
                self.assertTrue(any(fragment in e.message for e in problems), problems)

    def test_a_retained_coach_session_without_a_weekday_is_valid(self):
        self.external(retained=True, weekday=None)
        doc = read_json(self.root / "data/program.json")
        self.assertEqual(program.validate(doc, None, Library.load(self.root), self.root), [])

    def test_fixed_minimum_reports_position_independent_failures_once(self):
        self.rotation()
        self.edit_json("data/program.json", lambda doc: doc["priority"][0]["floor"].update(sets=5))
        with (self.root / "config.toml").open("a") as handle:
            handle.write("\n[sessions.cap_minutes]\nmin-a = 5\n")
        reasons = self.report()["reasons"]
        for failure in ("over its 5 min cap", "priority floor"):
            found = [reason for reason in reasons if failure in reason]
            self.assertEqual(len(found), 1, reasons)
            self.assertFalse(found[0].startswith(("a:", "b:")), found)

    def test_fixed_minimum_names_the_ordinary_position_a_dose_failure_compares_with(self):
        self.rotation()
        self.edit_json("data/program.json", lambda doc: doc["sessions"][1]["exercises"][0]["sets"][0].update(count=30))
        reasons = self.report()["reasons"]
        self.assertTrue(any(reason.startswith("against ordinary b: lats:") for reason in reasons), reasons)
        self.assertFalse(any(reason.startswith("against ordinary a: lats:") for reason in reasons), reasons)

    def test_minimum_help_describes_the_ordinary_week_reference(self):
        _, subparsers = cli.build_parser(commands.discover())
        variant = subparsers["structure balance"]._option_string_actions["--variant"]
        self.assertIn("a third of the corresponding ordinary week's planned dose", variant.help)
        self.assertNotIn("dose target", variant.help)

    def test_optional_standby_sessions_add_no_planned_dose(self):
        def optional(doc):
            for session in doc["sessions"]:
                if session["id"] == "min-b":
                    session["tier"] = "optional"
        self.edit_json("data/program.json", optional)
        report = self.report()
        self.assertEqual(report["positions"][0]["muscles"]["lats"], {
            "ordinary": 6, "third": 2, "planned": 0, "met": False})
        self.assertFalse(report["passed"])

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
        self.assertIn("Retained coach-led sessions: `pt`.", program.render_all(self.root)["routine/program.md"])
