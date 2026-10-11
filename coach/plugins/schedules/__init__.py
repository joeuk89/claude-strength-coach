"""Schedule rules: which session lands on which date (contract C23).

A rule may also define `problems(params, program) -> [(path, message)]`
for checks its parameter schema cannot express, such as session ids the
program lacks; `path` is relative to the rule's params.
"""

KIND = "schedule"
REQUIRED = ("plan", "positions")
OPTIONAL = ("problems",)
STATEFUL = False
