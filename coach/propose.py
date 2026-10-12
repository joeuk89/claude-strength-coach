"""The proposal pipeline behind `coach propose` (contract C24).

`propose week` turns the program, its state, the history and the decisions
into an editable draft overlay: each slot's scheme proposes, or a standing
override keeps its sets, then the core decays stale lines, applies the
week's transform, the load constraints, caps and rounding. Loads stay coaching numbers
until `coach.overlay.build` makes load objects through `coach.units`.
`propose finalize` turns the edited draft into the overlay R-13 approves.
"""

import copy
import json
import re
from dataclasses import replace
from datetime import timedelta, timezone
from pathlib import Path
from typing import NamedTuple

from coach import constraints as constraints_module
from coach import dates, decisions, flags, followups, history, jsonio, niggles, overlay, paths, patterns, plugins
from coach import capacity, cardio, conditioning, external, program, research, statusdays, weekflags
from coach import state as state_module
from coach import stats, units, validity
from coach.checks.instance import cap_for
from coach.errors import ConfigError, RefusedError, UsageError, ValidationError
from coach.library import Library, e1rm_supported
from coach.load_statements import PER_HAND_X2, bare_figures, bare_message
from coach.loads import AvailableLoads, available_loads
from coach.plugins import base

KINDS = ("weekly", "midweek", "deload")
DECAY_AFTER_DAYS = validity.RETURN_BANDS[0].upper
STALL_EXPOSURES = 3
_SET_SPEC = re.compile(r"^\s*(\d+)\s*[x×]\s*(\d+)(?:\s*-\s*(\d+))?\s*(\+)?\s*(s)?\s*(?:@\s*(\d+(?:\.\d+)?))?\s*"
                       r"(?:rpe\s*(\d+(?:\.\d+)?))?\s*$", re.IGNORECASE)


def proposal_paths(root, proposal_id):
    """(draft, untouched original, run facts) for a proposal id."""
    directory = Path(root) / paths.PROPOSALS_DIR
    return (directory / f"{proposal_id}.json", directory / f"{proposal_id}.proposed.json",
            directory / f"{proposal_id}.meta.json")


def _read(path, what):
    if not path.is_file():
        raise ValidationError(f"No {what}: {path} does not exist; run python3 -m coach propose week first")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def load_proposal(root, proposal_id):
    if not isinstance(proposal_id, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+", proposal_id):
        raise ValidationError(f"{proposal_id!r} is not a proposal id (YYYY-MM-DD-<kind>)")
    draft_path, proposed_path, meta_path = proposal_paths(root, proposal_id)
    return (_read(draft_path, f"proposal {proposal_id}"), _read(proposed_path, f"original of proposal {proposal_id}"),
            _read(meta_path, f"run facts of proposal {proposal_id}"))


def _write_proposal(root, proposal_id, draft, proposed, meta):
    draft_path, proposed_path, meta_path = proposal_paths(root, proposal_id)
    for path, doc in ((draft_path, draft), (proposed_path, proposed), (meta_path, meta)):
        if doc is not None:
            jsonio.write_doc(path, doc, False)


def _relative(root, path):
    return Path(path).relative_to(root).as_posix()


def _timestamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _same(a, b):
    return a is not None and b is not None and abs(a - b) < 1e-9


def _load_text(value, mode, unit):
    if mode not in units.LOADED_MODES:
        return None
    if value is None:
        return "load to set"
    return units.format_load(units.make_load(value, mode, unit))


def sets_text(sets, mode, unit, with_load=True):
    """The working sets in words, loads through units.format_load: "3×8 @ 24/hand (Hevy: 48) RPE 8"."""
    groups = []
    for s in sets:
        if not s.working:
            continue
        reps = (f"{s.rep_range[0]}–{s.rep_range[1]}" if s.rep_range else
                str(s.reps) if s.reps is not None else
                f"{s.duration_seconds} s" if s.duration_seconds else
                f"{units.json_number(s.distance_meters)} m" if s.distance_meters is not None else "?")
        words = f"{reps}+" if s.rep_out else reps
        load = _load_text(s.load, mode, unit) if with_load else None
        if load:
            words += f" @ {load}"
        if s.rpe is not None:
            words += f" {'stop at ' if s.rep_out else ''}RPE {units.json_number(s.rpe)}"
        if groups and groups[-1][1] == words:
            groups[-1][0] += 1
        else:
            groups.append([1, words])
    return ", ".join(f"{count}×{words}" for count, words in groups) or "no working sets"


def parse_sets(spec):
    """Working sets from a SPEC like "3x5@100 rpe7, 1x5@90", a range "3x8-10@25 rpe8", seconds "2x35s rpe7", or a
    rep-out set "1x5+@145" (at least 5 reps, then as many as possible before its RPE cap, base.REP_OUT_RPE_CAP when
    no rpe is given)."""
    found, timed = [], set()
    for part in spec.split(","):
        match = _SET_SPEC.fullmatch(part)
        if not match:
            raise UsageError(f"--sets: {part.strip()!r} is not COUNTxREPS[-REPS][+][@LOAD][ rpeN] or "
                             f"COUNTxSECONDSs[ rpeN], e.g. 3x5@100 rpe7, 1x5+@120 or 2x35s rpe7")
        count, reps, top, plus, seconds, load, rpe = match.groups()
        rep_range = (int(reps), int(top)) if top else None
        if plus and (rep_range or seconds):
            raise UsageError(f"--sets: {part.strip()!r} puts + on a {'range' if rep_range else 'timed set'}; a "
                             f"rep-out set takes fixed reps, e.g. 1x5+@120")
        if seconds and (rep_range or load):
            raise UsageError(f"--sets: {part.strip()!r} gives a timed set a {'range' if rep_range else 'load'}; "
                             f"a timed set takes one duration and no load, e.g. 2x35s rpe7")
        if rep_range and rep_range[0] > rep_range[1]:
            raise UsageError(f"--sets: {part.strip()!r} has a range that ends below its start")
        timed.add(bool(seconds))
        rpe = units.json_number(float(rpe)) if rpe else None
        if seconds:
            found += [base.SetSpec(type="normal", duration_seconds=int(reps), rpe=rpe)] * int(count)
            continue
        if plus and rpe is None:
            rpe = base.REP_OUT_RPE_CAP
        found += [base.SetSpec(type="normal", reps=None if rep_range else int(reps), rep_range=rep_range, rpe=rpe,
                               load=units.json_number(float(load)) if load else None,
                               rep_out=bool(plus))] * int(count)
    if len(timed) > 1:
        raise UsageError(f"--sets: {spec.strip()!r} mixes reps and seconds; give one or the other")
    return tuple(found)


def _metric_problem(exercise_id, mode, sets):
    """Why `sets` do not fit a line of `mode`: seconds go on a duration line only, and nothing on a distance line."""
    if mode == "distance":
        return f"{exercise_id} is a distance line, and --sets takes reps or seconds, not a distance"
    timed = any(s.duration_seconds is not None for s in sets if s.working)
    if mode == "duration" and not timed:
        return f'{exercise_id} is a duration line, so --sets takes seconds, e.g. "2x35s rpe7"'
    if mode != "duration" and timed:
        return f"{exercise_id} is {mode}, not a duration line, so --sets takes reps, not seconds"
    return None


class Run:
    """One propose run: everything read once and shared by every line."""

    def __init__(self, root, config, today, now):
        self.root = Path(root)
        self.config = config
        self.unit = config.athlete.units
        self.today = today
        self.now = now
        self.program = program.load(root)
        problems = program.validate(self.program, config, Library.load(root), root)
        if problems:
            raise ValidationError(f"{paths.PROGRAM} is not valid ({len(problems)} problem(s)); "
                                  "run python3 -m coach program validate",
                                  details=[e.to_json() for e in problems])
        self.state = state_module.load(root)
        self.registry = plugins.load(root)
        self.library = Library.load(root)
        self.overlays = overlay.list(root)
        self.by_id = {doc["id"]: doc for doc in self.overlays}
        self.decisions = decisions.load(root)
        self.sessions = {s["id"]: s for s in self.program["sessions"]}
        self._exposures = None
        self._series = None
        self._research = None
        self._recovery = None

    def recovery(self):
        """What each approved overlay line and logged exposure was for (`coach.capacity`)."""
        if self._recovery is None:
            self._recovery = capacity.Context(self.root)
        return self._recovery

    def exposures(self):
        """Every exposure as a plugin sees it, newest first."""
        if self._exposures is None:
            workout_overlays = {w["workout_id"]: w["overlay_id"] for w in history.workouts(self.root)}
            found = [self._exposure(e, workout_overlays.get(e["workout_id"])) for e in history.all_exposures(self.root)]
            self._exposures = sorted(found, key=lambda e: (e.date, e.workout_id), reverse=True)
        return self._exposures

    def _exposure(self, raw, overlay_id):
        doc = self.by_id.get(overlay_id)
        prescribed, decayed = self._prescribed(doc, raw["session_id"], raw["exercise_id"], raw["date"])
        sets = tuple(base.LoggedSet(index=s["index"], type=s["type"], reps=s["reps"], rpe=s["rpe"],
                                    load=history.coaching_number(s["load"]),
                                    duration_seconds=s.get("duration_seconds"),
                                    distance_meters=s.get("distance_meters"))
                     for s in raw["sets"] if not s.get("discounted"))
        week_kind = doc["kind"] if doc else None
        if self.recovery().for_exposure(dict(raw, overlay_id=overlay_id))["kind"] == "return":
            week_kind = "return"
        return base.Exposure(
            date=dates.parse_date(raw["date"]), workout_id=raw["workout_id"], session_id=raw["session_id"],
            exercise_id=raw["exercise_id"], load_mode=raw["load_mode"], sets=sets, suspect=raw["suspect"],
            excluded=raw["excluded"], prescribed=prescribed, week_kind=week_kind, decayed=decayed,
        )

    def _prescribed(self, doc, session_id, exercise_id, day):
        """(the working sets the overlay prescribed, whether that line was a return week's), or ((), False)."""
        if doc is not None:
            sessions = [s for s in doc["sessions"] if s["session_id"] == session_id]
            if sessions:
                target = dates.parse_date(day)
                session = min(sessions, key=lambda s: abs((dates.parse_date(s["date"]) - target).days))
                line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)
                if line is not None:
                    sets = tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load")))
                                 for s in line["sets"] if overlay.is_working(s))
                    return sets, bool((line.get("provenance") or {}).get("decay"))
        return (), False

    def slot(self, session_id, exercise_id):
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)

    def exposures_of(self, exercise_id, before, session_id=None, load_mode=None):
        return tuple(e for e in self.exposures() if e.exercise_id == exercise_id and e.date < before
                     and (session_id is None or e.session_id == session_id)
                     and (load_mode is None or e.load_mode == load_mode))

    def model_evidence(self, exercise_id, day):
        if self._series is None:
            self._series = stats.e1rm_series(self.root)
        return stats.capacity_evidence(self._series, exercise_id, day, validity.E1RM_WINDOW_DAYS)

    def e1rm(self, exercise_id, day):
        evidence = self.model_evidence(exercise_id, day)
        return evidence["estimate"]["e1rm"] if evidence["estimate"] else None

    def last_prescription(self, session_id, exercise_id, ordinary=False):
        """This slot's line in the newest approved overlay that has it; `recovery` names deload, light or return
        work, else None, and `ordinary` skips such lines."""
        return last_prescription(self.overlays, session_id, exercise_id, kind_of=self.recovery().line_kind,
                                 ordinary=ordinary)

    def agreed_override(self, session_id, exercise_id, day):
        """The override on this slot's line in the approved overlay in force on `day`, or None (C25).

        It is carried while no decision for it has expired or been withdrawn; a deload overlay's sets are already
        cut, so only a deload run carries them.
        """
        approved = [doc for doc in self.overlays if overlay.is_approved(doc)]
        found = overlay.pick_in_force(approved, day)
        if found is None:
            return None
        doc = found[0]
        sessions = [s for s in doc["sessions"] if s["session_id"] == session_id]
        if not sessions:
            return None
        session = min(sessions, key=lambda s: (abs((dates.parse_date(s["date"]) - day).days), s["date"]))
        line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id and not e.get("fold")
                     and e.get("override")), None)
        if line is None:
            return None
        made = [d for d in self.decisions["decisions"] if d["kind"] == "override"
                and d["scope"] == {"session_id": session_id, "exercise_id": exercise_id}
                and d["reason"] == line["override"]["reason"]]
        if made and not any(decisions.effective_status(d, day) == "active" for d in made):
            return None
        return {"overlay_id": doc["id"], "kind": doc["kind"], "reason": line["override"]["reason"],
                "sets": _coaching_sets(line["sets"]), "decayed": bool((line.get("provenance") or {}).get("decay"))}

    def increment(self, exercise_id, location):
        return stats.load_increment(self.library, self.config, exercise_id, location) or 0

    def research(self):
        """(notes by id, expired areas, local updates), or None when the instance has no research notes."""
        if self._research is None:
            if not (self.root / paths.RESEARCH_DIR).is_dir():
                self._research = False
            else:
                notes = research.load_all(self.root)[0]
                self._research = ({note.id: note for note in notes}, research.expired_areas(notes, self.today),
                                  research.local_updates_from(notes, self.today))
        return self._research or None


