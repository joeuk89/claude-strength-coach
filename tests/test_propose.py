"""The proposal pipeline, decisions and `coach propose` (contract C23–C26)."""

import json
import math
import re
import shutil
import textwrap
import unittest
from unittest import mock

from coach import dates, jsonio, overlay, units
from coach.plugins.schemes import double_progression
from coach.validate import validate as validate_schema
from tests.support import INSTANCES, REPO_ROOT
from tests.support.history import W, HistoryCase, read_json, write_json
from tests.support.skills import flat, skill_files, step_text
from tests.test_plugins import PLUGIN_TEST, fixed_load_plugin

NOW = "2026-10-11T18:00:00Z"
WEEK = "2026-W42"
FIRST_ID = "2026-10-12-weekly-2"
WORKING = ("normal", "dropset", "failure")
SQUAT, BENCH = "F0000001", "F0000002"


def working(line):
    return [s for s in line["sets"] if s["type"] in WORKING]


def coaching(load):
    return load["per_hand"] if load["mode"] in units.PER_HAND_MODES else load["hevy_total"]


def find_line(doc, exercise_id, session_id=None):
    return next(line for session in doc["sessions"] for line in session["exercises"]
                if line["exercise_id"] == exercise_id and session_id in (None, session["session_id"]))


def codes(doc, exercise_id=None):
    return sorted(f["code"] for f in doc["flags"] if exercise_id is None or f["exercise_id"] == exercise_id)


def edit_sets(template_id, change, workout_ids=(W[1], W[3])):
    """A fixture-set edit that applies `change(set)` to one exercise's sets in the given workouts."""
    def edit(workouts):
        for workout in workouts:
            if workout["id"] not in workout_ids:
                continue
            for exercise in workout["exercises"]:
                if exercise["exercise_template_id"] == template_id:
                    for index, set_ in enumerate(exercise["sets"]):
                        change(workout["id"], index, set_)
    return edit


class ProposeCase(HistoryCase):
    """The valid instance with its C14 workouts synced; `workouts` may edit the fixture set first."""

    synced = True
    workouts = None

    def setUp(self):
        super().setUp()
        if self.synced:
            self.cache(edit=self.workouts)
            self.sync()

    def propose(self, *extra, expect=0, env=None, week=WEEK):
        args = ("--week", week) if week else ()
        envelope = self.coach("propose", "week", *args, *extra, expect=expect, env=env)
        return envelope["data"] if expect == 0 else envelope

    def edit_program(self, change):
        self.edit_json("data/program.json", change)

    def slot(self, doc, session_id, exercise_id):
        session = next(s for s in doc["sessions"] if s["id"] == session_id)
        return next(e for e in session["exercises"] if e["exercise_id"] == exercise_id)

    def set_scheme(self, session_id, exercise_id, name, params=None):
        self.edit_program(lambda doc: self.slot(doc, session_id, exercise_id).update(
            scheme={"name": name, "params": params or {}}))

    def write_plugin(self, name, source):
        path = self.root / "plugins" / "schemes" / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        test = self.root / "plugins" / "tests" / f"test_{name}.py"
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text(PLUGIN_TEST, encoding="utf-8")

    def set_config(self, old, new):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def draft_path(self, proposal_id=FIRST_ID):
        return self.root / ".coach" / "proposals" / f"{proposal_id}.json"


