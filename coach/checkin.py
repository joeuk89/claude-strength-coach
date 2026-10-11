"""Check-in records, the card, missed-session tallies and the record skeleton (contract C36).

The card is the Sunday message as data: the window's sessions against the
overlay in force, results against the prescription, e1RM changes, flags
and Hevy routine state, then the numbered fields the data cannot answer.
`card_text` turns it into the message text. A check-in record is
`check-ins/<date>.md`; its week-review region is the card's data rendered
as of the record date from committed history only, so the freshness sweep
gives the same answer on every machine. A deep check-in falls due
`DEEP_AFTER_DAYS` after the last one, a coaching heuristic (rn:deloads.12).
"""

import copy
import importlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property
from pathlib import Path

from coach import checkin_catchup, checkin_parts, dates, flags, history, overlay, paths, program, render, routines
from coach import state, stats, units, validity
from coach import config as config_module
from coach.config_tables import coaching
from coach.config_tables.sessions import cap_minutes
from coach.errors import ValidationError
from coach.hevy.cache import HevyCache
from coach.library import Library

DEEP_AFTER_DAYS = 42
E1RM_ROW_LIMIT = 8          # a heuristic: as many lifts as a message reads at a glance
WORD_CEILINGS = {"weekly": 600, "deep": 1000, "catch-up": 600}    # heuristics, prose words outside regions
CARD_VERSION = 3
TIERS = ("weekly", "deep", "catch-up")
CARD_TIERS = ("weekly", "deep")
PROGRAM_START = "program-start"
CATCH_UP = "catch_up"
TIER_OF_MODE = {CATCH_UP: "catch-up"}
REGION_KIND = "week-review"
FIELD_ORDER = ("sessions", "coach_led", "runs", "sleep", "niggles", "nutrition", "meal_plan", "next_week")
HEVY_EDITS = "hevy_edits"
LABELS = {
    "sessions": "Sessions", "coach_led": "Coach-led", "runs": "Runs", "sleep": "Sleep", "niggles": "Niggles",
    "nutrition": "Nutrition", "meal_plan": "Meal plan", "next_week": "Next week", HEVY_EDITS: "Hevy edits",
}
MISS_TAG_TEXT = " / ".join(history.MISS_TAGS)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

SLEEP_ASK = ("One line: average hours a night, dates covered and source "
             "(manual diary, self-reported period mean or tracker), and how it felt.")
NUTRITION_ASK = (
    "MacroFactor: trend weight · expenditure · targets (kcal/protein) · 7-day average (kcal/protein). "
    "A screenshot works.\n"
    "No MacroFactor: this week's morning weigh-ins, and roughly how eating went "
    "(with your average daily protein if you track it).\n"
    "Both: days logged (of 7) · anchors most days (y/n).\n"
    "Nutrition not set up yet: one morning scale weight."
)
MEAL_PLAN_ASK = "What stuck, what got swapped?"
NEXT_WEEK_ASK = "Anything different: travel, schedule, kit, illness?"

_RECORD_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
_TITLE = re.compile(r"^# Check-in [—–-] (\d{4}-\d{2}-\d{2})(?: \((weekly|deep|catch-up)\))?\s*$")
_START_TITLE = re.compile(r"^# Program start [—–-] (\d{4}-\d{2}-\d{2})\s*$")
_ANY_REGION = re.compile(r"<!-- coach:begin (\S+) (\S+) -->.*?<!-- coach:end \1 \2 -->", re.DOTALL)
_DETAILS = re.compile(r"<details>.*?</details>", re.DOTALL)
_WORD = re.compile(r"\S*\w\S*")


def _as_date(value):
    if value is None or isinstance(value, date):
        return value
    return dates.parse_date(str(value))


def _round(value):
    quantised = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return units.json_number(float(quantised))


def _text(value):
    quantised = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    found = format(quantised, "f").rstrip("0").rstrip(".")
    return "0" if found in ("", "-0") else found


def _signed(value):
    if value is None:
        return "—"
    return "±0" if value == 0 else f"{'+' if value > 0 else ''}{_text(value)}"


@dataclass(frozen=True)
class Record:
    date: date
    tier: str
    path: Path

    def to_json(self):
        return {"date": self.date.isoformat(), "tier": self.tier, "path": self.path.as_posix()}


def parse_title(line):
    """(date, tier or None); program starts use `PROGRAM_START`, legacy check-ins have no tier."""
    match = _TITLE.match(line or "") or _START_TITLE.match(line or "")
    if not match:
        return None
    try:
        return dates.parse_date(match.group(1)), (PROGRAM_START if match.re is _START_TITLE else match.group(2))
    except ValueError:
        return None


def first_line(path):
    text = Path(path).read_text(encoding="utf-8")
    return text.split("\n", 1)[0]


def is_record_name(name):
    return bool(_RECORD_NAME.match(name))


def records(root):
    """Valid check-in and program-start records, oldest first; legacy check-in titles count as deep."""
    directory = Path(root) / paths.CHECKINS_DIR
    found = []
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        match = _RECORD_NAME.match(path.name)
        if not match:
            continue
        try:
            day = dates.parse_date(match.group(1))
        except ValueError:
            continue
        title = parse_title(first_line(path))
        if title is None or title[0] != day:
            continue
        tier = title[1] or "deep"
        found.append(Record(day, tier, paths.CHECKINS_DIR / path.name))
    return found


def reviews(root):
    return [record for record in records(root) if record.tier != PROGRAM_START]


@dataclass(frozen=True)
class Due:
    last: Record
    days_since: int
    due_date: date
    overdue_days: int
    mode: str
    tier_reasons: list

    def to_json(self):
        return {"last": self.last.to_json() if self.last else None, "days_since": self.days_since,
                "due_date": self.due_date.isoformat() if self.due_date else None,
                "overdue_days": self.overdue_days, "mode": self.mode, "tier_reasons": list(self.tier_reasons)}


