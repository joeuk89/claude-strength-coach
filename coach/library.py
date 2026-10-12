"""The exercise library: the builtin catalogue merged with the instance file.

The catalogue (`coach/catalogue/exercises.json`) ships with the framework.
The instance file (`data/exercises.json`) holds the athlete's overrides,
custom entries, confirmed load modes and avoided exercises; sync never
touches it. Only the catalogue says which apparatus an exercise `requires`
and whether it needs demonstrated `ability`. See contract C5 ("Exercise
library") and C54.
"""

import copy
import functools
import re
from pathlib import Path

from coach import jsonio, paths
from coach.errors import ValidationError

PATTERNS = (
    "squat", "hinge", "lunge", "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull",
    "elbow_flexion", "elbow_extension", "shoulder_raise", "knee_flexion", "knee_extension", "hip_abduction",
    "hip_adduction", "calf_raise", "core", "carry", "conditioning",
)
MUSCLES = (
    "abdominals", "front_delts", "side_delts", "rear_delts", "biceps", "triceps", "forearms", "quadriceps",
    "hamstrings", "calves", "glutes", "abductors", "adductors", "lats", "upper_back", "traps", "lower_back",
    "chest", "cardio", "neck", "full_body", "other",
)
EQUIPMENT = (
    "barbell", "ez_bar", "trap_bar", "dumbbell", "kettlebell", "machine", "smith_machine", "cable", "plate",
    "band", "suspension", "bodyweight", "cardio_machine", "other",
)
APPARATUS = ("flat_bench", "incline_bench", "pull_up_bar", "dip_station", "nordic_anchor", "box")
APPARATUS_SERVES = {"flat_bench": ("box",), "incline_bench": ("box",)}
DEMONSTRATED = "demonstrated"

CATALOGUE_PATH = Path(__file__).resolve().parent / "catalogue" / "exercises.json"
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")
CUSTOM_PREFIX = "custom_"
CATALOGUE_FIELDS = (
    "name", "aliases", "hevy_titles", "hevy_template_ids", "muscles", "pattern", "equipment",
    "load_mode_default", "increment", "substitutes",
)
INSTANCE_FIELDS = ("hevy_template_id", "load_mode", "load_mode_proposed", "confidence", "avoid")
CUSTOM_REQUIRED = ("name", "muscles", "pattern", "equipment", "load_mode_default")
_CUSTOM_DEFAULTS = {"aliases": [], "hevy_titles": [], "hevy_template_ids": [], "increment": None, "substitutes": []}
_NAMING_FIELDS = ("name", "aliases", "hevy_titles")

_SYNONYMS = {"db": "dumbbell", "bb": "barbell", "kb": "kettlebell", "pullup": "pull up", "chinup": "chin up",
             "pushup": "push up", "biceps": "bicep", "tricep": "triceps"}


def tokens(text):
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return " ".join(_SYNONYMS.get(word, word) for word in words).split()


def match_key(text):
    """The form two exercise names are compared in: "Bench Press (Dumbbell)" equals "dumbbell bench press"."""
    return " ".join(sorted(tokens(text)))


def empty_instance():
    return {"schema_version": 1, "exercises": {}}


@functools.lru_cache(maxsize=1)
def needs_demonstrated_ids():
    """Catalogue ids an athlete must have shown they can do before a swap picks them."""
    return tuple(entry["id"] for entry in _catalogue_entries() if entry.get("ability") == DEMONSTRATED)


@functools.lru_cache(maxsize=1)
def _catalogue_entries():
    return tuple(jsonio.read_doc(CATALOGUE_PATH, "exercise_catalogue")["exercises"])


def catalogue():
    """The builtin catalogue entries, in file order (copies)."""
    return copy.deepcopy(list(_catalogue_entries()))


def jsonpath(*parts):
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", part):
            path += f".{part}"
        else:
            path += f"[{part!r}]"
    return path


