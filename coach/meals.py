"""Meal plans: the standing template, a week's exceptions and the shopping list (contract C4, C34).

The coach drafts a week as exceptions to `[nutrition.template]` plus picks
for open and pool slots. `build` resolves the draft against the template,
the protein anchors, the recipe cards and the targets into
`data/nutrition/plans/<id>.json`. Items snapshot their macros and titles,
so a later card edit never changes a built plan or its render. The only
calorie number is the nutrition app's target, or `kcal_target` without an
app.
"""

import json
import math
import re
from datetime import timedelta, timezone
from pathlib import Path

from coach import config as config_module
from coach import dates, jsonio, nutrition, paths, recipes, render
from coach.config_tables.core import WEEKDAYS
from coach.errors import ConfigError, ValidationError
from coach.validate import Error
from coach.validate import validate as validate_schema

SCHEMA = "meal_plan"
DRAFT_SCHEMA = "meal_plan_draft"
SCHEMA_VERSION = 1
ID = re.compile(r"^\d{4}-\d{2}-\d{2}$")

BLOCK = "block"
WARN = "warn"
FLAG_SEVERITY = {
    "protein_below_floor": WARN,
    "kcal_off_target": WARN,
    "slot_open": WARN,
    "recipe_unknown": BLOCK,
    "variation_unknown": BLOCK,
    "variation_conflict": BLOCK,
    "recipe_benched": WARN,
    "use_up_unmatched": WARN,
    "units_mixed": WARN,
    "no_target": WARN,
}
DAY_FLAGS = ("protein_below_floor", "kcal_off_target")
ENTRY_KINDS = ("recipe", "cover", "skip")
RECIPE_ONLY = ("variations", "covered_by", "lock")


def settings(config):
    """([nutrition], [nutrition.template]); a ConfigError (exit 5) when either is missing."""
    if not nutrition.enabled(config):
        raise ConfigError("nutrition is not enabled: set [nutrition] enabled = true in config.toml "
                          "(/goals sets up the table)")
    template = config["nutrition"].get("template")
    if template is None:
        raise ConfigError("no standing week to plan from: add [nutrition.template] to config.toml "
                          "(config.example.toml shows one)")
    return config["nutrition"], template


def plan_style(template):
    if "plan_style" in template:
        return template["plan_style"]
    covered_dinner = any(row["slot"] == "dinner" and "cover" in row for row in template["standing"])
    return "loose" if covered_dinner else "strict"


def week_ahead(today, week_starts):
    """The first whole week that starts after `today`."""
    return dates.week_span(dates.week_span(today, week_starts).end + timedelta(days=1), week_starts)


def _num(value):
    if value is None:
        return None
    value = round(value, 2)
    return int(value) if float(value).is_integer() else value


def _applies(names, weekday, office):
    return any(name in ("daily", weekday) or (name == "office" and office) or (name == "home" and not office)
               for name in names)


def _rows_for(template, slot, weekday, office):
    return [(index, row) for index, row in enumerate(template["standing"])
            if row["slot"] == slot and _applies(row["days"], weekday, office)]


def _anchors_for(nutrition_cfg, slot, weekday, office):
    return [anchor for anchor in nutrition_cfg.get("anchors", [])
            if anchor["slot"] == slot and _applies(anchor["days"], weekday, office)]


def targets(root, nutrition_cfg):
    """The day targets: the app's latest calorie target (or kcal_target without an app) and the protein floor."""
    found = {"kcal": None, "kcal_source": None, "protein_floor_g": _num(nutrition_cfg["protein"]["floor_g"])}
    if nutrition_cfg["app"] != "none":
        with_target = [r for r in nutrition.readings(root) if r["target_kcal"] is not None]
        if with_target:
            latest = with_target[-1]
            found.update(kcal=_num(latest["target_kcal"]), kcal_source=f"reading {latest['date']}")
    elif "kcal_target" in nutrition_cfg:
        found.update(kcal=_num(nutrition_cfg["kcal_target"]), kcal_source="kcal_target")
    return found


def _template_entry(row):
    if "recipe" in row:
        return {"source": "template", "recipe": row["recipe"]}
    if "pool" in row:
        return {"source": "template", "pool": list(row["pool"])}
    return {"source": "template", "cover": row["cover"], "kcal": _num(row["kcal"]),
            "protein_g": _num(row["protein_g"])}


