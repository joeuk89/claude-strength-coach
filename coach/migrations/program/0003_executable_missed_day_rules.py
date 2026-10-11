"""Program v3 to v4: missed-day rules take the executable shape (contract C37).

A v3 rule was free text that nothing could run, so each becomes a `manual`
rule keeping its words, and the report names it for the coach to rewrite.
"""

DOC = "program"
FROM = 3
TO = 4


def text_of(rule):
    return f"{rule['condition']} → {rule['action']}"


def migrate(doc):
    doc["missed_day_rules"] = [
        {"id": rule["id"], "session_id": rule["session_id"], "text": text_of(rule), "when": {},
         "action": {"kind": "manual"}}
        for rule in doc["missed_day_rules"]
    ]
    return doc


def notes(before, after):
    return [f"data/program.json: missed-day rule {rule['id']} (\"{text_of(rule)}\") is now a manual rule; "
            "rewrite it as fold, shift or skip so coach can apply it"
            for rule in before["missed_day_rules"]]
