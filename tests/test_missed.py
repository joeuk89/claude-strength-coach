"""Missed-day rules: matching, fold and shift, the mid-week overlay, the record lines and the checks (contract C37)."""

import copy
import json
import re

from coach import dates, flags, jsonio, missed, overlay, propose, render
from coach.library import Library
from tests.support import INSTANCES, REPO_ROOT
from tests.support.activity import write_hevy_cache
from tests.support.history import SYNTHETIC, HistoryCase, read_json, write_json
from tests.support.skills import skill_text

NOW = "2026-10-15T08:00:00Z"
WEEKLY = "2026-10-12-weekly"
MIDWEEK = "2026-10-17-midweek"
ROW = "db_single_arm_row"
FOLD = {"rule_id": "miss-b", "from_session_id": "session-b", "from_date": "2026-10-14", "scope": "one_week"}
RECORD_LINES = [
    "- Missed Wed 14 Oct Session B (sleep).",
    "- Rule miss-b: Single-arm row 2×10 @ 30 added to Sat 17 Oct Session A, this week only.",
    "- Overlay 2026-10-17-midweek; Hevy: Session A.",
]


def sessions_of(doc):
    return [(s["date"], s["session_id"]) for s in doc["sessions"]]


def codes(doc_or_data):
    return [f["code"] for f in doc_or_data["flags"]]


def mid_week_section(text):
    lines = text.splitlines()
    start = lines.index("## Mid-week") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return [line for line in lines[start:end] if line.strip()]


class MissedCase(HistoryCase):
    base = INSTANCES / "missed"

    def setUp(self):
        super().setUp()
        self.env = {"COACH_NOW": NOW}

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def plan(self, session="session-b", day="2026-10-14", env=None):
        return self.coach("missed", "plan", "--session", session, "--date", day, env=env)["data"]

    def apply(self, *extra, session="session-b", day="2026-10-14", expect=0):
        envelope = self.coach("missed", "apply", "--session", session, "--date", day, *extra, expect=expect)
        return envelope["data"] if expect == 0 else envelope

    def edit_overlay(self, change, overlay_id=WEEKLY):
        path = self.root / "data" / "overlays" / f"{overlay_id}.json"
        doc = read_json(path)
        change(doc)
        doc["approval"] = None
        write_json(path, doc)

    def set_rules(self, rules):
        self.edit_json("data/program.json", lambda doc: doc.update(missed_day_rules=rules))

    def drop_workout_on(self, day):
        self.edit_json("data/history/2026-10.json",
                       lambda doc: doc.update(workouts=[w for w in doc["workouts"] if w["date"] != day]))

    def newest_record(self):
        return (self.root / "check-ins" / "2026-10-11.md").read_text(encoding="utf-8")


class ListTest(MissedCase):
    def test_lists_session_b_missed_on_14_oct(self):
        data = self.coach("missed", "list")["data"]
        self.assertEqual([(r["session_id"], r["date"]) for r in data["missed"]], [("session-b", "2026-10-14")])
        self.assertEqual(data["missed"][0]["overlay_id"], WEEKLY)
        self.assertFalse(data["missed"][0]["recorded"])

    def test_a_trained_session_and_a_session_not_yet_due_are_not_listed(self):
        self.assertEqual(self.coach("missed", "list", "--date", "2026-10-14")["data"]["missed"], [])

    def test_a_trained_unlogged_session_is_not_listed(self):
        self.coach("history", "annotate", "--kind", "trained_unlogged", "--date", "2026-10-14",
                   "--session", "session-b", "--note", "phone dead")
        self.assertEqual(self.coach("missed", "list")["data"]["missed"], [])

    def test_a_sunday_week_lists_the_same(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('week_starts = "monday"', 'week_starts = "sunday"'),
                        encoding="utf-8")
        data = self.coach("missed", "list")["data"]
        self.assertEqual([(r["session_id"], r["date"]) for r in data["missed"]], [("session-b", "2026-10-14")])