def _cadence(root):
    if not (Path(root) / paths.CONFIG).is_file():
        return config_module.registered_tables()["checkin"].keys["cadence_days"].default
    return config_module.load(root)["checkin"]["cadence_days"]


def deep_reasons(found, day):
    """Why a check-in on `day` runs deep, given the records before it; empty when weekly will do."""
    found = [record for record in found if record.tier != PROGRAM_START]
    if not found:
        return ["first check-in"]
    deep = [r for r in found if r.tier == "deep"]
    if not deep:
        return ["no deep check-in on record"]
    age = (day - deep[-1].date).days
    if age >= DEEP_AFTER_DAYS:
        return [f"last deep check-in {deep[-1].date.isoformat()} was {age} days ago ({DEEP_AFTER_DAYS} or more)"]
    return []


def deferred_reason(found):
    """"deferred from catch-up <date>" when the newest records are catch-ups and a deep review was due at one."""
    found = [record for record in found if record.tier != PROGRAM_START]
    for index in range(len(found) - 1, -1, -1):
        record = found[index]
        if record.tier != "catch-up":
            return None
        if deep_reasons(found[:index], record.date):
            return f"deferred from catch-up {record.date.isoformat()}"
    return None


def catch_up_after_days():
    """Days without a check-in before the card switches to catch-up: the longest layoff with no return week."""
    return validity.RETURN_BANDS[0].upper


def mode_for(found, day):
    """(mode, deep reasons) for a check-in on `day` after the records `found`: catch-up after a long gap, which
    never runs deep, else deep when one is due or a catch-up deferred one, else weekly."""
    found = [record for record in found if record.tier != PROGRAM_START]
    reasons = deep_reasons(found, day)
    deferred = deferred_reason(found)
    if deferred:
        reasons = [deferred] + reasons
    if found and (day - found[-1].date).days > catch_up_after_days():
        return CATCH_UP, reasons
    return ("deep" if reasons else "weekly"), reasons


def first_review_anchor(root):
    """Later setup records and block rollovers cannot postpone the earliest persisted start."""
    from coach import block
    starts = [record.date for record in records(root) if record.tier == PROGRAM_START]
    ledger = block.load(root)
    starts += [dates.parse_date(item["started"]) for item in (ledger or {}).get("blocks", []) if item["started"]]
    state_doc = history.load_optional(state, root)
    started = (state_doc or {}).get("block", {}).get("started")
    if started:
        starts.append(dates.parse_date(started))
    return min(starts, default=None)


def due(root, today):
    """When the next check-in falls due and which mode it runs in."""
    today = _as_date(today)
    found = [r for r in reviews(root) if r.date <= today]
    if not found:
        started = first_review_anchor(root)
        due_date = started + timedelta(days=_cadence(root)) if started else None
        overdue = max(0, (today - due_date).days) if due_date else 0
        return Due(None, None, due_date, overdue, "first", ["first check-in"])
    last = found[-1]
    days = (today - last.date).days
    due_date = last.date + timedelta(days=_cadence(root))
    mode, reasons = mode_for(found, today)
    return Due(last, days, due_date, max(0, (today - due_date).days), mode, reasons)


def _reps(set_):
    if set_.get("rep_range") is not None:
        return f"{set_['rep_range']['start']}–{set_['rep_range']['end']}"
    if set_.get("reps") is not None:
        return _text(set_["reps"])
    if set_.get("duration_seconds") is not None:
        return f"{_text(set_['duration_seconds'])} s"
    if set_.get("distance_meters") is not None:
        return f"{_text(set_['distance_meters'])} m"
    return "?"


def _load(load_mode, set_):
    if set_.get("load"):
        return units.format_load(set_["load"])
    if load_mode in units.LOADED_MODES:
        return render.CHOOSE_THE_LOAD
    return None


def prescribed_text(line):
    """`3×10 @ 22.5/hand (Hevy: 45) @ RPE 8`: a line's working sets, consecutive equal sets collapsed."""
    groups = []
    for set_ in (s for s in line["sets"] if overlay.is_working(s)):
        key = (_reps(set_), _load(line["load_mode"], set_), set_.get("rpe"))
        if groups and groups[-1][0] == key:
            groups[-1][1] += 1
        else:
            groups.append([key, 1])
    parts = []
    for (reps, load, rpe), count in groups:
        part = f"{count}×{reps}"
        if load:
            part += f" @ {load}"
        if rpe is not None:
            part += f" @ RPE {_text(rpe)}"
        parts.append(part)
    return " + ".join(parts) or None


def logged_text(workout, exercise_id):
    """`10, 10, 10 @ 22.5/hand (Hevy: 45) @ RPE 8`: the working sets logged for one exercise, or None."""
    sets = [s for e in workout["exercises"] if e["exercise_id"] == exercise_id
            for s in e["sets"] if s["type"] in history.WORKING_SET_TYPES]
    groups = []
    for set_ in sets:
        load = units.format_load(set_["load"]) if set_.get("load") else None
        key = (load, set_.get("rpe"))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(set_)
        else:
            groups.append([key, [set_]])
    parts = []
    for (load, rpe), members in groups:
        part = ", ".join(_reps(s) for s in members)
        if load:
            part += f" @ {load}"
        if rpe is not None:
            part += f" @ RPE {_text(rpe)}"
        parts.append(part)
    return " + ".join(parts) or None


def _cell(value):
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _row(cells):
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


@dataclass
class _Instance:
    root: Path
    config: object
    program: dict
    state: dict
    library: Library
    overlays: list

    @classmethod
    def load(cls, root):
        root = Path(root)
        return cls(root, config_module.load(root), history.load_optional(program, root),
                   history.load_optional(state, root), Library.load(root), overlay.list(root))

    @cached_property
    def adopted(self):
        return state.adopted(self.root, self.state, self.overlays)

    def schedules_on(self, day):
        return state.plans_on(self.adopted, day)

    def program_session(self, session_id):
        sessions = self.program["sessions"] if self.program else []
        return next((s for s in sessions if s["id"] == session_id), None)

    def name(self, exercise_id):
        entry = self.library.get(exercise_id)
        return entry["name"] if entry else exercise_id


