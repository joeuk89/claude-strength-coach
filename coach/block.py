"""Blocks and light weeks: the hard-week count, the fatigue triggers and the status line (contract C42, C43).

R-02's rules scripted; `CLAUDE.md` "Fatigue management & deloads" is the
prose copy (rn:deloads.1). The 75 % and 50 % lines (rn:deloads.2), the
hard-week ceiling (rn:deloads.3), the three-week skip rule (rn:deloads.4),
the two-of-four trigger rule (rn:deloads.5), the hard-week session gate
(rn:deloads.11) and the `light` and `return` transform numbers are coaching
heuristics, not research cut-offs. A planned no-training break week neither
counts nor resets (rn:deloads.13): bookkeeping, not a research finding.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from coach import config as config_module
from coach import dates, decisions, fatigue, flags, history, jsonio, overlay, paths
from coach import program as program_module
from coach import render, stats, statusdays, structure, validity
from coach import state as state_module
from coach.config_tables import coaching
from coach.errors import CoachError, ValidationError
from coach.library import Library
from coach.plugins import PluginError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "blocks"
CLASSES = ("hard", "partial", "low", "light", "return", "one_off", "minimum", "break")
PAUSED = ("one_off", "minimum", "break")
ENDS_BLOCK = ("light", "return", "low")
TRIGGERS = ("readiness", "rpe_drift", "niggle", "sleep")
TRIGGER_NAMES = {"readiness": "readiness", "rpe_drift": "RPE drift", "niggle": "niggle", "sleep": "sleep"}
TYPES = ("deload", "light", "return")
OUTCOMES = ("adopted", "declined")
READINGS = ("poor", "ok")
CEILING_DEFAULT = 6
CEILING_RANGE = (4, 8)
HARD_SHARE = (3, 4)
RESET_SHARE = (1, 2)
LOGGED_SHARE = (2, 3)
RPE_SHORTFALL = 1.5
SKIP_BELOW = 3
TRIGGERS_FOR_LIGHT = 2
LAYOFF_DAYS = validity.RETURN_BANDS[0].upper
NO_DECAY_BAND = validity.RETURN_BANDS[0].id
_ID = re.compile(r"^b-(\d+)$")
_NOT_DUE = {"status": "not_due", "type": None, "reason": None, "week": None, "decision_id": None}


def path_for(root):
    return Path(root) / paths.BLOCKS


def exists(root):
    return path_for(root).is_file()


def load(root):
    """The block ledger, checked; None when the instance has none yet."""
    if not exists(root):
        return None
    doc = jsonio.read_doc(path_for(root), SCHEMA)
    errors = problems(doc)
    if errors:
        raise ValidationError(f"{paths.BLOCKS} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    return doc


def problems(doc):
    """What the schema cannot say: increasing ids, one open block at the end, weeks in order and inside their block."""
    errors = []
    previous_number, previous_week = 0, None
    for index, block in enumerate(doc["blocks"]):
        path = f"$.blocks[{index}]"
        number = int(_ID.match(block["id"]).group(1))
        if number <= previous_number:
            errors.append(Error(f"{path}.id", f"{block['id']} does not follow the block before it"))
        previous_number = number
        last = index == len(doc["blocks"]) - 1
        if (block["ended"] is None) != (block["end_reason"] is None):
            errors.append(Error(f"{path}.ended", "ended and end_reason are set together"))
        if not last and block["ended"] is None:
            errors.append(Error(f"{path}.ended", "only the newest block may be open"))
        if last and block["ended"] is not None:
            errors.append(Error(f"{path}.ended", "the newest block is open; a block that ends starts the next"))
        for position, week in enumerate(block["weeks"]):
            if previous_week is not None and week["week"] <= previous_week:
                errors.append(Error(f"{path}.weeks[{position}].week", f"{week['week']} is not after {previous_week}"))
            previous_week = week["week"]
            if any(t not in TRIGGERS for t in week["triggers"]):
                errors.append(Error(f"{path}.weeks[{position}].triggers", "unknown trigger"))
            signals = week["signals"]
            if (signals["sleep_source"] == "override") != (signals["sleep_reason"] is not None):
                errors.append(Error(f"{path}.weeks[{position}].signals.sleep_reason",
                                    "a sleep override carries its reason, and only an override does"))
        if block["weeks"] and block["end_reason"] is not None and block["weeks"][-1]["class"] != block["end_reason"]:
            errors.append(Error(f"{path}.end_reason",
                                f"{block['end_reason']} does not match the class of the week that ended the block"))
    return errors


def count_of(block):
    """A block's hard weeks so far: the newest week's count, else its seed."""
    return block["weeks"][-1]["count_after"] if block["weeks"] else block["seed_hard_weeks"]


def newest_week(ledger):
    """The newest closed week's start date, or None."""
    found = [week["week"] for block in ledger["blocks"] for week in block["weeks"]]
    return dates.parse_date(found[-1]) if found else None


def _newest_entry(ledger):
    found = [week for block in ledger["blocks"] for week in block["weeks"]]
    return found[-1] if found else None


def _next_id(ledger):
    numbers = [int(_ID.match(block["id"]).group(1)) for block in ledger["blocks"]]
    return f"b-{max(numbers, default=0) + 1:04d}"


def _new_block(block_id, started, seed=0, seed_reason=None):
    return {"id": block_id, "started": started, "seed_hard_weeks": seed, "seed_reason": seed_reason,
            "ended": None, "end_reason": None, "weeks": []}


def ceiling_of(program_doc):
    return program_doc["blocks"]["hard_weeks_ceiling"] if program_doc else CEILING_DEFAULT


