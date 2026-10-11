import tempfile
import unittest
from datetime import date
from pathlib import Path

from coach import datablock
from coach.errors import ValidationError

BLOCK = '<!-- coach:note\nid = "x"\nwritten = 2026-10-01\n-->\n'


def write(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    with handle:
        handle.write(text)
    return Path(handle.name)


class ReadTest(unittest.TestCase):
    def read(self, text, kind="note"):
        path = write(text)
        self.addCleanup(path.unlink)
        return path, datablock.read(path, kind)

    def assert_error(self, text, fragment, kind="note"):
        path = write(text)
        self.addCleanup(path.unlink)
        with self.assertRaises(ValidationError) as caught:
            datablock.read(path, kind)
        self.assertIn(str(path), caught.exception.message)
        self.assertIn(fragment, caught.exception.message)

    def test_returns_data_and_the_rest_verbatim(self):
        rest = "<!-- coach:begin research x -->\n<!-- coach:end research x -->\n\n## Answer\nText -->\n"
        _, (data, found_rest) = self.read(BLOCK + rest)
        self.assertEqual(data, {"id": "x", "written": date(2026, 10, 1)})
        self.assertEqual(found_rest, rest)

    def test_empty_rest(self):
        _, (_, rest) = self.read(BLOCK)
        self.assertEqual(rest, "")

    def test_card_kind(self):
        _, (data, _) = self.read('<!-- coach:card\nslug = "oats"\n-->\n', kind="card")
        self.assertEqual(data, {"slug": "oats"})

    def test_missing_opener(self):
        self.assert_error("# A note\n", "first line must be exactly '<!-- coach:note'")

    def test_opener_not_on_the_first_line(self):
        self.assert_error("\n" + BLOCK, "first line must be exactly")

    def test_wrong_kind(self):
        self.assert_error('<!-- coach:card\nid = "x"\n-->\n', "'<!-- coach:card'")

    def test_missing_closer(self):
        self.assert_error('<!-- coach:note\nid = "x"\n', "never closed")

    def test_closer_must_be_the_whole_line(self):
        self.assert_error('<!-- coach:note\nid = "x" -->\n', "never closed")

    def test_arrow_inside_the_block(self):
        self.assert_error('<!-- coach:note\nquestion = "a --> b"\n-->\n', "contains '-->'")

    def test_invalid_toml(self):
        self.assert_error("<!-- coach:note\nid = \n-->\n", "not valid TOML")

    def test_unknown_kind_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            datablock.read("nowhere.md", "recipe")


if __name__ == "__main__":
    unittest.main()
