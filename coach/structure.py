"""Structure accounting: dose targets, planned against delivered dose, trailing adherence, static balance (contract C40, C41).

Planned and delivered dose count sets the same way (`coach.stats.set_weights`
and the same hard-set rule), so the two compare like for like. The 70 % and
80 % adherence thresholds and the three-of-four undershoot rule are coaching
heuristics (R-02), not research cut-offs. `FALLBACK_TARGET` is the low end
of the weekly range (rn:volume-frequency.1), a hypertrophy starting fallback
only; `SESSION_CEILING` is the per-session ceiling (rn:volume-frequency.3).
`MINIMUM_SHARE` compares ordinary programmed dose as application policy
(rn:minimum-effective-dose.6). `COVERAGE` is a product choice of muscles every
balance report shows, not a claim that each needs its own exercise.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property
from pathlib import Path

from coach import config as config_module
from coach import dates, decisions, flags, history, jsonio, overlay, paths, plugins, program, state, stats, validity
from coach.config_tables.sessions import cap_minutes
from coach.errors import ValidationError
from coach.library import Library
from coach.plugins import base

FALLBACK_TARGET = 10
HYPERTROPHY = "hypertrophy"
COVERAGE = ("chest", "lats", "upper_back", "front_delts", "side_delts", "rear_delts", "biceps", "triceps",
            "abdominals", "quadriceps", "hamstrings", "glutes", "calves")
OLDER_LIFTER_AGE = 60
SESSION_CEILING = 11.0
LOW_PCT = 70
ADD_SESSION_PCT = 80
WINDOW_WEEKS = 4
REACH_WEEKS = 12
UNDERSHOOT_WEEKS = 3
OVERRIDE_DAYS = 28
LAYOFF_AFTER_DAYS = validity.RETURN_BANDS[0].upper
FLOOR_PREFIX = "priority:"
PRIORITY_DAYS = 28
MINIMUM_MAX_SESSIONS = 2
MINIMUM_SHARE = 1 / 3
VARIANTS = ("minimum",)
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


def dose_goal(program_doc):
    """The lifting-dose goal the design conversation recorded in `dose_intent`, or None when none was."""
    intent = program_doc.get("dose_intent")
    return intent["goal"] if intent else None


def _uses_fallback(program_doc):
    return dose_goal(program_doc) in (None, HYPERTROPHY)


def _core_primary_muscles(program_doc, library):
    found = set()
    for session in program_doc["sessions"]:
        if session["tier"] != "core" or session["status"] != "active" or session["kind"] != "lifting":
            continue
        for line in session["exercises"]:
            entry = library.get(line["exercise_id"])
            found.update(entry["muscles"]["primary"] if entry else ())
    return found


def targets(program_doc, library=None):
    """The effective weekly dose targets: the program's `dose_targets`, plus the hypertrophy starting fallback.

    The fallback gives 10 to each primary muscle of an exercise in an active core session, and only when
    `dose_intent` records no goal or hypertrophy; any other goal has no target until one is agreed.
    """
    library = library or Library()
    found = dict.fromkeys(_core_primary_muscles(program_doc, library), FALLBACK_TARGET) \
        if _uses_fallback(program_doc) else {}
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
    def load(cls, root, today=None, now=None, program_doc=None, require_program=True):
        root = Path(root)
        config = config_module.load(root)
        today = _as_date(today) or stats._today(config, now)
        if program_doc is None and (require_program or program.exists(root)):
            program_doc = program.load(root)
        return cls(root=root, today=today, now=now, config=config, program=program_doc,
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

    @cached_property
    def adopted(self):
        """The first day the current program plans sessions from its schedule rule and coach-led sessions."""
        return state.adopted(self.root, self.state, self.overlays)

    def schedules_on(self, day):
        return state.plans_on(self.adopted, day)

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


def _schedule(inst, program_doc, span, rotation=None, schedule=None, allowed=None):
    """(date, session id) a schedule rule plans in a span: the program's rule over its active sessions by default."""
    schedule = schedule or program_doc["schedule"]
    rule = schedule["rule"]
    plugin = plugins.load(inst.root).get("schedule", rule)
    if plugin is None:
        raise ValidationError(f"The schedule rule {rule} is not a known schedule plugin; run python3 -m coach "
                              "program validate")
    params, errors = plugins.merged_params(plugin, schedule["params"])
    if errors:
        raise ValidationError(f"The {rule} schedule params are not valid; run python3 -m coach program validate")
    if rotation is None:
        rotation = (inst.state or {}).get("rotation") or {}
    ctx = base.ScheduleContext(
        today=inst.today, span_start=span.start, span_end=span.end, week_starts=inst.week_starts, params=params,
        rotation=dict(rotation), sessions=tuple(program_doc["sessions"]),
        external_sessions=tuple(program_doc["external_sessions"]),
    )
    if allowed is None:
        allowed = {s["id"] for s in program_doc["sessions"] if s["status"] == "active"}
    return sorted((day, sid) for day, sid in plugin.module.plan(ctx).sessions if span.contains(day) and sid in allowed)


