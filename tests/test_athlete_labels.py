"""Athlete-facing labels: exercise names, Hevy-aware loads, schedule and scheme summaries, training maxes and
rotation wording on every human page, with machine-readable ids kept in the data (contracts C5, C11, C16, C36, C38)."""

import copy
import json
import re
from datetime import date, datetime, timezone

from coach import checkin, checkin_catchup, overlay, pages, program, propose, render, sheets, summaries
from coach.library import Library
from coach.plugins import base
from tests.support import VALID, run_cli
from tests.support.history import read_json, write_json
from tests.test_manual_log import NoHevyCase
from tests.test_readable_numbers import BENCH_SETS, SQUAT_SETS, workout

WEEKLY = "2026-10-12-weekly"
RECORD = "check-ins/2026-10-11.md"
SUNDAY = "2026-10-18T18:00:00Z"
SATURDAY_EVENING = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
NAMES = ("Back Squat (Barbell)", "Bench Press (Dumbbell)", "Single Arm Row (Dumbbell)")
IDS = ("bb_back_squat", "db_bench_press", "db_single_arm_row")


def table_cells(text):
    """The first cell of every table row."""
    return [line.strip("|").split("|")[0].strip() for line in text.splitlines() if line.startswith("| ")]


class NoHevySurfacesTest(NoHevyCase):
    """With `[hevy] enabled = false`, no athlete page prints a Hevy value, and exercise cells carry names."""

    def log_week(self):
        with (self.root / "data/log/workouts.jsonl").open("a", encoding="utf-8") as handle:
            for line in (workout("2026-10-12", "session-a", [("bb_back_squat", "total", SQUAT_SETS),
                                                              ("db_bench_press", "per_hand_x2", BENCH_SETS)]),
                         workout("2026-10-15", "session-b",
                                 [("db_single_arm_row", "single_implement", [(30, 10, 8)] * 3)])):
                handle.write(json.dumps(line) + "\n")
        self.coach("history", "sync", now=SUNDAY)

    def test_overlay_region_uses_names_and_no_hevy_value(self):
        region = self.coach("overlay", "render", WEEKLY)["data"]["text"]
        self.assertNotIn("(Hevy:", region)
        cells = table_cells(region)
        for name, exercise_id in zip(NAMES, IDS):
            self.assertIn(name, cells)
            self.assertNotIn(exercise_id, cells)
        self.assertIn("| 25/hand |", region)

    def test_check_in_skeleton_after_logged_sessions(self):
        self.log_week()
        skeleton = self.coach("checkin", "skeleton", "--date", "2026-10-18", "--overlay", WEEKLY, "--dry-run",
                              now=SUNDAY)["data"]["text"]
        self.assertNotIn("(Hevy:", skeleton)
        review = skeleton.split("## Coach's read")[0]
        for name in NAMES:
            self.assertIn(f"| {name} |", review)
        for exercise_id in IDS:
            self.assertNotIn(f"| {exercise_id} |", skeleton)
        card = self.coach("checkin", "prepare", now=SUNDAY)["data"]["card"]
        self.assertLessEqual(set(IDS), {row["exercise_id"] for row in card["exercises"]})

    def test_routine_pages_and_proposal_text(self):
        self.coach("program", "render")
        for page in ("session-a.md", "session-b.md"):
            text = (self.root / "routine" / page).read_text(encoding="utf-8")
            self.assertNotIn("(Hevy:", text)
        self.log_week()
        data = self.coach("propose", "week", "--week", "2026-W43", "--dry-run", now=SUNDAY)["data"]
        human = json.dumps([[row["text"], row["change"], row["rationale"]] for row in data["lines"]],
                           ensure_ascii=False)
        self.assertNotIn("(Hevy:", human)
        self.assertIn("/hand", human)
        self.assertEqual({row["exercise_id"] for row in data["lines"]} & set(IDS), set(IDS))

    def test_freshness_uses_the_same_renderer(self):
        self.assertEqual(self.check("overlay_render_fresh"), {"pass"})
        path = self.root / RECORD
        text = path.read_text(encoding="utf-8")
        row = "| Single Arm Row (Dumbbell) | 3×10 | 30 |"
        self.assertIn(row, text)
        path.write_text(text.replace(row, row.replace("| 30 |", "| 32 |")), encoding="utf-8")
        self.assertEqual(self.check("overlay_render_fresh"), {"fail"})

    def check(self, check_id):
        _, envelope, _ = run_cli(["--root", str(self.root), "check", "--only", check_id], env={"COACH_NOW": self.now})
        return {row["status"] for row in envelope["data"]["results"]}


