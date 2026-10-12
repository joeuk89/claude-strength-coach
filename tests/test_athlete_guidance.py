"""Athlete guidance from the coaching decision to the pages trained from: line notes, the week focus, first-load
calibration and the beginner key (contract C10, C24, C46)."""

import json
import re
import unittest
from pathlib import Path

from coach import overlay, pages, propose, render, sheets
from tests.support import VALID
from tests.support.skills import flat, step_text
from tests.test_manual_log import NoHevyCase
from tests.test_starters import WEEK as STARTER_WEEK
from tests.test_starters import Case as StarterCase
from tests.test_starters import lines, set_athlete
from tests.test_week_rebuild import SUNDAY, WEEKLY as W43, RebuildCase, line

WEEKLY = "2026-10-12-weekly"
SHEETS = "this-week-sheets.md"
AUDIT = "internal calibration review: no previous log"
ADJUST = "Adjust after the first set to meet the agreed effort target"
FOCUS = "Practise a controlled squat descent"
DIGIT = re.compile(r"\d")


def table_row(text, *names):
    return next(row for row in text.splitlines() if row.startswith("| ") and any(n in row for n in names))


def bullet(text, name):
    return next(row for row in text.splitlines() if row.startswith(f"- **{name}**"))


def set_experience(root, experience):
    set_athlete(root, experience=experience)


class OverlayCopyCase(NoHevyCase):
    """The nohevy instance on the Sunday before its 2026-10-12 week, with the overlay editable in place."""

    now = "2026-10-11T18:00:00Z"

    def edit_overlay(self, change):
        path = self.root / "data" / "overlays" / f"{WEEKLY}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return doc

    def sheet(self):
        return sheets.render_sheets(self.root, WEEKLY)

    def check(self, check_id="sheets_render_fresh", expect=0):
        return [r["status"] for r in self.coach("check", "--only", check_id, expect=expect)["data"]["results"]]


def _line(doc, exercise_id):
    return next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == exercise_id)


class SheetNoteTest(OverlayCopyCase):
    def test_the_squat_note_sits_under_the_squat_and_nowhere_else(self):
        text = self.sheet()
        self.assertEqual(bullet(text, "Back Squat (Barbell)"),
                         "- **Back Squat (Barbell)**: Note: add 2.5 from last week · Cues: brace · knees out")
        self.assertEqual(text.count("add 2.5 from last week"), 1)

    def test_per_leg_and_capped_notes_print_exactly_once_beside_focus_and_cues(self):
        def change(doc):
            _line(doc, "bb_back_squat")["target_note"] = "10 per leg"
            _line(doc, "db_bench_press")["target_note"] = "stop at RPE 9"

        self.edit_overlay(change)
        text = self.sheet()
        self.assertEqual(bullet(text, "Back Squat (Barbell)"),
                         "- **Back Squat (Barbell)**: Note: 10 per leg · Cues: brace · knees out")
        self.assertEqual(bullet(text, "Bench Press (Dumbbell)"),
                         "- **Bench Press (Dumbbell)**: Focus: pause 1 s on the chest · Note: stop at RPE 9 · "
                         "Cues: elbows tucked · feet planted")
        self.assertEqual((text.count("10 per leg"), text.count("stop at RPE 9")), (1, 1))

    def test_a_note_repeating_the_focus_or_cues_prints_once(self):
        def change(doc):
            _line(doc, "db_bench_press")["target_note"] = "pause 1 s on the chest"
            _line(doc, "pull_up")["target_note"] = "full hang at the bottom"

        self.edit_overlay(change)
        text = self.sheet()
        self.assertEqual(text.count("pause 1 s on the chest"), 1)
        self.assertEqual(bullet(text, "Pull Up"), "- **Pull Up**: Cues: full hang at the bottom")