def _window(inst, found, end):
    if found:
        start = found[-1].date + timedelta(days=1)
    elif inst.overlays:
        start = min(dates.parse_date(doc["span"]["start"]) for doc in inst.overlays)
    else:
        start = end
    return dates.Span(min(start, end), end)


def _sessions(inst, window, adherence, workouts):
    rows, kept = [], []
    for row in adherence["sessions"]:
        if row["status"] == "upcoming":
            continue
        planned = inst.program_session(row["session_id"])
        tier = planned["tier"] if planned else "core"
        if tier == "optional" and row["status"] != "trained":
            continue
        workout = workouts.get(row["workout_id"])
        rows.append({
            "date": row["date"], "session_id": row["session_id"], "title": row["title"], "tier": tier,
            "status": row["status"], "moved": row["moved"], "unlogged": row["unlogged"],
            "tag": row["tag"] if row["status"] == "missed" else None, "workout_id": row["workout_id"],
            "workout_date": row["workout_date"], "minutes": workout["duration_minutes"] if workout else None,
            "cap_minutes": cap_minutes(inst.config, row["session_id"]),
        })
        kept.append(row)
    core = [r for r in rows if r["tier"] == "core"]
    extra = [{"workout_id": w["workout_id"], "date": w["date"], "title": w["title"], "session_id": w["session_id"],
              "minutes": workouts[w["workout_id"]]["duration_minutes"] if w["workout_id"] in workouts else None,
              "unsynced": w["unsynced"]} for w in adherence["extra"]]
    return {
        "planned_core": len(core), "trained_core": sum(1 for r in core if r["status"] == "trained"),
        "optional_trained": sum(1 for r in rows if r["tier"] == "optional"),
        "rows": rows, "external": _external(inst, window), "extra": extra,
    }, kept


def _external(inst, window):
    notes = history.annotations(inst.root, "external")
    found = []
    for external in inst.program["external_sessions"] if inst.program else []:
        if not external.get("weekday"):
            continue
        for day in window.days():
            if WEEKDAYS[day.weekday()] != external["weekday"] or not inst.schedules_on(day):
                continue
            matching = [a for a in notes if a["date"] == day.isoformat() and a["external_id"] == external["id"]]
            note = matching[-1] if matching else None
            found.append({"date": day.isoformat(), "external_id": external["id"], "title": external["title"],
                          "done": note["done"] if note else None, "note": note.get("note") if note else None})
    return sorted(found, key=lambda e: (e["date"], e["external_id"]))


def _exercises(inst, kept, workouts):
    by_id = {doc["id"]: doc for doc in inst.overlays}
    rows = []
    for row in kept:
        if row["status"] != "trained" or row.get("conditioning"):
            continue
        doc = by_id[row["overlay_id"]]
        session = next(s for s in doc["sessions"] if s["session_id"] == row["session_id"] and s["date"] == row["date"])
        workout = workouts.get(row["workout_id"])
        for line, result in zip(session["exercises"], row["exercises"]):
            rows.append({
                "date": row["date"], "session_id": row["session_id"], "exercise_id": line["exercise_id"],
                "name": inst.name(line["exercise_id"]), "prescribed": prescribed_text(line),
                "logged": logged_text(workout, line["exercise_id"]) if workout else None,
                "status": result["status"], "rpe_delta": result["rpe_delta"],
            })
    return rows


def _compound_patterns():
    try:
        return frozenset(importlib.import_module("coach.patterns").COMPOUND_PATTERNS)
    except (ImportError, AttributeError):
        return frozenset()


def _e1rm(inst, window, live, now):
    evidence = stats.e1rm_series(inst.root, include_unsynced=live, now=now, as_of=now)
    series = evidence["series"]
    start, end = window.start.isoformat(), window.end.isoformat()
    order = {exercise_id: index for index, exercise_id in enumerate(inst.library.ids())}
    compounds = _compound_patterns()
    rows = []
    for exercise_id, points in series.items():
        upto = [p for p in points if p["date"] <= end]
        if not upto or upto[-1]["date"] < start:
            continue
        latest = upto[-1]
        delta = _round(latest["e1rm"] - upto[-2]["e1rm"]) if len(upto) > 1 else None
        entry = inst.library.get(exercise_id) or {}
        rows.append({"exercise_id": exercise_id, "name": inst.name(exercise_id),
                     "load_mode": entry.get("load_mode"), "date": latest["date"], "e1rm": latest["e1rm"],
                     "delta": delta, "method": latest["method"], "basis": latest["basis"]})
    rows.sort(key=lambda r: ((inst.library.get(r["exercise_id"]) or {}).get("pattern") not in compounds,
                             order.get(r["exercise_id"], len(order)), r["exercise_id"]))
    notes = {}
    for exercise_id, observed in evidence["observations"].items():
        for o in observed:
            note = stats.capacity_note(o) if start <= o["date"] <= end else None
            if note:
                notes[exercise_id] = f"{inst.name(exercise_id)} ({o['date']}): {note}"
    return rows[:E1RM_ROW_LIMIT], list(notes.values())[:E1RM_ROW_LIMIT]


def _verify_lines(root):
    path = Path(root) / paths.HEVY_WRITES
    if not path.is_file():
        return []
    found = []
    for text in path.read_text(encoding="utf-8").splitlines():
        try:
            line = json.loads(text) if text.strip() else None
        except ValueError:
            continue
        if isinstance(line, dict) and line.get("kind") == "verify":
            found.append(line)
    return found


