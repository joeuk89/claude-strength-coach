"""Cardio: weekly numbers, the bout timeline, plan reconcile and the cardio flags (contract C48, C49).

Every week here is the one `[athlete] week_starts` defines. The
session-RPE load is information only: no flag reads it and no ratio of
it is ever computed, because acute:chronic ratios did not predict
running injury where a single-session spike did.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from coach import config as config_module
from coach import dates, flags, history, niggles, render, stats, statusdays, units, validity, weekflags
from coach import program as program_module
from coach.activity.store import ActivityStore

CITES = ("rn:running-load.1", "rn:running-load.2", "rn:running-load.3", "rn:running-load.4")
PLAN_TIERS = ("review", "program")
QUALITY_WORDS = ("interval", "tempo", "threshold", "hill", "fartlek", "track", "race")
LIFTING = "lifting"
EXTERNAL = "external"
NOT_ACTIVITIES = (LIFTING, EXTERNAL)
# Coaching heuristics, CR-10 scale: the RPE a bout is taken at when nothing better is known.
KIND_RPE = {"lifting": 6, "run": 4, "ride": 4, "swim": 4, "row": 5, "walk": 2, "hike": 3, "conditioning": 7,
            "sport": 6, "mobility": 1, "other": 4}
PLANNED_RPE = {True: 7, False: 3}
NIGHTS = 7
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
NO_ACTIVITY_SOURCE = "no activity source: [activity] enabled is false, so only lifting and coach-led sessions count"
REGION_KIND = "cardio"
_PLURAL = {"conditioning": "conditioning sessions", "sport": "sport sessions", "mobility": "mobility sessions",
           "other": "other activities", "lifting": "lifting sessions", "external": "coach-led sessions"}


@dataclass(frozen=True)
class Bout:
    date: date
    start: Optional[datetime]
    end: Optional[datetime]
    kind: str
    source: str
    ref: str
    session_id: Optional[str]
    minutes: Optional[float]
    distance_meters: Optional[float]
    quality: bool
    quality_basis: Optional[str]

    def is_activity(self):
        return self.kind not in NOT_ACTIVITIES

    def to_json(self):
        return {"date": self.date.isoformat(), "start": _stamp(self.start), "end": _stamp(self.end),
                "kind": self.kind, "source": self.source, "ref": self.ref, "session_id": self.session_id,
                "minutes": self.minutes, "distance_meters": self.distance_meters, "quality": self.quality,
                "quality_basis": self.quality_basis}


def _stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _settings(config):
    return config["cardio"]


def activity_on(config):
    return bool(config["activity"]["enabled"])


def plans_read(config):
    return _settings(config)["tier"] in PLAN_TIERS


def _store(root, config):
    return ActivityStore(root, config) if activity_on(config) else None


def week_span(config, week):
    if isinstance(week, dates.Span):
        return week
    return dates.parse_week(str(week), config["athlete"]["week_starts"])


def _label(span):
    try:
        return span.label()
    except ValueError:
        return None


def _minutes(seconds):
    return None if seconds is None else units.json_number(round(seconds / 60, 1))


def _distance(meters, unit):
    return None if meters is None else units.json_number(round(units.from_meters(meters, unit), 2))


def _distance_text(meters, unit):
    return f"{_distance(meters, unit):g} {unit}"


def _number(value):
    return units.json_number(round(value, 1)) if value is not None else None


def quality_of(activity, planned, rpe_min):
    """(quality, basis) for a logged Activity by the C48 rule: the first rule that applies wins."""
    if activity["kind"] == "conditioning":
        return True, "kind"
    if activity.get("rpe") is not None:
        return activity["rpe"] >= rpe_min, "rpe"
    if planned is not None:
        return bool(planned["quality"]), "planned"
    name = (activity.get("name") or "").lower()
    if any(word in name for word in QUALITY_WORDS):
        return True, "name"
    return False, "none"


def match(planned, logged, move_days, today=None):
    """Reconcile planned activities against logged Activities (C49).

    Pass 1 pairs the same kind on the same local date (`done`); pass 2 the
    same kind within `move_days`, nearest first, ties to the earlier
    activity and then the earlier plan (`moved`). An unmatched plan is
    `missed` before `today` and `upcoming` from it on (every one `missed`
    when `today` is None); an unmatched activity is `extra`.
    """
    plans = sorted(planned, key=lambda p: (p["date"], p["id"]))
    acts = sorted(logged, key=lambda a: (a["local_date"], a["start"], a["id"]))
    pairs, used = {}, set()
    for pi, plan in enumerate(plans):
        for ai, act in enumerate(acts):
            if ai not in used and act["kind"] == plan["kind"] and act["local_date"] == plan["date"]:
                pairs[pi] = ai
                used.add(ai)
                break
    candidates = []
    for pi, plan in enumerate(plans):
        if pi in pairs:
            continue
        for ai, act in enumerate(acts):
            gap = abs((dates.parse_date(act["local_date"]) - dates.parse_date(plan["date"])).days)
            if ai not in used and act["kind"] == plan["kind"] and gap <= move_days:
                candidates.append((gap, ai, pi))
    for _, ai, pi in sorted(candidates):
        if pi not in pairs and ai not in used:
            pairs[pi] = ai
            used.add(ai)

    items = []
    for pi, plan in enumerate(plans):
        act = acts[pairs[pi]] if pi in pairs else None
        if act is not None:
            moved = (dates.parse_date(act["local_date"]) - dates.parse_date(plan["date"])).days
            status = "done" if moved == 0 else "moved"
        else:
            moved = None
            status = "upcoming" if today is not None and dates.parse_date(plan["date"]) >= today else "missed"
        items.append(_item(status, plan, act, moved))
    items += [_item("extra", None, act, None) for ai, act in enumerate(acts) if ai not in used]
    return sorted(items, key=lambda i: (i["date"], i["planned_id"] or "", i["activity_id"] or ""))


def _item(status, plan, act, moved):
    target = (plan or {}).get("target") or {}
    actual = {"distance_meters": act.get("distance_meters") if act else None,
              "duration_seconds": act.get("duration_seconds") if act else None}
    delta = {key: (actual[key] - target[key] if actual[key] is not None and target.get(key) is not None else None)
             for key in ("distance_meters", "duration_seconds")}
    return {
        "status": status, "planned_id": plan["id"] if plan else None, "activity_id": act["id"] if act else None,
        "date": plan["date"] if plan else act["local_date"], "activity_date": act["local_date"] if act else None,
        "moved_days": moved if status == "moved" else None, "kind": (plan or act)["kind"],
        "title": plan["title"] if plan else act.get("name"), "target": plan.get("target") if plan else None,
        "actual": actual, "delta": delta, "quality": bool(plan["quality"]) if plan else None,
        "_planned": plan, "_activity": act,
    }


def _public(item):
    return {key: value for key, value in item.items() if not key.startswith("_")}


class _Week:
    """What every reader of one span needs, loaded once: config, the activity store, the planned match."""

    def __init__(self, root, config, span, today=None):
        self.root, self.config, self.span, self.today = root, config, span, today
        self.settings = _settings(config)
        self.store = _store(root, config)
        self.activities = self.store.activities(span) if self.store else []
        planned = self.store.planned(span) if self.store and plans_read(config) else []
        self.items = match(planned, self.activities, self.settings["reconcile_move_days"], today)
        self.plan_for = {i["activity_id"]: i["_planned"] for i in self.items if i["_planned"] and i["_activity"]}

    def activity_entries(self):
        """(Bout, srpe) for each logged Activity."""
        found = []
        for act in self.activities:
            plan = self.plan_for.get(act["id"])
            quality, basis = quality_of(act, plan, self.settings["quality_rpe_min"])
            if act.get("rpe") is not None:
                rpe, method = act["rpe"], "athlete"
            elif plan is not None:
                rpe, method = PLANNED_RPE[bool(plan["quality"])], "planned"
            else:
                rpe, method = KIND_RPE[act["kind"]], "kind_default"
            bout = Bout(dates.parse_date(act["local_date"]), dates.parse_timestamp(act["start"]),
                        dates.parse_timestamp(act["end"]) if act.get("end") else None, act["kind"], "logged",
                        act["id"], None, _minutes(act["duration_seconds"]), act.get("distance_meters"), quality, basis)
            found.append((bout, _srpe(rpe, bout.minutes, method)))
        return found

    def workouts(self):
        return [w for w in history.workouts(self.root, self.span.start, self.span.end) if not w["conditioning"]]

    def lifting_entries(self, workouts):
        found = []
        for workout in workouts:
            rpes = [s["rpe"] for e in workout["exercises"] for s in e["sets"]
                    if s["type"] in history.WORKING_SET_TYPES and s["rpe"] is not None]
            without = sum(1 for e in workout["exercises"] for s in e["sets"]
                          if s["type"] in history.WORKING_SET_TYPES and s["rpe"] is None)
            if rpes and len(rpes) >= without:
                rpe, method = round(sum(rpes) / len(rpes), 2), "lifting_sets"
            else:
                rpe, method = KIND_RPE[LIFTING], "kind_default"
            start = dates.parse_timestamp(workout["start_time"]) if workout.get("start_time") else None
            end = dates.parse_timestamp(workout["end_time"]) if workout.get("end_time") else None
            bout = Bout(dates.parse_date(workout["date"]), start, end, LIFTING, "logged", workout["workout_id"],
                        workout["session_id"], workout["duration_minutes"], None, False, None)
            found.append((bout, _srpe(rpe, bout.minutes, method)))
        return found

    def external_entries(self):
        found = []
        minutes, rpe = self.settings["external_session_minutes"], self.settings["external_session_rpe"]
        for note in history.annotations(self.root, "external"):
            day = dates.parse_date(note["date"])
            if note["done"] and self.span.contains(day):
                bout = Bout(day, None, None, EXTERNAL, "logged", note["id"], note["external_id"], minutes, None,
                            False, None)
                found.append((bout, _srpe(rpe, minutes, "external_default")))
        return found

    def upcoming_planned(self):
        """Planned bouts no logged Activity matched (tier review or program): from today on, or all with no today."""
        wanted = ("upcoming",) if self.today is not None else ("missed",)
        return [_planned_bout(i["_planned"]) for i in self.items if i["status"] in wanted]


def _srpe(rpe, minutes, method):
    load = None if minutes is None else _number(rpe * minutes)
    return {"rpe": units.json_number(rpe), "load": load, "method": method}


def _planned_bout(plan):
    target = plan.get("target") or {}
    return Bout(dates.parse_date(plan["date"]), None, None, plan["kind"], "planned", plan["id"], None,
                _minutes(target.get("duration_seconds")), target.get("distance_meters"), bool(plan["quality"]),
                "planned")


def _order(bout):
    return bout.date, _stamp(bout.start) or "", bout.kind, bout.ref


def _sorted(bouts):
    return sorted(bouts, key=_order)


def _logged_entries(week_data):
    entries = (week_data.lifting_entries(week_data.workouts()) + week_data.external_entries()
               + week_data.activity_entries())
    return sorted(entries, key=lambda e: _order(e[0]))


def bouts(root, span, mode, overlay=None, today=None):
    """The bout timeline for a span (C49).

    "logged": resolved workouts, Activities and coach-led sessions marked
    done. "proposal": the overlay's sessions, coach-led sessions placed on
    their weekday, and, at tier review or program, the planned activities
    no logged Activity has matched (from `today` on when it is given).
    """
    config = config_module.load(root)
    week_data = _Week(root, config, span, today)
    if mode == "logged":
        return [entry[0] for entry in _logged_entries(week_data)]
    if mode != "proposal":
        raise ValueError(f"mode must be logged or proposal, found {mode!r}")
    return _sorted(_proposal_bouts(week_data, overlay))


def _proposal_bouts(week_data, overlay):
    found = []
    program_doc = history.load_optional(program_module, week_data.root)
    kinds = {s["id"]: s["kind"] for s in program_doc["sessions"]} if program_doc else {}
    for session in (overlay or {}).get("sessions", []):
        kind = "conditioning" if kinds.get(session["session_id"]) == "conditioning" else LIFTING
        found.append(Bout(dates.parse_date(session["date"]), None, None, kind, "planned",
                          f"{overlay['id']}/{session['session_id']}", session["session_id"], None, None,
                          kind == "conditioning", "kind" if kind == "conditioning" else None))
    minutes = week_data.settings["external_session_minutes"]
    for external in program_doc["external_sessions"] if program_doc else []:
        for day in week_data.span.days():
            placed = external.get("weekday") == WEEKDAYS[day.weekday()]
            if placed and (week_data.today is None or day >= week_data.today):
                found.append(Bout(day, None, None, EXTERNAL, "planned", external["id"], external["id"], minutes,
                                  None, False, None))
    return found + week_data.upcoming_planned()


def flag_bouts(root, config, span, today):
    """What `cardio flags` judges: logged bouts up to today, then (review or program) plans from today on."""
    week_data = _Week(root, config, span, today)
    logged = [entry[0] for entry in _logged_entries(week_data) if entry[0].date <= today]
    return _sorted(logged + week_data.upcoming_planned())


def week(root, week_value):
    """The week's numbers (C48): lifting, coach-led sessions, runs, conditioning, other kinds and session-RPE load."""
    config = config_module.load(root)
    span = week_span(config, week_value)
    unit = _settings(config)["distance_unit"]
    week_data = _Week(root, config, span)
    workouts = week_data.workouts()
    entries = sorted(week_data.lifting_entries(workouts) + week_data.external_entries()
                     + week_data.activity_entries(), key=lambda e: _order(e[0]))
    hard_sets = sum(1 for w in workouts for e in w["exercises"] if e["exercise_id"] for s in e["sets"]
                    if s["type"] in history.WORKING_SET_TYPES and (s["rpe"] is None or s["rpe"] > stats.EASY_RPE))
    lifting_minutes = [w["duration_minutes"] for w in workouts if w["duration_minutes"] is not None]
    acts = [b for b, _ in entries if b.is_activity()]
    runs = [b for b in acts if b.kind == "run"]
    conditioning = [b for b in acts if b.kind == "conditioning"]
    other = {}
    for bout in acts:
        if bout.kind not in ("run", "conditioning"):
            entry = other.setdefault(bout.kind, {"count": 0, "minutes": 0})
            entry["count"] += 1
            entry["minutes"] = _number(entry["minutes"] + (bout.minutes or 0))
    by_method = {}
    for _, srpe in entries:
        by_method[srpe["method"]] = by_method.get(srpe["method"], 0) + 1
    return {
        "week": _label(span), "span": span.to_json(), "tier": _settings(config)["tier"], "distance_unit": unit,
        "activity_source": activity_on(config),
        "lifting": {"workouts": len(workouts), "hard_sets": hard_sets,
                    "minutes": _number(sum(lifting_minutes))},
        "external": {"done": sum(1 for b, _ in entries if b.kind == EXTERNAL)},
        "run": {"count": len(runs), "distance": _distance(sum(b.distance_meters or 0 for b in runs), unit),
                "minutes": _number(sum(b.minutes or 0 for b in runs)), "quality": sum(1 for b in runs if b.quality)},
        "conditioning": {"count": len(conditioning), "minutes": _number(sum(b.minutes or 0 for b in conditioning))},
        "other": dict(sorted(other.items())),
        "srpe": {"total": _number(sum(s["load"] or 0 for _, s in entries)),
                 "by_method": dict(sorted(by_method.items()))},
        "bouts": [_bout_row(bout, srpe, unit) for bout, srpe in entries],
    }