class DescribeTest(MissedCase):
    def rule(self, rule_id):
        return next(r for r in missed.rules(self.root) if r["id"] == rule_id)

    def test_fold_in_words_with_library_names(self):
        self.assertEqual(missed.describe(self.rule("miss-b"), self.root),
                         "Miss Session B: 2 sets of Single-arm row go into the next Session A, this week only.")

    def test_shift_skip_and_manual_in_words(self):
        self.assertEqual(missed.describe(self.rule("miss-a"), self.root),
                         "Miss Session A: it moves to Sat, else Thu, whichever is free first, this week only.")
        skip = {"id": "miss-c", "session_id": "session-b", "text": None, "when": {"min_days_left": 3},
                "action": {"kind": "skip"}}
        self.assertEqual(missed.describe(skip, self.root),
                         "Miss Session B with 3 or more days left in the week: skip it; the rest of the week "
                         "stays as planned.")
        manual = {"id": "miss-d", "session_id": "session-b", "text": "Ask the coach.", "when": {},
                  "action": {"kind": "manual"}}
        self.assertEqual(missed.describe(manual, self.root), "Ask the coach.")

    def test_rules_command_describes_each_rule(self):
        data = self.coach("missed", "rules")["data"]
        self.assertEqual([r["id"] for r in data["rules"]], ["miss-b", "miss-a"])
        self.assertEqual(data["rules"][0]["description"],
                         "Miss Session B: 2 sets of Single-arm row go into the next Session A, this week only.")

    def test_the_brief_says_what_to_do_from_the_rules(self):
        text = self.coach("pages", "show", "brief")["data"]["text"]
        lines = text.splitlines()
        start = lines.index("## If you miss a day")
        self.assertEqual(lines[start + 1:start + 3], [
            "- Miss Session B: 2 sets of Single-arm row go into the next Session A, this week only.",
            "- Miss Session A: it moves to Sat, else Thu, whichever is free first, this week only.",
        ])

    def test_the_program_page_lists_each_rule_in_words(self):
        page = (self.root / "routine" / "program.md").read_text(encoding="utf-8")
        self.assertIn("- `miss-b`: Miss Session B: 2 sets of Single-arm row go into the next Session A, this week "
                      "only.", page)


class FoldPlanTest(MissedCase):
    def test_plan_folds_two_sets_of_the_row_into_saturdays_session_a_and_writes_nothing(self):
        before = self.snapshot()
        data = self.plan()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(data["matched"])
        self.assertEqual(data["rule"]["id"], "miss-b")
        draft = data["draft"]
        self.assertEqual(draft["kind"], "midweek")
        self.assertEqual(draft["id"], MIDWEEK)
        self.assertEqual(draft["span"], {"start": "2026-10-17", "end": "2026-10-18"})
        self.assertEqual(draft["supersedes"], WEEKLY)
        self.assertIsNone(draft["approval"])
        self.assertEqual(sessions_of(draft), [("2026-10-17", "session-a")])
        last = draft["sessions"][0]["exercises"][-1]
        self.assertEqual(last["exercise_id"], ROW)
        self.assertEqual(render.target_line(last), "Target: 2×10 @ 30 @ RPE 8")
        self.assertEqual(last["fold"], FOLD)
        self.assertEqual([line["fold"] for line in draft["sessions"][0]["exercises"][:-1]], [None, None])
        self.assertLessEqual(len(data["summary"]), 5)
        self.assertTrue(any("2×10 @ 30" in line for line in data["summary"]), data["summary"])
        self.assertEqual(data["write_line"], 'Reply "go" to train this and write: Session A (Hevy).')
        rule_flags = [f for f in draft["flags"] if f["code"] == "missed_day_rule"]
        self.assertEqual([(f["session_id"], f["exercise_id"], f["severity"]) for f in rule_flags],
                         [("session-a", ROW, "info")])
        self.assertIn("miss-b", rule_flags[0]["message"])

    def test_the_draft_passes_the_prescription_check_with_no_block(self):
        draft_path = self.tmp / "draft.json"
        write_json(draft_path, self.plan()["draft"])
        data = self.coach("prescription", "check", "--file", str(draft_path))["data"]
        self.assertEqual([f for f in data["flags"] if f["severity"] == "block"], [])

    def test_a_fold_never_gives_more_sets_than_prescribed_and_takes_a_lower_rpe(self):
        self.set_rules([{"id": "miss-b", "session_id": "session-b", "text": None, "when": {},
                         "action": {"kind": "fold", "into": "next",
                                    "exercises": [{"exercise_id": ROW, "sets": 5, "rpe": 7}]}}])
        last = self.plan()["draft"]["sessions"][0]["exercises"][-1]
        self.assertEqual(render.target_line(last), "Target: 3×10 @ 30 @ RPE 7")

    def test_min_days_left_must_hold(self):
        self.set_rules([{"id": "miss-b", "session_id": "session-b", "text": None, "when": {"min_days_left": 5},
                         "action": {"kind": "skip"}}])
        data = self.plan()
        self.assertFalse(data["matched"])
        self.assertIsNone(data["rule"])

    def test_without_hevy_the_write_line_says_nothing_goes_to_hevy(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("[hevy]\nenabled = true", "[hevy]\nenabled = false"),
                        encoding="utf-8")
        data = self.plan()
        self.assertEqual(data["write_line"], 'Reply "go" to train this. Nothing goes to Hevy (no Hevy).')
        self.assertIn("Single-arm row 2×10 @ 30 @ RPE 8 added to Sat 17 Oct Session A", data["summary"][1])
        lines = self.apply("--dry-run")["record_lines"]
        self.assertEqual(lines[1:], ["- Rule miss-b: Single-arm row 2×10 @ 30 added to Sat 17 Oct Session A, this "
                                     "week only.", "- Overlay 2026-10-17-midweek; no Hevy."])

    def test_a_session_not_planned_that_day_exits_1(self):
        envelope = self.coach("missed", "plan", "--session", "session-b", "--date", "2026-10-13", expect=1)
        self.assertIn("session-b", envelope["error"]["message"])


