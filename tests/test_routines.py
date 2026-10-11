"""`routines diff|push|verify|retire` against the fake Hevy, and the builders behind them (contract C9, C10, C12)."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import dates, jsonio, overlay, routines, units
from coach.hevy.cache import HevyCache
from coach.validate import validate
from tests.support import FIXTURES, INSTANCES, VALID, run_cli
from tests.support.fake_hevy import FakeHevy

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
WEEKLY = "2026-10-12-weekly"
NOW = "2026-10-11T18:00:00Z"
R1 = "00000000-0000-4000-8000-000000000001"
R2 = "00000000-0000-4000-8000-000000000002"
ENV = {"HEVY_API_KEY": "k-0000-0000", "COACH_NOW": NOW}
ENVELOPE = jsonio.load_schema("envelope")


def read_overlay(root, overlay_id=WEEKLY):
    return json.loads(overlay.path_for(root, overlay_id).read_text(encoding="utf-8"))


def write_overlay(root, doc):
    jsonio.write_doc(overlay.path_for(root, doc["id"]), doc, dry_run=False)


def approved(doc):
    return overlay.approve(doc, dates.parse_timestamp(NOW))


def audit_lines(root):
    path = root / "data" / "hevy" / "writes.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def nulls(value, path="$"):
    if value is None:
        return [path]
    if isinstance(value, dict):
        return [p for key, item in value.items() for p in nulls(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [p for index, item in enumerate(value) for p in nulls(item, f"{path}[{index}]")]
    return []


class HalvingHevy(FakeHevy):
    """Stores the second DB bench set of Session A at half the weight it was sent."""

    def _stored_routine(self, request, existing):
        stored = super()._stored_routine(request, existing)
        if existing and existing.get("id") == R1:
            stored["exercises"][1]["sets"][1]["weight_kg"] /= 2
        return stored


class RoutinesCase(unittest.TestCase):
    fake_class = FakeHevy

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copytree(VALID, self.root, dirs_exist_ok=True)
        self.fake = self.fake_class(SYNTHETIC)
        for patcher in (mock.patch("coach.hevy.transport.from_env", return_value=self.fake),
                        mock.patch("coach.hevy.client.time.sleep")):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.cli("hevy", "pull", "--full")
        self.fake.requests.clear()

    def cli(self, *argv, expect=0, env=None):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env=env or ENV)
        self.assertEqual(code, expect, (envelope, stderr))
        self.assertEqual(validate(envelope, ENVELOPE), [], envelope)
        return envelope

    def routines_cmd(self, command, *extra, expect=0, env=None):
        return self.cli("routines", command, "--overlay", WEEKLY, *extra, expect=expect, env=env)

    def edit_overlay(self, change, approve=True):
        doc = read_overlay(self.root)
        change(doc)
        doc["approval"] = None
        write_overlay(self.root, approved(doc) if approve else doc)

    @property
    def put_paths(self):
        return [path for method, path, _ in self.fake.writes if method == "PUT"]

    def bench_changes(self, changes):
        return [c for c in changes if c["routine_id"] == R1 and c["path"].startswith("exercises[1].sets[")]


class DiffTest(RoutinesCase):
    def test_lists_db_bench_working_sets_at_hevy_50_and_classes_each_change(self):
        data = self.routines_cmd("diff")["data"]
        changes = data["changes"]
        self.assertTrue(changes)
        for change in changes:
            self.assertEqual(set(change), {"routine_id", "class", "path", "before", "after"})
            self.assertIn(change["class"], ("prescription", "structural"))
        bench = self.bench_changes(changes)
        for index in (1, 2, 3):
            path = f"exercises[1].sets[{index}]"
            found = [c for c in bench if c["path"] in (path, f"{path}.weight_kg")]
            self.assertEqual(len(found), 1, (index, bench))
            after = found[0]["after"]
            weight = after["weight_kg"] if isinstance(after, dict) else after
            self.assertEqual(weight, 50.0)
        weights = [c for c in bench if c["path"].endswith(".weight_kg")]
        self.assertTrue(weights)
        self.assertEqual({c["class"] for c in weights}, {"prescription"})
        added = [c for c in bench if c["path"] == "exercises[1].sets[3]"]
        self.assertEqual(added[0]["class"], "structural")
        self.assertIsNone(added[0]["before"])

    def test_diff_reads_the_cache_only(self):
        self.routines_cmd("diff")
        self.assertEqual(self.fake.requests, [])

    def test_refresh_regets_the_span_routines_into_the_cache(self):
        self.fake.collection("routines")[0]["title"] = "Session A (renamed in app)"
        data = self.routines_cmd("diff", "--refresh")["data"]
        self.assertEqual(sorted(r["path"] for r in self.fake.requests), [f"/v1/routines/{R1}", f"/v1/routines/{R2}"])
        self.assertEqual(HevyCache(self.root).routine(R1)["title"], "Session A (renamed in app)")
        self.assertEqual(data["routines"][0]["title"], "Session A (renamed in app)")

    def test_missing_cache_routine_exits_1_naming_hevy_pull(self):
        shutil.rmtree(self.root / ".coach")
        envelope = self.routines_cmd("diff", expect=1)
        self.assertIn("hevy pull", envelope["error"]["message"])

    def test_disabled_hevy_is_a_config_error(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("enabled = true", "enabled = false"), encoding="utf-8")
        self.routines_cmd("diff", expect=5)


class PushRefusalTest(RoutinesCase):
    def assert_refused(self, *extra, words=()):
        envelope = self.routines_cmd("push", *extra, expect=3)
        self.assertEqual(envelope["error"]["code"], "refused")
        self.assertEqual(self.fake.writes, [])
        for word in words:
            self.assertIn(word, envelope["error"]["message"] + json.dumps(envelope["error"].get("details", [])))
        return envelope

    def test_unapproved(self):
        self.edit_overlay(lambda doc: None, approve=False)
        self.assert_refused(words=("approved",))
        self.assert_refused("--dry-run")

    def test_stale_hash(self):
        doc = read_overlay(self.root)
        doc["focus"] = "Edited after approval."
        write_overlay(self.root, doc)
        self.assert_refused(words=("approv",))

    def test_unresolved_block_flag(self):
        flag = {"code": "stale_prescription", "severity": "block", "session_id": "session-a",
                "exercise_id": "db_bench_press", "message": "Last exposure is old.", "resolved": False,
                "resolution": None}
        self.edit_overlay(lambda doc: doc["flags"].append(flag))
        self.assert_refused(words=("stale_prescription",))

    def test_expired_span(self):
        envelope = self.routines_cmd("push", expect=3, env=dict(ENV, COACH_NOW="2026-10-19T08:00:00Z"))
        self.assertIn("ended", envelope["error"]["message"])
        self.assertEqual(self.fake.writes, [])

    def test_superseded_by_a_later_overlay(self):
        later = read_overlay(self.root)
        later.update(id="2026-10-14-midweek", kind="midweek", created_at="2026-10-13T08:00:00Z",
                     span={"start": "2026-10-14", "end": "2026-10-18"}, supersedes=WEEKLY, approval=None)
        later["sessions"] = [later["sessions"][1]]
        write_overlay(self.root, later)
        self.assert_refused(words=("2026-10-14-midweek",))

    def test_routine_changed_in_the_app_since_the_cache(self):
        self.fake.collection("routines")[1]["updated_at"] = "2026-10-11T07:30:00Z"
        envelope = self.assert_refused(words=("Session B",))
        self.assertNotIn("PUT", [r["method"] for r in self.fake.requests])
        self.assertIn("--refresh", envelope["error"]["message"])

    def test_refresh_does_not_bypass_an_app_edit(self):
        session_b = self.fake.collection("routines")[1]
        session_b["exercises"].append(copy.deepcopy(session_b["exercises"][0]))
        session_b["updated_at"] = "2026-10-11T07:30:00Z"
        cached_at = HevyCache(self.root).routine(R2)["updated_at"]
        self.assert_refused("--refresh", words=("Session B",))
        self.assert_refused("--refresh", "--dry-run", words=("Session B",))
        self.assertEqual(HevyCache(self.root).routine(R2)["updated_at"], cached_at)
        self.assert_refused(words=("Session B",))

        self.routines_cmd("diff", "--refresh")
        self.routines_cmd("push")
        self.assertIn(f"/v1/routines/{R2}", self.put_paths)


class PushTest(RoutinesCase):
    def test_after_approve_writes_each_routine_once_then_nothing(self):
        self.edit_overlay(lambda doc: None, approve=False)
        self.cli("overlay", "approve", WEEKLY)
        data = self.routines_cmd("push")["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}", f"/v1/routines/{R2}"])
        self.assertEqual([(r["method"], r["path"].rsplit("/", 1)[-1]) for r in self.fake.requests],
                         [("GET", R1), ("GET", R2), ("PUT", R1), ("GET", R1), ("PUT", R2), ("GET", R2)])
        self.assertEqual([r["status"] for r in data["routines"]], ["written", "written"])
        self.assertEqual(data["writes"], 2)
        lines = audit_lines(self.root)
        self.assertEqual([(l["kind"], l["routine_id"]) for l in lines],
                         [("write", R1), ("verify", R1), ("write", R2), ("verify", R2)])
        doc = read_overlay(self.root)
        for line in lines:
            schema = {"write": "hevy_write_line", "verify": "hevy_verify_line"}[line["kind"]]
            self.assertEqual(validate(line, jsonio.load_schema(schema)), [], line)
            self.assertEqual(line["overlay_id"], WEEKLY)
            self.assertEqual(line["overlay_hash"], doc["approval"]["hash"])
        self.assertTrue(all(l["verified"] and l["diff"] == [] for l in lines if l["kind"] == "verify"))

        again = self.routines_cmd("push")["data"]
        self.assertEqual(len(self.put_paths), 2)
        self.assertEqual([r["status"] for r in again["routines"]], ["unchanged", "unchanged"])
        self.assertEqual(again["writes"], 0)
        self.assertEqual(len(audit_lines(self.root)), 4)
        self.assertEqual(self.routines_cmd("diff")["data"]["changes"], [])

    def test_refresh_fills_routines_missing_from_the_cache(self):
        shutil.rmtree(self.root / ".coach")
        self.assertIn("hevy pull", self.routines_cmd("push", expect=1)["error"]["message"])
        data = self.routines_cmd("push", "--refresh")["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}", f"/v1/routines/{R2}"])
        self.assertEqual([r["status"] for r in data["routines"]], ["written", "written"])

    def test_put_bodies_have_no_nulls_and_no_routine_notes(self):
        self.routines_cmd("push")
        self.assertEqual(len(self.fake.put_bodies), 2)
        for body in self.fake.put_bodies:
            self.assertEqual(nulls(body), [])
            self.assertNotIn("notes", body["routine"])

    def test_weight_comes_from_hevy_kg_and_notes_follow_c12(self):
        self.routines_cmd("push")
        session_a = self.fake.put_bodies[0]["routine"]
        bench = session_a["exercises"][1]
        self.assertEqual([s.get("weight_kg") for s in bench["sets"]], [25, 50, 50, 50])
        self.assertEqual(bench["notes"], "Target: 3×8–10 @ 25/hand (Hevy: 50) @ RPE 8\n"
                                         "Focus: pause 1 s on the chest\nCues: elbows tucked · feet planted")
        self.assertTrue(session_a["exercises"][0]["notes"].startswith("Wk of 12 Oct: Heavier top sets"))
        self.assertEqual(session_a["title"], "Session A")
        pull_up = self.fake.put_bodies[1]["routine"]["exercises"][1]
        self.assertTrue(all("weight_kg" not in s for s in pull_up["sets"]))

    def test_dry_run_writes_nothing_and_matches_diff(self):
        diff = self.routines_cmd("diff")["data"]["changes"]
        cache_before = (self.root / ".coach" / "cache" / "hevy" / "routines.json").read_bytes()
        data = self.routines_cmd("push", "--dry-run")["data"]
        self.assertEqual(self.fake.writes, [])
        self.assertEqual(data["changes"], diff)
        self.assertEqual(data["writes"], 0)
        self.assertEqual(audit_lines(self.root), [])
        self.assertEqual((self.root / ".coach" / "cache" / "hevy" / "routines.json").read_bytes(), cache_before)

    def test_null_load_line_sends_no_weight_and_says_choose_the_load(self):
        def no_data(doc):
            bench = doc["sessions"][0]["exercises"][1]
            bench["sets"] = [{"type": "normal", "rep_range": {"start": 8, "end": 10}, "rpe": 7, "load": None}
                             for _ in range(3)]
            doc["flags"].append({"code": "no_data", "severity": "info", "session_id": "session-a",
                                 "exercise_id": "db_bench_press", "message": "No logged exposure yet.",
                                 "resolved": False, "resolution": None})
        self.edit_overlay(no_data)
        self.routines_cmd("push")
        bench = self.fake.put_bodies[0]["routine"]["exercises"][1]
        self.assertEqual(len(bench["sets"]), 3)
        for set_ in bench["sets"]:
            self.assertNotIn("weight_kg", set_)
            self.assertEqual(set_["rep_range"], {"start": 8, "end": 10})
        self.assertEqual(bench["notes"].splitlines()[0], "Target: 3×8–10 @ RPE 7 · choose the load")
        stored = self.fake.collection("routines")[0]["exercises"][1]["sets"]
        self.assertEqual({s["weight_kg"] for s in stored}, {None})
        verify = self.routines_cmd("verify")["data"]
        self.assertTrue(verify["verified"])


    def test_a_routine_serving_two_sessions_carries_the_next_one(self):
        def repeat_a(doc):
            saturday = copy.deepcopy(doc["sessions"][0])
            saturday["date"] = "2026-10-17"
            for set_ in saturday["exercises"][0]["sets"][1:]:
                set_["load"] = units.make_load(102.5, "total", "kg")
            doc["sessions"].append(saturday)
        self.edit_overlay(repeat_a)
        envelope = self.routines_cmd("push")
        squat = self.fake.put_bodies[0]["routine"]["exercises"][0]["sets"]
        self.assertEqual([s["weight_kg"] for s in squat], [60, 100, 100, 100])
        self.assertTrue(any("2026-10-17" in w for w in envelope["warnings"]), envelope["warnings"])
        later = self.routines_cmd("diff", env=dict(ENV, COACH_NOW="2026-10-13T08:00:00Z"))["data"]
        entry = later["routines"][0]
        self.assertEqual((entry["date"], entry["carries"]), ("2026-10-17", ["2026-10-12", "2026-10-17"]))
        self.assertEqual({c["after"] for c in entry["changes"] if c["path"].endswith("weight_kg")}, {102.5})

    def test_a_session_without_a_routine_exits_1_before_any_request(self):
        self.edit_overlay(lambda doc: doc["sessions"][1].update(hevy_routine_id=None))
        envelope = self.routines_cmd("push", expect=1)
        self.assertIn("session-b", envelope["error"]["message"])
        self.assertEqual(self.fake.requests, [])
        self.routines_cmd("diff", expect=1)

    def test_an_unapproved_overlay_with_a_session_without_a_routine_is_still_refused(self):
        self.edit_overlay(lambda doc: doc["sessions"][1].update(hevy_routine_id=None), approve=False)
        self.routines_cmd("push", expect=3)


class VerifyFailureTest(RoutinesCase):
    fake_class = HalvingHevy

    def test_tampered_weight_exits_1_logs_false_and_leaves_later_routines_unwritten(self):
        envelope = self.routines_cmd("push", expect=1)
        self.assertEqual(envelope["error"]["code"], "validation")
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}"])
        lines = audit_lines(self.root)
        self.assertEqual([(l["kind"], l["routine_id"]) for l in lines], [("write", R1), ("verify", R1)])
        self.assertFalse(lines[1]["verified"])
        self.assertEqual([c["path"] for c in lines[1]["diff"]], ["exercises[1].sets[1].weight_kg"])
        self.assertEqual(lines[1]["diff"][0]["after"], 50)
        statuses = [r["status"] for r in envelope["data"]["routines"]]
        self.assertEqual(statuses, ["failed", "not_reached"])


class VerifyTest(RoutinesCase):
    def test_true_after_push_false_with_the_diff_after_an_app_edit(self):
        self.routines_cmd("push")
        data = self.routines_cmd("verify")["data"]
        self.assertTrue(data["verified"])
        self.assertEqual([(r["routine_id"], r["verified"]) for r in data["routines"]], [(R1, True), (R2, True)])

        stored = self.fake.collection("routines")[1]
        stored["exercises"][0]["sets"][0]["weight_kg"] = 32.0
        stored["updated_at"] = "2026-10-11T19:00:00Z"
        data = self.routines_cmd("verify", "--refresh")["data"]
        self.assertFalse(data["verified"])
        by_id = {r["routine_id"]: r for r in data["routines"]}
        self.assertTrue(by_id[R1]["verified"])
        self.assertFalse(by_id[R2]["verified"])
        self.assertEqual([(c["path"], c["before"], c["after"]) for c in by_id[R2]["changes"]],
                         [("exercises[0].sets[0].weight_kg", 32.0, 30)])
        self.assertEqual(len(self.fake.writes), 2)

    def test_verify_before_any_push_reports_false(self):
        data = self.routines_cmd("verify")["data"]
        self.assertFalse(data["verified"])
        self.assertEqual(self.fake.requests, [])


ONE_OFF = "2026-10-12-one-off"


class RetireTest(RoutinesCase):
    def setUp(self):
        super().setUp()
        doc = read_overlay(self.root)
        doc.update(id=ONE_OFF, kind="one_off", approval=None)
        for session in doc["sessions"]:
            session["temporary"] = True
            session["title"] = f"Travel {session['title']}"
        write_overlay(self.root, approved(doc))
        overlay.path_for(self.root, WEEKLY).unlink()

    def retire(self, *extra, expect=0, now="2026-10-19T08:00:00Z"):
        return self.cli("routines", "retire", "--overlay", ONE_OFF, *extra, expect=expect,
                        env=dict(ENV, COACH_NOW=now))

    def test_retitles_each_temporary_routine_and_keeps_its_exercises(self):
        before = copy.deepcopy(self.fake.collection("routines"))
        data = self.retire()["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{R1}", f"/v1/routines/{R2}"])
        for body, old in zip(self.fake.put_bodies, before):
            self.assertEqual(body["routine"]["title"], "(unused)")
            self.assertEqual([e["exercise_template_id"] for e in body["routine"]["exercises"]],
                             [e["exercise_template_id"] for e in old["exercises"]])
            self.assertEqual(nulls(body), [])
        after = self.fake.collection("routines")
        for new, old in zip(after, before):
            self.assertEqual([[s["weight_kg"] for s in e["sets"]] for e in new["exercises"]],
                             [[s["weight_kg"] for s in e["sets"]] for e in old["exercises"]])
        self.assertEqual([r["status"] for r in data["routines"]], ["retired", "retired"])
        lines = audit_lines(self.root)
        self.assertEqual([l["kind"] for l in lines], ["write", "retire", "write", "retire"])
        for line in lines[1::2]:
            self.assertEqual(validate(line, jsonio.load_schema("hevy_retire_line")), [], line)
            self.assertTrue(line["verified"])
        self.assertEqual(self.retire()["data"]["writes"], 0)
        self.assertEqual(len(self.put_paths), 2)

    def test_span_not_ended_exits_3(self):
        envelope = self.retire(expect=3, now=NOW)
        self.assertEqual(envelope["error"]["code"], "refused")
        self.assertEqual(self.fake.writes, [])

    def test_dry_run_writes_nothing(self):
        data = self.retire("--dry-run")["data"]
        self.assertEqual(self.fake.writes, [])
        self.assertEqual([r["status"] for r in data["routines"]], ["would_retire", "would_retire"])
        self.assertEqual(audit_lines(self.root), [])

    def test_a_routine_a_live_overlay_still_uses_is_left_alone(self):
        current = read_overlay(self.root, ONE_OFF)
        current.update(id="2026-10-19-one-off", span={"start": "2026-10-19", "end": "2026-10-25"},
                       created_at="2026-10-18T08:00:00Z", approval=None)
        current["sessions"] = [dict(current["sessions"][0], date="2026-10-20")]
        write_overlay(self.root, current)
        data = self.retire()["data"]
        self.assertEqual(self.put_paths, [f"/v1/routines/{R2}"])
        self.assertEqual([r["status"] for r in data["routines"]], ["in_use", "retired"])


class SummaryTest(RoutinesCase):
    def test_names_each_changed_routine_and_both_dumbbell_numbers(self):
        report = self.routines_cmd("push", "--dry-run")["data"]
        text = routines.summary(report)
        self.assertEqual(report["summary"], text)
        self.assertIn("Session A", text)
        self.assertIn("Session B", text)
        self.assertIn("25/hand (Hevy: 50)", text)
        self.assertIn("22.5/hand (Hevy: 45)", text)
        self.assertIn("100 kg", text)

    def test_nothing_to_write(self):
        self.routines_cmd("push")
        text = routines.summary(self.routines_cmd("push", "--dry-run")["data"])
        self.assertIn("nothing to write", text)


class IntendedBodyTest(unittest.TestCase):
    def setUp(self):
        self.doc = overlay.load(VALID, WEEKLY)
        cached = json.loads((SYNTHETIC / "routines.json").read_text(encoding="utf-8"))["routines"]
        self.cached = {r["id"]: r for r in cached}

    def body(self, index=0):
        session = self.doc["sessions"][index]
        return routines.intended_body(self.doc, session, self.cached[session["hevy_routine_id"]])

    def test_keeps_the_routine_title_and_folder(self):
        routine = self.body()["routine"]
        self.assertEqual(routine["title"], "Session A")
        self.assertEqual(routine["folder_id"], 1)
        self.assertNotIn("notes", routine)

    def test_temporary_session_takes_its_own_title(self):
        session = dict(self.doc["sessions"][0], temporary=True, title="Hotel A")
        body = routines.intended_body(self.doc, session, self.cached[R1])
        self.assertEqual(body["routine"]["title"], "Hotel A")

    def test_sets_carry_only_set_values(self):
        sets = self.body()["routine"]["exercises"][1]["sets"]
        self.assertEqual(sets[0], {"type": "warmup", "weight_kg": 25, "reps": 10})
        self.assertEqual(sets[1], {"type": "normal", "weight_kg": 50, "rep_range": {"start": 8, "end": 10}})

    def test_a_line_without_a_hevy_template_id_is_a_validation_error(self):
        session = copy.deepcopy(self.doc["sessions"][0])
        session["exercises"][0]["hevy_template_id"] = None
        with self.assertRaises(routines.ValidationError):
            routines.intended_body(self.doc, session, self.cached[R1])


class DiffFunctionTest(unittest.TestCase):
    def setUp(self):
        self.doc = overlay.load(VALID, WEEKLY)
        cached = json.loads((SYNTHETIC / "routines.json").read_text(encoding="utf-8"))["routines"]
        self.cached = {r["id"]: r for r in cached}
        self.intended = routines.intended_body(self.doc, self.doc["sessions"][1], self.cached[R2])

    def stored(self):
        """The routine as the fake would store the intended body."""
        fake = FakeHevy(SYNTHETIC)
        fake.request("PUT", f"/v1/routines/{R2}", body=self.intended)
        return copy.deepcopy(fake.collection("routines")[1])

    def test_a_faithful_read_back_has_no_changes(self):
        self.assertEqual(routines.diff(self.intended, self.stored()), [])

    def test_weight_within_a_gram_matches(self):
        stored = self.stored()
        stored["exercises"][0]["sets"][0]["weight_kg"] = 30.0004
        self.assertEqual(routines.diff(self.intended, stored), [])

    def test_classes(self):
        stored = self.stored()
        stored["exercises"][0]["sets"][0]["weight_kg"] = 27.5
        stored["exercises"][0]["notes"] = "old note"
        stored["exercises"][0]["rest_seconds"] = 60
        stored["exercises"][1]["sets"][2]["reps"] = 6
        stored["exercises"][1]["sets"].append(copy.deepcopy(stored["exercises"][1]["sets"][0]))
        found = {c["path"]: c["class"] for c in routines.diff(self.intended, stored)}
        self.assertEqual(found, {
            "exercises[0].sets[0].weight_kg": "prescription",
            "exercises[0].notes": "prescription",
            "exercises[0].rest_seconds": "structural",
            "exercises[1].sets[2].reps": "structural",
            "exercises[1].sets[3]": "structural",
        })

    def test_a_swapped_exercise_is_one_structural_change(self):
        stored = self.stored()
        stored["exercises"][1]["exercise_template_id"] = "F0000001"
        changes = routines.diff(self.intended, stored)
        self.assertEqual([(c["path"], c["class"]) for c in changes], [("exercises[1]", "structural")])

    def test_missing_weight_matches_a_null_load(self):
        intended = copy.deepcopy(self.intended)
        for set_ in intended["routine"]["exercises"][0]["sets"]:
            del set_["weight_kg"]
        stored = self.stored()
        for set_ in stored["exercises"][0]["sets"]:
            set_["weight_kg"] = None
        self.assertEqual(routines.diff(intended, stored), [])
        for set_ in stored["exercises"][0]["sets"]:
            del set_["weight_kg"]
        self.assertEqual(routines.diff(intended, stored), [])


class DriftCheckTest(unittest.TestCase):
    def check(self, root, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), "check", "--only", "overlay_hevy_drift"],
                                         env={"COACH_NOW": now})
        self.assertIn(code, (0, 1), (envelope, stderr))
        results = envelope["data"]["results"]
        self.assertTrue(all(r["owner"] == "R-14" for r in results))
        return results

    def test_matching_cache_passes(self):
        results = self.check(INSTANCES / "routines-pushed")
        self.assertEqual([r["status"] for r in results], ["pass"], results)

    def test_drifted_cache_warns_per_routine(self):
        results = self.check(INSTANCES / "routines-drift")
        self.assertEqual([r["status"] for r in results], ["warn", "warn"], results)
        self.assertIn("Session A", results[0]["message"])
        self.assertIn(WEEKLY, results[0]["message"])

    def test_skips_without_a_cache(self):
        self.assertEqual([r["status"] for r in self.check(VALID)], ["skip"])

    def test_skips_when_hevy_is_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(INSTANCES / "routines-drift", tmp, dirs_exist_ok=True)
            path = Path(tmp, "config.toml")
            path.write_text(path.read_text(encoding="utf-8").replace("enabled = true", "enabled = false"),
                            encoding="utf-8")
            self.assertEqual([r["status"] for r in self.check(tmp)], ["skip"])


if __name__ == "__main__":
    unittest.main()
