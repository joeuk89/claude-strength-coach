"""Overlay checks: schema and consistency, load arithmetic, and fresh check-in regions (contract C13)."""

from coach import overlay, paths, render
from coach.checks import Result, check
from coach.errors import ValidationError


def _overlay_files(ctx):
    directory = ctx.root / paths.OVERLAYS_DIR
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def _file_results(ctx, kind):
    files = _overlay_files(ctx)
    if not files:
        return [Result("skip", f"no overlays in {paths.OVERLAYS_DIR}")]
    results = []
    for path in files:
        where = path.relative_to(ctx.root).as_posix()
        try:
            doc = overlay.read_json(path)
        except ValidationError as exc:
            if kind == overlay.SCHEMA_PROBLEM:
                results.append(Result("fail", exc.message, where))
            continue
        for found_kind, error in overlay.problems(doc, ctx.root, ctx.config):
            if found_kind == kind:
                results.append(Result("fail", f"{error.path}: {error.message}", where))
        if kind == overlay.SCHEMA_PROBLEM and isinstance(doc, dict) and doc.get("id") != path.stem:
            results.append(Result("fail", f"$.id: the file is named {path.name} but holds {doc.get('id')}", where))
    return results


@check(id="overlay_schema", owner="R-13")
def overlay_schema(ctx):
    return _file_results(ctx, overlay.SCHEMA_PROBLEM)


@check(id="overlay_arithmetic", owner="R-13")
def overlay_arithmetic(ctx):
    return _file_results(ctx, overlay.ARITHMETIC_PROBLEM)


@check(id="overlay_render_fresh", owner="R-13")
def overlay_render_fresh(ctx):
    directory = ctx.root / paths.CHECKINS_DIR
    records = sorted(directory.glob("*.md")) if directory.is_dir() else []
    if not records:
        return [Result("skip", f"no check-in records in {paths.CHECKINS_DIR}")]
    results = []
    for record in records:
        where = record.relative_to(ctx.root).as_posix()
        text = record.read_bytes().decode("utf-8")
        try:
            regions = render.find_regions(text, render.REGION_KIND)
        except ValueError as exc:
            results.append(Result("fail", str(exc), where))
            continue
        for overlay_id, start, end in regions:
            try:
                fresh = render.render_overlay(ctx.root, overlay_id)
            except (ValidationError, ValueError) as exc:
                message = exc.message if isinstance(exc, ValidationError) else str(exc)
                results.append(Result("fail", f"overlay {overlay_id} cannot be rendered: {message}", where))
                continue
            body = text[start + len(render.begin_marker(render.REGION_KIND, overlay_id)):
                        end - len(render.end_marker(render.REGION_KIND, overlay_id))]
            if not body.strip():
                results.append(Result(
                    "warn", f"the overlay {overlay_id} region is not rendered yet; "
                    f"run python3 -m coach overlay render {overlay_id} --into {where}", where))
            elif text[start:end] != fresh:
                results.append(Result(
                    "fail",
                    f"the overlay {overlay_id} region was edited by hand or is out of date; "
                    f"run python3 -m coach overlay render {overlay_id} --into {where}",
                    where,
                ))
    return results
