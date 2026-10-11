"""Flag code raised for follow-ups past their review date (contract C20, C27)."""

from coach.flags import register

register("followup_due", owner="R-27", severities=("info",),
         summary="An open follow-up is past its review date.")
