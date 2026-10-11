"""Whether the cached Hevy routines still carry the current overlay (contract C13)."""

from coach import overlay, paths, routines
from coach.checks import Result, check
from coach.errors import ValidationError
from coach.hevy.cache import HevyCache


@check(id="overlay_hevy_drift", owner="R-14")
def overlay_hevy_drift(ctx):
    if not ctx.config.hevy.enabled:
        return [Result("skip", "Hevy is turned off in config.toml.")]
    cache = HevyCache(ctx.root)
    cache_path = (paths.HEVY_CACHE_DIR / "routines.json").as_posix()
    try:
        if cache.read("routines") is None:
            return [Result("skip", "There is no Hevy routine cache yet; run python3 -m coach hevy pull.")]
        doc = routines.current_overlay(ctx.root, ctx.today())
        ids = routines.session_routines(ctx.root, doc) if doc else None
    except ValidationError as exc:
        return [Result("skip", f"cannot compare: {exc.message}")]
    if doc is None:
        return [Result("skip", "No overlay is in force or coming up.")]
    where = overlay.path_for(ctx.root, doc["id"]).relative_to(ctx.root).as_posix()
    results = [Result("warn", f"{s['title']} on {s['date']} in overlay {doc['id']} has no Hevy routine; run "
                              f"python3 -m coach routines create --overlay {doc['id']}.", where)
               for s in routines.unmapped_sessions(doc, ids)]
    for routine_id, session, _ in routines.plan(doc, ctx.today(), ids):
        cached = cache.routine(routine_id)
        if cached is None:
            results.append(Result("warn", f"{session['title']} ({routine_id}) is not in the Hevy cache; "
                                          "run python3 -m coach hevy pull.", cache_path))
            continue
        try:
            changes = routines.diff(routines.intended_body(doc, session, cached), cached)
        except ValidationError as exc:
            results.append(Result("warn", exc.message, where))
            continue
        if changes:
            structural = sum(1 for c in changes if c["class"] == routines.STRUCTURAL)
            results.append(Result(
                "warn",
                f"{cached.get('title') or session['title']} differs from overlay {doc['id']} in {len(changes)} "
                f"place(s), {structural} structural; run python3 -m coach routines diff --overlay {doc['id']}.",
                cache_path,
            ))
    if not results:
        results.append(Result("pass", f"Every routine in the cache matches overlay {doc['id']}.", cache_path))
    return results