class HevyOnLoadsTest(NoHevyCase):
    base = VALID

    def test_paired_dumbbells_keep_both_numbers_and_single_arm_prints_one(self):
        region = render.render_overlay(self.root, WEEKLY)
        self.assertIn("| Bench Press (Dumbbell) | 1×10 warm-up | 12.5/hand (Hevy: 25) |", region)
        self.assertIn("| Single Arm Row (Dumbbell) | 3×10 | 30 |", region)
        self.assertNotIn("Hevy: 30", region)
        doc = overlay.load(self.root, WEEKLY)
        row = doc["sessions"][1]
        self.assertEqual(render.render_hevy_note(doc, row, row["exercises"][0], False).splitlines()[0],
                         "Target: 3×10 @ 30 @ RPE 8")


class SummaryTest(NoHevyCase):
    """Schedules, schemes and equal-ended rep ranges read as short human summaries."""

    def program_doc(self):
        doc = program.load(self.root)
        doc["schedule"] = {"rule": "fixed_weekdays",
                           "params": {"days": {"sat": "session-a", "mon": "session-a", "thu": "session-b"}}}
        row = doc["sessions"][1]["exercises"]
        row[1]["scheme"] = {"name": "linear", "params": {"increment": 5, "misses_before_reset": 1,
                                                         "reset_factor": 0.9}}
        ladder = copy.deepcopy(row[1])
        ladder.update(exercise_id="assisted_pull_up", load_mode="assisted", start_load=50,
                      sets=[{"count": 3, "type": "normal", "rep_range": {"start": 6, "end": 6}, "rpe": 8}],
                      scheme={"name": "assistance_ladder", "params": {
                          "rungs": [{"name": f"{load} kg assistance", "load": load} for load in range(50, 0, -5)],
                          "reps": None, "sets": None, "rpe": None}})
        row.append(ladder)
        return doc

    def pages(self):
        return program.render_doc(self.program_doc(), Library.load(self.root), "kg", show_hevy=False)

    def test_fixed_schedule_reads_in_week_order_with_titles(self):
        page = self.pages()["routine/program.md"]
        self.assertIn("Schedule rule: fixed weekdays: Mon Session A · Thu Session B · Sat Session A", page)

    def test_scheme_summaries_have_no_raw_json(self):
        page = self.pages()["routine/session-b.md"]
        rows = [line for line in page.splitlines() if line.startswith("| Pull Up") or line.startswith("| Assisted")]
        self.assertEqual(len(rows), 2, page)
        for line in rows:
            self.assertIsNone(re.search(r"[{}\[\]]|null", line), line)
        self.assertIn("linear (add 5 kg after each exposure that hits all its reps; reset after 1 miss in a row; "
                      "a reset drops the load to 90 %)", rows[0])
        self.assertIn("assistance ladder (10 rungs: 50 kg assistance → 45 kg assistance → … → 5 kg assistance)",
                      rows[1])

    def test_equal_rep_range_ends_read_as_one_count_everywhere(self):
        self.assertIn("| 3×6 |", self.pages()["routine/session-b.md"])
        doc = overlay.load(self.root, WEEKLY)
        row = doc["sessions"][1]["exercises"][0]
        for set_ in row["sets"]:
            set_.pop("reps", None)
            set_["rep_range"] = {"start": 6, "end": 6}
        self.assertIn("| 3×6 |", render.render_week_ahead(doc))
        self.assertIn("3×6 @ 30", checkin.prescribed_text(row))
        self.assertIn("3×6 @ 30", pages.sets_text(row))
        self.assertIn("| 3×6 |", "\n".join(sheets._rows(row, "Row")))
        sets = tuple(base.SetSpec(type="normal", rep_range=(6, 6), load=30, rpe=8) for _ in range(3))
        self.assertEqual(propose.sets_text(sets, "single_implement", "kg"), "3×6 @ 30 RPE 8")

    def test_routine_start_loads_are_labelled_starting_values(self):
        page = self.pages()["routine/session-a.md"]
        self.assertIn("Start loads in kg: where each exercise began, not this week's prescription.", page)
        self.assertIn("[this week's brief](../this-week.md)", page)


