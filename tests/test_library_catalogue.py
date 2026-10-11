"""The builtin exercise catalogue ships valid and unambiguous."""

import json
import unittest
from collections import Counter

from coach import jsonio, library, units
from coach.validate import check_schema, validate
from tests.support import REPO_ROOT

CATALOGUE_PATH = REPO_ROOT / "coach" / "catalogue" / "exercises.json"


def _catalogue():
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


class CatalogueTest(unittest.TestCase):
    def setUp(self):
        self.doc = _catalogue()
        self.entries = self.doc["exercises"]

    def test_every_entry_validates(self):
        self.assertEqual(validate(self.doc, jsonio.load_schema("exercise_catalogue")), [])

    def test_size_is_about_80_to_130(self):
        self.assertGreaterEqual(len(self.entries), 80)
        self.assertLessEqual(len(self.entries), 130)

    def test_ids_are_unique_and_never_custom(self):
        ids = [entry["id"] for entry in self.entries]
        self.assertEqual([i for i, n in Counter(ids).items() if n > 1], [])
        self.assertEqual([i for i in ids if i.startswith("custom_")], [])

    def test_every_substitute_exists_and_is_not_itself(self):
        ids = {entry["id"] for entry in self.entries}
        problems = [
            f"{entry['id']} -> {sub}"
            for entry in self.entries for sub in entry["substitutes"]
            if sub not in ids or sub == entry["id"]
        ]
        self.assertEqual(problems, [])

    def test_aliases_names_and_hevy_titles_are_unique_across_entries(self):
        owners = {}
        clashes = []
        for entry in self.entries:
            for text in [entry["name"], *entry["aliases"], *entry["hevy_titles"]]:
                key = library.match_key(text)
                owner = owners.setdefault(key, entry["id"])
                if owner != entry["id"]:
                    clashes.append(f"{text!r}: {owner} and {entry['id']}")
        self.assertEqual(clashes, [])

    def test_every_alias_is_unique_as_written(self):
        aliases = [alias.lower() for entry in self.entries for alias in entry["aliases"]]
        self.assertEqual([a for a, n in Counter(aliases).items() if n > 1], [])

    def test_every_default_load_mode_is_in_the_c5_enum(self):
        self.assertEqual([e["id"] for e in self.entries if e["load_mode_default"] not in units.LOAD_MODES], [])

    def test_unloaded_modes_carry_no_increment(self):
        wrong = [
            e["id"] for e in self.entries
            if (e["load_mode_default"] in units.LOADED_MODES) != (e["increment"] is not None)
        ]
        self.assertEqual(wrong, [])

    def test_contract_fixture_ids_are_present(self):
        modes = {entry["id"]: entry["load_mode_default"] for entry in self.entries}
        expected = {
            "bb_back_squat": "total",
            "db_bench_press": "per_hand_x2",
            "db_single_arm_row": "single_implement",
            "pull_up": "bodyweight",
        }
        for exercise_id, mode in expected.items():
            self.assertEqual(modes.get(exercise_id), mode, exercise_id)

    def test_primary_and_secondary_muscles_do_not_overlap(self):
        overlap = [e["id"] for e in self.entries if set(e["muscles"]["primary"]) & set(e["muscles"]["secondary"])]
        self.assertEqual(overlap, [])


class SchemaEnumTest(unittest.TestCase):
    def test_schemas_use_supported_keywords(self):
        for name in ("exercise_catalogue", "exercise_library"):
            with self.subTest(schema=name):
                check_schema(jsonio.load_schema(name))

    def test_schema_enums_match_the_module_constants(self):
        for name in ("exercise_catalogue", "exercise_library"):
            defs = jsonio.load_schema(name)["$defs"]
            with self.subTest(schema=name):
                self.assertEqual(tuple(defs["pattern"]["enum"]), library.PATTERNS)
                self.assertEqual(tuple(defs["muscle"]["enum"]), library.MUSCLES)
                self.assertEqual(tuple(defs["equipment"]["enum"]), library.EQUIPMENT)
                self.assertEqual(tuple(defs["load_mode"]["enum"]), units.LOAD_MODES)
        self.assertEqual(tuple(jsonio.load_schema("exercise_catalogue")["$defs"]["apparatus"]["enum"]),
                         library.APPARATUS)

    def test_muscles_are_hevys_with_shoulders_split(self):
        self.assertNotIn("shoulders", library.MUSCLES)
        for name in ("front_delts", "side_delts", "rear_delts", "quadriceps", "lats", "chest"):
            self.assertIn(name, library.MUSCLES)


if __name__ == "__main__":
    unittest.main()
