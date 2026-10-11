"""Nutrition readings, status, flags, the brief line and the food questions (contract C35)."""

import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from coach import nutrition, protein, research
from tests.support import FIXTURES, INSTANCES, REPO_ROOT, VALID, run_cli, run_module
from tests.support.skills import skill_text, step_text

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
READINGS = Path("data") / "nutrition" / "readings.json"
SEED = FIXTURES / "nutrition" / "seed.json"
BRIEF_LINE = "Food: protein floor 110 g, last week 115 g · anchors: Whey shake · override: none"
OVERRIDE = """
[nutrition.override]
start = 2026-10-01
expires = 2026-10-15
what = "app protein target held at 120"
reason = "travel week"
exit_condition = "back home"
renewal = 0
"""


class InstanceCopy:
    def __init__(self, source=VALID):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(source, self.root)

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


def edit_config(root, old, new):
    path = Path(root) / "config.toml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_config(root, text):
    with open(Path(root) / "config.toml", "a", encoding="utf-8") as handle:
        handle.write(text)


def edit_latest(root, **changes):
    path = Path(root) / READINGS
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["readings"][-1].update(changes)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def codes(status):
    return [flag["code"] for flag in status["flags"]]


def flag(status, code):
    return next(item for item in status["flags"] if item["code"] == code)


