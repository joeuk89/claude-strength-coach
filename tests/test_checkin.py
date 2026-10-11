"""The check-in card, records, misses and the record skeleton (contract C36, C11, C17, C18, C20)."""

import json
import shutil
import sys
import tempfile
import textwrap
import types
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import coach.checkin_parts
import coach.checks
import coach.commands
from coach import checkin, flags
from tests.support import INSTANCES, REPO_ROOT
from tests.support.history import R_A, R_B, W, HistoryCase, read_json, write_json

CHECKIN = INSTANCES / "checkin"
TAGS = "time / sleep / ill / family / skipped / other"
R01_NUTRITION = "No MacroFactor: this week's morning weigh-ins, and roughly how eating went"
R01_MEAL_PLAN = "What stuck, what got swapped?"


class CheckinCase(HistoryCase):
    base = CHECKIN

    def prepare(self, *argv, expect=0):
        return self.coach("checkin", "prepare", *argv, expect=expect)

    def card(self, *argv):
        return self.prepare(*argv)["data"]["card"]

    def text(self, *argv):
        return self.prepare(*argv)["data"]["text"]

    def field(self, card, field_id):
        return next((f for f in card["fields"] if f["id"] == field_id), None)

    def rename(self, old, new):
        source = self.root / "check-ins" / f"{old}.md"
        text = source.read_text(encoding="utf-8").replace(old, new)
        source.unlink()
        (self.root / "check-ins" / f"{new}.md").write_text(text, encoding="utf-8")

    def data_bytes(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in sorted((self.root / "data").rglob("*")) if p.is_file()}


def stub_nutrition(status):
    module = types.ModuleType("coach.nutrition")
    module.QUESTION_NEXT_WEEK = "food exceptions next week: who cooks which nights, office-day changes, meals out?"
    module.status = lambda root, today: status
    return module


class RecordsTest(unittest.TestCase):
    def test_records_oldest_first_with_their_tiers(self):
        found = checkin.records(CHECKIN)
        self.assertEqual([(r.date.isoformat(), r.tier) for r in found],
                         [("2026-09-06", "deep"), ("2026-10-04", "weekly")])

    def test_a_record_without_a_tier_marker_counts_as_deep(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "check-ins").mkdir()
            (root / "check-ins" / "2026-10-04.md").write_text("# Check-in — 2026-10-04\n", encoding="utf-8")
            (root / "check-ins" / "notes.md").write_text("# Notes\n", encoding="utf-8")
            self.assertEqual([(r.date.isoformat(), r.tier) for r in checkin.records(root)], [("2026-10-04", "deep")])

    def test_due_after_the_last_record(self):
        due = checkin.due(CHECKIN, date(2026, 10, 13))
        self.assertEqual((due.last.date.isoformat(), due.days_since, due.due_date.isoformat(), due.overdue_days),
                         ("2026-10-04", 9, "2026-10-11", 2))
        self.assertEqual(due.mode, "weekly")

    def test_due_modes(self):
        self.assertEqual(checkin.due(CHECKIN, date(2026, 10, 14)).mode, "weekly")
        self.assertEqual(checkin.due(CHECKIN, date(2026, 10, 15)).mode, "catch_up")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(CHECKIN / "check-ins", root / "check-ins")
            (root / "check-ins" / "2026-10-11.md").write_text("# Check-in — 2026-10-11 (weekly)\n", encoding="utf-8")
            due = checkin.due(root, date(2026, 10, 18))
            self.assertEqual(due.mode, "deep")
            self.assertTrue(any("42 days" in reason for reason in due.tier_reasons), due.tier_reasons)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(checkin.due(Path(tmp), date(2026, 10, 15)).mode, "first")

    def test_catch_up_threshold_is_r02s_first_return_band(self):
        self.assertEqual(checkin.CATCH_UP_AFTER_DAYS, 10)