def _timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _Instance:
    """Everything a block command reads, read once."""

    root: Path
    today: object
    now: object
    config: object
    program: dict
    state: dict
    ledger: dict
    decisions: dict
    library: Library
    overlays: list
    _run: object = None
    _workouts: dict = None

    @classmethod
    def load(cls, root, today=None, now=None):
        root = Path(root)
        config = config_module.load(root)
        today = (dates.parse_date(today) if isinstance(today, str) else today) or stats._today(config, now)
        return cls(root=root, today=today, now=now, config=config, program=program_module.load(root),
                   state=state_module.load(root), ledger=load(root), decisions=decisions.load(root),
                   library=Library.load(root), overlays=overlay.list(root))

    def week(self, day):
        return dates.week_span(day, self.config.athlete.week_starts)

    def moment(self):
        return self.now or datetime.now(timezone.utc)

    def workout(self, workout_id):
        if self._workouts is None:
            self._workouts = {w["workout_id"]: w for w in history.workouts(self.root, now=self.now)}
        return self._workouts.get(workout_id)

    def run(self):
        if self._run is None:
            from coach import propose
            self._run = propose.Run(self.root, self.config, self.today, self.now)
        return self._run


def _planned_lines(inst, row):
    """The exercise lines a planned session row prescribed: its overlay session, else the program session."""
    if row["overlay_id"] is not None:
        doc = next((d for d in inst.overlays if d["id"] == row["overlay_id"]), None)
        session = next((s for s in (doc or {}).get("sessions", ())
                        if s["session_id"] == row["session_id"] and s["date"] == row["date"]), None)
        if session is not None:
            return session["exercises"]
    session = next((s for s in inst.program["sessions"] if s["id"] == row["session_id"]), None)
    if session is None:
        return []
    return [{"exercise_id": line["exercise_id"],
             "sets": [group for group in line["sets"] for _ in range(group["count"])]}
            for line in session["exercises"]]


def _target_reps(set_):
    if set_.get("reps") is not None:
        return set_["reps"], str(set_["reps"])
    found = set_.get("rep_range")
    if found:
        return found["start"], f"{found['start']}–{found['end']}"
    return None, None


def compare(prescribed_lines, workout):
    """A logged session against its prescription: the sets, the effort and the reps.

    `rpe_sets` pairs a target with a logged RPE; `rpe_missing` has a target and no logged RPE, so its effort was not
    measured. `effort_below` and `effort_above` name each line whose mean RPE difference is past `RPE_SHORTFALL`
    under or over its targets; `reps_missed` each line with a working set under its target reps (the bottom of a
    range). `signals` lists which of the three are non-empty, and `hard_gate` is the rn:deloads.11 gate.
    """
    prescribed = logged = missing = 0
    deltas, short, below, above = [], [], [], []
    for line in prescribed_lines:
        wanted = [s for s in line["sets"] if overlay.is_working(s)]
        got = [s for e in workout["exercises"] if e["exercise_id"] == line["exercise_id"]
               for s in e["sets"] if s["type"] in history.WORKING_SET_TYPES]
        prescribed += len(wanted)
        logged += min(len(got), len(wanted))
        pairs = list(zip(wanted, got))
        line_deltas = [g["rpe"] - w["rpe"] for w, g in pairs if w.get("rpe") is not None and g.get("rpe") is not None]
        missing += sum(1 for w, g in pairs if w.get("rpe") is not None and g.get("rpe") is None)
        deltas += line_deltas
        if line_deltas:
            line_mean = sum(line_deltas) / len(line_deltas)
            effort = {"exercise_id": line["exercise_id"], "mean_rpe_delta": round(line_mean, 2),
                      "sets": len(line_deltas)}
            if line_mean < -RPE_SHORTFALL:
                below.append(effort)
            elif line_mean > RPE_SHORTFALL:
                above.append(effort)
        targets = [_target_reps(w) for w, _ in pairs]
        if any(t is not None and g.get("reps") is not None and g["reps"] < t
               for (t, _), (_, g) in zip(targets, pairs)):
            texts = list(dict.fromkeys(text for _, text in targets if text))
            short.append({"exercise_id": line["exercise_id"], "target": "/".join(texts),
                          "logged": [g.get("reps") for _, g in pairs]})
    mean = sum(deltas) / len(deltas) if deltas else None
    signals = [code for code, found in (("effort_below_target", below), ("effort_above_target", above),
                                        ("reps_missed", short)) if found]
    gate = (not prescribed or (LOGGED_SHARE[1] * logged >= LOGGED_SHARE[0] * prescribed
                               and (mean is None or mean >= -RPE_SHORTFALL)))
    return {"prescribed_sets": prescribed, "logged_sets": logged, "rpe_sets": len(deltas), "rpe_missing": missing,
            "mean_rpe_delta": round(mean, 2) if mean is not None else None, "effort_below": below,
            "effort_above": above, "reps_missed": short, "signals": signals, "hard_gate": gate}


def trained_as_prescribed(prescribed_lines, workout):
    """The hard-week session gate (rn:deloads.11): at least two thirds of the prescribed working sets logged and a
    mean RPE no more than 1.5 under target, sets without a logged RPE counting as on target.

    The gate counts training stress for the fatigue ledger; it is not proof the prescription was met, so a session
    with missed reps or a grind past its target still passes. `compare` reports those.
    """
    return compare(prescribed_lines, workout)["hard_gate"]


def _review_row(inst, row):
    """(counts toward a hard week, the compare() review or None) for one planned session row."""
    if "external_id" in row:
        return row["status"] == "done", None
    if row["tier"] != "core" or row["status"] != "trained" or row.get("unlogged"):
        return False, None
    session = next((s for s in inst.program["sessions"] if s["id"] == row["session_id"]), None)
    if session is not None and session["kind"] == "conditioning":
        return True, None
    workout = inst.workout(row["workout_id"])
    if workout is None:
        return False, None
    found = compare(_planned_lines(inst, row), workout)
    return found["hard_gate"], found