class ValidWeekTest(ProposeCase):
    def test_dry_run_proposes_a_valid_current_overlay_and_writes_nothing(self):
        before = self.snapshot()
        data = self.propose("--dry-run")
        self.assertEqual(self.snapshot(), before)
        doc = data["overlay"]
        self.assertEqual(validate_schema(doc, jsonio.load_schema("overlay")), [])
        self.assertEqual(overlay.validate(doc, self.root), [])
        self.assertEqual(doc["schema_version"], overlay.current_version())
        self.assertEqual([(s["date"], s["session_id"]) for s in doc["sessions"]],
                         [("2026-10-12", "session-a"), ("2026-10-15", "session-b")])
        self.assertEqual(data["id"], FIRST_ID)
        self.assertFalse(data["written"])
        for session in doc["sessions"]:
            for line in session["exercises"]:
                with self.subTest(exercise=line["exercise_id"]):
                    provenance = line["provenance"]
                    self.assertTrue(provenance["scheme"])
                    self.assertIsNotNone(provenance["derived_from"])
                    self.assertFalse(provenance["inferred"])
                    rationale = provenance["rationale"]
                    self.assertTrue(rationale.endswith("."))
                    self.assertIsNone(re.search(r"[.!?]\s", rationale[:-1]), rationale)
        self.assertEqual([f for f in doc["flags"] if f["severity"] == "block"], [])

    def test_lines_quote_loads_through_units(self):
        data = self.propose("--dry-run")
        bench = next(row for row in data["lines"] if row["exercise_id"] == "db_bench_press")
        self.assertEqual(bench["text"], "3×8 @ 24.5/hand (Hevy: 49) RPE 8")
        self.assertEqual(bench["change"], "25/hand (Hevy: 50) → 24.5/hand (Hevy: 49)")
        self.assertEqual(set(bench), {"session_id", "date", "exercise_id", "text", "change", "rationale", "flags"})

    def test_overlay_sessions_copy_the_program_location(self):
        self.edit_program(lambda doc: doc["sessions"][0].update(location="home"))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual([s["location"] for s in doc["sessions"]], ["home", None])

    def test_a_real_run_writes_the_draft_and_its_untouched_copy(self):
        data = self.propose()
        self.assertEqual(data["draft"], f".coach/proposals/{FIRST_ID}.json")
        draft = read_json(self.draft_path())
        self.assertEqual(draft, read_json(self.root / data["proposed"]))
        self.assertEqual(draft["id"], FIRST_ID)
        self.assertFalse((self.root / "data" / "overlays" / f"{FIRST_ID}.json").exists())

    def test_sunday_weeks(self):
        self.set_config('week_starts = "monday"', 'week_starts = "sunday"')
        data = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual(data["span"], {"start": "2026-10-11", "end": "2026-10-17"})
        self.assertEqual([(s["date"], s["session_id"]) for s in data["sessions"]],
                         [("2026-10-12", "session-a"), ("2026-10-15", "session-b")])

    def test_midweek_reproposes_the_remaining_days(self):
        data = self.propose("--kind", "midweek", "--dry-run", env={"COACH_NOW": "2026-10-13T08:00:00Z"})
        self.assertEqual(data["id"], "2026-10-13-midweek")
        self.assertEqual([s["session_id"] for s in data["overlay"]["sessions"]], ["session-b"])

    def test_a_plan_file_replaces_the_schedule_rule(self):
        plan = self.coach("schedule", "plan", "--week", WEEK)["data"]
        plan["sessions"] = plan["sessions"][1:]
        path = self.tmp / "plan.json"
        write_json(path, plan)
        doc = self.propose("--plan", str(path), "--dry-run")["overlay"]
        self.assertEqual([s["session_id"] for s in doc["sessions"]], ["session-b"])


class DoubleProgressionTest(ProposeCase):
    workouts = staticmethod(edit_sets(BENCH, lambda wid, i, s: s.update(weight_kg=48.0)))

    def test_top_of_the_range_adds_the_increment_and_drops_to_the_bottom(self):
        line = find_line(self.propose("--dry-run")["overlay"], "db_bench_press")
        for set_ in working(line):
            self.assertEqual(set_["reps"], 8)
            self.assertIsNone(set_.get("rep_range"))
            self.assertEqual(set_["load"], units.make_load(26, "per_hand_x2", "kg"))


class DoubleProgressionShortTest(ProposeCase):
    @staticmethod
    def workouts(found):
        def change(workout_id, index, set_):
            set_["weight_kg"] = 48.0
            if workout_id == W[3] and index == 2:
                set_["reps"] = 9
        edit_sets(BENCH, change)(found)

    def test_one_set_short_holds_the_load_and_adds_a_rep(self):
        line = find_line(self.propose("--dry-run")["overlay"], "db_bench_press")
        self.assertEqual({(s["reps"], coaching(s["load"])) for s in working(line)}, {(10, 24)})


class DoubleProgressionAfterOwnOverlayTest(ProposeCase):
    """Last week's approved overlay asked for 3×8 @ 24/hand, the bottom of the program's 8–10; 3×8 was logged."""

    synced = False

    def setUp(self):
        super().setUp()
        weekly = read_json(self.root / "data" / "overlays" / "2026-10-12-weekly.json")
        weekly.pop("approval")
        weekly.update(id="2026-10-05-weekly", created_at="2026-10-04T18:00:00Z",
                      span={"start": "2026-10-05", "end": "2026-10-11"})
        for session, day in zip(weekly["sessions"], ("2026-10-05", "2026-10-08")):
            session["date"] = day
        for set_ in working(find_line(weekly, "db_bench_press")):
            set_.update(reps=8, rep_range=None, load=units.make_load(24, "per_hand_x2", "kg"))
        approved = overlay.approve(weekly, dates.parse_timestamp("2026-10-04T19:00:00Z"))
        write_json(self.root / "data" / "overlays" / "2026-10-05-weekly.json", approved)
        self.cache(edit=edit_sets(BENCH, lambda wid, i, s: s.update(weight_kg=48.0, reps=8), workout_ids=(W[3],)))
        self.sync()

    def test_the_bottom_of_the_range_holds_the_load_and_adds_a_rep(self):
        line = find_line(self.propose("--dry-run")["overlay"], "db_bench_press")
        self.assertEqual({(s["reps"], coaching(s["load"])) for s in working(line)}, {(9, 24)})
        self.assertIn("short of the top of the range", line["provenance"]["rationale"])


