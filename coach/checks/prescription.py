"""Every overlay in force today or later has no unresolved blocking prescription finding (contract C22)."""

from datetime import timedelta

from coach import dates, overlay, paths, validity
from coach.checks import Result, check
from coach.errors import ValidationError


def _in_force_from(docs, today):
    """The overlays in force on some day from today on."""
    found = {}
    for doc in docs:
        start = max(dates.parse_date(doc["span"]["start"]), today)
        end = dates.parse_date(doc["span"]["end"])
        day = start
        while day <= end:
            picked = overlay.pick_in_force(docs, day)
            if picked and picked[0]["id"] == doc["id"]:
                found[doc["id"]] = doc
                break
            day += timedelta(days=1)
    return [found[key] for key in sorted(found)]


@check(id="prescription_valid", owner=validity.OWNER)
def prescription_valid(ctx):
    docs = []
    for overlay_id in overlay.ids(ctx.root):
        try:
            docs.append(overlay.load(ctx.root, overlay_id))
        except ValidationError:
            continue
    live = _in_force_from(docs, ctx.today())
    if not live:
        return [Result("skip", "No overlay is in force today or later.", paths.OVERLAYS_DIR.as_posix())]
    results = []
    for doc in live:
        where = overlay.path_for(ctx.root, doc["id"]).relative_to(ctx.root).as_posix()
        try:
            found = validity.report(ctx.root, doc, ctx.config)["flags"]
        except ValidationError as exc:
            results.append(Result("skip", f"{doc['id']} cannot be checked: {exc.message}", where))
            continue
        for flag in validity.unresolved_blocks(doc, found):
            results.append(Result("fail", (
                f"{flag['code']}: {flag['message']}; settle it, then run python3 -m coach prescription check "
                f"--overlay {doc['id']} --write"), where))
    return results
