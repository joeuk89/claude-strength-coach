import copy
import json
import unittest
from datetime import date

from coach.errors import ValidationError
from coach.hevy.anonymise import anonymise

ROUTINE_ID = "7d3c2b1a-0000-4abc-9def-123456789abc"
WORKOUT_IDS = ["aa11bb22-3333-4444-8555-666677778888", "bb22cc33-4444-4555-8666-777788889999"]
DELETED_ID = "cc33dd44-5555-4666-8777-88889999aaaa"
CUSTOM_ID = "e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5b"
BUILTIN_ID = "79D0BB3A"
FOLDER_ID = 314159
KEY = "REALKEY-9f8e7d6c"
PRIVATE_TEXT = ["Monday Murder Session", "Push day w/ Sam", "Knee felt sore after the second set",
                "Slept 5 hours, wiped out", "Sam's sled push", "My Plan Folder", "Keep the elbows in tight today"]


def exercise(template_id, title, notes):
    return {"index": 0, "title": title, "notes": notes, "exercise_template_id": template_id, "superset_id": None,
            "sets": [{"index": 0, "type": "normal", "weight_kg": 92.5, "reps": 5, "rpe": 8,
                      "distance_meters": None, "duration_seconds": None, "custom_metric": None}]}


def workout(workout_id, title, description, start):
    return {"id": workout_id, "title": title, "routine_id": ROUTINE_ID, "description": description,
            "start_time": f"{start}T07:15:00Z", "end_time": f"{start}T08:20:00Z",
            "updated_at": f"{start}T08:25:31.123Z", "created_at": f"{start}T08:25:31.123Z",
            "exercises": [exercise(BUILTIN_ID, "Bench Press (Barbell)", "Knee felt sore after the second set"),
                          exercise(CUSTOM_ID, "Sam's sled push", "")]}


def real_responses():
    return {
        "workouts": [workout(WORKOUT_IDS[0], "Monday Murder Session", "Slept 5 hours, wiped out", "2026-06-01"),
                     workout(WORKOUT_IDS[1], "Push day w/ Sam", "", "2026-06-04")],
        "workout_events": [{"type": "updated", "workout": workout(WORKOUT_IDS[1], "Push day w/ Sam", "",
                                                                  "2026-06-04")},
                           {"type": "deleted", "id": DELETED_ID, "deleted_at": "2026-06-05T10:00:00Z"}],
        "routines": [{"id": ROUTINE_ID, "title": "Push day w/ Sam", "folder_id": FOLDER_ID,
                      "notes": "Keep the elbows in tight today",
                      "updated_at": "2026-05-30T12:00:00Z", "created_at": "2026-01-02T12:00:00Z",
                      "exercises": [dict(exercise(CUSTOM_ID, "Sam's sled push", "Keep the elbows in tight today"),
                                         rest_seconds=90)]}],
        "routine_folders": [{"id": FOLDER_ID, "index": 0, "title": "My Plan Folder",
                             "updated_at": "2026-01-02T12:00:00Z", "created_at": "2026-01-02T12:00:00Z"}],
        "exercise_templates": [
            {"id": BUILTIN_ID, "title": "Bench Press (Barbell)", "type": "weight_reps", "is_custom": False},
            {"id": CUSTOM_ID, "title": "Sam's sled push", "type": "weight_reps", "is_custom": True},
        ],
        "body_measurements": [{"date": "2026-06-01", "weight_kg": 93.7, "fat_percent": 21.4, "waist": None}],
        "user_info": {"data": {"id": "user-1", "name": "Sam Example", "url": "https://hevy.com/user/sam"}},
    }


