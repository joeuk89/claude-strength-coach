"""Overlay v4 to v5: a set may be a rep-out set, `rep_out` true (contract C10).

Earlier versions wrote a 5/3/1 wave's as-many-reps-as-possible set as a
`failure` set. On a wave line the coach did not override, that set becomes
a normal rep-out set; every other failure set stays a set to failure. The
version is part of the approval hash, so an approved overlay loses its
approval as in the earlier steps.
"""

from coach import overlay

DOC = "overlay"
FROM = 4
TO = 5


def _wave_lines(doc):
    for session in doc["sessions"]:
        for line in session["exercises"]:
            if (line.get("provenance") or {}).get("scheme") == "wave_531" and line.get("override") is None:
                yield line


def migrate(doc):
    for line in _wave_lines(doc):
        for set_ in line["sets"]:
            if set_.get("type") == "failure":
                set_["type"] = "normal"
                set_["rep_out"] = True
    return doc


def notes(before, after):
    found = []
    converted = sum(1 for line in _wave_lines(after) for set_ in line["sets"] if set_.get("rep_out"))
    if converted:
        found.append(f"{before['id']}: {converted} wave set(s) written as sets to failure are now rep-out (+) sets")
    if overlay.is_approved(before):
        found.append(f"{before['id']} loses its approval: the migration changes it, so re-approve it before pushing "
                     "it again")
    return found
