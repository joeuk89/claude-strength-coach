"""Structure accounting: dose targets, planned against delivered dose, trailing adherence, static balance (contract C40, C41).

Planned and delivered dose count sets the same way (`coach.stats.set_weights`
and the same hard-set rule), so the two compare like for like. The 70 % and
80 % adherence thresholds and the three-of-four undershoot rule are coaching
heuristics (R-02), not research cut-offs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from coach import config as config_module
from coach import dates, decisions, flags, history, overlay, plugins, program, state, stats, validity
from coach.errors import ValidationError
from coach.library import Library
from coach.plugins import base

DEFAULT_TARGET = 10
SESSION_CEILING = 11.0
LOW_PCT = 70
ADD_SESSION_PCT = 80
WINDOW_WEEKS = 4
REACH_WEEKS = 12
UNDERSHOOT_WEEKS = 3
OVERRIDE_DAYS = 28
LAYOFF_AFTER_DAYS = validity.RETURN_BANDS[0].upper
RULES = ("restructure", "add_session")
OUTCOMES = ("adopted", "declined", "deferred")


def _round(value):
    return stats._round(value)


def _pct(trained, planned):
    if not planned:
        return None
    return int(Decimal(100 * trained / planned).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _as_date(value):
    return dates.parse_date(value) if isinstance(value, str) else value


def _add(totals, muscles, factor=1.0):
    for muscle, value in muscles.items():
        totals[muscle] = totals.get(muscle, 0.0) + value * factor


def _rounded(muscles):
    return {muscle: _round(value) for muscle, value in sorted(muscles.items()) if value}


def _is_hard(set_):
    return set_.get("type") in history.WORKING_SET_TYPES and (set_.get("rpe") is None or set_["rpe"] > stats.EASY_RPE)


def session_dose(library, session):
    """Fractional hard sets per muscle that one planned session prescribes: an overlay session or a program session.

    A program session's set groups count `count` sets each; an overlay lists every set.
    """
    muscles = {}
    for line in session["exercises"]:
        entry = library.get(line["exercise_id"])
        if entry is None:
            continue
        hard = sum(s.get("count", 1) for s in line["sets"] if _is_hard(s))
        if hard:
            _add(muscles, stats.set_weights(entry), hard)
    return muscles


def planned_dose(root, sessions):
    """Fractional hard sets per muscle the given planned sessions prescribe, summed."""
    library = Library.load(root)
    totals = {}
    for session in sessions:
        _add(totals, session_dose(library, session))
    return _rounded(totals)


def targets(program_doc, library=None):
    """The effective weekly dose targets: the program's `dose_targets`, else 10 for each primary muscle of a core exercise.

    Only active core sessions supply the default; a muscle no such exercise trains as a primary muscle has no target.
    """
    library = library or Library()
    found = {}
    for session in program_doc["sessions"]:
        if session["tier"] != "core" or session["status"] != "active" or session["kind"] != "lifting":
            continue
        for line in session["exercises"]:
            entry = library.get(line["exercise_id"])
            for muscle in entry["muscles"]["primary"] if entry else ():
                found[muscle] = DEFAULT_TARGET
    found.update(program_doc.get("dose_targets") or {})
    return {muscle: found[muscle] for muscle in sorted(found)}


def _over_ceiling(muscles):
    return {muscle: _round(value) for muscle, value in sorted(muscles.items()) if value > SESSION_CEILING}


def _ceiling_text(over):
    return ", ".join(f"{muscle} {value}" for muscle, value in over.items())


@dataclass
class _Instance:
    """Everything a structure run reads, read once."""

    root: Path
    today: object
    now: object
    config: object = None
    program: dict = None
    state: dict = None
    library: Library = None
    overlays: list = None
    decisions: dict = None
    _workouts: list = field(default=None, repr=False)

    @classmethod
    def load(cls, root, today=None, now=None, program_doc=None):
        root = Path(root)
        config = config_module.load(root)
        today = _as_date(today) or stats._today(config, now)
        return cls(root=root, today=today, now=now, config=config,
                   program=program_doc if program_doc is not None else program.load(root),
                   state=history.load_optional(state, root), library=Library.load(root),
                   overlays=overlay.list(root), decisions=decisions.load(root))

    @property
    def week_starts(self):
        return self.config.athlete.week_starts

    def week(self, day):
        return dates.week_span(day, self.week_starts)

    def workouts(self):
        if self._workouts is None:
            self._workouts = history.workouts(self.root, now=self.now)
        return self._workouts

    def made_on(self, decision):
        zone = self.config.athlete.timezone
        return dates.parse_timestamp(decision["made_at"]).astimezone(dates.zone(zone) if zone else None).date()

    def program_session(self, session_id, program_doc=None):
        doc = program_doc or self.program
        return next((s for s in doc["sessions"] if s["id"] == session_id), None)

    def tier(self, session_id):
        found = self.program_session(session_id)
        return found["tier"] if found else "core"

    def is_lifting(self, session_id, program_doc=None):
        found = self.program_session(session_id, program_doc)
        return found is None or found["kind"] == "lifting"


def _schedule(inst, program_doc, span, rotation=None):
    """(date, session id) the program's schedule rule plans in a span: active sessions only."""
    rule = program_doc["schedule"]["rule"]
    plugin = plugins.load(inst.root).get("schedule", rule)
    if plugin is None:
        raise ValidationError(f"The schedule rule {rule} is not a known schedule plugin; run python3 -m coach "
                              "program validate")
    params, errors = plugins.merged_params(plugin, program_doc["schedule"]["params"])
    if errors:
        raise ValidationError(f"The {rule} schedule params are not valid; run python3 -m coach program validate")
    if rotation is None:
        rotation = (inst.state or {}).get("rotation") or {}
    ctx = base.ScheduleContext(
        today=inst.today, span_start=span.start, span_end=span.end, week_starts=inst.week_starts, params=params,
        rotation=dict(rotation), sessions=tuple(program_doc["sessions"]),
        external_sessions=tuple(program_doc["external_sessions"]),
    )
    active = {s["id"] for s in program_doc["sessions"] if s["status"] == "active"}
    return sorted((day, sid) for day, sid in plugin.module.plan(ctx).sessions if span.contains(day) and sid in active)


