"""Rendering an overlay: the check-in's week-ahead region and the Hevy notes (contract C11, C12)."""

import ast
import json
import re
import unittest
from unittest import mock

from coach import render, units
from tests.support import REPO_ROOT, VALID

WEEKLY = "2026-10-12-weekly"
RENDER_MODULE = REPO_ROOT / "coach" / "render.py"
LOAD_NUMBER_KEYS = ("per_hand", "hevy_total", "hevy_kg")


def valid_overlay():
    return json.loads((VALID / "data" / "overlays" / f"{WEEKLY}.json").read_text(encoding="utf-8"))


def note(doc, session, exercise):
    s = doc["sessions"][session]
    return render.render_hevy_note(doc, s, s["exercises"][exercise], exercise == 0)


class HevyNoteTest(unittest.TestCase):
    def test_first_exercise_has_the_week_line(self):
        doc = valid_overlay()
        lines = note(doc, 0, 0).splitlines()
        self.assertEqual(lines[0], f"Wk of 12 Oct: {doc['focus']}")
        self.assertEqual(lines[1], "Target: 3×5 @ 100 kg @ RPE 7")
        self.assertEqual(lines[2], "Cues: brace · knees out")
        self.assertEqual(len(lines), 3)

    def test_db_bench_shows_both_numbers_and_no_warmup(self):
        text = note(valid_overlay(), 0, 1)
        lines = text.splitlines()
        self.assertEqual(lines[0], "Target: 3×8–10 @ 25/hand (Hevy: 50) @ RPE 8")
        self.assertEqual(lines[1], "Focus: pause 1 s on the chest")
        self.assertNotIn("50", text.replace("(Hevy: 50)", ""))
        self.assertNotIn("12.5", text)
        self.assertNotIn("Wk of", text)

    def test_other_modes(self):
        doc = valid_overlay()
        self.assertEqual(note(doc, 1, 0).splitlines()[0], "Wk of 12 Oct: " + doc["focus"])
        self.assertEqual(note(doc, 1, 0).splitlines()[1], "Target: 3×10 @ 30 @ RPE 8")
        self.assertEqual(note(doc, 1, 1).splitlines()[0], "Target: 3×8 @ BW @ RPE 8")

    def test_groups_collapse_and_join(self):
        doc = valid_overlay()
        squat = doc["sessions"][0]["exercises"][0]
        top = json.loads(json.dumps(squat["sets"][1]))
        top.update(rpe=8, load=units.make_load(105, "total", "kg"), reps=3)
        squat["sets"].insert(1, top)
        self.assertEqual(note(doc, 0, 0).splitlines()[1], "Target: 1×3 @ 105 kg @ RPE 8 + 3×5 @ 100 kg @ RPE 7")

    def test_target_is_absolute(self):
        doc = valid_overlay()
        squat = doc["sessions"][0]["exercises"][0]
        self.assertEqual(squat["target_note"], "add 2.5 from last week")
        text = note(doc, 0, 0)
        self.assertNotIn("add 2.5 from last week", text)
        self.assertNotIn(squat["change"], text)

    def test_choose_the_load(self):
        doc = valid_overlay()
        bench = doc["sessions"][0]["exercises"][1]
        bench["sets"] = [{"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7, "load": None}] * 3
        self.assertEqual(note(doc, 0, 1).splitlines()[0], "Target: 3×8–10 @ RPE 7 · choose the load")

    def test_week_label(self):
        self.assertEqual(render.short_date("2026-10-05"), "5 Oct")
        self.assertEqual(render.day_label("2026-10-12"), "Mon 12 Oct")


class WeekAheadTest(unittest.TestCase):
    def test_markers_and_content(self):
        doc = valid_overlay()
        text = render.render_week_ahead(doc)
        lines = text.splitlines()
        self.assertEqual(lines[0], f"<!-- coach:begin overlay {WEEKLY} -->")
        self.assertEqual(lines[-1], f"<!-- coach:end overlay {WEEKLY} -->")
        self.assertIn("### Mon 12 Oct · Session A", text)
        self.assertIn("### Thu 15 Oct · Session B", text)
        self.assertIn("25/hand (Hevy: 50)", text)
        self.assertIn("12.5/hand (Hevy: 25)", text)
        self.assertIn("add 2.5 from last week", text)
        self.assertIn("97.5 → 100", text)
        self.assertIn(doc["focus"], text)
        self.assertIn("loads in kg", text)

    def test_choose_the_load_in_the_load_column(self):
        doc = valid_overlay()
        bench = doc["sessions"][0]["exercises"][1]
        bench["sets"] = [{"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7, "load": None}] * 3
        row = next(line for line in render.render_week_ahead(doc).splitlines() if "db_bench_press" in line)
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[:4], ["db_bench_press", "3×8–10", "choose the load", "7"])

    def test_flags_and_location(self):
        doc = valid_overlay()
        doc["sessions"][1]["location"] = "home"
        doc["flags"] = [{"code": "no_data", "severity": "warn", "session_id": "session-b",
                         "exercise_id": "pull_up", "message": "No history.", "resolved": False,
                         "resolution": None}]
        text = render.render_week_ahead(doc)
        self.assertIn("Location: home", text)
        self.assertIn("no_data", text)
        self.assertIn("No history.", text)

    def test_cells_escape_pipes(self):
        doc = valid_overlay()
        doc["sessions"][0]["exercises"][0]["target_note"] = "a | b"
        self.assertIn("a \\| b", render.render_week_ahead(doc))

    def test_render_is_deterministic(self):
        self.assertEqual(render.render_week_ahead(valid_overlay()), render.render_week_ahead(valid_overlay()))
        self.assertEqual(render.render_overlay(VALID, WEEKLY), render.render_overlay_doc(VALID, valid_overlay()))


class RegionTest(unittest.TestCase):
    REGION = "<!-- coach:begin overlay x-1 -->\nnew\n<!-- coach:end overlay x-1 -->"

    def test_replace_in_place(self):
        text = "# Head\n\n<!-- coach:begin overlay x-1 -->\nold\n<!-- coach:end overlay x-1 -->\n\ntail\n"
        out = render.splice_region(text, "overlay", "x-1", self.REGION)
        self.assertEqual(out, "# Head\n\n" + self.REGION + "\n\ntail\n")
        self.assertEqual(render.splice_region(out, "overlay", "x-1", self.REGION), out)

    def test_insert_at_the_end_of_the_week_ahead_section(self):
        text = "# Check-in\n\n## The week ahead — 12–18 Oct\n\nPlan prose.\n\n## Later\n\nMore.\n"
        out = render.splice_region(text, "overlay", "x-1", self.REGION)
        self.assertEqual(
            out,
            "# Check-in\n\n## The week ahead — 12–18 Oct\n\nPlan prose.\n\n" + self.REGION + "\n\n## Later\n\nMore.\n",
        )
        self.assertEqual(render.splice_region(out, "overlay", "x-1", self.REGION), out)

    def test_append_without_the_section(self):
        out = render.splice_region("# Check-in\nprose", "overlay", "x-1", self.REGION)
        self.assertEqual(out, "# Check-in\nprose\n\n" + self.REGION + "\n")

    def test_find_regions(self):
        text = "a\n" + self.REGION + "\nb\n<!-- coach:begin card c -->\nx\n<!-- coach:end card c -->\n"
        regions = render.find_regions(text, "overlay")
        self.assertEqual([(region_id, text[start:end]) for region_id, start, end in regions], [("x-1", self.REGION)])

    def test_unclosed_region_raises(self):
        with self.assertRaises(ValueError):
            render.find_regions("<!-- coach:begin overlay x-1 -->\nno end\n", "overlay")


class RenderPurityTest(unittest.TestCase):
    """render.py prints loads only through format_load and computes nothing with them (contract C5)."""

    def test_no_access_to_load_numbers(self):
        tree = ast.parse(RENDER_MODULE.read_text(encoding="utf-8"))
        touched = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in LOAD_NUMBER_KEYS:
                touched.append((node.lineno, node.value))
            if isinstance(node, ast.Attribute) and node.attr in LOAD_NUMBER_KEYS:
                touched.append((node.lineno, node.attr))
        self.assertEqual(touched, [], "render.py must not read per_hand, hevy_total or hevy_kg")

    def test_every_printed_load_goes_through_format_load(self):
        doc = valid_overlay()
        bench = doc["sessions"][0]["exercises"][1]
        bench["sets"][1]["load"] = units.make_load(23.75, "per_hand_x2", "kg")
        bench["change"] = None
        printed_loads = [
            s["load"] for session in doc["sessions"] for exercise in session["exercises"]
            for s in exercise["sets"] if s.get("load")
        ]
        calls = []

        def spy(load, show_hevy=True):
            calls.append(load)
            return f"<LOAD{len(calls)}>"

        with mock.patch.object(render, "format_load", side_effect=spy):
            region = render.render_week_ahead(doc)
            notes = "\n".join(
                render.render_hevy_note(doc, s, e, i == 0)
                for s in doc["sessions"] for i, e in enumerate(s["exercises"])
            )
        for value in ("23.75", "47.5", "Hevy", "/hand", "BW"):
            self.assertNotIn(value, region + notes)
        for load in printed_loads:
            self.assertIn(load, calls)
        self.assertTrue(re.search(r"<LOAD\d+>", region))


if __name__ == "__main__":
    unittest.main()
