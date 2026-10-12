"""Balance for a program draft, major-muscle coverage, goal-aware dose targets and run-mode checks (contract C40, C41)."""

import copy
import unittest
from unittest import mock

from coach import config as config_module
from coach import jsonio, migrate, program, structure
from coach.checks import structure as structure_check
from coach.library import MUSCLES
from tests.support import INSTANCES, VALID
from tests.support.history import read_json, write_json
from tests.support.skills import flat, step_text
from tests.test_structure import DOSE, StructureCase, codes

EMPTY = INSTANCES / "empty"
DRAFT = ".coach/drafts/program.json"
RUN = '\n[coaching]\nmode = "run"\n'


def messages(found, code):
    return [f["message"] for f in found if f["code"] == code]


def running_session(session_id):
    return {"id": session_id, "title": "Easy run", "kind": "conditioning", "tier": "core", "status": "active",
            "location": None, "focus": None, "scheme": None, "exercises": [{
                "exercise_id": "running", "load_mode": "duration",
                "sets": [{"count": 1, "type": "normal", "duration_seconds": 2400}], "rest_seconds": None,
                "superset_id": None, "cues": None, "constraints": [], "scheme": {"name": "hold", "params": {}},
                "start_load": None}]}


class FirstProgramDraftTest(StructureCase):
    """A fresh workspace with no adopted program checks a starter draft before adopting it."""

    base = EMPTY

    def setUp(self):
        super().setUp()
        self.data("starters", "draft", "full-body-3")
        self.draft = read_json(self.root / DRAFT)

    def test_a_starter_draft_balances_without_an_adopted_program_and_adopts_nothing(self):
        data = self.data("structure", "balance", "--program", str(self.root / DRAFT))
        self.assertEqual(data["targets"], dict(sorted(self.draft["program"]["dose_targets"].items())))
        self.assertEqual(set(data["coverage"]), set(structure.COVERAGE))
        self.assertEqual(data["coverage"]["chest"], "planned")
        self.assertEqual((data["compared_with"], data["added"], data["adherence"]), (None, [], None))
        self.assertIn("dose_coverage_gap", codes(data["flags"]))
        self.assertFalse((self.root / "data" / "program.json").exists())
        self.assertFalse((self.root / "data" / "state.json").exists())

    def test_the_bare_inner_program_balances_the_same(self):
        path = self.root / "candidate.json"
        write_json(path, self.draft["program"])
        bare = self.data("structure", "balance", "--program", str(path))
        wrapped = self.data("structure", "balance", "--program", str(self.root / DRAFT))
        self.assertEqual(bare, wrapped)
        self.assertFalse((self.root / "data" / "program.json").exists())

    def test_an_invalid_wrapper_and_an_invalid_inner_program_name_their_paths(self):
        broken = copy.deepcopy(self.draft)
        del broken["source"]
        write_json(self.root / "broken.json", broken)
        error = self.coach("structure", "balance", "--program", str(self.root / "broken.json"), expect=1)["error"]
        self.assertIn("not a valid program draft", error["message"])
        self.assertTrue(any("source" in d["message"] or d["path"] == "$.source" for d in error["details"]), error)

        broken = copy.deepcopy(self.draft)
        broken["program"]["dose_targets"]["pecs"] = 10
        write_json(self.root / "broken.json", broken)
        error = self.coach("structure", "balance", "--program", str(self.root / "broken.json"), expect=1)["error"]
        self.assertIn("$.program.dose_targets.pecs", [d["path"] for d in error["details"]])


class RedesignDraftTest(StructureCase):
    """With an adopted program, a draft is compared with it for new sessions under the adherence rules."""

    base = DOSE

    def test_a_draft_adding_a_session_reports_it_and_the_adherence_behind_the_block(self):
        current = read_json(self.root / "data" / "program.json")
        current["sessions"].append(running_session("run-sat"))
        current["schedule"]["params"]["days"]["sat"] = "run-sat"
        draft = {"schema_version": 2, "source": "design", "created_at": "2026-10-11T18:00:00Z", "program": current,
                 "position": None, "hevy_routines": {}, "hevy_folder": None, "report": [],
                 "detected": {"percentage_based": False, "evidence": [], "suggested_schemes": []}}
        write_json(self.root / "draft.json", draft)
        data = self.data("structure", "balance", "--program", str(self.root / "draft.json"))
        self.assertEqual((data["compared_with"], data["added"], data["adherence"]["pct"]),
                         ("data/program.json", ["run-sat"], 58))
        self.assertIn("add_session_type_blocked", codes(data["flags"]))


