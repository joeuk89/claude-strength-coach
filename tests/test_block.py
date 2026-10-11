"""Blocks and light weeks: week classes, the hard-week count, fatigue triggers, decisions and transforms (contract C42, C43)."""

import copy
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from coach import block, flags, jsonio, program
from coach.validate import validate
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli
from tests.support.history import read_json, write_json

BLOCK = INSTANCES / "block"
NOW = "2026-10-11T18:00:00Z"
NEXT_SUNDAY = "2026-10-18T18:00:00Z"
CEILING_LINE = ("Block 1 · 6 of 6 hard weeks · triggers 0 of 4 · light week: proposed for wk of 12 Oct "
                "(deload, ceiling)")
WORKING = ("normal", "dropset", "failure")
CODES = {"light_week_due": ("warn",), "light_week_skipped": ("info",), "fatigue_watch": ("info",),
         "deep_review_due": ("info",)}


def codes(data):
    return [f["code"] for f in data["flags"]]


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


class BlockCase(unittest.TestCase):
    """A temp copy of a fixture instance (block/ by default) and the coach CLI against it."""

    base = BLOCK

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(self.base, self.root)

    def coach(self, *argv, expect=0, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def data(self, *argv, now=NOW):
        return self.coach(*argv, now=now)["data"]

    def close(self, week="2026-W41", *extra, now=NOW):
        return self.data("block", "close", "--week", week, *extra, now=now)

    def edit(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)

    def workouts(self):
        return [w for path in sorted((self.root / "data" / "history").glob("2026-*.json"))
                for w in read_json(path)["workouts"]]

    def drop_workout(self, day):
        for path in (self.root / "data" / "history").glob("2026-*.json"):
            doc = read_json(path)
            doc["workouts"] = [w for w in doc["workouts"] if w["date"] != day]
            write_json(path, doc)

    def edit_workout(self, day, change):
        for path in (self.root / "data" / "history").glob("2026-*.json"):
            doc = read_json(path)
            for workout in doc["workouts"]:
                if workout["date"] == day:
                    change(workout)
            write_json(path, doc)

    def set_rpe(self, day, exercise_id, rpe):
        def change(workout):
            for exercise in workout["exercises"]:
                if exercise["exercise_id"] == exercise_id:
                    for set_ in exercise["sets"]:
                        set_["rpe"] = rpe
        self.edit_workout(day, change)

    def train_week(self, monday):
        """Copy the W41 workouts and coach-led session a week on, into the week starting `monday`."""
        shift = (date.fromisoformat(monday) - date(2026, 10, 5)).days
        moved = []
        for workout in self.workouts():
            if "2026-10-05" <= workout["date"] <= "2026-10-11":
                new = copy.deepcopy(workout)
                day = (date.fromisoformat(workout["date"]) + timedelta(days=shift)).isoformat()
                new.update(workout_id=workout["workout_id"][:-3] + f"{int(workout['workout_id'][-3:]) + 50:03d}",
                           date=day, start_time=f"{day}T18:00:00Z", end_time=f"{day}T19:00:00Z")
                moved.append(new)
        path = self.root / "data" / "history" / "2026-10.json"
        doc = read_json(path)
        doc["workouts"] += moved
        write_json(path, doc)
        tuesday = (date.fromisoformat(monday) + timedelta(days=1)).isoformat()

        def add(doc):
            doc["annotations"].append({"id": f"a-{len(doc['annotations']) + 1:04d}", "kind": "external",
                                       "created_at": NEXT_SUNDAY, "source": "test", "reason": None,
                                       "date": tuesday, "external_id": "pt-tue", "done": True, "note": "chest"})
        self.edit("data/history/annotations.json", add)

    def init(self, hard_weeks, through="2026-W40", started=None):
        argv = ["block", "init", "--hard-weeks", str(hard_weeks), "--through", through]
        if started:
            argv += ["--started", started]
        return self.data(*argv)

    def ledger(self):
        return read_json(self.root / "data" / "blocks.json")

    def state_block(self):
        return read_json(self.root / "data" / "state.json")["block"]


class CeilingTest(BlockCase):
    def test_w41_closes_six_hard_weeks_and_proposes_a_deload_at_the_ceiling(self):
        data = self.close("2026-W41", "--readiness", "ok", "--sleep", "ok")
        self.assertEqual([(w["week"], w["class"], w["count_after"]) for w in data["weeks"]],
                         [("2026-08-31", "hard", 1), ("2026-09-07", "hard", 2), ("2026-09-14", "hard", 3),
                          ("2026-09-21", "hard", 4), ("2026-09-28", "hard", 5), ("2026-10-05", "hard", 6)])
        self.assertEqual(data["weeks"][-1]["outcome"], "due")
        self.assertEqual(data["block"]["hard_weeks_completed"], 6)
        self.assertEqual(data["block"]["light_week"], {"status": "proposed", "type": "deload", "reason": "ceiling",
                                                       "week": "2026-10-12", "decision_id": None})
        [due] = [f for f in data["flags"] if f["code"] == "light_week_due"]
        self.assertIn("deload", due["message"])
        self.assertIn("ceiling", due["message"])
        self.assertEqual(data["status_line"], CEILING_LINE)
        self.assertEqual(self.state_block(), data["block"])
        self.assertEqual(self.ledger()["blocks"][0]["weeks"], data["weeks"])

    def test_each_week_records_its_counts_and_signals(self):
        week = self.close("2026-W41", "--readiness", "ok", "--sleep", "ok")["weeks"][-1]
        self.assertEqual((week["planned"], week["trained"], week["as_prescribed"]), (3, 3, 3))
        self.assertEqual(week["signals"], {"readiness": "ok", "sleep": "ok", "sleep_source": "athlete",
                                           "rpe_drift": False, "niggle": False})
        self.assertEqual(week["closed_at"], NOW)
        self.assertFalse(week["deep"])

    def test_classify_reads_one_week(self):
        before = snapshot(self.root)
        self.assertEqual(block.classify(self.root, "2026-10-05", today=date(2026, 10, 11)), "hard")
        self.assertEqual(snapshot(self.root), before)

    def test_the_ceiling_comes_from_the_program(self):
        self.edit("data/program.json", lambda doc: doc["blocks"].update(hard_weeks_ceiling=4))
        self.data("program", "render")
        data = self.close()
        self.assertEqual(data["block"]["light_week"]["status"], "proposed")
        self.assertTrue(data["status_line"].startswith("Block 1 · 6 of 4 hard weeks"))


class WeekClassTest(BlockCase):
    def test_a_missed_session_makes_the_week_partial(self):
        self.drop_workout("2026-09-24")
        data = self.close()
        self.assertEqual(data["weeks"][3]["class"], "partial")
        self.assertEqual((data["weeks"][3]["planned"], data["weeks"][3]["trained"]), (3, 2))
        self.assertEqual(data["block"]["hard_weeks_completed"], 5)
        self.assertEqual(data["block"]["light_week"]["status"], "not_due")

    def test_under_half_trained_is_low_and_ends_the_block(self):
        self.drop_workout("2026-09-21")
        self.drop_workout("2026-09-24")
        data = self.close()
        self.assertEqual(data["weeks"][3]["class"], "low")
        self.assertEqual(data["ended"], ["b-0001"])
        first, second = self.ledger()["blocks"]
        self.assertEqual((first["ended"], first["end_reason"]), ("2026-09-27", "low"))
        self.assertEqual((second["id"], second["started"], second["ended"]), ("b-0002", "2026-09-28", None))
        self.assertEqual([w["count_after"] for w in second["weeks"]], [1, 2])
        self.assertEqual(data["block"]["id"], "b-0002")
        self.assertEqual(data["block"]["hard_weeks_completed"], 2)
        self.assertTrue(data["status_line"].startswith("Block 2 · 2 of 6 hard weeks"))

    def test_half_the_working_sets_is_not_trained_as_prescribed(self):
        def halve(workout):
            for exercise in workout["exercises"]:
                exercise["sets"] = exercise["sets"][:1] if exercise["exercise_id"] == "bb_back_squat" else \
                    exercise["sets"][:2]
        self.edit_workout("2026-10-05", halve)
        week = self.close()["weeks"][-1]
        self.assertEqual((week["trained"], week["as_prescribed"], week["class"]), (3, 2, "partial"))
        self.assertEqual(week["count_after"], 5)

    def test_a_mean_rpe_two_under_target_is_not_trained_as_prescribed(self):
        self.set_rpe("2026-10-05", "bb_back_squat", 5)
        self.set_rpe("2026-10-05", "db_bench_press", 6)
        week = self.close()["weeks"][-1]
        self.assertEqual((week["as_prescribed"], week["class"]), (2, "partial"))

    def test_the_trained_as_prescribed_lines(self):
        line = {"exercise_id": "x", "sets": [{"type": "normal", "reps": 5, "rpe": 8}] * 3}

        def workout(*rpes):
            return {"exercises": [{"exercise_id": "x", "sets": [{"type": "normal", "rpe": r} for r in rpes]}]}
        self.assertTrue(block.trained_as_prescribed([line], workout(8, 8)))
        self.assertFalse(block.trained_as_prescribed([line], workout(8)))
        self.assertTrue(block.trained_as_prescribed([line], workout(6.5, 6.5, 6.5)))
        self.assertFalse(block.trained_as_prescribed([line], workout(6, 6.5, 6.5)))
        self.assertTrue(block.trained_as_prescribed([line], workout(None, None, None)))
        self.assertTrue(block.trained_as_prescribed([line], workout(None, None, 7)))
        warmup = {"type": "warmup", "rpe": 2}
        logged = workout(8, 8)
        logged["exercises"][0]["sets"].insert(0, warmup)
        self.assertTrue(block.trained_as_prescribed([line], logged))

    def test_an_unconfirmed_coach_led_session_is_left_out(self):
        self.edit("data/history/annotations.json",
                  lambda doc: doc.update(annotations=[a for a in doc["annotations"] if a["date"] != "2026-10-06"]))
        week = self.close()["weeks"][-1]
        self.assertEqual((week["planned"], week["trained"], week["class"]), (2, 2, "hard"))

    def test_a_one_off_week_neither_counts_nor_resets(self):
        with mock.patch("coach.structure.week", side_effect=self.kind_for("2026-09-14", "one_off")):
            data = self.close()
        self.assertEqual(data["weeks"][2]["class"], "one_off")
        self.assertEqual(data["block"]["hard_weeks_completed"], 5)
        self.assertEqual(data["ended"], [])

    def kind_for(self, week, kind):
        from coach import structure
        real = structure.week

        def week_report(root, span, **kwargs):
            report = real(root, span, **kwargs)
            if report["week"] == week:
                report["kind"] = kind
            return report
        return week_report


class TriggerTest(BlockCase):
    def test_two_triggers_from_readiness_and_sleep_propose_a_light_week(self):
        self.init(3)
        data = self.close("2026-W41", "--readiness", "poor", "--sleep", "poor")
        self.assertEqual(data["block"]["hard_weeks_completed"], 4)
        self.assertEqual(data["weeks"][-1]["triggers"], ["readiness", "sleep"])
        light = data["block"]["light_week"]
        self.assertEqual((light["status"], light["reason"], light["type"]), ("proposed", "triggers", "light"))
        self.assertIn("light_week_due", codes(data))
        self.assertIn("triggers 2 of 4 (readiness, sleep)", data["status_line"])

    def test_rpe_drift_on_squat_in_the_last_two_session_a_workouts_makes_it_a_deload(self):
        self.init(3)
        for day in ("2026-09-28", "2026-10-05"):
            self.set_rpe(day, "bb_back_squat", 8.5)
        data = self.close("2026-W41", "--readiness", "poor", "--sleep", "poor")
        self.assertEqual(data["weeks"][-1]["triggers"], ["readiness", "rpe_drift", "sleep"])
        self.assertTrue(data["weeks"][-1]["signals"]["rpe_drift"])
        self.assertEqual(data["block"]["light_week"]["type"], "deload")

    def test_drift_in_only_the_last_workout_is_not_two_running(self):
        self.set_rpe("2026-10-05", "bb_back_squat", 8.5)
        week = self.close("2026-W41")["weeks"][-1]
        self.assertFalse(week["signals"]["rpe_drift"])

    def test_two_triggers_below_three_hard_weeks_skip_the_light_week(self):
        self.init(1)
        data = self.close("2026-W41", "--readiness", "poor", "--sleep", "poor")
        self.assertEqual(data["weeks"][-1]["outcome"], "skipped")
        self.assertEqual(data["block"]["light_week"]["status"], "skipped")
        self.assertTrue(data["status_line"].endswith("light week: skipped (2 hard weeks)"))
        self.assertIn("light_week_skipped", codes(data))
        self.assertNotIn("light_week_due", codes(data))

    def test_one_trigger_is_a_watch(self):
        self.init(1)
        data = self.close("2026-W41", "--readiness", "poor", "--sleep", "ok")
        self.assertEqual(data["weeks"][-1]["outcome"], "watch")
        self.assertEqual([c for c in codes(data) if c != "deep_review_due"], ["fatigue_watch"])
        self.assertTrue(data["status_line"].endswith("triggers 1 of 4 (readiness) · light week: watch"))

    def test_an_aggravated_niggle_counts_and_an_easing_one_does_not(self):
        self.init(3)
        self.data("niggles", "add", "--area", "left knee", "--status", "aggravated", "--pattern", "squat")
        data = self.close("2026-W41", "--readiness", "poor")
        self.assertTrue(data["weeks"][-1]["signals"]["niggle"])
        self.assertEqual(data["weeks"][-1]["triggers"], ["readiness", "niggle"])
        self.assertEqual(data["block"]["light_week"]["type"], "deload")
        self.data("niggles", "update", "n-0001", "--status", "easing")
        data = self.close("2026-W41", "--readiness", "poor")
        self.assertFalse(data["weeks"][-1]["signals"]["niggle"])
        self.assertEqual(data["weeks"][-1]["outcome"], "watch")

    def test_sleep_debt_reads_the_cardio_module_when_the_athlete_says_nothing(self):
        with mock.patch("coach.block.sleep_debt", return_value=True) as reader:
            week = self.close("2026-W41")["weeks"][-1]
        self.assertEqual((week["signals"]["sleep"], week["signals"]["sleep_source"]), ("poor", "sleep_debt"))
        self.assertIn("sleep", week["triggers"])
        span = reader.call_args_list[-1][0][1]
        self.assertEqual((span.start, span.end), (date(2026, 10, 5), date(2026, 10, 11)))
        week = self.close("2026-W41")["weeks"][-1]
        self.assertEqual((week["signals"]["sleep"], week["signals"]["sleep_source"]), ("unknown", "none"))

    def test_an_ill_week_under_half_proposes_a_return_week(self):
        self.drop_workout("2026-10-05")
        self.drop_workout("2026-10-08")
        self.data("history", "annotate", "--kind", "miss", "--date", "2026-10-05", "--session", "session-a",
                  "--tag", "ill")
        data = self.close()
        self.assertEqual(data["weeks"][-1]["class"], "low")
        self.assertEqual(data["block"]["light_week"]["type"], "return")
        self.assertEqual(data["block"]["light_week"]["reason"], "illness")
        self.assertTrue(data["status_line"].endswith("proposed for wk of 12 Oct (return, illness)"))


class DecideTest(BlockCase):
    def test_a_declined_ceiling_week_is_proposed_again_at_the_next_close(self):
        self.close()
        data = self.data("block", "decide", "--outcome", "declined", "--reason", "competition week")
        decision = data["decision"]
        self.assertEqual((decision["kind"], decision["outcome"], decision["reason"]),
                         ("light_week", "declined", "competition week"))
        self.assertEqual(decision["details"], {"type": "deload", "week": "2026-10-12", "reason": "ceiling",
                                               "triggers": [], "hard_weeks": 6})
        self.assertEqual(data["block"]["light_week"]["status"], "declined")
        self.assertTrue(data["status_line"].endswith(
            "light week: declined (competition week), proposed again next check-in"))
        self.assertEqual(read_json(self.root / "data" / "decisions.json")["decisions"][-1]["id"], decision["id"])
        self.train_week("2026-10-12")
        again = self.close("2026-W42", now=NEXT_SUNDAY)
        self.assertEqual(again["block"]["hard_weeks_completed"], 7)
        self.assertEqual(again["block"]["light_week"]["status"], "proposed")
        self.assertEqual(again["block"]["light_week"]["week"], "2026-10-19")

    def test_adopted_then_the_light_week_closes_and_the_block_ends(self):
        self.close()
        data = self.data("block", "decide", "--outcome", "adopted", "--type", "deload", "--week", "2026-W42")
        self.assertEqual(data["block"]["light_week"]["status"], "agreed")
        self.assertEqual(data["command"], "python3 -m coach propose week --week 2026-10-12 --kind deload")
        self.assertTrue(data["status_line"].endswith("light week: agreed: deload, wk of 12 Oct"))
        proposal = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload")
        self.data("propose", "finalize", "--proposal", proposal["overlay"]["id"])
        closed = self.close("2026-W42", now=NEXT_SUNDAY)
        self.assertEqual(closed["weeks"][-1]["class"], "light")
        self.assertEqual(closed["ended"], ["b-0001"])
        self.assertEqual(closed["block"]["id"], "b-0002")
        self.assertEqual(closed["block"]["hard_weeks_completed"], 0)
        self.assertEqual(closed["block"]["light_week"]["status"], "not_due")
        self.assertEqual(self.ledger()["blocks"][0]["end_reason"], "light")
        self.assertFalse(closed["deep_review"]["due"], closed["deep_review"])

    def test_a_different_type_needs_a_reason(self):
        self.close()
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", expect=1)
        data = self.data("block", "decide", "--outcome", "adopted", "--type", "light", "--reason", "travel kit")
        self.assertEqual(data["block"]["light_week"]["type"], "light")
        self.assertEqual(data["command"],
                         "python3 -m coach propose week --week 2026-10-12 --kind deload --transform light")

    def test_the_coach_can_adopt_one_with_a_reason_when_none_was_proposed(self):
        self.init(2)
        self.close()
        self.coach("block", "decide", "--outcome", "adopted", "--type", "light", expect=1)
        data = self.data("block", "decide", "--outcome", "adopted", "--type", "light", "--reason", "work trip")
        self.assertEqual(data["block"]["light_week"], {"status": "agreed", "type": "light", "reason": "coach",
                                                       "week": "2026-10-12", "decision_id": data["decision"]["id"]})
        self.assertEqual(data["decision"]["details"]["reason"], "coach")

    def test_nothing_to_decline_without_a_proposal(self):
        self.coach("block", "decide", "--outcome", "declined", "--reason", "x", expect=1)

    def test_an_agreed_week_survives_a_reclose(self):
        self.close()
        self.data("block", "decide", "--outcome", "adopted")
        data = self.close()
        self.assertEqual(data["block"]["light_week"]["status"], "agreed")


class TransformTest(BlockCase):
    def line(self, doc, exercise_id):
        return next(line for session in doc["sessions"] for line in session["exercises"]
                    if line["exercise_id"] == exercise_id)

    def working(self, line):
        return [s for s in line["sets"] if s["type"] in WORKING]

    def logged_top(self, exercise_id):
        newest = max((w for w in self.workouts() if any(e["exercise_id"] == exercise_id for e in w["exercises"])),
                     key=lambda w: w["date"])
        loads = [s["load"] for e in newest["exercises"] if e["exercise_id"] == exercise_id for s in e["sets"]]
        return max((load["per_hand"] or load["hevy_total"]) for load in loads)

    def coaching(self, load):
        return load["per_hand"] if load["mode"] in ("per_hand_x2", "single_implement") else load["hevy_total"]

    def test_light_keeps_two_thirds_of_the_sets_at_held_loads_and_rpe_8(self):
        weekly = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        light = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload", "--transform", "light",
                          "--dry-run")["overlay"]
        for exercise_id in ("bb_back_squat", "db_bench_press", "db_single_arm_row"):
            with self.subTest(exercise=exercise_id):
                before, after = self.working(self.line(weekly, exercise_id)), self.working(self.line(light, exercise_id))
                self.assertEqual(len(after), max(1, round(len(before) * 0.67)))
                self.assertTrue(all(self.coaching(s["load"]) == self.logged_top(exercise_id) for s in after))
                self.assertTrue(all(s["rpe"] is not None and s["rpe"] <= 8 for s in after))

    def test_return_drops_one_set_at_the_derived_from_load(self):
        weekly = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        back = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload", "--transform", "return",
                         "--dry-run")["overlay"]
        for exercise_id in ("bb_back_squat", "db_bench_press"):
            with self.subTest(exercise=exercise_id):
                before, after = self.working(self.line(weekly, exercise_id)), self.working(self.line(back, exercise_id))
                self.assertEqual(len(after), len(before) - 1)
                self.assertTrue(all(self.coaching(s["load"]) == self.logged_top(exercise_id) for s in after))
                self.assertTrue(all(s["rpe"] is not None and s["rpe"] <= 8 for s in after))

    def test_both_are_listed_as_deload_rules(self):
        names = [p["name"] for p in self.data("plugins", "list")["plugins"] if p["kind"] == "transform"]
        self.assertEqual(names, ["light", "return", "scheme", "standard"])
        self.edit("data/program.json", lambda doc: doc["blocks"].update(deload_rule={"name": "light", "params": {}}))
        self.assertTrue(self.data("program", "validate")["valid"])


