"""A JSON Schema subset validator (contract C7).

Supported keywords: type (a name or a list), enum, const, required,
properties, additionalProperties, items, minItems, minimum, maximum,
pattern, and $ref to #/$defs/... Any other keyword is a SchemaError, so a
schema typo fails loudly instead of validating nothing.
"""

import math
import re
from dataclasses import dataclass

_KEYWORDS = {
    "type", "enum", "const", "required", "properties", "additionalProperties", "items",
    "minItems", "minimum", "maximum", "pattern", "$ref",
}
_ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description", "default", "examples", "$comment",
                "x-coach-paths"}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Error:
    path: str
    message: str

    def to_json(self):
        return {"path": self.path, "message": self.message}


class SchemaError(Exception):
    """The schema itself uses something this validator does not support."""


def validate(doc, schema):
    errors = []
    _check(doc, schema, schema, "$", errors)
    return errors


def check_schema(schema, root=None, where="$"):
    """Raise SchemaError if any part of `schema` uses an unsupported keyword."""
    root = schema if root is None else root
    if not isinstance(schema, dict):
        raise SchemaError(f"schema at {where} must be an object")
    unknown = set(schema) - _KEYWORDS - _ANNOTATIONS
    if unknown:
        raise SchemaError(f"unsupported schema keyword(s) at {where}: {', '.join(sorted(unknown))}")
    if "$ref" in schema:
        _resolve(schema["$ref"], root)
    for name, sub in schema.get("properties", {}).items():
        check_schema(sub, root, f"{where}.properties.{name}")
    for name, sub in schema.get("$defs", {}).items():
        check_schema(sub, root, f"{where}.$defs.{name}")
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            check_schema(schema[key], root, f"{where}.{key}")


def _child(path, key):
    if isinstance(key, int):
        return f"{path}[{key}]"
    if _IDENTIFIER.match(key):
        return f"{path}.{key}"
    return f"{path}[{key!r}]"


def _is_type(value, name):
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    if name == "number":
        return True
    if name == "integer":
        return isinstance(value, int) or value.is_integer()
    raise SchemaError(f"unknown type {name!r}")


def _describe(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return f"string {value!r}"
    return repr(value)


def _resolve(ref, root):
    prefix = "#/$defs/"
    if not ref.startswith(prefix):
        raise SchemaError(f"only $ref to #/$defs/... is supported, found {ref!r}")
    try:
        return root["$defs"][ref[len(prefix):]]
    except KeyError:
        raise SchemaError(f"$ref {ref!r} points at nothing") from None


def _check(value, schema, root, path, errors):
    if not isinstance(schema, dict):
        raise SchemaError(f"schema at {path} must be an object")
    unknown = set(schema) - _KEYWORDS - _ANNOTATIONS
    if unknown:
        raise SchemaError(f"unsupported schema keyword(s) at {path}: {', '.join(sorted(unknown))}")

    if "$ref" in schema:
        _check(value, _resolve(schema["$ref"], root), root, path, errors)

    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, name) for name in names):
            errors.append(Error(path, f"expected {' or '.join(names)}, found {_describe(value)}"))
            return

    if "const" in schema and not _same(value, schema["const"]):
        errors.append(Error(path, f"expected {schema['const']!r}, found {_describe(value)}"))
    if "enum" in schema and not any(_same(value, option) for option in schema["enum"]):
        options = ", ".join(repr(option) for option in schema["enum"])
        errors.append(Error(path, f"expected one of {options}, found {_describe(value)}"))

    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(Error(path, f"below the minimum {schema['minimum']}: {value!r}"))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(Error(path, f"above the maximum {schema['maximum']}: {value!r}"))

    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        errors.append(Error(path, f"does not match the pattern {schema['pattern']}: {value!r}"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(Error(path, f"expected at least {schema['minItems']} item(s), found {len(value)}"))
        if "items" in schema:
            for index, item in enumerate(value):
                _check(item, schema["items"], root, _child(path, index), errors)

    if isinstance(value, dict):
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            errors.append(Error(path, f"missing required key(s): {', '.join(missing)}"))
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _check(item, properties[key], root, _child(path, key), errors)
            elif extra is False:
                errors.append(Error(_child(path, key), "key not allowed here"))
            elif isinstance(extra, dict):
                _check(item, extra, root, _child(path, key), errors)


def _same(a, b):
    """JSON equality: 1 == 1.0, but True is not 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b