class LinearTest(ProposeCase):
    workouts = staticmethod(edit_sets(SQUAT, lambda wid, i, s: s.update(reps=4)))

    def setUp(self):
        super().setUp()
        self.set_scheme("session-a", "bb_back_squat", "linear")

    def test_two_missed_exposures_reset_to_ninety_percent_rounded_down(self):
        data = self.propose()
        line = find_line(data["overlay"], "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {87.5})
        self.assertLessEqual(87.5, 97.5 * 0.9)
        meta = read_json(self.root / ".coach" / "proposals" / f"{FIRST_ID}.meta.json")
        self.assertEqual(meta["scheme_state"]["session-a/bb_back_squat"],
                         {"scheme": "linear", "data": {"misses": 0, "through": "2026-10-05"}})
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        state = read_json(self.root / "data" / "state.json")
        self.assertEqual(state["scheme_state"]["session-a/bb_back_squat"]["pending"],
                         {"overlay_id": FIRST_ID, "data": {"misses": 0, "through": "2026-10-05"}})


class LinearOneMissTest(ProposeCase):
    workouts = staticmethod(edit_sets(SQUAT, lambda wid, i, s: s.update(reps=4), workout_ids=(W[3],)))

    def test_one_miss_holds(self):
        self.set_scheme("session-a", "bb_back_squat", "linear")
        line = find_line(self.propose("--dry-run")["overlay"], "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {97.5})


class FixedRepsRpeTest(ProposeCase):
    def test_load_comes_from_the_e1rm_rounded_down(self):
        from coach import stats
        self.set_scheme("session-a", "bb_back_squat", "fixed_reps_rpe")
        best = max(p["e1rm"] for p in stats.e1rm_series(self.root)["series"]["bb_back_squat"])
        raw = stats.load_for(best, 5, 7)
        expected = 97.5 - 2.5 * math.ceil((97.5 - raw) / 2.5)
        line = find_line(self.propose("--dry-run")["overlay"], "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {expected})
        self.assertLessEqual(expected, raw)
        self.assertGreater(expected, raw - 2.5)


class HoldTest(ProposeCase):
    def test_hold_repeats_the_last_approved_line(self):
        self.set_scheme("session-a", "bb_back_squat", "hold")
        line = find_line(self.propose("--dry-run")["overlay"], "bb_back_squat")
        approved = find_line(read_json(self.root / "data" / "overlays" / "2026-10-12-weekly.json"), "bb_back_squat")
        self.assertEqual(line["sets"], approved["sets"])


class LayoffCase(ProposeCase):
    base = INSTANCES / "layoff"
    synced = False

    def log_pull_up_loads(self, mode, loads):
        """Every logged pull-up's working sets at `loads`, in order, as `mode` loads."""
        def edit(doc):
            for workout in doc["workouts"]:
                for exercise in workout["exercises"]:
                    if exercise["exercise_id"] == "pull_up":
                        exercise["load_mode"] = mode
                        for set_, value in zip(exercise["sets"], loads):
                            set_.update(weight_kg=float(value), load=units.make_load(value, mode, "kg"))
        self.edit_json("data/history/2026-09.json", edit)


class LayoffTest(LayoffCase):
    def test_hold_applies_the_22_42_band_and_raises_return_week(self):
        self.set_scheme("session-a", "bb_back_squat", "hold")
        doc = self.propose("--dry-run")["overlay"]
        line = find_line(doc, "bb_back_squat")
        self.assertEqual([coaching(s["load"]) for s in working(line)], [90, 90])
        self.assertEqual(line["provenance"]["decay"],
                         {"days_off": 28, "band": "22-42", "load_factor": 0.9, "set_delta": -1, "rpe_cap": None})
        self.assertIn("return_week", codes(doc, "bb_back_squat"))
        message = next(f["message"] for f in doc["flags"] if f["code"] == "return_week"
                       and f["exercise_id"] == "bb_back_squat")
        self.assertIn("28 days off: return band 22-42 (loads × 0.9, set change -1)", message)

    def test_mixed_added_loads_round_down_below_the_derived_from_load(self):
        self.log_pull_up_loads("bodyweight", (20, 18.75, 18.75))
        self.set_scheme("session-b", "pull_up", "double_progression")
        line = find_line(self.propose("--dry-run")["overlay"], "pull_up")
        self.assertEqual([coaching(s["load"]) for s in working(line)], [17.5, 17.5])

    def test_every_proposal_passes_the_prescription_check(self):
        data = self.propose()
        self.assertEqual([f for f in data["overlay"]["flags"] if f["severity"] == "block"], [])
        checked = self.coach("prescription", "check", "--file", str(self.draft_path()))["data"]
        self.assertEqual(checked["summary"]["block"], 0, checked["flags"])
        self.assertTrue(all(row["band"] == "22-42" for row in checked["lines"]))

    def test_a_scheme_that_does_not_decay_is_stale(self):
        with mock.patch.object(double_progression, "decay", lambda ctx, proposal, days_off: proposal):
            doc = self.propose("--dry-run")["overlay"]
        self.assertIn("stale_prescription", codes(doc, "bb_back_squat"))

    def test_three_exposures_with_no_gain_stall(self):
        doc = self.propose("--dry-run")["overlay"]
        self.assertIn("stalled", codes(doc, "db_bench_press"))
        self.assertNotIn("stalled", codes(doc, "bb_back_squat"))


class AssistedLayoffCase(LayoffCase):
    """The layoff instance with the pull-up logged and programmed as an assisted lift at 20 kg of assistance."""

    ASSISTANCE = 20

    def setUp(self):
        super().setUp()
        load = units.make_load(self.ASSISTANCE, "assisted", "kg")
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["pull_up"].update(
            load_mode="assisted", load_mode_proposed="assisted"))
        self.edit_program(lambda doc: self.slot(doc, "session-b", "pull_up").update(
            load_mode="assisted", start_load=self.ASSISTANCE))
        for month in ("2026-08", "2026-09"):
            self.edit_json(f"data/history/{month}.json", lambda doc: [
                (exercise.update(load_mode="assisted"),
                 [s.update(weight_kg=float(self.ASSISTANCE), load=dict(load)) for s in exercise["sets"]])
                for workout in doc["workouts"] for exercise in workout["exercises"]
                if exercise["exercise_id"] == "pull_up"])

    def pull_up_check(self, data):
        checked = self.coach("prescription", "check", "--file", str(self.draft_path(data["id"])))["data"]
        return [f for f in checked["flags"] if f["exercise_id"] == "pull_up"]


class AssistedReturnTest(AssistedLayoffCase):
    def test_mixed_assistance_rounds_up_to_keep_the_least_logged_assistance(self):
        self.log_pull_up_loads("assisted", (20, 18.75, 18.75))
        self.set_scheme("session-b", "pull_up", "double_progression")
        data = self.propose()
        line = find_line(data["overlay"], "pull_up")
        self.assertEqual([coaching(s["load"]) for s in working(line)], [20, 20])
        self.assertEqual(self.pull_up_check(data), [])

    def test_a_cap_still_wins_over_rounding_assistance_up(self):
        self.log_pull_up_loads("assisted", (20, 18.75, 18.75))
        self.set_scheme("session-b", "pull_up", "double_progression")
        self.set_config("[caps]", "[caps]\npull_up = 19")
        line = find_line(self.propose("--dry-run")["overlay"], "pull_up")
        self.assertEqual([coaching(s["load"]) for s in working(line)], [17.5, 17.5])

    def test_the_return_week_flag_says_the_assistance_is_held(self):
        self.set_scheme("session-b", "pull_up", "double_progression")
        doc = self.propose("--dry-run")["overlay"]
        [message] = [f["message"] for f in doc["flags"] if f["code"] == "return_week" and f["exercise_id"] == "pull_up"]
        self.assertEqual(message, "31 days off: return band 22-42 (assistance held, set change -1)")

    def test_a_double_progression_line_in_the_22_42_band_keeps_its_assistance(self):
        self.set_scheme("session-b", "pull_up", "double_progression")
        data = self.propose()
        line = find_line(data["overlay"], "pull_up")
        self.assertEqual(line["provenance"]["decay"]["band"], "22-42")
        self.assertEqual([coaching(s["load"]) for s in working(line)], [self.ASSISTANCE] * 2)
        self.assertEqual(self.pull_up_check(data), [])

    def test_a_ladder_line_in_the_11_21_band_steps_back_a_rung_and_passes(self):
        def logged_on_the_24th(doc):
            pulls = next(w for w in doc["workouts"] if w["date"] == "2026-09-10")
            later = json.loads(json.dumps(pulls))
            later.update(workout_id="10000000-0000-4000-8000-000000000090", date="2026-09-24",
                         start_time="2026-09-24T18:00:00Z", end_time="2026-09-24T19:00:00Z",
                         exercises=[e for e in later["exercises"] if e["exercise_id"] == "pull_up"])
            doc["workouts"].append(later)
            doc["workouts"].sort(key=lambda w: w["date"])
        self.edit_json("data/history/2026-09.json", logged_on_the_24th)
        self.set_scheme("session-b", "pull_up", "assistance_ladder", {"rungs": [
            {"name": "heavy band", "load": 40}, {"name": "medium band", "load": 30},
            {"name": "light band", "load": 20}]})
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({"session-b/pull_up": {
            "scheme": "assistance_ladder", "data": {"rung": 2, "through": "2026-09-24"}, "pending": None}}))
        data = self.propose()
        line = find_line(data["overlay"], "pull_up")
        self.assertEqual(line["provenance"]["decay"]["band"], "11-21")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {30})
        self.assertEqual(self.pull_up_check(data), [])

    def test_a_hand_built_line_with_less_assistance_than_before_the_layoff_is_stale(self):
        self.set_scheme("session-b", "pull_up", "double_progression")
        data = self.propose()

        def less_assistance(doc):
            line = find_line(doc, "pull_up")
            line["sets"] = [dict(s, load=10) if s["type"] in WORKING else s for s in line["sets"]]
        self.edit_json(f".coach/proposals/{data['id']}.json", less_assistance)
        [flag] = self.pull_up_check(data)
        self.assertEqual((flag["code"], flag["severity"]), ("stale_prescription", "block"))
        self.assertIn("assistance 10 is below the pre-layoff assistance of 20", flag["message"])