class LayoffTest(BlockCase):
    base = INSTANCES / "layoff"

    def test_return_leaves_lines_the_core_already_decayed(self):
        weekly = self.data("propose", "week", "--week", "2026-W42", "--dry-run")["overlay"]
        back = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload", "--transform", "return",
                         "--dry-run")["overlay"]
        pairs = [(a, b) for sa, sb in zip(weekly["sessions"], back["sessions"])
                 for a, b in zip(sa["exercises"], sb["exercises"])]
        decayed = [(a, b) for a, b in pairs if a["provenance"]["decay"]]
        self.assertTrue(decayed)
        for before, after in decayed:
            with self.subTest(exercise=before["exercise_id"]):
                self.assertEqual(after["sets"], before["sets"])
                self.assertEqual(after["provenance"]["decay"]["band"], "22-42")

    def test_a_week_with_a_22_42_decay_after_a_layoff_is_a_return_week(self):
        proposal = self.data("propose", "week", "--week", "2026-W42")
        self.data("propose", "finalize", "--proposal", proposal["overlay"]["id"])
        data = self.close("2026-W42", now=NEXT_SUNDAY)
        self.assertEqual([(w["week"], w["class"]) for w in data["weeks"]], [("2026-10-12", "return")])
        self.assertEqual(data["ended"], ["b-0001"])
        self.assertEqual(self.ledger()["blocks"][0]["end_reason"], "return")
        self.assertEqual(data["block"]["hard_weeks_completed"], 0)

    def test_a_decayed_line_without_a_layoff_is_not_a_return_week(self):
        proposal = self.data("propose", "week", "--week", "2026-W42")
        self.data("propose", "finalize", "--proposal", proposal["overlay"]["id"])
        with mock.patch("coach.history.last_lifting_date", return_value=date(2026, 10, 9)):
            self.assertNotEqual(block.classify(self.root, "2026-10-12", today=date(2026, 10, 18)), "return")


