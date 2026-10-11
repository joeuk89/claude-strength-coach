"""Priority lifts, their floor dose on a missed session, and the minimum week (contract C40)."""

import copy
import json

from coach import dates, flags, jsonio, missed, overlay, program, structure
from coach.library import Library
from tests.support import INSTANCES, REPO_ROOT
from tests.support.history import HistoryCase, read_json, write_json
from tests.support.skills import skill_text

WEEKLY = "2026-10-12-weekly"
SQUAT = "bb_back_squat"
FLOOR_ID = "priority:bb_back_squat"


def priority_entry(exercise_id=SQUAT, kind="e1rm", **extra):
    return dict({"exercise_id": exercise_id, "kpi": {"kind": kind, "target": None, "by": None},
                 "floor": {"sets": 2, "rpe": None}}, **extra)


def codes(found):
    return [f["code"] for f in found]


class PriorityCase(HistoryCase):
    def set_priority(self, *entries):
        self.edit_json("data/program.json", lambda doc: doc.update(priority=list(entries)))

    def data(self, *argv, expect=0, env=None):
        envelope = self.coach(*argv, expect=expect, env=env)
        return envelope["data"] if expect == 0 else envelope


class KpiTest(PriorityCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()

    def lift(self, **env):
        return self.data("structure", "priority", env=env)["lifts"][0]

    def test_an_e1rm_kpi_reports_the_c18_best_point_and_its_date(self):
        self.set_priority(priority_entry(kpi={"kind": "e1rm", "target": 130, "by": "2027-01-31"}))
        lift = self.lift()
        best = self.data("stats", "e1rm", "--exercise", SQUAT)["best"][SQUAT]
        self.assertEqual(lift["kpi"]["now"], {"value": best["e1rm"], "date": best["date"]})
        self.assertEqual(lift["kpi"]["now"], {"value": 121.88, "date": "2026-10-05"})
        self.assertEqual(lift["kpi"]["trend"]["delta"], 1.55)
        self.assertEqual((lift["kpi"]["target"], lift["kpi"]["by"], lift["kpi"]["met"]), (130, "2027-01-31", False))
        self.assertEqual(lift["sessions"], ["session-a"])
        self.assertEqual(lift["floor"], {"sets": 2, "rpe": None})

    def test_since_narrows_the_trend(self):
        self.set_priority(priority_entry())
        lift = self.data("structure", "priority", "--since", "2026-10-01")["lifts"][0]
        self.assertIsNone(lift["kpi"]["trend"])
        self.assertEqual(lift["kpi"]["now"]["date"], "2026-10-05")

    def test_top_load_and_top_reps_read_the_newest_exposure(self):
        self.set_priority(priority_entry(kind="top_load"), priority_entry("pull_up", kind="top_reps"))
        lifts = {lift["exercise_id"]: lift for lift in self.data("structure", "priority")["lifts"]}
        self.assertEqual(lifts[SQUAT]["kpi"]["now"], {"value": 97.5, "date": "2026-10-05"})
        self.assertEqual(lifts["pull_up"]["kpi"]["now"]["date"], "2026-10-08")
        self.assertIsInstance(lifts["pull_up"]["kpi"]["now"]["value"], int)

    def test_a_rung_kpi_reads_the_ladder_state(self):
        def ladder(doc):
            line = doc["sessions"][1]["exercises"][1]
            line["scheme"] = {"name": "assistance_ladder",
                              "params": {"rungs": [{"name": "band", "load": None}, {"name": "full", "load": 0}]}}
        self.edit_json("data/program.json", ladder)
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({"session-b/pull_up": {
            "scheme": "assistance_ladder", "data": {"rung": 1, "through": "2026-10-08"}, "pending": None}}))
        self.set_priority(priority_entry("pull_up", kind="rung"))
        self.assertEqual(self.lift()["kpi"]["now"],
                         {"value": 1, "name": "full", "date": "2026-10-08", "session_id": "session-b"})

    def test_no_priority_lifts_reports_none(self):
        self.assertEqual(self.data("structure", "priority")["lifts"], [])