def _program_session(session, day):
    """A program session dated `day`, in the overlay session shape adherence matching reads."""
    exercises = []
    for line in session["exercises"]:
        sets = []
        for group in line["sets"]:
            single = {key: value for key, value in group.items() if key != "count"}
            sets += [dict(single, load=None) for _ in range(group["count"])]
        exercises.append({"exercise_id": line["exercise_id"], "load_mode": line["load_mode"], "sets": sets,
                          "rest_seconds": line["rest_seconds"]})
    return {"session_id": session["id"], "date": day.isoformat(), "title": session["title"], "hevy_routine_id": None,
            "temporary": False, "location": session.get("location"), "exercises": exercises}


def _planned_pairs(inst, span):
    """(overlay, session) planned in a span: the overlay in force each day, else the schedule rule on the program.

    The schedule rule plans nothing before the program's adoption (contract C41).
    """
    zone = inst.config.athlete.timezone
    pairs = overlay.planned(inst.overlays, span.days(), inst.adopted, zone)
    uncovered = {day for day in span.days() if inst.schedules_on(day) and not overlay.pick_in_force(inst.overlays, day)}
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
        days = [d for d in days if inst.schedules_on(d)]
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
    if (inst.root / minimum_plan_path(span.start)).exists():
        return "minimum"
    if "one_off" in kinds:
        return "one_off"
    if _in_layoff(span, activity, until):
        return "layoff"
    return "ordinary"


def _program_week(inst, span):
    """True for a week wholly on or after the program's adoption, or for any earlier week that plans a session."""
    if inst.adopted is not None and span.start >= inst.adopted:
        return True
    return bool(_planned_pairs(inst, span) or _external_rows(inst, span))


def _closed_weeks(inst, until, reach):
    """The program weeks among the `reach` weeks ending on or before `until`, newest first."""
    span = inst.week(until)
    if span.end > until:
        span = inst.week(span.start - timedelta(days=1))
    found = []
    for _ in range(reach):
        if _program_week(inst, span):
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


def _session_row(row, tier, planned):
    found = {"session_id": row["session_id"], "date": row["date"], "tier": tier, "status": row["status"],
             "moved": row["moved"], "workout_id": row["workout_id"], "overlay_id": row["overlay_id"]}
    if planned.get("moved_from"):
        found["moved_from"] = planned["moved_from"]
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
        sessions.append(_session_row(row, tier, sessions_by_key[(row["date"], row["session_id"])]))
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


def _cycle(inst, program_doc, reference, schedule=None, allowed=None):
    """[(position, [(date, session id)])] for each position of a schedule rule, planned in the reference week."""
    schedule = schedule or program_doc["schedule"]
    rule = schedule["rule"]
    plugin = plugins.load(inst.root).get("schedule", rule)
    if plugin is None:
        raise ValidationError(f"The schedule rule {rule} is not a known schedule plugin; run python3 -m coach "
                              "program validate")
    params, _ = plugins.merged_params(plugin, schedule["params"])
    positions = tuple(plugin.module.positions(params)) or (None,)
    found = []
    for position in positions:
        rotation = None
        if position is not None:
            rotation = {"position": position, "confirmed": True, "confirmed_at": None,
                        "week": reference.start.isoformat()}
        found.append((position, _schedule(inst, program_doc, reference, rotation, schedule, allowed)))
    return found


def _new_sessions(current, candidate):
    """Ids of sessions active in the candidate but not in the current program, and of new coach-led sessions."""
    active = {s["id"] for s in current["sessions"] if s["status"] == "active"} if current else set()
    externals = {e["id"] for e in current["external_sessions"]} if current else set()
    return ([s["id"] for s in candidate["sessions"] if s["status"] == "active" and s["id"] not in active]
            + [e["id"] for e in candidate["external_sessions"] if e["id"] not in externals])


