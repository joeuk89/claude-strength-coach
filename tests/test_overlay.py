"""Overlay documents: build, validate, in-force resolution, approval (contract C10)."""

import copy
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from coach import config as config_module
from coach import jsonio, overlay
from coach.errors import ValidationError
from tests.support import FIXTURES, MINIMAL_CONFIG, VALID

DRAFTS = FIXTURES / "overlay"
NOW = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
WEEKLY = "2026-10-12-weekly"


def draft(name="draft-kg.json"):
    return json.loads((DRAFTS / name).read_text(encoding="utf-8"))


def valid_overlay():
    return json.loads((VALID / "data" / "overlays" / f"{WEEKLY}.json").read_text(encoding="utf-8"))


def lb_config():
    return (
        'schema_version = 1\n\n[athlete]\nunits = "lb"\n\n[equipment]\n'
        "dumbbell_increment = 5.0\ndumbbell_max = 100.0\nbarbell_increment = 5.0\n"
        "bar_weight = 45.0\nplates = [45, 35, 25, 10, 5, 2.5]\nmachine_increment = 10.0\n"
        "cable_increment = 5.0\n"
    )


class Instance:
    """A temporary instance: a copy of `valid/` by default, or just a config."""

    def __init__(self, config_text=None, copy_valid=True):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        if copy_valid:
            shutil.copytree(VALID, self.root, dirs_exist_ok=True)
        if config_text is not None:
            (self.root / "config.toml").write_text(config_text, encoding="utf-8")

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


def paths(errors):
    return [error.path for error in errors]


def set_at(doc, session, exercise, index):
    return doc["sessions"][session]["exercises"][exercise]["sets"][index]


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.config = config_module.load(VALID)

    def build(self, doc, root=VALID, config=None):
        return overlay.build(doc, config or self.config, root=root, now=NOW)

    def test_db_bench_per_hand_kg(self):
        built = self.build(draft())
        bench = built["sessions"][0]["exercises"][1]
        self.assertEqual(bench["exercise_id"], "db_bench_press")
        self.assertEqual(
            bench["sets"][1]["load"],
            {"mode": "per_hand_x2", "unit": "kg", "per_hand": 25, "hevy_total": 50, "hevy_kg": 50.0},
        )
        self.assertEqual(overlay.validate(built, VALID), [])

    def test_lb_draft(self):
        with Instance(lb_config(), copy_valid=False) as root:
            built = overlay.build(draft(), config_module.load(root), root=root, now=NOW)
        load = built["sessions"][0]["exercises"][1]["sets"][1]["load"]
        self.assertEqual(load["unit"], "lb")
        self.assertEqual(load["hevy_total"], 50)
        self.assertEqual(load["hevy_kg"], 22.6796)

    def test_fills_every_key(self):
        built = self.build(draft())
        self.assertEqual(built["schema_version"], overlay.current_version())
        self.assertEqual(built["approval"], None)
        self.assertEqual(built["flags"], [])
        self.assertEqual(built["created_at"], "2026-10-11T18:00:00Z")
        session = built["sessions"][1]
        self.assertEqual(session["temporary"], False)
        self.assertIn("location", session)
        self.assertIsNone(session["focus"])
        row = session["exercises"][0]
        for key in ("superset_id", "focus", "target_note", "change", "override", "provenance"):
            self.assertIn(key, row)
            self.assertIsNone(row[key])
        self.assertEqual(jsonio.load_schema("overlay")["required"], list(built))

    def test_id_follows_span_and_kind_with_collision_suffix(self):
        with Instance() as root:
            built = self.build(draft(), root=root)
            self.assertEqual(built["id"], "2026-10-12-weekly-2")
            (root / "data" / "overlays" / "2026-10-12-weekly-2.json").write_text("{}", encoding="utf-8")
            self.assertEqual(self.build(draft(), root=root)["id"], "2026-10-12-weekly-3")
        with Instance(MINIMAL_CONFIG, copy_valid=False) as root:
            self.assertEqual(self.build(draft(), root=root)["id"], WEEKLY)
            one_off = draft()
            one_off["kind"] = "one_off"
            self.assertEqual(self.build(one_off, root=root)["id"], "2026-10-12-one-off")

    def test_draft_id_is_kept(self):
        doc = draft()
        doc["id"] = WEEKLY
        self.assertEqual(self.build(doc)["id"], WEEKLY)

    def test_draft_schema_errors_carry_paths(self):
        doc = draft()
        doc["sessions"][0]["exercises"][1]["sets"][1]["load"] = {"per_hand": 25}
        doc["approval"] = {"approved_at": "2026-10-11T18:00:00Z", "hash": "sha256:" + "0" * 64}
        with self.assertRaises(ValidationError) as caught:
            self.build(doc)
        found = [d["path"] for d in caught.exception.details]
        self.assertIn("$.sessions[0].exercises[1].sets[1].load", found)
        self.assertIn("$.approval", found)

    def test_negative_load_is_an_error_at_the_set(self):
        doc = draft()
        doc["sessions"][0]["exercises"][0]["sets"][1]["load"] = -5
        with self.assertRaises(ValidationError) as caught:
            self.build(doc)
        self.assertIn("$.sessions[0].exercises[0].sets[1].load", [d["path"] for d in caught.exception.details])

    def test_override_sets_are_built_too(self):
        doc = draft()
        doc["sessions"][0]["exercises"][1]["override"] = {
            "reason": "elbow is grumpy",
            "proposed_sets": [{"type": "normal", "reps": 8, "rpe": 8, "load": 27.5}],
        }
        built = self.build(doc)
        proposed = built["sessions"][0]["exercises"][1]["override"]["proposed_sets"][0]
        self.assertEqual(proposed["load"]["hevy_total"], 55)

    def test_location_copied_from_program(self):
        with Instance() as root:
            program = {"schema_version": 1, "sessions": [{"id": "session-a", "location": "home"}]}
            (root / "data" / "program.json").write_text(json.dumps(program), encoding="utf-8")
            doc = draft()
            doc["sessions"][0]["exercises"] = doc["sessions"][0]["exercises"][1:]
            built = self.build(doc, root=root)
        self.assertEqual(built["sessions"][0]["location"], "home")
        self.assertIsNone(built["sessions"][1]["location"])

    def test_location_null_without_program_and_draft_value_wins(self):
        doc = draft()
        doc["sessions"][1]["location"] = "home"
        built = self.build(doc)
        self.assertIsNone(built["sessions"][0]["location"])
        self.assertEqual(built["sessions"][1]["location"], "home")


