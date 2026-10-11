"""`[checkin]`: how often check-ins fall due (contract C4, C36)."""

from coach.config import Key, Table

CHECKIN = Table(keys={"cadence_days": Key("integer", default=7, minimum=1)})

TABLES = {"checkin": CHECKIN}