def _muscle_rows(program_doc, library, average, effective):
    """{muscle: {target, average, met, source, baseline, reason}} for each muscle balance reports.

    `effective` is `targets()`. `source`: `explicit` (in `dose_targets`), `omitted` (an explicit 0 with a recorded
    reason), `fallback` (the hypertrophy starting fallback), `pending` (another goal, no agreed target yet) or null
    (no target).
    """
    intent = program_doc.get("dose_intent") or {}
    explicit = program_doc.get("dose_targets") or {}
    baseline, reasons = intent.get("baseline") or {}, intent.get("reasons") or {}
    trained = _core_primary_muscles(program_doc, library)
    fallback = _uses_fallback(program_doc)
    names = sorted(set(effective) | trained | set(COVERAGE) | {m for m, v in average.items() if v})
    rows = {}
    for muscle in names:
        planned = _round(average.get(muscle, 0.0))
        target = effective.get(muscle)
        if muscle in explicit:
            source = "omitted" if explicit[muscle] == 0 and muscle in reasons else "explicit"
        elif target is not None:
            source = "fallback"
        elif not fallback and (muscle in trained or muscle in COVERAGE):
            source = "pending"
        else:
            source = None
        rows[muscle] = {"target": target, "average": planned, "met": None if target is None else planned >= target,
                        "source": source, "baseline": baseline.get(muscle), "reason": reasons.get(muscle)}
    return rows


def _muscle_flags(program_doc, muscles):
    """The volume_undershoot, dose_coverage_gap and dose_target_pending flags for the muscle rows."""
    goal = dose_goal(program_doc)
    baseline = (program_doc.get("dose_intent") or {}).get("baseline") or {}
    raised = []
    for muscle, row in muscles.items():
        planned, target, source = row["average"], row["target"], row["source"]
        if row["met"] is False:
            below = "the hypertrophy starting fallback of" if source == "fallback" else "its target of"
            raised.append(flags.make("volume_undershoot", message=(
                f"{muscle}: planned {planned} fractional sets a week on core and coach-led sessions, below {below} "
                f"{_round(target)}")))
        elif muscle in COVERAGE and not planned and source != "omitted":
            raised.append(flags.make("dose_coverage_gap", message=(
                f"{muscle}: target 0 with no reason recorded; record why in dose_intent.reasons, or agree a target"
                if source == "explicit" else
                f"{muscle}: no hard sets planned on core or coach-led sessions and no agreed target; agree a target, "
                "or set it to 0 with a reason in dose_intent.reasons (dose_intent needs a goal)")))
        elif source == "pending" and planned:
            if muscle in baseline:
                basis = f"; agree one from the ordinary baseline of {_round(baseline[muscle])} recorded"
            elif goal == "maintenance":
                basis = "; record the ordinary baseline in dose_intent.baseline and agree a target from it"
            else:
                basis = "; agree one with the athlete"
            raised.append(flags.make("dose_target_pending", message=(
                f"{muscle}: planned {planned} fractional sets a week with no agreed {goal} target{basis}")))
    return raised


def _balance_notes(inst, program_doc, muscles, conditioning):
    notes = []
    if any(row["source"] == "fallback" for row in muscles.values()):
        notes.append(f"A fallback target is the hypertrophy starting fallback of {FALLBACK_TARGET} fractional sets a "
                     "week (rn:volume-frequency.1); for a strength or maintenance goal, record dose_intent and agree "
                     "each target with the athlete.")
    if conditioning:
        notes.append("Conditioning sessions add training stress and recovery cost but count no resistance sets; weigh "
                     "them when agreeing dose targets and record the reason in dose_intent.reasons.")
    age = config_module.approximate_age(inst.config, inst.today)
    if dose_goal(program_doc) == "maintenance" and age and age["years"] >= OLDER_LIFTER_AGE:
        notes.append(f"The athlete is about {age['years']}: lifters aged about 60 and over need more than a third of "
                     "their usual weekly sets to keep muscle size (rn:minimum-effective-dose.2), so agree "
                     "maintenance targets nearer the ordinary baseline.")
    return notes


