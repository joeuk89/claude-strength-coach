"""Validity window, return bands and prescription checks (contract C21, C22).

The return bands live here and nowhere else in code; `CLAUDE.md`
"Coaching principles" holds the prose copy and a test keeps the two equal.
A check never changes a load: it flags each prescription line that is no
longer earned, cannot be built from the kit, or will not fit its session.
"""

import re
import statistics
from collections import namedtuple
from datetime import timedelta

from coach import config as config_module
from coach import constraints, dates, first_loads, flags, history, overlay, state, stats, units
from coach.checks.instance import _capped_value as capped_value
from coach.checks.instance import cap_for
from coach.config_tables.sessions import cap_minutes
from coach.errors import ConfigError, ValidationError
from coach.library import Library, e1rm_supported
from coach.loads import available_loads

OWNER = "R-24"

Band = namedtuple("Band", "upper id load_factor set_delta rpe_cap retest")
RETURN_BANDS = tuple(Band(*row) for row in (
    (10, "0-10", 1.00, 0, None, False),
    (21, "11-21", 0.95, -1, None, False),
    (42, "22-42", 0.90, -1, None, False),
    (None, "43+", 0.85, -1, 7, True),
))
GRACE_DAYS = 10
INTERVAL_BOUNDS = (7, 14)
INTERVAL_GAPS = 4
ILLNESS_RPE_CAP = 7
SYMPTOM_FREE_HOURS = 48

E1RM_WINDOW_DAYS = 42
UNEARNED_IMPLIED_RPE = 10.5
RPE_TOLERANCE = 1
CITES = ("rn:autoregulation.6",)
NO_E1RM_INCREMENTS = 2
FEASIBILITY_MODES = ("total", "per_hand_x2", "single_implement")

# Duration estimate: heuristics, not measured values (C22).
SECONDS_PER_REP = 4
SECONDS_PER_EXERCISE = 60
WARM_UP_SECONDS = 300
PACE_WORKOUTS = 4
PACE_MIN_WORKOUTS = 2
PACE_BOUNDS = (0.7, 1.5)

UNCONFIRMED = "load_mode_unconfirmed"
RPE_SCALE = (0, 10)

Verdict = namedtuple("Verdict", "implied reps unearned off")

_LINE_PATH = re.compile(r"^\$\.sessions\[(\d+)\]\.exercises\[(\d+)\]")


def band_for(days_off):
    """The return band a number of days off falls in."""
    for band in RETURN_BANDS:
        if band.upper is None or days_off <= band.upper:
            return band
    raise AssertionError("the last return band is open-ended")


def _day(value):
    return dates.parse_date(value) if isinstance(value, str) else value


def interval_days(exposures):
    """An exercise's usual gap between exposures: the median of its last four gaps, clamped to 7..14 days.

    `exposures` are exposure dicts or dates, in any order. Fewer than two
    gaps give the lower bound.
    """
    days = sorted({_day(e["date"] if isinstance(e, dict) else e) for e in exposures}, reverse=True)
    gaps = [(newer - older).days for newer, older in zip(days, days[1:])][:INTERVAL_GAPS]
    low, high = INTERVAL_BOUNDS
    if len(gaps) < 2:
        return low
    return min(high, max(low, int(statistics.median(gaps) + 0.5)))


def window_ok(exposure_age, interval):
    """True while an exposure is within the exercise's usual gap plus the grace days."""
    return exposure_age <= interval + GRACE_DAYS


