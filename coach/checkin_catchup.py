"""Catch-up mode: the card after a long gap, one tag for the gap, and the return brief (contract C36).

After more than `CATCH_UP_AFTER_DAYS` without a check-in the card stops
asking about each session. It shows one summary row per week, asks three
questions and carries the proposed return week, so one "ok" settles the
check-in. The return brief is the coach's brief for the week back,
whatever caused the gap: illness and layoffs from a proposal, travel and
no kit from a coach-built one-off overlay.
"""

from datetime import timedelta

from coach import dates, history, overlay, propose, render, validity
from coach.errors import CoachError, UsageError
from coach.library import Library

REASONS = ("ill", "travel", "no_kit", "layoff")
_REASON_TEXT = {"ill": ", through illness", "travel": ", travelling", "no_kit": ", without kit", "layoff": ""}
QUESTION_LABELS = {"gap": "The gap", "now": "Now", "next_week": "Next week"}
REPLY_OK = "Reply ok to accept all of this, or answer 1–3."
_MISS_TAG_TEXT = " / ".join(history.MISS_TAGS)


def _day(value):
    return dates.parse_date(value) if isinstance(value, str) else value


def schedule_plan(inst, span, today):
    """The schedule rule's plan for `span` (C23), or None when the program cannot be planned."""
    if not inst.program or not inst.state:
        return None
    try:
        run = propose.Run(inst.root, inst.config, today, None)
        return propose.plan_schedule(run, span)
    except CoachError:
        return None


def rotation_text(inst, end):
    """The rotation line for next week, from the schedule rule's inferred position (`schedule plan`)."""
    week = dates.week_span(end + timedelta(days=1), inst.config.athlete.week_starts)
    plan = schedule_plan(inst, week, end)
    rotation = plan.rotation if plan is not None else (inst.state or {}).get("rotation")
    if not rotation or not rotation.get("position"):
        return None
    status = "confirmed" if rotation.get("confirmed") else "inferred from the schedule rule, not confirmed"
    return f"Rotation: next week is {rotation['position']} ({status}); correct me if not."


def _session_of(workout, routines):
    if workout.get("session_id"):
        return workout["session_id"]
    mapped = routines.get(workout.get("routine_id") or "")
    return mapped.get("session_id") if mapped else None


def _covered(inst, window):
    return {day for day in window.days() if overlay.pick_in_force(inst.overlays, day)}


def planned(inst, window, overlay_rows, workouts, today):
    """Every planned session in the window: the card's C18 rows where an overlay is in force, else the
    schedule rule's plan, each matched to a workout of its session in the same week."""
    covered = _covered(inst, window)
    rows = [dict(row, planned_from="overlay") for row in overlay_rows]
    open_days = [day for day in window.days() if day not in covered]
    plan = schedule_plan(inst, window, today) if open_days else None
    if plan is None:
        return sorted(rows, key=lambda r: (r["date"], r["session_id"])), covered
    week_starts = inst.config.athlete.week_starts
    routines = (inst.state or {}).get("hevy", {}).get("routines", {})
    sessions = {s["id"]: s for s in inst.program["sessions"]}

    def week_of(day):
        return dates.week_span(_day(day), week_starts).start

    scheduled = [(day, sid) for day, sid in plan.sessions if day not in covered]
    candidates = [w for w in workouts if _day(w["date"]) in open_days]
    pairs = [(abs((_day(w["date"]) - day).days), w["date"], index, w["workout_id"])
             for index, (day, sid) in enumerate(scheduled) for w in candidates
             if _session_of(w, routines) == sid and week_of(w["date"]) == week_of(day)]
    matched, used = {}, set()
    for _, _, index, workout_id in sorted(pairs):
        if index not in matched and workout_id not in used:
            matched[index] = workout_id
            used.add(workout_id)

    unlogged = [a for a in history.annotations(inst.root, "trained_unlogged") if _day(a["date"]) in open_days]
    misses = [a for a in history.annotations(inst.root, "miss") if _day(a["date"]) in open_days]
    taken = set()

    def nearest(notes, day, sid):
        found = [a for a in notes if a["session_id"] == sid and a["id"] not in taken
                 and week_of(a["date"]) == week_of(day)]
        note = min(found, key=lambda a: (abs((_day(a["date"]) - day).days), a["date"]), default=None)
        if note is not None:
            taken.add(note["id"])
        return note

    for index, (day, sid) in enumerate(scheduled):
        session = sessions[sid]
        row = {"date": day.isoformat(), "session_id": sid, "title": session["title"], "tier": session["tier"],
               "status": "missed", "tag": None, "workout_id": matched.get(index), "planned_from": "schedule"}
        if index in matched or nearest(unlogged, day, sid) is not None:
            row["status"] = "trained"
        elif session["tier"] == "optional":
            continue
        else:
            note = nearest(misses, day, sid)
            row["tag"] = (note.get("tag") if note else None) or "untagged"
        rows.append(row)
    return sorted(rows, key=lambda r: (r["date"], r["session_id"])), covered


