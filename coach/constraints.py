"""Load constraints: the limits a slot (and later a niggle) puts on an exercise's load and effort (contract C26).

`active` is the one reader: the proposal pipeline enforces what it returns,
and later items read the same list. Each constraint carries its `source`
(`slot` here) so a flag can name where the limit came from.
"""

from coach import program


def active(root, session_id, exercise_id, on_date):
    """The constraints in force for one slot on a date, each {kind, value, reason, source}."""
    if not program.exists(root):
        return []
    doc = program.load(root)
    session = next((s for s in doc["sessions"] if s["id"] == session_id), None)
    line = next((e for e in session["exercises"] if e["exercise_id"] == exercise_id), None) if session else None
    if line is None:
        return []
    return [dict(constraint, source="slot") for constraint in line["constraints"]]
