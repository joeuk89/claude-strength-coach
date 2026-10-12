"""Rebuilding a week from the agreed plan: changes against the prior prescription, midweek carry-over, structural
rebuilds and the draft lifecycle (contract C24, C25)."""

import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from coach import propose
from coach.plugins import base
from tests.support import INSTANCES, run_cli
from tests.support.skills import flat, step_text

NOHEVY = INSTANCES / "nohevy"
LOG = Path("data") / "log" / "workouts.jsonl"
SUNDAY = "2026-10-18T19:00:00Z"
MONDAY_EVENING = "2026-10-19T19:45:00Z"
WEEKLY = "2026-10-19-weekly"
PUSH_UP_SLOT = {"exercise_id": "push_up", "load_mode": "bodyweight",
                "sets": [{"count": 2, "type": "normal", "rep_range": {"start": 6, "end": 12}, "rpe": 7}],
                "rest_seconds": 90, "superset_id": None, "cues": None, "constraints": [],
                "scheme": {"name": "double_progression", "params": {}}, "start_load": 0}


def workout(day, session_id, exercises, overlay_id="2026-10-12-weekly"):
    """A manual-log workout line; `exercises` are (exercise_id, load_mode, [(value, reps, rpe)])."""
    return {"schema_version": 1, "kind": "workout", "id": f"manual:{day}-{session_id}-1",
            "logged_at": f"{day}T19:30:00Z", "date": day, "session_id": session_id, "overlay_id": overlay_id,
            "duration_minutes": 55, "notes": "",
            "exercises": [{"exercise_id": exercise_id, "load_mode": load_mode, "unit": "kg", "notes": "",
                           "sets": [{"type": "normal", "reps": reps, "rpe": rpe, "value": value,
                                     "duration_seconds": None, "distance_meters": None}
                                    for value, reps, rpe in sets]}
                          for exercise_id, load_mode, sets in exercises]}


W42 = (workout("2026-10-12", "session-a", [("bb_back_squat", "total", [(100, 5, 7)] * 3),
                                           ("db_bench_press", "per_hand_x2", [(25, 9, 8)] * 3)]),
       workout("2026-10-15", "session-b", [("db_single_arm_row", "single_implement", [(30, 10, 8)] * 3),
                                           ("pull_up", "bodyweight", [(0, 8, 8)] * 3)]))


def line(doc, exercise_id, day=None):
    return next(e for s in doc["sessions"] for e in s["exercises"]
                if e["exercise_id"] == exercise_id and day in (None, s["date"]))


