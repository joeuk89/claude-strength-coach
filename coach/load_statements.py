"""Load-figure validation shared by authoring and integrity checks."""

import re
from dataclasses import dataclass


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


_EQUIPMENT_NOUN = r"(?:dumbbells?|dbs?|plates?|cables?|kettlebells?|barbells?)"
_CAPACITY = r"\s+(?:(?:go\s+)?up\s+(?:to|in)|to|down\s+to)\s*$"
_EQUIPMENT_CAPACITY_BEFORE = re.compile(
    rf"^\s*(?:(?:home only|equipment|kit):\s*)?(?:adjustable\s+)?{_EQUIPMENT_NOUN}"
    rf"(?:\s+(?:and\s+)?(?:adjustable\s+)?{_EQUIPMENT_NOUN})*{_CAPACITY}"
    rf"|^\s*(?:equipment|kit):[^:]*?{_CAPACITY}", re.IGNORECASE,
)
_WEIGHT = r"\d+(?:\.\d+)?\s*(?:kgs?|lbs?|kilos?|pounds?)(?![A-Za-z])"
_MEASUREMENT_SUBJECT = re.compile(
    r"\b(?:body\s*weight|body mass|goal\s+(?:weight|plan)|weight\s+goal|weigh(?:ed|s)?|weigh[\s-]?ins?)\b",
    re.IGNORECASE,
)
_CLAUSE_SEPARATOR = re.compile(
    r"(,|[;!?\n]|\.(?!\d)|\b(?:(?:and|but)\s+then|and|but|or|then|plus|while|whereas)\b)", re.IGNORECASE,
)
_MEASUREMENT_CONTINUATION = re.compile(r"\s*(?:to|at|or|→|->|and\s+now|,?\s*now)\s*", re.IGNORECASE)
_MEASUREMENT_SUFFIX = re.compile(rf"{_WEIGHT}\s+(?:of\s+)?(?:body\s*weight|body mass)\b", re.IGNORECASE)
_EQUIPMENT_LIMIT = re.compile(
    rf"{_WEIGHT}\s+{_EQUIPMENT_NOUN}\s+(?:is|are)\s+(?:the\s+)?(?:heaviest|maximum|largest)\b"
    rf"|{_WEIGHT}\s+capacity\b", re.IGNORECASE,
)
_INCREMENT_BEFORE = re.compile(r"\b(?:step|increment)\s+(?:is|of|:)\s*$", re.IGNORECASE)
_INCREMENT_AFTER = re.compile(r"\s*(?:cable\s+)?(?:steps?|increments?)\b", re.IGNORECASE)


def _measurement_spans(text):
    """Associate a measurement subject with its first figure and numeric continuations."""
    spans = [(match.start(), match.end()) for pattern in (_EQUIPMENT_LIMIT, _MEASUREMENT_SUFFIX)
             for match in pattern.finditer(text)]
    figures = _figures(text)
    for subject in _MEASUREMENT_SUBJECT.finditer(text):
        boundary = _CLAUSE_SEPARATOR.search(text, subject.end())
        end = boundary.start() if boundary else len(text)
        following = [figure for figure in figures if figure.start >= subject.end()]
        if not following or following[0].start >= end:
            continue
        measured_end = following[0].end
        for figure in following[1:]:
            if not _MEASUREMENT_CONTINUATION.fullmatch(text[measured_end:figure.start]):
                break
            measured_end = figure.end
        spans.append((subject.start(), measured_end))
    return spans


def _unrelated_measurement(text, figure, measurements):
    before = re.split(r"[,;!?\n]|\.(?!\d)", text[:figure.start])[-1]
    measured = any(start <= figure.start < end for start, end in measurements)
    return bool(measured or _EQUIPMENT_CAPACITY_BEFORE.search(before)
                or _INCREMENT_BEFORE.search(before) or _INCREMENT_AFTER.match(text[figure.end:]))


def bare_figures(text, load_column=False):
    """Load figures whose per-hand interpretation is not explicit.

    A load figure carries a weight unit, sits in a load column, or is part
    of an arrow chain (`45 → 50`). It is explicit when it, or another figure
    in its chain, says per hand or gives the Hevy value.
    """
    bare = []
    measurements = _measurement_spans(text)
    for chain in _chains(text, _figures(text)):
        if any(f.two_number or f.rpe for f in chain):
            continue
        bare += [f for f in chain if (f.unit or load_column or len(chain) > 1)
                 and (load_column or not _unrelated_measurement(text, f, measurements))]
    return bare


