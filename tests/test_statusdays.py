"""Status days: the commands, the readers and the illness return rule (contract C22, C50)."""

import json
import unittest

from coach import dates, statusdays
from tests.support import INSTANCES
from tests.test_cardio import CardioCase

LAYOFF = INSTANCES / "layoff"


def span(start, end):
    return dates.Span(dates.parse_date(start), dates.parse_date(end))


class CommandsTest(CardioCase):
    def path(self):
        return self.root / "data" / "status-days.json"

    def test_add_dry_run_writes_nothing(self):
        before = self.path().read_bytes()
        data = self.data("status-days", "add", "--kind", "ill", "--from", "2026-10-01", "--to", "2026-10-02",
                         "--note", "cold", "--dry-run")
        self.assertEqual((data["day"]["id"], data["written"]), ("s-0003", False))
        self.assertEqual(self.path().read_bytes(), before)

    def test_add_withdraw_and_list(self):
        added = self.data("status-days", "add", "--kind", "ill", "--from", "2026-10-01", "--to", "2026-10-02",
                          "--note", "cold")["day"]
        self.assertEqual(added["id"], "s-0003")
        self.assertEqual(added["source"], "coach")
        withdrawn = self.data("status-days", "withdraw", "s-0003", "--reason", "duplicate")["day"]
        self.assertEqual(withdrawn["withdrawn"], {"at": "2026-10-11T18:00:00Z", "reason": "duplicate"})
        rows = json.loads(self.path().read_text(encoding="utf-8"))["days"]
        self.assertEqual([r["id"] for r in rows], ["s-0001", "s-0002", "s-0003"])
        self.assertNotIn("s-0003", [r["id"] for r in self.data("status-days", "list", "--active")["days"]])
        self.assertIn("s-0003", [r["id"] for r in self.data("status-days", "list")["days"]])

    def test_withdraw_and_end_dry_runs_write_nothing(self):
        before = self.path().read_bytes()
        self.data("status-days", "withdraw", "s-0001", "--reason", "wrong", "--dry-run")
        self.data("status-days", "add", "--kind", "injured", "--from", "2026-10-09", "--note", "calf")
        after_add = self.path().read_bytes()
        self.assertNotEqual(after_add, before)
        self.data("status-days", "end", "s-0003", "--date", "2026-10-11", "--dry-run")
        self.assertEqual(self.path().read_bytes(), after_add)

    def test_an_ongoing_row_is_ended(self):
        self.data("status-days", "add", "--kind", "injured", "--from", "2026-10-09", "--note", "calf")
        self.assertIsNone(self.data("status-days", "list")["days"][-1]["span"]["end"])
        envelope = self.coach("status-days", "add", "--kind", "injured", "--from", "2026-10-10", "--note", "again",
                              expect=1)
        self.assertIn("s-0003", envelope["error"]["message"])
        ended = self.data("status-days", "end", "s-0003", "--date", "2026-10-11")["day"]
        self.assertEqual(ended["span"], {"start": "2026-10-09", "end": "2026-10-11"})
        self.coach("status-days", "end", "s-0003", "--date", "2026-10-12", expect=1)

    def test_bad_input(self):
        self.coach("status-days", "add", "--kind", "ill", "--from", "2026-10-05", "--to", "2026-10-01",
                   "--note", "x", expect=1)
        self.coach("status-days", "add", "--kind", "sick", "--from", "2026-10-05", "--note", "x", expect=2)
        self.coach("status-days", "withdraw", "s-0099", "--reason", "x", expect=1)
        self.data("status-days", "withdraw", "s-0001", "--reason", "x")
        self.coach("status-days", "withdraw", "s-0001", "--reason", "again", expect=1)

    def test_check_passes_on_the_fixture(self):
        results = self.data("check", "--only", "status_days_valid")["results"]
        self.assertEqual([r["status"] for r in results], ["pass"])


class ReadersTest(CardioCase):
    def test_active_and_ill_in(self):
        self.assertEqual([r["id"] for r in statusdays.active(self.root, span("2026-10-02", "2026-10-15"))],
                         ["s-0001", "s-0002"])
        self.assertTrue(statusdays.ill_in(self.root, span("2026-09-30", "2026-10-01")))
        self.assertFalse(statusdays.ill_in(self.root, span("2026-10-03", "2026-10-20")))

    def test_a_withdrawn_row_is_not_active(self):
        self.data("status-days", "withdraw", "s-0001", "--reason", "wrong")
        self.assertFalse(statusdays.ill_in(self.root, span("2026-09-30", "2026-10-01")))

    def test_no_file_reads_as_none(self):
        (self.root / "data" / "status-days.json").unlink()
        self.assertEqual(statusdays.active(self.root, span("2026-10-01", "2026-10-31")), [])


class IllnessRuleTest(CardioCase):
    base = LAYOFF

    def test_an_ill_status_day_in_the_gap_caps_the_first_session(self):
        self.data("status-days", "add", "--kind", "ill", "--from", "2026-09-20", "--to", "2026-09-22",
                  "--note", "flu")
        self.assertEqual(self.data("history", "annotations", "--kind", "miss")["annotations"], [])
        overlay = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        illness = [f for f in overlay["flags"] if f["code"] == "return_after_illness"]
        self.assertEqual(len(illness), 1)
        first = min(s["date"] for s in overlay["sessions"])
        session = next(s for s in overlay["sessions"] if s["date"] == first)
        working = [s for line in session["exercises"] for s in line["sets"] if s["type"] != "warmup"]
        self.assertTrue(working and all(s["rpe"] is not None and s["rpe"] <= 7 for s in working))

    def test_travel_only_explains_the_gap(self):
        self.data("status-days", "add", "--kind", "travel", "--from", "2026-09-20", "--to", "2026-09-22",
                  "--note", "holiday")
        overlay = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        self.assertNotIn("return_after_illness", [f["code"] for f in overlay["flags"]])


if __name__ == "__main__":
    unittest.main()