def _coaching_sets(overlay_sets):
    return tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load"))) for s in overlay_sets)


def last_prescription(overlays, session_id, exercise_id, exclude=None, kind_of=None, ordinary=False):
    """This slot's line in the newest approved overlay that has it, loads as coaching numbers: the prior agreed
    prescription a line's `change` is measured from.

    Lines a missed-day rule folded in (`fold`, C37) last one week, so they never stand for the slot. `exclude` names
    an overlay id to pass over, the proposal's own. `kind_of(doc, session, line)` names a line's recovery kind, and
    `ordinary` skips lines that are not `normal`.
    """
    approved = sorted((doc for doc in overlays if overlay.is_approved(doc) and doc["id"] != exclude),
                      key=lambda d: (d["created_at"], d["id"]), reverse=True)
    for doc in approved:
        sessions = sorted((s for s in doc["sessions"] if s["session_id"] == session_id),
                          key=lambda s: s["date"], reverse=True)
        for session in sessions:
            line = next((e for e in session["exercises"]
                         if e["exercise_id"] == exercise_id and not e.get("fold")), None)
            if line is None:
                continue
            kind = kind_of(doc, session, line) if kind_of else "normal"
            if ordinary and kind != "normal":
                continue
            return {"overlay_id": doc["id"], "session_id": session_id, "date": session["date"],
                    "exercise_id": exercise_id, "load_mode": line["load_mode"],
                    "sets": _coaching_sets(line["sets"]), "override": line["override"],
                    "recovery": None if kind == "normal" else kind}
    return None


def settle(state_doc, by_id):
    """(state with pending scheme state promoted or dropped, report rows) (C23)."""
    report = []
    settled = {}
    for slot, entry in state_doc["scheme_state"].items():
        pending = entry.get("pending")
        if pending:
            doc = by_id.get(pending["overlay_id"])
            if doc is not None and overlay.is_approved(doc):
                entry = dict(entry, data=pending["data"], pending=None)
                report.append({"slot": slot, "overlay_id": pending["overlay_id"], "action": "promoted"})
            else:
                entry = dict(entry, pending=None)
                report.append({"slot": slot, "overlay_id": pending["overlay_id"], "action": "dropped"})
        settled[slot] = entry
    return dict(state_doc, scheme_state=settled), report


def resolve_span(config, today, week=None, span=None, kind="weekly"):
    """The span a run covers: --span, else --week, else the week holding tomorrow; midweek starts today at the earliest."""
    week_starts = config.athlete.week_starts
    if span:
        try:
            start, end = (dates.parse_date(part) for part in span.split(".."))
            found = dates.Span(start, end)
        except ValueError as exc:
            raise UsageError(f"--span: {exc}; give START..END as YYYY-MM-DD..YYYY-MM-DD") from None
    else:
        try:
            found = dates.parse_week(week, week_starts) if week else dates.week_span(today + timedelta(days=1),
                                                                                     week_starts)
        except ValueError as exc:
            raise UsageError(f"--week: {exc}") from None
    if kind == "midweek" and found.start < today <= found.end and not span:
        found = dates.Span(today, found.end)
    return found


def _schedule_context(run, span):
    rotation = run.state["rotation"]
    return base.ScheduleContext(
        today=run.today, span_start=span.start, span_end=span.end, week_starts=run.config.athlete.week_starts,
        params=plugins.merged_params(run.registry.get("schedule", run.program["schedule"]["rule"]),
                                     run.program["schedule"]["params"])[0],
        rotation=dict(rotation), sessions=tuple(run.program["sessions"]),
        external_sessions=tuple(run.program["external_sessions"]),
    )


def plan_schedule(run, span):
    """The schedule rule's plan for a span: active program sessions only."""
    rule = run.program["schedule"]["rule"]
    plugin = run.registry.get("schedule", rule)
    found = plugin.module.plan(_schedule_context(run, span))
    sessions = [(day, sid) for day, sid in found.sessions
                if span.contains(day) and run.sessions.get(sid, {}).get("status") == "active"]
    return base.SchedulePlan(sessions=tuple(sorted(sessions)), rotation=found.rotation, flags=tuple(found.flags))


def plan_json(run, span, found):
    return {
        "rule": run.program["schedule"]["rule"], "span": span.to_json(),
        "sessions": [{"date": day.isoformat(), "session_id": sid, "title": run.sessions[sid]["title"]}
                     for day, sid in found.sessions],
        "rotation": found.rotation, "flags": list(found.flags),
    }


def read_plan(run, path, span):
    """A SchedulePlan from a JSON file (`schedule plan` output, or one R-22 or R-30b wrote); rotation unchanged."""
    raw = _read(Path(path), "plan file")
    sessions = raw.get("sessions") if isinstance(raw, dict) else None
    if not isinstance(sessions, list):
        raise ValidationError(f"{path}: a plan file holds a sessions list")
    found = []
    for index, item in enumerate(sessions):
        try:
            day = dates.parse_date(item["date"])
            session_id = item["session_id"]
        except (KeyError, TypeError, ValueError):
            raise ValidationError(f"{path}: $.sessions[{index}] needs a date and a session_id") from None
        if session_id not in run.sessions:
            raise ValidationError(f"{path}: $.sessions[{index}].session_id names no program session {session_id}")
        if not span.contains(day):
            raise ValidationError(f"{path}: $.sessions[{index}].date {day} is outside the span {span.start}..{span.end}")
        found.append((day, session_id))
    week_flags = [f for f in raw.get("flags", []) if isinstance(f, dict) and flags.is_known(f.get("code"))]
    return base.SchedulePlan(sessions=tuple(sorted(found)), rotation=None, flags=tuple(week_flags))


def _illness(run, first):
    """Why the first session back is capped at RPE 7, or None (C22 illness rule)."""
    last = history.last_lifting_date(run.root, first)
    if last is None or (first - last).days < 2:
        return None
    gap_start, gap_end = last + timedelta(days=1), first - timedelta(days=1)
    for annotation in history.annotations(run.root, "miss"):
        if annotation.get("tag") == "ill" and gap_start.isoformat() <= annotation["date"] <= gap_end.isoformat():
            return f"an ill miss on {annotation['date']}"
    return "an ill status day" if statusdays.ill_in(run.root, dates.Span(gap_start, gap_end)) else None


def _without_ill_days(run, span, found):
    """(plan without the sessions an ill status day covers, a flag per session left out) (C22 illness rule).

    Raises RefusedError when illness covers every session: nothing is trainable until the athlete is better.
    """
    ill = statusdays.ill_days(run.root, span)
    kept = tuple((day, sid) for day, sid in found.sessions if day not in ill)
    if not kept:
        rows = ", ".join(dict.fromkeys(ill[day] for day, _ in found.sessions))
        raise RefusedError(
            f"An ill status day ({rows}) covers every session in {span.start}..{span.end}, so none is planned: "
            f"training waits until the athlete has been {validity.SYMPTOM_FREE_HOURS} hours symptom-free. End the "
            "row with python3 -m coach status-days end <id> --date <last ill day>, then propose again; the first "
            f"session back asks for that confirmation and caps every set at RPE {validity.ILLNESS_RPE_CAP}.")
    left_out = [flags.make("ill_day_excluded", message=(
        f"{run.sessions[sid]['title']} ({sid}) on {day} is left out: ill status day {ill[day]} covers it"))
        for day, sid in found.sessions if day in ill]
    return replace(found, sessions=kept), left_out


def _scheme_state(plugin, stored, slot_key, scheme_name, line_flag):
    """(state the scheme sees, flags) from the stored entry (C23: INITIAL when absent or after a scheme change)."""
    if stored is None:
        return plugins.initial_state(plugin), []
    if stored["scheme"] not in (None, scheme_name):
        return plugins.initial_state(plugin), [line_flag(
            "scheme_reset", f"{slot_key} changed scheme from {stored['scheme']} to {scheme_name}; its state restarted")]
    if plugins.state_errors(plugin, stored["data"]):
        if stored["scheme"] is None:
            return plugins.initial_state(plugin), []
        return plugins.initial_state(plugin), [line_flag(
            "scheme_reset", f"{slot_key}'s stored state no longer fits {scheme_name}; its state restarted")]
    return dict(stored["data"]), []


def _hardest_load(sets, direction):
    loads = [s.load for s in sets if s.working and s.load is not None]
    return (max(loads) if direction > 0 else min(loads)) if loads else None


def _gain(older, newer, direction=None):
    """Progress over comparable work, or None when the logged metrics cannot be compared."""
    if older.load_mode != newer.load_mode:
        return None
    before, after = base.working(older.sets), base.working(newer.sets)
    if not before or len(before) != len(after):
        return None
    mode = newer.load_mode
    direction = direction if direction is not None else (-1 if mode == "assisted" else 1)
    metric = {"duration": "duration_seconds", "distance": "distance_meters"}.get(mode, "reps")
    if any(getattr(s, metric) is None for s in (*before, *after)):
        return None
    if mode in units.LOADED_MODES:
        if any(s.load is None for s in (*before, *after)):
            return None
        old_load, new_load = _hardest_load(before, direction), _hardest_load(after, direction)
        if (new_load - old_load) * direction > 1e-9:
            return True
        if not _same(old_load, new_load):
            return False
        old_work = sum(getattr(s, metric) for s in before if _same(s.load, old_load))
        new_work = sum(getattr(s, metric) for s in after if _same(s.load, new_load))
    else:
        old_work, new_work = (sum(getattr(s, metric) for s in sets) for sets in (before, after))
    if new_work > old_work:
        return True
    matched = all((a.load, a.reps, a.duration_seconds, a.distance_meters) ==
                  (b.load, b.reps, b.duration_seconds, b.distance_meters) for a, b in zip(before, after))
    effort_known = all(s.rpe is not None for s in (*before, *after))
    return (matched and effort_known and all(b.rpe <= a.rpe for a, b in zip(before, after))
            and any(b.rpe < a.rpe for a, b in zip(before, after)))


def _stalled(exposures, direction=None):
    usable = [e for e in exposures if e.usable and e.week_kind not in ("deload", "return")][:STALL_EXPOSURES]
    if len(usable) < STALL_EXPOSURES:
        return None
    newest, middle, oldest = usable
    gains = (_gain(oldest, middle, direction), _gain(middle, newest, direction))
    if any(gain is None or gain for gain in gains):
        return None
    return [e.date.isoformat() for e in reversed(usable)]


class LineResult:
    def __init__(self, draft_line, flags, state, scheme):
        self.draft_line = draft_line
        self.flags = flags
        self.state = state
        self.scheme = scheme


def _clip(sets, ceiling, direction=1):
    changed, found = [], []
    for index, s in enumerate(sets):
        if s.load is not None and (s.load > ceiling + 1e-9 if direction > 0 else s.load < ceiling - 1e-9):
            s = replace(s, load=ceiling)
            changed.append(index)
        found.append(s)
    return tuple(found), changed