class AuditReasonTest(OverlayCopyCase):
    def audited(self, note=None):
        def change(doc):
            squat = _line(doc, "bb_back_squat")
            squat["override"] = {"reason": AUDIT, "proposed_sets": squat["sets"]}
            squat["target_note"] = note

        return self.edit_overlay(change)

    def test_an_override_reason_stays_in_the_audit_and_off_the_athlete_pages(self):
        doc = self.audited()
        self.assertEqual(overlay.load(self.root, WEEKLY)["sessions"][0]["exercises"][0]["override"]["reason"], AUDIT)
        self.assertNotIn(AUDIT, render.render_week_ahead(doc))
        self.assertNotIn(AUDIT, self.sheet())

    def test_a_separate_target_note_reaches_the_sheet_and_the_week_ahead(self):
        doc = self.audited(ADJUST)
        region = render.render_week_ahead(doc)
        squat_row = table_row(region, "bb_back_squat", "Back Squat")
        self.assertTrue(squat_row.rstrip(" |").endswith(ADJUST), squat_row)
        self.assertIn(f"Note: {ADJUST}", bullet(self.sheet(), "Back Squat (Barbell)"))
        self.assertNotIn(AUDIT, region + self.sheet())

    def test_the_valid_week_ahead_keeps_focus_and_note_in_the_notes_cell(self):
        doc = json.loads((VALID / "data" / "overlays" / f"{WEEKLY}.json").read_text(encoding="utf-8"))
        _line(doc, "db_bench_press")["target_note"] = "pause 1 s on the chest"
        bench = table_row(render.render_week_ahead(doc), "db_bench_press", "Bench Press")
        self.assertEqual(bench.count("pause 1 s on the chest"), 1)


class SchemeNoteTest(OverlayCopyCase):
    def test_ladder_deload_and_rep_out_decisions_reach_the_sheet_unchanged(self):
        ladder = "Rung 2 of 3: band-assisted; rung 3 waits for an ordinary week"
        deload = "Deload week: 40/50/60 % of the training max, no + set"

        def change(doc):
            _line(doc, "pull_up")["target_note"] = ladder
            _line(doc, "bb_back_squat")["target_note"] = deload
            row = _line(doc, "db_single_arm_row")
            row["target_note"] = "Wave week 1 of 3"
            row["sets"][-1] = dict(row["sets"][-1], reps=5, rep_out=True, rpe=8.5)

        self.edit_overlay(change)
        text = self.sheet()
        self.assertIn(f"Note: {ladder}", bullet(text, "Pull Up"))
        self.assertIn(f"Note: {deload}", bullet(text, "Back Squat (Barbell)"))
        self.assertIn("Note: Wave week 1 of 3", bullet(text, "Single Arm Row (Dumbbell)"))
        self.assertIn("| 1×5+ | 30 | stop at 8.5 |", text)


class FreshnessTest(OverlayCopyCase):
    def setUp(self):
        super().setUp()
        self.coach("sheets", "render")

    def test_a_changed_note_makes_the_sheets_stale_until_rendered_again(self):
        self.assertEqual(self.check(), ["pass"])
        self.edit_overlay(lambda doc: _line(doc, "bb_back_squat").update(target_note="10 per leg"))
        self.assertEqual(self.check(expect=1), ["fail"])
        self.coach("sheets", "render", "--overlay", WEEKLY)
        before = (self.root / SHEETS).read_bytes()
        self.assertFalse(self.coach("sheets", "render", "--overlay", WEEKLY)["data"]["changed"])
        self.assertEqual((self.root / SHEETS).read_bytes(), before)
        self.assertIn(b"10 per leg", before)

    def test_a_changed_experience_makes_the_sheets_stale(self):
        set_experience(self.root, "beginner")
        self.assertEqual(self.check(expect=1), ["fail"])
        self.coach("sheets", "render")
        self.assertEqual(self.check(), ["pass"])


class BeginnerKeyTest(OverlayCopyCase):
    def test_a_beginner_sheet_explains_rpe_and_rep_ranges(self):
        set_experience(self.root, "beginner")
        text = self.sheet()
        key = text[text.index("---"):]
        self.assertIn("RPE 8 ≈ 2 reps left", key)
        self.assertIn("estimate", key)
        self.assertIn("8–10 means any count from 8 to 10 is on plan", key)
        self.assertIn("RPE", key[key.index("8–10"):])

    def test_an_experienced_athlete_gets_no_key(self):
        for experience in ("intermediate", "advanced"):
            with self.subTest(experience=experience):
                set_experience(self.root, experience)
                self.assertNotIn("reps left", self.sheet())


