"""Niggles as data: `coach niggles`, niggle load constraints in `propose week`, escalation (contract C26, C27)."""

import copy
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from coach import flags, library
from coach.activity import records
from tests.support import FIXTURES, INSTANCES, REPO_ROOT, run_cli
from tests.support.history import HistoryCase, read_json, write_json
from tests.support.skills import skill_text, step_text
from tests.test_checkin import CheckinCase
from tests.test_propose import ProposeCase, codes, coaching, find_line, working

PROFILE = FIXTURES / "niggles" / "profile.md"
DIAGNOSES = ("tendin", "strain", "sprain", "tear", "arthritis", "bursitis", "impingement", "diagnos")

MORE_LOAD_PLUGIN = '''
"""A synthetic scheme that adds load and a rep: 30 for 9."""

from coach.plugins import base

API = 1
KIND = "scheme"
NAME = "custom_more"
SUMMARY = "Proposes 30 for 9 reps."
PARAMS = {"schema": {"type": "object", "additionalProperties": False, "properties": {}}, "defaults": {}}
STATE = {"schema": base.EMPTY_SCHEMA, "initial": {}}
FLAGS = {}
CITES = ()


def propose(ctx):
    sets = base.with_reps(base.with_load(base.expand(ctx.slot.sets), 30), 9)
    return base.Proposal(sets=sets, rationale="More load and a rep", derived_from=base.baseline(ctx.exposures),
                         state={})


def decay(ctx, proposal, days_off):
    return base.default_decay(ctx, proposal, days_off)
'''


VERSION = 2


def niggle(niggle_id="n-0001", status="watching", patterns=(), exercises=(), constraints=(), history=None,
           constrain_while=("aggravated", "watching"), area="synthetic left knee"):
    history = history or [{"date": "2026-10-11", "status": status, "note": None, "flare_constraints": None}]
    found = [dict({"value": None, "reason": area}, **c) for c in constraints]
    return {"id": niggle_id, "area": area, "first_noted": history[0]["date"], "last_noted": history[-1]["date"],
            "mentions": len(history), "status": status, "notes": None,
            "applies_to": {"patterns": list(patterns), "exercises": list(exercises), "activity_kinds": []},
            "standing": [{"from": history[0]["date"], "constraints": found, "confirm": None}] if found else [],
            "constrain_while": list(constrain_while), "history": history}


def entries(*statuses):
    """One weekly history entry per status, the first on 2026-08-02."""
    return [{"date": (date(2026, 8, 2) + timedelta(weeks=i)).isoformat(), "status": s, "note": None,
             "flare_constraints": None} for i, s in enumerate(statuses)]


class NiggleCase(HistoryCase):
    def path(self):
        return self.root / "data" / "niggles.json"

    def write_niggles(self, *rows):
        write_json(self.path(), {"schema_version": VERSION, "niggles": list(rows)})

    def rows(self):
        return {row["id"]: row for row in read_json(self.path())["niggles"]}


class AddTest(NiggleCase):
    def test_add_writes_a_row_with_its_history(self):
        data = self.coach("niggles", "add", "--area", "synthetic left knee", "--status", "watching",
                          "--pattern", "squat,lunge", "--exercise", "db_bench_press", "--constraint", "rpe_cap=7",
                          "--note", "deep flexion under load")["data"]
        row = self.rows()["n-0001"]
        self.assertEqual(data["niggle"], row)
        self.assertEqual((row["first_noted"], row["last_noted"], row["mentions"], row["status"]),
                         ("2026-10-11", "2026-10-11", 1, "watching"))
        self.assertEqual(row["applies_to"], {"patterns": ["squat", "lunge"], "exercises": ["db_bench_press"],
                                             "activity_kinds": []})
        self.assertEqual(row["standing"], [{"from": "2026-10-11", "confirm": None, "constraints": [
            {"kind": "rpe_cap", "value": 7, "reason": "synthetic left knee"}]}])
        self.assertEqual(row["constrain_while"], ["aggravated", "watching"])
        self.assertEqual(row["history"], [{"date": "2026-10-11", "status": "watching",
                                           "note": "deep flexion under load", "flare_constraints": None}])

    def test_a_misspelt_pattern_exits_1_listing_the_valid_patterns(self):
        envelope = self.coach("niggles", "add", "--pattern", "squatt", expect=1)
        message = envelope["error"]["message"]
        self.assertIn("squatt", message)
        for pattern in library.PATTERNS:
            self.assertIn(pattern, message)
        self.assertFalse(self.path().exists())

    def test_an_unknown_exercise_id_exits_1(self):
        envelope = self.coach("niggles", "add", "--area", "x", "--exercise", "no_such_lift", expect=1)
        self.assertIn("no_such_lift", envelope["error"]["message"])

    def test_constraints_are_checked(self):
        for bad in ("rpe_cap", "rpe_cap=11", "load_cap=-1", "no_added_load=5", "speed_cap=3"):
            with self.subTest(constraint=bad):
                self.coach("niggles", "add", "--area", "x", "--constraint", bad, expect=1)

    def test_dry_run_writes_nothing(self):
        data = self.coach("niggles", "add", "--area", "x", "--dry-run")["data"]
        self.assertEqual(data["niggle"]["id"], "n-0001")
        self.assertFalse(self.path().exists())


