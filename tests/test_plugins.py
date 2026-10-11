"""The plugin contract: loader, purity scan, parameter schemas, instance plugins (contract C23)."""

import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from coach import flags, jsonio, plugins
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
SHIPPED = {
    "scheme": ["assistance_ladder", "double_progression", "fixed_reps_rpe", "hold", "linear", "maintenance",
               "rpe_anchored", "wave_531"],
    "schedule": ["alternating_external_anchor", "explicit_calendar", "fixed_weekdays", "next_in_sequence"],
    "transform": ["light", "return", "scheme", "standard"],
}
R23A_CODES = {"no_data": ("warn",), "stalled": ("warn",), "rpe_drift": ("warn",), "return_week": ("info",),
              "return_after_illness": ("warn",), "constraint_applied": ("info",), "override_standing": ("info",),
              "scheme_reset": ("warn",), "rotation_unconfirmed": ("warn",)}

FIXED_LOAD_PLUGIN = '''
"""A synthetic scheme that proposes one load from its params."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "{name}"
SUMMARY = "Proposes the load its params name."
PARAMS = {{"schema": {{"type": "object", "additionalProperties": False,
                      "properties": {{"load": {{"type": "number", "minimum": 0}}}}}},
          "defaults": {{"load": 25}}}}
STATE = {{"schema": base.EMPTY_SCHEMA, "initial": {{}}}}
FLAGS = {{}}
CITES = ()


def propose(ctx):
    return base.Proposal(sets=base.with_load(base.expand(ctx.slot.sets), ctx.params["load"]),
                         rationale="Fixed load from the params", derived_from=base.baseline(ctx.exposures), state={{}})


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
'''

PLUGIN_TEST = '''
import unittest


class SyntheticTest(unittest.TestCase):
    def test_runs(self):
        self.assertTrue(True)
'''


def fixed_load_plugin(name):
    return FIXED_LOAD_PLUGIN.format(name=name)


class InstanceCase(unittest.TestCase):
    """A temp copy of the valid instance with helpers to add instance plugins."""

    base = VALID

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(self.base, self.root)

    def write_plugin(self, name, source, kind="schemes", with_test=True):
        path = self.root / "plugins" / kind / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        if with_test:
            test = self.root / "plugins" / "tests" / f"test_{name}.py"
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text(PLUGIN_TEST, encoding="utf-8")

    def coach(self, *argv, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env=NOW)
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def edit_program(self, change):
        path = self.root / "data" / "program.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


class ShippedPluginsTest(unittest.TestCase):
    def test_every_shipped_plugin_is_valid(self):
        registry = plugins.load()
        self.assertEqual(registry.problems(), [])
        for kind, names in SHIPPED.items():
            with self.subTest(kind=kind):
                self.assertEqual(registry.names(kind), names)

    def test_kinds_declare_their_functions(self):
        found = {k.kind: k.required for k in plugins.kinds().values()}
        self.assertEqual(found, {"scheme": ("propose", "decay"), "schedule": ("plan", "positions"),
                                 "transform": ("apply",)})

    def test_plugin_modules_pass_the_purity_scan(self):
        for path in sorted((REPO_ROOT / "coach" / "plugins").glob("*/*.py")):
            if path.name == "__init__.py":
                continue
            with self.subTest(path=path.name):
                self.assertEqual(plugins.scan_source(path.read_text(encoding="utf-8"), str(path)), [])

    def test_cites_resolve_to_current_template_claims(self):
        from coach import research
        notes = research.load_notes(REPO_ROOT)
        for plugin in plugins.load().plugins:
            for ref in plugin.module.CITES:
                with self.subTest(plugin=plugin.name, ref=ref):
                    self.assertIsNotNone(research.resolve(ref, notes))


