"""Return to training: days off to the first session back, coach-led lifting, the catch-up span, resuming after a
return week and illness (contract C17, C22, C23, C24, C36)."""

import copy
from datetime import date

from coach import history, units
from tests.support.history import read_json, write_json
from tests.test_block import NOW, BlockCase

SUNDAY_25 = "2026-10-25T18:00:00Z"
SUNDAY_1 = "2026-11-01T18:00:00Z"
SUNDAY_8 = "2026-11-08T18:00:00Z"
WORKING = ("normal", "dropset", "failure")


def lines_by(data):
    return {(row["date"], row["exercise_id"]): row for row in data["lines"]}


def working(line):
    return [s for s in line["sets"] if s["type"] in WORKING]


class ReturnCase(BlockCase):
    """The block fixture, by default trained through Thu 15 Oct (Session A Mon 12, PT Tue 13, Session B Thu 15)."""

    trained_w42 = True

    def setUp(self):
        super().setUp()
        if self.trained_w42:
            self.train_week("2026-10-12")

    def month(self, day):
        path = self.root / "data" / "history" / f"{day[:7]}.json"
        if not path.exists():
            template = read_json(self.root / "data" / "history" / "2026-10.json")
            write_json(path, dict(template, month=day[:7], workouts=[]))
        return path

    def copy_workout(self, day, to):
        source = next(w for w in self.workouts() if w["date"] == day)
        workout = copy.deepcopy(source)
        workout.update(workout_id=f"{workout['workout_id'][:-3]}9{to[-2:]}", date=to,
                       start_time=f"{to}T10:00:00Z", end_time=f"{to}T11:00:00Z")
        self.append(workout)

    def append(self, workout):
        path = self.month(workout["date"])
        doc = read_json(path)
        doc["workouts"].append(workout)
        write_json(path, doc)

    def log_as_prescribed(self, doc, day):
        """A workout for the overlay's session on `day`, every working set logged as prescribed at RPE 6."""
        session = next(s for s in doc["sessions"] if s["date"] == day)
        template = copy.deepcopy(next(w for w in self.workouts() if w["session_id"] == session["session_id"]))
        by_id = {e["exercise_id"]: e for e in template["exercises"]}
        exercises = []
        for line in session["exercises"]:
            entry = copy.deepcopy(by_id[line["exercise_id"]])
            sets = []
            for index, wanted in enumerate(working(line)):
                load = wanted.get("load")
                value = (load["per_hand"] if load["mode"] in units.PER_HAND_MODES else load["hevy_total"]) \
                    if load else 0
                made = units.make_load(value, line["load_mode"], "kg")
                reps = wanted["reps"] if wanted.get("reps") is not None else wanted["rep_range"]["end"]
                sets.append({"index": index, "type": "normal", "reps": reps, "rpe": 6,
                             "weight_kg": float(made["hevy_kg"] or 0), "load": made,
                             "duration_seconds": None, "distance_meters": None})
            entry["sets"] = sets
            exercises.append(entry)
        template.update(workout_id=f"{template['workout_id'][:-3]}8{day[-2:]}", date=day,
                        start_time=f"{day}T18:00:00Z", end_time=f"{day}T19:00:00Z", overlay_id=doc["id"],
                        exercises=exercises)
        self.append(template)

    def propose(self, *argv, now):
        return self.data("propose", "week", *argv, now=now)

    def approve(self, data, now):
        self.data("propose", "finalize", "--proposal", data["id"], now=now)
        self.data("overlay", "approve", data["id"], now=now)
        return read_json(self.root / "data" / "overlays" / f"{data['id']}.json")

    def set_scheme(self, session_id, exercise_id, name):
        def change(doc):
            session = next(s for s in doc["sessions"] if s["id"] == session_id)
            line = next(e for e in session["exercises"] if e["exercise_id"] == exercise_id)
            line["scheme"] = {"name": name, "params": {}}
        self.edit("data/program.json", change)