def _is_return(inst, span):
    """True when the week's overlay decays a line past the first return band and a layoff of 11+ days came before it."""
    decayed = []
    for day in span.days():
        found = overlay.pick_in_force(inst.overlays, day)
        if not found:
            continue
        for session in overlay.sessions_on(found[0], day):
            if any(((line.get("provenance") or {}).get("decay") or {}).get("band", NO_DECAY_BAND) != NO_DECAY_BAND
                   for line in session["exercises"]):
                decayed.append(day)
    if not decayed:
        return False
    first = min(decayed)
    last = history.last_lifting_date(inst.root, first, now=inst.now)
    return last is None or (first - last).days > LAYOFF_DAYS


def _days_off_after(inst, span):
    """Days from the last lifting to the first session back in the week after `span`; None when unknown.

    The first session back is the first one the schedule plans that week from today on and no ill status day
    covers; with none planned, or a program that cannot be planned, the later of that week's first day and today.
    Unknown: no lifting on record, or illness covers every session left that week.
    """
    week = inst.week(span.end + timedelta(days=1))
    earliest = max(week.start, inst.today)
    first = earliest
    if earliest <= week.end:
        from coach import propose
        try:
            planned = [day for day, _ in propose.plan_schedule(inst.run(), week).sessions if day >= earliest]
        except (CoachError, PluginError):
            planned = []
        ill = statusdays.ill_days(inst.root, week)
        eligible = [day for day in planned if day not in ill]
        if planned and not eligible:
            return None
        first = eligible[0] if eligible else earliest
    last = history.last_lifting_date(inst.root, first, now=inst.now)
    return (first - last).days if last is not None else None


def _facts(inst, span):
    report = structure.week(inst.root, span, today=inst.today, now=inst.now)
    planned, trained = report["planned"], report["trained"]
    sessions = []
    as_prescribed = 0
    for row in report["sessions"]:
        counts, found = _review_row(inst, row)
        as_prescribed += counts
        if found is not None:
            sessions.append(dict(found, session_id=row["session_id"], date=row["date"],
                                 workout_id=row["workout_id"]))
    ill = any(row.get("status") == "missed" and row.get("tag") == "ill" for row in report["sessions"])
    if report["kind"] in ("light",) + PAUSED:
        found = report["kind"]
    elif _is_return(inst, span):
        found = "return"
    elif planned and RESET_SHARE[1] * trained < RESET_SHARE[0] * planned:
        found = "low"
    elif planned and HARD_SHARE[1] * as_prescribed >= HARD_SHARE[0] * planned:
        found = "hard"
    else:
        found = "partial"
    return {"class": found, "planned": planned, "trained": trained, "as_prescribed": as_prescribed,
            "on_break": sum(1 for row in report["on_break"] if row.get("tier", "core") == "core"), "ill": ill,
            "kind": report["kind"], "kind_reason": report["kind_reason"], "sessions": sessions}


def classify(root, week_start, *, today=None, now=None):
    """The week's class (C42): hard, partial, low, light, return, one_off, minimum or break. Reads only."""
    inst = _Instance.load(root, today, now)
    return _facts(inst, inst.week(_as_date(week_start)))["class"]


def _as_date(value):
    if isinstance(value, dates.Span):
        return value.start
    return dates.parse_date(value) if isinstance(value, str) else value


def _short(day):
    return render.short_date(dates.parse_date(day))


def _drift_words(lifts):
    return [lift["name"] for lift in lifts if lift["status"] == "drift"]


def _niggle_words(flared):
    parts = []
    for row in flared:
        when = [f"aggravated {_short(day)}" for day in row["aggravated_on"]]
        if row["aggravated_since"] and not row["aggravated_on"]:
            when = [f"aggravated since {_short(row['aggravated_since'])}"]
        parts.append(f"{row['area']} ({', '.join(when)})")
    return ", ".join(parts)


def _sleep_words(sleep):
    if sleep["source"] == "override":
        return f"poor sleep (override: {sleep['reason']})"
    measured = sleep["measured"]
    return (f"poor sleep ({measured['short_nights']} of the 7 nights to {_short(measured['window']['end'])} under "
            f"{measured['short_hours']:g} h)")


def _signals(inst, span, readiness, sleep, sleep_reason, target):
    """(signals, fired triggers, detail words, evidence) for one closed week.

    Readiness and a sleep override apply to the target week only.
    """
    drift = fatigue.drift_review(inst, span)
    drifting = _drift_words(drift)
    flared = fatigue.flares(inst, span)
    readiness = (readiness if target else None) or "unknown"
    measured = fatigue.sleep_reading(inst.root, span)
    if target and sleep:
        sleep_value, source, reason = sleep, "override", sleep_reason
    else:
        sleep_value, source, reason = measured["value"], measured["source"], None
    signals = {"readiness": readiness, "sleep": sleep_value, "sleep_source": source, "sleep_reason": reason,
               "rpe_drift": bool(drifting), "niggle": bool(flared)}
    fired = [name for name, on in (("readiness", readiness == "poor"), ("rpe_drift", bool(drifting)),
                                   ("niggle", bool(flared)), ("sleep", sleep_value == "poor")) if on]
    evidence = {"readiness": {"value": readiness, "source": "athlete" if readiness != "unknown" else "none"},
                "rpe_drift": drift, "niggle": flared,
                "sleep": {"value": sleep_value, "source": source, "reason": reason, "measured": measured}}
    words = {"rpe_drift": f"RPE drift on {', '.join(drifting)}" if drifting else None,
             "niggle": f"aggravated niggle: {_niggle_words(flared)}" if flared else None,
             "readiness": "poor readiness", "sleep": _sleep_words(evidence["sleep"]) if sleep_value == "poor" else None}
    return signals, fired, words, evidence


