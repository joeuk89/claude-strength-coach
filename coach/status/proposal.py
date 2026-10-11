"""Proposal drafts not yet finalised (contract C24, C52)."""

from pathlib import Path

from coach import paths
from coach.status import Section, provider


def unfinalised(root):
    """Ids of drafts in .coach/proposals/ that have no overlay yet, newest first."""
    directory = Path(root) / paths.PROPOSALS_DIR
    if not directory.is_dir():
        return []
    drafts = [p.stem for p in directory.glob("*.json") if "." not in p.stem]
    return sorted((d for d in drafts if not (Path(root) / paths.OVERLAYS_DIR / f"{d}.json").exists()), reverse=True)


@provider(id="proposal", owner="R-23a", order=35)
def proposal_status(ctx):
    found = unfinalised(ctx.root)
    if not found:
        return None
    lines = [f"Proposal {found[0]} is not finalised: finish it with python3 -m coach propose finalize --proposal "
             f"{found[0]}, or propose the week again."]
    if len(found) > 1:
        lines.append(f"{len(found) - 1} older unfinalised proposal(s): {', '.join(found[1:3])}.")
    return Section("proposal", lines, {"unfinalised": found}, "attention")