class _History:
    """One read of the history, shared by every line an overlay check looks at."""

    def __init__(self, root):
        self.root = root
        self.exposures = {}
        for exposure in history.all_exposures(root):
            self.exposures.setdefault(exposure["exercise_id"], []).append(exposure)
        for found in self.exposures.values():
            found.sort(key=lambda e: (e["date"], e["workout_id"]), reverse=True)
        self._series = None
        self._last_lifting = {}
        self._workouts = None

    def usable(self, exercise_id, before):
        """Non-excluded exposures of an exercise dated before `before` (a date), newest first."""
        before = before.isoformat()
        return [e for e in self.exposures.get(exercise_id, []) if not e["excluded"] and e["date"] < before]

    def baselines(self, exercise_id, before):
        """Usable exposures that are not open convention-slip candidates, newest first: what loads derive from."""
        return [e for e in self.usable(exercise_id, before) if not e["suspect"]]

    def last_lifting(self, before):
        if before not in self._last_lifting:
            self._last_lifting[before] = history.last_lifting_date(self.root, before)
        return self._last_lifting[before]

    def series(self):
        if self._series is None:
            self._series = stats.e1rm_series(self.root)
        return self._series["series"]

    def evidence(self, exercise_id, session_date):
        self.series()
        return stats.capacity_evidence(self._series, exercise_id, session_date, E1RM_WINDOW_DAYS)

    def workouts(self):
        if self._workouts is None:
            self._workouts = history.workouts(self.root)
        return self._workouts

    def gap_facts(self, exercise_id, session_date, first_back=None):
        """Days off and how they were measured, for one exercise before one session date.

        The layoff runs to `first_back`, the span's first session back, when it falls on or before the session.
        """
        back = first_back if first_back is not None and first_back <= session_date else session_date
        layoff_from = self.last_lifting(back)
        layoff = (back - layoff_from).days if layoff_from else None
        found = self.usable(exercise_id, session_date)
        newest = found[0] if found else None
        age = (session_date - dates.parse_date(newest["date"])).days if newest else None
        interval = interval_days(found) if found else None
        candidates = [value for value in (layoff, age - interval if newest else None) if value is not None]
        baseline = next((e for e in found if not e["suspect"]), None)
        return {"days_off": max(0, *candidates) if candidates else None, "layoff_days": layoff,
                "exposure_age": age, "interval_days": interval, "newest": newest, "baseline": baseline}


def days_off(root, exercise_id, session_date, first_back=None):
    """Days off for an exercise before a session: the longer of the layoff and its exposure age past its usual gap.

    The layoff is measured to `first_back`, the first session back in the span, when given. None when there is
    no lifting and no exposure to measure from.
    """
    first_back = _day(first_back) if first_back is not None else None
    return _History(root).gap_facts(exercise_id, _day(session_date), first_back)["days_off"]


def _rest_by_exercise(session):
    return {line["exercise_id"]: line.get("rest_seconds") or 0 for line in session["exercises"]}


def _set_seconds(set_):
    if set_.get("duration_seconds"):
        return set_["duration_seconds"]
    reps = set_.get("reps")
    if reps is None and set_.get("rep_range"):
        reps = set_["rep_range"]["end"]
    return (reps or 0) * SECONDS_PER_REP


def _estimated_seconds(exercises, rest_for):
    total = WARM_UP_SECONDS
    for exercise_id, sets in exercises:
        total += SECONDS_PER_EXERCISE + sum(_set_seconds(s) for s in sets)
        total += max(0, len(sets) - 1) * rest_for(exercise_id)
    return total


def _session_routines(root, session):
    found = {session.get("hevy_routine_id")} - {None}
    state_doc = history.load_optional(state, root)
    if state_doc:
        found |= {routine_id for routine_id, entry in state_doc["hevy"]["routines"].items()
                  if entry.get("session_id") == session["session_id"]}
    return found


def _pace(root, session, workouts):
    """Median of actual ÷ estimated minutes over the session's last logged workouts, clamped; 1 with too few."""
    routines = _session_routines(root, session)
    rest = _rest_by_exercise(session)
    fallback_rest = statistics.mean(rest.values()) if rest else 0
    logged = [w for w in workouts
              if w["date"] < session["date"] and w["duration_minutes"]
              and (w["session_id"] == session["session_id"] or (w["routine_id"] and w["routine_id"] in routines))]
    ratios = []
    for workout in sorted(logged, key=lambda w: w["date"], reverse=True)[:PACE_WORKOUTS]:
        exercises = [(e["exercise_id"], e["sets"]) for e in workout["exercises"]]
        seconds = _estimated_seconds(exercises, lambda i: rest.get(i, fallback_rest))
        ratios.append(workout["duration_minutes"] * 60 / seconds)
    if len(ratios) < PACE_MIN_WORKOUTS:
        return 1.0
    low, high = PACE_BOUNDS
    return min(high, max(low, statistics.median(ratios)))