class UpdateTest(NiggleCase):
    def setUp(self):
        super().setUp()
        self.coach("niggles", "add", "--area", "synthetic left knee", "--status", "watching")

    def test_activity_kinds_are_stored(self):
        self.coach("niggles", "update", "n-0001", "--activity-kinds", "run")
        self.assertEqual(self.rows()["n-0001"]["applies_to"]["activity_kinds"], ["run"])

    def test_an_unknown_activity_kind_exits_1_naming_the_allowed_kinds(self):
        message = self.coach("niggles", "update", "n-0001", "--activity-kinds", "jog", expect=1)["error"]["message"]
        self.assertIn("jog", message)
        for kind in records.KINDS:
            self.assertIn(kind, message)

    def test_a_mention_bumps_the_count_and_adds_one_history_entry_per_day(self):
        later = {"COACH_NOW": "2026-10-18T18:00:00Z"}
        self.coach("niggles", "update", "n-0001", "--mention", "--status", "aggravated", "--note", "sharp", env=later)
        self.coach("niggles", "update", "n-0001", "--mention", "--note", "sharper", env=later)
        row = self.rows()["n-0001"]
        self.assertEqual((row["mentions"], row["last_noted"], row["status"]), (2, "2026-10-18", "aggravated"))
        self.assertEqual(row["history"][-1], {"date": "2026-10-18", "status": "aggravated", "note": "sharper",
                                              "flare_constraints": None})
        self.assertEqual(len(row["history"]), 2)

    def test_applies_to_and_constraints_change_without_a_history_entry(self):
        self.coach("niggles", "update", "n-0001", "--pattern", "hinge", "--constraint", "no_added_load",
                   "--constraint", "load_cap=60", "--constrain-while", "aggravated,watching,easing")
        row = self.rows()["n-0001"]
        self.assertEqual(row["applies_to"]["patterns"], ["hinge"])
        self.assertEqual([c["kind"] for c in row["standing"][-1]["constraints"]], ["no_added_load", "load_cap"])
        self.assertEqual(row["constrain_while"], ["aggravated", "watching", "easing"])
        self.assertEqual(len(row["history"]), 1)
        self.coach("niggles", "update", "n-0001", "--clear-constraints")
        self.assertEqual(self.rows()["n-0001"]["standing"][-1]["constraints"], [])

    def test_resolve_keeps_the_row(self):
        self.coach("niggles", "resolve", "n-0001", "--note", "gone", env={"COACH_NOW": "2026-10-25T18:00:00Z"})
        row = self.rows()["n-0001"]
        self.assertEqual(row["status"], "resolved")
        self.assertEqual(row["history"][-1], {"date": "2026-10-25", "status": "resolved", "note": "gone",
                                              "flare_constraints": None})

    def test_an_unknown_id_exits_1(self):
        self.coach("niggles", "update", "n-0009", "--mention", expect=1)

    def test_update_and_resolve_dry_runs_write_nothing(self):
        before = self.path().read_bytes()
        self.coach("niggles", "update", "n-0001", "--mention", "--dry-run")
        self.coach("niggles", "resolve", "n-0001", "--dry-run")
        self.assertEqual(self.path().read_bytes(), before)