class ApplyTest(MissedCase):
    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        data = self.apply("--tag", "sleep", "--dry-run")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(data["written"])
        self.assertEqual(data["overlay_id"], MIDWEEK)
        self.assertEqual(data["record_lines"], RECORD_LINES)

    def test_apply_writes_the_overlay_the_miss_and_three_record_lines(self):
        data = self.apply("--tag", "sleep")
        self.assertTrue(data["written"])
        doc = overlay.load(self.root, MIDWEEK)
        self.assertIsNone(doc["approval"])
        self.assertEqual(doc["sessions"][0]["exercises"][-1]["fold"], FOLD)
        misses = [a for a in read_json(self.root / "data" / "history" / "annotations.json")["annotations"]
                  if a["kind"] == "miss"]
        self.assertEqual([(a["date"], a["session_id"], a["tag"]) for a in misses],
                         [("2026-10-14", "session-b", "sleep")])
        self.assertEqual(mid_week_section(self.newest_record()), RECORD_LINES)
        current = self.coach("overlay", "current", "--date", "2026-10-17")["data"]
        self.assertEqual(current["overlay_id"], MIDWEEK)
        self.assertEqual(self.coach("check", "--only", "annotations_valid,overlay_arithmetic")["data"]["summary"]["fail"], 0)

    def test_lines_reach_the_newest_record_even_when_its_title_is_malformed(self):
        path = self.root / "check-ins" / "2026-10-11.md"
        path.write_text(self.newest_record().replace("# Check-in — ", "# Check-in ", 1), encoding="utf-8")
        data = self.apply("--tag", "sleep")
        self.assertEqual(data["record"], "check-ins/2026-10-11.md")
        self.assertEqual(mid_week_section(self.newest_record()), RECORD_LINES)

    def test_an_untagged_miss_says_so(self):
        data = self.apply()
        self.assertEqual(data["record_lines"][0], "- Missed Wed 14 Oct Session B (untagged).")
        misses = [a for a in read_json(self.root / "data" / "history" / "annotations.json")["annotations"]
                  if a["kind"] == "miss"]
        self.assertIsNone(misses[0]["tag"])

    def test_a_second_miss_adds_to_the_same_section(self):
        self.apply("--tag", "sleep")
        self.drop_workout_on("2026-10-12")
        self.apply("--tag", "time", session="session-a", day="2026-10-12")
        lines = mid_week_section(self.newest_record())
        self.assertEqual(len(lines), 6)
        self.assertEqual(lines[:3], RECORD_LINES)
        self.assertEqual(self.newest_record().count("## Mid-week"), 1)

    def test_routines_diff_after_approval_lists_only_session_a(self):
        self.apply("--tag", "sleep")
        self.coach("overlay", "approve", MIDWEEK)
        write_hevy_cache(self.root, SYNTHETIC)
        data = self.coach("routines", "diff", "--overlay", MIDWEEK)["data"]
        self.assertEqual({r["session_id"] for r in data["routines"]}, {"session-a"})
        self.assertTrue(data["changes"])
        self.assertEqual({c["routine_id"] for c in data["changes"]}, {"00000000-0000-4000-8000-000000000001"})

    def test_an_unmatched_miss_is_refused_and_writes_nothing(self):
        self.set_rules([])
        before = self.snapshot()
        envelope = self.apply(expect=3)
        self.assertIn("--move-to", envelope["error"]["message"])
        self.assertIn("--drop", envelope["error"]["message"])
        self.assertEqual(self.snapshot(), before)

    def test_a_second_apply_of_the_same_miss_is_refused_and_writes_nothing(self):
        self.apply("--tag", "sleep")
        before = self.snapshot()
        envelope = self.apply("--tag", "sleep", expect=3)
        self.assertIn("already recorded", envelope["error"]["message"])
        self.assertEqual(self.snapshot(), before)