class DaysOffTest(ReturnCase):
    def test_the_layoff_runs_to_the_first_session_back_for_every_session_in_the_span(self):
        self.copy_workout("2026-10-12", "2026-10-17")
        data = self.propose("--week", "2026-W44", now=SUNDAY_25)
        self.assertEqual({row["date"] for row in data["lines"]}, {"2026-10-26", "2026-10-29"})
        self.assertEqual([row for row in data["lines"] if "return_week" in row["flags"]], [])
        self.assertTrue(all(line["provenance"]["decay"] is None
                            for session in data["overlay"]["sessions"] for line in session["exercises"]))
        checked = self.data("prescription", "check", "--file",
                            str(self.root / ".coach" / "proposals" / f"{data['id']}.json"), now=SUNDAY_25)
        self.assertEqual({row["days_off"] for row in checked["lines"]}, {9})
        self.assertEqual(checked["summary"]["block"], 0, checked["flags"])

    def test_the_lift_specific_overdue_gap_still_counts(self):
        self.copy_workout("2026-10-12", "2026-10-17")
        self.drop_workout("2026-10-15")
        self.drop_workout("2026-10-08")
        lines = lines_by(self.propose("--week", "2026-W44", "--dry-run", now=SUNDAY_25))
        self.assertIn("return_week", lines[("2026-10-29", "db_single_arm_row")]["flags"])
        self.assertNotIn("return_week", lines[("2026-10-26", "bb_back_squat")]["flags"])

    def test_a_coach_led_lifting_session_done_ends_the_layoff(self):
        self.data("history", "annotate", "--kind", "external", "--external", "pt-tue", "--date", "2026-10-21",
                  "--done", now=SUNDAY_25)
        lines = lines_by(self.propose("--week", "2026-W44", "--dry-run", now=SUNDAY_25))
        self.assertNotIn("return_week", lines[("2026-10-26", "bb_back_squat")]["flags"])

    def test_a_coach_led_session_not_done_does_not(self):
        self.data("history", "annotate", "--kind", "external", "--external", "pt-tue", "--date", "2026-10-21",
                  "--not-done", now=SUNDAY_25)
        lines = lines_by(self.propose("--week", "2026-W44", "--dry-run", now=SUNDAY_25))
        self.assertIn("return_week", lines[("2026-10-26", "bb_back_squat")]["flags"])
        self.assertIn("11 days off", lines[("2026-10-26", "bb_back_squat")]["rationale"])

    def test_only_coach_led_sessions_that_lift_count_and_the_newest_annotation_decides(self):
        def add_spin(doc):
            doc["external_sessions"].append({"id": "spin", "title": "Spin class", "weekday": None,
                                             "estimated_sets": {"cardio": 2}})
        self.edit("data/program.json", add_spin)
        self.data("history", "annotate", "--kind", "external", "--external", "spin", "--date", "2026-10-21",
                  "--done", now=SUNDAY_25)
        self.assertEqual(history.last_lifting_date(self.root, date(2026, 10, 26)), date(2026, 10, 15))
        for done, expected in (("--done", date(2026, 10, 20)), ("--not-done", date(2026, 10, 15))):
            with self.subTest(done=done):
                self.data("history", "annotate", "--kind", "external", "--external", "pt-tue", "--date",
                          "2026-10-20", done, now=SUNDAY_25)
                self.assertEqual(history.last_lifting_date(self.root, date(2026, 10, 26)), expected)


class CatchUpSpanTest(ReturnCase):
    def test_a_saturday_catch_up_plans_nothing_in_the_past(self):
        (self.root / "check-ins").mkdir(exist_ok=True)
        (self.root / "check-ins" / "2026-10-18.md").write_text("# Check-in — 2026-10-18 (weekly)\n", encoding="utf-8")
        card = self.data("checkin", "prepare", now="2026-10-31T10:00:00Z")["card"]
        week = card["catch_up"]["return_week"]
        self.assertEqual([s["date"] for s in week["sessions"]], ["2026-11-02", "2026-11-05"])
        self.assertEqual((week["days_off"], week["band"], week["week"]), (18, "11-21", "2026-W45"))


class AfterTheReturnWeekTest(ReturnCase):
    def return_week(self, *argv):
        data = self.propose("--week", "2026-W45", *argv, now=SUNDAY_1)
        doc = self.approve(data, SUNDAY_1)
        self.log_as_prescribed(doc, "2026-11-02")
        self.log_as_prescribed(doc, "2026-11-05")
        return doc

    def test_the_next_week_progresses_from_the_logged_return_week_with_its_sets_back(self):
        doc = self.return_week("--kind", "deload", "--transform", "return")
        self.assertEqual({s["title"] for s in doc["sessions"]}, {"Return — Session A", "Return — Session B"})
        self.assertTrue(doc["focus"].startswith("Return week of 2026-11-02"))
        squat = next(line for line in doc["sessions"][0]["exercises"] if line["exercise_id"] == "bb_back_squat")
        self.assertEqual(len(working(squat)), 2)
        data = self.propose("--week", "2026-W46", "--dry-run", now=SUNDAY_8)
        lines = lines_by(data)
        for day, exercise_id in (("2026-11-09", "bb_back_squat"), ("2026-11-12", "pull_up")):
            with self.subTest(exercise=exercise_id):
                logged = "2026-11-02" if day == "2026-11-09" else "2026-11-05"
                self.assertIn(logged, lines[(day, exercise_id)]["rationale"])
                self.assertTrue(lines[(day, exercise_id)]["text"].startswith("3×"), lines[(day, exercise_id)])

    def test_hold_restores_its_sets_at_the_load_the_return_week_logged(self):
        self.set_scheme("session-a", "bb_back_squat", "hold")
        first = self.approve(self.propose("--week", "2026-W43", now="2026-10-18T18:00:00Z"), "2026-10-18T18:00:00Z")
        held = next(line for line in first["sessions"][0]["exercises"] if line["exercise_id"] == "bb_back_squat")
        self.assertEqual(len(working(held)), 3)
        self.return_week()
        squat = lines_by(self.propose("--week", "2026-W46", "--dry-run", now=SUNDAY_8))[
            ("2026-11-09", "bb_back_squat")]
        self.assertTrue(squat["text"].startswith("3×5 @ 90"), squat)
        self.assertIn("the return week logged on 2026-11-02", squat["rationale"])

    def test_hold_restores_its_sets_after_an_ordinary_deload(self):
        self.set_scheme("session-a", "bb_back_squat", "hold")
        weekly = self.approve(self.propose("--week", "2026-W43", now="2026-10-18T18:00:00Z"), "2026-10-18T18:00:00Z")
        before = next(line for line in weekly["sessions"][0]["exercises"] if line["exercise_id"] == "bb_back_squat")
        self.log_as_prescribed(weekly, "2026-10-19")
        self.log_as_prescribed(weekly, "2026-10-22")
        deload = self.approve(self.propose("--week", "2026-W44", "--kind", "deload", now=SUNDAY_25), SUNDAY_25)
        self.assertEqual({s["title"] for s in deload["sessions"]}, {"Deload — Session A", "Deload — Session B"})
        cut = next(line for line in deload["sessions"][0]["exercises"] if line["exercise_id"] == "bb_back_squat")
        self.assertLess(len(working(cut)), len(working(before)))
        self.log_as_prescribed(deload, "2026-10-26")
        self.log_as_prescribed(deload, "2026-10-29")
        squat = lines_by(self.propose("--week", "2026-W45", "--dry-run", now=SUNDAY_1))[
            ("2026-11-02", "bb_back_squat")]
        self.assertEqual(squat["text"], f"{len(working(before))}×5 @ 95 RPE 7")
        self.assertIn(weekly["id"], squat["rationale"])