class ListTest(NiggleCase):
    def test_list_shows_status_activity_and_escalation(self):
        self.write_niggles(
            niggle("n-0001", "chronic", patterns=["vertical_push"], constraints=[{"kind": "no_added_load"}],
                   area="synthetic left shoulder", history=entries("chronic")),
            niggle("n-0002", "watching", history=entries("watching", "watching", "watching")),
            niggle("n-0003", "resolved", history=entries("watching", "resolved")))
        data = self.coach("niggles", "list")["data"]
        rows = {row["id"]: row for row in data["niggles"]}
        self.assertEqual(rows["n-0001"]["status"], "chronic")
        self.assertTrue(rows["n-0001"]["constraints_active"])
        self.assertIsNone(rows["n-0001"]["escalate"])
        self.assertIn("three check-ins", rows["n-0002"]["escalate"])
        self.assertFalse(rows["n-0003"]["constraints_active"])
        self.assertEqual([f["code"] for f in data["flags"]], ["niggle_escalate"])
        self.assertEqual([r["id"] for r in self.coach("niggles", "list", "--open")["data"]["niggles"]],
                         ["n-0001", "n-0002"])

    def test_no_file_lists_nothing(self):
        self.assertEqual(self.coach("niggles", "list")["data"]["niggles"], [])


class ConstraintsCommandTest(NiggleCase):
    def test_lists_each_program_line_a_niggle_constrains(self):
        self.write_niggles(niggle(patterns=["squat"], constraints=[{"kind": "rpe_cap", "value": 7}]))
        data = self.coach("niggles", "constraints")["data"]
        self.assertEqual(data["lines"], [{
            "session_id": "session-a", "exercise_id": "bb_back_squat",
            "constraints": [{"kind": "rpe_cap", "value": 7, "reason": "synthetic left knee", "source": "n-0001",
                             "scope": "standing", "since": "2026-10-11"}]}])
        self.assertEqual(self.coach("niggles", "constraints", "--session", "session-b")["data"]["lines"], [])
        self.coach("niggles", "constraints", "--session", "session-z", expect=1)


def on(day):
    return {"COACH_NOW": f"{day}T18:00:00Z"}


class DatedLimitsTest(NiggleCase):
    """A chronic squat limit of RPE 8, a flare to RPE 7 on 2026-10-06, settled on 2026-10-09."""

    def setUp(self):
        super().setUp()
        self.coach("niggles", "add", "--area", "synthetic lower back", "--status", "chronic", "--exercise",
                   "bb_back_squat", "--constraint", "rpe_cap=8", env=on("2026-10-01"))
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--mention", "--flare-constraint",
                   "rpe_cap=7", env=on("2026-10-06"))

    def squat_limits(self, *extra, day="2026-10-11"):
        data = self.coach("niggles", "constraints", *extra, env=on(day))["data"]
        found = [line for line in data["lines"] if line["exercise_id"] == "bb_back_squat"]
        return [(c["kind"], c["value"], c["scope"], c["since"], c["source"]) for line in found
                for c in line["constraints"]]

    def settle(self, day="2026-10-09"):
        self.coach("niggles", "update", "n-0001", "--status", "chronic", "--note", "settled", env=on(day))

    def test_the_flare_adds_its_limit_beside_the_standing_one(self):
        self.assertEqual(self.squat_limits(day="2026-10-07"), [
            ("rpe_cap", 8, "standing", "2026-10-01", "n-0001"), ("rpe_cap", 7, "flare", "2026-10-06", "n-0001")])
        row = self.rows()["n-0001"]
        self.assertEqual(row["standing"][-1]["constraints"][0]["value"], 8)
        self.assertEqual(row["history"][-1]["flare_constraints"][0]["value"], 7)

    def test_settling_restores_the_standing_limit_and_the_flare_date_still_reads_the_flare(self):
        self.settle()
        self.assertEqual(self.squat_limits(), [("rpe_cap", 8, "standing", "2026-10-01", "n-0001")])
        self.assertEqual(self.squat_limits("--date", "2026-10-06"), [
            ("rpe_cap", 8, "standing", "2026-10-01", "n-0001"), ("rpe_cap", 7, "flare", "2026-10-06", "n-0001")])
        self.assertEqual(self.squat_limits("--date", "2026-09-30"), [])

    def test_a_later_report_in_the_same_flare_keeps_its_limit(self):
        self.coach("niggles", "update", "n-0001", "--mention", "--note", "still sore", env=on("2026-10-08"))
        self.assertIn(("rpe_cap", 7, "flare", "2026-10-06", "n-0001"), self.squat_limits(day="2026-10-08"))
        self.coach("niggles", "update", "n-0001", "--clear-flare-constraints", "--note", "easing",
                   env=on("2026-10-10"))
        self.assertEqual(self.squat_limits(), [("rpe_cap", 8, "standing", "2026-10-01", "n-0001")])

    def test_a_flare_limit_without_a_report_is_refused_so_it_never_counts_as_a_check_in(self):
        for change in (("--flare-constraint", "rpe_cap=6"), ("--clear-flare-constraints",)):
            with self.subTest(change=change):
                self.coach("niggles", "update", "n-0001", *change, env=on("2026-10-08"), expect=1)
        row = self.coach("niggles", "list", env=on("2026-10-08"))["data"]["niggles"][0]
        self.assertEqual([entry["date"] for entry in row["history"]], ["2026-10-01", "2026-10-06"])

    def test_an_explicit_standing_edit_persists_past_later_flares(self):
        self.settle()
        self.coach("niggles", "update", "n-0001", "--constraint", "rpe_cap=7.5", env=on("2026-10-10"))
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--flare-constraint", "rpe_cap=6",
                   env=on("2026-10-13"))
        self.settle("2026-10-16")
        self.assertEqual(self.squat_limits(day="2026-10-17"), [("rpe_cap", 7.5, "standing", "2026-10-10", "n-0001")])
        self.assertEqual(self.squat_limits("--date", "2026-10-07", day="2026-10-17"), [
            ("rpe_cap", 8, "standing", "2026-10-01", "n-0001"), ("rpe_cap", 7, "flare", "2026-10-06", "n-0001")])

    def test_resolving_ends_every_limit_and_takes_no_flare_limit(self):
        self.coach("niggles", "update", "n-0001", "--status", "resolved", "--flare-constraint", "rpe_cap=6",
                   env=on("2026-10-10"), expect=1)
        self.coach("niggles", "resolve", "n-0001", env=on("2026-10-10"))
        self.assertEqual(self.squat_limits(), [])
        self.assertEqual(self.squat_limits("--date", "2026-10-06")[1][2], "flare")

    def test_list_shows_the_limits_in_force_today(self):
        row = self.coach("niggles", "list", env=on("2026-10-07"))["data"]["niggles"][0]
        self.assertEqual([(c["value"], c["scope"]) for c in row["in_force"]], [(8, "standing"), (7, "flare")])
        self.assertIsNone(row["confirm"])

    def test_a_standing_edit_cannot_be_backdated_and_a_bad_date_exits_2(self):
        self.coach("niggles", "update", "n-0001", "--constraint", "rpe_cap=7", env=on("2026-09-30"), expect=1)
        self.coach("niggles", "constraints", "--date", "2026-13-01", expect=2)