def _carried(inst, routine_id, session_id, end):
    """(overlay, session): the newest approved overlay started by `end` whose session `session_id` uses this routine."""
    holding = []
    for doc in inst.overlays:
        if not overlay.is_approved(doc) or doc["span"]["start"] > end.isoformat():
            continue
        sessions = [s for s in doc["sessions"] if s["session_id"] == session_id and not s.get("temporary")
                    and history.routine_of(doc, s, inst.state) == routine_id]
        if sessions:
            holding.append((doc, sessions))
    if not holding:
        return None, None
    doc, sessions = max(holding, key=lambda pair: (dates.parse_timestamp(pair[0]["created_at"]), pair[0]["id"]))
    upcoming = [s for s in sessions if s["date"] >= end.isoformat()]
    return doc, (min(upcoming, key=lambda s: s["date"]) if upcoming else max(sessions, key=lambda s: s["date"]))


_CHANGE_PATH = re.compile(r"^exercises\[(\d+)\](?:\.(.+))?$")
_CHANGE_FIELDS = {"rest_seconds": "rest", "superset_id": "superset", "rep_range": "rep range", "reps": "reps",
                  "type": "set type", "weight_kg": "load", "notes": "notes", "duration_seconds": "duration",
                  "distance_meters": "distance", "folder_id": "folder", "title": "title"}


def _template_name(inst, template_id):
    entry = inst.library.by_hevy_template_id(template_id) if template_id else None
    return entry["name"] if entry else (template_id or "an exercise")


def describe_change(inst, change, cached):
    """A C9 change in words: `Bench Press (Dumbbell) added`, `Squat (Barbell): reps changed`."""
    match = _CHANGE_PATH.match(change["path"])
    if not match:
        return f"{_CHANGE_FIELDS.get(change['path'], change['path'])} changed"
    index, rest = int(match.group(1)), match.group(2)
    have = cached.get("exercises") or []
    title = have[index].get("title") if index < len(have) else None
    if rest is None:
        before, after = change["before"], change["after"]
        if after is None:
            return f"{title or _template_name(inst, before['exercise_template_id'])} added"
        wanted = _template_name(inst, after["exercise_template_id"])
        return f"{wanted} removed" if before is None else f"{title or 'another exercise'} in place of {wanted}"
    if re.fullmatch(r"sets\[\d+\]", rest):
        return f"{title}: a set {'added' if change['after'] is None else 'removed'}"
    name = rest.rsplit(".", 1)[-1]
    return f"{title}: {_CHANGE_FIELDS.get(name, name)} changed"


def _hevy(inst, end):
    """Per routine of an active session: does the Hevy cache hold the overlay the last pass wrote? (R-03, C36)"""
    if not inst.config.hevy.enabled or not inst.state:
        return [], []
    cache = HevyCache(inst.root)
    audit = _verify_lines(inst.root)
    rows, raised = [], []
    for routine_id, mapped in sorted(inst.state["hevy"]["routines"].items()):
        session_id = mapped["session_id"]
        planned = inst.program_session(session_id)
        if inst.program and (planned is None or planned["status"] != "active"):
            continue
        doc, session = _carried(inst, routine_id, session_id, end)
        if doc is None:
            continue
        lines = [line for line in audit if line.get("routine_id") == routine_id]
        written = any(line.get("overlay_id") == doc["id"] and line.get("overlay_hash") == doc["approval"]["hash"]
                      and line.get("verified") is True for line in lines)
        cached = cache.routine(routine_id)
        entry = {"routine_id": routine_id, "title": (cached or {}).get("title") or session["title"],
                 "session_id": session_id, "overlay_id": doc["id"], "state": "not_cached", "changes": [],
                 "summary": None}
        rows.append(entry)
        if not written:
            entry["state"] = "not_written"
            raised.append(flags.make("stale_routine", session_id=session_id, message=(
                f"{entry['title']}: routine {routine_id} does not hold overlay {doc['id']}; the last programming "
                "pass did not write and verify it")))
            continue
        if cached is None:
            continue
        changes = routines.diff(routines.intended_body(doc, session, cached), cached)
        verified_at = max((dates.parse_timestamp(line["at"]) for line in lines if line.get("at")), default=None)
        updated = cached.get("updated_at")
        edited = bool(updated) and (verified_at is None or dates.parse_timestamp(updated) > verified_at)
        structural = [c for c in changes if c["class"] == routines.STRUCTURAL]
        if structural and edited:
            entry.update(state="edited_in_app", changes=structural)
        elif changes and edited:
            entry.update(state="loads_edited", changes=changes)
        else:
            entry["state"] = "current"
        described = [describe_change(inst, change, cached) for change in entry["changes"]]
        entry["summary"] = "; ".join(dict.fromkeys(described)) or None
    return rows, raised


def _hevy_runs(inst, window):
    try:
        if not inst.config["activity"]["enabled"]:
            return []
        from coach.activity.store import ActivityStore
        found = ActivityStore(inst.root, inst.config).activities(window, kinds=("run",))
    except (KeyError, ImportError, ValidationError):
        return []
    return [a for a in found if a["source"].startswith("hevy")]


def misses(root, since, until, now=None, include_unsynced=True):
    """Missed sessions by tag and by session: `miss` annotations plus untagged missed planned sessions (C18).
    An optional session skipped is not a miss, so it is never counted."""
    since, until = _as_date(since), _as_date(until)
    by_tag = {tag: 0 for tag in history.MISS_TAGS + ("untagged",)}
    by_session = {}

    def count(tag, session_id):
        by_tag[tag or "untagged"] += 1
        by_session[session_id] = by_session.get(session_id, 0) + 1

    program_doc = history.load_optional(program, root)
    optional = {s["id"] for s in (program_doc["sessions"] if program_doc else []) if s["tier"] == "optional"}
    adherence = stats.adherence(root, span=(since, until), include_unsynced=include_unsynced, today=until, now=now)
    docs = overlay.list(root)
    spans = {doc["id"]: doc["span"] for doc in docs}
    planned = [(row["session_id"], spans[row["overlay_id"]]) for row in adherence["sessions"]]
    moved = overlay.moved_away(docs)
    for row in adherence["sessions"]:
        if row["status"] == "missed" and row["session_id"] not in optional:
            count(row["tag"], row["session_id"])
    for note in history.annotations(root, "miss"):
        if not since.isoformat() <= note["date"] <= until.isoformat() or note["session_id"] in optional:
            continue
        if (note["date"], note["session_id"]) in moved or any(
                sid == note["session_id"] and span["start"] <= note["date"] <= span["end"] for sid, span in planned):
            continue
        count(note.get("tag"), note["session_id"])
    return {"since": since.isoformat(), "until": until.isoformat(), "by_tag": by_tag,
            "by_session": dict(sorted(by_session.items())), "sessions_missed": sum(by_session.values())}


