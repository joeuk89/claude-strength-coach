"""Standing overrides under the week's transform, judged on each session's date (contract C24, C25)."""

from tests.support.history import read_json, write_json
from tests.test_propose import FIRST_ID, ProposeCase, codes, coaching, find_line, working

KEPT = "2x15@60 rpe9"
DELOAD_ID = "2026-10-12-deload"


def squat_lines(doc):
    return [(session["date"], line) for session in doc["sessions"] for line in session["exercises"]
            if line["exercise_id"] == "bb_back_squat"]


class StandingOverrideCase(ProposeCase):
    def setUp(self):
        super().setUp()
        self.propose()

    def stand(self, *extra):
        return self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                          "bb_back_squat", "--sets", KEPT, "--reason", "synthetic: knee settles at 15 reps",
                          "--standing", *extra)["data"]["decision"]


class StandingOverrideTransformTest(StandingOverrideCase):
    def setUp(self):
        super().setUp()
        self.stand()

    def deload(self, *extra):
        return self.propose("--kind", "deload", "--dry-run", *extra)["overlay"]

    def assert_deloaded(self, doc):
        squat = find_line(doc, "bb_back_squat")
        self.assertEqual(squat["override"]["reason"], "synthetic: knee settles at 15 reps")
        self.assertIn("override_standing", codes(doc, "bb_back_squat"))
        sets = working(squat)
        self.assertEqual(len(sets), 1)
        self.assertEqual({s["reps"] for s in sets}, {15})
        self.assertEqual({s["rpe"] for s in sets}, {6})
        for s in sets:
            self.assertLessEqual(coaching(s["load"]), 60 * 0.9 + 1e-9)
            self.assertGreater(coaching(s["load"]), 60 * 0.9 - 2.5 - 1e-9)
        rationale = squat["provenance"]["rationale"]
        self.assertIn("kept as 2×15 @ 60 RPE 9, adjusted for the", rationale)
        self.assertIn("deload: 1×15", rationale)
        return squat

    def test_the_standard_deload_cuts_the_kept_sets_once(self):
        doc = self.deload()
        self.assert_deloaded(doc)
        bench = find_line(doc, "db_bench_press")
        self.assertEqual(len(working(bench)), 2)
        for s in working(bench):
            self.assertLessEqual(coaching(s["load"]), 22.5 * 0.9 + 1e-9)
            self.assertGreater(coaching(s["load"]), 22.5 * 0.9 - 2 - 1e-9)

    def test_a_scheme_deload_gives_the_kept_sets_the_standard_deload(self):
        self.set_scheme("session-a", "bb_back_squat", "wave_531", {"training_max": 100})
        self.assert_deloaded(self.deload("--transform", "scheme"))

    def test_a_light_week_holds_the_kept_load_with_no_set_above_rpe_8(self):
        squat = find_line(self.deload("--transform", "light"), "bb_back_squat")
        sets = working(squat)
        self.assertEqual(len(sets), 1)
        self.assertTrue(all(s["rpe"] <= 8 for s in sets))
        self.assertEqual({coaching(s["load"]) for s in sets}, {60})

    def test_constraints_and_the_illness_cap_still_bind_the_transformed_sets(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
            constraints=[{"kind": "load_cap", "value": 50, "reason": "synthetic knee"}]))
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-a",
                   "--tag", "ill")
        squat = find_line(self.deload("--transform", "light"), "bb_back_squat")
        sets = working(squat)
        self.assertEqual({coaching(s["load"]) for s in sets}, {50})
        self.assertEqual({s["rpe"] for s in sets}, {7})
        self.assertIn("slot load cap 50 (synthetic knee)", squat["provenance"]["rationale"])

    def test_the_constraint_flag_follows_the_kept_sets_not_the_schemes(self):
        for cap, flagged in ((70, False), (50, True)):
            with self.subTest(cap=cap):
                self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat").update(
                    constraints=[{"kind": "load_cap", "value": cap, "reason": "synthetic knee"}]))
                doc = self.propose("--dry-run")["overlay"]
                squat = find_line(doc, "bb_back_squat")
                scheme_sets = working({"sets": squat["override"]["proposed_sets"]})
                self.assertEqual(max(coaching(s["load"]) for s in scheme_sets), cap)
                self.assertEqual("constraint_applied" in codes(doc, "bb_back_squat"), flagged)

    def test_an_ordinary_week_keeps_the_sets_as_chosen(self):
        doc = self.propose("--dry-run")["overlay"]
        squat = find_line(doc, "bb_back_squat")
        self.assertEqual([(s["reps"], coaching(s["load"]), s["rpe"]) for s in working(squat)], [(15, 60, 9)] * 2)
        self.assertNotIn("adjusted for", squat["provenance"]["rationale"])


class StandingOverrideKitTest(StandingOverrideCase):
    def test_the_rationale_names_a_kept_load_the_kit_changes(self):
        self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                   "bb_back_squat", "--sets", "2x15@61 rpe9", "--reason", "synthetic: knee settles at 15 reps",
                   "--standing")
        squat = find_line(self.propose("--dry-run")["overlay"], "bb_back_squat")
        loads = {coaching(s["load"]) for s in working(squat)}
        self.assertEqual(len(loads), 1)
        [load] = loads
        self.assertNotEqual(load, 61)
        self.assertIn(f"the kit makes {load:g}, not 61", squat["provenance"]["rationale"])


class StandingOverrideExpiryTest(StandingOverrideCase):
    def test_an_override_ending_sunday_is_not_kept_for_monday_whenever_the_week_is_proposed(self):
        self.stand("--until", "2026-11-15")
        for now in ("2026-11-15T18:00:00Z", "2026-11-16T06:00:00Z"):
            with self.subTest(now=now):
                doc = self.propose("--dry-run", env={"COACH_NOW": now}, week="2026-W47")["overlay"]
                [(day, squat)] = squat_lines(doc)
                self.assertEqual(day, "2026-11-16")
                self.assertIsNone(squat["override"])
                self.assertNotIn("override_standing", codes(doc, "bb_back_squat"))

    def test_a_span_crossing_the_end_date_keeps_it_only_for_sessions_it_covers(self):
        self.edit_program(lambda doc: doc["schedule"]["params"].update(days={"mon": "session-a", "thu": "session-a"}))
        standing = self.stand("--until", "2026-11-11")
        week = self.propose(env={"COACH_NOW": "2026-11-08T18:00:00Z"}, week="2026-W46")
        monday, thursday = squat_lines(week["overlay"])
        self.assertEqual((monday[0], thursday[0]), ("2026-11-09", "2026-11-12"))
        self.assertEqual(monday[1]["override"]["reason"], standing["reason"])
        self.assertIsNone(thursday[1]["override"])

        draft_path = self.draft_path(week["id"])
        draft = read_json(draft_path)
        line = next(line for session in draft["sessions"] if session["date"] == "2026-11-12"
                    for line in session["exercises"] if line["exercise_id"] == "bb_back_squat")
        line["override"] = {"reason": "synthetic: travel day, lighter", "proposed_sets": line["sets"]}
        line["sets"] = [dict(s, rpe=6) for s in line["sets"]]
        write_json(draft_path, draft)
        data = self.coach("propose", "finalize", "--proposal", week["id"],
                          env={"COACH_NOW": "2026-11-12T06:00:00Z"})["data"]
        self.assertEqual([(d["reason"], d["standing"], d["until"]) for d in data["decisions"]],
                         [("synthetic: travel day, lighter", False, "2026-11-15")])