class OneOffWeekTest(MissedCase):
    """A miss in a coach-built one-off week whose Saturday leaves out a program exercise (hotel kit)."""

    ONE_OFF = "2026-10-12-one-off"

    def setUp(self):
        super().setUp()
        old = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(old)
        saturday = next(s for s in doc["sessions"] if s["date"] == "2026-10-17")
        saturday["exercises"] = [e for e in saturday["exercises"] if e["exercise_id"] != "db_bench_press"]
        doc.update(id=self.ONE_OFF, kind="one_off", approval=None)
        old.unlink()
        write_json(self.root / "data" / "overlays" / f"{self.ONE_OFF}.json", doc)
        self.coach("overlay", "approve", self.ONE_OFF)

    def test_the_mid_week_overlay_a_rule_writes_is_approved(self):
        data = self.apply("--tag", "sleep")
        self.assertEqual(data["overlay_id"], MIDWEEK)
        doc = overlay.load(self.root, MIDWEEK)
        self.assertNotIn("db_bench_press", [e["exercise_id"] for e in doc["sessions"][0]["exercises"]])
        approved = self.coach("overlay", "approve", MIDWEEK)["data"]
        self.assertTrue(approved["written"])


class UnfoldTest(MissedCase):
    def setUp(self):
        super().setUp()
        self.apply("--tag", "sleep")
        self.coach("overlay", "approve", MIDWEEK)

    def test_the_next_weekly_proposal_carries_no_fold(self):
        data = self.coach("propose", "week", "--week", "2026-W43", "--dry-run")["data"]
        lines = [line for s in data["overlay"]["sessions"] for line in s["exercises"]]
        self.assertEqual([line["fold"] for line in lines], [None] * len(lines))
        session_a = [s for s in data["overlay"]["sessions"] if s["session_id"] == "session-a"]
        self.assertTrue(session_a)
        self.assertNotIn(ROW, [line["exercise_id"] for s in session_a for line in s["exercises"]])
        session_b = next(s for s in data["overlay"]["sessions"] if s["session_id"] == "session-b")
        row = next(line for line in session_b["exercises"] if line["exercise_id"] == ROW)
        self.assertEqual(len([s for s in row["sets"] if overlay.is_working(s)]), 3)

    def test_last_prescription_ignores_fold_lines(self):
        from coach import config as config_module

        config = config_module.load(self.root)
        run = propose.Run(self.root, config, dates.parse_date("2026-10-18"), dates.parse_timestamp(NOW))
        self.assertIsNone(run.last_prescription("session-a", ROW))
        own = run.last_prescription("session-b", ROW)
        self.assertEqual(own["overlay_id"], WEEKLY)
        self.assertEqual(len([s for s in own["sets"] if s.working]), 3)


