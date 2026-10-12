"""The training-record commit plan in weekly close-out: `pages plan` and `pages publish --include` (C38)."""

import json
import os
import shutil
import unittest

from tests.support.history import read_json
from tests.test_missed import MIDWEEK, MissedCase
from tests.test_pages import WEEKLY, PublishCase, git, init_with_upstream

RECORDS = {
    "data/blocks.json": "added",
    "data/decisions.json": "added",
    "data/history/2026-10.json": "modified",
    "data/log/workouts.jsonl": "added",
    "data/state.json": "modified",
}
NEXT_WEEK = "2026-10-19-weekly"


@unittest.skipIf(shutil.which("git") is None, "needs git")
class CloseOutCase(PublishCase):
    def train_the_week(self):
        """A no-Hevy week: a manual workout, a standing override, a seeded block and the history sync."""
        self.disable_hevy()
        draft = self.coach("log", "prefill", "--session", "session-a", "--date", "2026-10-14")["data"]["draft"]
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                if set_["reps"] is None:
                    set_["reps"] = 8
        path = self.tmp / "workout.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        self.coach("log", "add", "--input", str(path), "--again")
        self.sync()
        self.coach("propose", "week", "--week", "2026-W43")
        self.coach("propose", "override", "--proposal", NEXT_WEEK, "--session", "session-a", "--exercise",
                   "bb_back_squat", "--load", "95", "--reason", "knee", "--standing")
        self.coach("block", "init", "--hard-weeks", "2", "--reason", "seeded at the check-in")

    def change_the_program(self):
        """A structural change: a new cue on the squat, rendered into routine/."""
        def cue(doc):
            for session in doc["sessions"]:
                for line in session["exercises"]:
                    if line["exercise_id"] == "bb_back_squat":
                        line["cues"] = "brace · knees out · sit back"
        self.edit_json("data/program.json", cue)
        self.coach("program", "render")

    def plan(self, *argv):
        return self.coach("pages", "plan", *argv)["data"]

    def status(self):
        lines = git(self.root, "status", "--porcelain", "--untracked-files=all", env=self.git_env).splitlines()
        return {line[3:] for line in lines}

    def committed(self, rev="HEAD"):
        return set(git(self.root, "show", "--name-only", "--no-renames", "--format=", rev, env=self.git_env).split())

    def commit_everything(self):
        git(self.root, "add", "-A", env=self.git_env)
        git(self.root, "commit", "-q", "-m", "records", env=self.git_env)
        git(self.root, "push", "-q", env=self.git_env)

    def remote_files(self):
        return set(git(self.remote, "ls-tree", "-r", "--name-only", "main", env=self.git_env).split())

    def include(self, paths):
        return [arg for path in paths for arg in ("--include", path)]


