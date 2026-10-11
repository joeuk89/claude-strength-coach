"""Research notes, claim references and the citation scan (contract C28).

A note is `research/<id>.md` (template) or `research/local/<id>.md`
(local): a hidden data block (coach.datablock), a rendered region, then
prose. A claim is cited as `rn:<note-id>.<n>`.
"""

import calendar
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath

from coach import datablock, dates, jsonio, paths
from coach.errors import ValidationError
from coach.validate import validate

REF = re.compile(r"\brn:([a-z0-9]+(?:-[a-z0-9]+)*)\.([0-9]+)\b")
LOCAL_PREFIX = "local-"
DISCLAIMER = "This note does not replace assessment by a qualified professional."
DUE_SOON_DAYS = 60
MAX_REVIEW_MONTHS = 24
SCHEMA = "research_note"
STATUS_ORDER = ("current", "due_soon", "expired")


@dataclass(frozen=True)
class Source:
    id: str
    citation: str
    url: str
    type: str
    year: int
    accessed: str = None

    def to_json(self):
        out = {"id": self.id, "citation": self.citation, "url": self.url, "type": self.type, "year": self.year}
        if self.accessed:
            out["accessed"] = self.accessed
        return out


@dataclass(frozen=True)
class Claim:
    note_id: str
    n: int
    text: str
    basis: str
    sources: tuple
    status: str
    confidence: str = None
    retired_on: str = None
    superseded_by: str = None

    @property
    def ref(self):
        return f"rn:{self.note_id}.{self.n}"

    def to_json(self):
        out = {"ref": self.ref, "n": self.n, "text": self.text, "basis": self.basis,
               "sources": list(self.sources), "status": self.status}
        for key in ("confidence", "retired_on", "superseded_by"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        return out


@dataclass(frozen=True)
class Note:
    id: str
    kind: str
    path: str
    topic: str
    question: str
    written: date
    review_by: date
    confidence: str
    applies_to: tuple
    tags: tuple
    updates: tuple
    sources: tuple
    claims: tuple
    data: dict
    rest: str

    def claim(self, n):
        return next((c for c in self.claims if c.n == n), None)


@dataclass(frozen=True)
class Problem:
    status: str
    path: str
    message: str


@dataclass(frozen=True)
class Citation:
    ref: str
    note_id: str
    n: int
    path: str
    line: int
    scope: str
    resolved: bool
    retired: bool

    def to_json(self):
        return {"ref": self.ref, "path": self.path, "line": self.line, "scope": self.scope,
                "resolved": self.resolved, "retired": self.retired}


def parse_ref(text):
    """(note id, n) for a whole claim ref, else None."""
    match = REF.fullmatch(text) if isinstance(text, str) else None
    return (match.group(1), int(match.group(2))) if match else None


def is_local_id(note_id):
    return note_id.startswith(LOCAL_PREFIX)


def note_files(root):
    """[(kind, root-relative posix path)] for every note file, template notes first."""
    root = Path(root)
    found = []
    for kind, folder in (("template", paths.RESEARCH_DIR), ("local", paths.RESEARCH_LOCAL_DIR)):
        directory = root / folder
        if directory.is_dir():
            for path in sorted(directory.glob("*.md")):
                if path.is_file():
                    found.append((kind, (folder / path.name).as_posix()))
    return found


def note_path(note_id):
    """Where the note with this id lives, by its kind."""
    folder = paths.RESEARCH_LOCAL_DIR if is_local_id(note_id) else paths.RESEARCH_DIR
    return (folder / f"{note_id}.md").as_posix()


def _jsonable(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def add_months(day, months):
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def read_note(root, rel, kind):
    """Parse and validate one note file on its own. Return (Note or None, [Problem])."""
    try:
        raw, rest = datablock.read(Path(root) / rel, "note")
    except ValidationError as exc:
        return None, [Problem("fail", rel, exc.message)]

    data = _jsonable(raw)
    schema = jsonio.load_schema(SCHEMA)
    current = jsonio.current_version(schema)
    version = data.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool) and version != current:
        if version > current:
            message = f"schema_version {version} is newer than this coach reads ({current}); run /framework-sync"
        else:
            message = (f"schema_version {version} is older than the current {current}; "
                       "run python3 -m coach migrate run")
        return None, [Problem("fail", rel, f"{rel}: {message}")]
    errors = validate(data, schema)
    if errors:
        return None, [Problem("fail", rel, f"{rel}: {error.path}: {error.message}") for error in errors]

    problems = [Problem("fail", rel, f"{rel}: {message}") for message in _rule_breaks(data, rest, rel, kind)]
    if problems:
        return None, problems
    return _build(data, rest, rel, kind), []


def _rule_breaks(data, rest, rel, kind):
    note_id = data["id"]
    stem = PurePosixPath(rel).stem
    if note_id != stem:
        yield f"id {note_id!r} must equal the file name {stem!r}"
    if kind == "template" and is_local_id(note_id):
        yield f"a template note's id must not start {LOCAL_PREFIX!r}; local notes live in research/local/"
    if kind == "local" and not is_local_id(note_id):
        yield f"a local note's id must start {LOCAL_PREFIX!r}"

    try:
        written, review_by = dates.parse_date(data["written"]), dates.parse_date(data["review_by"])
    except ValueError as exc:
        yield str(exc)
        return
    if review_by < written:
        yield f"review_by {review_by} is before written {written}"
    elif review_by > add_months(written, MAX_REVIEW_MONTHS):
        yield f"review_by {review_by} is more than {MAX_REVIEW_MONTHS} months after written {written}"

    areas, tags, updates = data.get("applies_to", []), data.get("tags", []), data.get("updates", [])
    if kind == "template" and not areas:
        yield "a template note needs at least one area in applies_to"
    if kind == "local" and not areas and not tags:
        yield "a local note needs at least one area in applies_to or one tag"
    if kind == "template" and updates:
        yield "updates is for local notes only; refresh the template note instead"
    for ref in updates:
        if is_local_id(parse_ref(ref)[0]):
            yield f"updates entry {ref} must name a template claim, not a local one"

    source_ids = [source["id"] for source in data.get("sources", [])]
    for source_id in sorted({s for s in source_ids if source_ids.count(s) > 1}):
        yield f"more than one source has id {source_id!r}"
    numbers = [claim["n"] for claim in data["claims"]]
    for n in sorted({n for n in numbers if numbers.count(n) > 1}):
        yield f"more than one claim numbered {n}"
    for claim in data["claims"]:
        n = claim["n"]
        if not isinstance(n, int):
            yield f"claim number {n!r} must be a whole number written without a decimal point"
        for source_id in claim["sources"]:
            if source_id not in source_ids:
                yield f"claim {n} cites source {source_id!r}, which this note does not list"
        if not claim["sources"] and claim["basis"] != "heuristic":
            yield f"claim {n} is {claim['basis']}, so it needs at least one source; only heuristic claims may have none"
        if claim["status"] == "retired" and "retired_on" not in claim:
            yield f"claim {n} is retired, so it needs retired_on"
        if claim["status"] == "current" and ("retired_on" in claim or "superseded_by" in claim):
            yield f"claim {n} is current, so it must not carry retired_on or superseded_by"

    if "rehab" in areas and DISCLAIMER not in (line.strip() for line in rest.split("\n")):
        yield f"a note covering rehab must carry the line {DISCLAIMER!r}"


def _build(data, rest, rel, kind):
    note_id = data["id"]
    return Note(
        id=note_id, kind=kind, path=rel, topic=data["topic"], question=data["question"],
        written=dates.parse_date(data["written"]), review_by=dates.parse_date(data["review_by"]),
        confidence=data["confidence"], applies_to=tuple(data.get("applies_to", [])),
        tags=tuple(data.get("tags", [])), updates=tuple(data.get("updates", [])),
        sources=tuple(Source(id=s["id"], citation=s["citation"], url=s["url"], type=s["type"], year=s["year"],
                             accessed=s.get("accessed")) for s in data.get("sources", [])),
        claims=tuple(Claim(note_id=note_id, n=c["n"], text=c["text"], basis=c["basis"],
                           sources=tuple(c["sources"]), status=c["status"], confidence=c.get("confidence"),
                           retired_on=c.get("retired_on"), superseded_by=c.get("superseded_by"))
                     for c in data["claims"]),
        data=data, rest=rest,
    )


def load_all(root):
    """Every valid note and every problem found. Never raises for a bad note.

    Returns (notes, problems, invalid_ids), where invalid_ids are the file
    stems of notes that failed validation.
    """
    notes, problems, invalid = [], [], set()
    for kind, rel in note_files(root):
        note, found = read_note(root, rel, kind)
        problems.extend(found)
        if note is None:
            invalid.add(PurePosixPath(rel).stem)
        else:
            notes.append(note)
    templates = [note for note in notes if note.kind == "template"]
    for note in notes:
        for ref in note.updates:
            if parse_ref(ref)[0] in invalid:
                continue
            claim = find_claim(ref, templates)
            if claim is None:
                problems.append(Problem("warn", note.path, f"{note.path}: updates names {ref}, which does not exist"))
            elif claim.status != "current":
                problems.append(Problem("warn", note.path,
                                        f"{note.path}: updates names {ref}, which was retired on {claim.retired_on}"))
    return notes, problems, invalid


def raise_on_failures(problems):
    failures = [problem for problem in problems if problem.status == "fail"]
    if failures:
        raise ValidationError(
            f"{len({p.path for p in failures})} research note(s) are invalid; see python3 -m coach research validate",
            details=[{"path": p.path, "message": p.message} for p in failures],
        )


def load_notes(root):
    """Every note, both kinds. Raises ValidationError (exit 1) if any note is invalid."""
    notes, problems, _ = load_all(root)
    raise_on_failures(problems)
    return notes


def find_claim(ref, notes):
    """The claim a ref names, current or retired, or None."""
    parsed = parse_ref(ref)
    if parsed is None:
        return None
    note = next((note for note in notes if note.id == parsed[0]), None)
    return note.claim(parsed[1]) if note else None


def resolve(ref, notes):
    """The claim a ref names when it exists and is current; None when missing or retired."""
    claim = find_claim(ref, notes)
    return claim if claim is not None and claim.status == "current" else None


def note_status(note, today):
    if note.review_by < today:
        return "expired"
    if note.review_by - timedelta(days=DUE_SOON_DAYS) <= today:
        return "due_soon"
    return "current"


def _in_force(note, today):
    """`current` or `due_soon`: what C28 calls a current note when it covers an area or supersedes a claim."""
    return note_status(note, today) != "expired"


def local_updates_from(notes, today):
    mapping = {}
    for note in notes:
        if note.kind == "local" and _in_force(note, today):
            for ref in note.updates:
                mapping.setdefault(ref, note.id)
    return mapping


def expired_areas(notes, today):
    """{area: [ids of expired notes in it that no in-force local note covers]}."""
    locals_in_force = [note for note in notes if note.kind == "local" and _in_force(note, today)]
    found = {}
    for note in notes:
        if _in_force(note, today):
            continue
        for area in note.applies_to:
            covered = any(
                area in local.applies_to
                or any(parse_ref(ref)[0] == note.id for ref in local.updates)
                for local in locals_in_force
            )
            if not covered:
                found.setdefault(area, []).append(note.id)
    return {area: found[area] for area in sorted(found)}


def area_statuses(notes, today):
    expired = expired_areas(notes, today)
    statuses = {}
    for note in notes:
        for area in note.applies_to:
            if area in expired:
                statuses[area] = "expired"
            elif _in_force(note, today):
                status = note_status(note, today)
                statuses[area] = max(statuses.get(area, "current"), status, key=STATUS_ORDER.index)
            else:
                statuses.setdefault(area, "current")
    return {area: statuses[area] for area in sorted(statuses)}


def expired_by_area(root, today):
    """Each expired area to the ids of the expired notes that make it so.

    Reads only the valid notes, so one broken note never stops a proposal;
    `coach check` reports the broken one.
    """
    return expired_areas(load_all(root)[0], today)


def local_updates(root, today):
    """Template claim ref to the id of the in-force local note superseding it (valid notes only)."""
    return local_updates_from(load_all(root)[0], today)


def _scan_files(root, globs):
    root = Path(root)
    seen = set()
    for pattern in globs:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            if rel not in seen and path.is_file():
                seen.add(rel)
                yield rel, path


def scan_citations(root, notes=None):
    """Every claim reference in the framework and instance files, in scan order."""
    if notes is None:
        notes = load_all(root)[0]
    found = []
    for scope, globs in (("framework", paths.CITATION_SCAN_FRAMEWORK), ("instance", paths.CITATION_SCAN_INSTANCE)):
        for rel, path in _scan_files(root, globs):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.split("\n"), start=1):
                for match in REF.finditer(line):
                    claim = find_claim(match.group(0), notes)
                    found.append(Citation(
                        ref=match.group(0), note_id=match.group(1), n=int(match.group(2)), path=rel, line=number,
                        scope=scope, resolved=claim is not None and claim.status == "current",
                        retired=claim is not None and claim.status == "retired",
                    ))
    return found