class DeepReviewTest(BlockCase):
    def test_due_at_the_ceiling_close_and_not_after_the_light_week(self):
        self.close()
        status = self.data("block", "status")
        self.assertEqual(status["deep_review"]["due"], True)
        self.assertEqual(status["deep_review"]["reasons"], ["light_week_proposed"])
        self.assertIn("deep_review_due", codes(status))
        self.assertEqual(status["status_line"], CEILING_LINE)
        self.data("block", "decide", "--outcome", "adopted")
        self.close("2026-W42", now=NEXT_SUNDAY)
        status = self.data("block", "status", now=NEXT_SUNDAY)
        self.assertFalse(status["deep_review"]["due"], status["deep_review"])
        self.assertNotIn("deep_review_due", codes(status))

    def test_the_adherence_trigger_makes_any_close_deep(self):
        self.init(1)
        flag = flags.make("restructure_required", message="58 %")
        with mock.patch("coach.structure.adherence", return_value={"flags": [flag]}):
            data = self.close()
            status = self.data("block", "status")
        self.assertEqual(data["deep_review"]["reasons"], ["restructure_required"])
        self.assertTrue(status["deep_review"]["due"])

    def test_six_weeks_since_the_last_deep_close(self):
        self.edit("data/state.json", lambda doc: doc["block"].update(last_deep_review="2026-08-30"))
        self.init(1)
        self.assertIn("six_weeks", self.close()["deep_review"]["reasons"])

    def test_the_first_close_with_no_deep_review_on_record(self):
        self.edit("data/state.json", lambda doc: doc["block"].update(last_deep_review=None))
        self.init(1)
        self.assertEqual(self.close()["deep_review"]["reasons"], ["first_close"])

    def test_a_deep_close_records_the_review(self):
        self.edit("data/state.json", lambda doc: doc["block"].update(last_deep_review=None))
        self.init(1)
        data = self.close("2026-W41", "--deep")
        self.assertTrue(data["weeks"][-1]["deep"])
        self.assertEqual(data["block"]["last_deep_review"], "2026-10-11")
        self.assertFalse(self.data("block", "status")["deep_review"]["due"])