def _anchor_entry(anchor):
    entry = {"source": "anchor", "name": anchor["name"]}
    if "recipe" in anchor:
        entry["recipe"] = anchor["recipe"]
    else:
        entry.update(kcal=_num(anchor["kcal"]), protein_g=_num(anchor["protein_g"]))
    return entry


def template_week(root, span, config=None):
    """The standing week over `span` before any exceptions, with open slots marked."""
    config = config if config is not None else config_module.load(root)
    nutrition_cfg, template = settings(config)
    days, open_slots = [], []
    for day in span.days():
        weekday = WEEKDAYS[day.weekday()]
        office = weekday in template["office_days"]
        slots = []
        for slot in template["slots"]:
            entries = [_template_entry(row) for _, row in _rows_for(template, slot, weekday, office)]
            entries += [_anchor_entry(anchor) for anchor in _anchors_for(nutrition_cfg, slot, weekday, office)]
            slots.append({"slot": slot, "entries": entries, "open": not entries})
            if not entries:
                open_slots.append({"date": day.isoformat(), "slot": slot})
        days.append({"date": day.isoformat(), "weekday": weekday, "office": office, "slots": slots})
    return {
        "span": span.to_json(),
        "week": span.label() if (span.end - span.start).days == 6 else None,
        "style": plan_style(template),
        "slots": list(template["slots"]),
        "office_days": list(template["office_days"]),
        "staples": list(template["staples"]),
        "kcal_tolerance_pct": template["kcal_tolerance_pct"],
        "shopping_issue": template["shopping_issue"],
        "targets": targets(root, nutrition_cfg),
        "days": days,
        "open_slots": open_slots,
    }


def _entry_problems(entry, where):
    kinds = [kind for kind in ENTRY_KINDS if kind in entry]
    if len(kinds) != 1:
        found = ", ".join(kinds) or "none"
        return [Error(where, f"an entry sets exactly one of recipe, cover or skip (found {found})")]
    kind, found = kinds[0], []
    if kind == "skip" and entry["skip"] is not True:
        found.append(Error(f"{where}.skip", "skip is only ever true; leave it out otherwise"))
    if kind == "cover":
        missing = [key for key in ("kcal", "protein_g") if key not in entry]
        if missing:
            found.append(Error(where, f"a cover entry needs its estimated {' and '.join(missing)}"))
    elif "kcal" in entry or "protein_g" in entry:
        found.append(Error(where, "kcal and protein_g belong only on a cover entry"))
    if kind != "recipe":
        extra = [key for key in RECIPE_ONLY if key in entry]
        if extra:
            found.append(Error(where, f"{', '.join(extra)} belong only on a recipe entry"))
    return found


def _draft_problems(draft, slots):
    errors = validate_schema(draft, jsonio.load_schema(DRAFT_SCHEMA))
    if errors:
        return errors
    found = []
    try:
        span = dates.Span(dates.parse_date(draft["span"]["start"]), dates.parse_date(draft["span"]["end"]))
    except ValueError as exc:
        return [Error("$.span", str(exc))]

    def placed(item, where):
        try:
            day = dates.parse_date(item["date"])
        except ValueError as exc:
            found.append(Error(f"{where}.date", str(exc)))
            return False
        if not span.contains(day):
            found.append(Error(f"{where}.date", f"{item['date']} is outside the span {span.start}..{span.end}"))
            return False
        if "slot" in item and item["slot"] not in slots:
            found.append(Error(f"{where}.slot", f"\"{item['slot']}\" is not one of [nutrition.template] slots "
                                                f"({', '.join(slots)})"))
            return False
        return True

    seen_slots, seen_office, skipped = set(), set(), set()
    for index, exception in enumerate(draft.get("exceptions", [])):
        where = f"$.exceptions[{index}]"
        has_entry = "slot" in exception or "entry" in exception
        if has_entry == ("office" in exception) or ("slot" in exception) != ("entry" in exception):
            found.append(Error(where, "an exception gives a slot and an entry, or office: true/false, not both"))
            continue
        if not placed(exception, where):
            continue
        if "office" in exception:
            if exception["date"] in seen_office:
                found.append(Error(where, f"{exception['date']} has two office exceptions"))
            seen_office.add(exception["date"])
            continue
        key = (exception["date"], exception["slot"])
        if key in seen_slots:
            found.append(Error(where, f"{exception['date']} {exception['slot']} has two exceptions"))
        seen_slots.add(key)
        found += _entry_problems(exception["entry"], f"{where}.entry")
        if exception["entry"].get("skip"):
            skipped.add(key)
    for index, assignment in enumerate(draft.get("assignments", [])):
        where = f"$.assignments[{index}]"
        if not placed(assignment, where):
            continue
        found += _entry_problems(assignment["entry"], f"{where}.entry")
        if (assignment["date"], assignment["slot"]) in skipped:
            found.append(Error(where, f"{assignment['date']} {assignment['slot']} is skipped by an exception"))
    return found


