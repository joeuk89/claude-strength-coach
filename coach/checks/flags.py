"""Every overlay flag uses a registered code (contract C20)."""

from coach import flags, overlay, paths
from coach.checks import Result, check
from coach.errors import ValidationError


@check(id="flag_codes_known", owner="R-20")
def flag_codes_known(ctx):
    directory = ctx.root / paths.OVERLAYS_DIR
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if not files:
        return [Result("skip", f"no overlays in {paths.OVERLAYS_DIR}")]
    results = []
    for path in files:
        where = path.relative_to(ctx.root).as_posix()
        try:
            doc = overlay.read_json(path)
        except ValidationError:
            continue
        found = doc.get("flags") if isinstance(doc, dict) else None
        for index, flag in enumerate(found if isinstance(found, list) else []):
            code = flag.get("code") if isinstance(flag, dict) else None
            if not flags.is_known(code):
                results.append(Result("fail", f"$.flags[{index}].code: {code!r} is not a registered flag code", where))
    return results
