"""Progression schemes: turn a slot's exposures into its next prescription (contract C23)."""

KIND = "scheme"
REQUIRED = ("propose", "decay")
OPTIONAL = ("deload", "override_state", "final_note")
STATEFUL = True