def _bout_row(bout, srpe, unit):
    return {"ref": bout.ref, "date": bout.date.isoformat(), "kind": bout.kind, "session_id": bout.session_id,
            "minutes": bout.minutes, "distance": _distance(bout.distance_meters, unit), "quality": bout.quality,
            "quality_basis": bout.quality_basis, "srpe": srpe}


def reconcile(root, week_value, today):
    """Planned against logged for the week (C49); empty at tier count."""
    config = config_module.load(root)
    span = week_span(config, week_value)
    tier = _settings(config)["tier"]
    if tier not in PLAN_TIERS or not activity_on(config):
        return {"week": _label(span), "span": span.to_json(), "tier": tier, "items": [], "summary": {}}
    week_data = _Week(root, config, span, today)
    rpe_min = week_data.settings["quality_rpe_min"]
    items = []
    for item in week_data.items:
        if item["status"] == "extra":
            item = dict(item, quality=quality_of(item["_activity"], None, rpe_min)[0])
        items.append(_public(item))
    summary = {}
    for item in items:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return {"week": _label(span), "span": span.to_json(), "tier": tier, "items": items, "summary": summary}


def sleep_judgement(store, settings, end):
    """(short nights, nights with data, debt: True | False | None) over the 7 nights ending on `end`."""
    nights = dates.Span(end - timedelta(days=NIGHTS - 1), end)
    hours = [day["asleep_hours"] for day in store.asleep_days(nights) if day["provenance"]["kind"] == "nightly"]
    short = sum(1 for value in hours if value < settings["sleep_short_hours"])
    if len(hours) < settings["sleep_min_nights"]:
        return short, len(hours), None
    return short, len(hours), short >= settings["sleep_debt_nights"]