class DueCommandTest(CheckinCase):
    def test_due_command(self):
        data = self.coach("checkin", "due")["data"]
        self.assertEqual(data["last"], {"date": "2026-10-04", "tier": "weekly", "path": "check-ins/2026-10-04.md"})
        self.assertEqual((data["days_since"], data["due_date"], data["overdue_days"], data["mode"]),
                         (7, "2026-10-11", 0, "weekly"))

    def test_cadence_comes_from_config(self):
        with open(self.root / "config.toml", "a", encoding="utf-8") as handle:
            handle.write("\n[checkin]\ncadence_days = 14\n")
        self.assertEqual(self.coach("checkin", "due")["data"]["due_date"], "2026-10-18")


class CardSessionsTest(CheckinCase):
    def test_window_mode_and_sessions(self):
        card = self.card()
        self.assertEqual(card["window"], {"start": "2026-10-05", "end": "2026-10-11"})
        self.assertEqual((card["mode"], card["days_since_last"], card["unsynced"]), ("weekly", 7, 0))
        sessions = card["sessions"]
        rows = [(r["title"], r["date"], r["status"], r["tag"]) for r in sessions["rows"]]
        self.assertEqual(rows, [("Session A", "2026-10-05", "trained", None),
                                ("Session B", "2026-10-08", "trained", None),
                                ("Session A", "2026-10-10", "missed", "untagged")])
        first = sessions["rows"][0]
        self.assertEqual((first["minutes"], first["cap_minutes"], first["tier"], first["workout_id"]),
                         (58, 45, "core", W[3]))
        self.assertEqual((sessions["planned_core"], sessions["trained_core"], sessions["optional_trained"]),
                         (3, 2, 0))
        self.assertEqual(sessions["external"],
                         [{"date": "2026-10-06", "external_id": "pt-tue", "title": "PT", "done": None, "note": None}])

    def test_until_ends_the_window_early(self):
        card = self.card("--until", "2026-10-08")
        self.assertEqual(card["window"]["end"], "2026-10-08")
        self.assertEqual([r["date"] for r in card["sessions"]["rows"]], ["2026-10-05", "2026-10-08"])

    def test_exercise_rows(self):
        rows = {(r["date"], r["exercise_id"]): r for r in self.card()["exercises"]}
        self.assertEqual(rows[("2026-10-05", "bb_back_squat")]["status"], "hit")
        bench = rows[("2026-10-05", "db_bench_press")]
        self.assertEqual(bench["status"], "hit")
        self.assertEqual(bench["prescribed"], "3×10 @ 22.5/hand (Hevy: 45) @ RPE 8")
        self.assertEqual(bench["logged"], "10, 10, 10 @ 22.5/hand (Hevy: 45) @ RPE 8")
        row = rows[("2026-10-08", "db_single_arm_row")]
        self.assertEqual((row["status"], row["rpe_delta"]), ("hit", 0.5))
        self.assertNotIn("2026-10-10", {r["date"] for r in rows.values()})

    def test_e1rm_rows(self):
        rows = {r["exercise_id"]: r for r in self.card()["e1rm"]}
        # C18's delta is latest minus previous rounded point: 121.88 − 120.33 = 1.55.
        self.assertEqual((rows["bb_back_squat"]["e1rm"], rows["bb_back_squat"]["delta"],
                          rows["bb_back_squat"]["method"]), (121.88, 1.55, "epley_rir"))
        self.assertEqual((rows["db_bench_press"]["e1rm"], rows["db_bench_press"]["delta"]), (31.5, 0))
        self.assertEqual((rows["db_single_arm_row"]["e1rm"], rows["db_single_arm_row"]["delta"]), (41.5, -0.5))
        order = [r["exercise_id"] for r in self.card()["e1rm"]]
        self.assertEqual(order[:3], ["bb_back_squat", "db_bench_press", "db_single_arm_row"])

    def test_e1rm_rows_are_capped_at_eight(self):
        self.assertEqual(checkin.E1RM_ROW_LIMIT, 8)

    def test_flags_and_hevy(self):
        card = self.card()
        over = [f for f in card["flags"] if f["code"] == "duration_over_cap"]
        self.assertEqual(len(over), 1)
        self.assertIn("2026-10-05", over[0]["message"])
        self.assertNotIn("stale_routine", {f["code"] for f in card["flags"]})
        states = {h["title"]: h["state"] for h in card["hevy"]}
        self.assertEqual(states, {"Session A": "current", "Session B": "edited_in_app"})
        edited = next(h for h in card["hevy"] if h["title"] == "Session B")
        self.assertTrue(edited["changes"])
        self.assertTrue(all(c["class"] == "structural" for c in edited["changes"]))
        last = card["fields"][-1]
        self.assertEqual(last["id"], "hevy_edits")
        self.assertIn("Session B", last["prefill"] + last["ask"])

    def test_text_asks_for_the_tag_and_the_coach_led_content(self):
        card = self.card()
        self.assertEqual([f["n"] for f in card["fields"]], list(range(1, len(card["fields"]) + 1)))
        text = self.text()
        lines = text.splitlines()
        first = next(line for line in lines if line.startswith("1. "))
        self.assertIn("Sessions", first)
        sessions_field = text[text.index("1. Sessions"):text.index("\n2. ")]
        self.assertIn("Sat 10 Oct Session A", sessions_field)
        self.assertIn(TAGS, sessions_field)
        coach_led = text[text.index("\n2. "):text.index("\n3. ")]
        self.assertIn("Coach-led", coach_led)
        self.assertIn("What did PT on Tue 6 Oct cover?", coach_led)

    def test_no_external_sessions_means_no_coach_led_field(self):
        self.edit_json("data/program.json", lambda doc: doc.update(external_sessions=[]))
        card = self.card()
        self.assertIsNone(self.field(card, "coach_led"))
        self.assertEqual([f["n"] for f in card["fields"]], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(card["sessions"]["external"], [])

    def test_external_annotation_is_stated_not_asked(self):
        self.coach("history", "annotate", "--kind", "external", "--date", "2026-10-06", "--external", "pt-tue",
                   "--done", "--note", "chest and back")
        card = self.card()
        self.assertEqual(card["sessions"]["external"][0]["note"], "chest and back")
        coach_led = self.field(card, "coach_led")
        self.assertIn("chest and back", coach_led["prefill"])
        self.assertIsNone(coach_led["ask"])

    def test_stale_routine_without_a_verify_line(self):
        path = self.root / "data" / "hevy" / "writes.jsonl"
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if R_A not in line]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        card = self.card()
        stale = [f for f in card["flags"] if f["code"] == "stale_routine"]
        self.assertEqual(len(stale), 1)
        self.assertIn("Session A", stale[0]["message"])
        self.assertEqual({h["title"]: h["state"] for h in card["hevy"]}["Session A"], "not_written")

    def drop_cached_routine(self, routine_id):
        self.edit_json(".coach/cache/hevy/routines.json",
                       lambda doc: doc.update(data=[r for r in doc["data"] if r["id"] != routine_id]))

    def test_stale_routine_does_not_need_the_cache(self):
        path = self.root / "data" / "hevy" / "writes.jsonl"
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if R_A not in line]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        self.drop_cached_routine(R_A)
        card = self.card()
        stale = [f for f in card["flags"] if f["code"] == "stale_routine"]
        self.assertEqual([f["session_id"] for f in stale], ["session-a"])
        self.assertEqual({h["routine_id"]: h["state"] for h in card["hevy"]}[R_A], "not_written")

    def test_a_written_routine_missing_from_the_cache_is_not_cached(self):
        self.drop_cached_routine(R_A)
        card = self.card()
        self.assertNotIn("stale_routine", {f["code"] for f in card["flags"]})
        self.assertEqual({h["routine_id"]: h["state"] for h in card["hevy"]}[R_A], "not_cached")

    def test_hevy_off_skips_the_routine_comparison(self):
        config = (self.root / "config.toml").read_text(encoding="utf-8")
        (self.root / "config.toml").write_text(config.replace("[hevy]\nenabled = true", "[hevy]\nenabled = false"),
                                               encoding="utf-8")
        card = self.card()
        self.assertEqual(card["hevy"], [])
        self.assertIsNone(self.field(card, "hevy_edits"))

    def test_trained_unlogged_counts_as_trained(self):
        self.coach("history", "annotate", "--kind", "trained_unlogged", "--date", "2026-10-10", "--session",
                   "session-a", "--note", "hotel gym, phone dead")
        card = self.card()
        self.assertEqual((card["sessions"]["trained_core"], card["sessions"]["planned_core"]), (3, 3))
        row = card["sessions"]["rows"][2]
        self.assertEqual((row["status"], row["unlogged"]), ("trained", True))
        tenth = [r for r in card["exercises"] if r["date"] == "2026-10-10"]
        self.assertEqual({r["status"] for r in tenth}, {"unknown"})
        self.assertEqual(len(tenth), 2)
        self.assertNotIn(TAGS, self.text())
        self.assertIsNone(self.field(card, "sessions")["ask"])

    def test_unsynced_workouts_read_without_writing(self):
        synced = self.card()
        (self.root / "data" / "history" / "2026-10.json").unlink()
        before = self.data_bytes()
        card = self.card()
        self.assertEqual(card["unsynced"], 2)
        for key in ("sessions", "exercises", "e1rm"):
            with self.subTest(key=key):
                self.assertEqual(card[key], synced[key])
        self.assertEqual(self.data_bytes(), before)