class PlanTest(CloseOutCase):
    def test_lists_exactly_the_changed_training_records_and_changes_nothing(self):
        self.train_the_week()
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", "--reason", "poor sleep all week")
        changed = dict(RECORDS, **{"routine/program.md": "modified"})
        before = self.snapshot()
        data = self.plan()
        self.assertEqual({row["path"]: row["change"] for row in data["records"]}, changed)
        self.assertEqual(data["include"], sorted(changed))
        self.assertFalse(data["program_changed"])
        self.assertIn("config.toml", self.status())
        self.assertEqual(self.snapshot(), before)

    def test_lists_the_program_only_for_a_structural_change(self):
        self.change_the_program()
        data = self.plan()
        self.assertEqual(data["include"], ["routine/session-a.md"])
        self.assertTrue(data["program_changed"])
        structural = self.plan("--structural")
        self.assertEqual(structural["include"], ["data/program.json", "routine/program.md", "routine/session-a.md"])

    def test_lists_deletions_and_untracked_files_under_eligible_directories(self):
        (self.root / "routine" / "session-b.md").unlink()
        (self.root / "data" / "log").mkdir(parents=True)
        (self.root / "data" / "log" / "workouts.jsonl").write_text("", encoding="utf-8")
        (self.root / "data" / "followups.json").write_text("{}", encoding="utf-8")
        rows = {row["path"]: row["change"] for row in self.plan()["records"]}
        self.assertEqual(rows, {"data/log/workouts.jsonl": "added", "routine/session-b.md": "deleted"})

    def test_a_staged_rename_lists_the_old_path_as_deleted(self):
        git(self.root, "mv", "data/history/2026-10.json", "data/history/moved.json", env=self.git_env)
        rows = {row["path"]: row["change"] for row in self.plan()["records"]}
        self.assertEqual(rows, {"data/history/2026-10.json": "deleted", "data/history/moved.json": "added"})

    def test_names_the_records_each_approved_write_step_will_write(self):
        cases = {
            ("--light-week",): ["data/blocks.json", "data/decisions.json", "data/state.json", "routine/program.md"],
            ("--one-off",): ["data/state.json"],
            ("--create-routines",): ["data/state.json"],
            ("--missed",): ["data/history/annotations.json"],
            ("--structural",): ["data/program.json", "routine/program.md"],
            ("--structural", "--session", "session-c", "--session", "session-a"):
                ["data/program.json", "routine/program.md", "routine/session-a.md", "routine/session-c.md"],
        }
        before = self.snapshot()
        for argv, planned in cases.items():
            with self.subTest(argv=argv):
                data = self.plan(*argv)
                self.assertEqual(data["planned"], planned)
                self.assertEqual(data["include"], planned)
                self.assertEqual({row["change"] for row in data["records"]}, {"planned"})
        self.assertEqual(self.snapshot(), before)

    def test_a_planned_record_that_already_changed_keeps_its_change(self):
        self.train_the_week()
        rows = {row["path"]: row["change"] for row in self.plan("--missed")["records"]}
        self.assertEqual(rows, dict(RECORDS, **{"data/history/annotations.json": "planned"}))

    def test_a_stale_index_stat_is_not_refreshed_by_the_plan(self):
        state = self.root / "data" / "state.json"
        later = state.stat().st_mtime + 3600
        os.utime(state, (later, later))
        index = (self.root / ".git" / "index").read_bytes()
        self.assertEqual(self.plan()["records"], [])
        self.assertEqual((self.root / ".git" / "index").read_bytes(), index)

    def test_a_session_page_needs_a_structural_change(self):
        message = self.coach("pages", "plan", "--session", "session-a", expect=2)["error"]["message"]
        self.assertIn("--structural", message)


