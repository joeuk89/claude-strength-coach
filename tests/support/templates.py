"""A Hevy template cache that resolves every catalogue exercise, as a full `hevy pull` would."""

from coach.hevy.cache import HevyCache
from coach.library import Library


def cache_catalogue_templates(root, fetched_at, prefix="TEMPLATE"):
    templates = [{"id": f"{prefix}-{index}", "title": entry["hevy_titles"][0]}
                 for index, entry in enumerate(Library().entries()) if entry["hevy_titles"]]
    HevyCache(root).write_collection("exercise_templates", templates, fetched_at)