class RecloseTest(BlockCase):
    def test_reclosing_the_newest_week_replaces_its_entry(self):
        self.close()
        data = self.close("2026-W41", "--readiness", "poor")
        self.assertTrue(data["replaced"])
        self.assertEqual([w["week"] for w in data["weeks"]], ["2026-10-05"])
        weeks = self.ledger()["blocks"][0]["weeks"]
        self.assertEqual(len(weeks), 6)
        self.assertEqual(weeks[-1]["signals"]["readiness"], "poor")
        self.assertEqual(weeks[-1]["count_after"], 6)

    def test_reclosing_an_older_week_exits_1(self):
        self.close()
        self.coach("block", "close", "--week", "2026-W40", expect=1)

    def test_reclosing_a_week_that_ended_a_block_undoes_the_end(self):
        history = self.root / "data" / "history" / "2026-10.json"
        logged = history.read_bytes()
        self.drop_workout("2026-10-05")
        self.drop_workout("2026-10-08")
        self.close()
        self.assertEqual(len(self.ledger()["blocks"]), 2)
        history.write_bytes(logged)
        data = self.close()
        self.assertEqual([b["id"] for b in self.ledger()["blocks"]], ["b-0001"])
        self.assertEqual(data["block"]["hard_weeks_completed"], 6)

    def test_a_week_that_has_not_started_exits_1(self):
        self.coach("block", "close", "--week", "2026-W43", expect=1)