class Library:
    """The merged library. Build it with `Library.load(root)` or `Library(instance_doc)`."""

    def __init__(self, instance_doc=None, path=None):
        self.instance = copy.deepcopy(instance_doc) if instance_doc is not None else empty_instance()
        self.path = path
        self._catalogue = {entry["id"]: entry for entry in _catalogue_entries()}
        errors = self._merge()
        if errors:
            where = path or "the instance library"
            raise ValidationError(f"{where} is not a valid exercise library ({len(errors)} problem(s))", details=errors)

    @classmethod
    def load(cls, root):
        path = Path(root) / paths.EXERCISES
        if not path.exists():
            return cls(None, path)
        return cls(jsonio.read_doc(path, "exercise_library"), path)

    def _merge(self):
        errors = []
        own = self.instance["exercises"]
        self._entries = {}
        for exercise_id, base in self._catalogue.items():
            self._entries[exercise_id] = self._merged(exercise_id, base, own.get(exercise_id, {}), "catalogue")
        for exercise_id in sorted(own):
            if exercise_id in self._catalogue:
                continue
            where = jsonpath("exercises", exercise_id)
            if not ID_PATTERN.match(exercise_id):
                errors.append({"path": where, "message": f"an exercise id must match {ID_PATTERN.pattern}"})
                continue
            if not exercise_id.startswith(CUSTOM_PREFIX):
                errors.append({"path": where, "message": (
                    f"{exercise_id} is not in the catalogue; a custom exercise's id starts {CUSTOM_PREFIX}"
                )})
                continue
            missing = [name for name in CUSTOM_REQUIRED if name not in own[exercise_id]]
            if missing:
                errors.append({"path": where, "message": f"a custom exercise needs: {', '.join(missing)}"})
                continue
            self._entries[exercise_id] = self._merged(exercise_id, _CUSTOM_DEFAULTS, own[exercise_id], "custom")
        if not errors:
            errors = self._cross_check()
        return errors

    @staticmethod
    def _merged(exercise_id, base, own, source):
        entry = {"id": exercise_id}
        for name in CATALOGUE_FIELDS:
            entry[name] = copy.deepcopy(own[name] if name in own else base[name])
        for name in INSTANCE_FIELDS:
            entry[name] = copy.deepcopy(own.get(name))
        template_id = entry["hevy_template_id"]
        if template_id is not None and template_id not in entry["hevy_template_ids"]:
            entry["hevy_template_ids"].append(template_id)
        entry["requires"] = list(base.get("requires", [])) if source == "catalogue" else []
        entry["ability"] = base.get("ability") if source == "catalogue" else None
        entry["source"] = source
        entry["overridden"] = sorted(name for name in CATALOGUE_FIELDS if name in own and source == "catalogue")
        entry["effective_load_mode"] = entry["load_mode"]
        return entry

    def _own_fields(self, exercise_id):
        return self.instance["exercises"].get(exercise_id, {})

    def _cross_check(self):
        errors = []
        own_ids = sorted(self.instance["exercises"])
        for exercise_id in own_ids:
            for index, substitute in enumerate(self._own_fields(exercise_id).get("substitutes", [])):
                if substitute not in self._entries or substitute == exercise_id:
                    errors.append({"path": jsonpath("exercises", exercise_id, "substitutes", index),
                                   "message": f"substitute {substitute!r} is not another library exercise"})

        names = {}
        for entry in self._entries.values():
            own = self._own_fields(entry["id"])
            for field in _NAMING_FIELDS:
                if field not in own:
                    for text in _texts(entry, field):
                        names.setdefault(match_key(text), entry["id"])
        for exercise_id in own_ids:
            own = self._own_fields(exercise_id)
            for field in _NAMING_FIELDS:
                if field not in own:
                    continue
                for index, text in enumerate(_texts(own, field)):
                    owner = names.setdefault(match_key(text), exercise_id)
                    if owner != exercise_id:
                        path = jsonpath("exercises", exercise_id, field) if field == "name" else \
                            jsonpath("exercises", exercise_id, field, index)
                        errors.append({"path": path, "message": f"{text!r} already names {owner}"})

        owners = {}
        for entry in self._entries.values():
            if entry["id"] in self.instance["exercises"]:
                continue
            for template_id in entry["hevy_template_ids"]:
                owners.setdefault(template_id, entry["id"])
        for exercise_id in own_ids:
            entry = self._entries.get(exercise_id)
            if entry is None:
                continue
            for template_id in entry["hevy_template_ids"]:
                owner = owners.setdefault(template_id, exercise_id)
                if owner != exercise_id:
                    field = "hevy_template_id" if template_id == entry["hevy_template_id"] else "hevy_template_ids"
                    errors.append({"path": jsonpath("exercises", exercise_id, field),
                                   "message": f"Hevy template {template_id} already belongs to {owner}"})
        return errors

    def ids(self):
        return list(self._entries)

    def entries(self):
        return [copy.deepcopy(entry) for entry in self._entries.values()]

    def get(self, exercise_id):
        entry = self._entries.get(exercise_id)
        return copy.deepcopy(entry) if entry is not None else None

    def by_hevy_template_id(self, template_id):
        for entry in self._entries.values():
            if entry["hevy_template_id"] == template_id:
                return copy.deepcopy(entry)
        for entry in self._entries.values():
            if template_id in entry["hevy_template_ids"]:
                return copy.deepcopy(entry)
        return None

    def match_title(self, title):
        """(entry, "hevy_title" | "alias") for a Hevy exercise title, or (None, None)."""
        key = match_key(title)
        for field, matched_by in (("hevy_titles", "hevy_title"), ("aliases", "alias"), ("name", "alias")):
            for entry in self._entries.values():
                if any(match_key(text) == key for text in _texts(entry, field)):
                    return copy.deepcopy(entry), matched_by
        return None, None

    def search(self, text):
        query = tokens(text)
        if not query:
            return []
        key = match_key(text)
        ranked = []
        for entry in self._entries.values():
            texts = [entry["name"], *entry["aliases"], *entry["hevy_titles"], entry["id"].replace("_", " ")]
            best = None
            for candidate in texts:
                words = tokens(candidate)
                if all(any(word.startswith(part) for word in words) for part in query):
                    rank = (0 if match_key(candidate) == key else 1, len(words))
                    best = rank if best is None else min(best, rank)
            if best is not None:
                ranked.append((best, entry["id"]))
        ranked.sort()
        return [summary(self._entries[exercise_id]) for _, exercise_id in ranked]

    def effective_load_mode(self, exercise_id):
        """The athlete's confirmed load mode, or None when it has not been confirmed."""
        entry = self._entries.get(exercise_id)
        return entry["load_mode"] if entry else None

    def increment(self, exercise_id, unit):
        """The entry's progression step in `unit` (per hand for per-hand modes), or None.

        None means the entry carries no load or names no step; callers then use
        the equipment increment from config.
        """
        entry = self._entries.get(exercise_id)
        if entry is None or entry["increment"] is None:
            return None
        return entry["increment"][unit]

    def avoided(self, exercise_id):
        entry = self._entries.get(exercise_id)
        return copy.deepcopy(entry["avoid"]) if entry else None


