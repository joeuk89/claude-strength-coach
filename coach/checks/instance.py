"""Whole-instance checks: schema versions, cross-file references, caps, .env safety, bare Hevy values and
rendered regions (contract C13).

Checks about a prescription (routine ids, library consistency, caps, bare
Hevy values in overlays) read only overlays whose span runs to today or
later: an ended overlay is history, and an approved one cannot be edited
without breaking its approval.
"""

import functools
import importlib
import json
import os
import pkgutil
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import coach
from coach import dates, jsonio, migrate, overlay, paths, recipes, render, research, units
from coach.checks import Result, check
from coach.config import equipment_for
from coach.errors import ConfigError, ValidationError
from coach.hevy.cache import HevyCache
from coach.library import Library

OWNER = "R-16"
PATHS_KEY = "x-coach-paths"
PER_HAND_X2 = "per_hand_x2"
SNAPSHOT_KINDS = ("cardio",)
OVERLAY_TEXT_FIELDS = ("target_note", "change", "cues", "focus")
TWO_NUMBER_EXAMPLE = "25/hand (Hevy: 50)"
MIGRATE_RUN = "run python3 -m coach migrate run"
REBUILD_HEVY_CACHE = "rebuild the cache with python3 -m coach hevy pull --full"
FRAMEWORK_SYNC_MARKER = ".claude/framework-sync.json"


def _rel(ctx, path):
    return Path(path).relative_to(ctx.root).as_posix()


def _overlays(ctx, live_only):
    """[(rel path, overlay)] for every readable overlay; with live_only, those whose span has not ended."""
    found = []
    today = ctx.today() if live_only else None
    for overlay_id in overlay.ids(ctx.root):
        try:
            doc = overlay.load(ctx.root, overlay_id)
        except ValidationError:
            continue
        if today is not None and dates.parse_date(doc["span"]["end"]) < today:
            continue
        found.append((_rel(ctx, overlay.path_for(ctx.root, overlay_id)), doc))
    return found


def _no_overlays(live_only):
    if live_only:
        return [Result("skip", "No overlay's span runs to today or later.", paths.OVERLAYS_DIR.as_posix())]
    return [Result("skip", f"No overlays in {paths.OVERLAYS_DIR}.", paths.OVERLAYS_DIR.as_posix())]


def _lines(doc):
    for s_index, session in enumerate(doc["sessions"]):
        for e_index, line in enumerate(session["exercises"]):
            yield f"$.sessions[{s_index}].exercises[{e_index}]", session, line


def _library(ctx):
    try:
        return Library.load(ctx.root)
    except ValidationError:
        return None


_BAD_LIBRARY = Result("skip", "The exercise library is invalid; see library_valid.", paths.EXERCISES.as_posix())


def claimed_documents():
    """{schema name: instance path globs} for the documents the migration runner does not own (C7)."""
    claimed = {}
    for path in sorted(jsonio.SCHEMA_DIR.glob("*.schema.json")):
        globs = json.loads(path.read_text(encoding="utf-8")).get(PATHS_KEY)
        if globs:
            claimed[path.name[:-len(".schema.json")]] = tuple(globs)
    return claimed


def _newer(where, found, current):
    return f"{where} has schema_version {found}, newer than this coach reads ({current}); run /framework-sync"


def _older(where, found, current, rel):
    fix = REBUILD_HEVY_CACHE if rel.startswith(f"{paths.HEVY_CACHE_DIR}/") else MIGRATE_RUN
    return f"{where} has schema_version {found}, older than the current {current}; {fix}"


def _registry_results(ctx):
    """(fail results, paths checked) for the documents the migration runner owns (C16)."""
    results, checked = [], set()
    for row in migrate.status(ctx.root):
        checked.add(row["path"])
        where, found, current = row["path"], row["version"], row["target"]
        if row["state"] == "unreadable":
            results.append(Result("fail", f"{where} is not a JSON object with an integer schema_version", where))
        elif row["state"] == "ahead":
            results.append(Result("fail", _newer(where, found, current), where))
        elif row["state"] == "behind":
            results.append(Result("fail", _older(where, found, current, where), where))
    return results, checked