class DeepTierTest(CheckinCase):
    def test_deep_after_42_days_with_misses(self):
        self.rename("2026-09-06", "2026-08-30")
        card = self.card()
        self.assertEqual(card["mode"], "deep")
        self.assertTrue(any("42 days" in reason for reason in card["tier_reasons"]), card["tier_reasons"])
        self.assertEqual(card["misses"]["by_tag"]["untagged"], 1)
        self.assertIn("2026-08-30", self.text())

    def test_weekly_at_35_days(self):
        card = self.card()
        self.assertEqual((card["mode"], card["misses"]), ("weekly", None))

    def test_tier_override(self):
        self.assertEqual(self.card("--tier", "deep")["mode"], "deep")
        self.rename("2026-09-06", "2026-08-30")
        self.assertEqual(self.card("--tier", "weekly")["mode"], "weekly")

    def test_misses_command(self):
        data = self.coach("checkin", "misses", "--since", "2026-08-30")["data"]
        self.assertEqual(data["by_tag"], {"time": 1, "sleep": 2, "ill": 0, "family": 0, "skipped": 0, "other": 0,
                                          "untagged": 1})
        self.assertEqual(data["by_session"], {"session-a": 3, "session-b": 1})
        self.assertEqual(data["sessions_missed"], 4)

    def test_a_tagged_miss_in_the_window_is_counted_once(self):
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-a",
                   "--tag", "family")
        data = self.coach("checkin", "misses", "--since", "2026-08-30")["data"]
        self.assertEqual((data["by_tag"]["family"], data["by_tag"]["untagged"], data["sessions_missed"]), (1, 0, 4))

    def test_a_skipped_optional_session_is_not_a_miss(self):
        def make_a_optional(doc):
            next(s for s in doc["sessions"] if s["id"] == "session-a")["tier"] = "optional"
        self.edit_json("data/program.json", make_a_optional)
        data = self.coach("checkin", "misses", "--since", "2026-08-30")["data"]
        self.assertEqual(data["by_session"], {"session-b": 1})
        self.assertEqual((data["by_tag"]["untagged"], data["sessions_missed"]), (0, 1))

    def test_no_record_is_a_first_deep_check_in(self):
        for path in (self.root / "check-ins").glob("*.md"):
            path.unlink()
        card = self.card()
        self.assertEqual(card["mode"], "deep")
        self.assertEqual(card["window"]["start"], "2026-10-05")
        self.assertIsNone(card["days_since_last"])

    def test_a_long_gap_warns_that_catch_up_is_pending(self):
        envelope = self.coach("checkin", "prepare", env={"COACH_NOW": "2026-10-16T18:00:00Z"})
        self.assertEqual(envelope["data"]["card"]["mode"], "weekly")
        self.assertTrue(any("catch_up_pending" in w for w in envelope["warnings"]), envelope["warnings"])