def bare_message(rel, where, figures, exercise, text, hevy_enabled):
    listed = ", ".join(repr(figure.text) for figure in figures)
    what = "is a bare dumbbell number" if len(figures) == 1 else "are bare dumbbell numbers"
    if hevy_enabled:
        guidance = ("write the per-hand load and the Hevy value, as in 25/hand (Hevy: 50), "
                    "or at least the per-hand load, as in 25 kg per hand")
    else:
        guidance = "write the per-hand load, as in 25 kg per hand"
    return (f"{rel} {where}: {listed} for {exercise} {what} in {text.strip()!r}; "
            f"{guidance}")


_LOAD_LED = re.compile(
    r"\s*(?:(?:next|this|last|following)\s+(?:week|session|time|block|workout)|today|tomorrow)?[\s:]*"
    r"(?:(?:move|moving|go|going|work|increase|increasing|reduce|hold|stay|add|drop|raise|rising|lower|bump"
    r"|build|building|climb|climbing|progress|progressing|aim|target|try|use|keep|push|pushing)\s+)?"
    r"(?:(?:up|down|back)\s+)?(?:(?:to|at|by|for|with)\s+)?"
    r"\d+(?:\.\d+)?\s*(?:kgs?|lbs?|kilos?|pounds?|/\s*hand|per\s+hand|each|→|->|=>|⇒)(?![A-Za-z])",
    re.IGNORECASE,
)


PER_HAND_X2 = "per_hand_x2"


