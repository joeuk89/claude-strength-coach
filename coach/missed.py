"""Missed-day rules: match a missed session to the program's rule and apply it as a mid-week overlay (contract C37).

Matching (`match`) and application (`apply_rule`) stay separate so a caller
can apply a rule it builds itself (a priority lift's floor dose), after the
program's rules as a fallback, alone or on top of a program fold.
`plan` is read-only; `apply` writes the miss, the overlay and the record
lines once the athlete has said "go".
"""

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from coach import checkin, dates, flags, history, jsonio, overlay, pages, paths, program, render, stats, structure
from coach import units, validity
from coach import config as config_module
from coach.errors import RefusedError, ValidationError
from coach.library import Library
from coach.validate import validate as validate_schema

NEXT = "next"
DEFAULT_FOLD_SETS = 2
SCOPE = "one_week"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
RECORD_HEADING = "## Mid-week"
RECORD_SOURCE = "missed apply"
FALLBACK = "python3 -m coach propose week --kind midweek"
FALLBACK_WORDS = f"reprogram the rest of the week with {FALLBACK} and a coach's brief"


class Unmatched(Exception):
    """A rule that cannot apply to this miss; the message says why in a few words."""


def _day(value):
    return dates.parse_date(value) if isinstance(value, str) else value


def _weekday_word(weekday):
    return weekday.capitalize()


def _today(config, now):
    zone_name = config.athlete.timezone
    return now.astimezone(dates.zone(zone_name) if zone_name else None).date()


def rules(root):
    return program.load(root)["missed_day_rules"]


class _Names:
    """Session titles from the program and exercise names from the library, ids when either is missing."""

    def __init__(self, program_doc=None, library=None):
        self.sessions = {s["id"]: s["title"] for s in (program_doc or {}).get("sessions", [])}
        self.library = library

    def session(self, session_id):
        return self.sessions.get(session_id, session_id)

    def exercise(self, exercise_id):
        entry = self.library.get(exercise_id) if self.library else None
        return entry["name"] if entry else exercise_id


def _names_for(root, program_doc=None, library=None):
    if root is not None:
        if program_doc is None and program.exists(root):
            program_doc = program.load(root)
        if library is None:
            library = Library.load(root)
    return _Names(program_doc, library)


def _sets_words(count):
    return f"{count} set" if count == 1 else f"{count} sets"


