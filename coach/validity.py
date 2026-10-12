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
from coach import dates, flags, history, overlay, state, stats, units
from coach.checks.instance import _capped_value as capped_value
from coach.checks.instance import cap_for
from coach.config_tables.sessions import cap_minutes
from coach.errors import ConfigError, ValidationError
from coach.library import Library, e1rm_supported

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

    def gap_facts(self, exercise_id, session_date):
        """Days off and how they were measured, for one exercise before one session date."""
        layoff_from = self.last_lifting(session_date)
        layoff = (session_date - layoff_from).days if layoff_from else None
        found = self.usable(exercise_id, session_date)
        newest = found[0] if found else None
        age = (session_date - dates.parse_date(newest["date"])).days if newest else None
        interval = interval_days(found) if found else None
        candidates = [value for value in (layoff, age - interval if newest else None) if value is not None]
        baseline = next((e for e in found if not e["suspect"]), None)
        return {"days_off": max(0, *candidates) if candidates else None, "layoff_days": layoff,
                "exposure_age": age, "interval_days": interval, "newest": newest, "baseline": baseline}


def days_off(root, exercise_id, session_date):
    """Days off for an exercise before a session: the longer of the layoff and its exposure age past its usual gap.

    None when there is no lifting workout and no exposure to measure from.
    """
    return _History(root).gap_facts(exercise_id, _day(session_date))["days_off"]


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