class FloorCase(PriorityCase):
    """missed/: Session A (squat) on Mon 12 Oct is missed and Session B stays on Thu 15 Oct."""

    base = INSTANCES / "missed"

    def setUp(self):
        super().setUp()
        self.env = {"COACH_NOW": "2026-10-13T08:00:00Z"}
        self.set_priority(priority_entry())
        self.edit_overlay(self.mon_a_thu_b)
        self.drop_workouts("2026-10-12")

    def mon_a_thu_b(self, doc):
        doc["sessions"] = [s for s in doc["sessions"] if s["date"] != "2026-10-17"]
        next(s for s in doc["sessions"] if s["session_id"] == "session-b")["date"] = "2026-10-15"

    def edit_overlay(self, change):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(path)
        change(doc)
        doc["approval"] = None
        write_json(path, doc)

    def drop_workouts(self, *days):
        self.edit_json("data/history/2026-10.json",
                       lambda doc: doc.update(workouts=[w for w in doc["workouts"] if w["date"] not in days]))

    def priority(self, env=None):
        return self.data("structure", "priority", "--since", "2026-10-12", env=env)

    def plan(self):
        return self.data("missed", "plan", "--session", "session-a", "--date", "2026-10-12")

    def set_rule(self, action, text=None):
        """Session A's only missed-day rule becomes `miss-a` with `action`; None leaves it no rule."""
        rules = [] if action is None else [
            {"id": "miss-a", "session_id": "session-a", "text": text, "when": {}, "action": action}]
        self.edit_json("data/program.json", lambda doc: doc.update(missed_day_rules=rules))


class FloorRuleTest(FloorCase):
    def test_priority_floor_builds_the_synthetic_fold_rule(self):
        rule = structure.priority_floor(self.root, "session-a", "2026-10-12")
        self.assertEqual(rule, {"id": FLOOR_ID, "session_id": "session-a", "text": None, "when": {},
                                "action": {"kind": "fold", "into": "next",
                                           "exercises": [{"exercise_id": SQUAT, "sets": 2, "rpe": None}]}})

    def test_none_when_the_missed_session_carried_no_priority_lift(self):
        self.assertIsNone(structure.priority_floor(self.root, "session-b", "2026-10-15"))

    def test_two_priority_lifts_in_one_session_share_one_rule(self):
        self.set_priority(priority_entry(), priority_entry("db_bench_press", floor={"sets": 1, "rpe": 6}))
        rule = structure.priority_floor(self.root, "session-a", "2026-10-12")
        self.assertEqual(rule["id"], "priority:bb_back_squat+db_bench_press")
        self.assertEqual(rule["action"]["exercises"][1], {"exercise_id": "db_bench_press", "sets": 1, "rpe": 6})

    def test_the_rule_reads_in_plain_words(self):
        rule = structure.priority_floor(self.root, "session-a", "2026-10-12")
        self.assertEqual(missed.describe(rule, self.root),
                         "Miss Session A: 2 sets of Back Squat (Barbell) go into the next session, this week only.")


class FloorFoldTest(FloorCase):
    def setUp(self):
        super().setUp()
        self.set_rule(None)

    def test_with_no_program_rule_the_floor_folds_the_lift(self):
        data = self.plan()
        self.assertTrue(data["matched"])
        self.assertEqual(data["rule"]["id"], FLOOR_ID)
        self.assertIsNone(data["floor_rule"])
        draft = data["draft"]
        self.assertEqual([(s["date"], s["session_id"]) for s in draft["sessions"]], [("2026-10-15", "session-b")])
        last = draft["sessions"][0]["exercises"][-1]
        self.assertEqual(last["exercise_id"], SQUAT)
        working = [s for s in last["sets"] if overlay.is_working(s)]
        self.assertEqual([(s["reps"], s["load"]["hevy_total"], s["rpe"]) for s in working], [(5, 100, 7)] * 2)
        self.assertEqual(last["fold"], {"rule_id": FLOOR_ID, "from_session_id": "session-a",
                                        "from_date": "2026-10-12", "scope": "one_week"})
        self.assertIn("missed_day_rule", codes(draft["flags"]))
        self.assertNotIn("priority_exposures_missed", codes(data["flags"]))
        self.assertEqual(data["flags"], [])

    def test_apply_writes_the_floor_and_the_record_line(self):
        data = self.data("missed", "apply", "--session", "session-a", "--date", "2026-10-12", "--tag", "time")
        self.assertTrue(data["record_lines"][1].startswith(f"- Rule {FLOOR_ID}: Back Squat (Barbell) 2×5"))
        doc = overlay.load(self.root, data["overlay_id"])
        self.assertEqual(doc["sessions"][0]["exercises"][-1]["fold"]["rule_id"], FLOOR_ID)
        self.data("overlay", "validate", data["overlay_id"])

    def test_a_pending_floor_raises_nothing_and_a_trained_one_counts_as_replaced(self):
        self.data("missed", "apply", "--session", "session-a", "--date", "2026-10-12")
        week = self.priority()["lifts"][0]["weeks"][-1]
        self.assertEqual((week["planned"], week["missed"], week["pending"], week["unreplaced"]), (1, 1, 1, 0))
        self.train_session_b_on("2026-10-15")
        data = self.priority(env={"COACH_NOW": "2026-10-19T08:00:00Z"})
        row = next(w for w in data["lifts"][0]["weeks"] if w["week"] == "2026-10-12")
        self.assertEqual((row["missed"], row["replaced"], row["unreplaced"]), (1, 1, 0))
        self.assertEqual(data["flags"], [])

    def test_a_floor_whose_session_is_missed_too_raises_the_flag(self):
        self.data("missed", "apply", "--session", "session-a", "--date", "2026-10-12")
        data = self.priority(env={"COACH_NOW": "2026-10-19T08:00:00Z"})
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"])
        self.assertEqual(data["flags"][0]["exercise_id"], SQUAT)
        self.assertIn("2026-W42", data["flags"][0]["message"])

    def train_session_b_on(self, day):
        def add(doc):
            source = next(w for w in doc["workouts"] if w["date"] == "2026-10-08")
            moved = json.loads(json.dumps(source).replace("2026-10-08", day))
            moved["workout_id"] = "10000000-0000-4000-8000-0000000000f1"
            doc["workouts"].append(moved)
        self.edit_json("data/history/2026-10.json", add)


