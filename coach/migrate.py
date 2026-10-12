"""The migration runner: upgrades every owned JSON document to its current schema version (contract C7, C16).

Each owned document type is a subpackage `coach/migrations/<schema name>/`
whose `__init__.py` sets `FILES` (glob patterns relative to the instance
root). Its steps are modules `NNNN_<slug>.py` defining `DOC`, `FROM`, `TO`
(= FROM + 1) and `migrate(doc) -> doc`, and optionally
`notes(before, after) -> list[str]` for the run's report and
`creates(before, after) -> {path: doc}` for documents the step brings into
being (written only where no file exists yet, after their own steps bring
them to their current version). The target
version is the `schema_version` const in `coach/schemas/<schema name>.schema.json`.
"""

import copy
import fnmatch
import importlib.util
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from coach import jsonio, paths
from coach.errors import ValidationError
from coach.validate import validate as validate_schema

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_STEP_FILE = re.compile(r"^(\d{4})_[a-z0-9_]+\.py$")


class RegistryError(Exception):
    """The migrations package itself is malformed: a framework bug, not an instance problem."""


@dataclass(frozen=True)
class Step:
    name: str
    doc: str
    from_version: int
    to_version: int
    migrate: object
    notes: object = None
    creates: object = None


@dataclass
class Document:
    name: str
    files: tuple
    schema: dict
    target: int
    steps: list = field(default_factory=list)

    def step_from(self, version):
        return next((step for step in self.steps if step.from_version == version), None)


@dataclass
class Registry:
    documents: dict

    @classmethod
    def discover(cls, directory=MIGRATIONS_DIR, schema_dir=jsonio.SCHEMA_DIR):
        directory, schema_dir = Path(directory), Path(schema_dir)
        documents = {}
        for doc_dir in sorted(p for p in directory.iterdir() if p.is_dir() and (p / "__init__.py").is_file()):
            name = doc_dir.name
            declaration = _load_module(doc_dir / "__init__.py", f"{name}")
            files = tuple(getattr(declaration, "FILES", ()))
            if not files:
                raise RegistryError(f"{doc_dir}/__init__.py must set FILES to the document's glob patterns")
            schema_path = schema_dir / f"{name}.schema.json"
            if not schema_path.is_file():
                raise RegistryError(f"{doc_dir}: no schema {schema_path.name} for document {name}")
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            document = Document(name, files, schema, jsonio.current_version(schema))
            document.steps = _steps(doc_dir, document)
            documents[name] = document
        return cls(documents)


def registry():
    """The framework's migrations, rediscovered on each call."""
    return Registry.discover()


