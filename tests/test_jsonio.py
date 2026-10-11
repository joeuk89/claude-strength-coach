import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from coach import jsonio
from coach.errors import ValidationError


def envelope(**overrides):
    doc = {"schema_version": 1, "ok": True, "command": "version", "data": {}, "warnings": []}
    doc.update(overrides)
    return doc


class JsonIoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_write_doc_format(self):
        path = self.dir / "sub" / "doc.json"
        jsonio.write_doc(path, {"schema_version": 1, "name": "Café"}, dry_run=False)
        self.assertEqual(path.read_text(encoding="utf-8"), '{\n  "schema_version": 1,\n  "name": "Café"\n}\n')
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_write_doc_dry_run_writes_nothing(self):
        path = self.dir / "doc.json"
        text = jsonio.write_doc(path, {"schema_version": 1}, dry_run=True)
        self.assertFalse(path.exists())
        self.assertEqual(text, '{\n  "schema_version": 1\n}\n')

    def test_read_doc_valid(self):
        path = self.write("env.json", json.dumps(envelope()))
        self.assertEqual(jsonio.read_doc(path, "envelope"), envelope())

    def test_read_doc_invalid_names_the_path(self):
        path = self.write("env.json", json.dumps(envelope(ok="yes")))
        with self.assertRaises(ValidationError) as caught:
            jsonio.read_doc(path, "envelope")
        self.assertIn("env.json", caught.exception.message)
        self.assertEqual(caught.exception.details[0]["path"], "$.ok")

    def test_read_doc_newer_version(self):
        path = self.write("env.json", json.dumps(envelope(schema_version=2)))
        with self.assertRaises(ValidationError) as caught:
            jsonio.read_doc(path, "envelope")
        self.assertIn("/framework-sync", caught.exception.message)

    def test_read_doc_older_version(self):
        path = self.write("env.json", json.dumps(envelope(schema_version=0)))
        with self.assertRaises(ValidationError) as caught:
            jsonio.read_doc(path, "envelope")
        self.assertIn("python3 -m coach migrate run", caught.exception.message)

    def test_read_doc_bad_json_and_missing_version(self):
        with self.assertRaises(ValidationError):
            jsonio.read_doc(self.write("a.json", "{not json"), "envelope")
        with self.assertRaises(ValidationError):
            jsonio.read_doc(self.write("b.json", "[]"), "envelope")
        with self.assertRaises(ValidationError):
            jsonio.read_doc(self.write("c.json", '{"ok": true}'), "envelope")

    def test_unknown_schema(self):
        with self.assertRaises(FileNotFoundError):
            jsonio.load_schema("no-such-schema")

    def test_canonical_hash(self):
        obj = {"b": 1, "a": ["é", 2.5]}
        expected = hashlib.sha256('{"a":["é",2.5],"b":1}'.encode("utf-8")).hexdigest()
        self.assertEqual(jsonio.canonical_hash(obj), f"sha256:{expected}")
        self.assertEqual(jsonio.canonical_hash({"a": ["é", 2.5], "b": 1}), jsonio.canonical_hash(obj))

    def test_every_schema_file_is_supported(self):
        from coach.validate import check_schema

        for path in sorted(jsonio.SCHEMA_DIR.glob("*.schema.json")):
            with self.subTest(schema=path.name):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(schema["properties"]["schema_version"]["const"], int)
                check_schema(schema)


if __name__ == "__main__":
    unittest.main()