def _balance(inst, program_doc, candidate):
    reference = inst.week(inst.today + timedelta(days=1))
    external = _week_external(program_doc, reference)
    positions, totals, conditioning_counts = [], {}, {}
    for position, planned in _cycle(inst, program_doc, reference):
        rows = [{"date": day.isoformat(), "session_id": session_id,
                 "tier": inst.program_session(session_id, program_doc)["tier"]} for day, session_id in planned]
        for _, session_id in planned:
            if not inst.is_lifting(session_id, program_doc):
                conditioning_counts[session_id] = conditioning_counts.get(session_id, 0) + 1
        dose = _ordinary_dose(inst, program_doc, planned, external)
        _add(totals, dose)
        positions.append({"position": position, "sessions": rows,
                          "external": [e["id"] for e in program_doc["external_sessions"]], "muscles": _rounded(dose)})
    average = {m: v / len(positions) for m, v in totals.items()}
    target = targets(program_doc, inst.library)
    muscles = _muscle_rows(program_doc, inst.library, average, target)
    raised = _muscle_flags(program_doc, muscles)
    coverage = {m: "planned" if muscles[m]["average"] else "omitted" if muscles[m]["source"] == "omitted" else "gap"
                for m in COVERAGE}
    conditioning = []
    for session_id, count in sorted(conditioning_counts.items()):
        session = inst.program_session(session_id, program_doc)
        conditioning.append({"session_id": session_id, "title": session["title"], "tier": session["tier"],
                             "per_week": _round(count / len(positions))})
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
              "goal": dose_goal(program_doc), "targets": target, "muscles": muscles, "coverage": coverage,
              "conditioning": conditioning, "notes": _balance_notes(inst, program_doc, muscles, conditioning),
              "by_session": sessions, "compared_with": None, "added": [], "adherence": None, "flags": raised}
    if candidate and inst.program is not None:
        added = _new_sessions(inst.program, program_doc)
        report, _ = _adherence(inst, inst.today)
        result.update(compared_with=paths.PROGRAM.as_posix(), added=added,
                      adherence={k: report[k] for k in ("pct", "planned", "trained", "insufficient_weeks")})
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


def balance(root, program=None, variant=None, *, today=None, now=None):
    """Static weekly balance on core sessions plus coach-led estimates; with `program`, a candidate is checked too.

    A candidate needs no adopted program: without one it gets the static balance alone, with no added sessions or
    adherence. With `variant` "minimum", the program's minimum week is checked instead (C40); the report's
    `passed` says whether it holds and `reasons` why not.
    """
    if variant is not None and variant not in VARIANTS:
        raise ValidationError(f"variant must be one of {', '.join(VARIANTS)}")
    inst = _Instance.load(root, today, now, require_program=program is None)
    doc = program if program is not None else inst.program
    if variant == "minimum":
        return _minimum_balance(inst, doc)
    return _balance(inst, doc, program is not None)


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


def floor_rule_id(exercise_ids):
    return FLOOR_PREFIX + "+".join(exercise_ids)


def _carried(doc, session_id, day, program_doc):
    """Exercise ids a session planned on `day` carries: its lines in the overlay, else its program lines."""
    if doc is not None:
        found = next((s for s in doc["sessions"] if s["session_id"] == session_id and s["date"] == day.isoformat()),
                     None)
        if found is not None:
            return {line["exercise_id"] for line in found["exercises"]}
    session = next((s for s in program_doc["sessions"] if s["id"] == session_id), None)
    return {line["exercise_id"] for line in session["exercises"]} if session else set()


def priority_floor(root, missed_session_id, date, doc=None, program_doc=None):
    """The synthetic C37 fold rule carrying each priority lift's floor dose out of a missed session, or None.

    One rule covers every priority lift the session carried; `doc` is the overlay in force (looked up when not
    given). Loads and reps come from that overlay's lines when `coach.missed.apply_rule` folds them.
    """
    root = Path(root)
    day = _as_date(date)
    program_doc = program.normalised(program_doc) if program_doc is not None else program.load(root)
    if doc is None:
        picked = overlay.in_force(root, day)
        doc = picked[0] if picked else None
    carried = _carried(doc, missed_session_id, day, program_doc)
    lifts = [lift for lift in program_doc["priority"] if lift["exercise_id"] in carried]
    if not lifts:
        return None
    return {"id": floor_rule_id([lift["exercise_id"] for lift in lifts]), "session_id": missed_session_id,
            "text": None, "when": {},
            "action": {"kind": "fold", "into": "next", "exercises": [
                {"exercise_id": lift["exercise_id"], "sets": lift["floor"]["sets"], "rpe": lift["floor"]["rpe"]}
                for lift in lifts]}}