class ScannerTest(unittest.TestCase):
    CAUGHT = {
        "y = x * 2": "multiplies by 2",
        "y = 0.5 * x": "multiplies by 2",
        "y = x / 2": "divides by 2",
        "x *= 2": "doubles or halves",
        "f = 0.45359237": "kg/lb",
        "open('notes.txt')": "calls open()",
        "eval('1')": "calls eval()",
        "import os": "imports os",
        "from pathlib import Path": "imports pathlib",
        "from coach import history": "imports coach",
        "import coach.units": "imports coach.units",
        "from coach import stats": "imports coach.stats",
        "import coach.stats": "imports coach.stats",
        "from coach.stats import e1rm_series": "imports coach.stats.e1rm_series",
        "import coach.plugins.base": "binds the whole coach package",
        "from coach.plugins.base import _flags": "private name",
        "base._validity.band_for(3)": "private attribute",
        "__builtins__": "uses __builtins__",
    }
    ALLOWED = [
        "from coach.plugins import base", "from coach.stats import e1rm, load_for, implied_rpe",
        "import coach.plugins.base as base", "import math", "from dataclasses import replace",
        "from typing import Optional", "from datetime import date, timedelta", "y = x * 3", "y = x * 0.9",
        "y = round(x / 4, 2)",
    ]

    def test_catches_io_imports_and_doubling(self):
        for source, words in self.CAUGHT.items():
            with self.subTest(source=source):
                found = plugins.scan_source(source)
                self.assertTrue(found, source)
                self.assertIn(words, " ".join(problem for _, problem in found))

    def test_allows_the_plugin_imports_and_ordinary_arithmetic(self):
        for source in self.ALLOWED:
            with self.subTest(source=source):
                self.assertEqual(plugins.scan_source(source), [])


class FlagCodesTest(unittest.TestCase):
    def test_every_r23a_code_is_registered(self):
        registry = flags.registry()
        for code, severities in R23A_CODES.items():
            with self.subTest(code=code):
                self.assertEqual(registry[code].owner, "R-23a")
                self.assertEqual(registry[code].severities, severities)
                self.assertFalse(registry[code].structural)
        owned = {code for code, entry in registry.items() if entry.owner == "R-23a"}
        self.assertEqual(owned, set(R23A_CODES))

    def test_evidence_expired_is_registered_for_r32(self):
        entry = flags.registry()["evidence_expired"]
        self.assertEqual((entry.owner, entry.severities), ("R-32", ("info",)))


class ProgramParamsTest(InstanceCase):
    def test_the_valid_program_validates(self):
        self.assertTrue(self.coach("program", "validate")["data"]["valid"])

    def test_a_misspelt_scheme_parameter_names_its_jsonpath(self):
        self.edit_program(lambda doc: doc["sessions"][0]["exercises"][0]["scheme"].update(params={"incremnt": 2.5}))
        envelope = self.coach("program", "validate", expect=1)
        paths = [d["path"] for d in envelope["error"]["details"]]
        self.assertIn("$.sessions[0].exercises[0].scheme.params.incremnt", paths)

    def test_an_unknown_scheme_name(self):
        self.edit_program(lambda doc: doc["sessions"][0]["exercises"][1]["scheme"].update(name="no_such_scheme"))
        envelope = self.coach("program", "validate", expect=1)
        [detail] = envelope["error"]["details"]
        self.assertEqual(detail["path"], "$.sessions[0].exercises[1].scheme.name")
        self.assertIn("no scheme named no_such_scheme", detail["message"])

    def test_schedule_and_deload_rule_names_and_params(self):
        def change(doc):
            doc["schedule"]["params"]["days"]["fri"] = "session-z"
            doc["blocks"]["deload_rule"] = {"name": "standard", "params": {"set_factr": 0.5}}
        self.edit_program(change)
        paths = [d["path"] for d in self.coach("program", "validate", expect=1)["error"]["details"]]
        self.assertIn("$.schedule.params.days.fri", paths)
        self.assertIn("$.blocks.deload_rule.params.set_factr", paths)

    def test_slot_constraints_take_the_load_constraint_shape(self):
        self.edit_program(lambda doc: doc["sessions"][0]["exercises"][0].update(constraints=["left knee"]))
        paths = [d["path"] for d in self.coach("program", "validate", expect=1)["error"]["details"]]
        self.assertIn("$.sessions[0].exercises[0].constraints[0]", paths)
        self.edit_program(lambda doc: doc["sessions"][0]["exercises"][0].update(
            constraints=[{"kind": "rpe_cap", "value": 12, "reason": "left knee"}]))
        paths = [d["path"] for d in self.coach("program", "validate", expect=1)["error"]["details"]]
        self.assertEqual(paths, ["$.sessions[0].exercises[0].constraints[0].value"])

    def test_fixed_reps_rpe_is_refused_on_a_line_without_an_e1rm_of_its_own(self):
        self.edit_program(lambda doc: doc["sessions"][1]["exercises"][1].update(
            scheme={"name": "fixed_reps_rpe", "params": {}}))
        [detail] = self.coach("program", "validate", expect=1)["error"]["details"]
        self.assertEqual(detail["path"], "$.sessions[1].exercises[1].scheme.name")
        self.assertIn("fixed_reps_rpe programs only total, per_hand_x2, single_implement lines; this slot is bodyweight",
                      detail["message"])
        shown = self.coach("plugins", "show", "fixed_reps_rpe")["data"]["plugins"][0]
        self.assertEqual(shown["load_modes"], ["total", "per_hand_x2", "single_implement"])

    def test_a_constraint_renders_in_words(self):
        self.edit_program(lambda doc: doc["sessions"][0]["exercises"][0].update(
            constraints=[{"kind": "rpe_cap", "value": 7, "reason": "left knee"}]))
        self.coach("program", "render")
        page = (self.root / "routine" / "session-a.md").read_text(encoding="utf-8")
        self.assertIn("constraint: RPE cap 7 (left knee)", page)


