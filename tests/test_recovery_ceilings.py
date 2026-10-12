"""An RPE ceiling changes the work the line prescribes, not only its printed RPE (contract C22, C24, C26)."""

import textwrap

from coach import stats
from tests.support.history import read_json, write_json
from tests.test_block import BlockCase
from tests.test_conditioning import CircuitCase
from tests.test_plugins import PLUGIN_TEST
from tests.test_propose import coaching, find_line, working

WEEK = "2026-W42"
SQUAT_E1RM = 120.33
MODEL_CODES = ("rpe_infeasible", "unearned_load")

FIVE_MORE_PLUGIN = '''
"""A synthetic scheme that adds 5 to the derived-from top load."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "custom_five_more"
SUMMARY = "Proposes the derived-from top load plus 5."
PARAMS = {"schema": {"type": "object", "additionalProperties": False, "properties": {}}, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ()


def propose(ctx):
    source = base.baseline(ctx.exposures)
    sets = base.with_load(base.expand(ctx.slot.sets), (source.top_load or 0) + 5)
    return base.Proposal(sets=sets, rationale="Five more", derived_from=source, state={})


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
'''


def line_codes(doc, exercise_id):
    return [f["code"] for f in doc["flags"] if f["exercise_id"] == exercise_id]


def line_flag(doc, exercise_id, code):
    [flag] = [f for f in doc["flags"] if f["exercise_id"] == exercise_id and f["code"] == code]
    return flag


class CeilingCase(BlockCase):
    def cap(self, exercise_id, value=6, status="aggravated"):
        self.data("niggles", "add", "--area", "synthetic lower back", "--status", status, "--exercise", exercise_id,
                  "--constraint", f"rpe_cap={value}")

    def propose(self, *extra):
        return self.data("propose", "week", "--week", WEEK, "--dry-run", *extra)["overlay"]

    def loads(self, doc, exercise_id):
        return {coaching(s["load"]) for s in working(find_line(doc, exercise_id))}

    def rpes(self, doc, exercise_id):
        return {s["rpe"] for s in working(find_line(doc, exercise_id))}

    def edit_squat_sets(self, change):
        for path in sorted((self.root / "data" / "history").glob("2026-*.json")):
            doc = read_json(path)
            for workout in doc["workouts"]:
                for exercise in workout["exercises"]:
                    if exercise["exercise_id"] == "bb_back_squat":
                        for logged in exercise["sets"]:
                            change(logged)
            write_json(path, doc)

    def edit_config(self, old, new):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def use_plugin(self, exercise_id):
        plugins = self.root / "plugins"
        (plugins / "schemes").mkdir(parents=True, exist_ok=True)
        (plugins / "schemes" / "custom_five_more.py").write_text(textwrap.dedent(FIVE_MORE_PLUGIN), encoding="utf-8")
        (plugins / "tests").mkdir(parents=True, exist_ok=True)
        (plugins / "tests" / "test_custom_five_more.py").write_text(PLUGIN_TEST, encoding="utf-8")

        def edit(doc):
            for session in doc["sessions"]:
                for exercise in session["exercises"]:
                    if exercise["exercise_id"] == exercise_id:
                        exercise["scheme"] = {"name": "custom_five_more", "params": {}}
        self.edit("data/program.json", edit)


class ModelCeilingTest(CeilingCase):
    def test_a_cap_brings_the_load_down_to_what_the_model_allows_at_it(self):
        self.cap("bb_back_squat")
        doc = self.propose()
        squat = working(find_line(doc, "bb_back_squat"))
        self.assertEqual({(s["reps"], s["rpe"], coaching(s["load"])) for s in squat}, {(5, 6, 92.5)})
        self.assertLessEqual(92.5, stats.load_for(SQUAT_E1RM, 5, 6))
        for code in MODEL_CODES:
            self.assertNotIn(code, line_codes(doc, "bb_back_squat"))
        message = line_flag(doc, "bb_back_squat", "constraint_applied")["message"]
        self.assertIn("at RPE 6 the e1RM of 120.33 from 2026-10-05 allows at most 92.56 for 5 reps, so 92.5", message)
        self.assertNotIn("rpe_ceiling_unchecked", line_codes(doc, "bb_back_squat"))

    def test_lines_without_a_ceiling_are_unchanged(self):
        before = self.propose()
        self.assertEqual((self.loads(before, "bb_back_squat"), self.rpes(before, "bb_back_squat")), ({95}, {7}))
        self.cap("bb_back_squat")
        after = self.propose()
        for exercise_id in ("db_bench_press", "db_single_arm_row", "pull_up"):
            with self.subTest(exercise=exercise_id):
                self.assertEqual(find_line(after, exercise_id)["sets"], find_line(before, exercise_id)["sets"])

    def test_a_cap_the_load_already_meets_keeps_the_load(self):
        self.cap("bb_back_squat", value=7)
        doc = self.propose()
        self.assertEqual((self.loads(doc, "bb_back_squat"), self.rpes(doc, "bb_back_squat")), ({95}, {7}))
        self.assertNotIn("rpe_ceiling_unchecked", line_codes(doc, "bb_back_squat"))

    def test_the_illness_cap_lowers_the_load_too(self):
        self.edit_squat_sets(lambda logged: logged.update(rpe=8))
        self.data("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-b",
                  "--tag", "ill")
        doc = self.propose()
        self.assertEqual(self.rpes(doc, "bb_back_squat"), {7})
        [load] = self.loads(doc, "bb_back_squat")
        self.assertLessEqual(load, stats.load_for(95 * (1 + 7 / 30), 5, 7) + 1e-9)
        self.assertLess(load, 95)
        for code in MODEL_CODES:
            self.assertNotIn(code, line_codes(doc, "bb_back_squat"))

    def test_a_light_week_rpe_cap_lowers_the_load_too(self):
        self.edit("data/program.json", lambda doc: doc["blocks"].update(
            deload_rule={"name": "light", "params": {"rpe_cap": 5}}))
        doc = self.propose("--kind", "deload")
        self.assertEqual(self.rpes(doc, "bb_back_squat"), {5})
        self.assertEqual(self.loads(doc, "bb_back_squat"), {90})
        self.assertLessEqual(90, stats.load_for(SQUAT_E1RM, 5, 5))
        for code in MODEL_CODES:
            self.assertNotIn(code, line_codes(doc, "bb_back_squat"))

    def test_a_standing_override_keeps_the_ceiling(self):
        proposal = self.data("propose", "week", "--week", WEEK)["id"]
        self.data("propose", "override", "--proposal", proposal, "--session", "session-a", "--exercise",
                  "bb_back_squat", "--sets", "3x5@97.5 rpe7", "--reason", "synthetic: agreed hold", "--standing")
        self.cap("bb_back_squat")
        doc = self.propose()
        self.assertIn("override_standing", line_codes(doc, "bb_back_squat"))
        self.assertEqual((self.loads(doc, "bb_back_squat"), self.rpes(doc, "bb_back_squat")), ({92.5}, {6}))
        self.assertIn("allows at most 92.56", find_line(doc, "bb_back_squat")["provenance"]["rationale"])