class ProposalConstraintTest(ProposeCase):
    def write_niggles(self, *rows):
        write_json(self.root / "data" / "niggles.json", {"schema_version": VERSION, "niggles": list(rows)})

    def set_pattern(self, exercise_id, pattern):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"][exercise_id].update(pattern=pattern))

    def niggle_flags(self, doc, code="constraint_applied"):
        return [f for f in doc["flags"] if f["code"] == code and "n-0001" in f["message"]]

    def test_an_rpe_cap_on_squat_caps_every_squat_line_while_watching(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat")["sets"][0].update(rpe=8))
        self.write_niggles(niggle(patterns=["squat"], constraints=[{"kind": "rpe_cap", "value": 7}]))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "bb_back_squat"))}, {7})
        [flag] = self.niggle_flags(doc)
        self.assertEqual(flag["exercise_id"], "bb_back_squat")
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "db_bench_press"))}, {8})

    def test_easing_does_not_apply(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat")["sets"][0].update(rpe=8))
        self.write_niggles(niggle(status="easing", patterns=["squat"], constraints=[{"kind": "rpe_cap", "value": 7}]))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "bb_back_squat"))}, {8})
        self.assertEqual(self.niggle_flags(doc), [])

    def test_no_added_load_on_hinge_holds_the_load_and_lets_reps_progress(self):
        self.write_plugin("custom_more", MORE_LOAD_PLUGIN)
        self.set_scheme("session-a", "db_bench_press", "custom_more")
        self.set_pattern("db_bench_press", "hinge")
        self.write_niggles(niggle(patterns=["hinge"], constraints=[{"kind": "no_added_load"}], area="synthetic back"))
        doc = self.propose("--dry-run")["overlay"]
        line = working(find_line(doc, "db_bench_press"))
        self.assertEqual({coaching(s["load"]) for s in line}, {22.5})
        self.assertEqual({s["reps"] for s in line}, {9})
        self.assertEqual(len(self.niggle_flags(doc)), 1)

    def test_a_named_exercise_matches_whatever_its_pattern(self):
        self.write_niggles(niggle(exercises=["pull_up"], constraints=[{"kind": "load_cap", "value": 0}]))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {0})
        self.assertEqual([f["exercise_id"] for f in self.niggle_flags(doc)], ["pull_up"])

    def test_a_chronic_niggle_applies_whatever_constrain_while_says_and_never_escalates(self):
        self.write_plugin("custom_more", MORE_LOAD_PLUGIN)
        self.set_scheme("session-a", "db_bench_press", "custom_more")
        self.set_pattern("db_bench_press", "vertical_push")
        self.write_niggles(niggle(status="chronic", patterns=["vertical_push"], constraints=[{"kind": "no_added_load"}],
                                  constrain_while=["aggravated"], area="synthetic left shoulder",
                                  history=entries(*["watching"] * 9, "chronic")))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {22.5})
        self.assertEqual(len(self.niggle_flags(doc)), 1)
        self.assertNotIn("niggle_escalate", codes(doc))

    def test_three_watching_entries_raise_niggle_escalate(self):
        self.write_niggles(niggle(patterns=["squat"], history=entries("watching", "watching", "watching")))
        doc = self.propose("--dry-run")["overlay"]
        [flag] = self.niggle_flags(doc, "niggle_escalate")
        self.assertEqual((flag["severity"], flag["session_id"], flag["exercise_id"]), ("warn", None, None))
        self.assertIn("qualified professional", flag["message"])
        for word in DIAGNOSES:
            self.assertNotIn(word, flag["message"].lower())

    def test_worsening_to_aggravated_escalates_and_easing_does_not(self):
        self.write_niggles(niggle(status="aggravated", history=entries("easing", "aggravated")))
        self.assertEqual(len(self.niggle_flags(self.propose("--dry-run")["overlay"], "niggle_escalate")), 1)
        self.write_niggles(niggle(status="easing", history=entries("watching", "watching", "easing")))
        self.assertEqual(self.niggle_flags(self.propose("--dry-run")["overlay"], "niggle_escalate"), [])

    def test_the_strictest_of_two_niggles_binds_and_both_stay_in_force(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat")["sets"][0].update(rpe=8))
        self.write_niggles(niggle(patterns=["squat"], constraints=[{"kind": "rpe_cap", "value": 7}]),
                           niggle("n-0002", exercises=["bb_back_squat"], constraints=[{"kind": "rpe_cap", "value": 6}],
                                  area="synthetic right hip"))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "bb_back_squat"))}, {6})
        [flag] = [f for f in doc["flags"] if f["code"] == "constraint_applied" and f["exercise_id"] == "bb_back_squat"]
        self.assertIn("n-0002 RPE cap 6 (synthetic right hip)", flag["message"])
        lines = self.coach("niggles", "constraints")["data"]["lines"]
        squat = next(line for line in lines if line["exercise_id"] == "bb_back_squat")
        self.assertEqual(sorted((c["source"], c["value"]) for c in squat["constraints"]), [("n-0001", 7), ("n-0002", 6)])

    def test_a_flare_limit_tighter_than_the_standing_one_binds(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "bb_back_squat")["sets"][0].update(rpe=8))
        row = niggle(status="aggravated", exercises=["bb_back_squat"], constraints=[{"kind": "rpe_cap", "value": 7.5}],
                     history=[{"date": "2026-10-11", "status": "aggravated", "note": None,
                               "flare_constraints": [{"kind": "rpe_cap", "value": 6.5, "reason": "synthetic knee"}]}])
        self.write_niggles(row)
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "bb_back_squat"))}, {6.5})
        self.assertIn("flare limit from 2026-10-11", " ".join(f["message"] for f in self.niggle_flags(doc)))

    def test_an_invalid_niggles_file_stops_the_proposal(self):
        self.write_niggles(niggle(patterns=["squatt"]))
        envelope = self.propose("--dry-run", expect=1)
        self.assertIn("niggles.json", envelope["error"]["message"])