def summary(inst, window, rows, covered, workouts, external):
    """One row per week in the window (C7 weeks): core planned and trained, misses by tag, optional sessions
    trained, coach-led sessions recorded done, workouts logged, and where the plan came from."""
    week_starts = inst.config.athlete.week_starts
    found = []
    start = window.start
    while start <= window.end:
        week = dates.week_span(start, week_starts)
        span = dates.Span(max(week.start, window.start), min(week.end, window.end))
        inside = [r for r in rows if span.contains(_day(r["date"]))]
        core = [r for r in inside if r["tier"] == "core"]
        missed = {}
        for tag in history.MISS_TAGS + ("untagged",):
            count = sum(1 for r in core if r["status"] == "missed" and (r["tag"] or "untagged") == tag)
            if count:
                missed[tag] = count
        days = span.days()
        held = sum(1 for day in days if day in covered)
        recorded = [e for e in external if span.contains(_day(e["date"])) and e["done"] is not None]
        found.append({
            "week": week.label(), "start": week.start.isoformat(),
            "planned_core": len(core), "trained_core": sum(1 for r in core if r["status"] == "trained"),
            "missed_by_tag": missed,
            "optional_trained": sum(1 for r in inside if r["tier"] == "optional" and r["status"] == "trained"),
            "external_done": sum(1 for e in recorded if e["done"]) if recorded else None,
            "workouts": sum(1 for w in workouts if span.contains(_day(w["date"]))),
            "planned_from": "overlay" if held == len(days) else "schedule" if held == 0 else "mixed",
        })
        start = week.end + timedelta(days=1)
    return found


def questions(rotation):
    gap = (f"One tag for the whole gap ({_MISS_TAG_TEXT}), or one per session if it was mixed. If you were ill: "
           f"have you been {validity.SYMPTOM_FREE_HOURS} hours symptom-free?")
    now = "Anything hurting, or different about kit, travel or schedule?"
    next_week = "Which days can you train next week?" + (f" {rotation}" if rotation else "")
    return [{"id": "gap", "n": 1, "ask": gap}, {"id": "now", "n": 2, "ask": now},
            {"id": "next_week", "n": 3, "ask": next_week}]


def write_line(config, doc):
    """R-03's closing line for a week built from `doc`: every session's routine, or no Hevy."""
    if not config.hevy.enabled:
        return 'Reply "go" to train this. Nothing goes to Hevy (no Hevy).'
    titles = list(dict.fromkeys(s["title"] for s in doc["sessions"]))
    return f'Reply "go" to train this and write: {", ".join(titles)} (Hevy).'


def _days_off(root, doc):
    first = min(_day(s["date"]) for s in doc["sessions"])
    last = history.last_lifting_date(root, first)
    return (first - last).days if last is not None else None


def _names(library, doc):
    for session in doc["sessions"]:
        yield session["session_id"], session["title"]
        for line in session["exercises"]:
            yield line["exercise_id"], (library.get(line["exercise_id"]) or {}).get("name", line["exercise_id"])


def _sessions(library, doc, lines, band, illness):
    by_session = {}
    for line in lines:
        entry = library.get(line["exercise_id"]) or {}
        by_session.setdefault((line["session_id"], line["date"]), []).append(
            f"{entry.get('name', line['exercise_id'])} {line['text']}")
    found = []
    for index, session in enumerate(sorted(doc["sessions"], key=lambda s: (s["date"], s["session_id"]))):
        caps = [cap for cap in (band.rpe_cap if band else None,
                                validity.ILLNESS_RPE_CAP if illness and index == 0 else None) if cap is not None]
        found.append({"date": session["date"], "session_id": session["session_id"], "title": session["title"],
                      "rpe_cap": min(caps) if caps else None,
                      "lines": by_session.get((session["session_id"], session["date"]), [])})
    return found


def return_week(inst, today, now):
    """(return week, problem): `propose week --dry-run` for the week holding tomorrow, summarised (C36)."""
    span = propose.resolve_span(inst.config, today)
    try:
        data = propose.propose_week(inst.root, inst.config, today, now, span, dry_run=True)
    except CoachError as exc:
        return None, str(exc)
    doc = data["overlay"]
    days_off = _days_off(inst.root, doc)
    band = validity.band_for(days_off) if days_off is not None else None
    illness = any(f["code"] == "return_after_illness" for f in doc["flags"])
    return {
        "proposal_id": data["id"], "overlay_id": doc["id"], "week": span.label(), "span": span.to_json(),
        "band": band.id if band else None, "days_off": days_off,
        "load_factor": band.load_factor if band else None, "set_delta": band.set_delta if band else None,
        "rpe_cap": band.rpe_cap if band else None,
        "sessions": _sessions(inst.library, doc, data["lines"], band, illness),
        "flags": doc["flags"], "lines_digest": data["lines_digest"],
        "names": dict(_names(inst.library, doc)),
    }, None