class CoverageTest(StructureCase):
    """The squat, DB bench, row and pull-up program in valid/ trains no hamstrings, calves, side delts or abs."""

    base = VALID

    def targets(self, targets, reasons=None):
        def change(doc):
            doc["dose_targets"] = targets
            if reasons is not None:
                doc["dose_intent"] = {"goal": "hypertrophy", "reasons": reasons}
        self.edit("data/program.json", change)

    def test_untrained_major_muscles_show_at_zero_with_a_coverage_gap(self):
        data = self.data("structure", "balance")
        for muscle in ("hamstrings", "calves"):
            self.assertEqual((data["muscles"][muscle]["average"], data["muscles"][muscle]["target"]), (0, None))
            self.assertEqual(data["coverage"][muscle], "gap")
        gaps = messages(data["flags"], "dose_coverage_gap")
        self.assertEqual(sorted(m.split(":")[0] for m in gaps), ["abdominals", "calves", "hamstrings", "side_delts"])

    def test_secondary_credit_stays_without_a_primary_exercise(self):
        muscles = self.data("structure", "balance")["muscles"]
        self.assertEqual({m: muscles[m]["average"] for m in ("biceps", "triceps", "front_delts", "rear_delts")},
                         {"biceps": 3, "triceps": 1.5, "front_delts": 1.5, "rear_delts": 1.5})

    def test_an_explicit_target_undershoots_and_other_gaps_stay(self):
        self.targets({"hamstrings": 6})
        data = self.data("structure", "balance")
        self.assertEqual(data["muscles"]["hamstrings"]["source"], "explicit")
        self.assertIn("hamstrings: planned 0 fractional sets a week on core and coach-led sessions, below its "
                      "target of 6", messages(data["flags"], "volume_undershoot"))
        gaps = [m.split(":")[0] for m in messages(data["flags"], "dose_coverage_gap")]
        self.assertNotIn("hamstrings", gaps)
        self.assertIn("calves", gaps)

    def test_an_agreed_zero_with_a_reason_is_a_visible_omission(self):
        reason = "hamstrings come from the athlete's twice-weekly hill sprints for now"
        self.targets({"hamstrings": 0}, {"hamstrings": reason})
        data = self.data("structure", "balance")
        self.assertEqual(data["muscles"]["hamstrings"],
                         {"target": 0, "average": 0, "met": True, "source": "omitted", "baseline": None,
                          "reason": reason})
        self.assertEqual(data["coverage"]["hamstrings"], "omitted")
        flagged = [m.split(":")[0] for f in data["flags"] for m in [f["message"]]]
        self.assertNotIn("hamstrings", flagged)
        self.assertIn("calves", flagged)

    def test_a_zero_without_a_reason_is_still_a_gap(self):
        self.targets({"hamstrings": 0})
        data = self.data("structure", "balance")
        self.assertIn("hamstrings: target 0 with no reason recorded; record why in dose_intent.reasons, or agree "
                      "a target", messages(data["flags"], "dose_coverage_gap"))