def _estimate(root, session, workouts):
    rest = _rest_by_exercise(session)
    exercises = [(line["exercise_id"], line["sets"]) for line in session["exercises"]]
    seconds = _estimated_seconds(exercises, lambda i: rest.get(i, 0))
    return int(seconds * _pace(root, session, workouts) / 60 + 0.5)


def estimate_minutes(root, session):
    """A session's estimated length in minutes, scaled by how its recent logged workouts ran (a heuristic)."""
    return _estimate(root, session, history.workouts(root))


def _number(value):
    return units.json_number(round(value, 2))


def rep_targets(reps, rep_range):
    """Every whole rep target a set allows: its reps, else each number in its (start, end) range."""
    if reps is not None:
        return (reps,)
    if rep_range:
        return tuple(range(rep_range[0], rep_range[1] + 1))
    return ()


def _targets(set_):
    found = set_.get("rep_range")
    return rep_targets(set_.get("reps"), (found["start"], found["end"]) if found else None)


def judge_set(estimate, load, targets, rpe=None, ceiling=False):
    """The e1RM model's verdict on one working set (C22), shared by proposals and the prescription check.

    `unearned` when even the fewest allowed reps imply more than UNEARNED_IMPLIED_RPE. `off` is "hard" or "easy" when
    no allowed rep target implies an RPE within RPE_TOLERANCE of `rpe`; a `ceiling` is only ever too hard. A
    lower-bound estimate shows neither unearned nor too hard. `implied` and `reps` name the closest rep target.
    """
    lower = stats.is_lower_bound(estimate)
    fewest, most = min(targets), max(targets)
    easiest = stats.implied_rpe(estimate["e1rm"], load, fewest)
    if not lower and easiest > UNEARNED_IMPLIED_RPE:
        return Verdict(easiest, fewest, True, None)
    if rpe is None:
        return Verdict(easiest, fewest, False, None)
    if easiest > rpe + RPE_TOLERANCE:
        return Verdict(easiest, fewest, False, None if lower else "hard")
    hardest = stats.implied_rpe(estimate["e1rm"], load, most)
    if hardest < rpe - RPE_TOLERANCE and not ceiling:
        return Verdict(hardest, most, False, "easy")
    return Verdict(easiest, fewest, False, None)


def implied_words(value):
    """An implied RPE as a message shows it: `RPE 7.75` on the scale, else the model result named as off the scale."""
    value = round(value, 2)
    low, high = RPE_SCALE
    if value > high:
        return f"a model result of {_number(value)} (past failure: above RPE {high})"
    if value < low:
        return f"a model result of {_number(value)} (far from failure: below RPE {low})"
    return f"RPE {_number(value)}"


def estimate_words(estimate):
    """`the e1RM of 19.6 from 2026-10-12`, saying when it is only a lower bound."""
    words = f"the e1RM of {_number(estimate['e1rm'])} from {estimate['date']}"
    return f"{words}, a lower bound from sets logged without RPE" if stats.is_lower_bound(estimate) else words


def reps_words(reps, targets):
    """`8`, or `8 (the closest rep target in 8–10)` for a set with a range."""
    if len(targets) == 1:
        return f"{reps}"
    return f"{reps} (the closest rep target in {targets[0]}–{targets[-1]})"


def _loads(sets):
    numbers = [history.coaching_number(s["load"]) for s in sets
               if s.get("load") and not s.get("discounted")]
    return [n for n in numbers if n is not None]


def _top_load(sets):
    numbers = _loads(sets)
    return max(numbers) if numbers else None


def _least_load(sets):
    numbers = _loads(sets)
    return min(numbers) if numbers else None