def citation_problems(citations, invalid_ids=()):
    """Apply the C28 scope rules. Refs into a note that failed validation are left to research_notes."""
    problems = []
    for c in citations:
        if c.note_id in invalid_ids:
            continue
        where = f"{c.path}:{c.line} cites {c.ref}"
        if c.scope == "framework":
            if is_local_id(c.note_id):
                problems.append(Problem("fail", c.path,
                                        f"{where}, a local claim; framework files cite template claims only"))
            elif c.retired:
                problems.append(Problem("fail", c.path, f"{where}, which is retired"))
            elif not c.resolved:
                problems.append(Problem("fail", c.path, f"{where}, which does not exist"))
        elif c.retired:
            if not PurePosixPath(c.path).is_relative_to(paths.CHECKINS_DIR):
                problems.append(Problem("warn", c.path, f"{where}, which is retired"))
        elif not c.resolved:
            problems.append(Problem("warn", c.path, f"{where}, which does not exist"))
    return problems


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def _link_text(text):
    return _cell(text).replace("[", "\\[").replace("]", "\\]")


def _status_line(note):
    parts = [f"**{note.kind.capitalize()} note**", f"written {note.written.isoformat()}",
             f"review by {note.review_by.isoformat()}", f"confidence {note.confidence}"]
    if note.applies_to:
        parts.append("areas " + ", ".join(note.applies_to))
    if note.tags:
        parts.append("tags " + ", ".join(note.tags))
    if note.updates:
        parts.append("updates " + ", ".join(note.updates))
    return " · ".join(parts)


