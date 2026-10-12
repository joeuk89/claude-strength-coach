from coach import constraints, dates, niggles, paths, program
from coach.commands import arg, command
from coach.errors import UsageError, ValidationError
from coach.library import Library

_LIST = dict(action="append", metavar="A[,B...]")


def _split(values):
    """Comma-separated, repeatable values as one list; None when the option was not given. "" gives []."""
    if values is None:
        return None
    return [part.strip() for value in values for part in value.split(",") if part.strip()]


def _applies(args, library):
    """(patterns, exercises, activity kinds), each checked, or None where the option was not given."""
    patterns = _split(args.pattern)
    exercises = _split(args.exercise)
    kinds = _split([args.activity_kinds] if args.activity_kinds is not None else None)
    return (niggles.check_patterns(patterns) if patterns is not None else None,
            niggles.check_exercises(exercises, library) if exercises is not None else None,
            niggles.check_activity_kinds(kinds) if kinds is not None else None)


def _constrain_while(args):
    found = _split([args.constrain_while] if args.constrain_while is not None else None)
    return niggles.check_statuses(found) if found is not None else None


def _constraints(args, reason):
    if args.constraint is None:
        return None
    return [niggles.parse_constraint(text, reason) for text in args.constraint]


def _report_day(args, ctx):
    """The day the report describes: --date, else today; never after today."""
    today = ctx.today()
    if args.date is None:
        return today
    try:
        day = dates.parse_date(args.date)
    except ValueError as exc:
        raise ValidationError(f"--date: {exc}") from None
    if day > today:
        raise ValidationError(f"--date {day} is after today ({today}): date a report to when it happened")
    return day


_DATE_ARG = arg("--date", metavar="D", help="the day the report describes, YYYY-MM-DD (default today); a week's "
                                            "fatigue check counts only reports dated inside it")

_APPLIES_ARGS = (
    arg("--pattern", help="movement pattern(s) it affects, comma-separated or repeated; \"\" clears", **_LIST),
    arg("--exercise", help="library exercise id(s) it affects, comma-separated or repeated; \"\" clears", **_LIST),
    arg("--activity-kinds", metavar="K[,K...]", help="activity kinds it affects (run, ride, ...); \"\" clears"),
    arg("--constraint", action="append", metavar="KIND[=VALUE]",
        help="a load limit while it is active: rpe_cap=7, no_added_load, load_cap=20; repeat for several"),
    arg("--constrain-while", metavar="S[,S...]",
        help="statuses its constraints apply in (default aggravated,watching)"),
    arg("--notes", metavar="TEXT", help="its standing notes"),
)


@command("niggles list", help="Niggles with whether their constraints are active today and any escalation",
         args=(arg("--open", action="store_true", help="leave out resolved rows"),
               arg("--status", choices=niggles.STATUSES, help="only rows with this status")))
def list_niggles(args, ctx):
    today = ctx.today()
    doc = niggles.load(ctx.root)
    rows = [dict(row, constraints_active=niggles.constraints_active(row, today), escalate=niggles.escalation(row))
            for row in doc["niggles"]
            if (not args.open or niggles.is_open(row)) and (args.status is None or row["status"] == args.status)]
    return {"today": today.isoformat(), "niggles": rows, "flags": niggles.escalate_flags(doc)}


@command("niggles add", help="Log a new niggle, the movements it affects and the load limits it sets",
         args=(arg("--area", metavar="TEXT", help="where it is, e.g. \"left knee\""),
               arg("--status", choices=niggles.STATUSES, default="watching", help="default watching"),
               arg("--note", metavar="TEXT", help="the report, one line"),
               _DATE_ARG,
               *_APPLIES_ARGS),
         writes=True)
def add(args, ctx):
    library = Library.load(ctx.root)
    patterns, exercises, kinds = _applies(args, library)
    constrain_while = _constrain_while(args)
    if args.area is None or not args.area.strip():
        raise UsageError("--area must say where the niggle is")
    doc, row = niggles.add(
        niggles.load(ctx.root, library), args.area, _report_day(args, ctx), args.status, patterns or [],
        exercises or [], kinds or [], _constraints(args, args.area.strip()) or [],
        constrain_while if constrain_while is not None else niggles.DEFAULT_CONSTRAIN_WHILE, args.note, args.notes)
    niggles.save(ctx.root, doc, args.dry_run, library)
    return {"niggle": row, "written": not args.dry_run}