class ImportTest(NiggleCase):
    def setUp(self):
        super().setUp()
        shutil.copy(PROFILE, self.root / "profile.md")

    def test_dry_run_maps_each_table_row_and_lists_the_section_lines(self):
        before = (self.root / "profile.md").read_bytes()
        data = self.coach("niggles", "import", "--from-profile", "--dry-run")["data"]
        self.assertFalse(self.path().exists())
        self.assertEqual([(r["id"], r["area"], r["first_noted"], r["last_noted"], r["mentions"], r["status"],
                           r["notes"]) for r in data["niggles"]],
                         [("n-0001", "Synthetic left knee", "2026-09-14", "2026-10-11", 3, "watching",
                           "deep flexion under load"),
                          ("n-0002", "Synthetic lower back", "2026-08-03", "2026-08-17", 2, "resolved", None)])
        for row in data["niggles"]:
            self.assertEqual(row["standing"], [])
            self.assertEqual(row["applies_to"], {"patterns": [], "exercises": [], "activity_kinds": []})
        self.assertEqual(data["lines"], [{"index": 1, "text": "Synthetic left shoulder: no overhead pressing."},
                                         {"index": 2, "text": "Synthetic right wrist, mostly settled."}])
        self.assertEqual((self.root / "profile.md").read_bytes(), before)

    def test_a_real_run_writes_niggles_and_leaves_the_profile(self):
        before = (self.root / "profile.md").read_bytes()
        self.coach("niggles", "import", "--from-profile")
        self.assertEqual(sorted(self.rows()), ["n-0001", "n-0002"])
        self.assertEqual((self.root / "profile.md").read_bytes(), before)
        self.coach("check", "--only", "niggles_schema")
        self.coach("niggles", "import", "--from-profile", expect=1)

    def test_chronic_lines_become_chronic_rows(self):
        data = self.coach("niggles", "import", "--from-profile", "--chronic", "1", "--dry-run")["data"]
        chronic = [r for r in data["niggles"] if r["status"] == "chronic"]
        self.assertEqual(len(chronic), 1)
        self.assertEqual(chronic[0]["area"], "Synthetic left shoulder: no overhead pressing.")
        self.assertEqual(chronic[0]["applies_to"], {"patterns": [], "exercises": [], "activity_kinds": []})
        self.assertEqual(chronic[0]["standing"], [])
        self.assertEqual(len(data["niggles"]), 3)
        self.assertNotIn("Synthetic right wrist, mostly settled.", [r["area"] for r in data["niggles"]])

    def test_an_index_past_the_lines_exits_1(self):
        self.coach("niggles", "import", "--from-profile", "--chronic", "3", "--dry-run", expect=1)

    def test_a_profile_without_the_section_imports_nothing(self):
        (self.root / "profile.md").write_text("# Athlete profile\n\nSynthetic.\n", encoding="utf-8")
        data = self.coach("niggles", "import", "--from-profile", "--dry-run")["data"]
        self.assertEqual((data["niggles"], data["lines"]), ([], []))

    def test_an_unreadable_row_exits_1_naming_it(self):
        text = PROFILE.read_text(encoding="utf-8").replace("| 3 | watching", "| three | watching")
        (self.root / "profile.md").write_text(text, encoding="utf-8")
        envelope = self.coach("niggles", "import", "--from-profile", "--dry-run", expect=1)
        self.assertIn("Synthetic left knee", json.dumps(envelope["error"]))


