"""The evidence behind a closed week's fatigue triggers: RPE drift, niggle flares, sleep and recovery ceilings (C43).

The drift eligibility (an earlier at-prescription exposure that did not drift,
sets matched to their own prescription, recovery work left out) is application
policy around rn:autoregulation.4, a low-confidence heuristic, not a validated
fatigue test.
"""

from dataclasses import dataclass

from coach import cardio, constraints, niggles, patterns

CITES = ("rn:autoregulation.4",)
RECOVERY_INTENTS = ("deload", "light", "return")
INTENT_WORDS = {"deload": "deload work", "light": "light-week work", "return": "return work"}


@dataclass(frozen=True)
class _Read:
    """One exposure for drift: `verdict` `drift`, `steady` or `unknown`, and `why` an unknown one is not comparable."""

    exposure: object
    intent: str
    cap: object
    in_scope: bool
    reading: object
    verdict: str
    why: object

    def to_json(self):
        reading = self.reading
        return {"date": self.exposure.date.isoformat(), "workout_id": self.exposure.workout_id,
                "session_id": self.exposure.session_id, "intent": self.intent, "verdict": self.verdict,
                "why": self.why, "compared_sets": reading.compared if reading else 0,
                "over_sets": list(reading.over) if reading else [],
                "set_aside": [{"set": n, "reason": why} for n, why in reading.set_aside] if reading else []}


def intent_of(inst, exposure):
    """What the exposure was for (`coach.capacity`): normal, deload, light, return or reduced."""
    workout = inst.workout(exposure.workout_id) or {}
    raw = {"date": exposure.date.isoformat(), "session_id": exposure.session_id, "exercise_id": exposure.exercise_id,
           "load_mode": exposure.load_mode, "overlay_id": workout.get("overlay_id"),
           "start_time": workout.get("start_time")}
    return inst.run().recovery().for_exposure(raw)["kind"]


def _rpe_caps(inst, exposure):
    if not exposure.session_id:
        return []
    return [c for c in constraints.active(inst.root, exposure.session_id, exposure.exercise_id, exposure.date)
            if c["kind"] == "rpe_cap"]


def _read(inst, exposure, entry):
    caps = _rpe_caps(inst, exposure)
    cap = min((c["value"] for c in caps), default=None)
    intent = intent_of(inst, exposure)
    in_scope = patterns.is_compound(entry) or cap is not None
    why = None
    if intent in RECOVERY_INTENTS:
        why = intent
    elif exposure.suspect:
        why = "suspect"
    elif not exposure.prescribed:
        why = "no_prescription"
    reading = None if why else patterns.drift_reading(exposure.sets, exposure.prescribed, cap, exposure.load_mode)
    verdict = "unknown"
    if reading is not None and reading.drifted:
        verdict = "drift"
    elif reading is not None and reading.steady:
        verdict = "steady"
    elif reading is not None:
        why = "too_few_compared"
    return _Read(exposure, intent, cap, in_scope, reading, verdict, why)


def drift_review(inst, span):
    """Per compound or recovery-capped lift whose newest exposure is in `span`, how its two newest exposures read.

    `status`: `drift` when both drifted against their own prescriptions and an earlier exposure of the same load
    mode was at the prescription without drifting (the trigger); `calibration` when both drifted with no such
    exposure before them; `not_counted` when the logged RPE ran over target on enough sets but the sets were set
    aside or an exposure was not comparable. Lifts with none of these are left out.
    """
    by_exercise = {}
    for exposure in inst.run().exposures():
        if not exposure.excluded and exposure.date <= span.end:
            by_exercise.setdefault(exposure.exercise_id, []).append(exposure)
    found = []
    for exercise_id, exposures in sorted(by_exercise.items()):
        if not span.contains(exposures[0].date):
            continue
        entry = inst.library.get(exercise_id) or {}
        pair = [_read(inst, exposure, entry) for exposure in exposures[:2]]
        if not any(read.in_scope for read in pair):
            continue
        both = (len(pair) == 2 and all(read.in_scope and read.verdict == "drift" for read in pair)
                and pair[0].exposure.load_mode == pair[1].exposure.load_mode)
        baseline = None
        if both:
            mode = pair[0].exposure.load_mode
            baseline = next((exposure for exposure in exposures[2:] if exposure.load_mode == mode
                             and _read(inst, exposure, entry).verdict == "steady"), None)
            status = "drift" if baseline is not None else "calibration"
        elif any(_looked_over(read) for read in pair):
            status = "not_counted"
        else:
            continue
        found.append({"exercise_id": exercise_id, "name": entry.get("name", exercise_id), "status": status,
                      "exposures": [read.to_json() for read in pair],
                      "baseline": baseline.ref() if baseline is not None else None})
    return found


