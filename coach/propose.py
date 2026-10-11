"""The proposal pipeline behind `coach propose` (contract C24).

`propose week` turns the program, its state, the history and the decisions
into an editable draft overlay: each slot's scheme proposes, then the core
decays stale lines, applies the week's transform, the load constraints,
caps and rounding, and any standing override. Loads stay coaching numbers
until `coach.overlay.build` makes load objects through `coach.units`.
`propose finalize` turns the edited draft into the overlay R-13 approves.
"""

import json
import re
from dataclasses import replace
from datetime import timedelta, timezone
from pathlib import Path

from coach import config as config_module
from coach import constraints as constraints_module
from coach import dates, decisions, flags, history, jsonio, overlay, paths, patterns, plugins, program, research
from coach import state as state_module
from coach import stats, units, validity
from coach.checks.instance import cap_for
from coach.errors import ConfigError, RefusedError, UsageError, ValidationError
from coach.library import Library
from coach.plugins import base

KINDS = ("weekly", "midweek", "deload")
DECAY_AFTER_DAYS = validity.RETURN_BANDS[0].upper
STALL_EXPOSURES = 3
_SET_SPEC = re.compile(r"^\s*(\d+)\s*[x×]\s*(\d+)(?:\s*-\s*(\d+))?\s*(?:@\s*(\d+(?:\.\d+)?))?\s*"
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


def sets_text(sets, mode, unit):
    """The working sets in words, loads through units.format_load: "3×8 @ 24/hand (Hevy: 48) RPE 8"."""
    groups = []
    for s in sets:
        if not s.working:
            continue
        reps = (f"{s.rep_range[0]}–{s.rep_range[1]}" if s.rep_range else
                str(s.reps) if s.reps is not None else
                f"{s.duration_seconds} s" if s.duration_seconds else
                f"{units.json_number(s.distance_meters)} m" if s.distance_meters is not None else "?")
        words = reps
        load = _load_text(s.load, mode, unit)
        if load:
            words += f" @ {load}"
        if s.rpe is not None:
            words += f" RPE {units.json_number(s.rpe)}"
        if groups and groups[-1][1] == words:
            groups[-1][0] += 1
        else:
            groups.append([1, words])
    return ", ".join(f"{count}×{words}" for count, words in groups) or "no working sets"


def parse_sets(spec):
    """Working sets from a SPEC like "3x5@100 rpe7, 1x5@90" (a range: "3x8-10@25 rpe8")."""
    found = []
    for part in spec.split(","):
        match = _SET_SPEC.fullmatch(part)
        if not match:
            raise UsageError(f"--sets: {part.strip()!r} is not COUNTxREPS[-REPS][@LOAD][ rpeN], e.g. 3x5@100 rpe7")
        count, reps, top, load, rpe = match.groups()
        rep_range = (int(reps), int(top)) if top else None
        if rep_range and rep_range[0] > rep_range[1]:
            raise UsageError(f"--sets: {part.strip()!r} has a range that ends below its start")
        found += [base.SetSpec(type="normal", reps=None if rep_range else int(reps), rep_range=rep_range,
                               rpe=units.json_number(float(rpe)) if rpe else None,
                               load=units.json_number(float(load)) if load else None)] * int(count)
    return tuple(found)


def _on_grid(value, increment, direction, anchor):
    """`value` rounded to a whole number of increments from `anchor`, in `direction`."""
    if value >= anchor:
        return units.json_number(round(anchor + units.round_to_increment(value - anchor, increment, direction), 6))
    flipped = {"down": "up", "up": "down"}.get(direction, direction)
    return units.json_number(round(anchor - units.round_to_increment(anchor - value, increment, flipped), 6))


def _from_list(value, available, direction):
    available = sorted(available)
    if direction == "down":
        lower = [w for w in available if w <= value + 1e-9]
        return lower[-1] if lower else available[0]
    return min(available, key=lambda w: (abs(w - value), -w))


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

    def exposures(self):
        """Every exposure as a plugin sees it, newest first."""
        if self._exposures is None:
            workout_overlays = {w["workout_id"]: w["overlay_id"] for w in history.workouts(self.root)}
            found = [self._exposure(e, workout_overlays.get(e["workout_id"])) for e in history.all_exposures(self.root)]
            self._exposures = sorted(found, key=lambda e: (e.date, e.workout_id), reverse=True)
        return self._exposures

    def _exposure(self, raw, overlay_id):
        doc = self.by_id.get(overlay_id)
        prescribed = self._prescribed(doc, raw["session_id"], raw["exercise_id"], raw["date"])
        sets = tuple(base.LoggedSet(index=s["index"], type=s["type"], reps=s["reps"], rpe=s["rpe"],
                                    load=history.coaching_number(s["load"]))
                     for s in raw["sets"] if not s.get("discounted"))
        return base.Exposure(
            date=dates.parse_date(raw["date"]), workout_id=raw["workout_id"], session_id=raw["session_id"],
            exercise_id=raw["exercise_id"], load_mode=raw["load_mode"], sets=sets, suspect=raw["suspect"],
            excluded=raw["excluded"], prescribed=prescribed, week_kind=doc["kind"] if doc else None,
        )

    def _prescribed(self, doc, session_id, exercise_id, day):
        if doc is not None:
            sessions = [s for s in doc["sessions"] if s["session_id"] == session_id]
            if sessions:
                target = dates.parse_date(day)
                session = min(sessions, key=lambda s: abs((dates.parse_date(s["date"]) - target).days))
                line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)
                if line is not None:
                    return tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load")))
                                 for s in line["sets"] if overlay.is_working(s))
        slot = self.slot(session_id, exercise_id)
        return tuple(s for s in base.expand(slot["sets"]) if s.working) if slot else ()

    def slot(self, session_id, exercise_id):
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)

    def exposures_of(self, exercise_id, before):
        return tuple(e for e in self.exposures() if e.exercise_id == exercise_id and e.date < before)

    def e1rm(self, exercise_id, day):
        if self._series is None:
            self._series = stats.e1rm_series(self.root)["series"]
        start = (day - timedelta(days=validity.E1RM_WINDOW_DAYS)).isoformat()
        points = [p["e1rm"] for p in self._series.get(exercise_id, []) if start <= p["date"] < day.isoformat()]
        return max(points) if points else None

    def last_prescription(self, session_id, exercise_id):
        """This slot's line in the newest approved overlay that has it, loads as coaching numbers."""
        approved = sorted((doc for doc in self.overlays if overlay.is_approved(doc)),
                          key=lambda d: (d["created_at"], d["id"]), reverse=True)
        for doc in approved:
            sessions = sorted((s for s in doc["sessions"] if s["session_id"] == session_id),
                              key=lambda s: s["date"], reverse=True)
            for session in sessions:
                line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None)
                if line is not None:
                    return {"overlay_id": doc["id"], "session_id": session_id, "date": session["date"],
                            "exercise_id": exercise_id, "load_mode": line["load_mode"],
                            "sets": tuple(base.SetSpec.from_dict(s, load=history.coaching_number(s.get("load")))
                                          for s in line["sets"]),
                            "override": line["override"]}
        return None

    def kit(self, location):
        return config_module.equipment_for(self.config, location)

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
    try:
        from coach import statusdays
    except ImportError:
        return None
    return "an ill status day" if statusdays.ill_in(run.root, dates.Span(gap_start, gap_end)) else None


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