def _catch_up_reasons(found, end, deep):
    gap = [f"{(end - found[-1].date).days} days since the last check-in, over {catch_up_after_days()}"] if found else []
    return gap + ([f"deep review deferred ({'; '.join(deep)})"] if deep else [])


def _build(root, today, until=None, tier=None, now=None, live=True, parts=True, with_return=None,
           deep_review_reasons=()):
    inst = _Instance.load(root)
    end = _as_date(until) or _as_date(today)
    found = [r for r in reviews(inst.root) if r.date < end]
    window = _window(inst, found, end)
    mode, reasons = mode_for(found, end)
    if deep_review_reasons:
        from coach.block import DEEP_REASON_WORDS
        unknown = set(deep_review_reasons) - DEEP_REASON_WORDS.keys()
        if unknown:
            raise ValueError(f"unknown deep review reasons: {', '.join(sorted(unknown))}")
        reasons = list(dict.fromkeys(reasons + [DEEP_REASON_WORDS[r] for r in deep_review_reasons]))
        if mode != CATCH_UP:
            mode = "deep"
    if tier == "weekly":
        mode, reasons = "weekly", []
    elif tier == "deep":
        mode = "deep"
    elif tier == CATCH_UP:
        mode = CATCH_UP
    deferred = mode == CATCH_UP and bool(reasons)
    if mode == CATCH_UP:
        reasons = _catch_up_reasons(found, end, reasons)

    adherence = stats.adherence(inst.root, span=(window.start, window.end), include_unsynced=live, today=end, now=now)
    workouts = {w["workout_id"]: w for w in history.workouts(inst.root, include_unsynced=live, now=now)}
    sessions, kept = _sessions(inst, window, adherence, workouts)
    hevy_rows, hevy_flags = _hevy(inst, end) if live else ([], [])
    raised = (stats.audit(inst.root, include_unsynced=live, today=end, now=now)["flags"]
              + stats.durations(inst.root, span=(window.start, window.end), include_unsynced=live, now=now)["flags"]
              + hevy_flags)
    e1rm, e1rm_notes = _e1rm(inst, window, live, now)
    card = {
        "schema_version": CARD_VERSION, "date": end.isoformat(), "window": window.to_json(), "mode": mode,
        "tier_reasons": reasons, "deep_deferred": deferred,
        "days_since_last": (end - found[-1].date).days if found else None,
        "unsynced": sum(1 for w in workouts.values() if w["unsynced"] and window.contains(dates.parse_date(w["date"]))),
        "sessions": sessions, "exercises": _exercises(inst, kept, workouts), "e1rm": e1rm, "e1rm_notes": e1rm_notes,
        "hevy": hevy_rows, "flags": raised, "fields": [], "facts": [], "misses": None,
        "catch_up": None,
    }

    replaced, extra_ids = {}, []
    if parts:
        context = checkin_parts.CardContext(inst.root, end, window, mode, copy.deepcopy(card))
        part_reasons = []
        for part in checkin_parts.discover():
            contribution = part.contribute(context)
            if contribution is None:
                continue
            for field_id, value in contribution.fields.items():
                if field_id not in part.fields:
                    raise ValidationError(f"card part {part.name} sets field {field_id!r}, which it does not own; "
                                          f"its FIELDS are {', '.join(part.fields) or 'empty'}")
                replaced[field_id] = value
                if field_id not in FIELD_ORDER + (HEVY_EDITS,) and field_id not in extra_ids:
                    extra_ids.append(field_id)
            card["facts"] += list(contribution.facts)
            card["flags"] += list(contribution.flags)
            part_reasons += list(contribution.tier_reasons)
        if part_reasons and tier != "weekly" and mode == CATCH_UP:
            card["deep_deferred"] = True
            card["tier_reasons"] = reasons + [f"deep review deferred ({'; '.join(part_reasons)})"]
        elif part_reasons and tier != "weekly":
            card["tier_reasons"] = reasons + part_reasons
            card["mode"] = "deep"
    if tier == "deep" and not card["tier_reasons"]:
        card["tier_reasons"] = ["asked for"]
    card["flags"] = flags.for_mode(card["flags"], coaching.mode(inst.config))

    if card["mode"] == CATCH_UP:
        proposing = live if with_return is None else with_return
        card["catch_up"] = checkin_catchup.build(inst, card, window, end, _as_date(today), now, proposing,
                                                 list(workouts.values()))
        return card

    if card["mode"] == "deep":
        deep = [r for r in found if r.tier == "deep"]
        card["misses"] = misses(inst.root, deep[-1].date if deep else window.start, end, now, live)

    builtin = _builtin_fields(inst, card, _hevy_runs(inst, window) if live else [])
    builtin.update(replaced)
    numbered = []
    for field_id in FIELD_ORDER + tuple(extra_ids) + (HEVY_EDITS,):
        content = builtin.get(field_id)
        if content is None:
            continue
        numbered.append({"id": field_id, "n": len(numbered) + 1,
                         "label": content.label or LABELS.get(field_id) or field_id.replace("_", " ").capitalize(),
                         "prefill": content.prefill, "ask": content.ask})
    card["fields"] = numbered
    return card


def prepare(root, today, until=None, tier=None, now=None, *, deep_review_reasons=()):
    """The card for the window from the day after the last record to `until` (default today)."""
    if tier is not None and tier not in CARD_TIERS:
        raise ValueError(f"tier must be one of {', '.join(CARD_TIERS)}")
    return _build(root, today, until, tier, now, deep_review_reasons=deep_review_reasons)