class NoDataTest(unittest.TestCase):
    """A loaded working set may have no load only when its line carries a no_data flag."""

    def setUp(self):
        self.config = config_module.load(VALID)

    def no_data_draft(self, flagged=True):
        doc = draft()
        bench = doc["sessions"][0]["exercises"][1]
        bench["sets"] = [{"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7, "load": None}] * 3
        if flagged:
            doc["flags"] = [{
                "code": "no_data", "severity": "warn", "session_id": "session-a",
                "exercise_id": "db_bench_press", "message": "No exposure and no start load.",
            }]
        return doc

    def test_builds_and_validates_with_the_flag(self):
        built = overlay.build(self.no_data_draft(), self.config, root=VALID, now=NOW)
        self.assertIsNone(built["sessions"][0]["exercises"][1]["sets"][0]["load"])
        self.assertEqual(built["flags"][0]["resolved"], False)
        self.assertIsNone(built["flags"][0]["resolution"])
        self.assertEqual(overlay.validate(built, VALID), [])

    def test_fails_without_the_flag(self):
        with self.assertRaises(ValidationError) as caught:
            overlay.build(self.no_data_draft(flagged=False), self.config, root=VALID, now=NOW)
        self.assertIn("$.sessions[0].exercises[1].sets[0].load", [d["path"] for d in caught.exception.details])

        built = overlay.build(self.no_data_draft(), self.config, root=VALID, now=NOW)
        built["flags"] = []
        self.assertIn("$.sessions[0].exercises[1].sets[0].load", paths(overlay.validate(built, VALID)))

    def test_flag_for_another_line_does_not_count(self):
        built = overlay.build(self.no_data_draft(), self.config, root=VALID, now=NOW)
        built["flags"][0]["exercise_id"] = "bb_back_squat"
        self.assertIn("$.sessions[0].exercises[1].sets[0].load", paths(overlay.validate(built, VALID)))

    def test_band_needs_no_flag(self):
        doc = draft()
        doc["sessions"][1]["exercises"].append({
            "exercise_id": "band_pull_apart", "load_mode": "band",
            "sets": [{"type": "normal", "reps": 15, "load": None}, {"type": "normal", "reps": 15}],
        })
        built = overlay.build(doc, self.config, root=VALID, now=NOW)
        self.assertEqual(overlay.validate(built, VALID), [])

    def test_unloaded_mode_with_a_load_is_an_error(self):
        doc = draft()
        doc["sessions"][1]["exercises"].append({
            "exercise_id": "band_pull_apart", "load_mode": "band",
            "sets": [{"type": "normal", "reps": 15, "load": 10}],
        })
        with self.assertRaises(ValidationError):
            overlay.build(doc, self.config, root=VALID, now=NOW)

    def test_warmup_may_leave_the_load_open(self):
        doc = draft()
        doc["sessions"][0]["exercises"][0]["sets"][0]["load"] = None
        built = overlay.build(doc, self.config, root=VALID, now=NOW)
        self.assertEqual(overlay.validate(built, VALID), [])


class ValidateTest(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(overlay.validate(valid_overlay(), VALID), [])

    def test_hevy_total_mismatch_names_the_load_path(self):
        doc = valid_overlay()
        set_at(doc, 0, 1, 1)["load"]["hevy_total"] = 25
        set_at(doc, 0, 1, 1)["load"]["hevy_kg"] = 25
        errors = overlay.validate(doc, VALID)
        self.assertEqual(paths(errors), ["$.sessions[0].exercises[1].sets[1].load.hevy_total"])
        self.assertIn("expected 50, found 25", errors[0].message)

    def test_hevy_kg_mismatch(self):
        doc = valid_overlay()
        set_at(doc, 0, 0, 1)["load"]["hevy_kg"] = 99
        self.assertEqual(paths(overlay.validate(doc, VALID)), ["$.sessions[0].exercises[0].sets[1].load.hevy_kg"])

    def test_load_mode_and_unit_must_match_the_line_and_config(self):
        doc = valid_overlay()
        set_at(doc, 1, 0, 0)["load"] = {"mode": "total", "unit": "kg", "per_hand": None, "hevy_total": 30,
                                        "hevy_kg": 30}
        set_at(doc, 1, 0, 1)["load"] = {"mode": "single_implement", "unit": "lb", "per_hand": 30,
                                        "hevy_total": 30, "hevy_kg": 13.6078}
        found = paths(overlay.validate(doc, VALID))
        self.assertIn("$.sessions[1].exercises[0].sets[0].load.mode", found)
        self.assertIn("$.sessions[1].exercises[0].sets[1].load.unit", found)

    def test_schema_errors(self):
        doc = valid_overlay()
        del doc["focus"]
        doc["sessions"][0]["exercises"][0]["sets"][0]["tempo"] = "3-1-1"
        found = paths(overlay.validate(doc, VALID))
        self.assertIn("$", found)
        self.assertIn("$.sessions[0].exercises[0].sets[0].tempo", found)

    def test_arithmetic_still_reported_beside_schema_errors(self):
        doc = valid_overlay()
        del doc["focus"]
        set_at(doc, 0, 1, 1)["load"]["hevy_total"] = 25
        self.assertIn("$.sessions[0].exercises[1].sets[1].load.hevy_total", paths(overlay.validate(doc, VALID)))

    def test_newer_and_older_versions(self):
        doc = valid_overlay()
        doc["schema_version"] = 99
        errors = overlay.validate(doc, VALID)
        self.assertEqual(paths(errors), ["$.schema_version"])
        self.assertIn("/framework-sync", errors[0].message)
        doc["schema_version"] = 0
        self.assertIn("migrate run", overlay.validate(doc, VALID)[0].message)

    def test_structural_rules(self):
        cases = [
            (lambda d: d["sessions"][0].update(date="2026-10-20"), "$.sessions[0].date"),
            (lambda d: d["span"].update(end="2026-10-11"), "$.span"),
            (lambda d: d.update(id="2026-10-13-weekly"), "$.id"),
            (lambda d: set_at(d, 0, 0, 1).update(rep_range={"start": 5, "end": 6}),
             "$.sessions[0].exercises[0].sets[1]"),
            (lambda d: set_at(d, 0, 0, 1).pop("reps"), "$.sessions[0].exercises[0].sets[1]"),
            (lambda d: set_at(d, 0, 1, 1).update(rep_range={"start": 10, "end": 8}),
             "$.sessions[0].exercises[1].sets[1].rep_range"),
            (lambda d: d["flags"].append({"code": "stalled", "severity": "warn", "session_id": "session-z",
                                          "exercise_id": None, "message": "x", "resolved": False,
                                          "resolution": None}), "$.flags[0].session_id"),
            (lambda d: d["flags"].append({"code": "stalled", "severity": "warn", "session_id": "session-a",
                                          "exercise_id": "pull_up", "message": "x", "resolved": False,
                                          "resolution": None}), "$.flags[0].exercise_id"),
            (lambda d: d["flags"].append({"code": "stalled", "severity": "warn", "session_id": None,
                                          "exercise_id": "pull_up", "message": "x", "resolved": False,
                                          "resolution": None}), "$.flags[0].session_id"),
            (lambda d: d["flags"].append({"code": "stalled", "severity": "warn", "session_id": None,
                                          "exercise_id": None, "message": "x", "resolved": True,
                                          "resolution": None}), "$.flags[0].resolution"),
            (lambda d: d["sessions"].append(copy.deepcopy(d["sessions"][0])), "$.sessions[2]"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                doc = valid_overlay()
                mutate(doc)
                self.assertIn(expected, paths(overlay.validate(doc, VALID)))

    def test_one_off_id_and_suffixes(self):
        doc = valid_overlay()
        doc.update(kind="one_off", id="2026-10-12-one-off-2")
        doc["approval"] = None
        self.assertEqual(overlay.validate(doc, VALID), [])
        doc["id"] = "2026-10-12-one-off-1"
        self.assertEqual(paths(overlay.validate(doc, VALID)), ["$.id"])

    def test_duration_sets_need_seconds_not_reps(self):
        doc = valid_overlay()
        doc["approval"] = None
        doc["sessions"][1]["exercises"].append({
            "exercise_id": "plank", "hevy_template_id": None, "load_mode": "duration", "rest_seconds": 60,
            "superset_id": None, "cues": None, "focus": None, "target_note": None, "change": None,
            "override": None, "provenance": None, "sets": [{"type": "normal", "duration_seconds": 45, "load": None}],
        })
        self.assertEqual(overlay.validate(doc, VALID), [])
        del doc["sessions"][1]["exercises"][2]["sets"][0]["duration_seconds"]
        self.assertIn("$.sessions[1].exercises[2].sets[0]", paths(overlay.validate(doc, VALID)))


class LocationTest(unittest.TestCase):
    def doc(self):
        doc = valid_overlay()
        doc["sessions"][1]["location"] = "home"
        return doc

    def test_known_location_validates(self):
        self.assertEqual(overlay.validate(self.doc(), VALID), [])

    def test_unknown_location_names_it(self):
        with Instance(MINIMAL_CONFIG) as root:
            errors = overlay.validate(self.doc(), root)
        self.assertEqual(paths(errors), ["$.sessions[1].location"])
        self.assertIn("home", errors[0].message)


class ApprovalTest(unittest.TestCase):
    def test_hash_ignores_approval_and_sees_every_edit(self):
        doc = valid_overlay()
        self.assertTrue(overlay.is_approved(doc))
        unapproved = dict(doc, approval=None)
        self.assertEqual(overlay.approval_hash(unapproved), doc["approval"]["hash"])
        set_at(doc, 0, 0, 1)["reps"] = 6
        self.assertFalse(overlay.is_approved(doc))

    def test_resolving_a_flag_breaks_approval(self):
        doc = valid_overlay()
        doc["flags"].append({"code": "stalled", "severity": "warn", "session_id": None, "exercise_id": None,
                             "message": "x", "resolved": False, "resolution": None})
        approved = overlay.approve(doc, NOW)
        self.assertTrue(overlay.is_approved(approved))
        approved["flags"][0].update(resolved=True, resolution="fine")
        self.assertFalse(overlay.is_approved(approved))

    def test_approve_stamps_time_and_hash(self):
        doc = dict(valid_overlay(), approval=None)
        self.assertFalse(overlay.is_approved(doc))
        approved = overlay.approve(doc, NOW)
        self.assertIsNone(doc["approval"])
        self.assertEqual(approved["approval"]["approved_at"], "2026-10-11T18:00:00Z")
        self.assertTrue(approved["approval"]["hash"].startswith("sha256:"))
        self.assertEqual(overlay.validate(approved, VALID), [])

    def test_unresolved_blocks(self):
        doc = valid_overlay()
        block = {"code": "stale_prescription", "severity": "block", "session_id": "session-a",
                 "exercise_id": "db_bench_press", "message": "x", "resolved": False, "resolution": None}
        doc["flags"] = [block, dict(block, resolved=True, resolution="decayed by hand"),
                        dict(block, severity="warn", code="stalled")]
        self.assertEqual(overlay.unresolved_blocks(doc), [block])


class InForceTest(unittest.TestCase):
    def midweek(self):
        doc = valid_overlay()
        doc.update(id="2026-10-14-midweek", kind="midweek", created_at="2026-10-14T07:00:00Z",
                   supersedes=WEEKLY, span={"start": "2026-10-14", "end": "2026-10-18"}, approval=None)
        doc["sessions"] = [doc["sessions"][1]]
        doc["sessions"][0]["exercises"][0]["sets"][0]["reps"] = 12
        return doc

    def test_weekly_then_midweek(self):
        with Instance() as root:
            jsonio.write_doc(root / "data" / "overlays" / "2026-10-14-midweek.json", self.midweek(), False)
            found, session = overlay.in_force(root, date(2026, 10, 12))
            self.assertEqual((found["id"], session["session_id"]), (WEEKLY, "session-a"))
            found, session = overlay.in_force(root, date(2026, 10, 13))
            self.assertEqual((found["id"], session), (WEEKLY, None))
            found, session = overlay.in_force(root, "2026-10-15")
            self.assertEqual((found["id"], session["session_id"]), ("2026-10-14-midweek", "session-b"))
            found, session = overlay.in_force(root, date(2026, 10, 16))
            self.assertEqual((found["id"], session), ("2026-10-14-midweek", None))
            self.assertIsNone(overlay.in_force(root, date(2026, 10, 19)))

    def test_a_session_day_beats_a_newer_overlay_without_one(self):
        later = self.midweek()
        later["span"] = {"start": "2026-10-14", "end": "2026-10-18"}
        later["sessions"][0]["date"] = "2026-10-16"
        with Instance() as root:
            later["id"] = "2026-10-14-midweek"
            jsonio.write_doc(root / "data" / "overlays" / "2026-10-14-midweek.json", later, False)
            found, session = overlay.in_force(root, date(2026, 10, 15))
        self.assertEqual((found["id"], session["session_id"]), (WEEKLY, "session-b"))

    def test_no_overlays(self):
        with Instance(MINIMAL_CONFIG, copy_valid=False) as root:
            self.assertIsNone(overlay.in_force(root, date(2026, 10, 12)))
            self.assertEqual(overlay.list(root), [])


class LoadTest(unittest.TestCase):
    def test_load_and_list(self):
        self.assertEqual(overlay.load(VALID, WEEKLY)["id"], WEEKLY)
        self.assertEqual([doc["id"] for doc in overlay.list(VALID)], [WEEKLY])

    def test_missing_and_malformed_ids(self):
        with self.assertRaises(ValidationError):
            overlay.load(VALID, "2026-01-01-weekly")
        with self.assertRaises(ValidationError):
            overlay.load(VALID, "../config")


if __name__ == "__main__":
    unittest.main()