def outcome_for(week_class, count, fired, ceiling, ill=False, days_off=None):
    """(outcome, light-week type, reason) by R-02's rules for a closed week.

    An illness week proposes a return week only when the days off to the first session back pass the first
    return band: a short illness is covered by the first session's illness cap alone.
    """
    if week_class == "low" and ill and (days_off is None or days_off > LAYOFF_DAYS):
        return "due", "return", "illness"
    if count >= ceiling:
        return "due", "deload", "ceiling"
    if len(fired) >= TRIGGERS_FOR_LIGHT:
        if count < SKIP_BELOW:
            return "skipped", None, None
        return "due", "deload" if {"rpe_drift", "niggle"} & set(fired) else "light", "triggers"
    if len(fired) == 1:
        return "watch", None, None
    return "none", None, None


def _week_text(day):
    return f"wk of {render.short_date(day)}"


def _decision(decisions_doc, decision_id):
    if not decision_id or decisions_doc is None:
        return None
    return next((d for d in decisions_doc["decisions"] if d["id"] == decision_id), None)


def _light_state_text(light, count, decisions_doc):
    status = light["status"]
    if status == "not_due":
        return "not due"
    if status == "watch":
        return "watch"
    if status == "skipped":
        return f"skipped ({count} hard weeks)"
    if status == "proposed":
        week = f" for {_week_text(light['week'])}" if light["week"] else ""
        detail = ", ".join(x for x in (light["type"], light["reason"]) if x)
        return f"proposed{week}" + (f" ({detail})" if detail else "")
    if status == "agreed":
        week = f", {_week_text(light['week'])}" if light["week"] else ""
        return f"agreed: {light['type'] or 'deload'}{week}"
    found = _decision(decisions_doc, light["decision_id"])
    reason = f" ({found['reason']})" if found else ""
    again = ", proposed again next check-in" if light["reason"] == "ceiling" else ""
    return f"declined{reason}{again}"


def status_line_for(block_state, ceiling, ledger=None, decisions_doc=None):
    """`Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>` (C43)."""
    number = int(_ID.match(block_state["id"]).group(1))
    count = block_state["hard_weeks_completed"]
    entry = _newest_entry(ledger) if ledger else None
    fired = entry["triggers"] if entry and entry["week"] == block_state["last_closed_week"] else []
    triggers = f"triggers {len(fired)} of {len(TRIGGERS)}"
    if fired:
        triggers += f" ({', '.join(TRIGGER_NAMES[t] for t in fired)})"
    return (f"Block {number} · {count} of {ceiling} hard weeks · {triggers} · "
            f"light week: {_light_state_text(block_state['light_week'], count, decisions_doc)}")


def status_line(root):
    """The status line from the instance's state, program, ledger and decisions; None without a readable state."""
    try:
        state_doc = state_module.load(root)
        program_doc = program_module.load(root) if program_module.exists(root) else None
        return status_line_for(state_doc["block"], ceiling_of(program_doc), load(root), decisions.load(root))
    except ValidationError:
        return None


def _deep_tier(inst, block_state):
    """(reasons, last deep date) by the check-in's own deep rules, counting a `--deep` close as a deep record."""
    from coach import checkin
    found = [r for r in checkin.reviews(inst.root) if r.date <= inst.today]
    if block_state["last_deep_review"]:
        found = sorted(found + [checkin.Record(dates.parse_date(block_state["last_deep_review"]), "deep",
                                               paths.STATE)], key=lambda r: r.date)
    deep = [r.date for r in found if r.tier == "deep"]
    reasons = []
    if checkin.deep_reasons(found, inst.today):
        reasons.append("six_weeks" if deep else "first_close")
    if checkin.deferred_reason(found):
        reasons.append("catch_up_deferred")
    return reasons, (deep[-1] if deep else None)


def _restructure_required(inst):
    # Run mode never presents the restructure, so no decision would ever clear it and every check-in would run deep.
    if coaching.mode(inst.config) == coaching.RUN:
        return False
    try:
        report = structure.adherence(inst.root, inst.today, today=inst.today, now=inst.now)
    except (ValidationError, PluginError):
        return False
    return any(f["code"] == "restructure_required" for f in report["flags"])


def repeated_decline(block_state, ledger, decisions_doc):
    """The declined `light_week` decision a proposal repeats unchanged, or None.

    Unchanged: the newest standing light-week decision declined an earlier proposal in this block, of the same
    type for the same reason, and every week closed since that proposal was due again without a break, firing no
    pair of triggers that decision had not seen. A repeat alone does not make a check-in deep; a new, changed or
    returning proposal does.
    """
    light = block_state["light_week"]
    if light["status"] != "proposed" or decisions_doc is None or ledger is None:
        return None
    standing = [d for d in decisions_doc["decisions"] if d["kind"] == "light_week" and d["status"] != "withdrawn"]
    newest = max(standing, key=lambda d: (d["made_at"], d["id"]), default=None)
    if newest is None or newest["outcome"] != "declined":
        return None
    details = newest["details"]
    if not ((block_state["started"] or "") <= details["week"] < (light["week"] or "")):
        return None
    if (details["type"], details["reason"]) != (light["type"], light["reason"]):
        return None
    last = block_state["last_closed_week"] or ""
    since = [w for w in ledger["blocks"][-1]["weeks"] if details["week"] <= w["week"] <= last]
    if not since or since[0]["week"] != details["week"]:
        return None
    seen = set(details["triggers"])
    for week in since:
        fired = set(week["triggers"])
        if week["outcome"] != "due" or (len(fired) >= TRIGGERS_FOR_LIGHT and not fired <= seen):
            return None
    return newest


