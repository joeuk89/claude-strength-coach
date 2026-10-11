"""Flag code raised when a niggle needs a qualified professional (contract C20, C27)."""

from coach.flags import register

register("niggle_escalate", owner="R-27", severities=("warn",),
         summary="Niggle reported three check-ins running, or worse: recommend a qualified professional.")