def _gain(older, newer):
    if newer.top_load is None or older.top_load is None:
        return False
    if newer.top_load > older.top_load + 1e-9:
        return True

    def reps_at_top(exposure):
        return sum(s.reps or 0 for s in exposure.sets if s.working and _same(s.load, exposure.top_load))
    return _same(newer.top_load, older.top_load) and reps_at_top(newer) > reps_at_top(older)


def _stalled(exposures):
    usable = [e for e in exposures if e.usable and e.week_kind != "deload"][:STALL_EXPOSURES]
    if len(usable) < STALL_EXPOSURES:
        return None
    newest, middle, oldest = usable
    if _gain(oldest, middle) or _gain(middle, newest):
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
    """One program slot through the pipeline: scheme, decay, transform, constraints, illness cap, caps, rounding, override."""
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
    slot_sets = tuple(s for s in base.expand(exercise["sets"]) if s.working)
    exposures = tuple(e if e.prescribed else replace(e, prescribed=slot_sets)
                      for e in run.exposures_of(exercise_id, day))
    active = constraints_module.active(run.root, session_id, exercise_id, day)
    days_off = validity.days_off(run.root, exercise_id, day) or 0
    info = base.ExerciseInfo(
        id=exercise_id, name=entry.get("name", exercise_id), pattern=entry.get("pattern"),
        muscles=entry.get("muscles", {}), equipment=entry.get("equipment"), load_mode=mode,
        increment=run.increment(exercise_id, location), is_compound=patterns.is_compound(entry),
        load_direction=-1 if mode == "assisted" else 1,
    )
    ctx = base.SchemeContext(
        today=run.today, session_date=day, unit=run.unit, week_kind=ctx_extra["kind"], exercise=info,
        slot=base.SlotInfo(session_id=session_id, sets=tuple(exercise["sets"]), rest_seconds=exercise["rest_seconds"],
                           cues=exercise["cues"], constraints=tuple(exercise["constraints"]),
                           start_load=exercise["start_load"]),
        params=params, state=state, exposures=exposures, e1rm=run.e1rm(exercise_id, day),
        last_prescription=run.last_prescription(session_id, exercise_id),
        last_override=decisions.last_override(run.decisions, session_id, exercise_id, run.today),
        days_off=days_off, constraints=tuple(active), scheme=scheme_name,
        scheme_deload=getattr(plugin.module, "deload", None),
    )
    proposal = plugin.module.propose(ctx)
    _check_proposal(plugin, proposal)
    clauses = [proposal.rationale.rstrip(". ")]
    adjusted = []
    line_flags += list(proposal.flags)
    source = proposal.derived_from

    decay = None
    if days_off > DECAY_AFTER_DAYS:
        band = validity.band_for(days_off)
        proposal = plugin.module.decay(ctx, proposal, days_off)
        decay = {"days_off": days_off, "band": band.id, "load_factor": band.load_factor, "set_delta": band.set_delta,
                 "rpe_cap": band.rpe_cap}
        adjusted.append(f"return band {band.id} after {days_off} days off")
        line_flags.append(line_flag("return_week", f"{days_off} days off: return band {band.id} (loads × "
                                                   f"{band.load_factor}, set change {band.set_delta}"
                                                   f"{f', RPE cap {band.rpe_cap}' if band.rpe_cap else ''})"))

    transform = ctx_extra["transform"]
    if transform is not None:
        plugin_t, transform_params = transform
        proposal = plugin_t.module.apply(replace(ctx, params=transform_params), proposal)
        adjusted.append(f"the {plugin_t.name} deload")
    newest = base.newest(exposures)
    first_after_illness = ctx_extra["illness"] is not None and day == ctx_extra["first_day"]
    try:
        cap, cap_source = cap_for(run.config, exercise_id, mode, location) if mode in units.LOADED_MODES else (None, None)
    except ConfigError:
        cap, cap_source = None, None
    references = _reference_loads(source, ctx, exercise)
    rounding = (run, entry, exercise_id, location, mode, cap, references, source)

    def limited(sets, round_down):
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
        return _rounded(sets, clipped, round_down, rounding), words

    sets, constraint_words = limited(proposal.sets, proposal.round_down)
    if first_after_illness:
        adjusted.append(f"an RPE {validity.ILLNESS_RPE_CAP} cap on the first session after illness")
    if constraint_words:
        line_flags.append(line_flag("constraint_applied", "; ".join(constraint_words)))
        adjusted += constraint_words
    if adjusted:
        clauses.append(f"adjusted for {', '.join(adjusted)}: {sets_text(sets, mode, run.unit)}")

    override = None
    last = ctx.last_override
    if last is not None and last["standing"]:
        chosen = base.Proposal(sets=tuple(base.SetSpec.from_dict(s) for s in last["chosen_sets"]), rationale="kept",
                               derived_from=source, state={})
        if decay is not None:
            chosen = plugin.module.decay(ctx, chosen, days_off)
        chosen_sets, _ = limited(chosen.sets, chosen.round_down)
        override = {"reason": last["reason"], "proposed_sets": [s.to_dict() for s in sets]}
        scheme_text = sets_text(sets, mode, run.unit)
        clauses = [f"standing override until {last['until']} ({last['reason'].rstrip('. ')}) kept as "
                   f"{sets_text(chosen_sets, mode, run.unit)} instead of the scheme's {scheme_text}"]
        line_flags.append(line_flag("override_standing", f"Standing override {last['id']} until {last['until']} "
                                                         f"kept; the scheme proposed {scheme_text}"))
        sets = chosen_sets

    line_flags += _core_flags(ctx, entry, exercise, sets, exposures, active, line_flag, mode)
    evidence_clause, evidence_flags = _evidence(run, plugin, transform, line_flag)
    line_flags += evidence_flags
    if evidence_clause:
        clauses.append(evidence_clause)

    rationale = "; ".join(c for c in clauses if c) + "."
    rationale = rationale[0].upper() + rationale[1:]
    previous = ctx.last_prescription
    draft_line = {
        "exercise_id": exercise_id,
        "hevy_template_id": entry.get("hevy_template_id") or next(iter(entry.get("hevy_template_ids") or []), None),
        "load_mode": mode, "rest_seconds": exercise["rest_seconds"], "superset_id": exercise["superset_id"],
        "cues": exercise["cues"], "focus": proposal.focus, "target_note": proposal.target_note,
        "change": change_text(previous["sets"] if previous else None, sets, mode, run.unit),
        "override": override,
        "provenance": {"scheme": scheme_name, "derived_from": source.ref() if source else None, "inferred": False,
                       "decay": decay, "rationale": rationale},
        "sets": [s.to_dict() for s in sets],
    }
    return LineResult(draft_line, line_flags, proposal.state, scheme_name)


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


