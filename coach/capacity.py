"""Recovery context for capacity comparisons; logged progression baselines stay intact."""

from datetime import timedelta

from coach import config as config_module
from coach import dates, decisions, overlay


class Context:
    def __init__(self, root, as_of=None):
        self.as_of = as_of
        zone_name = config_module.load(root).athlete.timezone
        self.tz = dates.zone(zone_name) if zone_name else None
        self.decisions = [d for d in decisions.load(root)["decisions"] if d["outcome"] == "adopted"
                          and (as_of is None or dates.parse_timestamp(d["made_at"]) <= as_of)]
        self.overlays = [doc for doc in overlay.list(root) if overlay.is_approved(doc)
                         and (as_of is None or (dates.parse_timestamp(doc["created_at"]) <= as_of
                              and dates.parse_timestamp(doc["approval"]["approved_at"]) <= as_of))]

    def light_week(self, day, exposure=None):
        """The adopted light-week decision whose week holds `day` and that applied then (to `exposure`), or None."""
        found = None
        for decision in self.decisions:
            if decision["kind"] != "light_week":
                continue
            if not (self.applies(decision, exposure) if exposure is not None else decision["status"] != "withdrawn"):
                continue
            start = dates.parse_date(decision["details"]["week"])
            if start <= day < start + timedelta(days=7):
                found = decision
        return found

    def line_kind(self, doc, session, line):
        """`normal`, `deload`, `light` or `return` for one line of an approved overlay, as `for_exposure` reads it."""
        decision = self.light_week(dates.parse_date(session["date"]))
        return line_kind(doc, line, decision["details"]["type"] if decision else None)

    def for_exposure(self, exposure):
        context = {"kind": "normal", "overlay_id": None, "decision_id": None}
        decision = self.light_week(dates.parse_date(exposure["date"]), exposure)
        if decision is not None:
            context.update(kind=decision["details"]["type"], decision_id=decision["id"])
        if exposure.get("overlay_id"):
            doc = next((d for d in self.overlays if d["id"] == exposure["overlay_id"]), None)
        else:
            found = overlay.pick_in_force(self.overlays, exposure["date"])
            doc = found[0] if found else None
        if doc is None:
            return context
        sessions = [s for s in doc["sessions"] if s["session_id"] == exposure["session_id"]]
        if not sessions:
            return context
        session = min(sessions, key=lambda s: abs((dates.parse_date(s["date"])
                                                  - dates.parse_date(exposure["date"])).days))
        line = next((e for e in session["exercises"] if e["exercise_id"] == exposure["exercise_id"]), None)
        if line is None:
            return context
        context["overlay_id"] = doc["id"]
        context["kind"] = line_kind(doc, line, None if context["kind"] == "normal" else context["kind"])
        approved_at = dates.parse_timestamp(doc["approval"]["approved_at"])
        overrides = [d for d in self.decisions if d["kind"] == "override"
                     and d["scope"] == {"session_id": exposure["session_id"], "exercise_id": exposure["exercise_id"]}
                     and (d["overlay_id"] == doc["id"]
                          or (d["standing"] and line.get("override")
                              and dates.parse_timestamp(d["made_at"]) <= approved_at))
                     and self.applies(d, exposure)]
        chosen = max(overrides, key=lambda d: (d["made_at"], d["id"]), default=None)
        if chosen and _reduced(chosen, exposure["load_mode"]):
            context.update(kind="reduced", decision_id=chosen["id"])
        return context

    def applies(self, decision, exposure):
        if decision["status"] == "withdrawn" and decision["closed_at"]:
            closed = dates.parse_timestamp(decision["closed_at"])
            if (self.as_of is None or closed <= self.as_of) and self._before_workout(closed, exposure):
                return False
        return decision["until"] is None or exposure["date"] <= decision["until"]

    def _before_workout(self, moment, exposure):
        """Without a start time, only an earlier local day proves a withdrawal came before the workout."""
        if exposure.get("start_time"):
            return moment <= dates.parse_timestamp(exposure["start_time"])
        return moment.astimezone(self.tz).date().isoformat() < exposure["date"]


def line_kind(doc, line, light_type=None):
    """What an overlay line was for: `return` when it carries a return-band cut, else the light-week type the
    week was agreed as, else `deload` in a deload overlay, else `normal`.

    A `return` week's logged loads are the next week's progression baseline; a deload's or light week's are not.
    """
    decay = (line.get("provenance") or {}).get("decay")
    if decay and (decay["load_factor"] < 1 or decay["set_delta"] < 0 or decay["rpe_cap"] is not None):
        return "return"
    if light_type is not None:
        return light_type
    return "deload" if doc["kind"] == "deload" else "normal"


def _reduced(decision, load_mode):
    proposed = [s for s in decision["proposed_sets"] or [] if overlay.is_working(s)]
    chosen = [s for s in decision["chosen_sets"] or [] if overlay.is_working(s)]
    if not proposed or not chosen or len(chosen) > len(proposed):
        return False
    reduced = len(chosen) < len(proposed)
    for before, after in zip(proposed, chosen):
        for key in ("load", "reps", "rpe"):
            old, new = before.get(key), after.get(key)
            if old is not None and new is not None:
                if key == "load" and load_mode == "assisted":
                    old, new = -old, -new
                if new > old:
                    return False
                reduced |= new < old
    return reduced
