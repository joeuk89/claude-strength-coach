"""What every plugin works with: contexts, proposals, plans, and the default return-band decay (contract C23).

Every load here is the coaching number in athlete units (C18): per hand for
per-hand modes, the total otherwise, the added load for bodyweight and the
assistance for assisted. The core builds load objects afterwards, so no
plugin ever converts or doubles a load.
"""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Callable, Optional

from coach import flags as _flags
from coach import stats as _stats
from coach import validity as _validity

API = 1
WORKING_TYPES = ("normal", "dropset", "failure")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
STANDARD_DELOAD = {"set_factor": 0.67, "load_factor": 0.9, "rpe": 6}
EMPTY_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {}}
DATE_PATTERN = "^\\d{4}-\\d{2}-\\d{2}$"
E1RM_MODES = _stats.SERIES_MODES


@dataclass(frozen=True)
class SetSpec:
    """One prescribed set. `rep_range` is a (start, end) pair; `load` a coaching number or None."""

    type: str = "normal"
    reps: Optional[int] = None
    rep_range: Optional[tuple] = None
    rpe: Optional[float] = None
    load: Optional[float] = None
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None

    @property
    def working(self):
        return self.type in WORKING_TYPES

    @property
    def target_reps(self):
        """The reps the set asks for: its reps, else the start of its range."""
        if self.reps is not None:
            return self.reps
        return self.rep_range[0] if self.rep_range else None

    @property
    def top_reps(self):
        """The most reps the set asks for: its reps, else the end of its range."""
        if self.reps is not None:
            return self.reps
        return self.rep_range[1] if self.rep_range else None

    @classmethod
    def from_dict(cls, item, load=None):
        rep_range = item.get("rep_range")
        return cls(
            type=item.get("type") or "normal", reps=item.get("reps"),
            rep_range=(rep_range["start"], rep_range["end"]) if rep_range else None,
            rpe=item.get("rpe"), load=load if load is not None else _plain_load(item.get("load")),
            duration_seconds=item.get("duration_seconds"), distance_meters=item.get("distance_meters"),
        )

    def to_dict(self):
        """The set in the overlay draft's shape (athlete units)."""
        return {
            "type": self.type, "reps": self.reps,
            "rep_range": {"start": self.rep_range[0], "end": self.rep_range[1]} if self.rep_range else None,
            "rpe": self.rpe, "load": self.load, "duration_seconds": self.duration_seconds,
            "distance_meters": self.distance_meters,
        }