def _texts(entry, field):
    value = entry.get(field)
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def summary(entry):
    """The short form `library list` and `library search` print."""
    return {key: copy.deepcopy(entry[key]) for key in (
        "id", "name", "pattern", "equipment", "load_mode_default", "effective_load_mode", "source", "avoid")}


_TYPE_MODES = {
    "duration": "duration",
    "distance_duration": "distance",
    "bodyweight_assisted_reps": "assisted",
    "bodyweight_reps": "bodyweight",
}
_HAND_HELD = ("dumbbell", "kettlebell")
_ONE_ARM = (("single", "arm"), ("one", "arm"), ("1", "arm"))
_ALTERNATING = ("alternating", "alternate", "alt")
_MODES_BY_HEVY_EQUIPMENT = {
    "dumbbell": ("per_hand_x2", "single_implement"),
    "kettlebell": ("per_hand_x2", "single_implement"),
    "barbell": ("total",),
    "plate": ("total",),
    "machine": ("total", "assisted"),
    "none": ("bodyweight", "assisted", "duration", "distance"),
    "resistance_band": ("band",),
}
_FALLBACK_MODE = {
    "dumbbell": "per_hand_x2", "kettlebell": "single_implement", "resistance_band": "band",
    "none": "bodyweight", "suspension": "bodyweight",
}
_EQUIPMENT_FROM_HEVY = {
    "none": "bodyweight", "barbell": "barbell", "dumbbell": "dumbbell", "kettlebell": "kettlebell",
    "machine": "machine", "plate": "plate", "resistance_band": "band", "suspension": "suspension", "other": "other",
}
_PATTERN_FROM_MUSCLE = {
    "chest": "horizontal_push", "shoulders": "vertical_push", "triceps": "elbow_extension",
    "biceps": "elbow_flexion", "forearms": "elbow_flexion", "lats": "vertical_pull",
    "upper_back": "horizontal_pull", "traps": "shoulder_raise", "lower_back": "hinge", "glutes": "hinge",
    "hamstrings": "knee_flexion", "quadriceps": "squat", "calves": "calf_raise", "abductors": "hip_abduction",
    "adductors": "hip_adduction", "abdominals": "core", "neck": "core", "cardio": "conditioning",
    "full_body": "conditioning", "other": "conditioning",
}