class InitTest(BlockCase):
    def test_init_seeds_the_count_and_the_next_close_starts_after_it(self):
        data = self.init(4, through="2026-W40")
        self.assertEqual(data["block"]["hard_weeks_completed"], 4)
        self.assertEqual(data["block"]["started"], "2026-09-07")
        self.assertEqual(data["next_close"], "2026-W41")
        closed = self.close()
        self.assertEqual([w["week"] for w in closed["weeks"]], ["2026-10-05"])
        self.assertEqual(closed["block"]["hard_weeks_completed"], 5)

    def test_init_refuses_once_a_week_is_closed(self):
        self.close()
        self.coach("block", "init", "--hard-weeks", "2", expect=1)

    def test_a_migrated_ledger_closes_only_the_target_week(self):
        def seeded(doc):
            doc["blocks"][0].update(seed_hard_weeks=3, seed_reason="carried over from data/state.json by the "
                                                                   "migration")
        self.edit("data/blocks.json", seeded)
        self.edit("data/state.json", lambda doc: doc["block"].update(hard_weeks_completed=3))
        data = self.close()
        self.assertEqual([w["week"] for w in data["weeks"]], ["2026-10-05"])
        self.assertEqual(data["block"]["hard_weeks_completed"], 4)

    def test_without_a_ledger_the_first_close_starts_one_from_the_state(self):
        (self.root / "data" / "blocks.json").unlink()
        self.edit("data/state.json", lambda doc: doc["block"].update(hard_weeks_completed=2))
        data = self.close()
        self.assertEqual(data["block"]["hard_weeks_completed"], 3)
        self.assertEqual(self.ledger()["blocks"][0]["seed_hard_weeks"], 2)