class RuleOrderTest(FloorCase):
    """The program's own rule comes first; the floor covers only what that rule leaves out of the week."""

    def folds(self, draft):
        return [(s["date"], line["exercise_id"], line["fold"]["rule_id"])
                for s in draft["sessions"] for line in s["exercises"] if line.get("fold")]

    def test_a_shift_to_a_free_day_moves_the_session_and_no_floor_folds(self):
        self.set_rule({"kind": "shift", "to_weekdays": ["fri"]})
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["floor_rule"]), (True, "miss-a", None))
        self.assertIn(("2026-10-16", "session-a", "2026-10-12"),
                      [(s["date"], s["session_id"], s.get("moved_from")) for s in data["draft"]["sessions"]])
        self.assertEqual(self.folds(data["draft"]), [])
        self.assertEqual(data["flags"], [])

    def test_a_skip_rule_lets_the_floor_fold_the_lift_into_the_next_session(self):
        self.set_rule({"kind": "skip"})
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"]), (True, FLOOR_ID))
        self.assertEqual(self.folds(data["draft"]), [("2026-10-15", SQUAT, FLOOR_ID)])
        self.assertEqual(data["flags"], [])

    def test_a_manual_rule_lets_the_floor_fold_the_lift(self):
        self.set_rule({"kind": "manual"}, text="Ask the coach.")
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"]), (True, FLOOR_ID))
        self.assertEqual(self.folds(data["draft"]), [("2026-10-15", SQUAT, FLOOR_ID)])

    def test_a_shift_with_no_free_day_falls_back_to_the_floor(self):
        self.set_rule({"kind": "shift", "to_weekdays": ["thu"]})
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"]), (True, FLOOR_ID))
        self.assertEqual(self.folds(data["draft"]), [("2026-10-15", SQUAT, FLOOR_ID)])
        self.assertEqual(data["flags"], [])

    def test_a_fold_leaving_out_the_lift_applies_and_the_floor_adds_the_lift(self):
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": "db_bench_press", "sets": 1}]})
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["floor_rule"]["id"]), (True, "miss-a", FLOOR_ID))
        self.assertEqual(self.folds(data["draft"]),
                         [("2026-10-15", "db_bench_press", "miss-a"), ("2026-10-15", SQUAT, FLOOR_ID)])
        self.assertEqual(data["summary"][0],
                         f"Missed Mon 12 Oct Session A; rule miss-a applies (fold), with the priority floor {FLOOR_ID}.")
        self.assertEqual(data["flags"], [])

    def test_a_fold_into_a_named_session_combines_with_the_floor(self):
        self.set_rule({"kind": "fold", "into": "session-b", "exercises": [{"exercise_id": "db_bench_press"}]})
        data = self.plan()
        self.assertEqual(self.folds(data["draft"]),
                         [("2026-10-15", "db_bench_press", "miss-a"), ("2026-10-15", SQUAT, FLOOR_ID)])

    def test_a_fold_whose_floor_cannot_fold_stands_alone_and_raises_the_flag(self):
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": "db_bench_press", "sets": 1}]})

        def warm_ups_only(doc):
            squat = next(line for line in doc["sessions"][0]["exercises"] if line["exercise_id"] == SQUAT)
            for set_ in squat["sets"]:
                set_["type"] = "warmup"
        self.edit_overlay(warm_ups_only)
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["floor_rule"]), (True, "miss-a", None))
        self.assertEqual(self.folds(data["draft"]), [("2026-10-15", "db_bench_press", "miss-a")])
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"])

    def test_the_combined_fold_writes_one_record_line_naming_both_rules(self):
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": "db_bench_press", "sets": 1}]})
        data = self.data("missed", "apply", "--session", "session-a", "--date", "2026-10-12")
        self.assertTrue(data["record_lines"][1].startswith(f"- Rules miss-a and {FLOOR_ID}: Bench Press (Dumbbell) 1×8–10"))
        self.data("overlay", "validate", data["overlay_id"])

    def test_a_fold_carrying_the_lift_at_the_floor_or_more_needs_no_floor(self):
        for sets in (2, 3):
            with self.subTest(sets=sets):
                self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": sets}]})
                data = self.plan()
                self.assertEqual((data["rule"]["id"], data["floor_rule"]), ("miss-a", None))
                self.assertEqual(self.folds(data["draft"]), [("2026-10-15", SQUAT, "miss-a")])
                self.assertEqual(len(self.working(data["draft"], SQUAT)), sets)
                self.assertEqual(data["flags"], [])

    def working(self, draft, exercise_id):
        return [(s.get("reps"), s["load"]["hevy_total"], s["rpe"]) for session in draft["sessions"]
                for line in session["exercises"] if line.get("fold") and line["exercise_id"] == exercise_id
                for s in line["sets"] if overlay.is_working(s)]

    def test_a_fold_carrying_the_lift_short_is_topped_up_to_the_floor(self):
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 1},
                                                                       {"exercise_id": "db_bench_press", "sets": 1}]})
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["floor_rule"]["id"]), (True, "miss-a", FLOOR_ID))
        self.assertEqual(self.folds(data["draft"]),
                         [("2026-10-15", SQUAT, "miss-a"), ("2026-10-15", "db_bench_press", "miss-a")])
        self.assertEqual(self.working(data["draft"], SQUAT), [(5, 100, 7)] * 2)
        self.assertEqual(len(self.working(data["draft"], "db_bench_press")), 1)
        self.assertEqual(data["summary"][0],
                         f"Missed Mon 12 Oct Session A; rule miss-a applies (fold), with the priority floor {FLOOR_ID}.")
        self.assertTrue(data["summary"][1].startswith("Back Squat (Barbell) 2×5"), data["summary"][1])
        floor_flags = [f["message"] for f in data["draft"]["flags"]
                       if f["code"] == "missed_day_rule" and f["message"].startswith(f"Rule {FLOOR_ID}")]
        self.assertEqual(floor_flags, [f"Rule {FLOOR_ID}: Back Squat (Barbell) from Mon 12 Oct Session A topped up "
                                       f"to 2 sets, this week only."])
        self.assertEqual(data["flags"], [])

    def test_a_short_fold_topped_up_writes_one_record_line_naming_both_rules(self):
        self.set_rule({"kind": "fold", "into": "session-b", "exercises": [{"exercise_id": SQUAT, "sets": 1}]})
        data = self.data("missed", "apply", "--session", "session-a", "--date", "2026-10-12")
        self.assertTrue(data["record_lines"][1].startswith(f"- Rules miss-a and {FLOOR_ID}: Back Squat (Barbell) 2×5"),
                        data["record_lines"][1])
        doc = overlay.load(self.root, data["overlay_id"])
        self.assertEqual(len(self.working(doc, SQUAT)), 2)
        self.data("overlay", "validate", data["overlay_id"])

    def test_a_short_fold_that_carries_every_prescribed_set_needs_no_floor(self):
        def one_working_set(doc):
            squat = next(line for line in doc["sessions"][0]["exercises"] if line["exercise_id"] == SQUAT)
            squat["sets"] = squat["sets"][:2]
        self.edit_overlay(one_working_set)
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 1}]})
        data = self.plan()
        self.assertEqual((data["rule"]["id"], data["floor_rule"]), ("miss-a", None))
        self.assertEqual(self.working(data["draft"], SQUAT), [(5, 100, 7)])
        self.assertEqual(data["flags"], [])

    def test_a_top_up_that_cannot_be_placed_leaves_the_fold_and_raises_the_flag(self):
        self.set_priority(priority_entry(), priority_entry("db_bench_press"))
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 1}]})

        def bench_warm_ups_only(doc):
            bench = next(line for line in doc["sessions"][0]["exercises"] if line["exercise_id"] == "db_bench_press")
            for set_ in bench["sets"]:
                set_["type"] = "warmup"
        self.edit_overlay(bench_warm_ups_only)
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["floor_rule"]), (True, "miss-a", None))
        self.assertEqual(self.working(data["draft"], SQUAT), [(5, 100, 7)])
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"] * 2)
        self.assertEqual(data["flags"][0]["exercise_id"], SQUAT)

    def test_a_short_lift_and_a_left_out_lift_share_one_floor_rule(self):
        self.set_priority(priority_entry(), priority_entry("db_bench_press"))
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 1}]})
        data = self.plan()
        both = "priority:bb_back_squat+db_bench_press"
        self.assertEqual(data["floor_rule"]["id"], both)
        self.assertEqual(self.folds(data["draft"]),
                         [("2026-10-15", SQUAT, "miss-a"), ("2026-10-15", "db_bench_press", both)])
        self.assertEqual(len(self.working(data["draft"], SQUAT)), 2)
        self.assertEqual(len(self.working(data["draft"], "db_bench_press")), 2)
        self.assertEqual(data["flags"], [])

    def test_the_top_up_takes_the_floor_rpe_not_the_folds_cap(self):
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 1, "rpe": 6}]})
        self.assertEqual(self.working(self.plan()["draft"], SQUAT), [(5, 100, 6), (5, 100, 7)])
        self.set_priority(priority_entry(floor={"sets": 3, "rpe": 5}))
        self.assertEqual(self.working(self.plan()["draft"], SQUAT), [(5, 100, 6), (5, 100, 5), (5, 100, 5)])

    def test_only_the_lifts_the_fold_leaves_out_get_the_floor(self):
        self.set_priority(priority_entry(), priority_entry("db_bench_press"))
        self.set_rule({"kind": "fold", "into": "next", "exercises": [{"exercise_id": SQUAT, "sets": 2}]})
        data = self.plan()
        self.assertEqual(data["floor_rule"]["id"], "priority:db_bench_press")
        self.assertEqual(self.folds(data["draft"]),
                         [("2026-10-15", SQUAT, "miss-a"), ("2026-10-15", "db_bench_press", "priority:db_bench_press")])

    def test_a_skip_rule_whose_floor_cannot_fold_keeps_the_skip_and_raises_the_flag(self):
        self.set_rule({"kind": "skip"})
        self.edit_overlay(lambda doc: doc.update(
            sessions=[s for s in doc["sessions"] if s["session_id"] == "session-a"]))
        data = self.plan()
        self.assertEqual((data["matched"], data["rule"]["id"], data["draft"]), (True, "miss-a", None))
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"])

    def test_a_manual_or_full_shift_whose_floor_cannot_fold_stays_unmatched(self):
        self.edit_overlay(lambda doc: doc.update(
            sessions=[s for s in doc["sessions"] if s["session_id"] == "session-a"]))
        for action, text in (({"kind": "manual"}, "Ask the coach."), ({"kind": "shift", "to_weekdays": ["mon"]}, None)):
            with self.subTest(action=action["kind"]):
                self.set_rule(action, text)
                data = self.plan()
                self.assertEqual((data["matched"], data["rule"]["id"], data["draft"]), (False, "miss-a", None))
                self.assertEqual(codes(data["flags"]), ["priority_exposures_missed", "missed_rule_unmatched"])


