"""Weigh-ins kept without nutrition set up, and one bodyweight precedence and basis for every reader (contract C35)."""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coach import pages, units
from coach.hevy.cache import HevyCache
from tests.support import INSTANCES, VALID, run_cli
from tests.support.skills import step_text

NOHEVY = INSTANCES / "nohevy"
READINGS = Path("data") / "nutrition" / "readings.json"
WELLNESS = Path(".coach") / "activity" / "wellness.jsonl"
NOW = "2026-10-12T08:00:00Z"
WEIGH_INS = (("2026-09-28", 64.2), ("2026-10-05", 63.9), ("2026-10-12", 63.5))
WEIGH_IN_RATE = round((63.5 - 64.2) / 14 * 7, 2)


def scale_reading(day, weight, unit="kg"):
    return {"date": day, "source": "scale", "weight_unit": unit, "trend_weight": None, "scale_weight": weight,
            "expenditure_kcal": None, "target_kcal": None, "target_protein_g": None, "avg_kcal": None,
            "avg_protein_g": None, "days_logged": None, "anchors_most_days": None, "note": None}


def trend_reading(day, weight):
    return dict(scale_reading(day, None), source="app", trend_weight=weight)


class Instance(unittest.TestCase):
    """A temp copy of an instance; `valid/` by default, whose config ends with its nutrition tables."""

    base = VALID

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(self.base, self.root)
        self.wellness().unlink(missing_ok=True)
        self.nutrition_table = self.config_text()[self.config_text().index("\n[nutrition]\n"):]

    def config_text(self):
        return (self.root / "config.toml").read_text(encoding="utf-8")

    def write_config(self, text):
        (self.root / "config.toml").write_text(text, encoding="utf-8")

    def edit_config(self, old, new):
        text = self.config_text()
        self.assertIn(old, text)
        self.write_config(text.replace(old, new, 1))

    def drop_nutrition(self):
        self.write_config(self.config_text().replace(self.nutrition_table, "\n"))
        self.readings()

    def restore_nutrition(self, app="macrofactor"):
        self.write_config(self.config_text().rstrip("\n") + "\n" + self.nutrition_table.replace(
            'app = "macrofactor"', f'app = "{app}"'))

    def set_activity(self, enabled):
        text = self.config_text().replace("[activity]\nenabled = false", "[activity]\nenabled = true")
        self.write_config(text.replace("[activity]\nenabled = true", f"[activity]\nenabled = {str(enabled).lower()}"))

    def readings(self, *found):
        path = self.root / READINGS
        if found:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"schema_version": 1, "readings": list(found)}), encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

    def hevy(self, *measurements):
        HevyCache(self.root).write_collection(
            "body_measurements", [{"date": day, "weight_kg": kg, "lean_mass_kg": None, "fat_percent": None}
                                  for day, kg in measurements], "2026-10-11T12:00:00Z")

    def wellness(self):
        return self.root / WELLNESS

    def coach(self, *argv, expect=0, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def record(self, day, weight, *extra, expect=0, now=NOW):
        return self.coach("bodyweight", "record", "--date", day, "--weight", str(weight), *extra,
                          expect=expect, now=now)

    def observations(self, now=NOW):
        return self.coach("bodyweight", "list", now=now)["data"]["observations"]

    def nutrition_trend(self, now=NOW):
        return self.coach("nutrition", "status", now=now)["data"]["trend"]

    def render(self, now=NOW):
        moment = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc)
        found = pages.render_all(self.root, moment, kinds=(pages.PROGRESS, pages.DASHBOARD))
        return found["progress.md"], found["README.md"]

    def bodyweight_section(self, now=NOW):
        progress, readme = self.render(now)
        section = progress[progress.index("## Bodyweight"):].strip().splitlines()[2:]
        summary = [line for line in readme.splitlines() if line.startswith("- Bodyweight:")]
        return section, summary