def _reference_loads(source, ctx, exercise):
    """Loads already real for this slot: the derived-from load, the last approved loads, the start load."""
    found = []
    if source is not None and source.top_load is not None:
        found.append(source.top_load)
    if ctx.last_prescription:
        found += [s.load for s in ctx.last_prescription["sets"] if s.load is not None]
    if exercise["start_load"] is not None:
        found.append(exercise["start_load"])
    return found


def _rounded(sets, clipped, round_down, rounding):
    """Each load snapped to the kit: down below the derived-from load, nearest otherwise; never past a cap (C23)."""
    run, entry, exercise_id, location, mode, cap, references, source = rounding
    if mode not in units.LOADED_MODES:
        return tuple(replace(s, load=None) for s in sets)
    kit = run.kit(location)
    dumbbells = kit.get("dumbbells") or []
    by_list = entry.get("equipment") == "dumbbell" and mode in units.PER_HAND_MODES and bool(dumbbells)
    increment = run.increment(exercise_id, location)
    anchor = references[0] if references else 0
    derived = source.top_load if source is not None else None
    found = []
    for index, s in enumerate(sets):
        if s.load is None:
            found.append(s)
            continue
        value = max(0, s.load)
        down = round_down or (derived is not None and value < derived - 1e-9)
        direction = "down" if down or index in clipped else "nearest"
        if by_list:
            value = _from_list(value, dumbbells, direction)
            if cap is not None and value > cap + 1e-9:
                value = _from_list(cap, dumbbells, "down")
        elif index not in clipped and increment and not any(_same(value, r) for r in references):
            value = _on_grid(value, increment, direction, anchor)
            if cap is not None and value > cap + 1e-9:
                value = _on_grid(cap, increment, "down", anchor)
        found.append(replace(s, load=units.json_number(max(0, value))))
    return tuple(found)


