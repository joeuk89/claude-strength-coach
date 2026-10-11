"""Interference rules: the plugin kind, the two framework rules, the provider and commands (contract C51)."""

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from coach import jsonio, migrate, plugins
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli

INTERFERENCE = INSTANCES / "interference"
CARDIO = INSTANCES / "cardio"
NOW = "2026-10-11T18:00:00Z"
SQUAT_DAY = "10000000-0000-4000-8000-000000000003"
DEFAULT_RULES = [
    {"name": "same_day", "params": {"min_gap_hours": 6, "lift_first": True}},
    {"name": "quality_before_heavy_lower", "params": {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6}},
]

CUSTOM_RULE = '''
"""A synthetic rule: names every quality activity in the span."""

from coach.plugins import base

API = 1
KIND = "interference"
NAME = "{name}"
SUMMARY = "Names every quality activity in the span."
PARAMS = {{"schema": base.EMPTY_SCHEMA, "defaults": {{}}}}
FLAGS = {{"custom_quality_seen": {{"severities": ["info"], "summary": "A quality activity is in the span."}}}}
CITES = ()


def evaluate(ctx):
    return [base.session_flag({code}, "quality activity on " + b.date.isoformat(), None)
            for b in base.quality_activities(ctx.bouts) if ctx.span.contains(b.date)]
'''

PLUGIN_TEST = '''
import unittest


class SyntheticTest(unittest.TestCase):
    def test_runs(self):
        self.assertTrue(True)
'''


def custom_rule(name, code='"custom_quality_seen"'):
    return CUSTOM_RULE.format(name=name, code=code)


class Case(unittest.TestCase):
    base = INTERFERENCE

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": NOW})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def data(self, *argv):
        return self.coach(*argv)["data"]

    def edit_json(self, relative, change):
        path = self.root / relative
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    def set_rules(self, rules):
        self.edit_json("data/program.json", lambda doc: doc.update(interference=rules))

    def planned(self, day, title, quality):
        argv = ["planned", "add", "--date", day, "--kind", "run", "--title", title, "--duration-min", "40"]
        self.coach(*argv, *(["--quality"] if quality else []))

    def proposal(self):
        return self.data("propose", "week", "--week", "2026-W42", "--dry-run")

    @staticmethod
    def collisions(found):
        return [f for f in found if f["code"] == "collision"]


class KindTest(unittest.TestCase):
    def test_the_framework_rules_are_valid_and_cite_the_concurrent_training_note(self):
        registry = plugins.load()
        self.assertEqual(registry.names("interference"), ["quality_before_heavy_lower", "same_day"])
        self.assertEqual(registry.get("interference", "same_day").module.CITES, ("rn:concurrent-training.4",))
        self.assertEqual(registry.get("interference", "quality_before_heavy_lower").module.CITES,
                         ("rn:concurrent-training.5",))

    def test_both_commands_are_allowlisted(self):
        allowed = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for name in ("interference list", "interference check"):
            self.assertIn(f"Bash(python3 -m coach {name}:*)", allowed["permissions"]["allow"])