def _schema_for(doc, names, schemas):
    """The claiming schema whose constant fields (other than schema_version) the line matches."""
    def matches(name):
        properties = schemas[name].get("properties", {})
        return all(doc.get(key) == spec["const"] for key, spec in properties.items()
                   if key != "schema_version" and isinstance(spec, dict) and "const" in spec)

    fitting = [name for name in names if matches(name)]
    return (fitting or names)[0]


def _claimed_results(ctx, skip):
    """(fail results, documents checked) for every file an `x-coach-paths` glob matches.

    A JSONL line keeps the version it was written at (C29), so only a line
    newer than this coach reads fails.
    """
    claimants, schemas = {}, {}
    for name, globs in claimed_documents().items():
        schemas[name] = jsonio.load_schema(name)
        for pattern in globs:
            for path in ctx.root.glob(pattern):
                rel = _rel(ctx, path)
                if path.is_file() and rel not in skip:
                    claimants.setdefault(rel, []).append(name)
    results, checked = [], 0
    for rel in sorted(claimants):
        text = (ctx.root / rel).read_text(encoding="utf-8")
        is_log = rel.endswith(".jsonl")
        if is_log:
            entries = [(f"{rel} line {n}", line) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
        else:
            entries = [(rel, text)]
        for where, raw in entries:
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError as exc:
                results.append(Result("fail", f"{where} is not valid JSON ({exc.msg})", rel))
                continue
            found = doc.get("schema_version") if isinstance(doc, dict) else None
            if isinstance(found, bool) or not isinstance(found, int):
                results.append(Result("fail", f"{where} has no integer schema_version", rel))
                continue
            checked += 1
            current = jsonio.current_version(schemas[_schema_for(doc, claimants[rel], schemas)])
            if found > current:
                results.append(Result("fail", _newer(where, found, current), rel))
            elif found < current and not is_log:
                results.append(Result("fail", _older(where, found, current, rel), rel))
    return results, checked


@check(id="schema_versions", owner=OWNER)
def schema_versions(ctx):
    results, registered = _registry_results(ctx)
    claimed, count = _claimed_results(ctx, skip=registered)
    total = len(registered) + count
    if not total and not claimed:
        return [Result("skip", "No versioned JSON documents in this instance.")]
    return results + claimed or [Result("pass", f"{total} document(s) and log line(s) are at a version this coach "
                                                "reads.")]


@check(id="dangling_exercise_ids", owner=OWNER)
def dangling_exercise_ids(ctx):
    lib = _library(ctx)
    if lib is None:
        return [_BAD_LIBRARY]
    found = _overlays(ctx, live_only=False)
    if not found:
        return _no_overlays(live_only=False)
    results = []
    for rel, doc in found:
        for where, session, line in _lines(doc):
            if lib.get(line["exercise_id"]) is None:
                results.append(Result("fail", (
                    f"{rel} {where}.exercise_id: {line['exercise_id']} in {session['session_id']} on "
                    f"{session['date']} is not in the exercise library; fix the id, or add a custom_ entry to "
                    f"{paths.EXERCISES}"
                ), rel))
    return results


@check(id="dangling_routine_ids", owner=OWNER)
def dangling_routine_ids(ctx):
    if not ctx.config.hevy.enabled:
        return [Result("skip", "Hevy is turned off in config.toml.")]
    cache_dir = (paths.CACHE_ROOT / "cache").as_posix()
    if not (ctx.root / cache_dir).is_dir():
        return [Result("skip", f"No {cache_dir}/ yet; run python3 -m coach hevy pull.")]
    cache_path = (paths.HEVY_CACHE_DIR / "routines.json").as_posix()
    try:
        cached = HevyCache(ctx.root).read("routines")
    except ValidationError as exc:
        return [Result("warn", f"Cannot read the routine cache: {exc.message}", cache_path)]
    if cached is None:
        return [Result("skip", "There is no Hevy routine cache yet; run python3 -m coach hevy pull.", cache_path)]
    found = _overlays(ctx, live_only=True)
    if not found:
        return _no_overlays(live_only=True)
    known = {routine.get("id") for routine in cached["data"]}
    results = []
    for rel, doc in found:
        for s_index, session in enumerate(doc["sessions"]):
            routine_id = session["hevy_routine_id"]
            if routine_id is not None and routine_id not in known:
                results.append(Result("fail", (
                    f"{rel} $.sessions[{s_index}].hevy_routine_id: {session['session_id']} on {session['date']} "
                    f"names Hevy routine {routine_id}, which is not in {cache_path}; run python3 -m coach hevy pull, "
                    "and if the routine is gone, rebuild the overlay with the right routine"
                ), rel))
    return results


@check(id="overlay_library_consistency", owner=OWNER)
def overlay_library_consistency(ctx):
    lib = _library(ctx)
    if lib is None:
        return [_BAD_LIBRARY]
    found = _overlays(ctx, live_only=True)
    if not found:
        return _no_overlays(live_only=True)
    results = []
    for rel, doc in found:
        for where, session, line in _lines(doc):
            exercise_id = line["exercise_id"]
            entry = lib.get(exercise_id)
            if entry is None:
                continue
            confirmed = lib.effective_load_mode(exercise_id)
            if confirmed is not None and confirmed != line["load_mode"]:
                results.append(Result("fail", (
                    f"{rel} {where}.load_mode: {exercise_id} in {session['session_id']} is {line['load_mode']}, "
                    f"but the library's confirmed load mode is {confirmed}; rebuild the overlay, or correct the "
                    f"library with python3 -m coach library set-mode {exercise_id} MODE"
                ), rel))
            template_id = line["hevy_template_id"]
            if template_id is not None and template_id not in entry["hevy_template_ids"]:
                owner = lib.by_hevy_template_id(template_id)
                held = f"which the library gives to {owner['id']}" if owner else "which no library entry holds"
                results.append(Result("fail", (
                    f"{rel} {where}.hevy_template_id: {exercise_id} in {session['session_id']} names Hevy "
                    f"template {template_id}, {held}; fix the overlay line or the library entry"
                ), rel))
    return results


def cap_for(config, exercise_id, mode, location):
    """(cap, where it comes from) in athlete units, or (None, None) when nothing caps the line."""
    caps = config.get("caps") or {}
    if exercise_id in caps:
        return caps[exercise_id], f"[caps] {exercise_id}"
    if mode in units.PER_HAND_MODES:
        table = f"[equipment.locations.{location}]" if location else "[equipment]"
        return equipment_for(config, location)["dumbbell_max"], f"{table} dumbbell_max"
    return None, None


def _capped_value(load):
    return load["per_hand"] if load["mode"] in units.PER_HAND_MODES else load["hevy_total"]


@check(id="load_caps", owner=OWNER)
def load_caps(ctx):
    config = ctx.config
    unit = config.athlete.units
    found = _overlays(ctx, live_only=True)
    if not found:
        return _no_overlays(live_only=True)
    results = []
    for rel, doc in found:
        for where, session, line in _lines(doc):
            try:
                cap, source = cap_for(config, line["exercise_id"], line["load_mode"], session["location"])
            except ConfigError:
                continue
            if cap is None:
                continue
            sound = [s["load"] for s in line["sets"]
                     if s.get("load") and s["load"]["unit"] == unit and not units.check_load(s["load"])]
            over = [load for load in sound if _capped_value(load) > cap]
            if not over:
                continue
            heaviest = max(over, key=_capped_value)
            per_hand = " per hand" if line["load_mode"] in units.PER_HAND_MODES else ""
            results.append(Result("fail", (
                f"{rel} {where}: {line['exercise_id']} in {session['session_id']} on {session['date']} is "
                f"{units.format_load(heaviest)} ({len(over)} set(s) over), above the {source} cap of "
                f"{units.json_number(cap)} {unit}{per_hand}"
            ), rel))
    return results


def _git(ctx, *argv):
    env = dict(os.environ)
    env.update(ctx.env)
    return subprocess.run(["git", "-C", str(ctx.root), *argv], capture_output=True, text=True, env=env, timeout=30)


@check(id="env_untracked", owner=OWNER)
def env_untracked(ctx):
    where = paths.ENV_FILE.as_posix()
    if shutil.which("git") is None:
        return [Result("skip", "git is not installed, so .env cannot be checked.", where)]
    inside = _git(ctx, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return [Result("skip", "The instance is not a git working tree.", where)]
    if _git(ctx, "ls-files", "--error-unmatch", "--", where).returncode == 0:
        return [Result("fail", (
            ".env is tracked by git, so the Hevy API key is in the repository; run git rm --cached .env, "
            "make sure .gitignore lists .env, and rotate the key in Hevy if this repository was ever pushed"
        ), where)]
    ignored = _git(ctx, "check-ignore", "-q", "--", where)
    if ignored.returncode == 128:
        return [Result("skip", f"git check-ignore failed: {ignored.stderr.strip()}", where)]
    if ignored.returncode != 0:
        if (ctx.root / where).exists():
            return [Result("fail", ".env is not ignored by git, so a commit could include the Hevy API key; "
                                   "add .env to .gitignore", where)]
        return [Result("warn", "No .env yet, but .gitignore does not list .env; add it before creating one.",
                       where)]
    return [Result("pass", ".env is untracked and ignored by git.", where)]


@dataclass(frozen=True)
class Figure:
    text: str
    start: int
    end: int
    unit: bool
    two_number: bool
    rpe: bool


_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\d)")
_RANGE_OR_DATE_BEFORE = re.compile(r"\d\s*[-–—]\s*$|\d:$")
_RANGE_OR_DATE_AFTER = re.compile(r"\s*[-–—]\s*\d|:\d")
_SETS_BY_REPS_BEFORE = re.compile(r"\d\s*[×xX*]\s*$")
_SETS_BY_REPS_AFTER = re.compile(r"\s*[×xX*]\s*\d")
_EXPLICIT_HEVY_BEFORE = re.compile(r"hevy\s*[:=]?\s*$", re.IGNORECASE)
_RPE_BEFORE = re.compile(r"(?:rpe|rir)\s*[:@]?\s*$", re.IGNORECASE)
_NOT_A_LOAD_AFTER = re.compile(
    r"\s*(?:%|(?:reps?|sets?|s|secs?|seconds?|mins?|minutes?|h|hrs?|hours?|days?|weeks?|wks?|m|km|cm|mm|kcal|g)"
    r"(?![A-Za-z]))",
    re.IGNORECASE,
)
_UNIT_AFTER = re.compile(r"\s*(?:kgs?|lbs?|kilos?|pounds?)(?![A-Za-z])", re.IGNORECASE)
_PER_HAND_AFTER = re.compile(r"\s*(?:/\s*hand|per\s+hand|each\s+hand|a\s+hand|each)(?![A-Za-z])", re.IGNORECASE)
_HEVY_AFTER = re.compile(r"\s*\(\s*hevy\b[^)]*\)", re.IGNORECASE)
_ARROW = re.compile(r"\s*(?:→|->|=>|⇒)\s*")


def _figures(text):
    figures = []
    for match in _NUMBER.finditer(text):
        before, after = text[:match.start()], text[match.end():]
        if (_RANGE_OR_DATE_BEFORE.search(before) or _RANGE_OR_DATE_AFTER.match(after)
                or _SETS_BY_REPS_BEFORE.search(before) or _SETS_BY_REPS_AFTER.match(after)
                or _EXPLICIT_HEVY_BEFORE.search(before) or _NOT_A_LOAD_AFTER.match(after)):
            continue
        end = match.end()
        unit = _UNIT_AFTER.match(text, end)
        if unit:
            end = unit.end()
        text_end = end
        hand = _PER_HAND_AFTER.match(text, end)
        if hand:
            end = hand.end()
        hevy = _HEVY_AFTER.match(text, end)
        if hevy:
            end = hevy.end()
        figures.append(Figure(text=text[match.start():text_end], start=match.start(), end=end, unit=bool(unit),
                              two_number=bool(hand or hevy), rpe=bool(_RPE_BEFORE.search(before))))
    return figures


def _chains(text, figures):
    chains = []
    for figure in figures:
        if chains and _ARROW.fullmatch(text[chains[-1][-1].end:figure.start]):
            chains[-1].append(figure)
        else:
            chains.append([figure])
    return chains


def bare_figures(text, load_column=False):
    """The load figures in `text` that, for a two-dumbbell exercise, give one number where two are needed.

    A load figure carries a weight unit, sits in a load column, or is part
    of an arrow chain (`45 → 50`). It is in the two-number form when it, or
    another figure in its chain, says per hand or gives the Hevy value.
    """
    bare = []
    for chain in _chains(text, _figures(text)):
        if any(f.two_number or f.rpe for f in chain):
            continue
        bare += [f for f in chain if f.unit or load_column or len(chain) > 1]
    return bare


def _bare_message(rel, where, figures, exercise, text):
    listed = ", ".join(repr(figure.text) for figure in figures)
    what = "is a bare dumbbell number" if len(figures) == 1 else "are bare dumbbell numbers"
    return (f"{rel} {where}: {listed} for {exercise} {what} in {text.strip()!r}; "
            f"write the per-hand load and the Hevy value, as in {TWO_NUMBER_EXAMPLE}")


def _overlay_text(line):
    for field in OVERLAY_TEXT_FIELDS:
        if line.get(field):
            yield field, line[field]
    if line.get("override"):
        yield "override.reason", line["override"]["reason"]


class _Mentions:
    """Finds exercise names in prose and the load mode each one implies."""

    _GENERIC = {"dumbbell": PER_HAND_X2, "dumbbells": PER_HAND_X2, "db": PER_HAND_X2, "dbs": PER_HAND_X2}

    def __init__(self, lib):
        modes = {}
        for entry in lib.entries():
            mode = entry["effective_load_mode"] or entry["load_mode_default"]
            for phrase in (entry["name"], *entry["aliases"], *entry["hevy_titles"], entry["id"]):
                modes.setdefault(self._key(phrase), (entry["id"], mode))
        for word, mode in self._GENERIC.items():
            modes.setdefault(word, (word, mode))
        self._modes = modes
        alternatives = sorted(modes, key=len, reverse=True)
        body = "|".join(r"\s+".join(re.escape(token) for token in phrase.split()) for phrase in alternatives)
        self._pattern = re.compile(rf"(?<![A-Za-z0-9_])(?:{body})(?![A-Za-z0-9_])", re.IGNORECASE)

    @staticmethod
    def _key(phrase):
        return " ".join(phrase.lower().split())

    def find(self, text):
        """[(start, end, exercise, mode)] in order."""
        return [(m.start(), m.end(), *self._modes[self._key(m.group(0))]) for m in self._pattern.finditer(text)]


def _attribute(position, mentions, carried):
    before = [m for m in mentions if m[1] <= position]
    return before[-1] if before else carried


_REGION = re.compile(r"<!-- coach:begin ([a-z-]+) (\S+) -->.*?<!-- coach:end \1 \2 -->", re.DOTALL)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_LOAD_HEADER = re.compile(r"\b(?:load|weight|kgs?|lbs?)\b", re.IGNORECASE)
_PER_HAND_HEADER = re.compile(r"/\s*hand\b|\bper\s+hand\b|\beach\b", re.IGNORECASE)
_HEVY_HEADER = re.compile(r"\bhevy\b", re.IGNORECASE)
_EXERCISE_HEADER = re.compile(r"\b(?:exercises?|lifts?|movements?)\b", re.IGNORECASE)


def _without_regions(text):
    return _REGION.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _cells(line):
    """(start, end) of each cell in a markdown table row."""
    bars = [m.start() for m in re.finditer(r"(?<!\\)\|", line)]
    return list(zip(bars, bars[1:]))


@dataclass(frozen=True)
class _Table:
    """What a markdown table's header says about its columns."""

    load: frozenset = frozenset()
    per_hand: frozenset = frozenset()
    hevy: frozenset = frozenset()
    exercise: int = 0

    @classmethod
    def from_header(cls, line):
        headers = [line[a + 1:b] for a, b in _cells(line)]
        hevy = {i for i, h in enumerate(headers) if _HEVY_HEADER.search(h)}
        named = [i for i, h in enumerate(headers) if _EXERCISE_HEADER.search(h)]
        return cls(load=frozenset(i for i, h in enumerate(headers) if _LOAD_HEADER.search(h) and i not in hevy),
                   per_hand=frozenset(i for i, h in enumerate(headers) if _PER_HAND_HEADER.search(h)),
                   hevy=frozenset(hevy), exercise=named[0] if named else 0)


def _row_figures(line, table):
    """[(figure, offset in line)] for the bare figures in a table row."""
    cells = [(i, a + 1, b) for i, (a, b) in enumerate(_cells(line))]
    paired = any(i in table.hevy and re.search(r"\d", line[a:b]) for i, a, b in cells)
    found = []
    for column, start, end in cells:
        if column in table.hevy or column in table.per_hand or (paired and column in table.load):
            continue
        found += [(f, start + f.start) for f in bare_figures(line[start:end], load_column=column in table.load)]
    return found


def _prose_results(rel, text, mentions):
    results = []
    lines = _without_regions(text).split("\n")
    table, carried = None, None
    for number, line in enumerate(lines, 1):
        is_row = line.lstrip().startswith("|")
        if not is_row:
            table, carried = None, None
        if is_row and _TABLE_SEPARATOR.match(line):
            continue
        if is_row and table is None:
            following = lines[number] if number < len(lines) else ""
            if _TABLE_SEPARATOR.match(following):
                table = _Table.from_header(line)
                continue
            table = _Table()
        found = mentions.find(line)
        if is_row:
            cells = _cells(line)
            name_cell = ""
            if table.exercise < len(cells):
                a, b = cells[table.exercise]
                name_cell = line[a + 1:b]
            if name_cell.strip():
                named = mentions.find(name_cell)
                carried = named[-1] if named else None
            figures = _row_figures(line, table)
        else:
            figures = [(f, f.start) for f in bare_figures(line)]
        bare = {}
        for figure, position in figures:
            mention = _attribute(position, found, carried if is_row else None)
            if mention and mention[3] == PER_HAND_X2:
                bare.setdefault(mention[2], []).append(figure)
        for exercise, listed in bare.items():
            results.append(Result("fail", _bare_message(rel, f"line {number}", listed, exercise, line), rel))
    return results


def _prose_files(ctx):
    files = [ctx.root / paths.PROFILE]
    checkins = ctx.root / paths.CHECKINS_DIR
    if checkins.is_dir():
        files += sorted(checkins.glob("*.md"))
    return [path for path in files if path.is_file()]


@check(id="bare_hevy_values", owner=OWNER)
def bare_hevy_values(ctx):
    results = []
    for rel, doc in _overlays(ctx, live_only=True):
        for where, session, line in _lines(doc):
            if line["load_mode"] != PER_HAND_X2:
                continue
            for field, text in _overlay_text(line):
                figures = bare_figures(text)
                if figures:
                    results.append(Result("fail", _bare_message(rel, f"{where}.{field}", figures,
                                                                line["exercise_id"], text), rel))
    prose = _prose_files(ctx)
    if prose:
        mentions = _Mentions(_library(ctx) or Library())
        for path in prose:
            results += _prose_results(_rel(ctx, path), path.read_text(encoding="utf-8"), mentions)
    return results


@functools.lru_cache(maxsize=None)
def _module_functions(name):
    """Every function called `name` defined in a top-level coach module."""
    found = []
    for info in pkgutil.iter_modules(coach.__path__):
        if info.ispkg or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"coach.{info.name}")
        function = getattr(module, name, None)
        if callable(function) and getattr(function, "__module__", None) == module.__name__:
            found.append(function)
    return tuple(found)


