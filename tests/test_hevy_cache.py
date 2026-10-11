import json
import tempfile
import unittest
from pathlib import Path

from coach.errors import ValidationError
from coach.hevy.cache import HevyCache

R1 = "00000000-0000-4000-8000-000000000001"
W = "10000000-0000-4000-8000-00000000000{}"


def wrap(data, fetched_at="2026-10-11T18:00:00Z"):
    return {"schema_version": 1, "fetched_at": fetched_at, "source": "hevy", "data": data}


class HevyCacheTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.dir = self.root / ".coach" / "cache" / "hevy"
        self.cache = HevyCache(self.root)

    def write(self, relative, doc):
        path = self.dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_an_empty_cache_reads_as_nothing(self):
        self.assertIsNone(self.cache.meta())
        self.assertEqual(self.cache.routines(), [])
        self.assertEqual(self.cache.workouts(), [])
        self.assertIsNone(self.cache.routine(R1))

    def test_reads_collections_unwrapped(self):
        self.write("routines.json", wrap([{"id": R1, "title": "Session A"}]))
        self.write("routine_folders.json", wrap([{"id": 1, "title": "Program"}]))
        self.write("exercise_templates.json", wrap([{"id": "F0000001"}]))
        self.write("body_measurements.json", wrap([{"date": "2026-10-05", "weight_kg": 80.4}]))
        self.assertEqual(self.cache.routine(R1)["title"], "Session A")
        self.assertEqual(self.cache.folders()[0]["title"], "Program")
        self.assertEqual(self.cache.exercise_templates(), [{"id": "F0000001"}])
        self.assertEqual(self.cache.body_measurements()[0]["weight_kg"], 80.4)

    def test_workouts_oldest_first_and_since(self):
        for n, day in ((1, "2026-09-28"), (3, "2026-10-05"), (2, "2026-10-01")):
            self.write(f"workouts/{W.format(n)}.json", wrap({"id": W.format(n), "start_time": f"{day}T18:00:00Z"}))
        self.assertEqual([w["id"][-1] for w in self.cache.workouts()], ["1", "2", "3"])
        self.assertEqual([w["id"][-1] for w in self.cache.workouts(since="2026-10-01")], ["2", "3"])
        self.assertEqual([w["id"][-1] for w in self.cache.workouts(since="2026-10-01T19:00:00Z")], ["3"])

    def test_upsert_routine_replaces_or_adds(self):
        self.write("routines.json", wrap([{"id": R1, "title": "Session A"}], "2026-10-10T00:00:00Z"))
        self.cache.upsert_routine({"id": R1, "title": "Session A2"})
        self.cache.upsert_routine({"id": "new", "title": "Temp"})
        self.assertEqual([r["title"] for r in self.cache.routines()], ["Session A2", "Temp"])
        doc = json.loads((self.dir / "routines.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["fetched_at"], "2026-10-10T00:00:00Z")

    def test_a_newer_schema_version_is_refused(self):
        self.write("routines.json", {"schema_version": 2, "fetched_at": "x", "source": "hevy", "data": []})
        with self.assertRaises(ValidationError) as caught:
            self.cache.routines()
        self.assertIn("framework-sync", caught.exception.message)

    def test_unsafe_workout_ids_are_refused(self):
        with self.assertRaises(ValidationError):
            self.cache.workout("../config")


if __name__ == "__main__":
    unittest.main()
