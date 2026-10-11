"""`python3 -m coach`. Kept to Python 3.6 syntax so an old Python reaches the floor check."""

import json
import sys

FLOOR = (3, 11)


def run():
    if tuple(sys.version_info[:2]) < FLOOR:
        found = ".".join(str(part) for part in sys.version_info[:3])
        sentence = "The coach scripts need Python 3.11 or newer, and this is Python {}.".format(found)
        sys.stderr.write("coach: " + sentence + "\n")
        envelope = {"schema_version": 1, "ok": False, "command": None,
                    "error": {"code": "config", "message": sentence}, "warnings": []}
        sys.stdout.write(json.dumps(envelope) + "\n")
        return 5
    from coach.cli import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