class MigrationTest(InstanceCase):
    def test_v1_program_and_state_upgrade_to_the_plugin_versions(self):
        program_path = self.root / "data" / "program.json"
        program = json.loads(program_path.read_text(encoding="utf-8"))
        program["schema_version"] = 1
        program["sessions"][0]["exercises"][0]["constraints"] = ["left knee: no deep flexion"]
        program_path.write_text(json.dumps(program), encoding="utf-8")
        state_path = self.root / "data" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state.update(schema_version=1, scheme_state={"session-a/bb_back_squat": {"sets_done": 3}})
        state["rotation"].pop("week")
        state["hevy"]["temporary_routines"] = []
        state["block"] = {"started": "2026-09-28", "hard_weeks_completed": 2,
                          "deload": {"status": "not_due", "since": None}}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        data = self.coach("migrate", "run")["data"]
        steps = {row["path"]: (row["from"], row["to"]) for row in data["files"]}
        self.assertEqual(steps["data/program.json"], (1, jsonio.current_version(jsonio.load_schema("program"))))
        self.assertEqual(steps["data/state.json"], (1, jsonio.current_version(jsonio.load_schema("state"))))
        self.assertTrue(any("left knee: no deep flexion" in note for note in data["notes"]))
        program = json.loads(program_path.read_text(encoding="utf-8"))
        self.assertEqual(program["sessions"][0]["exercises"][0]["constraints"], [])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["scheme_state"], {"session-a/bb_back_squat": {
            "scheme": None, "data": {"sets_done": 3}, "pending": None}})
        self.assertIsNone(state["rotation"]["week"])
        self.assertTrue(self.coach("program", "validate")["data"]["valid"])
        self.coach("state", "show")


