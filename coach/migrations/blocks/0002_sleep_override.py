"""Block ledger v2 to v3: a week's sleep may be a reasoned override of the measured sleep (C42, C43).

Every closed week gets `sleep_reason` null. An earlier `athlete` sleep source stays as it was: it records the
athlete's word from before an override needed a reason.
"""

DOC = "blocks"
FROM = 2
TO = 3


def migrate(doc):
    for block in doc["blocks"]:
        for week in block["weeks"]:
            week["signals"]["sleep_reason"] = None
    return doc
