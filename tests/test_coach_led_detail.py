"""Coach-led sessions: recorded length, effort, modality and timing, and trainer cancellations (C17, C41, C43, C48).

Every test runs on the `block` fixture: Session A (heavy squat) on Mondays, Session B on Thursdays and the
coach-led `pt-tue` on Tuesdays, each week W36 to W41 trained and its PT session annotated done.
"""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from coach import block, cardio, dates, history, jsonio, migrate
from tests.support import INSTANCES, run_cli
from tests.support.history import read_json, write_json
from tests.support.skills import flat, step_text

BLOCK = INSTANCES / "block"
NOW = "2026-10-11T18:00:00Z"
W40_SUNDAY, W41_MONDAY, W41_TUESDAY = "2026-10-04", "2026-10-05", "2026-10-06"


class CoachLedCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(BLOCK, self.root)

    def coach(self, *argv, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": NOW})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def data(self, *argv):
        return self.coach(*argv)["data"]

    def pt(self, day, *extra, expect=0):
        envelope = self.coach("history", "annotate", "--kind", "external", "--external", "pt-tue", "--date", day,
                              "--source", "test", *extra, expect=expect)
        return envelope["data"]["annotation"] if expect == 0 else envelope

    def edit(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)

    def cardio_bouts(self, week):
        found = self.data("cardio", "week", "--week", week)
        return found, [b for b in found["bouts"] if b["kind"] == "external"]

    def structure_week(self, week):
        return self.data("structure", "week", "--week", week)

    def pt_rows(self, report):
        return [row for row in report["sessions"] if row.get("external_id") == "pt-tue"]

    def interference(self, week="2026-W41"):
        return [f["message"] for f in self.data("interference", "check", "--week", week)["flags"]]


class EffortTest(CoachLedCase):
    def test_recorded_length_and_effort_replace_the_defaults(self):
        self.pt(W41_TUESDAY, "--done", "--minutes", "45", "--rpe", "8")
        data, [pt] = self.cardio_bouts("2026-W41")
        self.assertEqual(data["external"]["done"], 1)
        self.assertEqual(pt["minutes"], 45)
        self.assertEqual(pt["srpe"], {"rpe": 8, "load": 360, "method": "athlete", "minutes_method": "athlete"})

    def test_missing_detail_uses_defaults_labelled_as_defaults(self):
        _, [pt] = self.cardio_bouts("2026-W41")
        self.assertEqual(pt["minutes"], 60)
        self.assertEqual(pt["srpe"], {"rpe": 6, "load": 360, "method": "external_default",
                                      "minutes_method": "external_default"})

    def test_partial_detail_defaults_only_the_missing_field(self):
        self.pt(W41_TUESDAY, "--done", "--rpe", "8")
        _, [pt] = self.cardio_bouts("2026-W41")
        self.assertEqual((pt["minutes"], pt["srpe"]), (60, {"rpe": 8, "load": 480, "method": "athlete",
                                                            "minutes_method": "external_default"}))
        self.pt(W41_TUESDAY, "--done", "--minutes", "45")
        _, [pt] = self.cardio_bouts("2026-W41")
        self.assertEqual((pt["minutes"], pt["srpe"]), (45, {"rpe": 6, "load": 270, "method": "external_default",
                                                            "minutes_method": "athlete"}))

    def test_a_note_alone_invents_no_effort_or_modality(self):
        self.pt(W40_SUNDAY, "--done", "--note", "brutal")
        _, pts = self.cardio_bouts("2026-W40")
        brutal = next(b for b in pts if b["date"] == W40_SUNDAY)
        self.assertEqual((brutal["modality"], brutal["quality"]), (None, False))
        self.assertEqual(brutal["srpe"]["method"], "external_default")
        self.assertEqual(self.interference(), [])

    def test_a_start_is_stored_as_a_timestamp_on_its_date(self):
        found = self.pt(W41_TUESDAY, "--done", "--start-time", "07:30", "--minutes", "45")
        self.assertEqual(found["start"], "2026-10-06T07:30:00Z")
        refused = self.pt(W41_TUESDAY, "--done", "--start-time", "2026-10-07T07:30:00", expect=1)
        self.assertIn("falls on 2026-10-07", refused["error"]["message"])


class ModalityTest(CoachLedCase):
    def test_explicit_conditioning_is_a_quality_activity_before_heavy_lower_work(self):
        self.pt(W40_SUNDAY, "--done", "--modality", "conditioning", "--rpe", "8")
        data, pts = self.cardio_bouts("2026-W40")
        conditioning = next(b for b in pts if b["date"] == W40_SUNDAY)
        self.assertEqual((conditioning["modality"], conditioning["quality"], conditioning["quality_basis"]),
                         ("conditioning", True, "kind"))
        self.assertEqual(data["external"], {"done": 2, "conditioning": 1})
        [message] = self.interference()
        self.assertIn('quality_before_heavy_lower: coach-led conditioning "PT" (2026-10-04) is the day before', message)

    def test_conditioning_on_a_lifting_day_raises_the_same_day_check(self):
        self.pt(W41_MONDAY, "--done", "--modality", "conditioning", "--rpe", "8")
        messages = self.interference()
        self.assertTrue(any(m.startswith("same_day: Session A") and "coach-led conditioning" in m
                            for m in messages), messages)

    def test_lifting_or_unrecorded_modality_is_never_a_quality_activity(self):
        for extra in (("--modality", "lifting", "--rpe", "8"), ("--rpe", "8")):
            with self.subTest(extra=extra):
                self.pt(W40_SUNDAY, "--done", *extra)
                _, pts = self.cardio_bouts("2026-W40")
                self.assertFalse(next(b for b in pts if b["date"] == W40_SUNDAY)["quality"])
                self.assertEqual(self.interference(), [])

    def test_a_mixed_session_counts_once_and_carries_its_conditioning_part(self):
        self.pt(W40_SUNDAY, "--done", "--modality", "mixed", "--rpe", "8", "--minutes", "50")
        data, pts = self.cardio_bouts("2026-W40")
        mixed = [b for b in pts if b["date"] == W40_SUNDAY]
        self.assertEqual(len(mixed), 1)
        self.assertEqual((mixed[0]["modality"], mixed[0]["quality"], mixed[0]["minutes"]), ("mixed", True, 50))
        self.assertEqual(mixed[0]["srpe"]["load"], 400)
        self.assertEqual(data["srpe"]["total"], sum(b["srpe"]["load"] for b in data["bouts"]))
        self.assertEqual(data["conditioning"]["count"], 0)
        self.assertEqual(data["external"], {"done": 2, "conditioning": 1})
        self.assertEqual(self.structure_week("2026-W40")["trained"], 3)
        [message] = self.interference()
        self.assertIn("quality_before_heavy_lower: PT (2026-10-04) is the day before", message)

    def test_a_mixed_session_is_never_judged_against_itself(self):
        self.pt(W41_TUESDAY, "--done", "--modality", "mixed", "--rpe", "8")
        self.assertEqual(self.interference(), [])

    def test_only_lifting_counts_as_the_last_lifting_day(self):
        before = date(2026, 10, 5)
        self.assertEqual(history.last_lifting_date(self.root, before), date(2026, 10, 1))
        cases = (("conditioning", date(2026, 10, 1)), ("mixed", date(2026, 10, 4)), ("lifting", date(2026, 10, 4)))
        for modality, expected in cases:
            with self.subTest(modality=modality):
                self.pt(W40_SUNDAY, "--done", "--modality", modality)
                self.assertEqual(history.last_lifting_date(self.root, before), expected)


class CancellationTest(CoachLedCase):
    def test_a_trainer_cancellation_removes_the_obligation_and_keeps_a_hard_week(self):
        self.pt(W41_TUESDAY, "--trainer-cancelled", "trainer off sick")
        report = self.structure_week("2026-W41")
        self.assertEqual((report["planned"], report["trained"]), (2, 2))
        [row] = self.pt_rows(report)
        self.assertEqual((row["status"], row["cancellation"]), ("cancelled", {"by": "trainer",
                                                                             "reason": "trainer off sick"}))
        self.assertEqual(report["muscles"]["lats"]["delivered"], report["muscles"]["lats"]["planned"])
        self.assertEqual(block.classify(self.root, "2026-10-05", today=date(2026, 10, 11)), "hard")
        _, pts = self.cardio_bouts("2026-W41")
        self.assertEqual(pts, [])

    def test_a_plain_not_done_stays_an_uncompleted_obligation(self):
        self.pt(W41_TUESDAY, "--not-done", "--note", "cancelled")
        report = self.structure_week("2026-W41")
        self.assertEqual((report["planned"], report["trained"]), (3, 2))
        self.assertEqual(self.pt_rows(report)[0]["status"], "not_done")
        self.assertEqual(block.classify(self.root, "2026-10-05", today=date(2026, 10, 11)), "partial")

    def test_cancelling_every_obligation_pauses_the_count(self):
        self.edit("data/program.json", lambda doc: [s.update(tier="optional") for s in doc["sessions"]])
        self.pt(W41_TUESDAY, "--trainer-cancelled", "gym closed")
        weeks = self.data("block", "close", "--week", "2026-W41")["weeks"]
        self.assertEqual([w["class"] for w in weeks], ["hard"] * 5 + ["partial"])
        last = weeks[-1]
        self.assertEqual((last["planned"], last["trained"], last["as_prescribed"]), (0, 0, 0))
        self.assertEqual(last["count_after"], weeks[-2]["count_after"])
        ledger = read_json(self.root / "data" / "blocks.json")
        self.assertEqual(len(ledger["blocks"]), 1)

    def test_a_cancellation_ahead_and_repeated_updates_stay_one_occurrence(self):
        self.pt("2026-10-13", "--trainer-cancelled", "trainer away")
        self.pt("2026-10-13", "--trainer-cancelled", "trainer away all week")
        report = self.structure_week("2026-W42")
        [row] = self.pt_rows(report)
        self.assertEqual((row["status"], row["cancellation"]["reason"]), ("cancelled", "trainer away all week"))
        self.assertEqual(report["planned"], 0)
        proposal = cardio.bouts(self.root, dates.Span(date(2026, 10, 12), date(2026, 10, 18)), "proposal",
                                today=date(2026, 10, 11))
        self.assertEqual([b for b in proposal if b.kind == "external"], [])
        self.pt(W41_TUESDAY, "--done", "--rpe", "7")
        self.pt(W41_TUESDAY, "--done", "--rpe", "8")
        data, pts = self.cardio_bouts("2026-W41")
        self.assertEqual((data["external"]["done"], [b["srpe"]["rpe"] for b in pts]), (1, [8]))
        self.assertEqual(len(self.pt_rows(self.structure_week("2026-W41"))), 1)

    def test_a_session_without_a_weekday_keeps_one_occurrence_per_date(self):
        self.edit("data/program.json", lambda doc: doc["external_sessions"][0].update(weekday=None))
        self.pt("2026-10-07", "--not-done")
        self.pt("2026-10-07", "--trainer-cancelled", "double booked")
        report = self.structure_week("2026-W41")
        self.assertEqual([(r["date"], r["status"]) for r in self.pt_rows(report)],
                         [("2026-10-06", "done"), ("2026-10-07", "cancelled")])
        self.assertEqual((report["planned"], report["trained"]), (3, 3))

    def test_withdrawing_or_correcting_a_cancellation_restores_the_obligation(self):
        cancelled = self.pt(W41_TUESDAY, "--trainer-cancelled", "wrong week")
        self.coach("history", "annotate", "--kind", "external", "--withdraws", cancelled["id"], "--source", "test")
        report = self.structure_week("2026-W41")
        self.assertEqual((report["planned"], report["trained"]), (3, 3))
        self.pt(W41_TUESDAY, "--trainer-cancelled", "trainer ill")
        self.pt(W41_TUESDAY, "--not-done")
        report = self.structure_week("2026-W41")
        self.assertEqual((report["planned"], report["trained"]), (3, 2))
        self.assertEqual(block.classify(self.root, "2026-10-05", today=date(2026, 10, 11)), "partial")

    def test_the_check_in_card_states_the_cancellation(self):
        self.pt(W41_TUESDAY, "--trainer-cancelled", "trainer off sick")
        card = self.data("checkin", "prepare")["card"]
        [row] = [r for r in card["sessions"]["external"] if r["date"] == W41_TUESDAY]
        self.assertEqual((row["status"], row["done"], row["cancellation"]["reason"]),
                         ("cancelled", False, "trainer off sick"))
        field = next(f for f in card["fields"] if f["id"] == "coach_led")
        self.assertIn("cancelled by the trainer (trainer off sick), so not a miss", field["prefill"])


class RecordRulesTest(CoachLedCase):
    def refused(self, *extra, expect=1):
        return self.pt(W41_TUESDAY, *extra, expect=expect)["error"]["message"]

    def test_a_cancellation_cannot_be_done(self):
        self.assertIn("leave out --done", self.refused("--trainer-cancelled", "x", "--done", expect=2))
        path = self.root / "batch.json"
        path.write_text(json.dumps([{"kind": "external", "date": W41_TUESDAY, "external_id": "pt-tue",
                                     "done": True, "note": None,
                                     "cancellation": {"by": "trainer", "reason": "x"}}]), encoding="utf-8")
        envelope = self.coach("history", "annotate", "--input", str(path), expect=1)
        self.assertIn("needs done false", envelope["error"]["message"])

    def test_effort_and_modality_describe_only_a_session_that_happened(self):
        self.assertIn("not marked done", self.refused("--not-done", "--rpe", "8"))
        self.assertIn("not marked done", self.refused("--trainer-cancelled", "x", "--modality", "lifting"))

    def test_the_detail_fields_belong_only_to_external_annotations(self):
        envelope = self.coach("history", "annotate", "--kind", "miss", "--date", W41_MONDAY, "--session",
                              "session-a", "--rpe", "8", expect=1)
        self.assertIn("rpe belong only to an external annotation", envelope["error"]["message"])


class MigrationTest(CoachLedCase):
    def test_v1_annotations_migrate_with_their_meaning_unchanged(self):
        before = self.structure_week("2026-W41")
        self.pt(W41_TUESDAY, "--not-done")
        expected = self.structure_week("2026-W41")
        self.edit("data/history/annotations.json", lambda doc: doc.update(schema_version=1))
        self.assertEqual(self.coach("structure", "week", "--week", "2026-W41", expect=1)["error"]["message"]
                         .count("migrate run"), 1)
        files = self.data("migrate", "run")["files"]
        self.assertEqual([(f["path"], f["from"], f["to"]) for f in files],
                         [("data/history/annotations.json", 1, 2)])
        doc = read_json(self.root / "data" / "history" / "annotations.json")
        self.assertEqual(doc["schema_version"], jsonio.current_version(jsonio.load_schema("annotations")))
        self.assertTrue(all(set(a) <= {"id", "kind", "created_at", "source", "reason", "date", "external_id", "done",
                                       "note"} for a in doc["annotations"]))
        self.assertEqual(self.structure_week("2026-W41"), expected)
        self.assertNotEqual(before["trained"], expected["trained"])

    def test_the_step_is_registered(self):
        [step] = migrate.registry().documents["annotations"].steps
        self.assertEqual((step.from_version, step.to_version), (1, 2))


class SkillTextTest(unittest.TestCase):
    def test_the_check_in_records_only_stated_detail_and_trainer_cancellations(self):
        step = flat(step_text("check-in", "sunday-message.md"))
        self.assertIn("how long and how hard it was, and whether the trainer cancelled it", step)
        self.assertIn("Add only the detail the reply states: `duration_minutes`, `rpe` (session RPE), `modality`", step)
        self.assertIn('a word like "brutal" stays in the note', step)
        self.assertIn('"cancellation": {"by": "trainer", "reason": R}`: not a miss', step)


if __name__ == "__main__":
    unittest.main()