class PublishRecordsTest(CloseOutCase):
    def test_approved_records_are_committed_with_the_pages_and_pushed(self):
        self.train_the_week()
        planned = self.plan()["include"]
        self.approve()
        data = self.publish(*self.include(planned))["data"]
        self.assertTrue(data["pushed"])
        self.assertEqual([row["path"] for row in data["records"]["included"]], planned)
        self.assertEqual(data["records"]["local"], [])
        self.assertEqual(self.committed(), set(self.PUBLISHED) | set(planned) | {"this-week-sheets.md"})
        self.assertFalse(self.status() & set(planned))
        self.assertLessEqual(set(planned), self.remote_files())
        self.assertIn("config.toml", self.status())
        self.assertNotIn("config.toml", self.committed())

    def test_declining_the_plan_commits_only_the_pages_and_names_what_stays_local(self):
        self.train_the_week()
        planned = self.plan()["include"]
        records = {path: (self.root / path).read_bytes() for path in planned}
        self.approve()
        data = self.publish()["data"]
        self.assertEqual(data["records"]["included"], [])
        self.assertEqual([row["path"] for row in data["records"]["local"]], planned)
        self.assertFalse(self.committed() & set(planned))
        self.assertLessEqual(set(planned), self.status())
        self.assertEqual({path: (self.root / path).read_bytes() for path in planned}, records)

    def test_dry_run_reports_the_exact_paths_and_changes_nothing(self):
        self.train_the_week()
        planned = self.plan()["include"]
        self.approve()
        before = self.snapshot()
        data = self.publish("--dry-run", *self.include(planned))["data"]
        self.assertEqual(sorted(data["paths"]), sorted(self.PUBLISHED + ["this-week-sheets.md"] + planned))
        self.assertEqual([row["path"] for row in data["records"]["included"]], planned)
        self.assertEqual(self.snapshot(), before)

    def test_an_unrelated_staged_file_is_refused_before_anything_changes(self):
        self.train_the_week()
        planned = self.plan()["include"]
        self.approve()
        for path in ("config.toml", "data/state.json"):
            with self.subTest(staged=path):
                git(self.root, "add", "--", path, env=self.git_env)
                before = self.snapshot()
                others = [p for p in planned if p != path]
                message = self.publish(*self.include(others), expect=3)["error"]["message"]
                self.assertIn(path, message)
                self.assertEqual(self.snapshot(), before)
                git(self.root, "reset", "-q", "HEAD", "--", path, env=self.git_env)

    def test_a_staged_approved_record_does_not_block_publishing(self):
        self.train_the_week()
        planned = self.plan()["include"]
        git(self.root, "add", "--", "data/state.json", env=self.git_env)
        self.approve()
        self.publish(*self.include(planned))
        self.assertIn("data/state.json", self.committed())

    def test_secrets_config_profile_directories_and_escapes_are_refused(self):
        self.train_the_week()
        (self.root / ".env").write_text("HEVY_API_KEY=synthetic-not-a-key\n", encoding="utf-8")
        self.approve()
        for path in (".env", "config.toml", "profile.md", "data/log", "data/log/", "data/followups.json",
                     "../outside.json", "/data/state.json", "data/history/../../config.toml"):
            with self.subTest(path=path):
                before = self.snapshot()
                self.publish("--include", path, expect=3)
                self.assertEqual(self.snapshot(), before)

    def test_a_pattern_never_stages_a_directory(self):
        self.train_the_week()
        self.approve()
        data = self.publish("--include", "data/log/*", "--include", "data/history/*.json")["data"]
        self.assertEqual(data["records"]["included"], [])
        self.assertFalse(self.committed() & set(RECORDS))
        self.assertLessEqual(set(RECORDS), self.status())

    def test_a_path_changed_after_approval_stays_local_until_approved(self):
        self.train_the_week()
        planned = self.plan()["include"]
        self.approve()
        self.change_the_program()
        data = self.publish(*self.include(planned))["data"]
        self.assertEqual([row["path"] for row in data["records"]["local"]],
                         ["data/program.json", "routine/session-a.md"])
        self.assertFalse(self.committed() & {"data/program.json", "routine/session-a.md"})
        refused = self.publish("--include", "data/program.json", expect=3)["error"]["message"]
        self.assertIn("--structural", refused)
        again = self.publish("--structural", "--include", "data/program.json", "--include",
                             "routine/session-a.md")["data"]
        self.assertTrue(again["pushed"])
        self.assertEqual(self.committed(), {"data/program.json", "routine/session-a.md"})
        self.assertEqual(again["records"]["local"], [])

    def test_tracked_new_and_deleted_records_are_committed_without_unplanned_siblings(self):
        self.train_the_week()
        (self.root / "routine" / "session-b.md").unlink()
        self.approve()
        chosen = ["data/history/2026-10.json", "data/log/workouts.jsonl", "routine/session-b.md"]
        data = self.publish(*self.include(chosen))["data"]
        self.assertEqual({row["path"]: row["change"] for row in data["records"]["included"]},
                         {"data/history/2026-10.json": "modified", "data/log/workouts.jsonl": "added",
                          "routine/session-b.md": "deleted"})
        self.assertNotIn("routine/session-b.md", self.remote_files())
        self.assertIn("data/log/workouts.jsonl", self.remote_files())
        local = {row["path"] for row in data["records"]["local"]}
        self.assertEqual(local, {"data/blocks.json", "data/decisions.json", "data/state.json"})
        self.assertLessEqual(local, self.status())

    def test_a_staged_rename_is_refused_unless_both_paths_are_named(self):
        git(self.root, "mv", "data/history/2026-10.json", "data/history/moved.json", env=self.git_env)
        self.approve()
        before = self.snapshot()
        message = self.publish("--include", "data/history/moved.json", expect=3)["error"]["message"]
        self.assertIn("data/history/2026-10.json", message)
        self.assertEqual(self.snapshot(), before)
        data = self.publish("--include", "data/history/moved.json", "--include", "data/history/2026-10.json")["data"]
        self.assertEqual({row["path"]: row["change"] for row in data["records"]["included"]},
                         {"data/history/2026-10.json": "deleted", "data/history/moved.json": "added"})
        self.assertLessEqual({"data/history/2026-10.json", "data/history/moved.json"}, self.committed())
        self.assertNotIn("data/history/2026-10.json", self.remote_files())

    def test_an_unchanged_planned_record_is_reported_not_committed(self):
        self.approve()
        data = self.publish("--include", "data/state.json")["data"]
        self.assertEqual(data["records"]["unchanged"], ["data/state.json"])
        self.assertNotIn("data/state.json", self.committed())

    def test_a_rejected_push_keeps_the_record_commit(self):
        self.train_the_week()
        planned = self.plan()["include"]
        self.approve()
        hook = self.remote / "hooks" / "pre-receive"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text("#!/bin/sh\necho 'error: rejected by test hook' >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        envelope = self.publish(*self.include(planned), expect=4)
        self.assertIn("push it by hand", envelope["error"]["message"])
        self.assertLessEqual(set(planned), self.committed())
        self.assertFalse(self.remote_files() & {"data/log/workouts.jsonl", "data/blocks.json"})
        self.assertEqual(read_json(self.root / "data" / "blocks.json")["blocks"][0]["seed_hard_weeks"], 2)


class ApprovedPassTest(CloseOutCase):
    def test_an_approved_light_week_leaves_no_record_local(self):
        self.disable_hevy()
        self.coach("block", "init", "--hard-weeks", "2", "--reason", "seeded at the check-in")
        self.commit_everything()
        planned = self.plan("--light-week")["include"]
        self.approve()
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", "--reason", "poor sleep all week")
        dry = self.publish("--dry-run", *self.include(planned))["data"]
        self.assertEqual(dry["records"]["local"], [])
        data = self.publish(*self.include(planned))["data"]
        self.assertTrue(data["pushed"])
        self.assertEqual([row["path"] for row in data["records"]["included"]],
                         [path for path in planned if path != "data/blocks.json"])
        self.assertEqual(data["records"]["unchanged"], ["data/blocks.json"])
        self.assertFalse(self.status() & set(planned))
        self.assertLessEqual(set(planned), self.remote_files())

    def test_a_light_week_before_the_first_ledger_commits_the_ledger_it_creates(self):
        self.disable_hevy()
        self.commit_everything()
        self.assertFalse((self.root / "data" / "blocks.json").exists())
        planned = self.plan("--light-week")["include"]
        self.approve()
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", "--reason", "poor sleep all week")
        data = self.publish(*self.include(planned))["data"]
        self.assertEqual(data["records"]["local"], [])
        self.assertIn({"path": "data/blocks.json", "change": "added"}, data["records"]["included"])
        self.assertIn("data/blocks.json", self.remote_files())


@unittest.skipIf(shutil.which("git") is None, "needs git")
class MidweekPassTest(MissedCase):
    def setUp(self):
        super().setUp()
        init_with_upstream(self)

    def test_an_approved_matched_miss_leaves_no_record_local(self):
        self.assertTrue(self.plan()["matched"])
        planned = self.coach("pages", "plan", "--missed")["data"]["include"]
        self.assertEqual(planned, ["data/history/annotations.json"])
        self.apply("--tag", "sleep")
        self.coach("overlay", "approve", MIDWEEK)
        include = ["--include", "data/history/annotations.json"]
        dry = self.coach("pages", "publish", "--overlay", MIDWEEK, "--dry-run", *include)["data"]
        self.assertEqual(dry["records"]["local"], [])
        data = self.coach("pages", "publish", "--overlay", MIDWEEK, *include)["data"]
        self.assertEqual([row["path"] for row in data["records"]["included"]], planned)
        shown = git(self.root, "show", "--name-only", "--format=", "HEAD", env=self.git_env).split()
        self.assertIn("data/history/annotations.json", shown)
        self.assertIn(f"data/overlays/{MIDWEEK}.json", shown)


if __name__ == "__main__":
    unittest.main()
