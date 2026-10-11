import copy
import json
from pathlib import Path

from coach import jsonio, library, paths, program, units
from coach.commands import arg, command
from coach.errors import ConfigError, UsageError, ValidationError
from coach.hevy.cache import HevyCache
from coach.library import Library
from coach.validate import validate as validate_schema


def _entry(lib, exercise_id):
    entry = lib.get(exercise_id)
    if entry is None:
        hits = [hit["id"] for hit in lib.search(exercise_id.replace("_", " "))[:5]]
        hint = f"; did you mean {', '.join(hits)}?" if hits else "; see python3 -m coach library search TEXT"
        raise ValidationError(f"no library exercise has the id {exercise_id!r}{hint}")
    return entry


@command(
    "library list",
    help="List every library exercise with its confirmed load mode",
    args=(arg("--avoided", action="store_true", help="only the exercises the athlete avoids, with the reason"),),
)
def list_exercises(args, ctx):
    rows = [library.summary(entry) for entry in Library.load(ctx.root).entries()]
    if args.avoided:
        rows = [row for row in rows if row["avoid"] is not None]
    return {"exercises": rows, "count": len(rows)}


@command("library show", help="Show one exercise: the catalogue entry merged with the instance file",
         args=(arg("id", help="library exercise id"),))
def show(args, ctx):
    return {"exercise": _entry(Library.load(ctx.root), args.id)}


@command("library search", help="Find exercises by name, alias, Hevy title or id",
         args=(arg("text", help="words to look for"),))
def search(args, ctx):
    return {"query": args.text, "matches": Library.load(ctx.root).search(args.text)}


@command("library validate", help="Validate the catalogue and data/exercises.json; exit 1 with the JSONPath of each problem")
def validate(args, ctx):
    lib = Library.load(ctx.root)
    return {
        "valid": True,
        "path": paths.EXERCISES,
        "instance_file": lib.path.exists(),
        "catalogue_entries": len(library.catalogue()),
        "instance_entries": len(lib.instance["exercises"]),
    }


def _write(lib, doc, args):
    Library(doc, lib.path)
    jsonio.write_doc(lib.path, _sorted(doc), args.dry_run)
    return not args.dry_run


def _program_slots(ctx, lib, ids):
    """Lines of data/program.json left in another mode than the one `lib` confirms for `ids`, each with a warning."""
    if not program.exists(ctx.root):
        return []
    try:
        doc = program.read_json(program.path_for(ctx.root))
    except ValidationError:
        return []
    found = [row for exercise_id in ids for row in program.load_mode_mismatches(doc, lib, exercise_id)]
    for row in found:
        ctx.warn(f"{paths.PROGRAM.as_posix()}: {program.mismatch_message(row)}")
    return found


def _sorted(doc):
    return {"schema_version": doc["schema_version"],
            "exercises": {key: doc["exercises"][key] for key in sorted(doc["exercises"])}}


_SEPARATE_STEPS = {
    "hevy_template_id": "Hevy mapping is a separate step once a real Hevy template is confirmed",
    "hevy_template_ids": "Hevy mapping is a separate step once a real Hevy template is confirmed",
    "load_mode_proposed": "library seed records it for imported exercises",
    "confidence": "library seed records it for imported exercises",
    "avoid": "record it after creation with library set-avoid",
}


@command(
    "library create",
    help="Create a custom exercise from an instance-entry JSON file; preview with --dry-run",
    args=(arg("id", help="new custom_ library exercise id"),
          arg("--input", required=True, metavar="FILE",
              help="one exercise_library entry with required facts and a confirmed load_mode")),
    writes=True,
)
def create(args, ctx):
    lib = Library.load(ctx.root)
    existing = lib.get(args.id)
    if existing is not None and existing["source"] == "catalogue":
        raise ValidationError(f"{args.id!r} is a catalogue id; choose a new custom_ id; creation cannot override it")
    if not args.id.startswith(library.CUSTOM_PREFIX) or not library.ID_PATTERN.fullmatch(args.id):
        raise ValidationError("a custom exercise id must start custom_ and contain only lowercase letters, "
                              "digits and underscores")
    source = Path(args.input)
    try:
        entry = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read custom exercise JSON from {source}: {exc}") from None
    if not isinstance(entry, dict):
        raise ValidationError(f"{source} must contain one exercise_library entry object")
    if existing is not None:
        if lib.instance["exercises"][args.id] != entry:
            raise ValidationError(f"{args.id!r} already exists with different metadata; creation cannot update it. "
                                  "Use library show to review it or choose a new custom_ id")
        return {"exercise": existing, "path": paths.EXERCISES, "unchanged": True, "written": False}
    refused = [f"{key} ({reason})" for key, reason in _SEPARATE_STEPS.items() if key in entry]
    if refused:
        raise ValidationError(f"creation does not accept {'; '.join(refused)}; remove it from {source}")
    missing = [key for key in (*library.CUSTOM_REQUIRED, "load_mode") if key not in entry]
    if missing:
        raise ValidationError(f"a custom exercise needs explicit values for: {', '.join(missing)}")
    if entry["load_mode"] is None:
        raise ValidationError("load_mode must be the athlete's confirmed mode; see library set-mode --help")
    doc = copy.deepcopy(lib.instance)
    doc["exercises"][args.id] = entry
    errors = validate_schema(doc, jsonio.load_schema("exercise_library"))
    if errors:
        raise ValidationError("custom exercise does not match the exercise_library schema",
                              details=[error.to_json() for error in errors])
    try:
        proposed = Library(doc, lib.path)
    except ValidationError as exc:
        raise ValidationError("custom exercise conflicts with the exercise library", details=exc.details) from None
    written = _write(lib, doc, args)
    return {"exercise": proposed.get(args.id), "path": paths.EXERCISES, "unchanged": False, "written": written}


