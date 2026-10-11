"""Meal plan v1 to v2: allow shopping-coverage warnings on newly built plans."""

from coach import meals

DOC = "meal_plan"
FROM = 1
TO = 2


def migrate(doc):
    return doc


def notes(before, after):
    messages = [f"{before['id']} keeps its saved meals, shopping and flags; render it with "
                f"python3 -m coach meals render {before['id']}"]
    if meals.is_approved(before):
        messages.append(f"{before['id']} loses its approval: the schema version changes its hash; "
                        "obtain the athlete's agreement and re-approve before publishing its shopping issue")
    return messages
