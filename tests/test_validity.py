"""Prescription validity: return bands, the validity window and the overlay checks (contract C21, C22)."""

import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from coach import flags, overlay, units, validity
from tests.support import INSTANCES, REPO_ROOT, VALID, run_cli
from tests.support.history import (R_A, W, HistoryCase, hevy_exercise, hevy_set, hevy_workout, read_json,
                                   write_json)

OVERLAY = "data/overlays/2026-10-12-weekly.json"
NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
LAYOFF = INSTANCES / "layoff"
R24_CODES = {"stale_prescription": ("block",), "unearned_load": ("block",), "load_cap": ("block",),
             "load_unrepresentable": ("block",), "load_mode_mismatch": ("block",), "rpe_infeasible": ("warn",),
             "session_over_cap": ("warn",)}
LOAD_CODES = ("stale_prescription", "unearned_load", "load_cap", "load_unrepresentable", "rpe_infeasible")


def working(reps, rpe, load, count=3, mode="total", unit="kg"):
    built = units.make_load(load, mode, unit) if load is not None else None
    return [{"type": "normal", "reps": reps, "rpe": rpe, "load": built} for _ in range(count)]


def raw_flag(code, severity, *, session_id, exercise_id, message):
    """A flag dict for a code another item registers (no_data is R-23a's)."""
    return {"code": code, "severity": severity, "session_id": session_id, "exercise_id": exercise_id,
            "message": message, "resolved": False, "resolution": None}


def codes(found, exercise_id=None):
    return sorted(f["code"] for f in found if exercise_id is None or f["exercise_id"] == exercise_id)


class BandsTest(unittest.TestCase):
    def test_band_bounds(self):
        for days, band in ((0, "0-10"), (10, "0-10"), (11, "11-21"), (21, "11-21"), (22, "22-42"), (42, "22-42"),
                           (43, "43+"), (400, "43+")):
            with self.subTest(days=days):
                self.assertEqual(validity.band_for(days).id, band)

    def test_band_factors_and_caps(self):
        rows = [(b.id, b.load_factor, b.set_delta, b.rpe_cap, b.retest) for b in validity.RETURN_BANDS]
        self.assertEqual(rows, [("0-10", 1.00, 0, None, False), ("11-21", 0.95, -1, None, False),
                                ("22-42", 0.90, -1, None, False), ("43+", 0.85, -1, 7, True)])
        self.assertEqual(validity.GRACE_DAYS, 10)


class ClaudeMdBandsTest(unittest.TestCase):
    """The prose table in CLAUDE.md "Coaching principles" states the same bands as RETURN_BANDS."""

    def rows(self):
        lines = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
        start = lines.index("## Coaching principles")
        end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
        table = [line.strip() for line in lines[start:end] if line.strip().startswith("| ")]
        head = next(i for i, line in enumerate(table) if line.startswith("| Days off"))
        return [[cell.strip() for cell in row.strip("|").split("|")] for row in table[head + 2:]]

    def test_day_bounds_percentages_sets_and_rpe_match(self):
        rows = self.rows()
        self.assertEqual(len(rows), len(validity.RETURN_BANDS))
        lower = 0
        for (days, effect), band in zip(rows, validity.RETURN_BANDS):
            with self.subTest(band=band.id):
                bounds = [int(n) for n in re.findall(r"\d+", days)]
                if band.upper is None:
                    self.assertEqual(bounds, [lower])
                    self.assertIn("+", days)
                elif lower == 0:
                    self.assertEqual(bounds, [band.upper])
                else:
                    self.assertEqual(bounds, [lower, band.upper])
                cut = re.search(r"−\s*(\d+)\s*%", effect)
                self.assertEqual(int(cut.group(1)) if cut else 0, round((1 - band.load_factor) * 100))
                self.assertEqual("one working set fewer" in effect, band.set_delta == -1)
                cap = re.search(r"RPE (\d+) or below", effect)
                self.assertEqual(int(cap.group(1)) if cap else None, band.rpe_cap)
                lower = (band.upper or 0) + 1

    def test_illness_cap_matches(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(f"first session back capped at RPE {validity.ILLNESS_RPE_CAP}", text)


class IntervalTest(unittest.TestCase):
    def test_median_of_the_last_four_gaps_clamped(self):
        days = [date(2026, 10, d) for d in (1, 15, 29)] + [date(2026, 9, 17)]
        self.assertEqual(validity.interval_days(days), 14)
        self.assertEqual(validity.interval_days([date(2026, 10, d) for d in (1, 3, 5, 7)]), 7)
        self.assertEqual(validity.interval_days([date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)]), 14)

    def test_fewer_than_two_gaps_is_a_week(self):
        self.assertEqual(validity.interval_days([date(2026, 10, 1)]), 7)
        self.assertEqual(validity.interval_days([date(2026, 10, 1), date(2026, 10, 15)]), 7)

    def test_window(self):
        self.assertTrue(validity.window_ok(24, 14))
        self.assertFalse(validity.window_ok(25, 14))


