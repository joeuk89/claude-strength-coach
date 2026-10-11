"""Anonymising recorded Hevy responses into test fixtures (contract C15).

`responses` maps a fixture file stem (`workouts`, `workout_events`,
`routines`, `routine_folders`, `exercise_templates`, `body_measurements`)
to its list of raw items; `user_info` is dropped. Ids become salted fakes,
so joins survive; personal text becomes `Workout N`, `note N` and the like;
every date moves by the same whole number of weeks. The result is checked
for leftovers before it is returned.
"""

import hashlib
import json
import re
import uuid
from datetime import date, timedelta

from coach.errors import ValidationError

STEMS = ("workouts", "workout_events", "routines", "routine_folders", "exercise_templates", "body_measurements")
DROPPED = ("user_info",)
_BUILTIN_TEMPLATE = re.compile(r"^[0-9A-F]{8}$")
_DATED = re.compile(r"^(\d{4}-\d{2}-\d{2})((?:T[0-9:.]+)?(?:Z|[+-]\d{2}:?\d{2})?)$")
_GENERATED = re.compile(r"^(Workout|Routine|Folder|Custom exercise|note) \d+$")
_SYNTHETIC_BODY = {"weight_kg": 80.0, "lean_mass_kg": 64.0, "fat_percent": 18.0}
_SYNTHETIC_DEFAULT = 40.0


class _Anonymiser:
    def __init__(self, salt, responses):
        self.salt = salt
        self.weeks = 1 + int(self._digest("weeks")[:8], 16) % 260
        self.titles = {}
        self.notes = 0
        self.replaced_ids = set()
        self.replaced_text = set()
        templates = responses.get("exercise_templates") or []
        self.custom = {t["id"] for t in templates if t.get("is_custom")}
        self.public_titles = {t.get("title") for t in templates if not t.get("is_custom")}

    def _digest(self, text):
        return hashlib.sha256(f"{self.salt}:{text}".encode("utf-8")).hexdigest()

    def uuid(self, original):
        if original is None:
            return None
        self.replaced_ids.add(str(original))
        return str(uuid.UUID(hex=self._digest(f"id:{original}")[:32], version=4))

    def folder_id(self, original):
        if original is None:
            return None
        return 1_000_000 + int(self._digest(f"folder:{original}")[:12], 16) % 9_000_000

    def title(self, kind, key, original):
        if original:
            self.replaced_text.add(original)
        numbers = self.titles.setdefault(kind, {})
        numbers.setdefault(key, len(numbers) + 1)
        return f"{kind} {numbers[key]}"

    def note(self, original):
        if original is None or original == "":
            return original
        self.replaced_text.add(original)
        self.notes += 1
        return f"note {self.notes}"

    def is_custom(self, template_id):
        return template_id in self.custom or not _BUILTIN_TEMPLATE.fullmatch(str(template_id or ""))

    def exercise(self, item):
        item = dict(item)
        template_id = item.get("exercise_template_id")
        if self.is_custom(template_id):
            item["title"] = self.title("Custom exercise", template_id, item.get("title"))
            item["exercise_template_id"] = self.uuid(template_id)
        else:
            self.public_titles.add(item.get("title"))
        if "notes" in item:
            item["notes"] = self.note(item["notes"])
        return item

    def workout(self, item):
        item = dict(item)
        item["title"] = self.title("Workout", item["id"], item.get("title"))
        item["id"] = self.uuid(item["id"])
        item["routine_id"] = self.uuid(item.get("routine_id"))
        if "description" in item:
            item["description"] = self.note(item["description"])
        item["exercises"] = [self.exercise(e) for e in item.get("exercises") or []]
        return item

    def event(self, item):
        item = dict(item)
        if "workout" in item:
            item["workout"] = self.workout(item["workout"])
        if "id" in item:
            item["id"] = self.uuid(item["id"])
        return item

    def routine(self, item):
        item = dict(item)
        item["title"] = self.title("Routine", item["id"], item.get("title"))
        item["id"] = self.uuid(item["id"])
        item["folder_id"] = self.folder_id(item.get("folder_id"))
        if "notes" in item:
            item["notes"] = self.note(item["notes"])
        item["exercises"] = [self.exercise(e) for e in item.get("exercises") or []]
        return item

    def folder(self, item):
        item = dict(item)
        item["title"] = self.title("Folder", item["id"], item.get("title"))
        item["id"] = self.folder_id(item["id"])
        return item

    def template(self, item):
        if not item.get("is_custom"):
            return dict(item)
        item = dict(item)
        item["title"] = self.title("Custom exercise", item["id"], item.get("title"))
        item["id"] = self.uuid(item["id"])
        return item

    def body(self, index, item):
        out = {}
        for key, value in item.items():
            if key != "date" and isinstance(value, (int, float)) and not isinstance(value, bool):
                value = round(_SYNTHETIC_BODY.get(key, _SYNTHETIC_DEFAULT) + index / 10, 1)
            out[key] = value
        return out

    def shift(self, value):
        if isinstance(value, dict):
            return {key: self.shift(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.shift(item) for item in value]
        if isinstance(value, str):
            match = _DATED.fullmatch(value)
            if match:
                moved = date.fromisoformat(match.group(1)) - timedelta(weeks=self.weeks)
                return moved.isoformat() + match.group(2)
        return value

    def run(self, responses):
        handlers = {
            "workouts": self.workout,
            "workout_events": self.event,
            "routines": self.routine,
            "routine_folders": self.folder,
            "exercise_templates": self.template,
        }
        out = {}
        for stem in STEMS:
            if stem not in responses:
                continue
            items = responses[stem]
            if stem == "body_measurements":
                out[stem] = [self.body(index, item) for index, item in enumerate(items)]
            else:
                out[stem] = [handlers[stem](item) for item in items]
        return self.shift(out)

    def assert_clean(self, out, secrets):
        text = json.dumps(out, ensure_ascii=False)
        values = set()

        def collect(value):
            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
            elif isinstance(value, str):
                values.add(value)

        collect(out)
        problems = []
        if any(secret and secret in text for secret in secrets):
            problems.append("the API key")
        if any(original in text for original in self.replaced_ids):
            problems.append("an original id")
        private = {t for t in self.replaced_text if t not in self.public_titles and not _GENERATED.fullmatch(t)}
        if any(t in values or (len(t) >= 12 and t in text) for t in private):
            problems.append("an original title or note")
        if problems:
            raise ValidationError(
                f"The anonymised fixtures still contain {' and '.join(problems)}; nothing was written."
            )


def anonymise(responses, salt, *, secrets=()):
    unknown = sorted(set(responses) - set(STEMS) - set(DROPPED))
    if unknown:
        raise ValueError(f"no anonymisation rule for {', '.join(unknown)}")
    anonymiser = _Anonymiser(salt, responses)
    out = anonymiser.run(responses)
    anonymiser.assert_clean(out, secrets)
    return out
