"""Interference rules: the program's rules run over a span's bouts, flagging and never moving anything (contract C51).

The core decides which lifting bouts are heavy lower-body work, adds the
quality activities of the days just before the span (a session on the
span's first day is judged against them), and checks that each rule
emits only the codes it may.
"""

import math
from dataclasses import replace
from datetime import timedelta

from coach import cardio, dates, history, patterns, plugins
from coach import program as program_module
from coach.activity.store import ActivityStore
from coach.dates import Span
from coach.errors import ValidationError
from coach.library import Library
from coach.plugins import base

KIND = "interference"
FRAMEWORK_CODE = "collision"
HEAVY_PATTERNS = ("squat", "hinge")
HEAVY_RPE = 7
HEAVY_MAX_REPS = 6
WORKING_TYPES = ("normal", "dropset", "failure")
FRAMEWORK_RULES = ("same_day", "quality_before_heavy_lower")


def default_rules():
    """The framework rules with their default params, as a new program lists them."""
    registry = plugins.load()
    return [{"name": name, "params": dict(registry.get(KIND, name).module.PARAMS["defaults"])}
            for name in FRAMEWORK_RULES]


def program_rules(root):
    """The program's interference rules, or [] with no valid program."""
    doc = history.load_optional(program_module, root)
    return list(doc["interference"]) if doc else []


def listing(root):
    """The program's rules with their merged params, and every interference plugin (C51 `interference list`)."""
    registry = plugins.load(root)
    doc = history.load_optional(program_module, root)
    rules = None
    if doc is not None:
        rules = []
        for rule in doc["interference"]:
            plugin = registry.get(KIND, rule["name"])
            merged = plugins.merged_params(plugin, rule["params"])[0] if plugin else rule["params"]
            rules.append({"name": rule["name"], "params": merged, "source": plugin.source if plugin else None,
                          "summary": plugin.module.SUMMARY if plugin else None,
                          "cites": list(plugin.module.CITES) if plugin else []})
    available = [{"name": p.name, "source": p.source, "summary": p.module.SUMMARY,
                  "defaults": dict(p.module.PARAMS["defaults"]), "cites": list(p.module.CITES)}
                 for p in registry.plugins if p.kind == KIND and p.valid]
    return {"rules": rules, "available": available}


def flags(root, config, span, mode, bouts, today, overlay=None):
    """Every program rule's flags over the span's bouts (C51); [] when the program lists no rule."""
    rules = program_rules(root)
    if not rules:
        return []
    registry = plugins.load(root)
    resolved = []
    for rule in rules:
        plugin = registry.get(KIND, rule["name"])
        if plugin is None:
            raise ValidationError(f"interference rule {rule['name']} has no plugin; run python3 -m coach program "
                                  "validate")
        resolved.append((plugin, plugins.merged_params(plugin, rule["params"])[0]))
    lead = _lead_span(span, [params for _, params in resolved])
    zone = dates.zone(config["athlete"]["timezone"])
    timeline = tuple(_local(b, zone) for b in sorted(_lead_in(root, config, lead, today) + list(bouts),
                                                       key=_order))
    lines = _lift_lines(root, timeline, overlay, lead.start, span.end)
    library = Library.load(root)
    titles = _titles(root, config, timeline, overlay, Span(lead.start, span.end))
    found = []
    for plugin, params in resolved:
        heavy = frozenset(ref for ref, exercises in lines.items() if _heavy_lower(exercises, library, params))
        ctx = base.InterferenceContext(mode, span, params, timeline, heavy, titles)
        emitted = plugin.module.evaluate(ctx)
        found += _checked(plugin, emitted)
    return found


def _order(bout):
    return bout.date, bout.start.isoformat() if bout.start else "", bout.kind, bout.ref


def _local(bout, zone):
    if bout.start is None:
        return bout
    return replace(bout, start=bout.start.astimezone(zone), end=bout.end.astimezone(zone) if bout.end else None)