class FlagCodesTest(unittest.TestCase):
    def test_every_r24_code_is_registered(self):
        registry = flags.registry()
        for code, severities in R24_CODES.items():
            with self.subTest(code=code):
                self.assertEqual(registry[code].owner, "R-24")
                self.assertEqual(registry[code].severities, severities)
        self.assertEqual(validity.owned_codes(), set(R24_CODES))


class ValidityCase(HistoryCase):
    """The valid instance with its C14 workouts synced, and helpers to edit and check its overlay."""

    def setUp(self):
        super().setUp()
        self.cache()
        self.sync()
        self.edit_json(OVERLAY, lambda doc: doc.update(approval=None))

    def line(self, doc, exercise_id):
        return next(e for s in doc["sessions"] for e in s["exercises"] if e["exercise_id"] == exercise_id)

    def edit_line(self, exercise_id, change):
        self.edit_json(OVERLAY, lambda doc: change(self.line(doc, exercise_id)))

    def set_config(self, old, new):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def run_check(self, *extra, expect=0):
        return self.coach("prescription", "check", "--overlay", "2026-10-12-weekly", *extra, expect=expect)

    def found(self):
        return self.run_check()["data"]["flags"]


class ValidInstanceTest(ValidityCase):
    def test_no_block_and_every_line_in_the_first_band(self):
        data = self.run_check()["data"]
        self.assertEqual([f for f in data["flags"] if f["severity"] == "block"], [])
        for row in data["lines"]:
            with self.subTest(exercise=row["exercise_id"]):
                self.assertIsNotNone(row["days_off"])
                self.assertEqual(row["band"], "0-10")
        squat = next(row for row in data["lines"] if row["exercise_id"] == "bb_back_squat")
        self.assertEqual(squat["derived_from"], {"date": "2026-10-05", "workout_id": W[3]})
        self.assertTrue(squat["inferred"])
        self.assertEqual(squat["days_off"], 4)

    def test_days_off_function(self):
        self.assertEqual(validity.days_off(self.root, "bb_back_squat", "2026-10-12"), 4)
        self.assertEqual(validity.days_off(self.root, "db_single_arm_row", "2026-10-15"), 7)

    def test_no_history_reports_no_days_off(self):
        code, envelope, _ = run_cli(["--root", str(VALID), "prescription", "check", "--overlay",
                                     "2026-10-12-weekly"], env=NOW)
        self.assertEqual(code, 0, envelope)
        self.assertEqual({row["days_off"] for row in envelope["data"]["lines"]}, {None})
        self.assertEqual(envelope["data"]["flags"], [])


class FeasibilityTest(ValidityCase):
    def squat(self, sets):
        self.edit_line("bb_back_squat", lambda line: line.update(sets=sets))
        return codes(self.found(), "bb_back_squat")

    def test_a_single_at_120_rpe_8_is_infeasible(self):
        self.assertEqual(self.squat(working(1, 8, 120, count=1)), ["rpe_infeasible"])
        message = next(f["message"] for f in self.found() if f["code"] == "rpe_infeasible"
                       and f["exercise_id"] == "bb_back_squat")
        self.assertIn("implies RPE 10 ", message)
        self.assertIn("121.88", message)

    def test_3x5_at_125_is_unearned(self):
        self.assertEqual(self.squat(working(5, 8, 125)), ["unearned_load"])

    def test_3x5_at_100_rpe_8_is_fine(self):
        self.assertEqual(self.squat(working(5, 8, 100)), [])