class AgreedReturnWeekTest(ReturnCase):
    trained_w42 = False

    def test_an_agreed_return_week_without_a_layoff_is_the_next_baseline(self):
        self.close()
        self.data("block", "decide", "--outcome", "adopted", "--type", "return", "--reason", "back from a cold")
        doc = self.approve(self.propose("--week", "2026-W42", "--kind", "deload", "--transform", "return", now=NOW),
                           NOW)
        squat = next(line for line in doc["sessions"][0]["exercises"] if line["exercise_id"] == "bb_back_squat")
        self.assertEqual((squat["provenance"]["decay"], len(working(squat))), (None, 2))
        self.log_as_prescribed(doc, "2026-10-12")
        self.log_as_prescribed(doc, "2026-10-15")
        lines = lines_by(self.propose("--week", "2026-W43", "--dry-run", now="2026-10-18T18:00:00Z"))
        squat = lines[("2026-10-19", "bb_back_squat")]
        self.assertIn("2026-10-12", squat["rationale"])
        self.assertTrue(squat["text"].startswith("3×"), squat)


class IllnessTest(ReturnCase):
    def test_an_illness_open_today_plans_no_session(self):
        self.copy_workout("2026-10-12", "2026-10-19")
        self.data("status-days", "add", "--kind", "ill", "--from", "2026-10-22", "--note", "Head cold",
                  now="2026-10-22T08:00:00Z")
        for argv in (("--kind", "midweek"), ("--week", "2026-W44")):
            with self.subTest(argv=argv):
                refused = self.coach("propose", "week", *argv, "--dry-run", expect=3, now="2026-10-22T12:00:00Z")
                self.assertIn("s-0001", refused["error"]["message"])
                self.assertIn("48 hours symptom-free", refused["error"]["message"])

    def test_closing_the_illness_still_needs_the_recovery_confirmation(self):
        self.data("status-days", "add", "--kind", "ill", "--from", "2026-10-24", "--note", "Head cold",
                  now="2026-10-24T08:00:00Z")
        self.data("status-days", "end", "s-0001", "--date", "2026-10-26", now=SUNDAY_25)
        data = self.propose("--week", "2026-W44", now=SUNDAY_25)
        doc = data["overlay"]
        self.assertEqual([s["date"] for s in doc["sessions"]], ["2026-10-29"])
        excluded = [f for f in doc["flags"] if f["code"] == "ill_day_excluded"]
        self.assertEqual([(f["session_id"], f["severity"]) for f in excluded], [(None, "info")])
        self.assertIn("(session-a) on 2026-10-26 is left out: ill status day s-0001", excluded[0]["message"])
        index, flag = next((i, f) for i, f in enumerate(doc["flags"]) if f["code"] == "return_after_illness")
        self.assertEqual((flag["session_id"], flag["severity"], flag["resolved"]), ("session-b", "block", False))
        self.assertTrue(all(s["rpe"] is not None and s["rpe"] <= 7
                            for line in doc["sessions"][0]["exercises"] for s in working(line)))
        refused = self.coach("propose", "finalize", "--proposal", data["id"], expect=3, now=SUNDAY_25)
        self.assertIn("return_after_illness", refused["error"]["message"] + str(refused["error"].get("details")))
        self.data("propose", "resolve", "--proposal", data["id"], "--flag", str(index), "--resolution",
                  "Athlete confirmed 48 hours symptom-free on 25 Oct, symptoms above the neck only", now=SUNDAY_25)
        self.data("propose", "finalize", "--proposal", data["id"], now=SUNDAY_25)
