"""Density schemes: one session-level scheme sets every exercise's sets in a conditioning session (contract C51).

The prescribed work stays fixed by the scheme and progresses on the
athlete's session RPE (and, for circuits, the finish time against its
cap). Every exercise in the session uses `hold`, so loads stay as written.
"""

KIND = "conditioning"
REQUIRED = ("propose", "decay")
OPTIONAL = ("problems",)
STATEFUL = True