def _program_session(session, day):
    """A program session dated `day`, in the overlay session shape adherence matching reads."""
    exercises = []
    for line in session["exercises"]:
        sets = []
        for group in line["sets"]:
            single = {key: value for key, value in group.items() if key != "count"}
            sets += [dict(single, load=None) for _ in range(group["count"])]
        exercises.append({"exercise_id": line["exercise_id"], "load_mode": line["load_mode"], "sets": sets})
    return {"session_id": session["id"], "date": day.isoformat(), "title": session["title"], "hevy_routine_id": None,
            "temporary": False, "location": session.get("location"), "exercises": exercises}


def _planned_pairs(inst, span):
    """(overlay, session) planned in a span: the overlay in force each day, else the schedule rule on the program."""
    pairs, uncovered = [], set()
    for day in span.days():
        found = overlay.pick_in_force(inst.overlays, day)
        if found:
            pairs += [(found[0], s) for s in overlay.sessions_on(found[0], day)]
        else:
            uncovered.add(day)
    if uncovered:
        stand_in = {"id": None, "kind": None, "span": span.to_json(), "sessions": []}
        for day, session_id in _schedule(inst, inst.program, span):
            if day in uncovered:
                pairs.append((stand_in, _program_session(inst.program_session(session_id), day)))
    return sorted(pairs, key=lambda pair: (pair[1]["date"], pair[1]["session_id"]))


def _external_rows(inst, span):
    """Coach-led sessions in a span: placed on their weekday, or on the dates their annotations name when they have none."""
    notes = [a for a in history.annotations(inst.root, "external") if span.contains(dates.parse_date(a["date"]))]
    rows = []
    for external in inst.program["external_sessions"]:
        own = [a for a in notes if a["external_id"] == external["id"]]
        if external["weekday"]:
            days = [d for d in span.days() if base.WEEKDAYS[d.weekday()] == external["weekday"]]
        else:
            days = sorted({dates.parse_date(a["date"]) for a in own})
        used = set()
        for day in days:
            candidates = [(abs((dates.parse_date(a["date"]) - day).days), -index, index)
                          for index, a in enumerate(own) if index not in used]
            note = None
            if candidates:
                index = min(candidates)[2]
                used.add(index)
                note = own[index]
            if note is not None:
                status = "done" if note["done"] else "not_done"
            else:
                status = "upcoming" if day > inst.today else "unconfirmed"
            rows.append({"external_id": external["id"], "title": external["title"], "date": day.isoformat(),
                         "status": status,
                         "estimated_sets": {m: float(v) for m, v in sorted(external["estimated_sets"].items())}})
    return sorted(rows, key=lambda r: (r["date"], r["external_id"]))


