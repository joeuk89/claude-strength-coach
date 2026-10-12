"""Proposal drafts not yet finalised (contract C24, C52)."""

import json
from pathlib import Path

from coach import overlay, paths
from coach.errors import ValidationError
from coach.status import Section, provider


def unfinalised(root):
    """Ids of drafts in .coach/proposals/ that have no overlay yet, newest first."""
    directory = Path(root) / paths.PROPOSALS_DIR
    if not directory.is_dir():
        return []
    drafts = [p.stem for p in directory.glob("*.json") if "." not in p.stem]
    return sorted((d for d in drafts if not (Path(root) / paths.OVERLAYS_DIR / f"{d}.json").exists()), reverse=True)


def _meta(root, proposal_id):
    try:
        return json.loads((Path(root) / paths.PROPOSALS_DIR / f"{proposal_id}.meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def drafts(root, today):
    """(open, stale) unfinalised draft ids, newest first; a stale draft's span ended or a newer approved overlay
    covers its remaining days, so it asks for nothing but a discard."""
    from coach.propose import stale_reason

    found = unfinalised(root)
    if not found:
        return [], []
    docs = []
    for overlay_id in overlay.ids(root):
        try:
            docs.append(overlay.load(root, overlay_id))
        except ValidationError:
            continue
    stale = [d for d in found if stale_reason(_meta(root, d), today, docs)]
    return [d for d in found if d not in stale], stale


@provider(id="proposal", owner="R-23a", order=35)
def proposal_status(ctx):
    found, stale = drafts(ctx.root, ctx.today())
    if not found and not stale:
        return None
    data = {"unfinalised": found, "stale": stale}
    if not found:
        return Section("proposal", [f"{len(stale)} stale proposal draft(s), ended or replaced by a newer approved "
                                    f"overlay: {', '.join(stale[:3])}; remove each with python3 -m coach propose "
                                    "discard --proposal <id>."], data, "info")
    lines = [f"Proposal {found[0]} is not finalised: finish it with python3 -m coach propose finalize --proposal "
             f"{found[0]}, propose the week again, or drop it with python3 -m coach propose discard --proposal "
             f"{found[0]}."]
    if len(found) > 1:
        lines.append(f"{len(found) - 1} older unfinalised proposal(s): {', '.join(found[1:3])}.")
    return Section("proposal", lines, data, "attention")
