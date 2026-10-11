"""Checks on the activity-source files (contract C13, C29, C31, C32)."""

from coach import dates, jsonio, paths
from coach.activity import actions, adapters, associations, records
from coach.activity.store import SYNC_SCHEMA, ActivityStore, wellness_path
from coach.checks import Result, check
from coach.errors import ValidationError

OFF = "Activity sources are off ([activity] enabled = false)."


def _store(ctx):
    if not ctx.config.activity.enabled:
        return None
    return ActivityStore(ctx.root, ctx.config)


@check(id="activity_records_valid", owner="R-42a")
def activity_records_valid(ctx):
    if _store(ctx) is None:
        return [Result("skip", OFF)]
    files = [("activity", paths.ACTIVITIES), ("planned", paths.PLANNED),
             ("wellness", paths.WELLNESS_LOCAL), ("wellness", paths.WELLNESS_COMMITTED)]
    results = []
    for kind, relative in files:
        try:
            records.read_lines(ctx.root / relative, kind, relative.as_posix())
        except ValidationError as exc:
            results += [Result("fail", detail["message"], relative.as_posix()) for detail in exc.details]
    sync_path = ctx.root / paths.ACTIVITY_SYNC
    if sync_path.is_file():
        try:
            jsonio.read_doc(sync_path, SYNC_SCHEMA)
        except ValidationError as exc:
            where = paths.ACTIVITY_SYNC.as_posix()
            results += [Result("fail", f"{where}: {d['path']}: {d['message']}", where) for d in exc.details] \
                or [Result("fail", exc.message, where)]
    try:
        associations.load(ctx.root)
    except ValidationError as exc:
        results.append(Result("fail", exc.message, paths.ACTIVITY_ASSOCIATIONS.as_posix()))
    return results


@check(id="activity_wellness_location", owner="R-42a")
def activity_wellness_location(ctx):
    if _store(ctx) is None:
        return [Result("skip", OFF)]
    in_git = ctx.config.activity.wellness_in_git
    selected, other = wellness_path(ctx.config), wellness_path(ctx.config, not in_git)
    if not (ctx.root / other).is_file():
        return [Result("pass", f"Wellness records live at {selected.as_posix()}.", selected.as_posix())]
    return [Result("fail", f"A wellness file sits at {other.as_posix()}, but [activity] wellness_in_git = "
                           f"{'true' if in_git else 'false'} selects {selected.as_posix()}. "
                           f"Move it: {move_command(other, selected, ctx.root, leaving_git=not in_git)}",
                   other.as_posix())]


def move_command(source, target, root, leaving_git):
    source, target = source.as_posix(), target.as_posix()
    steps = [f"git rm --cached --quiet --ignore-unmatch {source}"] if leaving_git else []
    steps.append(f"mkdir -p {target.rsplit('/', 1)[0]}")
    if (root / target).is_file():
        steps.append(f"cat {source} >> {target} && rm {source}")
    else:
        steps.append(f"mv {source} {target}")
    return " && ".join(steps)


@check(id="activity_source_fresh", owner="R-42a")
def activity_source_fresh(ctx):
    store = _store(ctx)
    if store is None:
        return [Result("skip", OFF)]
    today = ctx.today()
    limit = ctx.config.activity.gap_warn_days
    sync_map = store.sync_map()["sources"]
    results = []
    for name, module in adapters.enabled_sources(ctx.config).items():
        if getattr(module, "FRESH_BY", "records") == "sync":
            synced = sync_map.get(name, {}).get("last_sync_at")
            newest = dates.parse_timestamp(synced).astimezone(ctx.timezone()).date() if synced else None
            basis = "last sync"
        else:
            live = {kind: [r for r in store.records(kind) if r["source"] == name] for kind in module.KINDS}
            text = actions.newest_date(live)
            newest = dates.parse_date(text) if text else None
            basis = "newest record"
        if newest is None:
            results.append(Result("warn", f"{name} has no {basis} yet; run python3 -m coach activity sync."))
            continue
        age = (today - newest).days
        if age > limit:
            results.append(Result("warn", f"{name}'s {basis} is from {newest} ({age} days ago, past "
                                          f"gap_warn_days = {limit}); run python3 -m coach activity sync."))
        else:
            results.append(Result("pass", f"{name}'s {basis} is from {newest} ({age} day(s) ago)."))
    return results