def _plain_load(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


@dataclass(frozen=True)
class LoggedSet:
    index: int
    type: str
    reps: Optional[int]
    rpe: Optional[float]
    load: Optional[float]

    @property
    def working(self):
        return self.type in WORKING_TYPES


@dataclass(frozen=True)
class Exposure:
    """One exercise in one logged workout (C17), its loads as coaching numbers.

    `prescribed` holds the working sets the overlay in force that day asked
    for (the program's set groups when none did); `week_kind` is that
    overlay's kind, or None.
    """

    date: date
    workout_id: str
    session_id: Optional[str]
    exercise_id: str
    load_mode: str
    sets: tuple
    suspect: bool = False
    excluded: bool = False
    prescribed: tuple = ()
    week_kind: Optional[str] = None

    @property
    def usable(self):
        return not self.excluded and not self.suspect

    @property
    def top_load(self):
        return top_load(self.sets)

    def ref(self):
        return {"date": self.date.isoformat(), "workout_id": self.workout_id}


@dataclass(frozen=True)
class ExerciseInfo:
    id: str
    name: str
    pattern: Optional[str]
    muscles: dict
    equipment: Optional[str]
    load_mode: str
    increment: float
    is_compound: bool
    load_direction: int = 1


@dataclass(frozen=True)
class SlotInfo:
    """A program slot. `sets` holds the program's set groups (each with a `count`)."""

    session_id: str
    sets: tuple
    rest_seconds: Optional[int]
    cues: Optional[str]
    constraints: tuple
    start_load: Optional[float]


@dataclass(frozen=True)
class SchemeContext:
    today: date
    session_date: date
    unit: str
    week_kind: str
    exercise: ExerciseInfo
    slot: SlotInfo
    params: dict
    state: dict
    exposures: tuple
    e1rm: Optional[float]
    last_prescription: Optional[dict]
    last_override: Optional[dict]
    days_off: int
    constraints: tuple
    scheme: str = ""
    scheme_deload: Optional[Callable] = None


@dataclass(frozen=True)
class Proposal:
    sets: tuple
    rationale: str
    derived_from: Optional[Exposure]
    state: dict
    flags: tuple = ()
    target_note: Optional[str] = None
    focus: Optional[str] = None
    round_down: bool = False


@dataclass(frozen=True)
class ScheduleContext:
    today: date
    span_start: date
    span_end: date
    week_starts: str
    params: dict
    rotation: dict
    sessions: tuple
    external_sessions: tuple


@dataclass(frozen=True)
class SchedulePlan:
    """Dated sessions for a span. `rotation` is the position the span implies, or None to leave it unchanged."""

    sessions: tuple
    rotation: Optional[dict] = None
    flags: tuple = field(default_factory=tuple)


def expand(groups):
    """One SetSpec per set of the program's set groups, in order."""
    found = []
    for group in groups:
        found += [SetSpec.from_dict(group)] * group.get("count", 1)
    return tuple(found)


def working(sets):
    return [s for s in sets if s.working]


def top_load(sets):
    loads = [s.load for s in sets if s.working and s.load is not None]
    return max(loads) if loads else None


def with_load(sets, load):
    """The sets with every working set at `load`."""
    return tuple(replace(s, load=load) if s.working else s for s in sets)


def with_reps(sets, reps):
    """The sets with every working set asking for exactly `reps`."""
    return tuple(replace(s, reps=reps, rep_range=None) if s.working else s for s in sets)


def newest(exposures):
    """The newest exposure that is not excluded, suspect or not."""
    return next((e for e in exposures if not e.excluded), None)


def baseline(exposures):
    """The exposure loads derive from: the newest neither excluded, suspect nor trained in a deload week."""
    return next((e for e in exposures if e.usable and e.week_kind != "deload"), None)


def usable_oldest_first(exposures, after=None):
    """Usable exposures outside deload weeks, oldest first, dated after `after` (a date or None)."""
    found = [e for e in exposures if e.usable and e.week_kind != "deload" and (after is None or e.date > after)]
    return list(reversed(found))


def missed(exposure):
    """True when an exposure fell short of what it prescribed: a set missing or below its target reps."""
    prescribed = working(exposure.prescribed)
    logged = [s for s in exposure.sets if s.working]
    if len(logged) < len(prescribed):
        return True
    for wanted, got in zip(prescribed, logged):
        if wanted.target_reps is not None and (got.reps or 0) < wanted.target_reps:
            return True
    return False


def prescription_sets(last_prescription):
    return tuple(last_prescription["sets"])


def start_load(ctx):
    """Where a slot starts with no usable exposure: the last approved load, else the program's start load."""
    if ctx.last_prescription:
        found = top_load(prescription_sets(ctx.last_prescription))
        if found is not None:
            return found
    return ctx.slot.start_load


def increment(ctx):
    return ctx.params.get("increment") or ctx.exercise.increment


def number(value):
    """A coaching number for a sentence: at most two decimals, no trailing zeros."""
    text = f"{round(value, 2):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def load_words(ctx, value):
    """A coaching number with its per-hand marker, for a rationale."""
    if value is None:
        return "no load"
    suffix = "/hand" if ctx.exercise.load_mode == "per_hand_x2" else ""
    if ctx.exercise.load_mode == "bodyweight":
        return "BW" if value == 0 else f"BW+{number(value)}"
    return f"{number(value)}{suffix}"


def flag(ctx, code, message, severity=None):
    """A C10 flag on this slot's line."""
    return _flags.make(code, severity, session_id=ctx.slot.session_id, exercise_id=ctx.exercise.id, message=message)


def week_flag(code, message, severity=None):
    """A C10 flag about the whole week (no session, no exercise)."""
    return _flags.make(code, severity, message=message)


def week_start(day, week_starts):
    back = day.weekday() if week_starts == "monday" else (day.weekday() + 1) % 7
    return day - timedelta(days=back)


def scaled(sets, factor, ceiling=None):
    """Working-set loads times `factor`, each first capped at `ceiling` (the derived-from load) when given."""
    found = []
    for s in sets:
        if s.working and s.load is not None:
            base = s.load if ceiling is None else min(s.load, ceiling)
            s = replace(s, load=base * factor)
        found.append(s)
    return tuple(found)


def keep_working(sets, count):
    """The sets with only the first `count` working sets kept (warm-ups stay)."""
    found, kept = [], 0
    for s in sets:
        if s.working:
            if kept >= count:
                continue
            kept += 1
        found.append(s)
    return tuple(found)


def rpe_capped(sets, cap):
    return tuple(replace(s, rpe=cap if s.rpe is None else min(s.rpe, cap)) if s.working else s for s in sets)


def return_band(days_off):
    """C22's return band for these days off: `id`, `load_factor`, `set_delta`, `rpe_cap` and `retest`."""
    return _validity.band_for(days_off)


def bands_back(days_off):
    """How many return bands past `0-10` these days off fall: 0 for `0-10`, 1 for `11-21`, and so on."""
    return _validity.RETURN_BANDS.index(_validity.band_for(days_off))


def return_set_count(proposal, set_delta):
    """The working sets a return week keeps: `max(1, min(proposal, derived-from) + set_delta)` (C23)."""
    count = len(working(proposal.sets))
    source = proposal.derived_from
    if source is not None and working(source.sets):
        count = min(count, len(working(source.sets)))
    return max(1, count + set_delta)


def default_decay(ctx, proposal, days_off):
    """C22's return band: load × its factor from the pre-layoff load, one working set fewer, RPE capped for 43+.

    The load is cut from the lower of the proposal and the derived-from
    exposure, so a return week never carries a progression.
    """
    band = _validity.band_for(days_off)
    sets = proposal.sets
    source = proposal.derived_from
    ceiling = source.top_load if source else None
    if band.load_factor != 1:
        sets = scaled(sets, band.load_factor, ceiling)
    if band.set_delta:
        sets = keep_working(sets, return_set_count(proposal, band.set_delta))
    if band.rpe_cap is not None:
        sets = rpe_capped(sets, band.rpe_cap)
    return replace(proposal, sets=sets, round_down=True)


def standard_deload(proposal, set_factor, load_factor, rpe):
    """Fewer working sets (at least one), each load times `load_factor` from the derived-from load, all at `rpe`."""
    source = proposal.derived_from
    count = len(working(proposal.sets))
    sets = keep_working(proposal.sets, max(1, round(count * set_factor)))
    sets = scaled(sets, load_factor, source.top_load if source else None)
    sets = tuple(replace(s, rpe=rpe) if s.working else s for s in sets)
    return replace(proposal, sets=sets, round_down=True)