class NoE1rmTest(HistoryCase):
    """Squat logged only at 20 reps, which gives no e1RM (C18)."""

    def setUp(self):
        super().setUp()

        def long_sets(workouts):
            for workout in workouts:
                for exercise in workout["exercises"]:
                    for set_ in exercise["sets"]:
                        set_["reps"] = 20
        self.cache(edit=long_sets)
        self.sync()
        self.edit_json(OVERLAY, lambda doc: doc.update(approval=None))

    def squat(self, load):
        def change(doc):
            doc["sessions"][0]["exercises"][0]["sets"] = working(5, None, load)
        self.edit_json(OVERLAY, change)
        found = self.coach("prescription", "check", "--overlay", "2026-10-12-weekly")["data"]["flags"]
        return codes(found, "bb_back_squat")

    def test_more_than_two_increments_above_the_last_exposure_is_unearned(self):
        self.assertEqual(self.squat(102.5), [])
        self.assertEqual(self.squat(105), ["unearned_load"])


class CapsAndKitTest(ValidityCase):
    def bench(self, per_hand):
        self.edit_line("db_bench_press", lambda line: line.update(
            sets=working(8, None, per_hand, mode="per_hand_x2")))

    def test_over_dumbbell_max_is_a_cap(self):
        self.bench(42)
        self.assertIn("load_cap", codes(self.found(), "db_bench_press"))

    def test_dumbbell_not_in_the_rack(self):
        self.bench(24)
        self.assertEqual(codes(self.found(), "db_bench_press"), [])
        self.set_config("dumbbells = []", "dumbbells = [20, 22.5, 25]")
        self.assertEqual(codes(self.found(), "db_bench_press"), ["load_unrepresentable"])

    def test_squat_total_with_no_plate_breakdown(self):
        self.edit_line("bb_back_squat", lambda line: line.update(sets=working(5, None, 101)))
        self.assertEqual(codes(self.found(), "bb_back_squat"), ["load_unrepresentable"])

    def at_home(self):
        self.edit_json(OVERLAY, lambda doc: doc["sessions"][0].update(location="home"))

    def test_a_home_session_uses_the_home_kit(self):
        self.at_home()
        self.bench(22.5)
        self.assertEqual(codes(self.found(), "db_bench_press"), ["load_cap"])
        self.bench(12.5)
        self.assertEqual(codes(self.found(), "db_bench_press"), ["load_unrepresentable"])

    def test_the_same_lines_away_from_home_use_the_main_kit(self):
        self.bench(22.5)
        self.assertEqual(codes(self.found(), "db_bench_press"), [])
        self.bench(12.5)
        self.assertEqual(codes(self.found(), "db_bench_press"), [])

    def test_an_empty_home_rack_is_not_checked(self):
        self.set_config("dumbbells = [5, 10, 15, 20]", "dumbbells = []")
        self.at_home()
        self.bench(12.5)
        self.assertEqual(codes(self.found(), "db_bench_press"), [])


class LoadModeMismatchTest(ValidityCase):
    def test_bad_hevy_total_uses_the_overlay_validator_message(self):
        def break_total(line):
            line["sets"][1]["load"]["hevy_total"] = 25
        self.edit_line("db_bench_press", break_total)
        [flag] = [f for f in self.found() if f["code"] == "load_mode_mismatch"]
        self.assertEqual(flag["exercise_id"], "db_bench_press")
        self.assertIn("$.sessions[0].exercises[1].sets[1].load.hevy_total: expected 50, found 25", flag["message"])

    def test_library_disagreement(self):
        def as_single(line):
            line["load_mode"] = "single_implement"
            for set_ in line["sets"]:
                set_["load"] = units.make_load(set_["load"]["per_hand"], "single_implement", "kg")
        self.edit_line("db_bench_press", as_single)
        self.assertIn("load_mode_mismatch", codes(self.found(), "db_bench_press"))