class DoseIntentTest(StructureCase):
    base = VALID

    def intent(self, intent, targets=None):
        def change(doc):
            doc["dose_intent"] = intent
            if targets is not None:
                doc["dose_targets"] = targets
        self.edit("data/program.json", change)

    def test_explicit_targets_without_intent_keep_validating_and_evaluating(self):
        self.edit("data/program.json", lambda doc: doc.update(dose_targets={"chest": 3}))
        self.data("program", "validate")
        data = self.data("structure", "balance")
        self.assertIsNone(data["goal"])
        self.assertEqual((data["muscles"]["chest"]["target"], data["muscles"]["chest"]["met"]), (3, True))
        self.assertEqual(data["muscles"]["lats"]["source"], "fallback")
        self.assertTrue(any("hypertrophy starting fallback" in note for note in data["notes"]))

    def test_a_nutrition_phase_does_not_select_a_lifting_goal(self):
        for phase in ("cut", "maintain"):
            with self.subTest(phase=phase):
                path = self.root / "config.toml"
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace('phase = "recomp"', f'phase = "{phase}"').replace(
                    'phase = "cut"', f'phase = "{phase}"'), encoding="utf-8")
                data = self.data("structure", "balance")
                self.assertIsNone(data["goal"])
                self.assertEqual(data["targets"]["chest"], structure.DEFAULT_TARGET)

    def test_maintenance_without_targets_or_baseline_is_pending_not_a_default(self):
        self.intent({"goal": "maintenance"})
        data = self.data("structure", "balance")
        self.assertEqual(data["targets"], {})
        self.assertEqual((data["muscles"]["chest"]["source"], data["muscles"]["chest"]["target"]), ("pending", None))
        self.assertIn("chest: planned 3 fractional sets a week with no agreed maintenance target; record the "
                      "ordinary baseline in dose_intent.baseline and agree a target from it",
                      messages(data["flags"], "dose_target_pending"))
        self.assertNotIn("volume_undershoot", codes(data["flags"]))

    def test_maintenance_judges_the_agreed_reduced_target_not_10_or_a_third(self):
        def change(doc):
            doc["sessions"][0]["exercises"][1]["sets"][0]["count"] = 4
            doc["dose_intent"] = {"goal": "maintenance", "baseline": {"chest": 12, "lats": 12},
                                  "reasons": {"chest": "kept a third of the athlete's own 12 sets while travelling"}}
            doc["dose_targets"] = {"chest": 4}
        self.edit("data/program.json", change)
        data = self.data("structure", "balance")
        self.assertEqual(data["muscles"]["chest"]["target"], 4)
        self.assertEqual((data["muscles"]["chest"]["met"], data["muscles"]["chest"]["baseline"]), (True, 12))
        self.assertEqual(data["targets"], {"chest": 4})
        self.assertEqual(data["muscles"]["lats"]["target"], None)
        self.assertIn("lats: planned 6 fractional sets a week with no agreed maintenance target; agree one from the "
                      "ordinary baseline of 12 recorded", messages(data["flags"], "dose_target_pending"))

    def test_an_older_lifter_on_maintenance_sees_the_caveat_not_a_third(self):
        self.intent({"goal": "maintenance", "baseline": {"chest": 12}}, {"chest": 8})
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("[athlete]\n", "[athlete]\nbirth_year = 1960\n"), encoding="utf-8")
        notes = self.data("structure", "balance")["notes"]
        self.assertTrue(any("rn:minimum-effective-dose.2" in note and "about 66" in note for note in notes), notes)
        path.write_text(text.replace("[athlete]\n", "[athlete]\nbirth_year = 1990\n"), encoding="utf-8")
        notes = self.data("structure", "balance")["notes"]
        self.assertFalse(any("minimum-effective-dose.2" in note for note in notes), notes)

    def test_unsupported_intent_and_malformed_metadata_fail_validation(self):
        cases = (({"goal": "endurance"}, None, "$.dose_intent.goal"),
                 ({"goal": "maintenance", "baseline": {"pecs": 12}}, None, "$.dose_intent.baseline.pecs"),
                 ({"goal": "maintenance", "baseline": {"chest": "twelve"}}, None, "$.dose_intent.baseline.chest"),
                 ({"baseline": {"chest": 12}}, None, "$.dose_intent"),
                 ({"goal": "strength", "reasons": {"calves": "skipped"}}, {}, "$.dose_intent.reasons.calves"))
        original = read_json(self.root / "data" / "program.json")
        for intent, targets, path in cases:
            with self.subTest(path=path, intent=intent):
                write_json(self.root / "data" / "program.json", original)
                self.intent(intent, targets)
                error = self.coach("program", "validate", expect=1)["error"]
                self.assertTrue(any(d["path"].startswith(path) for d in error["details"]), error["details"])

    def test_the_reasons_and_baseline_schemas_list_every_library_muscle(self):
        schema = jsonio.load_schema("program")
        self.assertEqual(tuple(schema["$defs"]["dose_reasons"]["properties"]), MUSCLES)
        self.assertEqual(schema["properties"]["dose_intent"]["properties"]["baseline"],
                         {"$ref": "#/$defs/dose_targets"})

    def test_migrate_run_takes_a_v8_program_to_no_recorded_intent(self):
        current = program.SCHEMA
        [step] = [s for s in migrate.registry().documents[current].steps if s.name.endswith("_dose_intent")]
        self.edit("data/program.json", lambda doc: doc.update(schema_version=step.from_version))
        self.data("migrate", "run")
        migrated = read_json(self.root / "data" / "program.json")
        self.assertEqual(migrated["schema_version"], step.to_version)
        self.assertNotIn("dose_intent", migrated)
        self.assertIsNone(program.load(self.root)["dose_intent"])