def _activity_dates(inst, until):
    """Dates any training happened, up to `until`: workouts, trained-unlogged sessions, coach-led sessions done."""
    found = {w["date"] for w in inst.workouts()}
    found |= {a["date"] for a in history.annotations(inst.root, "trained_unlogged")}
    newest = {(a["date"], a["external_id"]): a["done"] for a in history.annotations(inst.root, "external")}
    found |= {day for (day, _), done in newest.items() if done}
    return sorted(dates.parse_date(d) for d in found if d <= until.isoformat())


def _in_layoff(span, activity, until):
    """True when no training happened in the week and the gap around it is longer than the first return band."""
    if any(span.contains(day) for day in activity):
        return False
    before = [day for day in activity if day < span.start]
    if not before:
        return True
    after = [day for day in activity if day > span.end]
    following = after[0] if after else max(until, span.end) + timedelta(days=1)
    return (following - before[-1]).days > LAYOFF_AFTER_DAYS


def _light_decision(inst, span):
    for decision in inst.decisions["decisions"]:
        if (decision["kind"] == "light_week" and decision["outcome"] == "adopted"
                and decision["status"] != "withdrawn" and span.contains(dates.parse_date(decision["details"]["week"]))):
            return True
    return False


def _kind(inst, span, activity, until):
    kinds = set()
    for day in span.days():
        found = overlay.pick_in_force(inst.overlays, day)
        if found:
            kinds.add(found[0]["kind"])
    if "deload" in kinds or _light_decision(inst, span):
        return "light"
    if "one_off" in kinds:
        return "one_off"
    if _in_layoff(span, activity, until):
        return "layoff"
    return "ordinary"


def _history_start(inst):
    starts = [dates.parse_date(doc["span"]["start"]) for doc in inst.overlays]
    starts += [dates.parse_date(w["date"]) for w in inst.workouts()]
    return min(starts) if starts else None


def _closed_weeks(inst, until, reach):
    """Up to `reach` weeks ending on or before `until`, newest first, none ending before the history starts."""
    start = _history_start(inst)
    if start is None:
        return []
    span = inst.week(until)
    if span.end > until:
        span = inst.week(span.start - timedelta(days=1))
    found = []
    while len(found) < reach and span.end >= start:
        found.append(span)
        span = inst.week(span.start - timedelta(days=1))
    return found


def _scan(inst, until, reach=REACH_WEEKS):
    activity = _activity_dates(inst, until)
    return [(span, _kind(inst, span, activity, until)) for span in _closed_weeks(inst, until, reach)]


def _week_reports(inst, spans):
    """{span: report} for each week, from one adherence pass over all of them."""
    if not spans:
        return {}
    pairs = []
    for span in spans:
        pairs += _planned_pairs(inst, span)
    window = dates.Span(min(s.start for s in spans), max(s.end for s in spans))
    matched = stats.adherence_of(inst.root, pairs, window, today=inst.today, now=inst.now)
    sessions_by_key = {(s["date"], s["session_id"]): s for _, s in pairs}
    workouts = {w["workout_id"]: w for w in inst.workouts()}
    reports = {}
    for span in spans:
        rows = [r for r in matched["sessions"] if span.contains(dates.parse_date(r["date"]))]
        extra = [w for w in matched["extra"] if span.contains(dates.parse_date(w["date"]))]
        reports[span] = _report(inst, span, rows, extra, sessions_by_key, workouts)
    return reports


def _session_row(row, tier):
    found = {"session_id": row["session_id"], "date": row["date"], "tier": tier, "status": row["status"],
             "moved": row["moved"], "workout_id": row["workout_id"], "overlay_id": row["overlay_id"]}
    if row["status"] == "missed":
        found["tag"] = row["tag"]
    if row["unlogged"]:
        found["unlogged"] = True
    return found


def _workout_muscles(inst, workout):
    if workout is None or workout["conditioning"]:
        return {}
    return {m: v["fractional"] for m, v in stats._workout_dose(workout, inst.library).items()}