def apply_constraints(sets, active, newest_load, direction):
    """(sets, clipped indices, words) after the slot's load constraints (C26)."""
    clipped, words = set(), []
    for constraint in active:
        kind, value = constraint["kind"], constraint["value"]
        if kind == "rpe_cap":
            capped = base.rpe_capped(sets, value)
            if capped != sets:
                words.append(f"{constraint['source']} RPE cap {units.json_number(value)} ({constraint['reason']})")
            sets = capped
        elif kind == "load_cap":
            sets, changed = _clip(sets, value)
            if changed:
                clipped.update(changed)
                words.append(f"{constraint['source']} load cap {units.json_number(value)} ({constraint['reason']})")
        elif kind == "no_added_load" and newest_load is not None:
            sets, changed = _clip(sets, newest_load, direction)
            if changed:
                clipped.update(changed)
                words.append(f"{constraint['source']} no added load ({constraint['reason']})")
    return sets, clipped, words


def propose_line(run, session, day, exercise, ctx_extra):
    """One program slot through the pipeline: scheme or standing override, decay, transform, constraints, illness cap,
    caps, rounding."""
    session_id, exercise_id = session["id"], exercise["exercise_id"]
    slot_key = f"{session_id}/{exercise_id}"
    mode = exercise["load_mode"]
    location = session["location"]
    entry = run.library.get(exercise_id) or {}
    scheme_name = exercise["scheme"]["name"]
    plugin = run.registry.get("scheme", scheme_name)
    params, _ = plugins.merged_params(plugin, exercise["scheme"]["params"])

    def line_flag(code, message, severity=None):
        return flags.make(code, severity, session_id=session_id, exercise_id=exercise_id, message=message)

    state, line_flags = _scheme_state(plugin, ctx_extra["states"].get(slot_key), slot_key, scheme_name, line_flag)
    exposures = run.exposures_of(exercise_id, day, session_id=session_id, load_mode=mode)
    active = constraints_module.active(run.root, session_id, exercise_id, day)
    days_off = validity.days_off(run.root, exercise_id, day, ctx_extra["first_day"]) or 0
    info = _exercise_info(run, session, exercise)
    ctx = base.SchemeContext(
        today=run.today, session_date=day, unit=run.unit, week_kind=ctx_extra["kind"], exercise=info,
        slot=base.SlotInfo(session_id=session_id, sets=tuple(exercise["sets"]), rest_seconds=exercise["rest_seconds"],
                           cues=exercise["cues"], constraints=tuple(exercise["constraints"]),
                           start_load=exercise["start_load"]),
        params=params, state=state, exposures=exposures, e1rm=run.e1rm(exercise_id, day),
        last_prescription=run.last_prescription(session_id, exercise_id),
        last_override=decisions.last_override(run.decisions, session_id, exercise_id, day),
        days_off=days_off, constraints=tuple(active), scheme=scheme_name,
        scheme_deload=getattr(plugin.module, "deload", None),
        last_ordinary_prescription=run.last_prescription(session_id, exercise_id, ordinary=True),
    )
    proposal = plugin.module.propose(ctx)
    _check_proposal(plugin, proposal)
    scheme_sets = proposal.sets
    cut_from = _cut_from(proposal)
    clauses = [proposal.rationale.rstrip(". ")]
    scheme_clause = clauses[0]
    scheme_rep_out = any(s.rep_out for s in proposal.sets)
    evidence = run.model_evidence(exercise_id, day)
    if evidence["reason"] == "over_rep_cap":
        clauses.append(evidence["message"].rstrip(". "))
    adjusted = []
    line_flags += list(proposal.flags)
    source = proposal.derived_from

    decay = None
    if days_off > DECAY_AFTER_DAYS:
        band = validity.band_for(days_off)
        before = proposal.rationale
        proposal = plugin.module.decay(ctx, proposal, days_off)
        if proposal.rationale != before:
            clauses[0] = proposal.rationale.rstrip(". ")
        decay = {"days_off": days_off, "band": band.id, "load_factor": band.load_factor, "set_delta": band.set_delta,
                 "rpe_cap": band.rpe_cap}
        adjusted.append(f"return band {band.id} after {days_off} days off")
        load_words = "assistance held" if info.load_direction < 0 else f"loads × {band.load_factor}"
        line_flags.append(line_flag("return_week", f"{days_off} days off: return band {band.id} ({load_words}, "
                                                   f"set change {band.set_delta}"
                                                   f"{f', RPE cap {band.rpe_cap}' if band.rpe_cap else ''})"))

    transform = ctx_extra["transform"]

    def transformed(found, scheme_deload):
        plugin_t, transform_params = transform
        return plugin_t.module.apply(replace(ctx, params=transform_params, scheme_deload=scheme_deload), found)

    if transform is not None:
        before = proposal.rationale
        proposal = transformed(proposal, ctx.scheme_deload)
        if proposal.rationale != before:
            clauses[0] = proposal.rationale.rstrip(". ")
        adjusted.append(f"the {transform[0].name} deload")
    newest = base.newest(exposures)
    first_after_illness = ctx_extra["illness"] is not None and day == ctx_extra["first_day"]
    try:
        cap, cap_source = cap_for(run.config, exercise_id, mode, location) if mode in units.LOADED_MODES else (None, None)
    except ConfigError:
        cap, cap_source = None, None
    ceilings = [c["value"] for c in active if c["kind"] == "load_cap"]
    if cap is not None:
        ceilings.append(cap)
    floor = None
    if newest is not None and newest.top_load is not None and any(c["kind"] == "no_added_load" for c in active):
        if info.load_direction > 0:
            ceilings.append(newest.top_load)
        else:
            floor = newest.top_load
    rungs = tuple(r["load"] for r in params["rungs"] if r.get("load") is not None) \
        if scheme_name == "assistance_ladder" else ()
    rounding = _Rounding(
        available_loads(run.library, run.config, exercise_id, mode, location) if mode in units.LOADED_MODES else None,
        min(ceilings, default=None), floor, source.top_load if source is not None else None, info.load_direction,
        rungs)

    def limited(sets, round_down, load_cut, cut_from):
        """Constraints, the illness cap, caps and rounding: what every load passes after its scheme."""
        sets, clipped, words = apply_constraints(sets, active, newest.top_load if newest else None,
                                                 info.load_direction)
        if first_after_illness:
            sets = base.rpe_capped(sets, validity.ILLNESS_RPE_CAP)
        if cap is not None:
            sets, changed = _clip(sets, cap)
            if changed:
                clipped.update(changed)
                per_hand = "/hand" if mode in units.PER_HAND_MODES else ""
                words.append(f"{cap_source} caps the load at {units.json_number(cap)}{per_hand}")
        sets, kit_changes, off_ladder = _rounded(sets, clipped, round_down, cut_from if load_cut else None, rounding)
        words += [f"no ladder rung fits within it, so the line leaves the ladder at {_load_text(v, mode, run.unit)}"
                  for v in off_ladder]
        return sets, words, kit_changes

    sets, constraint_words, kit_changes = limited(proposal.sets, proposal.round_down, proposal.load_cut, cut_from)
    cut = _load_cut(cut_from, proposal, scheme_sets, sets, kit_changes, rounding) if proposal.load_cut else None
    if cut is not None:
        kit_changes.pop(cut["target"], None)
    estimate = evidence["estimate"]
    if (proposal.model_hold and source is not None and decay is None and transform is None and cut is None
            and mode in validity.FEASIBILITY_MODES and estimate is not None):
        held = _model_hold(proposal, sets, estimate, limited)
        if held is not None:
            (sets, constraint_words, kit_changes), over, verdict = held
            clauses.append(
                f"but {_load_text(over.load, mode, run.unit)} × "
                f"{validity.reps_words(verdict.reps, validity.rep_targets(over.reps, over.rep_range))} implies "
                f"{validity.implied_words(verdict.implied)} at {validity.estimate_words(estimate)}, so "
                f"{_load_text(base.top_load(sets), mode, run.unit)}, the heaviest load logged on "
                f"{source.date.isoformat()} that the e1RM model accepts, holds")
    if first_after_illness:
        adjusted.append(f"an RPE {validity.ILLNESS_RPE_CAP} cap on the first session after illness")
    if constraint_words:
        adjusted += constraint_words
    if adjusted:
        clauses.append(f"adjusted for {', '.join(adjusted)}: {sets_text(sets, mode, run.unit)}")
    clauses += _kit_words(kit_changes, mode, run.unit)
    if cut is not None:
        clauses.append(_cut_words(cut, mode, run.unit))

    override = None
    kept_from = _kept_override(run, ctx, session_id, exercise_id, day, transform)
    if kept_from is not None:
        kept = kept_from["sets"]
        chosen = base.Proposal(sets=kept, rationale="kept", derived_from=source, state={})
        chosen_cut_from = _cut_from(chosen)
        kept_adjusted = []
        if decay is not None and kept_from["decay"]:
            chosen = plugin.module.decay(ctx, chosen, days_off)
            kept_adjusted.append(f"return band {decay['band']} after {days_off} days off")
        if transform is not None and kept_from["transform"]:
            # A scheme's own deload rebuilds the scheme's prescription and would drop the coach's sets.
            chosen = transformed(chosen, None)
            kept_adjusted.append(f"the {transform[0].name} deload")
        chosen_sets, kept_words, kept_kit_changes = limited(chosen.sets, chosen.round_down, chosen.load_cut,
                                                            chosen_cut_from)
        cut = (_load_cut(chosen_cut_from, chosen, kept, chosen_sets, kept_kit_changes, rounding)
               if chosen.load_cut else None)
        if cut is not None:
            kept_kit_changes.pop(cut["target"], None)
        if first_after_illness:
            kept_adjusted.append(f"an RPE {validity.ILLNESS_RPE_CAP} cap on the first session after illness")
        kept_adjusted += kept_words
        override = {"reason": kept_from["reason"], "proposed_sets": [s.to_dict() for s in sets]}
        scheme_text = sets_text(sets, mode, run.unit)
        kept_text = sets_text(chosen_sets, mode, run.unit)
        if kept_adjusted:
            kept_text = (f"{sets_text(kept, mode, run.unit)}, adjusted for {', '.join(kept_adjusted)}: "
                         f"{kept_text},")
        clauses = [f"{kept_from['words']} ({kept_from['reason'].rstrip('. ')}) kept as "
                   f"{kept_text} instead of the scheme's {scheme_text}"]
        clauses += _kit_words(kept_kit_changes, mode, run.unit)
        if cut is not None:
            clauses.append(_cut_words(cut, mode, run.unit))
        code, message = kept_from["flag"]
        line_flags.append(line_flag(code, f"{message}; the scheme proposed {scheme_text}"))
        sets, constraint_words = chosen_sets, kept_words
    if cut is not None and cut["held"]:
        line_flags.append(line_flag("load_cut_held", _held_cut_words(cut, info.name, mode, run.unit),
                                    "info" if cut["other_cuts"] and not cut["rose"] else "warn"))

    if constraint_words:
        line_flags.append(line_flag("constraint_applied", "; ".join(constraint_words)))

    rep_out_words = _rep_out_words(sets)
    if rep_out_words:
        clauses.insert(1, rep_out_words)
    elif scheme_rep_out and override is None and clauses[0] == scheme_clause:
        clauses.insert(1, "no + set this week")

    line_flags += _core_flags(ctx, entry, exercise, sets, exposures, active, line_flag, mode)
    evidence_clause, evidence_flags = _evidence(run, plugin, transform, line_flag)
    line_flags += evidence_flags
    if evidence_clause:
        clauses.append(evidence_clause)

    rationale = "; ".join(c for c in clauses if c) + "."
    rationale = rationale[0].upper() + rationale[1:]
    final_note = getattr(plugin.module, "final_note", None)
    target_note = final_note(ctx, proposal, sets) if final_note is not None else proposal.target_note
    previous = ctx.last_prescription
    draft_line = {
        "exercise_id": exercise_id,
        "hevy_template_id": _template_id(entry),
        "load_mode": mode, "rest_seconds": exercise["rest_seconds"], "superset_id": exercise["superset_id"],
        "cues": exercise["cues"], "focus": proposal.focus, "target_note": target_note,
        "change": change_text(previous["sets"] if previous else None, sets, mode, run.unit),
        "override": override,
        "provenance": {"scheme": scheme_name, "derived_from": source.ref() if source else None, "inferred": False,
                       "decay": decay, "rationale": rationale},
        "sets": [s.to_dict() for s in sets],
    }
    return LineResult(draft_line, line_flags, proposal.state, scheme_name)


