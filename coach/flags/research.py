"""Flag codes about the research behind a proposal (contract C20, C28)."""

from coach.flags import register

register("evidence_expired", owner="R-32", severities=("info",),
         summary="A plugin's cited research note has expired; the rationale says the evidence is under review.")