def sleep_debt(root, span):
    """Whether the 7 nights ending on `span.end` hold a sleep debt (C49); None with no source or too few nights."""
    config = config_module.load(root)
    if not activity_on(config):
        return None
    return sleep_judgement(ActivityStore(root, config), _settings(config), span.end)[2]


def evaluation_date(ctx):
    """The last night the sleep rule judges: the span's last day, or today for a proposal or a span ending later."""
    return ctx.today if ctx.mode == "proposal" else min(ctx.span.end, ctx.today)


def evaluate(ctx):
    """{"flags", "skipped"} for a WeekFlagContext: every C49 rule, in the C49 table's order."""
    config = ctx.config
    settings = _settings(config)
    status = _status_flags(ctx)
    if not activity_on(config):
        return {"flags": status, "skipped": []}
    store = ActivityStore(ctx.root, config)
    judged = [b for b in ctx.bouts if b.is_activity() and (b.source == "logged" or plans_read(config))]
    spikes, skipped = _spike_flags(store, judged, settings)
    week_starts = config["athlete"]["week_starts"]
    earlier = _logged_earlier_in_week(ctx, week_starts) if ctx.mode == "proposal" else []
    found = _cap_flags(judged, settings, week_starts, earlier) + spikes + _stack_flags(judged, earlier)
    end = evaluation_date(ctx)
    short, nights, debt = sleep_judgement(store, settings, end)
    if debt:
        found.append(flags.make("sleep_debt", message=(
            f"{short} of the {NIGHTS} nights to {end.isoformat()} were under {settings['sleep_short_hours']:g} h "
            f"asleep ({nights} with data): recovery, not the program, may be the bottleneck this week.")))
    found += status + _niggle_flags(ctx.root, judged, ctx.span, settings["distance_unit"])
    return {"flags": found, "skipped": skipped}