def _rep_out_words(sets):
    """What the line's rep-out sets ask for, from the final sets, so caps a week or a constraint lowered are named."""
    found = []
    for s in base.working(sets):
        if not s.rep_out:
            continue
        cap = "" if s.rpe is None else f" before RPE {units.json_number(s.rpe)}"
        heuristic = " (a coaching heuristic)" if s.rpe == base.REP_OUT_RPE_CAP else ""
        words = f"the {s.reps}+ set takes as many reps as the athlete can{cap}{heuristic}"
        if words not in found:
            found.append(words)
    return ", ".join(found)


def _kept_override(run, ctx, session_id, exercise_id, day, transform):
    """The override a line keeps instead of its scheme's sets, or None (C25).

    An active standing decision wins. Otherwise the line keeps the override approved for this session in the overlay
    in force, a one-week override included, with the decay and transform its sets have not had yet.
    """
    last = ctx.last_override
    if last is not None and last["standing"]:
        return {"sets": tuple(base.SetSpec.from_dict(s) for s in last["chosen_sets"]), "reason": last["reason"],
                "decay": True, "transform": True, "words": f"standing override until {last['until']}",
                "flag": ("override_standing", f"Standing override {last['id']} until {last['until']} kept")}
    agreed = run.agreed_override(session_id, exercise_id, day)
    if agreed is None or (agreed["kind"] == "deload" and transform is None):
        return None
    return {"sets": agreed["sets"], "reason": agreed["reason"], "decay": not agreed["decayed"],
            "transform": agreed["kind"] != "deload", "words": f"the override approved in {agreed['overlay_id']}",
            "flag": ("override_kept", f"The override approved in {agreed['overlay_id']} kept")}


def _exercise_info(run, session, exercise):
    exercise_id, mode = exercise["exercise_id"], exercise["load_mode"]
    entry = run.library.get(exercise_id) or {}
    return base.ExerciseInfo(
        id=exercise_id, name=entry.get("name", exercise_id), pattern=entry.get("pattern"),
        muscles=entry.get("muscles", {}), equipment=entry.get("equipment"), load_mode=mode,
        increment=run.increment(exercise_id, session["location"]), is_compound=patterns.is_compound(entry),
        load_direction=-1 if mode == "assisted" else 1, e1rm_supported=e1rm_supported(exercise_id),
        is_isolation=patterns.is_isolation(entry),
    )


def _template_id(entry):
    ids = entry.get("hevy_template_ids") or []
    return entry.get("hevy_template_id") or (ids[0] if len(ids) == 1 else None)


def propose_conditioning(run, session, day, ctx_extra, repeat=False):
    """A conditioning session's lines from its density scheme; every load holds as written (C51).

    A deload run holds the scheme where it is. `repeat` marks a later date
    of a session this run already proposed: its state is already judged and
    decayed, so it holds, and a layoff never steps the scheme back twice.
    """
    judge = ctx_extra["kind"] != "deload" and not repeat
    session_id, scheme = session["id"], session["scheme"]
    plugin = run.registry.get("conditioning", scheme["name"])
    params, _ = plugins.merged_params(plugin, scheme["params"])
    key = conditioning.state_key(session_id)

    def session_flag(code, message, severity=None):
        return flags.make(code, severity, session_id=session_id, message=message)

    state, found = _scheme_state(plugin, ctx_extra["states"].get(key), key, scheme["name"], session_flag)
    last = conditioning.last_prescription(run.overlays, session_id)
    days_off = conditioning.days_off(run.root, run.config, day)
    ctx = base.ConditioningContext(
        today=run.today, session_date=day, session_id=session_id,
        exercises=tuple(_exercise_info(run, session, e) for e in session["exercises"]), params=params, state=state,
        bouts=conditioning.bouts(run.root, run.config, last, run.today) if judge else (),
        last_prescription=last, days_off=days_off,
    )
    proposal = plugin.module.propose(ctx)
    _check_conditioning(plugin, proposal, session)
    if days_off > DECAY_AFTER_DAYS and not repeat:
        proposal = plugin.module.decay(ctx, proposal, days_off)
        _check_conditioning(plugin, proposal, session)
        found.append(session_flag("return_week", (
            f"{days_off} days since the last logged conditioning session (return band "
            f"{validity.band_for(days_off).id}): {scheme['name']} steps back")))
    found += list(proposal.flags)
    rationale = proposal.rationale.rstrip(". ")
    rationale = rationale[0].upper() + rationale[1:] + "."
    lines = []
    for index, exercise in enumerate(session["exercises"]):
        line, line_flags = _conditioning_line(run, session, day, exercise, proposal, index == 0, rationale, ctx_extra)
        lines.append(line)
        found += line_flags
    return LineResult(lines, found, proposal.state, scheme["name"])


def _conditioning_line(run, session, day, exercise, proposal, first, rationale, ctx_extra):
    session_id, exercise_id, mode = session["id"], exercise["exercise_id"], exercise["load_mode"]
    entry = run.library.get(exercise_id) or {}
    previous = run.last_prescription(session_id, exercise_id)
    load = None
    if mode in units.LOADED_MODES:
        load = base.top_load(previous["sets"]) if previous else None
        load = exercise["start_load"] if load is None else load
    sets = tuple(replace(s, load=load) for s in proposal.lines[exercise_id])
    active = constraints_module.active(run.root, session_id, exercise_id, day)
    sets, clipped, words = apply_constraints(sets, active, load, -1 if mode == "assisted" else 1)
    if ctx_extra["illness"] is not None and day == ctx_extra["first_day"]:
        sets = base.rpe_capped(sets, validity.ILLNESS_RPE_CAP)
    try:
        cap, cap_source = cap_for(run.config, exercise_id, mode, session["location"]) \
            if mode in units.LOADED_MODES else (None, None)
    except ConfigError:
        cap, cap_source = None, None
    if cap is not None:
        sets, changed = _clip(sets, cap)
        if changed:
            words.append(f"{cap_source} caps the load at {units.json_number(cap)}")

    def line_flag(code, message):
        return flags.make(code, session_id=session_id, exercise_id=exercise_id, message=message)

    found = [line_flag("constraint_applied", "; ".join(words))] if words else []
    if mode in units.LOADED_MODES and load is None:
        found.append(line_flag("no_data", f"{entry.get('name', exercise_id)}: no approved load and no start load, so "
                                          "the load is left for the coach to set"))
    line = {
        "exercise_id": exercise_id, "hevy_template_id": _template_id(entry), "load_mode": mode,
        "rest_seconds": exercise["rest_seconds"], "superset_id": exercise["superset_id"], "cues": exercise["cues"],
        "focus": proposal.focus if first else None, "target_note": None,
        "change": change_text(previous["sets"] if previous else None, sets, mode, run.unit), "override": None,
        "provenance": {"scheme": session["scheme"]["name"], "derived_from": None, "inferred": False, "decay": None,
                       "rationale": rationale},
        "sets": [s.to_dict() for s in sets],
    }
    return line, found


def _check_conditioning(plugin, proposal, session):
    if not isinstance(proposal, base.ConditioningProposal):
        raise ValidationError(f"Density scheme {plugin.name} returned {type(proposal).__name__}, not a "
                              "ConditioningProposal")
    errors = plugins.state_errors(plugin, proposal.state)
    if errors:
        raise ValidationError(f"Density scheme {plugin.name} returned state that fails its STATE schema",
                              details=[e.to_json() for e in errors])
    wanted = [e["exercise_id"] for e in session["exercises"]]
    if sorted(proposal.lines) != sorted(wanted) or not all(proposal.lines[i] for i in wanted):
        raise ValidationError(f"Density scheme {plugin.name} must give sets for exactly {', '.join(wanted)}")
    if not proposal.rationale or not proposal.rationale.strip():
        raise ValidationError(f"Density scheme {plugin.name} gave no rationale")


def _check_proposal(plugin, proposal):
    if not isinstance(proposal, base.Proposal):
        raise ValidationError(f"Scheme {plugin.name} returned {type(proposal).__name__}, not a Proposal")
    errors = plugins.state_errors(plugin, proposal.state)
    if errors:
        raise ValidationError(f"Scheme {plugin.name} returned state that fails its STATE schema",
                              details=[e.to_json() for e in errors])
    source = proposal.derived_from
    if source is not None and not source.usable:
        raise ValidationError(f"Scheme {plugin.name} derived a line from {source.date} ({source.workout_id}), an "
                              "excluded or suspect exposure; derive from coach.plugins.base.baseline() instead")
    if not proposal.rationale or not proposal.rationale.strip():
        raise ValidationError(f"Scheme {plugin.name} gave no rationale")


class _Rounding(NamedTuple):
    available: AvailableLoads | None
    cap: float | None
    floor: float | None
    derived: float | None
    load_direction: int
    rungs: tuple[float, ...]


def _rounded(sets, clipped, round_down, cut_from, rounding):
    """(sets, {requested: selected}, off-ladder loads): each load snapped to the kit, never past a cap (C23).

    A cut from `cut_from` takes the nearest load no heavier than it, ties to the lighter. A clipped
    load, an effort ceiling (`round_down`) or any other load no heavier than the derived-from load rounds toward
    the lighter lift: down, or up for assistance, where more assistance is a lighter lift; a cap or an effort
    ceiling wins over a cut. An explicit ladder rung stays exact; a clipped rung moves to the nearest rung inside
    the bounds, else leaves the ladder.
    """
    if rounding.available is None:
        return tuple(replace(s, load=None) for s in sets), {}, []
    found, changes, off_ladder = [], {}, []
    for index, s in enumerate(sets):
        if s.load is None:
            found.append(s)
            continue
        value = max(0, s.load)
        leaves_ladder = False
        if rounding.rungs:
            rung = _bounded_rung(value, rounding) if index in clipped else next(
                (r for r in rounding.rungs if _same(value, r)), None)
            if rung is not None:
                found.append(replace(s, load=units.json_number(rung)))
                continue
            leaves_ladder = index in clipped
        derived = rounding.derived
        at_most_derived = derived is not None and (value - derived) * rounding.load_direction <= 1e-9
        floor, cap = rounding.floor, rounding.cap
        cut = cut_from is not None
        if cut and rounding.load_direction > 0 and not (round_down or index in clipped):
            direction, selected = "cut", rounding.available.select_cut(value, cut_from, cap)
        else:
            lighter = round_down or cut or index in clipped or at_most_derived
            direction = ("down" if rounding.load_direction > 0 else "up") if lighter else "nearest"
            selected = rounding.available.select(value, direction, cap)
        if selected is None and direction != "nearest":
            # Nothing on the lighter side (below the lightest dumbbell, the bare bar): the nearest load in the cap.
            selected = rounding.available.select(value, "nearest", cap)
        if selected is not None and floor is not None and selected < floor and (cap is None or cap >= floor):
            raised = rounding.available.select(floor, "up", cap)
            selected = raised if raised is not None else rounding.available.select(cap, "down", cap)
        if selected is not None and not _same(selected, value):
            changes[value] = selected
            value = selected
        if leaves_ladder and value not in off_ladder:
            off_ladder.append(value)
        found.append(replace(s, load=units.json_number(max(0, value))))
    return tuple(found), changes, off_ladder


def _kit_words(kit_changes, mode, unit):
    return [f"the kit makes {_load_text(after, mode, unit)}, not {_load_text(before, mode, unit)}"
            for before, after in kit_changes.items()]


def _beyond_failure(estimate, sets):
    """(set, verdict) for the first working set the e1RM model puts beyond failure, or None."""
    for s in base.working(sets):
        targets = validity.rep_targets(s.reps, s.rep_range)
        if s.load is not None and targets:
            verdict = validity.judge_set(estimate, s.load, targets)
            if verdict.unearned:
                return s, verdict
    return None