class _Flags:
    def __init__(self):
        self.items = []

    def add(self, code, message, date=None, slot=None):
        self.items.append({"code": code, "severity": FLAG_SEVERITY[code], "date": date, "slot": slot,
                           "message": message, "resolved": False, "resolution": None})


def _where(date, slot):
    return f"{render.day_label(date)} {slot}" if slot else render.day_label(date)


def _blank_item(slot, source):
    return {"slot": slot, "source": source, "recipe": None, "title": None, "variations": [], "covered_by": None,
            "cover": None, "name": None, "skip": False, "lock": None, "note": None, "kcal": None, "protein_g": None}


def _applied_variations(card, names):
    """(known variations in order, unknown names, conflicts as (first, second, item))."""
    known = {variation["name"]: variation for variation in card.data.get("variations", [])}
    applied, unknown, conflicts, changed_by = [], [], [], {}
    for name in names:
        variation = known.get(name)
        if variation is None:
            unknown.append(name)
            continue
        clash = next((change["item"] for change in variation["changes"] if change["item"] in changed_by), None)
        if clash is not None:
            conflicts.append((changed_by[clash], name, clash))
            continue
        for change in variation["changes"]:
            changed_by[change["item"]] = name
        applied.append(variation)
    return applied, unknown, conflicts


def _recipe_item(item, entry, cards, flags, date):
    item.update(recipe=entry["recipe"], variations=list(entry.get("variations", [])),
                covered_by=entry.get("covered_by"), lock=entry.get("lock"))
    where = _where(date, item["slot"])
    card = cards.get(item["recipe"])
    if card is None:
        flags.add("recipe_unknown", f"{where}: no recipe card \"{item['recipe']}\" in "
                                    f"{paths.MENU_DIR.as_posix()}/; pick another or add the card with /recipes.",
                  date, item["slot"])
        return item
    data = card.data
    item["title"] = data["title"]
    if data["status"] == "benched":
        flags.add("recipe_benched", f"{where}: {data['title']} is benched; un-bench it with the athlete's "
                                    "agreement or pick another.", date, item["slot"])
    applied, unknown, conflicts = _applied_variations(card, item["variations"])
    for name in unknown:
        flags.add("variation_unknown", f"{where}: {data['title']} has no variation \"{name}\".", date, item["slot"])
    for first, second, changed in conflicts:
        flags.add("variation_conflict", f"{where}: {data['title']} variations {first} and {second} both change "
                                        f"\"{changed}\", so they cannot stack; keep one.", date, item["slot"])
    kcal = data["per_serving"]["kcal"] + sum(v["delta"]["kcal"] for v in applied)
    protein = data["per_serving"]["protein_g"] + sum(v["delta"]["protein_g"] for v in applied)
    item.update(kcal=_num(kcal), protein_g=_num(protein))
    return item


def _item(slot, source, entry, cards, flags, date, note=None, name=None):
    item = _blank_item(slot, source)
    item.update(note=note, name=name)
    if entry.get("skip"):
        item.update(skip=True, kcal=0, protein_g=0)
    elif "cover" in entry:
        item.update(cover=entry["cover"], kcal=_num(entry["kcal"]), protein_g=_num(entry["protein_g"]))
    elif "recipe" in entry:
        _recipe_item(item, entry, cards, flags, date)
    else:
        item.update(kcal=_num(entry["kcal"]), protein_g=_num(entry["protein_g"]))
    return item


def _row_entry(row):
    if "recipe" in row:
        return {"recipe": row["recipe"]}
    return {"cover": row["cover"], "kcal": row["kcal"], "protein_g": row["protein_g"]}