def _lead_span(span, params_list):
    hours = max([p.get("hours", 24) for p in params_list if isinstance(p.get("hours"), (int, float))] or [24])
    days = max(1, math.ceil(hours / 24))
    return Span(span.start - timedelta(days=days), span.start - timedelta(days=1))


def _lead_in(root, config, lead, today):
    """Quality activities in the days before the span: logged ones to today, then plans from today on."""
    found = cardio.flag_bouts(root, config, lead, today)
    return [b for b in found if b.is_activity() and b.quality]


def _lift_lines(root, timeline, overlay, start, end):
    """{lifting bout ref: [(exercise_id, sets)]} from the overlay's lines (proposal) or resolved workouts (logged)."""
    lines = {}
    if overlay is not None:
        for session in overlay.get("sessions", []):
            ref = f"{overlay['id']}/{session['session_id']}"
            lines.setdefault(ref, []).extend((line["exercise_id"], line.get("sets", []))
                                             for line in session.get("exercises", []))
    refs = {b.ref for b in timeline if b.kind == cardio.LIFTING and b.source == "logged"}
    if refs:
        for workout in history.workouts(root, start, end):
            if workout["workout_id"] in refs:
                lines[workout["workout_id"]] = [(e["exercise_id"], e["sets"]) for e in workout["exercises"]]
    return lines


def _heavy_lower(exercises, library, params):
    """True when a compound squat or hinge has a working set at RPE ≥ heavy_rpe, or reps ≤ heavy_max_reps without RPE."""
    heavy_rpe = params.get("heavy_rpe", HEAVY_RPE)
    max_reps = params.get("heavy_max_reps", HEAVY_MAX_REPS)
    for exercise_id, sets in exercises:
        entry = library.get(exercise_id) if exercise_id else None
        if not patterns.is_compound(entry) or entry.get("pattern") not in HEAVY_PATTERNS:
            continue
        for item in sets:
            if (item.get("type") or "normal") not in WORKING_TYPES:
                continue
            if item.get("rpe") is not None:
                if item["rpe"] >= heavy_rpe:
                    return True
                continue
            reps = _fewest_reps(item)
            if reps is not None and reps <= max_reps:
                return True
    return False


def _fewest_reps(item):
    if item.get("reps") is not None:
        return item["reps"]
    rep_range = item.get("rep_range")
    return rep_range.get("start") if isinstance(rep_range, dict) else None


def _titles(root, config, timeline, overlay, whole):
    doc = history.load_optional(program_module, root)
    names = {}
    if doc is not None:
        names.update({s["id"]: s["title"] for s in doc["sessions"]})
        names.update({e["id"]: e["title"] for e in doc["external_sessions"]})
    titles = {}
    for session in (overlay or {}).get("sessions", []):
        titles[f"{overlay['id']}/{session['session_id']}"] = session.get("title") or names.get(session["session_id"])
    for workout in history.workouts(root, whole.start, whole.end):
        titles[workout["workout_id"]] = workout.get("title") or names.get(workout.get("session_id"))
    if cardio.activity_on(config):
        store = ActivityStore(root, config)
        titles.update({a["id"]: a.get("name") for a in store.activities(whole)})
        titles.update({p["id"]: p.get("title") for p in store.planned(whole)})
    for bout in timeline:
        if bout.kind == cardio.EXTERNAL:
            titles.setdefault(bout.ref, names.get(bout.session_id))
    return {ref: title for ref, title in titles.items() if title}


def _checked(plugin, emitted):
    """A rule's flags, refusing any code it may not emit: `collision` for a framework rule, its own FLAGS otherwise."""
    allowed = {FRAMEWORK_CODE} if plugin.source == "framework" else set(plugin.module.FLAGS)
    if not isinstance(emitted, list):
        raise plugins.PluginError(f"interference rule {plugin.name}: evaluate must return a list of flags")
    for flag in emitted:
        code = flag.get("code") if isinstance(flag, dict) else None
        if code not in allowed:
            raise plugins.PluginError(f"interference rule {plugin.name} emitted {code!r}; it may emit only "
                                      f"{', '.join(sorted(allowed)) or 'its own custom_ codes'}")
    return emitted