def _has_run(words, run):
    return any(tuple(words[i:i + len(run)]) == run for i in range(len(words)))


def propose(lib, template_id, title, template):
    """Match one Hevy exercise to the library and propose its load mode (contract C5, seed table).

    `template` is the cached Hevy exercise template, or None when the cache
    lacks it. Returns hevy_template_id, hevy_title, matched_id, matched_by,
    load_mode_proposed, confidence and rule.
    """
    template = template or {}
    hevy_type = template.get("type")
    hevy_equipment = template.get("equipment")
    entry, matched_by = lib.by_hevy_template_id(template_id), "template_id"
    if entry is None:
        entry, matched_by = lib.match_title(title)
    words = tokens(title)
    equipment = hevy_equipment if hevy_equipment in _EQUIPMENT_FROM_HEVY else None
    hand_held = equipment in _HAND_HELD if equipment else (entry or {}).get("equipment") in _HAND_HELD

    def result(mode, confidence, rule):
        return {
            "hevy_template_id": template_id, "hevy_title": title,
            "matched_id": entry["id"] if entry else None, "matched_by": matched_by if entry else None,
            "load_mode_proposed": mode, "confidence": confidence, "rule": rule,
        }

    if hevy_type in _TYPE_MODES or hevy_type == "reps_only":
        mode = _TYPE_MODES.get(hevy_type)
        if mode is None:
            band = hevy_equipment == "resistance_band" or (entry or {}).get("load_mode_default") == "band"
            mode = "band" if band else "bodyweight"
        agrees = entry is None or entry["load_mode_default"] == mode
        return result(mode, "high" if agrees else "low", "hevy_type")
    if hand_held and any(word in _ALTERNATING for word in words):
        return result("single_implement", "high", "alternating")
    if hand_held and any(_has_run(words, run) for run in _ONE_ARM):
        return result("single_implement", "high", "one_arm")
    if entry is not None and entry["source"] == "custom":
        return result(entry["load_mode_default"], "low", "custom")
    if entry is not None and matched_by in ("template_id", "hevy_title"):
        mode = entry["load_mode_default"]
        consistent = mode in _MODES_BY_HEVY_EQUIPMENT.get(equipment, (mode,))
        return result(mode, "high" if consistent else "low", "matched")
    if entry is not None:
        return result(entry["load_mode_default"], "low", "alias")
    return result(_FALLBACK_MODE.get(equipment, "total"), "low", "equipment")


def _muscle(hevy_name, title):
    if hevy_name == "shoulders":
        words = tokens(title)
        if "rear" in words or "reverse" in words:
            return "rear_delts"
        if "lateral" in words or "side" in words:
            return "side_delts"
        return "front_delts"
    return hevy_name if hevy_name in MUSCLES else "other"


def custom_id(title, taken):
    slug = "_".join(tokens(title)) or "exercise"
    base = CUSTOM_PREFIX + re.sub(r"[^a-z0-9_]", "", slug)
    candidate, suffix = base, 2
    while candidate in taken:
        candidate, suffix = f"{base}_{suffix}", suffix + 1
    return candidate