class SessionCapTest(ValidityCase):
    def over(self):
        return [f for f in self.found() if f["code"] == "session_over_cap" and f["session_id"] == "session-a"]

    def test_a_session_cap_entry(self):
        self.set_config("[caps]", "[caps]\n\n[sessions.cap_minutes]\nsession-a = 30")
        [flag] = self.over()
        self.assertRegex(flag["message"], r"estimated \d+ min")
        self.assertIsNone(flag["exercise_id"])
        self.set_config("session-a = 30", "session-a = 90")
        self.assertEqual(self.over(), [])

    def test_the_default_session_minutes(self):
        self.set_config("session_minutes = 60", "session_minutes = 30")
        self.assertEqual(len(self.over()), 1)
        self.set_config("session_minutes = 30", "session_minutes = 90")
        self.assertEqual(self.over(), [])

    def test_estimate_is_scaled_by_logged_pace(self):
        doc = read_json(self.root / OVERLAY)
        self.assertEqual(validity.estimate_minutes(self.root, doc["sessions"][0]), 39)


class IllnessTest(ValidityCase):
    def setUp(self):
        super().setUp()
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-a",
                   "--tag", "ill")

    def test_the_first_session_needs_rpe_7_on_every_set(self):
        found = self.found()
        self.assertIn("stale_prescription", codes(found, "db_bench_press"))
        self.assertNotIn("stale_prescription", codes(found, "bb_back_squat"))
        self.assertTrue(all(f["severity"] == "block" for f in found if f["code"] == "stale_prescription"))
        self.assertNotIn("stale_prescription", codes(found, "db_single_arm_row"))

    def test_capped_at_rpe_7_it_passes(self):
        def cap(line):
            for set_ in line["sets"]:
                if set_["type"] == "normal":
                    set_["rpe"] = 7
        self.edit_line("db_bench_press", cap)
        self.assertNotIn("stale_prescription", codes(self.found()))


class BiweeklyTest(HistoryCase):
    """A lift trained every 14 days next to a weekly one."""

    def setUp(self):
        super().setUp()
        workouts = []
        for n, day in enumerate(("2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05",
                                 "2026-10-12", "2026-10-19", "2026-10-26"), start=1):
            exercises = [hevy_exercise(0, "Squat (Barbell)", "F0000001", [hevy_set(i, 100.0, 5, 7) for i in range(3)])]
            if n % 2 == 1 and day <= "2026-10-05":
                exercises.append(hevy_exercise(1, "Bench Press (Dumbbell)", "F0000002",
                                               [hevy_set(i, 45.0, 10, 8) for i in range(3)]))
            workouts.append(hevy_workout(f"20000000-0000-4000-8000-00000000000{n}", R_A, "Session A", day, exercises))
        self.cache(workouts=workouts)
        self.sync(env={"COACH_NOW": "2026-11-11T18:00:00Z"})

    def test_14_days_after_is_valid_and_30_days_after_needs_a_band(self):
        self.assertEqual(validity.days_off(self.root, "db_bench_press", "2026-10-19"), 7)
        self.assertEqual(validity.band_for(validity.days_off(self.root, "db_bench_press", "2026-10-19")).id, "0-10")
        days = validity.days_off(self.root, "db_bench_press", "2026-11-04")
        self.assertEqual(days, 16)
        self.assertEqual(validity.band_for(days).id, "11-21")


class LayoffTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(LAYOFF, self.root)

    def coach(self, *argv, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env=NOW)
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def squat_flags(self):
        found = self.coach("prescription", "check", "--overlay", "2026-10-12-weekly")["data"]["flags"]
        return [f for f in found if f["exercise_id"] == "bb_back_squat"]

    def test_a_stale_squat_names_its_days_off_and_band(self):
        [flag] = [f for f in self.squat_flags() if f["code"] == "stale_prescription"]
        self.assertEqual(flag["severity"], "block")
        self.assertIn("28 days off", flag["message"])
        self.assertIn("22-42", flag["message"])

    def test_decayed_to_its_band_it_passes(self):
        path = self.root / OVERLAY
        doc = read_json(path)
        line = doc["sessions"][0]["exercises"][0]
        line["sets"] = [line["sets"][0]] + working(5, None, 90, count=2)
        line["provenance"] = {
            "scheme": None, "derived_from": {"date": "2026-09-14", "workout_id": "10000000-0000-4000-8000-000000000025"},
            "inferred": False, "rationale": None,
            "decay": {"days_off": 28, "band": "22-42", "load_factor": 0.9, "set_delta": -1, "rpe_cap": None},
        }
        write_json(path, doc)
        self.assertEqual(self.squat_flags(), [])

    def test_decayed_too_little_is_still_stale(self):
        path = self.root / OVERLAY
        doc = read_json(path)
        line = doc["sessions"][0]["exercises"][0]
        line["sets"] = working(5, None, 95, count=3)
        line["provenance"] = {
            "scheme": None, "derived_from": {"date": "2026-09-14", "workout_id": "10000000-0000-4000-8000-000000000025"},
            "inferred": False, "rationale": None,
            "decay": {"days_off": 28, "band": "22-42", "load_factor": 0.9, "set_delta": -1, "rpe_cap": None},
        }
        write_json(path, doc)
        [flag] = self.squat_flags()
        self.assertIn("load 95 is above 100 × 0.9", flag["message"])
        self.assertIn("3 working sets, at most 2", flag["message"])

    def decayed_without_a_source(self, derived_from):
        path = self.root / OVERLAY
        doc = read_json(path)
        line = doc["sessions"][0]["exercises"][0]
        line["sets"] = working(5, None, 100, count=3)
        line["provenance"] = {
            "scheme": None, "derived_from": derived_from, "inferred": False, "rationale": None,
            "decay": {"days_off": 28, "band": "22-42", "load_factor": 0.9, "set_delta": -1, "rpe_cap": None},
        }
        write_json(path, doc)
        [flag] = self.squat_flags()
        self.assertEqual(flag["code"], "stale_prescription")
        return flag["message"]

    def test_a_decayed_line_with_no_derived_from_is_stale(self):
        self.assertIn("cannot be checked against the decay: provenance.derived_from is null",
                      self.decayed_without_a_source(None))

    def test_a_decayed_line_derived_from_an_unknown_workout_is_stale(self):
        unknown = "10000000-0000-4000-8000-000000000099"
        message = self.decayed_without_a_source({"date": "2026-09-14", "workout_id": unknown})
        self.assertIn(f"derived_from names workout {unknown}, which the history does not hold", message)

    def test_a_no_data_line_gets_no_load_flag(self):
        path = self.root / OVERLAY
        doc = read_json(path)
        doc["sessions"][0]["exercises"][0]["sets"] = working(5, 9, None)
        doc["flags"].append(raw_flag("no_data", "warn", session_id="session-a", exercise_id="bb_back_squat",
                                     message="no usable exposure"))
        write_json(path, doc)
        self.assertEqual([f["code"] for f in self.squat_flags() if f["code"] in LOAD_CODES], [])

    def test_check_fails_on_the_stale_overlay(self):
        code, envelope, _ = run_cli(["--root", str(LAYOFF), "check", "--only", "prescription_valid"], env=NOW)
        self.assertEqual(code, 1)
        fails = [r for r in envelope["data"]["results"] if r["status"] == "fail"]
        self.assertTrue(any("stale_prescription" in r["message"] and "28 days off" in r["message"] for r in fails))


class SlipTest(HistoryCase):
    """Bench on 2026-10-05 is an open convention-slip candidate at Hevy 90 (C17)."""

    base = INSTANCES / "slip"

    def test_inferred_derived_from_skips_the_open_slip(self):
        envelope = self.coach("prescription", "check", "--overlay", "2026-10-12-weekly")
        bench = next(row for row in envelope["data"]["lines"] if row["exercise_id"] == "db_bench_press")
        self.assertEqual(bench["derived_from"], {"date": "2026-09-28", "workout_id": W[1]})
        squat = next(row for row in envelope["data"]["lines"] if row["exercise_id"] == "bb_back_squat")
        self.assertEqual(squat["derived_from"], {"date": "2026-10-05", "workout_id": W[3]})


