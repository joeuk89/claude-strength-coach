"""Run mode: the athlete's own program executed, structural flags shown as information (contract C20, C44)."""

import re
import shutil
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import coach.checkin_parts
from coach import config, flags
from coach.config_tables import coaching
from tests.support import INSTANCES, MINIMAL_CONFIG, REPO_ROOT, run_cli
from tests.support.history import read_json, write_json
from tests.support.skills import skill_text
from tests.test_block import BlockCase
from tests.test_checkin import CheckinCase
from tests.test_pages import PagesCase, section
from tests.test_propose import ProposeCase

DOSE = INSTANCES / "dose"
DOSE_NOW = "2026-10-11T18:00:00Z"
RUN = '\n[coaching]\nmode = "run"\n'
STRUCTURAL = ("add_session_type_blocked", "restructure_required", "volume_undershoot", "session_volume_high")


def run_mode(root):
    path = Path(root) / "config.toml"
    path.write_text(path.read_text(encoding="utf-8") + RUN, encoding="utf-8")


def skill(name):
    return " ".join(skill_text(name).split())


class ConfigTest(unittest.TestCase):
    def validate(self, extra):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "config.toml").write_text(MINIMAL_CONFIG + extra, encoding="utf-8")
            return run_cli(["--root", tmp, "config", "validate"])

    def test_run_and_coach_are_accepted(self):
        for mode in ("run", "coach"):
            with self.subTest(mode=mode):
                code, envelope, _ = self.validate(f'\n[coaching]\nmode = "{mode}"\n')
                self.assertEqual(code, 0, envelope)

    def test_any_other_mode_exits_5_naming_the_key(self):
        code, envelope, _ = self.validate('\n[coaching]\nmode = "auto"\n')
        self.assertEqual(code, 5, envelope)
        message = envelope["error"]["message"]
        self.assertIn("mode", message)
        self.assertIn("[coaching]", message)
        self.assertIn('"auto"', message)

    def test_the_default_is_coach(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "config.toml")
            path.write_text(MINIMAL_CONFIG, encoding="utf-8")
            self.assertEqual(coaching.mode(config.parse_file(path)), "coach")
            path.write_text(MINIMAL_CONFIG + RUN, encoding="utf-8")
            self.assertEqual(coaching.mode(config.parse_file(path)), "run")

    def test_the_example_sets_coach_mode(self):
        raw = tomllib.loads((REPO_ROOT / "config.example.toml").read_text(encoding="utf-8"))
        self.assertEqual(raw["coaching"], {"mode": "coach"})


class ForModeTest(unittest.TestCase):
    def setUp(self):
        self.found = [
            flags.make("restructure_required", message="58 % over four weeks"),
            flags.make("stale_prescription", session_id="session-a", exercise_id="bb_back_squat", message="stale"),
            flags.make("niggle_escalate", message="left knee three check-ins running"),
            flags.make("session_volume_high", "info", session_id="session-a", message="chest 12 sets"),
        ]

    def test_run_mode_shows_structural_flags_at_info_with_the_prefix(self):
        shown = flags.for_mode(self.found, "run")
        self.assertEqual((shown[0]["severity"], shown[0]["message"]), ("info", "run mode: 58 % over four weeks"))
        self.assertEqual((shown[3]["severity"], shown[3]["message"]), ("info", "run mode: chest 12 sets"))
        self.assertEqual(shown[1], self.found[1])
        self.assertEqual(shown[2], self.found[2])

    def test_coach_mode_returns_the_flags_unchanged(self):
        self.assertEqual(flags.for_mode(self.found, "coach"), self.found)

    def test_the_input_is_not_changed(self):
        before = [dict(f) for f in self.found]
        flags.for_mode(self.found, "run")
        self.assertEqual(self.found, before)

    def test_running_it_twice_prefixes_once(self):
        twice = flags.for_mode(flags.for_mode(self.found, "run"), "run")
        self.assertEqual(twice[0]["message"], "run mode: 58 % over four weeks")

    def test_a_block_flag_is_never_touched_even_on_a_structural_code(self):
        flag = dict(self.found[0], severity="block")
        self.assertEqual(flags.for_mode([flag], "run"), [flag])

    def test_an_unregistered_code_passes_through(self):
        flag = dict(self.found[0], code="custom_shape")
        self.assertEqual(flags.for_mode([flag], "run"), [flag])

    def test_an_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            flags.for_mode(self.found, "auto")

    def test_r30a_codes_are_the_structural_ones(self):
        registry = flags.registry()
        self.assertEqual({code for code, entry in registry.items() if entry.structural}, set(STRUCTURAL))


class StructureReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(DOSE, self.root)

    def data(self, *argv):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": DOSE_NOW})
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope["data"]

    def by_code(self, found):
        return {f["code"]: f for f in found}

    def test_adherence_reports_the_same_figure_and_downgrades_restructure_in_run_mode(self):
        coached = self.data("structure", "adherence")
        run_mode(self.root)
        run = self.data("structure", "adherence")
        self.assertEqual((coached["planned"], coached["trained"], coached["pct"]), (12, 7, 58))
        self.assertEqual((run["planned"], run["trained"], run["pct"]), (12, 7, 58))
        before, after = self.by_code(coached["flags"]), self.by_code(run["flags"])
        self.assertEqual(before["restructure_required"]["severity"], "warn")
        self.assertEqual(after["restructure_required"]["severity"], "info")
        self.assertEqual(after["restructure_required"]["message"],
                         "run mode: " + before["restructure_required"]["message"])
        self.assertEqual(after["adherence_low"], before["adherence_low"])
        for flag in run["flags"]:
            if flag["code"] in STRUCTURAL:
                self.assertEqual(flag["severity"], "info", flag)

    def test_week_downgrades_a_planned_session_over_11_sets(self):
        path = self.root / "data" / "overlays" / "2026-10-05-weekly.json"
        doc = read_json(path)
        session = next(s for s in doc["sessions"] if s["session_id"] == "session-a")
        bench = next(e for e in session["exercises"] if e["exercise_id"] == "db_bench_press")
        working = next(s for s in bench["sets"] if s["type"] == "normal")
        bench["sets"] = [dict(working) for _ in range(12)]
        write_json(path, doc)
        coached = self.data("structure", "week", "--week", "2026-W41")
        run_mode(self.root)
        run = self.data("structure", "week", "--week", "2026-W41")
        self.assertEqual([(f["code"], f["severity"]) for f in coached["flags"]], [("session_volume_high", "warn")])
        self.assertEqual([(f["code"], f["severity"]) for f in run["flags"]], [("session_volume_high", "info")])
        self.assertTrue(run["flags"][0]["message"].startswith("run mode: "))
        self.assertEqual(coached["muscles"], run["muscles"])

    def test_balance_shows_its_undershoot_at_info(self):
        coached = self.data("structure", "balance")
        run_mode(self.root)
        run = self.data("structure", "balance")
        self.assertIn("volume_undershoot", [f["code"] for f in coached["flags"]])
        self.assertEqual(coached["muscles"], run["muscles"])
        self.assertTrue(run["flags"])
        self.assertEqual({f["severity"] for f in run["flags"]}, {"info"})

    def test_decide_still_works_when_the_athlete_asks(self):
        run_mode(self.root)
        data = self.data("structure", "decide", "--rule", "restructure", "--outcome", "deferred",
                         "--revisit", "2026-11-02", "--dry-run")
        self.assertEqual(data["line"], "Adherence trigger: 58 % over 4 weeks: deferred to 2026-11-02")


class ProposeLoadsTest(ProposeCase):
    def loads(self):
        doc = self.propose("--dry-run")["overlay"]
        return [(s["session_id"], line["exercise_id"], [st.get("load") for st in line["sets"]])
                for s in doc["sessions"] for line in s["exercises"]]

    def test_loads_are_identical_in_both_modes(self):
        coached = self.loads()
        run_mode(self.root)
        self.assertEqual(self.loads(), coached)
        self.assertTrue(any(load for _, _, found in coached for load in found))