def change_text(before_sets, after_sets, mode, unit):
    """"22.5/hand (Hevy: 45) → 24.5/hand (Hevy: 49)" when the top working load moved, else None."""
    if mode not in units.LOADED_MODES or not before_sets:
        return None
    before, after = base.top_load(before_sets), base.top_load(after_sets)
    if before is None or after is None or _same(before, after):
        return None
    return f"{_load_text(before, mode, unit)} → {_load_text(after, mode, unit)}"


def _core_flags(ctx, entry, exercise, sets, exposures, active, line_flag, mode):
    found = []
    if mode in units.LOADED_MODES and any(s.working and s.load is None for s in sets):
        found.append(line_flag("no_data", f"{ctx.exercise.name}: no usable exposure and no start load, so the load "
                                          "is left for the coach to set"))
    dates_stalled = _stalled(exposures)
    if dates_stalled:
        found.append(line_flag("stalled", f"{ctx.exercise.name}: no load or rep gain over the exposures of "
                                          f"{', '.join(dates_stalled)} (a coaching heuristic)"))
    newest = base.newest(exposures)
    if newest is not None:
        caps = [c["value"] for c in active if c["kind"] == "rpe_cap"]
        cap = min(caps) if caps else None
        if patterns.is_compound(entry) or cap is not None:
            prescribed = newest.prescribed or tuple(s for s in base.expand(exercise["sets"]) if s.working)
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


def _focus(kind, span, transform):
    if kind == "deload":
        return f"Deload week of {span.start.isoformat()}: {transform[0].module.SUMMARY.rstrip('.')}."
    if kind == "midweek":
        return f"Rest of the week from {span.start.isoformat()}, re-proposed."
    return f"Week of {span.start.isoformat()}: each lift as its progression scheme proposes."


