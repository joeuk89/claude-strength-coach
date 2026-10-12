import json
import re
from pathlib import Path

from coach import dates, history
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _date(text, flag):
    if text is None:
        return None
    try:
        return dates.parse_date(text).isoformat()
    except ValueError as exc:
        raise UsageError(f"{flag}: {exc}") from None


@command("history sync", help="Resolve new and changed workouts from every history source into data/history/",
         writes=True)
def sync(args, ctx):
    report = history.sync(ctx.root, ctx.now(), args.dry_run)
    if report["unresolved"]:
        ctx.warn(f"{len(report['unresolved'])} exercise(s) have no library match or no confirmed load mode; "
                 "see data.unresolved, then python3 -m coach library seed or library confirm")
    return report


@command(
    "history rebuild",
    help="Re-resolve one month under the current rules; the only way to reinterpret stored loads",
    args=(arg("--month", required=True, metavar="YYYY-MM", help="the month file to rebuild"),),
    writes=True,
)
def rebuild(args, ctx):
    if not _MONTH.fullmatch(args.month):
        raise UsageError(f"--month: expected YYYY-MM, found {args.month!r}")
    return history.rebuild(ctx.root, args.month, ctx.now(), args.dry_run)


@command(
    "history show",
    help="Resolved workouts with annotations applied",
    args=(arg("--since", metavar="D", help="first date, YYYY-MM-DD"),
          arg("--until", metavar="D", help="last date, YYYY-MM-DD"),
          arg("--include-unsynced", action="store_true",
              help="also apply source changes not yet synced (new, changed and removed workouts), in memory; "
                   "nothing is written")),
)
def show(args, ctx):
    found = history.workouts(ctx.root, _date(args.since, "--since"), _date(args.until, "--until"),
                             args.include_unsynced, ctx.now())
    return {"workouts": found}


@command(
    "history annotations",
    help="The annotations in force (corrections and facts the log lacks)",
    args=(arg("--kind", choices=sorted(history.KIND_FIELDS), help="only this kind"),
          arg("--all", action="store_true",
              help="every annotation on file, each marked in_force (false once withdrawn, or a pure withdrawal)")),
)
def list_annotations(args, ctx):
    every = history.read_annotations(ctx.root)["annotations"]
    in_force = {a["id"] for a in history.active(every)}
    if args.all:
        found = [dict(a, in_force=a["id"] in in_force) for a in every]
    else:
        found = [a for a in every if a["id"] in in_force]
    return {"annotations": [a for a in found if args.kind is None or a["kind"] == args.kind]}


def _value(text, field):
    if text is None:
        return None
    if field == "type":
        return text
    if text == "null":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise UsageError(f"--value: expected a number for {field}, found {text!r}") from None


def _from_flags(args):
    if not args.kind:
        raise UsageError("give --kind, or --input FILE for a batch")
    kind = args.kind
    annotation = {"kind": kind, "source": args.source, "reason": args.reason}
    if args.withdraws:
        annotation["withdraws"] = args.withdraws
    if args.workout:
        annotation["workout_id"] = args.workout
    if args.exercise:
        annotation["exercise_id"] = args.exercise
    withdraws_only = args.withdraws and not (args.workout or args.exercise or args.field or args.value is not None)
    if args.set is not None or kind == "discount" or (kind == "repair" and not withdraws_only):
        annotation["set_index"] = args.set
    if args.field:
        annotation["field"] = args.field
    if args.value is not None or args.field:
        annotation["value"] = _value(args.value, args.field)
    if args.start or args.end:
        annotation["span"] = {"start": _date(args.start, "--start"), "end": _date(args.end, "--end")}
    if args.load_mode:
        annotation["load_mode"] = args.load_mode
    if args.date:
        annotation["date"] = _date(args.date, "--date")
    if args.session:
        annotation["session_id"] = args.session
    if kind == "miss" or args.tag:
        annotation["tag"] = args.tag
    if args.external:
        annotation["external_id"] = args.external
    if args.done is not None:
        annotation["done"] = args.done
    if kind in ("external", "trained_unlogged") or args.note:
        annotation["note"] = args.note
    return [{k: v for k, v in annotation.items() if not (k == "span" and None in v.values())}]


def _from_file(path):
    try:
        found = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path} cannot be read as JSON: {exc}") from None
    if isinstance(found, dict):
        found = found.get("annotations")
    if not isinstance(found, list) or not all(isinstance(a, dict) for a in found):
        raise ValidationError(f"{path} must hold a list of annotations (or {{\"annotations\": [...]}})")
    return [dict({"source": "coach", "reason": None}, **a) for a in found]


@command(
    "history annotate",
    help="Record a correction or a fact the log lacks in data/history/annotations.json",
    args=(
        arg("--kind", choices=sorted(history.KIND_FIELDS), help="what the annotation records"),
        arg("--workout", metavar="ID", help="workout id (discount, repair, confirm)"),
        arg("--exercise", metavar="ID", help="library exercise id"),
        arg("--set", type=int, metavar="N", help="set index; a discount without it covers the whole exposure"),
        arg("--field", choices=history.REPAIR_FIELDS, help="the field a repair corrects"),
        arg("--value", metavar="V", help="the corrected value (a number, or a set type)"),
        arg("--load-mode", choices=("total", "per_hand_x2", "single_implement", "bodyweight", "assisted", "band",
                                    "duration", "distance"), help="the load mode a load_mode annotation forces"),
        arg("--start", metavar="D", help="span start (load_mode, unknown_convention)"),
        arg("--end", metavar="D", help="span end (load_mode, unknown_convention)"),
        arg("--date", metavar="D", help="the day (miss, external, trained_unlogged)"),
        arg("--session", metavar="ID", help="session id (miss, trained_unlogged)"),
        arg("--tag", metavar="TAG", help=f"miss tag: {', '.join(history.MISS_TAGS)}"),
        arg("--external", metavar="ID", help="coach-led session id (external)"),
        arg("--done", dest="done", action="store_const", const=True, default=None, help="external: it happened"),
        arg("--not-done", dest="done", action="store_const", const=False, help="external: it did not happen"),
        arg("--note", metavar="TEXT", help="one line on what happened (external, trained_unlogged)"),
        arg("--reason", metavar="TEXT", help="why"),
        arg("--source", default="coach", metavar="TEXT", help="where it came from, e.g. check-in 2026-10-11"),
        arg("--withdraws", metavar="ID", help="the annotation this one withdraws"),
        arg("--input", metavar="FILE", help="a JSON list of annotations to add in one go"),
    ),
    writes=True,
)
def annotate(args, ctx):
    new = _from_file(args.input) if args.input else _from_flags(args)
    added = history.add_annotations(ctx.root, new, ctx.now(), args.dry_run, batch=bool(args.input))
    return {"annotations": added, "annotation": added[0] if len(added) == 1 else None, "written": not args.dry_run}