def _anchor_as_entry(anchor):
    if "recipe" in anchor:
        return {"recipe": anchor["recipe"]}
    return {"kcal": anchor["kcal"], "protein_g": anchor["protein_g"]}


def _sum(values):
    return _num(sum(value for value in values if value is not None))


def _pct_off(total, target):
    return round(abs(total - target) / target * 100)


def _day_flags(date, totals, plan_targets, tolerance, flags):
    floor = plan_targets["protein_floor_g"]
    if totals["protein_g"] < floor:
        flags.add("protein_below_floor", f"{render.day_label(date)}: {totals['protein_g']} g protein is under the "
                                         f"{floor} g floor; add a top-up or swap a meal.", date)
    kcal = plan_targets["kcal"]
    if kcal and abs(totals["kcal"] - kcal) > kcal * tolerance / 100:
        direction = "under" if totals["kcal"] < kcal else "over"
        flags.add("kcal_off_target", f"{render.day_label(date)}: {totals['kcal']} kcal is "
                                     f"{_pct_off(totals['kcal'], kcal)}% {direction} the {kcal} kcal target "
                                     f"(tolerance {_num(tolerance)}%).", date)


def _days(draft, nutrition_cfg, template, cards, plan_targets, flags):
    exceptions = {(e["date"], e["slot"]): e for e in draft.get("exceptions", []) if "slot" in e}
    office_days = {e["date"]: e["office"] for e in draft.get("exceptions", []) if "office" in e}
    assignments = {}
    for assignment in draft.get("assignments", []):
        assignments.setdefault((assignment["date"], assignment["slot"]), []).append(assignment)
    span = dates.Span(dates.parse_date(draft["span"]["start"]), dates.parse_date(draft["span"]["end"]))

    days = []
    for day in span.days():
        date, weekday = day.isoformat(), WEEKDAYS[day.weekday()]
        office = office_days.get(date, weekday in template["office_days"])
        items = []
        for slot in template["slots"]:
            slot_items, needs_pick = [], False
            exception = exceptions.get((date, slot))
            picks = assignments.get((date, slot), [])
            if exception is not None:
                slot_items.append(_item(slot, "exception", exception["entry"], cards, flags, date,
                                        note=exception.get("note")))
            else:
                rows = _rows_for(template, slot, weekday, office)
                if len(rows) > 1:
                    named = " and ".join(f"nutrition.template.standing[{index}]" for index, _ in rows)
                    raise ValidationError(f"{named} both fill {slot} on {date} once its office day changes; add an "
                                          f"exception for {date} {slot} to the draft")
                for _, row in rows:
                    if "pool" in row:
                        needs_pick = not picks
                    else:
                        slot_items.append(_item(slot, "template", _row_entry(row), cards, flags, date))
                for anchor in _anchors_for(nutrition_cfg, slot, weekday, office):
                    slot_items.append(_item(slot, "anchor", _anchor_as_entry(anchor), cards, flags, date,
                                            name=anchor["name"]))
            for pick in picks:
                slot_items.append(_item(slot, "assignment", pick["entry"], cards, flags, date, note=pick.get("note")))
            if needs_pick or not slot_items:
                what = "pick one from its pool" if needs_pick else "pick a recipe or add an exception"
                flags.add("slot_open", f"{_where(date, slot)} is open: {what}.", date, slot)
            items += slot_items
        totals = {"kcal": _sum(i["kcal"] for i in items), "protein_g": _sum(i["protein_g"] for i in items)}
        _day_flags(date, totals, plan_targets, template["kcal_tolerance_pct"], flags)
        days.append({"date": date, "office": office, "items": items, "totals": totals})
    return days


def _pool_key(item):
    return item["recipe"], tuple(sorted(item["variations"])), item["covered_by"]


def _pool(days, cards):
    groups = {}
    for day in days:
        for item in day["items"]:
            if item["recipe"] is None:
                continue
            key = _pool_key(item)
            if key not in groups:
                groups[key] = {"recipe": item["recipe"], "title": item["title"], "variations": list(key[1]),
                               "count": 0, "covered_by": item["covered_by"], "servings": None, "batches": None,
                               "kcal": item["kcal"], "protein_g": item["protein_g"]}
            groups[key]["count"] += 1
    for entry in groups.values():
        card = cards.get(entry["recipe"])
        if card is not None:
            entry["servings"] = card.data["servings"]
            if entry["covered_by"] is None:
                entry["batches"] = math.ceil(entry["count"] / entry["servings"])
    return sorted(groups.values(), key=lambda e: ((e["title"] or e["recipe"]).lower(), e["recipe"],
                                                  e["variations"], e["covered_by"] or ""))