def build(inst, card, window, end, today, now, live, workouts):
    """The card's `catch_up` object; the return week only on a live card (the record region has none)."""
    rows, covered = planned(inst, window, card["sessions"]["rows"], workouts, today)
    found = {
        "layoff_days": card["days_since_last"],
        "summary": summary(inst, window, rows, covered, workouts, card["sessions"]["external"]),
        "missed": [{"date": r["date"], "session_id": r["session_id"], "title": r["title"], "tag": r["tag"]}
                   for r in rows if r["tier"] == "core" and r["status"] == "missed"],
        "questions": questions(rotation_text(inst, end)),
        "return_week": None, "return_week_problem": None, "write_line": None,
    }
    if live:
        week, problem = return_week(inst, today, now)
        found.update(return_week=week, return_week_problem=problem)
        if week is not None:
            found["write_line"] = write_line(inst.config, {"sessions": week["sessions"]})
    return found


def _effects(band):
    """A band's change in plain words, from the numbers in coach.validity."""
    words = []
    if band.load_factor != 1:
        words.append(f"loads −{round((1 - band.load_factor) * 100)} %")
    if band.set_delta:
        words.append("one working set fewer per exercise" if band.set_delta == -1
                     else f"{-band.set_delta} working sets fewer per exercise")
    if band.rpe_cap is not None:
        words.append(f"every set at RPE {band.rpe_cap} or below")
    if band.retest:
        words.append("a re-test: next week's loads come from what this week logs")
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _band_sentence(days_off, band):
    if band is None:
        return "no lifting workout is on record, so no return band applies."
    if band.id == validity.RETURN_BANDS[0].id:
        return f"{days_off} days off is inside the first return band ({band.id}), so loads carry on as planned."
    return f"return band {band.id} after {days_off} days off, so {_effects(band)}."


def _week_line(week):
    lines = [f"Return week from {render.day_label(week['sessions'][0]['date'])}: "
             + _band_sentence(week["days_off"], _band(week))]
    for session in week["sessions"]:
        cap = f" (RPE cap {session['rpe_cap']})" if session["rpe_cap"] is not None else ""
        lines.append(f"- {render.day_label(session['date'])} {session['title']}{cap}: "
                     + " · ".join(session["lines"]))
    return lines


def _band(week):
    return next((b for b in validity.RETURN_BANDS if b.id == week["band"]), None)


def _flags_line(flags, names):
    found = {}
    for flag in flags:
        if flag["code"] == "return_week":
            continue
        found.setdefault(flag["code"], [])
        where = names.get(flag["exercise_id"] or flag["session_id"], flag["exercise_id"] or flag["session_id"])
        if where and where not in found[flag["code"]]:
            found[flag["code"]].append(where)
    if not found:
        return None
    return "Flags: " + "; ".join(f"`{code}`" + (f" ({', '.join(where)})" if where else "")
                                 for code, where in found.items()) + "."


def _cell(value):
    return "" if value is None else str(value).replace("|", "\\|")


def summary_table(card):
    """The weekly summary as a markdown table (the message and the record region share it)."""
    catch_up = card["catch_up"]
    external = bool(card["sessions"]["external"])
    optional = any(row["optional_trained"] for row in catch_up["summary"])
    head = ["Week of", "Core trained", "Missed"] + (["Optional"] if optional else []) \
        + (["Coach-led done"] if external else []) + ["Workouts"]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    for row in catch_up["summary"]:
        missed = ", ".join(f"{tag} {n}" for tag, n in row["missed_by_tag"].items()) or "none"
        cells = [render.short_date(row["start"]), f"{row['trained_core']} of {row['planned_core']}", missed]
        if optional:
            cells.append(row["optional_trained"])
        if external:
            cells.append("—" if row["external_done"] is None else row["external_done"])
        cells.append(row["workouts"])
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    if any(row["planned_from"] != "overlay" for row in catch_up["summary"]):
        lines += ["", "Weeks with no overlay in force are planned from the schedule rule."]
    return lines