def tag_gap(root, today, tag, now=None, dry_run=False):
    """Tag every untagged missed core session in the window since the last record with one miss tag (C36)."""
    card = _build(root, today, tier=CATCH_UP, now=now, parts=False, with_return=False)
    return checkin_catchup.tag_gap(root, card, tag, now, dry_run)


def _minutes_text(row):
    if row["minutes"] is None:
        return ""
    if row["cap_minutes"] is not None and row["minutes"] > row["cap_minutes"]:
        return f" ({row['minutes']} min, over the {row['cap_minutes']} min cap)"
    return f" ({row['minutes']} min)"


def _trained_text(row):
    text = f"{render.day_label(row['date'])} {row['title']} ✔"
    if row["moved"] and row["workout_date"]:
        text = f"{row['title']} ✔ on {render.day_label(row['workout_date'])} (planned {render.day_label(row['date'])})"
    if row["unlogged"]:
        return text + " (trained, not logged)"
    if row["tier"] == "optional":
        text += " (optional)"
    return text + _minutes_text(row)


def _sessions_field(inst, card):
    sessions = card["sessions"]
    source = "Hevy" if inst.config.hevy.enabled else "The log"
    trained = [_trained_text(r) for r in sessions["rows"] if r["status"] == "trained"]
    untagged = [r for r in sessions["rows"] if r["status"] == "missed" and r["tag"] == "untagged"]
    tagged = [r for r in sessions["rows"] if r["status"] == "missed" and r["tag"] != "untagged"]
    lines = [f"{source} shows: {', '.join(trained)}." if trained else "No planned session was logged."]
    if not sessions["rows"]:
        lines = ["No planned sessions in the window."]
    if tagged:
        lines.append("Missed: " + ", ".join(f"{render.day_label(r['date'])} {r['title']} ({r['tag']})"
                                            for r in tagged) + ".")
    if sessions["extra"]:
        lines.append("Also logged: " + ", ".join(f"{render.day_label(w['date'])} {w['title']}"
                                                 for w in sessions["extra"]) + ".")
    ask = None
    if untagged:
        lines.append("Not logged: " + ", ".join(f"{render.day_label(r['date'])} {r['title']}" for r in untagged) + ".")
        ask = f"Tag each miss: {MISS_TAG_TEXT}. Add anything you trained but didn't log."
    return checkin_parts.Field(prefill=" ".join(lines), ask=ask)


def _coach_led_field(inst, card):
    external = card["sessions"]["external"]
    if not external:
        return None
    extra = {w["date"]: w for w in card["sessions"]["extra"]}
    stated, asked = [], []
    for item in external:
        when = f"{item['title']} on {render.day_label(item['date'])}"
        if item["done"] is True:
            stated.append(f"{when}: done" + (f", {item['note']}" if item["note"] else "") + ".")
        elif item["done"] is False:
            stated.append(f"{when}: did not happen.")
        else:
            logged = extra.get(item["date"])
            if logged:
                stated.append(f"{when}: logged as {logged['title']}.")
            asked.append(f"What did {when} cover?")
    rotation = checkin_catchup.rotation_text(inst, _as_date(card["date"]))
    if rotation:
        stated.append(rotation)
    return checkin_parts.Field(prefill=" ".join(stated) or None, ask=" ".join(asked) or None)


def _runs_field(runs):
    if not runs:
        return checkin_parts.Field(ask="How many, and total distance?")
    metres = sum(a["distance_meters"] or 0 for a in runs)
    count = f"{len(runs)} run{'s' if len(runs) != 1 else ''}"
    logged = f"Hevy logged {count}" + (f", {_text(metres / 1000)} km" if metres else "") + "."
    return checkin_parts.Field(prefill=logged, ask="Any others: how many, and total distance?")


def _hevy_edits_field(card):
    edited = [h for h in card["hevy"] if h["state"] == "edited_in_app"]
    if not edited:
        return None
    facts = [f"{item['title']} was edited in the app since the last write: {item['summary']}." for item in edited]
    titles = " and ".join(item["title"] for item in edited)
    ask = f"Keep the in-app change to {titles} (it goes into the program) or replace it with the plan?"
    return checkin_parts.Field(prefill=" ".join(facts), ask=ask)


def _builtin_fields(inst, card, runs):
    rotation = None if card["sessions"]["external"] else checkin_catchup.rotation_text(inst, _as_date(card["date"]))
    return {
        "sessions": _sessions_field(inst, card),
        "coach_led": _coach_led_field(inst, card),
        "runs": _runs_field(runs),
        "sleep": checkin_parts.Field(ask=SLEEP_ASK),
        "niggles": checkin_parts.Field(ask="Anything new?"),
        "nutrition": checkin_parts.Field(ask=NUTRITION_ASK),
        "meal_plan": checkin_parts.Field(ask=MEAL_PLAN_ASK),
        "next_week": checkin_parts.Field(prefill=rotation, ask=NEXT_WEEK_ASK),
        HEVY_EDITS: _hevy_edits_field(card),
    }


def _e1rm_value(row):
    value = _text(row["e1rm"])
    value = f"{value}/hand" if row["load_mode"] == "per_hand_x2" else value
    return value + stats.basis_label(row)


def _result_text(row):
    if row["status"] == "hit":
        drift = f" (RPE {_signed(row['rpe_delta'])})" if row["rpe_delta"] else ""
        return f"{row['name']} hit{drift}"
    if row["status"] in ("under", "over"):
        return f"{row['name']} {row['status']}: {row['logged']} against {row['prescribed']}"
    return f"{row['name']} {row['status']}"


def _first_line(card):
    span = card["window"]
    reason = "; ".join(card["tier_reasons"])
    if not reason and card["days_since_last"] is not None:
        reason = f"{card['days_since_last']} days since the last check-in"
    head = f"Check-in for {render.day_label(span['start'])} – {render.day_label(span['end'])} ({card['mode']}"
    return head + (f" — {reason})." if reason else ").")