class NutritionPartTest(CheckinCase):
    @classmethod
    def setUpClass(cls):
        # Import every module that reads coach.nutrition at import time before the tests swap it out.
        coach.commands.discover()
        coach.checks.discover()

    def test_without_the_module_r01_fields_stay(self):
        with mock.patch.dict(sys.modules, {"coach.nutrition": None}):
            card = self.card()
        self.assertIn(R01_NUTRITION, self.field(card, "nutrition")["ask"])
        self.assertEqual(self.field(card, "nutrition")["n"], 6)
        self.assertEqual((self.field(card, "meal_plan")["n"], self.field(card, "meal_plan")["ask"]),
                         (7, R01_MEAL_PLAN))

    def test_enabled_status_replaces_field_6_and_drops_7(self):
        questions = ["readings?", "anchors most days (y/n)? Anything in the plan that didn't work?",
                     "food exceptions next week: who cooks which nights, office-day changes, meals out?"]
        stub = stub_nutrition({"enabled": True, "questions": questions})
        with mock.patch.dict(sys.modules, {"coach.nutrition": stub}):
            card = self.card()
        food = self.field(card, "nutrition")
        self.assertEqual(food["n"], 6)
        for question in questions:
            self.assertIn(question, food["ask"])
        self.assertIsNone(self.field(card, "meal_plan"))
        self.assertEqual(self.field(card, "next_week")["n"], 7)
        self.assertIn(questions[2], card["nudge_lines"])

    def test_disabled_status_brings_r01_back(self):
        with mock.patch.dict(sys.modules, {"coach.nutrition": stub_nutrition({"enabled": False})}):
            card = self.card()
        self.assertIn(R01_NUTRITION, self.field(card, "nutrition")["ask"])
        self.assertEqual(self.field(card, "meal_plan")["n"], 7)

    def test_the_real_module_with_the_fixture_config(self):
        card = self.card()
        food = self.field(card, "nutrition")
        self.assertIn("trend weight", food["ask"])
        self.assertIsNone(self.field(card, "meal_plan"))