class WeightOnlyPathTest(Instance):
    """With nutrition absent, activity on or off, a weigh-in is kept as a manual wellness body mass."""

    def test_the_weigh_in_and_its_date_are_kept_without_enabling_anything(self):
        for activity in (True, False):
            with self.subTest(activity=activity):
                self.setUp()
                self.drop_nutrition()
                self.set_activity(activity)
                config = self.config_text()
                data = self.record("2026-10-01", 64.2)["data"]
                self.assertEqual((data["written"], data["replaced"]), (True, False))
                self.assertEqual(data["weigh_in"], {"date": "2026-10-01", "value": 64.2, "unit": "kg"})
                self.assertEqual(self.config_text(), config)
                [kept] = self.observations()
                self.assertEqual({k: kept[k] for k in ("date", "value", "basis", "source")},
                                 {"date": "2026-10-01", "value": 64.2, "basis": "scale_weight", "source": "wellness"})
                self.assertIs(self.coach("nutrition", "status")["data"]["enabled"], False)
                self.assertIn("bodyweight record", self.coach("nutrition", "record", "--scale-weight", "64.2",
                                                              expect=5)["error"]["message"])
                if not activity:
                    self.coach("wellness", "list", expect=5)

    def test_repeating_writes_nothing_and_a_different_weight_needs_replace(self):
        self.drop_nutrition()
        self.record("2026-10-01", 64.2)
        lines = self.wellness().read_text(encoding="utf-8")
        again = self.record("2026-10-01", 64.2)["data"]
        self.assertEqual((again["changed"], again["written"]), (False, False))
        self.assertEqual(self.wellness().read_text(encoding="utf-8"), lines)
        refused = self.record("2026-10-01", 64.0, expect=1)["error"]["message"]
        self.assertIn("already has a weigh-in of 64.2 kg", refused)
        self.assertIn("--replace", refused)
        fixed = self.record("2026-10-01", 64.0, "--replace")["data"]
        self.assertEqual((fixed["written"], fixed["replaced"]), (True, True))
        self.assertEqual([o["value"] for o in self.observations()], [64])

    def test_other_readings_on_the_day_are_kept(self):
        self.coach("wellness", "add", "--date", "2026-10-01", "--sleep-hours", "7.5")
        self.record("2026-10-01", 64.2)
        [day] = self.coach("wellness", "list", "--from", "2026-10-01", "--to", "2026-10-01")["data"]["days"]
        self.assertEqual((day["sleep"]["asleep_hours"], day["body_mass_kg"]), (7.5, 64.2))

    def test_dry_run_writes_nothing(self):
        self.drop_nutrition()
        self.assertIs(self.record("2026-10-01", 64.2, "--dry-run")["data"]["written"], False)
        self.assertFalse(self.wellness().exists())


class LaterNutritionSetupTest(Instance):
    """Three weigh-ins kept with nutrition off feed the scale trend once nutrition is on, and copies add nothing."""

    def setUp(self):
        super().setUp()
        self.readings()
        self.drop_nutrition()
        for day, weight in WEIGH_INS:
            self.record(day, weight)
        self.restore_nutrition(app="none")

    def test_the_scale_trend_reads_the_wellness_weigh_ins(self):
        trend = self.nutrition_trend()
        self.assertEqual((trend["basis"], trend["fallback"], trend["sources"]), ("scale_weight", False, ["wellness"]))
        self.assertEqual(trend["span"], {"start": "2026-09-28", "end": "2026-10-12"})
        self.assertEqual(trend["rate_per_week"], WEIGH_IN_RATE)

    def test_goals_reads_the_kept_fresh_weigh_in(self):
        bodyweight = self.coach("nutrition", "targets")["data"]["inputs"]["bodyweight"]
        self.assertEqual(bodyweight, {"value": 63.5, "unit": "kg", "from": "wellness manual:2026-10-12-wellness"})

    def test_a_copy_in_a_nutrition_reading_adds_no_observation(self):
        self.coach("nutrition", "record", "--date", "2026-10-12", "--scale-weight", "63.5")
        found = self.observations()
        self.assertEqual([o["date"] for o in found], [day for day, _ in WEIGH_INS])
        self.assertEqual(found[-1]["source"], "wellness")
        self.assertEqual([d["source"] for d in found[-1]["duplicates"]], ["nutrition"])
        self.assertEqual(self.nutrition_trend()["rate_per_week"], WEIGH_IN_RATE)