def _claim_row(claim):
    basis = claim.basis + (f" ({claim.confidence} confidence)" if claim.confidence else "")
    status = claim.status
    if claim.status == "retired":
        status = f"retired {claim.retired_on}" + (f", see {claim.superseded_by}" if claim.superseded_by else "")
    sources = ", ".join(claim.sources) or "none"
    return f"| {claim.n} | {_cell(claim.text)} | {basis} | {sources} | {status} |"


def _source_row(source):
    kind = source.type + (f", accessed {source.accessed}" if source.accessed else "")
    return f"| {source.id} | [{_link_text(source.citation)}](<{source.url}>) | {kind} | {source.year} |"


def begin_marker(note_id):
    return f"<!-- coach:begin research {note_id} -->"


def end_marker(note_id):
    return f"<!-- coach:end research {note_id} -->"


def render_note(note):
    """The rendered region of a note, markers included, with no trailing newline."""
    lines = [begin_marker(note.id), "", _status_line(note), "",
             "| # | Claim | Basis | Sources | Status |", "| --- | --- | --- | --- | --- |"]
    lines += [_claim_row(claim) for claim in sorted(note.claims, key=lambda c: c.n)]
    lines.append("")
    if note.sources:
        lines += ["| Source | Citation | Type | Year |", "| --- | --- | --- | --- |"]
        lines += [_source_row(source) for source in note.sources]
    else:
        lines.append("No sources: every claim is a coaching heuristic.")
    lines += ["", end_marker(note.id)]
    return "\n".join(lines)


