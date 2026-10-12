"""Niggles v1 to v2: dated standing limits and temporary flare limits (contract C26, C27).

A v1 row held one constraint list, applied on every date. It becomes the
row's one standing version, dated from the row's first history entry, so
no limit in force before the step is weakened on any date. Version 1 kept
no earlier list, so none is invented. A row with limits that has been
aggravated may hold a flare's tighter limit in place of its standing one:
its version asks the coach to confirm the standing limits.
"""

DOC = "niggles"
FROM = 1
TO = 2


def confirm_text(row):
    return (f"Carried over from the single limit list of {row['id']}, which a flare may have tightened: confirm "
            f"these are the standing limits with python3 -m coach niggles update {row['id']} --constraint ..., "
            "and give a flare's own limits with --flare-constraint")


_KEYS = ("id", "area", "first_noted", "last_noted", "mentions", "status", "notes", "applies_to", "standing",
         "constrain_while", "history")


def migrate(doc):
    for row in doc["niggles"]:
        found = row.pop("constraints")
        flared = any(entry["status"] == "aggravated" for entry in row["history"])
        row["standing"] = [{"from": row["history"][0]["date"], "constraints": found,
                            "confirm": confirm_text(row) if flared else None}] if found else []
        for entry in row["history"]:
            entry["flare_constraints"] = None
        row.update({key: row.pop(key) for key in _KEYS})
    return doc


def notes(before, after):
    found = [row["id"] for row in after["niggles"] if row["standing"] and row["standing"][-1]["confirm"]]
    if not found:
        return []
    return [f"Niggle {', '.join(found)}: the limits were aggravated at some point, so they may be a flare's; confirm "
            "the standing limits with python3 -m coach niggles update ID --constraint ..."]