class IllnessTest(ProposeCase):
    def test_an_ill_miss_caps_the_first_session_at_rpe_7(self):
        self.coach("history", "annotate", "--kind", "miss", "--date", "2026-10-10", "--session", "session-a",
                   "--tag", "ill")
        doc = self.propose("--dry-run")["overlay"]
        first, later = doc["sessions"]
        for line in first["exercises"]:
            with self.subTest(exercise=line["exercise_id"]):
                self.assertTrue(all(s["rpe"] is not None and s["rpe"] <= 7 for s in working(line)))
        self.assertTrue(any(s["rpe"] == 8 for line in later["exercises"] for s in working(line)))
        [flag] = [f for f in doc["flags"] if f["code"] == "return_after_illness"]
        self.assertEqual((flag["session_id"], flag["exercise_id"]), ("session-a", None))
        self.assertIn("48 hours symptom-free", flag["message"])
        self.assertNotIn("stale_prescription", codes(doc))


class PluginLoadTest(ProposeCase):
    def test_a_plugin_returning_25_for_db_bench_gets_both_numbers(self):
        self.write_plugin("custom_fixed", fixed_load_plugin("custom_fixed"))
        self.set_scheme("session-a", "db_bench_press", "custom_fixed")
        line = find_line(self.propose("--dry-run")["overlay"], "db_bench_press")
        self.assertEqual(line["provenance"]["scheme"], "custom_fixed")
        for set_ in working(line):
            self.assertEqual(set_["load"], {"mode": "per_hand_x2", "unit": "kg", "per_hand": 25, "hevy_total": 50,
                                            "hevy_kg": 50.0})