def _model_hold(proposal, sets, estimate, limited):
    """When the final `sets` are beyond failure at `estimate`, the heaviest lighter load the derived-from exposure
    logged that the model accepts, put through `limited`: (limited result, set over, its verdict), else None.

    The program's reps, ranges and RPE stay; only the load is held.
    """
    over = _beyond_failure(estimate, sets)
    if over is None:
        return None
    top = base.top_load(sets)
    logged = sorted({s.load for s in base.working(proposal.derived_from.sets)
                     if s.load is not None and s.load < top - 1e-9}, reverse=True)
    for load in logged:
        found = limited(base.with_load(proposal.sets, load), True, False, None)
        if _beyond_failure(estimate, found[0]) is None:
            return (found, *over)
    return None


def _cut_from(proposal):
    """The top load a cut of this proposal is measured from: the derived-from load for a cut the scheme made itself
    (a linear reset), else the lower of the scheme's top load and the derived-from load, which `lightened` cuts."""
    source = proposal.derived_from
    derived = source.top_load if source is not None else None
    if proposal.load_cut:
        return derived
    return min((v for v in (base.top_load(proposal.sets), derived) if v is not None), default=None)


def _load_cut(baseline, proposal, scheme_sets, sets, kit_changes, rounding):
    """How the kit moved the top load of a line its scheme or week cut from `baseline`, or None.

    Assistance is never cut, and a top load a cap or constraint moved is reported by them instead.
    """
    target, actual = base.top_load(proposal.sets), base.top_load(sets)
    if (rounding.load_direction < 0 or baseline is None or target is None or actual is None
            or target >= baseline - 1e-9 or target not in kit_changes):
        return None
    before, after = base.working(scheme_sets), base.working(sets)
    other_cuts = len(after) < len(before) or any(
        a.rpe is not None and (b.rpe is None or a.rpe < b.rpe) for a, b in zip(after, before))
    lighter = rounding.available.select(target, "down", rounding.cap)
    return {"baseline": baseline, "target": target, "actual": actual, "held": actual >= baseline - 1e-9,
            "rose": actual > baseline + 1e-9, "other_cuts": other_cuts, "lighter": lighter}


def _cut_percent(cut, value):
    return units.json_number(round((cut["baseline"] - value) / cut["baseline"] * 100, 1))


def _cut_words(cut, mode, unit):
    """"a 10 % cut from 80 targets 72; the kit makes 72.5, an actual 9.4 % cut": target and actual, never only the
    target."""
    lead = (f"a {_cut_percent(cut, cut['target'])} % cut from {_load_text(cut['baseline'], mode, unit)} targets "
            f"{_load_text(cut['target'], mode, unit)}")
    if not cut["held"]:
        return (f"{lead}; the kit makes {_load_text(cut['actual'], mode, unit)}, an actual "
                f"{_cut_percent(cut, cut['actual'])} % cut")
    held = _load_text(cut["actual"], mode, unit)
    tail = "the set and effort cuts still apply" if cut["other_cuts"] else "no part of the cut applies"
    if cut["rose"]:
        return (f"{lead}; the kit makes nothing at or under {_load_text(cut['baseline'], mode, unit)}, so the load "
                f"rises to {held}, the nearest it makes, and {tail}")
    return f"{lead}; the nearest load the kit makes no heavier than {held} is {held} itself, so the load holds " \
           f"(an actual 0 % cut) and {tail}"


def _held_cut_words(cut, name, mode, unit):
    actual = _load_text(cut["actual"], mode, unit)
    outcome = f"the load rises to {actual}, the nearest it makes" if cut["rose"] else f"{actual} holds"
    words = (f"{name}: the kit cannot make the {_cut_percent(cut, cut['target'])} % cut to "
             f"{_load_text(cut['target'], mode, unit)}, so {outcome}")
    if cut["other_cuts"]:
        return f"{words}; the set and effort cuts still apply"
    if cut["lighter"] is None:
        return f"{words} and nothing lighter fits; no reset or cut is applied, so choose the load"
    return (f"{words}; no reset or cut is applied, so choose between holding it and "
            f"{_load_text(cut['lighter'], mode, unit)}, a {_cut_percent(cut, cut['lighter'])} % cut")


def _bounded_rung(value, rounding):
    """The rung nearest a clipped load inside the cap and floor, ties to the lighter lift; None when none fits."""
    fits = [r for r in rounding.rungs
            if (rounding.cap is None or r <= rounding.cap + 1e-9)
            and (rounding.floor is None or r >= rounding.floor - 1e-9)]
    return min(fits, key=lambda r: (abs(r - value), r * rounding.load_direction), default=None)


FIRST_PRESCRIPTION = "first prescription"


def change_text(before_sets, after_sets, mode, unit):
    """What moved from the prior agreed prescription, or None when nothing did.

    The set shape (count, reps, RPE) and the top working load are compared apart:
    "3×8–10 RPE 8 → 4×8 RPE 8", "100 → 110", or both, the load last. A line with no prior prescription reads
    "first prescription", never a made-up earlier load.
    """
    if not before_sets:
        return FIRST_PRESCRIPTION
    parts = []
    shape = [sets_text(sets, mode, unit, with_load=False) for sets in (before_sets, after_sets)]
    if shape[0] != shape[1]:
        parts.append(" → ".join(shape))
    if mode in units.LOADED_MODES:
        before, after = base.top_load(before_sets), base.top_load(after_sets)
        if (before is None) != (after is None) or (before is not None and not _same(before, after)):
            parts.append(f"{_load_text(before, mode, unit)} → {_load_text(after, mode, unit)}")
        elif not parts:
            full = [sets_text(sets, mode, unit) for sets in (before_sets, after_sets)]
            if full[0] != full[1]:
                parts.append(" → ".join(full))
    return ", ".join(parts) or None


def _core_flags(ctx, entry, exercise, sets, exposures, active, line_flag, mode):
    found = []
    if mode in units.LOADED_MODES and any(s.working and s.load is None for s in sets):
        found.append(line_flag("no_data", f"{ctx.exercise.name}: no usable exposure and no start load, so the load "
                                          "is left for the coach to set"))
    source = base.baseline(exposures)
    if source is not None and not source.prescribed and ctx.scheme in (
            "double_progression", "linear", "assistance_ladder"):
        found.append(line_flag("prescription_unknown", f"{ctx.exercise.name}: historical prescription unknown on "
                                          f"{source.date.isoformat()}; no prescribed hit or miss inferred"))
    direction = ctx.exercise.load_direction
    before_load = _hardest_load(source.sets, direction) if source else None
    after_load = _hardest_load(sets, direction)
    advancing_load = (before_load is not None and after_load is not None
                      and (after_load - before_load) * direction > 1e-9)
    dates_stalled = _stalled(exposures, direction)
    if dates_stalled and not advancing_load:
        found.append(line_flag("stalled", f"{ctx.exercise.name}: no load, reps, duration, distance or matched-work "
                                          f"effort gain over the three comparable exposures of "
                                          f"{', '.join(dates_stalled)} (a coaching heuristic, not a diagnosis)"))
    newest = base.newest(exposures)
    if newest is not None:
        caps = [c["value"] for c in active if c["kind"] == "rpe_cap"]
        cap = min(caps) if caps else None
        if patterns.is_compound(entry) or cap is not None:
            prescribed = newest.prescribed
            if patterns.rpe_drift(newest.sets, prescribed, cap):
                found.append(line_flag("rpe_drift", f"{ctx.exercise.name}: two or more working sets on "
                                                    f"{newest.date.isoformat()} were logged 1 or more RPE over target"))
        if newest.suspect:
            source = base.baseline(exposures)
            instead = f"the exposure of {source.date.isoformat()}" if source else "no exposure"
            found.append(line_flag("convention_slip", f"{ctx.exercise.name}: {newest.date.isoformat()} is an open "
                                                      f"convention-slip candidate, so the line derives from {instead}; "
                                                      "settle it with history annotate (discount or confirm)"))
    return found


def _evidence(run, plugin, transform, line_flag):
    """(rationale clause, flags) for cited research claims whose area has expired (C23 "Evidence", C28)."""
    found = run.research()
    if found is None:
        return None, []
    notes, expired, local = found
    cites = list(plugin.module.CITES) + (list(transform[0].module.CITES) if transform else [])
    clauses, raised, locals_cited = [], [], []
    for ref in cites:
        parsed = research.parse_ref(ref)
        note = notes.get(parsed[0]) if parsed else None
        if note is None:
            continue
        areas = [area for area in note.applies_to if area in expired]
        for area in areas:
            for note_id in expired[area]:
                stale = notes[note_id]
                words = f"evidence under review ({note_id} expired {stale.review_by.isoformat()})"
                if words not in clauses:
                    clauses.append(words)
                    raised.append(line_flag("evidence_expired", f"{plugin.name} cites {ref}; area {area}: {words}"))
        if not areas and ref in local:
            locals_cited.append(f"see local note {local[ref]} for {ref}")
    return "; ".join(clauses + locals_cited) or None, raised


def _transform(run, kind, name):
    if name is None and kind != "deload":
        return None
    rule = run.program["blocks"]["deload_rule"]
    name = name or rule["name"]
    plugin = run.registry.get("transform", name)
    if plugin is None:
        raise UsageError(f"no transform named {name}; known: {', '.join(run.registry.names('transform'))}")
    params, errors = plugins.merged_params(plugin, rule["params"] if name == rule["name"] else {})
    if errors:
        raise ValidationError(f"The {name} transform's params are not valid", details=[e.to_json() for e in errors])
    return plugin, params


def _week_label(kind, transform):
    """What a deload-kind week is for: "Return" for the return transform, which the next week progresses from,
    else "Deload"; None for other kinds."""
    if kind != "deload":
        return None
    return "Return" if transform is not None and transform[0].name == "return" else "Deload"


def _focus(kind, span, transform):
    if kind == "deload":
        return (f"{_week_label(kind, transform)} week of {span.start.isoformat()}: "
                f"{transform[0].module.SUMMARY.rstrip('.')}.")
    if kind == "midweek":
        return f"Rest of the week from {span.start.isoformat()}, re-proposed."
    return f"Week of {span.start.isoformat()}: each lift as its progression scheme proposes."


def _supersedes(run, span, own_id=None):
    overlapping = [doc for doc in run.overlays if doc["id"] != own_id
                   and doc["span"]["start"] <= span.end.isoformat() and span.start.isoformat() <= doc["span"]["end"]]
    newest = max(overlapping, key=lambda d: (d["created_at"], d["id"]), default=None)
    return newest["id"] if newest else None


def lines_of(doc, unit):
    """The compact rows the coach's brief reads: one per line, loads through units.format_load."""
    rows = []
    for session in doc["sessions"]:
        for line in session["exercises"]:
            sets = tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load"))) for s in line["sets"])
            rows.append({
                "session_id": session["session_id"], "date": session["date"], "exercise_id": line["exercise_id"],
                "text": sets_text(sets, line["load_mode"], unit), "change": line["change"],
                "rationale": (line.get("provenance") or {}).get("rationale"),
                "flags": [f["code"] for f in doc["flags"]
                          if f["session_id"] == session["session_id"] and f["exercise_id"] == line["exercise_id"]],
            })
    return rows


def propose_week(root, config, today, now, span, kind="weekly", transform_name=None, plan_file=None, dry_run=False):
    built = _build_week(root, config, today, now, span, kind, transform_name, plan_file=plan_file)
    if not dry_run:
        _write_built(root, built)
    return _week_result(root, config, built, dry_run)