def _reps(set_):
    if set_.get("reps") is not None:
        return set_["reps"]
    if set_.get("rep_range"):
        return set_["rep_range"]["start"]
    return None


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
        for session in self.doc["sessions"]:
            session_date = dates.parse_date(session["date"])
            for line in session["exercises"]:
                self.check_line(session, session_date, line, illness)
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
        gap = dates.Span(last + timedelta(days=1), first - timedelta(days=1))
        if gap.end < gap.start:
            return None
        reasons = [f"an ill miss on {a['date']}" for a in history.annotations(self.root, "miss")
                   if a.get("tag") == "ill" and gap.start.isoformat() <= a["date"] <= gap.end.isoformat()]
        if not reasons and _ill_status_day(self.root, gap):
            reasons.append("an ill status day")
        return (first.isoformat(), reasons[0]) if reasons else None

    def derived_from(self, session_date, line):
        provenance = line.get("provenance")
        if provenance is not None:
            return provenance["derived_from"], provenance["inferred"]
        before = min(session_date, dates.parse_date(self.created) + timedelta(days=1))
        found = self.history.baselines(line["exercise_id"], before)
        return ({"date": found[0]["date"], "workout_id": found[0]["workout_id"]} if found else None), True

    def check_line(self, session, session_date, line, illness):
        facts = self.history.gap_facts(line["exercise_id"], session_date)
        band = band_for(facts["days_off"]) if facts["days_off"] is not None else None
        derived, inferred = self.derived_from(session_date, line)
        evidence = self.history.evidence(line["exercise_id"], session_date)
        self.lines.append({
            "session_id": session["session_id"], "date": session["date"], "exercise_id": line["exercise_id"],
            "days_off": facts["days_off"], "band": band.id if band else None, "derived_from": derived,
            "inferred": inferred, "model_evidence": evidence,
        })
        if (session["session_id"], line["exercise_id"]) in self.no_data:
            return
        working = [s for s in line["sets"] if overlay.is_working(s)]
        self.stale(session, line, working, facts, band, derived, illness)
        self.caps_and_kit(session, line)
        self.feasibility(session, line, working, facts, evidence)

    def stale(self, session, line, working, facts, band, derived, illness):
        problems = []
        if facts["newest"] is not None and band.id != RETURN_BANDS[0].id:
            problems += self.decay_problems(session, line, working, facts, band, derived)
        if illness and session["date"] == illness[0]:
            over = [s for s in working if s.get("rpe") is None or s["rpe"] > ILLNESS_RPE_CAP]
            if over:
                problems.append(f"{illness[1]} falls in the gap before this first session back, so every working "
                                f"set needs RPE {ILLNESS_RPE_CAP} or below ({len(over)} set(s) are not)")
        if problems:
            self.flag("stale_prescription", session, line, f"{self.where(session, line)}: {'; '.join(problems)}")

    def decay_problems(self, session, line, working, facts, band, derived):
        lead = (f"{facts['days_off']} days off (newest exposure {facts['newest']['date']}) fall in return band "
                f"{band.id}")
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
                allowed = before * band.load_factor + self.increment(line, session)
                if top > allowed + 1e-9:
                    problems.append(f"{lead}: load {_number(top)} is above {_number(before)} × {band.load_factor} "
                                    f"plus one increment ({_number(allowed)})")
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
            kit = config_module.equipment_for(self.config, session["location"])
        except ConfigError:
            return
        per_hand = " per hand" if line["load_mode"] in units.PER_HAND_MODES else ""
        over = [load for load in loads if cap is not None and capped_value(load) > cap]
        if over:
            heaviest = max(over, key=capped_value)
            self.flag("load_cap", session, line,
                      f"{self.where(session, line)}: {units.format_load(heaviest)} is above the {source} cap of "
                      f"{units.json_number(cap)} {self.unit}{per_hand}")
        within = [load for load in loads if load not in over]
        missing = self.unbuildable(line, within, kit)
        if missing:
            self.flag("load_unrepresentable", session, line,
                      f"{self.where(session, line)}: {', '.join(missing)} cannot be built from "
                      f"{_kit_name(session)}")

    def unbuildable(self, line, loads, kit):
        entry = self.library.get(line["exercise_id"]) if self.library else None
        equipment = entry["equipment"] if entry else None
        missing = []
        if equipment == "dumbbell" and line["load_mode"] in units.PER_HAND_MODES and kit.get("dumbbells"):
            have = {units.json_number(round(w, 4)) for w in kit["dumbbells"]}
            for load in loads:
                if units.json_number(round(load["per_hand"], 4)) not in have:
                    missing.append(f"{units.format_load(load)} (no {units.json_number(load['per_hand'])} "
                                   f"{self.unit} dumbbell)")
        elif equipment == "barbell" and line["load_mode"] == "total":
            for load in loads:
                if units.plate_breakdown(load["hevy_total"], kit["bar_weight"], kit["plates"]) is None:
                    missing.append(f"{units.format_load(load)} (no plate breakdown on a "
                                   f"{units.json_number(kit['bar_weight'])} {self.unit} bar)")
        return list(dict.fromkeys(missing))

    def feasibility(self, session, line, working, facts, evidence):
        sets = [(s, history.coaching_number(s["load"]), _reps(s)) for s in working if self.sound(line, s.get("load"))]
        sets = [(s, load, reps) for s, load, reps in sets if load and reps]
        if not sets:
            return
        best = evidence["estimate"] if line["load_mode"] in FEASIBILITY_MODES else None
        if best is None:
            self.unearned_without_e1rm(session, line, sets, facts)
            return
        unearned, infeasible = [], []
        for s, load, reps in sets:
            implied = stats.implied_rpe(best["e1rm"], load, reps)
            if implied > UNEARNED_IMPLIED_RPE:
                unearned.append((implied, s, load, reps))
            elif s.get("rpe") is not None and abs(s["rpe"] - implied) > RPE_TOLERANCE:
                infeasible.append((abs(s["rpe"] - implied), implied, s, load, reps))
        basis = f"the e1RM of {_number(best['e1rm'])} from {best['date']}"
        if unearned:
            implied, s, load, reps = max(unearned, key=lambda item: item[0])
            self.flag("unearned_load", session, line,
                      f"{self.where(session, line)}: {units.format_load(s['load'])} × {reps} implies RPE "
                      f"{_number(implied)} against {basis}, beyond failure")
        if infeasible:
            _, implied, s, load, reps = max(infeasible, key=lambda item: item[0])
            self.flag("rpe_infeasible", session, line,
                      f"{self.where(session, line)}: target RPE {units.json_number(s['rpe'])}, but "
                      f"{units.format_load(s['load'])} × {reps} implies RPE {_number(implied)} at {basis}")

    def unearned_without_e1rm(self, session, line, sets, facts):
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
                      f"of {_number(step)} above {_number(before)} on {baseline['date']}, and there is no "
                      f"e1RM to judge it by{why}")

    def check_duration(self, session):
        cap = cap_minutes(self.config, session["session_id"])
        if cap is None:
            return
        minutes = _estimate(self.root, session, self.history.workouts())
        if minutes > cap:
            self.flag("session_over_cap", session, None,
                      f"{session['title']} on {session['date']}: estimated {minutes} min (a heuristic estimate) "
                      f"against a {cap} min cap")


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


def fill_provenance(doc, lines):
    """A copy of the overlay with every null provenance filled with its inferred exposure."""
    filled = dict(doc, sessions=[dict(s, exercises=[dict(line) for line in s["exercises"]]) for s in doc["sessions"]])
    rows = iter(lines)
    for session in filled["sessions"]:
        for line in session["exercises"]:
            row = next(rows)
            if line["provenance"] is None:
                line["provenance"] = {"scheme": None, "derived_from": row["derived_from"], "inferred": True,
                                      "decay": None, "rationale": None}
    return filled