def _and(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def describe(rule, root=None, program_doc=None, library=None):
    """The rule in plain words: its own `text` when set, else written from its action."""
    if rule.get("text"):
        return rule["text"]
    names = _names_for(root, program_doc, library)
    lead = f"Miss {names.session(rule['session_id'])}"
    days_left = (rule.get("when") or {}).get("min_days_left")
    if days_left is not None and days_left > 1:
        lead += f" with {days_left} or more days left in the week"
    action = rule["action"]
    kind = action["kind"]
    if kind == "fold":
        parts = []
        for item in action["exercises"]:
            words = f"{_sets_words(item.get('sets', DEFAULT_FOLD_SETS))} of {names.exercise(item['exercise_id'])}"
            if item.get("rpe") is not None:
                words += f" at RPE {units.json_number(item['rpe'])} at most"
            parts.append(words)
        into = "session" if action["into"] == NEXT else names.session(action["into"])
        verb = "goes" if len(parts) == 1 and parts[0].startswith("1 set ") else "go"
        return f"{lead}: {_and(parts)} {verb} into the next {into}, this week only."
    if kind == "shift":
        days = ", else ".join(_weekday_word(day) for day in action["to_weekdays"])
        tail = ", whichever is free first" if len(action["to_weekdays"]) > 1 else " if it is free"
        return f"{lead}: it moves to {days}{tail}, this week only."
    if kind == "skip":
        return f"{lead}: skip it; the rest of the week stays as planned."
    return f"{lead}: tell the coach, and the rest of the week is reprogrammed."


def _days_left(doc, day):
    return (dates.parse_date(doc["span"]["end"]) - _day(day)).days


def _holds(when, doc, day):
    minimum = (when or {}).get("min_days_left")
    return minimum is None or _days_left(doc, day) >= minimum


def match(root, session_id, day, doc=None, program_doc=None):
    """The first rule for `session_id` whose condition holds on `day`, or None.

    `doc` is the overlay in force on the day (looked up when not given).
    A matched `manual` rule still leaves the miss unmatched; `plan` says so.
    """
    if doc is None:
        picked = overlay.in_force(root, day)
        if picked is None:
            return None
        doc = picked[0]
    found = (program_doc or program.load(root))["missed_day_rules"]
    return next((rule for rule in found if rule["session_id"] == session_id and _holds(rule["when"], doc, day)),
                None)


def _missed_session(doc, session_id, day):
    session = next((s for s in doc["sessions"] if s["session_id"] == session_id and s["date"] == _day(day).isoformat()),
                   None)
    if session is None:
        raise ValidationError(f"{session_id} is not planned on {_day(day).isoformat()} in overlay {doc['id']}")
    return session


def _later_sessions(doc, day):
    return [s for s in doc["sessions"] if s["date"] > _day(day).isoformat()]


def _fold(doc, missed, day, rule, names, today):
    """(sessions after the miss with the fold applied, flags) for a `fold` rule."""
    action = rule["action"]
    later = copy.deepcopy(_later_sessions(doc, day))
    targets = [s for s in later
               if action["into"] in (NEXT, s["session_id"]) and s["date"] >= today.isoformat()]
    if not targets:
        into = "session" if action["into"] == NEXT else names.session(action["into"])
        raise Unmatched(f"no later {into} from today to the end of the overlay's span")
    target = min(targets, key=lambda s: s["date"])
    found_flags = []
    for item in action["exercises"]:
        line = next((e for e in missed["exercises"] if e["exercise_id"] == item["exercise_id"]), None)
        if line is None:
            raise Unmatched(f"{missed['title']} has no {names.exercise(item['exercise_id'])} line this week")
        working = [s for s in line["sets"] if overlay.is_working(s)]
        if not working:
            raise Unmatched(f"{names.exercise(item['exercise_id'])} has no working sets to fold")
        sets = copy.deepcopy(working[:min(item.get("sets", DEFAULT_FOLD_SETS), len(working))])
        cap = item.get("rpe")
        if cap is not None:
            for set_ in sets:
                set_["rpe"] = cap if set_.get("rpe") is None else min(set_["rpe"], cap)
        folded = dict(copy.deepcopy(line), sets=sets, superset_id=None, override=None, change=None, fold={
            "rule_id": rule["id"], "from_session_id": missed["session_id"], "from_date": missed["date"],
            "scope": SCOPE})
        target["exercises"].append(folded)
        found_flags += [dict(f, session_id=target["session_id"]) for f in doc["flags"]
                        if f["session_id"] == missed["session_id"] and f["exercise_id"] == line["exercise_id"]]
        found_flags.append(flags.make("missed_day_rule", session_id=target["session_id"],
                                      exercise_id=line["exercise_id"], message=(
            f"Rule {rule['id']}: {_sets_words(len(sets))} of {names.exercise(line['exercise_id'])} from "
            f"{render.day_label(missed['date'])} {missed['title']}, this week only.")))
    return later, found_flags


def _shift(doc, missed, day, rule, config, today):
    """(sessions after the miss with the missed session moved, flags) for a `shift` rule."""
    day = _day(day)
    end = dates.parse_date(doc["span"]["end"])
    taken = {s["date"] for s in doc["sessions"]}
    available = config.athlete.available_days
    for weekday in rule["action"]["to_weekdays"]:
        candidate = day + timedelta(days=(WEEKDAYS.index(weekday) - day.weekday()) % 7 or 7)
        if (candidate < today or candidate > end or candidate.isoformat() in taken
                or (available and weekday not in available)):
            continue
        moved = dict(copy.deepcopy(missed), date=candidate.isoformat(), moved_from=missed["date"])
        later = copy.deepcopy(_later_sessions(doc, day)) + [moved]
        later.sort(key=lambda s: s["date"])
        flag = flags.make("missed_day_rule", session_id=missed["session_id"], message=(
            f"Rule {rule['id']}: {missed['title']} moved from {render.day_label(missed['date'])} to "
            f"{render.day_label(candidate)}, this week only."))
        return later, [flag]
    days = ", ".join(_weekday_word(w) for w in rule["action"]["to_weekdays"])
    raise Unmatched(f"none of {days} is free after the miss, from today to the end of the overlay's span")


def _draft_set(set_):
    drafted = {key: value for key, value in set_.items() if key != "load"}
    drafted["load"] = history.coaching_number(set_.get("load"))
    return drafted


def _draft_line(line):
    drafted = {key: value for key, value in line.items() if key not in ("sets", "override")}
    drafted["sets"] = [_draft_set(s) for s in line["sets"]]
    if line.get("override"):
        drafted["override"] = {"reason": line["override"]["reason"],
                               "proposed_sets": [_draft_set(s) for s in line["override"]["proposed_sets"]]}
    else:
        drafted["override"] = None
    return drafted


def _draft(doc, sessions, extra_flags):
    ids = {s["session_id"] for s in sessions}
    carried = [f for f in doc["flags"] if f["session_id"] in ids and f["code"] not in validity.owned_codes()]
    kept = []
    for flag in carried + extra_flags:
        if not any(flag == other for other in kept):
            kept.append(flag)
    return {
        "schema_version": overlay.current_version(), "kind": "midweek",
        "span": {"start": min(s["date"] for s in sessions), "end": doc["span"]["end"]},
        "supersedes": doc["id"], "focus": doc["focus"], "flags": kept,
        "sessions": [dict(s, exercises=[_draft_line(line) for line in s["exercises"]]) for s in sessions],
    }


def apply_rule(root, doc, session_id, day, rule, now=None, config=None, library=None):
    """The mid-week overlay (built, unwritten, flags checked) for `rule` applied to a miss; None for `skip`.

    Takes any rule object, including one no program holds. Raises Unmatched
    when the rule cannot apply: `manual`, a fold with no later target, a
    shift with no free day. A day before today is never a target or free.
    """
    _missed_session(doc, session_id, day)
    kind = rule["action"]["kind"]
    if kind == "manual":
        raise Unmatched(f"rule {rule['id']} is manual")
    if kind == "skip":
        return None
    return _build(root, doc, session_id, day, [rule], now, config, library)


def _build(root, doc, session_id, day, rules, now, config, library):
    """The mid-week overlay for `fold` and `shift` rules applied in turn, each to the week the one before left."""
    root = Path(root)
    config = config or config_module.load(root)
    now = now or datetime.now(timezone.utc)
    today = _today(config, now)
    names = _names_for(root, library=library)
    missed = _missed_session(doc, session_id, day)
    sessions, extra = None, []
    for rule in rules:
        source = doc if sessions is None else dict(doc, sessions=[missed] + sessions)
        if rule["action"]["kind"] == "fold":
            sessions, found = _fold(source, missed, day, rule, names, today)
        else:
            sessions, found = _shift(source, missed, day, rule, config, today)
        extra += found
    if not sessions:
        raise Unmatched("no session is left in the overlay's span")
    built = overlay.build(_draft(doc, sessions, extra), config, root=root, now=now)
    built["flags"] = validity.merge_flags(built, validity.check_overlay(root, built))
    return built


def _left_out(floor_rule, rule, applied):
    """The part of the priority floor rule the program's rule leaves out of the week, or None.

    A shift that applied takes every lift with the session; a fold that applied covers the lifts it lists.
    """
    if floor_rule is None:
        return None
    if not applied or rule["action"]["kind"] == "skip":
        return floor_rule
    if rule["action"]["kind"] == "shift":
        return None
    folded = {item["exercise_id"] for item in rule["action"]["exercises"]}
    left = [item for item in floor_rule["action"]["exercises"] if item["exercise_id"] not in folded]
    if not left:
        return None
    return dict(floor_rule, id=structure.floor_rule_id([item["exercise_id"] for item in left]),
                action=dict(floor_rule["action"], exercises=left))


def _floor_missed(rule, missed, day, reason, names):
    """priority_exposures_missed for each lift a priority floor rule could not fold anywhere this week."""
    return [flags.make("priority_exposures_missed", session_id=missed["session_id"], exercise_id=item["exercise_id"],
                       message=f"{names.exercise(item['exercise_id'])} missed its exposure in {missed['title']} on "
                               f"{render.day_label(day)} and no floor dose of {_sets_words(item['sets'])} replaced it "
                               f"({reason}); the next week's own session carries it")
            for item in rule["action"]["exercises"]]


def _sets_text(line, with_rpe, show_hevy):
    if with_rpe and show_hevy:
        return render.target_line(line)[len("Target: "):]
    text = pages.sets_text(line, show_hevy)
    rpes = {s.get("rpe") for s in line["sets"] if overlay.is_working(s)}
    if with_rpe and len(rpes) == 1 and None not in rpes:
        text += f" @ RPE {units.json_number(rpes.pop())}"
    return text


def _folded_lines(draft):
    for session in draft["sessions"]:
        lines = [line for line in session["exercises"] if line.get("fold")]
        if lines:
            yield session, lines


def _change_text(draft, names, with_rpe, show_hevy=True):
    if draft is None:
        return None
    parts = []
    for session, lines in _folded_lines(draft):
        words = _and([f"{names.exercise(line['exercise_id'])} {_sets_text(line, with_rpe, show_hevy)}" for line in lines])
        parts.append(f"{words} added to {render.day_label(session['date'])} {session['title']}, this week only")
    for session in draft["sessions"]:
        if session.get("moved_from"):
            parts.append(f"{session['title']} moved from {render.day_label(session['moved_from'])} to "
                         f"{render.day_label(session['date'])}, this week only")
    return "; ".join(parts)


def _hevy_titles(draft):
    titles = []
    for session in draft["sessions"]:
        if session["title"] not in titles:
            titles.append(session["title"])
    return titles


def write_line(config, draft):
    """R-03's one approval line: what "go" writes."""
    if not config.hevy.enabled:
        return 'Reply "go" to train this. Nothing goes to Hevy (no Hevy).'
    if draft is None:
        return 'Reply "go" to train this. Nothing goes to Hevy (no change).'
    return f'Reply "go" to train this and write: {", ".join(_hevy_titles(draft))} (Hevy).'


def _check_text(draft):
    counts = {}
    for flag in draft["flags"]:
        if flag["severity"] in ("block", "warn") and not flag["resolved"]:
            counts.setdefault(flag["severity"], []).append(flag["code"])
    if not counts:
        return "Prescription check: no block or warn flags."
    parts = [f"{len(codes)} {severity} ({', '.join(sorted(set(codes)))})"
             for severity, codes in sorted(counts.items())]
    return f"Prescription check: {'; '.join(parts)}."


def plan(root, session_id, day, now=None):
    """What the matching rule would do to the rest of the week; writes nothing."""
    root = Path(root)
    day = _day(day)
    now = now or datetime.now(timezone.utc)
    config = config_module.load(root)
    program_doc = program.load(root)
    library = Library.load(root)
    names = _Names(program_doc, library)
    picked = overlay.in_force(root, day)
    if picked is None:
        raise ValidationError(f"No overlay is in force on {day}, so nothing was planned that day")
    doc = picked[0]
    missed = _missed_session(doc, session_id, day)
    missed_text = f"Missed {render.day_label(day)} {missed['title']}"
    found = {"session_id": session_id, "date": day.isoformat(), "title": missed["title"], "overlay_id": doc["id"],
             "matched": False, "rule": None, "floor_rule": None, "action": None, "description": None, "reason": None,
             "summary": [], "write_line": None, "draft": None, "flags": []}

    rule = match(root, session_id, day, doc, program_doc)
    draft, reason = None, None
    try:
        if rule is None:
            raise Unmatched("no rule names this session with its condition met")
        draft = apply_rule(root, doc, session_id, day, rule, now, config, library)
    except Unmatched as why:
        reason = why

    floor_rule = _left_out(structure.priority_floor(root, session_id, day, doc, program_doc), rule, reason is None)
    floor_flags, added = [], None
    if floor_rule is not None:
        try:
            if draft is not None:
                draft, added = _build(root, doc, session_id, day, [rule, floor_rule], now, config, library), floor_rule
            else:
                draft = apply_rule(root, doc, session_id, day, floor_rule, now, config, library)
                rule, reason = floor_rule, None
        except Unmatched as why:
            floor_flags = _floor_missed(floor_rule, missed, day, why, names)

    if rule is not None:
        found.update(rule=rule, action=rule["action"]["kind"],
                     description=describe(rule, program_doc=program_doc, library=library))
    if reason is not None:
        found["reason"] = str(reason)
        found["flags"] = floor_flags + [flags.make("missed_rule_unmatched", session_id=session_id, message=(
            f"No missed-day rule applies to {missed['title']} on {render.day_label(day)} ({reason}); "
            f"{FALLBACK_WORDS}."))]
        found["summary"] = [f"{missed_text}; no missed-day rule applies ({reason}).",
                            f"Next: {FALLBACK_WORDS}."]
        return found

    found.update(matched=True, draft=draft, floor_rule=added, write_line=write_line(config, draft), flags=floor_flags)
    with_floor = f", with the priority floor {added['id']}" if added else ""
    summary = [f"{missed_text}; rule {rule['id']} applies ({rule['action']['kind']}){with_floor}."]
    if draft is None:
        summary.append("Nothing else changes this week; only the miss is recorded.")
    else:
        summary.append(_change_text(draft, names, with_rpe=True, show_hevy=config.hevy.enabled) + ".")
        summary.append(f"Mid-week overlay {draft['id']}: {render.day_label(draft['span']['start'])} to "
                       f"{render.day_label(draft['span']['end'])}, over {doc['id']} on those days.")
        summary.append(_check_text(draft))
    found["summary"] = summary
    return found


def missed_sessions(root, today, day=None, now=None):
    """Planned core sessions dated before `day` (default today) with no workout and no `trained_unlogged` note."""
    root = Path(root)
    day = _day(day) or today
    last = min(day, today) - timedelta(days=1)
    picked = overlay.in_force(root, day) or overlay.in_force(root, last)
    if picked is None:
        return []
    start = dates.parse_date(picked[0]["span"]["start"])
    if last < start:
        return []
    program_doc = program.load(root) if program.exists(root) else None
    optional = {s["id"] for s in (program_doc or {}).get("sessions", []) if s["tier"] == "optional"}
    found = stats.adherence(root, span=(start, last), include_unsynced=True, today=last, now=now)
    misses = history.annotations(root, "miss")
    rows = []
    for row in found["sessions"]:
        if row["status"] != "missed" or row["session_id"] in optional:
            continue
        recorded = [a for a in misses if a["session_id"] == row["session_id"] and a["date"] == row["date"]]
        rows.append({"date": row["date"], "session_id": row["session_id"], "title": row["title"],
                     "overlay_id": row["overlay_id"], "recorded": bool(recorded),
                     "tag": recorded[-1].get("tag") if recorded else None})
    return rows


def _annotation(root, session_id, day, tag, now):
    doc = history.read_annotations(root)
    annotation = {"id": history.next_annotation_id(doc), "kind": "miss", "date": day.isoformat(),
                  "session_id": session_id, "tag": tag, "source": RECORD_SOURCE, "reason": None,
                  "created_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    errors = validate_schema({"schema_version": 1, "annotations": [annotation]},
                             jsonio.load_schema(history.ANNOTATIONS_SCHEMA))
    problems = [e.message for e in errors] + history.Checker(root).problems(annotation, doc["annotations"])
    if problems:
        raise ValidationError(f"the miss annotation is not valid: {problems[0]}")
    doc["annotations"].append(annotation)
    return doc, annotation


def record_lines(found, tag, names, config):
    rule, draft = found["rule"], found["draft"]
    rule_words = f"Rules {rule['id']} and {found['floor_rule']['id']}" if found["floor_rule"] else f"Rule {rule['id']}"
    lines = [f"- Missed {render.day_label(found['date'])} {found['title']} ({tag or 'untagged'}).",
             f"- {rule_words}: {_change_text(draft, names, with_rpe=False, show_hevy=config.hevy.enabled) or 'nothing changes this week'}."]
    if draft is None:
        lines.append("- No overlay; nothing goes to Hevy.")
    elif config.hevy.enabled:
        lines.append(f"- Overlay {draft['id']}; Hevy: {', '.join(_hevy_titles(draft))}.")
    else:
        lines.append(f"- Overlay {draft['id']}; no Hevy.")
    return lines


def with_record_lines(text, lines):
    """`text` with `lines` added at the end of its `## Mid-week` section, which goes at the end when absent."""
    body = text.rstrip("\n").split("\n")
    if RECORD_HEADING not in body:
        return "\n".join(body + ["", RECORD_HEADING, ""] + lines) + "\n"
    start = body.index(RECORD_HEADING) + 1
    end = next((i for i in range(start, len(body)) if body[i].startswith("## ")), len(body))
    while end > start and not body[end - 1].strip():
        end -= 1
    if end == start:
        body[start:start] = [""]
        end += 1
    return "\n".join(body[:end] + lines + body[end:]) + "\n"


def apply(root, session_id, day, tag=None, dry_run=False, now=None):
    """Write the miss, the mid-week overlay (unapproved) and three lines in the newest record."""
    root = Path(root)
    day = _day(day)
    now = now or datetime.now(timezone.utc)
    if tag is not None and tag not in history.MISS_TAGS:
        raise ValidationError(f"tag {tag!r} is not a miss tag; use one of {', '.join(history.MISS_TAGS)}")
    recorded = next((a for a in history.annotations(root, "miss")
                     if a["session_id"] == session_id and a["date"] == day.isoformat()), None)
    if recorded is not None:
        raise RefusedError(f"The miss of {session_id} on {day} is already recorded (annotation {recorded['id']}); "
                           f"nothing was written")
    found = plan(root, session_id, day, now)
    if not found["matched"]:
        raise RefusedError(f"No missed-day rule applies to {found['title']} on {day} ({found['reason']}); "
                           f"{FALLBACK_WORDS}")
    config = config_module.load(root)
    names = _names_for(root)
    annotations_doc, annotation = _annotation(root, session_id, day, tag, now)
    lines = record_lines(found, tag, names, config)
    found_records = checkin.records(root)
    record = found_records[-1].path.as_posix() if found_records else None
    draft = found["draft"]
    overlay_path = overlay.path_for(root, draft["id"]) if draft else None

    jsonio.write_doc(root / paths.ANNOTATIONS, annotations_doc, dry_run)
    if draft is not None:
        jsonio.write_doc(overlay_path, draft, dry_run)
    if record and not dry_run:
        path = root / record
        path.write_text(with_record_lines(path.read_text(encoding="utf-8"), lines), encoding="utf-8")
    return dict(found, annotation=annotation, overlay_id=draft["id"] if draft else None,
                overlay_path=overlay_path.relative_to(root).as_posix() if overlay_path else None,
                record=record, record_lines=lines, written=not dry_run, dry_run=dry_run)
