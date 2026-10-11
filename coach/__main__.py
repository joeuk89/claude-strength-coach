"""`python3 -m coach`. Kept to Python 3.6 syntax so an old Python reaches the floor check."""

import json
import sys

FLOOR = (3, 11)
HOOK_EVENTS = {"sessionstart": "SessionStart", "posttooluse": "PostToolUse"}


def _hook_event(argv):
    for first, second in zip(argv, argv[1:]):
        if first == "hooks" and second in HOOK_EVENTS:
            return HOOK_EVENTS[second]
    return None


def run(argv=None, version_info=None):
    argv = sys.argv[1:] if argv is None else argv
    version_info = sys.version_info if version_info is None else version_info
    if tuple(version_info[:2]) < FLOOR:
        found = ".".join(str(part) for part in version_info[:3])
        sentence = "The coach scripts need Python 3.11 or newer, and this is Python {}.".format(found)
        sys.stderr.write("coach: " + sentence + "\n")
        event = _hook_event(argv)
        if event == "SessionStart":
            context = "Coach status unavailable: " + sentence[0].lower() + sentence[1:]
            response = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
            sys.stdout.write(json.dumps(response) + "\n")
        if event:
            return 0
        envelope = {"schema_version": 1, "ok": False, "command": None,
                    "error": {"code": "config", "message": sentence}, "warnings": []}
        sys.stdout.write(json.dumps(envelope) + "\n")
        return 5
    from coach.cli import main

    return main(argv)


if __name__ == "__main__":
    sys.exit(run())
