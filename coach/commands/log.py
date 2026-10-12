"""`log` commands: the manual lifting log for athletes without Hevy (contract C46)."""

from coach import dates, log
from coach.commands import arg, command
from coach.errors import ValidationError
from coach.library import Library
from coach.overlay import read_json


def _date(text, flag):
    try:
        return dates.parse_date(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{flag}: {exc}") from None


@command("log list", help="The logged workouts no void removes, oldest first",
         args=(arg("--since", metavar="DATE", help="only workouts on or after this date"),))
def list_workouts(args, ctx):
    since = _date(args.since, "--since") if args.since else None
    found = [w for w in log.live(ctx.root) if since is None or w["date"] >= since]
    return {"workouts": found, "count": len(found), "path": log.label()}


@command("log prefill", help="A workout draft for one session as prescribed, and what to ask the athlete before log add",
         args=(arg("--session", required=True, metavar="ID", help="session id, e.g. session-a"),
               arg("--date", required=True, metavar="DATE", help="the day it was trained")))
def prefill(args, ctx):
    draft, ask = log.prefill(ctx.root, ctx.config, args.session, _date(args.date, "--date"), Library.load(ctx.root))
    return {"draft": draft, "ask": ask}


@command("log add", help="Validate a drafted workout, append it to the manual log and sync history",
         args=(arg("--input", required=True, metavar="FILE",
                   help="JSON workout line without id and logged_at, as log prefill gives it"),
               arg("--again", action="store_true", help="a second workout for the same date and session")),
         writes=True)
def add(args, ctx):
    data, warnings = log.add(ctx.root, ctx.config, Library.load(ctx.root), read_json(args.input), ctx.today(),
                             ctx.now(), again=args.again, dry_run=args.dry_run)
    for warning in warnings:
        ctx.warn(warning)
    return data


@command("log void", help="Remove a logged workout and sync history; its line stays in the log",
         args=(arg("id", help="workout id, e.g. manual:2026-10-12-session-a-1"),
               arg("--reason", required=True, metavar="TEXT")),
         writes=True)
def void(args, ctx):
    data, warnings = log.void(ctx.root, args.id, args.reason, ctx.now(), dry_run=args.dry_run)
    for warning in warnings:
        ctx.warn(warning)
    return data
