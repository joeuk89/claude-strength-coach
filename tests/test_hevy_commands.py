import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coach import jsonio
from coach.context import Context
from coach.hevy.client import HevyClient
from coach.validate import validate
from tests.support import FIXTURES, INSTANCES, VALID, run_cli, run_module
from tests.support.fake_hevy import FakeHevy

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
LATER = FIXTURES / "hevy" / "synthetic-later"
NOW = "2026-10-11T18:00:00Z"
FIXTURE_ENV = {"COACH_HEVY_FIXTURES": str(SYNTHETIC), "COACH_NOW": NOW}
COUNTS = {"workouts": 4, "routines": 2, "routine_folders": 1, "exercise_templates": 4, "body_measurements": 2}
W2 = "10000000-0000-4000-8000-000000000002"
W3 = "10000000-0000-4000-8000-000000000003"
R1 = "00000000-0000-4000-8000-000000000001"
C8_FILES = ["body_measurements.json", "exercise_templates.json", "meta.json", "routine_folders.json",
            "routines.json"] + [f"workouts/10000000-0000-4000-8000-00000000000{n}.json" for n in range(1, 5)]
ENVELOPE = jsonio.load_schema("envelope")


def snapshot(directory):
    if not directory.exists():
        return {}
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()}


class InstanceCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        shutil.copy(VALID / "config.toml", self.root / "config.toml")
        self.cache_dir = self.root / ".coach" / "cache" / "hevy"

    def run_hevy(self, *argv, env=None, expect=0):
        code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", *argv], env=env)
        self.assertEqual(code, expect, (envelope, stderr))
        self.assertEqual(validate(envelope, ENVELOPE), [])
        return envelope, stderr


