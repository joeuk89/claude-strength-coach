import io
import os
import socket
import unittest
import urllib.error
from unittest import mock

from coach.hevy import transport
from coach.hevy.transport import FixtureTransport, TransportTimeout, TransportUnreachable, UrllibTransport
from tests.support import FIXTURES

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
LATER = FIXTURES / "hevy" / "synthetic-later"
R1 = "00000000-0000-4000-8000-000000000001"


class FixtureTransportTest(unittest.TestCase):
    def setUp(self):
        self.t = FixtureTransport(SYNTHETIC)

    def get(self, path, **params):
        return self.t.request("GET", path, params=params)

    def test_pages_workouts_newest_first(self):
        first = self.get("/v1/workouts", page=1, pageSize=3)
        self.assertEqual(first.status, 200)
        self.assertEqual(first.body["page_count"], 2)
        self.assertEqual([w["start_time"][:10] for w in first.body["workouts"]],
                         ["2026-10-08", "2026-10-05", "2026-10-01"])
        second = self.get("/v1/workouts", page=2, pageSize=3)
        self.assertEqual([w["start_time"][:10] for w in second.body["workouts"]], ["2026-09-28"])

    def test_page_size_over_the_api_limit_is_a_400(self):
        self.assertEqual(self.get("/v1/workouts", page=1, pageSize=11).status, 400)
        self.assertEqual(self.get("/v1/exercise_templates", page=1, pageSize=100).status, 200)

    def test_single_items_and_count(self):
        self.assertEqual(self.get(f"/v1/routines/{R1}").body["routine"]["title"], "Session A")
        self.assertEqual(self.get("/v1/routines/nope").status, 404)
        self.assertEqual(self.get("/v1/workouts/count").body, {"workout_count": 4})
        self.assertEqual(self.get("/v1/exercise_templates/F0000002").body["title"], "Bench Press (Dumbbell)")

    def test_missing_collection_is_empty(self):
        body = self.get("/v1/workouts/events", page=1, pageSize=10, since="1970-01-01T00:00:00Z").body
        self.assertEqual(body, {"page": 1, "page_count": 0, "events": []})

    def test_later_directories_override_earlier_ones_per_file(self):
        layered = FixtureTransport(os.pathsep.join([str(SYNTHETIC), str(LATER)]))
        events = layered.request("GET", "/v1/workouts/events",
                                 params={"page": 1, "pageSize": 10, "since": "2026-10-11T00:00:00Z"}).body["events"]
        self.assertEqual(sorted(e["type"] for e in events), ["deleted", "updated"])
        self.assertEqual(len(layered.request("GET", "/v1/routines", params={"page": 1, "pageSize": 10})
                             .body["routines"]), 2)

    def test_events_are_filtered_by_since(self):
        layered = FixtureTransport(os.pathsep.join([str(SYNTHETIC), str(LATER)]))
        body = layered.request("GET", "/v1/workouts/events",
                               params={"page": 1, "pageSize": 10, "since": "2026-10-12T08:30:00Z"}).body
        self.assertEqual([e["type"] for e in body["events"]], ["deleted"])

    def test_callers_get_copies(self):
        self.get(f"/v1/routines/{R1}").body["routine"]["title"] = "changed"
        self.get("/v1/routines", page=1, pageSize=10).body["routines"][0]["title"] = "changed"
        self.assertEqual(self.get(f"/v1/routines/{R1}").body["routine"]["title"], "Session A")

    def test_writes_are_refused(self):
        response = self.t.request("PUT", f"/v1/routines/{R1}", body={"routine": {}})
        self.assertEqual(response.status, 405)

    def test_from_env_picks_fixtures_when_set(self):
        self.assertIsInstance(transport.from_env({"COACH_HEVY_FIXTURES": str(SYNTHETIC)}), FixtureTransport)
        self.assertIsInstance(transport.from_env({}), UrllibTransport)


class _FakeHTTPResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class UrllibTransportTest(unittest.TestCase):
    def test_sends_the_key_header_and_parses_json(self):
        seen = {}

        def fake_urlopen(req, timeout):
            seen["url"] = req.full_url
            seen["key"] = req.get_header("Api-key")
            seen["timeout"] = timeout
            return _FakeHTTPResponse(b'{"workout_count": 3}')

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            response = UrllibTransport().request("GET", "/v1/workouts/count", params={"a": 1},
                                                 headers={"api-key": "k"})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, {"workout_count": 3})
        self.assertEqual(seen["url"], "https://api.hevyapp.com/v1/workouts/count?a=1")
        self.assertEqual(seen["key"], "k")

    def test_http_errors_become_responses(self):
        error = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b'{"error": "bad key"}'))
        with mock.patch("urllib.request.urlopen", side_effect=error):
            response = UrllibTransport().request("GET", "/v1/workouts/count")
        self.assertEqual((response.status, response.body), (401, {"error": "bad key"}))

    def test_timeouts_and_unreachable(self):
        cases = [
            (socket.timeout("timed out"), TransportTimeout),
            (urllib.error.URLError(socket.timeout("timed out")), TransportTimeout),
            (urllib.error.URLError(OSError("no route")), TransportUnreachable),
        ]
        for raised, expected in cases:
            with self.subTest(raised=raised), mock.patch("urllib.request.urlopen", side_effect=raised):
                with self.assertRaises(expected):
                    UrllibTransport().request("GET", "/v1/workouts/count")


if __name__ == "__main__":
    unittest.main()