class RebuildCase(unittest.TestCase):
    """The nohevy instance with week 2026-W42 trained at squat 100 and row 30."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "instance"
        shutil.copytree(NOHEVY, self.root)
        self.log(*W42, now=SUNDAY)

    def run_coach(self, *argv, now=SUNDAY, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env={"COACH_NOW": now})
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope["data"] if expect == 0 else envelope

    def log(self, *workouts, now):
        with (self.root / LOG).open("a", encoding="utf-8") as handle:
            for found in workouts:
                handle.write(json.dumps(found) + "\n")
        self.run_coach("history", "sync", now=now)

    def override(self, proposal_id, session_id, exercise_id, *change, reason, now=SUNDAY):
        return self.run_coach("propose", "override", "--proposal", proposal_id, "--session", session_id,
                              "--exercise", exercise_id, *change, "--reason", reason, now=now)

    def rows(self, proposal_id, now=SUNDAY):
        return {(r["date"], r["exercise_id"]): r for r in self.run_coach("propose", "show", proposal_id,
                                                                          now=now)["lines"]}

    def agree_w43(self):
        """W43 proposed, squat overridden to 110 and row held at 30, finalized and approved."""
        proposed = self.run_coach("propose", "week", "--week", "2026-W43")
        self.assertEqual(proposed["id"], WEEKLY)
        self.override(WEEKLY, "session-a", "bb_back_squat", "--load", "110", reason="test jump")
        self.override(WEEKLY, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)
        self.run_coach("overlay", "approve", WEEKLY)
        return proposed

    def edit_json(self, relative, change):
        path = self.root / relative
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def add_push_ups(self):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"].update(push_up={
            "hevy_template_id": "F0000005", "load_mode": "bodyweight", "load_mode_proposed": "bodyweight",
            "confidence": "high", "avoid": None}))
        self.edit_json("data/program.json", lambda doc: doc["sessions"][0]["exercises"].append(PUSH_UP_SLOT))
        self.run_coach("program", "validate")

    def overlay(self, overlay_id):
        return json.loads((self.root / "data" / "overlays" / f"{overlay_id}.json").read_text(encoding="utf-8"))

    def snapshot(self, folder):
        return {p.name: p.read_bytes() for p in (self.root / folder).glob("*.json")}


class ChangeTest(RebuildCase):
    def test_overrides_compare_with_the_prior_agreed_prescription(self):
        proposed = {(r["date"], r["exercise_id"]): r for r in self.run_coach("propose", "week", "--week",
                                                                              "2026-W43")["lines"]}
        self.assertEqual(proposed[("2026-10-19", "bb_back_squat")]["change"], "100 → 102.5")
        self.override(WEEKLY, "session-a", "bb_back_squat", "--load", "110", reason="test jump")
        self.override(WEEKLY, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        self.override(WEEKLY, "session-a", "db_bench_press", "--sets", "4x8@25 rpe8", reason="more volume")
        rows = self.rows(WEEKLY)
        self.assertEqual(rows[("2026-10-19", "bb_back_squat")]["change"], "100 → 110")
        self.assertIsNone(rows[("2026-10-22", "db_single_arm_row")]["change"])
        self.assertEqual(rows[("2026-10-19", "db_bench_press")]["change"], "3×8–10 RPE 8 → 4×8 RPE 8")

    def test_a_first_prescription_is_named_without_an_earlier_load(self):
        (self.root / "data" / "overlays" / "2026-10-12-weekly.json").unlink()
        rows = self.run_coach("propose", "week", "--week", "2026-W43", "--dry-run")["lines"]
        squat = next(r for r in rows if r["exercise_id"] == "bb_back_squat")
        self.assertEqual(squat["change"], propose.FIRST_PRESCRIPTION)

    def test_change_text_reads_the_shape_and_the_load(self):
        def sets(count, load, reps=5, rpe=7):
            return (base.SetSpec(reps=reps, rpe=rpe, load=load),) * count

        self.assertIsNone(propose.change_text(sets(3, 100), sets(3, 100), "total", "kg"))
        self.assertEqual(propose.change_text(sets(3, 100), sets(4, 105), "total", "kg"),
                         "3×5 RPE 7 → 4×5 RPE 7, 100 → 105")
        self.assertEqual(propose.change_text(sets(3, 100), sets(3, 100, rpe=8), "total", "kg"),
                         "3×5 RPE 7 → 3×5 RPE 8")
        backoff = (base.SetSpec(reps=5, rpe=7, load=100),) + sets(2, 90)
        heavier = (base.SetSpec(reps=5, rpe=7, load=100),) + sets(2, 92.5)
        self.assertEqual(propose.change_text(backoff, heavier, "total", "kg"),
                         "1×5 @ 100 RPE 7, 2×5 @ 90 RPE 7 → 1×5 @ 100 RPE 7, 2×5 @ 92.5 RPE 7")
        self.assertEqual(propose.change_text(None, sets(3, 100), "total", "kg"), propose.FIRST_PRESCRIPTION)


class MidweekTest(RebuildCase):
    def setUp(self):
        super().setUp()
        self.agree_w43()
        self.log(workout("2026-10-19", "session-a", [("bb_back_squat", "total", [(110, 5, 8)] * 3),
                                                     ("db_bench_press", "per_hand_x2", [(25, 9, 8)] * 3)],
                         overlay_id=WEEKLY), now=MONDAY_EVENING)

    def test_a_rebuild_after_todays_session_starts_tomorrow_and_keeps_the_approved_hold(self):
        data = self.run_coach("propose", "week", "--kind", "midweek", "--week", "2026-W43", now=MONDAY_EVENING)
        self.assertEqual((data["id"], data["span"]), ("2026-10-20-midweek", {"start": "2026-10-20",
                                                                             "end": "2026-10-25"}))
        doc = data["overlay"]
        self.assertEqual([(s["date"], s["session_id"]) for s in doc["sessions"]], [("2026-10-22", "session-b")])
        row = line(doc, "db_single_arm_row")
        self.assertEqual({s["load"]["per_hand"] for s in row["sets"] if s["type"] == "normal"}, {30})
        self.assertEqual(row["override"]["reason"], "hold at 30")
        self.assertIsNone(row["change"])
        self.assertIn("override_kept", [f["code"] for f in doc["flags"] if f["exercise_id"] == "db_single_arm_row"])

        self.run_coach("propose", "finalize", "--proposal", data["id"], now=MONDAY_EVENING)
        decisions = json.loads((self.root / "data" / "decisions.json").read_text(encoding="utf-8"))["decisions"]
        self.assertEqual([d["overlay_id"] for d in decisions if d["scope"]["exercise_id"] == "db_single_arm_row"],
                         [WEEKLY])

    def test_a_session_still_to_train_today_stays_in_the_rebuild(self):
        monday, thursday = date(2026, 10, 19), date(2026, 10, 22)
        planned = base.SchedulePlan(sessions=((monday, "session-a"), (monday, "session-b"),
                                              (thursday, "session-b")))
        with mock.patch.object(propose, "plan_schedule", return_value=planned):
            data = self.run_coach("propose", "week", "--kind", "midweek", "--week", "2026-W43", "--dry-run",
                                  now=MONDAY_EVENING)
        self.assertEqual(data["span"]["start"], "2026-10-19")
        self.assertEqual([(s["date"], s["session_id"]) for s in data["overlay"]["sessions"]],
                         [("2026-10-19", "session-b"), ("2026-10-22", "session-b")])


def working(row):
    return [(s.get("reps"), s["load"]["per_hand"]) for s in row["sets"] if s["type"] == "normal"]


class KeptOverrideTest(RebuildCase):
    """When a midweek run keeps an approved one-week override, and how a transform treats it (C25)."""

    MIDWEEK = "2026-10-20-midweek"

    def log_monday(self, overlay_id):
        self.log(workout("2026-10-19", "session-a", [("bb_back_squat", "total", [(110, 5, 8)] * 3),
                                                     ("db_bench_press", "per_hand_x2", [(25, 9, 8)] * 3)],
                         overlay_id=overlay_id), now=MONDAY_EVENING)

    def midweek_row(self, *transform):
        data = self.run_coach("propose", "week", "--kind", "midweek", *transform, "--week", "2026-W43",
                              "--dry-run", now=MONDAY_EVENING)
        self.assertEqual(data["id"], self.MIDWEEK)
        doc = data["overlay"]
        codes = [f["code"] for f in doc["flags"] if f["exercise_id"] == "db_single_arm_row"]
        return line(doc, "db_single_arm_row"), codes

    def test_a_withdrawn_decision_stops_the_override_being_kept(self):
        self.agree_w43()
        self.log_monday(WEEKLY)
        decisions = json.loads((self.root / "data" / "decisions.json").read_text(encoding="utf-8"))["decisions"]
        [row_decision] = [d for d in decisions if d["scope"]["exercise_id"] == "db_single_arm_row"]
        self.run_coach("decisions", "withdraw", row_decision["id"], "--reason", "row back on the scheme",
                       now=MONDAY_EVENING)
        row, codes = self.midweek_row()
        self.assertIsNone(row["override"])
        self.assertNotIn("override_kept", codes)

    def test_a_light_transform_cuts_the_kept_override(self):
        self.agree_w43()
        self.log_monday(WEEKLY)
        row, codes = self.midweek_row("--transform", "light")
        self.assertEqual(row["override"]["reason"], "hold at 30")
        self.assertIn("override_kept", codes)
        self.assertEqual(working(row), [(10, 30)] * 2)

    def test_a_deload_overrides_sets_are_kept_only_by_a_transform_run_and_cut_once(self):
        deload = self.run_coach("propose", "week", "--kind", "deload", "--week", "2026-W43")
        self.override(deload["id"], "session-b", "db_single_arm_row", "--load", "25", reason="lighter row")
        flags = self.run_coach("propose", "show", deload["id"])["flags"]
        for found in flags:
            if found["severity"] == "block" and not found["resolved"]:
                self.run_coach("propose", "resolve", "--proposal", deload["id"], "--flag", found["ref"],
                               "--resolution", "synthetic: accepted for the test")
        self.run_coach("propose", "finalize", "--proposal", deload["id"])
        self.run_coach("overlay", "approve", deload["id"])
        approved = working(line(self.overlay(deload["id"]), "db_single_arm_row"))
        self.log_monday(deload["id"])

        plain, codes = self.midweek_row()
        self.assertIsNone(plain["override"])
        self.assertNotIn("override_kept", codes)

        light, codes = self.midweek_row("--transform", "light")
        self.assertEqual(light["override"]["reason"], "lighter row")
        self.assertIn("override_kept", codes)
        self.assertEqual(working(light), approved)


class StructuralRebuildTest(RebuildCase):
    def setUp(self):
        super().setUp()
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.override(WEEKLY, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)
        self.add_push_ups()

    def test_approval_refuses_an_overlay_built_before_the_structural_edit(self):
        before = self.snapshot("data/overlays")
        refused = self.run_coach("overlay", "approve", WEEKLY, expect=3)
        self.assertIn(f"propose rebuild --proposal {WEEKLY}", refused["error"]["message"])
        self.assertIn("push_up", json.dumps(refused["error"]["details"]))
        self.assertEqual(self.snapshot("data/overlays"), before)
        self.run_coach("propose", "finalize", "--proposal", WEEKLY, expect=3)

    def test_a_rebuild_adds_the_new_slot_and_keeps_unrelated_overrides(self):
        data = self.run_coach("propose", "rebuild", "--proposal", WEEKLY)
        self.assertEqual(data["id"], WEEKLY)
        self.assertEqual(data["overlay_removed"], f"data/overlays/{WEEKLY}.json")
        self.assertEqual([(k["exercise_id"], k["reason"]) for k in data["kept"]], [("db_single_arm_row", "hold at 30")])
        self.assertEqual(data["lost"], [])
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)
        self.run_coach("overlay", "approve", WEEKLY)
        doc = self.overlay(WEEKLY)
        push_up = line(doc, "push_up")
        self.assertEqual(sum(1 for s in push_up["sets"] if s["type"] == "normal"), 2)
        row = line(doc, "db_single_arm_row")
        self.assertEqual({s["load"]["per_hand"] for s in row["sets"] if s["type"] == "normal"}, {30})
        self.assertEqual(row["override"]["reason"], "hold at 30")


class RebuildCarryTest(RebuildCase):
    def test_a_resolved_block_flag_survives_a_rebuild(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        data = self.override(WEEKLY, "session-a", "bb_back_squat", "--load", "130", reason="test a heavy single week")
        [block] = [f for f in data["flags"] if f["severity"] == "block"]
        self.assertEqual(block["code"], "unearned_load")
        self.run_coach("propose", "resolve", "--proposal", WEEKLY, "--flag", block["ref"], "--resolution",
                       "synthetic: accepted for the test")
        self.add_push_ups()
        rebuilt = self.run_coach("propose", "rebuild", "--proposal", WEEKLY)
        self.assertEqual(rebuilt["resolutions_kept"], 1)
        self.assertEqual(self.run_coach("propose", "show", WEEKLY)["unresolved_blocks"], [])
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)

    def test_an_override_on_a_slot_the_program_dropped_is_listed_as_lost(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        self.override(WEEKLY, "session-a", "db_bench_press", "--sets", "4x8@25 rpe8", reason="more volume")
        self.override(WEEKLY, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        self.edit_json("data/program.json", lambda doc: doc["sessions"][0].update(exercises=[
            e for e in doc["sessions"][0]["exercises"] if e["exercise_id"] != "db_bench_press"]))
        data = self.run_coach("propose", "rebuild", "--proposal", WEEKLY)
        self.assertEqual([(r["exercise_id"], r["reason"]) for r in data["lost"]],
                         [("db_bench_press", "more volume")])
        self.assertEqual([r["exercise_id"] for r in data["kept"]], ["db_single_arm_row"])
        self.assertNotIn("db_bench_press", [r["exercise_id"] for r in data["lines"]])

    def test_an_explained_one_week_line_the_program_lacks_passes_finalize(self):
        self.run_coach("propose", "week", "--week", "2026-W43")
        path = self.root / ".coach" / "proposals" / f"{WEEKLY}.json"
        draft = json.loads(path.read_text(encoding="utf-8"))
        pull_up = line(draft, "pull_up")
        added = dict(pull_up, override={"reason": "extra pulling this week", "proposed_sets": pull_up["sets"]})
        draft["sessions"][0]["exercises"].append(added)
        path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
        self.override(WEEKLY, "session-b", "db_single_arm_row", "--load", "30", reason="hold at 30")
        self.run_coach("propose", "finalize", "--proposal", WEEKLY)
        self.assertIn("pull_up", [e["exercise_id"] for e in self.overlay(WEEKLY)["sessions"][0]["exercises"]])


class SameDayMidweekRebuildTest(RebuildCase):
    """A midweek draft proposed on Monday morning, rebuilt that evening after Monday's session was logged."""

    MIDWEEK = "2026-10-19-midweek"

    def setUp(self):
        super().setUp()
        self.agree_w43()
        self.run_coach("propose", "week", "--kind", "midweek", "--week", "2026-W43", now="2026-10-19T12:00:00Z")
        self.log(workout("2026-10-19", "session-a", [("bb_back_squat", "total", [(110, 5, 8)] * 3)],
                         overlay_id=WEEKLY), now=MONDAY_EVENING)

    def test_the_rebuild_keeps_the_draft_id_and_leaves_out_the_trained_session(self):
        data = self.run_coach("propose", "rebuild", "--proposal", self.MIDWEEK, now=MONDAY_EVENING)
        self.assertEqual((data["id"], data["span"]["start"]), (self.MIDWEEK, "2026-10-19"))
        self.assertEqual([(s["date"], s["session_id"]) for s in data["overlay"]["sessions"]],
                         [("2026-10-22", "session-b")])
        self.run_coach("propose", "finalize", "--proposal", self.MIDWEEK, now=MONDAY_EVENING)
        self.run_coach("overlay", "approve", self.MIDWEEK, now=MONDAY_EVENING)

    def test_a_next_morning_rebuild_leaves_out_the_session_trained_earlier_in_the_span(self):
        tuesday = "2026-10-20T08:00:00Z"
        self.add_push_ups()
        data = self.run_coach("propose", "rebuild", "--proposal", self.MIDWEEK, now=tuesday)
        self.assertEqual((data["id"], data["span"]["start"]), (self.MIDWEEK, "2026-10-19"))
        self.assertEqual([(s["date"], s["session_id"]) for s in data["overlay"]["sessions"]],
                         [("2026-10-22", "session-b")])
        self.run_coach("propose", "finalize", "--proposal", self.MIDWEEK, now=tuesday)
        self.run_coach("overlay", "approve", self.MIDWEEK, now=tuesday)
        state = json.loads((self.root / "data" / "state.json").read_text(encoding="utf-8"))
        pending_here = sorted(key for key, entry in state["scheme_state"].items()
                              if (entry.get("pending") or {}).get("overlay_id") == self.MIDWEEK)
        self.assertTrue(pending_here)
        self.assertFalse([key for key in pending_here if key.startswith("session-a/")], pending_here)