def _logged_earlier_in_week(ctx, week_starts):
    """Logged activities in the proposal span's week before the span starts: a midweek draft adds to them."""
    week_of = dates.week_span(ctx.span.start, week_starts)
    if week_of.start >= ctx.span.start:
        return []
    before = dates.Span(week_of.start, ctx.span.start - timedelta(days=1))
    return [bout for bout, _ in _Week(ctx.root, ctx.config, before).activity_entries()]


def _status_flags(ctx):
    today = dates.Span(ctx.today, ctx.today)
    doc = statusdays.load(ctx.root)
    rows = [r for r in doc["days"] if statusdays.is_live(r)
            and (statusdays.span_of(r).overlaps(ctx.span) or statusdays.span_of(r).overlaps(today))]
    found = []
    for row in rows:
        until = row["span"]["end"] or "ongoing"
        message = f"{row['kind'].capitalize()} {row['span']['start']} to {until} ({row['id']}: {row['note']})"
        if row["kind"] == "travel":
            found.append(flags.make("status_active", "info", message=f"{message}: plan around the days away."))
        elif row["kind"] == "injured":
            found.append(flags.make("status_active", "warn", message=(
                f"{message}: train around it, and check with a qualified professional before loading it.")))
        else:
            found.append(flags.make("status_active", "warn", message=(
                f"{message}: confirm {validity.SYMPTOM_FREE_HOURS} hours symptom-free before training; the first "
                f"session back is capped at RPE {validity.ILLNESS_RPE_CAP}.")))
    return found