def _field_lines(field):
    body = " ".join(part for part in (field["prefill"], field["ask"]) if part)
    lines = body.split("\n")
    if len(lines) == 1:
        return [f"{field['n']}. {field['label']}. {lines[0]}".rstrip()]
    return [f"{field['n']}. {field['label']}."] + [f"   {line}" for line in lines]


def _e1rm_notes(card):
    notes = card.get("e1rm_notes")
    return ["", "e1RM notes:"] + [f"- {note}" for note in notes] if notes else []


def card_text(card):
    """The Sunday message: the week as the log shows it, then the numbered fields."""
    if card["mode"] == CATCH_UP:
        return "\n".join(checkin_catchup.text_lines(card, _first_line(card))) + "\n"
    lines = [_first_line(card)]
    results = {}
    for row in card["exercises"]:
        results.setdefault((row["date"], row["session_id"]), []).append(row)
    summary = []
    for row in card["sessions"]["rows"]:
        found = results.get((row["date"], row["session_id"]))
        if row["status"] != "trained" or not found:
            continue
        if row["unlogged"]:
            summary.append(f"- {render.day_label(row['date'])} {row['title']}: not logged, so no results")
        else:
            summary.append(f"- {render.day_label(row['date'])} {row['title']}: "
                           + " · ".join(_result_text(r) for r in found))
    if summary:
        lines += ["", "Results against the prescription:"] + summary
    if card["e1rm"]:
        lines += ["", "e1RM: " + " · ".join(f"{r['name']} {_e1rm_value(r)} ({_signed(r['delta'])})"
                                             for r in card["e1rm"])]
    lines += _e1rm_notes(card)
    if card["flags"]:
        lines += ["", "Flags:"] + [f"- `{f['code']}`: {f['message']}" for f in card["flags"]]
    loads = [h for h in card["hevy"] if h["state"] == "loads_edited"]
    if loads:
        lines += ["", "Hevy: loads edited in the app (the next pass overwrites them): "
                  + ", ".join(h["title"] for h in loads) + "."]
    if card["misses"]:
        tally = " · ".join(f"{tag} {n}" for tag, n in card["misses"]["by_tag"].items() if n)
        lines += ["", f"Misses since {card['misses']['since']}: {tally or 'none'}."]
    if card["facts"]:
        lines += [""] + [f"- {fact}" for fact in card["facts"]]
    lines.append("")
    for field in card["fields"]:
        lines += _field_lines(field)
    return "\n".join(lines) + "\n"


def _review_card(root, day, tier):
    card_tier = {"deep": "deep", "catch-up": CATCH_UP}.get(tier, "weekly")
    return _build(root, day, tier=card_tier, live=False, parts=False)


def _missed_line(card):
    missed = [r for r in card["sessions"]["rows"] if r["status"] == "missed"]
    return ", ".join(f"{render.day_label(r['date'])} {r['title']} ({r['tag']})" for r in missed) or "none"


def _status_text(row):
    if row["status"] == "missed":
        return f"missed ({row['tag']})"
    if row["unlogged"]:
        return "trained, not logged"
    if row["moved"] and row["workout_date"]:
        return f"trained on {render.day_label(row['workout_date'])}"
    return "trained"


def _region(card, record_date):
    if card["mode"] == CATCH_UP:
        lines = [render.begin_marker(REGION_KIND, record_date)] + checkin_catchup.region_lines(card)
        return "\n".join(lines + [render.end_marker(REGION_KIND, record_date)])
    sessions = card["sessions"]
    window = card["window"]
    header = (f"**Window:** {window['start']} → {window['end']} · **Sessions:** {sessions['trained_core']} of "
              f"{sessions['planned_core']} core")
    if sessions["optional_trained"]:
        header += f" · {sessions['optional_trained']} optional"
    lines = [render.begin_marker(REGION_KIND, record_date), header + f" · **Missed:** {_missed_line(card)}"]
    if sessions["rows"] or sessions["extra"]:
        lines += ["", _row(["Day", "Session", "Status", "Minutes"]), "| --- | --- | --- | --- |"]
        for row in sessions["rows"]:
            minutes = "" if row["minutes"] is None else str(row["minutes"])
            if minutes and row["cap_minutes"] is not None:
                minutes += f" (cap {row['cap_minutes']})"
            lines.append(_row([render.day_label(row["date"]), row["title"], _status_text(row), minutes]))
        for workout in sessions["extra"]:
            minutes = "" if workout["minutes"] is None else str(workout["minutes"])
            lines.append(_row([render.day_label(workout["date"]), workout["title"], "extra", minutes]))
    if sessions["external"]:
        items = []
        for item in sessions["external"]:
            state_text = {True: "done", False: "not done", None: "not recorded"}[item["done"]]
            items.append(f"{render.day_label(item['date'])} {item['title']} {state_text}"
                         + (f" ({item['note']})" if item["note"] else ""))
        lines += ["", "**Coach-led:** " + " · ".join(items)]
    if card["exercises"]:
        lines += ["", _row(["Day", "Exercise", "Prescribed", "Logged", "Result"]), "| --- | --- | --- | --- | --- |"]
        for row in card["exercises"]:
            result = row["status"]
            if row["rpe_delta"]:
                result += f", RPE {_signed(row['rpe_delta'])}"
            lines.append(_row([render.day_label(row["date"]), row["exercise_id"], row["prescribed"], row["logged"],
                               result]))
    if card["e1rm"]:
        lines += ["", _row(["Lift", "e1RM", "Change", "Date"]), "| --- | --- | --- | --- |"]
        for row in card["e1rm"]:
            lines.append(_row([row["exercise_id"], _e1rm_value(row), _signed(row["delta"]),
                               render.short_date(row["date"])]))
    lines += _e1rm_notes(card)
    if card["flags"]:
        lines += ["", "**Flags**", ""]
        for flag in card["flags"]:
            where = " / ".join(part for part in (flag["session_id"], flag["exercise_id"]) if part)
            lines.append(f"- {flag['severity']} · `{flag['code']}`" + (f" · {where}" if where else "")
                         + f": {flag['message']}")
    if card["misses"]:
        tally = " · ".join(f"{tag} {n}" for tag, n in card["misses"]["by_tag"].items() if n) or "none"
        by_session = ", ".join(f"{sid} {n}" for sid, n in card["misses"]["by_session"].items())
        lines += ["", f"**Misses since {card['misses']['since']}:** {tally}"
                  + (f" (by session: {by_session})" if by_session else "")]
    lines.append(render.end_marker(REGION_KIND, record_date))
    return "\n".join(lines)


