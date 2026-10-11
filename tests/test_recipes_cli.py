import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import datablock
from tests.support import FIXTURES, INSTANCES, VALID, run_cli, run_module

YAML_CARDS = INSTANCES / "yaml-cards"
STALE = INSTANCES / "recipes-stale"
NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


class InstanceCopy:
    def __init__(self, source):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(source, self.root)

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


def menu(root):
    return Path(root) / "nutrition" / "menu"


def edit(path, old, new):
    text = datablock.read_text(path)
    assert old in text, (path, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


class CliMixin:
    def run_ok(self, root, *argv, env=None):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope

    def run_code(self, code_wanted, root, *argv, env=None):
        code, envelope, stderr = run_cli(["--root", str(root), *argv], env=env)
        self.assertEqual(code, code_wanted, (envelope, stderr))
        return envelope


class ValidateCommandTest(CliMixin, unittest.TestCase):
    def test_valid_instance_passes_as_a_subprocess(self):
        code, envelope, stderr = run_module(["--root", "tests/fixtures/instances/valid", "recipes", "validate"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(envelope["data"]["summary"], {"pass": 3, "warn": 0, "fail": 0})
        self.assertEqual([c["slug"] for c in envelope["data"]["cards"]],
                         ["chicken-rice-bowl", "overnight-oats", "whey-shake"])

    def test_macro_sum_fail_and_warn(self):
        with InstanceCopy(VALID) as root:
            card = menu(root) / "chicken-rice-bowl.md"
            edit(card, "kcal = 610", "kcal = 800")
            envelope = self.run_code(1, root, "recipes", "validate")
            message = envelope["error"]["message"]
            for fragment in ("chicken-rice-bowl", "800", "582"):
                self.assertIn(fragment, message)
            edit(card, "kcal = 800", "kcal = 700")
            envelope = self.run_ok(root, "recipes", "validate", "chicken-rice-bowl")
            self.assertEqual(envelope["data"]["cards"][0]["status"], "warn")
            self.assertTrue(any("700" in w for w in envelope["warnings"]))

    def test_lunch_density_warns_and_config_switches_it_off(self):
        with InstanceCopy(VALID) as root:
            card = menu(root) / "chicken-rice-bowl.md"
            edit(card, "kcal = 610\nprotein_g = 50\ncarbs_g = 55\nfat_g = 18",
                 "kcal = 500\nprotein_g = 20\ncarbs_g = 60\nfat_g = 20")
            envelope = self.run_ok(root, "recipes", "validate", "chicken-rice-bowl")
            self.assertEqual(envelope["data"]["cards"][0]["status"], "warn")
            self.assertIn("protein per 100 kcal", envelope["warnings"][0])
            with open(root / "config.toml", "a", encoding="utf-8") as handle:
                handle.write("\n[nutrition.bank]\nmin_protein_per_100kcal = {lunch = 0.0}\n")
            envelope = self.run_ok(root, "recipes", "validate", "chicken-rice-bowl")
            self.assertEqual(envelope["data"]["cards"][0]["status"], "pass")

    def test_comment_closer_in_the_block_fails_naming_the_file(self):
        with InstanceCopy(VALID) as root:
            edit(menu(root) / "whey-shake.md", 'title = "Whey shake"', 'title = "Whey --> shake"')
            envelope = self.run_code(1, root, "recipes", "validate")
            self.assertIn("whey-shake.md", envelope["error"]["message"])
            self.assertIn("-->", envelope["error"]["message"])
            envelope = self.run_code(1, root, "check", "--only", "recipe_cards")
            self.assertIn("whey-shake.md", envelope["data"]["results"][0]["message"])

    def test_unknown_slug(self):
        self.run_code(1, VALID, "recipes", "validate", "no-such-card")
        self.run_code(1, VALID, "recipes", "show", "no-such-card")

    def test_old_yaml_cards_are_named(self):
        envelope = self.run_code(1, YAML_CARDS, "recipes", "validate")
        self.assertIn("recipes convert", envelope["error"]["message"])


class ListShowTest(CliMixin, unittest.TestCase):
    def test_list_filters(self):
        cards = self.run_ok(VALID, "recipes", "list")["data"]["cards"]
        self.assertEqual(len(cards), 3)
        cards = self.run_ok(VALID, "recipes", "list", "--slot", "lunch")["data"]["cards"]
        self.assertEqual([c["slug"] for c in cards], ["chicken-rice-bowl"])
        self.assertEqual(self.run_ok(VALID, "recipes", "list", "--status", "benched")["data"]["cards"], [])

    def test_show(self):
        data = self.run_ok(VALID, "recipes", "show", "chicken-rice-bowl")["data"]
        self.assertEqual(data["card"]["per_serving"]["kcal"], 610)
        self.assertTrue(data["region_fresh"])


class RenderCommandTest(CliMixin, unittest.TestCase):
    def test_render_rewrites_only_the_stale_region(self):
        with InstanceCopy(VALID) as root:
            card = menu(root) / "chicken-rice-bowl.md"
            original = datablock.read_text(card)
            edit(card, "| **Slot** | lunch |", "| **Slot** | brunch |")
            edit(menu(root) / "index.md", "## Dinners", "## Suppers")
            before = snapshot(root)

            data = self.run_ok(root, "recipes", "render", "--dry-run")["data"]
            self.assertEqual(snapshot(root), before)
            self.assertTrue(data["dry_run"])
            self.assertEqual({c["slug"] for c in data["cards"] if c["changed"]}, {"chicken-rice-bowl"})
            self.assertTrue(data["index"]["changed"])

            self.run_ok(root, "recipes", "render")
            after = datablock.read_text(card)
            self.assertEqual(after, original)
            block_end = original.index("-->\n") + 4
            self.assertEqual(after[:block_end], original[:block_end])
            self.assertEqual(after[after.index("## Method"):], original[original.index("## Method"):])
            changed = {path for path, data in snapshot(root).items() if before[path] != data}
            self.assertEqual(changed, {"nutrition/menu/chicken-rice-bowl.md", "nutrition/menu/index.md"})

            once = snapshot(root)
            data = self.run_ok(root, "recipes", "render")["data"]
            self.assertEqual(snapshot(root), once)
            self.assertFalse(any(c["changed"] for c in data["cards"]))

    def test_render_adds_a_missing_region(self):
        with InstanceCopy(VALID) as root:
            card = menu(root) / "whey-shake.md"
            text = datablock.read_text(card)
            card.write_text(text[:text.index("<!-- coach:begin")], encoding="utf-8")
            self.run_code(1, root, "check", "--only", "recipe_render_fresh")
            self.run_ok(root, "recipes", "render", "whey-shake")
            self.assertEqual(datablock.read_text(card), text)

    def test_render_refuses_a_broken_bank(self):
        with InstanceCopy(VALID) as root:
            edit(menu(root) / "whey-shake.md", 'prep = "assemble"', 'prep = "blend"')
            before = snapshot(root)
            self.run_code(1, root, "recipes", "render")
            self.assertEqual(snapshot(root), before)


class ChecksTest(CliMixin, unittest.TestCase):
    IDS = "recipe_cards,recipe_render_fresh,recipe_index_fresh"

    def test_valid_instance_passes(self):
        results = self.run_ok(VALID, "check", "--only", self.IDS)["data"]["results"]
        self.assertEqual({r["id"]: r["status"] for r in results},
                         {"recipe_cards": "pass", "recipe_render_fresh": "pass", "recipe_index_fresh": "pass"})

    def test_stale_instance_fails_all_three(self):
        envelope = self.run_code(1, STALE, "check", "--only", self.IDS)
        failed = {r["id"] for r in envelope["data"]["results"] if r["status"] == "fail"}
        self.assertEqual(failed, {"recipe_cards", "recipe_render_fresh", "recipe_index_fresh"})

    def test_one_character_in_a_region(self):
        with InstanceCopy(VALID) as root:
            edit(menu(root) / "overnight-oats.md", "- 60 g rolled oats", "- 61 g rolled oats")
            envelope = self.run_code(1, root, "check", "--only", "recipe_render_fresh")
            self.assertIn("overnight-oats", envelope["error"]["message"] + json.dumps(envelope["data"]))
            self.run_ok(root, "check", "--only", "recipe_cards,recipe_index_fresh")

    def test_hand_edited_index(self):
        with InstanceCopy(VALID) as root:
            edit(menu(root) / "index.md", "| 440 |", "| 450 |")
            envelope = self.run_code(1, root, "check", "--only", "recipe_index_fresh")
            self.assertEqual(envelope["data"]["results"][0]["path"], "nutrition/menu/index.md")

    def test_no_bank_passes(self):
        with InstanceCopy(VALID) as root:
            shutil.rmtree(menu(root))
            self.run_ok(root, "check", "--only", self.IDS)


class ImportDraftTest(CliMixin, unittest.TestCase):
    def test_import_writes_nothing_and_drafts(self):
        with InstanceCopy(VALID) as root:
            page = FIXTURES / "recipes" / "jsonld-graph.html"
            before = snapshot(root)
            data = self.run_ok(root, "recipes", "import", "--html", str(page), "--url",
                               "https://recipes.example.com/lemon-chicken-traybake")["data"]
            self.assertEqual(snapshot(root), before)
            self.assertEqual(data["slug"], "lemon-chicken-potato-traybake")
            self.assertIn('title = "Lemon chicken & potato traybake"', data["toml"])
            self.assertTrue(data["prose"].startswith("## Method\n1. Heat the oven"))

            draft_file = root / "draft.json"
            draft_file.write_text(json.dumps(data), encoding="utf-8")
            drafted = self.run_ok(root, "recipes", "draft", "--input", str(draft_file))["data"]
            self.assertEqual(drafted["path"], "nutrition/menu/lemon-chicken-potato-traybake.md")
            self.assertFalse(drafted["exists"])
            self.assertTrue(drafted["text"].startswith("<!-- coach:card\n"))
            self.assertIn("<!-- coach:begin card lemon-chicken-potato-traybake -->", drafted["text"])
            self.assertIn("## Method\n1. Heat the oven", drafted["text"])
            draft_file.unlink()
            self.assertEqual(snapshot(root), before)

            (menu(root) / f"{data['slug']}.md").write_text(drafted["text"], encoding="utf-8")
            self.run_ok(root, "recipes", "render")
            self.run_ok(root, "check", "--only", "recipe_cards,recipe_render_fresh,recipe_index_fresh")

    def test_draft_that_fails_validation(self):
        with InstanceCopy(VALID) as root:
            draft_file = root / "draft.json"
            card = json.loads(json.dumps(self.run_ok(root, "recipes", "show", "whey-shake")["data"]["card"]))
            card["per_serving"]["kcal"] = 400
            draft_file.write_text(json.dumps({"slug": "big-shake", "card": card}), encoding="utf-8")
            envelope = self.run_code(1, root, "recipes", "draft", "--input", str(draft_file))
            self.assertIn("big-shake", envelope["error"]["message"])
            draft_file.write_text(json.dumps({"slug": "Bad Slug", "card": card}), encoding="utf-8")
            self.run_code(1, root, "recipes", "draft", "--input", str(draft_file))

    def test_import_page_without_a_recipe(self):
        envelope = self.run_code(1, VALID, "recipes", "import", "--html", str(FIXTURES / "recipes" / "no-recipe.html"))
        self.assertIn("no-recipe.html", envelope["error"]["message"])


def reviewed(parse_data):
    """Fill in the variation changes the review table asked for."""
    cards = {entry["slug"]: entry["card"] for entry in parse_data["cards"]}
    for variation in cards["chicken-rice-bowl"]["variations"]:
        if variation["name"] == "light":
            variation["changes"] = [{"item": "microwave basmati rice pouch", "qty": -0.5, "unit": "each"}]
        else:
            variation["changes"] = [{"item": "eggs", "qty": 1, "unit": "each", "aisle": "dairy-eggs"}]
    for variation in cards["yoghurt-honey-nuts"].get("variations", []):
        variation["changes"] = []
    return {"cards": [{"slug": slug, "card": card} for slug, card in cards.items()]}


class ConvertCommandTest(CliMixin, unittest.TestCase):
    def test_parse_writes_nothing_and_reviews_every_card(self):
        before = snapshot(YAML_CARDS)
        data = self.run_ok(YAML_CARDS, "recipes", "convert", "--parse")["data"]
        self.assertEqual(snapshot(YAML_CARDS), before)
        rows = {row["slug"]: row for row in data["review"]}
        self.assertEqual(set(rows), {"chicken-rice-bowl", "yoghurt-honey-nuts", "pub-burger"})
        chicken = rows["chicken-rice-bowl"]
        self.assertEqual((chicken["ingredients"], chicken["variations"]), (4, 2))
        self.assertEqual(chicken["variations_to_fill"], ["light", "+egg"])
        self.assertIn("| chicken-rice-bowl |", data["table"])
        self.assertEqual(len(data["table"].strip().splitlines()), 2 + 3)

    def test_apply_then_validate(self):
        with InstanceCopy(YAML_CARDS) as root:
            originals = {p.name: datablock.read_text(p) for p in menu(root).glob("*.md")}
            data = self.run_ok(root, "recipes", "convert", "--parse")["data"]
            input_file = root / "reviewed.json"
            input_file.write_text(json.dumps(reviewed(data)), encoding="utf-8")

            before = snapshot(root)
            dry = self.run_ok(root, "recipes", "convert", "--apply", "--input", str(input_file), "--dry-run",
                              env=NOW)["data"]
            self.assertEqual(snapshot(root), before)
            self.assertEqual(len(dry["written"]), 3)

            out = self.run_ok(root, "recipes", "convert", "--apply", "--input", str(input_file), env=NOW)["data"]
            self.assertEqual(out["backup_dir"], ".coach/backups/20261011T180000Z")
            self.assertTrue(out["index"]["changed"])
            backup = root / out["backup_dir"] / "nutrition" / "menu"
            for name, text in originals.items():
                self.assertEqual(datablock.read_text(backup / name), text)

            self.run_ok(root, "recipes", "validate")
            self.run_ok(root, "check", "--only", "recipe_cards,recipe_render_fresh,recipe_index_fresh")

            chicken = datablock.read_text(menu(root) / "chicken-rice-bowl.md")
            method = originals["chicken-rice-bowl.md"].split("## Method")[1].split("## Variations")[0].rstrip("\n")
            self.assertIn("## Method" + method + "\n", chicken)
            self.assertIn('changes = [{item = "microwave basmati rice pouch", qty = -0.5, unit = "each"}]', chicken)
            burger = datablock.read_text(menu(root) / "pub-burger.md")
            self.assertIn("## What to order\n- Single beef burger", burger)

            again = self.run_code(1, root, "recipes", "convert", "--apply", "--input", str(input_file), env=NOW)
            self.assertIn("not an old YAML card", again["error"]["message"])

    def test_apply_refuses_a_failing_card_and_writes_nothing(self):
        with InstanceCopy(YAML_CARDS) as root:
            data = reviewed(self.run_ok(root, "recipes", "convert", "--parse")["data"])
            data["cards"][0]["card"]["per_serving"]["kcal"] = 2000
            input_file = root / "reviewed.json"
            input_file.write_text(json.dumps(data), encoding="utf-8")
            before = snapshot(root)
            self.run_code(1, root, "recipes", "convert", "--apply", "--input", str(input_file), env=NOW)
            self.assertEqual(snapshot(root), before)

    def test_partial_apply_leaves_the_index(self):
        with InstanceCopy(YAML_CARDS) as root:
            data = reviewed(self.run_ok(root, "recipes", "convert", "--parse")["data"])
            data["cards"] = [c for c in data["cards"] if c["slug"] == "chicken-rice-bowl"]
            input_file = root / "reviewed.json"
            input_file.write_text(json.dumps(data), encoding="utf-8")
            index = datablock.read_text(menu(root) / "index.md")
            out = self.run_ok(root, "recipes", "convert", "--apply", "--input", str(input_file), env=NOW)["data"]
            self.assertEqual(sorted(out["still_old_format"]), ["pub-burger", "yoghurt-honey-nuts"])
            self.assertEqual(datablock.read_text(menu(root) / "index.md"), index)

    def test_usage(self):
        self.run_code(2, YAML_CARDS, "recipes", "convert")
        self.run_code(2, YAML_CARDS, "recipes", "convert", "--parse", "--apply")
        self.run_code(2, YAML_CARDS, "recipes", "convert", "--apply")


if __name__ == "__main__":
    unittest.main()