class NoSessionLeftTest(FloorCase):
    def setUp(self):
        super().setUp()
        self.edit_overlay(lambda doc: doc.update(
            sessions=[s for s in doc["sessions"] if s["session_id"] == "session-a"]))
        self.set_rule(None)

    def test_apply_rule_is_unmatched_and_the_flag_is_raised(self):
        doc = overlay.load(self.root, WEEKLY)
        rule = structure.priority_floor(self.root, "session-a", "2026-10-12")
        with self.assertRaises(missed.Unmatched):
            missed.apply_rule(self.root, doc, "session-a", "2026-10-12", rule,
                              now=dates.parse_timestamp("2026-10-13T08:00:00Z"))
        data = self.plan()
        self.assertFalse(data["matched"])
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed", "missed_rule_unmatched"])
        self.assertEqual(data["flags"][0]["exercise_id"], SQUAT)
        self.assertIsNone(data["draft"])

    def test_structure_priority_raises_it_for_that_week(self):
        data = self.priority()
        self.assertEqual(codes(data["flags"]), ["priority_exposures_missed"])
        week = data["lifts"][0]["weeks"][-1]
        self.assertEqual((week["label"], week["planned"], week["missed"], week["unreplaced"]), ("2026-W42", 1, 1, 1))

    def test_a_program_shift_that_moves_the_session_carries_the_lift(self):
        self.set_rule({"kind": "shift", "to_weekdays": ["sat"]})
        data = self.plan()
        self.assertEqual(data["rule"]["id"], "miss-a")
        self.assertEqual(data["flags"], [])