def _render_card(root, slug):
    """C11's `render_card(root, id)`: coach.recipes renders a region from a loaded card, not from an id."""
    return recipes.render_card_region(recipes.load_card(Path(root) / paths.MENU_DIR / f"{slug}.md"))


_REGION_ADAPTERS = {"card": _render_card}
# Where each kind's own freshness check already looks; the sweep leaves those regions to it.
_OWNER_CHECKED = {
    "overlay": lambda rel, region_id: PurePosixPath(rel).parent == paths.CHECKINS_DIR,
    "research": lambda rel, region_id: rel == research.note_path(region_id),
    "card": lambda rel, region_id: rel == (paths.MENU_DIR / f"{region_id}.md").as_posix(),
}
_KIND_MARKER = re.compile(r"<!-- coach:begin ([a-z-]+) \S+ -->")


def region_renderer(kind):
    found = _module_functions(f"render_{kind.replace('-', '_')}")
    return found[0] if found else _REGION_ADAPTERS.get(kind)


def _markdown_files(root):
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(d for d in subdirs if not d.startswith("."))
        for name in sorted(files):
            if name.endswith(".md"):
                yield Path(directory) / name


def _framework_files(ctx):
    """The paths tracked at the template commit /framework-sync last synced to; empty when that is unknown."""
    try:
        commit = json.loads((ctx.root / FRAMEWORK_SYNC_MARKER).read_text(encoding="utf-8"))["template_commit"]
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()
    if not isinstance(commit, str) or not commit or commit.startswith("-") or shutil.which("git") is None:
        return frozenset()
    listed = _git(ctx, "ls-tree", "-r", "-z", "--name-only", commit, "--")
    if listed.returncode != 0:
        return frozenset()
    return frozenset(name for name in listed.stdout.split("\0") if name)


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?!`)(?:(?!\n[ \t]*\n).)+?(?<!`)\1(?!`)", re.DOTALL)
_ANY_MARKER = re.compile(r"<!-- coach:(?:begin|end) [a-z-]+ \S+ -->")


def _blank(text):
    return re.sub(r"[^\n]", " ", text)


def _live_markup(text):
    """`text` with code blocks, code spans and markers that do not start their line blanked, offsets kept.

    Framework docs show region markers as examples inside code; those are not regions.
    """
    lines, fence = text.split("\n"), None
    for index, line in enumerate(lines):
        opening = _FENCE.match(line)
        if fence is None and opening:
            fence = opening.group(1)
            lines[index] = _blank(line)
        elif fence is not None:
            if opening and opening.group(1)[0] == fence[0] and len(opening.group(1)) >= len(fence) \
                    and not line[opening.end():].strip():
                fence = None
            lines[index] = _blank(line)
    text = _CODE_SPAN.sub(lambda m: _blank(m.group(0)), "\n".join(lines))
    out, position = [], 0
    for match in _ANY_MARKER.finditer(text):
        indent = text[text.rfind("\n", 0, match.start()) + 1:match.start()]
        if len(indent) > 3 or indent.strip():
            out += [text[position:match.start()], _blank(match.group(0))]
            position = match.end()
    return "".join(out) + text[position:]


def _region_results(ctx, rel, text):
    results, checked = [], 0
    live = _live_markup(text)
    for kind in sorted(set(_KIND_MARKER.findall(live))):
        try:
            regions = render.find_regions(live, kind)
        except ValueError as exc:
            results.append(Result("fail", f"{rel}: {exc}", rel))
            continue
        owner_checked = _OWNER_CHECKED.get(kind, lambda rel, region_id: False)
        regions = [r for r in regions if not owner_checked(rel, r[0])]
        if not regions or kind in SNAPSHOT_KINDS:
            continue
        renderer = region_renderer(kind)
        if renderer is None:
            results.append(Result("warn", f"{rel} has a {kind} region, and no coach renderer knows that kind", rel))
            continue
        for region_id, start, end in regions:
            checked += 1
            try:
                fresh = renderer(ctx.root, region_id)
            except (ValidationError, ValueError, OSError) as exc:
                message = exc.message if isinstance(exc, ValidationError) else str(exc)
                results.append(Result("warn", f"{rel}: the {kind} {region_id} region cannot be rendered: {message}",
                                      rel))
                continue
            if text[start:end] != fresh:
                results.append(Result("fail", (
                    f"{rel}: the {kind} {region_id} region differs from a fresh render; it was edited by hand or "
                    "its data changed. Edit the data, then re-render the region with its coach command"
                ), rel))
    return results, checked


@check(id="render_fresh_sweep", owner=OWNER)
def render_fresh_sweep(ctx):
    results, checked = [], 0
    framework = _framework_files(ctx)
    for path in _markdown_files(ctx.root):
        rel = _rel(ctx, path)
        if rel.startswith("tests/") or rel in framework:
            continue
        found, count = _region_results(ctx, rel, path.read_bytes().decode("utf-8"))
        results += found
        checked += count
    return results or [Result("pass", f"{checked} rendered region(s) outside their owners' checks are fresh.")]
