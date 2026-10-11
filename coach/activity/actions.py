"""What the activity, wellness and planned commands share: the enabled gate, spans, manual ids, add, void, status."""

from datetime import timedelta

from coach import dates, units
from coach.activity import adapters, records
from coach.activity.adapters import manual
from coach.activity.store import ActivityStore
from coach.errors import ConfigError, ValidationError

STATUS_DAYS = 14


def store_for(ctx):
    if not ctx.config.activity.enabled:
        raise ConfigError("[activity] enabled is false in config.toml; use /setup for athlete-approved "
                          "[activity] enabled = true and config validate; manual sleep needs no watch")
    return ActivityStore(ctx.root, ctx.config)


def parse_date(text, flag):
    try:
        return dates.parse_date(text)
    except ValueError as exc:
        raise ValidationError(f"{flag}: {exc}") from None


def span(args, ctx):
    """--from/--to; either left out falls back to the week holding today."""
    week = dates.week_span(ctx.today(), ctx.config.athlete.week_starts)
    start = parse_date(args.start, "--from") if args.start else week.start
    end = parse_date(args.end, "--to") if args.end else week.end
    try:
        return dates.Span(start, end)
    except ValueError as exc:
        raise ValidationError(str(exc)) from None


def distance_meters(args):
    given = [(unit, getattr(args, f"distance_{unit}")) for unit in ("km", "mi", "m")
             if getattr(args, f"distance_{unit}", None) is not None]
    if len(given) > 1:
        raise ValidationError("give one distance: --distance-km, --distance-mi or --distance-m")
    if not given:
        return None
    unit, value = given[0]
    try:
        return units.to_meters(value, unit)
    except ValueError as exc:
        raise ValidationError(f"--distance-{unit}: {exc}") from None


def minutes_to_seconds(value, flag):
    if value is None:
        return None
    if value <= 0:
        raise ValidationError(f"{flag} must be above zero, found {value:g}")
    return round(value * 60)


def next_manual_id(store, kind, day, record_kind):
    prefix = f"manual:{day}-{record_kind}-"
    taken = [int(line["id"][len(prefix):]) for line in store.lines(kind)
             if line["id"].startswith(prefix) and line["id"][len(prefix):].isdigit()]
    return f"{prefix}{max(taken, default=0) + 1}"


def build_manual(ctx, kind, item):
    """The full line for a manual record, validated."""
    record = manual.normalise(dict(item, file=kind), ctx)[0]
    line = records.upsert_line(record, records.utc_text(ctx.now()))
    errors = records.line_errors(line, kind)
    if errors:
        raise ValidationError(f"the {kind} record is not valid: {errors[0].path}: {errors[0].message}",
                              details=[e.to_json() for e in errors])
    return line


def write(store, kind, line, dry_run):
    changed = store.change(kind, line)
    if changed:
        store.append(kind, [line], dry_run)
    return {"record": line, "path": store.relative[kind], "changed": changed, "written": changed and not dry_run}


def void(ctx, store, kind, record_id, reason, dry_run):
    if not reason.strip():
        raise ValidationError("--reason must not be empty")
    current = store.latest(kind).get(record_id)
    if current is None:
        raise ValidationError(f"no {kind} record has the id {record_id!r}")
    if current["op"] == "void":
        raise ValidationError(f"{record_id} is already void ({current['reason']})")
    line = records.void_line(record_id, current["source"], reason.strip(), "athlete", records.utc_text(ctx.now()))
    store.append(kind, [line], dry_run)
    return {"void": line, "path": store.relative[kind], "written": not dry_run}


def status(ctx, store):
    today = ctx.today()
    window = dates.Span(today - timedelta(days=STATUS_DAYS - 1), today)
    sync_map = store.sync_map()["sources"]
    every = adapters.discover()
    names = ["manual", *adapters.enabled_sources(ctx.config)]
    rows = []
    for name in names:
        module = every[name]
        live = {kind: [r for r in store.records(kind) if r["source"] == name] for kind in module.KINDS}
        rows.append({
            "source": name,
            "last_sync_at": sync_map.get(name, {}).get("last_sync_at"),
            "counts": {kind: len(found) for kind, found in live.items()},
            "newest_date": newest_date(live),
            "missing_days": (None if "wellness" not in module.KINDS
                             else [d.isoformat() for d in window.days() if not _covers(live["wellness"], d)]),
        })
    return {"sources": rows, "window": window.to_json(), "wellness_path": store.relative["wellness"]}


def newest_date(live):
    found = [r["local_date"] for r in live.get("activity", [])] + [r["span"]["end"] for r in live.get("wellness", [])]
    return max(found, default=None)


def _covers(found, day):
    text = day.isoformat()
    return any(r["span"]["start"] <= text <= r["span"]["end"] for r in found)