class CliMixin:
    def run_ok(self, root, *argv, env=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope["data"]

    def run_code(self, wanted, root, *argv, env=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, wanted, (envelope, stderr))
        return envelope


class StatusTest(CliMixin, unittest.TestCase):
    def test_valid_fixture(self):
        data = self.run_ok(VALID, "nutrition", "status")
        self.assertIs(data["enabled"], True)
        self.assertEqual(data["app"], "macrofactor")
        self.assertEqual(data["phase"], "recomp")
        self.assertEqual(data["protein"]["floor_g"], 110)
        self.assertEqual(data["latest_reading"]["date"], "2026-10-11")
        self.assertIsNone(data["override"])
        self.assertEqual(data["brief_line"], BRIEF_LINE)
        self.assertIs(data["template"], True)
        self.assertEqual(len(data["questions"]), 3)
        self.assertEqual(codes(data), ["protein_floor_raise"])

    def test_floor_raise_proposes_the_next_step(self):
        raise_flag = flag(self.run_ok(VALID, "nutrition", "status"), "protein_floor_raise")
        self.assertEqual(raise_flag["floor_g"], 110)
        self.assertEqual(raise_flag["proposed_floor_g"], 120)
        self.assertEqual(raise_flag["dates"], ["2026-10-04", "2026-10-11"])
        self.assertEqual(raise_flag["proposed_floor_since"], "2026-10-12")
        self.assertIn("floor_since = 2026-10-12", raise_flag["message"])

    def test_accepted_raise_needs_two_new_readings(self):
        with InstanceCopy() as root:
            raise_flag = flag(self.run_ok(root, "nutrition", "status"), "protein_floor_raise")
            edit_config(root, "floor_g = 110", f"floor_g = {raise_flag['proposed_floor_g']}")
            edit_config(root, "floor_since = 2026-09-28", f"floor_since = {raise_flag['proposed_floor_since']}")
            later = {"COACH_NOW": "2026-10-18T18:00:00Z"}
            self.run_ok(root, "nutrition", "record", "--date", "2026-10-18", "--trend-weight", "82.1",
                        "--target-protein", "120", "--avg-protein", "121", "--days-logged", "7", env=later)
            self.assertEqual(codes(self.run_ok(root, "nutrition", "status", env=later)), [])
            latest = {"COACH_NOW": "2026-10-25T18:00:00Z"}
            self.run_ok(root, "nutrition", "record", "--date", "2026-10-25", "--trend-weight", "82.0",
                        "--target-protein", "120", "--avg-protein", "122", "--days-logged", "7", env=latest)
            raise_flag = flag(self.run_ok(root, "nutrition", "status", env=latest), "protein_floor_raise")
            self.assertEqual(raise_flag["dates"], ["2026-10-18", "2026-10-25"])
            self.assertEqual(raise_flag["proposed_floor_g"], 128)

    def test_no_raise_when_only_one_reading_counts(self):
        with InstanceCopy() as root:
            edit_config(root, "floor_since = 2026-09-28", "floor_since = 2026-10-05")
            self.assertNotIn("protein_floor_raise", codes(self.run_ok(root, "nutrition", "status")))

    def test_no_raise_with_the_floor_at_the_target(self):
        with InstanceCopy() as root:
            edit_config(root, "floor_g = 110", "floor_g = 128")
            edit_latest(root, target_protein_g=128)
            self.assertNotIn("protein_floor_raise", codes(self.run_ok(root, "nutrition", "status")))

    def test_raise_is_capped_at_the_target(self):
        with InstanceCopy() as root:
            edit_config(root, "floor_step_g = 10", "floor_step_g = 25")
            self.assertEqual(flag(self.run_ok(root, "nutrition", "status"), "protein_floor_raise")["proposed_floor_g"],
                             128)

    def test_no_raise_when_a_reading_is_under_the_floor(self):
        with InstanceCopy() as root:
            edit_latest(root, avg_protein_g=108)
            self.assertNotIn("protein_floor_raise", codes(self.run_ok(root, "nutrition", "status")))

    def test_app_protein_mismatch_and_logging_incomplete(self):
        with InstanceCopy() as root:
            edit_latest(root, target_protein_g=120, days_logged=6)
            data = self.run_ok(root, "nutrition", "status")
            self.assertIn("app_protein_mismatch", codes(data))
            self.assertEqual(flag(data, "app_protein_mismatch")["app_protein_g"], 120)
            self.assertIn("logging_incomplete", codes(data))

    def test_no_recent_reading(self):
        data = self.run_ok(VALID, "nutrition", "status", env={"COACH_NOW": "2026-10-26T18:00:00Z"})
        self.assertIn("no_recent_reading", codes(data))
        data = self.run_ok(VALID, "nutrition", "status", env={"COACH_NOW": "2026-10-24T18:00:00Z"})
        self.assertNotIn("no_recent_reading", codes(data))

    def test_no_readings_at_all(self):
        with InstanceCopy() as root:
            (root / READINGS).unlink()
            data = self.run_ok(root, "nutrition", "status")
            self.assertIsNone(data["latest_reading"])
            self.assertEqual(codes(data), ["no_recent_reading"])
            self.assertEqual(data["brief_line"],
                             "Food: protein floor 110 g, no reading yet · anchors: Whey shake · override: none")

    def test_override_expired_and_renewed_twice(self):
        with InstanceCopy() as root:
            append_config(root, OVERRIDE)
            data = self.run_ok(root, "nutrition", "status")
            self.assertEqual(data["override"]["state"], "active")
            self.assertNotIn("override_expired", codes(data))
            self.assertEqual(data["brief_line"].rsplit(" · ", 1)[1],
                             "override: app protein target held at 120, until 2026-10-15")
            data = self.run_ok(root, "nutrition", "status", env={"COACH_NOW": "2026-10-15T08:00:00Z"})
            self.assertEqual(data["override"]["state"], "expired")
            self.assertIn("override_expired", codes(data))
            edit_config(root, "renewal = 0", "renewal = 2")
            self.assertIn("override_renewed_twice", codes(self.run_ok(root, "nutrition", "status")))

    def test_trend_needs_fourteen_days(self):
        data = self.run_ok(VALID, "nutrition", "status")
        self.assertIsNone(data["trend"]["rate_per_week"])
        self.assertEqual(data["trend"]["target_rate_per_week"], 0.0)
        with InstanceCopy() as root:
            self.run_ok(root, "nutrition", "record", "--date", "2026-10-18", "--trend-weight", "82.1",
                        "--avg-protein", "118", "--days-logged", "7", "--anchors", "yes")
            trend = self.run_ok(root, "nutrition", "status")["trend"]
            self.assertEqual(trend["span"], {"start": "2026-10-04", "end": "2026-10-18"})
            self.assertEqual(trend["rate_per_week"], -0.2)
            self.assertEqual(trend["basis"], "trend_weight")
            self.assertNotIn("flag", trend)

    def test_disabled(self):
        with InstanceCopy() as root:
            edit_config(root, "[nutrition]\nenabled = true", "[nutrition]\nenabled = false")
            code, envelope, _ = run_cli(["--root", str(root), "nutrition", "status"], env=NOW)
            self.assertEqual(code, 0)
            self.assertEqual(envelope["data"]["enabled"], False)
            self.assertIsNone(envelope["data"]["brief_line"])
            self.assertEqual(envelope["data"]["questions"], [])
            self.run_code(5, root, "nutrition", "record", "--trend-weight", "82")
            self.run_code(5, root, "nutrition", "import", "--input", str(SEED))

    def test_absent_table_is_disabled(self):
        root = INSTANCES / "hevy-fresh"
        self.assertEqual(self.run_ok(root, "nutrition", "status")["enabled"], False)


class QuestionsTest(unittest.TestCase):
    def test_app_template_and_no_app(self):
        status = dict(nutrition.status(VALID, date(2026, 10, 11)), template=False)
        questions = nutrition.questions(status)
        self.assertEqual(len(questions), 2)
        self.assertIn("trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein) · "
                      "days logged", questions[0])
        self.assertIn("anchors most days (y/n)?", questions[1])
        self.assertEqual(len(nutrition.questions(dict(status, template=True))), 3)
        self.assertIn("who cooks which nights", nutrition.questions(dict(status, template=True))[2])
        no_app = nutrition.questions(dict(status, app="none"))
        self.assertIn("morning weigh-ins", no_app[0])
        self.assertNotIn("expenditure", no_app[0])

    def test_no_anchors_drops_the_anchors_ask(self):
        status = dict(nutrition.status(VALID, date(2026, 10, 11)), anchors=[])
        self.assertEqual(nutrition.questions(status)[1], "Anything in the plan that didn't work?")

    def test_disabled_status_has_nothing(self):
        self.assertEqual(nutrition.questions({"enabled": False}), [])
        self.assertIsNone(nutrition.brief_line({"enabled": False}))

    def test_brief_line(self):
        self.assertEqual(nutrition.brief_line(nutrition.status(VALID, date(2026, 10, 11))), BRIEF_LINE)


class RecordTest(CliMixin, unittest.TestCase):
    ARGS = ("nutrition", "record", "--date", "2026-10-18", "--trend-weight", "82.1", "--avg-protein", "118",
            "--days-logged", "7", "--anchors", "yes")

    def test_dry_run_writes_nothing_then_real_run_adds_then_repeat_refused(self):
        with InstanceCopy() as root:
            before = (root / READINGS).read_bytes()
            data = self.run_ok(root, *self.ARGS, "--dry-run")
            self.assertEqual((root / READINGS).read_bytes(), before)
            self.assertFalse(data["written"])
            reading = data["reading"]
            self.assertEqual(reading["date"], "2026-10-18")
            self.assertEqual(reading["source"], "app")
            self.assertEqual(reading["weight_unit"], "kg")
            self.assertEqual(reading["trend_weight"], 82.1)
            self.assertEqual(reading["avg_protein_g"], 118)
            self.assertIs(reading["anchors_most_days"], True)
            self.assertIsNone(reading["expenditure_kcal"])

            self.assertTrue(self.run_ok(root, *self.ARGS)["written"])
            stored = json.loads((root / READINGS).read_text(encoding="utf-8"))
            self.assertEqual([r["date"] for r in stored["readings"]][-1], "2026-10-18")
            self.assertEqual(stored["readings"][-1], reading)

            envelope = self.run_code(1, root, *self.ARGS)
            self.assertIn("--replace", envelope["error"]["message"])
            data = self.run_ok(root, *self.ARGS[:-1], "no", "--replace")
            self.assertTrue(data["replaced"])
            stored = json.loads((root / READINGS).read_text(encoding="utf-8"))
            self.assertEqual(len(stored["readings"]), 4)
            self.assertIs(stored["readings"][-1]["anchors_most_days"], False)

    def test_on_disk_format(self):
        with InstanceCopy() as root:
            self.run_ok(root, *self.ARGS)
            text = (root / READINGS).read_text(encoding="utf-8")
            self.assertTrue(text.endswith("}\n"))
            self.assertIn('\n  "readings": [', text)

    def test_readings_stay_sorted(self):
        with InstanceCopy() as root:
            self.run_ok(root, "nutrition", "record", "--date", "2026-10-01", "--avg-protein", "108")
            stored = json.loads((root / READINGS).read_text(encoding="utf-8"))
            self.assertEqual([r["date"] for r in stored["readings"]],
                             ["2026-09-28", "2026-10-01", "2026-10-04", "2026-10-11"])

    def test_date_defaults_to_today(self):
        with InstanceCopy() as root:
            (root / READINGS).unlink()
            data = self.run_ok(root, "nutrition", "record", "--scale-weight", "82.0")
            self.assertEqual(data["reading"]["date"], "2026-10-11")
            self.assertTrue((root / READINGS).is_file())

    def test_no_app_reading_is_a_scale_reading(self):
        with InstanceCopy() as root:
            edit_config(root, 'app = "macrofactor"', 'app = "none"')
            data = self.run_ok(root, "nutrition", "record", "--date", "2026-10-18", "--scale-weight", "82.0",
                               "--dry-run")
            self.assertEqual(data["reading"]["source"], "scale")

    def test_a_reading_needs_a_weight_or_protein(self):
        with InstanceCopy() as root:
            envelope = self.run_code(1, root, "nutrition", "record", "--date", "2026-10-18", "--days-logged", "7")
            self.assertIn("trend_weight", envelope["error"]["message"])

    def test_days_logged_is_zero_to_seven(self):
        with InstanceCopy() as root:
            self.run_code(1, root, "nutrition", "record", "--avg-protein", "110", "--days-logged", "8")

    def test_bad_date_is_a_validation_error(self):
        with InstanceCopy() as root:
            self.run_code(1, root, "nutrition", "record", "--date", "18/10/2026", "--avg-protein", "110")

    def test_readings_command(self):
        data = self.run_ok(VALID, "nutrition", "readings", "--last", "2")
        self.assertEqual([r["date"] for r in data["readings"]], ["2026-10-04", "2026-10-11"])
        self.assertEqual(data["count"], 2)
        self.assertEqual(self.run_ok(VALID, "nutrition", "readings")["count"], 3)


class ImportTest(CliMixin, unittest.TestCase):
    def test_dry_run_then_import_then_duplicate(self):
        with InstanceCopy() as root:
            before = (root / READINGS).read_bytes()
            data = self.run_ok(root, "nutrition", "import", "--input", str(SEED), "--dry-run")
            self.assertEqual((root / READINGS).read_bytes(), before)
            self.assertEqual([r["date"] for r in data["readings"]], ["2026-09-07", "2026-09-14", "2026-09-21"])
            self.assertEqual({r["source"] for r in data["readings"]}, {"seeded"})
            self.assertFalse(data["written"])

            data = self.run_ok(root, "nutrition", "import", "--input", str(SEED))
            self.assertTrue(data["written"])
            stored = json.loads((root / READINGS).read_text(encoding="utf-8"))["readings"]
            self.assertEqual(len(stored), 6)
            self.assertEqual(stored[0]["date"], "2026-09-07")
            self.assertEqual(stored[0]["source"], "seeded")
            self.assertIsNone(stored[0]["expenditure_kcal"])

            envelope = self.run_code(1, root, "nutrition", "import", "--input", str(SEED))
            self.assertIn("2026-09-07", envelope["error"]["message"])
            self.run_ok(root, "nutrition", "import", "--input", str(SEED), "--replace")
            self.assertEqual(len(json.loads((root / READINGS).read_text(encoding="utf-8"))["readings"]), 6)

    def test_import_refuses_other_sources_and_inner_duplicates(self):
        with InstanceCopy() as root:
            bad = root / "bad.json"
            bad.write_text(json.dumps([{"date": "2026-09-01", "source": "app", "avg_protein_g": 100}]),
                           encoding="utf-8")
            self.assertIn("seeded", self.run_code(1, root, "nutrition", "import", "--input", str(bad))["error"]["message"])
            bad.write_text(json.dumps([{"date": "2026-09-01", "avg_protein_g": 100},
                                       {"date": "2026-09-01", "avg_protein_g": 101}]), encoding="utf-8")
            self.run_code(1, root, "nutrition", "import", "--input", str(bad))
            bad.write_text(json.dumps([{"date": "2026-09-01", "avg_protien_g": 100}]), encoding="utf-8")
            self.assertIn("avg_protien_g", json.dumps(self.run_code(1, root, "nutrition", "import", "--input",
                                                                    str(bad))["error"]))


class ChecksTest(CliMixin, unittest.TestCase):
    def results(self, root, check_id, env=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), "check", "--only", check_id], env=env)
        return code, envelope["data"]["results"]

    def test_valid_fixture_passes_both(self):
        for check_id in ("nutrition_readings", "nutrition_override"):
            with self.subTest(check=check_id):
                code, results = self.results(VALID, check_id)
                self.assertEqual(code, 0)
                self.assertEqual([r["status"] for r in results], ["pass"])

    def test_bad_readings_fixture_fails(self):
        code, results = self.results(INSTANCES / "nutrition-bad-readings", "nutrition_readings")
        self.assertEqual(code, 1)
        self.assertEqual(results[0]["status"], "fail")
        self.assertEqual(results[0]["path"], "data/nutrition/readings.json")

    def test_override_fixture_warns_once_expired(self):
        root = INSTANCES / "nutrition-override"
        code, results = self.results(root, "nutrition_override")
        self.assertEqual([r["status"] for r in results], ["pass"])
        code, results = self.results(root, "nutrition_override", env={"COACH_NOW": "2026-10-22T08:00:00Z"})
        self.assertEqual(code, 0)
        self.assertEqual([r["status"] for r in results], ["warn"])
        self.assertIn("2026-10-22", results[0]["message"])

    def test_override_renewed_twice_warns(self):
        with InstanceCopy(INSTANCES / "nutrition-override") as root:
            edit_config(root, "renewal = 1", "renewal = 2")
            code, results = self.results(root, "nutrition_override")
            self.assertEqual([r["status"] for r in results], ["warn"])
            self.assertIn("renew", results[0]["message"])