MIN_A = {"id": "min-a", "title": "Minimum A", "kind": "lifting", "tier": "core", "status": "standby", "location": None,
         "focus": None, "exercises": []}


def line(exercise_id, mode, sets, reps=5, rpe=8, start_load=None, rest=120):
    return {"exercise_id": exercise_id, "load_mode": mode, "sets": [{"count": sets, "type": "normal", "reps": reps,
                                                                     "rpe": rpe}],
            "rest_seconds": rest, "superset_id": None, "cues": None, "constraints": [],
            "scheme": {"name": "double_progression", "params": {}}, "start_load": start_load}


def minimum_sessions(bench_sets=4, pull_up=True):
    min_a = dict(MIN_A, exercises=[line(SQUAT, "total", 4, start_load=90),
                                   line("db_bench_press", "per_hand_x2", bench_sets, reps=8, start_load=22)])
    b_lines = [line("db_single_arm_row", "single_implement", 4, reps=10, start_load=28)]
    if pull_up:
        b_lines.append(line("pull_up", "bodyweight", 3, reps=8, start_load=0))
    min_b = dict(MIN_A, id="min-b", title="Minimum B", exercises=b_lines)
    return [min_a, min_b]


class MinimumCase(PriorityCase):
    def setUp(self):
        super().setUp()
        self.env = {"COACH_NOW": "2026-10-11T18:00:00Z"}
        self.set_minimum()

    def set_minimum(self, sessions=None, ids=("min-a", "min-b"), days=None, priority=(SQUAT,)):
        def change(doc):
            doc["sessions"] = [s for s in doc["sessions"] if s["status"] != "standby"]
            doc["sessions"] += sessions if sessions is not None else minimum_sessions()
            doc["minimum_week"] = {"sessions": list(ids), "schedule": {
                "rule": "fixed_weekdays", "params": {"days": days or {"tue": "min-a", "fri": "min-b"}}}}
            doc["priority"] = [priority_entry(exercise_id) for exercise_id in priority]
        self.edit_json("data/program.json", change)

    def balance(self, expect=0):
        return self.data("structure", "balance", "--variant", "minimum", expect=expect)