def deep_review(inst, block_state):
    """Whether the check-in that closes the newest week is deep, and why (C43)."""
    reasons, last = _deep_tier(inst, block_state)
    repeat = None
    if block_state["light_week"]["status"] == "proposed":
        repeat = repeated_decline(block_state, inst.ledger, inst.decisions)
        if repeat is None:
            reasons.append("light_week_proposed")
    if _restructure_required(inst):
        reasons.append("restructure_required")
    return {"due": bool(reasons), "reasons": reasons, "last_deep_review": last.isoformat() if last else None,
            "repeat_of": repeat["id"] if repeat else None}


DEEP_REASON_WORDS = {"first_close": "no deep check-in on record", "six_weeks": "six weeks since the last deep check-in",
                     "catch_up_deferred": "a catch-up check-in deferred the deep review",
                     "light_week_proposed": "a light week is being proposed",
                     "restructure_required": "the adherence trigger fired"}
# The card derives these from the same records, so they only add words when its own record reasons are empty.
RECORD_DEEP_REASONS = ("first_close", "six_weeks", "catch_up_deferred")


def _flags(block_state, entry, deep, words=None, decisions_doc=None):
    light = block_state["light_week"]
    found = []
    if light["status"] == "proposed":
        reason = {"ceiling": f"{block_state['hard_weeks_completed']} completed hard weeks reach the ceiling",
                  "triggers": "two fatigue triggers"
                              + (f" ({', '.join(TRIGGER_NAMES[t] for t in entry['triggers'])})" if entry else ""),
                  "illness": "an illness week under 50 % trained",
                  "coach": "the coach's call"}.get(light["reason"], "carried over")
        when = f" for {_week_text(light['week'])}" if light["week"] else ""
        repeat = _decision(decisions_doc, deep.get("repeat_of"))
        again = (f"; proposed again after {repeat['id']} declined it ({repeat['reason']}), which alone does not make "
                 "the check-in deep") if repeat else ""
        found.append(flags.make("light_week_due", message=(
            f"Light week{when}: {light['type'] or 'deload'}, because {reason}{again}; record the answer with "
            "block decide")))
    elif light["status"] == "skipped" and entry:
        names = ", ".join(TRIGGER_NAMES[t] for t in entry["triggers"])
        found.append(flags.make("light_week_skipped", message=(
            f"Two fatigue triggers ({names}) below {SKIP_BELOW} completed hard weeks: light week skipped "
            f"({block_state['hard_weeks_completed']} hard weeks)")))
    elif light["status"] == "watch" and entry and entry["triggers"]:
        trigger = entry["triggers"][0]
        text = (words or {}).get(trigger) or TRIGGER_NAMES[trigger]
        found.append(flags.make("fatigue_watch", message=f"One fatigue trigger: {text}; watch it next week"))
    if deep["due"]:
        found.append(flags.make("deep_review_due", message=(
            "Run this check-in deep: " + "; ".join(DEEP_REASON_WORDS[r] for r in deep["reasons"]))))
    return found


def _number(value):
    return f"{round(abs(value), 1):g}"


def _session_flags(inst, review):
    """The prescription flags for one closed week's logged sessions: effort and reps against the prescription."""
    def name(exercise_id):
        return (inst.library.get(exercise_id) or {}).get("name", exercise_id)

    def efforts(lines):
        return "; ".join(f"{name(line['exercise_id'])} by {_number(line['mean_rpe_delta'])} across {line['sets']} sets"
                         for line in lines)

    found = []
    for session in review["sessions"]:
        where, session_id = f"{session['date']} {session['session_id']}", session["session_id"]
        if session["effort_below"]:
            found.append(flags.make("effort_below_target", session_id=session_id, message=(
                f"{where}: logged RPE averaged under target ({efforts(session['effort_below'])}); the loads "
                "look light, so review them with the athlete")))
        if session["effort_above"]:
            found.append(flags.make("effort_above_target", session_id=session_id, message=(
                f"{where}: logged RPE averaged over target ({efforts(session['effort_above'])}); review the "
                "loads and recovery with the athlete")))
        if session["reps_missed"]:
            lines = "; ".join(
                f"{name(line['exercise_id'])} {'/'.join(str(r) if r is not None else '-' for r in line['logged'])} "
                f"against {line['target']}" for line in session["reps_missed"])
            found.append(flags.make("reps_missed", session_id=session_id, message=(
                f"{where}: reps under the prescription ({lines}); the prescription was not met, whether or not the "
                "session counted toward the hard-week count")))
    return found


def _fatigue_flags(inst, review):
    """Calibration context for drift that has no earlier at-prescription exposure, and each recovery ceiling the
    logged work went over; neither is a fatigue trigger."""
    def name(exercise_id):
        return (inst.library.get(exercise_id) or {}).get("name", exercise_id)

    found = []
    for lift in review["fatigue"]["rpe_drift"]:
        if lift["status"] == "calibration":
            days = " and ".join(_short(e["date"]) for e in reversed(lift["exposures"]))
            found.append(flags.make("drift_calibration", exercise_id=lift["exercise_id"], message=(
                f"{lift['name']}: logged RPE ran 1 or more over target on {days}, with no earlier exposure at the "
                "prescription that did not drift, so this reads as load calibration, not fatigue drift; review the "
                "loads with the athlete")))
    for breach in review["recovery_ceilings"]:
        sets = ", ".join(f"set {s['set']} at RPE {s['rpe']:g} (ceiling {s['ceiling']:g})" for s in breach["sets"])
        found.append(flags.make("recovery_ceiling_exceeded", session_id=breach["session_id"],
                                exercise_id=breach["exercise_id"], message=(
            f"{breach['date']} {breach['session_id']}: {name(breach['exercise_id'])} went over its recovery RPE "
            f"ceiling ({breach['why']}): {sets}. A ceiling is a limit, not a target: ask how it felt and review "
            "the loads; it is not a fatigue trigger")))
    return found