def _name(inst, exercise_id):
    entry = inst.library.get(exercise_id)
    return entry["name"] if entry else exercise_id


def _usable_sets(exposure):
    return [s for s in exposure["sets"] if not s.get("discounted") and not s.get("convention_unknown")]


def _top_load(exposure):
    loads = [history.coaching_number(s["load"]) for s in _usable_sets(exposure)]
    loads = [load for load in loads if load is not None]
    return max(loads) if loads else None


def _top_reps(exposure):
    reps = [s["reps"] for s in _usable_sets(exposure) if s.get("reps") is not None]
    return max(reps) if reps else None


def _kpi_series(inst, lift, since, until):
    """[(date, value)] oldest first, the KPI's value now as {value, date, ...} or None, and why an e1RM is missing."""
    exercise_id, kind = lift["exercise_id"], lift["kpi"]["kind"]
    if kind == "e1rm":
        found = stats.e1rm_series(inst.root, exercise_id, since=since, now=inst.now)
        points = [p for p in found["series"].get(exercise_id, []) if p["date"] <= until.isoformat()]
        best = max(points, key=lambda p: (p["e1rm"], p["date"])) if points else None
        gone = found["unavailable"].get(exercise_id)
        why = {"reason": gone["reason"], "message": gone["message"], "date": gone["date"]} if gone else None
        return [(p["date"], p["e1rm"]) for p in points], ({"value": best["e1rm"], "date": best["date"],
                                                           "basis": best["basis"]} if best else None), why
    if kind in ("top_load", "top_reps"):
        measure = _top_load if kind == "top_load" else _top_reps
        exposures = sorted((e for e in history.all_exposures(inst.root, now=inst.now)
                            if e["exercise_id"] == exercise_id and since.isoformat() <= e["date"] <= until.isoformat()
                            and not e["excluded"] and not e["suspect"]),
                           key=lambda e: (e["date"], e["workout_id"]))
        series = [(e["date"], _round(v)) for e in exposures if (v := measure(e)) is not None]
        return series, ({"value": series[-1][1], "date": series[-1][0]} if series else None), None
    return [], _rung_now(inst, exercise_id), None


def _rung_now(inst, exercise_id):
    for session in inst.program["sessions"]:
        line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id
                     and e["scheme"]["name"] == "assistance_ladder"), None)
        if line is None:
            continue
        entry = ((inst.state or {}).get("scheme_state") or {}).get(f"{session['id']}/{exercise_id}") or {}
        data = entry.get("data") or {}
        if "rung" not in data:
            return None
        rungs = line["scheme"]["params"].get("rungs", [])
        name = rungs[data["rung"]]["name"] if data["rung"] < len(rungs) else None
        return {"value": data["rung"], "name": name, "date": data.get("through"), "session_id": session["id"]}
    return None


def _kpi(inst, lift, since, until):
    kpi = lift["kpi"]
    series, now_value, unavailable = _kpi_series(inst, lift, since, until)
    trend = None
    if len(series) > 1:
        trend = {"from": {"date": series[0][0], "value": series[0][1]},
                 "to": {"date": series[-1][0], "value": series[-1][1]},
                 "delta": _round(series[-1][1] - series[0][1])}
    met = None
    if kpi["target"] is not None and now_value is not None:
        modes = {line["load_mode"] for session in inst.program["sessions"] for line in session["exercises"]
                 if line["exercise_id"] == lift["exercise_id"]}
        lower_is_better = kpi["kind"] == "top_load" and "assisted" in modes
        met = now_value["value"] <= kpi["target"] if lower_is_better else now_value["value"] >= kpi["target"]
    return {"kind": kpi["kind"], "target": kpi["target"], "by": kpi["by"], "now": now_value, "trend": trend,
            "met": met, "unavailable": unavailable}


def _weeks_between(inst, since, until):
    span, last, found = inst.week(since), inst.week(until), []
    while span.start <= last.start:
        found.append(span)
        span = inst.week(span.end + timedelta(days=1))
    return found


def _lifted(session, exercise_id):
    return any(line["exercise_id"] == exercise_id and not line.get("fold") for line in session["exercises"])