class _Checker:
    def __init__(self, root, doc, config, arithmetic):
        self.root = root
        self.arithmetic = arithmetic
        self.doc = doc
        self.config = config
        self.unit = config.athlete.units
        self.show_hevy = config.hevy.enabled
        self.history = _History(root)
        try:
            self.library = Library.load(root)
        except ValidationError:
            self.library = None
        self.flags = []
        self.lines = []
        self.no_data = {(f["session_id"], f["exercise_id"]) for f in doc["flags"] if f["code"] == overlay.NO_DATA}
        self.created = doc["created_at"][:10]

    def flag(self, code, session, line, message):
        self.flags.append(flags.make(code, session_id=session["session_id"],
                                     exercise_id=line["exercise_id"] if line else None, message=message))

    def where(self, session, line):
        return _where(session, line)

    def sound(self, line, load):
        return (load is not None and load.get("mode") == line["load_mode"] and load.get("unit") == self.unit
                and not units.check_load(load))

    def run(self):
        self.mismatches()
        illness = self.illness()
        first_back = min((dates.parse_date(s["date"]) for s in self.doc["sessions"]), default=None)
        for session in self.doc["sessions"]:
            session_date = dates.parse_date(session["date"])
            for line in session["exercises"]:
                self.check_line(session, session_date, line, illness, first_back)
            self.check_duration(session)
        return {"flags": self.flags, "lines": self.lines}

    def mismatches(self):
        by_line = {}
        for error in self.arithmetic:
            match = _LINE_PATH.match(error.path)
            if match:
                by_line.setdefault((int(match.group(1)), int(match.group(2))), []).append(error)
        for s_index, session in enumerate(self.doc["sessions"]):
            for e_index, line in enumerate(session["exercises"]):
                found = [f"{e.path}: {e.message}" for e in by_line.get((s_index, e_index), [])]
                confirmed = self.library.effective_load_mode(line["exercise_id"]) if self.library else None
                if confirmed is not None and confirmed != line["load_mode"]:
                    found.append(f"the line is {line['load_mode']}, but the library's confirmed load mode is "
                                 f"{confirmed}")
                if found:
                    self.flag("load_mode_mismatch", session, line,
                              f"{self.where(session, line)}: {'; '.join(found)}")
                if self.library and confirmed is None:
                    self.flags.append(_unconfirmed_flag(self.library, session, line))

    def illness(self):
        """(date, reason) of the first session back when an `ill` miss or status day falls in the gap before it."""
        if not self.doc["sessions"]:
            return None
        first = min(dates.parse_date(s["date"]) for s in self.doc["sessions"])
        last = self.history.last_lifting(first)
        if last is None:
            return None
        start, end = last + timedelta(days=1), first - timedelta(days=1)
        if end < start:
            return None
        gap = dates.Span(start, end)
        reasons = [f"an ill miss on {a['date']}" for a in history.annotations(self.root, "miss")
                   if a.get("tag") == "ill" and gap.start.isoformat() <= a["date"] <= gap.end.isoformat()]
        if not reasons and _ill_status_day(self.root, gap):
            reasons.append("an ill status day")
        return (first.isoformat(), reasons[0]) if reasons else None

    def derived_from(self, session_date, line):
        provenance = line.get("provenance")
        if provenance is not None and not infers_source(line):
            return provenance["derived_from"], provenance["inferred"]
        before = min(session_date, dates.parse_date(self.created) + timedelta(days=1))
        found = self.history.baselines(line["exercise_id"], before)
        return ({"date": found[0]["date"], "workout_id": found[0]["workout_id"]} if found else None), True

    def check_line(self, session, session_date, line, illness, first_back):
        facts = self.history.gap_facts(line["exercise_id"], session_date, first_back)
        band = band_for(facts["days_off"]) if facts["days_off"] is not None else None
        derived, inferred = self.derived_from(session_date, line)
        evidence = self.history.evidence(line["exercise_id"], session_date)
        working = [s for s in line["sets"] if overlay.is_working(s)]
        ceiling_of = self.rpe_ceiling(session, session_date, line, illness)
        ceiling = _line_ceiling([ceiling_of(s) for s in working])
        row = {
            "session_id": session["session_id"], "date": session["date"], "exercise_id": line["exercise_id"],
            "days_off": facts["days_off"], "band": band.id if band else None, "derived_from": derived,
            "inferred": inferred, "model_evidence": evidence,
            "feasibility": _feasibility("not_judged", ceiling, "No load check: the line has no data."),
        }
        self.lines.append(row)
        first_load = (session["session_id"], line["exercise_id"]) in self.no_data
        if first_load and first_loads.missing_load(line):
            return
        self.stale(session, line, working, facts, band, derived, illness, coach_set=first_load and not derived)
        self.caps_and_kit(session, line)
        row["feasibility"] = self.feasibility(session, line, working, facts, evidence, ceiling, ceiling_of)

    def rpe_ceiling(self, session, session_date, line, illness):
        """A function giving why a working set's RPE is a ceiling for recovery work rather than a target, or None.

        A recovery cap makes a ceiling of an RPE at or over it, or a missing one: the overlay cannot tell an RPE the
        cap lowered from one that already met it. An RPE under every cap stays a target.
        """
        if self.doc["kind"] == "deload":
            return lambda s: "a deload, light or return week"
        if (line.get("provenance") or {}).get("decay"):
            return lambda s: "a return-band line"
        caps = []
        if illness and session["date"] == illness[0]:
            caps.append((ILLNESS_RPE_CAP, "the first session after illness"))
        try:
            active = constraints.active(self.root, session["session_id"], line["exercise_id"], session_date)
        except ValidationError:
            active = []
        caps += [(c["value"], "an RPE cap constraint") for c in active if c["kind"] == "rpe_cap"]

        def why(set_):
            rpe = set_.get("rpe")
            return next((words for value, words in caps if rpe is None or rpe >= value - 1e-9), None)
        return why

    def stale(self, session, line, working, facts, band, derived, illness, coach_set=False):
        """R-24's stale-prescription problems, one flag each. A `coach_set` first load derives from no exposure, so
        the return-band decay has nothing to check it against."""
        problems = []
        if facts["newest"] is not None and band.id != RETURN_BANDS[0].id and not coach_set:
            problems += self.decay_problems(session, line, working, facts, band, derived)
        if illness and session["date"] == illness[0]:
            over = [s for s in working if s.get("rpe") is None or s["rpe"] > ILLNESS_RPE_CAP]
            if over:
                problems.append(f"{illness[1]} falls in the gap before this first session back, so every working "
                                f"set needs RPE {ILLNESS_RPE_CAP} or below ({len(over)} set(s) are not)")
        for problem in problems:
            self.flag("stale_prescription", session, line, f"{self.where(session, line)}: {problem}")

    def decay_problems(self, session, line, working, facts, band, derived):
        """The decay problems, worded without the days off or the newest exposure, which move with the history and
        would part a stored resolution from its flag (C22)."""
        lead = f"its days off fall in return band {band.id}"
        provenance = line.get("provenance") or {}
        decay = provenance.get("decay")
        if decay is None:
            return [f"{lead}, and the line is not decayed to it"]
        if decay["band"] != band.id:
            return [f"{lead}, but the line is decayed to band {decay['band']}"]
        problems = []
        source, unchecked = self.decay_source(line["exercise_id"], derived)
        if unchecked:
            problems.append(f"{lead}, but its load and sets cannot be checked against the decay: {unchecked}")
        sound = [s for s in working if self.sound(line, s.get("load"))]
        if source is not None and line["load_mode"] == "assisted":
            least, before = _least_load(sound), _least_load(source["sets"])
            if least is not None and before is not None:
                allowed = before - self.increment(line, session)
                if least < allowed - 1e-9:
                    problems.append(f"{lead}: assistance {_number(least)} is below the pre-layoff assistance of "
                                    f"{_number(before)} minus one increment ({_number(allowed)})")
        elif source is not None:
            top, before = _top_load(sound), _top_load(source["sets"])
            if top is not None and before is not None:
                allowed, words = self.decay_ceiling(line, session, before, band.load_factor)
                if top > allowed + 1e-9:
                    problems.append(f"{lead}: load {_number(top)} is above {words}")
        if source is not None and band.set_delta:
            most = max(1, len(source["sets"]) + band.set_delta)
            if len(working) > most:
                problems.append(f"{lead}: {len(working)} working sets, at most {most} after the band's "
                                f"{band.set_delta} from {len(source['sets'])}")
        if band.rpe_cap is not None:
            over = [s for s in working if s.get("rpe") is None or s["rpe"] > band.rpe_cap]
            if over:
                problems.append(f"{lead}: every working set needs RPE {band.rpe_cap} or below "
                                f"({len(over)} set(s) are not)")
        return problems

    def decay_ceiling(self, line, session, before, factor):
        """(heaviest decayed load, words): the load the kit makes for `before` × `factor` by the cut rule, else
        that product plus one increment when the kit is unknown."""
        target = before * factor
        try:
            available = available_loads(self.library, self.config, line["exercise_id"], line["load_mode"],
                                        session["location"]) if self.library is not None else None
        except ConfigError:
            available = None
        if available is not None and available.declarable and not available.geometry_warning:
            allowed = available.select_cut(target, before)
            if allowed is not None:
                return allowed, (f"{_number(allowed)}, the kit's nearest load to {_number(before)} × {factor} "
                                 f"({_number(target)}) no heavier than {_number(before)}")
        allowed = target + self.increment(line, session)
        return allowed, f"{_number(before)} × {factor} plus one increment ({_number(allowed)})"

    def decay_source(self, exercise_id, derived):
        """The exposure a decayed line derives from, or None and why it can't serve as the baseline."""
        if not derived:
            return None, "provenance.derived_from is null"
        source = next((e for e in self.history.exposures.get(exercise_id, [])
                       if e["workout_id"] == derived["workout_id"]), None)
        if source is None:
            return None, f"derived_from names workout {derived['workout_id']}, which the history does not hold"
        if source["suspect"]:
            return None, (f"derived_from names workout {derived['workout_id']}, an open convention-slip "
                          "candidate")
        return source, None

    def increment(self, line, session):
        if self.library is None:
            return 0
        return stats.load_increment(self.library, self.config, line["exercise_id"], session["location"]) or 0

    def caps_and_kit(self, session, line):
        loads = [s["load"] for s in line["sets"] if self.sound(line, s.get("load"))]
        if not loads:
            return
        try:
            cap, source = cap_for(self.config, line["exercise_id"], line["load_mode"], session["location"])
            available = available_loads(self.library, self.config, line["exercise_id"], line["load_mode"],
                                        session["location"])
        except ConfigError:
            return
        per_hand = " per hand" if line["load_mode"] in units.PER_HAND_MODES else ""
        over = [load for load in loads if cap is not None and capped_value(load) > cap]
        if over:
            heaviest = max(over, key=capped_value)
            self.flag("load_cap", session, line,
                      f"{self.where(session, line)}: {self.load_text(heaviest)} is above the {source} cap of "
                      f"{units.json_number(cap)} {self.unit}{per_hand}")
        within = [load for load in loads if load not in over]
        if available.geometry_warning:
            self.flag("load_geometry_unknown", session, line,
                      f"{self.where(session, line)}: {available.geometry_warning}")
        missing = self.unbuildable(line, within, available)
        if missing:
            self.flag("load_unrepresentable", session, line,
                      f"{self.where(session, line)}: {', '.join(missing)} cannot be built from "
                      f"{_kit_name(session)}; correct the load, explicit ladder rung or equipment configuration")

    def load_text(self, load):
        return units.format_load(load, show_hevy=self.show_hevy)

    def unbuildable(self, line, loads, available):
        missing = []
        for load in loads:
            problem = available.problem(history.coaching_number(load))
            if problem:
                missing.append(f"{self.load_text(load)} ({problem})")
        return list(dict.fromkeys(missing))

    def feasibility(self, session, line, working, facts, evidence, ceiling, ceiling_of):
        """Flag what the e1RM model, or without it the load-step guard, finds; return the line's feasibility row."""
        sets = [(s, history.coaching_number(s["load"]), _targets(s)) for s in working
                if self.sound(line, s.get("load"))]
        sets = [(s, load, targets) for s, load, targets in sets if load and targets]
        if not sets:
            return _feasibility("not_judged", ceiling, "No loaded working set to judge.")
        if line["load_mode"] == "assisted":
            return _feasibility("not_judged", ceiling, "The e1RM model does not judge assisted lines.")
        best = evidence["estimate"] if line["load_mode"] in FEASIBILITY_MODES else None
        if best is None:
            self.unearned_without_e1rm(session, line, sets, facts, "there is no e1RM to judge it by")
            why = (evidence["message"] if line["load_mode"] in FEASIBILITY_MODES
                   else f"The e1RM model does not judge a {line['load_mode']} line.")
            return _feasibility("unavailable", ceiling, f"{why} No e1RM model check ran; only the load-step "
                                                        "guard applies.")
        if stats.is_lower_bound(best):
            self.unearned_without_e1rm(session, line, sets, facts, (
                f"the e1RM of {_number(best['e1rm'])} from {best['date']} comes from sets logged without RPE, so it "
                "cannot show a load beyond failure"))
        unearned, off = [], []
        for s, load, targets in sets:
            verdict = judge_set(best, load, targets, s.get("rpe"),
                                ceiling_of(s) is not None or bool(s.get("rep_out")))
            if verdict.unearned:
                unearned.append((verdict, s, targets))
            elif verdict.off:
                off.append((verdict, s, targets))
        basis = estimate_words(best)
        if unearned:
            verdict, s, targets = max(unearned, key=lambda item: item[0].implied)
            self.flag("unearned_load", session, line,
                      f"{self.where(session, line)}: {self.load_text(s['load'])} × "
                      f"{reps_words(verdict.reps, targets)} implies {implied_words(verdict.implied)} at {basis}")
        if off:
            verdict, s, targets = max(off, key=lambda item: abs(item[1]["rpe"] - item[0].implied))
            if s.get("rep_out"):
                kind, implies = "stop at RPE", "already implies"
            else:
                kind, implies = "RPE ceiling" if ceiling_of(s) else "target RPE", "implies"
            self.flag("rpe_infeasible", session, line,
                      f"{self.where(session, line)}: {kind} {units.json_number(s['rpe'])}, but "
                      f"{self.load_text(s['load'])} × {reps_words(verdict.reps, targets)} {implies} "
                      f"{implied_words(verdict.implied)} at {basis}")
        if stats.is_lower_bound(best):
            return _feasibility("lower_bound", ceiling, (
                f"Judged against {basis}: it can show a load too light for its RPE but never beyond failure, so the "
                "load-step guard applies too."))
        return _feasibility("checked", ceiling, f"Judged against {basis}.")

    def unearned_without_e1rm(self, session, line, sets, facts, no_model):
        baseline = facts["baseline"]
        if line["load_mode"] == "assisted" or baseline is None:
            return
        before = _top_load(baseline["sets"])
        step = self.increment(line, session)
        if before is None or not step:
            return
        top = max(load for _, load, _ in sets)
        if top > before + NO_E1RM_INCREMENTS * step + 1e-9:
            why = "" if e1rm_supported(line["exercise_id"]) else " (body mass dominates this movement)"
            self.flag("unearned_load", session, line,
                      f"{self.where(session, line)}: {_number(top)} is more than {NO_E1RM_INCREMENTS} increments "
                      f"of {_number(step)} above {_number(before)} on {baseline['date']}, and {no_model}{why}")

    def check_duration(self, session):
        cap = cap_minutes(self.config, session["session_id"])
        if cap is None:
            return
        minutes = _estimate(self.root, session, self.history.workouts())
        if minutes > cap:
            self.flag("session_over_cap", session, None,
                      f"{session['title']} on {session['date']}: estimated {minutes} min (a heuristic estimate) "
                      f"against a {cap} min cap")