def _review(span, facts):
    """One closed week's sessions against their prescriptions, and a summary that keeps the hard-week gate apart
    from completing the prescription."""
    sessions = facts["sessions"]
    parts = [f"{span.label()}: class {facts['class']}; {facts['as_prescribed']} of {facts['planned']} planned "
             "sessions passed the hard-week gate (rn:deloads.11), which counts training stress for the block, not "
             "completed prescriptions."]
    counts = [(sum(1 for s in sessions if code in s["signals"]), words) for code, words in (
        ("reps_missed", "missed reps"), ("effort_above_target", "logged effort over target"),
        ("effort_below_target", "logged effort under target"))]
    named = [f"{n} session{'s' if n != 1 else ''} {words}" for n, words in counts if n]
    if named:
        parts.append("Against the prescription: " + ", ".join(named) + ".")
    missing = sum(s["rpe_missing"] for s in sessions)
    if missing:
        parts.append(f"No RPE logged on {missing} set{'s' if missing != 1 else ''} with a target: the gate counts "
                     "them on target, but their effort was not measured.")
    if facts["kind"] == "illness":
        parts.append(f"Adherence leaves this week out ({facts['kind_reason']}).")
    return {"week": span.start.isoformat(), "label": span.label(), "class": facts["class"], "kind": facts["kind"],
            "kind_reason": facts["kind_reason"], "planned": facts["planned"], "trained": facts["trained"],
            "hard_gate": facts["as_prescribed"], "sessions": sessions, "summary": " ".join(parts)}


def _seed_from_state(block_state):
    return {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)),
            "blocks": [_new_block(block_state["id"], block_state["started"], block_state["hard_weeks_completed"],
                                  "carried over from data/state.json")]}


def _reopen(ledger):
    """The ledger without its newest closed week, undoing the block end that week caused."""
    blocks = ledger["blocks"]
    if not blocks[-1]["weeks"] and len(blocks) > 1 and blocks[-2]["weeks"]:
        blocks.pop()
        blocks[-1]["ended"] = blocks[-1]["end_reason"] = None
    for block in reversed(blocks):
        if block["weeks"]:
            block["weeks"].pop()
            return ledger
    return ledger


def _first_open_week(inst, ledger, target, replaced):
    """The first week a close covers: after the newest closed week, else after the week a seed counted through.

    A block seeded with a count and no week it ran through (a migrated
    state) covers every week before this close, so only the target closes.
    """
    newest = newest_week(ledger)
    if newest is not None:
        return inst.week(newest + timedelta(days=7))
    last = inst.state["block"]["last_closed_week"]
    if last and not replaced:
        return inst.week(dates.parse_date(last) + timedelta(days=7))
    block = ledger["blocks"][-1]
    if replaced or block["seed_reason"] is not None or not block["started"]:
        return target
    return inst.week(dates.parse_date(block["started"]))


def _light_week_after(previous, outcome, week_type, reason, target, replaced):
    if previous["status"] == "agreed" and previous["week"] and previous["week"] > target.end.isoformat():
        return dict(previous)
    if outcome == "due":
        week = (target.end + timedelta(days=1)).isoformat()
        if replaced and previous["status"] == "declined" and (previous["type"], previous["week"]) == (week_type, week):
            return dict(previous)
        return {"status": "proposed", "type": week_type, "reason": reason, "week": week, "decision_id": None}
    return dict(_NOT_DUE, status={"watch": "watch", "skipped": "skipped"}.get(outcome, "not_due"))


def _block_state(ledger, light_week, last_closed, last_deep):
    current = ledger["blocks"][-1]
    return {"id": current["id"], "started": current["started"], "hard_weeks_completed": count_of(current),
            "last_closed_week": last_closed, "last_deep_review": last_deep, "light_week": light_week}


def _render_program(root, dry_run):
    """Re-render routine/program.md, whose block line reads the state just written; returns the paths written."""
    try:
        pages = program_module.render_all(root)
    except ValidationError:
        return []
    page = paths.ROUTINE_PROGRAM_PAGE.as_posix()
    target = Path(root) / page
    text = pages[page]
    if target.is_file() and target.read_bytes().decode("utf-8") == text:
        return []
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    return [page]


def _with_block(inst, block_state):
    """The state with `block_state`; a null `program_adopted` is fixed at its earliest reading, because the
    fallback reads `block.started` and a new block must not move the adoption forward (C16)."""
    new_state = dict(inst.state, block=block_state)
    if not new_state.get("program_adopted"):
        found = [day for day in (state_module.adopted(inst.root, doc, inst.overlays) for doc in (inst.state, new_state))
                 if day is not None]
        if found:
            new_state["program_adopted"] = min(found).isoformat()
    return new_state