def _replacements(sessions_by_key, span, exercise_id, missed_key):
    """Keys of sessions in the week that fold the lift out of a missed exposure."""
    day, session_id = missed_key
    found = []
    for (other_day, other_id), session in sessions_by_key.items():
        if not span.contains(dates.parse_date(other_day)):
            continue
        if any(line["exercise_id"] == exercise_id and (line.get("fold") or {}).get("from_date") == day
               and line["fold"]["from_session_id"] == session_id for line in session["exercises"]):
            found.append((other_day, other_id))
    return found


def _priority_weeks(inst, lifts, since, until):
    """{exercise id: [week rows]} and the priority_exposures_missed flags over the program weeks `since` to `until`.

    A moved session is one planned exposure, on its new date.
    """
    spans = [span for span in _weeks_between(inst, since, until) if _program_week(inst, span)]
    if not spans:
        return {lift["exercise_id"]: [] for lift in lifts}, []
    pairs = [pair for span in spans for pair in _planned_pairs(inst, span)]
    window = dates.Span(spans[0].start, spans[-1].end)
    matched = stats.adherence_of(inst.root, pairs, window, today=inst.today, now=inst.now)
    status = {(r["date"], r["session_id"]): r["status"] for r in matched["sessions"]}
    sessions_by_key = {(s["date"], s["session_id"]): s for _, s in pairs}
    trained_on = {}
    for workout in inst.workouts():
        if workout["conditioning"]:
            continue
        for exercise in workout["exercises"]:
            if any(s["type"] in history.WORKING_SET_TYPES for s in exercise["sets"]):
                trained_on.setdefault(exercise["exercise_id"], []).append(dates.parse_date(workout["date"]))
    found, raised = {}, []
    for lift in lifts:
        exercise_id = lift["exercise_id"]
        rows = []
        for span in spans:
            keys = sorted(key for key, session in sessions_by_key.items()
                          if span.contains(dates.parse_date(key[0])) and inst.tier(key[1]) == "core"
                          and _lifted(session, exercise_id))
            missed = [key for key in keys if status.get(key) == "missed" and key[0] < inst.today.isoformat()]
            replaced = pending = 0
            unreplaced = []
            for key in missed:
                made_up = [status.get(other) for other in _replacements(sessions_by_key, span, exercise_id, key)]
                if "trained" in made_up:
                    replaced += 1
                elif "upcoming" in made_up:
                    pending += 1
                else:
                    unreplaced.append(key)
            rows.append({"week": span.start.isoformat(), "label": span.label(), "planned": len(keys),
                         "trained": sum(1 for day in trained_on.get(exercise_id, []) if span.contains(day)),
                         "missed": len(missed), "replaced": replaced, "pending": pending,
                         "unreplaced": len(unreplaced)})
            if unreplaced:
                days = ", ".join(f"{session_id} on {day}" for day, session_id in unreplaced)
                raised.append(flags.make(
                    "priority_exposures_missed", session_id=unreplaced[0][1], exercise_id=exercise_id,
                    message=f"{_name(inst, exercise_id)}: planned exposure missed in {span.label()} ({days}) and no "
                            f"floor dose of {lift['floor']['sets']} sets replaced it"))
        found[exercise_id] = rows
    return found, raised


def priority(root, since=None, *, today=None, now=None):
    """Each priority lift's KPI now and its trend since `since`, its exposures per week against plan, and the flags.

    `since` defaults to four weeks before today. The KPI reads every workout since then; the weekly rows start at
    the program's adoption.
    """
    inst = _Instance.load(root, today, now)
    since = _as_date(since) or inst.today - timedelta(days=PRIORITY_DAYS)
    until = inst.today
    if since > until:
        raise ValidationError(f"--since {since} is after today ({until})")
    lifts = inst.program["priority"]
    weeks, raised = _priority_weeks(inst, lifts, since, until) if lifts else ({}, [])
    rows = []
    for lift in lifts:
        exercise_id = lift["exercise_id"]
        rows.append({"exercise_id": exercise_id, "name": _name(inst, exercise_id),
                     "sessions": [s["id"] for s in inst.program["sessions"]
                                  if any(e["exercise_id"] == exercise_id for e in s["exercises"])],
                     "kpi": _kpi(inst, lift, since, until), "floor": lift["floor"], "weeks": weeks[exercise_id]})
    return {"since": since.isoformat(), "until": until.isoformat(), "lifts": rows, "flags": raised}