def _ingredients(card, variation_names):
    """(item, unit) -> {qty, aisle} for one batch, with the variations that apply."""
    found = {}
    for ingredient in card.data.get("ingredients", []):
        found[(ingredient["item"], ingredient["unit"])] = {"qty": ingredient["qty"], "aisle": ingredient["aisle"]}
    applied, _, _ = _applied_variations(card, variation_names)
    for variation in applied:
        for change in variation["changes"]:
            key = (change["item"], change["unit"])
            if key in found:
                found[key]["qty"] += change["qty"]
            else:
                found[key] = {"qty": change["qty"], "aisle": change.get("aisle", recipes.DEFAULT_AISLE_GUESS)}
    return {key: value for key, value in found.items() if value["qty"] > 0}


def _shopping(pool, cards, use_up, template, aisles, flags):
    needed = {}
    for entry in pool:
        card = cards.get(entry["recipe"])
        if entry["covered_by"] is not None or card is None:
            continue
        for key, ingredient in _ingredients(card, entry["variations"]).items():
            line = needed.setdefault(key, {"aisle": ingredient["aisle"], "qty": 0, "for": set()})
            line["qty"] += ingredient["qty"] * entry["batches"]
            line["for"].add(entry["recipe"])

    used_up = []
    for use in use_up:
        key = (use["item"], use["unit"])
        if key in needed:
            used = min(use["qty"], needed[key]["qty"])
            needed[key]["qty"] -= used
            used_up.append({"item": use["item"], "qty": _num(used), "unit": use["unit"]})
        elif any(item == use["item"] for item, _ in needed):
            units = ", ".join(sorted(unit for item, unit in needed if item == use["item"]))
            flags.add("units_mixed", f"{use['item']} to use up is in {use['unit']}, but the plan needs it in {units}; "
                                     "nothing was taken off the list.")
        else:
            flags.add("use_up_unmatched", f"{use['item']} ({_num(use['qty'])} {use['unit']}) to use up is in no "
                                          "recipe this week; plan a meal that uses it or drop it from use_up.")

    by_item = {}
    for item, unit in needed:
        by_item.setdefault(item, []).append(unit)
    for item, units in sorted(by_item.items()):
        if len(units) > 1:
            flags.add("units_mixed", f"{item} is needed in {' and '.join(sorted(units))}; the list shows a line for "
                                     "each.")

    lines = [{"aisle": value["aisle"], "item": item, "qty": _num(value["qty"]), "unit": unit,
              "for": sorted(value["for"])}
             for (item, unit), value in needed.items() if value["qty"] > 0]
    staples = list(template["staples"])
    check = [{"item": line["item"], "qty": line["qty"], "unit": line["unit"]}
             for staple in staples for line in sorted(lines, key=lambda l: l["unit"]) if line["item"] == staple]
    order = {aisle: index for index, aisle in enumerate(aisles)}
    buy = sorted((line for line in lines if line["item"] not in staples),
                 key=lambda l: (order.get(l["aisle"], len(order)), l["aisle"], l["item"], l["unit"]))
    return {"buy": buy, "check": check, "used_up": used_up}