def _load_module(path, label):
    spec = importlib.util.spec_from_file_location(f"coach_migration_{label}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _steps(doc_dir, document):
    steps = []
    for path in sorted(doc_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        if not _STEP_FILE.fullmatch(path.name):
            raise RegistryError(f"{path}: a step file is named NNNN_<slug>.py")
        module = _load_module(path, f"{document.name}_{path.stem}")
        name = f"{document.name}/{path.stem}"
        for attribute in ("DOC", "FROM", "TO", "migrate"):
            if not hasattr(module, attribute):
                raise RegistryError(f"{name} does not define {attribute}")
        if module.DOC != document.name:
            raise RegistryError(f"{name} declares DOC {module.DOC!r} but lives in {document.name}/")
        if module.TO != module.FROM + 1:
            raise RegistryError(f"{name} goes from {module.FROM} to {module.TO}; TO must be FROM + 1")
        if module.TO > document.target:
            raise RegistryError(f"{name} goes to {module.TO}, past the {document.name} schema's version "
                                f"{document.target}")
        if any(step.from_version == module.FROM for step in steps):
            raise RegistryError(f"{document.name} has two steps from version {module.FROM}")
        steps.append(Step(name, document.name, module.FROM, module.TO, module.migrate, getattr(module, "notes", None),
                          getattr(module, "creates", None)))
    return sorted(steps, key=lambda step: step.from_version)


def _owned_files(root, reg):
    """(relative path, document) for every file on disk an owned document's patterns match."""
    root = Path(root)
    found = []
    for document in reg.documents.values():
        for pattern in document.files:
            for path in sorted(root.glob(pattern)):
                if path.is_file():
                    found.append((path.relative_to(root).as_posix(), document))
    return found


def _version_of(path):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = doc.get("schema_version") if isinstance(doc, dict) else None
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


def status(root, reg=None):
    """One row per owned file: path, doc, version, target and state (current, behind, ahead, unreadable)."""
    reg = reg or registry()
    rows = []
    for relative, document in _owned_files(root, reg):
        version = _version_of(Path(root) / relative)
        if version is None:
            state = "unreadable"
        elif version < document.target:
            state = "behind"
        elif version > document.target:
            state = "ahead"
        else:
            state = "current"
        rows.append({"path": relative, "doc": document.name, "version": version, "target": document.target,
                     "state": state})
    return rows


def plan(root, reg=None):
    """(entries, problems): the steps each file behind its version needs, and what stops a run."""
    reg = reg or registry()
    entries, problems = [], []
    for row in status(root, reg):
        document = reg.documents[row["doc"]]
        if row["state"] == "unreadable":
            problems.append({"path": row["path"], "message": "not a JSON object with an integer schema_version"})
        elif row["state"] == "ahead":
            problems.append({"path": row["path"], "message": (
                f"schema_version {row['version']} is newer than this coach reads ({row['target']}); "
                "run /framework-sync")})
        elif row["state"] == "behind":
            steps, version = [], row["version"]
            while version < document.target:
                step = document.step_from(version)
                if step is None:
                    problems.append({"path": row["path"], "message": (
                        f"no step from version {version} for {document.name}; the framework is missing a migration")})
                    break
                steps.append(step.name)
                version = step.to_version
            else:
                entries.append({"path": row["path"], "doc": document.name, "from": row["version"],
                                "to": document.target, "steps": steps})
    return entries, problems


def _migrated(root, entry, document):
    """(new document, notes, errors, created {path: doc}) for one plan entry."""
    doc = json.loads((Path(root) / entry["path"]).read_text(encoding="utf-8"))
    notes, created = [], {}
    for name in entry["steps"]:
        step = next(s for s in document.steps if s.name == name)
        before = copy.deepcopy(doc)
        doc = step.migrate(copy.deepcopy(doc))
        doc["schema_version"] = step.to_version
        if step.notes is not None:
            notes += list(step.notes(before, doc))
        if step.creates is not None:
            created.update(step.creates(before, doc))
    errors = [{"path": f"{entry['path']}: {error.path}", "message": error.message}
              for error in validate_schema(doc, document.schema)]
    return doc, notes, errors, created


def _owner(reg, relative):
    return next((document for document in reg.documents.values()
                 if any(fnmatch.fnmatchcase(relative, pattern) for pattern in document.files)), None)


def _forward(document, doc):
    """A document a step created at the version that step knew, migrated on to the document's current version."""
    version = doc.get("schema_version")
    while isinstance(version, int) and version < document.target:
        step = document.step_from(version)
        if step is None:
            break
        doc = step.migrate(copy.deepcopy(doc))
        doc["schema_version"] = version = step.to_version
    return doc


def _created_errors(reg, relative, doc):
    document = _owner(reg, relative)
    if document is None:
        return [{"path": relative, "message": "a migration step created a file no owned document declares"}]
    return [{"path": f"{relative}: {error.path}", "message": error.message}
            for error in validate_schema(doc, document.schema)]


def _backup_dir(root, now):
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    base = Path(root) / paths.BACKUPS_DIR
    candidate, n = base / stamp, 1
    while candidate.exists():
        n += 1
        candidate = base / f"{stamp}-{n}"
    return candidate


def _restore(root, backup, relatives):
    for relative in relatives:
        shutil.copy2(backup / relative, Path(root) / relative)


def stage(root, relatives, what="migrated files"):
    """(staged paths, warning or None): `git add` the files, deletions included; never commits."""
    try:
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True)
    except FileNotFoundError:
        return [], f"git is not installed, so the {what} are not staged; stage them by hand"
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return [], f"{root} is not a git repository, so the {what} are not staged"
    added = subprocess.run(["git", "-C", str(root), "add", "--", *relatives], capture_output=True, text=True)
    if added.returncode != 0:
        return [], f"git add failed ({added.stderr.strip()}); stage the {what} by hand"
    return list(relatives), None


def run(root, dry_run, now=None, reg=None):
    """Migrate every file behind its version: back up, migrate, validate, write, then `git add`.

    Nothing is written unless every migrated document validates; a write
    that fails part way restores every file from the backup. Returns the
    report; raises ValidationError when the plan or a migrated document is
    invalid.
    """
    reg = reg or registry()
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    entries, problems = plan(root, reg)
    report = {"files": entries, "notes": [], "created": [], "backup": None, "written": False, "staged": [],
              "warnings": []}
    if problems:
        raise ValidationError(f"{len(problems)} file(s) cannot be migrated", details=problems)
    if not entries:
        return report

    backup = None
    if not dry_run:
        backup = _backup_dir(root, now)
        for entry in entries:
            target = backup / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / entry["path"], target)
        report["backup"] = backup.relative_to(root).as_posix()

    results, errors, created = [], [], {}
    for entry in entries:
        doc, notes, doc_errors, new_files = _migrated(root, entry, reg.documents[entry["doc"]])
        results.append((entry["path"], doc))
        report["notes"] += notes
        errors += doc_errors
        created.update({relative: new for relative, new in new_files.items() if not (root / relative).exists()})
    for relative in sorted(created):
        document = _owner(reg, relative)
        if document is not None:
            created[relative] = _forward(document, created[relative])
        errors += _created_errors(reg, relative, created[relative])
    report["created"] = sorted(created)
    if errors:
        where = f"; the originals are unchanged and backed up in {report['backup']}" if backup else ""
        raise ValidationError(f"A migration step produced an invalid document ({len(errors)} problem(s)){where}",
                              details=errors)
    if dry_run:
        return report

    relatives = [relative for relative, _ in results]
    try:
        for relative, doc in results:
            jsonio.write_doc(root / relative, doc, False)
        for relative, doc in sorted(created.items()):
            jsonio.write_doc(root / relative, doc, False)
    except BaseException:
        _restore(root, backup, relatives)
        for relative in created:
            (root / relative).unlink(missing_ok=True)
        raise
    report["written"] = True
    report["staged"], warning = stage(root, relatives + sorted(created))
    if warning:
        report["warnings"].append(warning)
    return report