def _minimum_week(program_doc):
    minimum = program_doc.get("minimum_week")
    if not minimum:
        raise ValidationError(f"The program has no minimum_week; add one to {paths.PROGRAM} and run python3 -m coach "
                              "program validate")
    return minimum


def _hard_sets(line):
    return sum(s.get("count", 1) for s in line["sets"] if _is_hard(s))


def _week_external(program_doc, span, retained=None):
    """Each coach-led session once in the week: on its weekday's date, or with no date when it has no weekday."""
    rows = []
    for external in program_doc["external_sessions"]:
        if retained is not None and external["id"] not in retained:
            continue
        days = [day for day in span.days() if base.WEEKDAYS[day.weekday()] == external["weekday"]]
        rows.append({"external_id": external["id"], "title": external["title"],
                     "date": days[0].isoformat() if days else None,
                     "estimated_sets": dict(external["estimated_sets"])})
    return rows


def _is_core_lifting(session):
    return session["tier"] == "core" and session["kind"] == "lifting"


def _ordinary_dose(inst, program_doc, planned, external):
    """One ordinary week's planned dose: its core lifting sessions plus the coach-led estimates."""
    dose = {}
    for _, session_id in planned:
        session = inst.program_session(session_id, program_doc)
        if _is_core_lifting(session):
            _add(dose, session_dose(inst.library, session))
    for row in external:
        _add(dose, row["estimated_sets"])
    return dose


def _minimum_reference(inst, program_doc, cycle, reference_position, external):
    """The ordinary dose a minimum position is checked against, None when unmatched, and the fields naming its sources.

    A fixed ordinary schedule's position is None, so only a null `reference_sessions` marks an unmatched position.
    """
    if reference_position not in cycle:
        return None, {"reference_position": None, "reference_sessions": None, "reference_external": None}
    planned = cycle[reference_position]
    rows = [{"date": day.isoformat(), "session_id": session_id} for day, session_id in planned
            if _is_core_lifting(inst.program_session(session_id, program_doc))]
    return _ordinary_dose(inst, program_doc, planned, external), {
        "reference_position": reference_position, "reference_sessions": rows, "reference_external": external}


def _minimum_position(inst, program_doc, position, planned, external, *, ordinary, reference):
    prefix = f"{position}: " if position else ""
    named = reference["reference_position"]
    dose_prefix = prefix or (f"against ordinary {named}: " if named else "")
    reasons = []
    if len(planned) > MINIMUM_MAX_SESSIONS:
        reasons.append(f"{prefix}the schedule plans {len(planned)} sessions in the week; a minimum week has at most "
                       f"{MINIMUM_MAX_SESSIONS}")
    rows, dose, carried = [], {}, {}
    for day, session_id in planned:
        session = inst.program_session(session_id, program_doc)
        minutes = validity.estimate_minutes(inst.root, _program_session(session, day))
        cap = cap_minutes(inst.config, session_id)
        within = cap is None or minutes <= cap
        rows.append({"date": day.isoformat(), "session_id": session_id, "minutes": minutes, "cap_minutes": cap,
                     "within_cap": within})
        if not within:
            reasons.append(f"{prefix}{session_id}: estimated {minutes} min, over its {cap} min cap")
        if _is_core_lifting(session):
            _add(dose, session_dose(inst.library, session))
        for line in session["exercises"]:
            sets = _hard_sets(line)
            if sets > carried.get(line["exercise_id"], (0, None))[0]:
                carried[line["exercise_id"]] = (sets, session_id)
    for session in external:
        _add(dose, session["estimated_sets"])
    floors = []
    for lift in program_doc["priority"]:
        sets, session_id = carried.get(lift["exercise_id"], (0, None))
        needed = lift["floor"]["sets"]
        floors.append({"exercise_id": lift["exercise_id"], "floor_sets": needed, "sets": sets,
                       "session_id": session_id, "met": sets >= needed})
        if sets < needed:
            held = f" ({session_id} has {sets})" if sets else ""
            reasons.append(f"{prefix}no session carries the priority floor of {needed} working sets of "
                           f"{_name(inst, lift['exercise_id'])}{held}")
    muscles = {}
    for muscle in sorted(set(ordinary or {}) | set(dose)):
        ordinary_sets = ordinary.get(muscle, 0.0) if ordinary is not None else None
        third = ordinary_sets * MINIMUM_SHARE if ordinary_sets is not None else None
        planned_sets = dose.get(muscle, 0.0)
        met = planned_sets >= third - 1e-9 if third is not None else None
        muscles[muscle] = {"ordinary": _round(ordinary_sets) if ordinary_sets is not None else None,
                           "third": _round(third) if third is not None else None,
                           "planned": _round(planned_sets), "met": met}
        if met is False:
            reasons.append(f"{dose_prefix}{muscle}: {_round(planned_sets)} fractional sets planned, below a third "
                           f"of its ordinary dose of {_round(ordinary[muscle])} ({_round(third)})")
    return {"position": position, **reference, "sessions": rows, "external": external, "muscles": muscles,
            "priority": floors}, reasons