def _line_ceiling(whys):
    """(why, ceiling sets, working sets) when some working set's RPE is a ceiling, else None."""
    found = [why for why in whys if why is not None]
    return (found[0], len(found), len(whys)) if found else None


def _feasibility(status, ceiling, message):
    """A prescription-check line's model verdict: `checked`, `lower_bound`, `unavailable` or `not_judged`, and
    whether its RPE is a target or a recovery ceiling (on any working set)."""
    if ceiling:
        why, count, total = ceiling
        if count < total:
            message += (f" Its RPE is a ceiling on {count} of {total} working sets ({why}), so only a load too hard "
                        "for it is flagged on those.")
        else:
            message += f" Its RPE is a ceiling ({why}), so only a load too hard for it is flagged."
    return {"status": status, "rpe": "ceiling" if ceiling else "target", "message": message}


def unconfirmed_flags(root, doc):
    """A `load_mode_unconfirmed` flag for each line whose exercise has no confirmed load mode.

    Raises ValidationError when the library cannot be read.
    """
    library = Library.load(root)
    return [_unconfirmed_flag(library, session, line)
            for session in doc["sessions"] for line in session["exercises"]
            if library.effective_load_mode(line["exercise_id"]) is None]


def _unconfirmed_flag(library, session, line):
    exercise_id = line["exercise_id"]
    return flags.make(UNCONFIRMED, session_id=session["session_id"], exercise_id=exercise_id, message=(
        f"{_where(session, line)}: no confirmed load mode in the library; once the athlete confirms how they load "
        f"it, run {library.mode_repair(exercise_id, line['load_mode'])}"))