def _record_path(day):
    return paths.CHECKINS_DIR / f"{day.isoformat()}.md"


def render_week_review(root, record_date):
    """The week-review region of the record dated `record_date` (C11). An older record's region is archive:
    it comes back exactly as the file holds it, so a later history correction never fails an old record."""
    root, day = Path(root), _as_date(record_date)
    found = reviews(root)
    record = next((r for r in found if r.date == day), None)
    if record is not None and found[-1].date != day:
        text = (root / record.path).read_text(encoding="utf-8")
        for region_id, start, end in render.find_regions(text, REGION_KIND):
            if region_id == day.isoformat():
                return text[start:end]
        raise ValueError(f"{record.path.as_posix()} holds no {REGION_KIND} {day.isoformat()} region")
    tier = record.tier if record else "weekly"
    return _region(_review_card(root, day, tier), day.isoformat())


def _details(overlay_region):
    return "\n".join(["<details>", "<summary>Prescription</summary>", "", overlay_region, "", "</details>"])


def _collapsed(text, start, end):
    return any(block.start() <= start and end <= block.end() for block in _DETAILS.finditer(text))


def skeleton_text(day, tier, review, overlay_region=None):
    sections = [f"# Check-in — {day.isoformat()} ({tier})", "", "## Week in review", review, "",
                "## Coach's read", "", "## Decisions", ""]
    if tier == "deep":
        sections += ["## Block planning", ""]
    sections += [render.WEEK_AHEAD_HEADING, ""]
    if overlay_region is not None:
        sections += [_details(overlay_region), ""]
    return "\n".join(sections)


def unsynced_in_window(root, day, now=None):
    """Workouts the record's window would include once `history sync` has run."""
    inst = _Instance.load(root)
    found = [r for r in reviews(inst.root) if r.date < day]
    window = _window(inst, found, day)
    return [w for w in history.workouts(inst.root, window.start, window.end, include_unsynced=True, now=now)
            if w["unsynced"]]


def skeleton(root, record_date, tier=None, overlay_id=None, refresh=False, dry_run=False, now=None):
    """Write `check-ins/<date>.md`, or with refresh re-render only its regions. Returns what was (or would be) done."""
    root, day = Path(root), _as_date(record_date)
    rel = _record_path(day)
    path = root / rel
    if tier is not None and tier not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)}")
    if overlay_id is not None:
        overlay_region = render.render_overlay(root, overlay_id)
    rendered = []
    if refresh:
        if not path.is_file():
            raise ValidationError(f"{rel.as_posix()} does not exist; write it with python3 -m coach checkin skeleton "
                                  f"--date {day.isoformat()} first")
        before = path.read_text(encoding="utf-8")
        text = before
        title = parse_title(before.split("\n", 1)[0])
        if title is None or title[0] != day:
            raise ValidationError(f"{rel.as_posix()} has an invalid record title; fix it before refreshing")
        tier = (title[1] or "deep") if tier is None else tier
        found_reviews = reviews(root)
        newest = bool(found_reviews and found_reviews[-1].date == day)
        for region_id, start, end in reversed(render.find_regions(text, REGION_KIND)):
            if region_id == day.isoformat() and newest:
                text = text[:start] + _region(_review_card(root, day, tier), region_id) + text[end:]
                rendered.append(f"{REGION_KIND} {region_id}")
        for region_id, start, end in reversed(render.find_regions(text, render.REGION_KIND)):
            text = text[:start] + render.render_overlay(root, region_id) + text[end:]
            rendered.append(f"{render.REGION_KIND} {region_id}")
        if overlay_id is not None:
            found = {r: (start, end) for r, start, end in render.find_regions(text, render.REGION_KIND)}
            if overlay_id not in found:
                text = render.splice_region(text, render.REGION_KIND, overlay_id, _details(overlay_region))
                rendered.append(f"{render.REGION_KIND} {overlay_id}")
            elif not _collapsed(text, *found[overlay_id]):
                start, end = found[overlay_id]
                text = text[:start] + _details(text[start:end]) + text[end:]
        changed = text != before
    else:
        if path.exists():
            raise ValidationError(f"{rel.as_posix()} already exists; re-render its regions with --refresh")
        if tier is None:
            mode = _build(root, day, now=now, live=False)["mode"]
            tier = TIER_OF_MODE.get(mode, mode)
        review = _region(_review_card(root, day, tier), day.isoformat())
        text = skeleton_text(day, tier, review, overlay_region if overlay_id is not None else None)
        rendered.append(f"{REGION_KIND} {day.isoformat()}")
        if overlay_id is not None:
            rendered.append(f"{render.REGION_KIND} {overlay_id}")
        changed = True
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {"path": rel.as_posix(), "tier": tier, "refresh": refresh, "regions": sorted(rendered),
            "written": changed and not dry_run, "dry_run": dry_run, "text": text}


def prose_words(text):
    """Words in a record outside its title, rendered regions and `<details>` blocks."""
    body = text.split("\n", 1)[1] if "\n" in text else ""
    body = _DETAILS.sub(" ", _ANY_REGION.sub(" ", body))
    return len(_WORD.findall(body))


def has_review(text):
    try:
        return bool(render.find_regions(text, REGION_KIND))
    except ValueError:
        return True