def _minimum_balance(inst, program_doc, reference=None):
    minimum = _minimum_week(program_doc)
    reference = reference or inst.week(inst.today + timedelta(days=1))
    target = targets(program_doc, inst.library)
    reasons = []
    if len(minimum["sessions"]) > MINIMUM_MAX_SESSIONS:
        reasons.append(f"it lists {len(minimum['sessions'])} sessions; a minimum week has at most "
                       f"{MINIMUM_MAX_SESSIONS}")
    positions = []
    ordinary_cycle = dict(_cycle(inst, program_doc, reference))
    minimum_cycle = dict(_cycle(inst, program_doc, reference, minimum["schedule"], set(minimum["sessions"])))
    reference_external = _week_external(program_doc, reference)
    external = _week_external(program_doc, reference, set(minimum.get("external_sessions", [])))
    if None not in ordinary_cycle and None not in minimum_cycle and ordinary_cycle.keys() != minimum_cycle.keys():
        reasons.append("ordinary and minimum rotating schedules must use the same position names; "
                       "use matching names or a fixed minimum schedule")
    for position, planned in minimum_cycle.items():
        references = [ref for ref in ordinary_cycle if position is None or ref is None or position == ref]
        for reference_position in references or [None]:
            ordinary, fields = _minimum_reference(inst, program_doc, ordinary_cycle, reference_position,
                                                  reference_external)
            row, found = _minimum_position(inst, program_doc, position, planned, external, ordinary=ordinary,
                                           reference=fields)
            positions.append(row)
            reasons += [reason for reason in found if reason not in reasons]
    return {"variant": "minimum", "reference_week": reference.label(), "sessions": list(minimum["sessions"]),
            "schedule": minimum["schedule"], "positions": positions, "targets": target, "passed": not reasons,
            "reasons": reasons, "flags": []}


def minimum_plan_path(week_start):
    return paths.PLANS_DIR / f"{_as_date(week_start).isoformat()}-minimum.json"


def minimum(root, week_start, *, write=False, dry_run=False, today=None, now=None):
    """The minimum week's plan for one week: a C23 SchedulePlan for `propose week --plan`, written with `write`.

    The report carries the minimum-week balance (`passed`, `reasons`) so a failing minimum week is visible before use.
    """
    inst = _Instance.load(root, today, now)
    minimum_week = _minimum_week(inst.program)
    span = inst.week(_as_date(week_start.start if isinstance(week_start, dates.Span) else week_start))
    planned = _schedule(inst, inst.program, span, schedule=minimum_week["schedule"],
                        allowed=set(minimum_week["sessions"]))
    if not planned:
        raise ValidationError(f"The minimum week's schedule plans no session in {span.label()}")
    plan_doc = {"variant": "minimum", "rule": minimum_week["schedule"]["rule"], "week": span.label(),
                "span": span.to_json(),
                "sessions": [{"date": day.isoformat(), "session_id": session_id,
                              "title": inst.program_session(session_id)["title"]} for day, session_id in planned],
                "external_sessions": _week_external(inst.program, span, set(minimum_week.get("external_sessions", []))),
                "rotation": None, "flags": []}
    path = minimum_plan_path(span.start)
    if write:
        jsonio.write_doc(inst.root / path, plan_doc, dry_run)
    report = _minimum_balance(inst, inst.program, span)
    return {"week": span.label(), "span": span.to_json(), "plan": plan_doc, "path": path.as_posix(),
            "written": write and not dry_run, "balance": {"passed": report["passed"], "reasons": report["reasons"]}}
