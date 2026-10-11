"""Helpers for history and stats tests: an instance copy with a Hevy cache, and fixture-set edits (C14, C15, C17)."""

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support import FIXTURES, VALID, run_cli
from tests.support.activity import write_hevy_cache

SYNTHETIC = FIXTURES / "hevy" / "synthetic"
NOW = "2026-10-11T18:00:00Z"
W = {n: f"10000000-0000-4000-8000-00000000000{n}" for n in range(1, 10)}
R_A = "00000000-0000-4000-8000-000000000001"
R_B = "00000000-0000-4000-8000-000000000002"
DB_BENCH_LOAD = {"mode": "per_hand_x2", "unit": "kg", "per_hand": 22.5, "hevy_total": 45, "hevy_kg": 45.0}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fixture_workouts(fixture_dir=SYNTHETIC):
    return read_json(Path(fixture_dir) / "workouts.json")["workouts"]


def hevy_set(index, weight_kg, reps, rpe, kind="normal"):
    return {"index": index, "type": kind, "weight_kg": weight_kg, "reps": reps, "distance_meters": None,
            "duration_seconds": None, "rpe": rpe, "custom_metric": None}


def hevy_exercise(index, title, template_id, sets):
    return {"index": index, "title": title, "notes": "", "exercise_template_id": template_id,
            "superset_id": None, "sets": sets}


def hevy_workout(workout_id, routine_id, title, day, exercises, start="18:00", end="19:00", updated=None):
    return {"id": workout_id, "title": title, "routine_id": routine_id, "description": "",
            "start_time": f"{day}T{start}:00Z", "end_time": f"{day}T{end}:00Z",
            "updated_at": updated or f"{day}T{end}:05Z", "created_at": f"{day}T{end}:05Z", "exercises": exercises}


class HistoryCase(unittest.TestCase):
    """A temp copy of an instance (default `valid/`) with a Hevy cache written from a fixture set."""

    base = VALID

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.root = self.tmp / "instance"
        shutil.copytree(self.base, self.root)
        self.env = {"COACH_NOW": NOW}

    def fixture_set(self, workouts=None, edit=None):
        """A fixture set copied from synthetic/, with its workouts replaced or edited."""
        directory = Path(tempfile.mkdtemp(dir=self.tmp))
        for path in SYNTHETIC.glob("*.json"):
            shutil.copy(path, directory / path.name)
        found = copy.deepcopy(workouts if workouts is not None else fixture_workouts())
        if edit:
            edit(found)
        write_json(directory / "workouts.json", {"x-synthetic": True, "workouts": found})
        return directory

    def cache(self, workouts=None, edit=None):
        """Write the instance's Hevy cache from the synthetic set, optionally changed."""
        shutil.rmtree(self.root / ".coach" / "cache" / "hevy", ignore_errors=True)
        write_hevy_cache(self.root, self.fixture_set(workouts, edit))

    def coach(self, *argv, expect=0, env=None):
        code, envelope, stderr = run_cli(["--root", str(self.root), *argv], env=dict(self.env, **(env or {})))
        self.assertEqual(code, expect, (envelope, stderr))
        return envelope

    def sync(self, **kwargs):
        return self.coach("history", "sync", **kwargs)["data"]

    def month(self, month):
        return read_json(self.root / "data" / "history" / f"{month}.json")

    def history_bytes(self):
        directory = self.root / "data" / "history"
        return {p.name: p.read_bytes() for p in sorted(directory.glob("*.json"))} if directory.is_dir() else {}

    def edit_json(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)
