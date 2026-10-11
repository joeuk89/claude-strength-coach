import copy
import json
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

from coach import recipes
from coach.config_tables.nutrition import bank_defaults
from coach.config import parse
from coach.errors import ConfigError
from tests.support import FIXTURES, INSTANCES, MINIMAL_CONFIG, REPO_ROOT, VALID
from tests.support.skills import skill_text

MENU = VALID / "nutrition" / "menu"
YAML_MENU = INSTANCES / "yaml-cards" / "nutrition" / "menu"
PAGES = FIXTURES / "recipes"


def config_from(text=MINIMAL_CONFIG):
    return parse(tomllib.loads(text), "config.toml")


def valid_card(slug="chicken-rice-bowl"):
    return recipes.load_card(MENU / f"{slug}.md")


def card_with(data, slug="test-card"):
    return recipes.Card(slug=slug, path=Path(f"{slug}.md"), text="", data=data, body_start=0)


def card_from_text(slug, text):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{slug}.md"
        path.write_text(text, encoding="utf-8")
        card = recipes.load_card(path)
    return card


def statuses(results):
    return [r.status for r in results]


class RoundTripMixin:
    def assert_round_trip(self, draft):
        self.assertEqual(tomllib.loads(recipes.card_toml(draft)), draft)


class BankConfigTest(unittest.TestCase):
    def test_defaults_without_a_nutrition_table(self):
        config = config_from()
        self.assertNotIn("nutrition", config)
        bank = recipes.bank_settings(config)
        self.assertEqual(bank["macro_sum_warn_pct"], 10)
        self.assertEqual(bank["min_protein_per_100kcal"]["lunch"], 5.0)

    def test_partial_table_takes_defaults(self):
        config = config_from(MINIMAL_CONFIG + "[nutrition.bank]\nmin_protein_per_100kcal = {lunch = 0.0}\n")
        bank = recipes.bank_settings(config)
        self.assertEqual(bank["min_protein_per_100kcal"],
                         {"breakfast": 5.0, "lunch": 0.0, "dinner": 5.0, "snack": 0.0})
        self.assertEqual(bank["aisles"][0], "produce")
        self.assertEqual(bank["slot_notes"], {})

    def test_unknown_and_bad_keys(self):
        for text, fragment in (("[nutrition.bank]\naisle = []\n", "aisle"),
                               ("[nutrition.bank]\nmacro_sum_warn_pct = -1\n", "macro_sum_warn_pct"),
                               ("[nutrition.bank.slot_notes]\nlunch = 3\n", "lunch")):
            with self.subTest(text=text):
                with self.assertRaises(ConfigError) as caught:
                    config_from(MINIMAL_CONFIG + text)
                self.assertIn(fragment, caught.exception.message)

    def test_commented_example_validates(self):
        text = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        block = re.search(r"^# \[nutrition\.bank\]\n(?:#.*\n)+", text, re.M)
        self.assertIsNotNone(block)
        uncommented = "\n".join(line[2:] for line in block.group(0).splitlines() if line.startswith("# "))
        config = config_from(MINIMAL_CONFIG + uncommented + "\n")
        self.assertEqual(config.nutrition.bank.slot_notes, {"breakfast": "must be fast or it gets skipped"})
        self.assertEqual(config.nutrition.bank.aisles, bank_defaults()["aisles"])