def _runs(bouts):
    return [b for b in bouts if b.kind == "run"]


def _cap_flags(bouts, settings, week_starts, earlier=()):
    """`earlier` bouts count toward the weekly caps only; single-run caps judge `bouts`."""
    unit = settings["distance_unit"]
    found = []
    weeks = sorted({dates.week_span(b.date, week_starts) for b in bouts}, key=lambda s: s.start)
    for week_of in weeks:
        inside = [b for b in (*earlier, *bouts) if week_of.contains(b.date)]
        runs = _runs(inside)
        label = week_of.label()
        meters = sum(b.distance_meters for b in runs if b.distance_meters is not None)
        minutes = sum(b.minutes for b in runs if b.minutes is not None)
        cap = settings["weekly_run_distance"]
        if cap > 0 and meters > units.to_meters(cap, unit):
            found.append(flags.make("cap_breach", message=(
                f"Run distance {_distance_text(meters, unit)} in {label} is over the {cap:g} {unit} weekly cap.")))
        cap = settings["weekly_run_minutes"]
        if cap > 0 and minutes > cap:
            found.append(flags.make("cap_breach", message=(
                f"Run time {_number(minutes):g} min in {label} is over the {cap:g} min weekly cap.")))
        for run in _runs(b for b in bouts if week_of.contains(b.date)):
            what = f"{'Planned activity (run)' if run.source == 'planned' else 'The run'} on {run.date.isoformat()}"
            cap = settings["single_run_distance"]
            if cap > 0 and run.distance_meters is not None and run.distance_meters > units.to_meters(cap, unit):
                found.append(flags.make("cap_breach", message=(
                    f"{what} ({_distance_text(run.distance_meters, unit)}) is over the {cap:g} {unit} "
                    "single-run cap.")))
            cap = settings["single_run_minutes"]
            if cap > 0 and run.minutes is not None and run.minutes > cap:
                found.append(flags.make("cap_breach", message=(
                    f"{what} ({run.minutes:g} min) is over the {cap:g} min single-run cap.")))
        quality = [b for b in inside if b.quality]
        cap = settings["weekly_quality"]
        if cap > 0 and len(quality) > cap:
            found.append(flags.make("cap_breach", message=(
                f"{len(quality)} quality activities in {label} is over the weekly cap of {cap}.")))
    return found


