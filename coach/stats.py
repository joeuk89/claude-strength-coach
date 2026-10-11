"""Stats derived from the resolved history: e1RM, adherence, dose, durations, audit (contract C18).

Every read applies annotations (C17). Loads are the coaching number in
athlete units: per hand for per-hand modes, the total otherwise, the added
load for bodyweight and the assistance for assisted. This module is the
only place an e1RM is computed.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from coach import config as config_module
from coach import bodyweight as bodyweight_module
from coach import capacity, dates, flags, history, overlay, program, state, units
from coach.config_tables.sessions import cap_minutes
from coach.hevy.cache import HevyCache
from coach.library import Library, e1rm_supported

MAX_REPS_TO_FAILURE = 12
EASY_RPE = 5
CITES = ("rn:autoregulation.5", "rn:proximity-to-failure.5")
BODYWEIGHT_WINDOW_DAYS = 14
SERIES_MODES = ("total", "per_hand_x2", "single_implement")
BODYWEIGHT_MODES = ("bodyweight", "assisted")
TOTAL_SYSTEM = "total_system"
LOAD_BASIS = "load"
TOTAL_SYSTEM_LABEL = "total system mass"
PRIMARY_WEIGHT = 1.0
SECONDARY_WEIGHT = 0.5
_EQUIPMENT_INCREMENT = {
    "dumbbell": "dumbbell_increment", "kettlebell": "dumbbell_increment", "barbell": "barbell_increment",
    "ez_bar": "barbell_increment", "trap_bar": "barbell_increment", "smith_machine": "barbell_increment",
    "plate": "barbell_increment", "machine": "machine_increment", "cable": "cable_increment",
}


def _round(value, places=2):
    """Round half up, as a JSON number."""
    quantised = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return units.json_number(float(quantised))


def reps_to_failure(reps, rpe):
    return reps + (10 - rpe) if rpe is not None else reps


def e1rm(load, reps, rpe=None):
    """Epley e1RM, with reps in reserve (10 − RPE) added when RPE is logged; None past 12 reps to failure."""
    if load is None or reps is None or reps < 1:
        return None
    n = reps_to_failure(reps, rpe)
    if n > MAX_REPS_TO_FAILURE:
        return None
    return load if n <= 1 else load * (1 + n / 30)


def load_for(e1rm_value, reps, rpe=None):
    """The load that gives `reps` at `rpe` for an e1RM: the inverse of `e1rm`."""
    n = reps_to_failure(reps, rpe)
    return e1rm_value if n <= 1 else e1rm_value / (1 + n / 30)


def implied_rpe(e1rm_value, load, reps):
    """The RPE a set implies at an e1RM; above 10 means the load is beyond failure for those reps."""
    n = 30 * (e1rm_value / load - 1)
    if load <= e1rm_value:
        n = max(1, n)
    return 10 - (n - reps)


def set_weights(entry):
    """{muscle: weight} for one set of a library entry: 1.0 per primary muscle, 0.5 per secondary."""
    weights = {muscle: SECONDARY_WEIGHT for muscle in entry["muscles"]["secondary"]}
    weights.update({muscle: PRIMARY_WEIGHT for muscle in entry["muscles"]["primary"]})
    return weights


def _today(config, now=None):
    zone_name = config.athlete.timezone
    moment = now or datetime.now(timezone.utc)
    return moment.astimezone(dates.zone(zone_name) if zone_name else None).date()


def _as_date(value):
    if value is None or isinstance(value, date):
        return value
    return dates.parse_date(value)


def _span(value):
    if value is None or isinstance(value, dates.Span):
        return value
    start, end = value
    return dates.Span(_as_date(start), _as_date(end))


def _bodyweight_on(found, day):
    """The C35 bodyweight observation nearest `day` within the window, as {value, date, source}."""
    item = bodyweight_module.nearest(found, day, BODYWEIGHT_WINDOW_DAYS)
    return None if item is None else {"value": item["value"], "date": item["date"], "source": item["source"]}


def _formula_load(exposure, logged, bodyweight):
    load = logged["load"]
    if load is None:
        return None
    if exposure["load_mode"] in SERIES_MODES:
        return history.coaching_number(load)
    if bodyweight is None:
        return None
    if exposure["load_mode"] == "bodyweight":
        return bodyweight["value"] + load["hevy_total"]
    return bodyweight["value"] - load["hevy_total"]


def basis_label(point):
    """The words a human display puts after an e1RM so its basis is clear: empty for an external-load e1RM."""
    return f" {TOTAL_SYSTEM_LABEL}" if point.get("basis") == TOTAL_SYSTEM else ""


def _unavailable(exposure, reason):
    if reason == "unsupported_exercise":
        message = ("no e1RM: body mass dominates this movement, so an estimate from the external load alone would "
                   "mislead; judge it by its logged reps and load")
    else:
        message = (f"no e1RM on {exposure['date']}: a total-system e1RM counts body mass, and no bodyweight "
                   f"observation lies within {BODYWEIGHT_WINDOW_DAYS} days of it; record one with bodyweight record, "
                   "as a Hevy body measurement or as a nutrition reading")
    sets = [{"set_index": s["index"], "load": history.coaching_number(s["load"]), "reps": s["reps"], "rpe": s["rpe"]}
            for s in exposure["sets"] if not s["discounted"] and not s["convention_unknown"]]
    return {"reason": reason, "message": message, "date": exposure["date"], "workout_id": exposure["workout_id"],
            "sets": sets}


def _estimate_set(exposure, logged, bodyweight, supported):
    number = _formula_load(exposure, logged, bodyweight)
    reps, rpe = logged["reps"], logged["rpe"]
    n = reps_to_failure(reps, rpe) if reps is not None else None
    reason = None
    if exposure["excluded"] or logged["discounted"] or logged["convention_unknown"]:
        reason = "excluded"
    elif exposure["suspect"]:
        reason = "suspect_convention"
    elif exposure["load_mode"] not in SERIES_MODES + BODYWEIGHT_MODES:
        reason = "unsupported_load_mode"
    elif not supported:
        reason = "unsupported_exercise"
    elif reps is not None and reps >= 1 and logged["load"] is not None and number is None:
        reason = "no_bodyweight_reading"
    elif number is None or reps is None or reps < 1:
        reason = "missing_load_or_reps"
    elif n > MAX_REPS_TO_FAILURE:
        reason = "over_rep_cap"
    value = e1rm(number, reps, rpe) if reason is None else None
    return {"set_index": logged["index"], "load": _round(number) if number is not None else None,
            "reps": reps, "rpe": rpe, "reps_to_failure": n,
            "e1rm": _round(value) if value is not None else None, "eligible": value is not None,
            "reason": reason, "method": "epley_rir" if rpe is not None else "epley"}


def e1rm_series(root, exercise_id=None, since=None, include_unsynced=False, now=None, as_of=None):
    """Comparable capacity series plus every exposure's estimate eligibility and context.

    `unavailable` explains an exercise whose newest exposure can give no e1RM: the movement has none
    (`unsupported_exercise`) or its total-system e1RM has no bodyweight reading (`no_bodyweight_reading`).
    `as_of` bounds workouts, annotations, recovery context and body weights.
    """
    config = config_module.load(root)
    until = _today(config, as_of).isoformat() if as_of else None
    readings = bodyweight_module.observations(root, config, config.athlete.units, until)
    since = str(since) if since else None
    series, observations, unavailable = {}, {}, {}
    recovery = capacity.Context(root, as_of)
    for exposure in history.all_exposures(root, include_unsynced, now, as_of):
        key = exposure["exercise_id"]
        if exercise_id and key != exercise_id:
            continue
        if since and exposure["date"] < since:
            continue
        supported = e1rm_supported(key)
        bodyweight = None
        if supported and exposure["load_mode"] in BODYWEIGHT_MODES:
            bodyweight = _bodyweight_on(readings, dates.parse_date(exposure["date"]))
        countable = not (exposure["excluded"] or exposure["suspect"]) and exposure["load_mode"] in (
            SERIES_MODES + BODYWEIGHT_MODES)
        gone = None
        if countable and not supported:
            gone = "unsupported_exercise"
        elif countable and exposure["load_mode"] in BODYWEIGHT_MODES and bodyweight is None:
            gone = "no_bodyweight_reading"
        if gone:
            unavailable[key] = _unavailable(exposure, gone)
        elif countable:
            unavailable.pop(key, None)
        sets = [_estimate_set(exposure, logged, bodyweight, supported) for logged in exposure["sets"]]
        usable = [s for s in sets if s["eligible"]]
        best_set = max(usable, key=lambda s: s["e1rm"]) if usable else None
        context = recovery.for_exposure(exposure)
        comparable = best_set is not None and context["kind"] == "normal"
        reason = (None if comparable else "unsupported_exercise" if gone == "unsupported_exercise"
                  else "recovery_context" if context["kind"] != "normal"
                  else "over_rep_cap" if any(s["reason"] == "over_rep_cap" for s in sets)
                  else sets[0]["reason"])
        observation = {"date": exposure["date"], "workout_id": exposure["workout_id"],
                       "session_id": exposure["session_id"], "load_mode": exposure["load_mode"],
                       "eligible": best_set is not None, "comparable": comparable, "reason": reason,
                       "context": context, "e1rm": best_set["e1rm"] if best_set else None, "sets": sets}
        observations.setdefault(key, []).append(observation)
        if comparable:
            point = {field: best_set[field] for field in ("e1rm", "method", "set_index", "load", "reps", "rpe")}
            point.update(date=exposure["date"], workout_id=exposure["workout_id"],
                         basis=TOTAL_SYSTEM if bodyweight else LOAD_BASIS, bodyweight=bodyweight)
            series.setdefault(key, []).append(point)
    best, delta = {}, {}
    for key, points in series.items():
        top = max(points, key=lambda p: (p["e1rm"], p["date"]))
        best[key] = {"e1rm": top["e1rm"], "date": top["date"]}
        delta[key] = _round(points[-1]["e1rm"] - points[-2]["e1rm"]) if len(points) > 1 else None
    return {"series": series, "best": best, "delta": delta, "observations": observations, "unavailable": unavailable}


RECOVERY_NOTES = {"deload": "deload (light week)", "light": "light week", "return": "return week",
                  "reduced": "reduced by an override"}


def capacity_note(observation):
    """Why an exposure that could carry an e1RM is left out of comparisons; None when nothing to say.

    Lifts no e1RM can come from, and exposures missing a load, reps or bodyweight reading, get no note.
    """
    if (observation["comparable"] or observation["load_mode"] not in SERIES_MODES + BODYWEIGHT_MODES
            or observation["reason"] == "unsupported_exercise"):
        return None
    kind = observation["context"]["kind"]
    if kind != "normal":
        return f"{RECOVERY_NOTES[kind]}, kept in the log and left out of e1RM changes"
    if observation["reason"] == "over_rep_cap":
        return f"more than {MAX_REPS_TO_FAILURE} reps from failure, too far for an e1RM"
    return None


def capacity_evidence(data, exercise_id, before, window_days):
    """The e1RM that may limit a prescription.

    Newer over-cap progression work at or above the load behind that e1RM makes it unavailable.
    """
    end = _as_date(before)
    start = (end - timedelta(days=window_days)).isoformat()
    points = [p for p in data["series"].get(exercise_id, []) if start <= p["date"] < end.isoformat()]
    best = max(points, key=lambda p: (p["e1rm"], p["date"])) if points else None
    newer = [o for o in data["observations"].get(exercise_id, [])
             if start <= o["date"] < end.isoformat() and o["date"] > (points[-1]["date"] if points else "")]
    # Return-week logs are the next week's progression baseline; deload, light and reduced work is not.
    outgrown = [o for o in newer if not o["eligible"] and o["context"]["kind"] in ("normal", "return")
                and any(s["reason"] == "over_rep_cap" and (best is None or s["load"] >= best["load"])
                        for s in o["sets"])]
    if outgrown:
        latest = outgrown[-1]
        return {"estimate": None, "reason": "over_rep_cap", "date": latest["date"],
                "message": f"e1RM unavailable: the {latest['date']} exposure was more than "
                           f"{MAX_REPS_TO_FAILURE} reps from failure, so older e1RMs no longer limit the load. "
                           "Load-step, equipment and return checks still apply."}
    return {"estimate": best, "reason": None if best else "no_comparable_estimate",
            "date": best["date"] if best else None,
            "message": (f"e1RM {units.json_number(best['e1rm'])} from {best['date']}." if best
                        else f"e1RM unavailable: no comparable e1RM in the last {window_days} days.")}


def _half(increment):
    return increment / 2


def load_increment(library, config, exercise_id, location):
    """The declared location step, then the library fallback, then the equipment default."""
    entry = library.get(exercise_id)
    key = _EQUIPMENT_INCREMENT.get(entry["equipment"]) if entry else None
    kit = config_module.equipment_for(config, location)
    declared = dict(config.declared_equipment)
    if location is not None:
        declared.update(declared.get("locations", {}).get(location, {}))
    if key in declared:
        return kit[key]
    step = library.increment(exercise_id, config.athlete.units)
    return step if step is not None else kit.get(key, 0)


def _target_reps(prescribed):
    if prescribed.get("reps") is not None:
        return prescribed["reps"]
    if prescribed.get("rep_range"):
        return prescribed["rep_range"]["start"]
    return None


def _exercise_status(line, logged_sets, increment):
    prescribed = [s for s in line["sets"] if overlay.is_working(s)]
    logged = [s for s in logged_sets if s["type"] in history.WORKING_SET_TYPES]
    result = {"exercise_id": line["exercise_id"], "sets_prescribed": len(prescribed), "sets_logged": len(logged),
              "rpe_delta": None}
    if not logged:
        return dict(result, status="missing")
    tolerance = _half(increment)
    under = len(logged) < len(prescribed)
    over = len(logged) > len(prescribed)
    deltas = []
    for want, got in zip(prescribed, logged):
        target = _target_reps(want)
        if target is not None and (got["reps"] is None or got["reps"] < target):
            under = True
        want_load, got_load = history.coaching_number(want.get("load")), history.coaching_number(got["load"])
        if want_load is not None and got_load is not None:
            if want_load - got_load > tolerance:
                under = True
            elif got_load - want_load > tolerance:
                over = True
        if want.get("rpe") is not None and got["rpe"] is not None:
            deltas.append(got["rpe"] - want["rpe"])
    if deltas:
        result["rpe_delta"] = _round(sum(deltas) / len(deltas))
    return dict(result, status="under" if under else "over" if over else "hit")


def _planned(root, overlays, overlay_id, span):
    if overlay_id:
        doc = overlay.load(root, overlay_id)
        planned = []
        for session in doc["sessions"]:
            found = overlay.pick_in_force(overlays, session["date"])
            if found and found[0]["id"] == doc["id"]:
                planned.append((doc, session))
        return planned, dates.Span(dates.parse_date(doc["span"]["start"]), dates.parse_date(doc["span"]["end"]))
    adopted = state.adopted(root, history.load_optional(state, root), overlays)
    return overlay.planned(overlays, span.days(), adopted, config_module.load(root).athlete.timezone), span


def _nearest(items, day, key):
    return min(items, key=lambda item: (abs((dates.parse_date(key(item)) - day).days), key(item)), default=None)


def adherence(root, overlay_id=None, span=None, include_unsynced=False, today=None, now=None, as_of=None):
    """Planned sessions against logged workouts, per session and exercise (C18 adherence per overlay).

    With `as_of`, only workouts started and annotations created by then count.
    """
    if (overlay_id is None) == (span is None):
        raise ValueError("give an overlay id or a span, not both")
    planned, window = _planned(root, overlay.list(root), overlay_id, _span(span))
    return dict(adherence_of(root, planned, window, include_unsynced, today, now, as_of), overlay_id=overlay_id)


def adherence_of(root, planned, window, include_unsynced=False, today=None, now=None, as_of=None):
    """`adherence` over given (overlay, session) pairs; a pair's overlay supplies the span its workouts match in.

    A session the schedule rule planned with no overlay in force comes paired with a stand-in overlay whose id is None.
    """
    config = config_module.load(root)
    today = _as_date(today) or _today(config, now)
    state_doc, program_doc = history.load_optional(state, root), history.load_optional(program, root)
    library = Library.load(root)

    spans = [window] + [dates.Span(dates.parse_date(d["span"]["start"]), dates.parse_date(d["span"]["end"]))
                        for d, _ in planned]
    found = history.workouts(root, min(s.start for s in spans), max(s.end for s in spans), include_unsynced, now,
                             as_of)
    found = {w["workout_id"]: w for w in found}

    pairs = []
    for position, (doc, session) in enumerate(planned):
        routine = history.routine_of(doc, session, state_doc)
        for workout in found.values():
            if not doc["span"]["start"] <= workout["date"] <= doc["span"]["end"]:
                continue
            carries = (routine is not None and workout["routine_id"] == routine if workout["source"] == "hevy"
                       else workout["session_id"] == session["session_id"])
            if carries:
                gap = abs((dates.parse_date(workout["date"]) - dates.parse_date(session["date"])).days)
                pairs.append((gap, workout["date"], position, workout["workout_id"]))
    matched, used = {}, set()
    for _, _, position, workout_id in sorted(pairs):
        if position not in matched and workout_id not in used:
            matched[position] = workout_id
            used.add(workout_id)

    unlogged_notes = history.annotations(root, "trained_unlogged", as_of)
    misses = history.annotations(root, "miss", as_of)
    sessions, used_notes, miss_pairs = [], set(), []
    for position, (doc, session) in enumerate(planned):
        day = dates.parse_date(session["date"])
        in_span = (lambda a, d=doc, s=session: a["session_id"] == s["session_id"]
                   and (d["span"]["start"] <= a["date"] <= d["span"]["end"] or a["date"] == s.get("moved_from")))
        row = {"session_id": session["session_id"], "date": session["date"], "title": session["title"],
               "overlay_id": doc["id"], "status": None, "workout_id": None, "workout_date": None, "moved": False,
               "unlogged": False, "tag": None, "exercises": []}
        conditioning = history.is_conditioning(row, program_doc)
        note = None
        if position not in matched:
            note = _nearest([a for a in unlogged_notes if in_span(a) and a["id"] not in used_notes], day,
                            lambda a: a["date"])
        if position in matched:
            workout = found[matched[position]]
            row.update(status="trained", workout_id=workout["workout_id"], workout_date=workout["date"],
                       moved=workout["date"] != session["date"])
            if not conditioning:
                location = session.get("location")
                for line in session["exercises"]:
                    logged = [s for e in workout["exercises"] if e["exercise_id"] == line["exercise_id"]
                              for s in e["sets"]]
                    increment = load_increment(library, config, line["exercise_id"], location)
                    row["exercises"].append(_exercise_status(line, logged, increment))
        elif note is not None:
            used_notes.add(note["id"])
            row.update(status="trained", unlogged=True, workout_date=note["date"],
                       moved=note["date"] != session["date"])
            if not conditioning:
                row["exercises"] = [{"exercise_id": line["exercise_id"], "status": "unknown",
                                     "sets_prescribed": sum(1 for s in line["sets"] if overlay.is_working(s)),
                                     "sets_logged": None, "rpe_delta": None} for line in session["exercises"]]
        elif day > today:
            row["status"] = "upcoming"
        else:
            row.update(status="missed", tag="untagged")
            miss_pairs += [(abs((dates.parse_date(a["date"]) - day).days), a["date"], position, a["id"], a)
                           for a in misses if in_span(a)]
        if conditioning:
            row["conditioning"] = True
        sessions.append(row)
    tagged, used_misses = set(), set()
    for _, _, position, miss_id, miss in sorted(miss_pairs, key=lambda p: p[:4]):
        if position not in tagged and miss_id not in used_misses:
            sessions[position]["tag"] = miss.get("tag") or "untagged"
            tagged.add(position)
            used_misses.add(miss_id)

    extra = [{"workout_id": w["workout_id"], "date": w["date"], "title": w["title"], "session_id": w["session_id"],
              "unsynced": w["unsynced"]}
             for w in found.values() if w["workout_id"] not in used and window.contains(dates.parse_date(w["date"]))]
    summary = {
        "planned": sum(1 for s in sessions if s["status"] != "upcoming"),
        "trained": sum(1 for s in sessions if s["status"] == "trained"),
        "missed": {}, "missed_total": sum(1 for s in sessions if s["status"] == "missed"),
        "upcoming": sum(1 for s in sessions if s["status"] == "upcoming"),
        "exercises": {status: 0 for status in ("hit", "under", "over", "missing", "unknown")},
    }
    for row in sessions:
        if row["status"] == "missed":
            summary["missed"][row["tag"]] = summary["missed"].get(row["tag"], 0) + 1
        for line in row["exercises"]:
            summary["exercises"][line["status"]] += 1
    return {"overlay_id": None, "span": window.to_json(), "today": today.isoformat(), "sessions": sessions,
            "extra": sorted(extra, key=lambda w: (w["date"], w["workout_id"])), "summary": summary}


def _week_label(span):
    try:
        return span.label()
    except ValueError:
        return None


def _add(muscles, muscle, direct, fractional):
    entry = muscles.setdefault(muscle, {"direct": 0, "fractional": 0})
    entry["direct"] += direct
    entry["fractional"] += fractional


def _rounded(muscles):
    return {m: {"direct": v["direct"], "fractional": _round(v["fractional"])} for m, v in sorted(muscles.items())}


def _workout_dose(workout, library):
    muscles = {}
    for exercise in workout["exercises"]:
        entry = library.get(exercise["exercise_id"]) if exercise["exercise_id"] else None
        if entry is None:
            continue
        hard = sum(1 for s in exercise["sets"]
                   if s["type"] in history.WORKING_SET_TYPES and (s["rpe"] is None or s["rpe"] > EASY_RPE))
        if not hard:
            continue
        for muscle, weight in set_weights(entry).items():
            _add(muscles, muscle, hard if weight == PRIMARY_WEIGHT else 0, hard * weight)
    return muscles


def dose(root, week=None, span=None, include_unsynced=False, now=None):
    """Hard sets delivered per muscle, direct and fractional, for a week or span (C18 dose)."""
    config = config_module.load(root)
    week_starts = config.athlete.week_starts
    if week is not None:
        window = dates.parse_week(str(week), week_starts) if not isinstance(week, dates.Span) else week
    else:
        window = _span(span)
    library = Library.load(root)
    totals, by_workout, weekly = {}, {}, {}
    for workout in history.workouts(root, window.start, window.end, include_unsynced, now):
        if workout["conditioning"]:
            continue
        muscles = _workout_dose(workout, library)
        week_span = dates.week_span(dates.parse_date(workout["date"]), week_starts)
        for muscle, value in muscles.items():
            _add(totals, muscle, value["direct"], value["fractional"])
            _add(weekly.setdefault(week_span, {}), muscle, value["direct"], value["fractional"])
        by_workout[workout["workout_id"]] = {"date": workout["date"], "session_id": workout["session_id"],
                                             "muscles": _rounded(muscles)}
    weeks = []
    day = window.start
    while day <= window.end:
        week_span = dates.week_span(day, week_starts)
        weeks.append({"week": week_span.label(), "span": week_span.to_json(),
                      "muscles": _rounded(weekly.get(week_span, {}))})
        day = week_span.end + timedelta(days=1)
    return {"week": _week_label(window), "span": window.to_json(), "muscles": _rounded(totals),
            "by_workout": by_workout, "weeks": weeks}


def durations(root, span=None, include_unsynced=False, now=None):
    """Each workout's minutes against its session cap (C19), with a duration_over_cap flag per breach."""
    config = config_module.load(root)
    window = _span(span)
    found = history.workouts(root, window.start if window else None, window.end if window else None,
                             include_unsynced, now)
    rows, raised = [], []
    for workout in found:
        cap = cap_minutes(config, workout["session_id"])
        minutes = workout["duration_minutes"]
        over = minutes is not None and cap is not None and minutes > cap
        rows.append({"workout_id": workout["workout_id"], "date": workout["date"], "title": workout["title"],
                     "session_id": workout["session_id"], "minutes": minutes, "cap_minutes": cap, "over_cap": over})
        if over:
            raised.append(flags.make("duration_over_cap", session_id=workout["session_id"],
                                     message=f"{workout['date']} {workout['title']}: {minutes} min against a "
                                             f"{cap} min cap"))
    return {"span": window.to_json() if window else None, "workouts": rows, "flags": raised}


def audit(root, weeks=8, include_unsynced=False, today=None, now=None):
    """Convention-slip candidates over the last `weeks` weeks, with a convention_slip flag per open one."""
    config = config_module.load(root)
    today = _as_date(today) or _today(config, now)
    start = today - timedelta(weeks=weeks)
    exposures = history.all_exposures(root, include_unsynced, now)
    candidates = [c for c in history.slip_candidates(exposures, history.annotations(root))
                  if start.isoformat() <= c["date"] <= today.isoformat()]
    raised = [flags.make("convention_slip", session_id=c["session_id"], exercise_id=c["exercise_id"],
                         message=f"{c['exercise_id']} on {c['date']}: top load {c['top_load']} is {c['ratio']}× "
                                 f"{c['previous']['top_load']} on {c['previous']['date']} at the same reps and RPE; "
                                 "confirm or discount it with python3 -m coach history annotate")
              for c in candidates if c["status"] == "open"]
    return {"weeks": weeks, "span": {"start": start.isoformat(), "end": today.isoformat()},
            "candidates": candidates, "flags": raised}