def _save(inst, ledger, block_state, dry_run):
    errors = validate_schema(ledger, jsonio.load_schema(SCHEMA)) + problems(ledger)
    new_state = dict(inst.state, block=block_state)
    errors += state_module.problems(new_state, inst.program)
    if errors:
        raise ValidationError(f"The block ledger or state would not be valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
    jsonio.write_doc(path_for(inst.root), ledger, dry_run)
    jsonio.write_doc(state_module.path_for(inst.root), new_state, dry_run)
    return _render_program(inst.root, dry_run) if not dry_run else []


def close(root, week_start, readiness=None, sleep=None, deep=False, dry_run=False, *, sleep_reason=None, today=None,
          now=None):
    """Close every week from the last closed one up to `week_start`'s week: class, count, triggers, rules (C42, C43).

    `sleep` overrides the week's measured sleep and needs `sleep_reason`: the athlete's feeling alone is readiness.
    """
    for name, value in (("readiness", readiness), ("sleep", sleep)):
        if value is not None and value not in READINGS:
            raise ValidationError(f"{name} must be one of {', '.join(READINGS)}")
    sleep_reason = sleep_reason.strip() if sleep_reason and sleep_reason.strip() else None
    if sleep is not None and sleep_reason is None:
        raise ValidationError("--sleep overrides the sleep measured from tracker or diary hours, so --sleep-reason "
                              "must say why (how the athlete felt is --readiness)")
    if sleep is None and sleep_reason is not None:
        raise ValidationError("--sleep-reason explains a --sleep override; give --sleep too")
    inst = _Instance.load(root, today, now)
    target = inst.week(_as_date(week_start))
    if target.start > inst.today:
        raise ValidationError(f"The week of {target.start} has not started yet; close a week once it is under way")
    ledger = inst.ledger or _seed_from_state(inst.state["block"])
    newest = newest_week(ledger)
    replaced = False
    if newest is not None and target.start < newest:
        raise ValidationError(f"The week of {target.start} is older than the newest closed week ({newest}); only the "
                              "newest closed week can be closed again")
    if newest is not None and target.start == newest:
        ledger, replaced = _reopen(ledger), True
    first = _first_open_week(inst, ledger, target, replaced)
    if first.start > target.start:
        raise ValidationError(f"The week of {target.start} is before block {ledger['blocks'][-1]['id']} started "
                              f"({ledger['blocks'][-1]['started']})")
    ceiling = ceiling_of(inst.program)
    closed_at = _timestamp(inst.moment())
    entries, ended, span, words, reviews = [], [], first, {}, []
    outcome = week_type = reason = None
    while span.start <= target.start:
        is_target = span.start == target.start
        facts = _facts(inst, span)
        block = ledger["blocks"][-1]
        count = 0 if facts["class"] in ENDS_BLOCK else count_of(block) + (facts["class"] == "hard")
        signals, fired, words, evidence = _signals(inst, span, readiness, sleep, sleep_reason, is_target)
        days_off = _days_off_after(inst, span) if facts["class"] == "low" and facts["ill"] else None
        outcome, week_type, reason = outcome_for(facts["class"], count, fired, ceiling, facts["ill"], days_off)
        entry = {"week": span.start.isoformat(), "class": facts["class"], "planned": facts["planned"],
                 "trained": facts["trained"], "as_prescribed": facts["as_prescribed"],
                 "on_break": facts["on_break"], "signals": signals,
                 "triggers": fired, "count_after": count, "outcome": outcome, "deep": bool(deep and is_target),
                 "closed_at": closed_at}
        block["weeks"].append(entry)
        entries.append(entry)
        reviews.append(dict(_review(span, facts), fatigue=evidence,
                            recovery_ceilings=fatigue.ceiling_breaches(inst, span)))
        if facts["class"] in ENDS_BLOCK:
            block["ended"], block["end_reason"] = span.end.isoformat(), facts["class"]
            ended.append(block["id"])
            ledger["blocks"].append(_new_block(_next_id(ledger), (span.end + timedelta(days=1)).isoformat()))
        span = inst.week(span.end + timedelta(days=1))

    previous = inst.state["block"]
    last_deep = inst.today.isoformat() if deep else previous["last_deep_review"]
    light_week = _light_week_after(previous["light_week"], outcome, week_type, reason, target, replaced)
    block_state = _block_state(ledger, light_week, target.start.isoformat(), last_deep)
    inst.state = _with_block(inst, block_state)
    inst.ledger = ledger
    deep_report = deep_review(inst, block_state)
    rendered = _save(inst, ledger, block_state, dry_run)
    raised = _flags(block_state, entries[-1], deep_report, words, inst.decisions)
    for review in reviews:
        raised += _session_flags(inst, review) + _fatigue_flags(inst, review)
    return {"weeks": entries, "replaced": replaced, "ended": ended, "block": block_state,
            "status_line": status_line_for(block_state, ceiling, ledger, inst.decisions),
            "deep_review": deep_report, "reviews": reviews, "flags": raised,
            "rendered": rendered, "written": not dry_run}


def status(root, *, today=None, now=None):
    """The state's block summary, the status line, whether the next check-in is deep, and the block flags (C42)."""
    inst = _Instance.load(root, today, now)
    block_state = inst.state["block"]
    ledger = inst.ledger
    entry = _newest_entry(ledger) if ledger else None
    if entry is not None and entry["week"] != block_state["last_closed_week"]:
        entry = None
    deep_report = deep_review(inst, block_state)
    current = ledger["blocks"][-1] if ledger else None
    return {"block": block_state, "ceiling": ceiling_of(inst.program),
            "status_line": status_line_for(block_state, ceiling_of(inst.program), ledger, inst.decisions),
            "deep_review": deep_report, "flags": _flags(block_state, entry, deep_report, decisions_doc=inst.decisions),
            "ledger": {"blocks": len(ledger["blocks"]), "current": current["id"],
                       "weeks_in_current": len(current["weeks"])} if ledger else None,
            "last_week": entry}


def _week_or_none(inst, value):
    return inst.week(_as_date(value)) if value is not None else None


def decide(root, outcome, week_type=None, week=None, reason=None, dry_run=False, *, today=None, now=None):
    """Record the athlete's answer to a light week as a C25 `light_week` decision and update the state (C43)."""
    if outcome not in OUTCOMES:
        raise ValidationError(f"outcome must be one of {', '.join(OUTCOMES)}")
    if week_type is not None and week_type not in TYPES:
        raise ValidationError(f"type must be one of {', '.join(TYPES)}")
    reason = reason.strip() if reason else None
    inst = _Instance.load(root, today, now)
    block_state = inst.state["block"]
    light = block_state["light_week"]
    span = _week_or_none(inst, week)
    proposed = light["status"] in ("proposed", "declined")
    if light["status"] == "agreed":
        raise ValidationError(f"A {light['type']} light week is already agreed for {light['week']}; withdraw "
                              f"{light['decision_id'] or 'its decision'} with decisions withdraw first")
    entry = _newest_entry(inst.ledger) if inst.ledger else None
    triggers = entry["triggers"] if entry and entry["week"] == block_state["last_closed_week"] else []
    if outcome == "declined":
        if not proposed:
            raise ValidationError("No light week is proposed, so there is nothing to decline")
        if not reason:
            raise ValidationError("--reason must say why the athlete declined the light week")
        if week_type is not None or span is not None:
            raise ValidationError("--type and --week apply to an adopted light week only")
        chosen_type, chosen_week, why = light["type"] or "deload", light["week"], light["reason"]
    else:
        if not proposed and not reason:
            raise ValidationError("No light week is proposed: adopting one is the coach's call, so --reason must say "
                                  "why")
        chosen_type = week_type or (light["type"] if proposed else None) or "deload"
        if proposed and light["type"] and chosen_type != light["type"] and not reason:
            raise ValidationError(f"The proposal is a {light['type']} week; --reason must say why it is a "
                                  f"{chosen_type} week instead")
        if span is not None:
            chosen_week = span.start.isoformat()
        elif proposed and light["week"]:
            chosen_week = light["week"]
        else:
            last = block_state["last_closed_week"]
            chosen_week = inst.week(dates.parse_date(last) + timedelta(days=7) if last
                                    else inst.today + timedelta(days=1)).start.isoformat()
        last = block_state["last_closed_week"]
        if last and chosen_week <= last:
            raise ValidationError(f"The week of {chosen_week} is already closed; a light week goes in a week after "
                                  f"{last}")
        why = light["reason"] if proposed else "coach"
    made_at = _timestamp(inst.moment())
    revisit = None
    if outcome == "declined" and why == "ceiling" and chosen_week:
        revisit = (dates.parse_date(chosen_week) + timedelta(days=6)).isoformat()
    record = {
        "id": None, "kind": "light_week", "made_at": made_at, "overlay_id": None, "scope": {}, "outcome": outcome,
        "reason": reason or f"{chosen_type} light week adopted", "standing": False, "until": None,
        "revisit_on": revisit, "proposed_sets": None, "chosen_sets": None,
        "details": {"type": chosen_type, "week": chosen_week or inst.week(inst.today + timedelta(days=1)).start.isoformat(),
                    "reason": why or "coach", "triggers": list(triggers),
                    "hard_weeks": block_state["hard_weeks_completed"]},
        "status": "active", "closed_at": None, "closed_reason": None,
    }
    updated, record = decisions.append(inst.root, inst.decisions, record, dry_run)
    if outcome == "declined":
        light_week = dict(light, status="declined", decision_id=record["id"])
    else:
        light_week = {"status": "agreed", "type": chosen_type, "reason": why or "coach", "week": chosen_week,
                      "decision_id": record["id"]}
    new_block = dict(block_state, light_week=light_week)
    inst.decisions = updated
    ledger = inst.ledger or _seed_from_state(block_state)
    rendered = _save(inst, ledger, new_block, dry_run)
    return {"decision": record, "block": new_block,
            "status_line": status_line_for(new_block, ceiling_of(inst.program), inst.ledger, updated),
            "command": propose_command(light_week) if outcome == "adopted" else None,
            "rendered": rendered, "written": not dry_run}


def propose_command(light_week):
    """The propose run that builds an agreed light week; a `deload` week takes the program's deload rule."""
    transform = "" if light_week["type"] == "deload" else f" --transform {light_week['type']}"
    return f"python3 -m coach propose week --week {light_week['week']} --kind deload{transform}"


def init(root, hard_weeks, started=None, through=None, reason=None, dry_run=False, *, today=None, now=None):
    """Start the ledger from a hard-week count the athlete confirms (C42); refuses once a week has been closed."""
    if not isinstance(hard_weeks, int) or hard_weeks < 0:
        raise ValidationError("--hard-weeks must be a whole number, 0 or more")
    inst = _Instance.load(root, today, now)
    if inst.ledger is not None and (newest_week(inst.ledger) is not None or len(inst.ledger["blocks"]) > 1):
        raise ValidationError(f"{paths.BLOCKS} already records closed weeks; block init only starts a ledger")
    last = inst.week(_as_date(through)) if through else inst.week(inst.week(inst.today).start - timedelta(days=1))
    if last.start > inst.today:
        raise ValidationError(f"--through {last.start} is a week that has not started yet")
    if started is not None:
        start = _as_date(started)
    else:
        start = last.start - timedelta(days=7 * max(hard_weeks - 1, 0))
    if start > last.end:
        raise ValidationError(f"--started {start} is after the week the count runs through ({last.start})")
    block_id = inst.state["block"]["id"]
    ledger = {"schema_version": jsonio.current_version(jsonio.load_schema(SCHEMA)),
              "blocks": [_new_block(block_id, start.isoformat(), hard_weeks,
                                    reason.strip() if reason else "confirmed with the athlete at block init")]}
    previous = inst.state["block"]
    block_state = {"id": block_id, "started": start.isoformat(), "hard_weeks_completed": hard_weeks,
                   "last_closed_week": last.start.isoformat(), "last_deep_review": previous["last_deep_review"],
                   "light_week": dict(previous["light_week"]) if previous["light_week"]["status"] == "agreed"
                   else dict(_NOT_DUE)}
    inst.state = _with_block(inst, block_state)
    rendered = _save(inst, ledger, block_state, dry_run)
    return {"ledger": ledger, "block": block_state, "next_close": inst.week(last.end + timedelta(days=1)).label(),
            "status_line": status_line_for(block_state, ceiling_of(inst.program), ledger, inst.decisions),
            "rendered": rendered, "written": not dry_run}