class DryRunTest(BlockCase):
    def test_every_writing_command_writes_nothing(self):
        cases = [("block", "close", "--week", "2026-W41"), ("block", "init", "--hard-weeks", "3")]
        for argv in cases:
            with self.subTest(argv=argv):
                before = snapshot(self.root)
                self.data(*argv, "--dry-run")
                self.assertEqual(snapshot(self.root), before)
        self.close()
        before = snapshot(self.root)
        for argv in (("block", "decide", "--outcome", "adopted"),
                     ("block", "decide", "--outcome", "declined", "--reason", "x")):
            with self.subTest(argv=argv):
                data = self.data(*argv, "--dry-run")
                self.assertFalse(data["written"])
                self.assertEqual(snapshot(self.root), before)


class MigrationTest(BlockCase):
    base = VALID

    def test_a_due_deload_becomes_a_proposed_light_week_and_seeds_the_ledger(self):
        def older(doc):
            doc["schema_version"] = 3
            doc["block"] = {"started": "2026-09-07", "hard_weeks_completed": 5,
                            "deload": {"status": "due", "since": "2026-10-04"}}
        self.edit("data/state.json", older)
        self.assertFalse((self.root / "data" / "blocks.json").exists())
        data = self.data("migrate", "run")
        self.assertEqual(data["created"], ["data/blocks.json"])
        migrated = self.state_block()
        self.assertEqual(migrated["light_week"]["status"], "proposed")
        self.assertEqual(migrated["hard_weeks_completed"], 5)
        [seeded] = self.ledger()["blocks"]
        self.assertEqual((seeded["id"], seeded["started"], seeded["seed_hard_weeks"], seeded["weeks"]),
                         ("b-0001", "2026-09-07", 5, []))
        self.data("state", "show")
        code, envelope, _ = run_cli(["--root", str(self.root), "check", "--only", "block_state,state_schema"],
                                    env={"COACH_NOW": NOW})
        self.assertEqual(code, 0, envelope)

    def test_each_old_status_maps(self):
        expected = {"not_due": "not_due", "done": "not_due", "due": "proposed", "in_progress": "agreed",
                    "skipped": "skipped"}
        for old, new in expected.items():
            with self.subTest(old=old):
                def older(doc, old=old):
                    doc["schema_version"] = 3
                    doc["block"] = {"started": "2026-09-07", "hard_weeks_completed": 2,
                                    "deload": {"status": old, "since": "2026-10-12"}}
                self.edit("data/state.json", older)
                (self.root / "data" / "blocks.json").unlink(missing_ok=True)
                self.data("migrate", "run")
                self.assertEqual(self.state_block()["light_week"]["status"], new)

    def test_an_existing_ledger_is_kept(self):
        write_json(self.root / "data" / "blocks.json", read_json(BLOCK / "data" / "blocks.json"))
        self.edit("data/state.json", lambda doc: doc.update(schema_version=3, block={
            "started": "2026-08-31", "hard_weeks_completed": 0, "deload": {"status": "not_due", "since": None}}))
        before = (self.root / "data" / "blocks.json").read_bytes()
        self.assertEqual(self.data("migrate", "run")["created"], [])
        self.assertEqual((self.root / "data" / "blocks.json").read_bytes(), before)