class ShiftTest(MissedCase):
    def setUp(self):
        super().setUp()
        self.drop_workout_on("2026-10-12")
        self.env = {"COACH_NOW": "2026-10-13T08:00:00Z"}

    def test_shift_moves_session_a_to_thursday_because_saturday_holds_session_a(self):
        data = self.plan(session="session-a", day="2026-10-12")
        self.assertTrue(data["matched"])
        self.assertEqual(data["rule"]["id"], "miss-a")
        draft = data["draft"]
        self.assertEqual(draft["span"], {"start": "2026-10-14", "end": "2026-10-18"})
        self.assertEqual(sessions_of(draft), [("2026-10-14", "session-b"), ("2026-10-15", "session-a"),
                                              ("2026-10-17", "session-a")])
        self.assertEqual([s["moved_from"] for s in draft["sessions"]], [None, "2026-10-12", None])
        moved = [f for f in draft["flags"] if f["code"] == "missed_day_rule"]
        self.assertEqual([(f["session_id"], f["exercise_id"]) for f in moved], [("session-a", None)])
        self.assertEqual(data["write_line"], 'Reply "go" to train this and write: Session B, Session A (Hevy).')

    def test_with_a_session_also_on_thursday_it_is_unmatched(self):
        def add_thursday(doc):
            extra = copy.deepcopy(next(s for s in doc["sessions"] if s["session_id"] == "session-b"))
            extra["date"] = "2026-10-15"
            doc["sessions"].append(extra)
        self.edit_overlay(add_thursday)
        data = self.plan(session="session-a", day="2026-10-12")
        self.assertFalse(data["matched"])
        self.assertEqual(data["rule"]["id"], "miss-a")
        self.assertEqual(codes(data), ["missed_rule_unmatched"])
        self.assertIsNone(data["draft"])

    def test_available_days_rule_out_a_day(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("available_days = []",
                                                                 'available_days = ["mon", "wed", "sat"]'),
                        encoding="utf-8")
        data = self.plan(session="session-a", day="2026-10-12")
        self.assertFalse(data["matched"])
        self.assertIn("Sat 17 Oct already has Session A planned", data["reason"])
        self.assertIn("Thu is not one of the athlete's available days", data["reason"])


class UnmatchedTest(MissedCase):
    def assert_unmatched(self, data):
        self.assertFalse(data["matched"])
        self.assertIsNone(data["draft"])
        self.assertEqual(codes(data), ["missed_rule_unmatched"])
        self.assertIn("--move-to", data["flags"][0]["message"])
        self.assertIn("--drop", data["flags"][0]["message"])

    def test_a_session_with_no_rule(self):
        self.set_rules([])
        self.assert_unmatched(self.plan())

    def test_a_manual_rule(self):
        self.set_rules([{"id": "miss-b", "session_id": "session-b", "text": "Text the coach.", "when": {},
                         "action": {"kind": "manual"}}])
        data = self.plan()
        self.assert_unmatched(data)
        self.assertEqual(data["rule"]["id"], "miss-b")

    def test_a_fold_with_no_later_target_in_the_span(self):
        self.edit_overlay(lambda doc: doc.update(sessions=[s for s in doc["sessions"] if s["date"] != "2026-10-17"]))
        self.assert_unmatched(self.plan())

    def test_a_fold_whose_target_day_has_passed(self):
        self.assert_unmatched(self.plan(env={"COACH_NOW": "2026-10-18T08:00:00Z"}))

    def test_a_shift_whose_free_days_have_passed(self):
        self.drop_workout_on("2026-10-12")
        self.edit_overlay(lambda doc: doc.update(sessions=[s for s in doc["sessions"] if s["date"] != "2026-10-17"]))
        self.assertTrue(self.plan(session="session-a", day="2026-10-12",
                                  env={"COACH_NOW": "2026-10-16T08:00:00Z"})["matched"])
        self.assert_unmatched(self.plan(session="session-a", day="2026-10-12",
                                        env={"COACH_NOW": "2026-10-18T08:00:00Z"}))

    def test_a_skip_rule_matches_and_changes_nothing(self):
        self.set_rules([{"id": "miss-b", "session_id": "session-b", "text": None, "when": {},
                         "action": {"kind": "skip"}}])
        data = self.plan()
        self.assertTrue(data["matched"])
        self.assertIsNone(data["draft"])
        applied = self.apply("--tag", "time")
        self.assertIsNone(applied["overlay_id"])
        self.assertEqual(applied["record_lines"], [
            "- Missed Wed 14 Oct Session B (time).",
            "- Rule miss-b: nothing changes this week.",
            "- No overlay; nothing goes to Hevy.",
        ])
        self.assertEqual(overlay.ids(self.root), [WEEKLY])


