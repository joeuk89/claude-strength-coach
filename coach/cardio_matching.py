"""Conservative one-to-one activity identity: disagreement remains reviewable."""

from typing import NamedTuple

from coach import dates

QUALITY_WORDS = ("interval", "tempo", "threshold", "hill", "fartlek", "track", "race")
IDENTITY_KEYS = ("name", "quality", "distance_meters", "duration_seconds")


def _name_quality(activity):
    name = (activity.get("name") or "").lower()
    if any(word in name for word in QUALITY_WORDS):
        return True
    if any(word in name for word in ("easy", "recovery")):
        return False
    return None


def _planned_quality(plan):
    return True if plan["kind"] == "conditioning" else bool(plan["quality"])


def _evidence(plan, activity, rpe_min):
    target = plan.get("target") or {}
    name = (activity.get("name") or "").strip().casefold()
    planned_quality = _planned_quality(plan)
    quality = _name_quality(activity)
    effort = activity["rpe"] >= rpe_min if activity.get("rpe") is not None else None
    if activity["kind"] == "conditioning":
        quality = effort = True
    values = {"name": int(name != plan["title"].strip().casefold()) if name else None,
              "quality": int(quality != planned_quality) if quality is not None else None,
              "effort": int(effort != planned_quality) if effort is not None else None}
    for key in ("distance_meters", "duration_seconds"):
        actual, wanted = activity.get(key), target.get(key)
        values[key] = abs(actual - wanted) if actual is not None and wanted is not None else None
    return values


def _narrow(options, evidence, keys):
    choices, basis = set(options), []
    for key in keys:
        values = [evidence[edge][key] for edge in options]
        if any(value is None for value in values) or len(set(values)) == 1:
            continue
        choices &= {edge for edge in options if evidence[edge][key] == min(values)}
        basis.append(key)
    return choices, basis


def _identify(options, evidence):
    """Every identity measure must agree; logged effort only splits what they leave tied."""
    if len(options) == 1:
        return set(options), ["unique_candidate"]
    choices, basis = _narrow(options, evidence, IDENTITY_KEYS)
    if len(choices) > 1:
        choices, effort = _narrow(choices, evidence, ("effort",))
        basis += effort
    return choices, basis


def _nearest(choices, basis, gaps):
    if len(choices) <= 1:
        return choices, basis
    closest = min(gaps[edge] for edge in choices)
    nearest = {edge for edge in choices if gaps[edge] == closest}
    return nearest, basis + ["date_proximity"] if len(nearest) < len(choices) else basis


def _first(choices, basis, key):
    if len(choices) <= 1:
        return choices, basis
    return {min(choices, key=key)}, basis + ["order"]


def _choose(remaining, evidence, plans, activities, gaps):
    """Each plan's and each activity's preferred edges for one round of mutual matching.

    Where every tied plan has one quality, no quality can transfer, so ties settle by date, then
    order. A plan whose candidates all identify with its quality pool, and fit in it, takes the
    nearest date before identity, so distance noise cannot pull identical plans onto each other's
    runs.
    """
    by_plan, by_activity = {}, {}
    for edge in remaining:
        by_plan.setdefault(edge[0], []).append(edge)
        by_activity.setdefault(edge[1], []).append(edge)
    identified = {ai: _identify(edges, evidence) for ai, edges in by_activity.items()}
    activity_choices = {}
    for ai, (choices, basis) in identified.items():
        if len({_planned_quality(plans[pi]) for pi, _ in choices}) == 1:
            choices, basis = _first(*_nearest(choices, basis, gaps),
                                    key=lambda edge: (plans[edge[0]]["date"], plans[edge[0]]["id"]))
        activity_choices[ai] = choices, basis
    plan_choices = {}
    for pi, edges in by_plan.items():
        quality = _planned_quality(plans[pi])
        members = {edge for edge in edges if edge in identified[edge[1]][0]
                   and all(_planned_quality(plans[p]) == quality for p, _ in identified[edge[1]][0])}
        pool = {p for edge in members for p, _ in identified[edge[1]][0]}
        if members and len(members) <= len(pool):
            choices, basis = _nearest(members, [], gaps)
            if len(choices) > 1:
                choices, split = _identify(choices, evidence)
                basis += split
            plan_choices[pi] = _first(choices, basis, key=lambda edge: _activity_order(activities[edge[1]]))
        else:
            plan_choices[pi] = _nearest(*_identify(edges, evidence), gaps)
    return plan_choices, activity_choices


def _activity_order(activity):
    return activity["local_date"], activity["start"], activity["id"]


def _session(plan):
    return plan["date"], plan["kind"], _planned_quality(plan)


class Resolution(NamedTuple):
    pairs: dict
    basis: dict
    plan_review: dict
    activity_review: dict
    candidates: set
    duplicates: dict


def resolve(plans, activities, move_days, associations, rpe_min):
    pairs, basis, plan_review, activity_review = {}, {}, {}, {}
    plan_days = [dates.parse_date(p["date"]) for p in plans]
    activity_days = [dates.parse_date(a["local_date"]) for a in activities]
    gaps = {(pi, ai): abs((plan_days[pi] - activity_days[ai]).days)
            for pi, p in enumerate(plans) for ai, a in enumerate(activities) if p["kind"] == a["kind"]}
    candidates = {edge for edge, gap in gaps.items() if gap <= move_days}
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
    sessions, duplicates = {}, {}
    for pi in sorted(range(len(plans)), key=lambda i: plans[i]["id"]):
        sessions.setdefault(_session(plans[pi]), []).append(pi)

    def claim_twins(matched):
        """Per other source, the first free plan for a matched plan's session: one session planned twice."""
        for pi in sorted(matched, key=lambda i: plans[i]["id"]):
            claimed = {plans[pi].get("source")}
            for other in sessions[_session(plans[pi])]:
                source = plans[other].get("source")
                if source not in claimed and not (other in pairs or other in reserved_plans or other in duplicates):
                    duplicates[other] = pi
                    claimed.add(source)

    claim_twins(pairs)
    remaining = {edge for edge in candidates if edge[0] not in reserved_plans | set(duplicates)
                 and edge[1] not in reserved_activities}
    evidence = {edge: _evidence(plans[edge[0]], activities[edge[1]], rpe_min) for edge in remaining}
    while remaining:
        plan_choices, activity_choices = _choose(remaining, evidence, plans, activities, gaps)
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
        claim_twins(pi for pi, _ in accepted)
        used = set(pairs.values())
        remaining = {edge for edge in remaining if edge[0] not in pairs and edge[0] not in duplicates
                     and edge[1] not in used}
    for pi, ai in remaining:
        plan_review[pi] = activity_review[ai] = "identity evidence is tied or conflicting; associate IDs to resolve"
    return Resolution(pairs, basis, plan_review, activity_review, candidates, duplicates)
