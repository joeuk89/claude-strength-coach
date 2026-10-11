"""The approval gate's PreToolUse hook: show what a Bash command would write to Hevy before it runs (contract C2, C12, C53).

`decide` reads Claude Code's PreToolUse hook input. A `coach` command that
writes to Hevy (`hevy_write` metadata) gets a dry run: the permission prompt
shows its summary, and a push the dry run refuses is denied with the reason.
A raw HTTP write to the Hevy API prompts with a warning. In
bypass-permissions mode all of these are denied, because nobody would see a
prompt. Every other command gets no opinion (None), so the normal
permission rules decide.
"""

import argparse
import contextlib
import io
import os
import re
import shlex
from pathlib import Path

from coach import routines
from coach.context import Context
from coach.errors import CoachError, RefusedError, UsageError

HEVY_HOST = "api.hevyapp.com"
BYPASS_MODE = "bypassPermissions"
ASK, DENY = "ask", "deny"

_PUNCTUATION = "();<>|&\n"
_SEPARATOR_CHARS = set(";|&()\n")
_PYTHON = re.compile(r"^python(\d+(\.\d+)*)?$")
_PYTHON_OPTIONS_WITH_VALUE = {"-X", "-W", "--check-hash-based-pycs"}
_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
_FD_BEFORE_REDIRECT = re.compile(r"(?<![\w-])\d+(?=[<>])")
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
_CURL_DATA = {"--data", "--data-ascii", "--data-binary", "--data-raw", "--data-urlencode", "--json", "--form",
              "--form-string", "--upload-file"}
_CURL_SHORT_WITH_VALUE = set("AbcCdDeEFHKmoPQrtTuUwxXyYz")
_WGET_DATA = {"--post-data", "--post-file", "--body-data", "--body-file"}
_HTTPIE = {"http", "https", "xh", "xhs"}
_MAX_DEPTH = 4

_UNAVAILABLE = ("Approval gate: summary unavailable ({}). This command writes to Hevy; allow it only if the "
                "athlete approved this exact write.")


def decide(hook_input, env=None):
    """The PreToolUse response for one tool call, or None for no opinion. Never raises."""
    env = os.environ if env is None else env
    try:
        return _decide(hook_input, env)
    except Exception as exc:
        return _response(ASK, _UNAVAILABLE.format(f"the gate failed: {type(exc).__name__}: {exc}"))


def unreadable_input(error):
    return _response(ASK, _UNAVAILABLE.format(f"the hook input could not be read: {error}"))