class PullTest(InstanceCase):
    def test_full_pull_writes_every_c8_file(self):
        code, envelope, stderr = run_module(["--root", str(self.root), "hevy", "pull", "--full"], env=FIXTURE_ENV)
        self.assertEqual(code, 0, (envelope, stderr))
        data = envelope["data"]
        self.assertEqual(data["counts"], COUNTS)
        self.assertEqual(data["mode"], "full")
        self.assertEqual(sorted(snapshot(self.cache_dir)), C8_FILES)
        for name in C8_FILES:
            with self.subTest(name=name):
                doc = json.loads((self.cache_dir / name).read_text(encoding="utf-8"))
                self.assertEqual(doc["schema_version"], 1)
        wrapped = json.loads((self.cache_dir / "routines.json").read_text(encoding="utf-8"))
        self.assertEqual(set(wrapped), {"schema_version", "fetched_at", "source", "data"})
        self.assertEqual(wrapped["data"][0]["id"], R1)
        meta = json.loads((self.cache_dir / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["counts"], COUNTS)
        self.assertEqual(meta["last_full_pull_at"], NOW)
        self.assertEqual(meta["events_since"], NOW)

    def test_status_reports_the_same_counts_and_the_pull_time(self):
        pulled = self.run_hevy("pull", "--full", env=FIXTURE_ENV)[0]["data"]
        later = dict(FIXTURE_ENV, COACH_NOW="2026-10-12T06:00:00Z")
        status = self.run_hevy("status", env=later)[0]["data"]
        self.assertEqual(status["counts"], pulled["counts"])
        self.assertEqual(status["pulled_at"], pulled["pulled_at"])
        self.assertEqual(status["pulled_at"], NOW)
        self.assertEqual(status["age_hours"], 12.0)
        self.assertFalse(status["stale"])

    def test_status_without_a_cache(self):
        status = self.run_hevy("status", env={"COACH_NOW": NOW})[0]["data"]
        self.assertEqual(status["cache"], "missing")
        self.assertIsNone(status["counts"])
        self.assertEqual(status["key"], "missing")

    def test_a_pull_with_no_cache_is_full(self):
        data = self.run_hevy("pull", env=FIXTURE_ENV)[0]["data"]
        self.assertEqual(data["mode"], "full")

    def test_incremental_pull_applies_one_update_and_one_delete(self):
        self.run_hevy("pull", "--full", env=FIXTURE_ENV)
        before = json.loads((self.cache_dir / "meta.json").read_text(encoding="utf-8"))
        env = {"COACH_HEVY_FIXTURES": os.pathsep.join([str(SYNTHETIC), str(LATER)]),
               "COACH_NOW": "2026-10-13T07:00:00Z"}
        data = self.run_hevy("pull", env=env)[0]["data"]
        self.assertEqual(data["mode"], "incremental")
        self.assertEqual(data["changes"]["workouts"], {"added": 0, "updated": 1, "removed": 1})
        self.assertFalse((self.cache_dir / "workouts" / f"{W2}.json").exists())
        updated = json.loads((self.cache_dir / "workouts" / f"{W3}.json").read_text(encoding="utf-8"))
        self.assertEqual(updated["data"]["exercises"][1]["sets"][2]["reps"], 9)
        meta = json.loads((self.cache_dir / "meta.json").read_text(encoding="utf-8"))
        self.assertGreater(meta["events_since"], before["events_since"])
        self.assertEqual(meta["events_since"], "2026-10-13T07:00:00Z")
        self.assertEqual(meta["last_full_pull_at"], NOW)
        self.assertEqual(meta["counts"]["workouts"], 3)

    def test_dry_run_leaves_the_cache_byte_identical(self):
        empty = self.run_hevy("pull", "--dry-run", env=FIXTURE_ENV)[0]["data"]
        self.assertEqual(snapshot(self.root / ".coach"), {})
        self.assertTrue(empty["dry_run"])
        self.assertEqual(empty["changes"]["workouts"]["added"], 4)

        self.run_hevy("pull", "--full", env=FIXTURE_ENV)
        before = snapshot(self.root)
        env = {"COACH_HEVY_FIXTURES": os.pathsep.join([str(SYNTHETIC), str(LATER)]),
               "COACH_NOW": "2026-10-13T07:00:00Z"}
        data = self.run_hevy("pull", "--dry-run", env=env)[0]["data"]
        self.assertEqual(data["changes"]["workouts"], {"added": 0, "updated": 1, "removed": 1})
        self.assertEqual(data["counts"]["workouts"], 3)
        self.assertEqual(snapshot(self.root), before)

    def test_disabled_hevy_is_a_config_error(self):
        config = (self.root / "config.toml").read_text(encoding="utf-8").replace("enabled = true", "enabled = false")
        (self.root / "config.toml").write_text(config, encoding="utf-8")
        envelope, _ = self.run_hevy("pull", env=FIXTURE_ENV, expect=5)
        self.assertIn("enabled", envelope["error"]["message"])


class PullFailureTest(InstanceCase):
    def with_fake(self, fake):
        return mock.patch("coach.hevy.transport.from_env", return_value=fake)

    def test_no_key_exits_5_naming_it_before_any_request(self):
        fake = FakeHevy(SYNTHETIC)
        with self.with_fake(fake):
            envelope, _ = self.run_hevy("pull", env={"COACH_NOW": NOW}, expect=5)
        self.assertIn("HEVY_API_KEY", envelope["error"]["message"])
        self.assertEqual(fake.requests, [])

    def test_a_key_in_dotenv_is_used(self):
        (self.root / ".env").write_text("HEVY_API_KEY=dotenv-key-0001\n", encoding="utf-8")
        fake = FakeHevy(SYNTHETIC)
        with self.with_fake(fake):
            self.run_hevy("pull", env={"COACH_NOW": NOW})
        self.assertEqual(fake.requests[0]["headers"]["api-key"], "dotenv-key-0001")

    def test_401_exits_5(self):
        fake = FakeHevy(SYNTHETIC)
        fake.fail_next(401, {"error": "Unauthorized"})
        with self.with_fake(fake):
            envelope, _ = self.run_hevy("pull", env={"HEVY_API_KEY": "k-0000-0000", "COACH_NOW": NOW}, expect=5)
        self.assertEqual(envelope["error"]["code"], "config")

    def test_timeout_exits_4(self):
        fake = FakeHevy(SYNTHETIC)
        fake.timeout_next()
        with self.with_fake(fake):
            envelope, _ = self.run_hevy("pull", env={"HEVY_API_KEY": "k-0000-0000", "COACH_NOW": NOW}, expect=4)
        self.assertEqual(envelope["error"]["code"], "network")
        self.assertFalse((self.cache_dir / "meta.json").exists())

    def test_three_429s_exit_4(self):
        fake = FakeHevy(SYNTHETIC)
        fake.fail_next(429, None, times=3)
        with self.with_fake(fake), mock.patch("coach.hevy.client.time.sleep") as sleep:
            self.run_hevy("pull", env={"HEVY_API_KEY": "k-0000-0000", "COACH_NOW": NOW}, expect=4)
        self.assertEqual([c.args for c in sleep.call_args_list], [(30,), (30,)])


class KeyNeverLeaksTest(InstanceCase):
    def test_the_key_appears_nowhere_after_pull_and_write(self):
        key = "TESTKEY-123"
        env = {"HEVY_API_KEY": key, "COACH_NOW": NOW}
        fake = FakeHevy(SYNTHETIC)
        fake.fail_next(404, {"error": f"echo {key}"})
        outputs = []
        with mock.patch("coach.hevy.transport.from_env", return_value=fake):
            code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", "pull"], env=env)
            outputs += [json.dumps(envelope), stderr]
            code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", "pull", "--full"], env=env)
            self.assertEqual(code, 0, envelope)
            outputs += [json.dumps(envelope), stderr]
            code, envelope, stderr = run_cli(["--root", str(self.root), "hevy", "status"], env=env)
            outputs += [json.dumps(envelope), stderr]

            ctx = Context(self.root, env, io.StringIO())
            client = HevyClient.from_context(ctx)
            client.put(f"/v1/routines/{R1}", {"routine": {"title": "Session A", "exercises": []}})
        self.assertEqual(fake.requests[-1]["headers"]["api-key"], key)
        files = [p for p in (self.root / ".coach").rglob("*") if p.is_file()]
        files.append(self.root / "data" / "hevy" / "writes.jsonl")
        self.assertTrue(files[-1].is_file())
        for path in files:
            outputs.append(path.read_text(encoding="utf-8"))
        for text in outputs:
            self.assertNotIn(key, text)


class RecordFixturesTest(InstanceCase):
    def test_refuses_when_fixtures_are_set(self):
        out = self.root / "recorded"
        envelope, _ = self.run_hevy("record-fixtures", "--out", str(out),
                                    env={"COACH_HEVY_FIXTURES": str(SYNTHETIC), "HEVY_API_KEY": "k-0000-0000"},
                                    expect=3)
        self.assertIn("COACH_HEVY_FIXTURES", envelope["error"]["message"])
        self.assertFalse(out.exists())

    def test_needs_a_real_key(self):
        fake = FakeHevy(SYNTHETIC)
        with mock.patch("coach.hevy.transport.from_env", return_value=fake):
            envelope, _ = self.run_hevy("record-fixtures", "--out", str(self.root / "recorded"),
                                        env={"COACH_NOW": NOW}, expect=5)
        self.assertIn("HEVY_API_KEY", envelope["error"]["message"])

    def test_records_with_gets_only_and_anonymises(self):
        out = self.root / "recorded"
        fake = FakeHevy(SYNTHETIC)
        with mock.patch("coach.hevy.transport.from_env", return_value=fake):
            envelope, stderr = self.run_hevy("record-fixtures", "--out", str(out),
                                             env={"HEVY_API_KEY": "TESTKEY-123", "COACH_NOW": NOW})
        self.assertEqual({r["method"] for r in fake.requests}, {"GET"})
        self.assertNotIn("/v1/user/info", {r["path"] for r in fake.requests})
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, ["body_measurements.json", "exercise_templates.json", "routine_folders.json",
                                 "routines.json", "workout_events.json", "workouts.json"])
        self.assertEqual(envelope["data"]["counts"]["workouts"], 4)
        text = "".join(p.read_text(encoding="utf-8") for p in out.iterdir())
        self.assertNotIn(R1, text)
        self.assertNotIn("Session A", text)
        self.assertNotIn("TESTKEY-123", text + stderr + json.dumps(envelope))
        self.assertIn("F0000002", text)
        replay = FakeHevy(out)
        self.assertEqual(replay.request("GET", "/v1/workouts/count").body, {"workout_count": 4})

    def test_dry_run_writes_nothing(self):
        out = self.root / "recorded"
        with mock.patch("coach.hevy.transport.from_env", return_value=FakeHevy(SYNTHETIC)):
            self.run_hevy("record-fixtures", "--out", str(out), "--dry-run",
                          env={"HEVY_API_KEY": "TESTKEY-123", "COACH_NOW": NOW})
        self.assertFalse(out.exists())


class CacheAgeCheckTest(unittest.TestCase):
    def check(self, root, now=NOW):
        code, envelope, stderr = run_cli(["--root", str(root), "check", "--only", "hevy_cache_age"],
                                         env={"COACH_NOW": now})
        self.assertIn(code, (0, 1), (envelope, stderr))
        return envelope["data"]["results"][0]

    def test_fresh_cache_passes(self):
        result = self.check(INSTANCES / "hevy-fresh")
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["owner"], "R-12")

    def test_stale_cache_warns(self):
        result = self.check(INSTANCES / "hevy-stale")
        self.assertEqual(result["status"], "warn")
        self.assertIn("hevy pull", result["message"])

    def test_missing_cache_warns(self):
        self.assertEqual(self.check(VALID)["status"], "warn")

    def test_disabled_hevy_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = (VALID / "config.toml").read_text(encoding="utf-8").replace("enabled = true", "enabled = false")
            Path(tmp, "config.toml").write_text(config, encoding="utf-8")
            self.assertEqual(self.check(tmp)["status"], "skip")


if __name__ == "__main__":
    unittest.main()
