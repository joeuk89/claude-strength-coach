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


_NON_LOAD_BEFORE = re.compile(
    r"(?:^\s*(?:(?:equipment|kit):\s*)?(?:adjustable\s+)?"
    r"(?:dumbbells?|dbs?|plates?)\s+(?:(?:go\s+)?up\s+(?:to|in)|to|down\s+to)\s*|"
    r"\b(?:body\s*weight|body mass|goal weight|goal plan current)\b[^,;!?]*)$", re.IGNORECASE,
)
_INCREMENT_AFTER = re.compile(r"\s*(?:cable\s+)?(?:steps?|increments?)\b", re.IGNORECASE)


def _unrelated_measurement(text, figure):
    before = statements(text[:figure.start])[-1]
    return bool(_NON_LOAD_BEFORE.search(before) or _INCREMENT_AFTER.match(text[figure.end:]))


def bare_figures(text, load_column=False):
    """Load figures whose per-hand interpretation is not explicit.

    A load figure carries a weight unit, sits in a load column, or is part
    of an arrow chain (`45 → 50`). It is in the two-number form when it, or
    another figure in its chain, says per hand or gives the Hevy value.
    """
    bare = []
    for chain in _chains(text, _figures(text)):
        if any(f.two_number or f.rpe for f in chain):
            continue
        bare += [f for f in chain if (f.unit or load_column or len(chain) > 1)
                 and (load_column or not _unrelated_measurement(text, f))]
    return bare


def bare_message(rel, where, figures, exercise, text, hevy_enabled=True):
    listed = ", ".join(repr(figure.text) for figure in figures)
    what = "is a bare dumbbell number" if len(figures) == 1 else "are bare dumbbell numbers"
    guidance = "write the per-hand load, as in 25 kg per hand"
    if hevy_enabled:
        guidance += "; optionally include the Hevy value, as in 25/hand (Hevy: 50)"
    return (f"{rel} {where}: {listed} for {exercise} {what} in {text.strip()!r}; "
            f"{guidance}")


def statements(text):
    """Separate clauses while preserving decimals and numeric comma continuations."""
    return re.split(r",(?!\s*\d)|[;!?\n]|\.(?!\d)", text)