class DraftLifecycleTest(RebuildCase):
    def setUp(self):
        super().setUp()
        self.agree_w43()
        self.run_coach("propose", "week", "--kind", "midweek", "--week", "2026-W43", now="2026-10-19T12:00:00Z")
        self.log(workout("2026-10-19", "session-a", [("bb_back_squat", "total", [(110, 5, 8)] * 3)],
                         overlay_id=WEEKLY), now=MONDAY_EVENING)
        newer = self.run_coach("propose", "week", "--kind", "midweek", "--week", "2026-W43", now=MONDAY_EVENING)
        self.run_coach("propose", "finalize", "--proposal", newer["id"], now=MONDAY_EVENING)
        self.run_coach("overlay", "approve", newer["id"], now=MONDAY_EVENING)

    def proposal_section(self, now):
        sections = {s["id"]: s for s in self.run_coach("status", now=now)["sections"]}
        return sections.get("proposal")

    def test_a_superseded_draft_asks_for_no_finalize_and_cannot_be_finalized(self):
        for now in ("2026-10-22T08:00:00Z", "2026-11-30T08:00:00Z"):
            with self.subTest(now=now):
                found = self.proposal_section(now)
                self.assertEqual(found["level"], "info")
                self.assertEqual(found["data"]["stale"], ["2026-10-19-midweek"])
                self.assertNotIn("finalize", " ".join(found["lines"]))
        before = self.snapshot("data/overlays")
        refused = self.run_coach("propose", "finalize", "--proposal", "2026-10-19-midweek",
                                 now="2026-10-22T08:00:00Z", expect=3)
        self.assertIn("2026-10-20-midweek", refused["error"]["message"])
        self.assertEqual(self.snapshot("data/overlays"), before)

    def test_an_ended_draft_cannot_be_finalized(self):
        refused = self.run_coach("propose", "finalize", "--proposal", "2026-10-19-midweek",
                                 now="2026-11-30T08:00:00Z", expect=3)
        self.assertIn("ended on 2026-10-25", refused["error"]["message"])

    def test_a_stale_draft_or_an_approved_overlay_is_not_rebuilt(self):
        before = self.snapshot("data/overlays")
        stale = self.run_coach("propose", "rebuild", "--proposal", "2026-10-19-midweek",
                               now="2026-10-22T08:00:00Z", expect=3)
        self.assertIn("is stale", stale["error"]["message"])
        approved = self.run_coach("propose", "rebuild", "--proposal", WEEKLY, now="2026-10-22T08:00:00Z", expect=3)
        self.assertIn("already approved", approved["error"]["message"])
        self.assertEqual(self.snapshot("data/overlays"), before)

    def test_discard_lists_the_active_standing_decisions_the_draft_made(self):
        data = self.run_coach("propose", "week", "--week", "2026-W44", now="2026-10-25T19:00:00Z")
        made = self.run_coach("propose", "override", "--proposal", data["id"], "--session", "session-a",
                              "--exercise", "bb_back_squat", "--load", "110", "--reason", "hold while the knee settles",
                              "--standing", now="2026-10-25T19:00:00Z")
        discarded = self.run_coach("propose", "discard", "--proposal", data["id"], now="2026-10-25T19:00:00Z")
        self.assertEqual(discarded["standing_decisions"], [made["decision"]["id"]])

    def test_discard_removes_the_draft_and_leaves_approved_work(self):
        overlays, decisions = self.snapshot("data/overlays"), (self.root / "data" / "decisions.json").read_bytes()
        data = self.run_coach("propose", "discard", "--proposal", "2026-10-19-midweek", now="2026-10-22T08:00:00Z")
        self.assertEqual(len(data["removed"]), 3)
        self.assertFalse(data["overlay_kept"])
        self.assertEqual(self.snapshot("data/overlays"), overlays)
        self.assertEqual((self.root / "data" / "decisions.json").read_bytes(), decisions)
        self.assertIsNone(self.proposal_section("2026-10-22T08:00:00Z"))
        self.run_coach("propose", "show", "2026-10-19-midweek", now="2026-10-22T08:00:00Z", expect=1)

    def test_discard_removes_an_unapproved_overlay_and_its_pending_state(self):
        data = self.run_coach("propose", "week", "--week", "2026-W44", now="2026-10-25T19:00:00Z")
        for flag in data["flags"]:
            if flag["severity"] == "block":
                self.run_coach("propose", "resolve", "--proposal", data["id"], "--flag", flag["ref"], "--resolution",
                               "synthetic: accepted for the test", now="2026-10-25T19:00:00Z")
        self.run_coach("propose", "finalize", "--proposal", data["id"], now="2026-10-25T19:00:00Z")
        discarded = self.run_coach("propose", "discard", "--proposal", data["id"], now="2026-10-25T19:00:00Z")
        self.assertIn(f"data/overlays/{data['id']}.json", discarded["removed"])
        self.assertFalse((self.root / "data" / "overlays" / f"{data['id']}.json").exists())
        state = json.loads((self.root / "data" / "state.json").read_text(encoding="utf-8"))
        self.assertTrue(discarded["pending_cleared"])
        self.assertTrue(all(entry["pending"] is None for entry in state["scheme_state"].values()))


class GuidanceTest(unittest.TestCase):
    def test_program_week_rebuilds_after_a_structural_edit_and_discards_stale_drafts(self):
        compute = flat(step_text("program-week", "compute.md"))
        for phrase in ("python3 -m coach propose rebuild --proposal <id>", "python3 -m coach propose discard",
                       "less any session trained today", "with their approved overrides and guidance"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, compute)
        write = flat(step_text("program-week", "write.md"))
        self.assertIn("rebuild and finalize the week's draft as compute.md step 5 says", write)


if __name__ == "__main__":
    unittest.main()
