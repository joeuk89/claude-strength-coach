"""Check-in record checks: titles that parse, and prose kept short (contract C36)."""

from coach import checkin, paths
from coach.checks import Result, check

OWNER = "R-21a"


def _record_files(ctx):
    directory = ctx.root / paths.CHECKINS_DIR
    if not directory.is_dir():
        return []
    return [p for p in sorted(directory.glob("*.md")) if checkin.is_record_name(p.name)]


@check(id="checkin_records", owner=OWNER)
def checkin_records(ctx):
    results = []
    for path in _record_files(ctx):
        rel = (paths.CHECKINS_DIR / path.name).as_posix()
        title = checkin.parse_title(checkin.first_line(path))
        if title is None:
            results.append(Result("warn", (
                f"{rel}: the first line is not '# Check-in — YYYY-MM-DD (weekly|deep|catch-up)', so the record "
                "counts as deep; fix the title line"), rel))
        elif title[0].isoformat() != path.stem:
            results.append(Result("warn", f"{rel}: the title is dated {title[0]}, the file name {path.stem}", rel))
    return results


@check(id="checkin_record_words", owner=OWNER)
def checkin_record_words(ctx):
    results = []
    for record in checkin.records(ctx.root):
        text = (ctx.root / record.path).read_text(encoding="utf-8")
        if not checkin.has_review(text):
            continue
        words = checkin.prose_words(text)
        ceiling = checkin.WORD_CEILINGS.get(record.tier, checkin.WORD_CEILINGS["weekly"])
        if words > ceiling:
            rel = record.path.as_posix()
            results.append(Result("warn", (
                f"{rel}: {words} words of prose outside its rendered regions, over the {ceiling}-word ceiling for a "
                f"{record.tier} record (a heuristic); cut it or let the data carry it"), rel))
    return results