def _timestamp(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(draft, root, *, now, config=None):
    """Resolve a draft (C34) into a meal plan document. Raises ValidationError for a bad draft."""
    config = config if config is not None else config_module.load(root)
    nutrition_cfg, template = settings(config)
    errors = _draft_problems(draft, template["slots"])
    if errors:
        raise ValidationError(f"the meal plan draft is not valid ({len(errors)} problem(s)): "
                              f"{errors[0].path}: {errors[0].message}", details=[e.to_json() for e in errors])
    cards = {card.slug: card for card in recipes.load_bank(root).valid_cards()}
    plan_targets = targets(root, nutrition_cfg)
    flags = _Flags()
    days = _days(draft, nutrition_cfg, template, cards, plan_targets, flags)
    pool = _pool(days, cards)
    use_up = draft.get("use_up", [])
    shopping = _shopping(pool, cards, use_up, template, recipes.bank_settings(config)["aisles"], flags)
    if plan_targets["kcal"] is None:
        how = ("no reading carries the app's calorie target yet; record one with python3 -m coach nutrition record"
               if nutrition_cfg["app"] != "none" else "set [nutrition] kcal_target through /goals")
        flags.add("no_target", f"No calorie target, so days are not checked against one: {how}.")
    return {
        "schema_version": SCHEMA_VERSION,
        "id": draft["span"]["start"],
        "span": dict(draft["span"]),
        "created_at": _timestamp(now),
        "style": plan_style(template),
        "targets": plan_targets,
        "input": {"exceptions": draft.get("exceptions", []), "assignments": draft.get("assignments", []),
                  "use_up": use_up, "notes": draft.get("notes")},
        "days": days,
        "pool": pool,
        "shopping": shopping,
        "flags": flags.items,
        "approval": None,
    }


def _version_error(doc):
    if not isinstance(doc, dict):
        return Error("$", "a meal plan is a JSON object")
    version = doc.get("schema_version")
    if isinstance(version, int) and not isinstance(version, bool):
        if version > SCHEMA_VERSION:
            return Error("$.schema_version", f"schema_version {version} is newer than this coach reads "
                                             f"({SCHEMA_VERSION}); run /framework-sync")
        if version < SCHEMA_VERSION:
            return Error("$.schema_version", f"schema_version {version} is older than the current {SCHEMA_VERSION}; "
                                             "run python3 -m coach migrate run")
    return None


def validate(doc, root=None):
    """Every problem with a meal plan document, each with a JSONPath; empty when it is sound."""
    version_error = _version_error(doc)
    if version_error:
        return [version_error]
    errors = validate_schema(doc, jsonio.load_schema(SCHEMA))
    if errors:
        return errors
    found = []
    try:
        span = dates.Span(dates.parse_date(doc["span"]["start"]), dates.parse_date(doc["span"]["end"]))
    except ValueError as exc:
        return [Error("$.span", str(exc))]
    if doc["id"] != doc["span"]["start"]:
        found.append(Error("$.id", f"a plan's id is its span start ({doc['span']['start']}), found {doc['id']}"))
    expected = [day.isoformat() for day in span.days()]
    if [day["date"] for day in doc["days"]] != expected:
        found.append(Error("$.days", f"days must run {expected[0]}..{expected[-1]}, one per date, in order"))
    for index, day in enumerate(doc["days"]):
        for key in ("kcal", "protein_g"):
            total = _sum(item[key] for item in day["items"])
            if total != day["totals"][key]:
                found.append(Error(f"$.days[{index}].totals.{key}",
                                   f"totals {key} is {day['totals'][key]} but its items sum to {total}"))
    counts = {}
    for day in doc["days"]:
        for item in day["items"]:
            if item["recipe"] is not None:
                counts[_pool_key(item)] = counts.get(_pool_key(item), 0) + 1
    pooled = {(e["recipe"], tuple(e["variations"]), e["covered_by"]): e["count"] for e in doc["pool"]}
    if pooled != counts:
        found.append(Error("$.pool", "the pool's counts differ from the recipes in the days"))
    for index, flag in enumerate(doc["flags"]):
        where = f"$.flags[{index}]"
        if flag["severity"] != FLAG_SEVERITY[flag["code"]]:
            found.append(Error(f"{where}.severity", f"{flag['code']} is a {FLAG_SEVERITY[flag['code']]} flag"))
        if flag["resolved"] != bool(flag["resolution"]):
            found.append(Error(f"{where}.resolution", "a resolved flag says how; an unresolved one has null"))
    return found


def path_for(root, plan_id):
    if not isinstance(plan_id, str) or not ID.fullmatch(plan_id):
        raise ValidationError(f"{plan_id!r} is not a meal plan id (YYYY-MM-DD, the plan's first day)")
    return Path(root) / paths.MEAL_PLANS_DATA_DIR / f"{plan_id}.json"


def rendered_path(plan_id):
    return paths.MEAL_PLANS_DIR / f"{plan_id}.md"


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise ValidationError(f"{path} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from None


def load(root, plan_id):
    """The plan with this id, validated. Raises ValidationError when absent or unsound."""
    doc = read_json(path_for(root, plan_id))
    errors = validate(doc, root)
    if not errors and doc["id"] != plan_id:
        errors.append(Error("$.id", f"the file is named {plan_id}.json but holds {doc['id']}"))
    if errors:
        raise ValidationError(f"Meal plan {plan_id} is not valid ({len(errors)} problem(s)): "
                              f"{errors[0].path}: {errors[0].message}", details=[e.to_json() for e in errors])
    return doc


def approval_hash(doc):
    return jsonio.canonical_hash({key: value for key, value in doc.items() if key != "approval"})


def is_approved(doc):
    approval = doc.get("approval")
    return bool(approval) and approval.get("hash") == approval_hash(doc)


def approve(doc, now):
    approved = dict(doc)
    approved["approval"] = {"approved_at": _timestamp(now), "hash": approval_hash(doc)}
    return approved


def unresolved_blocks(doc):
    return [flag for flag in doc["flags"] if flag["severity"] == BLOCK and not flag["resolved"]]


def _cell(text):
    return str(text).replace("|", "\\|")


def _link(slug, title):
    if title is None:
        return f"`{slug}` *(no card)*"
    escaped = title.replace("[", "\\[").replace("]", "\\]")
    return f"[{escaped}](../menu/{slug}.md)"


def _variations_text(variations):
    return f" ({', '.join(variations)})" if variations else ""


def _item_text(item):
    if item["skip"]:
        text = "*(skipped)*"
    elif item["recipe"] is not None:
        text = _link(item["recipe"], item["title"]) + _variations_text(item["variations"])
        if item["covered_by"]:
            text += f" *(covered: {item['covered_by']})*"
        if item["source"] == "anchor":
            text += " *(anchor)*"
    elif item["cover"] is not None:
        text = f"{item['cover']} *(covered)*"
    else:
        text = f"{item['name']} *(anchor)*"
    if item["lock"]:
        text += f" 🔒 {item['lock']}"
    if item["note"]:
        text += f" — {item['note']}"
    return _cell(text)


def _macros(kcal, protein):
    if kcal is None:
        return "unknown"
    return f"{_num(kcal)} kcal · {_num(protein)} g P"


def _slot_heading(slot):
    return slot.replace("-", " ").capitalize()


def _aisle_label(aisle):
    return aisle.replace("-", " / ")


def _amount_text(line):
    return recipes.ingredient_text({"qty": line["qty"], "unit": line["unit"], "item": line["item"]})


def _titles(doc):
    return {entry["recipe"]: entry["title"] or entry["recipe"] for entry in doc["pool"]}


def _buy_groups(doc):
    groups = []
    for line in doc["shopping"]["buy"]:
        if not groups or groups[-1][0] != line["aisle"]:
            groups.append((line["aisle"], []))
        groups[-1][1].append(line)
    return groups


def _buy_text(line, titles):
    return f"{_amount_text(line)} · {', '.join(titles.get(slug, slug) for slug in line['for'])}"


def shopping_markdown(doc):
    """The plan's shopping list as markdown, starting at its `## Shopping list` heading."""
    titles = _titles(doc)
    lines = ["## Shopping list", "", "### Buy", ""]
    groups = _buy_groups(doc)
    if not groups:
        lines += ["Nothing to buy.", ""]
    for aisle, group in groups:
        lines += [f"**{_aisle_label(aisle)}**", ""] + [f"- {_buy_text(line, titles)}" for line in group] + [""]
    lines += ["### Check you have", ""]
    check = doc["shopping"]["check"]
    lines += [f"- {_amount_text(line)}" for line in check] if check else ["No staples needed."]
    return "\n".join(lines) + "\n"


def shopping_issue(doc):
    """(title, body) for a GitHub issue: tickable Buy lines under aisle headings, then the staples."""
    span = doc["span"]
    title = f"Shopping: {render.short_date(span['start'])} – {render.short_date(span['end'])}"
    titles = _titles(doc)
    lines = [f"Meal plan: {rendered_path(doc['id']).as_posix()}", ""]
    for aisle, group in _buy_groups(doc):
        lines += [f"### {_aisle_label(aisle)}", ""] + [f"- [ ] {_buy_text(line, titles)}" for line in group] + [""]
    lines += ["### Check you have", ""]
    lines += [f"- [ ] {_amount_text(line)}" for line in doc["shopping"]["check"]] or ["Nothing to check."]
    return title, "\n".join(lines) + "\n"


def header(plan_id):
    return (f"<!-- generated by coach from {(paths.MEAL_PLANS_DATA_DIR / f'{plan_id}.json').as_posix()}; "
            f"edit the data, then run: python3 -m coach meals render {plan_id} -->")


STYLE_LINES = {
    "loose": "The pool is the plan: shop for it and eat each meal once. The week is a suggestion; swap meals "
             "within a slot, except 🔒 entries.",
    "strict": "Eat each meal on the day shown.",
}


def render_plan(doc):
    """The whole of `nutrition/plans/<id>.md`, from the plan document alone."""
    span, plan_targets = doc["span"], doc["targets"]
    if plan_targets["kcal"] is None:
        kcal_text = "no calorie target"
    else:
        kcal_text = f"{_num(plan_targets['kcal'])} kcal ({plan_targets['kcal_source']})"
    approval = (f"approved {doc['approval']['approved_at']}" if is_approved(doc) else "not yet approved")
    lines = [
        header(doc["id"]),
        f"# Meal plan — {render.day_label(span['start'])} → {render.day_label(span['end'])}",
        "",
        f"**Targets:** {kcal_text} · protein floor {_num(plan_targets['protein_floor_g'])} g · "
        f"style: {doc['style']} · {approval}",
        "",
        STYLE_LINES[doc["style"]],
        "",
        "## Pool",
        "",
    ]
    if doc["pool"]:
        lines += ["| Meal | Count | Per serving | Make |", "| --- | --- | --- | --- |"]
        for entry in doc["pool"]:
            if entry["covered_by"]:
                make = f"covered: {entry['covered_by']}"
            elif entry["batches"] is None:
                make = "—"
            elif entry["servings"] == 1:
                make = str(entry["batches"])
            else:
                make = f"{entry['batches']} × batch of {entry['servings']}"
            lines.append(f"| {_cell(_link(entry['recipe'], entry['title']) + _variations_text(entry['variations']))} "
                         f"| {entry['count']} | {_macros(entry['kcal'], entry['protein_g'])} | {_cell(make)} |")
    else:
        lines.append("_No recipes this week._")

    slots = list(dict.fromkeys(item["slot"] for day in doc["days"] for item in day["items"]))
    flagged_days = {f["date"] for f in doc["flags"] if f["code"] in DAY_FLAGS}
    lines += ["", "## The week", "",
              "| Day | " + " | ".join(_slot_heading(slot) for slot in slots) + " | Total |",
              "| --- | " + " | ".join("---" for _ in slots) + " | --- |"]
    open_slots = {(f["date"], f["slot"]) for f in doc["flags"] if f["code"] == "slot_open"}
    for day in doc["days"]:
        cells = []
        for slot in slots:
            texts = [_item_text(item) for item in day["items"] if item["slot"] == slot]
            if (day["date"], slot) in open_slots:
                texts.append("_open_")
            cells.append(" + ".join(texts) or "—")
        label = render.day_label(day["date"]) + (" · office" if day["office"] else "")
        total = _macros(day["totals"]["kcal"], day["totals"]["protein_g"])
        if day["date"] in flagged_days:
            total += " ⚠"
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {total} |")

    lines += ["", "## Flags", ""]
    if not doc["flags"]:
        lines.append("None.")
    for flag in doc["flags"]:
        text = f"- {flag['severity']} · `{flag['code']}`: {flag['message']}"
        if flag["resolved"]:
            text += f" (resolved: {flag['resolution']})"
        lines.append(text)

    notes = []
    if doc["input"]["notes"]:
        notes.append(doc["input"]["notes"])
    if doc["shopping"]["used_up"]:
        notes.append("Used up: " + ", ".join(_amount_text(line) for line in doc["shopping"]["used_up"]) + ".")
    if notes:
        lines += ["", "## Notes", "", "\n\n".join(notes)]
    lines += ["", shopping_markdown(doc).rstrip("\n")]
    return "\n".join(lines) + "\n"


def render_meal_plan(root, plan_id):
    """A fresh render of `nutrition/plans/<id>.md`, for the freshness check (C11)."""
    return render_plan(load(root, plan_id))