def _supersedes(run, span):
    overlapping = [doc for doc in run.overlays
                   if doc["span"]["start"] <= span.end.isoformat() and span.start.isoformat() <= doc["span"]["end"]]
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
    if kind not in KINDS:
        raise UsageError(f"--kind must be one of {', '.join(KINDS)}")
    run = Run(root, config, today, now)
    settled_state, settled = settle(run.state, run.by_id)
    run.state = settled_state
    found = read_plan(run, plan_file, span) if plan_file else plan_schedule(run, span)
    if not found.sessions:
        raise ValidationError(f"The schedule plans no active session in {span.start}..{span.end}")
    transform = _transform(run, kind, transform_name)
    first_day = found.sessions[0][0]
    ctx_extra = {"kind": kind, "transform": transform, "first_day": first_day, "illness": _illness(run, first_day),
                 "states": dict(settled_state["scheme_state"])}

    draft_sessions, all_flags, scheme_state = [], list(found.flags), {}
    for day, session_id in found.sessions:
        session = run.sessions[session_id]
        if ctx_extra["illness"] and day == first_day:
            all_flags.append(flags.make("return_after_illness", session_id=session_id, message=(
                f"{ctx_extra['illness']} falls in the gap before this first session back: confirm 48 hours "
                f"symptom-free; every set is capped at RPE {validity.ILLNESS_RPE_CAP}")))
        lines = []
        for exercise in session["exercises"]:
            result = propose_line(run, session, day, exercise, ctx_extra)
            lines.append(result.draft_line)
            all_flags += result.flags
            key = f"{session_id}/{exercise['exercise_id']}"
            entry = ctx_extra["states"].get(key)
            ctx_extra["states"][key] = {"scheme": result.scheme, "data": result.state,
                                        "pending": entry.get("pending") if entry else None}
            scheme_state[key] = {"scheme": result.scheme, "data": result.state}
        draft_sessions.append({
            "session_id": session_id, "date": day.isoformat(),
            "title": f"Deload — {session['title']}" if kind == "deload" else session["title"],
            "temporary": kind == "deload", "location": session["location"], "focus": session["focus"],
            "exercises": lines,
        })

    draft = {
        "schema_version": overlay.current_version(), "kind": kind, "span": span.to_json(),
        "supersedes": _supersedes(run, span), "focus": _focus(kind, span, transform), "flags": all_flags,
        "sessions": draft_sessions,
    }
    doc = overlay.build(draft, config, root=root, now=now)
    doc["flags"] = validity.merge_flags(doc, validity.check_overlay(root, doc))
    draft = dict(draft, id=doc["id"], flags=doc["flags"])
    meta = {
        "id": doc["id"], "kind": kind, "span": span.to_json(), "transform": transform[0].name if transform else None,
        "created_at": doc["created_at"], "rotation": found.rotation,
        "scheme_state": {} if kind == "deload" else scheme_state,
    }
    if not dry_run:
        if settled:
            _write_state(root, settled_state, run.program)
        _write_proposal(root, doc["id"], draft, draft, meta)
    draft_path, proposed_path, _ = proposal_paths(root, doc["id"])
    return {
        "id": doc["id"], "kind": kind, "span": span.to_json(), "draft": _relative(root, draft_path),
        "proposed": _relative(root, proposed_path), "overlay": doc, "lines": lines_of(doc, config.athlete.units),
        "settled": settled, "rotation": found.rotation, "written": not dry_run,
    }


def _write_state(root, doc, program_doc):
    errors = state_module.problems(doc, program_doc)
    if errors:
        raise ValidationError(f"The updated {paths.STATE} is not valid ({len(errors)} problem(s))",
                              details=[e.to_json() for e in errors])
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
    originals = _lines_by_key(proposed)
    unit = config.athlete.units
    changed = []
    for session, line in _locate(draft, session_id, exercise_id):
        original = originals.get(_line_key(session, line))
        before = (line.get("override") or {}).get("proposed_sets") or (original or line)["sets"]
        current = tuple(base.SetSpec.from_dict(s) for s in line["sets"])
        if new_sets is not None:
            sets = tuple(s for s in current if not s.working) + new_sets
        else:
            sets = base.with_load(current, load)
        if line["load_mode"] not in units.LOADED_MODES and any(s.load is not None for s in sets):
            raise ValidationError(f"{exercise_id} is {line['load_mode']}, which carries no load")
        line["sets"] = [s.to_dict() for s in sets]
        line["override"] = {"reason": reason.strip(), "proposed_sets": before}
        line["change"] = change_text(tuple(base.SetSpec.from_dict(s) for s in before), sets, line["load_mode"], unit)
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


