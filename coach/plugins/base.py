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
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None

    @property
    def working(self):
        return self.type in WORKING_TYPES


@dataclass(frozen=True)
class Exposure:
    """One exercise in one logged workout (C17), its loads as coaching numbers.

    `prescribed` holds the working sets the overlay in force that day asked
    for, or is empty when the historical prescription is unknown.
    `week_kind` is that overlay's kind, or None.
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
    e1rm_supported: bool = True
    is_isolation: bool = False


NO_E1RM_REASON = "body mass dominates this movement, so it gets no e1RM"


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


LIFT_KINDS = ("lifting", "external")


@dataclass(frozen=True)
class InterferenceContext:
    """One interference rule's view of a span (C51).

    `bouts` are C49 bouts sorted by date then start, plus the quality
    activities of the days just before the span. `heavy_lower` holds the
    refs of lifting bouts that are heavy lower-body work under this rule's
    params. `titles` maps a bout's ref to a name for messages. Timestamps
    are in the athlete's timezone.
    """

    mode: str
    span: object
    params: dict
    bouts: tuple
    heavy_lower: frozenset
    titles: dict = field(default_factory=dict)


def is_lift(bout):
    """True for a lifting workout or session and for a coach-led session."""
    return bout.kind in LIFT_KINDS


def quality_activities(bouts):
    return [b for b in bouts if b.quality and not is_lift(b)]


def timed(bout):
    return bout.start is not None and bout_end(bout) is not None


def bout_end(bout):
    """When the bout ended: its end, else its start plus its minutes, else None."""
    if bout.end is not None:
        return bout.end
    if bout.start is not None and bout.minutes is not None:
        return bout.start + timedelta(minutes=bout.minutes)
    return None


def hours_between(earlier, later):
    """Hours from one moment to a later one (negative when `later` comes first)."""
    return (later - earlier).total_seconds() / 3600


def hours_text(hours):
    return f"{number(round(hours, 1))} h"


def bout_text(ctx, bout):
    """A bout for a message: its title, kind when it is an activity, date and start time when known."""
    title = ctx.titles.get(bout.ref) or bout.session_id or bout.kind
    planned = "planned " if bout.source == "planned" else ""
    if is_lift(bout):
        what = f"{planned}{title}"
    else:
        what = f"{planned}{bout.kind} \"{title}\"" if title != bout.kind else f"{planned}{bout.kind}"
    when = bout.date.isoformat()
    if bout.start is not None:
        when += f" {bout.start.strftime('%H:%M')}"
    return f"{what} ({when})"


def session_flag(code, message, session_id, severity=None):
    """A C10 flag about one session (no exercise), such as an interference rule's."""
    return _flags.make(code, severity, session_id=session_id, message=message)


@dataclass(frozen=True)
class ConditioningContext:
    """A conditioning session's view for its density scheme (C51).

    `exercises` are in program order. `bouts` are the conditioning
    Activities matched to the session's last prescription, newest first,
    each `{date, activity_id, duration_seconds, rpe}`. `last_prescription`
    is `{overlay_id, session_id, date, dates, span, lines}` from the newest
    approved overlay holding the session, or None. `days_off` counts from
    the newest logged conditioning Activity.
    """

    today: date
    session_date: date
    session_id: str
    exercises: tuple
    params: dict
    state: dict
    bouts: tuple
    last_prescription: Optional[dict]
    days_off: int


@dataclass(frozen=True)
class ConditioningProposal:
    """`lines` maps each exercise id to its sets (reps, or the duration or distance its mode logs; no load)."""

    lines: dict
    focus: str
    rationale: str
    state: dict
    flags: tuple = ()


RPE_LOG_HINT = "Put your session RPE in the workout description, e.g. 'RPE 7'."
HEURISTIC = "a coaching heuristic"
AT_CAP = "at cap: coach to change"
RPE_STEP_BACK = 2
ONE_STEP_BACK_DAYS = 11
RESET_DAYS = 43


def work_set(exercise, value):
    """One working set of `value`: seconds for a duration exercise, metres for distance, else reps."""
    if exercise.load_mode == "duration":
        return SetSpec(duration_seconds=value)
    if exercise.load_mode == "distance":
        return SetSpec(distance_meters=value)
    return SetSpec(reps=value)