def custom_entry(template_id, title, template, load_mode):
    """An instance entry for a Hevy exercise the catalogue lacks, with fields taken from its template.

    Pattern and the front/side/rear delt split are guesses from Hevy's
    muscle groups and the title; the seed command reports them.
    """
    template = template or {}
    primary_hevy = template.get("primary_muscle_group") or "other"
    primary = _muscle(primary_hevy, title)
    secondary = []
    for name in template.get("secondary_muscle_groups") or []:
        muscle = _muscle(name, title)
        if muscle != primary and muscle not in secondary:
            secondary.append(muscle)
    equipment = _EQUIPMENT_FROM_HEVY.get(template.get("equipment"), "other")
    if equipment == "machine" and primary_hevy == "cardio":
        equipment = "cardio_machine"
    return {
        "name": title,
        "aliases": [],
        "hevy_titles": [title],
        "hevy_template_ids": [],
        "muscles": {"primary": [primary], "secondary": secondary},
        "pattern": _PATTERN_FROM_MUSCLE.get(primary_hevy, "conditioning"),
        "equipment": equipment,
        "load_mode_default": load_mode,
        "increment": None,
        "substitutes": [],
        "hevy_template_id": template_id,
    }


def routine_exercises(routines):
    """[(template_id, title, [routine titles])] for each distinct exercise, in routine order."""
    seen = {}
    for routine in routines:
        for exercise in routine.get("exercises") or []:
            template_id = exercise.get("exercise_template_id")
            if not template_id:
                continue
            titles = seen.setdefault(template_id, (exercise.get("title") or template_id, []))[1]
            if routine.get("title") not in titles:
                titles.append(routine.get("title"))
    return [(template_id, title, routines) for template_id, (title, routines) in seen.items()]


def seed(lib, routines, templates):
    """Propose a load mode for every distinct routine exercise and record the proposals.

    Returns (proposals, instance document, guessed): the document is the
    instance file with the proposals recorded; nothing is written here.
    Entries with a confirmed load mode keep it.
    """
    by_id = {item.get("id"): item for item in templates or []}
    doc = copy.deepcopy(lib.instance)
    proposals, guessed = [], []
    for template_id, routine_title, in_routines in routine_exercises(routines):
        current = Library(doc, lib.path)
        template = by_id.get(template_id)
        title = (template or {}).get("title") or routine_title
        proposal = propose(current, template_id, title, template)
        proposal["routines"] = in_routines
        exercises = doc["exercises"]
        if proposal["matched_id"] is None:
            new_id = custom_id(title, set(current.ids()))
            entry = custom_entry(template_id, title, template, proposal["load_mode_proposed"])
            entry.update(load_mode=None, load_mode_proposed=proposal["load_mode_proposed"],
                         confidence=proposal["confidence"], avoid=None)
            exercises[new_id] = entry
            proposal.update(matched_id=new_id, matched_by="custom", action="created")
            guessed.append(f"{new_id}: pattern and muscles were guessed from Hevy's template for {title!r}; "
                           f"check them with python3 -m coach library show {new_id}")
        else:
            proposal["action"] = _record(exercises, current.get(proposal["matched_id"]), template_id, proposal)
        proposals.append(proposal)
    Library(doc, lib.path)
    return proposals, doc, guessed


def _record(exercises, entry, template_id, proposal):
    exercise_id = entry["id"]
    created = exercise_id not in exercises
    own = exercises.setdefault(exercise_id, {})
    before = copy.deepcopy(own)
    if template_id not in entry["hevy_template_ids"]:
        if own.get("hevy_template_id") is None:
            own["hevy_template_id"] = template_id
        else:
            own["hevy_template_ids"] = entry["hevy_template_ids"] + [template_id]
    if own.get("load_mode") is not None:
        return "confirmed"
    for key in ("hevy_template_id", "load_mode", "avoid"):
        own.setdefault(key, None)
    own["load_mode_proposed"] = proposal["load_mode_proposed"]
    own["confidence"] = proposal["confidence"]
    if created:
        return "created"
    return "unchanged" if own == before else "updated"