class CapsAndConstraintsTest(ProposeCase):
    def test_a_caps_entry_clips_the_proposal(self):
        self.set_config("[caps]", "[caps]\ndb_bench_press = 24")
        doc = self.propose("--dry-run")["overlay"]
        line = find_line(doc, "db_bench_press")
        self.assertEqual({coaching(s["load"]) for s in working(line)}, {24})
        self.assertIn("constraint_applied", codes(doc, "db_bench_press"))
        self.assertNotIn("load_cap", codes(doc))

    def test_a_slot_rpe_cap_caps_every_working_set(self):
        self.edit_program(lambda doc: self.slot(doc, "session-a", "db_bench_press").update(
            constraints=[{"kind": "rpe_cap", "value": 7, "reason": "synthetic elbow"}]))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({s["rpe"] for s in working(find_line(doc, "db_bench_press"))}, {7})
        [flag] = [f for f in doc["flags"] if f["code"] == "constraint_applied"]
        self.assertIn("slot RPE cap 7 (synthetic elbow)", flag["message"])

    def test_a_load_cap_and_no_added_load(self):
        self.edit_program(lambda doc: (
            self.slot(doc, "session-a", "db_bench_press").update(
                constraints=[{"kind": "no_added_load", "value": None, "reason": "synthetic wrist"}]),
            self.slot(doc, "session-b", "pull_up").update(
                constraints=[{"kind": "load_cap", "value": 0, "reason": "synthetic shoulder"}])))
        doc = self.propose("--dry-run")["overlay"]
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}, {22.5})
        self.assertEqual({coaching(s["load"]) for s in working(find_line(doc, "pull_up"))}, {0})
        self.assertEqual(codes(doc).count("constraint_applied"), 2)


class HomeKitTest(ProposeCase):
    def setUp(self):
        super().setUp()
        self.write_plugin("custom_fixed", fixed_load_plugin("custom_fixed"))
        self.edit_program(lambda doc: doc["sessions"][0].update(location="home"))

    def bench(self, load):
        self.set_scheme("session-a", "db_bench_press", "custom_fixed", {"load": load})
        doc = self.propose("--dry-run")["overlay"]
        return doc, {coaching(s["load"]) for s in working(find_line(doc, "db_bench_press"))}

    def test_the_home_cap_clips_25_to_20(self):
        doc, loads = self.bench(25)
        self.assertEqual(loads, {20})
        self.assertIn("constraint_applied", codes(doc, "db_bench_press"))
        self.assertEqual(doc["sessions"][0]["location"], "home")

    def test_17_rounds_down_to_the_15_dumbbell(self):
        doc, loads = self.bench(17)
        self.assertEqual(loads, {15})
        self.assertNotIn("load_unrepresentable", codes(doc))


class RpeDriftTest(ProposeCase):
    @staticmethod
    def workouts(found):
        edit_sets(SQUAT, lambda wid, i, s: s.update(rpe=8), workout_ids=(W[3],))(found)
        edit_sets(BENCH, lambda wid, i, s: s.update(rpe=9), workout_ids=(W[3],))(found)

    def test_drift_fires_for_a_compound_lift(self):
        self.assertIn("rpe_drift", codes(self.propose("--dry-run")["overlay"], "bb_back_squat"))

    def test_an_isolation_lift_drifts_only_under_a_recovery_cap(self):
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"]["db_bench_press"].update(
            pattern="elbow_extension"))
        self.assertNotIn("rpe_drift", codes(self.propose("--dry-run")["overlay"], "db_bench_press"))
        self.edit_program(lambda doc: self.slot(doc, "session-a", "db_bench_press").update(
            constraints=[{"kind": "rpe_cap", "value": 8, "reason": "synthetic elbow"}]))
        self.assertIn("rpe_drift", codes(self.propose("--dry-run")["overlay"], "db_bench_press"))


