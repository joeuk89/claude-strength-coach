"""ActivityStore: the one reader of the activity-source files (contract C29, C30).

Files are append-only; for each id the last line wins, and a void line
removes the record from every view. Dedup and precedence happen here, at
read time, and never rewrite a file.
"""

from datetime import timedelta
from pathlib import Path

from coach import dates, jsonio, paths
from coach.activity import records

SYNC_SCHEMA = "activity_sync"
ACTIVITY_FIELDS = (
    "kind", "name", "indoor", "start", "end", "utc_offset", "local_date", "duration_seconds", "distance_meters",
    "elevation_gain_meters", "avg_hr", "max_hr", "active_kcal", "rpe", "device", "notes",
)
WELLNESS_FIELDS = ("sleep", "resting_hr_bpm", "hrv_ms", "steps", "body_mass_kg", "body_fat_pct")


def wellness_path(config, in_git=None):
    in_git = config.activity.wellness_in_git if in_git is None else in_git
    return paths.WELLNESS_COMMITTED if in_git else paths.WELLNESS_LOCAL


def _has(field, value):
    if field == "sleep":
        return isinstance(value, dict) and (value.get("asleep_hours") is not None
                                            or value.get("in_bed_hours") is not None)
    return value is not None


class ActivityStore:
    def __init__(self, root, config):
        self.root = Path(root)
        self.config = config
        self.precedence = list(config.activity.precedence)
        self.window = timedelta(minutes=config.activity.dedup_window_minutes)
        self.relative = {"activity": paths.ACTIVITIES, "planned": paths.PLANNED, "wellness": wellness_path(config)}
        self._lines = {}

    def path(self, kind):
        return self.root / self.relative[kind]

    def lines(self, kind):
        """Every line of a file, in the order written."""
        if kind not in self._lines:
            self._lines[kind] = records.read_lines(self.path(kind), kind, self.relative[kind].as_posix())
        return self._lines[kind]

    def latest(self, kind):
        """{id: last line} in first-seen order."""
        found = {}
        for line in self.lines(kind):
            found[line["id"]] = line
        return found

    def records(self, kind, include_void=False):
        """The last line per id; voided ids are left out unless include_void."""
        return [line for line in self.latest(kind).values() if include_void or line["op"] == "upsert"]

    def history(self, kind, record_id):
        return [line for line in self.lines(kind) if line["id"] == record_id]

    def rank(self, source):
        return self.precedence.index(source) if source in self.precedence else len(self.precedence)

    def _by_precedence(self, lines):
        newest_first = sorted(lines, key=lambda line: line["recorded_at"], reverse=True)
        return sorted(newest_first, key=lambda line: self.rank(line["source"]))

    def activity_groups(self):
        """Every resolved Activity, oldest first, with no date filter."""
        ordered = sorted(self.records("activity"),
                         key=lambda r: (r["start"], self.rank(r["source"]), r["id"]))
        groups = []
        for record in ordered:
            start = dates.parse_timestamp(record["start"])
            for group in groups:
                if (group["kind"] == record["kind"] and start - group["anchor"] <= self.window
                        and record["source"] not in group["sources"]):
                    group["members"].append(record)
                    group["sources"].add(record["source"])
                    break
            else:
                groups.append({"kind": record["kind"], "anchor": start, "members": [record],
                               "sources": {record["source"]}})
        resolved = [self._resolve_activity(group["members"]) for group in groups]
        return sorted(resolved, key=lambda a: (a["start"], a["id"]))

    def _resolve_activity(self, members):
        members = self._by_precedence(members)
        winner = members[0]
        out = {"id": winner["id"], "source": winner["source"], "source_id": winner.get("source_id")}
        sources = {}
        for field in ACTIVITY_FIELDS:
            out[field] = None
            for member in members:
                if member.get(field) is not None:
                    out[field] = member[field]
                    sources[field] = member["source"]
                    break
        out["merged_from"] = [member["id"] for member in members]
        out["field_sources"] = sources
        return out

    def activities(self, span, kinds=None):
        return [a for a in self.activity_groups()
                if span.contains(dates.parse_date(a["local_date"])) and (kinds is None or a["kind"] in kinds)]

    def planned(self, span, kinds=None):
        found = [records.strip(r) for r in self.records("planned")
                 if span.contains(dates.parse_date(r["date"])) and (kinds is None or r["kind"] in kinds)]
        return sorted(found, key=lambda r: (r["date"], self.rank(r["source"]), r["id"]))

    def wellness_days(self, span):
        daily, spans = {}, []
        for record in self.records("wellness"):
            start, end = (dates.parse_date(record["span"][key]) for key in ("start", "end"))
            if start == end:
                daily.setdefault(start, []).append(record)
            else:
                spans.append((dates.Span(start, end), record))
        days = []
        for day in span.days():
            candidates = (self._by_precedence(daily.get(day, []))
                          + self._by_precedence([r for s, r in spans if s.contains(day)]))
            resolved, sources, provenance = {"date": day.isoformat()}, {}, {}
            for field in WELLNESS_FIELDS:
                resolved[field] = None
                for record in candidates:
                    if _has(field, record.get(field)):
                        resolved[field] = record[field]
                        sources[field] = record["source"]
                        provenance[field] = {"id": record["id"], "source": record["source"],
                                             "span": record["span"],
                                             "kind": ("nightly" if record["span"]["start"] == record["span"]["end"]
                                                      else "period_mean")}
                        break
            if sources:
                resolved["field_sources"] = sources
                resolved["field_provenance"] = provenance
                days.append(resolved)
        return days

    def sleep_summary(self, span):
        evidence = {}
        for day in self.wellness_days(span):
            if day["sleep"] is None or day["sleep"].get("asleep_hours") is None:
                continue
            provenance = day["field_provenance"]["sleep"]
            item = evidence.setdefault(provenance["id"], dict(
                provenance, asleep_hours=day["sleep"]["asleep_hours"],
                self_report=provenance["source"] == "manual", resolved_dates=[]))
            item["resolved_dates"].append(day["date"])
        covered, weighted_hours, nightly_hours = [], 0, []
        for item in evidence.values():
            original = dates.Span(*(dates.parse_date(item["span"][key]) for key in ("start", "end")))
            original_dates = [day.isoformat() for day in original.days()]
            # A period mean cannot recover the average of only its unobserved or clipped nights.
            item["included_in_average"] = item["resolved_dates"] == original_dates
            if item["included_in_average"]:
                covered.extend(original_dates)
                weighted_hours += item["asleep_hours"] * len(original_dates)
            if item["kind"] == "nightly":
                nightly_hours.append(item["asleep_hours"])
        missing = sorted({day.isoformat() for day in span.days()} - set(covered))
        return {"avg_asleep_hours": round(weighted_hours / len(covered), 2) if covered else None,
                "nightly_avg_asleep_hours": (round(sum(nightly_hours) / len(nightly_hours), 2)
                                             if nightly_hours else None),
                "nights": len(nightly_hours), "nights_in_span": len(span.days()),
                "covered_dates": sorted(covered), "missing_dates": missing, "complete": not missing,
                "sources": sorted({item["source"] for item in evidence.values()}),
                "evidence": list(evidence.values())}

    def change(self, kind, line):
        """Whether appending `line` changes anything: a new or changed record, or a void of a live one."""
        history = self.history(kind, line["id"])
        last = history[-1] if history else None
        if line["op"] == "void":
            return last is not None and last["op"] == "upsert"
        if last is None:
            return True
        if last["op"] == "upsert":
            return last["content_hash"] != line["content_hash"]
        if last.get("by") == "sync":
            return True
        before = [entry for entry in history if entry["op"] == "upsert"]
        return not before or before[-1]["content_hash"] != line["content_hash"]

    def append(self, kind, lines, dry_run):
        if lines and not dry_run:
            records.append_lines(self.path(kind), lines)
            self._lines.pop(kind, None)

    def sync_map(self):
        path = self.root / paths.ACTIVITY_SYNC
        if not path.is_file():
            return {"schema_version": 1, "sources": {}}
        return jsonio.read_doc(path, SYNC_SCHEMA)

    def write_sync_map(self, doc, dry_run):
        jsonio.write_doc(self.root / paths.ACTIVITY_SYNC, doc, dry_run)