class CardTomlTest(RoundTripMixin, unittest.TestCase):
    def test_fixture_cards_round_trip(self):
        for path in sorted(MENU.glob("*.md")):
            if path.name != "index.md":
                with self.subTest(card=path.stem):
                    self.assert_round_trip(recipes.load_card(path).data)

    def test_awkward_strings_and_numbers(self):
        draft = {
            "schema_version": 1,
            "title": 'Mum\'s "best" chilli \\ with --> arrows\nand\ttabs ½ é',
            "slots": ["dinner"],
            "tags": [],
            "per_serving": {"kcal": 610, "protein_g": 50.5, "carbs_g": 0.25, "fat_g": 1e-05},
            "variations": [{"name": "+egg", "label": "x", "changes": [], "delta": {"kcal": -1.5}}],
            "odd key": True,
        }
        text = recipes.card_toml(draft)
        self.assertNotIn("-->", text)
        self.assert_round_trip(draft)

    def test_refuses_null(self):
        with self.assertRaises(ValueError):
            recipes.card_toml({"source": None})

    def test_composed_card_reads_back(self):
        card = valid_card()
        text = recipes.compose_card("chicken-rice-bowl", card.data, "## Method\n1. Eat.\n")
        again = card_from_text("chicken-rice-bowl", text)
        self.assertEqual(again.data, card.data)
        self.assertTrue(text.endswith("<!-- coach:end card chicken-rice-bowl -->\n\n## Method\n1. Eat.\n"))


class ValidateCardTest(unittest.TestCase):
    def setUp(self):
        self.config = config_from()
        self.data = copy.deepcopy(valid_card().data)

    def validate(self, data=None, config=None):
        return recipes.validate_card(card_with(data or self.data, "chicken-rice-bowl"), config or self.config)

    def test_fixture_cards_pass(self):
        for slug in ("chicken-rice-bowl", "overnight-oats", "whey-shake"):
            with self.subTest(slug=slug):
                self.assertEqual(recipes.validate_card(valid_card(slug), self.config), [])

    def test_macro_sum_bands(self):
        self.data["per_serving"]["kcal"] = 700
        results = self.validate()
        self.assertEqual(statuses(results), ["warn"])
        self.data["per_serving"]["kcal"] = 800
        results = self.validate()
        self.assertEqual(statuses(results), ["fail"])
        for fragment in ("chicken-rice-bowl", "800", "582", "20%"):
            self.assertIn(fragment, results[0].message)

    def test_macro_sum_bands_follow_config(self):
        self.data["per_serving"]["kcal"] = 700
        config = config_from(MINIMAL_CONFIG + "[nutrition.bank]\nmacro_sum_warn_pct = 25\n")
        self.assertEqual(self.validate(config=config), [])

    def test_density_warns_per_slot_and_can_be_switched_off(self):
        self.data["per_serving"] = {"kcal": 500, "protein_g": 20, "carbs_g": 60, "fat_g": 20}
        results = self.validate()
        self.assertEqual(statuses(results), ["warn"])
        self.assertIn("4.0 g protein per 100 kcal", results[0].message)
        self.assertIn("lunch", results[0].message)
        config = config_from(MINIMAL_CONFIG + "[nutrition.bank]\nmin_protein_per_100kcal = {lunch = 0.0}\n")
        self.assertEqual(self.validate(config=config), [])

    def test_snacks_are_not_density_checked(self):
        self.data["slots"] = ["snack"]
        self.data["per_serving"] = {"kcal": 500, "protein_g": 5, "carbs_g": 70, "fat_g": 22}
        self.assertEqual(self.validate(), [])

    def test_schema_errors_fail(self):
        del self.data["per_serving"]["fat_g"]
        self.data["prep"] = "microwave"
        results = self.validate()
        self.assertEqual(set(statuses(results)), {"fail"})
        text = " ".join(r.message for r in results)
        self.assertIn("fat_g", text)
        self.assertIn("prep", text)

    def test_unconfigured_slot_fails(self):
        self.data["slots"] = ["elevenses"]
        self.assertIn("elevenses", self.validate()[0].message)

    def test_eat_out_and_ingredients(self):
        self.data["prep"] = "eat-out"
        self.assertIn("eat-out", self.validate()[0].message)
        del self.data["ingredients"]
        del self.data["variations"]
        self.assertEqual(self.validate(), [])
        self.data["prep"] = "cook"
        self.assertIn("at least one ingredient", self.validate()[0].message)

    def test_aisle_outside_the_list_warns(self):
        self.data["ingredients"][0]["aisle"] = "deli"
        results = self.validate()
        self.assertEqual(statuses(results), ["warn"])
        self.assertIn("deli", results[0].message)

    def test_duplicate_ingredient_fails(self):
        self.data["ingredients"].append(dict(self.data["ingredients"][0]))
        self.assertEqual(statuses(self.validate()), ["fail"])

    def variation_messages(self, changes, delta=None):
        self.data["variations"] = [{"name": "v", "label": "v", "changes": changes,
                                    "delta": delta or {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}}]
        return [(r.status, r.message) for r in self.validate()]

    def test_variation_changes(self):
        pouch = "microwave basmati rice pouch"
        self.assertEqual(self.variation_messages([{"item": pouch, "qty": -1, "unit": "each"}]), [])
        cases = [
            ([{"item": "tofu", "qty": -1, "unit": "each"}], "fail", "not an ingredient"),
            ([{"item": "tofu", "qty": 100, "unit": "g"}], "fail", "without an aisle"),
            ([{"item": "tofu", "qty": 100, "unit": "g", "aisle": "deli"}], "warn", "deli"),
            ([{"item": pouch, "qty": 50, "unit": "g"}], "fail", "in g"),
            ([{"item": pouch, "qty": -2, "unit": "each"}], "fail", "has 1"),
            ([{"item": pouch, "qty": -1, "unit": "each"}, {"item": pouch, "qty": 1, "unit": "each"}], "fail", "twice"),
            ([], "warn", "changes no ingredients"),
        ]
        for changes, status, fragment in cases:
            with self.subTest(fragment=fragment):
                found = self.variation_messages(changes)
                self.assertEqual([s for s, _ in found], [status], found)
                self.assertIn(fragment, found[0][1])

    def test_variation_delta_has_a_20_kcal_floor(self):
        pouch = [{"item": "microwave basmati rice pouch", "qty": -0.5, "unit": "each"}]
        within_floor = {"kcal": -105, "protein_g": 0, "carbs_g": -22, "fat_g": 0}
        self.assertEqual(self.variation_messages(pouch, within_floor), [])
        warn = {"kcal": -300, "protein_g": 0, "carbs_g": -84, "fat_g": 0}
        self.assertEqual([s for s, _ in self.variation_messages(pouch, warn)], ["warn"])
        fail = {"kcal": -50, "protein_g": 0, "carbs_g": -30, "fat_g": 0}
        found = self.variation_messages(pouch, fail)
        self.assertEqual([s for s, _ in found], ["fail"])
        self.assertIn('variation "v"', found[0][1])

    def test_duplicate_variation_name_fails(self):
        self.data["variations"].append(copy.deepcopy(self.data["variations"][0]))
        self.assertIn("defined twice", self.validate()[0].message)