def _where(session, line):
    return f"{line['exercise_id']} in {session['session_id']} on {session['date']}"


def _kit_name(session):
    return f"[equipment.locations.{session['location']}]" if session["location"] else "[equipment]"


def _ill_status_day(root, span):
    try:
        from coach import statusdays
    except ImportError:
        return False
    return statusdays.ill_in(root, span)


def report(root, doc, config=None):
    """{flags, lines} for an overlay: the R-24 flags and, per line, days off, band and the exposure it came from.

    Raises ValidationError when the overlay fails its schema; load
    arithmetic problems become `load_mode_mismatch` flags instead.
    """
    config = config if config is not None else config_module.load(root)
    found = overlay.problems(doc, root, config)
    schema_errors = [e for kind, e in found if kind == overlay.SCHEMA_PROBLEM]
    if schema_errors:
        raise ValidationError(f"The overlay is not valid ({len(schema_errors)} problem(s))",
                              details=[e.to_json() for e in schema_errors])
    arithmetic = [e for kind, e in found if kind == overlay.ARITHMETIC_PROBLEM]
    return _Checker(root, doc, config, arithmetic).run()


def check_overlay(root, doc):
    """The R-24 flags for an overlay."""
    return report(root, doc)["flags"]


def owned_codes():
    return {code for code, entry in flags.registry().items() if entry.owner == OWNER}


