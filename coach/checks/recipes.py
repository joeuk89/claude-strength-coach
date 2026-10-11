"""Recipe bank checks (contract C33)."""

from coach import datablock, paths, recipes
from coach.checks import Result, check
from coach.errors import ValidationError

OWNER = "R-33b"


@check(id="recipe_cards", owner=OWNER)
def recipe_cards(ctx):
    bank = recipes.load_bank(ctx.root)
    config = ctx.config
    results = [Result("fail", message, path) for path, message in bank.broken]
    for card in bank.cards:
        results += recipes.validate_card(card, config)
    return results


@check(id="recipe_render_fresh", owner=OWNER)
def recipe_render_fresh(ctx):
    results = []
    for card in recipes.load_bank(ctx.root).valid_cards():
        try:
            region = recipes.current_region(card)
        except ValidationError as exc:
            results.append(Result("fail", exc.message, card.rel))
            continue
        if region is None:
            results.append(Result("fail", f"{card.slug}: no rendered region; run python3 -m coach recipes render",
                                  card.rel))
        elif region != recipes.render_card_region(card):
            results.append(Result("fail", f"{card.slug}: the rendered region differs from its data block; "
                                          "run python3 -m coach recipes render", card.rel))
    return results


@check(id="recipe_index_fresh", owner=OWNER)
def recipe_index_fresh(ctx):
    bank = recipes.load_bank(ctx.root)
    path = ctx.root / paths.MENU_INDEX
    where = paths.MENU_INDEX.as_posix()
    if not path.exists():
        if bank.cards:
            return [Result("fail", f"{where} is missing; run python3 -m coach recipes render", where)]
        return []
    if datablock.read_text(path) != recipes.render_index(bank, ctx.config):
        return [Result("fail", f"{where} differs from a fresh render; it is never hand-edited. "
                               "Run python3 -m coach recipes render", where)]
    return []
