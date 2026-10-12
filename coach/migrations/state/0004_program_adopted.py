"""State v4 to v5: the state records the day the program was adopted, when its sessions start to count (C16, C41).

An older state never recorded it, so the migration leaves it null and the
accounting dates the program from the newest program archive, else the block
start or the first overlay (coach.state.adopted).
"""

DOC = "state"
FROM = 4
TO = 5


def migrate(doc):
    return dict({"schema_version": doc["schema_version"], "program_adopted": None},
                **{key: value for key, value in doc.items() if key != "schema_version"})


def notes(before, after):
    return ["data/state.json: program_adopted is unknown, so the schedule rule plans sessions from the newest "
            "program archive, else the block start or the first overlay; the next program adopt records it"]
