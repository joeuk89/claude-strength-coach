"""Follow-ups as data: `coach followups`, the deep-review gate and `followup_due` (contract C27)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import flags
from tests.support import INSTANCES, run_cli
from tests.support.history import HistoryCase, read_json
from tests.test_propose import ProposeCase

ADD = ("followups", "add", "--text", "Re-test pull-up ladder", "--review-at", "2026-11-08",
       "--source", "check-in 2026-10-11")
AFTER_REVIEW = {"COACH_NOW": "2026-11-09T09:00:00Z"}
REVIEW_DAY = {"COACH_NOW": "2026-11-08T09:00:00Z"}


class FollowupCase(HistoryCase):
    def path(self):
        return self.root / "data" / "followups.json"

    def add(self, *extra, env=None):
        return self.coach(*ADD, *extra, env=env)["data"]


class AddTest(FollowupCase):
    def test_add_creates_the_file_with_one_open_item_and_a_raised_event(self):
        data = self.add()
        doc = read_json(self.path())
        self.assertEqual(doc["schema_version"], 1)
        [item] = doc["items"]
        self.assertEqual(item, {
            "id": "f-0001", "raised": "2026-10-11", "source": "check-in 2026-10-11", "text": "Re-test pull-up ladder",
            "review_at": "2026-11-08", "status": "open",
            "events": [{"date": "2026-10-11", "action": "raised", "note": None}]})
        self.assertEqual(data["item"], item)
        self.assertTrue(data["written"])

    def test_dry_run_writes_nothing(self):
        data = self.add("--dry-run")
        self.assertFalse(self.path().exists())
        self.assertEqual(data["item"]["id"], "f-0001")
        self.assertFalse(data["written"])

    def test_ids_are_never_reused(self):
        self.add()
        self.coach("followups", "drop", "f-0001", "--reason", "no longer relevant")
        self.assertEqual(self.add()["item"]["id"], "f-0002")

    def test_a_review_date_before_the_raised_date_exits_1(self):
        self.coach("followups", "add", "--text", "x", "--review-at", "2026-10-01", "--source", "chat", expect=1)
        self.assertFalse(self.path().exists())


class ListTest(FollowupCase):
    def test_due_lists_open_items_past_their_review_date(self):
        self.add()
        self.assertEqual(self.coach("followups", "list", "--due")["data"]["items"], [])
        due = self.coach("followups", "list", "--due", env=AFTER_REVIEW)["data"]["items"]
        self.assertEqual([i["id"] for i in due], ["f-0001"])
        self.assertTrue(due[0]["due"])

    def test_open_leaves_out_closed_items(self):
        self.add()
        self.add()
        self.coach("followups", "resolve", "f-0002", "--note", "done")
        listed = self.coach("followups", "list", "--open")["data"]["items"]
        self.assertEqual([i["id"] for i in listed], ["f-0001"])
        self.assertEqual(len(self.coach("followups", "list")["data"]["items"]), 2)

    def test_no_file_lists_nothing(self):
        self.assertEqual(self.coach("followups", "list")["data"]["items"], [])


class DispositionTest(FollowupCase):
    def test_resolve_drop_and_defer_record_events(self):
        self.add()
        self.add()
        self.add()
        self.coach("followups", "resolve", "f-0001", env=REVIEW_DAY)
        self.coach("followups", "drop", "f-0002", "--reason", "the PT took it over", env=REVIEW_DAY)
        self.coach("followups", "defer", "f-0003", "--to", "2026-12-06", "--kept", env=REVIEW_DAY)
        items = {i["id"]: i for i in read_json(self.path())["items"]}
        self.assertEqual((items["f-0001"]["status"], items["f-0001"]["events"][-1]["action"]), ("resolved", "resolved"))
        self.assertEqual(items["f-0002"]["status"], "dropped")
        self.assertEqual(items["f-0002"]["events"][-1], {"date": "2026-11-08", "action": "dropped",
                                                         "note": "the PT took it over"})
        self.assertEqual((items["f-0003"]["status"], items["f-0003"]["review_at"]), ("open", "2026-12-06"))
        self.assertEqual(items["f-0003"]["events"][-1]["action"], "kept")

    def test_defer_without_kept_is_a_deferral(self):
        self.add()
        self.coach("followups", "defer", "f-0001", "--to", "2026-11-22")
        self.assertEqual(read_json(self.path())["items"][0]["events"][-1]["action"], "deferred")

    def test_drop_needs_a_reason(self):
        self.add()
        self.coach("followups", "drop", "f-0001", "--reason", "  ", expect=2)

    def test_defer_needs_a_later_date(self):
        self.add()
        self.coach("followups", "defer", "f-0001", "--to", "2026-10-11", expect=1)

    def test_a_closed_item_cannot_be_closed_again(self):
        self.add()
        self.coach("followups", "resolve", "f-0001")
        self.coach("followups", "drop", "f-0001", "--reason", "x", expect=1)
        self.coach("followups", "defer", "f-0001", "--to", "2026-12-01", expect=1)

    def test_an_unknown_id_exits_1(self):
        self.add()
        self.coach("followups", "resolve", "f-0009", expect=1)

    def test_writing_dry_runs_write_nothing(self):
        self.add()
        before = self.path().read_bytes()
        self.coach("followups", "resolve", "f-0001", "--dry-run")
        self.coach("followups", "drop", "f-0001", "--reason", "x", "--dry-run")
        self.coach("followups", "defer", "f-0001", "--to", "2026-12-01", "--dry-run")
        self.assertEqual(self.path().read_bytes(), before)


class RenderDeepTest(FollowupCase):
    def render(self, expect=0, env=REVIEW_DAY):
        return self.coach("followups", "render", "--deep", "--date", "2026-11-08", expect=expect, env=env)

    def test_an_item_open_before_the_date_blocks_the_render_until_it_has_a_disposition(self):
        self.add()
        failed = self.render(expect=1)
        self.assertIn("f-0001", failed["error"]["message"])
        self.assertIn("f-0001", json.dumps(failed["error"]["details"]))
        self.coach("followups", "defer", "f-0001", "--to", "2026-12-06", env=REVIEW_DAY)
        text = self.render()["data"]["text"]
        self.assertIn("f-0001", text)
        self.assertIn("2026-12-06", text)
        self.assertIn("Re-test pull-up ladder", text)

    def test_every_disposition_is_rendered(self):
        self.add()
        self.add()
        self.add()
        self.coach("followups", "resolve", "f-0001", "--note", "ladder done", env=REVIEW_DAY)
        self.coach("followups", "drop", "f-0002", "--reason", "the PT took it over", env=REVIEW_DAY)
        self.coach("followups", "defer", "f-0003", "--to", "2026-12-06", "--kept", env=REVIEW_DAY)
        data = self.render()["data"]
        self.assertEqual([(i["id"], i["disposition"]) for i in data["items"]],
                         [("f-0001", "resolved"), ("f-0002", "dropped"), ("f-0003", "kept")])
        self.assertIn("the PT took it over", data["text"])
        self.assertIn("ladder done", data["text"])

    def test_items_raised_on_the_date_and_items_closed_earlier(self):
        self.add()
        self.coach("followups", "resolve", "f-0001")
        self.coach(*ADD, env=REVIEW_DAY)
        data = self.render()["data"]
        self.assertEqual([(i["id"], i["disposition"]) for i in data["items"]], [("f-0002", "raised")])

    def test_nothing_open_renders_a_none_line(self):
        self.assertIn("none open", self.render()["data"]["text"])

    def test_render_takes_the_deep_flag(self):
        self.coach("followups", "render", "--date", "2026-11-08", expect=2)


class DueFlagTest(ProposeCase):
    def test_propose_week_carries_followup_due_for_a_due_item(self):
        self.coach(*ADD)
        doc = self.propose("--dry-run", env=AFTER_REVIEW, week=None)["overlay"]
        [flag] = [f for f in doc["flags"] if f["code"] == "followup_due"]
        self.assertEqual((flag["severity"], flag["session_id"], flag["exercise_id"]), ("info", None, None))
        self.assertIn("f-0001", flag["message"])
        self.assertIn("Re-test pull-up ladder", flag["message"])

    def test_no_flag_before_the_review_date(self):
        self.coach(*ADD)
        doc = self.propose("--dry-run")["overlay"]
        self.assertNotIn("followup_due", [f["code"] for f in doc["flags"]])


class RegistryTest(unittest.TestCase):
    def test_followup_due_is_registered(self):
        code = flags.registry()["followup_due"]
        self.assertEqual((code.owner, code.severities, code.structural), ("R-27", ("info",), False))


class CheckTest(unittest.TestCase):
    def check(self, root):
        code, envelope, _ = run_cli(["--root", str(root), "check", "--only", "followups_schema"])
        return code, envelope["data"]["results"]

    def test_followups_schema_skips_fails_and_passes(self):
        code, results = self.check(INSTANCES / "valid")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["skip"]))
        code, results = self.check(INSTANCES / "followups-invalid")
        self.assertEqual(code, 1)
        self.assertIn("$.items[0].events[1].note", results[0]["message"])
        self.assertEqual(results[0]["path"], "data/followups.json")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "followups-invalid", root)
            path = root / "data" / "followups.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["items"][0]["events"][1]["note"] = "the PT took it over"
            path.write_text(json.dumps(doc), encoding="utf-8")
            code, results = self.check(root)
        self.assertEqual((code, [r["status"] for r in results]), (0, ["pass"]))


if __name__ == "__main__":
    unittest.main()
