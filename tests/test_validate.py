import unittest

from coach.validate import Error, SchemaError, validate

SCHEMA = {
    "type": "object",
    "required": ["schema_version", "items"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": 1},
        "kind": {"enum": ["weekly", "deload"]},
        "note": {"type": ["string", "null"]},
        "count": {"type": "integer", "minimum": 0, "maximum": 10},
        "id": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "items": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/item"}},
        "extra": {"type": "object", "additionalProperties": {"type": "number"}},
    },
    "$defs": {
        "item": {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}, "weight": {"type": "number"}},
            "additionalProperties": False,
        }
    },
}


def good():
    return {"schema_version": 1, "kind": "weekly", "note": None, "count": 3, "id": "a-1",
            "items": [{"name": "squat", "weight": 100.5}], "extra": {"a": 1}}


class ValidateTest(unittest.TestCase):
    def assert_error(self, doc, path, fragment):
        errors = validate(doc, SCHEMA)
        self.assertTrue(errors, "expected an error")
        self.assertIn(path, [e.path for e in errors], errors)
        message = next(e.message for e in errors if e.path == path)
        self.assertIn(fragment, message)

    def test_valid_document(self):
        self.assertEqual(validate(good(), SCHEMA), [])

    def test_required(self):
        doc = good()
        del doc["items"]
        self.assert_error(doc, "$", "items")

    def test_additional_properties(self):
        doc = good()
        doc["surprise"] = 1
        self.assert_error(doc, "$.surprise", "not allowed")

    def test_const_and_enum(self):
        doc = good()
        doc["schema_version"] = 2
        self.assert_error(doc, "$.schema_version", "1")
        doc = good()
        doc["kind"] = "midweek"
        self.assert_error(doc, "$.kind", "weekly")

    def test_types(self):
        doc = good()
        doc["count"] = 2.5
        self.assert_error(doc, "$.count", "integer")
        doc = good()
        doc["count"] = True
        self.assert_error(doc, "$.count", "integer")
        doc = good()
        doc["note"] = 3
        self.assert_error(doc, "$.note", "string")
        doc = good()
        doc["items"][0]["weight"] = "heavy"
        self.assert_error(doc, "$.items[0].weight", "number")

    def test_integral_float_is_an_integer(self):
        doc = good()
        doc["count"] = 3.0
        self.assertEqual(validate(doc, SCHEMA), [])

    def test_minimum_maximum_pattern_min_items(self):
        doc = good()
        doc["count"] = -1
        self.assert_error(doc, "$.count", "minimum")
        doc = good()
        doc["count"] = 11
        self.assert_error(doc, "$.count", "maximum")
        doc = good()
        doc["id"] = "Bad Id"
        self.assert_error(doc, "$.id", "pattern")
        doc = good()
        doc["items"] = []
        self.assert_error(doc, "$.items", "at least 1")

    def test_ref_and_nested_paths(self):
        doc = good()
        doc["items"].append({"weight": 1})
        self.assert_error(doc, "$.items[1]", "name")

    def test_additional_properties_schema(self):
        doc = good()
        doc["extra"]["b"] = "x"
        self.assert_error(doc, "$.extra.b", "number")

    def test_odd_keys_use_bracket_paths(self):
        doc = good()
        doc["extra"]["two words"] = "x"
        self.assert_error(doc, "$.extra['two words']", "number")

    def test_error_is_comparable(self):
        self.assertEqual(Error("$.a", "m"), Error("$.a", "m"))

    def test_unsupported_keyword_is_a_schema_error(self):
        with self.assertRaises(SchemaError):
            validate({}, {"type": "object", "patternProperties": {}})
        with self.assertRaises(SchemaError):
            validate({}, {"$ref": "#/$defs/missing"})


if __name__ == "__main__":
    unittest.main()