class KitCeilingTest(CeilingCase):
    def test_a_coarse_kit_rounds_under_the_ceiling_never_over_it(self):
        self.edit_config("plates = [25, 20, 15, 10, 5, 2.5, 1.25]", "plates = [25]")
        self.cap("bb_back_squat")
        doc = self.propose()
        self.assertEqual(self.loads(doc, "bb_back_squat"), {70})
        rationale = find_line(doc, "bb_back_squat")["provenance"]["rationale"]
        self.assertIn("allows at most 92.56 for 5 reps, so 70", rationale)
        self.assertNotIn("rpe_ceiling_unchecked", line_codes(doc, "bb_back_squat"))

    def test_a_kit_with_nothing_under_the_ceiling_leaves_the_choice_to_the_coach(self):
        self.edit_config("dumbbells = []", "dumbbells = [25, 30]")
        self.cap("db_bench_press")
        doc = self.propose()
        self.assertEqual(self.loads(doc, "db_bench_press"), {25})
        flag = line_flag(doc, "db_bench_press", "rpe_ceiling_unchecked")
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("allows at most 22.5/hand (Hevy: 45) for 8 reps at RPE 6, but the kit makes nothing that light",
                      flag["message"])
        self.assertIn("choose the load", flag["message"])


class UncheckedCeilingTest(CeilingCase):
    def test_a_bodyweight_line_says_the_cap_is_unchecked(self):
        self.cap("pull_up")
        doc = self.propose()
        self.assertEqual(self.rpes(doc, "pull_up"), {6})
        flag = line_flag(doc, "pull_up", "rpe_ceiling_unchecked")
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("the e1RM model does not judge a bodyweight line", flag["message"])
        self.assertIn("review the load with the athlete", flag["message"])
        self.assertNotIn("allows at most", flag["message"])

    def test_an_estimate_from_unrated_sets_holds_the_load_instead_of_progressing(self):
        self.edit_squat_sets(lambda logged: logged.update(rpe=None))
        self.use_plugin("bb_back_squat")
        self.assertEqual(self.loads(self.propose(), "bb_back_squat"), {100})
        self.cap("bb_back_squat")
        doc = self.propose()
        self.assertEqual((self.loads(doc, "bb_back_squat"), self.rpes(doc, "bb_back_squat")), ({95}, {6}))
        flag = line_flag(doc, "bb_back_squat", "rpe_ceiling_unchecked")
        self.assertIn("a lower bound", flag["message"])
        self.assertIn("goes no further than 95, logged 2026-10-05", flag["message"])
        self.assertNotIn("allows at most", find_line(doc, "bb_back_squat")["provenance"]["rationale"])

    def test_with_no_squat_history_the_start_load_stands_for_the_coach_to_review(self):
        for path in sorted((self.root / "data" / "history").glob("2026-*.json")):
            doc = read_json(path)
            for workout in doc["workouts"]:
                workout["exercises"] = [e for e in workout["exercises"] if e["exercise_id"] != "bb_back_squat"]
            write_json(path, doc)
        self.cap("bb_back_squat")
        doc = self.propose()
        self.assertEqual(self.rpes(doc, "bb_back_squat"), {6})
        flag = line_flag(doc, "bb_back_squat", "rpe_ceiling_unchecked")
        self.assertIn("e1RM unavailable", flag["message"])
        self.assertIn("no logged load to hold", flag["message"])
        self.assertNotIn("allows at most", flag["message"])


class ConditioningCeilingTest(CircuitCase):
    def test_a_capped_conditioning_line_holds_its_load_and_says_the_cap_is_unchecked(self):
        self.data("niggles", "add", "--area", "synthetic lower back", "--status", "aggravated", "--exercise",
                  "kb_swing", "--constraint", "rpe_cap=6")
        doc = self.propose("--dry-run")["overlay"]
        swings = self.circuit_lines(doc)["kb_swing"]
        self.assertEqual({s["load"]["per_hand"] for s in swings["sets"]}, {24})
        [flag] = [f for f in doc["flags"] if f["code"] == "rpe_ceiling_unchecked" and f["exercise_id"] == "kb_swing"]
        self.assertIn("n-0001 RPE cap 6 cannot be checked against an e1RM on a conditioning line", flag["message"])
        self.assertEqual([f for f in doc["flags"] if f["code"] == "rpe_ceiling_unchecked"
                          and f["exercise_id"] == "burpee"], [])