class Mentions:
    """Exercise mentions resolved only when their load mode is unambiguous.

    A movement name derived from an entry's name ("Lateral Raise (Cable)"
    gives "lateral raise") also matches, as does every variant of the
    movement an entry's own phrase names, but an entry that lists the phrase
    as its own name or alias owns it unless equipment in its statement picks
    another.
    """

    _EQUIPMENT = {"db": "dumbbell", "dbs": "dumbbell", "dumbbells": "dumbbell",
                  "bb": "barbell", "kb": "kettlebell", "cables": "cable",
                  "kettlebells": "kettlebell", "barbells": "barbell"}
    _SPELLINGS = {"dumbbell": r"(?:dumbbells?|dbs?)", "barbell": r"(?:barbells?|bb)",
                  "kettlebell": r"(?:kettlebells?|kb)", "cable": r"cables?"}
    _KINDS = {"smith": "smith_machine", "smith machine": "smith_machine", "trap bar": "trap_bar",
              "hex bar": "trap_bar", "ez bar": "ez_bar", "bar": "barbell", "bars": "barbell",
              "machines": "machine", "bands": "band", "rope": "cable", "ropes": "cable"}
    _EQUIPMENT_WORD = re.compile(
        r"(?<![A-Za-z])(dumbbells?|dbs?|barbells?|bb|kettlebells?|kb|cables?|ropes?|smith(?:[\s-]+machine)?"
        r"|machines?|bands?|landmine|(?:trap|hex|ez)[\s-]+bar|bars?|(?:weighted\s+|weight\s+)?vests?|plates?"
        r"|sandbags?|backpacks?|medicine[\s-]+balls?|assist(?:ed|ance))(?![A-Za-z])", re.IGNORECASE,
    )
    _NOT_MOVEMENT_WORDS = {"dumbbell", "barbell", "kettlebell", "cable", "machine", "band", "bodyweight", "smith",
                           "bar", "trap", "back", "over", "one", "two", "low", "good", "exercise", "anti", "through"}

    def __init__(self, lib):
        entries = list(lib.entries())
        movement = {e["id"]: self._key(re.sub(r"\s*\([^)]*\)", "", e["name"])) for e in entries}
        variants = {}
        for entry in entries:
            variants.setdefault(movement[entry["id"]], []).append(entry)
        candidates = {}
        for entry in entries:
            for phrase in (entry["name"], *entry["aliases"], *entry["hevy_titles"], entry["id"]):
                candidates.setdefault(self._key(phrase), {})[entry["id"]] = (entry, True)
        for entry in entries:
            for phrase in (entry["name"], *entry["aliases"], *entry["hevy_titles"], entry["id"]):
                for variant in variants[movement[entry["id"]]]:
                    candidates[self._key(phrase)].setdefault(variant["id"], (variant, False))
            candidates.setdefault(movement[entry["id"]], {}).setdefault(entry["id"], (entry, False))
        self._candidates = candidates
        alternatives = "|".join(self._phrase_pattern(key) for key in sorted(candidates, key=len, reverse=True))
        words = {word for entry in entries if entry["load_mode_default"] not in ("distance", "duration")
                 for phrase in (movement[entry["id"]], *entry["aliases"])
                 for word in self._key(phrase).split()
                 if word.isalpha() and len(word) > 2 and word not in self._NOT_MOVEMENT_WORDS}
        word = "(?:" + "|".join(sorted(words, key=len, reverse=True)) + r")(?:e?s)?(?![A-Za-z0-9_])"
        dumbbell_movement = rf"{self._SPELLINGS['dumbbell']}(?:[\s-]+{word}){{1,3}}"
        self._pattern = re.compile(rf"(?<![A-Za-z0-9_])(?:(?:{alternatives})(?:e?s)?(?![A-Za-z0-9_])"
                                   rf"|{dumbbell_movement})", re.IGNORECASE)
        families = {}
        for entry in entries:
            if entry["load_mode_default"] not in ("distance", "duration"):
                families.setdefault(movement[entry["id"]].split()[-1], set()).add(movement[entry["id"]])
        heads = sorted(head for head, names in families.items() if len(names) > 1 and head.isalpha() and len(head) > 2)
        self._movement_head = re.compile(rf"(?<![A-Za-z0-9_])(?:{'|'.join(heads)})(?:e?s)?(?![A-Za-z0-9_])",
                                         re.IGNORECASE)

    def _names_subject(self, clause):
        loads = [figure for figure in _figures(clause) if figure.unit or figure.two_number]
        before = clause[:loads[0].start] if loads else clause
        return bool(self._pattern.search(before) or self._movement_head.search(before))

    def statements(self, text):
        """Split text into one statement per subject.

        Punctuation and conjunctions end a clause. A clause that opens with a
        load instruction continues the statement before it, so its figures
        keep that statement's exercise. Otherwise a clause starts a new
        statement only when, before its first load, it names an exercise or
        a word that ends several library movement names (`leg curl`,
        `3 sets of seal row`); any other clause continues.
        """
        parts = _CLAUSE_SEPARATOR.split(text)
        found = [parts[0]]
        joint = ""
        for separator, following in zip(parts[1::2], parts[2::2]):
            joint += separator
            if not following.strip():
                joint += following
                continue
            if _LOAD_LED.match(following) or not self._names_subject(following):
                found[-1] += joint + following
            else:
                found.append(following)
            joint = ""
        return found

    @classmethod
    def _key(cls, phrase):
        return " ".join(cls._EQUIPMENT.get(word, word) for word in phrase.lower().replace("-", " ").split())

    @classmethod
    def _phrase_pattern(cls, key):
        return r"[\s-]+".join(cls._SPELLINGS.get(token, re.escape(token)) for token in key.split())

    def _lookup(self, key):
        for stem in (key, key[:-1] if key.endswith("s") else None, key[:-2] if key.endswith("es") else None):
            if stem in self._candidates:
                return list(self._candidates[stem].values())
        return None

    @classmethod
    def _kind(cls, word):
        word = re.sub(r"[\s-]+", " ", word.lower())
        return cls._KINDS.get(word, cls._EQUIPMENT.get(word, word))

    def _equipment(self, text):
        """The equipment kinds `text` names outside its measurements."""
        measurements = _measurement_spans(text)
        return {self._kind(match.group(1)) for match in self._EQUIPMENT_WORD.finditer(text)
                if not any(start <= match.start() < stop for start, stop in measurements)}

    def find(self, statement):
        """[(start, end, exercise, mode)] in order; mode is None when the mention is ambiguous.

        Equipment named anywhere in the statement, outside a measurement,
        selects among a movement's variants, and a `per_hand_x2` mention in a
        statement that names any other equipment (a barbell, a vest, a plate)
        is ambiguous. A dumbbell word before a movement the library does not
        name, or names only for other equipment, is a `per_hand_x2` mention
        named by its own words.
        """
        found = []
        equipment = self._equipment(statement)
        for match in self._pattern.finditer(statement):
            key = self._key(match.group(0))
            candidates = self._lookup(key) or self._lookup(key.partition(" ")[2])
            if candidates is None or ("dumbbell" in key.split()
                                      and all(entry["equipment"] != "dumbbell" for entry, _ in candidates)):
                exercise, mode = match.group(0), PER_HAND_X2
            else:
                owners = [entry for entry, owned in candidates if owned] or [entry for entry, _ in candidates]
                entries = [entry for entry, _ in candidates if entry["equipment"] in equipment] or owners
                modes = {e["effective_load_mode"] or e["load_mode_default"] for e in entries}
                exercise = entries[0]["id"]
                mode = next(iter(modes)) if len(modes) == 1 else None
            if mode == PER_HAND_X2 and equipment - {"dumbbell"}:
                mode = None
            found.append((match.start(), match.end(), exercise, mode))
        return found