@command(
    "library seed",
    help="Match every exercise in the cached Hevy routines to the library and record a proposed load mode",
    writes=True,
)
def seed(args, ctx):
    cache = HevyCache(ctx.root)
    if cache.read("routines") is None:
        raise ConfigError("there are no cached Hevy routines to seed from; run python3 -m coach hevy pull first")
    routines = cache.routines()
    templates = cache.exercise_templates() if cache.read("exercise_templates") is not None else None
    if templates is None:
        ctx.warn("no cached Hevy exercise templates, so proposals use routine titles only, without Hevy's "
                 "exercise type or equipment; run python3 -m coach hevy pull for better proposals")
    lib = Library.load(ctx.root)
    proposals, doc, guessed = library.seed(lib, routines, templates)
    for line in guessed:
        ctx.warn(line)
    unchanged = lib.path.exists() and doc == lib.instance
    written = False if unchanged else _write(lib, doc, args)
    return {"proposals": proposals, "guessed": guessed, "path": paths.EXERCISES, "written": written}


@command(
    "library confirm",
    help="Confirm the proposed load mode of the named exercises, or of every unconfirmed one with --all",
    args=(
        arg("ids", nargs="*", metavar="ID", help="library exercise ids"),
        arg("--all", action="store_true", help="every instance entry with a proposal and no confirmed mode"),
    ),
    writes=True,
)
def confirm(args, ctx):
    if bool(args.ids) == bool(args.all):
        raise UsageError("give exercise ids or --all, not both")
    lib = Library.load(ctx.root)
    doc = copy.deepcopy(lib.instance)
    own = doc["exercises"]
    if args.all:
        ids = [i for i in sorted(own) if own[i].get("load_mode") is None and own[i].get("load_mode_proposed")]
    else:
        ids = list(dict.fromkeys(args.ids))
        for exercise_id in ids:
            _entry(lib, exercise_id)
        missing = [i for i in ids if not own.get(i, {}).get("load_mode_proposed")]
        if missing:
            raise ValidationError(
                f"no proposed load mode to confirm for {', '.join(missing)}; run python3 -m coach library seed, "
                "or set one with python3 -m coach library set-mode ID MODE"
            )
    confirmed = []
    for exercise_id in ids:
        previous = own[exercise_id].get("load_mode")
        own[exercise_id]["load_mode"] = own[exercise_id]["load_mode_proposed"]
        confirmed.append({"id": exercise_id, "load_mode": own[exercise_id]["load_mode"], "previous": previous})
    unconfirmed = sorted(i for i in own if own[i].get("load_mode") is None)
    written = _write(lib, doc, args) if confirmed else False
    slots = _program_slots(ctx, Library(doc, lib.path), [row["id"] for row in confirmed])
    return {"confirmed": confirmed, "still_unconfirmed": unconfirmed, "written": written, "program_slots": slots}


@command(
    "library set-mode",
    help="Record the athlete's load mode for one exercise",
    args=(arg("id", help="library exercise id"), arg("mode", help=f"one of {', '.join(units.LOAD_MODES)}")),
    writes=True,
)
def set_mode(args, ctx):
    if args.mode not in units.LOAD_MODES:
        raise ValidationError(f"{args.mode!r} is not a load mode; valid modes: {', '.join(units.LOAD_MODES)}")
    lib = Library.load(ctx.root)
    _entry(lib, args.id)
    doc = copy.deepcopy(lib.instance)
    own = doc["exercises"].setdefault(args.id, {})
    previous = own.get("load_mode")
    own["load_mode"] = args.mode
    written = _write(lib, doc, args) if previous != args.mode else False
    slots = _program_slots(ctx, Library(doc, lib.path), [args.id])
    return {"id": args.id, "load_mode": args.mode, "previous": previous, "written": written, "program_slots": slots}


@command(
    "library set-avoid",
    help="Record that the athlete cannot or will not do an exercise, with the reason; --clear removes it",
    args=(
        arg("id", help="library exercise id"),
        arg("--reason", help="why the athlete avoids it, in plain words"),
        arg("--clear", action="store_true", help="the athlete no longer avoids it"),
    ),
    writes=True,
)
def set_avoid(args, ctx):
    if (args.reason is None) == (not args.clear):
        raise UsageError("give --reason TEXT or --clear")
    if args.reason is not None and not args.reason.strip():
        raise ValidationError("--reason must say why the athlete avoids the exercise; it is empty")
    lib = Library.load(ctx.root)
    _entry(lib, args.id)
    doc = copy.deepcopy(lib.instance)
    avoid = None if args.clear else {"reason": args.reason.strip()}
    if args.clear and args.id not in doc["exercises"]:
        return {"id": args.id, "avoid": None, "previous": None, "written": False}
    own = doc["exercises"].setdefault(args.id, {})
    previous = own.get("avoid")
    own["avoid"] = avoid
    written = _write(lib, doc, args) if previous != avoid else False
    return {"id": args.id, "avoid": avoid, "previous": previous, "written": written}
