"""Conservative one-to-one activity identity: disagreement remains reviewable."""

from coach import dates

QUALITY_WORDS = ("interval", "tempo", "threshold", "hill", "fartlek", "track", "race")


def _name_quality(activity):
    name = (activity.get("name") or "").lower()
    if any(word in name for word in QUALITY_WORDS):
        return True
    if any(word in name for word in ("easy", "recovery")):
        return False
    return None


def _evidence(plan, activity, rpe_min):
    target = plan.get("target") or {}
    name = (activity.get("name") or "").strip().casefold()
    quality = _name_quality(activity)
    values = {"name": int(name != plan["title"].strip().casefold()) if name else None,
              "quality": int(quality != plan["quality"]) if quality is not None else None,
              "effort": int((activity["rpe"] >= rpe_min) != plan["quality"])
              if activity.get("rpe") is not None else None}
    for key in ("distance_meters", "duration_seconds"):
        actual, wanted = activity.get(key), target.get(key)
        values[key] = abs(actual - wanted) if actual is not None and wanted is not None else None
    return values


def _best(options, evidence, plans, activities):
    if len(options) <= 1:
        return set(options), ["unique_candidate"]
    choices, basis = set(options), []
    for key in ("name", "quality", "distance_meters", "duration_seconds"):
        values = [evidence[edge][key] for edge in options]
        if any(value is None for value in values) or len(set(values)) == 1:
            continue
        best = min(values)
        choices &= {edge for edge in options if evidence[edge][key] == best}
        basis.append(key)
    if not basis and len({plans[pi]["quality"] for pi, _ in options}) == 1:
        measured = any(evidence[edge][key] is not None for edge in options
                       for key in ("distance_meters", "duration_seconds"))
        if not measured:
            gaps = {edge: abs((dates.parse_date(plans[edge[0]]["date"])
                              - dates.parse_date(activities[edge[1]]["local_date"])).days) for edge in options}
            choices = {edge for edge in options if gaps[edge] == min(gaps.values())}
            basis = ["date_proximity"]
    return choices, basis


def resolve(plans, activities, move_days, associations, rpe_min):
    pairs, basis, plan_review, activity_review = {}, {}, {}, {}
    candidates = {(pi, ai) for pi, p in enumerate(plans) for ai, a in enumerate(activities)
                  if p["kind"] == a["kind"] and abs((dates.parse_date(p["date"])
                     - dates.parse_date(a["local_date"])).days) <= move_days}
    by_id = {p["id"]: pi for pi, p in enumerate(plans)}
    aliases = {key: ai for ai, a in enumerate(activities) for key in a.get("merged_from", [a["id"]])}
    requests = {}
    reserved_plans, reserved_activities = set(), set()
    for activity_id, planned_id in sorted(associations.items()):
        pi, ai = by_id.get(planned_id), aliases.get(activity_id)
        if pi is not None:
            reserved_plans.add(pi)
        if ai is not None:
            reserved_activities.add(ai)
        if pi is None or ai is None or (pi, ai) not in candidates:
            reason = "association has a missing record, different kind or date outside the move window"
            if pi is not None:
                plan_review[pi] = reason
            if ai is not None:
                activity_review[ai] = reason
        else:
            requests.setdefault(pi, set()).add(ai)
    for pi, wanted in requests.items():
        ai = next(iter(wanted))
        if len(wanted) != 1 or sum(ai in values for values in requests.values()) != 1:
            plan_review[pi] = "conflicting explicit associations"
            for ai in wanted:
                activity_review[ai] = "conflicting explicit associations"
    for pi, wanted in requests.items():
        ai = next(iter(wanted))
        if pi not in plan_review and ai not in activity_review:
            pairs[pi], basis[pi] = ai, ["explicit_association"]
        else:
            reason = plan_review.get(pi) or activity_review[ai]
            plan_review[pi] = activity_review[ai] = reason
    remaining = {edge for edge in candidates if edge[0] not in reserved_plans
                 and edge[1] not in reserved_activities}
    evidence = {edge: _evidence(plans[edge[0]], activities[edge[1]], rpe_min) for edge in remaining}
    contradicted = set()
    for edge, values in evidence.items():
        pi, ai = edge
        corroborated = any(values[key] == 0 for key in ("name", "distance_meters", "duration_seconds"))
        contradictory_effort = values["quality"] == 1 or values["effort"] == 1
        if contradictory_effort and plans[pi]["date"] != activities[ai]["local_date"] and not corroborated:
            contradicted.add(edge)
            plan_review[pi] = activity_review[ai] = (
                "observed effort conflicts with the moved plan; associate IDs to resolve")
    remaining -= contradicted
    while remaining:
        plan_choices = {pi: _best([edge for edge in remaining if edge[0] == pi], evidence, plans, activities)
                        for pi in {edge[0] for edge in remaining}}
        activity_choices = {ai: _best([edge for edge in remaining if edge[1] == ai], evidence, plans, activities)
                            for ai in {edge[1] for edge in remaining}}
        accepted = []
        for pi, (choices, reasons) in plan_choices.items():
            if len(choices) != 1:
                continue
            edge = next(iter(choices))
            other, other_reasons = activity_choices[edge[1]]
            if other == {edge}:
                accepted.append(edge)
                basis[pi] = sorted(set(reasons + other_reasons))
        if not accepted:
            break
        for pi, ai in accepted:
            pairs[pi] = ai
            plan_review.pop(pi, None)
            activity_review.pop(ai, None)
        used = set(pairs.values())
        remaining = {edge for edge in remaining if edge[0] not in pairs and edge[1] not in used}
    for pi, ai in remaining:
        plan_review[pi] = activity_review[ai] = "identity evidence is tied or conflicting; associate IDs to resolve"
    return pairs, basis, plan_review, activity_review, candidates