def density_verdict(ctx, rpe_target, time_cap_minutes=None):
    """("up" | "back" | "hold", why, flags) from the newest matched bout (C51).

    Up when the session RPE is at or under target (and, with a time cap,
    the session finished inside it); back when the RPE is target + 2 or
    more, or the session ran over the cap; hold otherwise. No bout holds;
    no RPE, or no finish time against a cap, holds with `no_data`.
    """
    if not ctx.bouts:
        return "hold", "no conditioning session was logged against the last prescription", ()
    bout = ctx.bouts[0]
    rpe = bout["rpe"]
    if rpe is None:
        message = (f"The conditioning session on {bout['date']} has no session RPE, so the scheme holds; "
                   f"{RPE_LOG_HINT}")
        return "hold", f"the session on {bout['date']} logged no RPE", (session_flag("no_data", message,
                                                                                   ctx.session_id),)
    seconds = bout.get("duration_seconds")
    minutes = seconds / 60 if seconds else None
    if time_cap_minutes is not None and minutes is None:
        message = f"The conditioning session on {bout['date']} has no finish time, so the scheme holds."
        return "hold", f"the session on {bout['date']} has no finish time", (session_flag("no_data", message,
                                                                                         ctx.session_id),)
    said = f"session RPE {number(rpe)} against a target of {number(rpe_target)} on {bout['date']}"
    if time_cap_minutes is not None:
        said += f" in {number(round(minutes, 1))} min against a {number(time_cap_minutes)}-min cap"
    if rpe >= rpe_target + RPE_STEP_BACK or (time_cap_minutes is not None and minutes > time_cap_minutes):
        return "back", said, ()
    if rpe <= rpe_target:
        return "up", said, ()
    return "hold", said, ()


def stepped(state, prescription):
    """The state moved on to `prescription`, the current one kept so a step back restores it exactly."""
    return {"current": prescription, "previous": [*state["previous"], state["current"]]}


def stepped_back(state):
    """The state one step back, or None when it is already at its start."""
    if not state["previous"]:
        return None
    return {"current": state["previous"][-1], "previous": list(state["previous"][:-1])}


def density_decay(state, start, days_off):
    """(state, words) after `days_off` without conditioning: 11–42 days one step back, 43 or more the start."""
    if days_off >= RESET_DAYS:
        return {"current": start, "previous": []}, f"{days_off} days off, so back to the start"
    back = stepped_back(state)
    if back is None:
        return state, f"{days_off} days off, already at the start"
    return back, f"{days_off} days off, so one step back"


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
    """True when a logged working set fell short of its prescribed reps, False when every prescribed set was logged
    at them, and None when that is unknown: the historical prescription is unknown, or the exposure is `incomplete`
    with no short set.

    A set that was never logged is not a failed attempt: it may have been skipped for time.
    """
    prescribed = working(exposure.prescribed)
    if not prescribed:
        return None
    logged = working(exposure.sets)
    for wanted, got in zip(prescribed, logged):
        if wanted.target_reps is not None and (got.reps or 0) < wanted.target_reps:
            return True
    return None if len(logged) < len(prescribed) else False


def incomplete(exposure):
    """True when a known prescription asked for more working sets than were logged."""
    prescribed = working(exposure.prescribed)
    return bool(prescribed) and len(working(exposure.sets)) < len(prescribed)


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


def lightened(sets, factor, source, load_direction=1):
    """Working-set loads times `factor` from the lower of each and the derived-from top load.

    More assistance is a lighter lift, so assistance (`load_direction` −1)
    is never cut: each set keeps at least the derived-from least assistance.
    """
    if load_direction > 0:
        return scaled(sets, factor, source.top_load if source else None)
    loads = [s.load for s in working(source.sets) if s.load is not None] if source else []
    if not loads:
        return sets
    return tuple(replace(s, load=max(s.load, min(loads))) if s.working and s.load is not None else s for s in sets)


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
    exposure, so a return week never carries a progression. Assistance is
    never cut (see `lightened`).
    """
    band = _validity.band_for(days_off)
    sets = proposal.sets
    direction = ctx.exercise.load_direction
    if band.load_factor != 1 or direction < 0:
        sets = lightened(sets, band.load_factor, proposal.derived_from, direction)
    if band.set_delta:
        sets = keep_working(sets, return_set_count(proposal, band.set_delta))
    if band.rpe_cap is not None:
        sets = rpe_capped(sets, band.rpe_cap)
    return replace(proposal, sets=sets, round_down=True)


def standard_deload(proposal, set_factor, load_factor, rpe, load_direction=1):
    """Fewer working sets (at least one), each load times `load_factor` from the derived-from load, all at `rpe`.

    Assistance is never cut (see `lightened`).
    """
    count = len(working(proposal.sets))
    sets = keep_working(proposal.sets, max(1, round(count * set_factor)))
    sets = lightened(sets, load_factor, proposal.derived_from, load_direction)
    sets = tuple(replace(s, rpe=rpe) if s.working else s for s in sets)
    return replace(proposal, sets=sets, round_down=True)