def _targets(read):
    targets = [s.rpe for s in read.exposure.prescribed if s.working]
    if read.cap is not None:
        targets = [read.cap if t is None else min(t, read.cap) for t in targets] or [read.cap]
    return targets


def _looked_over(read):
    """True when the logged RPE ran 1 or more over a prescribed target on enough working sets, compared or not."""
    targets = _targets(read)
    if not targets:
        return False
    logged = [s for s in read.exposure.sets if s.working]
    over = sum(1 for index, s in enumerate(logged) for target in [targets[min(index, len(targets) - 1)]]
               if target is not None and s.rpe is not None and s.rpe >= target + patterns.DRIFT_OVER_TARGET)
    return over >= patterns.DRIFT_MIN_SETS


def flares(inst, span, through):
    """Each niggle aggravated at some point from `span.start` through `through`, from its dated history (C27).

    A row already aggravated when the week began counts from that entry; a later status never erases an aggravated
    entry inside the window, and a flare that settled before the week began does not count.
    """
    if not niggles.exists(inst.root):
        return []
    start, end = span.start.isoformat(), through.isoformat()
    found = []
    for row in niggles.load(inst.root, inst.library)["niggles"]:
        before = [entry for entry in row["history"] if entry["date"] < start]
        persisting = before[-1]["date"] if before and before[-1]["status"] == "aggravated" else None
        inside = [entry["date"] for entry in row["history"]
                  if start <= entry["date"] <= end and entry["status"] == "aggravated"]
        if persisting or inside:
            found.append({"id": row["id"], "area": row["area"], "aggravated_on": inside,
                          "aggravated_since": persisting, "status_now": row["status"]})
    return found


def sleep_reading(root, span):
    """The week's measured sleep: `poor` or `ok` by the `sleep_debt` rule over tracker and diary nights alike, else
    `unknown`, with the nights behind it."""
    evidence = cardio.sleep_evidence(root, span)
    if evidence is None:
        return {"value": "unknown", "source": "none", "why": "no activity source"}
    if evidence["debt"] is None:
        return dict(evidence, value="unknown", source="none",
                    why=f"{evidence['nights']} nights with hours asleep, under the {evidence['min_nights']} needed")
    return dict(evidence, value="poor" if evidence["debt"] else "ok", source="sleep_debt", why=None)


def ceiling_breaches(inst, span):
    """Each logged line in `span` over its recovery RPE ceiling: deload, light or return work's prescribed RPE, or an
    active RPE cap. Reported whether or not the exposure counts toward drift."""
    found = []
    for exposure in inst.run().exposures():
        if exposure.excluded or not span.contains(exposure.date):
            continue
        intent = intent_of(inst, exposure)
        caps = _rpe_caps(inst, exposure)
        cap = min((c["value"] for c in caps), default=None)
        prescribed = [s.rpe for s in exposure.prescribed if s.working]
        recovery = intent in RECOVERY_INTENTS and any(rpe is not None for rpe in prescribed)
        if not recovery and cap is None:
            continue
        lowest = min((rpe for rpe in prescribed if rpe is not None), default=None)
        sets = []
        for index, logged in enumerate(s for s in exposure.sets if s.working):
            ceiling = None
            if recovery:
                ceiling = prescribed[index] if index < len(prescribed) and prescribed[index] is not None else lowest
            if cap is not None:
                ceiling = cap if ceiling is None else min(ceiling, cap)
            if ceiling is not None and logged.rpe is not None and logged.rpe > ceiling + 1e-9:
                sets.append({"set": index + 1, "rpe": logged.rpe, "ceiling": ceiling})
        if sets:
            why = [INTENT_WORDS[intent]] if recovery else []
            why += [f"RPE cap {c['value']:g} ({c['reason']})" for c in caps]
            found.append({"date": exposure.date.isoformat(), "session_id": exposure.session_id,
                          "exercise_id": exposure.exercise_id, "workout_id": exposure.workout_id,
                          "intent": intent, "why": "; ".join(why), "sets": sets})
    return sorted(found, key=lambda b: (b["date"], b["session_id"] or "", b["exercise_id"]))