class CardTest(CheckinCase):
    def setUp(self):
        super().setUp()
        self.parts_dir = Path(tempfile.mkdtemp(dir=self.tmp))
        self.name = f"structural_{id(self)}"
        (self.parts_dir / f"{self.name}.py").write_text(textwrap.dedent("""
            from coach import flags
            from coach.checkin_parts import Contribution
            FIELDS = ()
            def contribute(ctx):
                return Contribution(flags=[flags.make("restructure_required", message="58 % over four weeks"),
                                           flags.make("niggle_escalate", message="left knee")])
        """), encoding="utf-8")
        self.addCleanup(sys.modules.pop, f"coach.checkin_parts.{self.name}", None)

    def prepared(self):
        paths = list(coach.checkin_parts.__path__) + [str(self.parts_dir)]
        with mock.patch.object(coach.checkin_parts, "__path__", paths):
            return self.prepare()["data"]

    def test_run_mode_card_shows_no_structural_flag_above_info(self):
        coached = self.prepared()
        flag = next(f for f in coached["card"]["flags"] if f["code"] == "restructure_required")
        self.assertEqual(flag["severity"], "warn")
        run_mode(self.root)
        data = self.prepared()
        for found in data["card"]["flags"]:
            if flags.registry()[found["code"]].structural:
                self.assertEqual(found["severity"], "info", found)
        flag = next(f for f in data["card"]["flags"] if f["code"] == "restructure_required")
        self.assertEqual(flag["message"], "run mode: 58 % over four weeks")
        self.assertIn("- `restructure_required`: run mode: 58 % over four weeks", data["text"])
        escalate = next(f for f in data["card"]["flags"] if f["code"] == "niggle_escalate")
        self.assertEqual((escalate["severity"], escalate["message"]), ("warn", "left knee"))


class BriefTest(PagesCase):
    def add_structural_flag(self):
        doc = self.overlay_doc()
        doc["flags"].append({"code": "volume_undershoot", "severity": "warn", "session_id": None,
                             "exercise_id": None, "message": "chest below its target", "resolved": False,
                             "resolution": None})
        self.write_overlay(doc)

    def header(self, text):
        return text.splitlines()[1]

    def test_coach_mode_watches_the_structural_flag_and_says_nothing_of_run_mode(self):
        self.add_structural_flag()
        text = self.brief()
        self.assertIn("- chest below its target", section(text, "Watch"))
        self.assertNotIn("run mode", self.header(text))

    def test_run_mode_drops_it_from_watch_and_names_run_mode_in_the_header(self):
        self.add_structural_flag()
        run_mode(self.root)
        text = self.brief()
        self.assertNotIn("chest below its target", text)
        self.assertIn("run mode", self.header(text))
        self.assertEqual(self.overlay_doc()["flags"][-1]["severity"], "warn")


class DeepReviewTest(BlockCase):
    def test_the_adherence_trigger_does_not_make_a_run_mode_close_deep(self):
        self.init(1)
        run_mode(self.root)
        flag = flags.make("restructure_required", message="58 %")
        with mock.patch("coach.structure.adherence", return_value={"flags": [flag]}):
            data = self.close()
        self.assertNotIn("restructure_required", data["deep_review"]["reasons"])


class SkillTest(unittest.TestCase):
    def test_check_in_says_no_restructure_and_no_structure_decide(self):
        text = skill("check-in")
        paragraph = text[text.index("**Run mode"):][:1200]
        for phrase in ('mode = "run"', "do not present a restructure", "structure decide", "/new-program"):
            self.assertIn(phrase, paragraph)

    def test_new_program_and_program_week_each_carry_a_run_mode_paragraph(self):
        for name in ("new-program", "program-week"):
            with self.subTest(skill=name):
                text = skill(name)
                self.assertIn("**Run mode", text)
                self.assertIn('mode = "run"', text)


class ContractTest(unittest.TestCase):
    def test_c44_names_for_mode_and_the_config_table_module(self):
        text = (REPO_ROOT / "docs" / "design" / "coach-contract.md").read_text(encoding="utf-8")
        section_text = text.split("## C44.", 1)[1].split("\n## C45.", 1)[0]
        self.assertIn("coach.flags.for_mode", section_text)
        self.assertIn("coach/config_tables/coaching.py", section_text)

    def test_glossary_defines_run_mode(self):
        text = (REPO_ROOT / "CONTEXT.md").read_text(encoding="utf-8")
        self.assertRegex(text, re.compile(r"^\*\*Run mode\*\*:", re.M))


if __name__ == "__main__":
    unittest.main()