class WeekFocusTest(RebuildCase):
    def note(self, *argv, expect=0):
        return self.run_coach("propose", "note", "--proposal", W43, *argv, expect=expect)

    def test_the_week_focus_reaches_the_overlay_record_sheets_and_brief(self):
        proposed = self.run_coach("propose", "week", "--week", "2026-W43")
        self.assertIn("progression scheme proposes", proposed["overlay"]["focus"])
        self.assertEqual(self.note("--week-focus", FOCUS)["focus"], FOCUS)
        self.assertEqual(self.run_coach("propose", "show", W43)["unexplained"], [])
        doc = self.run_coach("propose", "finalize", "--proposal", W43)["overlay"]
        self.assertEqual(doc["focus"], FOCUS)
        self.assertIn(f"**Week focus:** {FOCUS}", render.render_week_ahead(doc))
        self.run_coach("overlay", "approve", W43)
        self.run_coach("sheets", "render", "--overlay", W43)
        self.assertIn(f"**Week focus:** {FOCUS}", (self.root / SHEETS).read_text(encoding="utf-8"))
        self.run_coach("pages", "render")
        brief = (self.root / "this-week.md").read_text(encoding="utf-8")
        focus = brief[brief.index("## Focus"):brief.index("## Sessions")]
        self.assertIn(FOCUS, focus)
        self.assertNotIn("progression scheme proposes", focus)

    def test_line_guidance_needs_no_override_reason_and_survives_rebuild(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.note("--week-focus", FOCUS)
        found = self.note("--session", "session-a", "--exercise", "bb_back_squat", "--target-note", ADJUST)
        self.assertEqual([(r["exercise_id"], r["target_note"]) for r in found["lines"]], [("bb_back_squat", ADJUST)])
        self.override(W43, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        rebuilt = self.run_coach("propose", "rebuild", "--proposal", W43)
        self.assertEqual(rebuilt["overlay"]["focus"], FOCUS)
        self.assertEqual(line(rebuilt["overlay"], "bb_back_squat")["target_note"], ADJUST)
        self.assertIsNone(line(rebuilt["overlay"], "bb_back_squat")["override"])
        self.assertEqual(line(rebuilt["overlay"], "db_single_arm_row")["override"]["reason"], "hold at 30")
        self.assertEqual(rebuilt["guidance_kept"], [{"session_id": "session-a", "date": "2026-10-19",
                                                     "exercise_id": "bb_back_squat", "fields": ["target_note"]}])
        doc = self.run_coach("propose", "finalize", "--proposal", W43)["overlay"]
        self.assertEqual((doc["focus"], line(doc, "bb_back_squat")["target_note"]), (FOCUS, ADJUST))

    def test_a_note_on_a_line_with_a_kept_standing_override_survives_rebuild(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.run_coach("propose", "override", "--proposal", W43, "--session", "session-a", "--exercise",
                       "bb_back_squat", "--load", "100", "--reason", "hold while the knee settles", "--standing")
        self.run_coach("propose", "finalize", "--proposal", W43)
        self.run_coach("overlay", "approve", W43)
        now = "2026-10-25T19:00:00Z"
        week = self.run_coach("propose", "week", "--week", "2026-W44", now=now)
        self.assertEqual(line(week["overlay"], "bb_back_squat")["override"]["reason"], "hold while the knee settles")
        self.run_coach("propose", "note", "--proposal", week["id"], "--session", "session-a",
                       "--exercise", "bb_back_squat", "--target-note", "stop at RPE 9", now=now)
        rebuilt = self.run_coach("propose", "rebuild", "--proposal", week["id"], now=now)
        squat = line(rebuilt["overlay"], "bb_back_squat")
        self.assertEqual((squat["target_note"], squat["override"]["reason"]),
                         ("stop at RPE 9", "hold while the knee settles"))
        self.assertEqual(rebuilt["guidance_kept"], [{"session_id": "session-a", "date": "2026-10-26",
                                                     "exercise_id": "bb_back_squat", "fields": ["target_note"]}])
        self.assertEqual((rebuilt["kept"], rebuilt["guidance_lost"]), ([], []))

    def test_a_hand_edited_note_is_not_an_unexplained_change(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.edit_json(f".coach/proposals/{W43}.json",
                       lambda doc: doc["sessions"][0]["exercises"][0].update(target_note=ADJUST))
        self.assertEqual(self.run_coach("propose", "show", W43)["unexplained"], [])
        self.edit_json(f".coach/proposals/{W43}.json",
                       lambda doc: doc["sessions"][0]["exercises"][0]["sets"][0].update(rpe=9))
        self.assertEqual(len(self.run_coach("propose", "show", W43)["unexplained"]), 1)

    def test_a_note_is_checked_and_cleared(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        error = self.note("--session", "session-a", "--exercise", "db_bench_press", "--target-note", "go to 50 kg",
                          expect=1)
        self.assertIn("bare dumbbell number", error["error"]["message"])
        self.note("--week-focus", "two\nlines", expect=2)
        self.note("--target-note", "x", expect=2)
        self.note("--session", "session-a", "--exercise", "bb_back_squat", "--target-note", "x")
        cleared = self.note("--session", "session-a", "--exercise", "bb_back_squat", "--target-note", "")
        self.assertIsNone(cleared["lines"][0]["target_note"])
        draft, _, _ = propose.load_proposal(self.root, W43)
        self.assertIsNone(draft["sessions"][0]["exercises"][0]["target_note"])


ROMANIAN = {"exercise_id": "db_romanian_deadlift", "load_mode": "per_hand_x2",
            "sets": [{"count": 3, "type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7}],
            "rest_seconds": 120, "superset_id": None, "cues": None, "constraints": [],
            "scheme": {"name": "double_progression", "params": {}}, "start_load": None}


class DesignCalibrationTest(RebuildCase):
    """A designed program whose new Romanian deadlift has no start load and no history."""

    def setUp(self):
        super().setUp()
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"].update(db_romanian_deadlift={
            "hevy_template_id": "F0000006", "load_mode": "per_hand_x2", "load_mode_proposed": "per_hand_x2",
            "confidence": "high", "avoid": None}))
        self.edit_json("data/program.json", lambda doc: doc["sessions"][0]["exercises"].append(dict(ROMANIAN)))
        self.run_coach("program", "validate")

    def test_an_unknown_first_load_carries_calibration_guidance_to_the_sheet(self):
        proposed = self.run_coach("propose", "week", "--week", "2026-W43")
        note = line(proposed["overlay"], "db_romanian_deadlift")["target_note"]
        self.assertEqual(note, propose.CALIBRATION_NOTE)
        self.assertIsNone(DIGIT.search(note))
        self.assertIsNone(line(proposed["overlay"], "bb_back_squat")["target_note"])
        self.override(W43, "session-a", "db_romanian_deadlift", "--load", "20", reason="agreed first load")
        draft, _, _ = propose.load_proposal(self.root, W43)
        chosen = line(draft, "db_romanian_deadlift")["target_note"]
        self.assertEqual(chosen, propose.CALIBRATION_SET_NOTE)
        self.assertIsNone(DIGIT.search(chosen))
        self.run_coach("propose", "finalize", "--proposal", W43)
        self.run_coach("overlay", "approve", W43)
        self.run_coach("sheets", "render", "--overlay", W43)
        sheet = (self.root / SHEETS).read_text(encoding="utf-8")
        self.assertIn(f"Note: {chosen}", bullet(sheet, "Romanian Deadlift (Dumbbell)"))
        self.assertNotIn("agreed first load", sheet)

    def test_a_coach_note_survives_a_first_load_override(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.run_coach("propose", "note", "--proposal", W43, "--session", "session-a", "--exercise",
                       "db_romanian_deadlift", "--target-note", ADJUST)
        self.override(W43, "session-a", "db_romanian_deadlift", "--load", "20", reason="agreed first load")
        draft, _, _ = propose.load_proposal(self.root, W43)
        self.assertEqual(line(draft, "db_romanian_deadlift")["target_note"], ADJUST)


class StarterGuidanceTest(StarterCase):
    def finalized(self, starter_id, experience="intermediate", edit=None):
        root = self.with_templates()
        set_athlete(root, experience=experience)
        found = self.ok(root, "starters", "draft", starter_id)
        if edit is not None:
            path = root / found["path"]
            draft = json.loads(path.read_text(encoding="utf-8"))
            edit(draft["program"])
            path.write_text(json.dumps(draft), encoding="utf-8")
        adopted = self.ok(root, "program", "adopt", "--input", str(root / found["path"]))
        modes = {entry["exercise_id"]: entry["load_mode"] for _, entry in lines(found["draft"]["program"])}
        for entry in adopted["unconfirmed"]:
            self.ok(root, "library", "set-mode", entry["exercise_id"], modes[entry["exercise_id"]])
        proposed = self.ok(root, "propose", "week", "--week", STARTER_WEEK)
        doc = self.ok(root, "propose", "finalize", "--proposal", proposed["id"])["overlay"]
        return root, doc

    def test_a_starter_calibration_line_carries_its_guidance_to_the_sheet(self):
        root, doc = self.finalized("full-body-3")
        session = next(s for s in doc["sessions"] if s["session_id"] == "full-body-a")
        squat = next(e for e in session["exercises"] if e["exercise_id"] == "bb_back_squat")
        self.assertEqual(squat["target_note"], propose.CALIBRATION_NOTE)
        self.assertNotIn(propose.RAMP_NOTE, squat["target_note"])
        text = sheets.render_sheets(root, doc["id"])
        self.assertIn(f"Note: {propose.CALIBRATION_NOTE}", bullet(text, "Back Squat (Barbell)"))
        self.assertNotIn("reps left", text)

    def test_a_wave_line_keeps_its_scheme_note_and_rep_out_cap(self):
        def training_max(program_doc):
            press = next(s for s in program_doc["sessions"] if s["id"] == "press-day")["exercises"][0]
            press["scheme"]["params"]["training_max"] = 60

        root, doc = self.finalized("wave-3wk", edit=training_max)
        session = next(s for s in doc["sessions"] if s["session_id"] == "press-day")
        press = session["exercises"][0]
        self.assertTrue(press["target_note"].startswith("Wave week 1 of 3"), press["target_note"])
        text = sheets.render_sheets(root, doc["id"])
        self.assertIn("Note: Wave week 1 of 3", bullet(text, "Overhead Press (Barbell)"))
        cap = next(s["rpe"] for s in press["sets"] if s.get("rep_out"))
        self.assertIn(f"| stop at {render._number(cap)} |", text)

    def test_a_beginner_gets_a_ramp_note_on_each_sessions_first_loaded_lift_and_the_key(self):
        root, doc = self.finalized("full-body-3", experience="beginner")
        for session in doc["sessions"]:
            with self.subTest(session=session["session_id"]):
                first, *rest = session["exercises"]
                self.assertIn(propose.RAMP_NOTE, first["target_note"])
                self.assertTrue(all(propose.RAMP_NOTE not in (e["target_note"] or "") for e in rest))
        self.assertIsNone(DIGIT.search(propose.RAMP_NOTE))
        text = sheets.render_sheets(root, doc["id"])
        self.assertEqual(text.count(propose.RAMP_NOTE), len(doc["sessions"]))
        self.assertIn("RPE 8 ≈ 2 reps left", text)


class BeginnerWarmupTest(RebuildCase):
    """The nohevy program with warm-up sets on the squat, for a beginner."""

    def setUp(self):
        super().setUp()
        set_experience(self.root, "beginner")

        def warm_up(doc):
            squat = doc["sessions"][0]["exercises"][0]
            squat["sets"].insert(0, {"count": 2, "type": "warmup", "reps": 5})

        self.edit_json("data/program.json", warm_up)
        self.run_coach("program", "validate")

    def test_warm_up_sets_stand_in_for_the_ramp_and_stay_off_the_working_sets(self):
        proposed = self.run_coach("propose", "week", "--week", "2026-W43")["overlay"]
        squat, row = line(proposed, "bb_back_squat"), line(proposed, "db_single_arm_row")
        self.assertNotIn(propose.RAMP_NOTE, squat["target_note"] or "")
        self.assertEqual(row["target_note"], propose.RAMP_NOTE)
        self.assertEqual([s["type"] for s in squat["sets"]][:2], ["warmup", "warmup"])
        self.assertEqual(len([s for s in squat["sets"] if overlay.is_working(s)]), 3)
        self.assertTrue(all(s.get("load") is None for s in squat["sets"] if s["type"] == "warmup"))
        doc = self.run_coach("propose", "finalize", "--proposal", W43)["overlay"]
        self.run_coach("overlay", "approve", W43)
        text = sheets.render_sheets(self.root, doc["id"])
        self.assertIn("| Back Squat (Barbell) | 2×5 warm-up |", text)
        self.assertEqual(render.target_line(line(doc, "bb_back_squat")).split(" @ ")[0], "Target: 3×5")


class GuidanceWorkflowTest(unittest.TestCase):
    """The skills set guidance through `propose note` and keep audit reasons off the athlete's pages."""

    def test_program_week_sets_the_week_focus_and_line_guidance_before_finalizing(self):
        brief = flat(step_text("program-week", "brief.md"))
        self.assertIn("in the draft as its week focus, replacing the generic line (compute.md step 3)", brief)
        self.assertIn("never the override reason. A rebuild keeps both", brief)
        compute = flat(step_text("program-week", "compute.md"))
        self.assertIn("python3 -m coach propose note --proposal <id>` with `--week-focus", compute)
        for flag in ("--target-note", "--focus", "--cues"):
            self.assertIn(flag, compute)
        self.assertIn("The reason stays your audit, off the athlete's pages; **athlete guidance** (brief.md step 1) "
                      "needs none", compute)

    def test_calibration_and_beginner_warm_ups_name_no_invented_numbers(self):
        brief = flat(step_text("program-week", "brief.md"))
        self.assertIn("never swap in an unexplained number", brief)
        self.assertIn("the program's warm-up sets, or the qualitative ramp note", brief)
        self.assertIn("no warm-up loads or percentages the coach has not agreed", brief)
        self.assertIn("Guess no number for them", flat(step_text("new-program", "starter.md")))
        self.assertIn("calibration note in place of a guessed number", flat(step_text("new-program", "design.md")))


if __name__ == "__main__":
    unittest.main()
