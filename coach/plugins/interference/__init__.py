"""Interference rules: flag lifting and quality activities placed too close together (contract C51).

A rule judges the week's bouts and returns flags; it never moves, drops or
reorders anything. Framework rules emit only `collision`; instance rules
emit only their own `custom_` codes.
"""

KIND = "interference"
REQUIRED = ("evaluate",)
OPTIONAL = ()
STATEFUL = False
