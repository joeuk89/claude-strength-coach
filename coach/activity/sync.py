"""`activity sync`: fetch, normalise, hash, append what changed, record each source's state (contract C31)."""

import traceback
from collections import Counter

from coach.activity import adapters, records
from coach.errors import CoachError, ConfigError, UsageError, ValidationError


def file_kind(record):
    if "span" in record:
        return "wellness"
    if "date" in record and "start" not in record:
        return "planned"
    return "activity"


def run(ctx, store, only=None, dry_run=False):
    every = adapters.discover()
    sources = adapters.enabled_sources(ctx.config)
    if only is not None:
        if only not in every or not adapters.is_source(every[only]):
            known = ", ".join(name for name, m in every.items() if adapters.is_source(m)) or "none"
            raise UsageError(f"unknown activity source {only!r}; synced sources: {known}")
        if only not in sources:
            raise ConfigError(f"[sources.{only}] is not enabled in config.toml, so it cannot sync")
        sources = {only: sources[only]}

    sync_map = store.sync_map()
    now = records.utc_text(ctx.now())
    report = []
    for name, module in sources.items():
        previous = sync_map["sources"].get(name, {})
        try:
            result, pending, dropped = _collect(ctx, store, module, dict(previous.get("state", {})), now)
        except Exception as exc:
            if not isinstance(exc, CoachError):
                ctx.log(traceback.format_exc().rstrip())
            message = exc.message if isinstance(exc, CoachError) else f"{type(exc).__name__}: {exc}"
            ctx.warn(f"{name}: sync failed, so its records and sync state are unchanged: {message}")
            report.append({"source": name, "ok": False, "error": message})
            continue
        for warning in result.warnings:
            ctx.warn(f"{name}: {warning}")
        for reason, count in sorted(dropped.items()):
            ctx.warn(f"{name}: dropped {count} item(s): {reason}")
        appended = voided = 0
        for kind, lines in pending.items():
            store.append(kind, lines, dry_run)
            voided += sum(1 for line in lines if line["op"] == "void")
            appended += sum(1 for line in lines if line["op"] == "upsert")
        sync_map["sources"][name] = {"last_sync_at": now, "state": result.sync_state}
        report.append({"source": name, "ok": True, "appended": appended, "voided": voided,
                       "dropped": dict(sorted(dropped.items())), "last_sync_at": now})
    if any(row["ok"] for row in report):
        store.write_sync_map(sync_map, dry_run)
    return report


def _collect(ctx, store, module, state, now):
    result = module.fetch(ctx, state)
    dropped = Counter()
    batch = {}
    for item in result.items:
        try:
            normalised = module.normalise(item, ctx)
        except adapters.Drop as drop:
            dropped[drop.reason] += 1
            continue
        for record in normalised:
            kind, line = _line(store, module, record, now)
            if kind is not None:
                batch[(kind, line["id"])] = line
    pending = {}
    for (kind, _), line in batch.items():
        if store.change(kind, line):
            pending.setdefault(kind, []).append(line)
    return result, pending, dropped


def _line(store, module, record, now):
    if record.get("op") == "void":
        line = records.void_line(record["id"], record["source"], record["reason"], "sync", now)
        kind = next((k for k in module.KINDS if store.history(k, record["id"])), None)
    else:
        kind = file_kind(record)
        line = records.upsert_line(record, now)
    if kind is not None and kind not in module.KINDS:
        raise ValidationError(f"adapter {module.NAME} returned a {kind} record, but its KINDS are {module.KINDS}")
    if kind is not None:
        errors = records.line_errors(line, kind)
        if errors:
            raise ValidationError(f"adapter {module.NAME} returned an invalid {kind} record {line['id']}",
                                  details=[e.to_json() for e in errors])
    return kind, line