def _spike_flags(store, bouts, settings):
    unit = settings["distance_unit"]
    lookback, ratio = settings["spike_lookback_days"], settings["spike_ratio"]
    groups = store.activity_groups()
    first = min((dates.parse_date(a["local_date"]) for a in groups), default=None)
    found, skipped = [], []
    for run in _runs(bouts):
        by_distance = run.distance_meters is not None
        if not by_distance and run.minutes is None:
            continue
        history_days = (run.date - first).days if first else 0
        reason = None
        if history_days < settings["spike_min_history_days"]:
            reason = (f"store history shorter than the {lookback}-day lookback: the first logged activity is "
                      f"{_count_text(max(history_days, 0), 'day')} before this run, under spike_min_history_days "
                      f"({settings['spike_min_history_days']})")
        window = dates.Span(run.date - timedelta(days=lookback), run.date - timedelta(days=1))
        before = store.activities(window, kinds=("run",))
        values = [a["distance_meters"] if by_distance else _minutes(a["duration_seconds"]) for a in before]
        values = [v for v in values if v is not None]
        if reason is None and not values:
            reason = f"no logged run in the {lookback} days before it"
        if reason:
            skipped.append({"ref": run.ref, "date": run.date.isoformat(), "source": run.source, "reason": reason})
            continue
        longest = max(values)
        value = run.distance_meters if by_distance else run.minutes
        if value > ratio * longest:
            if by_distance:
                size, reference = _distance_text(value, unit), _distance_text(longest, unit)
            else:
                size, reference = f"{value:g} min", f"{longest:g} min"
            severity = "info" if run.source == "planned" else "warn"
            what = "Planned activity (run)" if run.source == "planned" else "Run"
            found.append(flags.make("run_volume_spike", severity, message=(
                f"{what} on {run.date.isoformat()} is {size}, more than {ratio:g} × the longest run in the "
                f"{lookback} days before it ({reference}). In one observational cohort, single runs this far "
                "past the recent longest had more overuse injuries.")))
    return found, skipped


def _stack_flags(bouts, earlier=()):
    """A pair of two `earlier` bouts is not judged again."""
    quality = sorted((b for b in (*earlier, *bouts) if b.quality), key=lambda b: (b.date, b.ref))
    found = []
    for first, second in zip(quality, quality[1:]):
        if (second.date - first.date).days <= 1 and (first not in earlier or second not in earlier):
            found.append(flags.make("quality_stack", message=(
                f"Quality activities on {_bout_text(first)} and {_bout_text(second)}: keep an easy day between "
                "quality sessions.")))
    return found


def _bout_text(bout):
    planned = "planned " if bout.source == "planned" else ""
    return f"{bout.date.isoformat()} ({planned}{bout.kind}, by {bout.quality_basis})"