def text_lines(card, first_line):
    """The catch-up message: the weeks at a glance, the return week, three questions, the write line."""
    catch_up = card["catch_up"]
    lines = [first_line, ""] + summary_table(card)
    if card["facts"]:
        lines += [""] + [f"- {fact}" for fact in card["facts"]]
    week = catch_up["return_week"]
    lines.append("")
    if week is not None:
        lines += _week_line(week)
        flags_line = _flags_line(week["flags"], week["names"])
        if flags_line:
            lines += ["", flags_line]
    else:
        lines.append(f"No return week could be proposed: {catch_up['return_week_problem']}")
    lines.append("")
    for question in catch_up["questions"]:
        lines.append(f"{question['n']}. {QUESTION_LABELS[question['id']]}. {question['ask']}")
    lines.append("")
    if catch_up["write_line"]:
        lines += [catch_up["write_line"], REPLY_OK]
    else:
        lines.append("Answer 1–3.")
    return lines


def region_lines(card):
    """The catch-up record's week-review body: header, the missed line and the weekly table."""
    catch_up = card["catch_up"]
    window = card["window"]
    trained = sum(row["trained_core"] for row in catch_up["summary"])
    planned_core = sum(row["planned_core"] for row in catch_up["summary"])
    missed = ", ".join(f"{render.day_label(m['date'])} {m['title']} ({m['tag']})" for m in catch_up["missed"])
    return [f"**Window:** {window['start']} → {window['end']} · **Sessions:** {trained} of {planned_core} core · "
            f"**Missed:** {missed or 'none'}", ""] + summary_table(card)


def tag_gap(root, card, tag, now, dry_run=False):
    """One `miss` annotation per untagged missed core session in the card's window (C36)."""
    if tag not in history.MISS_TAGS:
        raise UsageError(f"--tag must be one of {', '.join(history.MISS_TAGS)}")
    source = f"checkin tag-gap {card['date']}"
    items = [{"kind": "miss", "date": m["date"], "session_id": m["session_id"], "tag": tag, "source": source,
              "reason": None} for m in card["catch_up"]["missed"] if m["tag"] == "untagged"]
    added = history.add_annotations(root, items, now, dry_run) if items else []
    return {"tag": tag, "window": card["window"], "annotations": added, "written": bool(added) and not dry_run}


def return_brief(root, config, now, proposal_id=None, overlay_id=None, reason="layoff"):
    """The return template of the coach's brief, from a proposal or a coach-built overlay. Reads only."""
    if reason not in REASONS:
        raise UsageError(f"--reason must be one of {', '.join(REASONS)}")
    if proposal_id is not None:
        shown = propose.show(root, config, proposal_id, now)
        doc, lines = shown["overlay"], shown["lines"]
    else:
        doc = overlay.load(root, overlay_id)
        lines = propose.lines_of(doc, config.athlete.units)
    days_off = _days_off(root, doc)
    band = validity.band_for(days_off) if days_off is not None else None
    ill = reason == "ill"
    sessions = _sessions(Library.load(root), doc, lines, band, ill)
    first = sessions[0]["date"]
    last = history.last_lifting_date(root, _day(first))

    if days_off is None:
        gap = f"No lifting workout is on record before {render.day_label(first)}."
    else:
        gap = (f"{days_off} days off since your last lifting workout on {render.day_label(last)}"
               f"{_REASON_TEXT[reason]}.")
    clause = _band_sentence(days_off, band)
    returning = band is not None and band.id != validity.RETURN_BANDS[0].id
    week = f"This is a return week: {clause}" if returning else clause[0].upper() + clause[1:]
    if ill:
        week += f" The first session back caps every set at RPE {validity.ILLNESS_RPE_CAP}."
    text = [f"**The gap.** {gap}", "", f"**This week.** {week}"]
    if ill:
        text += ["", f"**Before you train.** Train only once you have been {validity.SYMPTOM_FREE_HOURS} hours "
                     "symptom-free. Fever, chest symptoms or a slow recovery mean checking with a qualified "
                     "professional before training again."]
    text += ["", "**Sessions**"]
    for session in sessions:
        cap = f" (RPE cap {session['rpe_cap']})" if session["rpe_cap"] is not None else ""
        text += ["", f"{render.day_label(session['date'])} — {session['title']}{cap}"]
        text += [f"- {line}" for line in session["lines"]]
    text += ["", "**After this week.** Normal progression resumes from the loads you log this week.", "",
             write_line(config, doc)]
    warnings = []
    if ill and _uncapped(doc):
        warnings.append(f"the first session has working sets without an RPE at or under "
                        f"{validity.ILLNESS_RPE_CAP}; record the ill misses (checkin tag-gap --tag ill) and "
                        "propose the week again")
    return {"source": {"proposal": proposal_id, "overlay": overlay_id}, "reason": reason, "days_off": days_off,
            "band": band.id if band else None, "sessions": sessions, "warnings": warnings,
            "text": "\n".join(text) + "\n"}


def _uncapped(doc):
    first = min(doc["sessions"], key=lambda s: (s["date"], s["session_id"]))
    return any(s.get("rpe") is None or s["rpe"] > validity.ILLNESS_RPE_CAP
               for line in first["exercises"] for s in line["sets"] if overlay.is_working(s))