def _report(inst, span, rows, extra, sessions_by_key, workouts):
    target = targets(inst.program, inst.library)
    sessions, planned_dose_, delivered, bonus, by_session, raised = [], {}, {}, {}, {}, []
    counted_planned = counted_trained = 0
    logged = []
    for row in rows:
        tier = inst.tier(row["session_id"])
        sessions.append(_session_row(row, tier))
        workout = workouts.get(row["workout_id"])
        if tier == "core":
            if row["status"] != "upcoming":
                counted_planned += 1
                counted_trained += row["status"] == "trained"
            if inst.is_lifting(row["session_id"]):
                _add(planned_dose_, session_dose(inst.library, sessions_by_key[(row["date"], row["session_id"])]))
        if row["overlay_id"] is not None and inst.is_lifting(row["session_id"]):
            over = _over_ceiling(session_dose(inst.library, sessions_by_key[(row["date"], row["session_id"])]))
            if over:
                raised.append(flags.make(
                    "session_volume_high", "warn", session_id=row["session_id"],
                    message=f"{row['date']} {row['session_id']}: {_ceiling_text(over)} fractional sets planned in "
                            f"one session, above about {_round(SESSION_CEILING)}; move the excess to another session"))
        if workout is not None:
            muscles = _workout_muscles(inst, workout)
            _add(delivered if tier == "core" else bonus, muscles)
            logged.append((row["session_id"], row["date"], workout, muscles))
    for item in extra:
        workout = workouts.get(item["workout_id"])
        muscles = _workout_muscles(inst, workout)
        _add(bonus, muscles)
        logged.append((item["session_id"], item["date"], workout, muscles))
    for external in _external_rows(inst, span):
        sessions.append(external)
        if external["status"] in ("done", "not_done"):
            counted_planned += 1
            counted_trained += external["status"] == "done"
        if external["status"] != "unconfirmed":
            _add(planned_dose_, external["estimated_sets"])
        if external["status"] == "done":
            _add(delivered, external["estimated_sets"])

    ids = [session_id for session_id, _, workout, _ in logged if session_id and workout is not None]
    for session_id, day, workout, muscles in logged:
        if workout is None:
            continue
        if session_id:
            key = session_id if ids.count(session_id) == 1 else f"{session_id}@{day}"
            by_session[key] = _rounded(muscles)
        over = _over_ceiling(muscles)
        if over:
            raised.append(flags.make(
                "session_volume_high", "info", session_id=session_id,
                message=f"{day} {workout['title']}: {_ceiling_text(over)} fractional sets in one session, above "
                        f"about {_round(SESSION_CEILING)}; the sets past that add little"))

    names = sorted(set(target) | {m for d in (planned_dose_, delivered, bonus) for m, v in d.items() if v})
    muscles = {m: {"target": target.get(m), "planned": _round(planned_dose_.get(m, 0.0)),
                   "delivered": _round(delivered.get(m, 0.0)), "bonus": _round(bonus.get(m, 0.0))} for m in names}
    sessions.sort(key=lambda s: (s["date"], s.get("session_id") or s.get("external_id")))
    return {"week": span.start.isoformat(), "label": span.label(), "span": span.to_json(), "kind": None,
            "sessions": sessions, "planned": counted_planned, "trained": counted_trained, "muscles": muscles,
            "by_session": by_session, "flags": raised}


def week(root, week_start, *, today=None, now=None):
    """One week's sessions, planned and trained counts, and per-muscle target, planned, delivered and bonus dose."""
    inst = _Instance.load(root, today, now)
    span = inst.week(_as_date(week_start.start if isinstance(week_start, dates.Span) else week_start))
    report = _week_reports(inst, [span])[span]
    until = max(inst.today, span.end)
    report["kind"] = _kind(inst, span, _activity_dates(inst, until), until)
    return report


def ordinary_weeks(root, until, n=WINDOW_WEEKS, reach=REACH_WEEKS, *, today=None, now=None):
    """Start dates of the last `n` ordinary weeks ending on or before `until`, oldest first, within `reach` weeks."""
    inst = _Instance.load(root, today, now)
    until = _as_date(until) or inst.today
    found = [span for span, kind in _scan(inst, until, reach) if kind == "ordinary"][:n]
    return [span.start.isoformat() for span in reversed(found)]


