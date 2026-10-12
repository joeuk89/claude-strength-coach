"""The weekly card asks only what applies and carries the athlete's logged notes (contract C36, C35, C49)."""

import json
import re
import shutil
import unittest

from tests.support import INSTANCES
from tests.support.config_edit import apply
from tests.support.history import HistoryCase

NOHEVY = INSTANCES / "nohevy"
SUNDAY = "2026-10-18T18:00:00Z"
WORKOUT_NOTE = "shoulder a bit pinchy on bench, otherwise fine"
BENCH_NOTE = "right shoulder pinchy at the bottom, 3/10"
APP_READINGS = "trend weight · expenditure"
NO_APP_READINGS = "this week's morning weigh-ins"
PLAN_ASK = "Anything in the plan that didn't work?"


class CardSourcesCase(HistoryCase):
    """A copy of `nohevy/` reviewed on Sunday 18 October: the window is 12–18 October."""

    base = NOHEVY

    def setUp(self):
        super().setUp()
        self.env = {"COACH_NOW": SUNDAY}

    def configure(self, values):
        path = self.root / "config.toml"
        path.write_text(apply(path.read_text(encoding="utf-8"), values), encoding="utf-8")

    def without(self, *relative):
        for name in relative:
            path = self.root / name
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

    def card(self):
        return self.coach("checkin", "prepare")["data"]

    def field(self, card, field_id):
        return next((f for f in card["fields"] if f["id"] == field_id), None)

    def log(self, day="2026-10-12", notes="", bench_notes=""):
        draft = self.coach("log", "prefill", "--session", "session-a", "--date", day)["data"]["draft"]
        draft["notes"] = notes
        for exercise in draft["exercises"]:
            for set_ in exercise["sets"]:
                set_["reps"] = set_["reps"] or 10
            if exercise["exercise_id"] == "db_bench_press":
                exercise["notes"] = bench_notes
        path = self.tmp / f"log-{day}.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        self.coach("log", "add", "--input", str(path))
        self.coach("history", "sync")

    def data_bytes(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in sorted(self.root.rglob("*")) if p.is_file() and ".coach" not in p.parts}


class ApplicableFieldsTest(CardSourcesCase):
    def test_nothing_set_up_asks_one_scale_weight_and_no_runs_or_meal_plan(self):
        self.configure({"activity": {"enabled": False}, "nutrition": {"enabled": False}})
        self.without("data/nutrition/plans", "data/activity/planned.jsonl")
        self.log()
        data = self.card()
        ids = [f["id"] for f in data["card"]["fields"]]
        self.assertNotIn("runs", ids)
        self.assertNotIn("meal_plan", ids)
        weight = self.field(data["card"], "nutrition")
        self.assertEqual((weight["label"], weight["prefill"], weight["ask"]),
                         ("Bodyweight", None, "One morning scale weight."))
        self.assertNotIn("MacroFactor", data["text"])
        self.assertNotIn("Runs.", data["text"])
        self.assertNotIn("Meal plan", data["text"])
        self.assertEqual([f["n"] for f in data["card"]["fields"]], list(range(1, len(ids) + 1)))

    def test_macrofactor_asks_its_status_questions_once(self):
        self.configure({"activity": {"enabled": False}})
        data = self.card()
        food = self.field(data["card"], "nutrition")
        self.assertEqual(food["label"], "Food")
        self.assertEqual(food["ask"].count(APP_READINGS), 1)
        self.assertNotIn(NO_APP_READINGS, food["ask"])
        self.assertEqual(data["text"].count("Food."), 1)
        self.assertIsNone(self.field(data["card"], "meal_plan"))

    def test_nutrition_without_an_app_asks_the_scale_questions_only(self):
        self.configure({"nutrition": {"app": "none"}})
        food = self.field(self.card()["card"], "nutrition")
        self.assertIn(NO_APP_READINGS, food["ask"])
        self.assertNotIn(APP_READINGS, food["ask"])
        self.assertNotIn("MacroFactor", food["ask"])

    def test_a_meal_plan_in_force_is_stated_and_asked_about(self):
        food = self.field(self.card()["card"], "nutrition")
        self.assertIn("Meal plan: nutrition/plans/2026-10-12.md.", food["prefill"])
        self.assertIn(PLAN_ASK, food["ask"])

    def test_the_meal_plan_prefill_sits_on_its_own_line_above_the_lettered_asks(self):
        data = self.card()
        food = self.field(data["card"], "nutrition")
        lines = data["text"].splitlines()
        at = lines.index(f"{food['n']}. Food.")
        self.assertTrue(lines[at + 1].startswith("   Meal plan: nutrition/plans/2026-10-12.md."), lines[at + 1])
        self.assertTrue(lines[at + 2].startswith("   a. "), lines[at + 2])

    def test_no_meal_plan_means_no_plan_question(self):
        self.without("data/nutrition/plans")
        food = self.field(self.card()["card"], "nutrition")
        self.assertNotIn(PLAN_ASK, food["ask"])
        self.assertNotIn("Meal plan", food["prefill"] or "")
        self.assertIn("anchors most days (y/n)?", food["ask"])