class NoDataTest(ProposeCase):
    synced = False

    def test_no_exposure_and_no_start_load_leaves_the_load_empty(self):
        shutil.rmtree(self.root / "data" / "overlays")
        self.edit_program(lambda doc: self.slot(doc, "session-a", "db_bench_press").update(start_load=None))
        doc = self.propose("--dry-run")["overlay"]
        line = find_line(doc, "db_bench_press")
        self.assertEqual({s["load"] for s in working(line)}, {None})
        self.assertIn("no_data", codes(doc, "db_bench_press"))
        self.assertIsNone(line["provenance"]["derived_from"])
        squat = find_line(doc, "bb_back_squat")
        self.assertEqual({coaching(s["load"]) for s in working(squat)}, {100})


class ConventionSlipTest(ProposeCase):
    base = INSTANCES / "slip"
    synced = False

    def test_a_slip_candidate_is_never_derived_from(self):
        doc = self.propose("--dry-run")["overlay"]
        bench = find_line(doc, "db_bench_press")
        self.assertEqual(bench["provenance"]["derived_from"], {"date": "2026-09-28", "workout_id": W[1]})
        self.assertIn("convention_slip", codes(doc, "db_bench_press"))
        self.assertEqual({coaching(s["load"]) for s in working(bench)}, {24.5})


class DeloadTest(ProposeCase):
    def test_the_standard_deload(self):
        data = self.propose("--kind", "deload", "--dry-run")
        doc = data["overlay"]
        self.assertEqual((data["id"], doc["kind"]), ("2026-10-12-deload", "deload"))
        derived = {"bb_back_squat": 97.5, "db_bench_press": 22.5, "db_single_arm_row": 30, "pull_up": 0}
        increment = {"bb_back_squat": 2.5, "db_bench_press": 2, "db_single_arm_row": 2, "pull_up": 2.5}
        for session in doc["sessions"]:
            self.assertTrue(session["temporary"])
            self.assertTrue(session["title"].startswith("Deload — "))
            for line in session["exercises"]:
                with self.subTest(exercise=line["exercise_id"]):
                    sets = working(line)
                    self.assertEqual(len(sets), 2)
                    self.assertEqual({s["rpe"] for s in sets}, {6})
                    target = derived[line["exercise_id"]] * 0.9
                    for s in sets:
                        self.assertLessEqual(coaching(s["load"]), target + 1e-9)
                        self.assertGreater(coaching(s["load"]), target - increment[line["exercise_id"]] - 1e-9)


class OverrideTest(ProposeCase):
    def setUp(self):
        super().setUp()
        self.propose()

    def override(self, *extra, expect=0, env=None):
        envelope = self.coach("propose", "override", "--proposal", FIRST_ID, "--session", "session-a", "--exercise",
                              "bb_back_squat", *extra, expect=expect, env=env)
        return envelope["data"] if expect == 0 else envelope

    def test_a_standing_override_holds_until_its_end_date(self):
        data = self.override("--sets", "3x5@95 rpe7", "--reason", "knee", "--standing")
        draft = read_json(self.draft_path())
        line = find_line(draft, "bb_back_squat")
        proposed = find_line(read_json(self.root / ".coach" / "proposals" / f"{FIRST_ID}.proposed.json"),
                             "bb_back_squat")
        self.assertEqual(line["override"], {"reason": "knee", "proposed_sets": proposed["sets"]})
        self.assertEqual({s["load"] for s in working(line)}, {95})
        decision = data["decision"]
        self.assertEqual((decision["id"], decision["until"], decision["standing"]), ("d-0001", "2026-11-08", True))
        stored = read_json(self.root / "data" / "decisions.json")["decisions"]
        self.assertEqual(stored[0]["chosen_sets"], line["sets"])

        next_week = self.propose(env={"COACH_NOW": "2026-10-18T18:00:00Z"}, week="2026-W43")["overlay"]
        squat = find_line(next_week, "bb_back_squat")
        self.assertIn("override_standing", codes(next_week, "bb_back_squat"))
        self.assertEqual(squat["override"]["reason"], "knee")
        self.assertTrue(all(coaching(s["load"]) <= 95 for s in working(squat)))
        self.assertIn("standing override until 2026-11-08", squat["provenance"]["rationale"].lower())

        later = self.propose(env={"COACH_NOW": "2026-11-10T18:00:00Z"}, week="2026-W46")["overlay"]
        self.assertNotIn("override_standing", codes(later))
        self.assertIsNone(find_line(later, "bb_back_squat")["override"])
        listed = self.coach("decisions", "list", env={"COACH_NOW": "2026-11-10T18:00:00Z"})["data"]["decisions"]
        self.assertEqual(listed[0]["effective_status"], "expired")

    def test_a_withdrawn_override_stops_applying(self):
        self.override("--load", "95", "--reason", "knee", "--standing")
        self.coach("decisions", "withdraw", "d-0001", "--reason", "knee settled")
        doc = self.propose(env={"COACH_NOW": "2026-10-18T18:00:00Z"}, week="2026-W43")["overlay"]
        self.assertNotIn("override_standing", codes(doc))

    def test_a_standing_override_lasts_eight_weeks_at_most(self):
        envelope = self.override("--load", "95", "--reason", "knee", "--standing", "--until", "2026-12-31",
                                 expect=1)
        self.assertIn("at most 8 weeks", envelope["error"]["message"])
        self.override("--load", "95", "--reason", "knee", "--until", "2026-11-01", expect=2)

    def test_an_override_that_makes_a_block_shows_it_in_the_draft_to_resolve(self):
        data = self.override("--sets", "3x5@140 rpe7", "--reason", "synthetic test")
        index = next(i for i, f in enumerate(data["flags"]) if f["code"] == "unearned_load")
        envelope = self.coach("propose", "finalize", "--proposal", FIRST_ID, expect=3)
        self.assertIn("unearned_load", json.dumps(envelope["error"]))
        self.coach("propose", "resolve", "--proposal", FIRST_ID, "--flag", str(index), "--resolution",
                   "synthetic: the athlete tested it last week")
        self.assertTrue(self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]["written"])

    def test_dry_runs_write_nothing(self):
        before = self.snapshot()
        self.override("--load", "95", "--reason", "knee", "--standing", "--dry-run")
        self.coach("propose", "resolve", "--proposal", FIRST_ID, "--flag", "0", "--resolution", "x", "--dry-run")
        self.coach("propose", "finalize", "--proposal", FIRST_ID, "--dry-run")
        self.assertEqual(self.snapshot(), before)