def _build_week(root, config, today, now, span, kind, transform_name, plan_file=None, plan=None, proposal_id=None):
    """Everything `propose week` writes, built and checked: the draft, its overlay, run facts and settled state.

    `plan` (a SchedulePlan) and `proposal_id` let `propose rebuild` replan the same dated sessions under the same id.
    """
    if kind not in KINDS:
        raise UsageError(f"--kind must be one of {', '.join(KINDS)}")
    run = Run(root, config, today, now)
    settled_state, settled = settle(run.state, run.by_id)
    run.state = settled_state
    if plan is not None:
        found = plan
    elif plan_file:
        found = read_plan(run, plan_file, span)
    else:
        span, found = _rest_of_week(run, span, kind, keep_start=proposal_id is not None)
    if not found.sessions:
        raise ValidationError(f"The schedule plans no active session in {span.start}..{span.end}")
    found, ill_flags = _without_ill_days(run, span, found)
    transform = _transform(run, kind, transform_name)
    first_day = found.sessions[0][0]
    ctx_extra = {"kind": kind, "transform": transform, "first_day": first_day, "illness": _illness(run, first_day),
                 "states": dict(settled_state["scheme_state"])}

    draft_sessions, all_flags, scheme_state, session_keys = [], list(found.flags) + ill_flags, {}, []
    label = _week_label(kind, transform)
    for day, session_id in found.sessions:
        session = run.sessions[session_id]
        if ctx_extra["illness"] and day == first_day:
            all_flags.append(flags.make("return_after_illness", session_id=session_id, message=(
                f"{ctx_extra['illness']} falls in the gap before this first session back: resolve this only once "
                f"the athlete confirms {validity.SYMPTOM_FREE_HOURS} hours symptom-free (ending the ill status day "
                f"does not confirm it); every set is capped at RPE {validity.ILLNESS_RPE_CAP}")))
        if conditioning.has_scheme(session):
            repeat = session_id in {sid for _, sid in session_keys}
            results = [(conditioning.state_key(session_id),
                        propose_conditioning(run, session, day, ctx_extra, repeat))]
            lines = results[0][1].draft_line
        else:
            results = [(f"{session_id}/{exercise['exercise_id']}", propose_line(run, session, day, exercise, ctx_extra))
                       for exercise in session["exercises"]]
            lines = [result.draft_line for _, result in results]
        for key, result in results:
            all_flags += result.flags
            entry = ctx_extra["states"].get(key)
            ctx_extra["states"][key] = {"scheme": result.scheme, "data": result.state,
                                        "pending": entry.get("pending") if entry else None}
            scheme_state[key] = {"scheme": result.scheme, "data": result.state}
        session_keys.append(([key for key, _ in results], session_id))
        draft_sessions.append({
            "session_id": session_id, "date": day.isoformat(),
            "title": f"{label} — {session['title']}" if label else session["title"],
            "temporary": kind == "deload", "location": session["location"], "focus": session["focus"],
            "exercises": lines,
        })
    all_flags += followups.due_flags(root, today) + niggles.week_flags(root)
    basis = {key: _state_basis(run.registry, key, entry["scheme"], settled_state["scheme_state"].get(key))
             for key, entry in scheme_state.items()}
    draft_sessions, dropped, drop_flags = _drop_rule(run, span, draft_sessions, session_keys, scheme_state, all_flags)
    all_flags = [f for f in all_flags if not any(f in entry["flags"] for entry in dropped)]

    draft = {
        "schema_version": overlay.current_version(), "kind": kind, "span": span.to_json(),
        "supersedes": _supersedes(run, span, proposal_id), "focus": _focus(kind, span, transform), "flags": all_flags,
        "sessions": draft_sessions,
    }
    if proposal_id is not None:
        draft["id"] = proposal_id
    doc = overlay.build(draft, config, root=root, now=now)
    doc["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    doc["flags"] += _week_flags(root, config, today, span, doc) + drop_flags
    doc["flags"] += external.requirement_flags(root, doc, config.hevy.enabled)
    draft = dict(draft, id=doc["id"], flags=doc["flags"])
    meta = {
        "id": doc["id"], "kind": kind, "span": span.to_json(), "transform": transform[0].name if transform else None,
        "created_at": doc["created_at"], "rotation": found.rotation,
        "scheme_state": {} if kind == "deload" else scheme_state, "dropped": dropped, "state_basis": basis,
        "plan": None if plan is None and not plan_file else {
            "sessions": [{"date": day.isoformat(), "session_id": sid} for day, sid in found.sessions],
            "flags": list(found.flags)},
    }
    return {"run": run, "settled_state": settled_state, "settled": settled, "draft": draft, "proposed": draft,
            "doc": doc, "meta": meta, "span": span, "kind": kind, "rotation": found.rotation, "dropped": dropped}


def _write_built(root, built):
    if built["settled"]:
        _write_state(root, built["settled_state"], built["run"].program)
    _write_proposal(root, built["doc"]["id"], built["draft"], built["proposed"], built["meta"])


def _week_result(root, config, built, dry_run):
    doc = built["doc"]
    draft_path, proposed_path, _ = proposal_paths(root, doc["id"])
    lines = lines_of(doc, config.athlete.units)
    return {
        "id": doc["id"], "kind": built["kind"], "span": built["span"].to_json(), "draft": _relative(root, draft_path),
        "proposed": _relative(root, proposed_path), "overlay": doc, "lines": lines,
        "lines_digest": jsonio.canonical_hash(lines), "settled": built["settled"], "rotation": built["rotation"],
        "dropped": [_dropped_row(entry) for entry in built["dropped"]], "written": not dry_run,
    }


def _rest_of_week(run, span, kind, keep_start=False):
    """(span, plan) from the schedule rule; a midweek run leaves out each session already trained from the span
    start through today.

    When nothing is left to train today, the span starts tomorrow, unless `keep_start`: a rebuild keeps its draft's
    span, because the span start is part of the draft's id.
    """
    found = plan_schedule(run, span)
    if kind != "midweek" or not span.start <= run.today <= span.end:
        return span, found
    done = trained_on(run.root, span.start, run.today)
    if not done:
        return span, found
    left = tuple(planned for planned in found.sessions if planned not in done)
    if (not keep_start and span.start == run.today and run.today < span.end
            and not any(day == run.today for day, _ in left)):
        span = dates.Span(run.today + timedelta(days=1), span.end)
        found = plan_schedule(run, span)
        left = found.sessions
    return span, replace(found, sessions=left)


def trained_on(root, start, end):
    """(date, session id) pairs trained from `start` through `end`: each planned session `stats adherence` counts as
    trained (C18), on its planned date, and any other workout logged in those days."""
    found = stats.adherence(root, span=(start, end), today=end)
    done = {(dates.parse_date(row["date"]), row["session_id"]) for row in found["sessions"]
            if row["status"] == "trained"}
    done |= {(dates.parse_date(w["date"]), w["session_id"]) for w in found["extra"]
             if start.isoformat() <= w["date"] <= end.isoformat() and w["session_id"]}
    return done


def _dropped_row(entry):
    return {key: entry[key] for key in ("session_id", "date", "trigger", "reason", "restored")}


def _drop_rule(run, span, draft_sessions, session_keys, scheme_state, all_flags):
    """Step 5b: (kept sessions, dropped entries, flags) under the C51 drop rule.

    A dropped entry keeps the session's draft, the flags that name it and
    the scheme state it would have left pending, so `propose restore` can
    put all three back. A core session is never dropped, and neither is a
    draft's only session.
    """
    fired = conditioning.triggers(run.root, run.config, run.today, span, draft_sessions, run.program["sessions"])
    leaving = {item["index"] for item in fired if item["tier"] == "optional"}
    if leaving and len(leaving) == len(draft_sessions):
        leaving = set()
    found_flags, dropped = [], []
    for item in fired:
        if item["index"] not in leaving:
            why = ("a core session is never dropped" if item["tier"] == "core"
                   else "it is the only planned session in the span")
            found_flags.append(conditioning.keep_flag(item, why))
            continue
        flag = conditioning.drop_flag(item)
        found_flags.append(flag)
        keys, _ = session_keys[item["index"]]
        dropped.append({"session_id": item["session_id"], "date": item["date"], "trigger": item["trigger"],
                        "reason": item["reason"], "restored": None, "message": flag["message"],
                        "session": draft_sessions[item["index"]], "keys": keys})
    kept = [s for index, s in enumerate(draft_sessions) if index not in leaving]
    kept_keys = {key for index, (keys, _) in enumerate(session_keys) if index not in leaving for key in keys}
    kept_ids = {s["session_id"] for s in kept}
    claimed = set()
    for entry in dropped:
        entry["scheme_state"] = {key: scheme_state[key] for key in entry["keys"] if key in scheme_state}
        for key in entry["keys"]:
            if key not in kept_keys:
                scheme_state.pop(key, None)
        sid = entry["session_id"]
        entry["flags"] = [f for f in all_flags if f["session_id"] == sid] if sid not in kept_ids | claimed else []
        claimed.add(sid)
    return kept, dropped, found_flags


def _week_flags(root, config, today, span, doc):
    """Step 5a: every week-flag provider's flags for the draft's span (C24, C49)."""
    bouts = tuple(cardio.bouts(root, span, "proposal", overlay=doc, today=today))
    return weekflags.run(weekflags.WeekFlagContext(root, today, span, "proposal", config, doc, bouts))


def _check_state(doc, program_doc):
    errors = state_module.problems(doc, program_doc)
    if errors:
        raise ValidationError(f"The updated {paths.STATE} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])


def _write_state(root, doc, program_doc):
    _check_state(doc, program_doc)
    jsonio.write_doc(state_module.path_for(root), doc, False)


def _line_key(session, line):
    return session["session_id"], session["date"], line["exercise_id"]


def _lines_by_key(draft):
    return {_line_key(s, line): line for s in draft.get("sessions", []) for line in s.get("exercises", [])}


def unexplained_changes(draft, proposed):
    """Lines of the draft that differ from the untouched proposal and carry no override reason."""
    before, after = _lines_by_key(proposed), _lines_by_key(draft)
    found = []
    for key, line in after.items():
        original = before.get(key)
        explained = bool((line.get("override") or {}).get("reason", "").strip())
        strip = {k: v for k, v in line.items() if k != "override"}
        if original is None:
            if not explained:
                found.append((key, "is not in the proposal and has no override reason"))
        elif strip != {k: v for k, v in original.items() if k != "override"} and not explained:
            found.append((key, "differs from the proposal and has no override reason"))
    for key in before:
        if key not in after:
            found.append((key, "was removed from the proposal; put it back, or override it with a reason"))
    return [{"path": f"{session_id} {day} {exercise_id}", "message": message}
            for (session_id, day, exercise_id), message in found]


def _locate(draft, session_id, exercise_id):
    found = [(session, line) for session in draft["sessions"] if session["session_id"] == session_id
             for line in session["exercises"] if line["exercise_id"] == exercise_id]
    if not found:
        raise ValidationError(f"The proposal has no line for {exercise_id} in session {session_id}")
    return found


def override(root, config, proposal_id, session_id, exercise_id, new_sets, load, reason, standing, until, now,
             today, dry_run):
    """Change one slot's line(s) in a draft, keeping the proposal in `override.proposed_sets` (C24, C25)."""
    if not reason or not reason.strip():
        raise UsageError("--reason must say why the line is overridden")
    draft, proposed, _ = load_proposal(root, proposal_id)
    selected = _locate(draft, session_id, exercise_id)
    figures = bare_figures(reason)
    if figures and any(line["load_mode"] == PER_HAND_X2 for _, line in selected):
        raise ValidationError(bare_message("override", "reason", figures, exercise_id, reason, config.hevy.enabled))
    originals = _lines_by_key(proposed)
    unit = config.athlete.units
    previous = last_prescription(overlay.list(root), session_id, exercise_id, exclude=proposal_id)
    changed = []
    for session, line in selected:
        original = originals.get(_line_key(session, line))
        before = (line.get("override") or {}).get("proposed_sets") or (original or line)["sets"]
        current = tuple(base.SetSpec.from_dict(s) for s in line["sets"])
        if new_sets is not None:
            problem = _metric_problem(exercise_id, line["load_mode"], new_sets)
            if problem:
                raise ValidationError(problem)
            sets = tuple(s for s in current if not s.working) + _rep_out_capped(root, session, line, new_sets)
        else:
            sets = base.with_load(current, load)
        if line["load_mode"] not in units.LOADED_MODES and any(s.load is not None for s in sets):
            raise ValidationError(f"{exercise_id} is {line['load_mode']}, which carries no load")
        line["sets"] = [s.to_dict() for s in sets]
        line["override"] = {"reason": reason.strip(), "proposed_sets": before}
        line["change"] = change_text(previous["sets"] if previous else None, sets, line["load_mode"], unit)
        changed.append({"date": session["date"], "text": sets_text(sets, line["load_mode"], unit)})

    if until is not None and not standing:
        raise UsageError("--until goes with --standing")
    doc = overlay.build(draft, config, root=root, now=now)
    draft["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    decision = None
    if standing:
        until_date = decisions.standing_until(today, until)
        _, line = _locate(draft, session_id, exercise_id)[0]
        record = decisions.override(_timestamp(now), proposal_id, session_id, exercise_id, reason.strip(),
                                    line["override"]["proposed_sets"], line["sets"], True, until_date.isoformat())
        _, decision = decisions.append(root, decisions.load(root), record, dry_run)
    if not dry_run:
        _write_proposal(root, proposal_id, draft, None, None)
    return {"id": proposal_id, "session_id": session_id, "exercise_id": exercise_id, "lines": changed,
            "decision": decision, "flags": draft["flags"], "written": not dry_run}


def _rep_out_capped(root, session, line, sets):
    """`sets` with each rep-out set capped at the lowest RPE cap that applies to the line: an active `rpe_cap`
    constraint (C26) or its return band's (C22)."""
    if not any(s.rep_out for s in sets):
        return sets
    day = dates.parse_date(session["date"])
    caps = [c["value"] for c in constraints_module.active(root, session["session_id"], line["exercise_id"], day)
            if c["kind"] == "rpe_cap"]
    decay = (line.get("provenance") or {}).get("decay") or {}
    if decay.get("rpe_cap") is not None:
        caps.append(decay["rpe_cap"])
    if not caps:
        return sets
    return tuple(base.rpe_capped((s,), min(caps))[0] if s.rep_out else s for s in sets)


def resolve(root, proposal_id, index, resolution, dry_run):
    if not resolution or not resolution.strip():
        raise UsageError("--resolution must say how the flag is settled")
    draft, _, _ = load_proposal(root, proposal_id)
    found = draft.get("flags", [])
    if not 0 <= index < len(found):
        raise ValidationError(f"Proposal {proposal_id} has {len(found)} flag(s); --flag takes 0 to {len(found) - 1}")
    if found[index]["code"] == validity.UNCONFIRMED:
        raise RefusedError(f"Flag {index} clears only once the library holds a confirmed load mode, not with a "
                           f"resolution: {found[index]['message']}")
    found[index] = dict(found[index], resolved=True, resolution=resolution.strip())
    if not dry_run:
        _write_proposal(root, proposal_id, draft, None, None)
    return {"id": proposal_id, "flag": found[index], "written": not dry_run}


def restore(root, config, proposal_id, session_id, reason, now, today, dry_run):
    """Put a conditioning session the drop rule removed back into a draft, resolving its flag (C24, C51).

    The session goes back into the draft and the untouched proposal alike,
    since it is what the pipeline proposed, so finalize accepts it. Its
    scheme state is pending again, and the week flags are judged afresh.
    """
    if not reason or not reason.strip():
        raise UsageError("--reason must say why the session goes back in")
    draft, proposed, meta = load_proposal(root, proposal_id)
    entries = [e for e in meta.get("dropped", []) if e["session_id"] == session_id and e["restored"] is None]
    if not entries:
        dropped = sorted({e["session_id"] for e in meta.get("dropped", []) if e["restored"] is None})
        raise ValidationError(f"Proposal {proposal_id} has no dropped session {session_id} to restore; dropped: "
                              f"{', '.join(dropped) or 'none'}")
    reason = reason.strip()
    for entry in entries:
        for doc in (draft, proposed):
            doc["sessions"] = sorted([*doc["sessions"], copy.deepcopy(entry["session"])], key=lambda s: s["date"])
        entry["restored"] = {"reason": reason, "at": _timestamp(now)}
        draft["flags"] = draft["flags"] + [f for f in entry["flags"] if f not in draft["flags"]]
        if meta["kind"] != "deload":
            meta["scheme_state"].update(entry["scheme_state"])
        for flag in draft["flags"]:
            if flag["code"] == "conditioning_dropped" and flag["message"] == entry["message"] and not flag["resolved"]:
                flag.update(resolved=True, resolution=reason)
    doc = overlay.build(draft, config, root=root, now=now)
    doc["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    span = dates.Span(dates.parse_date(meta["span"]["start"]), dates.parse_date(meta["span"]["end"]))
    known = {validity.flag_key(f) for f in doc["flags"]}
    doc["flags"] += [f for f in _week_flags(root, config, today, span, doc) if validity.flag_key(f) not in known]
    draft["flags"] = doc["flags"]
    if not dry_run:
        _write_proposal(root, proposal_id, draft, proposed, meta)
    return {"id": proposal_id, "session_id": session_id, "restored": [_dropped_row(e) for e in entries],
            "flags": draft["flags"], "lines": lines_of(doc, config.athlete.units), "written": not dry_run}


def rebuild(root, config, proposal_id, today, now, dry_run):
    """Propose a draft's span again under the same id from the program as it is now, keeping the draft's
    explained edits and flag resolutions (C24).

    An edit whose line the program no longer has is reported in `lost`, never applied elsewhere. An unapproved
    overlay finalized from the old draft is removed, so only a new finalize can reach approval.
    """
    draft, proposed, meta = load_proposal(root, proposal_id)
    path = overlay.path_for(root, proposal_id)
    if path.exists() and overlay.is_approved(overlay.read_json(path) or {}):
        raise RefusedError(f"Overlay {proposal_id} is already approved, so rebuild does not replace it; run "
                           "propose week again for a new id")
    stale = stale_reason(meta, today, overlay.list(root))
    if stale:
        raise RefusedError(f"Proposal {proposal_id} is stale: {stale}. Propose the week again, or discard it with "
                           f"python3 -m coach propose discard --proposal {proposal_id}")
    span = dates.Span(dates.parse_date(meta["span"]["start"]), dates.parse_date(meta["span"]["end"]))
    plan = None
    if meta.get("plan"):
        plan = base.SchedulePlan(
            sessions=tuple(sorted((dates.parse_date(s["date"]), s["session_id"]) for s in meta["plan"]["sessions"])),
            rotation=None, flags=tuple(meta["plan"].get("flags", ())))
    built = _build_week(root, config, today, now, span, meta["kind"], meta.get("transform"), plan=plan,
                        proposal_id=proposal_id)
    new_draft = copy.deepcopy(built["draft"])
    kept, lost = _carry_edits(root, proposal_id, draft, proposed, new_draft, config.athlete.units)
    doc = overlay.build(new_draft, config, root=root, now=now)
    doc["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    resolved = {_flag_identity(f): f for f in draft.get("flags", []) if f.get("resolved")}
    carried_resolutions = 0
    for flag in doc["flags"]:
        earlier = resolved.get(_flag_identity(flag))
        if earlier is not None and not flag["resolved"] and flag["code"] != validity.UNCONFIRMED:
            flag.update(resolved=True, resolution=earlier["resolution"])
            carried_resolutions += 1
    new_draft["flags"] = doc["flags"]
    built = dict(built, draft=new_draft, doc=doc)
    finalized = path.exists()
    if not dry_run:
        _write_built(root, built)
        if finalized:
            path.unlink()
    result = _week_result(root, config, built, dry_run)
    dropped_again = {(e["session_id"], e["date"]) for e in built["dropped"]}
    restores_lost = [_dropped_row(e) for e in meta.get("dropped", [])
                     if e.get("restored") and (e["session_id"], e["date"]) in dropped_again]
    return dict(result, kept=kept, lost=lost, resolutions_kept=carried_resolutions, restores_lost=restores_lost,
                overlay_removed=_relative(root, path) if finalized else None)


def _flag_identity(flag):
    return flag["code"], flag.get("session_id"), flag.get("exercise_id"), flag["message"]


def _carry_edits(root, proposal_id, draft, proposed, new_draft, unit):
    """Copy each explained line edit of `draft` onto the same session, date and exercise in `new_draft`.

    Returns (kept rows, lost rows). The scheme's new sets become the line's `override.proposed_sets`.
    """
    originals = _lines_by_key(proposed)
    targets = {_line_key(session, line): (session, line) for session in new_draft["sessions"]
               for line in session["exercises"]}
    overlays = overlay.list(root)
    kept, lost = [], []
    for session in draft.get("sessions", []):
        for line in session.get("exercises", []):
            reason = ((line.get("override") or {}).get("reason") or "").strip()
            if not reason:
                continue
            key = _line_key(session, line)
            row = {"session_id": key[0], "date": key[1], "exercise_id": key[2], "reason": reason}
            original = originals.get(key) or {}
            if original.get("override") == line["override"] and original.get("sets") == line["sets"]:
                continue
            if key not in targets:
                lost.append(row)
                continue
            _, target = targets[key]
            scheme_sets = ((target.get("override") or {}).get("proposed_sets")) or target["sets"]
            for field, value in line.items():
                if field not in ("override", "change", "provenance") and (field not in original
                                                                          or original[field] != value):
                    target[field] = copy.deepcopy(value)
            target["override"] = {"reason": reason, "proposed_sets": scheme_sets}
            previous = last_prescription(overlays, key[0], key[2], exclude=proposal_id)
            target["change"] = change_text(previous["sets"] if previous else None,
                                           tuple(base.SetSpec.from_dict(s) for s in target["sets"]),
                                           target["load_mode"], unit)
            kept.append(row)
    return kept, lost


def discard(root, proposal_id, today, dry_run):
    """Remove a draft and any unapproved overlay finalized from it, with the scheme state pending on that overlay
    (C24). An approved overlay of the same id, and every decision, stay as they are."""
    draft_path, proposed_path, meta_path = proposal_paths(root, proposal_id)
    load_proposal(root, proposal_id)
    removed = [p for p in (draft_path, proposed_path, meta_path) if p.exists()]
    path = overlay.path_for(root, proposal_id)
    approved = path.exists() and overlay.is_approved(overlay.read_json(path) or {})
    if path.exists() and not approved:
        removed.append(path)
    state_doc = state_module.load(root)
    cleared = sorted(slot for slot, entry in state_doc["scheme_state"].items()
                     if not approved and (entry.get("pending") or {}).get("overlay_id") == proposal_id)
    standing = [d["id"] for d in decisions.load(root)["decisions"] if d["kind"] == "override" and d["standing"]
                and d["overlay_id"] == proposal_id and decisions.effective_status(d, today) == "active"]
    if not dry_run:
        if cleared:
            for slot in cleared:
                state_doc["scheme_state"][slot] = dict(state_doc["scheme_state"][slot], pending=None)
            _write_state(root, state_doc, program.load(root))
        for found in removed:
            found.unlink()
    return {"id": proposal_id, "removed": [_relative(root, p) for p in removed], "pending_cleared": cleared,
            "overlay_kept": approved, "standing_decisions": standing, "written": not dry_run}


def show(root, config, proposal_id, now):
    draft, proposed, meta = load_proposal(root, proposal_id)
    doc = overlay.build(draft, config, root=root, now=now)
    lines = lines_of(doc, config.athlete.units)
    return {"id": proposal_id, "kind": meta["kind"], "span": meta["span"], "overlay": doc, "lines": lines,
            "lines_digest": jsonio.canonical_hash(lines), "unexplained": unexplained_changes(draft, proposed),
            "unresolved_blocks": overlay.unresolved_blocks(doc),
            "dropped": [_dropped_row(e) for e in meta.get("dropped", [])]}


def stale_reason(meta, today, overlays):
    """Why a draft no longer stands for its days, or None: its span has ended, or an overlay finalized after the
    draft was proposed and since approved covers its remaining days (C24)."""
    span, created = meta.get("span") or {}, meta.get("created_at")
    if not span.get("start") or not span.get("end") or not created:
        return None
    if span["end"] < today.isoformat():
        return f"its span ended on {span['end']}"
    rest = max(span["start"], today.isoformat())
    proposed_at = dates.parse_timestamp(created)
    newer = [doc for doc in overlays if doc["id"] != meta.get("id") and overlay.is_approved(doc)
             and dates.parse_timestamp(doc["created_at"]) > proposed_at
             and doc["span"]["start"] <= span["end"] and rest <= doc["span"]["end"]]
    if not newer:
        return None
    newest = max(newer, key=lambda d: (d["created_at"], d["id"]))
    return f"overlay {newest['id']}, approved since it was proposed, covers its remaining days"


def _refuse_structure_drift(root, doc, then):
    drift = structure_drift(root, doc)
    if drift:
        raise RefusedError(f"Overlay {doc['id']} no longer matches data/program.json; {then}",
                           details=[{"path": None, "message": message} for message in drift])


def structure_drift(root, doc):
    """How a pipeline-built overlay's sessions differ from the program's exercises, one message each (C24).

    One-off overlays are coach-built and lines a missed-day rule folded in last one week, so neither is compared.
    A line the program lacks passes when it carries an override reason: the coach added it for this week.
    """
    if doc["kind"] == "one_off" or not (Path(root) / paths.PROGRAM).is_file():
        return []
    sessions = {s["id"]: s for s in program.load(root)["sessions"]}
    found = []
    for session in doc["sessions"]:
        planned = sessions.get(session["session_id"])
        if planned is None:
            found.append(f"{session['session_id']} on {session['date']} is no longer a program session")
            continue
        lines = [line for line in session["exercises"] if not line.get("fold")]
        want = {line["exercise_id"] for line in planned["exercises"]}
        missing = want - {line["exercise_id"] for line in lines}
        extra = {line["exercise_id"] for line in lines if line["exercise_id"] not in want
                 and not ((line.get("override") or {}).get("reason") or "").strip()}
        if missing:
            found.append(f"{session['session_id']} on {session['date']} lacks {', '.join(sorted(missing))}")
        if extra:
            found.append(f"{session['session_id']} on {session['date']} has {', '.join(sorted(extra))}, which "
                         "the program does not list, with no override reason")
    return found


def finalize(root, config, proposal_id, now, dry_run, today=None):
    """Write the overlay, one-week override decisions and pending scheme state, once every change is explained (C24).

    Everything is built and checked before the first write, so a refusal or a dry run writes nothing.
    """
    draft, proposed, meta = load_proposal(root, proposal_id)
    stale = stale_reason(meta, today or now.date(), overlay.list(root))
    if stale:
        raise RefusedError(f"Proposal {proposal_id} is stale: {stale}. Propose the week again, or discard it with "
                           f"python3 -m coach propose discard --proposal {proposal_id}")
    state_doc = state_module.load(root)
    registry = plugins.load(root)
    _check_basis(meta, state_doc, registry, proposal_id)
    unexplained = unexplained_changes(draft, proposed)
    if unexplained:
        raise ValidationError(f"{len(unexplained)} line(s) of proposal {proposal_id} changed without an override "
                              "reason; use propose override, or give the line's override a reason",
                              details=unexplained)
    doc = overlay.build(draft, config, root=root, now=now)
    doc["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    blocks = overlay.unresolved_blocks(doc)
    if blocks:
        raise RefusedError(
            f"Proposal {proposal_id} has {len(blocks)} unresolved block flag(s); settle each as its message "
            "says, or, where a reason can accept it, resolve it with propose resolve",
            details=[{"path": None, "message": f"{f['code']} ({f['session_id']} / {f['exercise_id']}): {f['message']}"}
                     for f in blocks])
    path = overlay.path_for(root, doc["id"])
    if path.exists() and (overlay.read_json(path) or {}).get("approval"):
        raise RefusedError(f"Overlay {doc['id']} is already approved, so finalize does not replace it; run "
                           "propose week again for a new id")
    _refuse_structure_drift(root, doc, f"run python3 -m coach propose rebuild --proposal {proposal_id}, which "
                                       "keeps the draft's overrides, then finalize again")

    decision_doc = decisions.load(root)
    recorded = {(d["overlay_id"], d["scope"].get("session_id"), d["scope"].get("exercise_id"))
                for d in decision_doc["decisions"] if d["kind"] == "override"}
    made = [d for d in decision_doc["decisions"] if d["kind"] == "override"]
    appended = []
    for session in draft["sessions"]:
        day = dates.parse_date(session["date"])
        for line in session["exercises"]:
            if not line.get("override"):
                continue
            scope = (session["session_id"], line["exercise_id"])
            kept = any(d["scope"] == {"session_id": scope[0], "exercise_id": scope[1]}
                       and d["reason"] == line["override"]["reason"] and decisions.effective_status(d, day) == "active"
                       and (d["standing"] or d["chosen_sets"] == line["sets"])
                       for d in made)
            if (proposal_id, *scope) in recorded or kept:
                continue
            record = decisions.override(_timestamp(now), doc["id"], scope[0], scope[1], line["override"]["reason"],
                                        line["override"]["proposed_sets"], line["sets"], False, doc["span"]["end"])
            decision_doc, decision = decisions.append(root, decision_doc, record, True)
            recorded.add((proposal_id, *scope))
            appended.append(decision)

    program_doc = program.load(root)
    last_lines = _last_lines(draft)
    pending = []
    for slot, entry in meta["scheme_state"].items():
        stored = state_doc["scheme_state"].get(slot)
        plugin_name = entry["scheme"]
        plugin = registry.get("conditioning" if conditioning.is_state_key(slot) else "scheme", plugin_name)
        if stored is None or stored["scheme"] not in (None, plugin_name):
            stored = {"scheme": plugin_name, "data": plugins.initial_state(plugin), "pending": None}
        data = _override_state(program_doc, plugin, slot, entry["data"], last_lines.get(slot))
        state_doc["scheme_state"][slot] = dict(stored, scheme=plugin_name,
                                               pending={"overlay_id": doc["id"], "data": data})
        pending.append(slot)
    if meta.get("rotation"):
        rotation = dict(state_doc["rotation"])
        rotation.update(meta["rotation"])
        state_doc["rotation"] = rotation
    _check_state(state_doc, program_doc)

    if not dry_run:
        # The overlay goes last: pending state naming a missing overlay is dropped at the next settle, so a write
        # that fails part-way leaves no new overlay to approve without its state.
        jsonio.write_doc(state_module.path_for(root), state_doc, False)
        if appended:
            jsonio.write_doc(decisions.path_for(root), decision_doc, False)
        jsonio.write_doc(path, doc, False)
    return {"id": doc["id"], "path": _relative(root, path), "overlay": doc, "decisions": appended,
            "pending": pending, "rotation": state_doc["rotation"], "written": not dry_run}


def _state_basis(registry, slot, plugin_name, entry):
    """A hash of the stored data finalize builds the slot's pending state on, a state kept for another scheme
    counting as the scheme's initial one, as finalize treats it."""
    if entry is None or entry["scheme"] not in (None, plugin_name):
        plugin = registry.get("conditioning" if conditioning.is_state_key(slot) else "scheme", plugin_name)
        data = plugins.initial_state(plugin) if plugin is not None else None
    else:
        data = entry["data"]
    return jsonio.canonical_hash(data)


def _check_basis(meta, state_doc, registry, proposal_id):
    """Refuse a draft whose slots' stored state changed after it was proposed: its loads come from the old state,
    and its pending state would quietly undo the change."""
    basis = meta.get("state_basis") or {}
    changed = sorted(slot for slot, entry in meta["scheme_state"].items() if slot in basis and basis[slot]
                     != _state_basis(registry, slot, entry["scheme"], state_doc["scheme_state"].get(slot)))
    if changed:
        raise RefusedError(f"The stored scheme state of {', '.join(changed)} changed after proposal {proposal_id} "
                           "was proposed (a training max set, or another week settled), so its loads are out of "
                           "date; run propose week again for this span")


def _open_drafts(root, slot, today, skip):
    """Ids of proposals for a span not yet over that hold `slot` and whose overlay is not approved."""
    found = []
    for path in sorted((Path(root) / paths.PROPOSALS_DIR).glob("*.meta.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        proposal_id = meta.get("id")
        if (proposal_id and proposal_id != skip and slot in (meta.get("scheme_state") or {})
                and meta["span"]["end"] >= today.isoformat() and not _approved(root, proposal_id)):
            found.append(proposal_id)
    return found


def _last_lines(draft):
    """Each slot's line in the draft's latest session holding it, by `<session id>/<exercise id>`."""
    found = {}
    for session in sorted(draft["sessions"], key=lambda s: s["date"]):
        for line in session["exercises"]:
            found[f"{session['session_id']}/{line['exercise_id']}"] = line
    return found


def _override_state(program_doc, plugin, slot, data, line):
    """The pending state of a slot whose line the coach overrode, through its scheme's `override_state` (C23)."""
    hook = getattr(plugin.module, "override_state", None) if plugin is not None else None
    if hook is None or line is None or not line.get("override"):
        return data
    session_id, exercise_id = slot.split("/", 1)
    exercise = next((e for s in program_doc["sessions"] if s["id"] == session_id for e in s["exercises"]
                     if e["exercise_id"] == exercise_id), None)
    if exercise is None or exercise["scheme"]["name"] != plugin.name:
        return data
    params, errors = plugins.merged_params(plugin, exercise["scheme"]["params"])
    if errors:
        raise ValidationError(f"Scheme {plugin.name} params fail its PARAMS schema",
                              details=[e.to_json() for e in errors])
    found = hook(params, dict(data), tuple(base.working([base.SetSpec.from_dict(s) for s in line["sets"]])),
                 exercise["load_mode"])
    errors = plugins.state_errors(plugin, found)
    if errors:
        raise ValidationError(f"Scheme {plugin.name} returned an override state that fails its STATE schema",
                              details=[e.to_json() for e in errors])
    return found


def _approved(root, overlay_id):
    return overlay.path_for(root, overlay_id).is_file() and overlay.is_approved(overlay.load(root, overlay_id))


def set_training_max(root, session_id, exercise_id, value, reason, now, today, dry_run):
    """Set one slot's training max explicitly, keeping its place in the wave, and record why as a `training_max`
    decision (C23, C25). A pending state its overlay's approval already holds is taken as the slot's state first; a
    pending state still waiting for approval takes the new training max too, so approving it later keeps the change."""
    if not reason or not reason.strip():
        raise UsageError("--reason must say why the training max changes")
    if value <= 0:
        raise UsageError("--value must be above 0")
    program_doc = program.load(root)
    exercise = next((e for s in program_doc["sessions"] if s["id"] == session_id for e in s["exercises"]
                     if e["exercise_id"] == exercise_id), None)
    if exercise is None:
        raise ValidationError(f"The program has no {exercise_id} in session {session_id}")
    name = exercise["scheme"]["name"]
    plugin = plugins.load(root).get("scheme", name)
    if plugin is None or "training_max" not in plugins.initial_state(plugin):
        raise ValidationError(f"{session_id}/{exercise_id} runs {name}, which keeps no training max")
    slot = f"{session_id}/{exercise_id}"
    state_doc = state_module.load(root)
    stored = state_doc["scheme_state"].get(slot)
    if stored is None or stored["scheme"] not in (None, name):
        data, pending = plugins.initial_state(plugin), None
    else:
        data, pending = dict(stored["data"]), stored["pending"]
        if pending and _approved(root, pending["overlay_id"]):
            data, pending = dict(pending["data"]), None
        if plugins.state_errors(plugin, data):
            data = plugins.initial_state(plugin)
    before = data["training_max"]
    value = units.json_number(value)
    data["training_max"] = value
    if data.get("through", False) is None:
        data["through"] = {"date": today.isoformat(), "workout_id": None}
    if pending and not plugins.state_errors(plugin, pending["data"]):
        pending = dict(pending, data=dict(pending["data"], training_max=value))
    state_doc["scheme_state"][slot] = {"scheme": name, "data": data, "pending": pending}
    _check_state(state_doc, program_doc)
    record = decisions.training_max(_timestamp(now), session_id, exercise_id, name, before, value, reason.strip())
    decision_doc, decision = decisions.append(root, decisions.load(root), record, True)
    if not dry_run:
        jsonio.write_doc(state_module.path_for(root), state_doc, False)
        jsonio.write_doc(decisions.path_for(root), decision_doc, False)
    waiting = pending["overlay_id"] if pending else None
    drafts = _open_drafts(root, slot, today, waiting)
    notes = []
    if waiting:
        notes.append(f"{waiting} still prescribes the old training max's loads, and a session trained from them can "
                     f"miss the new one's: propose that week again before approving {waiting}")
    if drafts:
        listed = ", ".join(drafts)
        notes.append(f"{listed} was proposed at the old training max, so finalize refuses it: propose that week "
                     f"again before finalizing {listed}")
    return {"slot": slot, "scheme": name, "from": before, "to": value, "state": data, "decision": decision,
            "pending_overlay": waiting, "open_drafts": drafts, "note": "; ".join(notes) or None,
            "written": not dry_run}

