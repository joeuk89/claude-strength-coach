import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from coach import jsonio
from coach.errors import ConfigError, NetworkError, ValidationError
from coach.hevy import envfile
from coach.hevy.client import HevyClient
from coach.validate import validate
from tests.support import FIXTURES
from tests.support.fake_hevy import FakeClock, FakeHevy

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
R1 = "00000000-0000-4000-8000-000000000001"
WRITE_LINE = jsonio.load_schema("hevy_write_line")


def routine_body(title="Session A", weight=100.0):
    return {"routine": {"title": title, "exercises": [
        {"exercise_template_id": "F0000001", "rest_seconds": 180, "notes": "Target: 3×5 @ 100 kg",
         "sets": [{"type": "normal", "weight_kg": weight, "reps": 5}]}]}}


class ClientCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.audit = Path(self._tmp.name) / "data" / "hevy" / "writes.jsonl"
        self.clock = FakeClock()
        self.fake = FakeHevy(SYNTHETIC, clock=self.clock)
        self.client = HevyClient(self.fake, "TESTKEY-123", clock=self.clock.now, sleep=self.clock.sleep,
                                 audit_path=self.audit)

    def audit_lines(self):
        if not self.audit.exists():
            return []
        return [json.loads(line) for line in self.audit.read_text(encoding="utf-8").splitlines()]


class ReadTest(ClientCase):
    def test_get_sends_the_key_header(self):
        self.assertEqual(self.client.get("/v1/workouts/count"), {"workout_count": 4})
        self.assertEqual(self.fake.requests[0]["headers"]["api-key"], "TESTKEY-123")

    def test_paginate_walks_every_page(self):
        workouts = list(self.client.paginate("/v1/workouts", "workouts", page_size=3))
        self.assertEqual(len(workouts), 4)
        self.assertEqual([r["params"]["page"] for r in self.fake.requests], [1, 2])

    def test_paginate_passes_extra_params(self):
        list(self.client.paginate("/v1/workouts/events", "events", params={"since": "2026-01-01T00:00:00Z"}))
        self.assertEqual(self.fake.requests[0]["params"]["since"], "2026-01-01T00:00:00Z")

    def test_reads_are_not_audited_or_rate_limited(self):
        for _ in range(12):
            self.client.get("/v1/workouts/count")
        self.assertEqual(self.clock.slept, [])
        self.assertEqual(self.audit_lines(), [])