class MinimumBalanceTest(MinimumCase):
    def test_a_two_session_week_meeting_every_rule_passes(self):
        data = self.balance()
        self.assertTrue(data["passed"])
        self.assertEqual(data["reasons"], [])
        position = data["positions"][0]
        self.assertEqual([(s["date"], s["session_id"]) for s in position["sessions"]],
                         [("2026-10-13", "min-a"), ("2026-10-16", "min-b")])
        self.assertEqual(position["muscles"]["chest"], {"target": 10, "third": 3.33, "planned": 4, "met": True})
        self.assertEqual(position["priority"], [{"exercise_id": SQUAT, "floor_sets": 2, "sets": 4,
                                                 "session_id": "min-a", "met": True}])

    def test_three_sessions_fail(self):
        third = dict(MIN_A, id="min-c", title="Minimum C", exercises=[line("db_bench_press", "per_hand_x2", 2)])
        self.set_minimum(sessions=minimum_sessions() + [third], ids=("min-a", "min-b", "min-c"),
                         days={"tue": "min-a", "thu": "min-c", "fri": "min-b"})
        envelope = self.balance(expect=1)
        self.assertIn("at most 2", envelope["error"]["message"])
        self.assertFalse(envelope["data"]["passed"])

    def test_a_missing_priority_floor_fails_naming_the_lift(self):
        self.set_minimum(sessions=minimum_sessions(pull_up=False), priority=(SQUAT, "pull_up"))
        envelope = self.balance(expect=1)
        self.assertEqual(envelope["data"]["reasons"],
                         ["no session carries the priority floor of 2 working sets of Pull Up"])

    def test_chest_below_a_third_of_its_target_fails(self):
        self.set_minimum(sessions=minimum_sessions(bench_sets=2))
        envelope = self.balance(expect=1)
        self.assertEqual(envelope["data"]["reasons"],
                         ["chest: 2 fractional sets planned, below a third of its target of 10 (3.33)"])
        self.assertEqual(envelope["error"]["details"][0]["path"], "$.minimum_week")

    def test_a_session_over_its_cap_fails(self):
        (self.root / "config.toml").write_text(
            (self.root / "config.toml").read_text(encoding="utf-8") + "\n[sessions.cap_minutes]\nmin-a = 5\n",
            encoding="utf-8")
        envelope = self.balance(expect=1)
        self.assertEqual(len(envelope["data"]["reasons"]), 1)
        self.assertIn("min-a: estimated", envelope["data"]["reasons"][0])
        self.assertIn("over its 5 min cap", envelope["data"]["reasons"][0])

    def test_no_minimum_week_exits_1(self):
        self.edit_json("data/program.json", lambda doc: doc.update(minimum_week=None))
        self.assertIn("no minimum_week", self.balance(expect=1)["error"]["message"])