class RunnerTest(StructureCase):
    """Running adds context, never resistance sets."""

    base = VALID

    def test_running_sessions_leave_the_hard_set_counts_alone_and_show_as_context(self):
        lifting = self.data("structure", "balance")

        def change(doc):
            doc["sessions"] += [running_session("run-tue"), running_session("run-sat")]
            doc["schedule"]["params"]["days"].update(tue="run-tue", sat="run-sat")
        self.edit("data/program.json", change)
        runner = self.data("structure", "balance")
        self.assertEqual(runner["muscles"], lifting["muscles"])
        self.assertEqual(runner["targets"], lifting["targets"])
        self.assertEqual([(c["session_id"], c["per_week"]) for c in runner["conditioning"]],
                         [("run-sat", 1), ("run-tue", 1)])
        self.assertTrue(any("count no resistance sets" in note for note in runner["notes"]), runner["notes"])
        self.assertEqual(lifting["conditioning"], [])


class RunModeCheckTest(StructureCase):
    base = VALID

    def check_rows(self):
        return self.coach("check", "--only", "program_balance")["data"]["results"]

    def test_structural_concerns_are_informational_in_run_mode_in_balance_and_the_check(self):
        coached = self.check_rows()
        self.assertEqual({r["status"] for r in coached}, {"warn"})
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + RUN, encoding="utf-8")
        run = self.check_rows()
        self.assertEqual(len(run), len(coached))
        self.assertEqual({r["status"] for r in run}, {"pass"})
        self.assertTrue(all("run mode: " in r["message"] for r in run), run)
        self.assertEqual({f["severity"] for f in self.data("structure", "balance")["flags"]}, {"info"})

    def test_a_block_flag_keeps_its_severity_in_run_mode(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8") + RUN, encoding="utf-8")
        report = {"flags": [{"code": "volume_undershoot", "severity": "block", "session_id": None,
                             "exercise_id": None, "message": "chest: blocked", "resolved": False,
                             "resolution": None}]}
        with mock.patch.object(structure, "balance", return_value=report):
            rows = structure_check.program_balance(_Context(self.root))
        self.assertEqual([(r.status, r.message) for r in rows], [("warn", "volume_undershoot: chest: blocked")])


class SkillTextTest(unittest.TestCase):
    def test_design_shows_a_dose_example_and_keeps_target_baseline_and_minimum_apart(self):
        text = flat(step_text("new-program", "design.md"))
        for phrase in ('"dose_targets": {', '"dose_intent": {"goal": "maintenance", "baseline"', "**target**",
                       "**ordinary baseline**", "**minimum week**", "never from the nutrition phase",
                       "rn:minimum-effective-dose.2"):
            self.assertIn(phrase, text)

    def test_every_path_checks_the_draft_balance_before_adoption(self):
        command = "python3 -m coach structure balance --program .coach/drafts/program.json"
        for name in ("SKILL.md", "design.md", "import.md", "starter.md"):
            with self.subTest(file=name):
                self.assertIn(command, flat(step_text("new-program", name)))


class _Context:
    def __init__(self, root):
        self.root = root
        self.config = config_module.load(root)

    def today(self):
        return None

    def now(self):
        return None


if __name__ == "__main__":
    unittest.main()
