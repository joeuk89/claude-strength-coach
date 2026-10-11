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
_EQUIPMENT_CAPACITY_BEFORE = re.compile(
    rf"^\s*(?:(?:home only|equipment|kit):\s*)?(?:adjustable\s+)?{_EQUIPMENT_NOUN}"
    rf"(?:\s*(?:,|and)\s*(?:adjustable\s+)?{_EQUIPMENT_NOUN})*"
    r"\s+(?:(?:go\s+)?up\s+(?:to|in)|to|down\s+to)\s*$", re.IGNORECASE,
)
_WEIGHT = r"\d+(?:\.\d+)?\s*(?:kgs?|lbs?|kilos?|pounds?)(?![A-Za-z])"
_MEASUREMENT_SUBJECT_WORDS = r"(?:body\s*weight|body mass|goal\s+(?:weight|plan)|weight\s+goal)"
_MEASUREMENT_SUBJECT = re.compile(rf"\b{_MEASUREMENT_SUBJECT_WORDS}\b", re.IGNORECASE)
_CLAUSE_SEPARATOR = re.compile(
    r"(,|[;!?\n]|\.(?!\d)|\b(?:(?:and|but)\s+then|and|but|then|plus|while|whereas)\b)", re.IGNORECASE,
)
_MEASUREMENT_CONTINUATION = re.compile(r"\s*(?:to|at|→|->|and\s+now|,?\s*now)\s*", re.IGNORECASE)
_MEASUREMENT_SUFFIX = re.compile(rf"{_WEIGHT}\s+(?:of\s+)?(?:body\s*weight|body mass)\b", re.IGNORECASE)
_EQUIPMENT_LIMIT = re.compile(
    rf"{_WEIGHT}\s+{_EQUIPMENT_NOUN}\s+(?:is|are)\s+(?:the\s+)?(?:heaviest|maximum|largest)\b",
    re.IGNORECASE,
)
_INCREMENT_BEFORE = re.compile(r"\b(?:step|increment)\s+(?:is|of|:)\s*$", re.IGNORECASE)
_INCREMENT_AFTER = re.compile(r"\s*(?:cable\s+)?(?:steps?|increments?)\b", re.IGNORECASE)


def measurement_spans(text):
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
    before = re.split(r"[;!?\n]|\.(?!\d)", text[:figure.start])[-1]
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
    measurements = measurement_spans(text)
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


_LOAD_CONTINUATION = re.compile(
    r"\s*(?:(?:next|this|last|following)\s+(?:week|session|time|block|workout)|today|tomorrow)?[\s:]*"
    r"(?:(?:move|go|work|increase|reduce|hold|stay|add|drop|raise|lower|bump|build|aim|target|try|use|keep)\s+)?"
    r"(?:(?:up|down|back)\s+)?(?:(?:to|at|by|for|with)\s+)?"
    r"\d+(?:\.\d+)?\s*(?:kgs?|lbs?|kilos?|pounds?|/\s*hand|per\s+hand|each|→|->|=>|⇒)(?![A-Za-z])"
    rf"|\s*(?:at\s+)?{_MEASUREMENT_SUBJECT_WORDS}\b",
    re.IGNORECASE,
)


def statements(text):
    """Split text into one statement per subject.

    Punctuation and conjunctions start a new subject. A clause that opens
    with a load instruction or a bodyweight measurement continues the
    statement before it, so its figures keep that statement's exercise.
    """
    parts = _CLAUSE_SEPARATOR.split(text)
    found = [parts[0]]
    joint = ""
    for separator, following in zip(parts[1::2], parts[2::2]):
        joint += separator
        if not following.strip():
            joint += following
            continue
        if _LOAD_CONTINUATION.match(following):
            found[-1] += joint + following
        else:
            found.append(following)
        joint = ""
    return found