class ErrorTest(ClientCase):
    def test_401_and_403_are_config_errors_naming_the_key(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.fake.fail_next(status, {"error": "Unauthorized"})
                with self.assertRaises(ConfigError) as caught:
                    self.client.get("/v1/workouts/count")
                self.assertIn("HEVY_API_KEY", caught.exception.message)

    def test_timeout_and_5xx_are_network_errors(self):
        self.fake.timeout_next()
        with self.assertRaises(NetworkError):
            self.client.get("/v1/workouts/count")
        self.fake.fail_next(502, None)
        with self.assertRaises(NetworkError):
            self.client.get("/v1/workouts/count")

    def test_other_4xx_is_a_validation_error_carrying_the_status(self):
        with self.assertRaises(ValidationError) as caught:
            self.client.get("/v1/routines/nope")
        self.assertEqual(caught.exception.status, 404)

    def test_a_429_backs_off_30_seconds_then_succeeds(self):
        self.fake.fail_next(429, {"error": "Too many requests"})
        self.assertEqual(self.client.get("/v1/workouts/count"), {"workout_count": 4})
        self.assertEqual(self.clock.slept, [30])

    def test_three_429s_in_a_row_give_up(self):
        self.fake.fail_next(429, None, times=3)
        with self.assertRaises(NetworkError) as caught:
            self.client.get("/v1/workouts/count")
        self.assertIn("429", caught.exception.message)
        self.assertEqual(self.clock.slept, [30, 30])

    def test_no_message_carries_the_key(self):
        for status in (401, 404, 500):
            self.fake.fail_next(status, {"error": "TESTKEY-123 is not valid"})
            with self.assertRaises(Exception) as caught:
                self.client.get("/v1/workouts/count")
            self.assertNotIn("TESTKEY-123", str(caught.exception))


class WriteTest(ClientCase):
    def test_put_returns_the_body_and_appends_one_audit_line(self):
        result = self.client.put(f"/v1/routines/{R1}", routine_body(), overlay_id="2026-10-12-weekly",
                                 overlay_hash="sha256:" + "0" * 64)
        self.assertEqual(result["routine"]["exercises"][0]["sets"][0]["weight_kg"], 100.0)
        [line] = self.audit_lines()
        self.assertEqual(validate(line, WRITE_LINE), [])
        self.assertEqual(line["kind"], "write")
        self.assertEqual(line["method"], "PUT")
        self.assertEqual(line["status"], 200)
        self.assertEqual(line["routine_id"], R1)
        self.assertEqual(line["overlay_id"], "2026-10-12-weekly")
        self.assertEqual(line["at"], "2026-10-11T18:00:00Z")
        self.assertEqual(line["request_body"], routine_body())
        self.assertEqual(line["request_sha256"], jsonio.canonical_hash(routine_body()))

    def test_failed_writes_are_audited_too(self):
        bad = routine_body()
        bad["routine"]["exercises"][0]["sets"][0]["rep_range"] = None
        with self.assertRaises(ValidationError) as caught:
            self.client.put(f"/v1/routines/{R1}", bad)
        self.assertIn("Expected object, received null", caught.exception.message)
        self.fake.timeout_next()
        with self.assertRaises(NetworkError):
            self.client.post("/v1/routines", routine_body("New"))
        lines = self.audit_lines()
        self.assertEqual([(l["method"], l["status"]) for l in lines], [("PUT", 400), ("POST", None)])
        for line in lines:
            self.assertEqual(validate(line, WRITE_LINE), [])
            self.assertIsNone(line["overlay_id"])

    def test_every_put_and_post_through_the_fake_appends_one_line(self):
        self.client.put(f"/v1/routines/{R1}", routine_body())
        created = self.client.post("/v1/routines", routine_body("Temp"))
        self.client.post("/v1/routine_folders", {"routine_folder": {"title": "One-off weeks"}})
        lines = self.audit_lines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1]["routine_id"], None)
        self.assertTrue(created["routine"]["id"])

    def test_eight_writes_are_spaced_by_the_bucket(self):
        for n in range(8):
            self.client.put(f"/v1/routines/{R1}", routine_body(weight=100.0 + n))
        times = [line["at"] for line in self.audit_lines()]
        self.assertEqual(times, [
            "2026-10-11T18:00:00Z", "2026-10-11T18:00:00Z", "2026-10-11T18:00:00Z",
            "2026-10-11T18:00:03Z", "2026-10-11T18:00:06Z", "2026-10-11T18:00:09Z",
            "2026-10-11T18:00:12Z", "2026-10-11T18:00:15Z",
        ])
        self.assertEqual([line["status"] for line in self.audit_lines()], [200] * 8)

    def test_a_write_429_is_retried_after_30_seconds(self):
        self.fake.fail_next(429, None)
        self.client.put(f"/v1/routines/{R1}", routine_body())
        self.assertIn(30, self.clock.slept)
        [line] = self.audit_lines()
        self.assertEqual(line["status"], 200)

    def test_the_fake_returns_429_after_seven_rapid_writes(self):
        rapid = HevyClient(self.fake, "k", clock=self.clock.now, sleep=self.clock.sleep, audit_path=self.audit,
                           write_burst=100)
        for n in range(7):
            rapid.put(f"/v1/routines/{R1}", routine_body(weight=100.0 + n))
        self.fake.clock.current += timedelta(seconds=1)
        rapid.put(f"/v1/routines/{R1}", routine_body())
        self.assertEqual(self.clock.slept, [30])

    def test_the_audit_never_holds_the_key(self):
        self.client.put(f"/v1/routines/{R1}", routine_body())
        self.assertNotIn("TESTKEY-123", self.audit.read_text(encoding="utf-8"))

    def test_writes_need_an_audit_path(self):
        client = HevyClient(self.fake, "k", clock=self.clock.now, sleep=self.clock.sleep)
        with self.assertRaises(RuntimeError):
            client.put(f"/v1/routines/{R1}", routine_body())
        self.assertEqual(self.fake.writes, [])


class FakeBehaviourTest(ClientCase):
    def test_routine_notes_are_dropped_and_updated_at_bumps(self):
        body = routine_body()
        body["routine"]["notes"] = "week focus"
        self.clock.current += timedelta(hours=1)
        self.client.put(f"/v1/routines/{R1}", body)
        stored = self.client.get(f"/v1/routines/{R1}")["routine"]
        self.assertNotIn("notes", stored)
        self.assertEqual(stored["updated_at"], "2026-10-11T19:00:00Z")
        self.assertEqual(self.fake.put_bodies, [body])


class EnvFileTest(unittest.TestCase):
    def test_environment_wins_then_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(envfile.api_key(root, {}))
            (root / ".env").write_text('# comment\nexport HEVY_API_KEY="from-file"\nOTHER=x\n', encoding="utf-8")
            self.assertEqual(envfile.api_key(root, {}), "from-file")
            self.assertEqual(envfile.api_key(root, {"HEVY_API_KEY": "from-env"}), "from-env")
            (root / ".env").write_text("HEVY_API_KEY=\n", encoding="utf-8")
            self.assertIsNone(envfile.api_key(root, {"HEVY_API_KEY": "  "}))


if __name__ == "__main__":
    unittest.main()
