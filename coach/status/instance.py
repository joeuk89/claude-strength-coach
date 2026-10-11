"""Whether this copy is set up and its data files are at the versions this coach reads (contract C52)."""

from pathlib import Path

from coach import migrate, paths
from coach.status import INSTANCE, TEMPLATE, UNINITIALISED, Section, instance_kind, provider

MIGRATE = "python3 -m coach migrate run"


@provider(id="instance", owner="R-26b", order=10)
def instance(ctx):
    kind = instance_kind(ctx.root)
    if kind == TEMPLATE:
        return Section("instance", ["This is the template repo, not an athlete's instance."], {"kind": kind})
    if kind == UNINITIALISED:
        missing = [str(name) for name in (paths.CONFIG, paths.PROFILE) if not (Path(ctx.root) / name).is_file()]
        return Section("instance", [f"This copy is not set up yet (no {' or '.join(missing)}); run /setup."],
                       {"kind": kind, "missing": missing}, "attention")
    rows = migrate.status(ctx.root)
    behind = [row["path"] for row in rows if row["state"] in ("behind", "unreadable")]
    ahead = [row["path"] for row in rows if row["state"] == "ahead"]
    lines = []
    if behind:
        lines.append(f"{_count(behind)} behind the schema version this coach reads ({', '.join(behind)}); "
                     f"run {MIGRATE}.")
    if ahead:
        lines.append(f"{_count(ahead)} newer than this coach reads ({', '.join(ahead)}); run /framework-sync.")
    level = "attention" if lines else "info"
    return Section("instance", lines, {"kind": INSTANCE, "behind": behind, "ahead": ahead}, level)


def _count(found):
    return "1 data file is" if len(found) == 1 else f"{len(found)} data files are"
