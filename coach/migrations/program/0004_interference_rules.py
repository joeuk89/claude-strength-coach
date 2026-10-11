"""Program v4 to v5: the two framework interference rules with their default params (contract C51)."""

DOC = "program"
FROM = 4
TO = 5

RULES = (
    {"name": "same_day", "params": {"min_gap_hours": 6, "lift_first": True}},
    {"name": "quality_before_heavy_lower", "params": {"hours": 24, "heavy_rpe": 7, "heavy_max_reps": 6}},
)


def migrate(doc):
    doc["interference"] = [{"name": rule["name"], "params": dict(rule["params"])} for rule in RULES]
    return doc


def notes(before, after):
    return ["data/program.json: interference rules same_day and quality_before_heavy_lower added with their "
            "defaults; set interference to [] to turn them off"]