def _response(decision, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def _decide(hook_input, env):
    if not isinstance(hook_input, dict):
        raise ValueError("the hook input is not a JSON object")
    if hook_input.get("tool_name") != "Bash":
        return None
    tool_input = hook_input.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        raise ValueError("tool_input.command is missing")
    cwd = Path(hook_input.get("cwd") or os.getcwd())
    found = list(_Scanner(env).writes(tool_input["command"], cwd, {}))
    if not found:
        return None
    if hook_input.get("permission_mode") == BYPASS_MODE:
        what = "; ".join(item.label for item in found)
        return _response(DENY, f"Approval gate: {what} writes to Hevy, which needs the athlete's approval at a "
                               "permission prompt, and bypass-permissions mode shows none. Run it in a session "
                               "with normal permissions.")
    reviews = [item.review() for item in found]
    denied = [text for decision, text in reviews if decision == DENY]
    if denied:
        return _response(DENY, "\n\n".join(denied))
    return _response(ASK, "\n\n".join(text for _, text in reviews))


class _CoachWrite:
    def __init__(self, cmd, args, root, env):
        self.cmd, self.args, self.root, self.env = cmd, args, root, env
        self.label = f"python3 -m coach {cmd.name}"

    def review(self):
        ctx = Context(self.root, self.env, io.StringIO())
        args = argparse.Namespace(**vars(self.args))
        args.dry_run = True
        try:
            report = self.cmd.func(args, ctx)
        except RefusedError as exc:
            reasons = [d["message"] for d in exc.details] if len(exc.details) > 1 else []
            lines = [f"Approval gate: {exc.message} The dry run of {self.cmd.name} refuses it, so the gate blocked it."]
            return DENY, "\n".join(lines + [f"- {reason}" for reason in reasons])
        except CoachError as exc:
            return ASK, _UNAVAILABLE.format(f"the dry run failed: {exc.message.rstrip('.')}")
        except Exception as exc:
            return ASK, _UNAVAILABLE.format(f"the dry run failed: {type(exc).__name__}: {exc}")
        try:
            text = routines.summary(report)
        except Exception as exc:
            return ASK, _UNAVAILABLE.format(f"{type(exc).__name__}: {exc}")
        lines = [f"Approval gate: {self.label} writes to Hevy. Dry run:", text]
        lines += [f"Warning: {warning}" for warning in ctx.warnings]
        lines.append("Allow only if the athlete approved exactly these changes.")
        return ASK, "\n".join(lines)


class _HttpWrite:
    def __init__(self, method, url):
        self.label = f"{method} {url}"

    def review(self):
        return ASK, (f"Approval gate: this command writes to the Hevy API directly ({self.label}), skipping the "
                     "coach's approval check, read-back and audit log. Use python3 -m coach routines push "
                     "instead. Allow it only if the athlete asked for this exact write.")


class _Unreadable:
    def __init__(self, why):
        self.label = "a command the gate could not read"
        self.why = why

    def review(self):
        return ASK, _UNAVAILABLE.format(f"the gate could not read the command: {self.why}")


class _Scanner:
    """Finds the Hevy writes in one Bash command line."""

    def __init__(self, env):
        self.env = env
        self._parser = None

    def writes(self, command, cwd, shell_vars, depth=0):
        text = _FD_BEFORE_REDIRECT.sub("", command.replace("\\\n", " "))
        try:
            tokens = _tokens(text)
        except ValueError as exc:
            if self._mentions_write(command):
                yield _Unreadable(str(exc))
            return
        for words in _segments(tokens):
            local = {}
            while words and _ASSIGNMENT.match(words[0]):
                name, value = _ASSIGNMENT.match(words[0]).groups()
                local[name] = value
                words = words[1:]
            if not words:
                shell_vars.update(local)
                continue
            program = os.path.basename(words[0])
            if program in ("cd", "pushd"):
                cwd = _change_dir(cwd, words[1:])
                continue
            if program == "export":
                shell_vars.update(dict(_ASSIGNMENT.match(w).groups() for w in words[1:] if _ASSIGNMENT.match(w)))
                continue
            variables = dict(shell_vars, **local)
            nested = _nested_script(words)
            if nested is not None:
                if depth < _MAX_DEPTH:
                    yield from self.writes(nested, cwd, dict(variables), depth + 1)
                elif self._mentions_write(nested):
                    yield _Unreadable("shell commands nested too deeply")
                continue
            argv = _coach_argv(words)
            if argv is not None:
                yield from self._coach(argv, cwd, variables)
                continue
            http = _http_write(words)
            if http:
                yield _HttpWrite(*http)

    def _coach(self, argv, cwd, variables):
        from coach import cli, commands

        if self._parser is None:
            registered = commands.discover()
            self._parser = cli.build_parser(registered)[0]
            self._commands = {cmd.name: cmd for cmd in registered}
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                args = self._parser.parse_args(argv)
        except SystemExit:
            return
        except UsageError as exc:
            if self._mentions_write(" ".join(argv)) or any("$" in word or "`" in word for word in argv):
                yield _Unreadable(exc.message)
            return
        cmd = self._commands[args._command]
        if not cmd.hevy_write or args.dry_run:
            return
        env = dict(self.env, **variables)
        if args.root:
            root = cwd / os.path.expanduser(args.root)
        elif env.get("COACH_ROOT"):
            root = cwd / os.path.expanduser(env["COACH_ROOT"])
        else:
            root = cwd
        yield _CoachWrite(cmd, args, root, env)

    def _mentions_write(self, text):
        from coach import commands

        flat = " ".join(text.split())
        if HEVY_HOST in flat and any(method in flat.upper() for method in _WRITE_METHODS):
            return True
        return any(cmd.name in flat for cmd in commands.discover() if cmd.hevy_write)


def _tokens(text):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=_PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    return list(lexer)


def _segments(tokens):
    """Simple commands, split at separators, with redirections and their targets left out."""
    words, skip_next = [], False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token and set(token) <= _SEPARATOR_CHARS:
            if words:
                yield words
            words = []
        elif token and set(token) <= set(_PUNCTUATION):
            skip_next = True
        else:
            words.append(token)
    if words:
        yield words


def _change_dir(cwd, args):
    targets = [arg for arg in args if not arg.startswith("-")]
    if not targets:
        return Path.home() if not args else cwd
    return cwd / os.path.expanduser(targets[0])


def _nested_script(words):
    """The script of `bash -c '...'` or `eval ...`, else None."""
    for index, word in enumerate(words):
        name = os.path.basename(word)
        if name == "eval" and index == 0:
            return " ".join(words[1:])
        if name not in _SHELLS:
            continue
        rest = words[index + 1:]
        for position, option in enumerate(rest):
            if not option.startswith("-") or option.startswith("--"):
                break
            if "c" in option[1:] and position + 1 < len(rest):
                return rest[position + 1]
        return None
    return None


def _coach_argv(words):
    """The arguments after `python -m coach` in a simple command, else None."""
    for index, word in enumerate(words):
        if not _PYTHON.match(os.path.basename(word)):
            continue
        position = index + 1
        while position < len(words) and words[position].startswith("-"):
            option = words[position]
            if option == "-mcoach":
                return words[position + 1:]
            if option == "-m":
                if position + 1 < len(words) and words[position + 1] == "coach":
                    return words[position + 2:]
                return None
            if option == "-c":
                return None
            position += 2 if option in _PYTHON_OPTIONS_WITH_VALUE else 1
        return None
    return None


def _http_write(words):
    """(method, url) when the command is an HTTP client writing to the Hevy API, else None."""
    url = next((word for word in words if HEVY_HOST in word), None)
    if url is None:
        return None
    for index, word in enumerate(words):
        name = os.path.basename(word)
        rest = words[index + 1:]
        if name == "curl":
            method = _curl_method(rest)
        elif name == "wget":
            method = _wget_method(rest)
        elif name in _HTTPIE:
            method = _httpie_method(rest)
        else:
            continue
        return (method, url) if method else None
    return None


def _curl_method(args):
    method, data, get = None, False, False
    position = 0
    while position < len(args):
        arg = args[position]
        following = args[position + 1] if position + 1 < len(args) else ""
        if arg == "--request":
            method = following
        elif arg.startswith("--request="):
            method = arg.split("=", 1)[1]
        elif arg == "--get":
            get = True
        elif arg in _CURL_DATA or arg.split("=", 1)[0] in _CURL_DATA:
            data = True
        elif arg.startswith("-") and not arg.startswith("--"):
            for offset, letter in enumerate(arg[1:], start=1):
                if letter == "G":
                    get = True
                if letter in _CURL_SHORT_WITH_VALUE:
                    value = arg[offset + 1:] or following
                    if letter == "X":
                        method = value
                    elif letter in "dFT":
                        data = True
                    break
        position += 1
    if method:
        method = method.upper()
        return None if method in _READ_METHODS else method
    return "POST" if data and not get else None


def _wget_method(args):
    for position, arg in enumerate(args):
        name, _, value = arg.partition("=")
        if name == "--method":
            method = (value or (args[position + 1] if position + 1 < len(args) else "")).upper()
            if method not in _READ_METHODS:
                return method
        if name in _WGET_DATA:
            return "POST"
    return None


def _httpie_method(args):
    seen_url = False
    for arg in args:
        if arg.startswith("-"):
            continue
        if not seen_url and arg.upper() in _WRITE_METHODS:
            return arg.upper()
        if HEVY_HOST in arg:
            seen_url = True
        elif seen_url and re.match(r"^[^:=]+(:=|=|@)", arg):
            return "POST"
    return None