class NoCalorieModelTest(unittest.TestCase):
    BANNED = re.compile(r"mifflin|harris|katch|bmr|tdee|activity factor", re.I)

    def test_pattern_catches_each_term(self):
        for text in ("Mifflin", "harris_benedict", "Katch-McArdle", "bmr =", "TDEE", "Activity Factor"):
            self.assertTrue(self.BANNED.search(text), text)

    def test_no_package_module_names_a_calorie_equation(self):
        offenders = []
        for path in sorted((REPO_ROOT / "coach").rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if self.BANNED.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "the nutrition app owns expenditure and calorie targets")


class SkillWiringTest(unittest.TestCase):
    def test_check_in_runs_the_commands_and_handles_every_flag(self):
        text = skill_text("check-in")
        for needle in ("6. **Food**", "nutrition record", "nutrition status", "only when a standing weekly template",
                       "protein_floor_raise", "override_expired", "override_renewed_twice", "app_protein_mismatch",
                       "logging_incomplete", "no_recent_reading"):
            self.assertIn(needle, text)
        self.assertNotIn("**Meal plan**", text)

    def test_goals_writes_the_numbers_to_config(self):
        text = skill_text("goals")
        for needle in ("[nutrition.protein]", "[[nutrition.anchors]]", "[nutrition.override]", "config validate",
                       "What stays prose"):
            self.assertIn(needle, text)

    def test_targets_use_the_who_body_fat_line_and_goals_a_relative_bulk_rate(self):
        self.assertEqual(protein.HIGH_BODY_FAT_PCT, {"male": 25, "female": 35})
        text = skill_text("goals")
        flat = " ".join(text.split())
        self.assertNotRegex(flat, r"32 ?% for women|/~32 ?%")
        self.assertIn("~0.25–0.5 % of bodyweight per week, nearer the low end for advanced lifters", flat)
        self.assertNotRegex(text, r"lb ?(/|a |per )w(ee)?k")

    def test_goals_quotes_the_protein_numbers(self):
        text = step_text("goals", "protein.md")
        self.assertIn("python3 -m coach nutrition targets", text)
        self.assertNotRegex(text, r"×|\d g/kg")