def resolve(root, proposal_id, index, resolution, dry_run):
    if not resolution or not resolution.strip():
        raise UsageError("--resolution must say how the flag is settled")
    draft, _, _ = load_proposal(root, proposal_id)
    found = draft.get("flags", [])
    if not 0 <= index < len(found):
        raise ValidationError(f"Proposal {proposal_id} has {len(found)} flag(s); --flag takes 0 to {len(found) - 1}")
    found[index] = dict(found[index], resolved=True, resolution=resolution.strip())
    if not dry_run:
        _write_proposal(root, proposal_id, draft, None, None)
    return {"id": proposal_id, "flag": found[index], "written": not dry_run}


def show(root, config, proposal_id, now):
    draft, proposed, meta = load_proposal(root, proposal_id)
    doc = overlay.build(draft, config, root=root, now=now)
    return {"id": proposal_id, "kind": meta["kind"], "span": meta["span"], "overlay": doc,
            "lines": lines_of(doc, config.athlete.units), "unexplained": unexplained_changes(draft, proposed),
            "unresolved_blocks": overlay.unresolved_blocks(doc)}


def finalize(root, config, proposal_id, now, today, dry_run):
    """Write the overlay, one-week override decisions and pending scheme state, once every change is explained (C24)."""
    draft, proposed, meta = load_proposal(root, proposal_id)
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
            f"Proposal {proposal_id} has {len(blocks)} unresolved block flag(s); settle each, or resolve it with "
            "propose resolve and a reason",
            details=[{"path": None, "message": f"{f['code']} ({f['session_id']} / {f['exercise_id']}): {f['message']}"}
                     for f in blocks])
    path = overlay.path_for(root, doc["id"])
    if path.exists() and (overlay.read_json(path) or {}).get("approval"):
        raise RefusedError(f"Overlay {doc['id']} is already approved, so finalize does not replace it; run "
                           "propose week again for a new id")

    decision_doc = decisions.load(root)
    recorded = {(d["overlay_id"], d["scope"].get("session_id"), d["scope"].get("exercise_id"))
                for d in decision_doc["decisions"] if d["kind"] == "override"}
    standing = {(d["scope"].get("session_id"), d["scope"].get("exercise_id"))
                for d in decision_doc["decisions"]
                if d["kind"] == "override" and d["standing"] and decisions.effective_status(d, today) == "active"}
    appended = []
    for session in draft["sessions"]:
        for line in session["exercises"]:
            if not line.get("override"):
                continue
            scope = (session["session_id"], line["exercise_id"])
            if (proposal_id, *scope) in recorded or scope in standing:
                continue
            record = decisions.override(_timestamp(now), doc["id"], scope[0], scope[1], line["override"]["reason"],
                                        line["override"]["proposed_sets"], line["sets"], False, doc["span"]["end"])
            decision_doc, decision = decisions.append(root, decision_doc, record, True)
            recorded.add((proposal_id, *scope))
            appended.append(decision)

    state_doc = state_module.load(root)
    pending = []
    for slot, entry in meta["scheme_state"].items():
        stored = state_doc["scheme_state"].get(slot)
        plugin_name = entry["scheme"]
        if stored is None or stored["scheme"] not in (None, plugin_name):
            plugin = plugins.load(root).get("scheme", plugin_name)
            stored = {"scheme": plugin_name, "data": plugins.initial_state(plugin), "pending": None}
        state_doc["scheme_state"][slot] = dict(stored, scheme=plugin_name,
                                               pending={"overlay_id": doc["id"], "data": entry["data"]})
        pending.append(slot)
    if meta.get("rotation"):
        rotation = dict(state_doc["rotation"])
        rotation.update(meta["rotation"])
        state_doc["rotation"] = rotation

    if not dry_run:
        jsonio.write_doc(path, doc, False)
        if appended:
            jsonio.write_doc(decisions.path_for(root), decision_doc, False)
        _write_state(root, state_doc, program.load(root))
    return {"id": doc["id"], "path": _relative(root, path), "overlay": doc, "decisions": appended,
            "pending": pending, "rotation": state_doc["rotation"], "written": not dry_run}