class RunsFieldTest(CardSourcesCase):
    def setUp(self):
        super().setUp()
        self.configure({"activity": {"enabled": False}})

    def test_planned_runs_keep_the_runs_field_with_the_source_off(self):
        runs = self.field(self.card()["card"], "runs")
        self.assertEqual(runs["prefill"], "Planned, not logged: Wed 14 Oct Easy 5 km, Fri 16 Oct Intervals.")
        self.assertEqual(runs["ask"], "How many, and total distance?")

    def test_a_recorded_run_keeps_the_runs_field_with_the_source_off(self):
        self.without("data/activity/planned.jsonl")
        line = json.loads((self.root / "data/activity/activities.jsonl").read_text(encoding="utf-8").splitlines()[0])
        line.update(id="manual:2026-10-14-run-1", start="2026-10-14T05:30:00Z", end="2026-10-14T06:00:00Z",
                    local_date="2026-10-14")
        with open(self.root / "data/activity/activities.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line) + "\n")
        runs = self.field(self.card()["card"], "runs")
        self.assertEqual(runs["prefill"], "Logged: 1 run, 5 km.")
        self.assertEqual(runs["ask"], "Any others not logged: how many, and total distance?")

    def test_lifting_alone_is_no_evidence_of_running(self):
        self.without("data/activity/planned.jsonl")
        self.log()
        self.assertIsNone(self.field(self.card()["card"], "runs"))

    def test_an_activity_source_keeps_the_runs_field(self):
        self.configure({"activity": {"enabled": True}})
        self.without("data/activity/planned.jsonl", "data/activity/activities.jsonl")
        runs = self.field(self.card()["card"], "runs")
        self.assertEqual(runs["ask"], "How many, and total distance?")


class LoggedNotesTest(CardSourcesCase):
    def setUp(self):
        super().setUp()
        self.configure({"activity": {"enabled": False}, "nutrition": {"enabled": False}})
        self.without("data/activity/planned.jsonl")

    def test_workout_and_exercise_notes_reach_the_card_and_the_record_once(self):
        self.log(notes=WORKOUT_NOTE, bench_notes=BENCH_NOTE)
        data = self.card()
        self.assertEqual(data["card"]["schema_version"], 6)
        notes = [{k: n[k] for k in ("date", "session_id", "exercise_id", "text")} for n in data["card"]["notes"]]
        self.assertEqual(notes, [
            {"date": "2026-10-12", "session_id": "session-a", "exercise_id": None, "text": WORKOUT_NOTE},
            {"date": "2026-10-12", "session_id": "session-a", "exercise_id": "db_bench_press", "text": BENCH_NOTE},
        ])
        self.assertEqual(data["card"]["notes"][1]["name"], "Bench Press (Dumbbell)")
        text = data["text"]
        self.assertEqual(text.count(WORKOUT_NOTE), 1)
        self.assertEqual(text.count(BENCH_NOTE), 1)
        self.assertIn(f'- Mon 12 Oct Session A, Bench Press (Dumbbell): "{BENCH_NOTE}"', text)

        record = self.coach("checkin", "skeleton", "--date", "2026-10-18")["data"]["text"]
        self.assertEqual(record.count(WORKOUT_NOTE), 1)
        self.assertEqual(record.count(BENCH_NOTE), 1)
        self.assertIn(f'- Mon 12 Oct Session A: "{WORKOUT_NOTE}"', record)
        path = self.root / "check-ins" / "2026-10-18.md"
        before = path.read_text(encoding="utf-8")
        refreshed = self.coach("checkin", "skeleton", "--date", "2026-10-18", "--refresh")["data"]
        self.assertFalse(refreshed["written"])
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertEqual(self.card()["text"], text)

    def test_a_logged_concern_is_put_for_confirmation_not_asked_blind(self):
        self.log(notes=WORKOUT_NOTE, bench_notes=BENCH_NOTE)
        niggles = self.field(self.card()["card"], "niggles")
        self.assertEqual(niggles["prefill"], "You logged notes on Mon 12 Oct Session A (above).")
        self.assertIn("Is anything in those notes a niggle to track, or was it nothing?", niggles["ask"])
        self.assertNotIn(BENCH_NOTE, niggles["prefill"])

    def test_notes_outside_the_window_are_not_new(self):
        log = self.root / "data/log/workouts.jsonl"
        lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        lines[-1]["notes"] = "old knee grumble"
        log.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        self.coach("history", "sync")
        self.log()
        data = self.card()
        self.assertEqual(data["card"]["notes"], [])
        self.assertNotIn("old knee grumble", data["text"])
        self.assertNotIn("Notes logged", data["text"])
        self.assertIn("Mon 12 Oct Session A: Back Squat (Barbell)", data["text"])
        niggles = self.field(data["card"], "niggles")
        self.assertEqual((niggles["prefill"], niggles["ask"]), (None, "Anything new?"))

    def test_preparing_writes_nothing_and_a_confirmed_concern_uses_the_niggle_log(self):
        self.log(notes=WORKOUT_NOTE, bench_notes=BENCH_NOTE)
        before = self.data_bytes()
        self.card()
        self.assertEqual(self.data_bytes(), before)
        self.assertFalse((self.root / "data" / "niggles.json").exists())
        self.coach("niggles", "add", "--area", "right shoulder", "--status", "watching", "--pattern",
                   "horizontal_push", "--note", BENCH_NOTE)
        niggles = self.field(self.card()["card"], "niggles")
        self.assertEqual(niggles["prefill"],
                         "Open: right shoulder (watching). You logged notes on Mon 12 Oct Session A (above).")
        self.assertIn("For each open one: quiet, or still there?", niggles["ask"])


class CardDocsTest(unittest.TestCase):
    def test_the_sunday_message_names_the_applicable_fields(self):
        from tests.support.skills import step_text
        step = " ".join(step_text("check-in", "sunday-message.md").split())
        self.assertIn("one morning scale weight", step)
        self.assertIn("no run recorded or planned in the window", step)
        self.assertIn("the card never records a niggle from a note alone", step)
        self.assertIsNone(re.search(r"No MacroFactor:", step))


if __name__ == "__main__":
    unittest.main()
