"""The `python3 -m coach` entry point: parse, run one command, print one envelope (contract C2, C3)."""

import argparse
import json
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import PurePath

from coach import commands as commands_package
from coach.context import Context
from coach.errors import ERROR_CODES, CoachError, ExitCode, UsageError

ENVELOPE_VERSION = 1


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        where = self.prog.removeprefix("coach").strip()
        raise UsageError(f"{where}: {message}" if where else message)


def build_parser(commands):
    """Return (root parser, {command name: its subparser})."""
    parser = _Parser(prog="coach", description="Coach scripts: one JSON envelope on stdout per run.")
    parser.add_argument("--root", help="instance root (default: $COACH_ROOT, then the current directory)")
    top = parser.add_subparsers(dest="_group", metavar="<group>", required=True, parser_class=_Parser)
    groups, subparsers = {}, {}
    names = {c.name for c in commands}
    for cmd in commands:
        words = cmd.name.split()
        if len(words) == 1:
            if any(n.startswith(cmd.name + " ") for n in names):
                raise RuntimeError(f"{cmd.name!r} is both a command and a group")
            sub = top.add_parser(cmd.name, help=cmd.help, description=cmd.help)
        else:
            group, name = words
            if group not in groups:
                group_parser = top.add_parser(group, help=f"{group} commands")
                groups[group] = group_parser.add_subparsers(
                    dest="_command_word", metavar="<command>", required=True, parser_class=_Parser
                )
            sub = groups[group].add_parser(name, help=cmd.help, description=cmd.help)
        for flags, kwargs in cmd.args:
            sub.add_argument(*flags, **kwargs)
        if cmd.accepts_dry_run:
            sub.add_argument("--dry-run", action="store_true", help="do every read and check; write nothing")
        sub.set_defaults(_command=cmd.name)
        subparsers[cmd.name] = sub
    return parser, subparsers


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, PurePath):
        return value.as_posix()
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


def _emit(stdout, envelope):
    stdout.write(json.dumps(envelope, ensure_ascii=False, default=_json_default) + "\n")


def _envelope(command_name, warnings, data=None, error=None):
    envelope = {"schema_version": ENVELOPE_VERSION, "ok": error is None, "command": command_name}
    if data is not None:
        envelope["data"] = data
    if error is not None:
        envelope["error"] = error
    envelope["warnings"] = list(warnings)
    return envelope


def resolve_root(option, env):
    return option or env.get("COACH_ROOT") or os.getcwd()


def main(argv=None, env=None, stdout=None, stderr=None, commands=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    command_name, ctx = None, None
    try:
        commands = commands_package.discover() if commands is None else commands
        parser, _ = build_parser(commands)
        args = parser.parse_args(argv)
        cmd = next(c for c in commands if c.name == args._command)
        command_name = cmd.name
        ctx = Context(resolve_root(args.root, env), env, stderr)
        data = cmd.func(args, ctx)
        _emit(stdout, _envelope(command_name, ctx.warnings, data=data if data is not None else {}))
        return int(ExitCode.OK)
    except CoachError as exc:
        warnings = ctx.warnings if ctx else []
        if ctx:
            ctx.log(exc.message)
        else:
            stderr.write(f"coach: {exc.message}\n")
        error = {"code": exc.code, "message": exc.message}
        if exc.details:
            error["details"] = exc.details
        _emit(stdout, _envelope(command_name, warnings, data=exc.data, error=error))
        return int(exc.exit_code)
    except Exception as exc:
        for line in traceback.format_exc().rstrip().splitlines():
            stderr.write(f"coach: {line}\n")
        error = {
            "code": ERROR_CODES[ExitCode.INTERNAL],
            "message": f"Internal error ({type(exc).__name__}: {exc}); the traceback is on stderr.",
        }
        _emit(stdout, _envelope(command_name, ctx.warnings if ctx else [], error=error))
        return int(ExitCode.INTERNAL)
