"""The `coach check` summary (contract C52)."""

from coach import checks
from coach.status import Section, provider

@provider(id="checks", owner="R-26b", order=20)
def check_summary(ctx):
    rows, summary = checks.run(ctx, checks.discover())
    failing = _ids(rows, "fail")
    warning = _ids(rows, "warn")
    counts = ", ".join(f"{summary[status]} {status}" for status in ("pass", "warn", "fail", "skip"))
    lines = [f"coach check: {counts}."]
    if failing:
        lines.append(f"Failing: {', '.join(failing)}; run python3 -m coach check --only {','.join(failing)}.")
    if warning:
        lines.append(f"Warnings: {', '.join(warning)}.")
    data = {"summary": summary, "fail": failing, "warn": warning}
    return Section("checks", lines, data, "attention" if failing else "info")


def _ids(rows, status):
    return list(dict.fromkeys(row["id"] for row in rows if row["status"] == status))
