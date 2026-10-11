"""`python3 -m coach`. Kept to Python 3.6 syntax so an old Python reaches the floor check."""

import io
import json
import sys
import traceback

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
    event = _hook_event(argv)
    if tuple(version_info[:2]) < FLOOR:
        found = ".".join(str(part) for part in version_info[:3])
        sentence = "The coach scripts need Python 3.11 or newer, and this is Python {}.".format(found)
        sys.stderr.write("coach: " + sentence + "\n")
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
    if event:
        return _run_hook(argv, event)
    from coach.cli import main

    return main(argv)


def unavailable_response(reason):
    context = ("Coach status unavailable: the coach scripts failed ({}). "
               "Run python3 -m coach status to see why.".format(reason))
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}


def _run_hook(argv, event):
    buffer = io.StringIO()
    try:
        from coach.cli import main

        code = main(argv, stdout=buffer)
        if code == 0:
            sys.stdout.write(buffer.getvalue())
            return 0
        reason = _error_message(buffer.getvalue()) or "exit code {}".format(code)
    except (Exception, SystemExit) as exc:
        for line in traceback.format_exc().rstrip().splitlines():
            sys.stderr.write("coach: " + line + "\n")
        reason = "{}: {}".format(type(exc).__name__, exc)
    if event == "SessionStart":
        sys.stdout.write(json.dumps(unavailable_response(reason)) + "\n")
    return 0


def _error_message(output):
    try:
        message = json.loads(output)["error"]["message"]
    except Exception:
        return None
    return message.rstrip(".") if isinstance(message, str) and message else None


if __name__ == "__main__":
    sys.exit(run())
