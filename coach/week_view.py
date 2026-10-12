"""The week beyond its lifting sessions, and the recovery items Watch shows (contract C38).

Coach-led sessions are placed as structure accounting places them (C41) and
take the status of their `external` annotation (C17). Activities take the
cardio reconcile's status (C49), which reads plans only at `[cardio] tier`
review or program, so a page, adherence and cardio give one answer. The
recovery items read niggles (C27) as they stand on the page's date, except
what each applies to, which has no history, and the block state (C43) as it
stands now.
"""

import re

from coach import block, cardio, dates, niggles, render, stats, structure
from coach import config as config_module
from coach.activity.store import ActivityStore

COACH_LED, ACTIVITY = "coach_led", "activity"
LOGGED = "logged"
NIGGLE_STATUSES = ("aggravated", "watching", "easing")
CLOSED_STATUSES = (None, "resolved")
NIGGLE_FLAGS = ("niggle_link", "niggle_escalate")
SLEEP_FLAGS = ("sleep_debt",)
SLEEP_KEY = "sleep"
LIGHT_WEEK_KEY = "light_week"
# Lower sorts first: overlay `block` flags are 20 and `warn` flags 30 (C38).
PRIORITY = {"aggravated": 22, "light_week_proposed": 24, "watching": 26, "easing": 26, "fatigue_watch": 27,
            "light_week_declined": 28, "light_week_skipped": 35, "chronic": 45}
# This week's own `sleep_debt` reading replaces the sleep watch from the last closed week, whatever their order.
FLAG_FIRST_KEYS = (SLEEP_KEY,)
TRIGGER_WORDS = {"readiness": "poor readiness", "rpe_drift": "RPE drift on a compound lift",
                 "niggle": "an aggravated niggle", "sleep": "poor sleep"}
PROPOSED_BECAUSE = {"ceiling": "{hard_weeks} completed hard weeks reach the ceiling",
                    "triggers": "two fatigue triggers fired", "illness": "an illness week was under half trained",
                    "coach": "the coach called it"}
_NIGGLE_ID = re.compile(r"^Niggle (n-\d+) \(")
_ORDER = {COACH_LED: 1, ACTIVITY: 2}


def niggle_key(niggle_id):
    return f"niggle:{niggle_id}"


def coach_led(root, span, today, as_of=None):
    """One row per coach-led session the week places, with its annotated status; none on a planned break."""
    found = []
    for row, note in structure.coach_led(root, span, today=today, as_of=as_of):
        if row["status"] == stats.ON_BREAK:
            continue
        item = {"type": COACH_LED, "date": row["date"], "id": row["external_id"], "kind": None,
                "title": row["title"], "status": row["status"], "moved_to": None, "quality": None,
                "quality_basis": None, "minutes": None, "rpe": None, "distance_meters": None,
                "reason": (row.get("cancellation") or {}).get("reason")}
        if note is not None:
            item.update(kind=note.get("modality"), minutes=note.get("duration_minutes"), rpe=note.get("rpe"))
            if note["date"] != row["date"]:
                item["moved_to"] = note["date"]
        found.append(item)
    return found


def activities(root, span, today):
    """One row per planned or logged activity in the week, a matched pair as one row on the planned date.

    At tier review or program the rows are the cardio reconcile's items, a duplicate plan left out; at tier count no
    plan is read, so only logged activities show, each as `logged`.
    """
    config = config_module.load(root)
    if not cardio.activity_on(config):
        return []
    if not cardio.plans_read(config):
        rpe_min = config["cardio"]["quality_rpe_min"]
        return [_logged_row(act, rpe_min) for act in ActivityStore(root, config).activities(span)]
    return [_reconciled_row(item, span) for item in cardio.reconcile(root, span, today)["items"]
            if item["status"] != "duplicate"]


def _logged_row(act, rpe_min):
    quality, basis = cardio.quality_of(act, None, rpe_min)
    return {"type": ACTIVITY, "date": act["local_date"], "id": act["id"], "kind": act["kind"],
            "title": act.get("name"), "status": LOGGED, "moved_to": None, "quality": quality,
            "quality_basis": basis, "minutes": _minutes(act.get("duration_seconds")), "rpe": None,
            "distance_meters": act.get("distance_meters"), "reason": None}


def _reconciled_row(item, span):
    planned_in = span.contains(dates.parse_date(item["date"]))
    actual = item["actual"]
    target = item["target"] or {}
    return {"type": ACTIVITY, "date": item["date"] if planned_in else item["activity_date"],
            "id": item["planned_id"] or item["activity_id"], "kind": item["kind"], "title": item["title"],
            "status": LOGGED if item["status"] == "extra" else item["status"],
            "moved_to": item["activity_date"] if item["status"] == "moved" else None, "quality": item["quality"],
            "quality_basis": item["quality_basis"] or ("planned" if item["planned_id"] else None),
            "minutes": _minutes(actual["duration_seconds"] if item["activity_id"] else target.get("duration_seconds")),
            "distance_meters": actual["distance_meters"] if item["activity_id"] else target.get("distance_meters"),
            "rpe": None, "reason": item["review_reason"]}


def _minutes(seconds):
    return None if seconds is None else round(seconds / 60)