class InstancePluginTest(InstanceCase):
    def test_a_valid_instance_plugin_is_listed_and_valid(self):
        self.write_plugin("custom_test", fixed_load_plugin("custom_test"))
        listed = {p["name"]: p for p in self.coach("plugins", "list")["data"]["plugins"]}
        self.assertEqual(listed["custom_test"]["source"], "instance")
        self.assertTrue(listed["custom_test"]["valid"])
        self.assertTrue(self.coach("plugins", "validate")["data"]["valid"])
        shown = self.coach("plugins", "show", "custom_test")["data"]["plugins"][0]
        self.assertEqual(shown["params"]["defaults"], {"load": 25})

    def test_a_plugin_without_its_test_file_fails(self):
        self.write_plugin("custom_test", fixed_load_plugin("custom_test"), with_test=False)
        details = self.coach("plugins", "validate", expect=1)["error"]["details"]
        self.assertTrue(any("test_custom_test.py" in d["message"] for d in details), details)

    def test_a_plugin_named_like_a_framework_plugin_collides(self):
        self.write_plugin("linear", fixed_load_plugin("linear"))
        details = self.coach("plugins", "validate", expect=1)["error"]["details"]
        self.assertTrue(any("collides with the framework scheme linear" in d["message"] for d in details), details)
        self.assertEqual(plugins.load(self.root).get("scheme", "linear").source, "framework")

    def test_a_plugin_that_doubles_or_opens_a_file_is_never_imported(self):
        source = fixed_load_plugin("custom_doubler").replace('ctx.params["load"]', 'ctx.params["load"] * 2')
        self.write_plugin("custom_doubler", source)
        self.write_plugin("custom_reader", fixed_load_plugin("custom_reader") + "\nNOTES = open('x').read()\n")
        registry = plugins.load(self.root)
        for name, words in (("custom_doubler", "multiplies by 2"), ("custom_reader", "calls open()")):
            with self.subTest(name=name):
                [plugin] = registry.find(name)
                self.assertIsNone(plugin.module)
                self.assertTrue(any(words in p for p in plugin.problems), plugin.problems)

    def test_shape_problems(self):
        source = fixed_load_plugin("custom_shape").replace('NAME = "custom_shape"', 'NAME = "other"').replace(
            "FLAGS = {}", 'FLAGS = {"bad_code": {"severities": ["warn"], "summary": "x"}}').replace(
            "CITES = ()", 'CITES = ("rn:local-knee.1",)\nLOAD_MODES = ("total", "kettlebell")')
        self.write_plugin("custom_shape", source)
        [plugin] = plugins.load(self.root).find("custom_shape")
        text = " | ".join(plugin.problems)
        self.assertIn("NAME is 'other'", text)
        self.assertIn("must start custom_", text)
        self.assertIn("local claim", text)
        self.assertIn("LOAD_MODES must be a tuple of load modes", text)

    def test_instance_flags_are_registered(self):
        saved = dict(flags.registry())
        self.addCleanup(lambda: (flags._REGISTRY.clear(), flags._REGISTRY.update(saved)))
        source = fixed_load_plugin("custom_flagged").replace(
            "FLAGS = {}", 'FLAGS = {"custom_watch": {"severities": ["info"], "summary": "A synthetic code."}}')
        self.write_plugin("custom_flagged", source)
        self.assertTrue(plugins.load(self.root).get("scheme", "custom_flagged").valid)
        self.assertEqual(flags.registry()["custom_watch"].severities, ("info",))

    def test_plugins_test_runs_the_instance_tests(self):
        self.write_plugin("custom_test", fixed_load_plugin("custom_test"))
        self.assertTrue(self.coach("plugins", "test")["data"]["passed"])
        (self.root / "plugins" / "tests" / "test_custom_test.py").write_text(
            PLUGIN_TEST.replace("assertTrue(True)", "assertTrue(False)"), encoding="utf-8")
        self.coach("plugins", "test", expect=1)


class ChecksTest(unittest.TestCase):
    def check(self, root, check_id):
        code, envelope, _ = run_cli(["--root", str(root), "check", "--only", check_id], env=NOW)
        return code, [r for r in envelope["data"]["results"] if r["id"] == check_id]

    def test_plugins_valid_passes_and_fails(self):
        code, results = self.check(VALID, "plugins_valid")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["pass"]))
        code, results = self.check(INSTANCES / "plugins-invalid", "plugins_valid")
        self.assertEqual(code, 1)
        self.assertIn("test_custom_untested.py", results[0]["message"])
        self.assertEqual(results[0]["path"], "plugins/schemes/custom_untested.py")

    def test_decisions_schema_passes_skips_and_fails(self):
        code, results = self.check(VALID, "decisions_schema")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["skip"]))
        code, results = self.check(INSTANCES / "decisions-invalid", "decisions_schema")
        self.assertEqual(code, 1)
        self.assertIn("$.decisions[0].until", results[0]["message"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "decisions-invalid", root)
            path = root / "data" / "decisions.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["decisions"][0]["until"] = "2026-11-08"
            path.write_text(json.dumps(doc), encoding="utf-8")
            code, results = self.check(root, "decisions_schema")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["pass"]))


if __name__ == "__main__":
    unittest.main()