class RenderTest(unittest.TestCase):
    def test_fixture_regions_are_fresh(self):
        for path in sorted(MENU.glob("*.md")):
            if path.name != "index.md":
                card = recipes.load_card(path)
                with self.subTest(card=card.slug):
                    self.assertEqual(recipes.current_region(card), recipes.render_card_region(card))
                    self.assertEqual(recipes.rendered_text(card), card.text)

    def test_region_content(self):
        region = recipes.render_card_region(valid_card())
        self.assertIn("| **Per serving** | 610 kcal · 50 g P · 55 g C · 18 g F |", region)
        self.assertIn("- 1 microwave basmati rice pouch", region)
        self.assertIn("- 170 g chicken breast, cooked", region)
        self.assertIn("- **light** — half the rice pouch · −105 kcal · −22 g C", region)
        self.assertNotIn("**Source**", region)

    def test_missing_region_is_inserted_after_the_block(self):
        card = valid_card()
        start, stop = recipes.find_region(card)
        bare = card_from_text(card.slug, card.text[:start] + card.text[stop:])
        self.assertIsNone(recipes.find_region(bare))
        once = recipes.rendered_text(bare)
        self.assertTrue(once.startswith(card.text[:card.body_start] + recipes.render_card_region(card)))
        again = recipes.rendered_text(card_from_text(card.slug, once))
        self.assertEqual(again, once)

    def test_region_runs_from_marker_to_marker(self):
        card = valid_card()
        region = recipes.current_region(card)
        self.assertTrue(region.startswith("<!-- coach:begin card chicken-rice-bowl -->"))
        self.assertTrue(region.endswith("<!-- coach:end card chicken-rice-bowl -->"))
        self.assertEqual(card.text[recipes.find_region(card)[1]], "\n")

    def test_second_region_is_an_error(self):
        card = valid_card()
        text = card.text + "\n" + recipes.render_card_region(card) + "\n"
        with self.assertRaises(recipes.ValidationError):
            recipes.find_region(card_from_text(card.slug, text))

    def test_mismatched_region_marker_is_an_error(self):
        card = valid_card()
        text = card.text.replace("coach:end card chicken-rice-bowl", "coach:end card other")
        with self.assertRaises(recipes.ValidationError):
            recipes.find_region(card_from_text(card.slug, text))

    def test_index_sections_notes_and_benched_last(self):
        bank = recipes.load_bank(VALID)
        benched = copy.deepcopy(bank.get("chicken-rice-bowl"))
        benched.slug = "aaa-benched"
        benched.data["title"] = "Aardvark bowl"
        benched.data["status"] = "benched"
        bank.cards.append(benched)
        config = config_from(MINIMAL_CONFIG + '[nutrition.bank.slot_notes]\nlunch = "office days need it portable"\n')
        text = recipes.render_index(bank, config)
        self.assertTrue(text.startswith("<!-- generated by coach from nutrition/menu/;"))
        headings = [line for line in text.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["## Breakfasts", "## Lunches", "## Dinners", "## Snacks"])
        lunch = text.split("## Lunches")[1].split("## Dinners")[0]
        self.assertIn("office days need it portable", lunch)
        self.assertLess(lunch.index("chicken-rice-bowl.md"), lunch.index("aaa-benched.md"))

    def test_fixture_index_is_fresh(self):
        text = (MENU / "index.md").read_text(encoding="utf-8")
        self.assertEqual(recipes.render_index(recipes.load_bank(VALID), config_from()), text)