def _ordinary_closed_since(inst, made_on, until):
    """How many ordinary weeks started after `made_on` and ended on or before `until`."""
    weeks = (until - made_on).days // 7 + 1
    return sum(1 for span, kind in _scan(inst, until, weeks) if kind == "ordinary" and span.start > made_on)


def _in_effect(inst, decision, until):
    if decision["kind"] != "adherence_trigger" or decision["status"] == "withdrawn":
        return False
    made_on = inst.made_on(decision)
    if made_on > until:
        return False
    if decision["details"]["rule"] == "add_session":
        return decision["outcome"] == "adopted" and (until - made_on).days <= OVERRIDE_DAYS
    if decision["outcome"] == "deferred":
        return decision["revisit_on"] is None or until < dates.parse_date(decision["revisit_on"])
    return _ordinary_closed_since(inst, made_on, until) < WINDOW_WEEKS


def _newest(found):
    return max(found, key=lambda d: (d["made_at"], d["id"])) if found else None


def _triggers(inst, until, rule=None):
    return [d for d in inst.decisions["decisions"] if d["kind"] == "adherence_trigger"
            and (rule is None or d["details"]["rule"] == rule) and inst.made_on(d) <= until]


def _restructure_suppressed(inst, until):
    newest = _newest(_triggers(inst, until, "restructure"))
    return newest is not None and _in_effect(inst, newest, until)


def _decision_in_effect(inst, until):
    return _newest([d for d in _triggers(inst, until) if _in_effect(inst, d, until)])


def _adherence(inst, until):
    scanned = _scan(inst, until)
    chosen = [span for span, kind in scanned if kind == "ordinary"][:WINDOW_WEEKS]
    reports = _week_reports(inst, chosen)
    oldest = chosen[-1].start if len(chosen) == WINDOW_WEEKS else None
    skipped = [{"week": span.start.isoformat(), "label": span.label(), "kind": kind}
               for span, kind in reversed(scanned) if kind != "ordinary" and (oldest is None or span.start > oldest)]
    weeks = [dict(reports[span], kind="ordinary") for span in reversed(chosen)]
    planned = sum(r["planned"] for r in weeks)
    trained = sum(r["trained"] for r in weeks)
    insufficient = len(weeks) < WINDOW_WEEKS
    raised = []
    if not insufficient and planned:
        ratio = 100 * trained / planned
        pct = _pct(trained, planned)
        span_text = f"{trained} of {planned} planned core and coach-led sessions ({pct} %) over the last " \
                    f"{len(weeks)} ordinary weeks"
        if ratio < LOW_PCT:
            raised.append(flags.make("adherence_low", message=f"{span_text}: below {LOW_PCT} %"))
        if ratio < ADD_SESSION_PCT:
            raised.append(flags.make(
                "add_session_type_blocked",
                message=f"{span_text}: below {ADD_SESSION_PCT} %, so no new recurring session without a recorded "
                        "override (structure decide --rule add_session)"))
        if ratio < LOW_PCT and not _restructure_suppressed(inst, until):
            raised.append(flags.make(
                "restructure_required",
                message=f"{span_text}: present a smaller schedule, then record the athlete's answer with "
                        "structure decide --rule restructure"))
        raised += _delivered_undershoot(weeks)
    return {"until": until.isoformat(),
            "weeks": [{"week": r["week"], "label": r["label"], "planned": r["planned"], "trained": r["trained"]}
                      for r in weeks],
            "skipped": skipped, "planned": planned, "trained": trained, "pct": _pct(trained, planned),
            "insufficient_weeks": insufficient, "flags": raised,
            "decision": _decision_in_effect(inst, until)}, weeks


def _delivered_undershoot(weeks):
    short = {}
    for report in weeks:
        for muscle, row in report["muscles"].items():
            if row["target"] is not None and row["delivered"] + row["bonus"] < row["target"]:
                short.setdefault(muscle, []).append(report["label"])
    return [flags.make("volume_undershoot", message=(
                f"{muscle}: delivered below its target of {_round(weeks[0]['muscles'][muscle]['target'])} fractional "
                f"sets in {len(labels)} of the last {len(weeks)} ordinary weeks ({', '.join(labels)})"))
            for muscle, labels in sorted(short.items()) if len(labels) >= UNDERSHOOT_WEEKS]