def rows(root, span, today, as_of=None):
    """Coach-led sessions, then activities, for each day of the week, by date."""
    found = coach_led(root, span, today, as_of) + activities(root, span, today)
    return sorted(found, key=lambda r: (r["date"], _ORDER[r["type"]], r["title"] or "", r["id"]))


def flag_keys(flag):
    """What an overlay flag is about, for telling it from an equivalent Watch item: a niggle, or sleep."""
    if flag["code"] in NIGGLE_FLAGS:
        found = _NIGGLE_ID.match(flag["message"])
        return (niggle_key(found.group(1)),) if found else ()
    if flag["code"] in SLEEP_FLAGS:
        return (SLEEP_KEY,)
    return ()


def open_niggle_ids(root, today):
    """The niggles noted by `today` and not resolved on it, chronic ones included."""
    if not niggles.exists(root):
        return set()
    return {row["id"] for row in niggles.load(root)["niggles"]
            if niggles.status_on(row, today) not in CLOSED_STATUSES}


def is_current(flag, open_ids):
    """False for a stored niggle flag whose niggle is resolved, or not yet noted, on the page's date."""
    keys = flag_keys(flag)
    return not (flag["code"] in NIGGLE_FLAGS and keys and keys[0][len("niggle:"):] not in open_ids)


def niggle_watch(root, today):
    """(key, text, priority) for each niggle aggravated, watching or easing on `today`, and each chronic one whose
    limits are in force on it."""
    if not niggles.exists(root):
        return []
    found = []
    for row in niggles.load(root)["niggles"]:
        status = niggles.status_on(row, today)
        if status == "chronic":
            if niggles.constraints_on(row, today):
                found.append((niggle_key(row["id"]), f"{row['area'].capitalize()} niggle (chronic): its limits "
                                                     "apply to this week's loads.", PRIORITY["chronic"]))
            continue
        if status not in NIGGLE_STATUSES:
            continue
        since = _status_since(row, today)
        text = f"{row['area'].capitalize()} niggle ({status} since {render.short_date(since)})"
        reason = niggles.escalation(dict(row, status=status, history=_history_to(row, today)))
        if reason:
            text += (f": {reason}. Have it assessed by a qualified professional (a doctor or physiotherapist); "
                     "the program works around it meanwhile")
        else:
            applies = _applies_words(row)
            limits = " Its limits apply to this week's loads." if niggles.constraints_on(row, today) else ""
            text += f": tell the coach how it responds{applies}.{limits}"
        found.append((niggle_key(row["id"]), text.rstrip(".") + ".", PRIORITY["aggravated" if reason else status]))
    return found


def _history_to(row, today):
    return [e for e in row["history"] if e["date"] <= today.isoformat()]


def _status_since(row, today):
    entries = _history_to(row, today)
    since = entries[-1]["date"]
    for entry in reversed(entries):
        if entry["status"] != entries[-1]["status"]:
            break
        since = entry["date"]
    return since


def _applies_words(row):
    applies = row["applies_to"]
    parts = [f"{kind}s" for kind in applies["activity_kinds"]]
    parts += [pattern.replace("_", " ") for pattern in applies["patterns"]]
    parts += [exercise.replace("_", " ") for exercise in applies["exercises"]]
    return f" to {_joined(parts)}" if parts else ""


def _joined(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def block_watch(root):
    """(key, text, priority) for the block's current fatigue watch and light-week state (C43)."""
    facts = block.watch_facts(root)
    if facts is None:
        return []
    light, triggers = facts["light_week"], facts["triggers"]
    found = []
    if light["status"] == "watch" and triggers:
        words = _trigger_words(triggers[0], facts["signals"])
        week = f" in the week of {render.short_date(facts['week'])}" if facts["week"] else ""
        sleep = triggers[0] == "sleep"
        found.append((SLEEP_KEY if sleep else "fatigue_watch",
                      f"Fatigue watch: {words}{week}. Tell the coach how you recover this week.",
                      PRIORITY["fatigue_watch"]))
    elif light["status"] == "proposed":
        when = f" for the week of {render.short_date(light['week'])}" if light["week"] else ""
        because = PROPOSED_BECAUSE.get(light["reason"], "").format(hard_weeks=facts["hard_weeks"])
        found.append((LIGHT_WEEK_KEY, f"Light week proposed{when}: a {light['type'] or 'deload'} week"
                      + (f", because {because}" if because else "") + ". Decide it with the coach at the check-in.",
                      PRIORITY["light_week_proposed"]))
    elif light["status"] == "declined":
        decision = facts["decision"]
        reason = f": {decision['reason']}" if decision else ""
        again = " It is proposed again at the next check-in." if light["reason"] == "ceiling" else ""
        found.append((LIGHT_WEEK_KEY, f"Light week declined{reason}.{again}", PRIORITY["light_week_declined"]))
    elif light["status"] == "skipped" and triggers:
        names = _joined([_trigger_words(t, facts["signals"]) for t in triggers])
        found.append((LIGHT_WEEK_KEY, f"Two fatigue triggers ({names}) with {facts['hard_weeks']} completed hard "
                                      "weeks, too few for a light week: watch how you recover this week.",
                      PRIORITY["light_week_skipped"]))
    return found


def _trigger_words(trigger, signals):
    words = TRIGGER_WORDS[trigger]
    if trigger == "sleep" and signals and signals.get("sleep_source") == "override" and signals.get("sleep_reason"):
        words += f" ({signals['sleep_reason']})"
    return words
