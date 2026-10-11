"""Research note checks (contract C13, C28). All four skip when the instance has no research/ directory."""

from coach import paths, research
from coach.checks import Result, check
from coach.errors import ValidationError

_SKIP = [Result("skip", "no research/ directory", str(paths.RESEARCH_DIR))]


def _has_research(ctx):
    return (ctx.root / paths.RESEARCH_DIR).is_dir()


@check(id="research_notes", owner="R-32a")
def research_notes(ctx):
    if not _has_research(ctx):
        return _SKIP
    notes, problems, _ = research.load_all(ctx.root)
    if problems:
        return [Result(problem.status, problem.message, problem.path) for problem in problems]
    return [Result("pass", f"{len(notes)} research note(s) are valid.", str(paths.RESEARCH_DIR))]


@check(id="research_citations", owner="R-32a")
def research_citations(ctx):
    if not _has_research(ctx):
        return _SKIP
    notes, _, invalid = research.load_all(ctx.root)
    citations = research.scan_citations(ctx.root, notes)
    problems = research.citation_problems(citations, invalid)
    if problems:
        return [Result(problem.status, problem.message, problem.path) for problem in problems]
    return [Result("pass", f"{len(citations)} claim reference(s) checked; none needs attention.")]


@check(id="research_render_fresh", owner="R-32a")
def research_render_fresh(ctx):
    if not _has_research(ctx):
        return _SKIP
    notes, _, _ = research.load_all(ctx.root)
    results = []
    for note in notes:
        fix = f"run python3 -m coach research render {note.id}"
        try:
            region = research.region_in(note)
        except ValidationError as exc:
            results.append(Result("fail", f"{note.path}: {exc.message}", note.path))
            continue
        if region is None:
            results.append(Result("fail", f"{note.path} has no rendered region; {fix}", note.path))
        elif region != research.render_note(note):
            results.append(Result("fail", f"{note.path}: the rendered region is stale or was edited by hand; {fix}",
                                  note.path))
    return results or [Result("pass", f"{len(notes)} rendered region(s) are fresh.")]


@check(id="research_expiry", owner="R-32a")
def research_expiry(ctx):
    if not _has_research(ctx):
        return _SKIP
    today = ctx.today()
    notes, _, _ = research.load_all(ctx.root)
    by_id = {note.id: note for note in notes}
    expired = research.expired_areas(notes, today)
    results = []
    for area, note_ids in expired.items():
        listed = ", ".join(f"{note_id} (review by {by_id[note_id].review_by.isoformat()})" for note_id in note_ids)
        results.append(Result(
            "warn",
            f"research area {area} is expired: {listed}. Write or refresh a local note in this area "
            "(reference/research-notes.md).",
            by_id[note_ids[0]].path,
        ))
    return results or [Result("pass", f"no research area is expired on {today.isoformat()}.")]