class ApplyRuleTest(MissedCase):
    def test_a_synthetic_rule_applies_without_being_in_the_program(self):
        doc = overlay.load(self.root, WEEKLY)
        rule = {"id": "floor-bb-back-squat", "session_id": "session-a", "text": None, "when": {},
                "action": {"kind": "fold", "into": "session-b", "exercises": [{"exercise_id": "bb_back_squat"}]}}
        self.drop_workout_on("2026-10-12")
        draft = missed.apply_rule(self.root, doc, "session-a", "2026-10-12", rule,
                                  now=dates.parse_timestamp("2026-10-13T08:00:00Z"))
        session_b = next(s for s in draft["sessions"] if s["session_id"] == "session-b")
        last = session_b["exercises"][-1]
        self.assertEqual(last["exercise_id"], "bb_back_squat")
        self.assertEqual(last["fold"]["rule_id"], "floor-bb-back-squat")
        self.assertEqual(render.target_line(last), "Target: 2×5 @ 100 kg @ RPE 7")


class ChecksTest(MissedCase):
    def check(self, check_id, root=None, expect=0):
        root = root or self.root
        from tests.support import run_cli

        code, envelope, stderr = run_cli(["--root", str(root), "check", "--only", check_id], env=self.env)
        self.assertEqual(code, expect, (envelope, stderr))
        return [r for r in envelope["data"]["results"] if r["id"] == check_id]

    def test_missed_rules_valid_passes_on_the_fixture_and_fails_on_a_bad_into(self):
        self.assertEqual([r["status"] for r in self.check("missed_rules_valid")], ["pass"])
        results = self.check("missed_rules_valid", INSTANCES / "missed-bad-rule", expect=1)
        self.assertEqual([r["status"] for r in results], ["fail"])
        self.assertIn("session-z", results[0]["message"])

    def test_missed_rules_valid_names_an_exercise_the_session_lacks_and_a_parked_session(self):
        def change(doc):
            doc["missed_day_rules"][0]["action"]["exercises"][0]["exercise_id"] = "bb_back_squat"
            doc["sessions"][0]["status"] = "parked"
        self.edit_json("data/program.json", change)
        messages = [r["message"] for r in self.check("missed_rules_valid", expect=1)]
        self.assertTrue(any("bb_back_squat" in m for m in messages), messages)
        self.assertTrue(any("session-a" in m and "not active" in m for m in messages), messages)

    def test_overlay_folds_expired_passes_with_a_midweek_fold(self):
        self.apply("--tag", "sleep")
        self.assertEqual([r["status"] for r in self.check("overlay_folds_expired")], ["pass"])

    def test_overlay_folds_expired_fails_on_a_weekly_overlay_holding_a_fold(self):
        results = self.check("overlay_folds_expired", INSTANCES / "missed-weekly-fold", expect=1)
        self.assertEqual([r["status"] for r in results], ["fail"])
        self.assertIn("weekly", results[0]["message"])

    def test_overlay_folds_expired_fails_on_a_fold_from_more_than_six_days_back(self):
        self.apply("--tag", "sleep")
        self.edit_overlay(lambda doc: doc["sessions"][0]["exercises"][-1]["fold"].update(from_date="2026-10-10"),
                          MIDWEEK)
        results = self.check("overlay_folds_expired", expect=1)
        self.assertIn("2026-10-10", results[0]["message"])