class CardPartsTest(CheckinCase):
    def setUp(self):
        super().setUp()
        self.parts_dir = Path(tempfile.mkdtemp(dir=self.tmp))
        self.added = []

    def tearDown(self):
        for name in self.added:
            sys.modules.pop(f"coach.checkin_parts.{name}", None)

    def part(self, name, body):
        name = f"{name}_{id(self)}"
        (self.parts_dir / f"{name}.py").write_text(textwrap.dedent(body), encoding="utf-8")
        self.added.append(name)
        return name

    def paths(self, builtin=True):
        found = list(coach.checkin_parts.__path__) if builtin else []
        return mock.patch.object(coach.checkin_parts, "__path__", found + [str(self.parts_dir)])

    def test_a_part_replaces_a_builtin_field(self):
        self.part("runs_a", """
            from coach.checkin_parts import Contribution, Field
            FIELDS = ("runs",)
            def contribute(ctx):
                return Contribution(fields={"runs": Field(prefill="Logged: 2 runs, 10 km.", ask="Any others?")},
                                    facts=["A fact from a part."])
        """)
        with self.paths():
            card = self.card()
            text = self.text()
        runs = self.field(card, "runs")
        self.assertEqual((runs["n"], runs["prefill"], runs["ask"]), (3, "Logged: 2 runs, 10 km.", "Any others?"))
        self.assertIn("3. Runs. Logged: 2 runs, 10 km. Any others?", text)
        self.assertIn("A fact from a part.", card["facts"])

    def test_two_parts_owning_one_field_is_an_error(self):
        first = self.part("runs_a", "FIELDS = ('runs',)\ndef contribute(ctx):\n    return None\n")
        second = self.part("runs_b", "FIELDS = ('runs',)\ndef contribute(ctx):\n    return None\n")
        with self.paths():
            envelope = self.prepare(expect=1)
        message = envelope["error"]["message"]
        self.assertIn(first, message)
        self.assertIn(second, message)

    def test_none_for_a_field_removes_it_and_renumbers(self):
        self.part("no_plan", """
            from coach.checkin_parts import Contribution
            FIELDS = ("meal_plan",)
            def contribute(ctx):
                return Contribution(fields={"meal_plan": None})
        """)
        with self.paths(builtin=False):
            card = self.card()
        self.assertIsNone(self.field(card, "meal_plan"))
        self.assertEqual([f["n"] for f in card["fields"]], list(range(1, len(card["fields"]) + 1)))
        self.assertEqual(self.field(card, "next_week")["n"], 7)

    def test_a_contribution_of_none_keeps_the_builtin(self):
        self.part("quiet", "FIELDS = ('sleep',)\ndef contribute(ctx):\n    return None\n")
        with self.paths():
            card = self.card()
        self.assertIn("average hours a night", self.field(card, "sleep")["ask"])

    def test_tier_reasons_and_flags_from_a_part(self):
        self.part("deep_reason", """
            from coach import flags
            from coach.checkin_parts import Contribution
            FIELDS = ()
            def contribute(ctx):
                return Contribution(tier_reasons=["two fatigue triggers"],
                                    flags=[flags.make("stale_routine", message="from a part")])
        """)
        with self.paths():
            card = self.card()
        self.assertEqual(card["mode"], "deep")
        self.assertIn("two fatigue triggers", card["tier_reasons"])
        self.assertIn("from a part", [f["message"] for f in card["flags"]])

    def test_a_part_may_only_set_fields_it_owns(self):
        self.part("greedy", """
            from coach.checkin_parts import Contribution, Field
            FIELDS = ("runs",)
            def contribute(ctx):
                return Contribution(fields={"sleep": Field(ask="?")})
        """)
        with self.paths():
            envelope = self.prepare(expect=1)
        self.assertIn("sleep", envelope["error"]["message"])