def adherence(root, until=None, *, today=None, now=None):
    """Sessions trained over planned across the trailing four ordinary weeks, with the adherence flags (C41)."""
    inst = _Instance.load(root, today, now)
    return _adherence(inst, _as_date(until) or inst.today)[0]


def _cycle(inst, program_doc, reference):
    """[(position, [(date, session id)])] for each position of the schedule rule, planned in the reference week."""
    rule = program_doc["schedule"]["rule"]
    plugin = plugins.load(inst.root).get("schedule", rule)
    if plugin is None:
        raise ValidationError(f"The schedule rule {rule} is not a known schedule plugin; run python3 -m coach "
                              "program validate")
    params, _ = plugins.merged_params(plugin, program_doc["schedule"]["params"])
    positions = tuple(plugin.module.positions(params)) or (None,)
    found = []
    for position in positions:
        rotation = None
        if position is not None:
            rotation = {"position": position, "confirmed": True, "confirmed_at": None,
                        "week": reference.start.isoformat()}
        found.append((position, _schedule(inst, program_doc, reference, rotation)))
    return found


def _new_sessions(current, candidate):
    """Ids of sessions active in the candidate but not in the current program, and of new coach-led sessions."""
    active = {s["id"] for s in current["sessions"] if s["status"] == "active"} if current else set()
    externals = {e["id"] for e in current["external_sessions"]} if current else set()
    return ([s["id"] for s in candidate["sessions"] if s["status"] == "active" and s["id"] not in active]
            + [e["id"] for e in candidate["external_sessions"] if e["id"] not in externals])


def _balance(inst, program_doc, candidate):
    reference = inst.week(inst.today + timedelta(days=1))
    positions, totals = [], {}
    for position, planned in _cycle(inst, program_doc, reference):
        dose, rows = {}, []
        for day, session_id in planned:
            session = inst.program_session(session_id, program_doc)
            rows.append({"date": day.isoformat(), "session_id": session_id, "tier": session["tier"]})
            if session["tier"] == "core" and session["kind"] == "lifting":
                _add(dose, session_dose(inst.library, session))
        for external in program_doc["external_sessions"]:
            _add(dose, external["estimated_sets"])
        _add(totals, dose)
        positions.append({"position": position, "sessions": rows,
                          "external": [e["id"] for e in program_doc["external_sessions"]], "muscles": _rounded(dose)})
    average = {m: v / len(positions) for m, v in totals.items()}
    target = targets(program_doc, inst.library)
    names = sorted(set(target) | {m for m, v in average.items() if v})
    muscles = {m: {"target": target.get(m), "average": _round(average.get(m, 0.0)),
                   "met": None if m not in target else _round(average.get(m, 0.0)) >= target[m]} for m in names}
    raised = [flags.make("volume_undershoot", message=(
                f"{m}: planned {muscles[m]['average']} fractional sets a week on core and coach-led sessions, below "
                f"its target of {_round(target[m])}"))
              for m in names if muscles[m]["met"] is False]
    sessions = {}
    for session in program_doc["sessions"]:
        if session["status"] != "active" or session["kind"] != "lifting":
            continue
        dose = session_dose(inst.library, session)
        sessions[session["id"]] = _rounded(dose)
        over = _over_ceiling(dose)
        if over:
            raised.append(flags.make(
                "session_volume_high", "warn", session_id=session["id"],
                message=f"{session['id']}: {_ceiling_text(over)} fractional sets planned in one session, above "
                        f"about {_round(SESSION_CEILING)}; move the excess to another session"))
    result = {"reference_week": reference.label(), "positions": positions, "average": _rounded(average),
              "targets": target, "muscles": muscles, "by_session": sessions, "added": [], "adherence": None,
              "flags": raised}
    if candidate:
        added = _new_sessions(inst.program, program_doc)
        report, _ = _adherence(inst, inst.today)
        result.update(added=added, adherence={k: report[k] for k in ("pct", "planned", "trained",
                                                                       "insufficient_weeks")})
        blocked = (added and not report["insufficient_weeks"] and report["pct"] is not None
                   and 100 * report["trained"] / report["planned"] < ADD_SESSION_PCT)
        override = _newest([d for d in _triggers(inst, inst.today, "add_session") if _in_effect(inst, d, inst.today)])
        if blocked and override is None:
            for session_id in added:
                raised.append(flags.make(
                    "add_session_type_blocked", session_id=session_id,
                    message=f"{session_id} is a new recurring session and adherence is {report['pct']} % over the "
                            f"last {WINDOW_WEEKS} ordinary weeks, below {ADD_SESSION_PCT} %; add it only with an "
                            "override recorded by structure decide --rule add_session"))
    return result