class CheckTest(BlockCase):
    def check(self, only, expect):
        code, envelope, stderr = run_cli(["--root", str(self.root), "check", "--only", only], env={"COACH_NOW": NOW})
        self.assertEqual(code, expect, (envelope, stderr))
        return [r for r in envelope["data"]["results"] if r["id"] == only]

    def test_the_ceiling_must_be_4_to_8(self):
        self.assertEqual([r["status"] for r in self.check("block_config", 0)], ["pass"])
        for ceiling in (3, 9):
            with self.subTest(ceiling=ceiling):
                self.edit("data/program.json", lambda doc: doc["blocks"].update(hard_weeks_ceiling=ceiling))
                [row] = self.check("block_config", 1)
                self.assertEqual(row["status"], "fail")
                self.assertIn("from 4 to 8", row["message"])

    def test_state_must_agree_with_the_ledger(self):
        self.close()
        self.assertEqual([r["status"] for r in self.check("block_state", 0)], ["pass"])
        self.edit("data/state.json", lambda doc: doc["block"].update(hard_weeks_completed=4))
        [row] = self.check("block_state", 1)
        self.assertIn("hard_weeks_completed", row["message"])

    def test_an_agreed_light_week_without_its_overlay_warns(self):
        self.close()
        self.data("block", "decide", "--outcome", "adopted")
        [row] = self.check("light_week_overlay", 0)
        self.assertEqual(row["status"], "warn")
        self.assertIn("propose week --week 2026-10-12 --kind deload", row["message"])
        proposal = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload")
        self.data("propose", "finalize", "--proposal", proposal["overlay"]["id"])
        self.assertEqual([r["status"] for r in self.check("light_week_overlay", 0)], ["pass"])

    def test_a_deload_overlay_without_a_decision_warns(self):
        proposal = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload")
        self.data("propose", "finalize", "--proposal", proposal["overlay"]["id"])
        [row] = self.check("light_week_overlay", 0)
        self.assertEqual(row["status"], "warn")
        self.assertIn("block decide", row["message"])

    def test_the_fixture_passes_every_check_after_a_close(self):
        self.close()
        code, envelope, _ = run_cli(["--root", str(self.root), "check", "--only",
                                     "block_state,block_config,routine_render_fresh,state_schema,decisions_schema"],
                                    env={"COACH_NOW": NOW})
        self.assertEqual(code, 0, envelope)