class PagesTest(Instance):
    def test_a_no_hevy_app_instance_shows_its_trend_weight(self):
        self.base = NOHEVY
        self.setUp()
        section, summary = self.bodyweight_section()
        self.assertEqual(section[2:], ["| 28 Sep 2026 | 82.55 |", "| 5 Oct 2026 | 82.4 |", "",
                                       "Basis: trend weight (nutrition readings); weekly means."])
        self.assertEqual(summary, ["- Bodyweight: 82.4 kg on 11 Oct 2026, trend weight (nutrition readings)"])

    def test_a_no_app_scale_instance_shows_its_scale_weights(self):
        self.edit_config('app = "macrofactor"', 'app = "none"')
        self.readings(scale_reading("2026-09-28", 80.6), scale_reading("2026-10-05", 80.2))
        section, summary = self.bodyweight_section()
        self.assertEqual(section[2:], ["| 28 Sep 2026 | 80.6 |", "| 5 Oct 2026 | 80.2 |", "",
                                       "Basis: scale weight (nutrition readings); weekly means."])
        self.assertEqual(summary, ["- Bodyweight: 80.2 kg on 5 Oct 2026, scale weight (nutrition readings)"])

    def test_a_wellness_only_instance_shows_its_weigh_ins(self):
        self.readings()
        self.drop_nutrition()
        for day, weight in WEIGH_INS:
            self.record(day, weight)
        section, summary = self.bodyweight_section()
        self.assertEqual(section[2:], ["| 28 Sep 2026 | 64.2 |", "| 5 Oct 2026 | 63.9 |", "| 12 Oct 2026 | 63.5 |",
                                       "", "Basis: scale weight (recorded weigh-ins); weekly means."])
        self.assertEqual(summary, ["- Bodyweight: 63.5 kg on 12 Oct 2026, scale weight (recorded weigh-ins)"])

    def test_no_observation_is_honestly_empty(self):
        self.readings()
        section, summary = self.bodyweight_section()
        self.assertEqual(section, ["No bodyweight recorded yet: weigh-ins given to the coach, logged in Hevy or "
                                   "read from a nutrition app show here."])
        self.assertEqual(summary, [])


class PrecedenceTest(Instance):
    """Overlapping sources on one date give one observation, in a documented order, in any unit and as of any day."""

    def setUp(self):
        super().setUp()
        self.edit_config('app = "macrofactor"', 'app = "none"')
        self.readings(scale_reading("2026-10-05", 80.0))
        self.hevy(("2026-10-05", 80.4))

    def test_wellness_then_hevy_then_nutrition(self):
        self.record("2026-10-05", 80.2)
        [kept] = self.observations()
        self.assertEqual((kept["value"], kept["source"]), (80.2, "wellness"))
        self.assertEqual(kept["duplicates"], [{"source": "hevy", "value": 80.4, "ref": "hevy 2026-10-05"},
                                              {"source": "nutrition", "value": 80, "ref": "reading 2026-10-05"}])
        section, _ = self.bodyweight_section()
        self.assertIn("| 5 Oct 2026 | 80.2 |", section)
        self.coach("wellness", "void", "manual:2026-10-05-wellness", "--reason", "test")
        [kept] = self.observations()
        self.assertEqual((kept["value"], kept["source"]), (80.4, "hevy"))

    def test_kg_and_lb_instances_agree_after_conversion(self):
        found = {}
        for unit in ("kg", "lb"):
            with self.subTest(unit=unit):
                self.setUp()
                self.readings()
                self.hevy()
                self.edit_config('bodyweight_units = "kg"', f'bodyweight_units = "{unit}"')
                for day, kg in WEIGH_INS:
                    self.record(day, kg if unit == "kg" else units.mass_from_kg(kg, "lb"))
                found[unit] = self.nutrition_trend(), self.observations()
        (kg_trend, kg_points), (lb_trend, lb_points) = found["kg"], found["lb"]
        self.assertAlmostEqual(lb_trend["rate_per_week"] * units.LB_TO_KG, kg_trend["rate_per_week"], places=2)
        self.assertEqual(kg_trend["span"], lb_trend["span"])
        for kg_point, lb_point in zip(kg_points, lb_points):
            self.assertAlmostEqual(units.mass_kg(lb_point["value"], "lb"), kg_point["value"], places=3)

    def test_an_observation_after_as_of_is_left_out(self):
        self.readings()
        self.hevy()
        for day, weight in WEIGH_INS:
            self.record(day, weight)
        early = "2026-10-06T08:00:00Z"
        self.assertEqual([o["date"] for o in self.observations(now=early)], ["2026-09-28", "2026-10-05"])
        self.assertIsNone(self.nutrition_trend(now=early)["rate_per_week"])
        section, summary = self.bodyweight_section(now=early)
        self.assertNotIn("| 12 Oct 2026 | 63.5 |", section)
        self.assertEqual(summary, ["- Bodyweight: 63.9 kg on 5 Oct 2026, scale weight (recorded weigh-ins)"])