class AnonymiseTest(unittest.TestCase):
    def setUp(self):
        self.original = real_responses()
        self.out = anonymise(copy.deepcopy(self.original), "salt-1", secrets=[KEY])
        self.text = json.dumps(self.out, ensure_ascii=False)

    def test_custom_ids_titles_and_notes_are_replaced(self):
        workouts = self.out["workouts"]
        self.assertEqual([w["title"] for w in workouts], ["Workout 1", "Workout 2"])
        self.assertEqual(self.out["routines"][0]["title"], "Routine 1")
        self.assertEqual(self.out["routine_folders"][0]["title"], "Folder 1")
        custom = self.out["exercise_templates"][1]
        self.assertEqual(custom["title"], "Custom exercise 1")
        self.assertNotEqual(custom["id"], CUSTOM_ID)
        self.assertEqual(workouts[0]["exercises"][1]["title"], "Custom exercise 1")
        self.assertEqual(workouts[0]["exercises"][1]["exercise_template_id"], custom["id"])
        self.assertRegex(workouts[0]["description"], r"^note \d+$")
        self.assertEqual(workouts[1]["description"], "")
        self.assertEqual(workouts[0]["exercises"][1]["notes"], "")
        self.assertRegex(self.out["routines"][0]["notes"], r"^note \d+$")

    def test_builtin_templates_are_kept(self):
        self.assertEqual(self.out["exercise_templates"][0], self.original["exercise_templates"][0])
        first = self.out["workouts"][0]["exercises"][0]
        self.assertEqual((first["exercise_template_id"], first["title"]), (BUILTIN_ID, "Bench Press (Barbell)"))

    def test_joins_survive(self):
        routine = self.out["routines"][0]
        folder = self.out["routine_folders"][0]
        self.assertEqual({w["routine_id"] for w in self.out["workouts"]}, {routine["id"]})
        self.assertEqual(routine["folder_id"], folder["id"])
        self.assertIsInstance(folder["id"], int)
        self.assertEqual(self.out["workout_events"][0]["workout"]["id"], self.out["workouts"][1]["id"])
        self.assertRegex(routine["id"], r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

    def test_ids_are_deterministic_per_salt(self):
        again = anonymise(real_responses(), "salt-1")
        other = anonymise(real_responses(), "salt-2")
        self.assertEqual(again["routines"][0]["id"], self.out["routines"][0]["id"])
        self.assertNotEqual(other["routines"][0]["id"], self.out["routines"][0]["id"])

    def test_timestamps_shift_by_whole_weeks(self):
        before = date.fromisoformat(self.original["workouts"][0]["start_time"][:10])
        after_text = self.out["workouts"][0]["start_time"]
        after = date.fromisoformat(after_text[:10])
        shift = (after - before).days
        self.assertNotEqual(shift, 0)
        self.assertEqual(shift % 7, 0)
        self.assertEqual(after_text[10:], "T07:15:00Z")
        self.assertEqual(self.out["workouts"][0]["updated_at"][10:], "T08:25:31.123Z")
        measured = date.fromisoformat(self.out["body_measurements"][0]["date"])
        self.assertEqual((measured - date(2026, 6, 1)).days, shift)
        deleted = date.fromisoformat(self.out["workout_events"][1]["deleted_at"][:10])
        self.assertEqual((deleted - date(2026, 6, 5)).days, shift)

    def test_training_numbers_stay_and_body_values_are_synthetic(self):
        sets = self.out["workouts"][0]["exercises"][0]["sets"][0]
        self.assertEqual((sets["weight_kg"], sets["reps"], sets["rpe"]), (92.5, 5, 8))
        body = self.out["body_measurements"][0]
        self.assertNotEqual(body["weight_kg"], 93.7)
        self.assertNotEqual(body["fat_percent"], 21.4)
        self.assertIsNone(body["waist"])

    def test_user_info_is_dropped(self):
        self.assertNotIn("user_info", self.out)
        self.assertNotIn("Sam Example", self.text)

    def test_nothing_original_is_left(self):
        for original in [ROUTINE_ID, CUSTOM_ID, DELETED_ID, *WORKOUT_IDS, *PRIVATE_TEXT]:
            with self.subTest(original=original):
                self.assertNotIn(original, self.text)

    def test_a_leftover_secret_fails_without_echoing_it(self):
        responses = real_responses()
        responses["workouts"][0]["exercises"][0]["sets"][0]["unexpected"] = KEY
        with self.assertRaises(ValidationError) as caught:
            anonymise(responses, "salt-1", secrets=[KEY])
        self.assertNotIn(KEY, caught.exception.message)

    def test_an_unknown_collection_is_refused(self):
        with self.assertRaises(ValueError):
            anonymise({"mystery": [{"x": 1}]}, "salt-1")


if __name__ == "__main__":
    unittest.main()