class CheckTest(unittest.TestCase):
    def test_passes_on_the_valid_instance(self):
        code, envelope, _ = run_cli(["--root", str(VALID), "check", "--only", "prescription_valid"], env=NOW)
        self.assertEqual(code, 0, envelope)
        self.assertEqual({r["status"] for r in envelope["data"]["results"]}, {"pass"})

    def test_passes_once_the_findings_are_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(LAYOFF, root)
            path = root / OVERLAY
            doc = read_json(path)
            doc["approval"] = None
            write_json(path, doc)
            code, envelope, _ = run_cli(["--root", str(root), "prescription", "check", "--overlay",
                                         "2026-10-12-weekly", "--write"], env=NOW)
            self.assertEqual(code, 0, envelope)
            doc = read_json(path)
            for flag in doc["flags"]:
                flag.update(resolved=True, resolution="athlete trained it as written")
            write_json(path, doc)
            code, envelope, _ = run_cli(["--root", str(root), "check", "--only", "prescription_valid"], env=NOW)
        self.assertEqual(code, 0, envelope)

    def test_ended_overlays_are_not_checked(self):
        code, envelope, _ = run_cli(["--root", str(LAYOFF), "check", "--only", "prescription_valid"],
                                    env={"COACH_NOW": "2026-10-19T18:00:00Z"})
        self.assertEqual(code, 0, envelope)
        self.assertEqual({r["status"] for r in envelope["data"]["results"]}, {"skip"})


class WriteTest(ValidityCase):
    def test_write_merges_flags_and_fills_inferred_provenance(self):
        self.set_config("dumbbell_max = 40.0", "dumbbell_max = 20.0")
        data = self.run_check("--write")["data"]
        self.assertTrue(data["written"])
        doc = read_json(self.root / OVERLAY)
        self.assertIn("load_cap", codes(doc["flags"]))
        squat = self.line(doc, "bb_back_squat")
        self.assertEqual(squat["provenance"], {"scheme": None, "derived_from": {"date": "2026-10-05",
                                                                                "workout_id": W[3]},
                                               "inferred": True, "decay": None, "rationale": None})
        self.coach("overlay", "validate", "2026-10-12-weekly")

    def test_write_keeps_the_resolution_of_an_identical_flag_and_drops_old_ones(self):
        self.set_config("dumbbell_max = 40.0", "dumbbell_max = 20.0")
        self.run_check("--write")

        def resolve_and_add_stale(doc):
            for flag in doc["flags"]:
                flag.update(resolved=True, resolution="agreed with the athlete")
            doc["flags"].append(flags.make("stale_prescription", session_id="session-b", exercise_id="pull_up",
                                           message="an old finding"))
            doc["flags"].append(raw_flag("no_data", "warn", session_id="session-b", exercise_id="pull_up",
                                           message="kept: not an R-24 code"))
        self.edit_json(OVERLAY, resolve_and_add_stale)
        self.run_check("--write")
        doc = read_json(self.root / OVERLAY)
        cap = next(f for f in doc["flags"] if f["code"] == "load_cap")
        self.assertEqual((cap["resolved"], cap["resolution"]), (True, "agreed with the athlete"))
        self.assertNotIn("an old finding", [f["message"] for f in doc["flags"]])
        self.assertIn("no_data", codes(doc["flags"]))

    def test_dry_run_writes_nothing(self):
        before = (self.root / OVERLAY).read_bytes()
        data = self.run_check("--write", "--dry-run")["data"]
        self.assertFalse(data["written"])
        self.assertEqual((self.root / OVERLAY).read_bytes(), before)

    def test_an_approved_overlay_is_refused(self):
        self.coach("overlay", "approve", "2026-10-12-weekly")
        before = (self.root / OVERLAY).read_bytes()
        self.run_check("--write", expect=3)
        self.run_check("--write", "--dry-run", expect=3)
        self.assertEqual((self.root / OVERLAY).read_bytes(), before)

    def test_write_needs_an_overlay_id(self):
        self.coach("prescription", "check", "--file", str(self.root / OVERLAY), "--write", expect=2)