class FinalizeTest(ProposeCase):
    def setUp(self):
        super().setUp()
        self.propose()

    def test_an_unexplained_hand_edit_exits_1(self):
        def edit(doc):
            working(find_line(doc, "bb_back_squat"))[0]["load"] = 92.5
        draft = read_json(self.draft_path())
        edit(draft)
        write_json(self.draft_path(), draft)
        envelope = self.coach("propose", "finalize", "--proposal", FIRST_ID, expect=1)
        self.assertEqual(envelope["error"]["details"][0]["path"], "session-a 2026-10-12 bb_back_squat")
        self.assertIn("unexplained", json.dumps(self.coach("propose", "show", FIRST_ID)["data"]))

    def test_an_explained_hand_edit_is_accepted(self):
        draft = read_json(self.draft_path())
        line = find_line(draft, "bb_back_squat")
        line["override"] = {"reason": "synthetic: bar felt slow", "proposed_sets": line["sets"]}
        line["sets"] = [dict(s, load=92.5) for s in line["sets"]]
        write_json(self.draft_path(), draft)
        data = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]
        self.assertEqual([d["standing"] for d in data["decisions"]], [False])
        self.assertEqual(data["decisions"][0]["until"], "2026-10-18")

    def test_finalize_writes_the_overlay_and_pending_state(self):
        data = self.coach("propose", "finalize", "--proposal", FIRST_ID)["data"]
        self.assertEqual(data["path"], f"data/overlays/{FIRST_ID}.json")
        doc = read_json(self.root / data["path"])
        self.assertEqual(overlay.validate(doc, self.root), [])
        self.assertIsNone(doc["approval"])
        state = read_json(self.root / "data" / "state.json")
        self.assertEqual(state["scheme_state"]["session-b/pull_up"]["pending"],
                         {"overlay_id": FIRST_ID, "data": {"misses": 0, "through": "2026-10-08"}})
        self.assertEqual(sorted(data["pending"]), sorted(f"{s}/{e}" for s, e in (
            ("session-a", "bb_back_squat"), ("session-a", "db_bench_press"), ("session-b", "db_single_arm_row"),
            ("session-b", "pull_up"))))

    def test_the_first_overlay_of_a_week_takes_the_plain_id(self):
        (self.root / "data" / "overlays" / "2026-10-12-weekly.json").unlink()
        self.propose()
        data = self.coach("propose", "finalize", "--proposal", "2026-10-12-weekly")["data"]
        self.assertEqual(data["path"], "data/overlays/2026-10-12-weekly.json")

    def test_approval_promotes_pending_state(self):
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        self.coach("overlay", "approve", FIRST_ID)
        settled = self.propose()["settled"]
        self.assertIn({"slot": "session-b/pull_up", "overlay_id": FIRST_ID, "action": "promoted"}, settled)
        entry = read_json(self.root / "data" / "state.json")["scheme_state"]["session-b/pull_up"]
        self.assertEqual(entry, {"scheme": "linear", "data": {"misses": 0, "through": "2026-10-08"}, "pending": None})

    def test_an_unapproved_overlay_drops_pending_state(self):
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        settled = self.propose()["settled"]
        self.assertIn({"slot": "session-b/pull_up", "overlay_id": FIRST_ID, "action": "dropped"}, settled)
        entry = read_json(self.root / "data" / "state.json")["scheme_state"]["session-b/pull_up"]
        self.assertEqual(entry, {"scheme": "linear", "data": {"misses": 0, "through": None}, "pending": None})

    def test_the_status_names_an_unfinalised_proposal(self):
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        self.assertIn(FIRST_ID, sections["proposal"]["lines"][0])
        self.coach("propose", "finalize", "--proposal", FIRST_ID)
        sections = {s["id"]: s for s in self.coach("status")["data"]["sections"]}
        self.assertNotIn("proposal", sections)