class TrainingMaxTest(NoHevyCase):
    def set_wave(self, stored=None):
        path = self.root / "data/program.json"
        doc = read_json(path)
        squat = doc["sessions"][0]["exercises"][0]
        squat["scheme"] = {"name": "wave_531", "params": {"training_max": 180}}
        write_json(path, doc)
        if stored is not None:
            path = self.root / "data/state.json"
            state = read_json(path)
            state["scheme_state"]["session-a/bb_back_squat"] = {
                "scheme": "wave_531", "data": {"completed_weeks": 1, "training_max": stored, "through": None},
                "pending": None}
            write_json(path, state)

    def progress(self):
        return pages.render_progress(self.root, SATURDAY_EVENING)

    def test_routine_shows_the_starting_max_and_progress_the_current_one(self):
        self.set_wave(stored=195)
        self.coach("program", "render")
        page = (self.root / "routine/session-a.md").read_text(encoding="utf-8")
        self.assertIn("wave 531 (starting training max 180 kg)", page)
        self.assertIn("- Back Squat (Barbell), Session A: current training max 195 kg (program start 180 kg).",
                      self.progress())

    def test_without_state_the_program_max_is_the_current_one(self):
        self.set_wave()
        self.assertIn("- Back Squat (Barbell), Session A: current training max 180 kg, the program's starting "
                      "training max.", self.progress())

    def test_no_section_without_a_training_max_scheme(self):
        self.assertNotIn("Training maxes", self.progress())


class RotationTest(NoHevyCase):
    """A sequence stores the session last trained; pages and the card name the session the week starts with."""

    def setUp(self):
        super().setUp()
        path = self.root / "data/program.json"
        doc = read_json(path)
        doc["schedule"] = {"rule": "next_in_sequence",
                           "params": {"sequence": ["session-a", "session-b"], "days": ["mon", "thu"]}}
        write_json(path, doc)
        path = self.root / "data/state.json"
        state = read_json(path)
        state["rotation"] = {"position": "session-b", "confirmed": True, "confirmed_at": "2026-10-11",
                             "week": "2026-10-12"}
        write_json(path, state)

    def test_brief_header_names_the_first_session(self):
        header = pages.render_brief(self.root, SATURDAY_EVENING).splitlines()[1]
        self.assertIn("Starts with Session A after Session B (confirmed)", header)

    def test_card_names_the_first_session_of_next_week(self):
        inst = checkin._Instance.load(self.root)
        text = checkin_catchup.rotation_text(inst, date(2026, 10, 11))
        self.assertIn("next week starts with Session A, after Session B as the last session trained (confirmed)",
                      text)

    def test_status_line_says_last_trained(self):
        code, envelope, _ = run_cli(["--root", str(self.root), "status"], env={"COACH_NOW": "2026-10-11T18:00:00Z"})
        self.assertEqual(code, 0, envelope)
        self.assertIn("Rotation: session-b last trained, session-a next, confirmed", json.dumps(envelope))


class MarkdownSafetyTest(NoHevyCase):
    def test_names_escape_pipes(self):
        doc = overlay.load(self.root, WEEKLY)
        region = render.render_week_ahead(doc, lambda exercise_id: "Squat | paused")
        self.assertIn("| Squat \\| paused |", region)

    def test_refresh_keeps_prose_and_is_stable(self):
        first = checkin.skeleton(self.root, "2026-10-11", refresh=True)["text"]
        self.assertIn("Synthetic test record.", first)
        self.assertIn("Stay the course: add load where last week's sets were met.", first)
        self.assertEqual(first, (self.root / RECORD).read_text(encoding="utf-8"))
        second = checkin.skeleton(self.root, "2026-10-11", refresh=True)
        self.assertFalse(second["written"])
        self.assertEqual(second["text"], first)

    def test_summary_names_ids_it_knows(self):
        names = summaries.Names({"pt": "PT session"}, {"kb_swing": "Kettlebell Swing"}, "kg")
        self.assertEqual(summaries.rule_text({"name": "standard", "params": {"rpe": 6, "load_factor": None}}, names),
                         "standard (RPE 6)")
        self.assertEqual(summaries.scheme_text({"name": "custom", "params": {"reps": {"kb_swing": 10}}}, names),
                         "custom (reps Kettlebell Swing 10)")

