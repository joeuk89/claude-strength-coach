"""Shopping coverage for scheduled protein anchors."""

import json
import unittest

from coach import config as config_module
from coach import dates, meals
from tests.test_meals import (
    CliMixin, DRAFT_PATH, InstanceCopy, NOW_DT, PLAN_ID, PLAN_JSON, PLAN_MD,
    buy, day, draft_with, flags_for, items, set_config, snapshot,
)
from tests.support import VALID


class AnchorShoppingTest(CliMixin, unittest.TestCase):
    def build(self, root=VALID, *, days=None, linked=False, draft=None):
        config = config_module.load(root)
        anchor = {"name": "Whey shake", "slot": "snack", "days": days or ["daily"]}
        anchor.update({"recipe": "whey-shake"} if linked else {"kcal": 150, "protein_g": 30})
        config["nutrition"]["anchors"] = [anchor]
        return meals.build(draft or draft_with(), root, now=NOW_DT, config=config)

    def test_bare_anchor_warns_without_guessing_the_same_named_card(self):
        plan = self.build()
        warnings = flags_for(plan, "anchor_shopping_unknown")
        self.assertEqual([flag["date"] for flag in warnings], [day["date"] for day in plan["days"]])
        for flag in warnings:
            self.assertEqual((flag["severity"], flag["slot"]), ("warn", "snack"))
            self.assertIn("Whey shake", flag["message"])
            self.assertIn("recipe", flag["message"])
            self.assertIn("shopping", flag["message"])
        self.assertIsNone(buy(plan, "whey protein powder"))
        self.assertFalse(any(entry["recipe"] == "whey-shake" for entry in plan["pool"]))
        self.assertEqual(meals.validate(plan, VALID), [])
        for planned_day in plan["days"]:
            anchor = items(plan, planned_day["date"], "snack")[0]
            self.assertEqual((anchor["kcal"], anchor["protein_g"]), (150, 30))

    def test_warning_reaches_dry_run_saved_render_and_shopping(self):
        with InstanceCopy() as root:
            before = snapshot(root)
            dry = self.run_ok(root, "meals", "build", "--input", str(DRAFT_PATH), "--dry-run")
            self.assertEqual(snapshot(root), before)
            self.assertIn("anchor_shopping_unknown", dry["rendered"])
            self.assertIn("Whey shake", dry["rendered"])
            self.run_ok(root, "meals", "build", "--input", str(DRAFT_PATH))
            self.run_ok(root, "meals", "render", PLAN_ID)
            self.assertEqual((root / PLAN_MD).read_text(encoding="utf-8"), dry["rendered"])
            shopping = self.run_ok(root, "meals", "shopping", PLAN_ID)
            self.assertIn("Whey shake", shopping["text"])
            self.assertIn("anchor_shopping_unknown", shopping["text"])
            self.run_ok(root, "meals", "approve", PLAN_ID)
            issue = self.run_ok(root, "meals", "shopping", PLAN_ID, "--format", "issue")
            self.assertIn("anchor_shopping_unknown", issue["body"])
            self.assertIn("Whey shake", issue["body"])

    def test_linked_daily_anchor_shops_seven_servings_and_is_not_an_open_slot(self):
        with InstanceCopy() as root:
            path = root / "nutrition/menu/whey-shake.md"
            path.write_text(path.read_text(encoding="utf-8").replace("qty = 38", "qty = 30"), encoding="utf-8")
            set_config(root, "kcal = 150\nprotein_g = 30\n", 'recipe = "whey-shake"\n')
            config = config_module.load(root)
            span = dates.Span(dates.parse_date("2026-10-12"), dates.parse_date("2026-10-18"))
            template = meals.template_week(root, span, config)
            plan = self.build(root, linked=True)
        self.assertFalse(any(slot["slot"] == "snack" for slot in template["open_slots"]))
        self.assertEqual(buy(plan, "whey protein powder")["qty"], 210)
        pooled = [entry for entry in plan["pool"] if entry["recipe"] == "whey-shake"]
        self.assertEqual(len(pooled), 1)
        self.assertEqual((pooled[0]["count"], pooled[0]["batches"]), (7, 7))
        self.assertEqual(flags_for(plan, "anchor_shopping_unknown"), [])
        self.assertEqual([d["totals"] for d in plan["days"]], [d["totals"] for d in self.build()["days"]])
        self.assertTrue(all(len(items(plan, d["date"], "snack")) == 1 for d in plan["days"]))

    def test_non_daily_anchors_only_warn_or_shop_on_scheduled_days(self):
        for linked in (False, True):
            with self.subTest(linked=linked):
                plan = self.build(days=["mon", "fri"], linked=linked)
                warnings = flags_for(plan, "anchor_shopping_unknown")
                if linked:
                    self.assertEqual(warnings, [])
                    self.assertEqual(buy(plan, "whey protein powder")["qty"], 76)
                else:
                    self.assertEqual([flag["date"] for flag in warnings], ["2026-10-12", "2026-10-16"])
                self.assertEqual(items(plan, "2026-10-13", "snack"), [])

    def test_office_change_and_skip_replace_scheduled_anchors(self):
        draft = draft_with(exceptions=[{"date": "2026-10-13", "office": False},
                                      {"date": "2026-10-16", "office": True},
                                      {"date": "2026-10-15", "slot": "snack", "entry": {"skip": True}}])
        for linked in (False, True):
            with self.subTest(linked=linked):
                plan = self.build(days=["office"], linked=linked, draft=draft)
                if linked:
                    self.assertEqual(buy(plan, "whey protein powder")["qty"], 38)
                else:
                    self.assertEqual([f["date"] for f in flags_for(plan, "anchor_shopping_unknown")],
                                     ["2026-10-16"])

    def test_covered_recipe_replaces_anchor_without_an_unwanted_purchase(self):
        draft = draft_with(exceptions=[{"date": "2026-10-12", "slot": "snack",
                                      "entry": {"recipe": "whey-shake", "covered_by": "work"}}])
        plan = self.build(days=["mon"], linked=True, draft=draft)
        self.assertIsNone(buy(plan, "whey protein powder"))
        self.assertEqual(flags_for(plan, "anchor_shopping_unknown"), [])
        self.assertEqual(items(plan, "2026-10-12", "snack")[0]["covered_by"], "work")
        self.assertEqual(day(plan, "2026-10-12")["totals"], day(self.build(), "2026-10-12")["totals"])

    def test_supplied_food_replaces_bare_anchor_and_its_warning(self):
        plan = self.build(days=["mon"], draft=draft_with(exceptions=[
            {"date": "2026-10-12", "slot": "snack", "entry": {"cover": "work", "kcal": 150, "protein_g": 30}}
        ]))
        self.assertEqual(flags_for(plan, "anchor_shopping_unknown"), [])
        self.assertIsNone(buy(plan, "whey protein powder"))
        self.assertEqual(items(plan, "2026-10-12", "snack")[0]["cover"], "work")

    def test_historical_approved_plan_keeps_its_snapshot_and_hash(self):
        with InstanceCopy() as root:
            plan = self.build(root)
            plan["flags"] = [f for f in plan["flags"] if f["code"] != "anchor_shopping_unknown"]
            approved = meals.approve(plan, NOW_DT)
            (root / PLAN_JSON).write_text(json.dumps(approved), encoding="utf-8")
            loaded = meals.load(root, PLAN_ID)
            self.assertEqual(loaded, approved)
            self.assertTrue(meals.is_approved(loaded))
            before = snapshot(root)
            rendered = self.run_ok(root, "meals", "render", PLAN_ID, "--dry-run")
            self.assertNotIn("anchor_shopping_unknown", rendered["text"])
            self.assertEqual(snapshot(root), before)

    def test_linked_anchor_obeys_batch_rounding_use_up_and_pantry(self):
        with InstanceCopy() as root:
            path = root / "nutrition/menu/whey-shake.md"
            path.write_text(path.read_text(encoding="utf-8").replace("servings = 1", "servings = 2")
                            .replace("qty = 38", "qty = 60"), encoding="utf-8")
            set_config(root, 'staples = ["eggs", "rolled oats", "olive oil"]',
                       'staples = ["eggs", "rolled oats", "olive oil", "whey protein powder"]')
            plan = self.build(root, linked=True, draft=draft_with(
                use_up=[{"item": "whey protein powder", "qty": 30, "unit": "g"}]))
        self.assertIsNone(buy(plan, "whey protein powder"))
        self.assertIn({"item": "whey protein powder", "qty": 210, "unit": "g"}, plan["shopping"]["check"])
        self.assertEqual(plan["shopping"]["used_up"], [{"item": "whey protein powder", "qty": 30, "unit": "g"}])


if __name__ == "__main__":
    unittest.main()