V1_ROWS = [
    {"id": "n-0001", "area": "synthetic lower back", "first_noted": "2026-09-01", "last_noted": "2026-10-06",
     "mentions": 2, "status": "aggravated", "notes": None,
     "applies_to": {"patterns": [], "exercises": ["bb_back_squat"], "activity_kinds": []},
     "constraints": [{"kind": "rpe_cap", "value": 7, "reason": "synthetic lower back"}],
     "constrain_while": ["aggravated", "watching"],
     "history": [{"date": "2026-09-01", "status": "chronic", "note": None},
                 {"date": "2026-10-06", "status": "aggravated", "note": "flared"}]},
    {"id": "n-0002", "area": "synthetic left knee", "first_noted": "2026-09-14", "last_noted": "2026-09-14",
     "mentions": 1, "status": "watching", "notes": None,
     "applies_to": {"patterns": ["lunge"], "exercises": [], "activity_kinds": []},
     "constraints": [{"kind": "load_cap", "value": 20, "reason": "synthetic left knee"}],
     "constrain_while": ["aggravated", "watching"],
     "history": [{"date": "2026-09-14", "status": "watching", "note": None}]},
    {"id": "n-0003", "area": "synthetic wrist", "first_noted": "2026-09-14", "last_noted": "2026-09-14",
     "mentions": 1, "status": "watching", "notes": None,
     "applies_to": {"patterns": [], "exercises": [], "activity_kinds": []}, "constraints": [],
     "constrain_while": ["aggravated", "watching"],
     "history": [{"date": "2026-09-14", "status": "watching", "note": None}]},
]