class SkillTest(unittest.TestCase):
    def read(self, name):
        return (REPO_ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    def test_program_week_settles_collision_and_names_the_list_command(self):
        text = self.read("program-week")
        self.assertIn("`collision`", text)
        self.assertIn("python3 -m coach interference list", text)

    def test_check_in_names_collision_among_the_cardio_flags(self):
        self.assertIn("`collision` from the program's interference rules", self.read("check-in"))

    def test_new_program_sets_the_rules_in_a_designed_draft(self):
        text = self.read("new-program")
        self.assertIn("The program's `interference`", text)
        self.assertIn("python3 -m coach interference\n   list", text)


class MigrationTest(Case):
    base = VALID

    def test_the_step_adds_both_framework_rules_with_their_defaults(self):
        current = jsonio.current_version(jsonio.load_schema("program"))
        [step] = [s for s in migrate.registry().documents["program"].steps if s.name.endswith("_interference_rules")]
        self.assertLessEqual(step.to_version, current)

        def older(doc):
            doc["schema_version"] = step.from_version
            doc.pop("interference")
        self.edit_json("data/program.json", older)
        dry = self.data("migrate", "run", "--dry-run")
        self.assertEqual([(f["path"], f["from"], f["to"]) for f in dry["files"]],
                         [("data/program.json", step.from_version, current)])
        self.data("migrate", "run")
        shown = self.data("program", "show")["program"]
        self.assertEqual(shown["interference"], DEFAULT_RULES)
        self.assertTrue(self.data("program", "validate")["valid"])

    def test_list_shows_the_rules_and_params(self):
        data = self.data("interference", "list")
        self.assertEqual([(r["name"], r["params"]) for r in data["rules"]],
                         [(r["name"], r["params"]) for r in DEFAULT_RULES])
        self.assertEqual({r["source"] for r in data["rules"]}, {"framework"})
        self.assertEqual({r["name"] for r in data["available"]}, {"same_day", "quality_before_heavy_lower"})


class ProposalTest(Case):
    def test_a_quality_run_the_day_before_heavy_squats_is_one_collision_warn(self):
        found = self.collisions(self.proposal()["overlay"]["flags"])
        self.assertEqual(len(found), 1, found)
        [flag] = found
        self.assertEqual((flag["severity"], flag["session_id"]), ("warn", "session-a"))
        for words in ("quality_before_heavy_lower", "Tempo", "2026-10-11", "Session A", "2026-10-12"):
            self.assertIn(words, flag["message"])

    def test_a_quality_run_on_session_b_day_is_one_same_day_info(self):
        self.planned("2026-10-15", "Threshold", quality=True)
        found = [f for f in self.collisions(self.proposal()["overlay"]["flags"]) if "same_day" in f["message"]]
        self.assertEqual(len(found), 1, found)
        [flag] = found
        self.assertEqual((flag["severity"], flag["session_id"]), ("info", "session-b"))
        self.assertIn("lift first, keep at least 6 h between", flag["message"])

    def test_an_easy_run_on_session_b_day_adds_nothing(self):
        before = self.collisions(self.proposal()["overlay"]["flags"])
        self.planned("2026-10-15", "Easy 6 km", quality=False)
        self.assertEqual(self.collisions(self.proposal()["overlay"]["flags"]), before)

    def test_an_empty_list_turns_every_rule_off(self):
        self.set_rules([])
        self.assertEqual(self.collisions(self.proposal()["overlay"]["flags"]), [])
        self.assertEqual(self.data("interference", "list")["rules"], [])

    def test_rules_never_move_drop_or_reorder_a_session(self):
        def sessions(data):
            return [(s["date"], s["session_id"], [line["exercise_id"] for line in s["exercises"]])
                    for s in data["overlay"]["sessions"]]
        self.planned("2026-10-15", "Threshold", quality=True)
        with_rules = self.proposal()
        self.assertTrue(self.collisions(with_rules["overlay"]["flags"]))
        self.set_rules([])
        without = self.proposal()
        self.assertEqual(sessions(with_rules), sessions(without))
        self.assertEqual([line["text"] for line in with_rules["lines"]], [line["text"] for line in without["lines"]])

    def test_a_rule_with_no_plugin_fails_program_validate_naming_it(self):
        self.set_rules([{"name": "no_such_rule", "params": {}}])
        envelope = self.coach("program", "validate", expect=1)
        details = envelope["error"]["details"]
        self.assertIn("$.interference[0].name", [d["path"] for d in details])
        self.assertTrue(any("no_such_rule" in d["message"] for d in details), details)

    def test_bad_params_fail_program_validate(self):
        self.set_rules([{"name": "same_day", "params": {"min_gap_hours": -1}}])
        envelope = self.coach("program", "validate", expect=1)
        self.assertTrue(any(d["path"].startswith("$.interference[0].params") for d in envelope["error"]["details"]))

    def test_a_rule_listed_twice_fails_program_validate(self):
        self.set_rules(DEFAULT_RULES + DEFAULT_RULES[:1])
        envelope = self.coach("program", "validate", expect=1)
        self.assertIn("$.interference[2].name", [d["path"] for d in envelope["error"]["details"]])


class InstanceRuleTest(Case):
    def write_rule(self, name, source, with_test=True):
        path = self.root / "plugins" / "interference" / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        if with_test:
            test = self.root / "plugins" / "tests" / f"test_{name}.py"
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text(PLUGIN_TEST, encoding="utf-8")

    def test_a_custom_rule_with_its_test_is_discovered_and_runs(self):
        self.write_rule("custom_quality_seen", custom_rule("custom_quality_seen"))
        self.set_rules(DEFAULT_RULES + [{"name": "custom_quality_seen", "params": {}}])
        self.assertTrue(self.data("plugins", "validate")["valid"])
        self.assertTrue(self.data("program", "validate")["valid"])
        listed = {r["name"]: r for r in self.data("interference", "list")["rules"]}
        self.assertEqual(listed["custom_quality_seen"]["source"], "instance")
        found = [f for f in self.proposal()["overlay"]["flags"] if f["code"] == "custom_quality_seen"]
        self.assertEqual([f["message"] for f in found], ["quality activity on 2026-10-16"])

    def test_a_custom_rule_emitting_a_framework_code_fails_plugins_validate(self):
        self.write_rule("custom_collider", custom_rule("custom_collider", code='"collision"'))
        envelope = self.coach("plugins", "validate", expect=1)
        messages = [d["message"] for d in envelope["error"]["details"]]
        self.assertTrue(any("custom_collider" in m and "collision" in m for m in messages), messages)

    def test_a_framework_code_emitted_at_run_time_fails_the_proposal(self):
        self.write_rule("custom_sneaky", custom_rule("custom_sneaky", code='"collis" + "ion"'))
        self.set_rules([{"name": "custom_sneaky", "params": {}}])
        envelope = self.coach("propose", "week", "--week", "2026-W42", "--dry-run", expect=9)
        self.assertIn("custom_sneaky", envelope["error"]["message"])


class LoggedTest(Case):
    """The cardio fixture's squat day (workout 3, 2026-10-05) moved to 08:00–08:58 UTC where a test needs the morning."""

    base = CARDIO

    def activity(self, kind, start, minutes, rpe=None):
        argv = ["activity", "add", "--kind", kind, "--start", start, "--duration-min", str(minutes)]
        self.coach(*argv, *(["--rpe", str(rpe)] if rpe is not None else []))

    def check(self, week="2026-W41"):
        return self.collisions(self.data("interference", "check", "--week", week)["flags"])

    def squat_day(self, change):
        def edit(doc):
            for workout in doc["workouts"]:
                if workout["workout_id"] == SQUAT_DAY:
                    change(workout)
        self.edit_json("data/history/2026-10.json", edit)

    def morning_squats(self):
        self.squat_day(lambda w: w.update(start_time="2026-10-05T08:00:00Z", end_time="2026-10-05T08:58:00Z"))

    def test_the_fixture_week_has_no_collision(self):
        self.assertEqual(self.check(), [])

    def test_conditioning_ending_22_hours_before_heavy_squats_is_a_warn(self):
        self.activity("conditioning", "2026-10-04T19:40:00Z", 20)
        [flag] = self.check()
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("quality_before_heavy_lower", flag["message"])
        self.assertIn("ended 22 h before", flag["message"])

    def test_conditioning_ending_26_hours_before_is_none(self):
        self.activity("conditioning", "2026-10-04T15:40:00Z", 20)
        self.assertEqual(self.check(), [])

    def test_the_provider_puts_it_in_cardio_flags_too(self):
        self.activity("conditioning", "2026-10-04T19:40:00Z", 20)
        found = self.collisions(self.data("cardio", "flags", "--week", "2026-W41")["flags"])
        self.assertEqual(len(found), 1, found)

    def test_a_quality_run_two_hours_after_lifting_is_a_gap_warn(self):
        self.morning_squats()
        self.activity("run", "2026-10-05T10:58:00Z", 30, rpe=8)
        [flag] = self.check()
        self.assertEqual(flag["severity"], "warn")
        self.assertIn("same_day", flag["message"])
        self.assertIn("started 2 h after", flag["message"])

    def test_a_quality_run_seven_hours_after_lifting_is_none(self):
        self.morning_squats()
        self.activity("run", "2026-10-05T15:58:00Z", 30, rpe=8)
        self.assertEqual(self.check(), [])

    def test_a_quality_run_ending_seven_hours_before_lifting_is_an_order_warn(self):
        self.morning_squats()
        self.activity("run", "2026-10-05T00:30:00Z", 30, rpe=8)
        same_day = [f for f in self.check() if "same_day" in f["message"]]
        self.assertEqual(len(same_day), 1, same_day)
        self.assertEqual(same_day[0]["severity"], "warn")
        self.assertIn("came before", same_day[0]["message"])

    def test_an_easy_run_never_collides(self):
        self.morning_squats()
        self.activity("run", "2026-10-05T09:30:00Z", 30, rpe=4)
        self.activity("run", "2026-10-04T20:00:00Z", 30, rpe=4)
        self.assertEqual(self.check(), [])

    def test_rpe_6_sets_of_8_are_not_heavy_unless_heavy_rpe_is_6(self):
        def easier(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == "bb_back_squat":
                    for item in exercise["sets"]:
                        item.update(rpe=6, reps=8)
        self.squat_day(easier)
        self.activity("conditioning", "2026-10-04T19:40:00Z", 20)
        self.assertEqual(self.check(), [])
        rules = [dict(DEFAULT_RULES[0]), {"name": "quality_before_heavy_lower",
                                          "params": {"hours": 24, "heavy_rpe": 6, "heavy_max_reps": 6}}]
        self.set_rules(rules)
        self.assertEqual(len(self.check()), 1)

    def test_check_needs_a_week_or_a_span(self):
        self.coach("interference", "check", expect=2)


if __name__ == "__main__":
    unittest.main()