class MigrationTest(MissedCase):
    def v2_overlay(self):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = read_json(path)
        doc["schema_version"] = 2
        for session in doc["sessions"]:
            del session["moved_from"]
            for line in session["exercises"]:
                del line["fold"]
        doc["approval"]["hash"] = overlay.approval_hash(doc)
        write_json(path, doc)

    def v3_program(self):
        def change(doc):
            doc["schema_version"] = 3
            doc["missed_day_rules"] = [
                {"id": "miss-0001", "session_id": "session-a", "condition": "Session A missed",
                 "action": "train it Tue"},
                {"id": "miss-0002", "session_id": "session-b", "condition": "Session B missed",
                 "action": "skip it"},
            ]
        self.edit_json("data/program.json", change)

    def test_run_upgrades_free_text_rules_to_manual_and_adds_overlay_nulls(self):
        self.v3_program()
        self.v2_overlay()
        data = self.coach("migrate", "run")["data"]
        rule_notes = [n for n in data["notes"] if "missed-day rule" in n]
        self.assertEqual(len(rule_notes), 2)
        program_doc = read_json(self.root / "data" / "program.json")
        self.assertEqual(program_doc["schema_version"], jsonio.current_version(jsonio.load_schema("program")))
        self.assertEqual(program_doc["missed_day_rules"][0], {
            "id": "miss-0001", "session_id": "session-a", "text": "Session A missed → train it Tue", "when": {},
            "action": {"kind": "manual"}})
        self.assertEqual([r["action"]["kind"] for r in program_doc["missed_day_rules"]], ["manual", "manual"])
        doc = read_json(self.root / "data" / "overlays" / f"{WEEKLY}.json")
        self.assertEqual(doc["schema_version"], overlay.current_version())
        self.assertEqual({s["moved_from"] for s in doc["sessions"]}, {None})
        self.assertEqual({repr(line["fold"]) for s in doc["sessions"] for line in s["exercises"]}, {"None"})
        self.assertTrue(self.coach("program", "validate")["data"]["valid"])

    def test_dry_run_lists_approved_overlays_that_lose_approval_and_writes_nothing(self):
        self.v3_program()
        self.v2_overlay()
        before = self.snapshot()
        data = self.coach("migrate", "run", "--dry-run")["data"]
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(any(f"{WEEKLY} loses its approval" in n for n in data["notes"]), data["notes"])
        steps = {row["path"]: row["steps"] for row in data["files"]}
        self.assertEqual(steps[f"data/overlays/{WEEKLY}.json"][0], "overlay/0002_fold_marker")
        self.assertEqual(steps["data/program.json"][0], "program/0003_executable_missed_day_rules")


class RegistrationTest(MissedCase):
    def test_flags_are_registered_to_r22(self):
        for code in ("missed_day_rule", "missed_rule_unmatched"):
            with self.subTest(code=code):
                entry = flags.registry()[code]
                self.assertEqual((entry.owner, entry.severities, entry.structural), ("R-22", ("info",), False))

    def test_the_four_commands_are_allowlisted(self):
        allowed = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        rules = set(allowed["permissions"]["allow"])
        for name in ("list", "plan", "rules", "apply"):
            with self.subTest(command=name):
                self.assertIn(f"Bash(python3 -m coach missed {name}:*)", rules)

    def test_library_names_come_from_the_instance(self):
        self.assertEqual(Library.load(self.root).get(ROW)["name"], "Single-arm row")


class ProgramWeekSkillTest(MissedCase):
    def test_the_mid_week_step_runs_the_missed_commands_and_only_writes_after_go(self):
        text = skill_text("program-week")
        step = " ".join(re.search(r"\*\*Mid-week\?\*\*(.*?)\n\n", text, re.DOTALL).group(1).split())
        order = ["missed list", "missed plan", '"go"', "missed apply", "overlay approve", "routines push"]
        positions = [step.index(word) for word in order]
        self.assertEqual(positions, sorted(positions), step)
        self.assertIn("`missed_rule_unmatched`", step)
        self.assertIn('"No rule applies"', step)
        self.assertNotIn("--kind midweek", step)
        self.assertNotIn("missed apply", step[:step.index('"go"')])
        self.assertIn("for Hevy users, `python3 -m coach routines push", step)
        self.assertIn("`recorded: true`", step)
