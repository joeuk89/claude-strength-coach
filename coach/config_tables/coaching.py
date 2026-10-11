"""`[coaching]`: whether the coach reviews the program's structure or runs the athlete's own (contract C44)."""

from coach.config import Key, Table

COACH, RUN = "coach", "run"
MODES = (COACH, RUN)

COACHING = Table(keys={"mode": Key("string", default=COACH, choices=MODES)})

TABLES = {"coaching": COACHING}


def mode(config):
    return config["coaching"]["mode"]