class SkeletonTest(CheckinCase):
    RECORD = Path("check-ins") / "2026-10-11.md"

    def skeleton(self, *argv, expect=0):
        return self.coach("checkin", "skeleton", "--date", "2026-10-11", *argv, expect=expect)

    def record(self):
        return (self.root / self.RECORD).read_text(encoding="utf-8")

    def test_writes_the_record(self):
        self.skeleton("--overlay", "2026-10-12-weekly")
        text = self.record()
        self.assertTrue(text.startswith("# Check-in — 2026-10-11 (weekly)\n"))
        self.assertIn("<!-- coach:begin week-review 2026-10-11 -->", text)
        for heading in ("## Week in review", "## Coach's read", "## Decisions", "## Next week"):
            self.assertIn(f"\n{heading}\n", text)
        self.assertNotIn("## Block planning", text)
        details = text[text.index("<details>"):text.index("</details>")]
        self.assertIn("<!-- coach:begin overlay 2026-10-12-weekly -->", details)
        self.assertIn("<!-- coach:end overlay 2026-10-12-weekly -->", details)
        review = text[text.index("<!-- coach:begin week-review"):text.index("<!-- coach:end week-review")]
        self.assertIn("**Window:** 2026-10-05 → 2026-10-11", review)
        self.assertIn("**Sessions:** 2 of 3 core", review)
        self.assertIn("**Missed:** Sat 10 Oct Session A (untagged)", review)
        self.assertNotIn(TAGS, review)

    def test_region_reads_synced_history_only_and_warns(self):
        (self.root / "data" / "history" / "2026-10.json").unlink()
        envelope = self.skeleton()
        self.assertEqual(envelope["data"]["unsynced"], 2)
        self.assertTrue(any("history sync" in w for w in envelope["warnings"]), envelope["warnings"])
        self.assertIn("**Sessions:** 0 of 3 core", self.record())

    def test_second_run_exits_1(self):
        self.skeleton()
        self.skeleton(expect=1)

    def test_dry_run_writes_nothing(self):
        data = self.skeleton("--overlay", "2026-10-12-weekly", "--dry-run")["data"]
        self.assertFalse((self.root / self.RECORD).exists())
        self.assertTrue(data["text"].startswith("# Check-in — 2026-10-11 (weekly)"))

    def test_refresh_rewrites_only_the_regions(self):
        self.skeleton("--overlay", "2026-10-12-weekly")
        text = self.record().replace("## Coach's read\n", "## Coach's read\n\nA solid week; one miss.\n", 1)
        (self.root / self.RECORD).write_text(text, encoding="utf-8")
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-a",
                   "--tag", "sleep")
        self.skeleton("--refresh")
        after = self.record()
        self.assertIn("**Missed:** Sat 10 Oct Session A (sleep)", after)
        start = after.index("<!-- coach:end week-review 2026-10-11 -->")
        old_start = text.index("<!-- coach:end week-review 2026-10-11 -->")
        self.assertEqual(after[start:], text[old_start:])
        self.assertEqual(after[:after.index("<!-- coach:begin week-review")],
                         text[:text.index("<!-- coach:begin week-review")])

    def test_refresh_collapses_an_overlay_region_written_by_overlay_render(self):
        self.skeleton()
        self.coach("overlay", "render", "2026-10-12-weekly", "--into", str(self.root / self.RECORD))
        self.assertNotIn("<details>", self.record())
        self.skeleton("--refresh", "--overlay", "2026-10-12-weekly")
        text = self.record()
        self.assertEqual(text.count("<!-- coach:begin overlay 2026-10-12-weekly -->"), 1)
        details = text[text.index("<details>"):text.index("</details>")]
        self.assertIn("<!-- coach:begin overlay 2026-10-12-weekly -->", details)
        self.assertIn("<!-- coach:end overlay 2026-10-12-weekly -->", details)
        self.skeleton("--refresh", "--overlay", "2026-10-12-weekly")
        self.assertEqual(self.record(), text)

    def test_deep_record_adds_block_planning_and_misses(self):
        self.rename("2026-09-06", "2026-08-30")
        self.skeleton()
        text = self.record()
        self.assertTrue(text.startswith("# Check-in — 2026-10-11 (deep)\n"))
        self.assertIn("\n## Block planning\n", text)
        self.assertLess(text.index("## Decisions"), text.index("## Block planning"))
        review = text[text.index("<!-- coach:begin week-review"):text.index("<!-- coach:end week-review")]
        self.assertIn("untagged 1", review)

    def test_the_new_record_passes_every_check(self):
        self.skeleton("--overlay", "2026-10-12-weekly")
        results = self.coach("check")["data"]["results"]
        failed = [r for r in results if r["status"] == "fail"]
        self.assertEqual(failed, [])


