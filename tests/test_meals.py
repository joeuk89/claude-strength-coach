"""Meal plans as exceptions to a standing template (contract C4, C34)."""

import copy
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from coach import config as config_module
from coach import meals
from coach.errors import ValidationError
from tests.support import FIXTURES, INSTANCES, VALID, run_cli, run_module

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
NOW_DT = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
DRAFT_PATH = FIXTURES / "meals" / "draft-2026-10-12.json"
DRAFT = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
PLAN_ID = "2026-10-12"
PLAN_JSON = Path("data/nutrition/plans/2026-10-12.json")
PLAN_MD = Path("nutrition/plans/2026-10-12.md")
STALE = INSTANCES / "meals-stale-render"
BAD_ARITHMETIC = INSTANCES / "meals-bad-arithmetic"
BAD_TEMPLATE = INSTANCES / "meals-bad-template"

CONFLICT_CARD = """<!-- coach:card
schema_version = 1
title = "Rice test bowl"
slots = ["lunch", "dinner"]
servings = 1
prep = "assemble"
time_min = 5
status = "active"
nutrition = "estimated"

[per_serving]
kcal = 500
protein_g = 40
carbs_g = 60
fat_g = 11

[[ingredients]]
qty = 1
unit = "each"
item = "microwave basmati rice pouch"
aisle = "tins-jars-dry"

[[ingredients]]
qty = 150
unit = "g"
item = "chicken breast, cooked"
aisle = "meat-fish"

[[variations]]
name = "light"
label = "half the rice"
changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]
delta = {kcal = -105, protein_g = 0, carbs_g = -22, fat_g = 0}

[[variations]]
name = "no-rice"
label = "no rice"
changes = [{item = "microwave basmati rice pouch", qty = -1, unit = "each"}]
delta = {kcal = -210, protein_g = 0, carbs_g = -44, fat_g = 0}
-->
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


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def draft_with(**changes):
    draft = copy.deepcopy(DRAFT)
    draft.update(changes)
    return draft


def build(draft=None, root=VALID):
    return meals.build(copy.deepcopy(draft or DRAFT), root, now=NOW_DT)


def day(plan, date):
    return next(d for d in plan["days"] if d["date"] == date)


def items(plan, date, slot):
    return [item for item in day(plan, date)["items"] if item["slot"] == slot]


def buy(plan, item):
    return next((line for line in plan["shopping"]["buy"] if line["item"] == item), None)


def codes(plan, severity=None):
    return [f["code"] for f in plan["flags"] if severity is None or f["severity"] == severity]


def flags_for(plan, code):
    return [f for f in plan["flags"] if f["code"] == code]


def set_config(root, old, new):
    path = Path(root) / "config.toml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class CliMixin:
    def run_ok(self, root, *argv, env=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope["data"]

    def run_code(self, wanted, root, *argv, env=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, wanted, (envelope, stderr))
        return envelope


class TemplateTest(CliMixin, unittest.TestCase):
    def test_valid_week_lists_the_standing_week(self):
        data = self.run_ok(VALID, "meals", "template", "--week", "2026-10-12")
        self.assertEqual(data["span"], {"start": "2026-10-12", "end": "2026-10-18"})
        self.assertEqual([d["date"] for d in data["days"]],
                         ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17",
                          "2026-10-18"])
        slots = {(d["weekday"], s["slot"]): s for d in data["days"] for s in d["slots"]}
        for weekday in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            self.assertEqual(slots[(weekday, "breakfast")]["entries"][0]["recipe"], "overnight-oats")
            anchor = slots[(weekday, "snack")]["entries"][0]
            self.assertEqual((anchor["source"], anchor["name"]), ("anchor", "Whey shake"))
            self.assertFalse(slots[(weekday, "snack")]["open"])
        for weekday in ("tue", "thu"):
            self.assertEqual(slots[(weekday, "lunch")]["entries"][0]["pool"], ["chicken-rice-bowl"])
            self.assertFalse(slots[(weekday, "lunch")]["open"])
        for weekday in ("mon", "wed", "fri", "sat", "sun"):
            self.assertTrue(slots[(weekday, "lunch")]["open"])
        for weekday in ("mon", "tue", "wed", "thu"):
            self.assertEqual(slots[(weekday, "dinner")]["entries"][0]["cover"], "family")
        for weekday in ("fri", "sat", "sun"):
            self.assertTrue(slots[(weekday, "dinner")]["open"])
        self.assertEqual([d["office"] for d in data["days"]], [False, True, False, True, False, False, False])
        self.assertEqual(len(data["open_slots"]), 8)
        self.assertEqual(data["style"], "loose")

    def test_default_is_the_week_ahead(self):
        self.assertEqual(self.run_ok(VALID, "meals", "template")["span"]["start"], "2026-10-12")

    def test_sunday_weeks(self):
        with InstanceCopy() as root:
            set_config(root, 'week_starts = "monday"', 'week_starts = "sunday"')
            data = self.run_ok(root, "meals", "template", "--week", "2026-10-12")
        self.assertEqual(data["span"], {"start": "2026-10-11", "end": "2026-10-17"})
        self.assertEqual(data["days"][0]["weekday"], "sun")

    def test_no_template_exits_5(self):
        with InstanceCopy() as root:
            path = root / "config.toml"
            path.write_text(path.read_text(encoding="utf-8").split("[nutrition.template]")[0], encoding="utf-8")
            envelope = self.run_code(5, root, "meals", "template")
        self.assertIn("[nutrition.template]", envelope["error"]["message"])


class BuildTest(CliMixin, unittest.TestCase):
    def test_dry_run_writes_nothing_and_returns_the_plan(self):
        with InstanceCopy() as root:
            (root / PLAN_JSON).unlink()
            before = snapshot(root)
            data = self.run_ok(root, "meals", "build", "--input", str(DRAFT_PATH), "--dry-run")
            self.assertEqual(snapshot(root), before)
        self.assertIs(data["written"], False)
        self.assertEqual(data["plan"]["id"], PLAN_ID)

    def test_day_totals_equal_their_items(self):
        plan = build()
        for each in plan["days"]:
            self.assertEqual(each["totals"]["kcal"], sum(i["kcal"] for i in each["items"]))
            self.assertEqual(each["totals"]["protein_g"], sum(i["protein_g"] for i in each["items"]))
        self.assertEqual(day(plan, "2026-10-12")["totals"], {"kcal": 2110, "protein_g": 148})
        self.assertEqual(meals.validate(plan, VALID), [])

    def test_exception_replaces_the_template_dinner(self):
        dinner = items(build(), "2026-10-14", "dinner")
        self.assertEqual(len(dinner), 1)
        self.assertEqual((dinner[0]["source"], dinner[0]["cover"], dinner[0]["note"]), ("exception", "out", "birthday"))
        self.assertEqual(items(build(), "2026-10-13", "dinner")[0]["cover"], "family")

    def test_light_bowl_twice_shops_340_g_chicken_and_one_pouch(self):
        plan = build()
        self.assertIn({"recipe": "chicken-rice-bowl", "title": "Chicken + rice bowl", "variations": ["light"],
                       "count": 2, "covered_by": None, "servings": 1, "batches": 2, "kcal": 505, "protein_g": 50},
                      plan["pool"])
        self.assertEqual((buy(plan, "chicken breast, cooked")["qty"], buy(plan, "chicken breast, cooked")["unit"]),
                         (340, "g"))
        self.assertEqual(buy(plan, "microwave basmati rice pouch")["qty"], 1)

    def test_use_up_is_subtracted(self):
        plan = build()
        self.assertEqual(buy(plan, "spinach")["qty"], 140)
        self.assertEqual(plan["shopping"]["used_up"], [{"item": "spinach", "qty": 100, "unit": "g"}])

    def test_staples_go_to_check_you_have(self):
        plan = build()
        self.assertIsNone(buy(plan, "eggs"))
        self.assertEqual(plan["shopping"]["check"],
                         [{"item": "eggs", "qty": 9, "unit": "each"}, {"item": "rolled oats", "qty": 420, "unit": "g"},
                          {"item": "olive oil", "qty": 1, "unit": "tbsp"}])

    def test_buy_groups_follow_the_aisle_walk_order(self):
        aisles = [line["aisle"] for line in build()["shopping"]["buy"]]
        walk = config_module.load(VALID).nutrition.bank.aisles
        self.assertEqual(aisles, sorted(aisles, key=walk.index))
        self.assertEqual(list(dict.fromkeys(aisles)), ["produce", "meat-fish", "dairy-eggs", "tins-jars-dry"])

    def test_targets_and_style(self):
        plan = build()
        self.assertEqual(plan["targets"], {"kcal": 2400, "kcal_source": "reading 2026-10-11", "protein_floor_g": 110})
        self.assertEqual(plan["style"], "loose")
        self.assertEqual(plan["created_at"], "2026-10-11T18:00:00Z")
        self.assertEqual(codes(plan, "block"), [])

    def test_kcal_off_target_uses_the_tolerance(self):
        flagged = [f["date"] for f in flags_for(build(), "kcal_off_target")]
        self.assertEqual(flagged, ["2026-10-13", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"])

    def test_lock_and_input_are_kept(self):
        plan = build()
        self.assertEqual(items(plan, "2026-10-13", "lunch")[0]["lock"], "post-run, must be quick")
        self.assertEqual(plan["input"]["notes"], "Batch the chilli on Sunday.")
        self.assertEqual(plan["input"]["use_up"], DRAFT["use_up"])

    def test_batches_round_up_by_servings(self):
        def chilli_dinners(count):
            dates = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16"][:count]
            assignments = [{"date": d, "slot": "lunch", "entry": {"recipe": "turkey-chilli"}} for d in dates]
            return build(draft_with(assignments=assignments, exceptions=[], use_up=[]))

        three, five = chilli_dinners(3), chilli_dinners(5)
        self.assertEqual(next(p for p in three["pool"] if p["recipe"] == "turkey-chilli")["batches"], 1)
        self.assertEqual(buy(three, "turkey mince, 5% fat")["qty"], 500)
        self.assertEqual(next(p for p in five["pool"] if p["recipe"] == "turkey-chilli")["batches"], 2)
        self.assertEqual(buy(five, "turkey mince, 5% fat")["qty"], 1000)

    def test_meal_kit_entry_counts_but_is_not_shopped(self):
        draft = draft_with(assignments=[
            {"date": "2026-10-16", "slot": "dinner", "entry": {"recipe": "turkey-chilli", "covered_by": "gousto"}}],
            exceptions=[], use_up=[])
        plan = build(draft)
        self.assertEqual(day(plan, "2026-10-16")["totals"]["kcal"], 440 + 620 + 150)
        self.assertIsNone(buy(plan, "turkey mince, 5% fat"))
        entry = next(p for p in plan["pool"] if p["recipe"] == "turkey-chilli")
        self.assertEqual((entry["covered_by"], entry["batches"]), ("gousto", None))

    def test_slot_open(self):
        plan = build(draft_with(assignments=DRAFT["assignments"][1:]))
        open_flags = flags_for(plan, "slot_open")
        self.assertEqual([(f["date"], f["slot"], f["severity"]) for f in open_flags],
                         [("2026-10-12", "lunch", "warn")])

    def test_protein_below_floor(self):
        draft = draft_with(exceptions=DRAFT["exceptions"] + [
            {"date": "2026-10-17", "slot": "snack", "entry": {"skip": True}},
            {"date": "2026-10-17", "slot": "breakfast", "entry": {"skip": True}}])
        flagged = flags_for(build(draft), "protein_below_floor")
        self.assertEqual([(f["date"], f["severity"]) for f in flagged], [("2026-10-17", "warn")])

    def test_no_target_without_reading_or_kcal_target(self):
        with InstanceCopy() as root:
            (root / "data" / "nutrition" / "readings.json").unlink()
            plan = build(root=root)
        self.assertIn("no_target", codes(plan))
        self.assertEqual(plan["targets"]["kcal"], None)
        self.assertNotIn("kcal_off_target", codes(plan))

    def test_kcal_target_without_an_app(self):
        with InstanceCopy() as root:
            set_config(root, 'app = "macrofactor"', 'app = "none"\nkcal_target = 2000')
            plan = build(root=root)
        self.assertEqual(plan["targets"], {"kcal": 2000, "kcal_source": "kcal_target", "protein_floor_g": 110})

    def test_variation_conflict_blocks_approval(self):
        with InstanceCopy() as root:
            (root / "nutrition" / "menu" / "rice-test-bowl.md").write_text(CONFLICT_CARD, encoding="utf-8")
            draft = draft_with(assignments=DRAFT["assignments"] + [
                {"date": "2026-10-18", "slot": "dinner",
                 "entry": {"recipe": "rice-test-bowl", "variations": ["light", "no-rice"]}}])
            draft_path = write_json(root / "draft.json", draft)
            data = self.run_ok(root, "meals", "build", "--input", str(draft_path))
            conflict = [f for f in data["plan"]["flags"] if f["code"] == "variation_conflict"]
            self.assertEqual([f["severity"] for f in conflict], ["block"])
            envelope = self.run_code(3, root, "meals", "approve", PLAN_ID)
            self.assertIn("variation_conflict", json.dumps(envelope["error"]))

    def test_unknown_benched_and_unmatched(self):
        with InstanceCopy() as root:
            card = root / "nutrition" / "menu" / "spinach-omelette.md"
            card.write_text(card.read_text(encoding="utf-8").replace('status = "active"', 'status = "benched"'),
                            encoding="utf-8")
            draft = draft_with(
                assignments=DRAFT["assignments"] + [
                    {"date": "2026-10-12", "slot": "snack", "entry": {"recipe": "no-such-card"}},
                    {"date": "2026-10-13", "slot": "snack",
                     "entry": {"recipe": "chicken-rice-bowl", "variations": ["extra-large"]}}],
                use_up=[{"item": "spinach", "qty": 100, "unit": "g"}, {"item": "leeks", "qty": 2, "unit": "each"}])
            plan = build(draft, root)
        self.assertEqual([f["severity"] for f in flags_for(plan, "recipe_unknown")], ["block"])
        self.assertEqual([f["severity"] for f in flags_for(plan, "variation_unknown")], ["block"])
        self.assertEqual({f["severity"] for f in flags_for(plan, "recipe_benched")}, {"warn"})
        unmatched = flags_for(plan, "use_up_unmatched")
        self.assertEqual(len(unmatched), 1)
        self.assertIn("leeks", unmatched[0]["message"])
        unknown_item = items(plan, "2026-10-12", "snack")[-1]
        self.assertEqual((unknown_item["recipe"], unknown_item["kcal"]), ("no-such-card", None))
        self.assertEqual(meals.validate(plan, VALID), [])

    def test_units_mixed(self):
        draft = draft_with(use_up=[{"item": "spinach", "qty": 1, "unit": "each"}])
        plan = build(draft)
        self.assertEqual([f["severity"] for f in flags_for(plan, "units_mixed")], ["warn"])
        self.assertEqual(buy(plan, "spinach")["qty"], 240)

    def test_draft_problems_exit_1(self):
        for bad in (draft_with(assignments=[{"date": "2026-10-30", "slot": "lunch",
                                             "entry": {"recipe": "turkey-chilli"}}]),
                    draft_with(assignments=[{"date": "2026-10-12", "slot": "elevenses",
                                             "entry": {"recipe": "turkey-chilli"}}]),
                    draft_with(exceptions=[{"date": "2026-10-14", "slot": "dinner",
                                            "entry": {"recipe": "turkey-chilli", "cover": "out"}}]),
                    draft_with(exceptions=[{"date": "2026-10-14", "slot": "dinner", "entry": {"cover": "out"}}]),
                    draft_with(exceptions=DRAFT["exceptions"] * 2),
                    draft_with(notes=3)):
            with self.subTest(draft=bad):
                with self.assertRaises(ValidationError):
                    build(bad)

    def test_office_exception_moves_the_pool(self):
        draft = draft_with(exceptions=[{"date": "2026-10-15", "office": False},
                                       {"date": "2026-10-16", "office": True}],
                           assignments=[], use_up=[])
        plan = build(draft)
        self.assertEqual([d["office"] for d in plan["days"]][3:5], [False, True])
        opened = {(f["date"], f["slot"]) for f in flags_for(plan, "slot_open")}
        self.assertIn(("2026-10-16", "lunch"), opened)
        self.assertIn(("2026-10-15", "lunch"), opened)

    def test_rebuilding_an_approved_plan_is_refused(self):
        with InstanceCopy() as root:
            self.run_ok(root, "meals", "approve", PLAN_ID)
            self.run_code(3, root, "meals", "build", "--input", str(DRAFT_PATH))
            self.run_code(3, root, "meals", "build", "--input", str(DRAFT_PATH), "--dry-run")


class FixtureTest(unittest.TestCase):
    def test_valid_plan_is_the_fixture_draft_built(self):
        stored = json.loads((VALID / PLAN_JSON).read_text(encoding="utf-8"))
        self.assertEqual(stored, build())

    def test_valid_instance_checks_pass(self):
        code, envelope, _ = run_cli(["--root", str(VALID), "check", "--only",
                                     "meal_plans,meal_plan_render_fresh,nutrition_template"], env=NOW)
        self.assertEqual(code, 0, envelope)
        self.assertEqual({r["status"] for r in envelope["data"]["results"]}, {"pass"})


class ApproveShoppingTest(CliMixin, unittest.TestCase):
    def test_shopping_issue_needs_approval(self):
        with InstanceCopy() as root:
            envelope = self.run_code(3, root, "meals", "shopping", PLAN_ID, "--format", "issue")
            self.assertEqual(envelope["error"]["code"], "refused")
            approved = self.run_ok(root, "meals", "approve", PLAN_ID)
            self.assertTrue(approved["hash"].startswith("sha256:"))
            self.assertIs(self.run_ok(root, "meals", "approve", PLAN_ID)["already_approved"], True)
            data = self.run_ok(root, "meals", "shopping", PLAN_ID, "--format", "issue")
        body = data["body"]
        buy_part = body.split("### Check you have")[0]
        item_lines = [line for line in buy_part.splitlines() if line and not line.startswith(("#", "Meal plan"))]
        self.assertTrue(item_lines)
        self.assertTrue(all(line.startswith("- [ ] ") for line in item_lines), item_lines)
        self.assertIn("- [ ] 140 g spinach", body)
        check_part = body.split("### Check you have")[1]
        self.assertIn("- [ ] 9 eggs", check_part)
        self.assertLess(body.index("### produce"), body.index("### meat / fish"))
        self.assertIn("12 Oct", data["title"])

    def test_markdown_shopping_works_before_approval(self):
        data = self.run_ok(VALID, "meals", "shopping", PLAN_ID)
        self.assertEqual(data["format"], "markdown")
        self.assertIn("140 g spinach", data["text"])

    def test_approve_dry_run_writes_nothing(self):
        with InstanceCopy() as root:
            before = snapshot(root)
            self.run_ok(root, "meals", "approve", PLAN_ID, "--dry-run")
            self.assertEqual(snapshot(root), before)

    def test_an_edit_breaks_the_approval(self):
        with InstanceCopy() as root:
            self.run_ok(root, "meals", "approve", PLAN_ID)
            path = root / PLAN_JSON
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["input"]["notes"] = "changed"
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertIs(self.run_ok(root, "meals", "show", PLAN_ID)["approved"], False)
            self.run_code(3, root, "meals", "shopping", PLAN_ID, "--format", "issue")


class RenderTest(CliMixin, unittest.TestCase):
    def test_render_twice_is_byte_identical_with_the_c11_header(self):
        with InstanceCopy() as root:
            (root / PLAN_MD).unlink()
            first = self.run_ok(root, "meals", "render", PLAN_ID)
            self.assertIs(first["written"], True)
            once = (root / PLAN_MD).read_bytes()
            second = self.run_ok(root, "meals", "render", PLAN_ID)
            self.assertIs(second["changed"], False)
            self.assertEqual((root / PLAN_MD).read_bytes(), once)
        text = once.decode("utf-8")
        self.assertTrue(text.startswith(
            "<!-- generated by coach from data/nutrition/plans/2026-10-12.json; edit the data, then run: "
            "python3 -m coach meals render 2026-10-12 -->\n"))
        self.assertEqual(once, (VALID / PLAN_MD).read_bytes())

    def test_render_shows_the_plan(self):
        text = meals.render_plan(build())
        self.assertIn("2400 kcal (reading 2026-10-11) · protein floor 110 g · style: loose", text)
        self.assertIn("| [Chicken + rice bowl](../menu/chicken-rice-bowl.md) (light) | 2 |", text)
        self.assertIn("family *(covered)*", text)
        self.assertIn("out *(covered)* — birthday", text)
        self.assertIn("🔒 post-run, must be quick", text)
        self.assertIn("Whey shake *(anchor)*", text)
        self.assertIn("`kcal_off_target`", text)
        self.assertIn("Batch the chilli on Sunday.", text)
        self.assertIn("100 g spinach", text)
        self.assertIn("## Shopping list", text)

    def test_render_dry_run_writes_nothing(self):
        with InstanceCopy() as root:
            (root / PLAN_MD).unlink()
            before = snapshot(root)
            data = self.run_ok(root, "meals", "render", PLAN_ID, "--dry-run")
            self.assertEqual(snapshot(root), before)
        self.assertIn("# Meal plan", data["text"])

    def test_hand_edit_fails_the_freshness_check(self):
        envelope = self.run_code(1, STALE, "check", "--only", "meal_plan_render_fresh")
        result = envelope["data"]["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertIn("meals render 2026-10-12", result["message"])
        with InstanceCopy() as root:
            (root / PLAN_MD).write_text((root / PLAN_MD).read_text(encoding="utf-8") + "x\n", encoding="utf-8")
            self.run_code(1, root, "check", "--only", "meal_plan_render_fresh")

    def test_editing_a_card_after_the_build_changes_nothing(self):
        with InstanceCopy() as root:
            card = root / "nutrition" / "menu" / "chicken-rice-bowl.md"
            card.write_text(card.read_text(encoding="utf-8").replace('title = "Chicken + rice bowl"',
                                                                     'title = "Chicken bowl"')
                            .replace("kcal = 610", "kcal = 640"), encoding="utf-8")
            data = self.run_ok(root, "meals", "render", PLAN_ID, "--dry-run")
        self.assertEqual(data["text"], (VALID / PLAN_MD).read_text(encoding="utf-8"))


class ChecksTest(CliMixin, unittest.TestCase):
    def test_meal_plans_fails_on_bad_arithmetic(self):
        envelope = self.run_code(1, BAD_ARITHMETIC, "check", "--only", "meal_plans")
        self.assertIn("totals", envelope["data"]["results"][0]["message"])
        self.run_code(1, BAD_ARITHMETIC, "meals", "validate", PLAN_ID)

    def test_nutrition_template_fails_on_missing_and_benched_cards(self):
        envelope = self.run_code(1, BAD_TEMPLATE, "check", "--only", "nutrition_template")
        messages = " ".join(r["message"] for r in envelope["data"]["results"])
        self.assertIn("porridge", messages)
        self.assertIn("benched", messages)
        self.assertIn("protein-bar", messages)

    def test_checks_skip_without_plans_or_nutrition(self):
        root = INSTANCES / "hevy-fresh"
        data = self.run_ok(root, "check", "--only", "meal_plans,meal_plan_render_fresh,nutrition_template")
        self.assertEqual({r["status"] for r in data["results"]}, {"skip"})


class BriefLineTest(CliMixin, unittest.TestCase):
    def test_brief_line_names_the_plan_covering_today(self):
        data = self.run_ok(VALID, "nutrition", "status", env={"COACH_NOW": "2026-10-14T08:00:00Z"})
        self.assertTrue(data["brief_line"].endswith(" · plan: nutrition/plans/2026-10-12.md"), data["brief_line"])
        self.assertNotIn("plan:", self.run_ok(VALID, "nutrition", "status")["brief_line"])


class SubprocessTest(unittest.TestCase):
    def test_build_dry_run_as_a_subprocess(self):
        code, envelope, stderr = run_module(
            ["--root", "tests/fixtures/instances/valid", "meals", "build", "--input",
             "tests/fixtures/meals/draft-2026-10-12.json", "--dry-run"], env=NOW)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(envelope["data"]["plan"]["id"], PLAN_ID)


if __name__ == "__main__":
    unittest.main()