class IngredientParseTest(unittest.TestCase):
    def test_lines(self):
        cases = {
            "170 g pre-cooked chicken breast": (170, "g", "pre-cooked chicken breast"),
            "1 pouch (250 g) microwave basmati rice": (1, "each", "microwave basmati rice pouch"),
            "6 cherry tomatoes": (6, "each", "cherry tomatoes"),
            "1 tsp (7 g) honey": (1, "tsp", "honey"),
            "- 600g boneless chicken thighs": (600, "g", "boneless chicken thighs"),
            "1 ½ tsp dried oregano": (1.5, "tsp", "dried oregano"),
            "1/2 tsp ground allspice": (0.5, "tsp", "ground allspice"),
            "½ lemon": (0.5, "each", "lemon"),
            "1.5 kg potatoes": (1500, "g", "potatoes"),
            "2 Tbsp. Olive Oil": (2, "tbsp", "olive oil"),
            "4 garlic cloves": (4, "each", "garlic cloves"),
            "3 garlic cloves, crushed": (3, "each", "garlic cloves"),
            "1 onion, thinly sliced": (1, "each", "onion"),
            "100 g chicken breast, cooked": (100, "g", "chicken breast, cooked"),
            "100 g chicken breast, raw, diced": (100, "g", "chicken breast, raw"),
            "2 red peppers, deseeded": (2, "each", "red peppers"),
            "2 yellow peppers": (2, "each", "yellow peppers"),
            "2 carrots, peeled and chopped": (2, "each", "carrots"),
            "1 chilli, deseeded and finely chopped": (1, "each", "chilli"),
            "1 red onion, peeled, halved and thinly sliced": (1, "each", "red onion"),
            "100 g chicken breast, cooked and sliced": (100, "g", "chicken breast, cooked and sliced"),
            "1,000 g flour": (1000, "g", "flour"),
            "1,250g beef mince": (1250, "g", "beef mince"),
            "12,5 g butter": (12.5, "g", "butter"),
        }
        for line, (qty, unit, item) in cases.items():
            with self.subTest(line=line):
                self.assertEqual(recipes.parse_ingredient(line), {"qty": qty, "unit": unit, "item": item})

    def test_unreadable_lines(self):
        for line in ("Salt and pepper, to taste", "1-2 tbsp honey", "2 to 3 eggs", "a handful of spinach", "0 g x",
                     "2 x 400g tins chopped tomatoes", "2x400g tins chopped tomatoes", "3 × 25 g sachets oats", "2 red and 2 yellow peppers",
                     "2 red & 2 yellow peppers", "2 red peppers or 3 green peppers",
                     "2 red peppers, 2 yellow peppers", "2 tbsp oil plus 1 tbsp butter"):
            with self.subTest(line=line):
                self.assertIsNone(recipes.parse_ingredient(line))

    def test_energy(self):
        cases = {"1883 kJ / 450 kcal": 450, "1,883kJ (450kcal)": 450, "450 kcal": 450, "450 Calories": 450,
                 "2,100 kcal": 2100, "450": 450, 450: 450}
        for value, kcal in cases.items():
            with self.subTest(value=value):
                self.assertEqual(recipes._energy_kcal(value), kcal)
        self.assertAlmostEqual(recipes._energy_kcal("1883 kJ"), 1883 / recipes.KJ_PER_KCAL)

    def test_aisle_guesses(self):
        cases = {"chicken stock": "tins-jars-dry", "frozen peas": "frozen", "0% greek yoghurt": "dairy-eggs",
                 "cherry tomatoes": "produce", "tomato paste": "tins-jars-dry", "white tortilla wraps": "bakery",
                 "peanut butter": "tins-jars-dry", "egg noodles": "tins-jars-dry", "egg noodle": "tins-jars-dry",
                 "butter beans": "tins-jars-dry", "coconut milk": "tins-jars-dry", "ground beef": "meat-fish",
                 "ground ginger": "tins-jars-dry"}
        for item, aisle in cases.items():
            with self.subTest(item=item):
                self.assertEqual(recipes.guess_aisle(item), (aisle, True))
        self.assertEqual(recipes.guess_aisle("zaatar"), (recipes.DEFAULT_AISLE_GUESS, False))