class MinimumPlanTest(MinimumCase):
    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()

    def test_write_then_propose_from_the_plan(self):
        data = self.data("structure", "minimum", "--week", "2026-W42", "--write")
        self.assertEqual(data["path"], ".coach/plans/2026-10-12-minimum.json")
        self.assertTrue(data["written"])
        self.assertTrue(data["balance"]["passed"])
        written = read_json(self.root / data["path"])
        self.assertEqual([(s["date"], s["session_id"]) for s in written["sessions"]],
                         [("2026-10-13", "min-a"), ("2026-10-16", "min-b")])
        proposal = self.data("propose", "week", "--week", "2026-W42", "--plan", str(self.root / data["path"]),
                             "--dry-run")
        doc = proposal["overlay"]
        self.assertEqual(doc["kind"], "weekly")
        self.assertEqual([(s["date"], s["session_id"]) for s in doc["sessions"]],
                         [("2026-10-13", "min-a"), ("2026-10-16", "min-b")])

    def test_the_written_plan_makes_the_week_a_minimum_week(self):
        self.assertNotEqual(self.data("structure", "week", "--week", "2026-W42")["kind"], "minimum")
        self.data("structure", "minimum", "--week", "2026-W42", "--write")
        self.assertEqual(self.data("structure", "week", "--week", "2026-W42")["kind"], "minimum")

    def test_without_write_or_with_dry_run_nothing_is_written(self):
        self.assertFalse(self.data("structure", "minimum", "--week", "2026-W42")["written"])
        self.assertFalse(self.data("structure", "minimum", "--week", "2026-W42", "--write", "--dry-run")["written"])
        self.assertFalse((self.root / ".coach" / "plans").exists())

    def test_a_week_starting_sunday_names_its_own_start(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('week_starts = "monday"', 'week_starts = "sunday"'),
                        encoding="utf-8")
        data = self.data("structure", "minimum", "--week", "2026-W42")
        self.assertEqual(data["path"], ".coach/plans/2026-10-11-minimum.json")
        self.assertEqual([s["date"] for s in data["plan"]["sessions"]], ["2026-10-13", "2026-10-16"])