class BasisTest(Instance):
    """A rate stays within one basis; a scale fallback is labelled; no basis switch makes gain or loss."""

    def test_an_app_trend_under_14_days_falls_back_to_scale_weigh_ins(self):
        for day, weight in WEIGH_INS:
            self.record(day, weight)
        trend = self.nutrition_trend()
        self.assertEqual((trend["preferred_basis"], trend["basis"], trend["fallback"]),
                         ("trend_weight", "scale_weight", True))
        self.assertEqual(trend["rate_per_week"], WEIGH_IN_RATE)
        section, summary = self.bodyweight_section()
        self.assertEqual(section[-1], "Basis: scale weight (recorded weigh-ins), standing in for trend weight, which "
                                      "covers under 14 days; weekly means.")
        self.assertTrue(summary[0].startswith("- Bodyweight: 63.5 kg on 12 Oct 2026, scale weight (recorded"))

    def test_a_supported_app_trend_ignores_scale_weigh_ins(self):
        self.readings(trend_reading("2026-09-21", 82.8), trend_reading("2026-10-05", 82.4))
        for day, weight in WEIGH_INS:
            self.record(day, weight)
        trend = self.nutrition_trend()
        self.assertEqual((trend["basis"], trend["fallback"], trend["sources"]), ("trend_weight", False, ["nutrition"]))
        self.assertEqual(trend["rate_per_week"], -0.2)

    def test_leaving_the_app_starts_a_scale_series_with_no_artificial_loss(self):
        self.readings(trend_reading("2026-09-14", 82.8), trend_reading("2026-09-28", 82.6),
                      scale_reading("2026-10-05", 80.1), scale_reading("2026-10-12", 80.0))
        self.edit_config('app = "macrofactor"', 'app = "none"')
        trend = self.nutrition_trend()
        self.assertEqual((trend["basis"], trend["fallback"]), ("scale_weight", False))
        self.assertEqual((trend["rate_per_week"], trend["span"]), (None, None))
        section, _ = self.bodyweight_section()
        self.assertNotIn("| 28 Sep 2026 | 82.6 |", section)

    def test_no_weight_anywhere_stays_unavailable(self):
        self.readings()
        trend = self.nutrition_trend()
        self.assertEqual((trend["basis"], trend["rate_per_week"], trend["sources"]), ("trend_weight", None, []))
        self.assertEqual(self.coach("nutrition", "targets")["data"]["inputs"]["bodyweight"], None)


class SkillWiringTest(unittest.TestCase):
    """Goals and check-in keep a fresh weigh-in before reading it, and check nutrition is on before writing to it."""

    def test_goals_keeps_the_weigh_in_before_the_targets_read_it(self):
        goals = " ".join(step_text("goals", "SKILL.md").split())
        self.assertIn("Keep it first: `python3 -m coach bodyweight record --date <day> --weight X`, nutrition on or "
                      "off; `nutrition targets` reads it.", goals)
        protein = " ".join(step_text("goals", "protein.md").split())
        self.assertIn("`--bodyweight` only for a what-if weight", protein)

    def test_check_in_handles_nutrition_off_before_recording_a_reading(self):
        text = " ".join(step_text("check-in", "nutrition.md").split())
        off = text.index("If it says `enabled: false`, keep any weigh-in with `python3 -m coach bodyweight record")
        self.assertLess(off, text.index("python3 -m coach nutrition record --date"))
        self.assertIn("`fallback: true`", text)


if __name__ == "__main__":
    unittest.main()