class MigrationTest(NiggleCase):
    def setUp(self):
        super().setUp()
        write_json(self.path(), {"schema_version": 1, "niggles": copy.deepcopy(V1_ROWS)})

    def test_one_limit_list_becomes_a_standing_version_and_a_flared_row_asks_for_confirmation(self):
        report = self.coach("migrate", "run")["data"]
        rows = self.rows()
        self.assertEqual(read_json(self.path())["schema_version"], VERSION)
        knee, wrist, back = rows["n-0002"], rows["n-0003"], rows["n-0001"]
        self.assertEqual(knee["standing"], [{"from": "2026-09-14", "constraints": V1_ROWS[1]["constraints"],
                                             "confirm": None}])
        self.assertEqual(wrist["standing"], [])
        self.assertEqual(back["standing"][0]["constraints"], V1_ROWS[0]["constraints"])
        self.assertEqual(back["standing"][0]["from"], "2026-09-01")
        self.assertIn("confirm", back["standing"][0]["confirm"])
        self.assertIn("niggles update n-0001 --constraint", back["standing"][0]["confirm"])
        self.assertEqual({entry["flare_constraints"] for row in rows.values() for entry in row["history"]}, {None})
        self.assertEqual(list(back), ["id", "area", "first_noted", "last_noted", "mentions", "status", "notes",
                                      "applies_to", "standing", "constrain_while", "history"])
        self.assertTrue(any("n-0001" in note for note in report["notes"]))
        self.assertFalse(any("n-0002" in note for note in report["notes"]))

    def test_no_limit_is_weakened_on_any_date(self):
        self.coach("migrate", "run")
        for day in ("2026-09-01", "2026-10-06", "2026-10-11"):
            with self.subTest(day=day):
                lines = self.coach("niggles", "constraints", "--date", day)["data"]["lines"]
                squat = next(line for line in lines if line["exercise_id"] == "bb_back_squat")
                self.assertEqual([(c["kind"], c["value"]) for c in squat["constraints"]], [("rpe_cap", 7)])

    def test_status_asks_to_confirm_the_standing_limit_until_it_is_set(self):
        self.coach("migrate", "run")
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        self.assertIn("n-0001", sections["niggles"]["data"]["confirm"])
        self.assertTrue(any("confirm these are the standing limits" in line for line in sections["niggles"]["lines"]))
        self.coach("niggles", "update", "n-0001", "--constraint", "rpe_cap=8")
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        self.assertEqual(sections["niggles"]["data"]["confirm"], [])


class RegistryTest(unittest.TestCase):
    def test_niggle_escalate_is_registered(self):
        code = flags.registry()["niggle_escalate"]
        self.assertEqual((code.owner, code.severities, code.structural), ("R-27", ("warn",), False))