class ImportTest(RoundTripMixin, unittest.TestCase):
    def page(self, name):
        return (PAGES / name).read_text(encoding="utf-8")

    def test_graph_page(self):
        page = self.page("jsonld-graph.html")
        draft, flags = recipes.import_jsonld(page, "https://recipes.example.com/lemon-chicken-traybake")
        self.assertEqual(draft["title"], "Lemon chicken & potato traybake")
        self.assertEqual(draft["servings"], 4)
        self.assertEqual(draft["per_serving"], {"kcal": 450, "protein_g": 38, "carbs_g": 40, "fat_g": 15})
        self.assertEqual(draft["nutrition"], "published")
        self.assertEqual(draft["slots"], ["dinner"])
        self.assertEqual(draft["time_min"], 15)
        self.assertIn("active_time_uncertain", [f["code"] for f in flags])
        recipe = recipes.extract_recipe(page)
        lines = recipe["recipeIngredient"]
        unparsed = next(f for f in flags if f["code"] == "unparsed_ingredients")["lines"]
        self.assertEqual(len(draft["ingredients"]) + len(unparsed), len(lines))
        self.assertEqual(unparsed, ["Salt and pepper, to taste", "1-2 tbsp honey"])
        self.assertNotIn("macro_sum", [f["code"] for f in flags])
        self.assert_round_trip(draft)
        self.assertIn("2. Toss the potatoes", recipes.method_prose(recipe))

    def test_plain_meal_kit_page(self):
        draft, flags = recipes.import_jsonld(self.page("jsonld-plain.html"), "https://www.gousto.co.uk/cookbook/x")
        codes = [f["code"] for f in flags]
        self.assertIn("per_serving_doubt", codes)
        self.assertEqual(draft["tags"], ["meal-kit", "gousto"])
        self.assertEqual(draft["per_serving"], {"kcal": 580, "protein_g": 28.6, "carbs_g": 63, "fat_g": 23.9})
        self.assertEqual(len(draft["ingredients"]), 6)
        self.assert_round_trip(draft)

    def test_missing_nutrition_and_failed_macro_sum(self):
        page = '<script type="application/ld+json">{"@type": "Recipe", "name": "X", "recipeYield": 2, %s}</script>'
        draft, flags = recipes.import_jsonld(page % '"recipeIngredient": ["100 g rice"]')
        self.assertNotIn("per_serving", draft)
        self.assertEqual(draft["nutrition"], "estimated")
        self.assertIn("missing_nutrition", [f["code"] for f in flags])
        self.assert_round_trip(draft)
        nutrition = '"nutrition": {"calories": "3350 kJ", "proteinContent": "10 g", "carbohydrateContent": "10 g", ' \
                    '"fatContent": "10 g"}'
        draft, flags = recipes.import_jsonld(page % nutrition)
        self.assertEqual(draft["per_serving"]["kcal"], 801)
        by_code = {f["code"]: f for f in flags}
        self.assertEqual(by_code["macro_sum"]["severity"], "fail")
        self.assert_round_trip(draft)

    def test_review_fixture_preserves_quantities_identity_and_provenance(self):
        draft, flags = recipes.import_jsonld(self.page("jsonld-review.html"))
        by_item = {item["item"]: item for item in draft["ingredients"]}
        self.assertEqual(len(by_item), len(draft["ingredients"]))
        self.assertEqual(by_item["garlic cloves"]["qty"], 3)
        self.assertEqual(by_item["onion"]["qty"], 1)
        self.assertEqual(by_item["olive oil"]["qty"], 6)
        self.assertEqual(by_item["olive oil"]["unit"], "tbsp")
        self.assertEqual(by_item["egg noodles"]["aisle"], "tins-jars-dry")
        self.assertIn("chicken breast, cooked", by_item)
        self.assertIn("chicken breast, raw", by_item)
        by_code = {flag["code"]: flag for flag in flags}
        self.assertEqual(by_code["unparsed_ingredients"]["lines"], ["2 red and 2 yellow peppers"])
        self.assertEqual(by_code["aisle_guessed"]["items"], ["zaatar"])
        self.assertEqual(draft["source"], "https://recipes.example.com/vegetable-noodles")
        self.assertEqual(draft["time_min"], 15)
        self.assertEqual(by_code["active_time_uncertain"]["source_times"],
                         {"prepTime": "PT15M", "cookTime": "PT30M", "totalTime": "PT45M"})
        self.assert_round_trip(draft)

    def test_duplicate_ingredients_only_sum_compatible_units(self):
        recipe = recipes.extract_recipe(self.page("jsonld-review.html"))
        recipe["recipeIngredient"] = ["4 tbsp olive oil", "2 tbsp olive oil", "100 ml olive oil",
                                      "1 kg rice", "500 g rice"]
        page = '<script type="application/ld+json">' + json.dumps(recipe) + '</script>'
        draft, flags = recipes.import_jsonld(page)
        self.assertEqual([(i["item"], i["qty"], i["unit"]) for i in draft["ingredients"]],
                         [("olive oil", 6, "tbsp"), ("olive oil", 100, "ml"), ("rice", 1500, "g")])
        flag = next(f for f in flags if f["code"] == "incompatible_ingredient_units")
        self.assertEqual(flag["items"], ["olive oil"])
        self.assertEqual(flag["lines"], recipe["recipeIngredient"][:3])
        self.assertTrue(any(r.status == "fail" for r in recipes.validate_card(card_with(draft), config_from())))

    def test_prep_clauses_joined_by_and_merge_into_one_shopping_item(self):
        page = '<script type="application/ld+json">' + json.dumps({
            "@type": "Recipe", "recipeIngredient": ["1 chilli, deseeded and finely chopped", "1 chilli, sliced"],
        }) + '</script>'
        draft, flags = recipes.import_jsonld(page)
        self.assertEqual([(i["item"], i["qty"], i["unit"]) for i in draft["ingredients"]], [("chilli", 2, "each")])
        self.assertNotIn("incompatible_ingredient_units", [f["code"] for f in flags])

    def test_repeated_unmatched_item_is_listed_once(self):
        page = '<script type="application/ld+json">' + json.dumps({
            "@type": "Recipe", "recipeIngredient": ["1 tsp zaatar", "2 tsp zaatar"],
        }) + '</script>'
        draft, flags = recipes.import_jsonld(page)
        self.assertEqual([(i["item"], i["qty"]) for i in draft["ingredients"]], [("zaatar", 3)])
        self.assertEqual(next(f for f in flags if f["code"] == "aisle_guessed")["items"], ["zaatar"])

    def test_active_time_is_always_reviewed_even_with_only_prep_time(self):
        for source_times, proposed in (({"prepTime": "PT15M"}, 15), ({"totalTime": "PT45M"}, 0),
                                       ({"cookTime": "PT30M"}, 0), ({}, 0),
                                       ({"prepTime": None, "totalTime": ""}, 0)):
            with self.subTest(source_times=source_times):
                recipe = {"@type": "Recipe", **source_times}
                page = '<script type="application/ld+json">' + json.dumps(recipe) + '</script>'
                draft, flags = recipes.import_jsonld(page)
                self.assertEqual(draft["time_min"], proposed)
                usable = {key: value for key, value in source_times.items() if value}
                code = "active_time_uncertain" if usable else "time_missing"
                self.assertEqual([f["code"] for f in flags if "time" in f["code"]], [code])
                flag = next(f for f in flags if f["code"] == code)
                self.assertIn("active", flag["message"])
                if usable:
                    self.assertEqual(flag["source_times"], usable)

    def test_recipe_sources_explains_every_import_flag(self):
        codes = set(re.findall(r'"code": "([a-z_]+)"', (REPO_ROOT / "coach" / "recipes.py").read_text()))
        guide = (REPO_ROOT / "reference" / "recipe-sources.md").read_text()
        self.assertIn("active_time_uncertain", codes)
        for code in sorted(codes):
            with self.subTest(code=code):
                self.assertIn(f"`{code}`", guide)

    def test_no_recipe(self):
        with self.assertRaises(recipes.ValidationError):
            recipes.import_jsonld(self.page("no-recipe.html"))