class FreshnessTest(CheckinCase):
    def sweep(self, expect=0):
        return self.coach("check", "--only", "render_fresh_sweep", expect=expect)["data"]["results"]

    def edit_region(self, name, old, new):
        path = self.root / "check-ins" / name
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_the_fixture_record_is_fresh(self):
        self.sweep()

    def test_editing_the_newest_region_fails(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        self.edit_region("2026-10-11.md", "2 of 3 core", "3 of 3 core")
        failed = [r for r in self.sweep(expect=1) if r["status"] == "fail"]
        self.assertTrue(any("week-review 2026-10-11" in r["message"] for r in failed), failed)

    def test_editing_an_older_region_does_not(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        self.edit_region("2026-10-04.md", "**Window:**", "**Window (edited):**")
        self.sweep()

    def test_render_week_review_returns_an_archive_region_unchanged(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        self.edit_region("2026-10-04.md", "**Window:**", "**Window (edited):**")
        self.assertIn("**Window (edited):**", checkin.render_week_review(self.root, "2026-10-04"))


class RecordChecksTest(CheckinCase):
    def check(self, check_id):
        return self.coach("check", "--only", check_id)["data"]["results"]

    def test_word_ceiling_warns_on_a_long_weekly_record(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        path = self.root / "check-ins" / "2026-10-11.md"
        prose = " ".join(["word"] * 700)
        path.write_text(path.read_text(encoding="utf-8").replace("## Coach's read\n", f"## Coach's read\n\n{prose}\n"),
                        encoding="utf-8")
        results = self.check("checkin_record_words")
        warned = [r for r in results if r["status"] == "warn"]
        self.assertEqual(len(warned), 1)
        self.assertIn("2026-10-11", warned[0]["message"])

    def test_word_ceiling_passes_a_short_record(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        self.assertEqual({r["status"] for r in self.check("checkin_record_words")}, {"pass"})

    def test_word_ceilings_are_labelled_heuristics(self):
        self.assertEqual(checkin.WORD_CEILINGS, {"weekly": 600, "deep": 1000, "catch-up": 600})

    def test_records_check_warns_on_an_unparseable_first_line(self):
        (self.root / "check-ins" / "2026-10-07.md").write_text("Some notes\n", encoding="utf-8")
        warned = [r for r in self.check("checkin_records") if r["status"] == "warn"]
        self.assertEqual([r["path"] for r in warned], ["check-ins/2026-10-07.md"])

    def test_records_check_passes_the_fixture(self):
        self.assertEqual({r["status"] for r in self.check("checkin_records")}, {"pass"})


class RegistrationTest(unittest.TestCase):
    def test_stale_routine_is_registered(self):
        code = flags.registry()["stale_routine"]
        self.assertEqual((code.owner, code.severities, code.structural), ("R-21a", ("warn",), False))

    def test_commands_are_allowlisted(self):
        allowed = set(read_json(REPO_ROOT / ".claude" / "settings.json")["permissions"]["allow"])
        for name in ("prepare", "misses", "due", "skeleton"):
            with self.subTest(command=name):
                self.assertIn(f"Bash(python3 -m coach checkin {name}:*)", allowed)


class CheckInSkillTest(unittest.TestCase):
    def setUp(self):
        self.text = " ".join((REPO_ROOT / ".claude" / "skills" / "check-in" / "SKILL.md").read_text(
            encoding="utf-8").split())

    def section(self, start, end):
        return self.text[self.text.index(start):self.text.index(end)]

    def test_sunday_message_comes_from_prepare(self):
        step = self.section("## 3. Send the Sunday message", "## 4.")
        self.assertIn("python3 -m coach checkin prepare", step)
        self.assertIn("data.text", step)
        self.assertIn("python3 -m coach history annotate --input", step)

    def test_record_comes_from_the_skeleton(self):
        step = self.section("## 6. Write the record", "## 7.")
        self.assertIn("python3 -m coach checkin skeleton", step)

    def test_deep_tier_reads_misses(self):
        self.assertIn("python3 -m coach checkin misses", self.text)


if __name__ == "__main__":
    unittest.main()