def flag_key(flag):
    return flag["code"], flag["severity"], flag["session_id"], flag["exercise_id"], flag["message"]


def merge_flags(doc, found):
    """The overlay's flags with every earlier R-24 flag replaced by `found`, keeping the resolution of identical ones.

    A missing load mode never keeps a resolution: only confirming the mode in the library settles it.
    """
    owned = owned_codes()
    earlier = {flag_key(f): f for f in doc["flags"] if f["code"] in owned and f["code"] != UNCONFIRMED}
    merged = [f for f in doc["flags"] if f["code"] not in owned]
    for flag in found:
        before = earlier.get(flag_key(flag))
        if before is not None:
            flag = dict(flag, resolved=before["resolved"], resolution=before["resolution"])
        merged.append(flag)
    return merged


def unresolved_blocks(doc, found):
    """The blocking findings in `found` that the overlay does not hold as resolved."""
    resolved = {flag_key(f) for f in doc["flags"] if f["resolved"] and f["code"] != UNCONFIRMED}
    return [f for f in found if f["severity"] == "block" and flag_key(f) not in resolved]


def earlier_wording(doc, flag):
    """The message of a resolved flag an approved overlay holds on `flag`'s code, severity, session and exercise, or
    None. An approved overlay cannot be re-checked, so its resolution stands when the history rewords the flag."""
    if not doc.get("approval") or flag["code"] == UNCONFIRMED:
        return None
    return next((f["message"] for f in doc["flags"] if f["resolved"] and flag_key(f)[:4] == flag_key(flag)[:4]), None)


def infers_source(line):
    """True when the checker infers the line's source exposure: a hand-built line, or an overridden one whose
    scheme named no exposure (the coach's sets replaced the scheme's, so its null source no longer describes them)."""
    provenance = line.get("provenance")
    return provenance is None or (provenance["derived_from"] is None and line.get("override") is not None)


def fill_provenance(doc, lines):
    """A copy of the overlay with every inferred source stored: a null provenance becomes one carrying the
    exposure, and an overridden line's null `derived_from` takes it, both marked `inferred`."""
    filled = dict(doc, sessions=[dict(s, exercises=[dict(line) for line in s["exercises"]]) for s in doc["sessions"]])
    rows = iter(lines)
    for session in filled["sessions"]:
        for line in session["exercises"]:
            row = next(rows)
            if line["provenance"] is None:
                line["provenance"] = {"scheme": None, "derived_from": row["derived_from"], "inferred": True,
                                      "decay": None, "rationale": None}
            elif infers_source(line) and row["derived_from"] is not None:
                line["provenance"] = dict(line["provenance"], derived_from=row["derived_from"], inferred=True)
    return filled