class ConvertTest(RoundTripMixin, unittest.TestCase):
    def test_documented_chicken_card(self):
        text = (YAML_MENU / "chicken-rice-bowl.md").read_text(encoding="utf-8")
        draft, row = recipes.convert_yaml_card(text)
        self.assertEqual(row["slug"], "chicken-rice-bowl")
        self.assertEqual(row["ingredients"], 4)
        self.assertEqual(row["unparsed"], [])
        self.assertEqual(row["variations"], 2)
        self.assertEqual(row["variations_to_fill"], ["light", "+egg"])
        deltas = {v["name"]: v["delta"] for v in draft["variations"]}
        self.assertEqual(deltas["light"], {"kcal": -105, "protein_g": 0, "carbs_g": -22, "fat_g": 0})
        self.assertEqual(deltas["+egg"], {"kcal": 70, "protein_g": 6, "carbs_g": 0, "fat_g": 5})
        self.assertEqual(draft["per_serving"], {"kcal": 610, "protein_g": 50, "carbs_g": 55, "fat_g": 18})
        self.assertNotIn("source", draft)
        self.assert_round_trip(draft)

    def test_every_fixture_card_round_trips(self):
        for path in sorted(YAML_MENU.glob("*.md")):
            if path.name != "index.md":
                with self.subTest(card=path.stem):
                    draft, _ = recipes.convert_yaml_card(path.read_text(encoding="utf-8"))
                    self.assert_round_trip(draft)

    def test_eat_out_card(self):
        draft, row = recipes.convert_yaml_card((YAML_MENU / "pub-burger.md").read_text(encoding="utf-8"))
        self.assertNotIn("ingredients", draft)
        self.assertEqual(row["variations_to_fill"], [])
        self.assertIn("## What to order", recipes.legacy_prose((YAML_MENU / "pub-burger.md").read_text()))

    def test_prose_keeps_method_and_drops_generated_sections(self):
        text = (YAML_MENU / "chicken-rice-bowl.md").read_text(encoding="utf-8")
        prose = recipes.legacy_prose(text)
        self.assertTrue(prose.startswith("## Method\n1. Heat the rice pouch (90 sec).\n2. Bowl everything; season.\n"))
        for gone in ("## Ingredients", "## Variations", "# Chicken", "**Per serving**"):
            self.assertNotIn(gone, prose)

    def test_variation_without_kcal_is_computed_and_noted(self):
        text = "---\nname: x\nslot: [snack]\nkcal: 100\nprotein: 5\ncarbs: 10\nfat: 4\n---\n\n# X\n\n" \
               "## Variations\n- **big** — double it · +10 g carbs\n"
        draft, row = recipes.convert_yaml_card(text)
        self.assertEqual(draft["variations"][0]["delta"]["kcal"], 40)
        self.assertTrue(any("big" in note for note in row["notes"]))

    def test_block_lists_and_unread_front_matter(self):
        text = ("---\nname: x\nslot:\n  - snack\nkcal: 100\nprotein: 5\ncarbs: 10\nfat: 4\ntags:\n  - portable\n"
                "  - quick\nmacros:\n  fibre: 3\nrating: 5\n---\n\n# X\n")
        draft, row = recipes.convert_yaml_card(text)
        self.assertEqual(draft["slots"], ["snack"])
        self.assertEqual(draft["tags"], ["portable", "quick"])
        self.assertIn("front matter line not read: fibre: 3", row["notes"])
        self.assertIn("front matter key macros is not carried over", row["notes"])
        self.assertIn("front matter key rating is not carried over", row["notes"])
        self.assertIn("rating", recipes.review_table([row]))

    def test_legacy_slot_notes(self):
        index = (YAML_MENU / "index.md").read_text(encoding="utf-8")
        notes, unplaced = recipes.legacy_slot_notes(index, list(recipes.DEFAULT_SLOTS))
        self.assertEqual(notes, {"dinner": "Family cooks most nights; top up protein on light nights."})
        self.assertEqual(unplaced, [])
        odd = "# Index\nOld intro.\n\n## Treats\nWeekends only.\n\n## Breakfast\nMust be fast.\n\n| a |\n"
        notes, unplaced = recipes.legacy_slot_notes(odd, list(recipes.DEFAULT_SLOTS))
        self.assertEqual(notes, {"breakfast": "Must be fast."})
        self.assertEqual(unplaced, [{"heading": None, "note": "Old intro."},
                                    {"heading": "Treats", "note": "Weekends only."}])
        rendered = (MENU / "index.md").read_text(encoding="utf-8")
        self.assertEqual(recipes.legacy_slot_notes(rendered, ["lunch"]), ({}, []))

    def test_needs_front_matter(self):
        with self.assertRaises(recipes.ValidationError):
            recipes.convert_yaml_card("# no front matter\n")


class ReferenceDocTest(unittest.TestCase):
    DOC = REPO_ROOT / "reference" / "recipe-cards.md"

    def test_example_card_is_valid_and_fresh(self):
        text = self.DOC.read_text(encoding="utf-8")
        example = re.search(r"```markdown\n(<!-- coach:card\n.*?)```", text, re.S).group(1)
        card = card_from_text("chicken-rice-bowl", example)
        self.assertEqual(recipes.validate_card(card, config_from()), [])
        self.assertEqual(recipes.rendered_text(card), example)

    def test_no_hand_kept_mirrors(self):
        texts = {"recipe-cards.md": self.DOC.read_text(encoding="utf-8"), "recipes skill": skill_text("recipes")}
        for name, text in texts.items():
            text = text.lower()
            with self.subTest(path=name):
                self.assertNotIn("same-write", text)
                self.assertNotIn("stats block", text)


if __name__ == "__main__":
    unittest.main()