def _count_text(count, kind):
    if count == 1:
        return f"1 {kind}" if kind not in _PLURAL else f"1 {_PLURAL[kind][:-1]}"
    return f"{count} {_PLURAL.get(kind, kind + 's')}"


def _niggle_flags(root, bouts, span, unit):
    if not niggles.exists(root):
        return []
    found = []
    for row in niggles.load(root)["niggles"]:
        status = niggles.status_on(row, span.end)
        kinds = row["applies_to"]["activity_kinds"]
        if status in (None, "resolved") or not kinds:
            continue
        parts = []
        for kind in kinds:
            linked = [b for b in bouts if b.kind == kind]
            if linked:
                meters = sum(b.distance_meters or 0 for b in linked)
                parts.append(_count_text(len(linked), kind) + (f", {_distance_text(meters, unit)}" if meters else ""))
        if parts:
            found.append(flags.make("niggle_link", message=(
                f"Niggle {row['id']} ({row['area']}, {status}) applies to {', '.join(kinds)}: "
                f"{'; '.join(parts)} in {span.start.isoformat()} to {span.end.isoformat()}. Ask how it responded.")))
    return found


def render_text(root, week_value, today):
    """The cardio region for a check-in record: the week's numbers, the reconcile and the flags (C49)."""
    config = config_module.load(root)
    span = week_span(config, week_value)
    unit = _settings(config)["distance_unit"]
    numbers = week(root, span)
    ctx = weekflags.WeekFlagContext(root, today, span, "logged", config, None,
                                    tuple(flag_bouts(root, config, span, today)))
    found = weekflags.run(ctx)
    label = span.label()
    lines = [render.begin_marker(REGION_KIND, label),
             f"**Cardio, {label}** ({render.short_date(span.start)} → {render.short_date(span.end)}) · "
             f"tier {numbers['tier']}", ""]
    lifting = numbers["lifting"]
    lines.append(f"Lifting: {lifting['workouts']} workouts, {lifting['hard_sets']} hard sets, "
                 f"{_cell(lifting['minutes'])} min · coach-led done: {numbers['external']['done']} · "
                 f"session-RPE load {_cell(numbers['srpe']['total'])} (information only)")
    if not numbers["activity_source"]:
        lines += ["", "No activity source: runs and conditioning are not counted."]
    else:
        lines += ["", f"| Kind | Count | Distance ({unit}) | Minutes | Quality |", "| --- | --- | --- | --- | --- |",
                  f"| Runs | {numbers['run']['count']} | {_cell(numbers['run']['distance'])} | "
                  f"{_cell(numbers['run']['minutes'])} | {numbers['run']['quality']} |",
                  f"| Conditioning | {numbers['conditioning']['count']} | | "
                  f"{_cell(numbers['conditioning']['minutes'])} | {numbers['conditioning']['count']} |"]
        for kind, entry in numbers["other"].items():
            lines.append(f"| {kind.capitalize()} | {entry['count']} | | {_cell(entry['minutes'])} | |")
    items = reconcile(root, span, today)["items"]
    if items:
        lines += ["", f"| Planned | Date | Status | Logged | Distance Δ ({unit}) | Minutes Δ |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for item in items:
            delta = item["delta"]
            lines.append(
                f"| {item['title'] or item['kind']} | {render.short_date(dates.parse_date(item['date']))} | "
                f"{item['status']} | "
                f"{render.short_date(dates.parse_date(item['activity_date'])) if item['activity_date'] else ''} | "
                f"{_cell(_signed(_distance(delta['distance_meters'], unit)))} | "
                f"{_cell(_signed(_minutes(delta['duration_seconds'])))} |")
    lines += [""] + ([f"- {f['severity']} `{f['code']}`: {f['message']}" for f in found] or ["No cardio flags."])
    lines.append(render.end_marker(REGION_KIND, label))
    return "\n".join(lines)


def _cell(value):
    return "" if value is None else f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _signed(value):
    return None if value is None else (f"+{value:g}" if value > 0 else f"{value:g}")


def splice(text, label, region):
    """`text` with the cardio region for `label` replaced, or appended at the end when absent."""
    for found_id, start, end in render.find_regions(text, REGION_KIND):
        if found_id == label:
            return text[:start] + region + text[end:]
    if text and not text.endswith("\n"):
        text += "\n"
    return text + ("\n" if text else "") + region + "\n"