def load_one(root, note_id):
    """The valid note with this id; raises ValidationError if it is missing or invalid."""
    rel = note_path(note_id)
    if not (Path(root) / rel).is_file():
        raise ValidationError(f"there is no research note {note_id!r} (looked for {rel})")
    kind = "local" if is_local_id(note_id) else "template"
    note, problems = read_note(root, rel, kind)
    if note is None:
        raise ValidationError(f"{rel} is not a valid research note",
                              details=[{"path": p.path, "message": p.message} for p in problems])
    return note


def render_research(root, note_id):
    """The fresh rendered region of one note (contract C11)."""
    return render_note(load_one(root, note_id))


def find_region(text, note_id):
    """(start, end) offsets of the note's region in `text`, or None when it has none."""
    begins = [m.start() for m in re.finditer(f"^{re.escape(begin_marker(note_id))}$", text, re.MULTILINE)]
    ends = [m.end() for m in re.finditer(f"^{re.escape(end_marker(note_id))}$", text, re.MULTILINE)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise ValidationError(f"research note {note_id}: expected one {begin_marker(note_id)} line followed by "
                              f"one {end_marker(note_id)} line")
    return begins[0], ends[0]


def region_in(note):
    """The note's region as it stands in the file, or None."""
    span = find_region(note.rest, note.id)
    return None if span is None else note.rest[span[0]:span[1]]


def rerendered_rest(note):
    """The text after the data block with only the region replaced (or inserted first)."""
    region = render_note(note)
    span = find_region(note.rest, note.id)
    if span is not None:
        return note.rest[:span[0]] + region + note.rest[span[1]:]
    if not note.rest:
        return region + "\n"
    return region + "\n" + ("" if note.rest.startswith("\n") else "\n") + note.rest


def write_region(root, note, dry_run):
    """Re-render the note's region in place. Return True when the file changes."""
    path = Path(root) / note.path
    text = path.read_text(encoding="utf-8")
    head = text[:len(text) - len(note.rest)]
    updated = head + rerendered_rest(note)
    if updated == text:
        return False
    if not dry_run:
        _write_text(path, updated)
    return True


def _write_text(path, text):
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
