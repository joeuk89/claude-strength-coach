"""Reading and writing the package's JSON documents (contract C7)."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from coach.errors import ValidationError
from coach.validate import validate

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def load_schema(name):
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def current_version(schema):
    return schema["properties"]["schema_version"]["const"]


def read_doc(path, schema_name):
    """Read a JSON document, gate its schema_version, and validate it."""
    path = Path(path)
    schema = load_schema(schema_name)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None

    version = doc.get("schema_version") if isinstance(doc, dict) else None
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValidationError(f"{path} has no integer schema_version, so it is not a {schema_name} document")
    current = current_version(schema)
    if version > current:
        raise ValidationError(
            f"{path} has schema_version {version}, newer than this coach reads ({current}); run /framework-sync"
        )
    if version < current:
        raise ValidationError(
            f"{path} has schema_version {version}, older than the current {current}; run python3 -m coach migrate run"
        )

    errors = validate(doc, schema)
    if errors:
        raise ValidationError(
            f"{path} is not a valid {schema_name} document ({len(errors)} problem(s))",
            details=[error.to_json() for error in errors],
        )
    return doc


def dumps(doc):
    """The on-disk text of a document: indent 2, UTF-8 as is, trailing newline."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def write_doc(path, doc, dry_run):
    """Write `doc` atomically and return its text; with dry_run, only return it."""
    text = dumps(doc)
    if dry_run:
        return text
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
    return text


def canonical_hash(obj):
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
