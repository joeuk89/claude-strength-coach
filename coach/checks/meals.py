"""Meal plan checks: plan documents, rendered plans and the standing template's cards (contract C34)."""

from coach import meals, nutrition, paths, recipes
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-33c"


def _plan_files(ctx):
    directory = ctx.root / paths.MEAL_PLANS_DATA_DIR
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


@check(id="meal_plans", owner=OWNER)
def meal_plans(ctx):
    files = _plan_files(ctx)
    if not files:
        return [Result("skip", f"no meal plans in {paths.MEAL_PLANS_DATA_DIR}")]
    results = []
    for path in files:
        where = path.relative_to(ctx.root).as_posix()
        try:
            doc = meals.read_json(path)
        except ValidationError as exc:
            results.append(Result("fail", exc.message, where))
            continue
        for error in meals.validate(doc, ctx.root):
            results.append(Result("fail", f"{error.path}: {error.message}", where))
        if isinstance(doc, dict) and doc.get("id") != path.stem:
            results.append(Result("fail", f"$.id: the file is named {path.name} but holds {doc.get('id')}", where))
    return results


@check(id="meal_plan_render_fresh", owner=OWNER)
def meal_plan_render_fresh(ctx):
    files = _plan_files(ctx)
    if not files:
        return [Result("skip", f"no meal plans in {paths.MEAL_PLANS_DATA_DIR}")]
    results = []
    for path in files:
        plan_id = path.stem
        rendered = meals.rendered_path(plan_id)
        where = rendered.as_posix()
        try:
            fresh = meals.render_meal_plan(ctx.root, plan_id)
        except ValidationError as exc:
            results.append(Result("fail", f"meal plan {plan_id} cannot be rendered: {exc.message}", where))
            continue
        target = ctx.root / rendered
        if not target.is_file():
            results.append(Result("fail", f"{where} is missing; run python3 -m coach meals render {plan_id}", where))
        elif target.read_bytes() != fresh.encode("utf-8"):
            results.append(Result("fail", f"{where} was edited by hand or is out of date; it is never hand-edited. "
                                          f"Run python3 -m coach meals render {plan_id}", where))
    return results


def _named_cards(config):
    """(where, slug) for every card the template and the anchors name."""
    named = []
    nutrition_cfg = config["nutrition"]
    for index, row in enumerate(nutrition_cfg.get("template", {}).get("standing", [])):
        where = f"nutrition.template.standing[{index}]"
        named += [(where, row["recipe"])] if "recipe" in row else [(where, slug) for slug in row.get("pool", [])]
    for index, anchor in enumerate(nutrition_cfg.get("anchors", [])):
        if "recipe" in anchor:
            named.append((f"nutrition.anchors[{index}]", anchor["recipe"]))
    return named


@check(id="nutrition_template", owner=OWNER)
def nutrition_template(ctx):
    config = ctx.config
    if not nutrition.enabled(config):
        return [Result("skip", "nutrition is not enabled")]
    named = _named_cards(config)
    if not named and "template" not in config["nutrition"]:
        return [Result("skip", "no [nutrition.template] and no anchor names a card")]
    cards = {card.slug: card for card in recipes.load_bank(ctx.root).valid_cards()}
    results = []
    for where, slug in named:
        card = cards.get(slug)
        if card is None:
            results.append(Result("fail", f"{where} names \"{slug}\", which has no card in "
                                          f"{paths.MENU_DIR.as_posix()}/", paths.CONFIG.as_posix()))
        elif card.data["status"] == "benched":
            results.append(Result("fail", f"{where} names \"{slug}\", which is benched; un-bench it or change "
                                          "the row", paths.CONFIG.as_posix()))
    return results