class CheckTest(unittest.TestCase):
    def check(self, root):
        code, envelope, _ = run_cli(["--root", str(root), "check", "--only", "niggles_schema"])
        return code, envelope["data"]["results"]

    def test_niggles_schema_skips_fails_and_passes(self):
        code, results = self.check(INSTANCES / "valid")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["skip"]))
        code, results = self.check(INSTANCES / "niggles-invalid")
        self.assertEqual(code, 1)
        messages = " ".join(r["message"] for r in results)
        self.assertIn("$.niggles[0].applies_to.patterns[0]", messages)
        self.assertIn("squatt", messages)
        self.assertIn("no_such_exercise", messages)
        self.assertEqual({r["path"] for r in results}, {"data/niggles.json"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "niggles-invalid", root)
            path = root / "data" / "niggles.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["niggles"][0]["applies_to"].update(patterns=["squat"], exercises=["bb_back_squat"])
            path.write_text(json.dumps(doc), encoding="utf-8")
            code, results = self.check(root)
        self.assertEqual((code, [r["status"] for r in results]), (0, ["pass"]))


class CardPartTest(CheckinCase):
    def test_the_niggles_field_names_open_rows_and_due_follow_ups_are_facts(self):
        write_json(self.root / "data" / "niggles.json", {"schema_version": VERSION, "niggles": [
            niggle("n-0001", "watching", history=entries("watching", "watching", "watching")),
            niggle("n-0002", "chronic", area="synthetic left shoulder", history=entries("chronic")),
            niggle("n-0003", "resolved", area="synthetic lower back", history=entries("resolved"))]})
        self.coach("followups", "add", "--text", "Re-test pull-up ladder", "--review-at", "2026-10-01",
                   "--source", "chat", "--raised", "2026-09-20")
        card = self.card()
        field = self.field(card, "niggles")
        self.assertIn("synthetic left knee (watching)", field["prefill"])
        self.assertIn("synthetic left shoulder (chronic)", field["prefill"])
        self.assertNotIn("lower back", field["prefill"])
        self.assertIn("Anything new?", field["ask"])
        self.assertIn("niggle_escalate", [f["code"] for f in card["flags"]])
        self.assertTrue(any("f-0001" in fact for fact in card["facts"]))
        self.assertIn("followup_due", [f["code"] for f in card["flags"]])

    def test_without_the_files_the_builtin_field_stays(self):
        self.assertEqual(self.field(self.card(), "niggles")["prefill"], None)


class StatusTest(HistoryCase):
    def test_due_follow_ups_and_aggravated_niggles_need_attention(self):
        write_json(self.root / "data" / "niggles.json", {"schema_version": VERSION, "niggles": [
            niggle("n-0001", "aggravated", history=entries("watching", "aggravated"))]})
        self.coach("followups", "add", "--text", "Re-test pull-up ladder", "--review-at", "2026-10-11",
                   "--source", "chat")
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        self.assertEqual(sections["followups"]["level"], "attention")
        self.assertIn("f-0001", sections["followups"]["lines"][0])
        self.assertEqual(sections["niggles"]["level"], "attention")
        self.assertIn("synthetic left knee", sections["niggles"]["lines"][0])
        self.assertIn("qualified professional", " ".join(sections["niggles"]["lines"]))

    def test_the_aggravated_line_says_whether_a_limit_is_in_force(self):
        history = [{"date": "2026-10-11", "status": "aggravated", "note": None, "flare_constraints": None}]
        cap = [{"kind": "rpe_cap", "value": 7}]
        write_json(self.root / "data" / "niggles.json", {"schema_version": VERSION, "niggles": [
            niggle("n-0001", "aggravated", history=history, area="synthetic left knee"),
            niggle("n-0002", "aggravated", history=history, constraints=cap, area="synthetic right hip"),
            niggle("n-0003", "aggravated", history=history, constraints=cap, constrain_while=["watching"],
                   area="synthetic left wrist")]})
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        lines = {line.split()[1]: line for line in sections["niggles"]["lines"]}
        self.assertIn("no limit set", lines["n-0001"])
        self.assertIn("niggles update n-0001 --constraint", lines["n-0001"])
        self.assertIn("constraints apply to every proposal", lines["n-0002"])
        self.assertIn("not in force", lines["n-0003"])
        self.assertIn("niggles update n-0003 --constrain-while", lines["n-0003"])


class SkillTest(unittest.TestCase):
    def read(self, skill):
        return " ".join(skill_text(skill).split())

    def test_check_in_maintains_niggles_and_follow_ups_with_the_commands(self):
        text = self.read("check-in")
        act = " ".join(step_text("check-in", "act.md").split())
        self.assertIn("python3 -m coach niggles update", act)
        self.assertIn("python3 -m coach niggles add", act)
        self.assertNotIn("### Niggle log", act)
        deep = text[text.index("**Deep tier** — all of the above"):
                    text.index("**Both tiers — the hard-week count.**")]
        self.assertIn("python3 -m coach followups render --deep --date", deep)
        self.assertIn("python3 -m coach niggles list", deep)
        self.assertIn("chronic", deep)
        self.assertIn("without asking for a resolution", deep)

    def test_program_week_reads_niggle_constraints_from_the_proposal(self):
        text = self.read("program-week")
        self.assertIn("python3 -m coach niggles constraints", text)
        self.assertIn("`rpe_ceiling_unchecked`: no e1RM or kit meets the ceiling", text)

    def test_check_in_keeps_a_flare_limit_apart_from_the_standing_one(self):
        act = " ".join(step_text("check-in", "act.md").split())
        self.assertIn("--status aggravated --flare-constraint rpe_cap=6", act)
        self.assertIn("Never tighten `--constraint` for a flare.", act)


if __name__ == "__main__":
    unittest.main()