class SchemeResetTest(ProposeCase):
    def test_a_changed_scheme_restarts_its_state(self):
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update({
            "session-b/pull_up": {"scheme": "hold", "data": {}, "pending": None}}))
        doc = self.propose("--dry-run")["overlay"]
        [flag] = [f for f in doc["flags"] if f["code"] == "scheme_reset"]
        self.assertEqual(flag["exercise_id"], "pull_up")
        self.assertIn("from hold to linear", flag["message"])


class AlternatingTest(ProposeCase):
    def setUp(self):
        super().setUp()

        def change(doc):
            doc["external_sessions"] = [{"id": "pt-tue", "title": "PT", "weekday": "tue",
                                         "estimated_sets": {"chest": 3}}]
            doc["schedule"] = {"rule": "alternating_external_anchor", "params": {
                "weeks": [{"name": "week-a", "days": {"mon": "session-a", "thu": "session-b"}},
                          {"name": "week-b", "days": {"wed": "session-a", "fri": "session-b"}}],
                "anchor_external_id": "pt-tue"}}
        self.edit_program(change)
        self.edit_json("data/state.json", lambda doc: doc.update(rotation={
            "position": "week-a", "confirmed": True, "confirmed_at": "2026-10-04", "week": "2026-10-05"}))

    def test_the_rotation_advances_unconfirmed_until_confirmed(self):
        plan = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual(plan["rotation"], {"position": "week-b", "confirmed": False, "week": "2026-10-12"})
        self.assertEqual([(s["date"], s["session_id"]) for s in plan["sessions"]],
                         [("2026-10-14", "session-a"), ("2026-10-16", "session-b")])
        self.assertEqual([f["code"] for f in plan["flags"]], ["rotation_unconfirmed"])
        self.assertIn("rotation_unconfirmed", codes(self.propose("--dry-run")["overlay"]))

        confirmed = self.coach("schedule", "confirm", "--position", "week-b")["data"]
        self.assertEqual(confirmed["rotation"], {"position": "week-b", "confirmed": True,
                                                 "confirmed_at": "2026-10-11", "week": "2026-10-12"})
        plan = self.coach("schedule", "plan", "--week", WEEK)["data"]
        self.assertEqual((plan["rotation"]["confirmed"], plan["flags"]), (True, []))

    def test_confirm_takes_a_known_position(self):
        self.coach("schedule", "confirm", "--position", "week-c", expect=1)


class EvidenceTest(ProposeCase):
    def test_an_expired_cited_note_puts_the_line_under_review(self):
        text = (REPO_ROOT / "research" / "progression-training-age.md").read_text(encoding="utf-8")
        text = re.sub(r"written = \S+", "written = 2024-01-01", text, count=1)
        text = re.sub(r"review_by = \S+", "review_by = 2025-06-01", text, count=1)
        (self.root / "research" / "progression-training-age.md").write_text(text, encoding="utf-8")
        doc = self.propose("--dry-run")["overlay"]
        self.assertIn("evidence_expired", codes(doc, "db_bench_press"))
        self.assertIn("evidence under review (progression-training-age expired 2025-06-01)",
                      find_line(doc, "db_bench_press")["provenance"]["rationale"])
        self.assertNotIn("evidence_expired", [f["code"] for f in doc["flags"] if f["exercise_id"] == "pull_up"
                                              and "autoregulation" in f["message"]])


class SkillWiringTest(unittest.TestCase):
    def compute_and_other_steps(self):
        compute = flat(step_text("program-week", "compute.md"))
        steps = [path for path in skill_files("program-week")[1:] if path.name != "compute.md"]
        return compute, flat(" ".join(path.read_text(encoding="utf-8") for path in steps))

    def test_program_week_computes_with_propose(self):
        compute, others = self.compute_and_other_steps()
        for command in ("propose week", "propose override", "propose resolve", "propose finalize"):
            with self.subTest(command=command):
                self.assertIn(f"python3 -m coach {command}", compute)
        self.assertNotIn("propose ", others)

    def test_program_week_light_mode_deloads_with_propose(self):
        compute, others = self.compute_and_other_steps()
        self.assertIn("python3 -m coach propose week --kind deload", compute)
        self.assertNotIn("propose ", others)


if __name__ == "__main__":
    unittest.main()