def balance(root, program=None, *, today=None, now=None):
    """Static weekly balance on core sessions plus coach-led estimates; with `program`, a candidate is checked too."""
    inst = _Instance.load(root, today, now)
    return _balance(inst, program if program is not None else inst.program, program is not None)


def decision_line(pct, weeks, rule, outcome, reason, revisit_on):
    """R-02's adherence decision line for the check-in record."""
    head = f"Adherence trigger: {pct} % over {weeks} weeks: "
    if rule == "add_session":
        return f"{head}adopted (override: {reason})"
    if outcome == "declined":
        return f"{head}declined: {reason}"
    if outcome == "deferred":
        return f"{head}deferred to {revisit_on}"
    return f"{head}adopted"


def decide(root, rule, outcome, reason=None, revisit_on=None, *, today=None, now=None, dry_run=False):
    """Record the athlete's answer to the adherence trigger, or an override for a new session (C25), and its line."""
    if rule not in RULES:
        raise ValidationError(f"rule must be one of {', '.join(RULES)}")
    if outcome not in OUTCOMES:
        raise ValidationError(f"outcome must be one of {', '.join(OUTCOMES)}")
    inst = _Instance.load(root, today, now)
    report, _ = _adherence(inst, inst.today)
    if report["insufficient_weeks"] or report["pct"] is None:
        raise ValidationError(f"There is no adherence figure to decide on: {len(report['weeks'])} ordinary week(s) "
                              f"in the last {REACH_WEEKS}, and the rule needs {WINDOW_WEEKS}")
    ratio = 100 * report["trained"] / report["planned"]
    reason = reason.strip() if reason else None
    if rule == "add_session":
        if outcome != "adopted":
            raise ValidationError("An add_session override is only ever adopted; without one, no session is added")
        if ratio >= ADD_SESSION_PCT:
            raise ValidationError(f"Adherence is {report['pct']} %, not below {ADD_SESSION_PCT} %; a new session "
                                  "needs no override")
        if not reason:
            raise ValidationError("--reason must name the session the override adds")
    elif ratio >= LOW_PCT:
        raise ValidationError(f"Adherence is {report['pct']} %, not below {LOW_PCT} %; there is no smaller-schedule "
                              "proposal to decide")
    if outcome == "declined" and not reason:
        raise ValidationError("--reason must say why the athlete declined")
    if outcome == "deferred":
        if revisit_on is None:
            raise ValidationError("--revisit D is the date a deferred decision comes back")
        if revisit_on <= inst.today:
            raise ValidationError(f"--revisit {revisit_on} must be after today ({inst.today})")
    elif revisit_on is not None:
        raise ValidationError("--revisit applies to a deferred decision only")
    revisit_text = revisit_on.isoformat() if revisit_on else None
    if not reason:
        reason = f"deferred to {revisit_text}" if outcome == "deferred" else "smaller schedule adopted"
    moment = inst.now or datetime.now(timezone.utc)
    made_on = inst.today
    decision = {
        "id": None, "kind": "adherence_trigger", "made_at": moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "overlay_id": None,
        "scope": {}, "outcome": outcome, "reason": reason, "standing": False,
        "until": (made_on + timedelta(days=OVERRIDE_DAYS)).isoformat() if rule == "add_session" else None,
        "revisit_on": revisit_text, "proposed_sets": None, "chosen_sets": None,
        "details": {"rule": rule, "adherence_pct": report["pct"], "weeks": [w["week"] for w in report["weeks"]]},
        "status": "active", "closed_at": None, "closed_reason": None,
    }
    _, decision = decisions.append(root, inst.decisions, decision, dry_run)
    line = decision_line(report["pct"], len(report["weeks"]), rule, outcome, reason, revisit_text)
    return {"decision": decision, "line": line,
            "adherence": {k: report[k] for k in ("pct", "planned", "trained", "weeks")}, "written": not dry_run}