class ProgramTest(MinimumCase):
    def problems(self):
        doc = read_json(self.root / "data" / "program.json")
        return [(e.path, e.message) for e in program.validate(doc, None, Library.load(self.root), self.root)]

    def test_the_fixture_is_valid(self):
        self.assertEqual(self.problems(), [])

    def test_a_priority_lift_no_session_holds_is_rejected(self):
        self.edit_json("data/program.json", lambda doc: doc["priority"].append(priority_entry("bb_deadlift")))
        self.assertEqual([p for p, _ in self.problems()], ["$.priority[1].exercise_id"])
        data = self.data("program", "validate", expect=1)
        self.assertIn("$.priority[1].exercise_id", json.dumps(data))

    def test_a_minimum_week_session_that_is_not_standby_is_rejected(self):
        self.edit_json("data/program.json", lambda doc: doc["minimum_week"]["sessions"].append("session-a"))
        self.assertEqual(self.problems(), [("$.minimum_week.sessions[2]",
                                            "session-a is active; a minimum-week session is standby")])

    def test_the_minimum_week_schedule_is_checked_like_the_programs(self):
        self.edit_json("data/program.json", lambda doc: doc["minimum_week"]["schedule"]["params"]["days"].update(
            sat="min-z"))
        self.assertEqual(self.problems(), [("$.minimum_week.schedule.params.days.sat", "no program session min-z")])

    def test_defaults_fill_on_load(self):
        self.edit_json("data/program.json", lambda doc: doc.update(priority=[{"exercise_id": SQUAT,
                                                                              "kpi": {"kind": "e1rm"}}]))
        loaded = program.load(self.root)
        self.assertEqual(loaded["priority"][0], priority_entry())

    def test_the_program_page_lists_priority_lifts_and_the_minimum_week(self):
        pages = program.render_all(self.root)
        text = pages["routine/program.md"]
        self.assertIn("## Priority lifts", text)
        self.assertIn("Back Squat (Barbell): KPI e1RM; floor 2 working sets at the prescribed RPE", text)
        self.assertIn("## Minimum week", text)


class MigrationTest(PriorityCase):
    def test_migrate_run_adds_empty_priority_and_no_minimum_week(self):
        def before(doc):
            doc["schema_version"] = 5
            del doc["priority"]
            del doc["minimum_week"]
        self.edit_json("data/program.json", before)
        data = self.data("migrate", "run")
        steps = {row["path"]: row["steps"] for row in data["files"]}
        self.assertEqual(steps["data/program.json"][0], "program/0005_priority_and_minimum_week")
        doc = read_json(self.root / "data" / "program.json")
        self.assertEqual((doc["priority"], doc["minimum_week"]), ([], None))
        self.assertEqual(doc["schema_version"], jsonio.current_version(jsonio.load_schema("program")))

    def test_overlay_step_lists_lost_approvals_and_keeps_the_lines(self):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        before = read_json(path)
        doc = copy.deepcopy(before)
        doc["schema_version"] = 3
        doc["approval"]["hash"] = overlay.approval_hash(doc)
        write_json(path, doc)
        data = self.data("migrate", "run")
        self.assertTrue(any(f"{WEEKLY} loses its approval" in n for n in data["notes"]), data["notes"])
        after = read_json(path)
        self.assertEqual(after["sessions"], before["sessions"])
        self.assertEqual(after["schema_version"], overlay.current_version())

    def test_a_priority_rule_id_is_a_valid_fold_marker(self):
        doc = overlay.load(self.root, WEEKLY)
        doc["sessions"][0]["exercises"][0]["fold"] = {"rule_id": "priority:bb_back_squat+db_bench_press",
                                                      "from_session_id": "session-b", "from_date": "2026-10-12",
                                                      "scope": "one_week"}
        found = [e.path for kind, e in overlay.problems(doc, self.root) if kind == overlay.SCHEMA_PROBLEM]
        self.assertEqual(found, [])
        doc["sessions"][0]["exercises"][0]["fold"]["rule_id"] = "priority:Back Squat"
        found = [e.path for kind, e in overlay.problems(doc, self.root) if kind == overlay.SCHEMA_PROBLEM]
        self.assertEqual(found, ["$.sessions[0].exercises[0].fold.rule_id"])


class RegistrationTest(PriorityCase):
    def test_the_flag_is_registered_to_r30b(self):
        entry = flags.registry()["priority_exposures_missed"]
        self.assertEqual((entry.owner, entry.severities, entry.structural), ("R-30b", ("warn",), False))

    def test_the_commands_are_allowlisted(self):
        allowed = set(read_json(REPO_ROOT / ".claude" / "settings.json")["permissions"]["allow"])
        for name in ("structure priority", "structure minimum"):
            self.assertIn(f"Bash(python3 -m coach {name}:*)", allowed)

    def test_the_check_in_skill_runs_structure_priority(self):
        text = skill_text("check-in")
        self.assertIn("python3 -m coach structure priority", text)
        self.assertIn("priority_exposures_missed", text)

    def test_program_week_offers_the_minimum_week(self):
        text = " ".join(skill_text("program-week").split())
        self.assertIn("python3 -m coach structure minimum", text)
        self.assertIn("--plan", text)