class RenderTest(BlockCase):
    def test_program_page_carries_the_status_line(self):
        page = (self.root / "routine" / "program.md").read_text(encoding="utf-8")
        self.assertIn(f"Status: {block.status_line(self.root)}", page)
        self.close()
        page = (self.root / "routine" / "program.md").read_text(encoding="utf-8")
        self.assertIn(f"Status: {CEILING_LINE}", page)
        self.assertEqual(program.render_all(self.root)["routine/program.md"], page)

    def test_no_skill_mentions_a_pencil(self):
        for path in sorted((REPO_ROOT / ".claude" / "skills").rglob("*.md")):
            with self.subTest(skill=path.parent.name):
                self.assertNotIn("pencil", path.read_text(encoding="utf-8").lower())

    def test_the_check_in_skill_names_the_block_commands(self):
        text = " ".join((REPO_ROOT / ".claude" / "skills" / "check-in" / "SKILL.md").read_text(encoding="utf-8").split())
        for command in ("block close", "block decide", "block status"):
            self.assertIn(f"python3 -m coach {command}", text)


class RegistryTest(unittest.TestCase):
    def test_the_four_codes_are_registered(self):
        registry = flags.registry()
        for code, severities in CODES.items():
            with self.subTest(code=code):
                self.assertEqual(registry[code].owner, "R-31")
                self.assertEqual(registry[code].severities, severities)
                self.assertFalse(registry[code].structural)

    def test_the_ledger_schema_rejects_a_bad_class(self):
        doc = read_json(BLOCK / "data" / "blocks.json")
        doc["blocks"][0]["weeks"].append({"week": "2026-08-31", "class": "medium"})
        self.assertIn("$.blocks[0].weeks[0].class", [e.path for e in validate(doc, jsonio.load_schema("blocks"))])

    def test_problems_catch_an_open_block_before_the_newest(self):
        doc = read_json(BLOCK / "data" / "blocks.json")
        doc["blocks"].append(dict(doc["blocks"][0], id="b-0002"))
        self.assertIn("$.blocks[0].ended", [e.path for e in block.problems(doc)])

    def test_outcome_rules(self):
        self.assertEqual(block.outcome_for("hard", 6, [], 6), ("due", "deload", "ceiling"))
        self.assertEqual(block.outcome_for("hard", 3, ["readiness", "sleep"], 6), ("due", "light", "triggers"))
        self.assertEqual(block.outcome_for("hard", 3, ["readiness", "niggle"], 6), ("due", "deload", "triggers"))
        self.assertEqual(block.outcome_for("hard", 2, ["readiness", "sleep"], 6), ("skipped", None, None))
        self.assertEqual(block.outcome_for("partial", 4, ["sleep"], 6), ("watch", None, None))
        self.assertEqual(block.outcome_for("low", 0, [], 6, ill=True), ("due", "return", "illness"))
        self.assertEqual(block.outcome_for("low", 0, [], 6), ("none", None, None))


if __name__ == "__main__":
    unittest.main()