@command("niggles update", help="Record a check-in report on a niggle (status, note, mention) or change what it "
                                "applies to and its limits",
         args=(arg("id", metavar="ID", help="niggle id, e.g. n-0001"),
               arg("--status", choices=niggles.STATUSES, help="its status as of the report's day"),
               arg("--note", metavar="TEXT", help="the report, one line"),
               arg("--mention", action="store_true", help="the athlete reported it: bump mentions and last noted "
                                                          "(once a day)"),
               _DATE_ARG,
               arg("--area", metavar="TEXT", help="rename where it is"),
               arg("--clear-constraints", action="store_true", help="remove every constraint"),
               *_APPLIES_ARGS),
         writes=True)
def update(args, ctx):
    library = Library.load(ctx.root)
    patterns, exercises, kinds = _applies(args, library)
    constrain_while = _constrain_while(args)
    doc = niggles.load(ctx.root, library)
    current = next((row for row in doc["niggles"] if row["id"] == args.id), None)
    if current is None:
        raise ValidationError(f"No niggle {args.id} in {paths.NIGGLES}")
    if args.clear_constraints and args.constraint:
        raise UsageError("--clear-constraints and --constraint together: give the constraints to keep instead")
    found = [] if args.clear_constraints else _constraints(args, (args.area or current["area"]).strip())
    doc, row = niggles.update(doc, args.id, _report_day(args, ctx), args.status, args.note, args.mention,
                              area=args.area, notes=args.notes, patterns=patterns, exercises=exercises,
                              activity_kinds=kinds, constraints=found, constrain_while=constrain_while)
    niggles.save(ctx.root, doc, args.dry_run, library)
    return {"niggle": row, "written": not args.dry_run}


@command("niggles resolve", help="Mark a niggle resolved; the row is kept, since a recurrence is the signal",
         args=(arg("id", metavar="ID", help="niggle id, e.g. n-0001"),
               arg("--note", metavar="TEXT", help="the report, one line"),
               _DATE_ARG),
         writes=True)
def resolve(args, ctx):
    library = Library.load(ctx.root)
    doc, row = niggles.resolve(niggles.load(ctx.root, library), args.id, _report_day(args, ctx), args.note)
    niggles.save(ctx.root, doc, args.dry_run, library)
    return {"niggle": row, "written": not args.dry_run}


def _indices(text):
    if text is None:
        return []
    try:
        return [int(part) for part in text.split(",") if part.strip()]
    except ValueError:
        raise UsageError(f"--chronic {text!r}: give line numbers from the dry run, e.g. 1,3") from None


@command("niggles import", help="Convert profile.md's niggle log table into data/niggles.json, once; the dry run "
                                "also numbers the Injuries / limitations lines for --chronic",
         args=(arg("--from-profile", action="store_true", required=True, help="read profile.md"),
               arg("--chronic", metavar="I[,I...]", help="section lines that are lasting limitations: imported as "
                                                         "chronic rows; unmarked lines are not imported")),
         writes=True)
def import_profile(args, ctx):
    path = ctx.root / paths.PROFILE
    if not path.is_file():
        raise ValidationError(f"No {paths.PROFILE} to import from")
    library = Library.load(ctx.root)
    doc, rows, lines = niggles.import_profile(niggles.load(ctx.root, library), path.read_text(encoding="utf-8"),
                                              ctx.today(), _indices(args.chronic))
    if rows:
        niggles.save(ctx.root, doc, args.dry_run, library)
    return {"niggles": rows, "lines": lines, "written": bool(rows) and not args.dry_run}


@command("niggles constraints", help="Each program line a niggle constrains today, with the constraints",
         args=(arg("--session", metavar="S", help="one program session only"),))
def niggle_constraints(args, ctx):
    doc = program.load(ctx.root)
    sessions = [s for s in doc["sessions"] if args.session in (None, s["id"])]
    if args.session is not None and not sessions:
        raise ValidationError(f"No session {args.session} in {paths.PROGRAM}")
    today = ctx.today()
    lines = []
    for session in sessions:
        for exercise in session["exercises"]:
            found = [c for c in constraints.active(ctx.root, session["id"], exercise["exercise_id"], today)
                     if c["source"] != "slot"]
            if found:
                lines.append({"session_id": session["id"], "exercise_id": exercise["exercise_id"],
                              "constraints": found})
    return {"today": today.isoformat(), "lines": lines}