class ProteinNoteTest(unittest.TestCase):
    def claim(self, n):
        return research.find_claim(f"rn:protein-energy-deficit.{n}", research.load_notes(REPO_ROOT))

    def test_womens_high_body_fat_line_is_the_who_line(self):
        claim = self.claim(4)
        self.assertIn("~25 % for men or ~35 % for women", claim.text)
        self.assertEqual(claim.basis, "heuristic")
        self.assertEqual(claim.sources[0], "romero-corral-2008")

    def test_bulk_rate_is_a_share_of_bodyweight(self):
        claim = self.claim(12)
        self.assertIn("~0.25–0.5 % of bodyweight per week, nearer the low end for advanced lifters", claim.text)
        self.assertEqual((claim.basis, claim.confidence), ("evidence", "low"))
        self.assertEqual(sorted(claim.sources), ["helms-2023", "iraki-2019"])

    def test_floor_clamp_is_unchanged(self):
        self.assertIn("never below 1.2 g/kg", self.claim(7).text)

    def test_no_lb_rate_or_32_percent_line_in_the_note(self):
        text = (REPO_ROOT / "research" / "protein-energy-deficit.md").read_text(encoding="utf-8")
        self.assertNotRegex(" ".join(text.split()), r"32 ?% for women")
        self.assertNotRegex(text, r"lb ?(/|a |per )w(ee)?k")


class SubprocessTest(unittest.TestCase):
    def test_status_as_a_subprocess(self):
        code, envelope, stderr = run_module(["--root", "tests/fixtures/instances/valid", "nutrition", "status"],
                                            env=NOW)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(envelope["data"]["brief_line"], BRIEF_LINE)


if __name__ == "__main__":
    unittest.main()