class FileTest(ValidityCase):
    def test_a_draft_is_built_in_memory_and_checked(self):
        draft = read_json(REPO_ROOT / "tests" / "fixtures" / "overlay" / "draft-kg.json")
        draft["sessions"][0]["exercises"][0]["sets"] = [{"type": "normal", "reps": 5, "rpe": 8, "load": 125}]
        path = self.tmp / "draft.json"
        write_json(path, draft)
        before = sorted(p.name for p in (self.root / "data" / "overlays").iterdir())
        data = self.coach("prescription", "check", "--file", str(path))["data"]
        self.assertEqual(data["source"], "draft")
        self.assertIn("unearned_load", codes(data["flags"], "bb_back_squat"))
        self.assertEqual(sorted(p.name for p in (self.root / "data" / "overlays").iterdir()), before)

    def test_a_draft_may_carry_provenance(self):
        draft = read_json(REPO_ROOT / "tests" / "fixtures" / "overlay" / "draft-kg.json")
        draft["sessions"][0]["exercises"][0]["provenance"] = {
            "scheme": None, "derived_from": None, "inferred": False, "decay": None, "rationale": None}
        path = self.tmp / "draft.json"
        write_json(path, draft)
        data = self.coach("prescription", "check", "--file", str(path))["data"]
        squat = next(row for row in data["lines"] if row["exercise_id"] == "bb_back_squat")
        self.assertEqual((squat["derived_from"], squat["inferred"]), (None, False))

    def test_an_overlay_file(self):
        data = self.coach("prescription", "check", "--file", str(self.root / OVERLAY))["data"]
        self.assertEqual(data["source"], "overlay")


class MigrationTest(unittest.TestCase):
    """`migrate run` takes a v1 overlay to v2 (C21)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(VALID, self.root)
        shutil.copy(REPO_ROOT / "tests" / "fixtures" / "overlay" / "v1-approved.json", self.root / OVERLAY)

    def migrate(self, *extra):
        code, envelope, stderr = run_cli(["--root", str(self.root), "migrate", "run", *extra], env=NOW)
        self.assertEqual(code, 0, (envelope, stderr))
        return envelope["data"]

    def test_dry_run_lists_the_overlays_that_lose_approval(self):
        before = (self.root / OVERLAY).read_bytes()
        data = self.migrate("--dry-run")
        self.assertEqual(data["files"][0]["steps"][0], "overlay/0001_line_provenance")
        self.assertEqual(len(data["notes"]), 1)
        self.assertIn("2026-10-12-weekly loses its approval", data["notes"][0])
        self.assertEqual((self.root / OVERLAY).read_bytes(), before)

    def test_run_adds_null_provenance_to_every_line(self):
        self.migrate()
        doc = read_json(self.root / OVERLAY)
        self.assertEqual(doc["schema_version"], overlay.current_version())
        lines = [line for session in doc["sessions"] for line in session["exercises"]]
        self.assertEqual(len(lines), 4)
        self.assertEqual({repr(line["provenance"]) for line in lines}, {"None"})

    def test_an_unapproved_overlay_has_no_note(self):
        doc = read_json(self.root / OVERLAY)
        doc["approval"] = None
        write_json(self.root / OVERLAY, doc)
        self.assertEqual(self.migrate("--dry-run")["notes"], [])


class ProgramWeekSkillTest(unittest.TestCase):
    def test_names_prescription_check_in_the_build_step_before_the_brief(self):
        text = " ".join((REPO_ROOT / ".claude" / "skills" / "program-week" / "SKILL.md").read_text(
            encoding="utf-8").split())
        build = text[text.index("## 3. Build the overlay"):text.index("## 4. Present the coach's brief")]
        self.assertIn("python3 -m coach prescription check --overlay <id> --write", build)
        self.assertEqual(text.count("prescription check"), build.count("prescription check"))
        for code in R24_CODES:
            with self.subTest(code=code):
                self.assertIn(f"`{code}`", build)


if __name__ == "__main__":
    unittest.main()
